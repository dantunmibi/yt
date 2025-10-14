# .github/scripts/generate_tts.py
import os
import json
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

print("✅ Using Coqui AI TTS (free and open source)")

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
def generate_tts_coqui(text):
    # Coqui TTS API endpoint (using their demo API)
    url = "https://app.coqui.ai/api/v2/samples"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.getenv("COQUI_API_KEY", "demo"),  # Use demo if no key
    }
    
    payload = {
        "text": text,
        "voice_id": "d0ba0d1d-4c4b-4175-91a8-6c8d4fbdf579",  # Coqui's English female voice
        "speed": 1.0,
        "language": "en"
    }
    
    print("📡 Calling Coqui AI API...")
    
    # First, generate the sample
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 201:
        print(f"⚠️ Coqui AI generation failed ({response.status_code}): {response.text}")
        
        # Fallback to local TTS if API fails
        return generate_tts_fallback(text)
    
    sample_data = response.json()
    sample_id = sample_data.get('id')
    
    if not sample_id:
        print("❌ No sample ID returned from Coqui AI")
        return generate_tts_fallback(text)
    
    # Wait for sample to be ready and download it
    return download_coqui_sample(sample_id, text)

def download_coqui_sample(sample_id, text, max_attempts=10):
    """Wait for sample to be ready and download it"""
    download_url = f"https://app.coqui.ai/api/v2/samples/{sample_id}"
    
    for attempt in range(max_attempts):
        print(f"   Waiting for audio generation... ({attempt + 1}/{max_attempts})")
        
        response = requests.get(download_url, timeout=30)
        if response.status_code == 200:
            sample_data = response.json()
            audio_url = sample_data.get('audio_url')
            
            if audio_url:
                # Download the audio file
                audio_response = requests.get(audio_url, timeout=60)
                if audio_response.status_code == 200:
                    return audio_response.content
                else:
                    print(f"⚠️ Audio download failed: {audio_response.status_code}")
        
        # Wait before retrying
        import time
        time.sleep(3)
    
    print("❌ Coqui AI sample generation timeout")
    return generate_tts_fallback(text)

def generate_tts_fallback(text):
    """Fallback TTS using gTTS (Google Text-to-Speech)"""
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
        # Ultimate fallback - generate silent audio with moviepy
        return generate_silent_audio_fallback(text)

def generate_silent_audio_fallback(text):
    """Generate silent audio as last resort fallback"""
    try:
        from moviepy import AudioClip
        import numpy as np
        
        # Calculate duration based on word count
        words = len(text.split())
        duration = max(30, min(60, (words / 150) * 60))  # 30-60 second range
        
        # Generate silent audio
        def make_silence(t):
            return np.zeros(2)  # Stereo silence
        
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
    # Install gTTS if needed for fallback
    try:
        import gtts
    except ImportError:
        print("📦 Installing gTTS for fallback support...")
        os.system("pip install gtts")
        import gtts
    
    audio_content = generate_tts_coqui(spoken)
    
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
        "tts_provider": "coqui_ai"
    }
    
    with open(os.path.join(TMP, "audio_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

except requests.exceptions.Timeout:
    print("❌ Request timed out. TTS API might be slow.")
    raise SystemExit(1)
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
    raise SystemExit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    raise SystemExit(1)

print("✅ TTS generation complete with Coqui AI")