import os
import json
import requests
from dotenv import load_dotenv
from moviepy import AudioFileClip, ImageClip, TextClip, CompositeVideoClip, ColorClip
import platform

load_dotenv()

# Get system font path
def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/arial.ttf"
    elif system == "Darwin":  # macOS
        return "/System/Library/Fonts/Supplemental/Arial.ttf"
    else:  # Linux
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

FONT = get_font_path()

TMP = "/github/workspace/tmp"
OUT = os.path.join(TMP, "short.mp4")
w, h = 1080, 1920

# Load script JSON
with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "AI Short")
hook = data.get("hook", "")
bullets = data.get("bullets", [])
cta = data.get("cta", "")
topic = data.get("topic", "abstract")

# Generate background with Pollinations
bg_path = os.path.join(TMP, "bg.jpg")
try:
    prompt = f"A visually appealing vertical 1080x1920 background for a YouTube Shorts video about '{topic}'"
    url = "https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt)
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        with open(bg_path, "wb") as f:
            f.write(response.content)
        print("✅ Background generated with Pollinations")
    else:
        print(f"⚠️ Pollinations request failed with status {response.status_code}, using fallback background")
        bg_path = None
except Exception as e:
    print(f"⚠️ Pollinations background generation failed: {e}")
    bg_path = None

# Load audio
audio = AudioFileClip(os.path.join(TMP, "voice.mp3"))
duration = audio.duration

# Background clip
if not bg_path or not os.path.exists(bg_path):
    bg_clip = ColorClip(size=(w, h), color=(30, 30, 30), duration=duration)
else:
    bg_clip = ImageClip(bg_path).resized(height=h).with_duration(duration)

clips = [bg_clip]

# Hook text
hook_dur = min(3, duration)
if hook:
    hook_txt = (
        TextClip(
            text=hook,
            font=FONT,
            font_size=70,
            color="white",
            method="caption",
            size=(w - 100, None),
            text_align="center"
        )
        .with_duration(hook_dur)
        .with_position(("center", 200))
    )
    clips.append(hook_txt)

# Bullets
remaining = max(0, duration - hook_dur - 2.5)
per = remaining / max(1, len(bullets)) if bullets else 0
y = 850

for i, b in enumerate(bullets):
    if not b:  # Skip empty bullets
        continue
    start = hook_dur + i * per
    t = (
        TextClip(
            text=b,
            font=FONT,
            font_size=56,
            color="white",
            method="caption",
            size=(w - 150, None),
            text_align="center"
        )
        .with_duration(per)
        .with_start(start)
        .with_position(("center", y))
    )
    clips.append(t)

# CTA
if cta:
    cta_txt = (
        TextClip(
            text=cta,
            font=FONT,
            font_size=56,
            color="white",
            method="caption",
            size=(w - 150, None),
            text_align="center"
        )
        .with_duration(2.5)
        .with_start(max(0, duration - 2.5))
        .with_position(("center", h - 250))
    )
    clips.append(cta_txt)

# Compose final video
video = CompositeVideoClip(clips, size=(w, h)).with_audio(audio)
video.write_videofile(
    OUT, 
    fps=24, 
    codec="libx264", 
    audio_codec="aac", 
    threads=2,
    preset='medium'
)

print(f"✅ Saved video to {OUT}")

# Clean up
audio.close()
video.close()
if bg_clip:
    bg_clip.close()
