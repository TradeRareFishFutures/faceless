import whisper
import json
from pathlib import Path
import sys

# ========================= CONFIG =========================
MODEL_SIZE = "base"                    # "tiny", "base", "small"
MANIFEST_PATH = Path("output_peter_stewie/manifest.json")
# =========================================================

def main():
    print(f"Loading Whisper model '{MODEL_SIZE}'...")

    try:
        model = whisper.load_model(MODEL_SIZE)
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        sys.exit(1)

    if not MANIFEST_PATH.exists():
        print(f"❌ Manifest not found: {MANIFEST_PATH}")
        print("   Please make sure you have run your generation script first.")
        return

    print(f"Loading manifest: {MANIFEST_PATH.name}")

    # Try multiple encodings to handle bad characters
    manifest = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin1"]:
        try:
            with open(MANIFEST_PATH, "r", encoding=encoding) as f:
                manifest = json.load(f)
            print(f"   Loaded successfully using {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            print(f"   JSON error with {encoding}: {e}")
            continue

    if manifest is None:
        print("❌ Failed to load manifest with any encoding.")
        return

    print(f"Found {len(manifest)} audio files to transcribe...\n")

    for i, entry in enumerate(manifest):
        audio_file = Path(entry.get("file", ""))
        
        if not audio_file.exists():
            print(f"[{i+1:2d}/{len(manifest)}] ⚠️  File not found: {audio_file.name}")
            continue

        print(f"[{i+1:2d}/{len(manifest)}] Transcribing: {audio_file.name} ...", end=" ")

        try:
            result = model.transcribe(
                str(audio_file),
                word_timestamps=True,
                language="en"
            )

            words = []
            for segment in result.get("segments", []):
                for word in segment.get("words", []):
                    words.append({
                        "word": word["word"].strip(),
                        "start": round(float(word["start"]), 3),
                        "end": round(float(word["end"]), 3),
                    })

            entry["words"] = words
            print("✅")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Save back with proper encoding
    try:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n🎉 Success! Updated manifest saved to {MANIFEST_PATH.name}")
    except Exception as e:
        print(f"\n❌ Failed to save manifest: {e}")

if __name__ == "__main__":
    main()