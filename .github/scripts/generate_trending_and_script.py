# .github/scripts/generate_trending_and_script.py
import os
import json
import re
import hashlib
from datetime import datetime
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# ===== SERIES-AWARE ENHANCEMENTS (PACKAGE 3) =====
SERIES_NAME = os.getenv("SERIES_NAME", "none")
EPISODE_NUMBER = int(os.getenv("EPISODE_NUMBER", "0"))
CONTENT_TYPE = os.getenv("CONTENT_TYPE", "general")

print(f"🎬 Series-aware generation:")
print(f"   Series: {SERIES_NAME}")
print(f"   Episode: {EPISODE_NUMBER}")
print(f"   Content Type: {CONTENT_TYPE}")

# ✅ CRITICAL: Store history in tmp (will use GitHub artifact for persistence)
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


def load_series_guidance():
    """Load series-specific content guidance from YOUR 83-video performance data"""
    try:
        with open('config/content_recommendations.json', 'r') as f:
            config = json.load(f)
        
        # New structure uses 'series' key
        if 'series' in config:
            # Map content_type to series
            content_type_mapping = {
                'tool_teardown_tuesday': 'tool_teardown_tuesday',
                'tool_teardown_thursday': 'tool_teardown_thursday',
                'viral_ai_saturday': 'viral_ai_saturday',
                'ai_tools': 'tool_teardown_tuesday',  # Fallback
                'entertainment': 'viral_ai_saturday'  # Fallback
            }
            
            series_key = content_type_mapping.get(CONTENT_TYPE, 'tool_teardown_tuesday')
            
            if series_key in config['series']:
                series_config = config['series'][series_key]
                print(f"✅ Loaded series guidance for: {series_key}")
                print(f"   Proven performance: {series_config.get('proven_performance', 'N/A')}")
                return series_config
        
        print(f"⚠️ No series guidance found for: {CONTENT_TYPE}, using defaults")
        return None
    except Exception as e:
        print(f"⚠️ Could not load series guidance: {e}")
        return None


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
        'date': datetime.now().isoformat(),
        'series': SERIES_NAME,
        'episode': EPISODE_NUMBER,
        'content_type': CONTENT_TYPE
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
            decay_factor = 1.0 / (1.0 + idx * 0.02)
            adjusted_threshold = similarity_threshold * decay_factor
            
            if base_similarity > adjusted_threshold:
                days_ago = idx // 1
                print(f"⚠️ Topic too similar ({base_similarity:.2f} > {adjusted_threshold:.2f}) to: {prev_title}")
                print(f"   (from {days_ago} days ago)")
                return True
    
    return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_script_with_retry(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()


# ===== MAIN EXECUTION =====

# Load history and trending
history = load_history()
trending = load_trending()
series_guidance = load_series_guidance()

# Get previous topics
previous_topics = [f"{t.get('topic', 'unknown')}: {t.get('title', '')}" for t in history['topics'][-15:]]
previous_titles = [t.get('title', '') for t in history['topics']]

# Extract real trending topics
trending_topics = []
trending_summaries = []

if trending and trending.get('topics'):
    trending_topics = trending['topics'][:5]
    
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

# ===== BUILD SERIES-SPECIFIC PROMPT =====

# Build title template from series guidance
title_template = ""
proven_examples = []
avoid_examples = []
cta_template = ""

if series_guidance:
    # Get title formula
    if isinstance(series_guidance.get('title_formula'), dict):
        title_template = series_guidance['title_formula'].get('with_episode', '')
        if title_template and EPISODE_NUMBER > 0:
            title_template = title_template.replace('[N]', str(EPISODE_NUMBER))
        
        # Get proven winners from YOUR channel
        proven_examples = series_guidance['title_formula'].get('proven_winners_from_your_channel', [])
    
    # Get hook examples
    if 'script_guidance' in series_guidance:
        avoid_examples = series_guidance['script_guidance'].get('hook_examples_that_failed', [])
        cta_template = series_guidance['script_guidance'].get('cta_template', '')
        if cta_template and EPISODE_NUMBER > 0:
            cta_template = cta_template.replace('[N+1]', str(EPISODE_NUMBER + 1))

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
USE THE EXACT TREND and expand it into a viral script.
"""
else:
    trending_mandate = ""

# Build series-specific instructions
series_instructions = ""
if series_guidance:
    series_instructions = f"""
⚠️ SERIES-SPECIFIC REQUIREMENTS FOR {SERIES_NAME}:

PROVEN PERFORMANCE FROM YOUR 83 VIDEOS:
{series_guidance.get('proven_performance', 'N/A')}

Title Template (USE THIS): {title_template}

PROVEN WINNERS FROM YOUR CHANNEL (REPLICATE THESE):
{chr(10).join(f"  ✅ {ex}" for ex in proven_examples[:5])}

PROVEN FAILURES FROM YOUR CHANNEL (AVOID THESE):
{chr(10).join(f"  ❌ {ex}" for ex in avoid_examples[:3])}

Content Requirements:
{chr(10).join(f"  • {req}" for req in series_guidance.get('content_requirements', {}).get('must_include', []))}

Optimal Length: {series_guidance.get('content_requirements', {}).get('optimal_length', '25-28 seconds')}

Target Completion Rate: {series_guidance.get('content_requirements', {}).get('target_completion', '60%')}+

Hook Structure: {series_guidance.get('content_requirements', {}).get('hook_structure', 'Grab attention in first 3 seconds')}

CTA Template: {cta_template}

This is EPISODE {EPISODE_NUMBER} of the {SERIES_NAME} series.
"""

# ===== MAIN PROMPT =====

prompt = f"""You are a viral YouTube Shorts content creator with millions of views.

CONTEXT:
- Current date: {datetime.now().strftime('%Y-%m-%d')}
- Series: {SERIES_NAME}
- Episode Number: {EPISODE_NUMBER}
- Content Type: {CONTENT_TYPE}
- Previously covered (DO NOT REPEAT THESE): 
{chr(10).join(f"  • {t}" for t in previous_topics) if previous_topics else '  None'}

{trending_mandate}

{series_instructions}

TASK: Create a trending, viral-worthy script for a 45-75 second YouTube Short.

CRITICAL DATA-DRIVEN REQUIREMENTS (from analyzing 83 videos):

✅ WHAT WORKS (64.6% completion proven):
- Specific tool names: ChatGPT, Canva, Midjourney (NOT "this AI tool")
- SECRET or HIDDEN or FREE angle in title
- Visual transformations (Text to 3D: 461.7% completion!)
- Time benefits in SECONDS (not minutes)
- Before/after demonstrations

❌ WHAT FAILS (14.7-30.5% completion proven):
- Generic "3 AI Tools" or "AI Hacks" titles
- Vague tools without naming specific products
- News without entertainment value
- Negative framing (FAILED, HACKED) without resolution
- Fear-mongering without solutions

PROVEN VIRAL FORMULAS FROM YOUR CHANNEL:
- "Text to 3D Models: This AI Tool Changes Design FOREVER!" (461.7% completion!)
- "ChatGPT-5 Sees Earth Future: 3 Mind-Blowing Climate AI Facts" (185.9%)
- "Instagram FREE AI Photos: Get Photoshop Magic NOW!" (71.3%)
- "Rizzbot FLIPPED ME OFF on TikTok LIVE! AI Gone Wild?" (80.7%, 333 views)

CTA GUIDELINES:
❌ BAD: "Comment which one", "Subscribe for more"
✅ GOOD: "Next {series_guidance.get('posting_day', 'week') if series_guidance else 'Tuesday'}: [SPECIFIC TOOL TEASE]. Subscribe!"

SPECIFICITY RULES:
❌ VAGUE: "This AI tool can help you"
✅ SPECIFIC: "ChatGPT Code Interpreter analyzes spreadsheets in 10 seconds"

OUTPUT FORMAT (JSON ONLY - NO OTHER TEXT):
{{
  "title": "MUST follow series template with Episode {EPISODE_NUMBER} if applicable (under 100 chars)",
  "topic": "one_word_category",
  "series": "{SERIES_NAME}",
  "episode": {EPISODE_NUMBER},
  "content_type": "{CONTENT_TYPE}",
  "hook": "Question or shocking statement (under 12 words)",
  "bullets": [
    "First key point - BE SPECIFIC with tool names/numbers (15-20 words)",
    "Second point - SPECIFIC fact with source or demo (15-20 words)",
    "Third point - SPECIFIC actionable result with exact method (15-20 words)"
  ],
  "cta": "MUST follow series CTA template (under 20 words)",
  "hashtags": ["#shorts", "#viral", "#trending", "#{CONTENT_TYPE}", "#fyp"],
  "description": "2-3 sentence description mentioning Episode {EPISODE_NUMBER if EPISODE_NUMBER > 0 else ''}",
  "visual_prompts": [
    "Specific image prompt for hook (show END RESULT first!)",
    "Specific image prompt for bullet 1 (visual transformation)",
    "Specific image prompt for bullet 2 (before/after comparison)",
    "Specific image prompt for bullet 3 (final result demonstration)"
  ]
}}

REMEMBER FROM YOUR 83-VIDEO ANALYSIS:
- Tool demos average 64.6% completion (YOUR BEST!)
- Text-to-3D got 461.7% (people watched 4.6 times!)
- Generic AI Hacks got only 14.7% (AVOID!)
- Specific tool names perform 4x better than generic
- Entertainment with shock value works (Rizzbot: 80.7%)
- News without value fails (30.5% average)

USE THE TRENDING TOPICS ABOVE!
BE SPECIFIC WITH TOOL NAMES!
FOLLOW THE PROVEN FORMULA!"""

# Try generating script with multiple attempts
max_attempts = 5
attempt = 0

while attempt < max_attempts:
    try:
        attempt += 1
        print(f"🎬 Generating viral script (attempt {attempt}/{max_attempts})...")
        
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
        
        # Validate against trending topics if available
        if trending_topics:
            script_text = f"{data['title']} {data['hook']} {' '.join(data['bullets'])}".lower()
            
            trend_keywords = []
            for topic in trending_topics:
                words = [w for w in topic.lower().split() if len(w) > 4 and w not in [
                    'this', 'that', 'with', 'from', 'will', 'just', 'new'
                ]]
                trend_keywords.extend(words)
            
            matches = sum(1 for kw in trend_keywords if kw in script_text)
            
            if matches < 2:
                print(f"⚠️ Script does not use trending topics! Only {matches} keyword matches.")
                raise ValueError("Script ignores trending topics - regenerating...")
        
        # Add series metadata
        data['series'] = SERIES_NAME
        data['episode'] = EPISODE_NUMBER
        data['content_type'] = CONTENT_TYPE
        
        # Add optional fields with defaults
        if "hashtags" not in data:
            data["hashtags"] = ["#shorts", "#viral", "#trending", "#fyp"]
        
        if "description" not in data:
            desc = f"{data['title']} - {data['hook']}"
            if EPISODE_NUMBER > 0:
                desc = f"Episode {EPISODE_NUMBER}: {desc}"
            data["description"] = desc
        
        if "visual_prompts" not in data or len(data["visual_prompts"]) < 4:
            data["visual_prompts"] = [
                f"Eye-catching opening showing END RESULT for: {data['hook']}, cinematic, vibrant",
                f"Visual transformation: {data['bullets'][0]}, photorealistic, before/after",
                f"Demo screenshot: {data['bullets'][1]}, clear UI, professional",
                f"Final result: {data['bullets'][2]}, impressive output, satisfying"
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
        
        print("✅ Script generated successfully!")
        print(f"   Title: {data['title']}")
        print(f"   Series: {data['series']} - Episode {data['episode']}")
        print(f"   Content Type: {data['content_type']}")
        print(f"   Hook: {data['hook']}")
        
        break  # Success, exit loop
        
    except Exception as e:
        print(f"❌ Attempt {attempt} failed: {e}")
        
        if attempt >= max_attempts:
            print("⚠️ Max attempts reached, using fallback based on YOUR best performers...")
            
            # Fallback uses YOUR proven format (Text to 3D style)
            data = {
                "title": f"Tool Teardown Tuesday - Episode {EPISODE_NUMBER if EPISODE_NUMBER > 0 else 1}: ChatGPT Vision's SECRET Image Analysis!",
                "topic": "ai_tools",
                "series": SERIES_NAME if SERIES_NAME != "none" else "Tool Teardown Tuesday",
                "episode": EPISODE_NUMBER if EPISODE_NUMBER > 0 else 1,
                "content_type": CONTENT_TYPE,
                "hook": "ChatGPT can now analyze ANY image in SECONDS",
                "bullets": [
                    "ChatGPT Vision analyzes photos, screenshots, diagrams and extracts text, data or insights instantly without any manual work",
                    "Upload any image to ChatGPT, ask specific questions about it, and get detailed analysis in under 10 seconds",
                    "You can use it for homework help, document analysis, design feedback, or understanding complex diagrams with zero learning curve"
                ],
                "cta": f"Next Thursday Episode {EPISODE_NUMBER + 1 if EPISODE_NUMBER > 0 else 2}: Midjourney SECRET parameter! Subscribe now!",
                "hashtags": ["#chatgpt", "#ai", "#technology", "#aitools", "#shorts", "#viral"],
                "description": f"Episode {EPISODE_NUMBER if EPISODE_NUMBER > 0 else 1} of Tool Teardown Tuesday: ChatGPT Vision's image analysis feature changes everything. Upload any image and get instant analysis. No setup required!",
                "visual_prompts": [
                    "ChatGPT interface showing image upload with analysis results appearing, glowing UI elements, professional tech aesthetic",
                    "Before/after split screen: complex diagram on left, ChatGPT detailed explanation on right, clear visual transformation",
                    "User uploading screenshot to ChatGPT and receiving instant structured analysis with highlighted key points",
                    "Multiple example images (photo, document, chart) with ChatGPT analysis overlays showing the versatility"
                ]
            }
            
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
print(f"   Series: {data.get('series', 'none')} - Episode {data.get('episode', 0)}")
print(f"   Bullets: {len(data['bullets'])} points")

if trending:
    print(f"\n🌐 Source: {trending.get('source', 'Unknown')}")
    if trending_topics:
        print(f"   Used trending topic from: {', '.join(trending_topics[:2])}...")