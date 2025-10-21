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
import re

def clean_text_for_tts(text):
    """
    Enhanced text preprocessing for natural TTS pronunciation
    Handles acronyms, technical terms, and special characters
    """
    
    # Step 1: Preserve important punctuation for natural pauses
    text = text.replace('...', ' pause ')
    
    # Step 2: Handle special characters
    text = text.replace('%', ' percent')
    text = text.replace('&', ' and ')
    text = text.replace('+', ' plus ')
    text = text.replace('@', ' at ')
    text = text.replace('$', ' dollars ')
    text = text.replace('€', ' euros ')
    text = text.replace('£', ' pounds ')
    text = text.replace('#', ' hashtag ')
    
    # Step 3: Handle common acronyms with NATURAL spellings
    # These work better with most TTS engines than phonemes
    acronym_replacements = {
        # AI/ML terms (most important for your use case)
        r'\bAI\b': 'A I',  # Spell it out clearly
        r'\bML\b': 'M L',
        r'\bGPT\b': 'G P T',
        r'\bLLM\b': 'L L M',
        r'\bNLP\b': 'N L P',
        
        # ChatGPT and variants
        r'\bChatGPT\b': 'Chat G P T',
        r'\bchatgpt\b': 'chat G P T',
        r'\bCHATGPT\b': 'Chat G P T',
        
        # Tech companies
        r'\bAPI\b': 'A P I',
        r'\bUI\b': 'U I',
        r'\bUX\b': 'U X',
        r'\bCEO\b': 'C E O',
        r'\bCTO\b': 'C T O',
        
        # Computer hardware
        r'\bCPU\b': 'C P U',
        r'\bGPU\b': 'G P U',
        r'\bRAM\b': 'ram',  # This is often pronounced as a word
        r'\bSSD\b': 'S S D',
        r'\bUSB\b': 'U S B',
        
        # Web/Internet
        r'\bHTTP\b': 'H T T P',
        r'\bHTTPS\b': 'H T T P S',
        r'\bURL\b': 'U R L',
        r'\bHTML\b': 'H T M L',
        r'\bCSS\b': 'C S S',
        r'\bJSON\b': 'J son',  # Pronounced as "jay-son"
        r'\bSQL\b': 'S Q L',
        r'\bXML\b': 'X M L',
        
        # Organizations
        r'\bNASA\b': 'nasa',  # Pronounced as word
        r'\bFBI\b': 'F B I',
        r'\bCIA\b': 'C I A',
        r'\bUSA\b': 'U S A',
        r'\bUK\b': 'U K',
        r'\bUN\b': 'U N',
        r'\bEU\b': 'E U',
        
        # Sports/Entertainment
        r'\bNBA\b': 'N B A',
        r'\bNFL\b': 'N F L',
        r'\bUFC\b': 'U F C',
        
        # Units
        r'\bGB\b': 'gigabytes',
        r'\bMB\b': 'megabytes',
        r'\bKB\b': 'kilobytes',
        r'\bTB\b': 'terabytes',
        r'\bFPS\b': 'F P S',
        
        # Tech/Gaming
        r'\bVR\b': 'V R',
        r'\bAR\b': 'A R',
        r'\bMR\b': 'M R',
        r'\bDIY\b': 'D I Y',
        r'\bOK\b': 'okay',
        r'\bOKay\b': 'okay',
        
        # Social Media
        r'\bDM\b': 'D M',
        r'\bPM\b': 'P M',
        r'\bFAQ\b': 'F A Q',
        r'\bFYI\b': 'F Y I',
        r'\bTBH\b': 'T B H',
        r'\bIMO\b': 'I M O',
        r'\bAFAIK\b': 'A F A I K',
    }
    
    # Apply all replacements
    for pattern, replacement in acronym_replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Step 4: Handle numbers with context
    # "4K video" should be "four K video"
    text = re.sub(r'\b(\d+)K\b', r'\1 K', text)
    text = re.sub(r'\b(\d+)x\b', r'\1 times', text)
    
    # Step 5: Remove emojis
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    
    # Step 6: Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s([.,!?])', r'\1', text)  # Remove space before punctuation
    
    # Step 7: Ensure sentences end properly for natural pauses
    text = re.sub(r'([.!?])\s*$', r'\1 ', text)
    
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
    sections = [("hook", hook)] + [(f"bullet_{i}", b) for i, b in enumerate(bullets)] + [("cta", cta)]
    
    try:
        print("🔊 Initializing Coqui TTS for sectional generation...")
        tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False)

        for name, text in sections:
            if not text.strip():
                continue
            
            clean = clean_text_for_coqui(text)
            out_path = os.path.join(TMP, f"{name}.mp3")
            print(f"🎧 Generating section: {name} (Text: {clean[:40]}...)")
            
            tts.tts_to_file(text=clean, file_path=out_path)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                section_paths.append(out_path)
            else:
                raise Exception(f"Coqui section generation failed for {name}")

    except Exception as e:
        print(f"⚠️ Sectional Coqui TTS failed: {e}")
        print("🔄 Falling back to gTTS with section splitting...")
        
        # ✅ FIX: Generate full audio, then split it into sections
        fallback_path = generate_tts_fallback(spoken, FULL_AUDIO_PATH)
        
        if not os.path.exists(fallback_path) or os.path.getsize(fallback_path) < 1000:
            raise Exception("Fallback audio generation failed")
        
        # Split the full audio into sections based on word count proportions
        print("🔪 Splitting full audio into sections for timing...")
        full_audio = AudioSegment.from_file(fallback_path)
        total_duration_ms = len(full_audio)
        
        # Calculate proportions based on word count
        section_texts = [(name, text) for name, text in sections if text.strip()]
        total_words = sum(len(text.split()) for _, text in section_texts)
        
        current_pos = 0
        section_paths = []
        
        for name, text in section_texts:
            words = len(text.split())
            proportion = words / total_words if total_words > 0 else 1.0 / len(section_texts)
            section_duration_ms = int(total_duration_ms * proportion)
            
            # Extract section
            section_audio = full_audio[current_pos:current_pos + section_duration_ms]
            section_path = os.path.join(TMP, f"{name}.mp3")
            section_audio.export(section_path, format="mp3")
            
            section_paths.append(section_path)
            current_pos += section_duration_ms
            
            print(f"   ✅ {name}: {section_duration_ms/1000:.2f}s")
        
        print("✅ Sections created from fallback audio")
        return section_paths

    # Combine sections (original logic continues)
    combined_audio = AudioSegment.silent(duration=0)
    for path in section_paths:
        part = AudioSegment.from_file(path)
        combined_audio += part + AudioSegment.silent(duration=150)
        
    combined_audio.export(FULL_AUDIO_PATH, format="mp3")
    print(f"✅ Combined TTS saved to {FULL_AUDIO_PATH}")
    
    return section_paths


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