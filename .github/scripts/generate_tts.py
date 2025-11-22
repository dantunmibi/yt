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

# 🛡️ MODEL LIST (Primary + Fallback)
# 1. Facebook MMS (Best Quality, Natural)
# 2. Facebook FastSpeech2 (Backup, Fast)
# 3. Espnet (Last Resort)
MODELS = [
    "facebook/mms-tts-eng",
    "facebook/fastspeech2-en-ljspeech", 
    "espnet/kan-bayashi_ljspeech_vits"
]

def intelligent_cleaner(text):
    """Cleaning logic for Neural TTS"""
    if not text: return ""
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text) 
    text = re.sub(r'\bAI\b', 'A.I.', text)
    text = re.sub(r'\bChatGPT\b', 'Chat G P T', text)
    
    def replace_caps(match):
        word = match.group(0)
        if word in ["TOP", "NOW", "WOW", "HOW", "FREE", "NEW", "HOT"]:
            return word.capitalize()
        return word
    text = re.sub(r'\b[A-Z]{3,4}\b', replace_caps, text)
    
    return re.sub(r'\s+', ' ', text).strip()

def try_generate_with_model(model_id, text):
    """Helper to try a specific model"""
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": text}

    print(f"🌊 Sending request to: {model_id}...")
    response = requests.post(api_url, headers=headers, json=payload)
    
    # Handle Loading (503)
    if response.status_code == 503:
        wait_time = response.json().get("estimated_time", 20)
        print(f"⏳ Model {model_id} is loading. Waiting {wait_time}s...")
        time.sleep(wait_time)
        # Recursive retry for loading state
        return try_generate_with_model(model_id, text)

    if response.status_code != 200:
        print(f"⚠️ Model {model_id} failed: {response.status_code}")
        return None

    return response.content

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_hf_audio_robust(text):
    """Iterates through models until one works"""
    if not HF_TOKEN:
        raise ValueError("❌ HUGGINGFACE_API_KEY is missing!")

    for model_id in MODELS:
        audio_content = try_generate_with_model(model_id, text)
        if audio_content:
            # Save raw audio
            temp_path = os.path.join(TMP, "temp_audio.flac")
            with open(temp_path, "wb") as f:
                f.write(audio_content)
            return temp_path, model_id
    
    raise Exception("❌ All HF Models failed.")

def convert_to_mp3(input_path):
    print("🔄 Converting to MP3...")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        
        # Speed up slightly (1.1x)
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
        print(f"❌ Script file not found")
        exit(1)

    try:
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        raw_text = f"{data.get('hook', '')} {' '.join(data.get('bullets', []))} {data.get('cta', '')}"
        clean_text = intelligent_cleaner(raw_text)
        
        # Generate
        raw_path, used_model = generate_hf_audio_robust(clean_text)
        
        # Convert
        if convert_to_mp3(raw_path):
            if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
                print(f"✅ Audio Generated using: {used_model}")
                metadata = {
                    "engine": f"HuggingFace ({used_model})",
                    "text_length": len(clean_text),
                    "file_size": os.path.getsize(OUTPUT_FILE)
                }
                with open(METADATA_FILE, "w") as f:
                    json.dump(metadata, f, indent=2)
            else:
                raise Exception("Final MP3 empty")
        else:
            raise Exception("Conversion failed")

    except Exception as e:
        print(f"❌ FATAL AUDIO ERROR: {e}")
        exit(1)

if __name__ == "__main__":
    main()