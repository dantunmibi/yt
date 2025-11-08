"""
Smart Time Analyzer - Analyzes YOUR posting times vs completion rates
Generates recommendations for updating posting_schedule.json based on YOUR data.
Run by daily_analytics.yml after fetch_youtube_analytics.py updates performance data.
"""

import os
import json
from datetime import datetime
import pytz
from collections import defaultdict

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
CONFIG_DIR = os.path.join(os.getenv("GITHUB_WORKSPACE", "."), "config")
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
SCHEDULE_FILE = os.path.join(CONFIG_DIR, "posting_schedule.json")
RECOMMENDATIONS_FILE = os.path.join(TMP, "schedule_recommendations.json")

# Minimum data requirements
MIN_VIDEOS_FOR_ANALYSIS = 10
MIN_VIDEOS_PER_HOUR = 2

def analyze_posting_time_performance():
    """
    Correlate posting time → completion rate from YOUR actual data.
    Returns: Analysis results or None if insufficient data.
    """
    
    if not os.path.exists(PERFORMANCE_FILE):
        print("⚠️ No performance data found")
        print("   Upload at least 10 videos to enable time analysis")
        return None
    
    with open(PERFORMANCE_FILE, 'r') as f:
        performance = json.load(f)
    
    # Group videos by hour posted (UTC)
    hourly_performance = defaultdict(lambda: {
        'completions': [],
        'views': [],
        'video_count': 0,
        'titles': [],
        'content_types': defaultdict(int)
    })
    
    total_analyzed = 0
    
    for content_type, data in performance.items():
        for upload in data['uploads']:
            upload_date = upload.get('upload_date')
            completion = upload.get('completion_rate_24h')
            views = upload.get('views_24h')
            title = upload.get('title', 'Unknown')
            
            # Skip videos without analytics data
            if not upload_date or completion is None or views is None:
                continue
            
            try:
                # Parse upload time
                upload_time = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                hour_utc = upload_time.hour
                
                # Record performance data for this hour
                hourly_performance[hour_utc]['completions'].append(completion)
                hourly_performance[hour_utc]['views'].append(views)
                hourly_performance[hour_utc]['video_count'] += 1
                hourly_performance[hour_utc]['titles'].append(title[:50])
                hourly_performance[hour_utc]['content_types'][content_type] += 1
                
                total_analyzed += 1
                
            except Exception as e:
                print(f"⚠️ Skipping video due to date parsing error: {str(e)[:50]}")
                continue
    
    if total_analyzed < MIN_VIDEOS_FOR_ANALYSIS:
        print(f"⚠️ Only {total_analyzed} videos with timing data")
        print(f"   Need at least {MIN_VIDEOS_FOR_ANALYSIS} for meaningful analysis")
        print(f"   Continue posting - analyzer will activate automatically")
        return None
    
    print(f"\n{'='*60}")
    print(f"🕐 POSTING TIME ANALYSIS")
    print(f"{'='*60}")
    print(f"Analyzed: {total_analyzed} videos with complete analytics data")
    
    # Calculate statistics per hour
    hourly_stats = {}
    
    for hour, data in hourly_performance.items():
        if data['video_count'] < MIN_VIDEOS_PER_HOUR:
            continue  # Need at least 2 videos per hour for reliability
        
        avg_completion = sum(data['completions']) / len(data['completions'])
        avg_views = sum(data['views']) / len(data['views'])
        
        # Performance score: 70% completion weight + 30% views weight (normalized)
        # Views normalized to max 10 points (200 views = max score)
        views_score = min(avg_views / 200, 1.0) * 10
        score = (avg_completion * 0.7) + (views_score * 0.3)
        
        hourly_stats[hour] = {
            'avg_completion': avg_completion,
            'avg_views': avg_views,
            'sample_size': data['video_count'],
            'score': score,
            'content_mix': dict(data['content_types']),
            'example_titles': data['titles'][:3]  # Top 3 examples
        }
    
    if not hourly_stats:
        print("⚠️ Not enough videos posted at consistent times")
        print("   Need at least 2 videos at same hour for comparison")
        return None
    
    # Sort hours by performance score
    sorted_hours = sorted(hourly_stats.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # Display top performing times
    print(f"\n🏆 YOUR TOP PERFORMING POSTING TIMES (UTC):\n")
    
    for i, (hour, stats) in enumerate(sorted_hours[:5], 1):
        print(f"{i}. {hour:02d}:00 UTC")
        print(f"   Avg Completion: {stats['avg_completion']:.1f}%")
        print(f"   Avg Views: {stats['avg_views']:.0f}")
        print(f"   Sample Size: {stats['sample_size']} videos")
        print(f"   Performance Score: {stats['score']:.2f}/100")
        
        # Show content mix
        content_list = ", ".join([f"{ct}({cnt})" for ct, cnt in stats['content_mix'].items()])
        print(f"   Content Mix: {content_list}")
        print()
    
    # Determine confidence level
    if total_analyzed >= 30:
        confidence = 'high'
    elif total_analyzed >= 20:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return {
        'analyzed_at': datetime.now(pytz.UTC).isoformat(),
        'total_videos': total_analyzed,
        'hourly_stats': hourly_stats,
        'top_hours': sorted_hours[:3],  # Top 3 hours
        'all_hours': sorted_hours,
        'confidence': confidence
    }

def generate_schedule_recommendations(time_analysis):
    """Generate recommendations for updating posting schedule based on YOUR data"""
    
    if not time_analysis:
        return
    
    # Load current schedule
    if not os.path.exists(SCHEDULE_FILE):
        print("⚠️ No posting_schedule.json found - skipping recommendations")
        return
    
    with open(SCHEDULE_FILE, 'r') as f:
        schedule = json.load(f)
    
    # Extract current posting times
    current_times = set()
    for day, slots in schedule['schedule']['weekly_schedule'].items():
        for slot in slots:
            time_str = slot['time']
            hour = int(time_str.split(':')[0])
            current_times.add(hour)
    
    # Load or create recommendations file
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
    
    # Get top performing hours
    top_hours = [hour for hour, stats in time_analysis['top_hours']]
    
    print(f"\n{'='*60}")
    print(f"📋 SCHEDULE ANALYSIS")
    print(f"{'='*60}")
    print(f"Current posting times (UTC): {sorted(current_times)}")
    print(f"YOUR top performing times: {top_hours}")
    print(f"Analysis confidence: {time_analysis['confidence'].upper()}")
    print(f"Based on {time_analysis['total_videos']} videos")
    
    # Only generate recommendations if confidence is medium or high
    if time_analysis['confidence'] not in ['medium', 'high']:
        print(f"\n⏳ Confidence level too low for recommendations")
        print(f"   Continue posting to build confidence")
        return
    
    # Find hours that perform well but aren't in current schedule
    new_optimal_hours = [h for h in top_hours if h not in current_times]
    underperforming_current = [h for h in current_times if h not in top_hours]
    
    # Check if posting time recommendation already exists
    existing_time_rec = any(
        rec.get('type') == 'POSTING_TIME_OPTIMIZATION'
        for rec in recommendations['pending_recommendations']
    )
    
    if new_optimal_hours and not existing_time_rec:
        # Calculate potential improvement
        current_avg = calculate_average_performance(time_analysis, current_times)
        optimal_avg = calculate_average_performance(time_analysis, top_hours)
        improvement = optimal_avg - current_avg
        
        # Build detailed performance comparison
        time_comparison = {}
        for hour in sorted(current_times.union(set(top_hours))):
            if hour in time_analysis['hourly_stats']:
                stats = time_analysis['hourly_stats'][hour]
                time_comparison[f"{hour:02d}:00 UTC"] = {
                    'completion': f"{stats['avg_completion']:.1f}%",
                    'views': int(stats['avg_views']),
                    'sample_size': stats['sample_size'],
                    'in_current_schedule': hour in current_times,
                    'in_top_performers': hour in top_hours
                }
        
        recommendation = {
            'type': 'POSTING_TIME_OPTIMIZATION',
            'current_schedule_hours': sorted(list(current_times)),
            'recommended_hours': top_hours,
            'new_optimal_hours': new_optimal_hours,
            'underperforming_hours': underperforming_current,
            'data': {
                'sample_size': time_analysis['total_videos'],
                'confidence': time_analysis['confidence'],
                'current_avg_completion': f"{current_avg:.1f}%",
                'optimal_avg_completion': f"{optimal_avg:.1f}%",
                'potential_improvement': f"{improvement:+.1f}%",
                'time_comparison': time_comparison
            },
            'suggested_action': (
                f"YOUR data shows best performance at {', '.join([f'{h:02d}:00' for h in top_hours])} UTC. "
                f"Consider testing {new_optimal_hours[0]:02d}:00 UTC for one series. "
                f"Potential improvement: {improvement:+.1f}% completion rate."
            ),
            'implementation_steps': [
                f"1. Test {new_optimal_hours[0]:02d}:00 UTC for 3-4 weeks",
                "2. Compare performance vs current times",
                f"3. If successful, consider shifting from {underperforming_current[0]:02d}:00 UTC" if underperforming_current else "3. Monitor results",
                "4. Update cron schedule in ai_shorts_trending.yml if validated"
            ],
            'requires_manual_action': True,
            'requires_cron_change': True,
            'created_at': datetime.now(pytz.UTC).isoformat(),
            'status': 'pending_manual_review',
            'severity': 'high' if improvement > 10 else 'medium'
        }
        
        recommendations['pending_recommendations'].append(recommendation)
        
        print(f"\n💡 NEW RECOMMENDATION GENERATED:")
        print(f"   Type: Posting Time Optimization")
        print(f"   Potential Improvement: {improvement:+.1f}%")
        print(f"   Suggested test: {new_optimal_hours[0]:02d}:00 UTC")
        
    elif not new_optimal_hours:
        print(f"\n✅ CURRENT SCHEDULE ALREADY OPTIMAL")
        print(f"   Your posting times match top performing hours")
        
    else:
        print(f"\n✅ Posting time recommendation already pending review")
    
    # Update generated_at timestamp
    recommendations['generated_at'] = datetime.now(pytz.UTC).isoformat()
    
    # Save recommendations
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    print(f"\n💾 Recommendations saved to: {RECOMMENDATIONS_FILE}")

def calculate_average_performance(time_analysis, hours):
    """Calculate weighted average performance for given hours"""
    
    total_completion = 0
    total_weight = 0
    
    for hour in hours:
        if hour in time_analysis['hourly_stats']:
            stats = time_analysis['hourly_stats'][hour]
            weight = stats['sample_size']  # Weight by number of videos
            
            total_completion += stats['avg_completion'] * weight
            total_weight += weight
    
    if total_weight == 0:
        return 0
    
    return total_completion / total_weight

if __name__ == "__main__":
    print("="*60)
    print("🕐 SMART TIME ANALYZER")
    print("="*60)
    
    # Analyze posting time performance
    time_analysis = analyze_posting_time_performance()
    
    if time_analysis:
        # Generate schedule recommendations
        generate_schedule_recommendations(time_analysis)
        
        print(f"\n{'='*60}")
        print(f"✅ Time analysis complete!")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"⏳ NOT ENOUGH DATA YET")
        print(f"{'='*60}")
        print(f"Continue posting videos - analysis activates at {MIN_VIDEOS_FOR_ANALYSIS}+ videos")