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

# Insert this block near the beginning of the script, after file path definitions

# ---- Load Global Metadata ONCE ----
try:
    with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("❌ Error: script.json not found.")
    raise # Stop if the main script data is missing

title = data.get("title", "AI Short")
description = data.get("description", f"{title}")
hashtags = data.get("hashtags", ["#shorts", "#viral", "#trending"])
topic = data.get("topic", "general")
# ------------------------------------

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
    THUMB_DURATION = 0.6
    FADE_DURATION = 0.3

    # Use subprocess for better error handling and security
    ffmpeg_args = [
        "ffmpeg", 
        "-y", # Overwrite output files without asking
        "-loop", "1", "-t", str(THUMB_DURATION), "-i", THUMB,
        "-i", VIDEO,
        "-filter_complex", 
        f"[0:v][1:v]xfade=transition=fade:duration={FADE_DURATION}:offset={THUMB_DURATION - FADE_DURATION},format=yuv420p",
        "-c:v", "libx264", 
        "-preset", "ultrafast", 
        "-pix_fmt", "yuv420p", 
        READY_VIDEO
    ]
    
    try:
        subprocess.run(ffmpeg_args, check=True, capture_output=True, text=True)
        
        if os.path.exists(READY_VIDEO) and os.path.getsize(READY_VIDEO) > 0:
            VIDEO = READY_VIDEO
            print("✅ Thumbnail embedded successfully!")
        else:
            raise Exception("Output file was created but is empty.")

    except subprocess.CalledProcessError as e:
        print(f"⚠️ Thumbnail embedding failed (FFmpeg error): {e.stderr}")
        print("⚠️ Using original video.")
    except Exception as e:
        print(f"⚠️ Thumbnail embedding failed: {e}")
        print("⚠️ Using original video.")

else:
    print("⚠️ Thumbnail not found, skipping embed step.")

# -------------------------------------------------------------------------
# ---- Step 2.5: UNCONDITIONAL Renaming and Final Path Setup ----
# -------------------------------------------------------------------------
safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
video_output_path = os.path.join(TMP, f"{safe_title}.mp4")

# Rename the final video file (VIDEO holds either the original or the ready_video path)
if VIDEO != video_output_path:
    if os.path.exists(VIDEO):
        try:
            os.rename(VIDEO, video_output_path)
            VIDEO = video_output_path
            print(f"🎬 Final video renamed to: {video_output_path}")
        except Exception as e:
            # If rename fails (e.g., permissions), at least we know the path for upload
            VIDEO = video_output_path
            print(f"⚠️ Renaming failed: {e}. Proceeding with original file at final path: {VIDEO}")
    else:
        # This case should be impossible if Step 1 succeeded, but set final path anyway
        VIDEO = video_output_path
        print("⚠️ File not found before rename. Setting final upload path.")
else:
    print("🎬 Video already has the correct title name. Proceeding.")
# -------------------------------------------------------------------------

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

# ---- Step 4: Load metadata ----

enhanced_description = f"""{description}

{' '.join(hashtags)}

---
Follow Ascent Dragox For More!
Created: {datetime.now().strftime('%Y-%m-%d')}
Topic: {topic}
"""

tags = ["shorts", "viral", "trending", topic, "ai"]
if hashtags:
    tags.extend([tag.replace('#', '') for tag in hashtags[:10]])
tags = list(set(tags))[:15]

print(f"📝 Metadata ready:")
print(f"   Title: {title}")
print(f"   Tags: {', '.join(tags[:5])}...")
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
            Image.open(THUMB).save(THUMB, quality=85, optimize=True)
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(THUMB)).execute()
        print("✅ Thumbnail set successfully (desktop view).")
    except Exception as e:
        print(f"⚠️ Thumbnail step failed: {e}")
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
history = history[-100:]
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
