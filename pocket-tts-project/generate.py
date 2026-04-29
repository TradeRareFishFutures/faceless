import json
from pathlib import Path
import subprocess
import re

# ========================= CONFIG =========================
SCRIPT_FILE = "script.json"
OUTPUT_DIR = Path("output_peter_stewie")

REFERENCES = {
    "Peter":  "references/peter.safetensors",
    "Stewie": "references/stewie.safetensors"
}

# Use venv Python (critical on Windows)
VENV_PYTHON = Path("venv/Scripts/python.exe").resolve()

OUTPUT_DIR.mkdir(exist_ok=True)

with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"🎤 Starting generation of {len(data['script'])} lines...")
print(f"Using Python: {VENV_PYTHON}\n")

for i, entry in enumerate(data["script"]):
    speaker = entry.get("speaker")
    text = entry.get("line", "").strip()
    
    ref_path = REFERENCES.get(speaker)
    if not ref_path or not Path(ref_path).exists():
        print(f"⚠️  Missing reference for {speaker} → skipping")
        continue
    
    filename_base = f"{i:03d}_{speaker}"
    preview = (text[:78] + "...") if len(text) > 78 else text
    print(f"[{i+1:2d}/{len(data['script'])}] {speaker}: {preview}")

    # ------------------- Chunk long lines -------------------
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = []
    current_len = 0
    MAX_CHARS = 165

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if current_len + len(sent) > MAX_CHARS and current:
            chunks.append(' '.join(current))
            current = [sent]
            current_len = len(sent)
        else:
            current.append(sent)
            current_len += len(sent) + 1

    if current:
        chunks.append(' '.join(current))

    if len(chunks) == 1 and len(text) < 190:
        chunks = [text]

    # ------------------- Generate each chunk -------------------
    for j, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
            
        suffix = f"_{j:02d}" if len(chunks) > 1 else ""
        output_file = f"{filename_base}{suffix}.wav"
        output_path = OUTPUT_DIR / output_file

        print(f"   └─ Chunk {j+1}/{len(chunks)} → {output_file}", end=" ")

        try:
            subprocess.run([
                str(VENV_PYTHON),
                "-m", "pocket_tts",
                "generate",
                "--text", chunk,
                "--voice", str(ref_path),
                "--output-path", str(output_path),   # ← Fixed: --output-path
                "--language", "english"
            ], check=True, capture_output=True, text=True, timeout=90)

            print("✅ Done")
            
        except subprocess.CalledProcessError as e:
            print("❌ Failed")
            if e.stderr:
                print(f"      → {e.stderr.strip()[-450:]}")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")

print("\n🎉 Generation finished!")
print(f"Files are in: {OUTPUT_DIR.resolve()}")