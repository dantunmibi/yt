# .github/scripts/generate_trending_and_script.py
import os
import json
import re
import hashlib
from datetime import datetime
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
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
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {'topics': [], 'hashes': []}
    return {'topics': [], 'hashes': []}

def save_to_history(topic, script_hash):
    history = load_history()
    history['topics'].append({
        'topic': topic,
        'hash': script_hash,
        'date': datetime.now().isoformat()
    })
    history['topics'] = history['topics'][-50:]
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def get_content_hash(data):
    content = json.dumps(data, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()

def load_trending():
    trending_file = os.path.join(TMP, "trending.json")
    if os.path.exists(trending_file):
        with open(trending_file, 'r') as f:
            return json.load(f)
    return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_script_with_retry(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()

history = load_history()
trending = load_trending()

previous_topics = [t['topic'] for t in history['topics'][-10:]]
trending_info = ""

if trending and trending.get('topics'):
    trending_info = f"\nCURRENT TRENDING TOPICS:\n" + "\n".join(f"- {t}" for t in trending['topics'][:5])

prompt = f"""You are a viral YouTube Shorts content creator with millions of views.

CONTEXT:
- Current date: {datetime.now().strftime('%Y-%m-%d')}
- Previously covered topics (DO NOT REPEAT): {', '.join(previous_topics) if previous_topics else 'None'}
{trending_info}

TASK: Generate a trending, viral-worthy topic and script for a 30-60 second YouTube Short.

REQUIREMENTS:
✅ Topic must be DIFFERENT from previous topics
✅ Hook must create a curiosity gap (make viewers NEED to watch)
✅ Include specific numbers, statistics, or surprising facts
✅ 3 concise, punchy bullet points (each 10-15 words max)
✅ Strong CTA that encourages engagement (like/subscribe/comment with specific action)
✅ Add 5-10 relevant hashtags for maximum discoverability
✅ Focus on: AI, Tech, Psychology, Money, Health, Productivity, Science

PROVEN VIRAL FORMULAS:
- "3 Things Nobody Tells You About..."
- "Why [Surprising Fact] Will Change Everything"
- "The Secret [Group] Don't Want You to Know"
- "I Tried [Thing] For 30 Days, Here's What Happened"

OUTPUT FORMAT (JSON ONLY):
{{
  "title": "Catchy title with number or hook (under 100 chars)",
  "topic": "one_word_category",
  "hook": "Question or shocking statement (under 12 words)",
  "bullets": [
    "First key point with specific detail or number",
    "Second point with surprising fact or statistic",
    "Third point with actionable insight or revelation"
  ],
  "cta": "Specific action request (e.g., 'Comment which one surprised you most!')",
  "hashtags": ["#shorts", "#viral", "#trending", "#category", "#fyp"],
  "description": "2-3 sentence description for YouTube (include key points)",
  "visual_prompts": [
    "Detailed image prompt for hook scene",
    "Detailed image prompt for bullet 1",
    "Detailed image prompt for bullet 2",
    "Detailed image prompt for bullet 3"
  ]
}}

Make it IRRESISTIBLE to click and watch!"""

try:
    print("🎬 Generating viral script...")
    raw_text = generate_script_with_retry(prompt)
    print(f"🔍 Raw output length: {len(raw_text)} chars")
    
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
    
    required_fields = ["title", "topic", "hook", "bullets", "cta"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    if "hashtags" not in data:
        data["hashtags"] = ["#shorts", "#viral", "#trending", "#fyp"]
    
    if "description" not in data:
        data["description"] = f"{data['title']} - {data['hook']}"
    
    if "visual_prompts" not in data or len(data["visual_prompts"]) < 4:
        data["visual_prompts"] = [
            f"Eye-catching opening image for: {data['hook']}, cinematic, dramatic lighting",
            f"Visual representation of: {data['bullets'][0]}, photorealistic, vibrant",
            f"Visual representation of: {data['bullets'][1]}, photorealistic, vibrant",
            f"Visual representation of: {data['bullets'][2]}, photorealistic, vibrant"
        ]
    
    if not isinstance(data["bullets"], list) or len(data["bullets"]) < 3:
        raise ValueError("bullets must be a list with at least 3 items")
    
    content_hash = get_content_hash(data)
    if content_hash in [t.get('hash') for t in history['topics']]:
        print("⚠️ Generated duplicate content, regenerating...")
        raise ValueError("Duplicate content detected")
    
    save_to_history(data['topic'], content_hash)
    
    print("✅ Script generated successfully")
    print(f"   Title: {data['title']}")
    print(f"   Topic: {data['topic']}")
    print(f"   Hashtags: {', '.join(data['hashtags'][:5])}")
    
except Exception as e:
    print(f"❌ Error generating script: {e}")
    print("Using fallback script...")
    data = {
        "title": "3 AI Tools That Will Blow Your Mind in 2025",
        "topic": "technology",
        "hook": "AI just changed everything. Here's what you missed.",
        "bullets": [
            "New AI can read your mind with 85% accuracy",
            "This tool automates 10 hours of work in 10 minutes",
            "Anyone can now create professional videos without skills"
        ],
        "cta": "Comment which one you'll try first!",
        "hashtags": ["#ai", "#shorts", "#technology", "#viral", "#fyp", "#trending"],
        "description": "Discover 3 revolutionary AI tools changing how we work and create in 2025. These innovations are making advanced technology accessible to everyone.",
        "visual_prompts": [
            "Futuristic AI brain interface, glowing neural connections, cinematic",
            "Person amazed by holographic brain scan, futuristic lab setting",
            "Automated workflow visualization, digital efficiency, vibrant graphics",
            "Creator making professional video content, modern studio, dynamic"
        ]
    }

os.makedirs(TMP, exist_ok=True)
script_path = os.path.join(TMP, "script.json")

with open(script_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Saved script to {script_path}")
print(f"📊 Total topics in history: {len(history['topics'])}")