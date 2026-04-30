import json
import random
import os
from pathlib import Path
from moviepy import (
    VideoFileClip, AudioFileClip, concatenate_audioclips,
    CompositeVideoClip, TextClip, ColorClip, concatenate_videoclips
)

BACKGROUND_DIR = "backgrounds"
OUTPUT_PATH = "output_final/final_video.mp4"
FONT = "C:/Windows/Fonts/arialbd.ttf"
FONT_SIZE = 70
CAPTION_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 3
VIDEO_SIZE = (1080, 1920)  # 9:16 vertical

def load_manifest(path="output_peter_stewie/manifest.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_random_background(duration):
    clips = list(Path(BACKGROUND_DIR).glob("*.mp4")) + list(Path(BACKGROUND_DIR).glob("*.mov"))
    if not clips:
        raise FileNotFoundError(f"No video files found in {BACKGROUND_DIR}/")
    path = str(random.choice(clips))
    clip = VideoFileClip(path).without_audio()
    # rotate landscape to portrait
    clip = clip.resized(height=1920)
    # center crop to 1080 wide
    x_center = clip.w / 2
    clip = clip.cropped(x1=x_center - 540, x2=x_center + 540)
        # loop if shorter than needed
    if clip.duration < duration:
        times = int(duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * times)
    return clip.subclipped(0, duration)

def build_caption_clips(manifest, words_per_caption=2):
    captions = []
    all_chunks = []

    # collect all chunks first
    for entry in manifest:
        if "words" not in entry:
            continue
        words = entry["words"]
        i = 0
        while i < len(words):
            chunk = words[i:i + words_per_caption]
            all_chunks.append({
                "text": " ".join(w["word"] for w in chunk),
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
            })
            i += words_per_caption

    # build clips — active chunk is yellow, others invisible
    for idx, chunk in enumerate(all_chunks):
        duration = chunk["end"] - chunk["start"]
        if duration <= 0:
            continue

        # active (highlighted) caption
        active = (TextClip(text=chunk["text"], font_size=FONT_SIZE, font=FONT,
                        color="yellow", stroke_color=STROKE_COLOR,
                        stroke_width=STROKE_WIDTH)
                    .with_start(chunk["start"])
                    .with_duration(duration)
                    .with_position(("center", 0.75), relative=True))
        captions.append(active)

    return captions
def assemble():
    Path("output_final").mkdir(exist_ok=True)
    manifest = load_manifest()

    # stitch audio
    audio_clips = [AudioFileClip(e["file"]) for e in manifest]
    full_audio = concatenate_audioclips(audio_clips)
    total_duration = full_audio.duration

    # build caption timestamps relative to full timeline
    offset = 0
    for entry in manifest:
        if "words" in entry:
            for w in entry["words"]:
                w["start"] += offset
                w["end"] += offset
        audio = AudioFileClip(entry["file"])
        offset += audio.duration
        audio.close()

    # background
    bg = get_random_background(total_duration)

    # captions
    captions = build_caption_clips(manifest)

    # composite
    final = CompositeVideoClip([bg] + captions).with_audio(full_audio)
    final = final.subclipped(0, total_duration)

    print(f"Rendering {total_duration:.1f}s video...")
    final.write_videofile(OUTPUT_PATH, fps=30, codec="libx264", audio_codec="aac")
    print(f"Done → {OUTPUT_PATH}")

if __name__ == "__main__":
    assemble()