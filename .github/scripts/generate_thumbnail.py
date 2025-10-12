# .github/scripts/generate_thumbnail.py
import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import platform

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# Get system font path
def get_font_path(size=72):
    system = platform.system()
    font_paths = []
    
    if system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
            "C:/Windows/Fonts/arial.ttf",
        ]
    elif system == "Darwin":  # macOS
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    else:  # Linux (GitHub Actions)
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    
    # Try each font path
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"⚠️ Could not load font {font_path}: {e}")
                continue
    
    # Fallback to default
    print("⚠️ Using default font")
    return ImageFont.load_default()

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

topic = data.get("topic", data.get("title", "AI Short"))
text = topic[:80]

# Generate bg via Pollinations AI (free, no API key needed)
bg_path = os.path.join(TMP, "thumb_bg.png")
try:
    prompt = f"Vibrant eye-catching YouTube thumbnail background for: {topic}, bold colors, high contrast, eye-catching"
    url = "https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt) + "?width=1280&height=720"
    print(f"🎨 Generating thumbnail background...")
    img_data = requests.get(url, timeout=30).content
    with open(bg_path, "wb") as f:
        f.write(img_data)
    print("✅ Background generated with Pollinations")
except Exception as e:
    print(f"⚠️ Pollinations failed ({e}), using solid color fallback")
    # fallback create solid color
    img = Image.new("RGB", (1280, 720), (30, 144, 255))
    img.save(thumb_path)

thumb_path = os.path.join(TMP, "thumbnail.png")
print(f"✅ Saved thumbnail to {thumb_path}")