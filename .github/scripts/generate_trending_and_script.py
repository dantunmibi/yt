# .github/scripts/generate_trending_and_script.py
import os
import json
import re
import google.generativeai as genai

# Set up paths
TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# List available models and use the best one
try:
    models = genai.list_models()
    # Prefer gemini-2.0-flash-exp or gemini-1.5-flash
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
    print("Using default model: gemini-1.5-flash")
    model = genai.GenerativeModel("models/gemini-1.5-flash")

# Generate trending topic and script
prompt = """You are a YouTube Shorts content creator. Generate a trending, engaging topic and a short script for a 30-60 second video.

Requirements:
- Topic should be interesting, viral-worthy, and relevant to current trends
- Include a strong hook (first 3 seconds)
- 3 key bullet points (main content)
- Strong call-to-action at the end
- Keep it concise and punchy

Return ONLY a JSON object with this exact structure:
{
  "title": "Catchy title under 100 characters",
  "topic": "One word topic category (e.g., tech, psychology, business)",
  "hook": "Attention-grabbing opening line",
  "bullets": [
    "First key point",
    "Second key point", 
    "Third key point"
  ],
  "cta": "Call to action"
}

Make it engaging and trendy!"""

try:
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    print(f"🔍 Raw output: {raw_text!r}")
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
        print("⚠️ Gemini returned JSON in code block. Extracting...")
    else:
        # Try to find JSON directly
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
            print("⚠️ Gemini returned non-JSON. Attempting to fix...")
        else:
            raise ValueError("No JSON found in response")
    
    data = json.loads(json_text)
    
    # Validate required fields
    required_fields = ["title", "topic", "hook", "bullets", "cta"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    if not isinstance(data["bullets"], list) or len(data["bullets"]) < 3:
        raise ValueError("bullets must be a list with at least 3 items")
    
    print("✅ Script generated successfully")
    print(f"   Title: {data['title']}")
    print(f"   Topic: {data['topic']}")
    
except Exception as e:
    print(f"❌ Error generating script: {e}")
    print("Using fallback script...")
    data = {
        "title": "AI is Changing Everything",
        "topic": "technology",
        "hook": "Did you know AI can now do THIS?",
        "bullets": [
            "AI is revolutionizing how we work",
            "It's making tasks 10x faster",
            "The future is already here"
        ],
        "cta": "Follow for more AI insights!"
    }

# Create tmp directory and save script
os.makedirs(TMP, exist_ok=True)
script_path = os.path.join(TMP, "script.json")

with open(script_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Saved script to {script_path}")