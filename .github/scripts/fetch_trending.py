# .github/scripts/fetch_trending.py
import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)

# Your focus areas — prioritized
CORE_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "gpt", "openai",
    "technology", "tech", "robot", "innovation", "future", "futurism",
    "productivity", "psychology", "mindset", "focus", "learning",
    "motivation", "discipline", "health", "science", "money", "finance",
    "startup", "automation"
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_google_news_trends():
    print("🌐 Fetching Google News Top Stories (RSS)...")
    url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.text)

    topics = []
    for item in root.findall(".//item"):
        title = item.find("title").text
        if title and len(title) > 5:
            topics.append(title.strip())
        if len(topics) >= 25:
            break

    print(f"✅ Found {len(topics)} Google News topics")
    return topics


def fetch_youtube_trending():
    print("🎥 Fetching YouTube trending videos (public feed)...")
    url = "https://www.youtube.com/feed/trending"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    titles = []
    for line in r.text.split("\n"):
        if '"title":{"runs":[{"text":"' in line:
            try:
                title = line.split('"title":{"runs":[{"text":"')[1].split('"')[0]
                if len(title) > 5:
                    titles.append(title.strip())
                if len(titles) >= 20:
                    break
            except Exception:
                continue

    print(f"✅ Found {len(titles)} YouTube trends")
    return titles


def prioritize_topics(topics):
    """Rank topics by presence of your focus keywords."""
    prioritized = []
    others = []

    for topic in topics:
        t_lower = topic.lower()
        if any(k in t_lower for k in CORE_KEYWORDS):
            prioritized.append(topic)
        else:
            others.append(topic)

    # Keep only the top 10 relevant ones, fill remaining from others
    combined = prioritized[:10]
    for t in others:
        if len(combined) >= 10:
            break
        combined.append(t)

    print(f"🔥 Prioritized {len(prioritized)} niche-relevant topics")
    return combined, prioritized


def categorize_topics(topics):
    categories = {
        'ai': ['ai', 'artificial intelligence', 'chatgpt', 'machine learning', 'gpt', 'neural'],
        'tech': ['tech', 'software', 'app', 'robot', 'digital', 'innovation', 'code', 'device'],
        'business': ['money', 'startup', 'entrepreneur', 'invest', 'stock', 'finance', 'market', 'business'],
        'psychology': ['mind', 'habit', 'mental', 'brain', 'psychology', 'focus', 'behavior', 'emotion'],
        'health': ['health', 'fitness', 'diet', 'sleep', 'wellness', 'nutrition', 'longevity'],
        'productivity': ['productivity', 'work', 'focus', 'time', 'goal', 'efficiency', 'organization', 'tools'],
        'innovation': ['innovation', 'future', 'breakthrough', 'discovery', 'invention'],
        'learning': ['learning', 'education', 'study', 'knowledge', 'skills', 'training'],
        'motivation': ['motivation', 'inspire', 'success', 'mindset', 'growth', 'discipline'],
        'futurism': ['future', 'robotics', 'space', 'technology', 'sci-fi', 'automation']
    }

    categorized = {}
    for topic in topics:
        t = topic.lower()
        matched = False
        for cat, keywords in categories.items():
            if any(kw in t for kw in keywords):
                categorized.setdefault(cat, []).append(topic)
                matched = True
                break
        if not matched:
            categorized.setdefault('general', []).append(topic)
    return categorized


def main():
    print("🚀 Starting fetch_trending.py")

    topics = []
    source = "fallback"

    try:
        topics = fetch_google_news_trends()
        source = "google_news"
    except Exception as e:
        print(f"⚠️ Google News failed: {e}")
        try:
            topics = fetch_youtube_trending()
            source = "youtube_trending"
        except Exception as e2:
            print(f"⚠️ YouTube trending failed: {e2}")
            print("🪄 Using fallback trending topics...")
            topics = [
                "AI breakthroughs in 2025",
                "Future of digital health",
                "New productivity apps",
                "Psychology of focus",
                "Business automation tools",
                "Fitness technology",
                "Remote work future",
                "Financial independence trends",
                "Motivation and self-discipline science",
                "Learning with AI tutors"
            ]

    prioritized_topics, niche_topics = prioritize_topics(topics)
    categorized = categorize_topics(prioritized_topics)

    if not any("ai" in t.lower() for t in prioritized_topics):
        prioritized_topics.insert(0, "AI breakthrough of the day")

    data = {
        "date": datetime.now().isoformat(),
        "source": source,
        "topics": prioritized_topics,
        "niche_relevant": niche_topics,
        "categorized": categorized
    }

    out_path = os.path.join(TMP, "trending.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved trending topics to {out_path}")
    print(f"📊 Source: {source} | {len(prioritized_topics)} topics (🔥 {len(niche_topics)} niche relevant)")
    print("🏁 fetch_trending.py completed successfully")


if __name__ == "__main__":
    main()
