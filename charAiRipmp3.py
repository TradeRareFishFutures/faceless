"""
Character.ai Voice Line Collector (Firefox) - Fixed 2026
"""

import json
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

# ── CONFIG ─────────────────────────────────────
CHARACTER_URL = "https://character.ai/chat/YOUR_CHARACTER_ID_HERE"  # ← Change this
SCRIPT_FILE   = "script.json"
OUTPUT_DIR    = "output_mp3s"

# Optional: Increase if the character is slow to respond
RESPONSE_TIMEOUT = 45
# ───────────────────────────────────────────────

def load_peter_lines():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Adjust this logic if your JSON structure is different
    speaker = data["characters"][0] if "characters" in data else None
    if speaker:
        return [e["line"] for e in data.get("script", []) if e.get("speaker") == speaker]
    return [e["line"] for e in data.get("script", [])]

def build_driver():
    options = Options()
    
    # Persistent Firefox profile
    profile_path = os.path.join(os.getcwd(), "firefox_profile")
    os.makedirs(profile_path, exist_ok=True)
    
    options.add_argument("-profile")
    options.add_argument(profile_path)

    # === ADD THESE LINES TO FIX THE BINARY ISSUE ===
    possible_binary_locations = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        r"C:\Users\EJ\AppData\Local\Mozilla Firefox\firefox.exe",   # common for user installs
    ]
    
    binary_found = False
    for binary_path in possible_binary_locations:
        if os.path.exists(binary_path):
            options.binary_location = binary_path
            print(f"✓ Using Firefox binary: {binary_path}")
            binary_found = True
            break
    
    if not binary_found:
        print("⚠️  Firefox binary not found in common locations.")
        print("   Please tell me where firefox.exe is located on your PC (or install the regular version).")

    service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_window_size(1400, 1000)
    return driver
    options = Options()
    
    # Use a persistent Firefox profile (recommended)
    profile_path = os.path.join(os.getcwd(), "firefox_profile")
    os.makedirs(profile_path, exist_ok=True)
    
    options.add_argument(f"-profile")
    options.add_argument(profile_path)
    
    # Optional: headless=False so you can see what's happening
    # options.add_argument("--headless")  
    
    service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_window_size(1400, 1000)
    return driver

def get_input_box(driver):
    for sel in ["div[contenteditable='true']", "textarea", "div[role='textbox']"]:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        if els:
            return els[0]
    raise RuntimeError("Input box not found")

def send_line(driver, line):
    box = get_input_box(driver)
    box.click()
    
    # Clear and send text more reliably
    driver.execute_script("arguments[0].innerHTML = '';", box)
    driver.execute_script("arguments[0].innerText = arguments[1];", box, line)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", box)
    time.sleep(0.5)
    box.send_keys(Keys.ENTER)

def count_messages(driver):
    return len(driver.find_elements(By.CSS_SELECTOR, "div[data-message-id], article, [data-testid*='message']"))

def click_voice_button(driver):
    # Updated selectors for 2026 (more flexible)
    selectors = [
        "button[aria-label*='voice' i]",
        "button[aria-label*='play' i]",
        "button[aria-label*='speak' i]",
        "button[data-testid*='voice' i]",
        "button[data-testid*='tts' i]",
        "button svg path[d*='M12']",   # common speaker icon fallback
        "[role='button'] svg[viewBox]", # very generic fallback
    ]
    
    for sel in selectors:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        for btn in btns[-3:]:   # try the last few (most recent messages)
            try:
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(0.3)
                    btn.click()
                    print(f"  ✓ Clicked voice button with selector: {sel}")
                    return True
            except:
                continue
    print("  ⚠️  No voice button found")
    return False

def inject_interceptor(driver):
    driver.execute_script("""
        window._audioUrls = window._audioUrls || [];
        const origOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            if (typeof url === 'string' && /\\.mp3|\\.ogg|\\.wav|\\.m4a|audio/i.test(url)) {
                window._audioUrls.push(url);
            }
            return origOpen.apply(this, arguments);
        };
        
        const origFetch = window.fetch;
        window.fetch = async function(input, init) {
            const url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
            if (typeof url === 'string' && /\\.mp3|\\.ogg|\\.wav|\\.m4a|audio/i.test(url)) {
                window._audioUrls.push(url);
            }
            return origFetch.apply(this, arguments);
        };
    """)

def capture_audio_url(driver, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        urls = driver.execute_script("return window._audioUrls || []")
        if urls:
            url = urls[-1]
            driver.execute_script("window._audioUrls = []")
            return url
        time.sleep(0.6)
    return None

def download_file(url, dest, cookies):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, cookies=cookies, headers=headers, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)

# ── MAIN ───────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        lines = load_peter_lines()
        print(f"Loaded {len(lines)} lines")
    except FileNotFoundError:
        print(f"❌ {SCRIPT_FILE} not found! Please create it or fix the path.")
        return
    except Exception as e:
        print(f"Error loading script: {e}")
        return

    driver = build_driver()

    try:
        print(f"Opening {CHARACTER_URL}")
        driver.get(CHARACTER_URL)

        input("\n>>> Log in manually if needed, make sure voice is enabled for the character, then press Enter to start...\n")

        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true'], textarea")))

        inject_interceptor(driver)
        print("Interceptor injected. Starting collection...\n")

        for idx, line in enumerate(lines, 1):
            print(f"[{idx:03d}/{len(lines)}] {line[:90]}{'...' if len(line)>90 else ''}")

            prev_count = count_messages(driver)
            send_line(driver, line)

            print("  Waiting for response...")
            if not WebDriverWait(driver, RESPONSE_TIMEOUT).until(
                lambda d: count_messages(d) > prev_count
            ):
                print("  Timeout waiting for response. Skipping.")
                continue

            time.sleep(3)  # extra time for voice to become available

            if not click_voice_button(driver):
                print("  Skipping this line.\n")
                continue

            print("  Waiting for audio URL...")
            audio_url = capture_audio_url(driver, timeout=18)
            
            if not audio_url:
                print("  No audio URL captured. Skipping.\n")
                continue

            print(f"  Audio URL captured → {audio_url[:100]}...")
            
            dest = os.path.join(OUTPUT_DIR, f"line_{idx:03d}.mp3")
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            
            download_file(audio_url, dest, cookies)
            print(f"  ✅ Saved → {dest}\n")

            time.sleep(1.5)  # be gentle with the site

    except Exception as e:
        print(f"\nError during execution: {e}")
    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()
        print("Done.")

if __name__ == "__main__":
    main()