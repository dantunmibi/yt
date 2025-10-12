# .github/scripts/generate_tts.py
import os
import json
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_VOICE_ID")

if not ELEVEN_KEY:
    print("❌ ELEVENLABS_API_KEY not found")
    raise SystemExit(1)

if not VOICE_ID:
    print("❌ ELEVEN_VOICE_ID not found")
    raise SystemExit(1)

print("✅ ElevenLabs credentials found")

script_path = os.path.join(TMP, "script.json")
if not os.path.exists(script_path):
    print(f"❌ Script file not found: {script_path}")
    raise SystemExit(1)

with open(script_path, "r", encoding="utf-8") as f:
    data = json.load(f)

hook = data.get("hook", "")
bullets = data.get("bullets", [])
cta = data.get("cta", "")

spoken_parts = [hook]
for bullet in bullets:
    spoken_parts.append(bullet)
spoken_parts.append(cta)

spoken = ". ".join(spoken_parts)

print(f"🎙️  Generating voice for text ({len(spoken)} chars)")
print(f"   Preview: {spoken[:100]}...")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_tts(text, voice_id, api_key):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    voice_settings = [
        {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        },
        {
            "stability": 0.6,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True
        }
    ]
    
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": voice_settings[0]
    }
    
    print("📡 Calling ElevenLabs API...")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code != 200:
        error_msg = response.text
        print(f"⚠️ Primary settings failed ({response.status_code}), trying alternative...")
        
        payload["voice_settings"] = voice_settings[1]
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ TTS error {response.status_code}: {response.text}")
            raise Exception(f"TTS generation failed: {response.text}")
    
    return response.content

try:
    audio_content = generate_tts(spoken, VOICE_ID, ELEVEN_KEY)
    
    out = os.path.join(TMP, "voice.mp3")
    with open(out, "wb") as f:
        f.write(audio_content)
    
    file_size = len(audio_content) / 1024
    print(f"✅ Saved voice to {out} ({file_size:.1f} KB)")
    
    if file_size < 10:
        print("⚠️ Audio file seems too small, may be corrupted")
        raise Exception("Generated audio file is too small")
    
    words = len(spoken.split())
    estimated_duration = (words / 150) * 60
    print(f"📊 Estimated duration: {estimated_duration:.1f}s ({words} words)")
    
    metadata = {
        "text": spoken,
        "words": words,
        "estimated_duration": estimated_duration,
        "file_size_kb": file_size
    }
    
    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except requests.exceptions.Timeout:
    print("❌ Request timed out. ElevenLabs API might be slow.")
    raise SystemExit(1)
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
    raise SystemExit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete")