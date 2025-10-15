import os
import json
import re
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)

print("✅ Using Local Coqui TTS (offline)")

def clean_text_for_coqui(text):
    """Clean text to prevent Coqui TTS corruption"""
    text = text.replace('%', ' percent')
    text = text.replace('&', ' and ')
    text = text.replace('+', ' plus ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s\.\s', '. ', text)
    return text.strip()

def split_sentences(text, max_len=250):
    """Split long text into smaller parts for stable TTS"""
    parts = re.split(r'(?<=[.!?])\s+', text)
    result, current = [], ""
    for part in parts:
        if len(current) + len(part) < max_len:
            current += " " + part
        else:
            result.append(current.strip())
            current = part
    if current:
        result.append(current.strip())
    return result

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_tts_local(text):
    """Generate TTS using local Coqui TTS with chunking and trimming"""
    try:
        from TTS.api import TTS
        from pydub import AudioSegment
        from pydub.silence import split_on_silence
        print("🔊 Initializing Coqui TTS...")

        cleaned_text = clean_text_for_coqui(text)
        print(f"   Cleaned text preview: {cleaned_text[:80]}...")

        # ✅ Use a stable model (Glow-TTS is robust and consistent)
        tts = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False)

        out_path = os.path.join(TMP, "voice.mp3")

        # 🔹 Split text into smaller sentences
        segments = split_sentences(cleaned_text)
        print(f"🧩 Generating {len(segments)} segments...")

        combined_audio = AudioSegment.silent(duration=0)
        for i, seg in enumerate(segments):
            seg_path = os.path.join(TMP, f"tts_part_{i}.wav")
            print(f"   ▶️ Segment {i+1}/{len(segments)}: {seg[:60]}...")
            tts.tts_to_file(text=seg, file_path=seg_path)

            part = AudioSegment.from_file(seg_path)
            combined_audio += part + AudioSegment.silent(duration=150)

        # 🔹 Trim excessive silence
        print("✂️  Trimming silence...")
        chunks = split_on_silence(combined_audio, silence_thresh=-40, min_silence_len=600)
        if chunks:
            combined_audio = sum(chunks)

        combined_audio.export(out_path, format="mp3")
        file_size = os.path.getsize(out_path) / 1024

        if file_size < 10:
            raise Exception("Generated audio file too small, likely corrupted")

        print(f"✅ Coqui TTS saved to voice.mp3 ({file_size:.1f} KB)")
        return out_path

    except Exception as e:
        print(f"⚠️ Coqui TTS failed: {e}")
        return generate_tts_fallback(text)

def generate_tts_fallback(text):
    """Fallback TTS using gTTS"""
    try:
        print("🔄 Using gTTS fallback...")
        from gtts import gTTS

        tts = gTTS(text=text, lang='en', slow=False)
        out_path = os.path.join(TMP, "voice.mp3")
        tts.save(out_path)

        print("✅ gTTS fallback saved to voice.mp3")
        return out_path

    except Exception as e:
        print(f"⚠️ gTTS fallback failed: {e}")
        return generate_silent_audio_fallback(text)

def generate_silent_audio_fallback(text):
    """Generate silent audio as last resort fallback"""
    try:
        from moviepy import AudioClip
        import numpy as np

        words = len(text.split())
        duration = max(15, min(60, (words / 150) * 60))  # 15–60s range

        def make_silence(t):
            return np.zeros(2)

        silent_audio = AudioClip(make_silence, duration=duration)
        out_path = os.path.join(TMP, "voice.mp3")

        silent_audio.write_audiofile(out_path, fps=22050, bitrate='192k', logger=None)
        silent_audio.close()

        print(f"✅ Silent audio fallback created ({duration:.1f}s)")
        return out_path

    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        raise Exception("All TTS generation methods failed")

# Main execution
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

# 🧩 Save each section separately for precise timing
from TTS.api import TTS
from pydub import AudioSegment

tts = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False)
section_paths = []

sections = [("hook", hook)] + [(f"bullet_{i}", b) for i, b in enumerate(bullets)] + [("cta", cta)]
for name, text in sections:
    if not text.strip():
        continue
    clean = clean_text_for_coqui(text)
    out_path = os.path.join(TMP, f"{name}.mp3")
    print(f"🎧 Generating section: {name}")
    tts.tts_to_file(text=clean, file_path=out_path)
    section_paths.append(out_path)

# Combine them (with short pauses) to make the main voice.mp3
combined_audio = AudioSegment.silent(duration=0)
for path in section_paths:
    part = AudioSegment.from_file(path)
    combined_audio += part + AudioSegment.silent(duration=150)
combined_audio.export(os.path.join(TMP, "voice.mp3"), format="mp3")
print(f"✅ Combined TTS saved to voice.mp3")

print(f"🎙️  Generating voice for text ({len(spoken)} chars)")
print(f"   Preview: {spoken[:100]}...")

try:
    # Generate audio
    audio_file_path = generate_tts_local(spoken)

    # Verify audio duration
    from moviepy import AudioFileClip

    audio_check = AudioFileClip(audio_file_path)
    actual_duration = audio_check.duration
    audio_check.close()

    file_size = os.path.getsize(audio_file_path) / 1024
    print(f"🎵 Actual audio duration: {actual_duration:.2f} seconds")

    if actual_duration > 120:
        print(f"⚠️ Audio duration too long ({actual_duration:.1f}s), regenerating with gTTS...")
        audio_file_path = generate_tts_fallback(spoken)
        audio_check = AudioFileClip(audio_file_path)
        actual_duration = audio_check.duration
        audio_check.close()
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
        "tts_provider": "coqui_local",
    }

    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete with Local Coqui TTS")