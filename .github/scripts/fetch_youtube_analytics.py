"""
YouTube Analytics Data Fetcher
Fetches completion rates for recent videos using YouTube Analytics API.
Run this daily via separate workflow to update performance data.
"""

import os
import json
from datetime import datetime, timedelta
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

def get_youtube_analytics_client():
    """Authenticate YouTube Analytics API"""
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"]
        )
        
        analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        print("✅ YouTube Analytics API authenticated")
        return analytics
        
    except Exception as e:
        print(f"❌ Analytics authentication failed: {e}")
        return None

def fetch_video_analytics(analytics, video_id, upload_date):
    """
    Fetch analytics for a specific video.
    Returns: {views, avg_view_duration, avg_view_percentage}
    """
    
    try:
        # Parse upload date
        upload_datetime = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
        
        # Fetch data from upload date to now (max 30 days)
        start_date = upload_datetime.date().isoformat()
        end_date = min(datetime.now(pytz.UTC).date(), upload_datetime.date() + timedelta(days=30)).isoformat()
        
        # Query Analytics API
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
            print(f"   ⚠️ No analytics data yet for {video_id}")
            return None
        
        # Extract metrics
        row = response['rows'][0]
        
        analytics_data = {
            'views': row[1],
            'estimated_minutes_watched': row[2],
            'average_view_duration_seconds': row[3],
            'average_view_percentage': row[4],
            'fetched_at': datetime.now(pytz.UTC).isoformat(),
            'data_period': f"{start_date} to {end_date}"
        }
        
        print(f"   ✅ Fetched analytics for {video_id}")
        print(f"      Views: {analytics_data['views']}")
        print(f"      Avg View %: {analytics_data['average_view_percentage']:.1f}%")
        
        return analytics_data
        
    except Exception as e:
        print(f"   ❌ Failed to fetch analytics for {video_id}: {e}")
        return None

def update_performance_data():
    """Update performance data with real YouTube analytics"""
    
    # Authenticate
    analytics = get_youtube_analytics_client()
    if not analytics:
        print("❌ Cannot proceed without Analytics API access")
        return
    
    # Load performance data
    if not os.path.exists(PERFORMANCE_FILE):
        print("⚠️ No performance data file found")
        return
    
    with open(PERFORMANCE_FILE, 'r') as f:
        performance = json.load(f)
    
    # Load upload history
    if not os.path.exists(UPLOAD_LOG):
        print("⚠️ No upload history found")
        return
    
    with open(UPLOAD_LOG, 'r') as f:
        upload_history = json.load(f)
    
    # Find videos that need analytics updates
    videos_updated = 0
    
    for content_type, data in performance.items():
        print(f"\n📊 Updating analytics for {content_type}...")
        
        for upload in data['uploads']:
            # Skip if already has recent analytics data (< 24 hours old)
            if upload.get('completion_rate_24h') is not None:
                fetched_at = upload.get('analytics_fetched_at')
                if fetched_at:
                    fetched_time = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
                    if datetime.now(pytz.UTC) - fetched_time < timedelta(hours=24):
                        continue  # Skip, data is fresh
            
            video_id = upload.get('video_id')
            upload_date = upload.get('upload_date')
            
            if not video_id or not upload_date:
                continue
            
            # Fetch analytics
            analytics_data = fetch_video_analytics(analytics, video_id, upload_date)
            
            if analytics_data:
                # Update upload record
                upload['completion_rate_24h'] = analytics_data['average_view_percentage']
                upload['views_24h'] = analytics_data['views']
                upload['avg_view_duration_seconds'] = analytics_data['average_view_duration_seconds']
                upload['analytics_fetched_at'] = analytics_data['fetched_at']
                upload['status'] = 'analytics_available'
                
                # Calculate rewatch rate (if video is < 60 seconds, avg_view_percentage > 100% = rewatches)
                if analytics_data['average_view_percentage'] > 100:
                    upload['rewatch_rate'] = analytics_data['average_view_percentage'] / 100
                else:
                    upload['rewatch_rate'] = 1.0
                
                videos_updated += 1
        
        # Recalculate averages for content type
        uploads_with_data = [u for u in data['uploads'] if u.get('completion_rate_24h') is not None]
        
        if uploads_with_data:
            data['average_completion'] = sum(u['completion_rate_24h'] for u in uploads_with_data) / len(uploads_with_data)
            data['average_rewatch'] = sum(u.get('rewatch_rate', 1.0) for u in uploads_with_data) / len(uploads_with_data)
            data['average_views_24h'] = sum(u.get('views_24h', 0) for u in uploads_with_data) / len(uploads_with_data)
            
            print(f"   📈 Updated averages:")
            print(f"      Completion: {data['average_completion']:.1f}%")
            print(f"      Rewatch: {data['average_rewatch']:.2f}x")
            print(f"      Views (24h): {data['average_views_24h']:.0f}")
    
    # Save updated performance data
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(performance, f, indent=2)
    
    print(f"\n✅ Updated analytics for {videos_updated} videos")
    print(f"💾 Saved to: {PERFORMANCE_FILE}")

if __name__ == "__main__":
    print("=" * 60)
    print("📊 YOUTUBE ANALYTICS DATA FETCH")
    print("=" * 60)
    
    update_performance_data()
    
    print("\n" + "=" * 60)
    print("✅ Analytics fetch complete")
    print("=" * 60)