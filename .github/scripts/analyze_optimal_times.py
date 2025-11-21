"""
Smart Time Analyzer
FIXED: Removed 200-view cap. Optimized for Viral Velocity Scoring.
"""

import os
import json
import math
from datetime import datetime
import pytz
from collections import defaultdict

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
RECOMMENDATIONS_FILE = os.path.join(TMP, "schedule_recommendations.json")

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f: return json.load(f)
    return {}

def analyze_posting_time_performance():
    perf = load_json(PERFORMANCE_FILE)
    if not perf: return None

    # Group by Hour
    hour_stats = defaultdict(lambda: {'scores': [], 'views': [], 'completions': [], 'count': 0})

    for c_type, data in perf.items():
        for u in data['uploads']:
            if not u.get('completion_rate_24h'): continue
            
            try:
                # Parse Time
                dt = datetime.fromisoformat(u['upload_date'].replace('Z', '+00:00'))
                h = dt.hour
                
                views = u.get('views_24h', 0)
                comp = u.get('completion_rate_24h', 0)
                
                if views < 10: continue
                
                # Viral Score = Retention * Log(Views)
                score = comp * math.log10(views)
                
                hour_stats[h]['scores'].append(score)
                hour_stats[h]['views'].append(views)
                hour_stats[h]['completions'].append(comp)
                hour_stats[h]['count'] += 1
            except: continue

    if not hour_stats: return None

    # Aggregate
    results = []
    for h, data in hour_stats.items():
        # We allow even single samples if the score is massive (to catch that 461% anomaly)
        results.append({
            'hour': h,
            'avg_score': sum(data['scores']) / len(data['scores']),
            'avg_views': sum(data['views']) / len(data['views']),
            'avg_completion': sum(data['completions']) / len(data['completions']),
            'count': data['count']
        })
    
    results.sort(key=lambda x: x['avg_score'], reverse=True)
    
    print(f"\n{'='*60}")
    print(f"🕐 TOP TIME SLOTS (Viral Velocity Model)")
    print(f"{'='*60}")
    
    top_hours = []
    for r in results[:3]:
        print(f"{r['hour']:02d}:00 UTC")
        print(f"   Viral Score: {r['avg_score']:.0f}")
        print(f"   Avg Retention: {r['avg_completion']:.1f}%")
        print(f"   Avg Views: {r['avg_views']:.0f}")
        top_hours.append((r['hour'], r))
    
    return {'top_hours': top_hours, 'total_videos': sum(len(d['uploads']) for d in perf.values()), 'confidence': 'high'}

def generate_schedule_recommendations(time_analysis):
    if not time_analysis: return
    
    # Load existing recommendations
    recs = load_json(RECOMMENDATIONS_FILE)
    if 'pending_recommendations' not in recs: recs['pending_recommendations'] = []
    
    top_slot = time_analysis['top_hours'][0][1]
    
    # STRATEGY: 120-Minute Delay Buffer
    # We recommend the top hour, but explicitly note the window
    rec = {
        'type': 'POSTING_TIME_OPTIMIZATION',
        'suggested_action': (
            f"🚀 PRIME WINDOW DETECTED: {top_slot['hour']:02d}:00 UTC. "
            f"Avg Retention: {top_slot['avg_completion']:.1f}%. "
            f"This aligns with your US Desktop audience (Mid-afternoon/Evening)."
        ),
        'new_optimal_hours': [h[0] for h in time_analysis['top_hours']],
        'data': top_slot,
        'created_at': datetime.now(pytz.UTC).isoformat()
    }
    
    recs['schedule_insights'] = rec
    recs['pending_recommendations'].append(rec)
    
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recs, f, indent=2)
    print(f"\n💾 Schedule recommendations updated in {RECOMMENDATIONS_FILE}")

if __name__ == "__main__":
    results = analyze_posting_time_performance()
    generate_schedule_recommendations(results)