"""
One-time script to backfill analytics for existing 74 videos.
Run this ONCE before enabling Package 4 features.
"""

import os
import json
from datetime import datetime, timedelta
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")

def get_youtube_client():
    """Authenticate YouTube Data API"""
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=[
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/yt-analytics.readonly"
            ]
        )
        
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        
        print("✅ YouTube API authenticated")
        return youtube, analytics
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return None, None

def fetch_all_channel_videos(youtube):
    """Fetch all uploaded videos from the channel"""
    videos = []
    
    try:
        # Get uploads playlist ID
        channels_response = youtube.channels().list(
            part="contentDetails",
            mine=True
        ).execute()
        
        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        print(f"📺 Fetching videos from uploads playlist: {uploads_playlist_id}")
        
        # Fetch all videos from uploads playlist
        next_page_token = None
        
        while True:
            playlist_response = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in playlist_response['items']:
                video_id = item['contentDetails']['videoId']
                snippet = item['snippet']
                
                videos.append({
                    'video_id': video_id,
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'description': snippet['description']
                })
            
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break
        
        print(f"✅ Found {len(videos)} videos on channel")
        return videos
        
    except Exception as e:
        print(f"❌ Failed to fetch videos: {e}")
        return []

def categorize_video_by_title(title, description):
    """
    Categorize video based on title/description patterns.
    Maps to your new content types.
    """
    
    title_lower = title.lower()
    desc_lower = description.lower()
    combined = f"{title_lower} {desc_lower}"
    
    # Tool Teardown Tuesday patterns
    tool_keywords = [
        'midjourney', 'chatgpt', 'notion', 'canva', 'claude',
        'ai tool', 'text to 3d', 'dall-e', 'stable diffusion',
        'gemini', 'perplexity', 'ai feature', 'secret parameter'
    ]
    
    # SECRET PROMPTS patterns
    prompt_keywords = [
        'secret prompt', 'chatgpt prompt', 'email prompt',
        'prompts', 'prompt library', 'ai hack'
    ]
    
    # AI News patterns
    news_keywords = [
        'announcement', 'released', 'new feature', 'update',
        'openai', 'google', 'microsoft', 'meta', 'leaked',
        'breaking', 'just announced'
    ]
    
    # Check patterns
    if any(kw in combined for kw in tool_keywords):
        return 'tool_teardown_tuesday'
    elif any(kw in combined for kw in prompt_keywords):
        return 'secret_prompts_thursday'
    elif any(kw in combined for kw in news_keywords):
        return 'ai_news_roundup'
    else:
        return 'general'  # Uncategorized

def fetch_video_analytics(analytics, video_id, published_date):
    """Fetch analytics for a video"""
    
    try:
        # Parse published date
        published_datetime = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
        
        # Get analytics from publish date to now (max 90 days for accuracy)
        start_date = published_datetime.date().isoformat()
        end_date = datetime.now(pytz.UTC).date().isoformat()
        
        # Limit to last 90 days for more accurate data
        if (datetime.now(pytz.UTC).date() - published_datetime.date()).days > 90:
            start_date = (datetime.now(pytz.UTC).date() - timedelta(days=90)).isoformat()
        
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
            dimensions="video",
            filters=f"video=={video_id}",
            sort="-views"
        ).execute()
        
        if 'rows' not in response or not response['rows']:
            return None
        
        row = response['rows'][0]
        
        return {
            'views': row[1],
            'estimated_minutes_watched': row[2],
            'average_view_duration_seconds': row[3],
            'average_view_percentage': row[4]
        }
        
    except Exception as e:
        print(f"   ⚠️ Analytics failed for {video_id}: {e}")
        return None

def backfill_performance_data():
    """Main backfill function"""
    
    print("=" * 60)
    print("📊 BACKFILLING ANALYTICS FOR EXISTING VIDEOS")
    print("=" * 60)
    
    # Authenticate
    youtube, analytics = get_youtube_client()
    
    if not youtube or not analytics:
        print("❌ Cannot proceed without API access")
        return
    
    # Fetch all videos
    videos = fetch_all_channel_videos(youtube)
    
    if not videos:
        print("❌ No videos found")
        return
    
    print(f"\n📹 Processing {len(videos)} videos...")
    
    # Initialize performance structure
    performance = {
        'tool_teardown_tuesday': {
            'uploads': [],
            'average_completion': 0,
            'average_rewatch': 0,
            'average_views': 0,
            'total_uploads': 0,
            'series_performance': {}
        },
        'secret_prompts_thursday': {
            'uploads': [],
            'average_completion': 0,
            'average_rewatch': 0,
            'average_views': 0,
            'total_uploads': 0,
            'series_performance': {}
        },
        'ai_news_roundup': {
            'uploads': [],
            'average_completion': 0,
            'average_rewatch': 0,
            'average_views': 0,
            'total_uploads': 0,
            'series_performance': {}
        },
        'general': {
            'uploads': [],
            'average_completion': 0,
            'average_rewatch': 0,
            'average_views': 0,
            'total_uploads': 0,
            'series_performance': {}
        }
    }
    
    # Process each video
    processed = 0
    skipped = 0
    
    for idx, video in enumerate(videos, 1):
        video_id = video['video_id']
        title = video['title']
        
        print(f"\n[{idx}/{len(videos)}] {title[:60]}...")
        
        # Categorize
        content_type = categorize_video_by_title(title, video['description'])
        print(f"   📂 Category: {content_type}")
        
        # Fetch analytics
        analytics_data = fetch_video_analytics(analytics, video_id, video['published_at'])
        
        if not analytics_data:
            print(f"   ⚠️ No analytics data available")
            skipped += 1
            continue
        
        # Calculate rewatch rate
        rewatch_rate = 1.0
        if analytics_data['average_view_percentage'] > 100:
            rewatch_rate = analytics_data['average_view_percentage'] / 100
        
        # Add to performance data
        upload_record = {
            'video_id': video_id,
            'title': title,
            'upload_date': video['published_at'],
            'completion_rate': analytics_data['average_view_percentage'],
            'views': analytics_data['views'],
            'avg_view_duration_seconds': analytics_data['average_view_duration_seconds'],
            'rewatch_rate': rewatch_rate,
            'status': 'backfilled',
            'backfilled_at': datetime.now(pytz.UTC).isoformat()
        }
        
        performance[content_type]['uploads'].append(upload_record)
        performance[content_type]['total_uploads'] += 1
        
        print(f"   ✅ Views: {analytics_data['views']}, Completion: {analytics_data['average_view_percentage']:.1f}%")
        
        processed += 1
    
    # Calculate averages for each content type
    print(f"\n📊 Calculating averages...")
    
    for content_type, data in performance.items():
        uploads_with_data = data['uploads']
        
        if uploads_with_data:
            data['average_completion'] = sum(u['completion_rate'] for u in uploads_with_data) / len(uploads_with_data)
            data['average_rewatch'] = sum(u['rewatch_rate'] for u in uploads_with_data) / len(uploads_with_data)
            data['average_views'] = sum(u['views'] for u in uploads_with_data) / len(uploads_with_data)
            
            print(f"\n   {content_type}:")
            print(f"      Videos: {len(uploads_with_data)}")
            print(f"      Avg Completion: {data['average_completion']:.1f}%")
            print(f"      Avg Rewatch: {data['average_rewatch']:.2f}x")
            print(f"      Avg Views: {data['average_views']:.0f}")
    
    # Save performance data
    os.makedirs(TMP, exist_ok=True)
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(performance, f, indent=2)
    
    print(f"\n✅ Backfill complete!")
    print(f"   Processed: {processed} videos")
    print(f"   Skipped: {skipped} videos")
    print(f"   Saved to: {PERFORMANCE_FILE}")
    
    # Identify top performers
    print(f"\n🏆 TOP PERFORMERS:")
    
    all_uploads = []
    for content_type, data in performance.items():
        for upload in data['uploads']:
            upload['content_type'] = content_type
            all_uploads.append(upload)
    
    # Sort by completion rate
    top_completion = sorted(all_uploads, key=lambda x: x['completion_rate'], reverse=True)[:5]
    
    print(f"\n   📈 Highest Completion Rates:")
    for i, video in enumerate(top_completion, 1):
        print(f"      {i}. {video['title'][:50]}")
        print(f"         Completion: {video['completion_rate']:.1f}% | Views: {video['views']}")
    
    # Sort by rewatch rate
    top_rewatch = sorted(all_uploads, key=lambda x: x['rewatch_rate'], reverse=True)[:5]
    
    print(f"\n   🔄 Highest Rewatch Rates:")
    for i, video in enumerate(top_rewatch, 1):
        print(f"      {i}. {video['title'][:50]}")
        print(f"         Rewatch: {video['rewatch_rate']:.2f}x | Completion: {video['completion_rate']:.1f}%")

if __name__ == "__main__":
    backfill_performance_data()