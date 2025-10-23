# .github/scripts/upload_to_cloudinary.py
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import cloudinary
import cloudinary.uploader

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

def upload_video_for_makecom(video_path):
    """Upload video to Cloudinary and return public URL"""
    
    print("📤 Uploading video to Cloudinary for Make.com...")
    
    try:
        # Upload video with specific settings for Instagram/TikTok compatibility
        result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",
            folder="makecom_videos",
            public_id=f"video_{os.getenv('GITHUB_RUN_NUMBER', 'test')}",
            overwrite=True,
            invalidate=True,
            # Ensure format compatibility
            format="mp4",
            # Keep original quality
            quality="auto"
        )
        
        video_url = result.get("secure_url")
        
        print(f"✅ Video uploaded to Cloudinary")
        print(f"   URL: {video_url}")
        print(f"   Duration: {result.get('duration', 0)} seconds")
        print(f"   Size: {result.get('bytes', 0) / (1024*1024):.2f} MB")
        
        return video_url
        
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {e}")
        raise

if __name__ == "__main__":
    # Get workspace path
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    TMP = os.path.join(workspace, "tmp")
    video_path = os.path.join(TMP, "short.mp4")
    
    if not os.path.exists(video_path):
        print(f"❌ Video not found at: {video_path}")
        sys.exit(1)
    
    # Upload and get URL
    url = upload_video_for_makecom(video_path)
    
    # Write URL to file for next step
    output_file = os.path.join(TMP, "video_url.txt")
    with open(output_file, "w") as f:
        f.write(url)
    
    print(f"✅ URL saved to: {output_file}")