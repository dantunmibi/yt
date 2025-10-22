# .github/scripts/upload_instagram.py
import os
import json
from datetime import datetime
from typing import Optional, Dict
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import time

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

class InstagramUploader:
    """Instagram Reels upload using Meta Graph API"""
    
    def __init__(self):
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.api_base = "https://graph.facebook.com/v18.0"
        
    def _get_params(self) -> dict:
        """Get API params"""
        return {"access_token": self.access_token}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _create_container(self, video_url: str, metadata: dict) -> str:
        """Create media container"""
        
        url = f"{self.api_base}/{self.account_id}/media"
        
        # Prepare caption with hashtags
        caption = metadata.get("description", "")
        hashtags = metadata.get("hashtags", [])
        
        if hashtags:
            caption += "\n\n" + " ".join(hashtags[:30])  # Instagram limit
        
        params = {
            **self._get_params(),
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],  # Instagram limit
            "share_to_feed": True
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data["id"]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _check_container_status(self, container_id: str) -> str:
        """Check if container is ready"""
        
        url = f"{self.api_base}/{container_id}"
        params = {
            **self._get_params(),
            "fields": "status_code"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get("status_code", "")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _publish_container(self, container_id: str) -> str:
        """Publish the media container"""
        
        url = f"{self.api_base}/{self.account_id}/media_publish"
        params = {
            **self._get_params(),
            "creation_id": container_id
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data["id"]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _get_media_url(self, media_id: str) -> str:
        """Get permalink for published media"""
        
        url = f"{self.api_base}/{media_id}"
        params = {
            **self._get_params(),
            "fields": "permalink"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get("permalink", "")
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Main upload method"""
        
        if not self.access_token or not self.account_id:
            return {
                "success": False,
                "error": "Missing Instagram credentials (access_token or account_id)"
            }
        
        try:
            # Note: Instagram requires video to be publicly accessible URL
            # You'll need to upload to a temporary hosting service first
            print("📸 Starting Instagram Reels upload...")
            print("⚠️ Note: Instagram requires publicly accessible video URL")
            print("   You need to implement video hosting (S3, Cloudinary, etc.)")
            
            # Placeholder for video hosting
            # video_url = self._upload_to_hosting(video_path)
            video_url = os.getenv("TEMP_VIDEO_URL")  # Must be set
            
            if not video_url:
                return {
                    "success": False,
                    "error": "Video hosting URL not provided (set TEMP_VIDEO_URL)"
                }
            
            # Create container
            print("📦 Creating media container...")
            container_id = self._create_container(video_url, metadata)
            
            # Wait for processing
            print("⏳ Processing video...")
            max_attempts = 20
            for i in range(max_attempts):
                time.sleep(5)
                status = self._check_container_status(container_id)
                
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    return {
                        "success": False,
                        "error": "Video processing failed"
                    }
                
                print(f"   Attempt {i+1}/{max_attempts}: {status}")
            
            if status != "FINISHED":
                return {
                    "success": False,
                    "error": "Video processing timeout"
                }
            
            # Publish
            print("📤 Publishing to Instagram...")
            media_id = self._publish_container(container_id)
            
            # Get URL
            permalink = self._get_media_url(media_id)
            
            print(f"✅ Instagram Reels upload complete!")
            print(f"   URL: {permalink}")
            
            return {
                "success": True,
                "video_id": media_id,
                "url": permalink,
                "platform": "instagram"
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            if e.response:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
            
            return {
                "success": False,
                "error": f"HTTP error: {error_msg}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


def main():
    """Standalone execution"""
    try:
        with open(os.path.join(TMP, "script.json"), "r") as f:
            metadata = json.load(f)
        
        video_path = os.path.join(TMP, "short.mp4")
        
        uploader = InstagramUploader()
        result = uploader.upload(video_path, metadata)
        
        if result["success"]:
            print(f"✅ Success: {result['url']}")
        else:
            print(f"❌ Failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()