# .github/scripts/generate_tts.py
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

script_path = os.path.join(TMP, "script.json")
if not os.path.exists(script_path):
    print(f"❌ Script file not found: {script_path}")
    raise SystemExit(1)

with open(script_path, "r", encoding="utf-8") as f:
    data = json.load(f)

hook = data.get("hook", "")
bullets = data.get("bullets", [])
cta = data.get("cta", "")

spoken_parts = [hook] + bullets + [cta]
spoken = ". ".join(spoken_parts)

print(f"🎙️  Generating local Coqui TTS ({len(spoken)} chars)")
print(f"   Preview: {spoken[:100]}...")

out_path = os.path.join(TMP, "voice.mp3")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_tts(text):
    print("🧠 Loading local Coqui TTS model...")
    try:
        from TTS.api import TTS
        # You can replace this model with another one if you prefer a different voice
        tts = TTS(model_name="tts_models/en/vctk/vits")
        tts.tts_to_file(text=text, file_path=out_path)
        with open(out_path, "rb") as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Local TTS failed: {e}")

try:
    audio_content = generate_tts(spoken)
    Path(out_path).write_bytes(audio_content)

    file_size = len(audio_content) / 1024
    print(f"✅ Saved voice to {out_path} ({file_size:.1f} KB)")

    if file_size < 10:
        print("⚠️ Audio file too small — may be corrupted")
        raise Exception("Generated audio file too small")

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

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete")
