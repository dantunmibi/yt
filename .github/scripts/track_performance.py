"""
Performance Tracking & Auto-Adjustment System
Tracks video completion rates and generates schedule recommendations.
Run this AFTER upload completes to log performance data.
"""

import os
import json
from datetime import datetime, timedelta
import pytz

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
RECOMMENDATIONS_FILE = os.path.join(TMP, "schedule_recommendations.json")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

def load_performance_data():
    """Load existing performance data"""
    if os.path.exists(PERFORMANCE_FILE):
        try:
            with open(PERFORMANCE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_performance_data(data):
    """Save performance data"""
    os.makedirs(TMP, exist_ok=True)
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def track_upload_performance():
    """
    Track the upload that just completed.
    NOTE: Actual completion rate data requires YouTube Analytics API.
    For now, we track uploads and predict based on content type patterns.
    """
    
    # Load script data
    script_file = os.path.join(TMP, "script.json")
    if not os.path.exists(script_file):
        print("⚠️ No script.json found, skipping performance tracking")
        return
    
    with open(script_file, 'r') as f:
        script_data = json.load(f)
    
    # Load upload data
    if not os.path.exists(UPLOAD_LOG):
        print("⚠️ No upload_history.json found, skipping performance tracking")
        return
    
    with open(UPLOAD_LOG, 'r') as f:
        upload_history = json.load(f)
    
    if not upload_history:
        print("⚠️ Upload history is empty")
        return
    
    latest_upload = upload_history[-1]
    
    # Extract metadata
    content_type = script_data.get('content_type', 'unknown')
    series_name = script_data.get('series', 'none')
    episode = script_data.get('episode', 0)
    title = script_data.get('title', 'Unknown')
    
    # Load existing performance data
    performance = load_performance_data()
    
    # Initialize content type if new
    if content_type not in performance:
        performance[content_type] = {
            'uploads': [],
            'average_completion': 0,
            'average_rewatch': 0,
            'total_uploads': 0,
            'series_performance': {}
        }
    
    # Add upload record (completion data will be filled later via YouTube API)
    upload_record = {
        'upload_date': latest_upload.get('upload_date', datetime.now().isoformat()),
        'video_id': latest_upload.get('video_id'),
        'title': title,
        'series': series_name,
        'episode': episode,
        'shorts_url': latest_upload.get('shorts_url'),
        'completion_rate_24h': None,  # Will be updated later
        'views_24h': None,
        'rewatch_rate': None,
        'status': 'pending_analytics'
    }
    
    performance[content_type]['uploads'].append(upload_record)
    performance[content_type]['total_uploads'] += 1
    
    # Track series performance separately
    if series_name != 'none':
        if series_name not in performance[content_type]['series_performance']:
            performance[content_type]['series_performance'][series_name] = {
                'episodes': [],
                'average_completion': 0,
                'total_episodes': 0
            }
        
        performance[content_type]['series_performance'][series_name]['episodes'].append({
            'episode': episode,
            'upload_date': upload_record['upload_date'],
            'video_id': upload_record['video_id'],
            'completion_rate_24h': None,
            'status': 'pending_analytics'
        })
        performance[content_type]['series_performance'][series_name]['total_episodes'] += 1
    
    # Keep only last 50 uploads per content type
    performance[content_type]['uploads'] = performance[content_type]['uploads'][-50:]
    
    save_performance_data(performance)
    
    print(f"✅ Performance tracking logged:")
    print(f"   Content Type: {content_type}")
    print(f"   Series: {series_name}")
    print(f"   Episode: {episode}")
    print(f"   Total uploads for {content_type}: {performance[content_type]['total_uploads']}")
    print(f"   Status: Waiting for 24h analytics data")

def generate_recommendations():
    """
    Generate schedule adjustment recommendations based on performance.
    Requires at least 4 weeks of data (12 uploads minimum).
    """
    
    performance = load_performance_data()
    
    if not performance:
        print("ℹ️ No performance data yet, skipping recommendations")
        return
    
    # Check if we have enough data
    total_uploads = sum(data['total_uploads'] for data in performance.values())
    
    if total_uploads < 12:
        print(f"ℹ️ Only {total_uploads} uploads tracked, need 12+ for recommendations")
        return
    
    print(f"\n📊 Analyzing performance data ({total_uploads} total uploads)...")
    
    recommendations = {
        'generated_at': datetime.now(pytz.UTC).isoformat(),
        'pending_recommendations': [],
        'completed_recommendations': []
    }
    
    # Analyze each content type
    for content_type, data in performance.items():
        uploads_with_data = [u for u in data['uploads'] if u.get('completion_rate_24h') is not None]
        
        if len(uploads_with_data) < 4:
            print(f"   {content_type}: Only {len(uploads_with_data)} uploads with analytics, skipping")
            continue
        
        # Calculate average completion
        avg_completion = sum(u['completion_rate_24h'] for u in uploads_with_data) / len(uploads_with_data)
        avg_views = sum(u.get('views_24h', 0) for u in uploads_with_data) / len(uploads_with_data)
        
        print(f"\n   📈 {content_type}:")
        print(f"      Avg Completion: {avg_completion:.1f}%")
        print(f"      Avg Views (24h): {avg_views:.0f}")
        print(f"      Sample Size: {len(uploads_with_data)} videos")
        
        # Check if performance is below target
        schedule_file = 'config/posting_schedule.json'
        target_completion = 60  # default
        
        try:
            with open(schedule_file, 'r') as f:
                schedule = json.load(f)['schedule']
                
            for day_slots in schedule['weekly_schedule'].values():
                for slot in day_slots:
                    if slot['type'] == content_type:
                        target_str = slot.get('target_completion', '60%')
                        target_completion = int(target_str.replace('%', ''))
                        break
        except:
            pass
        
        # Generate recommendation if significantly below target
        if avg_completion < target_completion - 10:
            recommendation = {
                'type': 'UNDERPERFORMING',
                'content_type': content_type,
                'current_performance': {
                    'avg_completion': avg_completion,
                    'avg_views': avg_views,
                    'sample_size': len(uploads_with_data)
                },
                'target_completion': target_completion,
                'gap': target_completion - avg_completion,
                'suggested_action': f"Consider reducing {content_type} frequency or improving content quality",
                'created_at': datetime.now(pytz.UTC).isoformat(),
                'status': 'pending_review'
            }
            
            recommendations['pending_recommendations'].append(recommendation)
            print(f"      ⚠️ RECOMMENDATION: {recommendation['suggested_action']}")
        
        elif avg_completion > target_completion + 10:
            recommendation = {
                'type': 'OVERPERFORMING',
                'content_type': content_type,
                'current_performance': {
                    'avg_completion': avg_completion,
                    'avg_views': avg_views,
                    'sample_size': len(uploads_with_data)
                },
                'target_completion': target_completion,
                'gap': avg_completion - target_completion,
                'suggested_action': f"Consider INCREASING {content_type} frequency - it's outperforming!",
                'created_at': datetime.now(pytz.UTC).isoformat(),
                'status': 'pending_review'
            }
            
            recommendations['pending_recommendations'].append(recommendation)
            print(f"      ✅ RECOMMENDATION: {recommendation['suggested_action']}")
    
    # Save recommendations
    os.makedirs(TMP, exist_ok=True)
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    if recommendations['pending_recommendations']:
        print(f"\n💡 Generated {len(recommendations['pending_recommendations'])} new recommendations")
        print(f"   Review them in: {RECOMMENDATIONS_FILE}")
    else:
        print(f"\n✅ No new recommendations - all content types performing within targets")

if __name__ == "__main__":
    print("=" * 60)
    print("📊 PERFORMANCE TRACKING & RECOMMENDATIONS")
    print("=" * 60)
    
    # Track this upload
    track_upload_performance()
    
    # Generate recommendations if enough data
    generate_recommendations()
    
    print("\n" + "=" * 60)
    print("✅ Performance tracking complete")
    print("=" * 60)