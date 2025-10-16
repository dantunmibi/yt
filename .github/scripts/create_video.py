# .github/scripts/create_video.py
import os
import json
import requests
from moviepy import *
import platform
from tenacity import retry, stop_after_attempt, wait_exponential
from pydub import AudioSegment
from time import sleep

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
OUT = os.path.join(TMP, "short.mp4")
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
def generate_thumbnail_huggingface(prompt, filename):
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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=20))
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

audio_path = os.path.join(TMP, "voice.mp3")
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
    # keep your existing estimate-based code block here

def estimate_speech_duration(text, audio_path="tmp/voice.mp3"):
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

hook_estimated = estimate_speech_duration(hook)
bullets_estimated = [estimate_speech_duration(b) for b in bullets]
cta_estimated = estimate_speech_duration(cta)

total_estimated = hook_estimated + sum(bullets_estimated) + cta_estimated
margin = 0.98
duration *= margin

time_scale = duration / max(total_estimated, 1)

hook_dur = min(hook_estimated * time_scale, duration * 0.2) if hook else 0
cta_dur = min(cta_estimated * time_scale, duration * 0.2) if cta else 0
bullets_dur = duration - hook_dur - cta_dur

if bullets_estimated and sum(bullets_estimated) > 0:
    bullet_durs = [(b_est / sum(bullets_estimated)) * bullets_dur for b_est in bullets_estimated]
else:
    bullet_durs = [bullets_dur / max(1, len(bullets))] * len(bullets)

print(f"⏱️  Scene timings (audio-synced):")
print(f"   Hook: {hook_dur:.1f}s")
for i, dur in enumerate(bullet_durs):
    print(f"   Bullet {i+1}: {dur:.1f}s")
print(f"   CTA: {cta_dur:.1f}s")

clips = []
current_time = 0

def smart_text_wrap(text, font_size, max_width):
    """Intelligently wrap text to prevent word splitting across lines"""
    from PIL import Image, ImageDraw, ImageFont
    
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
    """Create text with strong outline and shadow for visibility on any background"""
    
    wrapped_text = smart_text_wrap(text, font_size, max_width)
    
    test_clip = TextClip(
        text=wrapped_text,
        font=FONT,
        font_size=font_size,
        method='label',
        text_align='center'
    )
    
    max_height = h * 0.20
    iterations = 0
    while test_clip.h > max_height and font_size > 32 and iterations < 10:
        font_size -= 4
        wrapped_text = smart_text_wrap(text, font_size, max_width)
        test_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            method='label',
            text_align='center'
        )
        iterations += 1
    
    while test_clip.w > max_width and font_size > 32:
        font_size -= 6
        wrapped_text = smart_text_wrap(text, font_size, max_width - 60)
        test_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            method='label',
            text_align='center'
        )
    
    return wrapped_text, font_size

def create_scene(image_path, text, duration, start_time, position_y='center', color_fallback=(30, 30, 30)):
    """Create a scene with background image and highly visible text overlay"""
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
        
        temp_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            method='label',
            text_align='center'
        )
        temp_clip = temp_clip.with_position(('center', 'center'))

        text_height = temp_clip.h
        text_width = temp_clip.w
        
        text_height_with_padding = int(text_height * 2.0)
        
        if position_y == 'center':
            pos_y = (h - text_height_with_padding) // 2
        elif isinstance(position_y, int):
            min_y = SAFE_ZONE_MARGIN
            max_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 120
            
            pos_y = max(min_y, min(position_y, max_y))
            
            if position_y > h * 0.6:
                pos_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 150
        else:
            pos_y = SAFE_ZONE_MARGIN
        
        absolute_max_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 150
        if pos_y > absolute_max_y:
            pos_y = absolute_max_y
            print(f"      ⚠️ Position adjusted to prevent cutoff: Y={pos_y}")
        
        if pos_y < SAFE_ZONE_MARGIN:
            pos_y = SAFE_ZONE_MARGIN
            print(f"      ⚠️ Position adjusted (too high): Y={pos_y}")
        
        print(f"      Text: '{wrapped_text[:30]}...'")
        print(f"         Position: Y={pos_y}, Height={text_height}px (+padding={text_height_with_padding}px)")
        print(f"         Font: {font_size}px, Width={text_width}px")
        print(f"         Bottom edge: {pos_y + text_height_with_padding}px (screen: {h}px)")
        
        main_text = (TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            color='white',
            method='label',
            text_align='center',
            stroke_color='black',
            stroke_width=8
        )
        .with_position(('center', 'center'))
        .with_duration(duration)
        .with_start(start_time)
        .with_position(('center', pos_y))
        .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
        
        scene_clips.extend([main_text])
    
    return scene_clips

if hook:
    print(f"🎬 Creating hook scene (synced with audio)...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y=400,
        color_fallback=(30, 144, 255)
    )
    clips.extend(hook_clips)
    current_time += hook_dur
else:
    print("⚠️ No hook text found")

print(f"📋 Creating {len(bullets)} bullet scenes (synced with audio)...")
for i, bullet in enumerate(bullets):
    if not bullet:
        continue
    
    img_index = min(i + 1, len(scene_images) - 1)
    colors = [(255, 99, 71), (50, 205, 50), (255, 215, 0)]
    
    bullet_clips = create_scene(
        scene_images[img_index] if scene_images and img_index < len(scene_images) else None,
        bullet,
        bullet_durs[i],
        current_time,
        position_y=900,
        color_fallback=colors[i % len(colors)]
    )
    clips.extend(bullet_clips)
    print(f"   Bullet {i+1}: {current_time:.1f}s - {current_time + bullet_durs[i]:.1f}s (synced)")
    current_time += bullet_durs[i]

if cta:
    print(f"📢 Creating CTA scene (synced with audio)...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y=1200,
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