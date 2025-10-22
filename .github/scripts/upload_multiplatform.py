# .github/scripts/upload_multiplatform.py
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import importlib.util

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
VIDEO = os.path.join(TMP, "short.mp4")
THUMB = os.path.join(TMP, "thumbnail.png")
UPLOAD_LOG = os.path.join(TMP, "upload_history.json")
PLATFORM_CONFIG = os.path.join(TMP, "platform_config.json")

# Platform-specific upload modules
PLATFORM_MODULES = {
    "youtube": ".github/scripts/upload_youtube.py",
    "tiktok": ".github/scripts/upload_tiktok.py",
    "instagram": ".github/scripts/upload_instagram.py",
    "facebook": ".github/scripts/upload_facebook.py"
}

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
            "tiktok": {
                "enabled": False,
                "priority": 2,
                "privacy": "public",
                "allow_comments": True,
                "allow_duet": True,
                "allow_stitch": True
            },
            "instagram": {
                "enabled": False,
                "priority": 3,
                "is_reel": True
            },
            "facebook": {
                "enabled": False,
                "priority": 4,
                "privacy": "PUBLIC"
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
            # Import and run existing YouTube upload
            spec = importlib.util.spec_from_file_location("upload_youtube", PLATFORM_MODULES["youtube"])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # The existing script already uploads, we just need to capture the result
            # Read from upload_history.json to get the video_id
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
        except Exception as e:
            print(f"❌ YouTube upload failed: {e}")
            return {
                "platform": "youtube",
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
            "session_id": os.getenv("TIKTOK_SESSION_ID"),
            "access_token": os.getenv("TIKTOK_ACCESS_TOKEN")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        if not self.enabled:
            print(f"⏭️ TikTok upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ TikTok credentials missing")
            return None
        
        print(f"📱 Uploading to TikTok...")
        # TikTok upload implementation would go here
        # For now, return placeholder
        return {
            "platform": "tiktok",
            "success": False,
            "error": "Not implemented yet",
            "uploaded_at": datetime.now().isoformat()
        }


class InstagramUploader(PlatformUploader):
    """Instagram Reels upload handler"""
    
    def __init__(self):
        super().__init__("instagram")
    
    def _load_credentials(self) -> dict:
        return {
            "username": os.getenv("INSTAGRAM_USERNAME"),
            "password": os.getenv("INSTAGRAM_PASSWORD"),
            "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN")
        }
    
    def upload(self, video_path: str, metadata: dict) -> Optional[dict]:
        if not self.enabled:
            print(f"⏭️ Instagram upload disabled")
            return None
        
        if not all(self.credentials.values()):
            print(f"⚠️ Instagram credentials missing")
            return None
        
        print(f"📸 Uploading to Instagram Reels...")
        # Instagram upload implementation would go here
        return {
            "platform": "instagram",
            "success": False,
            "error": "Not implemented yet",
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
            print(f"⚠️ Facebook credentials missing")
            return None
        
        print(f"👥 Uploading to Facebook Reels...")
        # Facebook upload implementation would go here
        return {
            "platform": "facebook",
            "success": False,
            "error": "Not implemented yet",
            "uploaded_at": datetime.now().isoformat()
        }


class MultiPlatformManager:
    """Manages uploads across multiple platforms"""
    
    def __init__(self):
        self.uploaders = {
            "youtube": YouTubeUploader(),
            "tiktok": TikTokUploader(),
            "instagram": InstagramUploader(),
            "facebook": FacebookUploader()
        }
        self.results = []
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platforms sorted by priority"""
        config = self.uploaders["youtube"]._load_platform_config()
        
        enabled = []
        for platform, uploader in self.uploaders.items():
            if uploader.enabled:
                priority = config.get(platform, {}).get("priority", 99)
                enabled.append((priority, platform))
        
        enabled.sort()
        return [p for _, p in enabled]
    
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
        
        print(f"📋 Enabled platforms: {', '.join(enabled_platforms)}")
        
        for platform in enabled_platforms:
            uploader = self.uploaders.get(platform)
            
            if not uploader:
                continue
            
            print(f"\n{'='*60}")
            print(f"📤 Uploading to {platform.upper()}")
            print(f"{'='*60}")
            
            try:
                result = uploader.upload(video_path, metadata)
                
                if result:
                    self.results.append(result)
                    
                    if result.get("success"):
                        print(f"✅ {platform.upper()} upload successful!")
                        if result.get("url"):
                            print(f"   URL: {result['url']}")
                    else:
                        print(f"❌ {platform.upper()} upload failed: {result.get('error')}")
                        
            except Exception as e:
                print(f"❌ {platform.upper()} upload error: {e}")
                self.results.append({
                    "platform": platform,
                    "success": False,
                    "error": str(e),
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
        print("📊 UPLOAD SUMMARY")
        print("="*60)
        
        successful = [r for r in self.results if r.get("success")]
        failed = [r for r in self.results if not r.get("success")]
        
        print(f"Total platforms: {len(self.results)}")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        
        if successful:
            print(f"\n✅ Successful uploads:")
            for result in successful:
                platform = result.get("platform", "unknown").upper()
                url = result.get("url", "N/A")
                print(f"   • {platform}: {url}")
        
        if failed:
            print(f"\n❌ Failed uploads:")
            for result in failed:
                platform = result.get("platform", "unknown").upper()
                error = result.get("error", "Unknown error")
                print(f"   • {platform}: {error}")
        
        print("="*60)


def main():
    """Main execution"""
    # Load metadata
    try:
        with open(os.path.join(TMP, "script.json"), "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print("❌ script.json not found")
        raise
    
    # Validate video exists
    if not os.path.exists(VIDEO):
        raise FileNotFoundError(f"Video not found: {VIDEO}")
    
    # Create manager and upload
    manager = MultiPlatformManager()
    manager.upload_to_all(VIDEO, metadata)
    manager.save_results()
    manager.print_summary()


if __name__ == "__main__":
    main()