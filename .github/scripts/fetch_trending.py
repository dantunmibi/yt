import json
import time
import random
from typing import List, Dict, Any
import os
import google.generativeai as genai

# Configure using the same pattern as your working script
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use the same model selection logic as your working script
try:
    models = genai.list_models()
    model_name = None
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            if '2.0-flash' in m.name or '2.5-flash' in m.name:
                model_name = m.name
                break
            elif '1.5-flash' in m.name and not model_name:
                model_name = m.name
    
    if not model_name:
        model_name = "models/gemini-1.5-flash"
    
    print(f"✅ Using model: {model_name}")
    model = genai.GenerativeModel(model_name)
except Exception as e:
    print(f"⚠️ Error listing models: {e}")
    model = genai.GenerativeModel("models/gemini-1.5-flash")

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
os.makedirs(TMP, exist_ok=True)

def get_trending_ideas(user_query: str) -> List[Dict[str, str]]:
    """
    Calls the Gemini API to generate structured trending content ideas.
    Uses the same pattern as your working script.
    """
    
    # Define the structure for the JSON output
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "topics": {
                "type": "ARRAY", 
                "items": {"type": "STRING"},
                "description": "List of 5 trending topics related to the query"
            }
        },
        "required": ["topics"]
    }

    system_prompt = (
        "You are a viral content strategist. Analyze current global trends "
        "and provide 5 trending topics that would work well for short-form video content. "
        "Focus on what's currently popular and engaging."
    )

    full_user_query = f"Generate 5 trending topics for short-form video content about: {user_query}"
    
    prompt = f"""Based on current real-time trends, generate 5 unique and distinct trending topics for short-form video content.

QUERY: {user_query}

REQUIREMENTS:
- Topics must be currently trending and relevant
- Each should be specific and engaging for short-form video
- Include a mix of different angles and approaches
- Focus on what's popular right now in social media

OUTPUT FORMAT (JSON ONLY):
{{
  "topics": [
    "Trending topic 1 with specific details",
    "Trending topic 2 with specific details", 
    "Trending topic 3 with specific details",
    "Trending topic 4 with specific details",
    "Trending topic 5 with specific details"
  ]
}}"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"--- Attempting to fetch trending ideas (Attempt {attempt + 1}/{max_retries}) ---")
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            
            # Parse the response
            result_text = response.text.strip()
            
            # Extract JSON if it's wrapped in code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            
            result_data = json.loads(result_text)
            
            # Convert to the expected format
            trending_ideas = []
            for i, topic in enumerate(result_data.get('topics', [])):
                trending_ideas.append({
                    "topic_title": f"Trending: {topic}",
                    "summary": f"This topic is currently trending and has high engagement potential for short-form video content.",
                    "category": "Trending"
                })
            
            print(f"✅ Successfully generated {len(trending_ideas)} trending ideas")
            return trending_ideas

        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                sleep_time = (2 ** attempt) + random.random()
                print(f"Waiting for {sleep_time:.2f} seconds before retrying...")
                time.sleep(sleep_time)

    print("⚠️ Failed to get trending ideas after multiple retries, using fallback...")
    
    # Fallback trending ideas
    return [
        {
            "topic_title": "AI Video Generation Breakthroughs 2025",
            "summary": "Latest developments in AI video creation tools and their impact on content creation",
            "category": "Technology"
        },
        {
            "topic_title": "Space Exploration: Moon to Mars Missions",
            "summary": "Current space missions and their significance for future exploration",
            "category": "Science"
        },
        {
            "topic_title": "Sustainable Tech Innovations",
            "summary": "New technologies addressing climate change and environmental challenges",
            "category": "Innovation"
        }
    ]

if __name__ == "__main__":        
    # Example usage:
    topic_focus = "AI brain hacks, cutting-edge technology, innovation, digital productivity, trending life enhancement tools, and life optimization tricks for Ultra Engaging Youtube Shorts"
    trending_ideas = get_trending_ideas(topic_focus)

    if trending_ideas:
        print(f"\n--- Trending Video Ideas for: {topic_focus} ---")
        for i, idea in enumerate(trending_ideas):
            print(f"\nIdea {i + 1}:")
            print(f"  Title: {idea['topic_title']}")
            print(f"  Category: {idea['category']}")
            print(f"  Summary: {idea['summary']}")
        
        # Save to file for use by other scripts
        trending_data = {
            "topics": [idea["topic_title"] for idea in trending_ideas],
            "generated_at": time.time(),
            "query": topic_focus
        }
        
        trending_file = os.path.join(TMP, "trending.json")
        with open(trending_file, "w") as f:
            json.dump(trending_data, f, indent=2)
        
        print(f"\n💾 Saved trending data to: {trending_file}")
    else:
        print("\nCould not retrieve any trending video ideas.")