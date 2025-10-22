# .github/scripts/upload_facebook.py
import os
import json
from datetime import datetime
from typing import Optional, Dict
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

class FacebookUploader:
    """Facebook Reels upload using Graph API"""
    
    def __init__(self):
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_base = "https://graph.facebook.com/v18.0"
        
    def _get_params(self) -> dict:
        """Get API params"""
        return {"access_token": self.access_token}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _init_upload(self, video_size: int) -> dict:
        """Initialize video upload session"""
        
        url = f"{self.api_base}/{self.page_id}/video_reels"
        
        params = {
            **self._get_params(),
            "upload_phase": "start",
            "file_size": video_size
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _upload_video(self, upload_url: str, video_path: str, video_id: str) -> bool:
        """Upload video file"""
        
        with open(video_path, 'rb') as f:
            files = {'file': f}
            params = self._get_params()
            params['upload_phase'] = 'transfer'
            params['video_id'] = video_id
            
            response = requests.post(upload_url, params=params, files=files)
            response.raise_for_status()
        
        return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _finish_upload(self, video_id: str, metadata: dict) -> dict:
        """Finalize upload and publish"""
        
        url = f"{self.api_base}/{self.page_id}/video_reels"
        
        # Prepare description with hashtags
        description = metadata.get("description", "")
        hashtags = metadata.get("hashtags", [])
        
        if hashtags:
            description += "\n\n" + " ".join(hashtags[:30])
        
        params = {
            **self._get_params(),
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": description[:1000],  # Facebook limit
            "title": metadata.get("title", "")[:100]
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _get_video_url(self, video_id: str) -> str:
        """Get video permalink"""
        
        url = f"{self.api_base}/{video_id}"
        params = {
            **self._get_params(),
            "fields": "permalink_url"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get("permalink_url", "")
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Main upload method"""
        
        if not self.access_token or not self.page_id:
            return {
                "success": False,
                "error": "Missing Facebook credentials (access_token or page_id)"
            }
        
        try:
            video_size = os.path.getsize(video_path)
            
            # Initialize upload
            print("👥 Initializing Facebook Reels upload...")
            init_response = self._init_upload(video_size)
            
            video_id = init_response.get("video_id")
            upload_url = init_response.get("upload_url")
            
            if not video_id or not upload_url:
                return {
                    "success": False,
                    "error": "Failed to initialize upload session"
                }
            
            # Upload video
            print("📤 Uploading video to Facebook...")
            self._upload_video(upload_url, video_path, video_id)
            
            # Finish and publish
            print("✅ Publishing to Facebook Reels...")
            finish_response = self._finish_upload(video_id, metadata)
            
            # Get permalink
            permalink = self._get_video_url(video_id)
            
            print(f"✅ Facebook Reels upload complete!")
            print(f"   URL: {permalink}")
            
            return {
                "success": True,
                "video_id": video_id,
                "url": permalink,
                "platform": "facebook"
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
        
        uploader = FacebookUploader()
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