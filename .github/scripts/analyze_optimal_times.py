"""
Smart Time Analyzer (Day + Hour Edition)
FIXED: Analyzes specific Day/Time slots (e.g., "Tuesday 23:00")
using Viral Velocity Scoring to find your absolute best weekly windows.
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

def analyze_day_and_time():
    perf = load_json(PERFORMANCE_FILE)
    if not perf: return None

    # Group by (Day, Hour)
    # Key: "Tuesday_23"
    slot_stats = defaultdict(lambda: {'scores': [], 'views': [], 'completions': [], 'count': 0, 'day': '', 'hour': 0})

    for c_type, data in perf.items():
        for u in data['uploads']:
            if not u.get('completion_rate_24h'): continue
            
            try:
                # Parse Date/Time
                dt = datetime.fromisoformat(u['upload_date'].replace('Z', '+00:00'))
                day_name = dt.strftime('%A') # "Tuesday"
                h = dt.hour
                
                key = f"{day_name}_{h}"
                
                views = u.get('views_24h', 0)
                comp = u.get('completion_rate_24h', 0)
                
                if views < 10: continue
                
                # Viral Score Formula
                score = comp * math.log10(views)
                
                slot_stats[key]['scores'].append(score)
                slot_stats[key]['views'].append(views)
                slot_stats[key]['completions'].append(comp)
                slot_stats[key]['count'] += 1
                slot_stats[key]['day'] = day_name
                slot_stats[key]['hour'] = h
            except: continue

    if not slot_stats: return None

    # Aggregate Results
    results = []
    for key, data in slot_stats.items():
        results.append({
            'day': data['day'],
            'hour': data['hour'],
            'avg_score': sum(data['scores']) / len(data['scores']),
            'avg_views': sum(data['views']) / len(data['views']),
            'avg_completion': sum(data['completions']) / len(data['completions']),
            'count': data['count']
        })
    
    # Sort by Viral Score (Desc)
    results.sort(key=lambda x: x['avg_score'], reverse=True)
    
    print(f"\n{'='*60}")
    print(f"📅 TOP WEEKLY SLOTS (Day + Time)")
    print(f"{'='*60}")
    
    top_slots = []
    for r in results[:5]:
        print(f"🏆 {r['day']} @ {r['hour']:02d}:00 UTC")
        print(f"   Viral Score: {r['avg_score']:.0f}")
        print(f"   Avg Retention: {r['avg_completion']:.1f}%")
        print(f"   Avg Views: {r['avg_views']:.0f}")
        print(f"   (Based on {r['count']} videos)")
        print("-" * 30)
        top_slots.append(r)
    
    return {'top_slots': top_slots, 'all_data': results}

def generate_schedule_recommendations(analysis):
    if not analysis: return
    
    recs = load_json(RECOMMENDATIONS_FILE)
    if 'pending_recommendations' not in recs: recs['pending_recommendations'] = []
    
    top_slot = analysis['top_slots'][0]
    
    # Generate actionable insight
    rec = {
        'type': 'SCHEDULE_OPTIMIZATION',
        'suggested_action': (
            f"🚀 BEST SLOT: {top_slot['day']} at {top_slot['hour']:02d}:00 UTC. "
            f"This slot generates {top_slot['avg_completion']:.1f}% retention. "
            f"Make sure your 'tool_teardown' content hits this specific window."
        ),
        'best_day': top_slot['day'],
        'best_hour': top_slot['hour'],
        'data': top_slot,
        'created_at': datetime.now(pytz.UTC).isoformat()
    }
    
    recs['schedule_insights'] = rec
    recs['pending_recommendations'].append(rec)
    
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(recs, f, indent=2)
    print(f"\n💾 Schedule recommendations updated in {RECOMMENDATIONS_FILE}")

if __name__ == "__main__":
    analysis = analyze_day_and_time()
    generate_schedule_recommendations(analysis)