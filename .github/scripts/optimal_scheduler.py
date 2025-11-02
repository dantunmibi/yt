import os
import json
from datetime import datetime, timedelta
import pytz

def check_schedule():
    """
    Checks if the current time falls within a valid posting window based on a JSON schedule.
    This script is robust against minor GitHub Actions scheduler delays and handles
    cross-midnight time slots.
    """
    schedule_file = 'config/posting_schedule.json'
    TOLERANCE_MINUTES = 30

    # Handle manual override
    if os.getenv('IGNORE_SCHEDULE') == 'true':
        print("✅ Schedule check BYPASSED by user input (ignore_schedule: true).")
        set_github_output('true', 'manual', 'manual_dispatch', datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M UTC"))
        return

    # Load schedule and determine timezone
    try:
        with open(schedule_file, 'r') as f:
            schedule_data = json.load(f)['schedule']
        
        target_tz_name = schedule_data.get('timezone', 'UTC')
        target_tz = pytz.timezone(target_tz_name)
        weekly_schedule = schedule_data['weekly_schedule']
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ Error: Could not load or parse schedule file '{schedule_file}'. Details: {e}")
        set_github_output('false')
        return

    # Get current time in the target timezone
    now = datetime.now(target_tz)
    current_day_name = now.strftime('%A')
    
    print(f"ℹ️ Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (Day: {current_day_name})")
    print(f"ℹ️ Checking with tolerance window of ±{TOLERANCE_MINUTES} minutes")

    # Check today's schedule
    if current_day_name in weekly_schedule:
        match = check_day_schedule(now, weekly_schedule[current_day_name], now, TOLERANCE_MINUTES)
        if match:
            print(f"✅ Match found for today ({current_day_name})!")
            set_github_output(
                should_post='true',
                priority=match['priority'],
                content_type=match['type'],
                current_time=now.strftime("%Y-%m-%d %H:%M %Z")
            )
            return
    
    # Also check yesterday's schedule for late-night slots that might spill into today
    yesterday = now - timedelta(days=1)
    yesterday_name = yesterday.strftime('%A')
    
    if yesterday_name in weekly_schedule:
        # Check if any of yesterday's late slots (after 22:00) might match
        for slot in weekly_schedule[yesterday_name]:
            slot_hour, slot_minute = map(int, slot['time'].split(':'))
            if slot_hour >= 22:  # Only check late-night slots
                # Create datetime for yesterday's slot
                slot_datetime = yesterday.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
                time_diff_minutes = abs((now - slot_datetime).total_seconds() / 60)
                
                if time_diff_minutes <= TOLERANCE_MINUTES:
                    print(f"✅ Match found for late-night slot from {yesterday_name}!")
                    print(f"   -> Scheduled time: {slot['time']} UTC ({yesterday_name})")
                    print(f"   -> Current time: {now.strftime('%H:%M')} UTC ({current_day_name})")
                    print(f"   -> Time difference: {time_diff_minutes:.1f} minutes")
                    print(f"   -> Content Type: {slot['type']}, Priority: {slot['priority']}")
                    set_github_output(
                        should_post='true',
                        priority=slot['priority'],
                        content_type=slot['type'],
                        current_time=now.strftime("%Y-%m-%d %H:%M %Z")
                    )
                    return

    print(f"ℹ️ No active posting window found at the current time.")
    set_github_output('false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"))

def check_day_schedule(now, day_slots, reference_date, tolerance_minutes):
    """Check if current time matches any slot in the day's schedule."""
    for slot in day_slots:
        slot_time_str = slot['time']
        slot_hour, slot_minute = map(int, slot_time_str.split(':'))
        
        # Create a datetime object for the slot time
        slot_datetime = reference_date.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
        
        # Calculate the time difference in minutes
        time_diff_minutes = abs((now - slot_datetime).total_seconds() / 60)
        
        if time_diff_minutes <= tolerance_minutes:
            print(f"   -> Matched slot: {slot_time_str} UTC")
            print(f"   -> Actual time: {now.strftime('%H:%M')} UTC")
            print(f"   -> Time difference: {time_diff_minutes:.1f} minutes")
            print(f"   -> Content Type: {slot['type']}, Priority: {slot['priority']}")
            return slot
    
    return None

def set_github_output(should_post='false', priority='low', content_type='off_schedule', current_time='N/A'):
    """Writes outputs for subsequent GitHub Actions steps."""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'should_post={should_post}\n')
            f.write(f'priority={priority}\n')
            f.write(f'content_type={content_type}\n')
            f.write(f'current_time={current_time}\n')
    else:
        print("--- GITHUB_OUTPUT (local run) ---")
        print(f"should_post={should_post}")
        print(f"priority={priority}")
        print(f"content_type={content_type}")
        print(f"current_time={current_time}")

if __name__ == "__main__":
    check_schedule()