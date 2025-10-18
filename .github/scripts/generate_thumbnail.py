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

def get_font_path_string(bold=True):
    """Get font path as string for smart_text_wrap"""
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
            return font_path
    
    return None

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "AI Short")
topic = data.get("topic", "trending")
hook = data.get("hook", "")

# Use the shorter text between title and hook
if hook and len(hook) > 10:
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

# Canvas dimensions
w = 720
h = 1280

display_text += '\n'

# Safe zones for text (from create_video.py - WORKING LOGIC)
SAFE_ZONE_MARGIN = 40
TEXT_MAX_WIDTH = w - (2 * SAFE_ZONE_MARGIN)  # 640px usable width

def generate_thumbnail_huggingface(prompt):
    """Generate thumbnail using Hugging Face"""
    try:
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        if not hf_token:
            print("⚠️ No HUGGINGFACE_API_KEY found")
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

        models = [
            "stabilityai/stable-diffusion-xl-base-1.0",
            "prompthero/openjourney-v4",
            "Lykon/dreamshaper-xl-v2-turbo",
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
                print(f"💰 {model} requires payment")
                continue
            elif response.status_code in [503, 429]:
                print(f"⌛ {model} is loading or rate-limited")
                continue
            else:
                print(f"⚠️ {model} failed ({response.status_code})")

        raise Exception("All Hugging Face models failed")

    except Exception as e:
        print(f"⚠️ Hugging Face thumbnail generation failed: {e}")
        raise

def generate_thumbnail_pollinations(prompt):
    """Pollinations backup"""
    try:
        negative_terms = (
            "youtube logo, play button, watermark, ui, interface, overlay, "
            "branding, text, caption, words, title, subtitle, watermarking, "
            "frame, icon, symbol, graphics, arrows, shapes, low quality, distorted"
        )

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

        print(f"🌐 Pollinations thumbnail (seed={seed})")
        response = requests.get(url, timeout=120)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            print(f"✅ Pollinations image generated")
            return response.content
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")

    except Exception as e:
        print(f"⚠️ Pollinations thumbnail failed: {e}")
        raise

def generate_picsum_fallback(bg_path, topic=None, title=None):
    """Smart keyword-based fallback"""
    import re, random, requests

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

    print(f"🔎 Searching fallback image for topic '{topic}' (resolved: '{resolved_key}')")

    # Try Unsplash
    try:
        seed = random.randint(1, 9999)
        url = f"https://source.unsplash.com/720x1280/?{requests.utils.quote(resolved_key)}&sig={seed}"
        print(f"🖼️ Unsplash fallback (seed={seed})")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Unsplash image saved")
            return bg_path
    except Exception as e:
        print(f"⚠️ Unsplash error: {e}")

    # Try Pexels CDN (EXPANDED: 30-50 IDs per category)
    try:
        curated_pexels = {
            "ai": [8386440, 8386442, 1671643, 3184325, 5698515, 8728382, 7594184, 3861969, 
                   8386434, 8386435, 5473955, 7594180, 3861958, 8728380, 7859750, 8386428,
                   3912952, 3861951, 5483077, 8728378, 9820209, 7672246, 5473967, 8728390,
                   3861943, 8386426, 7672252, 5483080, 8728372, 9820215, 7672258, 5473970,
                   8386424, 8728370, 3861935, 7672264, 5483083, 8728368, 9820221, 7672270,
                   8386422, 3861927, 5483086, 8728366, 9820227, 7672276, 5473973, 8386420],
            
            "technology": [3861959, 3184325, 1671643, 4974912, 5380664, 442150, 1181271, 1181263,
                          325111, 3861969, 325153, 1181292, 373543, 5380669, 1714208, 1181280,
                          5380672, 3861943, 1181298, 373547, 325156, 5380675, 1181304, 373551,
                          5380678, 3861927, 1181310, 373555, 325159, 5380681, 1181316, 373559,
                          5380684, 3861911, 1181322, 373563, 325162, 5380687, 1181328, 373567,
                          5380690, 3861895, 1181334, 373571, 325165, 5380693, 1181340, 373575],
            
            "science": [356056, 3184325, 1671643, 586339, 2280571, 3825573, 256262, 60582,
                       2280549, 3825551, 256287, 60597, 2280527, 3825529, 256312, 60612,
                       2280505, 3825507, 256337, 60627, 2280483, 3825485, 256362, 60642,
                       2280461, 3825463, 256387, 60657, 2280439, 3825441, 256412, 60672,
                       2280417, 3825419, 256437, 60687, 2280395, 3825397, 256462, 60702,
                       2280373, 3825375, 256487, 60717, 2280351, 3825353, 256512, 60732],
            
            "psychology": [3184325, 8386440, 3861959, 7952404, 4164610, 7176325, 3812745, 3184319,
                          4164588, 7176303, 3812723, 3184297, 4164566, 7176281, 3812701, 3184275,
                          4164544, 7176259, 3812679, 3184253, 4164522, 7176237, 3812657, 3184231,
                          4164500, 7176215, 3812635, 3184209, 4164478, 7176193, 3812613, 3184187,
                          4164456, 7176171, 3812591, 3184165, 4164434, 7176149, 3812569, 3184143,
                          4164412, 7176127, 3812547, 3184121, 4164390, 7176105, 3812525, 3184099],
            
            "money": [4386321, 3183150, 394372, 4386375, 259027, 164527, 3943716, 259132,
                     4386299, 3183128, 394394, 259154, 164549, 3943738, 259176, 4386277,
                     3183106, 394416, 259198, 164571, 3943760, 259220, 4386255, 3183084,
                     394438, 259242, 164593, 3943782, 259264, 4386233, 3183062, 394460,
                     259286, 164615, 3943804, 259308, 4386211, 3183040, 394482, 259330,
                     164637, 3943826, 259352, 4386189, 3183018, 394504, 259374, 164659],
            
            "business": [3183150, 394372, 3184325, 267614, 3184418, 7688336, 3184287, 3184365,
                        3183128, 394394, 3184347, 267636, 7688358, 3184309, 3184387, 3183106,
                        394416, 3184369, 267658, 7688380, 3184331, 3184409, 3183084, 394438,
                        3184391, 267680, 7688402, 3184353, 3184431, 3183062, 394460, 3184413,
                        267702, 7688424, 3184375, 3184453, 3183040, 394482, 3184435, 267724,
                        7688446, 3184397, 3184475, 3183018, 394504, 3184457, 267746, 7688468],
            
            "nature": [34950, 3222684, 2014422, 590041, 15286, 36717, 62415, 132037, 145035,
                      36739, 1257860, 1320370, 1450350, 1624430, 15308, 62437, 132059, 145057,
                      1257882, 1320392, 1450372, 1624452, 36761, 62459, 132081, 145079, 1257904,
                      1320414, 1450394, 1624474, 36783, 62481, 132103, 145101, 1257926, 1320436,
                      1450416, 1624496, 36805, 62503, 132125, 145123, 1257948, 1320458, 1450438,
                      1624518, 36827, 62525, 132147, 145145],
            
            "travel": [346885, 3222684, 2387873, 59989, 132037, 145035, 210186, 62415, 36717,
                      1257860, 1320370, 1450350, 1624430, 1753810, 346907, 2387895, 59011,
                      132059, 145057, 210208, 62437, 1257882, 1320392, 1450372, 1624452,
                      1753832, 346929, 2387917, 59033, 132081, 145079, 210230, 62459,
                      1257904, 1320414, 1450394, 1624474, 1753854, 346951, 2387939, 59055,
                      132103, 145101, 210252, 62481, 1257926, 1320436, 1450416, 1624496],
            
            "abstract": [3222684, 267614, 1402787, 8386440, 210186, 356056, 6153896, 9569811,
                        10453212, 1181244, 12043246, 12661306, 12985914, 3222706, 267636, 1402809,
                        210208, 6153918, 9569833, 10453234, 1181266, 12043268, 12661328, 12985936,
                        3222728, 267658, 1402831, 210230, 6153940, 9569855, 10453256, 1181288,
                        12043290, 12661350, 12985958, 3222750, 267680, 1402853, 210252, 6153962,
                        9569877, 10453278, 1181310, 12043312, 12661372, 12985980, 3222772, 267702],
            
            "food": [1640777, 1410235, 2097090, 262959, 3338496, 3764640, 4614280, 5745514,
                    6754873, 7692894, 8500370, 9205700, 10518300, 1640799, 1410257, 2097112,
                    262981, 3338518, 3764662, 4614302, 5745536, 6754895, 7692916, 8500392,
                    9205722, 10518322, 1640821, 1410279, 2097134, 263003, 3338540, 3764684,
                    4614324, 5745558, 6754917, 7692938, 8500414, 9205744, 10518344, 1640843,
                    1410301, 2097156, 263025, 3338562, 3764706, 4614346, 5745580, 6754939],
            
            "people": [3184395, 3184325, 1671643, 1181671, 1222271, 1546906, 2204536, 2379004,
                      3258764, 4154856, 5384435, 6749100, 7897860, 3184417, 1671665, 1181693,
                      1222293, 1546928, 2204558, 2379026, 3258786, 4154878, 5384457, 6749122,
                      7897882, 3184439, 1671687, 1181715, 1222315, 1546950, 2204580, 2379048,
                      3258808, 4154900, 5384479, 6749144, 7897904, 3184461, 1671709, 1181737,
                      1222337, 1546972, 2204602, 2379070, 3258830, 4154922, 5384501, 6749166],
        }

        if resolved_key not in curated_pexels:
            resolved_key = "abstract"

        photo_id = random.choice(curated_pexels[resolved_key])
        url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280"
        print(f"📸 Pexels CDN fallback (id={photo_id}, category={resolved_key})")
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            
            img = Image.open(bg_path).convert("RGB")
            w_img, h_img = img.size
            target_ratio = 9 / 16
            current_ratio = w_img / h_img
            if current_ratio > target_ratio:
                new_w = int(h_img * target_ratio)
                left = (w_img - new_w) // 2
                img = img.crop((left, 0, left + new_w, h_img))
            elif current_ratio < target_ratio:
                new_h = int(w_img / target_ratio)
                top = (h_img - new_h) // 2
                img = img.crop((0, top, w_img, top + new_h))
            img = img.resize((720, 1280), Image.LANCZOS)
            img.save(bg_path, quality=95)
            print(f"✅ Pexels image saved and resized")
            return bg_path
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")

    # Try Picsum
    try:
        seed = random.randint(1, 1000)
        url = f"https://picsum.photos/720/1280?random={seed}"
        print(f"🎲 Picsum fallback (seed={seed})")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Picsum image saved")
            return bg_path
    except Exception as e:
        print(f"⚠️ Picsum fallback failed: {e}")
        return None

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=4, max=20))
def generate_thumbnail_bg(topic, title):
    bg_path = os.path.join(TMP, "thumb_bg.png")
    
    prompt = f"YouTube thumbnail style, viral content, trending, {topic}, high contrast, vibrant colors, dramatic lighting, professional photography, no text, cinematic, eye-catching, seed={random.randint(1000,9999)}"
    
    providers = [
        ("Pollinations", generate_thumbnail_pollinations),
        ("Hugging Face", generate_thumbnail_huggingface)
    ]
    
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name}")
            image_content = provider_func(prompt)
            with open(bg_path, "wb") as f:
                f.write(image_content)
            
            if os.path.getsize(bg_path) > 1000:
                print(f"✅ {provider_name} succeeded")
                return bg_path
                
        except Exception as e:
            print(f"⚠️ {provider_name} failed: {e}")
            continue

    print("🖼️ AI providers failed, trying photo APIs")
    result = generate_picsum_fallback(bg_path, topic=topic, title=title)
    
    if result and os.path.exists(bg_path) and os.path.getsize(bg_path) > 1000:
        return bg_path
    
    # Gradient fallback
    print("⚠️ All providers failed, using gradient")
    img = Image.new("RGB", (720, 1280), (0, 0, 0))
    draw_grad = ImageDraw.Draw(img)
    
    for y in range(1280):
        r = int(30 + (255 - 30) * (y / 1280))
        g = int(144 - (144 - 50) * (y / 1280))
        b = int(255 - (255 - 200) * (y / 1280))
        draw_grad.line([(0, y), (720, y)], fill=(r, g, b))
    
    img.save(bg_path)
    return bg_path

# Generate background
bg_path = generate_thumbnail_bg(topic, title)
img = Image.open(bg_path).convert("RGB")

# CRITICAL FIX: Ensure image is exactly 720x1280 BEFORE any processing
if img.size != (720, 1280):
    print(f"⚠️ Background is {img.size}, resizing to 720x1280 BEFORE text processing...")
    img = img.resize((720, 1280), Image.LANCZOS)

# Enhance image
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.3)

enhancer = ImageEnhance.Color(img)
img = enhancer.enhance(1.2)

img = img.convert("RGBA")

# Vignette
vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
vd = ImageDraw.Draw(vignette)

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

# Create dummy draw for measurements
dummy_img = Image.new('RGB', (1, 1))
dummy_draw = ImageDraw.Draw(dummy_img)

# Smart text wrapping using ACTUAL pixel measurements
def smart_text_wrap(text, font_obj, max_width, draw_obj):
    """Wrap text based on actual rendered pixel width"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw_obj.textbbox((0, 0), test_line, font=font_obj)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

# Find optimal font size
font_size = 75
min_font_size = 35
max_height = h * 0.35
text_lines = []

print(f"🎯 Finding optimal font size within {TEXT_MAX_WIDTH}px width...")

while font_size >= min_font_size:
    # Create font at this size
    test_font = get_font_path(font_size, bold=True)
    
    # Wrap text with this font size
    wrapped_lines = smart_text_wrap(display_text, test_font, TEXT_MAX_WIDTH, dummy_draw)
    
    # Measure dimensions
    total_height = 0
    max_line_width = 0
    
    for line in wrapped_lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=test_font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        total_height += line_height
        max_line_width = max(max_line_width, line_width)
    
    # Add spacing between lines
    if len(wrapped_lines) > 1:
        total_height += (len(wrapped_lines) - 1) * 18
    
    # Check if everything fits
    if total_height <= max_height and max_line_width <= TEXT_MAX_WIDTH:
        text_lines = wrapped_lines
        print(f"✅ Font {font_size}px: {len(wrapped_lines)} lines, max width {max_line_width}px")
        break
    
    font_size -= 3

if not text_lines:
    font_size = min_font_size
    test_font = get_font_path(font_size, bold=True)
    text_lines = smart_text_wrap(display_text, test_font, TEXT_MAX_WIDTH, dummy_draw)
    print(f"⚠️ Using minimum font size {min_font_size}px")

main_font = get_font_path(font_size, bold=True)
print(f"📝 Final font: {font_size}px for {len(text_lines)} lines")

# Calculate line heights
line_spacing = 18
line_heights = []

for line in text_lines:
    bbox = draw.textbbox((0, 0), line, font=main_font)
    line_heights.append(bbox[3] - bbox[1])

# Position text at TOP (from create_video.py positioning logic)
top_limit = SAFE_ZONE_MARGIN + 80
start_y = int(h * 0.15)  # 15% from top
start_y = max(start_y, top_limit)

print(f"📍 Text positioning: Top-centered at Y={start_y}")

# Draw each line centered with STRICT margin enforcement
current_y = start_y

for i, line in enumerate(text_lines):
    bbox = draw.textbbox((0, 0), line, font=main_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Calculate centered position
    x = (w - text_w) // 2
    y = current_y
    
    # CRITICAL FIX: If text is too wide, reduce font size for this line
    if text_w > TEXT_MAX_WIDTH:
        print(f"⚠️ Line {i+1} width {text_w}px exceeds {TEXT_MAX_WIDTH}px - this shouldn't happen!")
        # Force within bounds
        x = SAFE_ZONE_MARGIN
        if x + text_w > w - SAFE_ZONE_MARGIN:
            print(f"❌ ERROR: Line still overflows even at X={x}!")
    
    # Enforce strict margins
    if x < SAFE_ZONE_MARGIN:
        x = SAFE_ZONE_MARGIN
    if x + text_w > w - SAFE_ZONE_MARGIN:
        x = w - SAFE_ZONE_MARGIN - text_w
    
    # Final safety check
    right_edge = x + text_w
    if right_edge > w - SAFE_ZONE_MARGIN:
        print(f"❌ Line {i+1} STILL overflows! X={x}, Width={text_w}, Right edge={right_edge}, Max allowed={w - SAFE_ZONE_MARGIN}")
    
    print(f"   Line {i+1}: '{line}' X={x}, Y={y}, Width={text_w}px, Right edge={x + text_w}px (canvas={w}px, max_right={w - SAFE_ZONE_MARGIN}px)")
    
    # Shadow
    shadow_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_overlay)
    
    for offset in [5, 4, 3, 2]:
        shadow_alpha = int(160 * (offset / 5))
        sd.text((x + offset, y + offset), line, font=main_font, fill=(0, 0, 0, shadow_alpha))
    
    img = Image.alpha_composite(img, shadow_overlay)
    
    # Stroke
    stroke_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    so = ImageDraw.Draw(stroke_overlay)
    
    stroke_width = 4
    for sx in range(-stroke_width, stroke_width + 1):
        for sy in range(-stroke_width, stroke_width + 1):
            if sx != 0 or sy != 0:
                so.text((x + sx, y + sy), line, font=main_font, fill=(0, 0, 0, 240))
    
    img = Image.alpha_composite(img, stroke_overlay)
    
    # White text
    text_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    to = ImageDraw.Draw(text_overlay)
    to.text((x, y), line, font=main_font, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, text_overlay)
    
    # Move to next line
    current_y += text_h + line_spacing

# Save final thumbnail - should already be correct size
thumb_path = os.path.join(TMP, "thumbnail.png")
final_img = img.convert("RGB")

# Double-check dimensions (should not need resizing now)
if final_img.size != (720, 1280):
    print(f"❌ ERROR: Image is {final_img.size} after all processing - this shouldn't happen!")
    final_img = final_img.resize((720, 1280), Image.LANCZOS)
else:
    print(f"✅ Image dimensions verified: {final_img.size}")

# Final sharpening
final_img = final_img.filter(ImageFilter.SHARPEN)

final_img.save(thumb_path, quality=95, optimize=True)

# Verify saved image
saved_img = Image.open(thumb_path)
print(f"✅ Saved high-quality thumbnail to {thumb_path}")
print(f"   Size: {os.path.getsize(thumb_path) / 1024:.1f} KB")
print(f"   Dimensions: {saved_img.size}")
print(f"   Text lines: {len(text_lines)}")
print(f"   Text content: {text_lines}")
print(f"   Font size: {font_size}px")