# .github/scripts/generate_trending_and_script.py
import os, json, random, requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# 0️⃣ Set temporary directory
TMP_DIR = "/github/workspace/tmp"

# 1️⃣ Load Gemini API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ Missing GEMINI_API_KEY in environment variables. Get one at https://aistudio.google.com/app/apikey")

genai.configure(api_key=api_key)

# 2️⃣ Scrape trending Shorts titles
headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.youtube.com/feed/trending?bp=EgZzcm9ydHM%3D"
titles = []

try:
    r = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    titles = [meta["content"] for meta in soup.find_all("meta", itemprop="name") if meta.get("content")]
    titles = [t for t in titles if len(t.split()) > 2]
except Exception as e:
    print("⚠️ Error fetching trending titles:", e)

if not titles:
    titles = [
        "Amazing AI tools you need to know",
        "Weird psychology fact you didn’t know",
        "How billionaires think differently",
        "Mind-blowing science facts about space",
    ]

# 3️⃣ Filter by niche keywords
keywords = ["AI", "psychology", "motivation", "facts", "technology", "business", "science", "success", "money"]
filtered = [t for t in titles if any(k.lower() in t.lower() for k in keywords)]
topic = random.choice(filtered if filtered else titles).strip()

# 4️⃣ Prompt Gemini
prompt = f"""
You are a YouTube Shorts scriptwriter.
Generate a 40–70 word script as JSON with keys:
- title (<=60 chars)
- hook (1 line)
- bullets (2–3 short lines)
- cta (1 line)
Use a viral, curiosity-driven tone.
Topic: '{topic}'
Return valid JSON only.
"""

# ✅ Use latest working model
MODEL = "models/gemini-2.5-flash"
print(f"✅ Using model: {MODEL}")
model = genai.GenerativeModel(model_name=MODEL)

# 5️⃣ Generate response
response = model.generate_content(prompt)
content = (response.text or "").strip()

# 6️⃣ Parse Gemini response safely
if not content:
    print("⚠️ Gemini returned an empty response. Exiting...")
    exit()

try:
    data = json.loads(content)
except json.JSONDecodeError:
    print("⚠️ Gemini returned non-JSON. Attempting to fix...")
    print("🔍 Raw output:", repr(content))
    re_prompt = f"""
    Convert the following text into valid JSON only.
    It must have keys: title, hook, bullets, cta.
    No explanations, no markdown, no code blocks.
    Input:
    {content}
    """
    fixed = model.generate_content(re_prompt)
    fixed_text = (fixed.text or "").strip()

    if not fixed_text:
        print("❌ Gemini returned nothing when trying to fix JSON.")
        exit()

    try:
        data = json.loads(fixed_text)
    except json.JSONDecodeError:
        print("❌ Still invalid JSON. Here’s what Gemini returned:")
        print(fixed_text)
        exit()

# 7️⃣ Save results
os.makedirs(TMP_DIR, exist_ok=True)
with open(os.path.join(TMP_DIR, "script.json"), "w", encoding="utf-8") as f:
    json.dump({"topic": topic, **data}, f, ensure_ascii=False, indent=2)

print("✅ Topic:", topic)
print(f"✅ Saved script to {os.path.join(TMP_DIR, 'script.json')}")
