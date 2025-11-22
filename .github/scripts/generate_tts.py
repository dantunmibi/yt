import os
import json
import re
import subprocess
from gtts import gTTS

# Configuration
TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
SCRIPT_FILE = os.path.join(TMP, "script.json")
OUTPUT_FILE = os.path.join(TMP, "voice.mp3")
METADATA_FILE = os.path.join(TMP, "audio_metadata.json")

# 🎙️ VOICE CONFIG (Free Neural)
# "en-US-ChristopherNeural" is the best for Tech/Education
NEURAL_VOICE = "en-US-ChristopherNeural"

def intelligent_cleaner(text):
    """
    Advanced cleaner for Neural TTS.
    Fixes pronunciation of acronyms, emojis, and odd phrasing.
    """
    if not text: return ""

    # 1. Remove Emojis (Fixes "Exploding Head" reading)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. Fix "AI" -> "A.I."
    text = re.sub(r'\bAI\b', 'A.I.', text)
    text = re.sub(r'\bai\b', 'A.I.', text)
    
    # 3. Fix ALL CAPS words (TOP, NOW, WOW) being read as letters
    def replace_caps(match):
        word = match.group(0)
        if word in ["TOP", "NOW", "WOW", "HOW", "FREE", "NEW", "HOT", "STOP"]:
            return word.capitalize() # "Top" is read as word
        return word
    text = re.sub(r'\b[A-Z]{3,4}\b', replace_caps, text)
    
    # 4. Fix Tech Acronyms
    replacements = {
        r'\bChatGPT\b': 'Chat G P T', 
        r'\bLLM\b': 'L L M',
        r'\bSEO\b': 'S E O'
    }
    for p, r in replacements.items():
        text = re.sub(p, r, text, flags=re.IGNORECASE)
        
    # 5. Clean Artifacts
    text = text.replace('*', '').replace('#', '').replace('_', '')
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def generate_edge_tts_cli(text, output_path):
    """
    Uses the Edge-TTS CLI to bypass Python AsyncIO Handshake errors.
    This is the STABLE fix for GitHub Actions.
    """
    print(f"🌊 Attempting Neural Audio via CLI (Edge-TTS)...")
    
    # Rate +10% for better retention on Shorts
    command = [
        "edge-tts",
        "--text", text,
        "--write-media", output_path,
        "--voice", NEURAL_VOICE,
        "--rate=+10%"
    ]
    
    try:
        # Run the command safely
        result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Edge-TTS CLI Failed: {e.stderr}")
        return False

def generate_fallback_gtts(text, output_path):
    """
    Catastrophic Fallback: Google Translate TTS
    Only used if Edge-TTS servers are down.
    """
    print(f"🔄 Switching to Google Fallback (gTTS)...")
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"❌ gTTS Failed: {e}")
        return False

def main():
    if not os.path.exists(SCRIPT_FILE):
        print(f"❌ Script file not found: {SCRIPT_FILE}")
        exit(1)

    try:
        # 1. Load & Process Text
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        raw_text = f"{data.get('hook', '')} {' '.join(data.get('bullets', []))} {data.get('cta', '')}"
        clean_text = intelligent_cleaner(raw_text)
        
        print(f"📝 Text Length: {len(clean_text)} chars")
        print(f"🔍 Preview: {clean_text[:60]}...")

        # 2. Attempt Generation
        engine_used = "None"
        
        # Try Edge (Quality)
        success = generate_edge_tts_cli(clean_text, OUTPUT_FILE)
        
        if success:
            engine_used = "Edge-TTS (ChristopherNeural)"
        else:
            # Try Google (Reliability)
            success = generate_fallback_gtts(clean_text, OUTPUT_FILE)
            engine_used = "gTTS (Fallback)"

        # 3. Verify & Save Metadata
        if success and os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
            print(f"✅ Audio generated successfully using {engine_used}")
            
            # Estimate duration (Words / 2.5 words per sec)
            duration_est = len(clean_text.split()) / 2.5
            
            metadata = {
                "engine": engine_used,
                "text_length": len(clean_text),
                "estimated_duration": duration_est,
                "file_size": os.path.getsize(OUTPUT_FILE)
            }
            
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)
        else:
            raise Exception("Audio file creation failed.")

    except Exception as e:
        print(f"❌ FATAL AUDIO ERROR: {e}")
        exit(1)

if __name__ == "__main__":
    main()