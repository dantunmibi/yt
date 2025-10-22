# .github/scripts/upload_tiktok.py
import os
import json
from datetime import datetime
from typing import Optional, Dict
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

class TikTokUploader:
    """TikTok upload using official TikTok API"""
    
    def __init__(self):
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.api_base = "https://open.tiktokapis.com/v2"
        
    def _get_headers(self) -> dict:
        """Get API headers"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _init_upload(self, metadata: dict) -> Optional[dict]:
        """Initialize video upload"""
        
        # Get video file info
        video_path = os.path.join(TMP, "short.mp4")
        video_size = os.path.getsize(video_path)
        
        # Prepare upload request
        url = f"{self.api_base}/post/publish/video/init/"
        
        payload = {
            "post_info": {
                "title": metadata.get("title", "")[:150],  # TikTok max 150 chars
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # Upload in single chunk
                "total_chunk_count": 1
            }
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        
        return response.json()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _upload_video(self, upload_url: str, video_path: str) -> bool:
        """Upload video file to TikTok"""
        
        with open(video_path, 'rb') as f:
            video_data = f.read()
        
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_data))
        }
        
        response = requests.put(upload_url, headers=headers, data=video_data)
        response.raise_for_status()
        
        return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _check_status(self, publish_id: str) -> dict:
        """Check upload status"""
        
        url = f"{self.api_base}/post/publish/status/{publish_id}/"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json()
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Main upload method"""
        
        if not self.access_token:
            return {
                "success": False,
                "error": "Missing TikTok access token"
            }
        
        try:
            print("📱 Initializing TikTok upload...")
            init_response = self._init_upload(metadata)
            
            upload_url = init_response["data"]["upload_url"]
            publish_id = init_response["data"]["publish_id"]
            
            print("📤 Uploading video to TikTok...")
            self._upload_video(upload_url, video_path)
            
            print("⏳ Processing video...")
            # Check status (may take a few seconds)
            import time
            for i in range(10):
                time.sleep(3)
                status = self._check_status(publish_id)
                
                if status["data"]["status"] == "PUBLISH_COMPLETE":
                    share_url = status["data"].get("share_url", "")
                    
                    print(f"✅ TikTok upload complete!")
                    print(f"   URL: {share_url}")
                    
                    return {
                        "success": True,
                        "video_id": publish_id,
                        "url": share_url,
                        "platform": "tiktok"
                    }
                elif status["data"]["status"] == "FAILED":
                    return {
                        "success": False,
                        "error": "Upload failed during processing"
                    }
            
            # Timeout
            return {
                "success": False,
                "error": "Upload timed out"
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
        
        uploader = TikTokUploader()
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