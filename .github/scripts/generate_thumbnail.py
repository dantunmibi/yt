# .github/scripts/generate_thumbnail.py
import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from time import sleep
import textwrap

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

def get_font_path(size=80, bold=True):
    system = platform.system()
    font_paths = []
    
    if system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/impact.ttf",
        ]
    elif system == "Darwin":
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
        ]
    else:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"⚠️ Could not load font {font_path}: {e}")
    
    print("⚠️ Using default font")
    return ImageFont.load_default()

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "AI Short")
topic = data.get("topic", "trending")
hook = data.get("hook", "")

# ✅ FIXED: Use the SHORTER one between title and hook
if hook and len(hook) > 10:
    # Choose the shorter text for better thumbnail fit
    if len(hook) < len(title):
        display_text = hook
        print(f"🎯 Using SHORTER hook: {display_text}")
    else:
        display_text = title
        print(f"🎯 Using SHORTER title: {display_text}")
else:
    display_text = title
    print(f"📝 Using title (no suitable hook): {display_text}")

print(f"📊 Length comparison - Hook: {len(hook)} chars, Title: {len(title)} chars")

# ✅ FIXED: Better text processing that preserves complete text
def optimize_text_for_thumbnail(text, max_lines=2, max_chars_per_line=24):
    # ✅ FIXED: Define words variable here
    words = text.split()
    """Optimize text for thumbnail display while preserving meaning"""
    print(f"📝 Processing text: {text}")
    
    # Clean text but preserve key elements
    text = text.replace('"', '').replace("'", "")
    text = ' '.join(text.split())  # Remove extra spaces
    
    # If text fits in one line, use it
    if len(text) <= max_chars_per_line:
        return [text]
    
    # Try to find natural break points first
    if "?" in text:
        parts = text.split("?")
        if len(parts) == 2:
            line1 = parts[0] + "?"
            line2 = parts[1].strip()
            if len(line1) <= max_chars_per_line and len(line2) <= max_chars_per_line:
                return [line1, line2]
    
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            line1 = parts[0] + ":"
            line2 = parts[1].strip()
            if len(line1) <= max_chars_per_line and len(line2) <= max_chars_per_line:
                return [line1, line2]
    
    # Smart word-based line breaking
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        
        if len(test_line) <= max_chars_per_line:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
            if len(lines) >= max_lines:
                break
    
    # Add the last line
    if current_line and len(lines) < max_lines:
        lines.append(' '.join(current_line))
    
    # Ensure we don't exceed max lines
    lines = lines[:max_lines]
    
    print(f"📝 Final lines: {lines}")
    return lines

text_lines = optimize_text_for_thumbnail(display_text, max_lines=2, max_chars_per_line=24)

# ✅ FIXED: Correct Hugging Face thumbnail generation
def generate_thumbnail_huggingface(prompt):
    """Generate thumbnail using Hugging Face - FIXED VERSION"""
    try:
        # ✅ Use Stable Diffusion XL (more reliable)
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        
        if not hf_token:
            print("   ⚠️ HUGGINGFACE_API_KEY not set, skipping Hugging Face")
            raise Exception("No Hugging Face API key")
        
        headers = {"Authorization": f"Bearer {hf_token}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": "blurry, low quality, text, watermark, ugly, boring, plain",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": 720,
                "height": 1280,
            }
        }
        
        print(f"🤗 Hugging Face thumbnail: {prompt[:60]}...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
        
        if response.status_code == 200:
            # Verify content
            if len(response.content) > 1000:
                print("   ✅ Hugging Face thumbnail generated")
                return response.content
            else:
                raise Exception("Empty image received")
        
        elif response.status_code == 503:
            print(f"   ⚠️ Model is loading (503), will retry...")
            raise Exception("Model loading")
        
        elif response.status_code == 404:
            print(f"   ❌ Hugging Face 404: Check API key")
            print(f"   💡 Token should start with 'hf_'")
            raise Exception("404 error")
        
        elif response.status_code == 401:
            print(f"   ❌ Hugging Face 401: Invalid token")
            raise Exception("Invalid API token")
        
        else:
            print(f"   ⚠️ Hugging Face error {response.status_code}")
            raise Exception(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Hugging Face thumbnail failed: {e}")
        raise

def generate_thumbnail_pollinations(prompt):
    """Pollinations as backup"""
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=720&height=1280&nologo=true&enhance=true"
        print(f"🌐 Pollinations thumbnail: {prompt[:60]}...")
        response = requests.get(url, timeout=120)
        
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Pollinations thumbnail failed: {e}")
        raise

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=4, max=20))
def generate_thumbnail_bg(topic, title):
    bg_path = os.path.join(TMP, "thumb_bg.png")
    
    # ✅ FIXED: Better prompt for YouTube thumbnails
    prompt = f"YouTube thumbnail style, viral content, trending, {topic}, high contrast, vibrant colors, dramatic lighting, professional photography, no text, cinematic, eye-catching"
    
    providers = [
        ("Hugging Face", generate_thumbnail_huggingface),
        ("Pollinations", generate_thumbnail_pollinations)
    ]
    
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name} for thumbnail...")
            image_content = provider_func(prompt)
            with open(bg_path, "wb") as f:
                f.write(image_content)
            
            # Verify file was created
            if os.path.getsize(bg_path) > 1000:
                print(f"✅ {provider_name} thumbnail generated successfully")
                return bg_path
            else:
                print(f"⚠️ {provider_name} returned empty file")
                
        except Exception as e:
            print(f"⚠️ {provider_name} thumbnail failed: {e}")
            continue

    # 🖼️ Try Unsplash fallback
    def generate_unsplash_fallback(topic, title, bg_path, retries=3, delay=3):
        query = requests.utils.quote(topic or title or "abstract technology")
        base_url = f"https://source.unsplash.com/720x1280/?{query}"

        for attempt in range(1, retries + 1):
            try:
                print(f"🖼️ Unsplash fallback attempt {attempt}/{retries} ({query})...")
                head_resp = requests.head(base_url, allow_redirects=True, timeout=15)
                final_url = head_resp.url
                content_type = head_resp.headers.get("Content-Type", "")

                if "image" not in content_type:
                    print(f"⚠️ Not an image ({content_type}), retrying...")
                    sleep(delay)
                    continue

                response = requests.get(final_url, timeout=30)
                if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                    with open(bg_path, "wb") as f:
                        f.write(response.content)
                    print(f"✅ Unsplash fallback image saved ({final_url})")
                    return bg_path
            except Exception as e:
                print(f"⚠️ Unsplash attempt {attempt} failed: {e}")
                sleep(delay)

        print("⚠️ Unsplash fallback failed after retries")
        return None
    
    # Fallback to gradient
    print("⚠️ All providers failed, using gradient fallback")
    img = Image.new("RGB", (720, 1280), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Create vibrant gradient
    for y in range(1280):
        r = int(30 + (255 - 30) * (y / 1280))
        g = int(144 - (144 - 50) * (y / 1280))
        b = int(255 - (255 - 200) * (y / 1280))
        draw.line([(0, y), (720, y)], fill=(r, g, b))
    
    img.save(bg_path)
    return bg_path

# Generate background
bg_path = generate_thumbnail_bg(topic, title)
img = Image.open(bg_path).convert("RGB")

# Enhance image
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.3)

enhancer = ImageEnhance.Color(img)
img = enhancer.enhance(1.2)

img = img.convert("RGBA")

# ✅ FIXED: Better vignette for text readability
vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
vd = ImageDraw.Draw(vignette)
w, h = img.size

# Draw radial gradient for better text contrast
center_x, center_y = w // 2, h // 2
max_radius = int((w**2 + h**2)**0.5) // 2

for radius in range(0, max_radius, 20):
    alpha = int(100 * (radius / max_radius))
    vd.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        outline=(0, 0, 0, alpha),
        width=30
    )

img = Image.alpha_composite(img, vignette)

draw = ImageDraw.Draw(img)

# ✅ IMPROVED: Dynamic font sizing based on text length
max_chars = max(len(line) for line in text_lines) if text_lines else 0
if max_chars > 15:
    font_size = 60
else:
    font_size = 70

main_font = get_font_path(font_size, bold=True)
w, h = img.size

print("📝 Adding optimized text to thumbnail...")

# Calculate total text height with proper spacing
line_heights = []
for line in text_lines:
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_h = bbox[3] - bbox[1]
    line_heights.append(text_h)

line_spacing = 20
total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing

# Position text in upper third for YouTube Shorts
start_y = h * 0.18  # Slightly higher for better balance

for i, line in enumerate(text_lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (w - text_w) / 2
    y = start_y + sum(line_heights[:i]) + (i * line_spacing)
    
    # ✅ IMPROVED: Better shadow effect
    shadow_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_overlay)
    
    # Multiple shadow layers for better readability
    for offset in [3, 2, 1]:
        shadow_alpha = int(120 * (offset / 3))
        sd.text((x + offset, y + offset), line, font=main_font, fill=(0, 0, 0, shadow_alpha))
    
    img = Image.alpha_composite(img, shadow_overlay)
    
    # ✅ IMPROVED: Thicker stroke for better readability
    stroke_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    so = ImageDraw.Draw(stroke_overlay)
    
    stroke_size = 3
    for adj_x in range(-stroke_size, stroke_size + 1):
        for adj_y in range(-stroke_size, stroke_size + 1):
            if abs(adj_x) == stroke_size or abs(adj_y) == stroke_size:
                so.text((x + adj_x, y + adj_y), line, font=main_font, fill=(0, 0, 0, 200))
    
    img = Image.alpha_composite(img, stroke_overlay)
    
    # ✅ IMPROVED: Bright text with slight glow
    text_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    to = ImageDraw.Draw(text_overlay)
    to.text((x, y), line, font=main_font, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, text_overlay)

# Save final thumbnail
thumb_path = os.path.join(TMP, "thumbnail.png")
final_img = img.convert("RGB")

# Final sharpening
final_img = final_img.filter(ImageFilter.SHARPEN)

final_img.save(thumb_path, quality=95, optimize=True)

print(f"✅ Saved high-quality thumbnail to {thumb_path}")
print(f"   Size: {os.path.getsize(thumb_path) / 1024:.1f} KB")
print(f"   Dimensions: {final_img.size}")
print(f"   Text lines: {len(text_lines)}")
print(f"   Text content: {text_lines}")
print(f"   Font size: {font_size}px")