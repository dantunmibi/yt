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

# Get system font path
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

# Load script JSON
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
    """Generate image with Pollinations AI"""
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

# Generate unique images for each scene
print("🎨 Generating scene images...")
scene_images = []

try:
    # Hook scene
    hook_prompt = visual_prompts[0] if len(visual_prompts) > 0 else f"Eye-catching dramatic opening for: {hook}, cinematic lighting, vibrant colors"
    hook_img = generate_image(hook_prompt, "scene_hook.jpg")
    scene_images.append(hook_img)
    
    # Bullet scenes
    for i, bullet in enumerate(bullets):
        bullet_prompt = visual_prompts[i+1] if len(visual_prompts) > i+1 else f"Visual representation: {bullet}, photorealistic, vibrant, engaging"
        bullet_img = generate_image(bullet_prompt, f"scene_bullet_{i}.jpg")
        scene_images.append(bullet_img)
    
    print(f"✅ Generated {len(scene_images)} unique images")
    
except Exception as e:
    print(f"⚠️ Image generation failed: {e}, using fallback")
    # Create fallback colored backgrounds
    scene_images = []
    colors = [(30, 144, 255), (255, 99, 71), (50, 205, 50), (255, 215, 0)]
    for i in range(4):
        scene_images.append(None)  # Will use color clips instead

# Load audio
audio_path = os.path.join(TMP, "voice.mp3")
if not os.path.exists(audio_path):
    print(f"❌ Audio file not found: {audio_path}")
    raise FileNotFoundError("voice.mp3 not found")

audio = AudioFileClip(audio_path)
duration = audio.duration
print(f"🎵 Audio loaded: {duration:.2f} seconds")

# Calculate scene durations
hook_dur = min(3.5, duration * 0.15)  # 15% for hook, max 3.5s
cta_dur = min(3, duration * 0.15)  # 15% for CTA, max 3s
bullets_dur = duration - hook_dur - cta_dur
bullet_dur = bullets_dur / max(1, len(bullets))

print(f"⏱️  Scene timings:")
print(f"   Hook: {hook_dur:.1f}s")
print(f"   Each bullet: {bullet_dur:.1f}s")
print(f"   CTA: {cta_dur:.1f}s")

clips = []
current_time = 0

# Helper function to create scene with image and text
def create_scene(image_path, text, duration, start_time, position_y='center', color_fallback=(30, 30, 30)):
    """Create a scene with background image and text overlay"""
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
    
    # Text overlay with shadow effect
    if text:
        # Shadow text
        shadow = (TextClip(
            text=text,
            font=FONT,
            font_size=64,
            color='black',
            method='caption',
            size=(w - 120, None),
            text_align='center'
        )
        .with_duration(duration)
        .with_start(start_time)
        .with_position(('center', position_y if position_y != 'center' else 'center'))
        .with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.2)]))
        
        # Main text
        main_text = (TextClip(
            text=text,
            font=FONT,
            font_size=64,
            color='white',
            method='caption',
            size=(w - 120, None),
            text_align='center',
            stroke_color='black',
            stroke_width=2
        )
        .with_duration(duration)
        .with_start(start_time)
        .with_position(('center', position_y if position_y != 'center' else 'center'))
        .with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.2)]))
        
        scene_clips.extend([shadow, main_text])
    
    return scene_clips

# Hook scene
if hook:
    print(f"🎬 Creating hook scene...")
    hook_clips = create_scene(
        scene_images[0] if scene_images else None,
        hook,
        hook_dur,
        current_time,
        position_y=300,
        color_fallback=(30, 144, 255)
    )
    clips.extend(hook_clips)
    current_time += hook_dur
else:
    print("⚠️ No hook text found")

# Bullet scenes
print(f"📋 Creating {len(bullets)} bullet scenes...")
for i, bullet in enumerate(bullets):
    if not bullet:
        continue
    
    img_index = min(i + 1, len(scene_images) - 1)
    colors = [(255, 99, 71), (50, 205, 50), (255, 215, 0)]
    
    bullet_clips = create_scene(
        scene_images[img_index] if scene_images else None,
        bullet,
        bullet_dur,
        current_time,
        position_y=800,
        color_fallback=colors[i % len(colors)]
    )
    clips.extend(bullet_clips)
    current_time += bullet_dur
    print(f"   Bullet {i+1}: {current_time-bullet_dur:.1f}s - {current_time:.1f}s")

# CTA scene
if cta:
    print(f"📢 Creating CTA scene...")
    cta_clips = create_scene(
        scene_images[-1] if scene_images else None,
        cta,
        cta_dur,
        current_time,
        position_y=1400,
        color_fallback=(255, 20, 147)
    )
    clips.extend(cta_clips)
else:
    print("⚠️ No CTA text found")

# Compose final video
print(f"🎬 Composing video with {len(clips)} clips...")
video = CompositeVideoClip(clips, size=(w, h))

# Attach audio
print(f"🔊 Attaching audio...")
video = video.with_audio(audio)

# Verify audio is attached
if video.audio is None:
    print("❌ ERROR: No audio attached to video!")
    raise Exception("Audio failed to attach")
else:
    print(f"✅ Audio verified: {video.audio.duration:.2f}s")

# Write video
print(f"📹 Writing video file to {OUT}...")
try:
    video.write_videofile(
        OUT,
        fps=30,  # Increased from 24 for smoother playback
        codec="libx264",
        audio_codec="aac",
        threads=4,  # Increased from 2
        preset='medium',
        audio_bitrate='192k',
        bitrate='8000k',  # Higher quality
        logger=None  # Suppress verbose output
    )
    
    print(f"✅ Video created successfully!")
    print(f"   Path: {OUT}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Size: {os.path.getsize(OUT) / (1024*1024):.2f} MB")
    
    # Verify output file
    if not os.path.exists(OUT) or os.path.getsize(OUT) < 100000:
        raise Exception("Output video is missing or too small")
    
except Exception as e:
    print(f"❌ Video creation failed: {e}")
    raise

finally:
    # Clean up resources
    print("🧹 Cleaning up...")
    audio.close()
    video.close()
    
    # Close all image clips
    for clip in clips:
        try:
            clip.close()
        except:
            pass

print("✅ Video pipeline complete!")