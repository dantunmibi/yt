# .github/scripts/track_performance.py
"""
Performance Tracking & Auto-Adjustment System
Tracks video completion rates and generates schedule recommendations.
Run this AFTER upload completes to log performance data.

CONTEXT: Based on YOUR 83-video analysis showing:
- tool_teardown_tuesday: 64.6% avg completion (WINNER)
- viral_ai_saturday: Entertainment content 60-80% range
- ai_news_roundup: 30.5% avg (KILLED)
- secret_prompts_thursday: 14.7% avg (KILLED)
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
    For now, we track uploads and predict based on YOUR proven patterns.
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
        'completion_rate_24h': None,  # Will be updated by analytics workflow
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
    Uses YOUR 83-video baseline as reference.
    
    YOUR PROVEN BASELINES:
    - tool_teardown_tuesday: 64.6% (target: 70%)
    - viral_ai_saturday: ~60% (target: 50%)
    - KILLED: ai_news_roundup (30.5%), secret_prompts_thursday (14.7%)
    """
    
    performance = load_performance_data()
    
    if not performance:
        print("ℹ️ No performance data yet, skipping recommendations")
        return
    
    # Check if we have enough data (need uploads with analytics)
    total_uploads_with_data = 0
    for content_type, data in performance.items():
        uploads_with_data = [u for u in data['uploads'] if u.get('completion_rate_24h') is not None]
        total_uploads_with_data += len(uploads_with_data)
    
    if total_uploads_with_data < 4:
        print(f"ℹ️ Only {total_uploads_with_data} uploads with analytics data")
        print(f"   Need at least 4 for meaningful recommendations")
        print(f"   Using YOUR 83-video baseline as reference for now")
        return
    
    print(f"\n📊 Analyzing performance data ({total_uploads_with_data} uploads with analytics)...")
    
    recommendations = {
        'generated_at': datetime.now(pytz.UTC).isoformat(),
        'baseline_reference': 'Based on YOUR 83-video historical analysis',
        'pending_recommendations': [],
        'completed_recommendations': []
    }
    
    # Load existing recommendations to preserve them
    if os.path.exists(RECOMMENDATIONS_FILE):
        with open(RECOMMENDATIONS_FILE, 'r') as f:
            existing = json.load(f)
            recommendations['pending_recommendations'] = existing.get('pending_recommendations', [])
            recommendations['completed_recommendations'] = existing.get('completed_recommendations', [])
    
    # YOUR proven targets from 83-video analysis
    proven_targets = {
        'tool_teardown_tuesday': {
            'target_completion': 70,
            'proven_average': 64.6,
            'sample_size': 24,
            'grade': 'A (your best performer)'
        },
        'tool_teardown_thursday': {
            'target_completion': 65,
            'proven_average': 64.6,
            'sample_size': 0,
            'grade': 'A (predicted based on Tuesday data)'
        },
        'viral_ai_saturday': {
            'target_completion': 50,
            'proven_average': 60.0,
            'sample_size': 5,
            'grade': 'B+ (entertainment/shock value)'
        }
    }
    
    # Analyze each content type
    for content_type, data in performance.items():
        uploads_with_data = [u for u in data['uploads'] if u.get('completion_rate_24h') is not None]
        
        if len(uploads_with_data) < 2:
            print(f"   {content_type}: Only {len(uploads_with_data)} uploads with analytics, using baseline")
            continue
        
        # Calculate current performance
        avg_completion = sum(u['completion_rate_24h'] for u in uploads_with_data) / len(uploads_with_data)
        avg_views = sum(u.get('views_24h', 0) for u in uploads_with_data) / len(uploads_with_data)
        
        print(f"\n   📈 {content_type}:")
        print(f"      Current Avg Completion: {avg_completion:.1f}%")
        print(f"      Current Avg Views (24h): {avg_views:.0f}")
        print(f"      Sample Size: {len(uploads_with_data)} new videos")
        
        # Get target and baseline
        target_info = proven_targets.get(content_type, {
            'target_completion': 60,
            'proven_average': 50,
            'sample_size': 0,
            'grade': 'Unknown'
        })
        
        target_completion = target_info['target_completion']
        proven_average = target_info['proven_average']
        
        print(f"      YOUR Proven Baseline: {proven_average:.1f}% ({target_info['sample_size']} videos from backfill)")
        print(f"      Target: {target_completion}%")
        
        # Compare new performance to YOUR baseline
        baseline_delta = avg_completion - proven_average
        target_delta = avg_completion - target_completion
        
        # Check if recommendation already exists for this content type
        existing_rec = any(
            rec.get('content_type') == content_type and rec.get('type') in ['UNDERPERFORMING_VS_BASELINE', 'OUTPERFORMING_BASELINE']
            for rec in recommendations['pending_recommendations']
        )
        
        # Generate recommendation if significantly different from baseline
        if baseline_delta < -10 and not existing_rec:
            recommendation = {
                'type': 'UNDERPERFORMING_VS_BASELINE',
                'content_type': content_type,
                'current_performance': {
                    'avg_completion': avg_completion,
                    'avg_views': avg_views,
                    'sample_size': len(uploads_with_data)
                },
                'your_proven_baseline': proven_average,
                'target_completion': target_completion,
                'gap_vs_baseline': baseline_delta,
                'gap_vs_target': target_delta,
                'suggested_action': f"New {content_type} videos performing {abs(baseline_delta):.1f}% worse than YOUR proven {proven_average:.1f}% average. Review recent video quality or revert to proven format.",
                'created_at': datetime.now(pytz.UTC).isoformat(),
                'status': 'pending_review',
                'severity': 'high' if baseline_delta < -15 else 'medium'
            }
            
            recommendations['pending_recommendations'].append(recommendation)
            print(f"      ⚠️ RECOMMENDATION: {recommendation['suggested_action']}")
        
        elif baseline_delta > 10 and not existing_rec:
            recommendation = {
                'type': 'OUTPERFORMING_BASELINE',
                'content_type': content_type,
                'current_performance': {
                    'avg_completion': avg_completion,
                    'avg_views': avg_views,
                    'sample_size': len(uploads_with_data)
                },
                'your_proven_baseline': proven_average,
                'target_completion': target_completion,
                'gap_vs_baseline': baseline_delta,
                'gap_vs_target': target_delta,
                'suggested_action': f"New {content_type} videos performing {baseline_delta:.1f}% BETTER than YOUR proven {proven_average:.1f}% average! Whatever you changed is WORKING. Replicate this format.",
                'created_at': datetime.now(pytz.UTC).isoformat(),
                'status': 'pending_review',
                'severity': 'positive'
            }
            
            recommendations['pending_recommendations'].append(recommendation)
            print(f"      ✅ RECOMMENDATION: {recommendation['suggested_action']}")
        
        else:
            print(f"      ✅ Performing within {abs(baseline_delta):.1f}% of YOUR proven baseline - consistent!")
    
    # Save recommendations
    os.makedirs(TMP, exist_ok=True)
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    if recommendations['pending_recommendations']:
        print(f"\n💡 Generated {len(recommendations['pending_recommendations'])} new recommendations")
        print(f"   Review them in: {RECOMMENDATIONS_FILE}")
    else:
        print(f"\n✅ No new recommendations - performance consistent with YOUR proven baselines")


def generate_cron_recommendations():
    """
    Generate cron schedule change recommendations based on posting time analysis.
    Called by daily_analytics to populate schedule_recommendations.json with timing insights.
    """
    
    performance = load_performance_data()
    
    if not performance:
        return
    
    # Analyze which days/times get best performance
    day_performance = {}
    time_performance = {}
    
    for content_type, data in performance.items():
        for upload in data['uploads']:
            upload_date = upload.get('upload_date')
            completion = upload.get('completion_rate_24h')
            
            if not upload_date or completion is None:
                continue
            
            try:
                upload_time = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                day_name = upload_time.strftime('%A')
                hour = upload_time.hour
                
                if day_name not in day_performance:
                    day_performance[day_name] = []
                day_performance[day_name].append(completion)
                
                if hour not in time_performance:
                    time_performance[hour] = []
                time_performance[hour].append(completion)
                
            except:
                continue
    
    # Calculate averages
    day_averages = {
        day: sum(completions) / len(completions)
        for day, completions in day_performance.items()
        if len(completions) >= 2
    }
    
    time_averages = {
        hour: sum(completions) / len(completions)
        for hour, completions in time_performance.items()
        if len(completions) >= 2
    }
    
    if not day_averages or not time_averages:
        print("   Not enough data for schedule recommendations")
        return
    
    # Find best days and times
    best_days = sorted(day_averages.items(), key=lambda x: x[1], reverse=True)[:3]
    best_times = sorted(time_averages.items(), key=lambda x: x[1], reverse=True)[:3]
    
    print(f"\n📅 SCHEDULE INSIGHTS:")
    print(f"   Best days: {', '.join([f'{day} ({avg:.1f}%)' for day, avg in best_days])}")
    print(f"   Best times: {', '.join([f'{hour:02d}:00 ({avg:.1f}%)' for hour, avg in best_times])}")
    
    # Load existing recommendations
    if os.path.exists(RECOMMENDATIONS_FILE):
        with open(RECOMMENDATIONS_FILE, 'r') as f:
            recommendations = json.load(f)
    else:
        recommendations = {
            'generated_at': datetime.now(pytz.UTC).isoformat(),
            'baseline_reference': 'Based on YOUR actual performance data',
            'pending_recommendations': [],
            'completed_recommendations': []
        }
    
    # Add schedule insights to recommendations file
    recommendations['schedule_insights'] = {
        'best_days': [{'day': day, 'avg_completion': avg} for day, avg in best_days],
        'best_times_utc': [{'hour': hour, 'avg_completion': avg} for hour, avg in best_times],
        'sample_size': sum(len(completions) for completions in day_performance.values()),
        'generated_at': datetime.now(pytz.UTC).isoformat()
    }
    
    # Update timestamp
    recommendations['generated_at'] = datetime.now(pytz.UTC).isoformat()
    
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recommendations, f, indent=2)


if __name__ == "__main__":
    print("=" * 60)
    print("📊 PERFORMANCE TRACKING & RECOMMENDATIONS")
    print("=" * 60)
    
    # Track this upload
    track_upload_performance()
    
    # Generate recommendations if enough data
    generate_recommendations()
    
    # Generate cron schedule recommendations
    generate_cron_recommendations()
    
    print("\n" + "=" * 60)
    print("✅ Performance tracking complete")
    print("=" * 60)