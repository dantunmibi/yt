# .github/scripts/generate_tts.py
# .github/scripts/generate_tts.py
import os
import json
import re
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

def clean_text_for_coqui(text):
    """Clean text to prevent Coqui TTS corruption"""
    # Replace problematic symbols
    text = text.replace('%', ' percent')
    text = text.replace('&', ' and ')
    text = text.replace('+', ' plus ')
    
    # Fix sentence segmentation
    text = re.sub(r'\s+', ' ', text)  # Remove extra spaces
    text = re.sub(r'\s\.\s', '. ', text)  # Fix space around periods
    
    return text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def generate_tts_local(text):
    """Generate TTS using local Coqui TTS"""
    try:
        from TTS.api import TTS
        
        print("🔊 Initializing Coqui TTS...")
        
        # Clean text before processing
        cleaned_text = clean_text_for_coqui(text)
        print(f"   Cleaned text preview: {cleaned_text[:80]}...")
        
        # Initialize Coqui TTS with a fast English model
        tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
        
        # Generate speech directly to MP3
        print("📢 Generating speech...")
        out_path = os.path.join(TMP, "voice.mp3")
        
        # Generate directly to MP3
        tts.tts_to_file(text=cleaned_text, file_path=out_path)
        
        # Verify the file was created properly
        if not os.path.exists(out_path):
            raise Exception("TTS output file was not created")
        
        # Get file size and verify it's reasonable
        file_size = os.path.getsize(out_path) / 1024
        if file_size < 10:
            raise Exception("Generated audio file is too small, likely corrupted")
        
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
        
        # Use original duration calculation
        words = len(text.split())
        duration = max(15, min(60, (words / 150) * 60))  # 15-60 second range
        
        # Generate silent audio
        def make_silence(t):
            return np.zeros(2)
        
        silent_audio = AudioClip(make_silence, duration=duration)
        out_path = os.path.join(TMP, "voice.mp3")
        
        # Write directly as MP3
        silent_audio.write_audiofile(
            out_path, 
            fps=22050, 
            bitrate='192k',
            logger=None
        )
        silent_audio.close()
        
        print(f"✅ Silent audio fallback created ({duration:.1f}s)")
        return out_path
        
    except Exception as e:
        print(f"❌ All TTS methods failed: {e}")
        raise Exception("All TTS generation methods failed")

try:
    # Generate the audio file
    audio_file_path = generate_tts_local(spoken)
    
    # Verify audio duration using moviepy
    from moviepy import AudioFileClip
    audio_check = AudioFileClip(audio_file_path)
    actual_duration = audio_check.duration
    audio_check.close()
    
    file_size = os.path.getsize(audio_file_path) / 1024
    print(f"🎵 Actual audio duration: {actual_duration:.2f} seconds")
    
    # CRITICAL: Validate audio duration is reasonable
    if actual_duration > 120:  # More than 2 minutes is definitely wrong
        print(f"❌ Audio duration too long ({actual_duration:.1f}s), regenerating with gTTS...")
        audio_file_path = generate_tts_fallback(spoken)
        
        # Re-check duration
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
        "tts_provider": "coqui_local"
    }
    
    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except Exception as e:
    print(f"❌ TTS generation failed: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete with Local Coqui TTS")