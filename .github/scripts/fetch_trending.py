import json
import time
import random
from typing import List, Dict, Any
import os
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Configure using the same pattern as your working script
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use the same model selection logic as your working script
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
    for attempt in range(3):  # Try 3 times
        try:
            from pytrends.request import TrendReq
            
            print(f"🔍 Fetching Google Trends (US) - Attempt {attempt + 1}/3...")
    # Simplified initialization - let pytrends handle its own defaults
            try:
                pytrends = TrendReq(hl='en-US', tz=360)
            except Exception as init_error:
                print(f"   ⚠️ PyTrends initialization failed: {init_error}")
                return []
            
            relevant_trends = []
        
            # Filter for tech/AI/science related
            tech_keywords = [
                'ai', 'tech', 'robot', 'google', 'chatgpt', 'openai', 'microsoft',
                'apple', 'samsung', 'meta', 'vr', 'ar', 'space', 'nasa', 'science',
                'brain', 'psychology', 'innovation', 'app', 'software', 'crypto',
                'bitcoin', 'tesla', 'elon', 'gadget', 'phone', 'computer', 'gaming'
            ]
            
            for trend in all_trends:
                try:
                    print(f"   🔍 Searching trends for: {topic}")
                    pytrends.build_payload([topic], timeframe='now 7-d', geo='')
                    related = pytrends.related_queries()
                    
                    if topic in related and 'top' in related[topic]:
                        top_queries = related[topic]['top']
                        if top_queries is not None and not top_queries.empty:
                            for query in top_queries['query'].head(5):
                                if len(query) > 10:  # Filter very short queries
                                    relevant_trends.append(query)
                                    print(f"      ✓ {query}")
                    
                    time.sleep(2)  # Rate limiting between requests
                    
                except Exception as e:
                    print(f"   ⚠️ Failed for '{topic}': {str(e)[:50]}...")
                    continue
            
            print(f"✅ Found {len(relevant_trends)} gardening-related trends from Google")
            return relevant_trends[:15]
            
        except ImportError:
            print("⚠️ pytrends not installed - run: pip install pytrends")
            return []
        except Exception as e:
            print(f"⚠️ Google Trends failed: {e}")
            return []


def get_tech_news_rss() -> List[str]:
    """Scrape latest tech news from RSS feeds (FREE)"""
    try:
        print("📰 Fetching tech news from RSS feeds...")
        
        # Free tech news RSS feeds
        rss_feeds = [
            'https://techcrunch.com/feed/',
            'https://www.theverge.com/rss/index.xml',
            'https://www.wired.com/feed/rss',
        ]
        
        headlines = []
        
        for feed_url in rss_feeds:
            try:
                response = requests.get(feed_url, timeout=10)
                soup = BeautifulSoup(response.content, 'xml')
                
                # Get recent items (last 24 hours preferred)
                items = soup.find_all('item')[:10]
                
                for item in items:
                    title = item.find('title')
                    if title:
                        headline = title.text.strip()
                        # Filter for AI/tech keywords
                        if any(kw in headline.lower() for kw in [
                            'ai', 'chatgpt', 'openai', 'google', 'microsoft',
                            'tech', 'robot', 'vr', 'ar', 'space', 'science',
                            'innovation', 'breakthrough'
                        ]):
                            headlines.append(headline)
                
            except Exception as e:
                print(f"   ⚠️ Failed to fetch {feed_url}: {e}")
                continue
        
        print(f"✅ Found {len(headlines)} relevant tech headlines")
        return headlines[:15]
        
    except Exception as e:
        print(f"⚠️ RSS feed scraping failed: {e}")
        return []


def get_real_trending_topics() -> List[str]:
    """Combine multiple FREE sources for real trending topics"""
    
    print("\n" + "="*60)
    print("🌐 FETCHING REAL-TIME TRENDING TOPICS (FREE SOURCES)")
    print("="*60)
    
    all_trends = []
    
    # Source 1: Google Trends
    google_trends = get_google_trends()
    all_trends.extend(google_trends)
    
    # Source 2: Tech News RSS
    tech_news = get_tech_news_rss()
    all_trends.extend(tech_news)
    
    # Deduplicate and prioritize
    seen = set()
    unique_trends = []
    for trend in all_trends:
        trend_clean = trend.lower().strip()
        if trend_clean not in seen and len(trend) > 10:  # Filter out too short
            seen.add(trend_clean)
            unique_trends.append(trend)
    
    print(f"\n📊 Total unique trending topics found: {len(unique_trends)}")
    
    return unique_trends[:20]  # Return top 20


def filter_and_rank_trends(trends: List[str], user_query: str) -> List[Dict[str, str]]:
    """Use Gemini to filter and rank trends based on viral potential"""
    
    if not trends:
        print("⚠️ No trends to filter, using fallback...")
        return get_fallback_ideas()
    
    print(f"\n🤖 Using Gemini to rank {len(trends)} real trends for viral potential...")
    
    # Define the structure for the JSON output
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

REAL TRENDING TOPICS (from Google Trends & Tech News):
{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(trends[:20]))}

TASK: Select the TOP 5 topics that would make the MOST VIRAL YouTube Shorts.

SELECTION CRITERIA:
✅ Must be genuinely surprising or mind-blowing
✅ Must have visual potential for short-form video
✅ Must be currently trending (these are all real trends from today)
✅ Must relate to: AI, Tech, Psychology, Money, Health, Productivity, Science, Innovation
✅ Must have "wow factor" - make viewers stop scrolling

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
    # Example usage:
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
            "source": "google_trends + tech_rss + gemini_ranking"
        }
        
        trending_file = os.path.join(TMP, "trending.json")
        with open(trending_file, "w") as f:
            json.dump(trending_data, f, indent=2)
        
        print(f"\n💾 Saved trending data to: {trending_file}")
        print(f"📊 Data sources: Google Trends + Tech News RSS (100% FREE)")
    else:
        print("\n❌ Could not retrieve any trending video ideas.")