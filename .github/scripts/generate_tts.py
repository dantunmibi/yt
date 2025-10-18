import os
import json
import re
from tenacity import retry, stop_after_attempt, wait_exponential
from TTS.api import TTS
from pydub import AudioSegment
from pydub.silence import split_on_silence
# Removed moviepy imports, relying on pydub
import numpy as np

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
FULL_AUDIO_PATH = os.path.join(TMP, "voice.mp3")

print("✅ Using Local Coqui TTS (offline)")

# --- Utility Functions ---

def clean_text_for_coqui(text):
    """Clean text to prevent Coqui TTS corruption"""
    text = text.replace('%', ' percent')
    text = text.replace("AI", "A. I.")
    text = text.replace('&', ' and ')
    text = text.replace('+', ' plus ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s\.\s', '. ', text)

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    return text.strip()

def generate_tts_fallback(text, out_path):
    """Fallback TTS using gTTS"""
    try:
        print("🔄 Using gTTS fallback...")
        from gtts import gTTS

        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(out_path)

        print(f"✅ gTTS fallback saved to {out_path}")
        return out_path

    except Exception as e:
        print(f"⚠️ gTTS fallback failed: {e}")
        return generate_silent_audio_fallback(text, out_path)

def generate_silent_audio_fallback(text, out_path):
    """Generate silent audio as last resort fallback using pydub"""
    try:
        from pydub import AudioSegment
        
        words = len(text.split())
        # Calculate duration in milliseconds (15s min, 60s max)
        duration_ms = max(15000, min(60000, (words / 150) * 60000))
        duration_s = duration_ms / 1000.0

        silent_audio = AudioSegment.silent(duration=duration_ms, frame_rate=22050)
        silent_audio.export(out_path, format="mp3")

        print(f"✅ Silent audio fallback created ({duration_s:.1f}s)")
        return out_path
    
    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        raise Exception("All TTS generation methods failed")


# --- Core Execution ---

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
spoken = ". ".join([p.strip() for p in spoken_parts if p.strip()]) # Rebuild spoken text safely

print(f"🎙️ Generating voice for text ({len(spoken)} chars)")
print(f"   Preview: {spoken[:100]}...")

# --- Sectional TTS Generation (Primary Strategy) ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_sectional_tts():
    """Generates individual TTS files for precise timing and combines them."""
    section_paths = []
    
    try:
        print("🔊 Initializing Coqui TTS for sectional generation...")
        # Initialize Coqui TTS model once for all sections
        tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False)

        sections = [("hook", hook)] + [(f"bullet_{i}", b) for i, b in enumerate(bullets)] + [("cta", cta)]
        
        for name, text in sections:
            if not text.strip():
                continue
            
            clean = clean_text_for_coqui(text)
            out_path = os.path.join(TMP, f"{name}.mp3")
            print(f"🎧 Generating section: {name} (Text: {clean[:40]}...)")
            
            # Coqui TTS section generation
            tts.tts_to_file(text=clean, file_path=out_path)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                section_paths.append(out_path)
            else:
                # If section generation fails (e.g., specific punctuation issue), raise for retry
                raise Exception(f"Coqui section generation failed for {name}")

    except Exception as e:
        # If Coqui fails entirely, fall back to gTTS for the whole script
        print(f"⚠️ Sectional Coqui TTS failed entirely: {e}")
        print("🔄 Falling back to gTTS for full audio generation...")
        
        # If any section generation fails, we fall back to a single gTTS file.
        fallback_path = generate_tts_fallback(spoken, FULL_AUDIO_PATH)
        
        if os.path.getsize(fallback_path) < 1000:
             raise Exception("Fallback audio too small.")
             
        # Create dummy empty files for sections to prevent later FileNotFoundError in video script
        for name, _ in sections:
            # We don't need to create empty files if the video script is smart, but doing it safely
            dummy_path = os.path.join(TMP, f"{name}.mp3")
            if not os.path.exists(dummy_path):
                open(dummy_path, 'w').close()
            
        print("⚠️ Sectional audio lost, video timing will use estimates from full audio.")
        return [fallback_path] # Return list containing only the full audio path


    # Combine them (with short pauses) to make the main voice.mp3
    combined_audio = AudioSegment.silent(duration=0)
    for path in section_paths:
        part = AudioSegment.from_file(path)
        # Add 150ms pause between sections
        combined_audio += part + AudioSegment.silent(duration=150)
        
    combined_audio.export(FULL_AUDIO_PATH, format="mp3")
    print(f"✅ Combined TTS saved to {FULL_AUDIO_PATH}")
    
    return section_paths

try:
    # 1. Execute the generation process
    section_paths = generate_sectional_tts()

    # 2. Verify the final combined audio (or the single fallback file) using pydub
    final_audio_path = FULL_AUDIO_PATH
    
    audio_check = AudioSegment.from_file(final_audio_path)
    actual_duration = audio_check.duration_seconds # Duration in seconds
    
    file_size = os.path.getsize(final_audio_path) / 1024
    print(f"🎵 Actual audio duration: {actual_duration:.2f} seconds")

    if actual_duration > 120:
        print(f"⚠️ Audio duration too long ({actual_duration:.1f}s), forcing gTTS fallback...")
        generate_tts_fallback(spoken, FULL_AUDIO_PATH) # Overwrite with gTTS
        
        audio_check = AudioSegment.from_file(FULL_AUDIO_PATH)
        actual_duration = audio_check.duration_seconds
        print(f"🎵 Fixed audio duration: {actual_duration:.2f} seconds")

    words = len(spoken.split())
    estimated_duration = (words / 150) * 60

    print(f"📊 Text stats: {words} words, estimated: {estimated_duration:.1f}s, actual: {actual_duration:.1f}s")

    metadata = {
        "text": spoken,
        "words": words,
        "estimated_duration": estimated_duration,
        "actual_duration": actual_duration,
        "file_size_kb": file_size,
        # Determine final provider
        "tts_provider": "coqui_sectional" if len(section_paths) > 1 else "gtts_fallback_full",
    }

    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete")