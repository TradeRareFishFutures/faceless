"""
Character.ai Voice Ripper - Multi-Speaker Version
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

def load_lines_by_speaker():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    script = data.get("script", [])
    speakers = {}
    
    for entry in script:
        speaker = entry.get("speaker")
        line = entry.get("line")
        if speaker and line:
            if speaker not in speakers:
                speakers[speaker] = []
            speakers[speaker].append(line)
    
    print(f"Loaded {len(speakers)} speakers from script:")
    for speaker, lines in speakers.items():
        print(f"   • {speaker}: {len(lines)} lines")
    print()
    return speakers


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
        window.capturedAudioUrls = [];
        console.log('%c🔧 ADVANCED INTERCEPTOR ACTIVE', 'color: orange; font-weight: bold');

        const origFetch = window.fetch;
        window.fetch = async function(input, init) {
            const url = typeof input === 'string' ? input : (input?.url || '');
            if (url.includes('character-ai-multimodal-memo') || url.endsWith('.mp3')) {
                if (!window.capturedAudioUrls.includes(url)) {
                    window.capturedAudioUrls.push(url);
                    console.log('%c🎤 MP3 CAPTURED', 'color: lime', url);
                }
            }
            return origFetch.apply(this, arguments);
        };

        // Monitor <audio> elements
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                    const el = mutation.target;
                    if (el.tagName === 'AUDIO' || el.tagName === 'SOURCE') {
                        const src = el.src || el.getAttribute('src');
                        if (src && (src.includes('character-ai-multimodal-memo') || src.endsWith('.mp3'))) {
                            if (!window.capturedAudioUrls.includes(src)) {
                                window.capturedAudioUrls.push(src);
                                console.log('%c🎤 MP3 via audio src:', 'color: cyan', src);
                            }
                        }
                    }
                }
            });
        });

        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['src'], subtree: true });
    """)
    print("✅ Advanced interceptor injected")


def find_input_box(driver):
    selectors = ["div[contenteditable='true']", "[role='textbox']", "textarea"]
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


def click_and_download_for_speaker(driver, speaker_name, batch_num):
    print(f"🔍 Clicking voice buttons for {speaker_name}...")
    clicked = 0
    seen = set()

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3.5)

    buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Play voice']")

    for btn in buttons:
        try:
            # Strong unique identifier
            y = int(btn.location.get('y', 0))
            h = int(btn.size.get('height', 0))
            identifier = f"{y}_{h}"

            if identifier in seen:
                continue
            seen.add(identifier)

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.7)

            btn.click()
            clicked += 1
            print(f"  🔊 Clicked voice button #{clicked}")
            time.sleep(2.4)

        except:
            continue

    print(f"Clicked {clicked} voice buttons for {speaker_name}.")

    # Extract URLs
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
    print(f"Found {len(all_urls)} MP3 URLs.")

    # Download
    safe_speaker = "".join(c if c.isalnum() or c in " _-" else "_" for c in speaker_name)
    saved_count = 0
    for i, url in enumerate(all_urls, 1):
        dest = os.path.join(OUTPUT_DIR, f"{safe_speaker}_batch{batch_num}_{i:03d}.mp3")
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
            print(f"  💾 Saved: {os.path.basename(dest)}")
            saved_count += 1
        except Exception as e:
            print(f"  ❌ Failed: {os.path.basename(dest)}")

    print(f"✅ Finished downloading for {speaker_name} ({saved_count} files)\n")


def main():
    speakers = load_lines_by_speaker()
    if not speakers:
        print("No speakers found!")
        return

    driver = build_driver()

    try:
        driver.get(CHARACTER_URL)
        input("\n>>> Log in, enable voice mode, then press Enter to start...\n")

        inject_interceptor(driver)

        batch_num = 1
        for speaker, lines in speakers.items():
            print(f"\n{'='*70}")
            print(f"PROCESSING SPEAKER: {speaker.upper()}  |  {len(lines)} lines")
            print(f"{'='*70}\n")

            # Reset captured URLs for this speaker
            driver.execute_script("window.capturedAudioUrls = [];")

            send_all_lines(driver, lines)

            print(f"Waiting {WAIT_AFTER_ALL_SENT} seconds for responses...")
            time.sleep(WAIT_AFTER_ALL_SENT)

            click_and_download_for_speaker(driver, speaker, batch_num)

            batch_num += 1

            # Pause to let user change voice (except after last speaker)
            if speaker != list(speakers.keys())[-1]:
                input(f"\n>>> Finished voice for '{speaker}'.\n"
                      f">>> Now change the voice to the NEXT character in Character.ai,\n"
                      f">>> then press Enter to continue...\n")

        print("\n🎉 All speakers have been processed successfully!")

    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()