import json
from pathlib import Path

def build_manifest(script_path="script.json", audio_dir="output_peter_stewie", out="output_peter_stewie/manifest.json"):
    with open(script_path) as f:
        data = json.load(f)
    
    lines = data["script"]
    manifest = []

    for i, line in enumerate(lines):
        file = f"{audio_dir}/{i:03d}_{line['speaker']}.wav"
        manifest.append({
            "index": i,
            "speaker": line["speaker"],
            "text": line["line"],
            "file": file,
        })

    Path(out).write_text(json.dumps(manifest, indent=2))
    print(f"Built manifest with {len(manifest)} entries → {out}")

if __name__ == "__main__":
    build_manifest()