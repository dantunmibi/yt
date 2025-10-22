# .github/scripts/upload_facebook.py
import os
import json
import time
from datetime import datetime
from typing import Optional, Dict
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"

class FacebookUploader:
    """Facebook Reels upload using Graph API v18.0"""
    
    def __init__(self):
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_version = "v18.0"
        self.api_base = f"https://graph.facebook.com/{self.api_version}"
        
        # Validate credentials
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
            url = f"{self.api_base}/me"
            params = self._get_params()
            params["fields"] = "id,name"
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ Facebook credentials valid for: {data.get('name', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Facebook credential validation failed: {e}")
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _init_upload(self, video_size: int) -> dict:
        """Initialize video upload session (Phase 1: START)"""
        
        url = f"{self.api_base}/{self.page_id}/video_reels"
        
        params = {
            **self._get_params(),
            "upload_phase": "start",
            "file_size": video_size
        }
        
        print(f"📤 Initializing Facebook upload session...")
        print(f"   Video size: {video_size / (1024*1024):.2f} MB")
        
        response = requests.post(url, params=params, timeout=30)
        
        if response.status_code != 200:
            error_msg = self._parse_error(response)
            raise Exception(f"Init upload failed: {error_msg}")
        
# After initializing upload
        data = response.json()

        # Make sure upload_session_id is returned
        if "video_id" not in data or "upload_url" not in data or "upload_session_id" not in data:
            raise Exception(f"Invalid init response: {data}")

        print(f"✅ Upload session initialized")
        print(f"   Video ID: {data['video_id']}")
        print(f"   Upload Session ID: {data['upload_session_id']}")

        return data

        upload_session_id = init_response.get("upload_session_id")  # new
        self._upload_video(upload_url, video_path, video_id, upload_session_id)


    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _upload_video(self, upload_url: str, video_path: str, video_id: str, upload_session_id: str) -> bool:
        """Upload video file (Phase 2: TRANSFER)"""
        
        file_size = os.path.getsize(video_path)
        
        print(f"📤 Uploading video file...")
        print(f"   Path: {video_path}")
        print(f"   Size: {file_size / (1024*1024):.2f} MB")
        
        with open(video_path, 'rb') as video_file:
            files = {
                'video_file_chunk': (
                    os.path.basename(video_path),
                    video_file,
                    'video/mp4'
                )
            }
            
            params = {
                **self._get_params(),
                'upload_phase': 'transfer',
                'video_id': video_id,
                'start_offset': 0,
                'upload_session_id': upload_session_id
            }
            
            # Use the upload_url for transfer
            response = requests.post(
                upload_url,
                files=files,
                data=params,
                timeout=300  # 5 minutes for large files
            )
            
            if response.status_code not in [200, 201]:
                error_msg = self._parse_error(response)
                raise Exception(f"Video upload failed: {error_msg}")
            
            print(f"✅ Video uploaded successfully")
            return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _finish_upload(self, video_id: str, metadata: dict) -> dict:
        """Finalize upload and publish (Phase 3: FINISH)"""
        
        url = f"{self.api_base}/{self.page_id}/video_reels"
        
        # Prepare description with hashtags
        description = metadata.get("description", "")
        hashtags = metadata.get("hashtags", [])
        
        # Combine description and hashtags (Facebook limit: 1000 chars for Reels)
        full_description = description
        if hashtags:
            hashtag_str = " ".join(hashtags[:30])  # Max 30 hashtags
            full_description = f"{description}\n\n{hashtag_str}"
        
        # Truncate if too long
        full_description = full_description[:1000]
        
        params = {
            **self._get_params(),
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",  # or "DRAFT" for unpublished
            "description": full_description,
            "title": metadata.get("title", "")[:100]  # Facebook title limit
        }
        
        print(f"📢 Publishing to Facebook Reels...")
        print(f"   Title: {params['title']}")
        print(f"   Description length: {len(full_description)} chars")
        
        response = requests.post(url, params=params, timeout=30)
        
        if response.status_code not in [200, 201]:
            error_msg = self._parse_error(response)
            raise Exception(f"Publish failed: {error_msg}")
        
        data = response.json()
        print(f"✅ Published successfully!")
        
        return data
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _get_video_url(self, video_id: str, max_attempts: int = 10) -> str:
        """Get video permalink (may take time to process)"""
        
        print(f"🔗 Fetching video URL...")
        
        for attempt in range(max_attempts):
            url = f"{self.api_base}/{video_id}"
            params = {
                **self._get_params(),
                "fields": "permalink_url,status"
            }
            
            try:
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    permalink = data.get("permalink_url")
                    status = data.get("status", {})
                    
                    if permalink:
                        print(f"✅ Video URL retrieved: {permalink}")
                        return permalink
                    else:
                        print(f"⏳ Attempt {attempt + 1}/{max_attempts}: Video still processing...")
                        time.sleep(5)
                else:
                    print(f"⚠️ Attempt {attempt + 1}/{max_attempts}: Status {response.status_code}")
                    time.sleep(5)
                    
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1}/{max_attempts}: {e}")
                time.sleep(5)
        
        # Return fallback URL if permalink unavailable
        fallback_url = f"https://www.facebook.com/{self.page_id}/videos/{video_id}"
        print(f"⚠️ Using fallback URL: {fallback_url}")
        return fallback_url
    
    def _parse_error(self, response: requests.Response) -> str:
        """Parse Facebook API error response"""
        try:
            error_data = response.json()
            error = error_data.get("error", {})
            
            error_type = error.get("type", "Unknown")
            error_message = error.get("message", str(response.text))
            error_code = error.get("code", response.status_code)
            
            return f"[{error_code}] {error_type}: {error_message}"
        except:
            return f"Status {response.status_code}: {response.text[:200]}"
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Main upload method - coordinates all phases"""
        
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
        if video_size < 1000:  # Less than 1KB
            return {
                "success": False,
                "error": "Video file is too small or corrupted",
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
            # Phase 1: Initialize upload
            init_response = self._init_upload(video_size)
            
            video_id = init_response.get("video_id")
            upload_url = init_response.get("upload_url")
            
            if not video_id or not upload_url:
                return {
                    "success": False,
                    "error": "Failed to initialize upload session",
                    "platform": "facebook"
                }
            
            # Phase 2: Upload video
            self._upload_video(upload_url, video_path, video_id)
            
            # Phase 3: Finish and publish
            finish_response = self._finish_upload(video_id, metadata)
            
            # Get permalink (with retry logic)
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
            
            return {
                "success": False,
                "error": f"HTTP error: {error_msg}",
                "platform": "facebook"
            }
            
        except Exception as e:
            print(f"\n❌ Upload Error: {e}\n")
            
            return {
                "success": False,
                "error": str(e),
                "platform": "facebook"
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