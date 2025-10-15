# .github/scripts/fetch_trending.py
import os
import json
from datetime import datetime
from pytrends.request import TrendReq
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

print("🚀 Starting fetch_trending.py")
pytrends = TrendReq(hl="en-US", tz=360)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_trending_topics():
    """Fetch trending topics from Google Trends with robust fallbacks."""
    try:
        print("🔍 Fetching daily trending topics...")
        trending = pytrends.trending_searches()
        topics = trending.head(15).iloc[:, 0].tolist()
        print(f"✅ Fetched {len(topics)} daily topics")

    except Exception as daily_error:
        print(f"⚠️ Daily trends failed: {daily_error}")

        try:
            print("   Trying real-time trending topics...")
            realtime = pytrends.realtime_trending_searches(pn="US")
            topics = []
            for item in realtime.head(10)["title"]:
                if isinstance(item, str) and item.strip():
                    topics.append(item.strip())
            print(f"✅ Fetched {len(topics)} real-time topics")

        except Exception as realtime_error:
            print(f"⚠️ Real-time trends failed: {realtime_error}")
            print("   Using fallback topics...")
            topics = [
                "Artificial Intelligence", "Productivity", "Mental Health",
                "Technology", "Business", "Science", "Health", "Education",
                "Innovation", "Digital Transformation"
            ]

    # Categorize topics (unchanged)
    categories = {
        "tech": ["ai", "tech", "software", "app", "robot", "phone", "computer", "digital", "innovation", "code"],
        "business": ["money", "startup", "entrepreneur", "invest", "stock", "business", "finance", "market"],
        "psychology": ["mind", "habit", "mental", "brain", "psychology", "focus", "mindset", "behavior"],
        "health": ["health", "fitness", "diet", "sleep", "workout", "wellness", "nutrition", "exercise"],
        "productivity": ["productivity", "work", "focus", "time", "goal", "efficiency", "organization", "tools"]
    }

    categorized = {}
    for topic in topics:
        if not isinstance(topic, str):
            continue
        topic_lower = topic.lower()
        matched = False
        for cat, keywords in categories.items():
            if any(kw in topic_lower for kw in keywords):
                categorized.setdefault(cat, []).append(topic)
                matched = True
                break
        if not matched:
            categorized.setdefault("general", []).append(topic)

    print(f"✅ Found {len(topics)} topics across {len(categorized)} categories: {list(categorized.keys())}")

    return {
        "date": datetime.now().isoformat(),
        "topics": topics[:10],
        "categorized": categorized,
    }

# Main execution (unchanged)
try:
    trending_data = fetch_trending_topics()
    os.makedirs(TMP, exist_ok=True)
    with open(os.path.join(TMP, "trending.json"), "w", encoding="utf-8") as f:
        json.dump(trending_data, f, indent=2)
    print(f"✅ Saved trending topics to {TMP}/trending.json")

except Exception as e:
    print(f"❌ Critical error in fetch_trending: {e}")
    fallback_data = {
        "date": datetime.now().isoformat(),
        "topics": ["AI", "Technology", "Innovation"],
        "categorized": {"tech": ["AI", "Technology", "Innovation"]},
    }
    os.makedirs(TMP, exist_ok=True)
    with open(os.path.join(TMP, "trending.json"), "w", encoding="utf-8") as f:
        json.dump(fallback_data, f, indent=2)
    print("✅ Created fallback trending data")

print("🏁 fetch_trending.py completed successfully")
