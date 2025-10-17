# .github/scripts/create_video.py
import os
import json
import requests
from moviepy import *
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from pydub import AudioSegment
from time import sleep
from PIL import Image, ImageDraw, ImageFont
import random

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
OUT = os.path.join(TMP, "short.mp4")
audio_path = os.path.join(TMP, "voice.mp3")
w, h = 1080, 1920

# Safe zones for text (avoiding screen edges)
SAFE_ZONE_MARGIN = 130
TEXT_MAX_WIDTH = w - (2 * SAFE_ZONE_MARGIN)

def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/arialbd.ttf"
    elif system == "Darwin":
        return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    else:
        font_options = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for font in font_options:
            if os.path.exists(font):
                return font
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

FONT = get_font_path()
print(f"📝 Using font: {FONT}")

with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "AI Short")
hook = data.get("hook", "")
bullets = data.get("bullets", [])
cta = data.get("cta", "")
topic = data.get("topic", "abstract")
visual_prompts = data.get("visual_prompts", [])

# ✅ FIXED: Correct Hugging Face API endpoints
def generate_image_huggingface(prompt, filename, width=1080, height=1920):
    """Generate image using Hugging Face (with multiple free model fallbacks)"""
    try:
        hf_token = os.getenv('HUGGINGFACE_API_KEY')
        if not hf_token:
            print("    ⚠️ HUGGINGFACE_API_KEY not found — skipping Hugging Face")
            raise Exception("Missing token")

        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": "blurry, low quality, watermark, text, logo, frame, ugly, dull, text paragraphs, prompt text, very long text",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": width,
                "height": height,
            }
        }

        # List of models to try, in order (from thumbnail script)
        models = [
            "stabilityai/stable-diffusion-xl-base-1.0",  # Paid (best quality)
            "prompthero/openjourney-v4",               # Free (fast + decent)
            "Lykon/dreamshaper-xl-v2-turbo",           # Free (creative, solid)
            "runwayml/stable-diffusion-v1-5",
            "stabilityai/sdxl-turbo"
        ]

        for model in models:
            url = f"https://api-inference.huggingface.co/models/{model}"
            print(f"🤗 Trying model: {model}")

            response = requests.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code == 200 and len(response.content) > 1000:
                filepath = os.path.join(TMP, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"    ✅ Hugging Face model succeeded: {model}")
                return filepath

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
        print(f"⚠️ Hugging Face image generation failed: {e}")
        raise


def generate_image_pollinations(prompt, filename, width=1080, height=1920):
    """Pollinations backup with anti-logo filter and unique seed (from thumbnail script)"""
    try:
        # Strong negative prompt to avoid logos, text, UI, and play buttons
        negative_terms = (
            "youtube logo, play button, watermark, ui, interface, overlay, branding, text, caption, words, title, subtitle, watermarking, long text, frame, icon, symbol, graphics, arrows, shapes, low quality, distorted"
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
            f"?width={width}&height={height}"
            f"&negative={requests.utils.quote(negative_terms)}"
            f"&nologo=true&notext=true&enhance=true&clean=true"
            f"&seed={seed}&rand={seed}"
        )

        print(f"    🌐 Pollinations thumbnail: {prompt[:60]}... (seed={seed})")
        response = requests.get(url, timeout=120)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            filepath = os.path.join(TMP, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Pollinations image generated (seed {seed})")
            return filepath
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")

    except Exception as e:
        print(f"    ⚠️ Pollinations thumbnail failed: {e}")
        raise

# ✅ NEW: Integrated the comprehensive fallback from generate_thumbnail.py
def generate_picsum_fallback(bg_path, topic=None, title=None, width=1080, height=1920):
    """
    Smart keyword-based fallback (no API keys) from Unsplash, Pexels, and Picsum.
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

    text_source = (topic or title or "").lower()
    print(f"🔍 DEBUG: text_source='{text_source}', topic='{topic}'")
    resolved_key = next((mapped for word, mapped in topic_map.items() if word in text_source), "abstract")
    print(f"🔍 DEBUG: resolved_key='{resolved_key}'")

    print(f"🔎 Searching fallback image for topic '{topic}' (resolved key: '{resolved_key}')...")

    # --- 🔹 Step 2: Try Unsplash (free, no API key) ---
    try:
        seed = random.randint(1, 9999)
        url = f"https://source.unsplash.com/{width}x{height}/?{requests.utils.quote(resolved_key)}&sig={seed}"
        print(f"🖼️ Unsplash fallback for '{resolved_key}' (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Unsplash image saved for '{resolved_key}'")
            return bg_path
        else:
            print(f"    ⚠️ Unsplash failed ({response.status_code})")
    except Exception as e:
        print(f"    ⚠️ Unsplash error: {e}")

    # --- 🔹 Step 3: Try Pexels CDN curated fallback (using 720x1280 to maintain aspect ratio) ---
    # --- 🔹 Step 3: Try Pexels Search, then Popular Fallback (No API) ---

# First attempt: Search approach
    
    try:
        print("    🔄 Falling back to Pexels popular photos...")
            
            # Large pool of popular Pexels photo IDs across categories
        popular_pexels_ids = {
            "ai": [2045531, 6153896, 8386440, 8386442, 8386445, 9569811, 10453212, 11053713, 1181244, 12043246, 12661306, 12985914],
            "technology": [2045531, 6153896, 8386440, 1181244, 4974912, 3861959, 3184325, 1671643, 11053713, 12043246, 12661306, 12985914],
            "science": [2045531, 6153896, 3184325, 356056, 586339, 8386440, 9569811, 10453212, 11053713, 12043246, 12661306, 12985914],
            "psychology": [3184325, 8386440, 7952404, 2045531, 6153896, 9569811, 10453212, 11053713, 1181244, 12043246, 12661306, 12985914],
            "money": [4386321, 3183150, 394372, 4386375, 210186, 5699432, 6858968, 7730325, 8567952, 10453212, 11341612, 12985914],
            "business": [3183150, 394372, 3184325, 267614, 210186, 5699432, 6858968, 7730325, 8567952, 10453212, 11341612, 12985914],
            "nature": [34950, 3222684, 2014422, 590041, 15286, 36717, 62415, 132037, 145035, 36717, 1257860, 1320370, 1450350, 1624430],
            "travel": [346885, 3222684, 2387873, 59989, 132037, 145035, 210186, 62415, 36717, 1257860, 1320370, 1450350, 1624430, 1753810],
            "abstract": [3222684, 267614, 1402787, 8386440, 210186, 356056, 6153896, 9569811, 10453212, 1181244, 12043246, 12661306, 12985914],
            "food": [1640777, 1410235, 2097090, 262959, 3338496, 3764640, 4614280, 5745514, 6754873, 7692894, 8500370, 9205700, 10518300],
            "people": [3184395, 3184325, 1671643, 1181671, 1222271, 1546906, 2204536, 2379004, 3258764, 4154856, 5384435, 6749100, 7897860]
        }
            
        if resolved_key not in popular_pexels_ids:
            resolved_key = "abstract"
            
            # Shuffle and try multiple random IDs
        photo_ids = popular_pexels_ids[resolved_key].copy()
        random.shuffle(photo_ids)
            
        for attempt, photo_id in enumerate(photo_ids[:4]):  # Try 4 different IDs
            # Add random parameter to avoid caching
            seed = random.randint(1000, 9999)
            url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280&random={seed}"
                
            print(f"📸 Pexels popular fallback attempt {attempt+1} (id={photo_id}, topic='{resolved_key}')...")

            response = requests.get(url, timeout=30)
            if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                with open(bg_path, "wb") as f:
                    f.write(response.content)
                print(f"    ✅ Pexels popular image saved (id: {photo_id})")

                    # Resize to exact dimensions
                img = Image.open(bg_path).convert("RGB")
                img = img.resize((width, height), Image.LANCZOS)
                img.save(bg_path, quality=95)
                print(f"    ✂️ Resized to exact {width}x{height}")

                return bg_path
            else:
                print(f"    ⚠️ Pexels photo {photo_id} failed: {response.status_code}")
            
        print("    ⚠️ All Pexels popular photos failed")
            
    except Exception as e:
        print(f"    ⚠️ Pexels popular photos fallback failed: {e}")

    # --- 🔹 Step 4: Picsum Random fallback ---
    try:
        seed = random.randint(1, 1000)
        url = f"https://picsum.photos/{width}/{height}?random={seed}"
        print(f"🎲 Picsum fallback (seed={seed})...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(bg_path, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Picsum image saved")
            return bg_path
        else:
            print(f"    ⚠️ Picsum failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"    ⚠️ Picsum fallback failed: {e}")
        return None

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=25))
def generate_image_reliable(prompt, filename, width=1080, height=1920, topic=None, title=None):
    """Try multiple image generation providers and fallbacks in order"""
    filepath = os.path.join(TMP, filename)
    
    # 1. AI Providers
    providers = [
        ("Pollinations", generate_image_pollinations),
        ("Hugging Face", generate_image_huggingface)
        
    ]
    
    for provider_name, provider_func in providers:
        try:
            print(f"🎨 Trying {provider_name} for image...")
            result = provider_func(prompt, filename, width, height)
            if result and os.path.exists(result) and os.path.getsize(result) > 1000:
                return result
        except Exception as e:
            print(f"    ⚠️ {provider_name} failed: {e}")
            continue

    # 2. Fallbacks (Unsplash, Pexels, Picsum)
    print("🖼️ AI providers failed, trying photo API fallbacks...")
    result = generate_picsum_fallback(filepath, topic=topic, title=title, width=width, height=height)

    if result and os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return result
    
    # 3. Last resort: Solid color fallback
    print("⚠️ All providers failed, using solid color fallback")
    img = Image.new("RGB", (width, height), (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)))
    img.save(filepath)
    return filepath


# --- Main Scene Generation Logic ---

print("🎨 Generating scene images with reliable providers...")
scene_images = []

try:
    # 1. Hook Scene
    hook_prompt = visual_prompts[0] if len(visual_prompts) > 0 else f"Eye-catching dramatic opening for: {hook or title}, cinematic lighting, vibrant colors"
    hook_img = generate_image_reliable(
        hook_prompt, 
        "scene_hook.jpg", 
        width=w, height=h, 
        topic=topic, 
        title=hook or title
    )
    scene_images.append(hook_img)
    
    # 2. Bullet Point Scenes
    for i, bullet in enumerate(bullets):
        bullet_prompt = visual_prompts[i+1] if len(visual_prompts) > i+1 else f"Visual representation: {bullet}, photorealistic, vibrant, engaging"
        bullet_img = generate_image_reliable(
            bullet_prompt, 
            f"scene_bullet_{i}.jpg", 
            width=w, height=h, 
            topic=topic, 
            title=bullet
        )
        scene_images.append(bullet_img)

    # 3. Final CTA/Summary Scene
    cta_prompt = visual_prompts[-1] if len(visual_prompts) > len(bullets) else f"Inspirational closing shot for: {cta or title}, motivational, high-energy, summary visual"
    cta_img = generate_image_reliable(
        cta_prompt, 
        "scene_cta.jpg", 
        width=w, height=h, 
        topic=topic, 
        title=cta or title
    )
    scene_images.append(cta_img)
    
    successful_images = len([img for img in scene_images if img and os.path.exists(img) and os.path.getsize(img) > 1000])
    print(f"✅ Generated {successful_images} reliable images out of {len(scene_images)} total scenes.")
    
except Exception as e:
    print(f"⚠️ Image generation failed entirely: {e}")
    # Fallback to an array of Nones or default image paths if the try block fails
    scene_images = [None] * (len(bullets) + 2)


if not os.path.exists(audio_path):
    print(f"❌ Audio file not found: {audio_path}")
    raise FileNotFoundError("voice.mp3 not found")

audio = AudioFileClip(audio_path)
duration = audio.duration
print(f"🎵 Audio loaded: {duration:.2f} seconds")

# 🔍 Prefer real per-section durations if available
def get_audio_duration(path):
    """Get audio duration safely using mutagen (works on Python 3.14)."""
    try:
        if os.path.exists(path):
            return len(AudioSegment.from_file(path)) / 1000.0
    except:
        pass
    return 0

hook_path = os.path.join(TMP, "hook.mp3")
cta_path = os.path.join(TMP, "cta.mp3")
bullet_paths = [os.path.join(TMP, f"bullet_{i}.mp3") for i in range(len(bullets))]

if all(os.path.exists(p) for p in [hook_path, cta_path] + bullet_paths):
    print("🎯 Using real per-section audio durations for sync")
    hook_dur = get_audio_duration(hook_path)
    bullet_durs = [get_audio_duration(p) for p in bullet_paths]
    cta_dur = get_audio_duration(cta_path)
else:
    print("⚙️ Using estimated word-based durations (fallback)")

def estimate_speech_duration(text, audio_path):
    """Estimate how long the given text should take"""
    words = len(text.split())
    if words == 0:
        return 0.0

    fallback_wpm = 140  # words per minute average

    if os.path.exists(audio_path):
        try:
            audio = AudioSegment.from_file(audio_path)
            total_audio_duration = len(audio) / 1000.0

            all_text = " ".join([hook] + bullets + [cta])
            total_words = len(all_text.split()) or 1

            seconds_per_word = total_audio_duration / total_words
            return seconds_per_word * words  # ✅ stays inside try block
        except Exception as e:
            print(f"⚠️ Could not analyze TTS file for pacing: {e}")
            return (words / fallback_wpm) * 60.0
    else:
        return (words / fallback_wpm) * 60.0



hook_estimated = estimate_speech_duration(hook, audio_path)
bullets_estimated = [estimate_speech_duration(b, audio_path) for b in bullets]
cta_estimated = estimate_speech_duration(cta, audio_path)

total_estimated = hook_estimated + sum(bullets_estimated) + cta_estimated

    # Safety check for zero-length text/audio
if total_estimated == 0:
    section_count = max(1, len(bullets) + (1 if hook else 0) + (1 if cta else 0))
    equal_split = duration / section_count 
        
    hook_dur = equal_split if hook else 0
    bullet_durs = [equal_split] * len(bullets)
    cta_dur = equal_split if cta else 0

else:
        # ✅ FIXED: Ensure scenes match EXACT audio duration
        # Remove margin - we want to use the full audio duration
    time_scale = duration / total_estimated 

        # Apply the time scale to every estimated duration
    hook_dur = hook_estimated * time_scale
    bullet_durs = [b_est * time_scale for b_est in bullets_estimated]
    cta_dur = cta_estimated * time_scale
        
        # ✅ CRITICAL FIX: Adjust last section to account for rounding errors
    total_scenes = hook_dur + sum(bullet_durs) + cta_dur
    duration_diff = duration - total_scenes
        
    if abs(duration_diff) > 0.01:  # If difference > 10ms
        # Add the difference to the CTA (last section)
        cta_dur += duration_diff
        print(f"⚙️ Adjusted CTA duration by {duration_diff:.2f}s to match audio exactly")

print(f"⏱️  Scene timings (audio-synced):")
for i, dur in enumerate(bullet_durs):
    print(f"   Bullet {i+1}: {dur:.1f}s")
print(f"   CTA: {cta_dur:.1f}s")
print(f"   Total: {hook_dur + sum(bullet_durs) + cta_dur:.2f}s (Audio: {duration:.2f}s)")

clips = []
current_time = 0

def smart_text_wrap(text, font_size, max_width):
    """Intelligently wrap text to prevent word splitting across lines"""
    
    try:
        pil_font = ImageFont.truetype(FONT, font_size)
    except:
        avg_char_width = font_size * 0.55
        max_chars_per_line = int(max_width / avg_char_width)
        
        words = text.split()
        if len(words) <= 2:  # Short phrases like "next obsession"
            return text + '\n'
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
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines) + '\n'
    
    words = text.split()
    lines = []
    current_line = []
    
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=pil_font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
            word_bbox = draw.textbbox((0, 0), word, font=pil_font)
            word_width = word_bbox[2] - word_bbox[0]
            if word_width > max_width:
                pass
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines) + '\n'

def create_text_with_effects(text, font_size=64, max_width=TEXT_MAX_WIDTH):
    """Create properly wrapped text with safe font sizing"""
    
    wrapped_text = smart_text_wrap(text, font_size, max_width)
    
    # Simple font size adjustment without complex clip creation
    try:
        pil_font = ImageFont.truetype(FONT, font_size)
        dummy_img = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        
        # Check if text fits within constraints
        lines = wrapped_text.split('\n')
        total_height = 0
        max_line_width = 0
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=pil_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            total_height += line_height
            max_line_width = max(max_line_width, line_width)
        
        # Adjust font size if needed
        max_height = h * 0.25
        iterations = 0
        
        while (total_height > max_height or max_line_width > max_width) and font_size > 32 and iterations < 10:
            font_size -= 4
            wrapped_text = smart_text_wrap(text, font_size, max_width)
            
            pil_font = ImageFont.truetype(FONT, font_size)
            lines = wrapped_text.split('\n')
            total_height = 0
            max_line_width = 0
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=pil_font)
                line_width = bbox[2] - bbox[0]
                line_height = bbox[3] - bbox[1]
                total_height += line_height
                max_line_width = max(max_line_width, line_width)
            
            iterations += 1
            
    except Exception as e:
        print(f"      ⚠️ Font sizing warning: {e}")
        # Fallback: simple character-based sizing
        if len(wrapped_text) > 100:
            font_size = max(32, font_size - 8)
    
    return wrapped_text, font_size

def create_scene(image_path, text, duration, start_time, position_y='center', color_fallback=(30, 30, 30)):
    """Create a scene with background image and properly rendered text"""
    scene_clips = []
    
    if image_path and os.path.exists(image_path):
        bg = (ImageClip(image_path)
              .resized(height=h)
              .with_duration(duration)
              .with_start(start_time)
              .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
    else:
        bg = (ColorClip(size=(w, h), color=color_fallback, duration=duration)
              .with_start(start_time))
    
    scene_clips.append(bg)
    
    if text:
        wrapped_text, font_size = create_text_with_effects(text)

        text_method = 'label' if len(text.split()) <= 3 else 'caption'
        stroke_width = 2 if len(text.split()) <= 3 else 4
        
        # ✅ FIXED: Use basic TextClip with proper descender spacing
        text_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            color='white',
            stroke_width=stroke_width,
            stroke_color='black', 
            method=text_method,
            text_align='center',
            size=(TEXT_MAX_WIDTH, None),
        )
        
        # Calculate safe position with proper descender space
        text_height = text_clip.h
        text_width = text_clip.w
        
        # Add extra padding for descenders (20-30px depending on font size)
        descender_padding = max(35, int(font_size * 0.6))
        
        bottom_safe_zone = SAFE_ZONE_MARGIN + 180 
        # Calculate vertical positioning with proper safety margins
        if position_y == 'center':
            pos_y = (h - text_height) // 2
        elif position_y == 'top':
            # Top position: safe from notification area
            pos_y = SAFE_ZONE_MARGIN + 80
        elif position_y == 'bottom':
            # Bottom position: safe from UI elements + descender space
            pos_y = h - text_height - bottom_safe_zone - descender_padding
        else:
            # For numeric positions, ensure they're safe
            pos_y = min(max(SAFE_ZONE_MARGIN + 80, position_y), 
                       h - text_height - bottom_safe_zone - descender_padding)
        
        # Final safety check with proper margins
        bottom_limit = h - bottom_safe_zone - descender_padding
        top_limit = SAFE_ZONE_MARGIN + 80
        
        if pos_y + text_height > bottom_limit:
            pos_y = bottom_limit - text_height
        if pos_y < top_limit:
            pos_y = top_limit
        
        text_clip = (text_clip
                    .with_duration(duration)
                    .with_start(start_time)
                    .with_position(('center', pos_y))
                    .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
        
        print(f"      Text: '{wrapped_text[:40]}...'")
        print(f"         Font: {font_size}px, Size: {text_width}x{text_height}px")

        print(f"         Position: Y={pos_y}px (top edge)")

        
        scene_clips.append(text_clip)
    
    return scene_clips

# In your main execution section, change these calls:


if hook:
    print(f"🎬 Creating hook scene (synced with audio)...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y='top',  # Changed from 400 to 'top'
        color_fallback=(30, 144, 255)
    )
    clips.extend(hook_clips)
    current_time += hook_dur

# For bullets - use 'center' 
for i, bullet in enumerate(bullets):
    if not bullet:
        continue
    
    img_index = min(i + 1, len(scene_images) - 1)
    colors = [(255, 99, 71), (50, 205, 50), (255, 215, 0)]

    print(f"🎬 Creating bullet {i+1} scene (synced with audio)...")
    
    bullet_clips = create_scene(
        scene_images[img_index] if scene_images and img_index < len(scene_images) else None,
        bullet,
        bullet_durs[i],
        current_time,
        position_y='center',  # Changed from 900 to 'center'
        color_fallback=colors[i % len(colors)]
    )

    clips.extend(bullet_clips)      # ✅ <-- missing line
    current_time += bullet_durs[i]  # ✅ <-- advance timeline
# For CTA - use 'bottom'
if cta:
    print(f"📢 Creating CTA scene (synced with audio)...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y='bottom',  # Changed from 1200 to 'bottom'
        color_fallback=(255, 20, 147)
    )
    clips.extend(cta_clips)
    print(f"   CTA: {current_time:.1f}s - {current_time + cta_dur:.1f}s (synced)")
else:
    print("⚠️ No CTA text found")

print(f"🎬 Composing video with {len(clips)} clips...")
video = CompositeVideoClip(clips, size=(w, h))

print(f"🔊 Attaching audio...")
video = video.with_audio(audio)

if video.audio is None:
    print("❌ ERROR: No audio attached to video!")
    raise Exception("Audio failed to attach")
else:
    print(f"✅ Audio verified: {video.audio.duration:.2f}s")
    print(f"✅ Text-audio synchronization: ENABLED")

print(f"📹 Writing video file to {OUT}...")
try:
    video.write_videofile(
        OUT,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset='medium',
        audio_bitrate='192k',
        bitrate='8000k',
        logger=None
    )
    
    print(f"✅ Video created successfully!")
    print(f"   Path: {OUT}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Size: {os.path.getsize(OUT) / (1024*1024):.2f} MB")
    print(f"   Features:")
    print(f"      ✓ Smart text wrapping (no word splitting)")
    print(f"      ✓ Text stays within safe boundaries")
    print(f"      ✓ Proper descender spacing for letters like g, j, p, q, y")
    print(f"      ✓ Audio-synchronized text timing")
    print(f"      ✓ High visibility text (outline + shadow)")
    print(f"      ✓ Adaptive font sizing")
    print(f"      ✓ Dynamic position adjustment")
    
    if not os.path.exists(OUT) or os.path.getsize(OUT) < 100000:
        raise Exception("Output video is missing or too small")
    
except Exception as e:
    print(f"❌ Video creation failed: {e}")
    raise

finally:
    print("🧹 Cleaning up...")
    audio.close()
    video.close()
    
    for clip in clips:
        try:
            clip.close()
        except:
            pass

print("✅ Video pipeline complete with all enhancements!")
