import os
import sys

REQUIRED_SECRETS = {
    "GEMINI_API_KEY": "AI content generation",
    "HUGGINGFACE_API_KEY": "Image generation", 
    "GOOGLE_CLIENT_ID": "YouTube upload",
    "GOOGLE_CLIENT_SECRET": "YouTube upload",
    "GOOGLE_REFRESH_TOKEN": "YouTube upload"
}

print("🔐 Validating required secrets...")

missing = []
for secret, purpose in REQUIRED_SECRETS.items():
    value = os.getenv(secret)
    if not value or len(value.strip()) == 0:
        missing.append(f"  ❌ {secret} (needed for: {purpose})")
        print(f"❌ Missing: {secret}")
    else:
        # Don't print actual values, just confirm presence
        print(f"✅ Found: {secret} ({len(value)} chars)")

if missing:
    print("\n❌ VALIDATION FAILED - Missing required secrets:")
    for m in missing:
        print(m)
    print("\n💡 Add these secrets in: Settings → Secrets → Actions")
    sys.exit(1)

print("\n✅ All required secrets validated successfully")