"""
Performance Tracking & Auto-Adjustment System
FIXED: Implements Viral Velocity Scoring & Anomaly Detection.
Replaces hardcoded baselines with dynamic scoring.
"""

import os
import json
import math
from datetime import datetime
import pytz

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
RECOMMENDATIONS_FILE = os.path.join(TMP, "schedule_recommendations.json")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def calculate_viral_score(completion_rate, views):
    """
    Calculates Viral Potential.
    Score = Retention * Log10(Views)
    """
    if views < 10: return 0
    # Log10 ensures 100k views > 1k views, but not 10x weighted
    return completion_rate * math.log10(views)

def track_upload_performance():
    """Track the new upload pending analytics"""
    script_file = os.path.join(TMP, "script.json")
    
    # We allow running without upload log if we just want to analyze existing data
    if not os.path.exists(script_file) or not os.path.exists(UPLOAD_LOG):
        print("ℹ️ No new upload to track today (Analysis mode)")
        return

    script_data = load_json(script_file)
    upload_history = load_json(UPLOAD_LOG)
    if not upload_history: return

    latest = upload_history[-1]
    content_type = script_data.get('content_type', 'unknown')
    
    perf = load_json(PERFORMANCE_FILE)
    if content_type not in perf:
        perf[content_type] = {'uploads': [], 'total_uploads': 0}

    # Avoid duplicates based on video_id
    existing_ids = [u.get('video_id') for u in perf[content_type]['uploads']]
    if latest.get('video_id') in existing_ids:
        print("ℹ️ Upload already tracked")
        return

    record = {
        'upload_date': latest.get('upload_date', datetime.now().isoformat()),
        'video_id': latest.get('video_id'),
        'title': script_data.get('title', 'Unknown'),
        'content_type': content_type,
        'completion_rate_24h': None,
        'views_24h': None,
        'status': 'pending_analytics'
    }
    
    perf[content_type]['uploads'].append(record)
    perf[content_type]['total_uploads'] += 1
    perf[content_type]['uploads'] = perf[content_type]['uploads'][-50:] # Keep last 50
    
    save_json(PERFORMANCE_FILE, perf)
    print(f"✅ Tracked new upload: {content_type}")

def generate_recommendations():
    """
    Generate insights based on REAL data (Viral Velocity).
    """
    perf = load_json(PERFORMANCE_FILE)
    if not perf: return

    print("\n📊 ANALYZING CONTENT PERFORMANCE (Viral Model)...")
    
    recommendations = {
        'generated_at': datetime.now(pytz.UTC).isoformat(),
        'pending_recommendations': []
    }

    # 1. Analyze Categories
    for c_type, data in perf.items():
        valid_uploads = [u for u in data['uploads'] if u.get('completion_rate_24h') is not None]
        if not valid_uploads: continue

        scores = []
        completions = []
        views = []

        for u in valid_uploads:
            comp = u['completion_rate_24h']
            v = u.get('views_24h', 0)
            score = calculate_viral_score(comp, v)
            scores.append(score)
            completions.append(comp)
            views.append(v)
        
        avg_score = sum(scores) / len(scores)
        avg_comp = sum(completions) / len(completions)
        
        print(f"   👉 {c_type}: Score {avg_score:.0f} | Avg Ret {avg_comp:.1f}%")

        # A. DETECT REWATCH LOOPS (The "Text-to-3D" Effect)
        if avg_comp > 90:
            rec = {
                'type': 'VIRAL_ANOMALY',
                'content_type': c_type,
                'suggested_action': f"🚀 {c_type} is a VIRAL LOOP ({avg_comp:.1f}%). This is your winning format. DOUBLE FREQUENCY.",
                'severity': 'positive'
            }
            recommendations['pending_recommendations'].append(rec)
            print(f"      🔥 VIRAL LOOP DETECTED!")

        # B. DETECT DEAD FORMATS
        elif avg_comp < 40:
            rec = {
                'type': 'KILL_FORMAT',
                'content_type': c_type,
                'suggested_action': f"💀 {c_type} is dead ({avg_comp:.1f}%). Viewers are clicking off immediately. STOP PRODUCING.",
                'severity': 'critical'
            }
            recommendations['pending_recommendations'].append(rec)
            print(f"      💀 DEAD FORMAT DETECTED")

        # C. DETECT HIGH POTENTIAL
        elif avg_score > 150:
             rec = {
                'type': 'HIGH_POTENTIAL',
                'content_type': c_type,
                'suggested_action': f"✅ {c_type} has high velocity (Score {avg_score:.0f}). Improve hook to boost retention.",
                'severity': 'medium'
            }
             recommendations['pending_recommendations'].append(rec)

    save_json(RECOMMENDATIONS_FILE, recommendations)
    print(f"\n💡 Generated {len(recommendations['pending_recommendations'])} smart insights.")

# Compatibility function for existing workflow calls
def generate_cron_recommendations():
    pass 

if __name__ == "__main__":
    track_upload_performance()
    generate_recommendations()