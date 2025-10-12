# .github/scripts/generate_tts.py
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_VOICE_ID")

# Verify API credentials
if not ELEVEN_KEY:
    print("❌ ELEVENLABS_API_KEY not found")
    raise SystemExit(1)

if not VOICE_ID:
    print("❌ ELEVEN_VOICE_ID not found")
    raise SystemExit(1)

print("✅ ElevenLabs credentials found")

# Load script
script_path = os.path.join(TMP, "script.json")
if not os.path.exists(script_path):
    print(f"❌ Script file not found: {script_path}")
    raise SystemExit(1)

with open(script_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Construct spoken text
hook = data.get("hook", "")
bullets = " ".join(data.get("bullets", []))
cta = data.get("cta", "")
spoken = f"{hook} {bullets} {cta}"

print(f"🎙️  Generating voice for text ({len(spoken)} chars)")
print(f"   Preview: {spoken[:100]}...")

# Call ElevenLabs API
url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
headers = {
    "xi-api-key": ELEVEN_KEY,
    "Content-Type": "application/json"
}
payload = {
    "text": spoken,
    "model_id": "eleven_multilingual_v2",  # Updated to v2 for better quality
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True
    }
}

try:
    print("📡 Calling ElevenLabs API...")
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if r.status_code != 200:
        print(f"❌ TTS error {r.status_code}: {r.text}")
        raise SystemExit(1)
    
    # Save audio file
    out = os.path.join(TMP, "voice.mp3")
    with open(out, "wb") as f:
        f.write(r.content)
    
    file_size = len(r.content) / 1024  # KB
    print(f"✅ Saved voice to {out} ({file_size:.1f} KB)")

except requests.exceptions.Timeout:
    print("❌ Request timed out. ElevenLabs API might be slow.")
    raise SystemExit(1)
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
    raise SystemExit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    raise SystemExit(1)