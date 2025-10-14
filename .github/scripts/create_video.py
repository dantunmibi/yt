# .github/scripts/create_video.py
import os
import json
import requests
from moviepy import *
import platform
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
OUT = os.path.join(TMP, "short.mp4")
w, h = 1080, 1920

# Safe zones for text (avoiding screen edges)
SAFE_ZONE_MARGIN = 120
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

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_image(prompt, filename, width=1080, height=1920):
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width={width}&height={height}&nologo=true"
        print(f"   Generating: {prompt[:60]}...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            filepath = os.path.join(TMP, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"   ✅ Saved to {filename}")
            return filepath
        else:
            raise Exception(f"Image generation failed with status {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        raise

print("🎨 Generating scene images...")
scene_images = []

try:
    hook_prompt = visual_prompts[0] if len(visual_prompts) > 0 else f"Eye-catching dramatic opening for: {hook}, cinematic lighting, vibrant colors"
    hook_img = generate_image(hook_prompt, "scene_hook.jpg")
    scene_images.append(hook_img)
    
    for i, bullet in enumerate(bullets):
        bullet_prompt = visual_prompts[i+1] if len(visual_prompts) > i+1 else f"Visual representation: {bullet}, photorealistic, vibrant, engaging"
        bullet_img = generate_image(bullet_prompt, f"scene_bullet_{i}.jpg")
        scene_images.append(bullet_img)
    
    print(f"✅ Generated {len(scene_images)} unique images")
    
except Exception as e:
    print(f"⚠️ Image generation failed: {e}, using fallback")
    scene_images = []
    for i in range(4):
        scene_images.append(None)

audio_path = os.path.join(TMP, "voice.mp3")
if not os.path.exists(audio_path):
    print(f"❌ Audio file not found: {audio_path}")
    raise FileNotFoundError("voice.mp3 not found")

audio = AudioFileClip(audio_path)
duration = audio.duration
print(f"🎵 Audio loaded: {duration:.2f} seconds")

# Calculate timing based on word count for better sync
def estimate_speech_duration(text):
    """Estimate duration based on average speaking rate (150 words/min)"""
    words = len(text.split())
    return (words / 150) * 60  # seconds

hook_estimated = estimate_speech_duration(hook) if hook else 0
bullets_estimated = [estimate_speech_duration(b) for b in bullets]
cta_estimated = estimate_speech_duration(cta) if cta else 0

# Adjust durations to fit actual audio length
total_estimated = hook_estimated + sum(bullets_estimated) + cta_estimated
time_scale = duration / max(total_estimated, 1)

hook_dur = min(hook_estimated * time_scale, duration * 0.2) if hook else 0
cta_dur = min(cta_estimated * time_scale, duration * 0.2) if cta else 0
bullets_dur = duration - hook_dur - cta_dur

# Distribute bullet time proportionally
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
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)

def create_text_with_effects(text, font_size=64, max_width=TEXT_MAX_WIDTH):
    """Create text with clean visibility"""
    
    wrapped_text = smart_text_wrap(text, font_size, max_width)
    
    test_clip = TextClip(
        text=wrapped_text,
        font=FONT,
        font_size=font_size,
        method='label',
        text_align='center'
    )
    
    # More conservative height limit to prevent cutoff
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
        font_size -= 4
        wrapped_text = smart_text_wrap(text, font_size, max_width - 80)
        test_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            method='label',
            text_align='center'
        )
    
    return wrapped_text, font_size

def create_scene(image_path, text, duration, start_time, position_y='center', color_fallback=(30, 30, 30)):
    """Create a scene with clean, highly visible text"""
    scene_clips = []
    
    # Background
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
        # Adaptive font sizing and smart wrapping
        wrapped_text, font_size = create_text_with_effects(text)
        
        # Calculate actual position to ensure text stays in safe zone
        temp_clip = TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            method='label',
            text_align='center'
        )
        text_height = temp_clip.h
        text_width = temp_clip.w
        
        # Conservative padding to prevent cutoff
        text_height_with_padding = int(text_height * 1.3)
        
        # Determine safe Y position
        if position_y == 'center':
            pos_y = (h - text_height_with_padding) // 2
        elif isinstance(position_y, int):
            min_y = SAFE_ZONE_MARGIN + 40
            max_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 80
            
            pos_y = max(min_y, min(position_y, max_y))
            
            if position_y > h * 0.6:
                pos_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 120
        else:
            pos_y = SAFE_ZONE_MARGIN + 40
        
        # Final safety adjustments
        absolute_max_y = h - SAFE_ZONE_MARGIN - text_height_with_padding - 100
        if pos_y > absolute_max_y:
            pos_y = absolute_max_y
        
        if pos_y < SAFE_ZONE_MARGIN + 40:
            pos_y = SAFE_ZONE_MARGIN + 40
        
        print(f"      Text: '{wrapped_text[:30]}...'")
        print(f"         Position: Y={pos_y}, Height={text_height}px")
        print(f"         Font: {font_size}px")
        
        # SINGLE clean text layer with thick stroke - no complex shadows
        main_text = (TextClip(
            text=wrapped_text,
            font=FONT,
            font_size=font_size,
            color='white',
            method='label',
            text_align='center',
            stroke_color='black',
            stroke_width=8  # Thicker stroke for better visibility
        )
        .with_duration(duration)
        .with_start(start_time)
        .with_position(('center', pos_y))
        .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)]))
        
        # Add only the main text layer
        scene_clips.append(main_text)
    
    return scene_clips

# Hook scene
if hook:
    print(f"🎬 Creating hook scene (synced with audio)...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y=400,  # Adjusted for better visibility
        color_fallback=(30, 144, 255)
    )
    clips.extend(hook_clips)
    current_time += hook_dur
else:
    print("⚠️ No hook text found")

# Bullet scenes with audio sync
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
        position_y=900,  # Adjusted position
        color_fallback=colors[i % len(colors)]
    )
    clips.extend(bullet_clips)
    print(f"   Bullet {i+1}: {current_time:.1f}s - {current_time + bullet_durs[i]:.1f}s (synced)")
    current_time += bullet_durs[i]

# CTA scene
if cta:
    print(f"📢 Creating CTA scene (synced with audio)...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y=1400,  # Adjusted for better visibility
        color_fallback=(255, 20, 147)
    )
    clips.extend(cta_clips)
    print(f"   CTA: {current_time:.1f}s - {current_time + cta_dur:.1f}s (synced)")
else:
    print("⚠️ No CTA text found")

# Compose final video
print(f"🎬 Composing video with {len(clips)} clips...")
video = CompositeVideoClip(clips, size=(w, h))

# Attach audio
print(f"🔊 Attaching audio...")
video = video.with_audio(audio)

if video.audio is None:
    print("❌ ERROR: No audio attached to video!")
    raise Exception("Audio failed to attach")
else:
    print(f"✅ Audio verified: {video.audio.duration:.2f}s")
    print(f"✅ Text-audio synchronization: ENABLED")

# Write video
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
    print(f"      ✓ Clean text with thick stroke (no messy shadows)")
    print(f"      ✓ Guaranteed text visibility")
    print(f"      ✓ Audio-synchronized timing")
    print(f"      ✓ Conservative positioning to prevent cutoff")
    
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

print("✅ Video pipeline complete with clean text visibility!")