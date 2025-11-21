import os
import json
import re
import asyncio
import edge_tts
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuration
TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)
SCRIPT_FILE = os.path.join(TMP, "script.json")
OUTPUT_FILE = os.path.join(TMP, "voice.mp3")
METADATA_FILE = os.path.join(TMP, "audio_metadata.json")

# 🎙️ VOICE SELECTION
# "en-US-ChristopherNeural" -> Best for Tech/Tutorials (Calm, authoritative)
# "en-US-GuyNeural" -> Best for High Energy/Viral (Fast, punchy)
# "en-US-EricNeural" -> Best for News (Serious)
VOICE = "en-US-ChristopherNeural" 

print(f"✅ Selected Neural Voice: {VOICE}")

def intelligent_cleaner(text):
    """
    Advanced cleaner designed specifically for Neural TTS engines.
    Fixes pronunciation anomalies while preserving flow.
    """
    if not text: return ""

    # 1. NUCLEAR EMOJI REMOVAL
    # Removes emojis that cause the engine to say "Red Heart", "Exploding Head"
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. Fix "AI" pronunciation
    # Neural engines sometimes say "Ay" instead of "A.I."
    text = re.sub(r'\bAI\b', 'A.I.', text)
    text = re.sub(r'\bai\b', 'A.I.', text)
    
    # 3. Fix "TOP" / "NOW" / "WOW" being read as acronyms
    # We lowercase them in the context of a sentence to force word pronunciation
    # but keep the emphasis by surrounding with subtle pauses if needed.
    
    def replace_caps(match):
        word = match.group(0)
        # List of words that should NEVER be spelled out as letters
        if word in ["TOP", "NOW", "WOW", "HOW", "FREE", "NEW", "HOT"]:
            return word.capitalize() # "Top" is read as a word, "TOP" sometimes as T-O-P
        return word

    text = re.sub(r'\b[A-Z]{3,4}\b', replace_caps, text)
    
    # 4. Fix Tech Acronyms (Force letter pronunciation)
    # Neural engines are usually good at this, but we ensure consistency
    replacements = {
        r'\bChatGPT\b': 'Chat G P T',
        r'\bLLM\b': 'L L M',
        r'\bSEO\b': 'S E O',
        r'\bROI\b': 'R O I',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
    # 5. Fix Markdown artifacts
    text = text.replace('*', '').replace('#', '').replace('_', '')
    text = re.sub(r'\[.*?\]', '', text) # Remove [Visual Cues]
    
    # 6. Cleanup whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_neural_voice(text, output_file):
    """
    Generates audio using Microsoft Edge's Neural TTS API.
    """
    print(f"🌊 Generating Neural Audio ({len(text)} chars)...")
    
    # Rate adjustment: +10% speed is standard for Shorts retention
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    
    await communicate.save(output_file)
    
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        print(f"✅ Saved to {output_file} ({os.path.getsize(output_file)} bytes)")
    else:
        raise Exception("Generated audio file is empty")

def main():
    if not os.path.exists(SCRIPT_FILE):
        print(f"❌ Script file not found: {SCRIPT_FILE}")
        return

    try:
        # 1. Load Script
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 2. Assemble Text
        # We combine them naturally because Neural TTS handles sentence pauses perfectly
        hook = data.get("hook", "")
        bullets = " ".join(data.get("bullets", []))
        cta = data.get("cta", "")
        
        full_text = f"{hook} {bullets} {cta}"
        
        # 3. Clean Text
        clean_text = intelligent_cleaner(full_text)
        print(f"📝 Cleaned Text: {clean_text[:100]}...")
        
        # 4. Generate
        asyncio.run(generate_neural_voice(clean_text, OUTPUT_FILE))
        
        # 5. Generate Metadata (For Package 4 tracking)
        # Use pydub to get exact duration if available, otherwise estimate
        duration_sec = 0
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(OUTPUT_FILE)
            duration_sec = len(audio) / 1000.0
        except ImportError:
            print("⚠️ pydub not installed, estimating duration")
            duration_sec = len(clean_text.split()) / 2.5 # Rough estimate
            
        metadata = {
            "text_length": len(clean_text),
            "duration_seconds": duration_sec,
            "voice_model": VOICE,
            "engine": "Edge-TTS (Neural)",
            "status": "success"
        }
        
        with open(METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
            
        print(f"📊 Duration: {duration_sec:.2f}s")
        
    except Exception as e:
        print(f"❌ TTS Generation Failed: {e}")
        # Optional: Add your gTTS fallback here if you really want it, 
        # but Edge-TTS is extremely reliable.
        exit(1)

if __name__ == "__main__":
    main()