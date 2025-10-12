# .github/scripts/fetch_trending.py
import os
import json
from datetime import datetime
from pytrends.request import TrendReq

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

def fetch_trending_topics():
    """Fetch trending topics from Google Trends"""
    try:
        print("🔍 Fetching trending topics from Google Trends...")
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Get trending searches
        trending = pytrends.trending_searches(pn='united_states')
        topics = trending[0].head(20).tolist()
        
        # Filter and categorize
        categories = {
            'tech': ['ai', 'tech', 'software', 'app', 'robot', 'phone', 'computer'],
            'business': ['money', 'startup', 'entrepreneur', 'invest', 'stock'],
            'psychology': ['mind', 'habit', 'mental', 'brain', 'psychology'],
            'health': ['health', 'fitness', 'diet', 'sleep', 'workout'],
            'productivity': ['productivity', 'work', 'focus', 'time', 'goal']
        }
        
        categorized = {}
        for topic in topics:
            topic_lower = topic.lower()
            for cat, keywords in categories.items():
                if any(kw in topic_lower for kw in keywords):
                    if cat not in categorized:
                        categorized[cat] = []
                    categorized[cat].append(topic)
                    break
        
        print(f"✅ Found {len(topics)} trending topics")
        print(f"   Categorized into: {list(categorized.keys())}")
        
        return {
            'date': datetime.now().isoformat(),
            'topics': topics[:10],
            'categorized': categorized
        }
        
    except Exception as e:
        print(f"⚠️ Could not fetch trends: {e}")
        return {
            'date': datetime.now().isoformat(),
            'topics': ['AI Technology', 'Productivity Hacks', 'Mental Health'],
            'categorized': {
                'tech': ['AI Technology'],
                'productivity': ['Productivity Hacks'],
                'psychology': ['Mental Health']
            }
        }

# Save trending data
trending_data = fetch_trending_topics()
with open(os.path.join(TMP, "trending.json"), "w") as f:
    json.dump(trending_data, f, indent=2)

print(f"✅ Saved trending topics to {TMP}/trending.json")