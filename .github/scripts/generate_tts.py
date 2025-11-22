import os
import json
import re
import requests
import time
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuration
TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
SCRIPT_FILE = os.path.join(TMP, "script.json")
OUTPUT_FILE = os.path.join(TMP, "voice.mp3")
METADATA_FILE = os.path.join(TMP, "audio_metadata.json")

# Secrets
HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY")

# Model: Facebook MMS-TTS (English)
# Using modern Router URL
API_URL = "https://router.huggingface.co/hf-inference/models/facebook/mms-tts-eng"

def intelligent_cleaner(text):
    """
    Cleaning logic for Neural TTS.
    Fixes pronunciation and removes artifacts.
    """
    if not text: return ""
    
    # 1. Remove Emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. Fix Pronunciation
    text = re.sub(r'\bAI\b', 'A.I.', text)
    text = re.sub(r'\bai\b', 'A.I.', text)
    text = re.sub(r'\bChatGPT\b', 'Chat G P T', text)
    
    # 3. Fix ALL CAPS words
    def replace_caps(match):
        word = match.group(0)
        if word in ["TOP", "NOW", "WOW", "HOW", "FREE", "NEW", "HOT"]:
            return word.capitalize()
        return word
    text = re.sub(r'\b[A-Z]{3,4}\b', replace_caps, text)
    
    # 4. Cleanup
    text = text.replace('*', '').replace('#', '').replace('_', '')
    text = re.sub(r'\[.*?\]', '', text) 
    
    return re.sub(r'\s+', ' ', text).strip()

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=10, max=40))
def generate_hf_audio(text):
    """
    Generates audio using HuggingFace Inference Router.
    Handles 'Model Loading' (503) errors automatically.
    """
    if not HF_TOKEN:
        raise ValueError("❌ HUGGINGFACE_API_KEY is missing in Secrets!")

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": text}

    print(f"🌊 Sending request to HF Router ({len(text)} chars)...")
    response = requests.post(API_URL, headers=headers, json=payload)
    
    # Case 1: Model is Loading (Free Tier Cold Start)
    if response.status_code == 503:
        estimated_time = response.json().get("estimated_time", 20)
        print(f"⏳ Model is sleeping. Waking up... (Wait {estimated_time}s)")
        time.sleep(estimated_time)
        raise Exception("Model loading retry") # Triggers tenacity retry

    # Case 2: Actual Error
    if response.status_code != 200:
        raise Exception(f"HF API Error {response.status_code}: {response.text}")

    # Case 3: Success
    # Save raw audio (MMS usually returns FLAC)
    temp_path = os.path.join(TMP, "temp_audio.flac")
    with open(temp_path, "wb") as f:
        f.write(response.content)
    
    return temp_path

def convert_to_mp3(input_path):
    """
    Converts raw FLAC to MP3 and speeds up slightly for Shorts retention.
    """
    print("🔄 Converting FLAC to MP3 and optimizing speed...")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        
        # Speed up slightly (1.1x) for viral retention
        new_sample_rate = int(audio.frame_rate * 1.1)
        faster_audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
        faster_audio = faster_audio.set_frame_rate(audio.frame_rate)
        
        faster_audio.export(OUTPUT_FILE, format="mp3")
        return True
    except Exception as e:
        print(f"⚠️ Conversion failed: {e}")
        return False

def main():
    if not os.path.exists(SCRIPT_FILE):
        print(f"❌ Script file not found: {SCRIPT_FILE}")
        exit(1)

    try:
        # 1. Load Script
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        raw_text = f"{data.get('hook', '')} {' '.join(data.get('bullets', []))} {data.get('cta', '')}"
        clean_text = intelligent_cleaner(raw_text)
        
        # 2. Generate (with Retry Logic)
        raw_audio_path = generate_hf_audio(clean_text)
        
        # 3. Convert & Optimize
        if convert_to_mp3(raw_audio_path):
            # 4. Save Metadata
            if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
                print(f"✅ Neural Audio Generated Successfully")
                metadata = {
                    "engine": "HuggingFace MMS-TTS",
                    "text_length": len(clean_text),
                    "file_size": os.path.getsize(OUTPUT_FILE)
                }
                with open(METADATA_FILE, "w") as f:
                    json.dump(metadata, f, indent=2)
            else:
                raise Exception("Final MP3 file is empty")
        else:
            raise Exception("Audio conversion failed")

    except Exception as e:
        print(f"❌ FATAL AUDIO ERROR: {e}")
        exit(1)

if __name__ == "__main__":
    main()