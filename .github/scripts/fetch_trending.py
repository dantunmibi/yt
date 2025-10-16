import json
import time
import random
from typing import List, Dict, Any
import os

# NOTE: The apiKey is dynamically provided by the runtime environment.
# DO NOT include a real key here.
API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
MODEL_NAME = "gemini-2.5-flash-preview-09-2025"

def get_trending_ideas(user_query: str) -> List[Dict[str, str]]:
    """
    Calls the Gemini API to generate structured trending content ideas.
    It uses Google Search grounding to ensure the ideas are current.
    """
    
    # Define the structure for the JSON output (list of ideas)
    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "topic_title": {"type": "STRING", "description": "A compelling title for a video on the trending topic."},
                "summary": {"type": "STRING", "description": "A brief summary explaining why this topic is trending now."},
                "category": {"type": "STRING", "description": "The likely content category (e.g., Tech, Finance, Gaming)."}
            },
            "required": ["topic_title", "summary", "category"],
            "propertyOrdering": ["topic_title", "summary", "category"]
        }
    }

    # System instruction sets the persona and rules for the model
    system_prompt = (
        "You are a viral content strategist. Your task is to analyze current global trends "
        "using real-time search data and propose 3 highly engaging, short-form video "
        "content ideas. The output MUST be a strict JSON array following the provided schema."
    )

    # User query specifies the task
    full_user_query = f"Based on current real-time trends, generate 3 unique and distinct video ideas. Focus on {user_query}."
    
    payload = {
        "contents": [{"parts": [{"text": full_user_query}]}],
        # Enable Google Search grounding for real-time information
        "tools": [{"google_search": {}}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "config": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    # Exponential backoff parameters
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"--- Attempting to fetch trending ideas (Attempt {attempt + 1}/{max_retries}) ---")
            
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY # The runtime provides this key
            }
            
            response = requests.post(
                API_URL, 
                headers=headers, 
                data=json.dumps(payload)
            )
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            
            result = response.json()
            
            # Extract and parse the generated JSON text
            json_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # The result should be a list of dictionaries conforming to the schema
            return json.loads(json_text)

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error on attempt {attempt + 1}: {e}. Retrying...")
        except Exception as e:
            print(f"An unexpected error occurred on attempt {attempt + 1}: {e}. Retrying...")

        if attempt < max_retries - 1:
            # Exponential backoff
            sleep_time = (2 ** attempt) + random.random()
            print(f"Waiting for {sleep_time:.2f} seconds before retrying...")
            time.sleep(sleep_time)

    print("Failed to get trending ideas after multiple retries.")
    return []

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("The 'requests' library is required. Please install it with: pip install requests")
        exit(1)
        
    # Example usage:
    topic_focus = "Artificial Intelligence and Space Exploration"
    trending_ideas = get_trending_ideas(topic_focus)

    if trending_ideas:
        print(f"\n--- Trending Video Ideas for: {topic_focus} ---")
        for i, idea in enumerate(trending_ideas):
            print(f"\nIdea {i + 1}:")
            print(f"  Title: {idea['topic_title']}")
            print(f"  Category: {idea['category']}")
            print(f"  Summary: {idea['summary']}")
    else:
        print("\nCould not retrieve any trending video ideas.")
