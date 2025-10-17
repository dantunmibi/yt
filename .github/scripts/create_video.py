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
    """Generate image using Hugging Face"""
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
                "width": width,
                "height": height,
            }
        }
        
        print(f"🤗 Hugging Face Image: {prompt[:60]}...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
        
        if response.status_code == 200:
            if len(response.content) > 1000:
                filepath = os.path.join(TMP, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print("   ✅ Hugging Face thumbnail generated")
                return filepath
            else:
                raise Exception("Empty image received")
        
        elif response.status_code == 503:
            print(f"   ⚠️ Model is loading (503), will retry...")
            raise Exception("Model loading")

        elif response.status_code == 402:

            print(f"   ⚠️ Hugging Face 402: Quota exceeded or billing issue")

            raise Exception("402 quota error")
        
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
        print(f"⚠️ Hugging Face image failed: {e}")
        raise

def generate_image_pollinations(prompt, filename, width=1080, height=1920):
    """Pollinations as backup"""
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width={width}&height={height}&nologo=true"
        print(f"   🌐 Pollinations: {prompt[:50]}...")
        response = requests.get(url, timeout=120)
        
        if response.status_code == 200:
            filepath = os.path.join(TMP, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Pollinations saved to {filename}")
            return filepath
        else:
            raise Exception(f"Pollinations failed: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Pollinations failed: {e}")
        raise

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=25))
def generate_image_reliable(prompt, filename, width=1080, height=1920):
    """Try multiple image generation providers in order"""
    providers = [
        ("Hugging Face", generate_image_huggingface),
        ("Pollinations", generate_image_pollinations)
    ]
    
    for provider_name, provider_func in providers:
        try:
            result = provider_func(prompt, filename, width, height)
            if result and os.path.exists(result):
                return result
        except Exception as e:
            print(f"   ⚠️ {provider_name} failed: {e}")
            continue
    
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

print("🎨 Generating scene images with reliable providers...")
scene_images = []

try:
    hook_prompt = visual_prompts[0] if len(visual_prompts) > 0 else f"Eye-catching dramatic opening for: {hook}, cinematic lighting, vibrant colors"
    hook_img = generate_image_reliable(hook_prompt, "scene_hook.jpg")
    scene_images.append(hook_img)
    
    for i, bullet in enumerate(bullets):
        bullet_prompt = visual_prompts[i+1] if len(visual_prompts) > i+1 else f"Visual representation: {bullet}, photorealistic, vibrant, engaging"
        bullet_img = generate_image_reliable(bullet_prompt, f"scene_bullet_{i}.jpg")
        scene_images.append(bullet_img)
    
    successful_images = len([img for img in scene_images if img is not None])
    print(f"✅ Generated {successful_images} AI images, {len(scene_images) - successful_images} fallbacks")
    
except Exception as e:
    print(f"⚠️ Image generation failed: {e}, using all fallbacks")
    scene_images = [None] * 4

if not os.path.exists(audio_path):
    print(f"❌ Audio file not found: {audio_path}")
    raise FileNotFoundError("voice.mp3 not found")

audio = AudioFileClip(audio_path)
duration = audio.duration
print(f"🎵 Audio loaded: {duration:.2f} seconds")

# 🔍 Prefer real per-section durations if available
def get_audio_duration(path):
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
print(f"   Hook: {hook_dur:.1f}s")
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
        avg_char_width = font_size * 0.6
        max_chars_per_line = int(max_width / avg_char_width)
        
        words = text.split()
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
        
        return '\n'.join(lines)
    
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
    
    return '\n'.join(lines)

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
        
        # ✅ FIXED: Use basic TextClip with proper descender spacing
        text_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            color='white',
            stroke_color='black',
            stroke_width=6,
            method='label',
            text_align='center'
        )
        
        # Calculate safe position with proper descender space
        text_height = text_clip.h
        text_width = text_clip.w
        
        # Add extra padding for descenders (20-30px depending on font size)
        descender_padding = max(25, int(font_size * 0.4))
        
        # Calculate vertical positioning with proper safety margins
        if position_y == 'center':
            pos_y = (h - text_height) // 2
        elif position_y == 'top':
            # Top position: safe from notification area
            pos_y = SAFE_ZONE_MARGIN + 80
        elif position_y == 'bottom':
            # Bottom position: safe from UI elements + descender space
            pos_y = h - text_height - SAFE_ZONE_MARGIN - descender_padding - 60
        else:
            # For numeric positions, ensure they're safe
            pos_y = min(max(SAFE_ZONE_MARGIN + 80, position_y), 
                       h - text_height - SAFE_ZONE_MARGIN - descender_padding - 60)
        
        # Final safety check with proper margins
        bottom_limit = h - SAFE_ZONE_MARGIN - descender_padding - 60
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

        print(f"         Bottom edge: {bottom_pos}px")

        print(f"         Screen: {h}px height")

        print(f"         Clearance: Top={top_clearance}px, Bottom={bottom_clearance}px")

        print(f"         Descender padding: {descender_padding}px")

        

        if bottom_clearance < 120:

            print(f"         ⚠️ WARNING: Bottom clearance is low! ({bottom_clearance}px)")
        
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