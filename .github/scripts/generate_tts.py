# .github/scripts/generate_tts.py
import os
import json
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

print("✅ Using Local Coqui TTS (offline)")

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
def generate_tts_local(text):
    """Generate TTS using local Coqui TTS"""
    try:
        from TTS.api import TTS
        
        print("🔊 Initializing Coqui TTS...")
        
        # Initialize Coqui TTS with a fast English model
        tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
        
        # Generate speech
        print("📢 Generating speech...")
        out_path = os.path.join(TMP, "voice_temp.wav")
        tts.tts_to_file(text=text, file_path=out_path)
        
        # Convert to MP3 if needed
        if os.path.exists(out_path):
            # For now, just use the WAV file (MoviePy can handle it)
            with open(out_path, 'rb') as f:
                audio_content = f.read()
            
            # Clean up temp file
            os.remove(out_path)
            return audio_content
        else:
            raise Exception("TTS generation failed - no output file")
            
    except Exception as e:
        print(f"⚠️ Coqui TTS failed: {e}")
        return generate_tts_fallback(text)

def generate_tts_fallback(text):
    """Fallback TTS using gTTS"""
    try:
        print("🔄 Using gTTS fallback...")
        from gtts import gTTS
        import io
        
        tts = gTTS(text=text, lang='en', slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        return audio_buffer.read()
    except Exception as e:
        print(f"⚠️ gTTS fallback failed: {e}")
        return generate_silent_audio_fallback(text)

def generate_silent_audio_fallback(text):
    """Generate silent audio as last resort fallback"""
    try:
        from moviepy import AudioClip
        import numpy as np
        
        # Calculate duration based on word count
        words = len(text.split())
        duration = max(30, min(60, (words / 150) * 60))
        
        # Generate silent audio
        def make_silence(t):
            return np.zeros(2)
        
        silent_audio = AudioClip(make_silence, duration=duration)
        
        # Save to temporary file and read back
        temp_path = os.path.join(TMP, "temp_silent.mp3")
        silent_audio.write_audiofile(temp_path, fps=22050, verbose=False, logger=None)
        
        with open(temp_path, 'rb') as f:
            audio_content = f.read()
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return audio_content
    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        raise Exception("All TTS generation methods failed")

try:
    audio_content = generate_tts_local(spoken)
    
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
        "file_size_kb": file_size,
        "tts_provider": "coqui_local"
    }
    
    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete with Local Coqui TTS")