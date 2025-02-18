import atexit, sys, time, threading, traceback, socket
import undetected_chromedriver as uc
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import requests
from flask import Flask, request, jsonify

provider_api_url = None
api_server_thread = None

options = uc.ChromeOptions()
options.add_argument("--user-data-dir=C:\\Users\\IpSpyer\\AppData\\Local\\Google\\Chrome\\User Data")
options.add_argument("--profile-directory=Default")

try:
    driver = uc.Chrome(options=options, version_main=132)
except Exception as e:
    sys.exit(f"Error starting undetected-chromedriver: {e}")

def cleanup_driver():
    try:
        driver.quit()
    except Exception as e:
        print(f"Error during driver cleanup: {e}", file=sys.stderr)
atexit.register(cleanup_driver)
driver.get("https://chatgpt.com")

def send_message(message):
    element = None
    try:
        element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//p[@data-placeholder='Message ChatGPT']"))
        )
        print("DEBUG: Found input element with data-placeholder.")
    except Exception as e:
        print("DEBUG: Could not find element with data-placeholder; trying fallback...", file=sys.stderr)
        traceback.print_exc()
    if not element:
        try:
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='textbox']"))
            )
            print("DEBUG: Found input element with role='textbox'.")
        except Exception as e:
            print("ERROR: No input element found.", file=sys.stderr)
            traceback.print_exc()
            return
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        driver.execute_script(
            "arguments[0].focus(); "
            "arguments[0].innerText = arguments[1]; "
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
            element, message
        )
        time.sleep(0.5)
        driver.execute_script(
            "var elem = arguments[0]; "
            "var eventDown = new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}); "
            "var eventUp = new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}); "
            "elem.dispatchEvent(eventDown); "
            "elem.dispatchEvent(eventUp);",
            element
        )
        print("DEBUG: Message sent successfully.")
    except Exception as e:
        print("ERROR: Failed to send web message.", file=sys.stderr)
        traceback.print_exc()

def get_current_response_text():
    xpath = "//p[@data-start and @data-end]"
    try:
        response_elements = driver.find_elements(By.XPATH, xpath)
        texts = []
        for elem in response_elements:
            try:
                t = elem.text.strip()
                if t:
                    texts.append(t)
            except StaleElementReferenceException:
                continue
        return "\n".join(texts)
    except Exception as e:
        print("DEBUG: Error fetching response texts:", e, file=sys.stderr)
        return ""

def get_last_response(timeout=60):
    xpath = "//p[@data-start and @data-end]"
    initial_text = get_current_response_text()
    print("DEBUG: Initial response:", initial_text)
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            current_text = get_current_response_text()
            if current_text and current_text != initial_text:
                print("DEBUG: New response detected:", current_text)
                return current_text
        except Exception as e:
            print("DEBUG: Exception while checking response:", e, file=sys.stderr)
        time.sleep(1)
    print("DEBUG: Timeout waiting for new response.")
    return "(No response received)"

def run_api_server():
    app = Flask(__name__)

    @app.route('/chat', methods=['POST'])
    def chat():
        data = request.get_json()
        msg = data.get("message", "")
        if not msg:
            return jsonify({"error": "No message provided"}), 400
        send_message(msg)
        resp = get_last_response()
        return jsonify({"response": resp})

    app.run(host='0.0.0.0', port=5000)

def send_message_api_provider(message):
    try:
        response = requests.post(provider_api_url, json={"message": message})
        if response.status_code == 200:
            data = response.json()
            return data.get("response", "(No response received)")
        else:
            return f"(Error: {response.status_code})"
    except Exception as e:
        print("ERROR: API call failed.", e)
        return "(API error)"

def process_message(user_message):
    if provider_api_url:
        response = send_message_api_provider(user_message)
    else:
        send_message(user_message)
        response = get_last_response()
    print("DEBUG: Final response for GUI:", response)
    root.after(0, update_chat_display, "GPT: " + response)

root = tk.Tk()
root.title("ChatGPT GUI")

disclaimer_label = tk.Label(
    root, 
    text="This app is worldwide but because of I don't have a server its accessible to everyone including bad minded persons"
)
disclaimer_label.pack(padx=10, pady=(5, 5))

chat_display = ScrolledText(root, state='disabled', wrap='word', width=80, height=20)
chat_display.pack(padx=10, pady=10)

input_field = tk.Entry(root, width=80)
input_field.pack(padx=10, pady=(0, 10))

def update_chat_display(message):
    chat_display.configure(state='normal')
    chat_display.insert(tk.END, message + "\n")
    chat_display.configure(state='disabled')
    chat_display.yview(tk.END)

def send_button_pressed():
    user_message = input_field.get().strip()
    if not user_message:
        return
    update_chat_display("You: " + user_message)
    input_field.delete(0, tk.END)
    threading.Thread(target=process_message, args=(user_message,), daemon=True).start()

send_button = tk.Button(root, text="Send", command=send_button_pressed)
send_button.pack(padx=10, pady=(0, 10))

api_server_thread = None

def generate_api():
    global api_server_thread
    if not api_server_thread:
        api_server_thread = threading.Thread(target=run_api_server, daemon=True)
        api_server_thread.start()
        ip = socket.gethostbyname(socket.gethostname())
        update_chat_display(f"API generated at: http://{ip}:5000/chat (if port 5000 is open to the internet)")
    else:
        update_chat_display("API already generated.")

gen_api_button = tk.Button(root, text="Generate API", command=generate_api)
gen_api_button.pack(padx=10, pady=(0, 10))

def open_provider_api_settings():
    def save_provider_api():
        global provider_api_url
        url = api_entry.get().strip()
        if url:
            provider_api_url = url
            update_chat_display("Using provider API: " + url)
        settings_window.destroy()
    settings_window = tk.Toplevel(root)
    settings_window.title("Provider API Settings")
    tk.Label(settings_window, text="Enter Provider API URL:").pack(padx=10, pady=10)
    api_entry = tk.Entry(settings_window, width=50)
    api_entry.pack(padx=10, pady=5)
    save_button = tk.Button(settings_window, text="Save", command=save_provider_api)
    save_button.pack(padx=10, pady=10)

insert_api_button = tk.Button(root, text="Insert Provider API", command=open_provider_api_settings)
insert_api_button.pack(padx=10, pady=(0, 10))

root.mainloop()
