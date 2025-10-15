# .github/scripts/fetch_trending.py
import os
import json
import requests
from datetime import datetime
from pytrends.request import TrendReq
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_trending_topics():
    """Fetch trending topics from Google Trends"""
    try:
        print("🔍 Fetching trending topics from Google Trends...")
        
        # Updated pytrends initialization
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10,25), retries=2)
        
        # Method 1: Try daily searches (most reliable)
        try:
            print("   Trying daily trending searches...")
            trending = pytrends.trending_searches()  # Remove pn parameter
            topics = trending[0].head(15).tolist()
            print(f"   Found {len(topics)} daily trends")
            
        except Exception as daily_error:
            print(f"   Daily trends failed: {daily_error}")
            
            # Method 2: Try real-time trends
            try:
                print("   Trying real-time trends...")
                trending = pytrends.realtime_trending_searches(pn='US')
                topics = []
                for item in trending.head(10)['title']:
                    if isinstance(item, str) and item.strip():
                        topics.append(item.strip())
                print(f"   Found {len(topics)} real-time trends")
                
            except Exception as realtime_error:
                print(f"   Real-time trends failed: {realtime_error}")
                
                # Method 3: Use built-in suggestions
                print("   Using fallback topics...")
                topics = [
                    "Artificial Intelligence", "Productivity", "Mental Health",
                    "Technology", "Business", "Science", "Health", "Education",
                    "Innovation", "Digital Transformation"
                ]
        
        # Filter and categorize
        categories = {
            'tech': ['ai', 'tech', 'software', 'app', 'robot', 'phone', 'computer', 'digital', 'innovation', 'code'],
            'business': ['money', 'startup', 'entrepreneur', 'invest', 'stock', 'business', 'finance', 'market'],
            'psychology': ['mind', 'habit', 'mental', 'brain', 'psychology', 'focus', 'mindset', 'behavior'],
            'health': ['health', 'fitness', 'diet', 'sleep', 'workout', 'wellness', 'nutrition', 'exercise'],
            'productivity': ['productivity', 'work', 'focus', 'time', 'goal', 'efficiency', 'organization', 'tools']
        }
        
        categorized = {}
        for topic in topics:
            if not isinstance(topic, str):
                continue
                
            topic_lower = topic.lower()
            matched = False
            
            for cat, keywords in categories.items():
                if any(kw in topic_lower for kw in keywords):
                    if cat not in categorized:
                        categorized[cat] = []
                    categorized[cat].append(topic)
                    matched = True
                    break
            
            # If no category matched, add to general
            if not matched:
                if 'general' not in categorized:
                    categorized['general'] = []
                categorized['general'].append(topic)
        
        print(f"✅ Found {len(topics)} trending topics")
        print(f"   Categorized into: {list(categorized.keys())}")
        
        return {
            'date': datetime.now().isoformat(),
            'topics': topics[:10],
            'categorized': categorized
        }
        
    except Exception as e:
        print(f"⚠️ Could not fetch trends: {e}")
        # Return good fallback data that will work for content generation
        return {
            'date': datetime.now().isoformat(),
            'topics': [
                "AI Technology", "Productivity Tools", "Mental Wellness", 
                "Business Innovation", "Health Tech", "Digital Learning",
                "Smart Devices", "Future Work", "Sustainable Tech", "Creative AI"
            ],
            'categorized': {
                'tech': ['AI Technology', 'Smart Devices', 'Creative AI'],
                'productivity': ['Productivity Tools', 'Future Work'],
                'psychology': ['Mental Wellness'],
                'business': ['Business Innovation', 'Sustainable Tech'],
                'health': ['Health Tech'],
                'general': ['Digital Learning']
            }
        }

# Save trending data
try:
    trending_data = fetch_trending_topics()
    with open(os.path.join(TMP, "trending.json"), "w") as f:
        json.dump(trending_data, f, indent=2)

    print(f"✅ Saved trending topics to {TMP}/trending.json")
    
except Exception as e:
    print(f"❌ Critical error in fetch_trending: {e}")
    # Create minimal fallback file
    fallback_data = {
        'date': datetime.now().isoformat(),
        'topics': ['AI', 'Technology', 'Innovation'],
        'categorized': {'tech': ['AI', 'Technology', 'Innovation']}
    }
    with open(os.path.join(TMP, "trending.json"), "w") as f:
        json.dump(fallback_data, f, indent=2)
    print("✅ Created fallback trending data")