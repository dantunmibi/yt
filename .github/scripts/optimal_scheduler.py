import os
import json
from datetime import datetime, timedelta
import pytz

# --- START OF CHANGES ---

def load_schedule():
    """Loads the schedule configuration from a JSON file."""
    try:
        with open('config/posting_schedule.json', 'r') as f:
            config = json.load(f)['schedule']
            return {
                "tz": pytz.timezone(config.get('timezone', 'UTC')),
                "schedule": config['weekly_schedule']
            }
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ CRITICAL: Could not load or parse 'config/posting_schedule.json'. Error: {e}")
        return None

# Load configuration globally
config_data = load_schedule()
if config_data:
    LOCAL_TZ = config_data['tz']
    OPTIMAL_SCHEDULE = config_data['schedule']
else:
    # Fallback if config fails to load
    LOCAL_TZ = pytz.timezone('UTC')
    OPTIMAL_SCHEDULE = {}

# --- END OF CHANGES ---

# (The rest of your script: CONTENT_RECOMMENDATIONS, get_next_optimal_time, etc., remains exactly the same)
# ... your existing functions from here down ...
# Content type recommendations
CONTENT_RECOMMENDATIONS = {
    "ai_tools": "Latest AI tools, ChatGPT features, new tech releases",
    "productivity": "Time management, focus hacks, workflow optimization",
    "brain_hack": "Memory techniques, learning methods, cognitive enhancement",
    "tech_news": "Breaking tech news, industry updates, innovations",
    "trending": "Viral topics, trending discussions, hot takes",
    "surprise": "Mind-blowing facts, unexpected discoveries, 'did you know'",
    "entertainment": "Fun tech, cool gadgets, interesting demonstrations",
    "lifestyle": "Tech lifestyle, daily routines, practical applications",
    "motivation": "Success stories, inspirational content, mindset shifts",
    "mindset": "Philosophy, long-term thinking, perspective shifts"
}


def get_next_optimal_time(current_time=None):
    """
    Calculate the next optimal posting time based on current time.
    Returns datetime object of next optimal slot.
    """
    if current_time is None:
        current_time = datetime.now(LOCAL_TZ)
    
    # Get current weekday (0=Monday, 6=Sunday)
    current_weekday = current_time.weekday()
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    # Check if there's an optimal time today after current time
    today_slots = OPTIMAL_SCHEDULE.get(current_weekday, [])
    
    for slot in today_slots:
        slot_time = datetime.strptime(slot["time"], "%H:%M").time()
        slot_datetime = current_time.replace(
            hour=slot_time.hour,
            minute=slot_time.minute,
            second=0,
            microsecond=0
        )
        
        # If slot is in the future today
        if slot_datetime > current_time:
            return {
                "datetime": slot_datetime,
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]]
            }
    
    # No more slots today, find next day's first slot
    days_ahead = 1
    while days_ahead < 8:  # Check up to 7 days ahead
        next_day = (current_weekday + days_ahead) % 7
        next_slots = OPTIMAL_SCHEDULE.get(next_day, [])
        
        if next_slots:
            first_slot = next_slots[0]
            slot_time = datetime.strptime(first_slot["time"], "%H:%M").time()
            
            next_datetime = current_time + timedelta(days=days_ahead)
            next_datetime = next_datetime.replace(
                hour=slot_time.hour,
                minute=slot_time.minute,
                second=0,
                microsecond=0
            )
            
            return {
                "datetime": next_datetime,
                "priority": first_slot["priority"],
                "content_type": first_slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[first_slot["content_type"]]
            }
        
        days_ahead += 1
    
    # Fallback: Default to Tuesday 1 PM next week
    days_until_tuesday = (1 - current_weekday) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    
    next_tuesday = current_time + timedelta(days=days_until_tuesday)
    next_tuesday = next_tuesday.replace(hour=13, minute=0, second=0, microsecond=0)
    
    return {
        "datetime": next_tuesday,
        "priority": "highest",
        "content_type": "ai_tools",
        "recommendation": CONTENT_RECOMMENDATIONS["ai_tools"]
    }


def should_post_now(tolerance_minutes=30):
    """
    Check if current time is within an optimal posting window.
    Returns (should_post: bool, slot_info: dict)
    """
    current_time = datetime.now(LOCAL_TZ)
    current_weekday = current_time.weekday()
    
    today_slots = OPTIMAL_SCHEDULE.get(current_weekday, [])
    
    for slot in today_slots:
        slot_time = datetime.strptime(slot["time"], "%H:%M").time()
        slot_datetime = current_time.replace(
            hour=slot_time.hour,
            minute=slot_time.minute,
            second=0,
            microsecond=0
        )
        
        # Check if within tolerance window
        time_diff = abs((current_time - slot_datetime).total_seconds() / 60)
        
        if time_diff <= tolerance_minutes:
            return True, {
                "time": slot["time"],
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]],
                "minutes_off": int(time_diff)
            }
    
    return False, None


def get_weekly_schedule():
    """Get the full weekly optimal schedule"""
    schedule = {}
    
    for day, slots in OPTIMAL_SCHEDULE.items():
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule[day_names[day]] = [
            {
                "time": slot["time"],
                "priority": slot["priority"],
                "content_type": slot["content_type"],
                "recommendation": CONTENT_RECOMMENDATIONS[slot["content_type"]]
            }
            for slot in slots
        ]
    
    return schedule


def calculate_delay_until_optimal():
    """
    Calculate how many seconds to wait until next optimal time.
    Useful for scheduling workflows.
    """
    next_slot = get_next_optimal_time()
    current_time = datetime.now(LOCAL_TZ)
    
    delay = (next_slot["datetime"] - current_time).total_seconds()
    
    return {
        "delay_seconds": int(delay),
        "delay_hours": delay / 3600,
        "delay_days": delay / 86400,
        "next_post_time": next_slot["datetime"].isoformat(),
        "priority": next_slot["priority"],
        "content_type": next_slot["content_type"],
        "recommendation": next_slot["recommendation"]
    }


def main():
    """Main execution for testing and GitHub Actions integration"""
    print("🕐 YouTube Shorts Optimal Posting Scheduler")
    print("=" * 60)
    
    current_time = datetime.now(LOCAL_TZ)
    print(f"📅 Current Time: {current_time.strftime('%A, %B %d, %Y %I:%M %p WAT')}")
    print()
    
    # Check if should post now
    should_post, slot_info = should_post_now(tolerance_minutes=30)
    
    if should_post:
        print("✅ OPTIMAL POSTING WINDOW - POST NOW!")
        print(f"   Time Slot: {slot_info['time']} WAT")
        print(f"   Priority: {slot_info['priority'].upper()}")
        print(f"   Content Type: {slot_info['content_type']}")
        print(f"   Recommendation: {slot_info['recommendation']}")
        print(f"   Timing: {slot_info['minutes_off']} minutes from optimal")
        
        # Set output for GitHub Actions
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"should_post=true\n")
            f.write(f"priority={slot_info['priority']}\n")
            f.write(f"content_type={slot_info['content_type']}\n")
    else:
        print("⏳ NOT IN OPTIMAL WINDOW - Calculating next slot...")
        
        next_slot = get_next_optimal_time()
        delay_info = calculate_delay_until_optimal()
        
        print(f"\n📌 Next Optimal Time:")
        print(f"   Date/Time: {next_slot['datetime'].strftime('%A, %B %d, %Y %I:%M %p WAT')}")
        print(f"   Priority: {next_slot['priority'].upper()}")
        print(f"   Content Type: {next_slot['content_type']}")
        print(f"   Recommendation: {next_slot['recommendation']}")
        print(f"\n⏱️  Time Until Next Slot:")
        print(f"   {delay_info['delay_hours']:.1f} hours ({delay_info['delay_days']:.1f} days)")
        
        # Set output for GitHub Actions
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"should_post=false\n")
            f.write(f"next_post_time={next_slot['datetime'].isoformat()}\n")
            f.write(f"delay_hours={delay_info['delay_hours']:.1f}\n")
    
    # Print weekly schedule
    print("\n" + "=" * 60)
    print("📅 WEEKLY OPTIMAL SCHEDULE")
    print("=" * 60)
    
    weekly = get_weekly_schedule()
    for day, slots in weekly.items():
        print(f"\n{day}:")
        for slot in slots:
            priority_emoji = {
                "highest": "⭐⭐⭐",
                "high": "⭐⭐",
                "medium": "⭐",
                "low": "○"
            }[slot["priority"]]
            
            print(f"  {priority_emoji} {slot['time']} WAT - {slot['content_type']}")
            print(f"     → {slot['recommendation']}")
    
    # Save schedule to file
    schedule_file = os.path.join(TMP, "posting_schedule.json")
    schedule_data = {
        "current_time": current_time.isoformat(),
        "should_post_now": should_post,
        "next_optimal_slot": get_next_optimal_time(),
        "weekly_schedule": get_weekly_schedule(),
        "timezone": "Africa/Lagos (WAT/UTC+1)"
    }
    
    with open(schedule_file, 'w') as f:
        json.dump(schedule_data, f, indent=2, default=str)
    
    print(f"\n💾 Schedule saved to: {schedule_file}")
    print("\n💡 Tip: Run this during workflow to decide whether to post immediately or schedule")


if __name__ == "__main__":
    main()