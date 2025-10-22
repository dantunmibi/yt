# .github/scripts/generate_trending_and_script.py
import os
import json
import re
import hashlib
from datetime import datetime
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# ✅ FIXED: Store history in tmp (will use GitHub artifact for persistence)
os.makedirs(TMP, exist_ok=True)
HISTORY_FILE = os.path.join(TMP, "content_history.json")

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

def load_history():
    """Load history from previous run (if available)"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
                print(f"📂 Loaded {len(history.get('topics', []))} topics from history")
                return history
        except Exception as e:
            print(f"⚠️ Could not load history: {e}")
            return {'topics': []}
    
    print("📂 No previous history found, starting fresh")
    return {'topics': []}

def save_to_history(topic, script_hash, title):
    """Save to history file"""
    history = load_history()
    
    history['topics'].append({
        'topic': topic,
        'title': title,
        'hash': script_hash,
        'date': datetime.now().isoformat()
    })
    
    # Keep last 100 topics (increased from 50)
    history['topics'] = history['topics'][-100:]
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"💾 Saved to history ({len(history['topics'])} total topics)")

def get_content_hash(data):
    """Generate hash of content to detect duplicates"""
    content = json.dumps(data, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()

def load_trending():
    """Load trending topics from fetch_trending.py"""
    trending_file = os.path.join(TMP, "trending.json")
    if os.path.exists(trending_file):
        with open(trending_file, 'r') as f:
            return json.load(f)
    return None

def is_similar_topic(new_title, previous_titles, similarity_threshold=0.6):
    """Check if topic is too similar to previous ones with decay factor"""
    new_words = set(new_title.lower().split())
    
    # Weight recent topics more heavily (exponential decay)
    for idx, prev_title in enumerate(reversed(previous_titles)):
        prev_words = set(prev_title.lower().split())
        
        # Calculate Jaccard similarity
        intersection = len(new_words & prev_words)
        union = len(new_words | prev_words)
        
        if union > 0:
            base_similarity = intersection / union
            
            # Apply decay: recent topics need lower similarity, old topics need higher
            # idx=0 (most recent): decay=1.0, idx=50: decay≈0.5, idx=100: decay≈0.3
            decay_factor = 1.0 / (1.0 + idx * 0.02)
            adjusted_threshold = similarity_threshold * decay_factor
            
            if base_similarity > adjusted_threshold:
                days_ago = idx // 1  # Assuming 1 video per day
                print(f"⚠️ Topic too similar ({base_similarity:.2f} > {adjusted_threshold:.2f}) to: {prev_title}")
                print(f"   (from {days_ago} days ago)")
                return True
    
    return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_script_with_retry(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()

# Load history and trending
history = load_history()
trending = load_trending()

# Get previous topics (title + topic for better filtering)
previous_topics = [f"{t.get('topic', 'unknown')}: {t.get('title', '')}" for t in history['topics'][-15:]]
previous_titles = [t.get('title', '') for t in history['topics']]

# ✅ CRITICAL: Extract real trending topics and FORCE their use
trending_topics = []
trending_summaries = []

if trending and trending.get('topics'):
    trending_topics = trending['topics'][:5]
    
    # Get full data if available
    full_data = trending.get('full_data', [])
    if full_data:
        for item in full_data[:5]:
            trending_summaries.append(f"• {item['topic_title']}: {item.get('summary', 'No summary')}")
    else:
        trending_summaries = [f"• {t}" for t in trending_topics]
    
    print(f"🎯 Loaded {len(trending_topics)} REAL trending topics from web sources")
    print(f"   Source: {trending.get('source', 'unknown')}")
else:
    print("⚠️ No trending data found - will use fallback")

# Build mandatory trending section
if trending_topics:
    trending_mandate = f"""
⚠️⚠️⚠️ CRITICAL MANDATORY REQUIREMENT ⚠️⚠️⚠️

YOU MUST CREATE A SCRIPT ABOUT ONE OF THESE REAL TRENDING TOPICS:

{chr(10).join(trending_summaries)}

These are REAL trends from today ({datetime.now().strftime('%Y-%m-%d')}) collected from:
- Google Trends (real search data)
- Tech news RSS feeds (latest headlines)

YOU MUST PICK ONE OF THE 5 TOPICS ABOVE. 
DO NOT create content about anything else.
DO NOT make up your own topic.
USE THE EXACT TREND and expand it into a viral script.

If a trend is about "ChatGPT's new browser", your script MUST be about that exact feature.
If a trend is about "Samsung VR headset", your script MUST be about that specific device.
"""
else:
    trending_mandate = ""

prompt = f"""You are a viral YouTube Shorts content creator with millions of views.

CONTEXT:
- Current date: {datetime.now().strftime('%Y-%m-%d')}
- Previously covered (DO NOT REPEAT THESE): 
{chr(10).join(f"  • {t}" for t in previous_topics) if previous_topics else '  None'}

{trending_mandate}

TASK: Create a trending, viral-worthy script for a 45-75 second YouTube Short.

CRITICAL REQUIREMENTS:
✅ Topic must be COMPLETELY DIFFERENT from previous topics above
✅ Hook must create a curiosity gap (make viewers NEED to watch)
✅ Include specific numbers, statistics, or surprising facts
✅ 3 concise, punchy bullet points (each 15-20 words max)
✅ Be SPECIFIC - name actual tools, apps, techniques, not vague "this tool" or "this method"
✅ CTA must be casual and engaging - NOT salesy or course-pitchy
✅ Add 5-10 relevant and trending hashtags for maximum discoverability

PROVEN VIRAL FORMULAS:
- "3 Things Nobody Tells You About..."
- "Why [Surprising Fact] Will Change Everything"
- "The Secret [Group] Don't Want You to Know"
- "I Tried [Thing] For 30 Days, Here's What Happened"
- "[Number] Mind-Blowing Facts About..."

CTA GUIDELINES (VERY IMPORTANT):
❌ BAD CTAs: "Comment which one...", "Subscribe for more", "Click the link", "Take my course"
✅ GOOD CTAs: "Try this yourself and tag me!", "Which one shocked you?", "Save this before it's gone", "Share with someone who needs this", "Follow for daily tips like this"
- Keep it natural and conversational
- Make it feel like talking to a friend
- Encourage ACTION not just engagement metrics
- No selling, no courses, no links

SPECIFICITY RULES (VERY IMPORTANT):
DO NOT INCLUDE SPECIAL CHARACTERS OR QUOTES IN THE OUTPUT

❌ VAGUE: "This AI tool can help you"
✅ SPECIFIC: "ChatGPT's Code Interpreter can help you"

❌ VAGUE: "A simple trick improves focus"
✅ SPECIFIC: "The Pomodoro Technique improves focus by 40%"

❌ VAGUE: "Experts recommend this method"
✅ SPECIFIC: "Stanford researchers found this method doubles retention"

❌ VAGUE: "New AI feature"
✅ SPECIFIC: "Google's Gemini 2.0 Flash with live video"

OUTPUT FORMAT (JSON ONLY - NO OTHER TEXT):
{{
  "title": "Catchy title with specific details (under 100 chars)",
  "topic": "one_word_category",
  "hook": "Question or shocking statement with specifics (under 12 words)",
  "bullets": [
    "First key point - BE SPECIFIC with names/numbers/details (15-20 words)",
    "Second point - SPECIFIC fact or statistic with source (15-20 words)",
    "Third point - SPECIFIC actionable insight with exact method (15-20 words)"
  ],
  "cta": "Casual, friendly call-to-action - NO SALESY LANGUAGE (under 15 words)",
  "hashtags": ["#shorts", "#viral", "#trending", "#category", "#fyp"],
  "description": "2-3 sentence description with specific details for YouTube",
  "visual_prompts": [
    "Specific, detailed image prompt for hook scene with exact visual elements",
    "Specific, detailed image prompt for bullet 1 showing the exact concept visually",
    "Specific, detailed image prompt for bullet 2 with clear visual representation",
    "Specific, detailed image prompt for bullet 3 demonstrating the specific action"
  ]
}}

REMEMBER: 
- YOU MUST USE ONE OF THE 5 TRENDING TOPICS PROVIDED ABOVE!
- Be SPECIFIC! Name actual tools, techniques, studies, numbers!
- Make it COMPLETELY DIFFERENT from previous topics!
- Make it IRRESISTIBLE to click and watch!"""

# Try generating script with multiple attempts
max_attempts = 5
attempt = 0

while attempt < max_attempts:
    try:
        attempt += 1
        print(f"🎬 Generating viral script from REAL trends (attempt {attempt}/{max_attempts})...")
        
        raw_text = generate_script_with_retry(prompt)
        print(f"🔍 Raw output length: {len(raw_text)} chars")
        
        # Extract JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
            print("✅ Extracted JSON from code block")
        else:
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                print("✅ Extracted JSON directly")
            else:
                raise ValueError("No JSON found in response")
        
        data = json.loads(json_text)
        
        # Validate required fields
        required_fields = ["title", "topic", "hook", "bullets", "cta"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # ✅ VALIDATE: Check if script actually uses one of the trending topics
        if trending_topics:
            script_text = f"{data['title']} {data['hook']} {' '.join(data['bullets'])}".lower()
            
            # Check if ANY trending topic keyword appears in the script
            trend_keywords = []
            for topic in trending_topics:
                # Extract key words from trending topic (remove common words)
                words = [w for w in topic.lower().split() if len(w) > 4 and w not in [
                    'this', 'that', 'with', 'from', 'will', 'just', 'new'
                ]]
                trend_keywords.extend(words)
            
            # Check if at least 2 trending keywords appear
            matches = sum(1 for kw in trend_keywords if kw in script_text)
            
            if matches < 2:
                print(f"⚠️ Script doesn't use trending topics! Only {matches} keyword matches.")
                print(f"   Trending keywords: {trend_keywords[:10]}")
                print(f"   Script text: {script_text[:200]}...")
                raise ValueError("Script ignores trending topics - regenerating...")
        
        # Add optional fields with defaults
        if "hashtags" not in data:
            data["hashtags"] = ["#shorts", "#viral", "#trending", "#fyp"]
        
        if "description" not in data:
            data["description"] = f"{data['title']} - {data['hook']}"
        
        if "visual_prompts" not in data or len(data["visual_prompts"]) < 4:
            data["visual_prompts"] = [
                f"Eye-catching opening image for: {data['hook']}, cinematic, dramatic lighting, vibrant colors",
                f"Visual representation of: {data['bullets'][0]}, photorealistic, vibrant, professional",
                f"Visual representation of: {data['bullets'][1]}, photorealistic, vibrant, professional",
                f"Visual representation of: {data['bullets'][2]}, photorealistic, vibrant, professional"
            ]
        
        if not isinstance(data["bullets"], list) or len(data["bullets"]) < 3:
            raise ValueError("bullets must be a list with at least 3 items")
        
        # Check for duplicates
        content_hash = get_content_hash(data)
        if content_hash in [t.get('hash') for t in history['topics']]:
            print("⚠️ Generated duplicate content (exact match), regenerating...")
            raise ValueError("Duplicate content detected")
        
        # Check for similar topics
        if is_similar_topic(data['title'], previous_titles):
            print("⚠️ Topic too similar to previous, regenerating...")
            raise ValueError("Similar topic detected")
        
        # Success! Save to history
        save_to_history(data['topic'], content_hash, data['title'])
        
        print("✅ Script generated successfully from REAL trending data")
        print(f"   Title: {data['title']}")
        print(f"   Topic: {data['topic']}")
        print(f"   Hook: {data['hook']}")
        print(f"   Hashtags: {', '.join(data['hashtags'][:5])}")
        
        break  # Success, exit loop
        
    except Exception as e:
        print(f"❌ Attempt {attempt} failed: {e}")
        
        if attempt >= max_attempts:
            print("⚠️ Max attempts reached, using fallback script...")
            data = {
                "title": "ChatGPT Just Got a Browser - Here's Why It Matters",
                "topic": "technology",
                "hook": "ChatGPT can now browse the web in real-time",
                "bullets": [
                    "ChatGPT's new browser integration lets it access live web data, fact-check in real-time, and find current information instantly",
                    "Unlike traditional search, it can analyze entire websites, compare sources, and synthesize information across multiple pages automatically",
                    "You can ask it to research competitors, track price changes, or monitor news - all without leaving the conversation"
                ],
                "cta": "Try asking ChatGPT to research something live and share your results!",
                "hashtags": ["#chatgpt", "#ai", "#technology", "#openai", "#shorts", "#viral", "#tech"],
                "description": "ChatGPT's new browser integration changes everything. Now it can access real-time web data, fact-check instantly, and research topics without you leaving the chat. This is a game-changer for AI assistants.",
                "visual_prompts": [
                    "Smartphone showing ChatGPT interface with browser window overlay, glowing network connections, person looking amazed, blue tech lighting",
                    "Split screen showing ChatGPT analyzing multiple websites simultaneously with data streams and fact-checking overlays, futuristic UI",
                    "Person using ChatGPT on laptop with multiple browser tabs auto-researching in background, glowing AI assistant icon, productive workspace",
                    "ChatGPT logo with browser icon merging together, digital neural network connections, inspiring tech visualization, bright colors"
                ]
            }
            
            # Save fallback to history too
            fallback_hash = get_content_hash(data)
            save_to_history(data['topic'], fallback_hash, data['title'])

# Save script to file
os.makedirs(TMP, exist_ok=True)
script_path = os.path.join(TMP, "script.json")

with open(script_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Saved script to {script_path}")
print(f"📊 Total topics in history: {len(history['topics'])}")
print(f"📝 Script preview:")
print(f"   Title: {data['title']}")
print(f"   Bullets: {len(data['bullets'])} points")
print(f"   Visual prompts: {len(data['visual_prompts'])} images")

if trending:
    print(f"\n🌐 Source: {trending.get('source', 'Unknown')}")
    print(f"   Trending topics used: {', '.join(trending_topics[:3])}...")