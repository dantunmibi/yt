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
import random

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
def optimize_text_for_thumbnail(text, max_lines=3, max_chars_per_line=18):
    """Optimize text for thumbnail display while preserving ALL text"""
    print(f"📝 Processing text: {text}")
    
    # Clean text but preserve key elements
    text = text.replace('"', '').replace("'", "")
    text = ' '.join(text.split())  # Remove extra spaces
    
    words = text.split()
    
    # If text is very short, use as-is
    if len(text) <= max_chars_per_line:
        return [text]
    
    # Try to find natural break points first (for 2-line splits)
    if "?" in text and max_lines >= 2:
        parts = text.split("?", 1)  # Split only on first ?
        if len(parts) == 2:
            line1 = parts[0] + "?"
            line2 = parts[1].strip()
            # Check if both lines fit
            if len(line1) <= max_chars_per_line and line2:
                # If line2 fits, we're done
                if len(line2) <= max_chars_per_line:
                    return [line1, line2] if line2 else [line1]
                # Otherwise, split line2 further
                else:
                    remaining_words = line2.split()
                    result = [line1]
                    current_line = []
                    for word in remaining_words:
                        test_line = ' '.join(current_line + [word])
                        if len(test_line) <= max_chars_per_line:
                            current_line.append(word)
                        else:
                            if current_line:
                                result.append(' '.join(current_line))
                            current_line = [word]
                    if current_line:
                        result.append(' '.join(current_line))
                    return result[:max_lines]
    
    if ":" in text and max_lines >= 2:
        parts = text.split(":", 1)
        if len(parts) == 2:
            line1 = parts[0] + ":"
            line2 = parts[1].strip()
            if len(line1) <= max_chars_per_line and line2:
                if len(line2) <= max_chars_per_line:
                    return [line1, line2] if line2 else [line1]
    
    # Smart word-based line breaking - PRESERVE ALL TEXT
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        
        if len(test_line) <= max_chars_per_line:
            current_line.append(word)
        else:
            # Save current line and start new one
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    # ✅ CRITICAL FIX: Add the remaining words even if we hit max_lines
    if current_line:
        lines.append(' '.join(current_line))
    
    # If we have too many lines, try to condense
    if len(lines) > max_lines:
        print(f"⚠️ Text needs {len(lines)} lines, condensing to {max_lines}...")
        # Try to merge last lines or use ellipsis if needed
        if max_lines == 2:
            # Keep first line, merge rest with ellipsis if needed
            remaining = ' '.join(lines[1:])
            if len(remaining) > max_chars_per_line * 2:
                # Truncate intelligently - keep the punchline if possible
                words_remaining = remaining.split()
                line2_words = []
                line3_words = []
                
                # Fill line 2
                for word in words_remaining[:len(words_remaining)//2]:
                    test = ' '.join(line2_words + [word])
                    if len(test) <= max_chars_per_line:
                        line2_words.append(word)
                    else:
                        break
                
                # Fill line 3 with remaining (prioritize end words for punchline)
                for word in words_remaining[len(line2_words):]:
                    test = ' '.join(line3_words + [word])
                    if len(test) <= max_chars_per_line:
                        line3_words.append(word)
                
                return [lines[0], ' '.join(line2_words), ' '.join(line3_words)][:max_lines]
            else:
                lines = [lines[0]] + [remaining]
        
        lines = lines[:max_lines]
    
    print(f"📝 Final lines ({len(lines)}): {lines}")
    return lines

text_lines = optimize_text_for_thumbnail(display_text, max_lines=3, max_chars_per_line=22)

# ✅ FIXED: Correct Hugging Face thumbnail generation
def generate_thumbnail_huggingface(prompt):
    """Generate thumbnail using Hugging Face (with multiple free model fallbacks)"""
    try:
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        if not hf_token:
            print("⚠️ No HUGGINGFACE_API_KEY found — skipping Hugging Face")
            raise Exception("Missing token")

        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": "blurry, low quality, watermark, text, logo, frame, ugly, dull",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": 720,
                "height": 1280,
            }
        }

        # List of models to try, in order
        models = [
            "stabilityai/stable-diffusion-xl-base-1.0",  # Paid (best quality)
            "prompthero/openjourney-v4",                    # Free (fast + decent)
            "Lykon/dreamshaper-xl-v2-turbo",             # Free (creative, solid)
            "runwayml/stable-diffusion-v1-5",
            "stabilityai/sdxl-turbo"
        ]

        for model in models:
            url = f"https://api-inference.huggingface.co/models/{model}"
            print(f"🤗 Trying model: {model}")

            response = requests.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code == 200 and len(response.content) > 1000:
                print(f"✅ Hugging Face model succeeded: {model}")
                return response.content

            elif response.status_code == 402:
                print(f"💰 {model} requires payment — moving to next model...")
                continue

            elif response.status_code in [503, 429]:
                print(f"⌛ {model} is loading or rate-limited — trying next...")
                continue

            else:
                print(f"⚠️ {model} failed ({response.status_code}) — trying next model...")

        # If no model worked
        raise Exception("All Hugging Face models failed")

    except Exception as e:
        print(f"⚠️ Hugging Face thumbnail generation failed: {e}")
        raise


def generate_thumbnail_pollinations(prompt):
    """Pollinations backup with anti-logo filter and unique seed"""
    try:
        # Strong negative prompt to avoid logos, text, UI, and play buttons
        negative_terms = (
            "youtube logo, play button, watermark, ui, interface, overlay, "
            "branding, text, caption, words, title, subtitle, watermarking, "
            "frame, icon, symbol, graphics, arrows, shapes, low quality, distorted"
        )

        # Encourage a clean photo-realistic cinematic look
        formatted_prompt = (
            f"{prompt}, cinematic lighting, ultra detailed, professional digital art, "
            "photo realistic, no text, no logos, no overlays"
        )

        seed = random.randint(1, 999999)

        url = (
            "https://image.pollinations.ai/prompt/"
            f"{requests.utils.quote(formatted_prompt)}"
            f"?width=720&height=1280"
            f"&negative={requests.utils.quote(negative_terms)}"
            f"&nologo=true&notext=true&enhance=true&clean=true"
            f"&seed={seed}&rand={seed}"
        )

        print(f"🌐 Pollinations thumbnail: {prompt[:60]}... (seed={seed})")
        response = requests.get(url, timeout=120)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            print(f"   ✅ Pollinations image generated (seed {seed})")
            return response.content
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")

    except Exception as e:
        print(f"⚠️ Pollinations thumbnail failed: {e}")
        raise




def generate_picsum_fallback(bg_path, topic=None, title=None):
    """
    Smart keyword-based fallback (no API keys).
    Order:
      1️⃣ Unsplash keyword (free, no key)
      2️⃣ Pexels CDN curated fallback
      3️⃣ Picsum random
    """
    import re, random, requests

    # --- 🔍 Step 1: Determine keyword from topic/title ---
    topic_map = {
        "ai": "ai",
        "artificial intelligence": "ai",
        "psychology": "psychology",
        "science": "science",
        "business": "business",
        "money": "money",
        "finance": "money",
        "technology": "technology",
        "tech": "technology",
        "nature": "nature",
        "travel": "travel",
        "people": "people",
        "food": "food",
        "motivation": "people",
        "self improvement": "psychology",
        "creativity": "ai",
    }

    text_source = (title or topic or "").lower()
    resolved_key = next((mapped for word, mapped in topic_map.items() if word in text_source), "abstract")

    print(f"🔎 Searching fallback image for topic '{topic}' (resolved key: '{resolved_key}')...")

    # --- 🔹 Step 2: Try Unsplash (free, no API key) ---
    try:
        seed = random.randint(1, 9999)
        url = f"https://source.unsplash.com/720x1280/?{requests.utils.quote(resolved_key)}&sig={seed}"
        print(f"🖼️ Unsplash fallback for '{resolved_key}' (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Unsplash image saved for '{resolved_key}'")
            return bg_path
        else:
            print(f"   ⚠️ Unsplash failed ({response.status_code})")
    except Exception as e:
        print(f"   ⚠️ Unsplash error: {e}")

    # --- 🔹 Step 3: Try Pexels CDN curated fallback ---
    try:
        curated = {
            "ai": [8386440, 8386442, 1671643, 3184325],
            "technology": [3861959, 3184325, 1671643, 4974912],
            "science": [356056, 3184325, 1671643, 586339],
            "psychology": [3184325, 8386440, 3861959, 7952404],
            "money": [4386321, 3183150, 394372, 4386375],
            "business": [3183150, 394372, 3184325, 267614],
            "nature": [34950, 3222684, 2014422, 590041],
            "travel": [346885, 3222684, 2387873, 59989],
            "abstract": [3222684, 267614, 1402787, 8386440, 210186, 356056],
            "food": [1640777, 1410235, 2097090, 262959],
            "people": [3184395, 3184325, 1671643, 1181671],
        }

        if resolved_key not in curated:
            resolved_key = "abstract"

        photo_id = random.choice(curated[resolved_key])
        url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280"
        print(f"📸 Pexels CDN fallback for '{resolved_key}' (id={photo_id})...")
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Pexels fallback image saved")

            # 🔹 Force exact size
            from PIL import Image
            img = Image.open(bg_path).convert("RGB")
            w, h = img.size
            target_ratio = 9 / 16
            current_ratio = w / h
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                right = left + new_w
                img = img.crop((left, 0, right, h))
            elif current_ratio < target_ratio:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                bottom = top + new_h
                img = img.crop((0, top, w, bottom))
            img = img.resize((720, 1280), Image.LANCZOS)
            img.save(bg_path, quality=95)
            print(f"   ✂️ Cropped + resized to exact 720x1280")

            return bg_path

        else:
            print(f"   ⚠️ Pexels failed: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Pexels error: {e}")

    # --- 🔹 Step 4: Picsum Random fallback ---
    try:
        seed = random.randint(1, 1000)
        url = f"https://picsum.photos/720/1280?random={seed}"
        print(f"🎲 Picsum fallback (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Picsum image saved")
            return bg_path
        else:
            print(f"   ⚠️ Picsum failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ⚠️ Picsum fallback failed: {e}")
        return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=4, max=20))
def generate_thumbnail_bg(topic, title):
    bg_path = os.path.join(TMP, "thumb_bg.png")
    
    prompt = f"YouTube thumbnail style, viral content, trending, {topic}, high contrast, vibrant colors, dramatic lighting, professional photography, no text, cinematic, eye-catching, seed={random.randint(1000,9999)}"
    
    # List of providers to try in order
    providers = [
        ("Hugging Face", generate_thumbnail_huggingface),
        ("Pollinations", generate_thumbnail_pollinations)
    ]
    
    # Try AI providers first
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name} for thumbnail...")
            image_content = provider_func(prompt)
            with open(bg_path, "wb") as f:
                f.write(image_content)
            
            if os.path.getsize(bg_path) > 1000:
                print(f"✅ {provider_name} thumbnail generated successfully")
                return bg_path
            else:
                print(f"⚠️ {provider_name} returned empty file")
                
        except Exception as e:
            print(f"⚠️ {provider_name} thumbnail failed: {e}")
            continue

        # Try Picsum
    print("🖼️ AI providers failed, trying photo APIs...")
    result = generate_picsum_fallback(bg_path, topic=topic, title=title)
    
    if result and os.path.exists(bg_path) and os.path.getsize(bg_path) > 1000:
        return bg_path
    
    # Last resort: Gradient fallback
    print("⚠️ All providers failed, using gradient fallback")
    img = Image.new("RGB", (720, 1280), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Create gradient
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

# Better vignette for text readability
vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
vd = ImageDraw.Draw(vignette)
w, h = img.size

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

# ✅ FIXED: Add font size calculation that ensures text fits within screen width
def calculate_font_size_that_fits(text_lines, max_width=650, min_size=30):
    """Calculate font size that ensures text doesn't go outside screen with margins"""
    # Account for margins in max width
    LEFT_MARGIN = 60
    RIGHT_MARGIN = 60
    safe_max_width = max_width - LEFT_MARGIN - RIGHT_MARGIN  # Actually usable width
    
    for font_size in range(70, min_size - 1, -3):  # Step by 3px for faster iteration
        test_font = get_font_path(font_size, bold=True)
        all_lines_fit = True
        
        # Check if all lines fit within safe_max_width
        for line in text_lines:
            bbox = draw.textbbox((0, 0), line, font=test_font)
            line_width = bbox[2] - bbox[0]
            if line_width > safe_max_width:
                all_lines_fit = False
                break
        
        if all_lines_fit:
            print(f"✅ Font size {font_size}px fits all lines within {safe_max_width}px (with margins)")
            return font_size
    
    # If no size fits, use minimum and warn
    print(f"⚠️ Using minimum font size {min_size}px - text may still overflow!")
    return min_size

# Use the new font size calculation
font_size = calculate_font_size_that_fits(text_lines)
main_font = get_font_path(font_size, bold=True)

# ✅ Keep all your original font sizing logic as backup
max_chars = max(len(line) for line in text_lines) if text_lines else 0
num_lines = len(text_lines)

# Your original logic (keep as reference)
if num_lines >= 3:
    calculated_size = 55  # Smaller for 3 lines
elif max_chars > 18:
    calculated_size = 58
elif max_chars > 15:
    calculated_size = 60
else:
    calculated_size = 68

print(f"📝 Original calculated size: {calculated_size}px, Final size: {font_size}px")

w, h = img.size

print(f"📝 Adding {num_lines}-line text to thumbnail (font: {font_size}px)...")

# Calculate total text height with proper spacing
line_heights = []
for line in text_lines:
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_h = bbox[3] - bbox[1]
    line_heights.append(text_h)

line_spacing = 15 if num_lines >= 3 else 20
total_height = sum(line_heights) + (len(text_lines) - 1) * line_spacing

# Position text in upper third for YouTube Shorts
start_y = h * 0.15 if num_lines >= 3 else h * 0.18

# ✅ FIXED: Verify each line fits before drawing
for i, line in enumerate(text_lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # --- Safe layout constants for 1080x1920 vertical video ---
LEFT_MARGIN = 60       # slightly wider margin for mobile
RIGHT_MARGIN = 60
TOP_MARGIN = 150
BOTTOM_MARGIN = 200
MAX_TEXT_WIDTH = w - LEFT_MARGIN - RIGHT_MARGIN  # e.g. 960px usable width

# --- Per-line placement loop ---
for i, line in enumerate(text_lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # --- Horizontal positioning ---
    if text_w > MAX_TEXT_WIDTH:
        # Line is too wide; force left-align inside safe zone
        print(f"⚠️ Line {i+1} too wide ({text_w}px > {MAX_TEXT_WIDTH}px) — left-aligning")
        x = LEFT_MARGIN
    else:
        # Center the text, but still enforce both margins
        x = (w - text_w) / 2
        # Safety check: ensure it doesn't overflow on either side
        if x < LEFT_MARGIN:
            x = LEFT_MARGIN
        if x + text_w > w - RIGHT_MARGIN:
            x = w - RIGHT_MARGIN - text_w

    # --- Vertical positioning ---
    y = start_y + sum(line_heights[:i]) + (i * line_spacing)
    
    print(f"   Line {i+1}: '{line}'  X={x:.1f}  Y={y:.1f}  Width={text_w}px")

    # Draw your shadows / strokes / text here...

    shadow_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_overlay)
    
    for offset in [4, 3, 2]:
        shadow_alpha = int(140 * (offset / 4))
        sd.text((x + offset, y + offset), line, font=main_font, fill=(0, 0, 0, shadow_alpha))
    
    img = Image.alpha_composite(img, shadow_overlay)
    
    # Thicker stroke for better readability
    stroke_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    so = ImageDraw.Draw(stroke_overlay)
    
    stroke_size = 3
    for adj_x in range(-stroke_size, stroke_size + 1):
        for adj_y in range(-stroke_size, stroke_size + 1):
            if abs(adj_x) == stroke_size or abs(adj_y) == stroke_size:
                so.text((x + adj_x, y + adj_y), line, font=main_font, fill=(0, 0, 0, 220))
    
    img = Image.alpha_composite(img, stroke_overlay)
    
    # Bright text
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