"""
ONE-TIME MIGRATION SCRIPT
Converts existing content_performance.json from old structure to new unified structure.
Run this ONCE locally or via workflow before running backfill again.

OLD structure:
  'completion_rate': 49.6
  'views': 380

NEW structure:
  'completion_rate_24h': 49.6
  'views_24h': 380
  'status': 'analytics_available'
  'analytics_fetched_at': '2025-11-07T...'
"""

import os
import json
from datetime import datetime
import pytz

TMP = os.getenv("GITHUB_WORKSPACE", ".") + "/tmp"
PERFORMANCE_FILE = os.path.join(TMP, "content_performance.json")
BACKUP_FILE = os.path.join(TMP, "content_performance_BACKUP.json")

def migrate_performance_data():
    """Migrate old structure to new unified structure"""
    
    print("=" * 60)
    print("🔄 MIGRATING PERFORMANCE DATA TO UNIFIED STRUCTURE")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(PERFORMANCE_FILE):
        print(f"⚠️ No existing performance file found at: {PERFORMANCE_FILE}")
        print("   This is OK if you haven't run backfill yet.")
        return
    
    # Load existing data
    with open(PERFORMANCE_FILE, 'r') as f:
        old_data = json.load(f)
    
    print(f"✅ Loaded existing performance data")
    
    # Create backup
    with open(BACKUP_FILE, 'w') as f:
        json.dump(old_data, f, indent=2)
    
    print(f"💾 Backup saved to: {BACKUP_FILE}")
    
    # Migrate each content type
    migrated_count = 0
    
    for content_type, data in old_data.items():
        print(f"\n📊 Migrating {content_type}...")
        
        for upload in data['uploads']:
            # Check if already migrated
            if 'completion_rate_24h' in upload:
                print(f"   ⏭️  Already migrated: {upload.get('title', 'Unknown')[:40]}...")
                continue
            
            # Migrate field names
            if 'completion_rate' in upload:
                upload['completion_rate_24h'] = upload.pop('completion_rate')
            
            if 'views' in upload:
                upload['views_24h'] = upload.pop('views')
            
            # Update status
            if upload.get('status') == 'backfilled':
                upload['status'] = 'analytics_available'
            
            # Add analytics_fetched_at if missing
            if 'analytics_fetched_at' not in upload:
                # Use backfilled_at if available, otherwise use current time
                upload['analytics_fetched_at'] = upload.get('backfilled_at', datetime.now(pytz.UTC).isoformat())
            
            # Remove old backfilled_at field
            if 'backfilled_at' in upload:
                upload.pop('backfilled_at')
            
            migrated_count += 1
            print(f"   ✅ Migrated: {upload.get('title', 'Unknown')[:40]}...")
    
    # Save migrated data
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(old_data, f, indent=2)
    
    print(f"\n" + "=" * 60)
    print(f"✅ MIGRATION COMPLETE!")
    print(f"=" * 60)
    print(f"   Migrated: {migrated_count} uploads")
    print(f"   Saved to: {PERFORMANCE_FILE}")
    print(f"   Backup at: {BACKUP_FILE}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review the migrated file")
    print(f"   2. Commit and push changes")
    print(f"   3. Run daily_analytics workflow to test")

if __name__ == "__main__":
    migrate_performance_data()