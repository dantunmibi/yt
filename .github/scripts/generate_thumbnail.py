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
    img.save(bg_path)

# Open and process image
img = Image.open(bg_path).convert("RGBA")
draw = ImageDraw.Draw(img)

# Get font
font = get_font_path(72)
print(f"📝 Using font for thumbnail")

w, h = img.size

# Get text size using textbbox (textsize is deprecated)
bbox = draw.textbbox((0, 0), text, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]

x = (w - text_w) / 2
y = (h - text_h) / 2

# Draw rectangle for contrast
rect_pad = 30
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
od.rectangle(
    [x - rect_pad, y - rect_pad, x + text_w + rect_pad, y + text_h + rect_pad],
    fill=(0, 0, 0, 0)
)
img = Image.alpha_composite(img, overlay)

# Draw text with shadow
draw = ImageDraw.Draw(img)
draw.text((x + 3, y + 3), text, font=font, fill="white")  # Shadow
draw.text((x, y), text, font=font, fill="white")  # Main text

# Save thumbnail
thumb_path = os.path.join(TMP, "thumbnail.png")
img.convert("RGB").save(thumb_path)
print(f"✅ Saved thumbnail to {thumb_path}")