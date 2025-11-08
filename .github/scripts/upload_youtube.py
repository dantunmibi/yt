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

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")
READY_VIDEO = os.path.join(TMP, "short_ready.mp4")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

# ===== PACKAGE 3: SERIES-AWARE METADATA =====
SERIES_NAME = os.getenv("SERIES_NAME", "")
EPISODE_NUMBER = int(os.getenv("EPISODE_NUMBER", "0"))

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

# ✅ FIX: Extract series metadata from script if not in env
if not SERIES_NAME or SERIES_NAME == "none":
    SERIES_NAME = data.get("series", "none")
if EPISODE_NUMBER == 0:
    EPISODE_NUMBER = data.get("episode", 0)

# ✅ FIX: FALLBACK - Parse series from title if still "none"
if SERIES_NAME == "none" and title:
    import re
    
    # Pattern 1: "Tool Teardown Tuesday - Episode X: ..."
    match = re.match(r'^(Tool Teardown (?:Tuesday|Thursday))\s*-\s*Episode\s+(\d+)', title)
    if match:
        SERIES_NAME = match.group(1)
        if EPISODE_NUMBER == 0:
            EPISODE_NUMBER = int(match.group(2))
        print(f"📺 Extracted from title: {SERIES_NAME} - Episode {EPISODE_NUMBER}")
    
    # Pattern 2: "SECRET PROMPTS - Episode X: ..."
    elif "SECRET PROMPTS" in title:
        match = re.search(r'Episode\s+(\d+)', title)
        SERIES_NAME = "SECRET PROMPTS"
        if match and EPISODE_NUMBER == 0:
            EPISODE_NUMBER = int(match.group(1))
        print(f"📺 Extracted from title: {SERIES_NAME} - Episode {EPISODE_NUMBER}")
    
    # Pattern 3: "AI Weekend Roundup - Episode X: ..."
    elif "AI Weekend Roundup" in title:
        match = re.search(r'Episode\s+(\d+)', title)
        SERIES_NAME = "AI Weekend Roundup"
        if match and EPISODE_NUMBER == 0:
            EPISODE_NUMBER = int(match.group(1))
        print(f"📺 Extracted from title: {SERIES_NAME} - Episode {EPISODE_NUMBER}")

print(f"📺 Final Series Info:")
print(f"   Series: {SERIES_NAME}")
print(f"   Episode: {EPISODE_NUMBER}")

print(f"📺 Series Info:")
print(f"   Series: {SERIES_NAME}")
print(f"   Episode: {EPISODE_NUMBER}")

# ===== SERIES-AWARE TITLE FORMATTING =====
# If this is part of a series, ensure episode number is in title
if SERIES_NAME and SERIES_NAME != "none" and EPISODE_NUMBER > 0:
    # Check if episode number is already in title
    if f"Episode {EPISODE_NUMBER}" not in title and f"Ep {EPISODE_NUMBER}" not in title:
        # Check if title already has series prefix
        if not title.startswith(SERIES_NAME):
            # Add series name and episode
            title = f"{SERIES_NAME} - Episode {EPISODE_NUMBER}: {title}"
            print(f"📺 Series title formatted: {title}")
        else:
            print(f"📺 Title already has series format")
    else:
        print(f"📺 Episode number already in title")

# ---- Step 1: Validate video ----
if not os.path.exists(VIDEO):
    raise FileNotFoundError(f"Video file not found: {VIDEO}")

video_size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
print(f"📹 Video file found: {VIDEO} ({video_size_mb:.2f} MB)")
if video_size_mb < 0.1:
    raise ValueError("Video file is too small, likely corrupted")

# ---- Step 2: Rename video to safe filename ----
safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
video_output_path = os.path.join(TMP, f"{safe_title[:100]}.mp4")  # Limit filename length

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

# ---- Step 4: Prepare SERIES-AWARE metadata ----

# Build series information for description
series_info = ""
next_episode_tease = ""

if SERIES_NAME and SERIES_NAME != "none" and EPISODE_NUMBER > 0:
    series_info = f"""
🎬 This is Episode {EPISODE_NUMBER} of {SERIES_NAME}!

"""
    
    # Determine next episode day based on series
    next_day_map = {
        "Tool Teardown Tuesday": "Thursday",
        "Tool Teardown Thursday": "next Tuesday",
        "Viral AI Saturday": "next Tuesday"
    }
    next_day = next_day_map.get(SERIES_NAME, "soon")
    
    next_episode_tease = f"""📅 Episode {EPISODE_NUMBER + 1} drops {next_day} - Subscribe so you don't miss it!

"""

enhanced_description = f"""{series_info}{description}

{next_episode_tease}{' '.join(hashtags)}

---
Follow Ascent Dragox For More AI Tool Breakdowns!
Created: {datetime.now().strftime('%Y-%m-%d')}
Topic: {topic}
{f'Series: {SERIES_NAME}' if SERIES_NAME != 'none' else ''}
{f'Episode: {EPISODE_NUMBER}' if EPISODE_NUMBER > 0 else ''}
"""

# Build tags
tags = ["shorts", "viralshorts", topic, "trending", "fyp", "ai"]
if hashtags:
    tags.extend([tag.replace('#', '') for tag in hashtags[:10]])

# Add series-specific tags
if SERIES_NAME and SERIES_NAME != "none":
    series_tag = SERIES_NAME.lower().replace(' ', '')
    tags.append(series_tag)
    if "tool" in SERIES_NAME.lower():
        tags.extend(["aitools", "tooltutorial", "aitutorial"])
    elif "viral" in SERIES_NAME.lower():
        tags.extend(["viralai", "ainews", "trending"])

tags = list(set(tags))[:15]  # YouTube limit: 15 tags

print(f"📝 Metadata ready:")
print(f"   Title: {title[:80]}...")
print(f"   Tags: {', '.join(tags[:10])}...")
print(f"   Series: {SERIES_NAME} - Ep {EPISODE_NUMBER}")

snippet = {
    "title": title[:100],  # YouTube limit: 100 chars
    "description": enhanced_description[:5000],  # YouTube limit: 5000 chars
    "tags": tags,
    "categoryId": "28"  # Science & Technology
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

# ---- Step 7: Save upload history with SERIES METADATA ----
upload_metadata = {
    "video_id": video_id,
    "title": title,
    "topic": topic,
    "series": SERIES_NAME if SERIES_NAME != "none" else None,
    "episode": EPISODE_NUMBER if EPISODE_NUMBER > 0 else None,
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
if SERIES_NAME and SERIES_NAME != "none":
    print(f"Series: {SERIES_NAME} - Episode {EPISODE_NUMBER}")
print(f"Video ID: {video_id}")
print(f"Shorts URL: {shorts_url}")
print(f"Hashtags: {' '.join(hashtags[:5])}")
print("="*60)
print("\n💡 Tip: Share the Shorts URL for better mobile reach!")
print(f"🔗 {shorts_url}")