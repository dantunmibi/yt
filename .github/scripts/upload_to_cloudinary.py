# .github/scripts/upload_to_cloudinary.py
import os
import sys
import glob

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

def find_video_file():
    """Find the actual video file (handles renamed files)"""
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    TMP = os.path.join(workspace, "tmp")
    
    # Priority 1: Check environment variable (set by workflow)
    env_video = os.getenv("VIDEO_TO_UPLOAD")
    if env_video and os.path.exists(env_video):
        print(f"✅ Using video from environment: {env_video}")
        return env_video
    
    # Priority 2: Check for original short.mp4
    original_path = os.path.join(TMP, "short.mp4")
    if os.path.exists(original_path):
        print(f"✅ Using original video: {original_path}")
        return original_path
    
    # Priority 3: Find ANY .mp4 file in tmp (renamed video)
    mp4_files = glob.glob(os.path.join(TMP, "*.mp4"))
    if mp4_files:
        # Use the most recently modified file
        latest_video = max(mp4_files, key=os.path.getmtime)
        print(f"✅ Using renamed video: {latest_video}")
        return latest_video
    
    # No video found
    print(f"❌ No video file found in {TMP}")
    print(f"   Searched for:")
    print(f"   - Environment: {env_video}")
    print(f"   - Original: {original_path}")
    print(f"   - Any .mp4: {mp4_files}")
    return None

def upload_video_for_makecom(video_path):
    """Upload video to Cloudinary and return public URL"""
    
    print("📤 Uploading video to Cloudinary for Make.com...")
    
    if not video_path:
        raise Exception("No video path provided")
    
    if not os.path.exists(video_path):
        raise Exception(f"Video file doesn't exist: {video_path}")
    
    # Get file size
    file_size = os.path.getsize(video_path)
    if file_size < 100000:  # Less than 100KB
        raise Exception(f"Video file too small ({file_size} bytes), likely corrupted")
    
    print(f"   Video: {os.path.basename(video_path)}")
    print(f"   Size: {file_size / (1024*1024):.2f} MB")
    
    try:
        # Get video name without extension for public_id
        video_basename = os.path.basename(video_path)
        video_name = os.path.splitext(video_basename)[0]
        
        # Clean the name for Cloudinary (remove special chars)
        import re
        clean_name = re.sub(r'[^\w\s-]', '', video_name).strip().replace(' ', '_')
        
        # Upload video with specific settings for Instagram/TikTok compatibility
        result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",
            folder="makecom_videos",
            public_id=f"{clean_name}_{os.getenv('GITHUB_RUN_NUMBER', 'test')}",
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
        print(f"   Public ID: {result.get('public_id')}")
        
        return video_url
        
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {e}")
        raise

if __name__ == "__main__":
    # Get workspace path
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    TMP = os.path.join(workspace, "tmp")
    
    # Find the actual video file
    video_path = find_video_file()
    
    if not video_path:
        print(f"❌ No video file found!")
        sys.exit(1)
    
    # Upload and get URL
    url = upload_video_for_makecom(video_path)
    
    # Write URL to file for next step
    output_file = os.path.join(TMP, "video_url.txt")
    with open(output_file, "w") as f:
        f.write(url)
    
    print(f"✅ URL saved to: {output_file}")