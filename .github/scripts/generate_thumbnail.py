# .github/scripts/generate_thumbnail.py
import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from time import sleep

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

text = title[:80]

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
                "negative_prompt": "blurry, low quality, text, watermark, ugly",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": 1080,
                "height": 1920,
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
    prompt = f"YouTube thumbnail style, vibrant explosive colors, high contrast, eye-catching, dramatic, professional, about: {topic} - {title}, no text"
    
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
        query = requests.utils.quote(topic or title or "abstract")
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
    img = Image.new("RGB", (1280, 720), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    for y in range(720):
        r = int(30 + (255 - 30) * (y / 720))
        g = int(144 - (144 - 50) * (y / 720))
        b = int(255 - (255 - 200) * (y / 720))
        draw.line([(0, y), (1280, y)], fill=(r, g, b))
    
    img.save(bg_path)
    return bg_path

bg_path = generate_thumbnail_bg(topic, title)

img = Image.open(bg_path).convert("RGB")

enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.3)

enhancer = ImageEnhance.Color(img)
img = enhancer.enhance(1.2)

img = img.convert("RGBA")

vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
vd = ImageDraw.Draw(vignette)
w, h = img.size

for i in range(150):
    alpha = int((i / 150) * 120)
    vd.rectangle([i, i, w-i, h-i], outline=(0, 0, 0, alpha))

img = Image.alpha_composite(img, vignette)

draw = ImageDraw.Draw(img)

main_font = get_font_path(85, bold=True)
subtitle_font = get_font_path(45, bold=False)

words = text.split()
lines = []
current_line = []

for word in words:
    current_line.append(word)
    test_line = " ".join(current_line)
    bbox = draw.textbbox((0, 0), test_line, font=main_font)
    text_w = bbox[2] - bbox[0]
    
    if text_w > w - 200:
        current_line.pop()
        lines.append(" ".join(current_line))
        current_line = [word]

if current_line:
    lines.append(" ".join(current_line))

lines = lines[:2]

total_height = sum([draw.textbbox((0, 0), line, font=main_font)[3] - draw.textbbox((0, 0), line, font=main_font)[1] for line in lines])
total_height += (len(lines) - 1) * 20

start_y = (h - total_height) / 2

print("📝 Adding text to thumbnail...")
for i, line in enumerate(lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (w - text_w) / 2
    y = start_y + i * (text_h + 20)
    
    for offset in range(6, 0, -1):
        shadow_alpha = int(255 * (offset / 6) * 0.5)
        shadow_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_overlay)
        sd.text((x + offset, y + offset), line, font=main_font, fill=(0, 0, 0, shadow_alpha))
        img = Image.alpha_composite(img, shadow_overlay)
    
    stroke_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    so = ImageDraw.Draw(stroke_overlay)
    
    for adj_x in range(-3, 4):
        for adj_y in range(-3, 4):
            if adj_x != 0 or adj_y != 0:
                so.text((x + adj_x, y + adj_y), line, font=main_font, fill=(0, 0, 0, 255))
    
    img = Image.alpha_composite(img, stroke_overlay)
    
    text_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    to = ImageDraw.Draw(text_overlay)
    to.text((x, y), line, font=main_font, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, text_overlay)

thumb_path = os.path.join(TMP, "thumbnail.png")
final_img = img.convert("RGB")

final_img = final_img.filter(ImageFilter.SHARPEN)

final_img.save(thumb_path, quality=95, optimize=True)

print(f"✅ Saved high-quality thumbnail to {thumb_path}")
print(f"   Size: {os.path.getsize(thumb_path) / 1024:.1f} KB")
print(f"   Dimensions: {final_img.size}")