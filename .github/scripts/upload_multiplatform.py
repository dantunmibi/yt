# .github/scripts/upload_multiplatform.py
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import sys
import time
import traceback

input_platforms = os.getenv("PLATFORMS", "")
force_all = os.getenv("FORCE_ALL", "false").lower() == "true"

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")
PLATFORM_CONFIG = os.path.join(TMP, "platform_config.json")

# Import individual platform uploaders
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

class PlatformUploader:
    """Base class for platform uploaders"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.enabled = self._check_enabled()
        self.credentials = self._load_credentials()
    
    def _check_enabled(self) -> bool:
        """Check if platform is enabled in config"""
        config = self._load_platform_config()
        return config.get(self.platform_name, {}).get("enabled", False)
    
    def _load_platform_config(self) -> dict:
        """Load platform configuration"""
        if os.path.exists(PLATFORM_CONFIG):
            try:
                with open(PLATFORM_CONFIG, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Default configuration for all platforms"""
        return {
            "youtube": {
                "enabled": True,
                "priority": 1,
                "auto_playlist": True,
                "privacy": "public"
            },
            "facebook": {
                "enabled": True,
                "priority": 2,
                "privacy": "PUBLIC"
            },
            "instagram": {
                "enabled": False,
                "priority": 3,
                "is_reel": True
            },
            "tiktok": {
                "enabled": False,
                "priority": 4,
                "privacy": "public",
                "allow_comments": True,
                "allow_duet": True,
                "allow_stitch": True
            }
        }
    
    def _load_credentials(self) -> dict:
        """Load platform-specific credentials from environment"""
        return {}
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        """Upload to platform - to be implemented by subclasses"""
        raise NotImplementedError


class YouTubeUploader(PlatformUploader):
    """YouTube upload handler"""
    
    def __init__(self):
        super().__init__("youtube")
    
    def _load_credentials(self) -> dict:
        return {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        """Use existing YouTube upload logic"""
        if not self.enabled:
            print(f"⏭️ YouTube upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ YouTube credentials missing")
            return None
        
        try:
            print("\n" + "="*60)
            print("📺 YOUTUBE UPLOAD")
            print("="*60)
            
            # Store original video path for other platforms
            original_video = video_path
            
            # Import and execute YouTube upload module
            import upload_youtube
            
            # CRITICAL: Restore the original video path if YouTube renamed it
            # This ensures other platforms can find the video
            import glob
            renamed_videos = glob.glob(os.path.join(TMP, "*_AI_*.mp4"))
            if renamed_videos and not os.path.exists(original_video):
                # YouTube renamed it, copy it back
                import shutil
                renamed_video = renamed_videos[0]
                if os.path.exists(renamed_video):
                    shutil.copy2(renamed_video, original_video)
                    print(f"📋 Restored original video path for other platforms")
            
            # The module executes automatically and saves to upload_history.json
            # Read the result from the log
            if os.path.exists(UPLOAD_LOG):
                with open(UPLOAD_LOG, 'r') as f:
                    history = json.load(f)
                    if history:
                        latest = history[-1]
                        return {
                            "platform": "youtube",
                            "success": True,
                            "video_id": latest.get("video_id"),
                            "url": latest.get("shorts_url"),
                            "uploaded_at": datetime.now().isoformat()
                        }
            
            return {
                "platform": "youtube",
                "success": False,
                "error": "Upload completed but couldn't read result",
                "uploaded_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ YouTube upload failed: {e}")
            return {
                "platform": "youtube",
                "success": False,
                "error": str(e),
                "uploaded_at": datetime.now().isoformat()
            }


class FacebookUploader(PlatformUploader):
    """Facebook Reels upload handler"""
    
    def __init__(self):
        super().__init__("facebook")
    
    def _load_credentials(self) -> dict:
        return {
            "page_id": os.getenv("FACEBOOK_PAGE_ID"),
            "access_token": os.getenv("FACEBOOK_ACCESS_TOKEN")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        if not self.enabled:
            print(f"⏭️ Facebook upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ Facebook credentials missing (FACEBOOK_PAGE_ID or FACEBOOK_ACCESS_TOKEN)")
            return None
        
        try:
            # Import the Facebook uploader module
            from upload_facebook import FacebookUploader as FBUploader
            
            uploader = FBUploader()
            result = uploader.upload(video_path, metadata)
            
            return result
            
        except ImportError as e:
            print(f"❌ Failed to import Facebook uploader: {e}")
            return {
                "platform": "facebook",
                "success": False,
                "error": f"Import error: {e}",
                "uploaded_at": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Facebook upload error: {e}")
            return {
                "platform": "facebook",
                "success": False,
                "error": str(e),
                "uploaded_at": datetime.now().isoformat()
            }


class InstagramUploader(PlatformUploader):
    """Instagram Reels upload handler"""
    
    def __init__(self):
        super().__init__("instagram")
    
    def _load_credentials(self) -> dict:
        return {
            "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN"),
            "account_id": os.getenv("INSTAGRAM_ACCOUNT_ID"),
            "temp_video_url": os.getenv("TEMP_VIDEO_URL")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        if not self.enabled:
            print(f"⏭️ Instagram upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ Instagram credentials missing")
            print(f"   Required: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID, TEMP_VIDEO_URL")
            return None
        
        try:
            from upload_instagram import InstagramUploader as IGUploader
            
            uploader = IGUploader()
            result = uploader.upload(video_path, metadata)
            
            return result
            
        except ImportError as e:
            print(f"❌ Failed to import Instagram uploader: {e}")
            return {
                "platform": "instagram",
                "success": False,
                "error": f"Import error: {e}",
                "uploaded_at": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Instagram upload error: {e}")
            return {
                "platform": "instagram",
                "success": False,
                "error": str(e),
                "uploaded_at": datetime.now().isoformat()
            }


class TikTokUploader(PlatformUploader):
    """TikTok upload handler"""
    
    def __init__(self):
        super().__init__("tiktok")
    
    def _load_credentials(self) -> dict:
        return {
            "access_token": os.getenv("TIKTOK_ACCESS_TOKEN")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        if not self.enabled:
            print(f"⏭️ TikTok upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ TikTok credentials missing (TIKTOK_ACCESS_TOKEN)")
            return None
        
        try:
            from upload_tiktok import TikTokUploader as TTUploader
            
            uploader = TTUploader()
            result = uploader.upload(video_path, metadata)
            
            return result
            
        except ImportError as e:
            print(f"❌ Failed to import TikTok uploader: {e}")
            return {
                "platform": "tiktok",
                "success": False,
                "error": f"Import error: {e}",
                "uploaded_at": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ TikTok upload error: {e}")
            return {
                "platform": "tiktok",
                "success": False,
                "error": str(e),
                "uploaded_at": datetime.now().isoformat()
            }


class MultiPlatformManager:
    """Manages uploads across multiple platforms"""
    
    def __init__(self):
        self.uploaders = {
            "youtube": YouTubeUploader(),
            "facebook": FacebookUploader(),
            "instagram": InstagramUploader(),
            "tiktok": TikTokUploader()
        }
        self.results = []
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platforms sorted by priority, filtered by input if provided"""
        config = self.uploaders["youtube"]._load_platform_config()
        
        enabled = []
        for platform, uploader in self.uploaders.items():
            if uploader.enabled:
                priority = config.get(platform, {}).get("priority", 99)
                enabled.append((priority, platform))
        
        enabled.sort()
        enabled_platforms = [p for _, p in enabled]

        # Filter by workflow input if provided and force_all is False
        input_platforms = os.getenv("PLATFORMS", "")
        force_all = os.getenv("FORCE_ALL", "false").lower() == "true"

        if input_platforms and not force_all:
            requested = [p.strip().lower() for p in input_platforms.split(",")]
            enabled_platforms = [p for p in enabled_platforms if p in requested]

        return enabled_platforms

    
    def upload_to_all(self, video_path: str, metadata: dict) -> List[dict]:
        """Upload to all enabled platforms"""
        print("\n" + "="*60)
        print("🚀 MULTI-PLATFORM UPLOAD STARTING")
        print("="*60)
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        enabled_platforms = self.get_enabled_platforms()
        
        if not enabled_platforms:
            print("⚠️ No platforms enabled!")
            return []
        
        print(f"📋 Enabled platforms ({len(enabled_platforms)}): {', '.join(enabled_platforms)}")
        print(f"📹 Video: {os.path.basename(video_path)} ({os.path.getsize(video_path)/(1024*1024):.2f} MB)")
        print(f"📝 Title: {metadata.get('title', 'N/A')[:60]}...")

        for i, platform in enumerate(enabled_platforms, 1):
            uploader = self.uploaders.get(platform)
            
            if not uploader:
                continue
            
            print(f"\n{'='*60}")
            print(f"📤 [{i}/{len(enabled_platforms)}] Uploading to {platform.upper()}")
            print(f"{'='*60}")
            
            # Find the actual video file (YouTube may have renamed it)
            current_video_path = video_path
            if not os.path.exists(current_video_path):
                import glob
                possible_videos = glob.glob(os.path.join(TMP, "*.mp4"))
                if possible_videos:
                    current_video_path = max(possible_videos, key=os.path.getmtime)
                    print(f"⚠️ Original video not found, using: {os.path.basename(current_video_path)}")
            current_video_path = os.path.abspath(current_video_path)

            try:
                # Retry logic for Facebook
                attempts = 3 if platform == "facebook" else 1
                for attempt in range(1, attempts + 1):
                    try:
                        result = uploader.upload(current_video_path, metadata)
                        if result:
                            self.results.append(result)
                        break  # Success, exit retry loop
                    except Exception as e:
                        print(f"⚠️ Attempt {attempt} failed for {platform.upper()}: {e}")
                        traceback.print_exc()
                        if attempt < attempts:
                            print("⏳ Retrying in 5 seconds...")
                            time.sleep(5)
                        else:
                            # All retries failed, log as failed
                            self.results.append({
                                "platform": platform,
                                "success": False,
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                                "uploaded_at": datetime.now().isoformat()
                            })

                # Print summary for this platform
                if result:
                    if result.get("success"):
                        print(f"\n✅ {platform.upper()} upload successful!")
                        if result.get("url"):
                            print(f"   🔗 URL: {result['url']}")
                        if result.get("video_id"):
                            print(f"   🆔 Video ID: {result['video_id']}")
                    else:
                        print(f"\n❌ {platform.upper()} upload failed!")
                        print(f"   Error: {result.get('error', 'Unknown error')}")
                else:
                    print(f"\n⚠️ {platform.upper()} returned no result (likely skipped)")

            except Exception as e:
                print(f"\n❌ {platform.upper()} upload exception: {e}")
                traceback.print_exc()
                self.results.append({
                    "platform": platform,
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "uploaded_at": datetime.now().isoformat()
                })

        
        return self.results
    
    def save_results(self):
        """Save upload results to log"""
        log_file = os.path.join(TMP, "multiplatform_log.json")
        
        existing_log = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    existing_log = json.load(f)
            except:
                existing_log = []
        
        existing_log.append({
            "timestamp": datetime.now().isoformat(),
            "results": self.results
        })
        
        # Keep last 100 uploads
        existing_log = existing_log[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(existing_log, f, indent=2)
        
        print(f"\n💾 Results saved to {log_file}")
    
    def print_summary(self):
        """Print upload summary"""
        print("\n" + "="*60)
        print("📊 MULTI-PLATFORM UPLOAD SUMMARY")
        print("="*60)
        
        successful = [r for r in self.results if r.get("success")]
        failed = [r for r in self.results if not r.get("success")]
        skipped = len(self.uploaders) - len(self.results)
        
        print(f"\n📈 Statistics:")
        print(f"   Total platforms attempted: {len(self.results)}")
        print(f"   ✅ Successful: {len(successful)}")
        print(f"   ❌ Failed: {len(failed)}")
        print(f"   ⏭️  Skipped/Disabled: {skipped}")
        
        if successful:
            print(f"\n✅ Successful Uploads:")
            for result in successful:
                platform = result.get("platform", "unknown").upper()
                url = result.get("url", "N/A")
                video_id = result.get("video_id", "N/A")
                print(f"\n   🎯 {platform}")
                print(f"      URL: {url}")
                print(f"      Video ID: {video_id}")
        
        if failed:
            print(f"\n❌ Failed Uploads:")
            for result in failed:
                platform = result.get("platform", "unknown").upper()
                error = result.get("error", "Unknown error")
                print(f"\n   ⚠️  {platform}")
                print(f"      Error: {error[:200]}")
        
        print("\n" + "="*60)
        
        # Exit with error if all uploads failed
        if len(successful) == 0 and len(self.results) > 0:
            print("❌ All uploads failed!")
            return False
        
        return True


def main():
    """Main execution"""
    try:
        # Load metadata
        script_path = os.path.join(TMP, "script.json")
        if not os.path.exists(script_path):
            print(f"❌ Script file not found: {script_path}")
            raise FileNotFoundError(f"script.json not found at {script_path}")
        
        with open(script_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        print(f"📄 Loaded metadata:")
        print(f"   Title: {metadata.get('title', 'N/A')}")
        print(f"   Topic: {metadata.get('topic', 'N/A')}")
        print(f"   Hashtags: {len(metadata.get('hashtags', []))} tags")
        
        # Validate video exists
        if not os.path.exists(VIDEO):
            raise FileNotFoundError(f"Video not found: {VIDEO}")
        
        # Create manager and upload
        manager = MultiPlatformManager()
        manager.upload_to_all(VIDEO, metadata)
        manager.save_results()
        
        # Print summary and exit with appropriate code
        success = manager.print_summary()
        
        if not success:
            sys.exit(1)
        
    except FileNotFoundError as e:
        print(f"\n❌ File Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()