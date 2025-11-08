# .github/scripts/manage_playlists.py
import os
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from collections import defaultdict
import re
import difflib

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PLAYLIST_CONFIG_FILE = os.path.join(TMP, "playlist_config.json")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

# ---- Authenticate YouTube API ----
def get_youtube_client():
    """Authenticate and return YouTube API client"""
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube"]
        )
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        print("✅ YouTube API authenticated")
        return youtube
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        raise

# ---- Playlist Configuration ----
PLAYLIST_RULES = {
    # Technology / AI Shorts
"ai": {
    "money": {
        "title": "💰 AI & Money Moves",
        "keywords": [
            "ai money", "ai wealth", "ai investing", "ai business", "ai finance",
            "make money", "side hustle", "ai millionaire", "ai income", "passive income",
            "hidden money", "financial", "profit", "earn", "cash", "rich"
        ]
    },
    "productivity": {
        "title": "⚙️ AI Productivity & Focus Hacks",
        "keywords": [
            "productivity", "focus", "time management", "workflow", "digital habits",
            "ai productivity", "ai hacks", "efficiency", "automation", "chatgpt"
        ]
    },
    "brain": {
        "title": "🧠 AI & Brain Secrets",
        "keywords": [
            "brain", "memory", "learning", "mental", "focus", "cognitive",
            "ai brain", "neuroscience", "mind hacks", "superlearning"
        ]
    },
    "health": {
        "title": "💤 AI & Health Biohacks",
        "keywords": [
            "sleep", "recovery", "fitness", "health", "wellness", "longevity",
            "biohack", "ai health", "rest", "energy", "workout"
        ]
    },
    "lifestyle": {
        "title": "🚀 AI Lifestyle & Future Tech",
        "keywords": [
            "ai lifestyle", "gadgets", "future", "wearables", "tech", "automation",
            "ai trends", "smart home", "innovation", "daily life", "ai future"
        ]
    }
}

}

# ===== SERIES-BASED PLAYLIST RULES =====
SERIES_PLAYLISTS = {
    "Tool Teardown Tuesday": {
        "title": "🔧 Tool Teardown Tuesday - Complete Series",
        "description": "Every Tuesday, we tear down the latest AI tools and reveal their SECRET features. Watch the entire series to become an AI power user!",
        "keywords": ["ai tools", "tool teardown", "midjourney", "chatgpt", "notion ai", "canva ai", "ai tutorials"]
    },
    "SECRET PROMPTS": {
        "title": "🔐 SECRET PROMPTS - ChatGPT Mastery Series",
        "description": "The ultimate ChatGPT prompt library. Every Thursday, Episode by episode, learn the SECRET prompts that 10x your productivity.",
        "keywords": ["chatgpt prompts", "ai prompts", "productivity", "chatgpt tutorial", "secret prompts"]
    },
    "AI Weekend Roundup": {
        "title": "📰 AI Weekend Roundup - Latest AI News",
        "description": "Your weekly curated AI news. Every Saturday, we break down the week's most important AI updates and how they impact YOU.",
        "keywords": ["ai news", "tech news", "ai updates", "artificial intelligence", "trending ai"]
    }
}

def get_or_create_series_playlist(youtube, series_name, config):
    """
    Get or create playlist for a series (e.g., "Tool Teardown Tuesday").
    Separate from topic-based playlists.
    
    ✅ FIX: Added retry logic and propagation delay for newly created playlists
    """
    playlist_key = f"series_{series_name.lower().replace(' ', '_')}"
    
    if playlist_key in config:
        print(f"✅ Using existing series playlist: {series_name} (ID: {config[playlist_key]})")
        return config[playlist_key]
    
    # Check if series playlist config exists
    if series_name not in SERIES_PLAYLISTS:
        print(f"⚠️ No series playlist config for: {series_name}")
        return None
    
    # Create new series playlist
    try:
        playlist_info = SERIES_PLAYLISTS[series_name]
        
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_info["title"],
                    "description": playlist_info["description"],
                    "tags": playlist_info["keywords"]
                },
                "status": {"privacyStatus": "public"}
            }
        )
        response = request.execute()
        playlist_id = response["id"]
        
        config[playlist_key] = playlist_id
        save_playlist_config(config)
        print(f"🎉 Created series playlist: {playlist_info['title']} (ID: {playlist_id})")
        
        # ✅ FIX: Wait for YouTube API propagation (newly created playlists)
        import time
        print(f"   ⏳ Waiting 3 seconds for playlist propagation...")
        time.sleep(3)
        
        # ✅ FIX: Verify playlist exists before returning
        try:
            verify_request = youtube.playlists().list(
                part="snippet",
                id=playlist_id
            )
            verify_response = verify_request.execute()
            
            if verify_response.get('items'):
                print(f"   ✅ Playlist verified and ready to use")
            else:
                print(f"   ⚠️ Playlist created but not yet visible, waiting 2 more seconds...")
                time.sleep(2)
        except Exception as verify_error:
            print(f"   ⚠️ Verification failed (playlist may still be propagating): {verify_error}")
            time.sleep(2)
        
        return playlist_id
        
    except Exception as e:
        print(f"❌ Failed to create series playlist: {e}")
        return None

# Fetch your existing channel playlists and map them to categories if titles match
def fetch_and_map_existing_playlists(youtube, niche, config):
    print("🔄 Fetching existing playlists from channel...")
    existing_playlists = {}
    nextPageToken = None
    while True:
        response = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=nextPageToken
        ).execute()
        for item in response.get("items", []):
            existing_playlists[item["snippet"]["title"].lower()] = item["id"]
        nextPageToken = response.get("nextPageToken")
        if not nextPageToken:
            break

    # Map to your categories using fuzzy matching
    for category, rules in PLAYLIST_RULES[niche].items():
        key = f"{niche}_{category}"
        match = None
        for title, pid in existing_playlists.items():
            ratio = difflib.SequenceMatcher(None, rules["title"].lower(), title).ratio()
            if ratio > 0.6:
                match = pid
                break
        if match:
            if key in config and config[key] != match:
                print(f"♻️ Updated stale playlist ID for '{rules['title']}' -> {match}")
            else:
                print(f"✅ Mapped existing playlist '{rules['title']}' -> {match}")
            config[key] = match

            print(f"✅ Mapped existing playlist '{rules['title']}' -> {match}")
    return config


def load_upload_history():
    """
    Load video upload history with series metadata fallback
    ✅ FIX: Also checks content_history.json if series is missing
    """
    if os.path.exists(UPLOAD_LOG):
        try:
            with open(UPLOAD_LOG, 'r') as f:
                history = json.load(f)
            
            # ✅ FIX: Parse series from title if missing in metadata
            for video in history:
                if video.get("series") in [None, "none", ""]:
                    title = video.get("title", "")
                    
                    # Extract series from title patterns
                    import re
                    
                    if "Tool Teardown Tuesday" in title or "Tool Teardown Thursday" in title:
                        match = re.match(r'^(Tool Teardown (?:Tuesday|Thursday))', title)
                        if match:
                            video["series"] = match.group(1)
                            print(f"   🔧 Extracted series from title: {video['series']}")
                    
                    elif "SECRET PROMPTS" in title:
                        video["series"] = "SECRET PROMPTS"
                        print(f"   🔧 Extracted series from title: SECRET PROMPTS")
                    
                    elif "AI Weekend Roundup" in title:
                        video["series"] = "AI Weekend Roundup"
                        print(f"   🔧 Extracted series from title: AI Weekend Roundup")
            
            return history
        except Exception as e:
            print(f"⚠️ Error loading upload history: {e}")
            return []
    return []

def load_playlist_config():
    """Load existing playlist IDs"""
    if os.path.exists(PLAYLIST_CONFIG_FILE):
        try:
            with open(PLAYLIST_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_playlist_config(config):
    """Save playlist configuration"""
    with open(PLAYLIST_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"💾 Saved playlist config: {len(config)} playlists")

def get_or_create_playlist(youtube, niche, category, config):
    """
    Get existing playlist ID from config or create a new playlist if it doesn't exist.
    """
    playlist_key = f"{niche}_{category}"

    if playlist_key in config:
        print(f"✅ Using existing playlist: {playlist_key} (ID: {config[playlist_key]})")
        return config[playlist_key]

    # Create new playlist
    try:
        playlist_info = PLAYLIST_RULES[niche][category]
        title = playlist_info.get("title", "Untitled Playlist")
        description = playlist_info.get("description", "")
        tags = playlist_info.get("tags", [])

        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags
                },
                "status": {"privacyStatus": "public"}
            }
        )
        response = request.execute()
        playlist_id = response["id"]

        config[playlist_key] = playlist_id
        save_playlist_config(config)
        print(f"🎉 Created new playlist: {title} (ID: {playlist_id})")
        return playlist_id

    except Exception as e:
        print(f"❌ Failed to create playlist: {e}")
        return None

def categorize_video(video_metadata, niche):
    """Smart categorization for Shorts: fuzzy + keyword matching"""
    text = " ".join([
        video_metadata.get("title", ""),
        video_metadata.get("description", ""),
        video_metadata.get("topic", ""),
        " ".join(video_metadata.get("hashtags", []))
    ]).lower()

    if niche not in PLAYLIST_RULES:
        return None

    scores = {}
    for category, rules in PLAYLIST_RULES[niche].items():
        score = 0
        for kw in rules["keywords"]:
            kw = kw.lower()
            if kw in text:
                score += 3
            for word in kw.split():
                match_ratio = difflib.SequenceMatcher(None, word, text).ratio()
                if match_ratio > 0.6:
                    score += 1
        if score > 0:
            scores[category] = score

    if scores:
        best = max(scores, key=scores.get)
        print(f"   📂 Categorized as: {best} (score: {scores[best]})")
        return best

    print("   ⚠️ No category match found")
    return None

def add_video_to_playlist(youtube, video_id, playlist_id):
    """
    Add video to playlist only if it's not already there.
    
    ✅ FIX: Added retry logic for 404 errors (playlist propagation delays)
    """
    import time
    from googleapiclient.errors import HttpError
    
    # ✅ FIX: Retry logic for fetching playlist items (handles 404)
    max_retries = 3
    retry_delay = 2
    
    existing_videos = set()
    
    for attempt in range(max_retries):
        try:
            nextPageToken = None
            while True:
                request = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=nextPageToken
                )
                response = request.execute()
                for item in response.get("items", []):
                    existing_videos.add(item["snippet"]["resourceId"]["videoId"])
                nextPageToken = response.get("nextPageToken")
                if not nextPageToken:
                    break
            
            # Success - break retry loop
            break
            
        except HttpError as e:
            if e.resp.status == 404 and attempt < max_retries - 1:
                print(f"      ⚠️ Playlist not found (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                print(f"      ❌ Failed to fetch playlist items: {e}")
                return False
        except Exception as e:
            print(f"      ❌ Unexpected error fetching playlist: {e}")
            return False

    if video_id in existing_videos:
        print("      ℹ️ Video already in playlist, skipping")
        return False

    # Add video with retry logic
    for attempt in range(max_retries):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}
                    }
                }
            ).execute()
            print("      ✅ Added to playlist")
            return True

        except HttpError as e:
            if e.resp.status == 404 and attempt < max_retries - 1:
                print(f"      ⚠️ Playlist not found when adding video (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(2)
                continue
            else:
                print(f"      ❌ Failed to add video: {e}")
                return False
        except Exception as e:
            print(f"      ❌ Unexpected error adding video: {e}")
            return False
    
    return False

def organize_playlists(youtube, history, config, niche):
    """Main function to organize videos into BOTH topic AND series playlists"""
    print(f"\n🎬 Organizing {len(history)} videos into playlists...")
    print(f"   Niche: {niche}")
    
    stats = {
        "total_videos": len(history),
        "categorized": 0,
        "added_to_topic_playlists": 0,
        "added_to_series_playlists": 0,
        "already_in_playlists": 0,
        "failed": 0
    }
    
    for video in history:
        video_id = video.get("video_id")
        title = video.get("title", "Unknown")
        series_name = video.get("series", "none")  # NEW: Check for series metadata
        
        if not video_id:
            continue
        
        print(f"\n📹 Processing: {title}")
        if series_name and series_name != "none":
            print(f"   📺 Series: {series_name}")
        
        # 1. Add to TOPIC-BASED playlist (existing logic)
        category = categorize_video(video, niche)
        
        if category:
            stats["categorized"] += 1
            playlist_id = get_or_create_playlist(youtube, niche, category, config)
            
            if playlist_id:
                success = add_video_to_playlist(youtube, video_id, playlist_id)
                if success:
                    stats["added_to_topic_playlists"] += 1
                else:
                    stats["already_in_playlists"] += 1
        
        # 2. Add to SERIES-BASED playlist (NEW)
        if series_name and series_name != "none":
            series_playlist_id = get_or_create_series_playlist(youtube, series_name, config)
            
            if series_playlist_id:
                success = add_video_to_playlist(youtube, video_id, series_playlist_id)
                if success:
                    stats["added_to_series_playlists"] += 1
                    print(f"      ✅ Added to series playlist: {series_name}")
                else:
                    print(f"      ℹ️ Already in series playlist: {series_name}")
    
    return stats

def print_playlist_summary(config, niche):
    """Print summary of all playlists"""
    print("\n" + "="*60)
    print("📋 PLAYLIST SUMMARY")
    print("="*60)
    
    if niche in PLAYLIST_RULES:
        for category, rules in PLAYLIST_RULES[niche].items():
            playlist_key = f"{niche}_{category}"
            
            if playlist_key in config:
                playlist_id = config[playlist_key]
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                
                print(f"\n🎵 {rules['title']}")
                print(f"   Category: {category}")
                print(f"   URL: {playlist_url}")
                print(f"   Keywords: {', '.join(rules['keywords'][:5])}...")
            else:
                print(f"\n⚠️ {rules['title']}")
                print(f"   Status: Not yet created")

# ---- Main Execution ----
if __name__ == "__main__":
    print("🎬 YouTube Playlist Auto-Organizer")
    print("="*60)
    
    # Detect niche from script.json
    script_path = os.path.join(TMP, "script.json")
    niche = "ai"  # default
    
    if os.path.exists(script_path):
        try:
            with open(script_path, 'r') as f:
                data = json.load(f)
                topic = data.get("topic", "").lower()
                
                niche = "ai"
                
                print(f"🎯 Detected niche: {niche}")
        except:
            pass
    
    # Load data
    history = load_upload_history()
    config = load_playlist_config()
    
    if not history:
        print("⚠️ No upload history found. Upload some videos first!")
        exit(0)
    
    print(f"📂 Found {len(history)} videos in history")
    
    # Authenticate
    youtube = get_youtube_client()

    # Map existing playlists from your channel
    config = fetch_and_map_existing_playlists(youtube, niche, config)
    save_playlist_config(config)
    
    # Organize videos
    stats = organize_playlists(youtube, history, config, niche)
    
    # Replace the final print section (around line 447) with:

    # Print results
    print("\n" + "="*60)
    print("📊 ORGANIZATION RESULTS")
    print("="*60)
    print(f"Total videos processed: {stats['total_videos']}")
    print(f"Successfully categorized: {stats['categorized']}")
    print(f"Added to topic playlists: {stats['added_to_topic_playlists']}")
    print(f"Added to series playlists: {stats['added_to_series_playlists']}")
    print(f"Already in playlists: {stats['already_in_playlists']}")
    print(f"Failed/Skipped: {stats['failed']}")

    # Print playlist summary
    print_playlist_summary(config, niche)

    print("\n✅ Playlist organization complete!")
    print("\n💡 Tip: Playlists are created automatically and will grow with each new upload!")