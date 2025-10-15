# .github/scripts/generate_trending_and_script.py
import os
import json
import re
import hashlib
from datetime import datetime
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
# Store persistent history in the repo, not temp runner
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "content_history.json")


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
✅ Be SPECIFIC - name actual tools, apps, techniques, not vague "this tool" or "this method"
✅ CTA must be casual and engaging - NOT salesy or course-pitchy
✅ Add 5-10 relevant hashtags for maximum discoverability
✅ Focus on: AI, Tech, Psychology, Money, Health, Productivity, Science

PROVEN VIRAL FORMULAS:
- "3 Things Nobody Tells You About..."
- "Why [Surprising Fact] Will Change Everything"
- "The Secret [Group] Don't Want You to Know"
- "I Tried [Thing] For 30 Days, Here's What Happened"

CTA GUIDELINES (VERY IMPORTANT):
❌ BAD CTAs: "Comment which one...", "Subscribe for more", "Click the link", "Take my course"
✅ GOOD CTAs: "Try this yourself and tag me!", "Which one shocked you?", "Save this before it's gone", "Share with someone who needs this", "Follow for daily tips like this"
- Keep it natural and conversational
- Make it feel like talking to a friend
- Encourage ACTION not just engagement metrics
- No selling, no courses, no links

SPECIFICITY RULES:
❌ VAGUE: "This AI tool can help you"
✅ SPECIFIC: "ChatGPT's Code Interpreter can help you"

❌ VAGUE: "A simple trick improves focus"
✅ SPECIFIC: "The Pomodoro Technique improves focus by 40%"

❌ VAGUE: "Experts recommend this method"
✅ SPECIFIC: "Stanford researchers found this method doubles retention"

OUTPUT FORMAT (JSON ONLY):
{{
  "title": "Catchy title with specific details (under 100 chars)",
  "topic": "one_word_category",
  "hook": "Question or shocking statement with specifics (under 12 words)",
  "bullets": [
    "First key point - BE SPECIFIC with names/numbers/details",
    "Second point - SPECIFIC fact or statistic with source",
    "Third point - SPECIFIC actionable insight with exact method"
  ],
  "cta": "Casual, friendly call-to-action - NO SALESY LANGUAGE",
  "hashtags": ["#shorts", "#viral", "#trending", "#category", "#fyp"],
  "description": "2-3 sentence description with specific details for YouTube",
  "visual_prompts": [
    "Specific, detailed image prompt for hook scene with exact elements",
    "Specific, detailed image prompt for bullet 1 showing exact concept",
    "Specific, detailed image prompt for bullet 2 with clear visual",
    "Specific, detailed image prompt for bullet 3 demonstrating the action"
  ]
}}

REMEMBER: Be specific! Name actual tools, techniques, studies, numbers!
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
        "title": "ChatGPT Just Got This Insane Update",
        "topic": "technology",
        "hook": "ChatGPT's new voice mode is actually scary good",
        "bullets": [
            "It now remembers your entire conversation history across sessions",
            "The Advanced Voice Mode sounds 99% human with real emotions",
            "You can interrupt it mid-sentence like a real conversation"
        ],
        "cta": "Try it yourself and let me know what you think!",
        "hashtags": ["#chatgpt", "#ai", "#openai", "#technology", "#shorts", "#viral"],
        "description": "ChatGPT's latest update brings conversation memory, incredibly realistic voice, and natural interruptions. The AI assistant just got way more human-like.",
        "visual_prompts": [
            "Person amazed looking at smartphone with ChatGPT interface, dramatic lighting, shocked expression, modern tech aesthetic",
            "Visual representation of digital memory bank, glowing neural network storing conversations, futuristic blue and purple tones",
            "Sound wave visualization showing human-like voice patterns, emotional waveforms, vibrant colors flowing smoothly",
            "Two people having natural conversation, one is holographic AI assistant, seamless interaction, cutting-edge technology"
        ]
    }

os.makedirs(TMP, exist_ok=True)
script_path = os.path.join(TMP, "script.json")

with open(script_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Saved script to {script_path}")
print(f"📊 Total topics in history: {len(history['topics'])}")