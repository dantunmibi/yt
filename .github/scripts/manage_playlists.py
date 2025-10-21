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
        refresh_token="1//03SlzMO_5ZRZxCgYIARAAGAMSNwF-L9IrYBR3AXdy0NmT_kAM3Rc443AK4ZG4nVgcpN4p1OHSfP_Ds2kQQfrlsdeWaN9pAqdf-U0",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="665507293295-gglqptmju4k6c91ico0dakfn7avnt4gp.apps.googleusercontent.com",
        client_secret="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",
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

# ---- Core Functions ----

def load_upload_history():
    """Load video upload history"""
    if os.path.exists(UPLOAD_LOG):
        try:
            with open(UPLOAD_LOG, 'r') as f:
                return json.load(f)
        except:
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
    """Get existing playlist or create new one safely"""
    playlist_key = f"{niche}_{category}"
    
    if playlist_key in config:
        playlist_id = config[playlist_key]
        print(f"✅ Using existing playlist: {playlist_key} (ID: {playlist_id})")
        return playlist_id
    
    try:
        playlist_info = PLAYLIST_RULES[niche][category]
        title = playlist_info.get("title", "Untitled Playlist")
        description = playlist_info.get("description", "No description provided")
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
        
    except KeyError as e:
        print(f"❌ Missing key in playlist info: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to create playlist: {e}")
        return None

    """Get existing playlist or create new one"""
    playlist_key = f"{niche}_{category}"
    
    # Check if playlist already exists in config
    if playlist_key in config:
        playlist_id = config[playlist_key]
        print(f"✅ Using existing playlist: {PLAYLIST_RULES[niche][category]['title']} (ID: {playlist_id})")
        return playlist_id
    
    # Create new playlist
    try:
        playlist_info = PLAYLIST_RULES[niche][category]
        
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_info["title"],
                    "description": playlist_info["description"],
                    "tags": playlist_info.get("tags", [])
                },
                "status": {
                    "privacyStatus": "public"
                }
            }
        )
        
        response = request.execute()
        playlist_id = response["id"]
        
        config[playlist_key] = playlist_id
        save_playlist_config(config)
        
        print(f"🎉 Created new playlist: {playlist_info['title']} (ID: {playlist_id})")
        return playlist_id
        
    except HttpError as e:
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
    """Add video to playlist"""
    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        
        request.execute()
        print(f"      ✅ Added to playlist")
        return True
        
    except HttpError as e:
        error_message = str(e)
        if "videoAlreadyInPlaylist" in error_message:
            print(f"      ℹ️ Already in playlist")
        else:
            print(f"      ❌ Failed to add: {e}")
        return False

def organize_playlists(youtube, history, config, niche):
    """Main function to organize videos into playlists"""
    print(f"\n🎬 Organizing {len(history)} videos into playlists...")
    print(f"   Niche: {niche}")
    
    stats = {
        "total_videos": len(history),
        "categorized": 0,
        "added_to_playlists": 0,
        "already_in_playlists": 0,
        "failed": 0
    }
    
    for video in history:
        video_id = video.get("video_id")
        title = video.get("title", "Unknown")
        
        if not video_id:
            continue
        
        print(f"\n📹 Processing: {title}")
        
        # Determine category
        category = categorize_video(video, niche)
        
        if not category:
            stats["failed"] += 1
            continue
        
        stats["categorized"] += 1
        
        # Get or create playlist
        playlist_id = get_or_create_playlist(youtube, niche, category, config)
        
        if not playlist_id:
            stats["failed"] += 1
            continue
        
        # Add video to playlist
        success = add_video_to_playlist(youtube, video_id, playlist_id)
        
        if success:
            stats["added_to_playlists"] += 1
        else:
            stats["already_in_playlists"] += 1
    
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
    
    # Organize videos
    stats = organize_playlists(youtube, history, config, niche)
    
    # Print results
    print("\n" + "="*60)
    print("📊 ORGANIZATION RESULTS")
    print("="*60)
    print(f"Total videos processed: {stats['total_videos']}")
    print(f"Successfully categorized: {stats['categorized']}")
    print(f"Added to playlists: {stats['added_to_playlists']}")
    print(f"Already in playlists: {stats['already_in_playlists']}")
    print(f"Failed/Skipped: {stats['failed']}")
    
    # Print playlist summary
    print_playlist_summary(config, niche)
    
    print("\n✅ Playlist organization complete!")
    print("\n💡 Tip: Playlists are created automatically and will grow with each new upload!")