import os
import json
from datetime import datetime
import pytz

def check_schedule():
    """
    Checks if the current time falls within a valid posting window based on a JSON schedule.
    This script is robust and handles all run types (schedule, manual, forced).
    """
    schedule_file = 'config/posting_schedule.json'
    # Use a robust two-sided tolerance window (minutes before/after the scheduled time)
    TOLERANCE_MINUTES = 20

    # --- 1. Handle Manual Override (The FIX for `ignore_schedule`) ---
    if os.getenv('IGNORE_SCHEDULE', 'false').lower() == 'true':
        print("✅ Schedule check BYPASSED by user input (ignore_schedule: true).")
        set_github_output(should_post='true', priority='manual', content_type='manual_dispatch')
        return

    # --- 2. Load Schedule Configuration ---
    try:
        with open(schedule_file, 'r') as f:
            schedule_data = json.load(f)['schedule']
        
        target_tz_name = schedule_data.get('timezone', 'UTC')
        target_tz = pytz.timezone(target_tz_name)
        weekly_schedule = schedule_data['weekly_schedule']
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ Error: Could not load or parse '{schedule_file}'. Details: {e}")
        set_github_output(should_post='false')
        return

    # --- 3. Perform the Time Check for Scheduled Runs ---
    now = datetime.now(target_tz)
    current_day_name = now.strftime('%A')
    print(f"ℹ️ Checking schedule for: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (Day: {current_day_name})")

    if current_day_name not in weekly_schedule:
        print(f"ℹ️ No schedule defined for {current_day_name}.")
        set_github_output(should_post='false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"))
        return

    for slot in weekly_schedule[current_day_name]:
        slot_hour, slot_minute = map(int, slot['time'].split(':'))
        slot_datetime = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
        
        # Robust two-sided check
        time_diff_minutes = abs((now - slot_datetime).total_seconds() / 60)
        
        if time_diff_minutes <= TOLERANCE_MINUTES:
            print(f"✅ Match found! Current time {now.strftime('%H:%M')} is within the '{slot['time']}' window.")
            set_github_output(
                should_post='true',
                priority=slot['priority'],
                content_type=slot.get('type', 'general'),
                current_time=now.strftime("%Y-%m-%d %H:%M %Z")
            )
            return

    print(f"ℹ️ No active posting window found at the current time.")
    set_github_output(should_post='false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"))


def set_github_output(should_post, priority='low', content_type='off_schedule', current_time='N/A'):
    """Writes outputs for subsequent GitHub Actions steps."""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'should_post={should_post}\n')
            f.write(f'priority={priority}\n')
            f.write(f'content_type={content_type}\n')
            f.write(f'current_time={current_time}\n')

if __name__ == "__main__":
    check_schedule()