# .github/scripts/generate_tts.py
import os, json, requests
from dotenv import load_dotenv

load_dotenv()
TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_VOICE_ID")  # replace if needed

with open(os.path.join(TMP_DIR, "script.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

hook = data.get("hook","")
bullets = " ".join(data.get("bullets", []))
cta = data.get("cta","")
spoken = f"{hook} {bullets} {cta}"

url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
payload = {"text": spoken, "model": "eleven_multilingual_v1",
           "voice_settings":{"stability":0.4,"similarity_boost":0.75}}

r = requests.post(url, headers=headers, json=payload, timeout=60)
if r.status_code != 200:
    print("TTS error", r.status_code, r.text)
    raise SystemExit(1)

out = os.path.join(TMP_DIR, "voice.mp3")
with open(out, "wb") as f: f.write(r.content)
print("Saved voice to", out)
