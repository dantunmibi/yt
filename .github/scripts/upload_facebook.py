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
    """Facebook Reels upload using Graph API v24.0"""
    
    def __init__(self):
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_version = "v24.0"
        self.api_base = f"https://graph.facebook.com/{self.api_version}"
        
        if not self.access_token:
            print("⚠️ FACEBOOK_ACCESS_TOKEN not found in environment")
        if not self.page_id:
            print("⚠️ FACEBOOK_PAGE_ID not found in environment")
    
    def _get_params(self):
        return {"access_token": self.access_token}
    
    def _validate_credentials(self) -> bool:
        """Validate that the Page access token works"""
        try:
            url = f"{self.api_base}/{self.page_id}"
            params = {**self._get_params(), "fields": "id,name"}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            print(f"✅ Token valid for Page: {data.get('name')} ({data.get('id')})")
            return True
        except Exception as e:
            print(f"❌ Token validation failed: {e}")
            return False
    
    def _init_upload(self, video_size: int) -> dict:
        """Initialize video upload session (Phase 1: START)"""
        url = f"{self.api_base}/{self.page_id}/video_reels"
        params = {
            **self._get_params(),
            "upload_phase": "start"
        }

        print(f"📤 Initializing Facebook upload session...")
        print(f"   API URL: {url}")
        print(f"   Video size: {video_size / (1024*1024):.2f} MB")
        print(f"   Page ID: {self.page_id}")

        try:
            response = requests.post(url, params=params, timeout=30)
            print(f"   Response status: {response.status_code}")
            print(f"   Response headers: {dict(response.headers)}")

            if response.status_code != 200:
                error_msg = self._parse_error(response)
                print(f"   ❌ Error response: {error_msg}")
                print(f"   Full response: {response.text}")
                raise Exception(f"Init upload failed: {error_msg}")

            data = response.json()
            print(f"   Raw response data: {json.dumps(data, indent=2)}")

            video_id = data.get("video_id")
            upload_url = data.get("upload_url")  # presigned rupload URL
            upload_session_id = data.get("upload_session_id", video_id)
            start_offset = data.get("start_offset", 0)
            end_offset = data.get("end_offset", video_size)

            if not video_id or not upload_url:
                raise Exception(f"Invalid init response - missing fields: {data}")

            print(f"✅ Upload session initialized")
            print(f"   Video ID: {video_id}")
            print(f"   Upload URL: {upload_url}")
            print(f"   Upload Session ID: {upload_session_id}")
            print(f"   Start offset: {start_offset}")
            print(f"   End offset: {end_offset}")

            return {
                "video_id": video_id,
                "upload_url": upload_url,
                "upload_session_id": upload_session_id,
                "start_offset": start_offset,
                "end_offset": end_offset
            }

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request exception: {e}")
            traceback.print_exc()
            raise
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            traceback.print_exc()
            raise


    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _upload_video(self, video_path: str, video_id: str, upload_session_id: str, start_offset: int = 0, upload_url: Optional[str] = None) -> bool:
        """Upload video file to rupload URL (Phase 2: TRANSFER)"""
        file_size = os.path.getsize(video_path)

        print(f"📤 Uploading video file...")
        print(f"   Path: {video_path}")
        print(f"   Size: {file_size / (1024*1024):.2f} MB")
        print(f"   Start offset: {start_offset}")
        if not upload_url:
            raise Exception("No upload_url provided for transfer phase")

        # Use PUT to the presigned rupload URL. Add Authorization header per docs.
        headers = {
            "Authorization": f"OAuth {self.access_token}",
            "Content-Type": "application/octet-stream",
            "Offset": str(start_offset),
            "File-Size": str(file_size)
        }

        try:
            with open(video_path, 'rb') as video_file:
                # PUT the entire file (small files ok). For very large files you can implement chunked/resume with offsets.
                resp = requests.put(upload_url, data=video_file, headers=headers, timeout=300)
            
            # rupload returns ok as 200/201; treat anything else as failure
            if resp.status_code not in [200, 201]:
                error_msg = self._parse_error(resp)
                print(f"   ❌ Upload failed: {error_msg}")
                print(f"   Full response: {resp.text}")
                raise Exception(f"Video upload failed: {error_msg}")

            print(f"✅ Video uploaded successfully to rupload host")
            return True

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request exception during upload: {e}")
            traceback.print_exc()
            raise
        except Exception as e:
            print(f"   ❌ Unexpected upload error: {e}")
            traceback.print_exc()
            raise

    
    def _finish_upload(self, video_id: str, metadata: dict):
        """Finish and publish (Phase 3)"""
        url = f"{self.api_base}/{self.page_id}/video_reels"
        desc = metadata.get("description", "")
        tags = metadata.get("hashtags", [])
        if tags:
            desc = f"{desc}\n\n{' '.join(tags[:30])}"
        desc = desc[:1000]
        params = {
            **self._get_params(),
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": desc,
            "title": metadata.get("title", "")[:100]
        }
        print(f"📢 Publishing Reel…")
        r = requests.post(url, params=params, timeout=60)
        if r.status_code not in [200, 201]:
            raise Exception(f"Publish failed: {r.text}")
        print(f"✅ Reel published.")
        return r.json()
    
    def upload(self, video_path: str, metadata: dict) -> dict:
        """Full upload sequence"""
        print("\n" + "="*60)
        print("🎬 FACEBOOK REELS UPLOAD")
        print("="*60)

        if not os.path.exists(video_path):
            return {"success": False, "error": f"File not found: {video_path}"}
        if not self._validate_credentials():
            return {"success": False, "error": "Invalid token or page"}

        try:
            # 1️⃣ Phase 1: START (initialize upload session)
            video_size = os.path.getsize(video_path)
            init_data = self._init_upload(video_size)
            upload_url = init_data["upload_url"]
            video_id = init_data["video_id"]
            upload_session_id = init_data.get("upload_session_id", video_id)
            start_offset = init_data.get("start_offset", 0)

            # 2️⃣ Phase 2: TRANSFER (upload binary file)
            self._upload_video(
                video_path=video_path,
                video_id=video_id,
                upload_session_id=upload_session_id,
                start_offset=start_offset,
                upload_url=upload_url
            )

            # 3️⃣ Phase 3: FINISH (publish the reel)
            result = self._finish_upload(video_id, metadata)
            video_link = f"https://www.facebook.com/{self.page_id}/videos/{video_id}"
            print(f"✅ Done! {video_link}")

            return {"success": True, "video_id": video_id, "url": video_link}

        except Exception as e:
            print(f"❌ Upload failed: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}



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