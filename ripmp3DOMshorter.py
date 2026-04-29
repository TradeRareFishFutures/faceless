"""
Character.ai Voice Ripper - Clean Version (Good Sending + Button Clicking)
"""

import json
import os
import time
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# ── CONFIG ─────────────────────────────────────
CHARACTER_URL = "https://character.ai/chat/-O4Q26x5XkWtJ5vdvQzxiYbRoiCWRiCK2y6gXoWHPBg"
SCRIPT_FILE   = "dialog/script.json"
OUTPUT_DIR    = "output_mp3s"

WAIT_BETWEEN_SEND = 5
WAIT_AFTER_ALL_SENT = 15
# ───────────────────────────────────────────────

def load_lines():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    speaker = data.get("characters", [None])[0]
    return [e["line"] for e in data.get("script", []) if e.get("speaker") == speaker]

def build_driver():
    options = Options()
    options.add_argument("--start-maximized")
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def inject_interceptor(driver):
    driver.execute_script("""
        window.capturedAudioUrls = window.capturedAudioUrls || [];
        console.log('%c🔧 ADVANCED INTERCEPTOR ACTIVE', 'color: orange; font-weight: bold');

        // 1. Override fetch (you already had this)
        const origFetch = window.fetch;
        window.fetch = async function(input, init) {
            const url = typeof input === 'string' ? input : (input?.url || '');
            if (url.includes('character-ai-multimodal-memo') || url.endsWith('.mp3')) {
                console.log('%c🎤 MP3 via fetch:', 'color: lime', url);
                if (!window.capturedAudioUrls.includes(url)) {
                    window.capturedAudioUrls.push(url);
                }
            }
            return origFetch.apply(this, arguments);
        };

        // 2. Catch <audio> elements src changes (very common for voice)
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                    const el = mutation.target;
                    if (el.tagName === 'AUDIO' || el.tagName === 'SOURCE') {
                        const src = el.src || el.getAttribute('src');
                        if (src && (src.includes('character-ai-multimodal-memo') || src.endsWith('.mp3'))) {
                            console.log('%c🎤 MP3 via <audio> src:', 'color: cyan', src);
                            if (!window.capturedAudioUrls.includes(src)) {
                                window.capturedAudioUrls.push(src);
                            }
                        }
                    }
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['src'],
            subtree: true
        });

        // 3. Also monitor for new audio elements being added
        const nodeObserver = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {  // Element node
                        const audios = node.tagName === 'AUDIO' ? [node] : node.querySelectorAll ? node.querySelectorAll('audio, source') : [];
                        audios.forEach(audio => {
                            const src = audio.src || audio.getAttribute('src');
                            if (src && (src.includes('character-ai-multimodal-memo') || src.endsWith('.mp3'))) {
                                console.log('%c🎤 MP3 via new <audio>:', 'color: magenta', src);
                                if (!window.capturedAudioUrls.includes(src)) {
                                    window.capturedAudioUrls.push(src);
                                }
                            }
                        });
                    }
                });
            });
        });

        nodeObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });

        console.log('%c✅ MutationObservers + fetch interceptor ready', 'color: lime');
    """)
    print("✅ Advanced interceptor injected (fetch + audio src observers)")
    
    driver.execute_script("""
        window.capturedAudioUrls = [];
        console.log('%c🔧 INTERCEPTOR ACTIVE', 'color: orange; font-weight: bold');

        const origFetch = window.fetch;
        window.fetch = async function(input, init) {
            const url = typeof input === 'string' ? input : (input?.url || '');
            if (url.includes('character-ai-multimodal-memo') && url.endsWith('.mp3')) {
                console.log('%c🎤 MP3 CAPTURED', 'color: lime', url);
                if (!window.capturedAudioUrls.includes(url)) {
                    window.capturedAudioUrls.push(url);
                }
            }
            return origFetch.apply(this, arguments);
        };
    """)
    print("✅ Interceptor injected")

def find_input_box(driver):
    selectors = [
        "div[contenteditable='true']",
        "[role='textbox']",
        "textarea"
    ]
    for sel in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if el.is_displayed():
                    return el
        except:
            continue
    return None

def send_all_lines(driver, lines):
    print(f"Sending {len(lines)} lines...")
    for idx, line in enumerate(lines, 1):
        box = find_input_box(driver)
        if not box:
            print(f"  ❌ Input box not found for line {idx}")
            time.sleep(3)
            continue

        try:
            box.click()
            time.sleep(0.5)
            box.send_keys(Keys.CONTROL + "a")
            time.sleep(0.3)
            box.send_keys(Keys.DELETE)
            time.sleep(0.4)

            box.send_keys("!Re " + line)
            time.sleep(0.6)
            box.send_keys(Keys.ENTER)

            print(f"  ✓ Sent line {idx}")
            time.sleep(WAIT_BETWEEN_SEND)
        except Exception as e:
            print(f"  ❌ Failed sending line {idx}: {e}")
    print("All lines sent.\n")
def click_all_voice_buttons(driver, expected_new_buttons=0):
    print(f"🔍 Clicking 'Play voice' buttons (expecting ~{expected_new_buttons} new ones)...")
    clicked = 0
    seen = set()

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3.5)

    buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Play voice']")

    for btn in buttons:
        try:
            # More stable unique identifier
            rect = btn.rect  # Contains x, y, width, height
            identifier = f"{rect['y']:.0f}_{rect['height']:.0f}_{btn.get_attribute('outerHTML')[:80]}"

            if identifier in seen:
                continue

            seen.add(identifier)

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.6)

            btn.click()
            clicked += 1
            print(f"  🔊 Clicked voice button #{clicked}")

            time.sleep(2.4)   # Let the audio request fire

        except:
            continue

    print(f"✅ Clicked total of {clicked} voice buttons.\n")
    return clicked


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    lines = load_lines()
    print(f"Loaded {len(lines)} lines.\n")

    driver = build_driver()

    try:
        driver.get(CHARACTER_URL)
        input("\n>>> Log in, enable voice, then press Enter to start...\n")

        inject_interceptor(driver)

        # === Count existing voice buttons BEFORE sending lines ===
        print("Counting existing voice buttons...")
        before_buttons = len(driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Play voice']"))
        print(f"   Found {before_buttons} voice buttons before sending.\n")

        # Send the lines
        send_all_lines(driver, lines)

        print(f"Waiting {WAIT_AFTER_ALL_SENT} seconds for responses...")
        time.sleep(WAIT_AFTER_ALL_SENT)

        # Click only the NEW voice buttons
        click_all_voice_buttons(driver, expected_new_buttons=len(lines))

        # === Extract captured MP3 URLs ===
        captured = driver.execute_script("return window.capturedAudioUrls || []")

        extra_urls = driver.execute_script("""
            const urls = [];
            document.querySelectorAll('audio, source').forEach(el => {
                let src = el.src || el.getAttribute('src') || '';
                if (src && (src.includes('character-ai-multimodal-memo') || src.endsWith('.mp3'))) {
                    if (!urls.includes(src)) urls.push(src);
                }
            });
            return urls;
        """)

        all_urls = list(dict.fromkeys(captured + extra_urls))

        print(f"\nFound {len(all_urls)} unique MP3 URLs.")

        # Download in order (important!)
        for i, url in enumerate(all_urls, 1):
            dest = os.path.join(OUTPUT_DIR, f"line_{i:03d}.mp3")
            try:
                r = requests.get(url, timeout=45)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    f.write(r.content)
                print(f"  💾 Saved: line_{i:03d}.mp3")
            except Exception as e:
                print(f"  ❌ Failed line_{i:03d}: {e}")

        print("\nScript finished.")

    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()

if __name__ == "__main__":
    main()