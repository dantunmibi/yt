import os
import json
from datetime import datetime, timedelta
import pytz

def load_config():
    """Loads the schedule and recommendations from JSON files."""
    try:
        with open('config/posting_schedule.json', 'r') as f:
            schedule_config = json.load(f)['schedule']
        
        with open('config/content_recommendations.json', 'r') as f:
            recommendations_config = json.load(f)['recommendations']

        return {
            "tz": pytz.timezone(schedule_config.get('timezone', 'UTC')),
            "schedule": schedule_config['weekly_schedule'],
            "recommendations": recommendations_config
        }
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ CRITICAL: Could not load or parse config file. Error: {e}")
        return None

def check_schedule(config, ignore_schedule=False, tolerance_minutes=20):
    """Determines if it's the right time to post."""
    if not config:
        set_github_output(should_post='false', reason="Config not loaded")
        return

    target_tz = config['tz']
    now = datetime.now(target_tz)

    if ignore_schedule:
        print("✅ Schedule check BYPASSED by user input (ignore_schedule: true).")
        set_github_output('true', 'manual', 'manual_dispatch', now.strftime("%Y-%m-%d %H:%M %Z"))
        return

    current_day_name = now.strftime('%A')
    print(f"ℹ️ Checking schedule for: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (Day: {current_day_name})")

    if current_day_name not in config['schedule']:
        print(f"ℹ️ No schedule defined for {current_day_name}.")
        set_github_output('false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"))
        return

    for slot in config['schedule'][current_day_name]:
        slot_hour, slot_minute = map(int, slot['time'].split(':'))
        slot_datetime = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
        
        time_diff_minutes = abs((now - slot_datetime).total_seconds() / 60)
        
        if time_diff_minutes <= tolerance_minutes:
            print(f"✅ Match found! Current time {now.strftime('%H:%M')} is within the '{slot['time']}' window.")
            set_github_output(
                should_post='true',
                priority=slot['priority'],
                content_type=slot.get('type', 'general'), # Use .get() for safety
                current_time=now.strftime("%Y-%m-%d %H:%M %Z")
            )
            return

    print(f"ℹ️ No active posting window found at the current time.")
    set_github_output('false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"))

def set_github_output(should_post, priority='low', content_type='off_schedule', current_time='N/A', reason=''):
    """Writes outputs for subsequent GitHub Actions steps."""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'should_post={should_post}\n')
            f.write(f'priority={priority}\n')
            f.write(f'content_type={content_type}\n')
            f.write(f'current_time={current_time}\n')
            if reason:
                f.write(f'reason={reason}\n')
    else:
        # For local testing
        print("--- GITHUB_OUTPUT (local run) ---")
        print(f"should_post={should_post}, priority={priority}, content_type={content_type}")

def main():
    """Main execution logic."""
    config = load_config()
    ignore_schedule_flag = os.getenv("IGNORE_SCHEDULE", "false").lower() == "true"
    check_schedule(config, ignore_schedule=ignore_schedule_flag)

if __name__ == "__main__":
    main()