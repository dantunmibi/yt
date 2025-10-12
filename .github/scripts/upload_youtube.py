# .github/scripts/upload_youtube.py
import os
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")

# Verify video file exists
if not os.path.exists(VIDEO):
    raise FileNotFoundError(f"Video file not found: {VIDEO}")

print(f"📹 Video file found: {VIDEO} ({os.path.getsize(VIDEO) / (1024*1024):.2f} MB)")

# Load credentials
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

# Load script data
with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

title = data.get("title", "AI Short")
description = data.get("description", f"{title} — Auto-generated AI Short")

# Prepare video metadata
snippet = {
    "title": title[:100],
    "description": description[:5000],  # YouTube limit is 5000 chars
    "tags": ["ai", "shorts", "trending", "automation"],
    "categoryId": "27"  # Education category
}
body = {
    "snippet": snippet,
    "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False
    }
}

print(f"📤 Uploading video: {title}")

# Upload video
try:
    media = MediaFileUpload(VIDEO, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    res = None
    while res is None:
        status, res = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"⏳ Upload progress: {progress}%")
    
    video_id = res["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"✅ Video uploaded successfully!")
    print(f"   Video ID: {video_id}")
    print(f"   URL: {video_url}")

except HttpError as e:
    print(f"❌ HTTP error during upload: {e}")
    raise
except Exception as e:
    print(f"❌ Upload failed: {e}")
    raise

# Set thumbnail if exists
if os.path.exists(THUMB):
    try:
        print(f"🖼️  Setting thumbnail...")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMB)
        ).execute()
        print("✅ Thumbnail set successfully")
    except HttpError as e:
        print(f"⚠️  Thumbnail upload failed: {e}")
        print("   Video was uploaded successfully, but thumbnail couldn't be set")
else:
    print("⚠️  Thumbnail file not found, skipping")

print(f"\n🎉 All done! Your video is live at: {video_url}")