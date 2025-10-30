import json
import time
import random
from typing import List, Dict, Any
import os
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    models = genai.list_models()
    model_name = None
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            if '2.0-flash' in m.name or '2.5-flash' in m.name:
                model_name = m.name
                break
            elif '1.5-flash' in m.name and not model_name:
                model_name = m.name
    
    if not model_name:
        model_name = "models/gemini-1.5-flash"
    
    print(f"✅ Using model: {model_name}")
    model = genai.GenerativeModel(model_name)
except Exception as e:
    print(f"⚠️ Error listing models: {e}")
    model = genai.GenerativeModel("models/gemini-1.5-flash")

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)


def get_google_trends() -> List[str]:
    """Get real trending searches from Google Trends (FREE - no API key needed)"""
    for attempt in range(3):
        try:
            from pytrends.request import TrendReq
            
            print(f"🔍 Fetching Google Trends (US) - Attempt {attempt + 1}/3...")
            
            try:
                pytrends = TrendReq(hl='en-US', tz=360)
            except Exception as init_error:
                print(f"   ⚠️ PyTrends initialization failed: {init_error}")
                if attempt < 2:
                    time.sleep(5)
                    continue
                return []
            
            relevant_trends = []
            
            tech_keywords = [
                'ai', 'tech', 'robot', 'google', 'chatgpt', 'openai', 'microsoft',
                'apple', 'samsung', 'meta', 'vr', 'ar', 'space', 'nasa', 'science',
                'brain', 'psychology', 'innovation', 'app', 'software', 'crypto',
                'bitcoin', 'tesla', 'elon', 'gadget', 'phone', 'computer', 'gaming'
            ]
            
            # Try daily trends
            try:
                trending = pytrends.today_searches(pn='US')
                all_trends = trending.head(20).tolist()  # ✅ remove [0]

                for trend in all_trends:
                    trend_lower = trend.lower()
                    if any(keyword in trend_lower for keyword in tech_keywords):
                        relevant_trends.append(trend)
                        print(f"   ✓ Found daily trend: {trend}")

                print(f"✅ Found {len(relevant_trends)} tech-related daily trends")

            except Exception as e:
                print(f"   ⚠️ Daily trends failed: {str(e)[:100]}")

            
            # Search specific topics if needed
            if len(relevant_trends) < 10:
                print("   🔄 Searching related queries...")
                
                search_topics = [
                    'artificial intelligence', 'chatgpt', 'ai technology',
                    'tech news', 'innovation', 'productivity apps',
                    'brain hack', 'psychology', 'self improvement'
                ]
                
                for topic in search_topics:
                    try:
                        print(f"   🔍 Searching: {topic}")
                        pytrends.build_payload([topic], timeframe='now 7-d', geo='')
                        related = pytrends.related_queries()
                        
                        if topic in related and 'top' in related[topic]:
                            top_queries = related[topic]['top']
                            if top_queries is not None and not top_queries.empty:
                                for query in top_queries['query'].head(5):
                                    if len(query) > 10 and query not in relevant_trends:
                                        relevant_trends.append(query)
                                        print(f"      ✓ {query}")
                        
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"   ⚠️ Failed for '{topic}': {str(e)[:50]}...")
                        continue
            
            print(f"✅ Found {len(relevant_trends)} tech trends from Google")
            return relevant_trends[:15]
            
        except ImportError:
            print("⚠️ pytrends not installed")
            return []
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(5)
            continue
    
    return []


def get_tech_news_rss() -> List[str]:
    """Scrape latest tech news from RSS feeds (FREE) - ENHANCED VERSION"""
    try:
        print("📰 Fetching tech news from RSS feeds...")
        
        # Expanded tech news RSS feeds (verified working)
        rss_feeds = [
            'https://techcrunch.com/feed/',
            'https://www.theverge.com/rss/index.xml',
            'https://www.wired.com/feed/rss',
            'https://arstechnica.com/feed/',
            'https://www.engadget.com/rss.xml',
            'https://mashable.com/feeds/rss/all',
            'https://www.cnet.com/rss/news/',
        ]
        
        headlines = []
        
        for feed_url in rss_feeds:
            try:
                print(f"   📡 Fetching {feed_url}...")
                response = requests.get(feed_url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                if response.status_code != 200:
                    print(f"      ⚠️ Status {response.status_code}")
                    continue
                
                # Try both XML and HTML parsing
                try:
                    soup = BeautifulSoup(response.content, 'xml')
                except:
                    soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try multiple title tag patterns
                items = soup.find_all('item')
                if not items:
                    items = soup.find_all('entry')  # Atom format
                
                print(f"      Found {len(items)} items")
                
                for item in items[:15]:
                    title = None
                    
                    # Try different title extraction methods
                    if item.find('title'):
                        title = item.find('title').text.strip()
                    elif item.find('content'):
                        title = item.find('content').text.strip()[:100]
                    
                    if title and len(title) > 15:
                        # Filter for AI/tech keywords
                        tech_words = [
                            'ai', 'chatgpt', 'openai', 'google', 'microsoft',
                            'tech', 'robot', 'vr', 'ar', 'space', 'science',
                            'innovation', 'breakthrough', 'app', 'software',
                            'brain', 'psychology', 'productivity', 'hack'
                        ]
                        
                        headline_lower = title.lower()
                        if any(kw in headline_lower for kw in tech_words):
                            headlines.append(title)
                            print(f"      ✓ {title[:60]}...")
                
            except Exception as e:
                print(f"   ⚠️ Failed to fetch {feed_url}: {str(e)[:50]}...")
                continue
        
        print(f"✅ Found {len(headlines)} relevant tech headlines")
        return headlines[:15]
        
    except Exception as e:
        print(f"⚠️ RSS feed scraping failed: {e}")
        return []


def get_reddit_tech_trends() -> List[str]:
    """Get trending posts from tech subreddits (FREE - no API key)"""
    try:
        print("💬 Fetching Reddit tech trends...")
        
        subreddits = [
            'technology', 'artificial', 'ChatGPT', 'OpenAI', 
            'dataisbeautiful', 'futurology', 'gadgets', 'productivity'
        ]
        trends = []
        
        for subreddit in subreddits:
            try:
                url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit=20'
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
                
                print(f"   📱 Fetching r/{subreddit}...")
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    posts_found = 0
                    
                    for post in data['data']['children'][:15]:
                        title = post['data']['title']
                        
                        # STRICT filtering: Only accept informational/tutorial content
                        good_phrases = [
                            'how to', 'how i', 'guide to', 'tips for', 'method for',
                            'update:', 'breaking:', 'new:', 'just released', 'announced',
                            'discovered', 'study:', 'research:', 'found that',
                            'hack:', 'technique', 'tutorial', 'explained', 'review:'
                        ]
                        
                        # Reject questions and help requests
                        bad_phrases = [
                            '?', 'help', 'eli5', 'should i', 'why is',
                            'can someone', 'does anyone', 'am i the only',
                            'unpopular opinion', 'hot take'
                        ]
                        
                        title_lower = title.lower()
                        
                        # Must have good phrase AND no bad phrases
                        has_good = any(phrase in title_lower for phrase in good_phrases)
                        has_bad = any(phrase in title_lower for phrase in bad_phrases)
                        
                        if has_good and not has_bad:
                            trends.append(title)
                            posts_found += 1
                            print(f"      ✓ {title[:70]}...")
                    
                    print(f"      Found {posts_found} informational posts")
                else:
                    print(f"      ⚠️ Status {response.status_code}")
                
                time.sleep(2)  # Respectful rate limiting
                
            except Exception as e:
                print(f"   ⚠️ Failed to fetch r/{subreddit}: {e}")
                continue
        
        print(f"✅ Found {len(trends)} trending tech topics from Reddit")
        return trends[:15]
        
    except Exception as e:
        print(f"⚠️ Reddit scraping failed: {e}")
        return []


def get_real_trending_topics() -> List[str]:
    """Combine multiple FREE sources for real trending topics - ENHANCED"""
    
    print("\n" + "="*60)
    print("🌐 FETCHING REAL-TIME TRENDING TOPICS (FREE SOURCES)")
    print("="*60)
    
    all_trends = []
    
    # Source 1: Google Trends
    google_trends = get_google_trends()
    all_trends.extend(google_trends)
    
    # Source 2: Tech News RSS (ENHANCED)
    tech_news = get_tech_news_rss()
    all_trends.extend(tech_news)
    
    # Source 3: Reddit Tech Communities (NEW)
    reddit_trends = get_reddit_tech_trends()
    all_trends.extend(reddit_trends)
    
    # Deduplicate and prioritize
    seen = set()
    unique_trends = []
    for trend in all_trends:
        trend_clean = trend.lower().strip()
        if trend_clean not in seen and len(trend) > 10:
            seen.add(trend_clean)
            unique_trends.append(trend)
    
    print(f"\n📊 Total unique trending topics found: {len(unique_trends)}")
    
    return unique_trends[:25]  # Return top 25


def filter_and_rank_trends(trends: List[str], user_query: str) -> List[Dict[str, str]]:
    """Use Gemini to filter and rank trends based on viral potential"""
    
    if not trends:
        print("⚠️ No trends to filter, using fallback...")
        return get_fallback_ideas()
    
    print(f"\n🤖 Using Gemini to rank {len(trends)} real trends for viral potential...")
    
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "selected_topics": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "reason": {"type": "STRING"},
                        "viral_score": {"type": "NUMBER"}
                    }
                },
                "description": "Top 5 trending topics ranked by viral potential"
            }
        },
        "required": ["selected_topics"]
    }
    
    prompt = f"""You are a viral content strategist. Here are REAL trending topics from today:

REAL TRENDING TOPICS (from Google Trends, Tech RSS, Reddit):
{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(trends[:25]))}

TASK: Select the TOP 5 topics that would make the MOST VIRAL YouTube Shorts.

SELECTION CRITERIA:
✅ Must be genuinely surprising or mind-blowing
✅ Must have visual potential for short-form video
✅ Must be currently trending (these are all real trends from today)
✅ Must relate to: AI, Tech, Psychology, Money, Health, Productivity, Science, Innovation
✅ Must have "wow factor" - make viewers stop scrolling
✅ Prefer specific tools, techniques, or discoveries over general news

FOCUS AREAS: {user_query}

OUTPUT FORMAT (JSON ONLY):
{{
  "selected_topics": [
    {{
      "title": "Specific catchy title based on the trend",
      "reason": "Why this will go viral",
      "viral_score": 95
    }}
  ]
}}

GOOD EXAMPLES:
- "ChatGPT's Hidden Feature That Saves 2 Hours Daily"
- "Scientists Discovered Why You Forget Names Instantly"
- "This iPhone Setting Drains Your Battery 40% Faster"

Select 5 topics, ranked by viral_score (highest first)."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            
            result_text = response.text.strip()
            
            # Extract JSON if wrapped
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            
            data = json.loads(result_text)
            
            # Convert to expected format
            trending_ideas = []
            for item in data.get('selected_topics', [])[:5]:
                trending_ideas.append({
                    "topic_title": item.get('title', 'Unknown'),
                    "summary": item.get('reason', 'High viral potential'),
                    "category": "Trending",
                    "viral_score": item.get('viral_score', 90)
                })
            
            print(f"✅ Gemini ranked {len(trending_ideas)} viral topics from real trends")
            return trending_ideas
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    # Fallback: Just use first 5 trends
    print("⚠️ Gemini ranking failed, using raw trends...")
    return [
        {
            "topic_title": trend,
            "summary": "Currently trending topic",
            "category": "Trending"
        }
        for trend in trends[:5]
    ]


def get_fallback_ideas() -> List[Dict[str, str]]:
    """Fallback trending ideas if all methods fail"""
    return [
        {
            "topic_title": "ChatGPT's New Browser Feature Changes Everything",
            "summary": "OpenAI just released a browser integration that lets ChatGPT surf the web in real-time",
            "category": "Technology"
        },
        {
            "topic_title": "Samsung's Secret VR Headset Leaked",
            "summary": "Internal documents reveal Samsung's AR/VR headset with eye-tracking and hand gestures",
            "category": "Technology"
        },
        {
            "topic_title": "Google's Gemini 2.0 Flash Outperforms GPT-4",
            "summary": "New benchmarks show Gemini 2.0 is faster and more accurate than GPT-4 on coding tasks",
            "category": "Technology"
        }
    ]


if __name__ == "__main__":        
    topic_focus = "AI brain hacks, cutting-edge technology, innovation, digital productivity, trending life enhancement tools, and life optimization tricks for Ultra Engaging Youtube Shorts"
    
    # Get real trending topics from free sources
    real_trends = get_real_trending_topics()
    
    if real_trends:
        # Use Gemini to filter and rank for viral potential
        trending_ideas = filter_and_rank_trends(real_trends, topic_focus)
    else:
        print("⚠️ Could not fetch real trends, using fallback...")
        trending_ideas = get_fallback_ideas()
    
    if trending_ideas:
        print(f"\n" + "="*60)
        print(f"🎯 TOP VIRAL TRENDING IDEAS (FROM REAL DATA)")
        print("="*60)
        
        for i, idea in enumerate(trending_ideas):
            print(f"\nIdea {i + 1}:")
            print(f"  Title: {idea['topic_title']}")
            print(f"  Category: {idea['category']}")
            print(f"  Summary: {idea['summary']}")
            if 'viral_score' in idea:
                print(f"  Viral Score: {idea['viral_score']}/100")
        
        # Save to file for use by other scripts
        trending_data = {
            "topics": [idea["topic_title"] for idea in trending_ideas],
            "full_data": trending_ideas,
            "generated_at": time.time(),
            "query": topic_focus,
            "source": "google_trends + tech_rss + reddit + gemini_ranking"
        }
        
        trending_file = os.path.join(TMP, "trending.json")
        with open(trending_file, "w") as f:
            json.dump(trending_data, f, indent=2)
        
        print(f"\n💾 Saved trending data to: {trending_file}")
        print(f"📊 Data sources: Google Trends + Tech RSS + Reddit (100% FREE)")
    else:
        print("\n❌ Could not retrieve any trending video ideas.")