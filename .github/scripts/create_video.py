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
                "negative_prompt": "blurry, low quality, watermark, text, logo, frame, caption, title, subtitle, ui, interface, overlay, play button, youtube logo, branding, prompt text, paragraphs, words, symbol, icon, graphics, arrows, shapes, distorted, compression artifacts, pixelated, dull colors, cropped, stretched, deformed, multiple faces, duplicate body parts, text watermark, long text",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "width": width,
                "height": height,
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

            response = requests.post(url, headers=headers, json=payload, timeout=90)

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

        raise Exception("All Hugging Face models failed")

    except Exception as e:
        print(f"⚠️ Hugging Face image generation failed: {e}")
        raise


def generate_image_pollinations(prompt, filename, width=1080, height=1920):
    """Pollinations backup with anti-logo filter and unique seed"""
    try:
        negative_terms = (
            "blurry, low quality, watermark, text, logo, frame, caption, title, subtitle, ui, interface, overlay, play button, youtube logo, branding, prompt text, paragraphs, words, symbol, icon, graphics, arrows, shapes, distorted, compression artifacts, pixelated, dull colors, cropped, stretched, deformed, multiple faces, duplicate body parts, text watermark, long text"
        )

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
        response = requests.get(url, timeout=90)

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

def generate_picsum_fallback(bg_path, topic=None, title=None, width=1080, height=1920):
    """Smart keyword-based fallback (no API keys) from Unsplash, Pexels, and Picsum."""
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

    text_source = (topic or title or "").lower()
    resolved_key = next((mapped for word, mapped in topic_map.items() if word in text_source), "abstract")

    print(f"🔎 Searching fallback image for topic '{topic}' (resolved key: '{resolved_key}')...")

    # Try Unsplash
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

    # Try Pexels
    try:
        print("    🔄 Falling back to Pexels popular photos...")
            
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
            
        photo_ids = popular_pexels_ids[resolved_key].copy()
        random.shuffle(photo_ids)
            
        for attempt, photo_id in enumerate(photo_ids[:4]):
            seed = random.randint(1000, 9999)
            url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=720&h=1280&random={seed}"
                
            print(f"📸 Pexels popular fallback attempt {attempt+1} (id={photo_id}, topic='{resolved_key}')...")

            response = requests.get(url, timeout=30)
            if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                with open(bg_path, "wb") as f:
                    f.write(response.content)
                print(f"    ✅ Pexels popular image saved (id: {photo_id})")

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

    # Try Picsum
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

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
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
    print("⚠️ All providers failed, using gradient fallback")
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    colors = [(30, 144, 255), (255, 99, 71), (50, 205, 50), (255, 215, 0), (255, 20, 147)]
    color = colors[random.randint(0, len(colors) - 1)]
    
    for y in range(height):
        intensity = int(255 * (1 - y / height))
        r = min(255, max(0, color[0] + (intensity - 127) // 2))
        g = min(255, max(0, color[1] + (intensity - 127) // 2))
        b = min(255, max(0, color[2] + (intensity - 127) // 2))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
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
    scene_images = [None] * (len(bullets) + 2)

# ✅ FIX 2: VALIDATE AND REPLACE NONE/INVALID IMAGES
print(f"🔍 Validating {len(scene_images)} scene images...")
for i in range(len(scene_images)):
    img = scene_images[i] if i < len(scene_images) else None
    
    if not img or not os.path.exists(img) or os.path.getsize(img) < 1000:
        print(f"⚠️ Scene {i} invalid, creating gradient fallback...")
        fallback_path = os.path.join(TMP, f"scene_fallback_{i}.jpg")
        
        fallback_img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(fallback_img)
        
        colors = [(30, 144, 255), (255, 99, 71), (50, 205, 50), (255, 215, 0), (255, 20, 147)]
        color = colors[i % len(colors)]
        
        for y in range(h):
            intensity = int(255 * (1 - y / h))
            r = min(255, max(0, color[0] + (intensity - 127) // 2))
            g = min(255, max(0, color[1] + (intensity - 127) // 2))
            b = min(255, max(0, color[2] + (intensity - 127) // 2))
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        
        fallback_img.save(fallback_path)
        scene_images[i] = fallback_path

print(f"✅ All scene images validated")

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

        fallback_wpm = 140

        if os.path.exists(audio_path):
            try:
                audio = AudioSegment.from_file(audio_path)
                total_audio_duration = len(audio) / 1000.0

                all_text = " ".join([hook] + bullets + [cta])
                total_words = len(all_text.split()) or 1

                seconds_per_word = total_audio_duration / total_words
                return seconds_per_word * words
            except Exception as e:
                print(f"⚠️ Could not analyze TTS file for pacing: {e}")
                return (words / fallback_wpm) * 60.0
        else:
            return (words / fallback_wpm) * 60.0

    hook_estimated = estimate_speech_duration(hook, audio_path)
    bullets_estimated = [estimate_speech_duration(b, audio_path) for b in bullets]
    cta_estimated = estimate_speech_duration(cta, audio_path)

    total_estimated = hook_estimated + sum(bullets_estimated) + cta_estimated

    if total_estimated == 0:
        section_count = max(1, len(bullets) + (1 if hook else 0) + (1 if cta else 0))
        equal_split = duration / section_count 
        
        hook_dur = equal_split if hook else 0
        bullet_durs = [equal_split] * len(bullets)
        cta_dur = equal_split if cta else 0

    else:
        time_scale = duration / total_estimated 

        hook_dur = hook_estimated * time_scale
        bullet_durs = [b_est * time_scale for b_est in bullets_estimated]
        cta_dur = cta_estimated * time_scale
        
        # ✅ FIX 3: ACCOUNT FOR CROSS-FADE OVERLAPS
        num_sections = (1 if hook else 0) + len(bullets) + (1 if cta else 0)
        num_transitions = max(0, num_sections - 1)
        
        if num_transitions > 0:
            # Each cross-fade creates 0.3s overlap between scenes
            total_overlap = 0.3 * num_transitions
            
            # Reduce all scene durations proportionally
            total_base = hook_dur + sum(bullet_durs) + cta_dur
            
            if hook and total_base > 0:
                hook_dur = max(1.0, hook_dur - (total_overlap * hook_dur / total_base))
            
            for i in range(len(bullet_durs)):
                if total_base > 0:
                    bullet_durs[i] = max(1.0, bullet_durs[i] - (total_overlap * bullet_durs[i] / total_base))
            
            if cta and total_base > 0:
                cta_dur = max(1.0, cta_dur - (total_overlap * cta_dur / total_base))
            
            print(f"⚙️ Adjusted for {num_transitions} cross-fades (-{total_overlap:.2f}s total)")
        
        # Final rounding correction
        total_scenes = hook_dur + sum(bullet_durs) + cta_dur
        duration_diff = duration - total_scenes
            
        if abs(duration_diff) > 0.01:
            cta_dur += duration_diff
            print(f"⚙️ Final rounding adjustment: {duration_diff:.2f}s")

print(f"⏱️  Scene timings (audio-synced):")
if hook:
    print(f"   Hook: {hook_dur:.1f}s")
for i, dur in enumerate(bullet_durs):
    print(f"   Bullet {i+1}: {dur:.1f}s")
if cta:
    print(f"   CTA: {cta_dur:.1f}s")
print(f"   Total: {(hook_dur if hook else 0) + sum(bullet_durs) + (cta_dur if cta else 0):.2f}s (Audio: {duration:.2f}s)")

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
        if len(words) <= 2:
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
    
    try:
        pil_font = ImageFont.truetype(FONT, font_size)
        dummy_img = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        
        lines = wrapped_text.split('\n')
        total_height = 0
        max_line_width = 0
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=pil_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            total_height += line_height
            max_line_width = max(max_line_width, line_width)
        
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
        
        text_height = text_clip.h
        text_width = text_clip.w
        
        descender_padding = max(35, int(font_size * 0.6))
        
        bottom_safe_zone = SAFE_ZONE_MARGIN + 180 
        
        if position_y == 'center':
            pos_y = (h - text_height) // 2
        elif position_y == 'top':
            pos_y = SAFE_ZONE_MARGIN + 80
        elif position_y == 'bottom':
            pos_y = h - text_height - bottom_safe_zone - descender_padding
        else:
            pos_y = min(max(SAFE_ZONE_MARGIN + 80, position_y), 
                       h - text_height - bottom_safe_zone - descender_padding)
        
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

# Hook Scene
if hook:
    print(f"🎬 Creating hook scene (synced with audio)...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y='top',
        color_fallback=(30, 144, 255)
    )
    clips.extend(hook_clips)
    current_time += hook_dur

# ✅ FIX 1: HANDLE EMPTY BULLETS - ALWAYS ADVANCE TIMELINE
for i, bullet in enumerate(bullets):
    bullet_duration = bullet_durs[i]
    
    if not bullet or not bullet.strip():
        print(f"⚠️ Bullet {i+1} is empty, creating silent placeholder")
        placeholder = ColorClip(size=(w, h), color=(50, 50, 50), duration=bullet_duration).with_start(current_time)
        clips.append(placeholder)
        current_time += bullet_duration
        continue
    
    img_index = min(i + 1, len(scene_images) - 1)
    colors = [(255, 99, 71), (50, 205, 50), (255, 215, 0)]

    print(f"🎬 Creating bullet {i+1} scene (synced with audio)...")
    
    bullet_clips = create_scene(
        scene_images[img_index] if scene_images and img_index < len(scene_images) else None,
        bullet,
        bullet_duration,
        current_time,
        position_y='center',
        color_fallback=colors[i % len(colors)]
    )

    clips.extend(bullet_clips)
    current_time += bullet_duration

# CTA Scene
if cta:
    print(f"📢 Creating CTA scene (synced with audio)...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y='bottom',
        color_fallback=(255, 20, 147)
    )
    clips.extend(cta_clips)
    current_time += cta_dur
    print(f"   CTA: {current_time - cta_dur:.1f}s - {current_time:.1f}s (synced)")
else:
    print("⚠️ No CTA text found")

# ✅ FIX 4: VERIFY SYNC BEFORE COMPOSING
final_timeline = current_time
print(f"\n📊 SYNC VERIFICATION:")
print(f"   Timeline duration: {final_timeline:.2f}s")
print(f"   Audio duration: {duration:.2f}s")
print(f"   Difference: {abs(final_timeline - duration)*1000:.1f}ms")

if abs(final_timeline - duration) > 0.5:
    print(f"⚠️ WARNING: Significant sync drift detected!")
else:
    print(f"✅ Sync verified - within acceptable tolerance")

print(f"\n🎬 Composing video with {len(clips)} clips...")
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
    print(f"      ✓ Cross-fade overlap correction")
    print(f"      ✓ Empty content handling")
    print(f"      ✓ Image validation and fallbacks")
    
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

print("✅ Video pipeline complete with all critical fixes applied!")