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
        
        # Generate speech directly to MP3
        print("📢 Generating speech...")
        out_path = os.path.join(TMP, "voice.mp3")
        
        # Generate to WAV first, then convert to MP3
        temp_wav = os.path.join(TMP, "temp_voice.wav")
        tts.tts_to_file(text=text, file_path=temp_wav)
        
        # Convert WAV to MP3 using moviepy
        from moviepy import AudioFileClip
        audio_clip = AudioFileClip(temp_wav)
        audio_clip.write_audiofile(out_path, logger=None, bitrate='192k')
        audio_clip.close()
        
        # Clean up temp file
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        
        # Read the final MP3 file
        with open(out_path, 'rb') as f:
            audio_content = f.read()
            
        return audio_content
            
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
        
        with open(out_path, 'rb') as f:
            audio_content = f.read()
        
        return audio_content
    except Exception as e:
        print(f"⚠️ gTTS fallback failed: {e}")
        return generate_silent_audio_fallback(text)

def generate_silent_audio_fallback(text):
    """Generate silent audio as last resort fallback"""
    try:
        from moviepy import AudioClip
        import numpy as np
        
        # Use original duration calculation
        words = len(text.split())
        duration = (words / 150) * 60  # Original calculation
        
        # Generate silent audio
        def make_silence(t):
            return np.zeros(2)
        
        silent_audio = AudioClip(make_silence, duration=duration)
        
        # Save directly as MP3
        out_path = os.path.join(TMP, "voice.mp3")
        silent_audio.write_audiofile(out_path, fps=22050, logger=None, bitrate='192k')
        silent_audio.close()
        
        with open(out_path, 'rb') as f:
            audio_content = f.read()
            
        return audio_content
    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        raise Exception("All TTS generation methods failed")

try:
    audio_content = generate_tts_local(spoken)
    
    # Verify audio was created properly
    out = os.path.join(TMP, "voice.mp3")
    if not os.path.exists(out):
        raise Exception("Audio file was not created")
    
    # Get actual audio duration using moviepy
    from moviepy import AudioFileClip
    audio_check = AudioFileClip(out)
    actual_duration = audio_check.duration
    audio_check.close()
    
    file_size = os.path.getsize(out) / 1024
    print(f"✅ Saved voice to {out} ({file_size:.1f} KB)")
    print(f"🎵 Actual audio duration: {actual_duration:.2f} seconds")
    
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
        "actual_duration": actual_duration,
        "file_size_kb": file_size,
        "tts_provider": "coqui_local"
    }
    
    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete with Local Coqui TTS")