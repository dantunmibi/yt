# .github/scripts/upload_facebook.py
import os
import json
import time
from datetime import datetime
from typing import Optional, Dict
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import traceback

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

class FacebookUploader:
    """Facebook Reels upload using Graph API v24.0 - SIMPLIFIED NON-RESUMABLE"""
    
    def __init__(self):
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_version = "v24.0"
        self.api_base = f"https://graph.facebook.com/{self.api_version}"
        
        if not self.access_token:
            print("⚠️ FACEBOOK_ACCESS_TOKEN not found in environment")
        if not self.page_id:
            print("⚠️ FACEBOOK_PAGE_ID not found in environment")
    
    def _get_params(self) -> dict:
        """Get base API parameters"""
        return {"access_token": self.access_token}
    
    def _validate_credentials(self) -> bool:
        """Validate Facebook credentials before upload"""
        try:
            url = f"{self.api_base}/{self.page_id}"
            params = self._get_params()
            params["fields"] = "id,name"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ Token valid for Page: {data.get('name', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Facebook credential validation failed: {e}")
            return False
    
    def _parse_error(self, response: requests.Response) -> str:
        """Parse Facebook API error response"""
        try:
            error_data = response.json()
            error = error_data.get("error", {})
            
            error_type = error.get("type", "Unknown")
            error_message = error.get("message", str(response.text))
            error_code = error.get("code", response.status_code)
            error_subcode = error.get("error_subcode", "")
            
            error_str = f"[{error_code}]"
            if error_subcode:
                error_str += f"[{error_subcode}]"
            error_str += f" {error_type}: {error_message}"
            
            return error_str
        except:
            return f"Status {response.status_code}: {response.text[:500]}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _upload_video_simple(self, video_path: str, metadata: dict) -> str:
        """
        Upload video using simple single-request method (non-resumable)
        This is more reliable for videos under 1GB
        """
        
        file_size = os.path.getsize(video_path)
        
        print(f"📤 Uploading video file (simple method)...")
        print(f"   Path: {video_path}")
        print(f"   Size: {file_size / (1024*1024):.2f} MB")
        
        # Prepare description with hashtags
        description = metadata.get("description", "")
        hashtags = metadata.get("hashtags", [])
        
        full_description = description
        if hashtags:
            hashtag_str = " ".join(hashtags[:30])
            full_description = f"{description}\n\n{hashtag_str}"
        
        full_description = full_description[:1000]
        
        url = f"{self.api_base}/{self.page_id}/videos"
        
        # Open video file
        with open(video_path, 'rb') as video_file:
            files = {
                'source': (os.path.basename(video_path), video_file, 'video/mp4')
            }
            
            data = {
                **self._get_params(),
                'description': full_description,
                'title': metadata.get("title", "")[:100],
                'published': 'true'
            }
            
            print(f"   Uploading to: {url}")
            print(f"   Title: {data['title']}")
            print(f"   Description length: {len(full_description)} chars")
            
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=600  # 10 minutes for upload
            )
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code not in [200, 201]:
                error_msg = self._parse_error(response)
                print(f"   ❌ Upload failed: {error_msg}")
                print(f"   Full response: {response.text}")
                raise Exception(f"Video upload failed: {error_msg}")
            
            result = response.json()
            video_id = result.get("id")
            
            if not video_id:
                raise Exception(f"No video ID in response: {result}")
            
            print(f"✅ Video uploaded successfully!")
            print(f"   Video ID: {video_id}")
            
            return video_id
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=5, max=30))
    def _get_video_url(self, video_id: str) -> str:
        """Get video permalink (may take time to process)"""
        
        print(f"🔗 Fetching video URL...")
        
        url = f"{self.api_base}/{video_id}"
        params = {
            **self._get_params(),
            "fields": "permalink_url,status"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            permalink = data.get("permalink_url")
            status_data = data.get("status", {})
            video_status = status_data.get("video_status", "unknown")
            
            print(f"   Video status: {video_status}")
            
            if permalink:
                print(f"✅ Video URL retrieved: {permalink}")
                return permalink
            else:
                print(f"⚠️ No permalink yet, status: {video_status}")
        
        # Fallback URL
        fallback_url = f"https://www.facebook.com/{self.page_id}/videos/{video_id}"
        print(f"⚠️ Using fallback URL: {fallback_url}")
        return fallback_url
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Main upload method - SIMPLIFIED (non-resumable)"""
        
        print("\n" + "="*60)
        print("👥 FACEBOOK REELS UPLOAD")
        print("="*60)
        
        # Validate credentials
        if not self.access_token or not self.page_id:
            return {
                "success": False,
                "error": "Missing Facebook credentials (FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID)",
                "platform": "facebook"
            }
        
        # Validate video file
        if not os.path.exists(video_path):
            return {
                "success": False,
                "error": f"Video file not found: {video_path}",
                "platform": "facebook"
            }
        
        video_size = os.path.getsize(video_path)
        if video_size < 1000:
            return {
                "success": False,
                "error": "Video file is too small or corrupted",
                "platform": "facebook"
            }
        
        # Check file size limit (1GB for non-resumable)
        if video_size > 1024 * 1024 * 1024:
            return {
                "success": False,
                "error": f"Video too large ({video_size/(1024*1024*1024):.2f}GB). Max 1GB for simple upload.",
                "platform": "facebook"
            }
        
        # Validate credentials
        if not self._validate_credentials():
            return {
                "success": False,
                "error": "Facebook credential validation failed",
                "platform": "facebook"
            }
        
        try:
            # Upload video directly (single request)
            print("\n" + "-"*60)
            print("UPLOAD: Single-request method")
            print("-"*60)
            video_id = self._upload_video_simple(video_path, metadata)
            
            # Wait a bit for processing
            print("\n⏳ Waiting for video processing...")
            time.sleep(5)
            
            # Get permalink
            print("\n" + "-"*60)
            print("RETRIEVE: Get Video URL")
            print("-"*60)
            permalink = self._get_video_url(video_id)
            
            print("\n" + "="*60)
            print("✅ FACEBOOK UPLOAD COMPLETE!")
            print("="*60)
            print(f"Video ID: {video_id}")
            print(f"URL: {permalink}")
            print("="*60 + "\n")
            
            return {
                "success": True,
                "video_id": video_id,
                "url": permalink,
                "platform": "facebook",
                "uploaded_at": datetime.now().isoformat(),
                "metadata": {
                    "title": metadata.get("title", "")[:100],
                    "description_length": len(metadata.get("description", "")),
                    "hashtags_count": len(metadata.get("hashtags", []))
                }
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = self._parse_error(e.response) if e.response else str(e)
            print(f"\n❌ HTTP Error: {error_msg}\n")
            traceback.print_exc()
            
            return {
                "success": False,
                "error": f"HTTP error: {error_msg}",
                "platform": "facebook",
                "traceback": traceback.format_exc()
            }
            
        except Exception as e:
            print(f"\n❌ Upload Error: {e}\n")
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "platform": "facebook",
                "traceback": traceback.format_exc()
            }


def main():
    """Standalone execution for testing"""
    try:
        # Load metadata
        script_path = os.path.join(TMP, "script.json")
        if not os.path.exists(script_path):
            print(f"❌ Script file not found: {script_path}")
            return
        
        with open(script_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Get video path
        video_path = os.path.join(TMP, "short.mp4")
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            return
        
        # Create uploader and upload
        uploader = FacebookUploader()
        result = uploader.upload(video_path, metadata)
        
        # Print result
        if result["success"]:
            print(f"\n✅ SUCCESS!")
            print(f"   URL: {result['url']}")
            print(f"   Video ID: {result['video_id']}")
        else:
            print(f"\n❌ FAILED!")
            print(f"   Error: {result['error']}")
            if "traceback" in result:
                print(f"\n📋 Traceback:\n{result['traceback']}")
        
        # Save result to log
        log_file = os.path.join(TMP, "facebook_upload_log.json")
        with open(log_file, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"\n💾 Result saved to: {log_file}")
            
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()