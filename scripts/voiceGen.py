import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from time import sleep

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]

VOICE_IDS = {
    "Peter": "your_peter_voice_id_here",
    "Stewie": "your_stewie_voice_id_here",
}

def synthesize_line(text, voice_id, output_path):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
        },
    )
    r.raise_for_status()
    Path(output_path).write_bytes(r.content)

def lines_to_audio(lines, out_dir="audio_lines"):
    Path(out_dir).mkdir(exist_ok=True)
    manifest = []

    for i, line in enumerate(lines):
        speaker = line["speaker"]
        text = line["line"]
        voice_id = VOICE_IDS[speaker]
        path = f"{out_dir}/{i:03d}_{speaker}.mp3"

        synthesize_line(text, voice_id, path)
        manifest.append({"index": i, "speaker": speaker, "text": text, "file": path})
        sleep(0.3)  # stay under rate limit

    manifest_path = f"{out_dir}/manifest.json"
    Path(manifest_path).write_text(json.dumps(manifest, indent=2))
    print(f"Done. {len(manifest)} lines → {out_dir}/")
    return manifest

if __name__ == "__main__":
    with open("script.json") as f:
        lines = json.load(f)
    lines_to_audio(lines)