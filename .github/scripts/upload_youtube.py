# .github/scripts/upload_youtube.py
import os
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential
from PIL import Image
import re 
import subprocess

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")
READY_VIDEO = os.path.join(TMP, "short_ready.mp4")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

# ---- Load Global Metadata ONCE ----
try:
    with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("❌ Error: script.json not found.")
    raise

title = data.get("title", "AI Short")
description = data.get("description", f"{title}")
hashtags = data.get("hashtags", ["#shorts", "#viral", "#trending"])
topic = data.get("topic", "general")

# ---- Step 1: Validate video ----
if not os.path.exists(VIDEO):
    raise FileNotFoundError(f"Video file not found: {VIDEO}")

video_size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
print(f"📹 Video file found: {VIDEO} ({video_size_mb:.2f} MB)")
if video_size_mb < 0.1:
    raise ValueError("Video file is too small, likely corrupted")

# ---- Step 2: Embed thumbnail as fade-in intro ----
if os.path.exists(THUMB):
    print("🎨 Embedding thumbnail as intro frame with fade transition...")

    # Get video dimensions and fps
    try:
        probe_cmd = [
            "ffprobe", 
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0",
            VIDEO
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        video_info = result.stdout.strip().split(',')
        video_width, video_height = int(video_info[0]), int(video_info[1])
        
        # Parse fps (format: "30/1" or "30000/1001")
        fps_parts = video_info[2].split('/')
        video_fps = int(fps_parts[0]) / int(fps_parts[1])
        
        print(f"📐 Video dimensions: {video_width}x{video_height} @ {video_fps:.2f} fps")
        
    except Exception as e:
        print(f"⚠️ Could not get video info: {e}")
        print("⚠️ Using original video without thumbnail embed.")
        video_width, video_height, video_fps = 1080, 1920, 30

    THUMB_DURATION = 1.0
    FADE_DURATION = 0.2

    # ✅ FIXED: Proper FFmpeg filter with correct settb placement AFTER fps
    ffmpeg_args = [
        "ffmpeg", 
        "-y",
        "-loop", "1", 
        "-t", str(THUMB_DURATION), 
        "-framerate", str(video_fps),
        "-i", THUMB,
        "-i", VIDEO,
        "-filter_complex", 
        # ✅ CRITICAL FIX: settb MUST come AFTER fps (fps resets timebase)
        f"[0:v]scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
        f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1,fps={video_fps},settb=AVTB,setpts=PTS-STARTPTS[thumb_scaled];"
        f"[1:v]settb=AVTB,setpts=PTS-STARTPTS[video_scaled];"
        f"[thumb_scaled][video_scaled]xfade=transition=fade:duration={FADE_DURATION}:offset={THUMB_DURATION - FADE_DURATION}[v_out]",
        "-map", "[v_out]",
        "-map", "1:a?",
        "-c:v", "libx264", 
        "-preset", "ultrafast", 
        "-pix_fmt", "yuv420p", 
        "-c:a", "copy",
        "-shortest",
        READY_VIDEO
    ]
    
    try:
        print("🔄 Processing thumbnail embed with proper timebase...")
        result = subprocess.run(ffmpeg_args, check=True, capture_output=True, text=True)
        
        if os.path.exists(READY_VIDEO) and os.path.getsize(READY_VIDEO) > 100000:
            ready_size_mb = os.path.getsize(READY_VIDEO) / (1024 * 1024)
            VIDEO = READY_VIDEO
            print(f"✅ Thumbnail embedded successfully! New size: {ready_size_mb:.2f} MB")
        else:
            raise Exception("Output file was created but is too small.")

    except subprocess.CalledProcessError as e:
        print(f"⚠️ Thumbnail embedding failed (FFmpeg error):")
        print(f"   {e.stderr[:500]}")  # Show only first 500 chars of error
        print("⚠️ Using original video without thumbnail intro.")
    except Exception as e:
        print(f"⚠️ Thumbnail embedding failed: {e}")
        print("⚠️ Using original video without thumbnail intro.")

else:
    print("⚠️ Thumbnail not found, skipping embed step.")

# ---- Step 2.5: Rename video to safe filename ----
safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
video_output_path = os.path.join(TMP, f"{safe_title}.mp4")

if VIDEO != video_output_path:
    if os.path.exists(VIDEO):
        try:
            os.rename(VIDEO, video_output_path)
            VIDEO = video_output_path
            print(f"🎬 Final video renamed to: {video_output_path}")
        except Exception as e:
            print(f"⚠️ Renaming failed: {e}. Using original path.")
    else:
        print("⚠️ Video file not found before rename.")
else:
    print("🎬 Video already has the correct filename.")

# ---- Step 3: Authenticate ----
try:
    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    print("✅ YouTube API authenticated")
except Exception as e:
    print(f"❌ Authentication failed: {e}")
    raise

# ---- Step 4: Prepare metadata ----
enhanced_description = f"""{description}

{' '.join(hashtags)}

---
Follow Ascent Dragox For More!
Created: {datetime.now().strftime('%Y-%m-%d')}
Topic: {topic}
"""

tags = ["shorts", "viralshorts", topic, "trending", "fyp"]
if hashtags:
    tags.extend([tag.replace('#', '') for tag in hashtags[:10]])
tags = list(set(tags))[:15]

print(f"📝 Metadata ready:")
print(f"   Title: {title}")
print(f"   Tags: {', '.join(tags[:10])}...")
print(f"   Hashtags: {' '.join(hashtags[:3])}...")

snippet = {
    "title": title[:100],
    "description": enhanced_description[:5000],
    "tags": tags,
    "categoryId": "28"
}

body = {
    "snippet": snippet,
    "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
        "madeForKids": False
    }
}

print(f"📤 Uploading video to YouTube...")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
def upload_video(youtube_client, video_path, metadata):
    media = MediaFileUpload(
        video_path,
        chunksize=1024*1024,
        resumable=True,
        mimetype="video/mp4"
    )
    
    request = youtube_client.videos().insert(
        part="snippet,status",
        body=metadata,
        media_body=media
    )
    
    response = None
    last_progress = 0
    
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            if progress != last_progress and progress % 10 == 0:
                print(f"⏳ Upload progress: {progress}%")
                last_progress = progress
    return response

try:
    print("🚀 Starting upload...")
    result = upload_video(youtube, VIDEO, body)
    video_id = result["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    
    print(f"✅ Video uploaded successfully!")
    print(f"   Video ID: {video_id}")
    print(f"   Watch URL: {video_url}")
    print(f"   Shorts URL: {shorts_url}")

except HttpError as e:
    print(f"❌ HTTP error during upload: {e}")
    error_content = e.content.decode() if hasattr(e, 'content') else str(e)
    print(f"   Error details: {error_content}")
    raise
except Exception as e:
    print(f"❌ Upload failed: {e}")
    raise

# ---- Step 6: Set thumbnail (desktop view) ----
if os.path.exists(THUMB):
    try:
        print("🖼️ Setting thumbnail for desktop views...")
        thumb_size_mb = os.path.getsize(THUMB) / (1024*1024)
        if thumb_size_mb > 2:
            print(f"⚠️ Compressing thumbnail ({thumb_size_mb:.2f}MB)...")
            img = Image.open(THUMB)
            img.save(THUMB, quality=85, optimize=True)
        
        youtube.thumbnails().set(
            videoId=video_id, 
            media_body=MediaFileUpload(THUMB)
        ).execute()
        print("✅ Thumbnail set successfully (desktop view).")
    except Exception as e:
        print(f"⚠️ Thumbnail upload failed: {e}")
else:
    print("⚠️ No thumbnail file found, skipping thumbnail set.")

# ---- Step 7: Save upload history ----
upload_metadata = {
    "video_id": video_id,
    "title": title,
    "topic": topic,
    "upload_date": datetime.now().isoformat(),
    "video_url": video_url,
    "shorts_url": shorts_url,
    "hashtags": hashtags,
    "file_size_mb": video_size_mb,
    "tags": tags
}

history = []
if os.path.exists(UPLOAD_LOG):
    try:
        with open(UPLOAD_LOG, 'r') as f:
            history = json.load(f)
    except:
        history = []

history.append(upload_metadata)
history = history[-100:]  # Keep last 100 uploads

with open(UPLOAD_LOG, 'w') as f:
    json.dump(history, f, indent=2)

print("\n" + "="*60)
print("🎉 UPLOAD COMPLETE!")
print("="*60)
print(f"Title: {title}")
print(f"Topic: {topic}")
print(f"Video ID: {video_id}")
print(f"Shorts URL: {shorts_url}")
print(f"Hashtags: {' '.join(hashtags[:5])}")
print("="*60)
print("\n💡 Tip: Share the Shorts URL for better mobile reach!")
print(f"🔗 {shorts_url}")