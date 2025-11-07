import os
import json
from datetime import datetime, timedelta
import pytz

# ===== PACKAGE 4 CONFIGURATION =====
ENABLE_PRIORITY_RETRY = os.getenv("ENABLE_PRIORITY_RETRY", "true").lower() == "true"
ENABLE_DELAY_TRACKING = os.getenv("ENABLE_DELAY_TRACKING", "true").lower() == "true"
ENABLE_COMPLETION_PREDICTION = os.getenv("ENABLE_COMPLETION_PREDICTION", "true").lower() == "true"
ENABLE_AUTO_ADJUSTMENT = os.getenv("ENABLE_AUTO_ADJUSTMENT", "true").lower() == "true"  # ENABLED by default

print(f"🔧 Package 4 Features:")
print(f"   Priority Retry: {ENABLE_PRIORITY_RETRY}")
print(f"   Delay Tracking: {ENABLE_DELAY_TRACKING}")
print(f"   Completion Prediction: {ENABLE_COMPLETION_PREDICTION}")
print(f"   Auto Schedule Adjustment: {ENABLE_AUTO_ADJUSTMENT}")

def check_schedule():
    """
    PACKAGE 4 ENHANCED SCHEDULER with:
    - Feature 1: Priority-based retry logic
    - Feature 2: Delay tracking and reporting
    - Feature 3: Completion rate prediction (basic version)
    - Feature 4: Auto schedule adjustment recommendations
    """
    schedule_file = 'config/posting_schedule.json'
    
    # Handle manual override
    if os.getenv('IGNORE_SCHEDULE') == 'true':
        print("✅ Schedule check BYPASSED by user input (ignore_schedule: true).")
        set_github_output(
            should_post='true',
            priority='manual',
            content_type='manual_dispatch',
            series='none',
            episode_number=0,
            current_time=datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M UTC"),
            delay_minutes=0,
            target_completion='N/A',
            has_recommendations='false'
        )
        return

    # FEATURE 1: Check for pending retries FIRST
    if ENABLE_PRIORITY_RETRY:
        retry_result = check_retry_queue()
        if retry_result:
            print("🔄 Processing RETRY from missed high-priority slot")
            set_github_output(
                should_post='true',
                priority=retry_result['priority'],
                content_type=retry_result['content_type'],
                series=retry_result['series'],
                episode_number=retry_result['episode_number'],
                current_time=datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M UTC"),
                delay_minutes='retry',
                target_completion=retry_result.get('target_completion', 'N/A'),
                has_recommendations='false'
            )
            # Remove from retry queue
            remove_from_retry_queue(retry_result)
            return

    # Load schedule
    try:
        with open(schedule_file, 'r') as f:
            schedule_data = json.load(f)['schedule']
        
        target_tz_name = schedule_data.get('timezone', 'UTC')
        target_tz = pytz.timezone(target_tz_name)
        weekly_schedule = schedule_data['weekly_schedule']
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ Error: Could not load schedule file '{schedule_file}'. Details: {e}")
        set_github_output('false')
        return

    # Get current time
    now = datetime.now(target_tz)
    current_day_name = now.strftime('%A')
    
    print(f"ℹ️ Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (Day: {current_day_name})")
    print(f"ℹ️ Using WINDOW-BASED scheduling (accounts for up to 120-min GitHub delays)")

    # Check today's schedule with WIDE windows
    if current_day_name in weekly_schedule:
        match = check_day_schedule_with_windows(now, weekly_schedule[current_day_name], current_day_name)
        if match:
            print(f"✅ Match found for {current_day_name}!")
            
            # Calculate actual delay from scheduled time
            scheduled_time = datetime.strptime(match['time'], '%H:%M').time()
            scheduled_datetime = now.replace(
                hour=scheduled_time.hour, 
                minute=scheduled_time.minute, 
                second=0, 
                microsecond=0
            )
            delay_minutes = int((now - scheduled_datetime).total_seconds() / 60)
            
            # FEATURE 2: Track delay
            if ENABLE_DELAY_TRACKING:
                track_delay(match, delay_minutes, now)
            
            # Load episode tracking
            episode_number = get_next_episode_number(match.get('series', 'none'))
            
            # FEATURE 3: Predict completion rate
            predicted_completion = 'N/A'
            if ENABLE_COMPLETION_PREDICTION:
                predicted_completion = predict_completion_rate(
                    match.get('type', 'unknown'),
                    match.get('series', 'none')
                )
            
            # FEATURE 4: Check for schedule recommendations
            has_recommendations = 'false'
            if ENABLE_AUTO_ADJUSTMENT:
                has_recommendations = check_schedule_recommendations()
            
            set_github_output(
                should_post='true',
                priority=match['priority'],
                content_type=match['type'],
                series=match.get('series', 'none'),
                episode_number=episode_number,
                current_time=now.strftime("%Y-%m-%d %H:%M %Z"),
                delay_minutes=delay_minutes,
                target_completion=match.get('target_completion', 'N/A'),
                predicted_completion=predicted_completion,
                has_recommendations=has_recommendations
            )
            
            return
    
    # Check yesterday for late-night spillover
    yesterday = now - timedelta(days=1)
    yesterday_name = yesterday.strftime('%A')
    
    if yesterday_name in weekly_schedule:
        for slot in weekly_schedule[yesterday_name]:
            if 'window_end' in slot:
                window_end_hour, window_end_minute = map(int, slot['window_end'].split(':'))
                window_end = yesterday.replace(
                    hour=window_end_hour, 
                    minute=window_end_minute, 
                    second=0, 
                    microsecond=0
                )
                
                if window_end > now - timedelta(hours=24) and now <= window_end:
                    print(f"✅ Match found in late-night window from {yesterday_name}!")
                    episode_number = get_next_episode_number(slot.get('series', 'none'))
                    
                    predicted_completion = 'N/A'
                    if ENABLE_COMPLETION_PREDICTION:
                        predicted_completion = predict_completion_rate(
                            slot.get('type', 'unknown'),
                            slot.get('series', 'none')
                        )
                    
                    has_recommendations = 'false'
                    if ENABLE_AUTO_ADJUSTMENT:
                        has_recommendations = check_schedule_recommendations()
                    
                    set_github_output(
                        should_post='true',
                        priority=slot['priority'],
                        content_type=slot['type'],
                        series=slot.get('series', 'none'),
                        episode_number=episode_number,
                        current_time=now.strftime("%Y-%m-%d %H:%M %Z"),
                        delay_minutes='cross-day',
                        target_completion=slot.get('target_completion', 'N/A'),
                        predicted_completion=predicted_completion,
                        has_recommendations=has_recommendations
                    )
                    return

    # FEATURE 1: If we're here, check if we missed a high-priority slot
    if ENABLE_PRIORITY_RETRY:
        missed_slot = check_for_missed_priority_slot(now, weekly_schedule)
        if missed_slot:
            print(f"⚠️ Missed HIGHEST priority slot: {missed_slot['type']} at {missed_slot['time']}")
            add_to_retry_queue(missed_slot, now)

    print(f"ℹ️ No active posting window found at current time.")
    print(f"ℹ️ Next scheduled post: {find_next_scheduled_post(weekly_schedule, now)}")
    
    has_recommendations = 'false'
    if ENABLE_AUTO_ADJUSTMENT:
        has_recommendations = check_schedule_recommendations()
    
    set_github_output('false', current_time=now.strftime("%Y-%m-%d %H:%M %Z"), has_recommendations=has_recommendations)

def check_day_schedule_with_windows(now, day_slots, day_name):
    """Check if current time falls within posting window"""
    for slot in day_slots:
        window_start_str = slot.get('window_start', slot['time'])
        window_end_str = slot.get('window_end', slot['time'])
        
        window_start_hour, window_start_minute = map(int, window_start_str.split(':'))
        window_end_hour, window_end_minute = map(int, window_end_str.split(':'))
        
        window_start = now.replace(
            hour=window_start_hour, 
            minute=window_start_minute, 
            second=0, 
            microsecond=0
        )
        window_end = now.replace(
            hour=window_end_hour, 
            minute=window_end_minute, 
            second=0, 
            microsecond=0
        )
        
        if window_start <= now <= window_end:
            print(f"   ✅ Within posting window!")
            print(f"   -> Window: {window_start_str} - {window_end_str} UTC ({day_name})")
            print(f"   -> Scheduled time: {slot['time']} UTC")
            print(f"   -> Current time: {now.strftime('%H:%M')} UTC")
            print(f"   -> Series: {slot.get('series', 'N/A')}")
            print(f"   -> Content Type: {slot['type']}")
            print(f"   -> Priority: {slot['priority']}")
            print(f"   -> Target Completion: {slot.get('target_completion', 'N/A')}")
            return slot
    
    return None

def get_next_episode_number(series_name):
    """Track episode numbers for series content"""
    if series_name == 'none':
        return 0
    
    tracking_file = 'tmp/episode_tracking.json'
    
    try:
        if os.path.exists(tracking_file):
            with open(tracking_file, 'r') as f:
                tracking = json.load(f)
        else:
            tracking = {}
        
        current_episode = tracking.get(series_name, 0)
        next_episode = current_episode + 1
        
        print(f"📺 Series: {series_name}")
        print(f"   -> Next episode: {next_episode}")
        
        return next_episode
    except Exception as e:
        print(f"⚠️ Episode tracking error: {e}, defaulting to Episode 1")
        return 1

# ===== FEATURE 1: PRIORITY RETRY SYSTEM =====

def check_retry_queue():
    """Check if there are any pending high-priority retries"""
    retry_file = 'tmp/retry_queue.json'
    
    if not os.path.exists(retry_file):
        return None
    
    try:
        with open(retry_file, 'r') as f:
            queue = json.load(f)
        
        pending = queue.get('pending_retries', [])
        
        if not pending:
            return None
        
        # Get oldest retry that hasn't expired
        now = datetime.now(pytz.UTC)
        
        for retry in pending:
            retry_before = datetime.fromisoformat(retry['retry_before'].replace('Z', '+00:00'))
            
            if now <= retry_before:
                print(f"🔄 Found pending retry: {retry['content_type']}")
                print(f"   Original slot: {retry['original_slot']}")
                print(f"   Missed at: {retry['missed_timestamp']}")
                return retry
        
        return None
        
    except Exception as e:
        print(f"⚠️ Error reading retry queue: {e}")
        return None

def add_to_retry_queue(slot, missed_time):
    """Add a missed high-priority slot to retry queue"""
    retry_file = 'tmp/retry_queue.json'
    
    try:
        os.makedirs('tmp', exist_ok=True)
        
        if os.path.exists(retry_file):
            with open(retry_file, 'r') as f:
                queue = json.load(f)
        else:
            queue = {'pending_retries': [], 'completed_retries': []}
        
        # Add to pending
        retry_entry = {
            'original_slot': f"{missed_time.strftime('%A')} {slot['time']}",
            'priority': slot['priority'],
            'content_type': slot['type'],
            'series': slot.get('series', 'none'),
            'episode_number': get_next_episode_number(slot.get('series', 'none')),
            'missed_timestamp': missed_time.isoformat(),
            'retry_before': (missed_time + timedelta(days=7)).isoformat(),
            'reason': 'Workflow ran outside posting window',
            'target_completion': slot.get('target_completion', 'N/A')
        }
        
        queue['pending_retries'].append(retry_entry)
        
        with open(retry_file, 'w') as f:
            json.dump(queue, f, indent=2)
        
        print(f"📝 Added to retry queue: {slot['type']} (retry before {retry_entry['retry_before']})")
        
    except Exception as e:
        print(f"⚠️ Could not add to retry queue: {e}")

def remove_from_retry_queue(retry_entry):
    """Remove retry from queue after successful posting"""
    retry_file = 'tmp/retry_queue.json'
    
    try:
        with open(retry_file, 'r') as f:
            queue = json.load(f)
        
        # Move from pending to completed
        queue['pending_retries'] = [r for r in queue['pending_retries'] if r != retry_entry]
        
        retry_entry['completed_at'] = datetime.now(pytz.UTC).isoformat()
        queue['completed_retries'].append(retry_entry)
        
        # Keep only last 30 completed
        queue['completed_retries'] = queue['completed_retries'][-30:]
        
        with open(retry_file, 'w') as f:
            json.dump(queue, f, indent=2)
        
        print(f"✅ Retry completed and logged")
        
    except Exception as e:
        print(f"⚠️ Could not update retry queue: {e}")

def check_for_missed_priority_slot(now, weekly_schedule):
    """Check if we just missed a HIGHEST priority slot"""
    current_day_name = now.strftime('%A')
    
    if current_day_name not in weekly_schedule:
        return None
    
    for slot in weekly_schedule[current_day_name]:
        if slot.get('priority') != 'highest':
            continue
        
        window_end_str = slot.get('window_end', slot['time'])
        window_end_hour, window_end_minute = map(int, window_end_str.split(':'))
        
        window_end = now.replace(
            hour=window_end_hour,
            minute=window_end_minute,
            second=0,
            microsecond=0
        )
        
        # Check if we just passed the window (within last 30 minutes)
        if window_end < now <= window_end + timedelta(minutes=30):
            return slot
    
    return None

# ===== FEATURE 2: DELAY TRACKING =====

def track_delay(slot, delay_minutes, actual_time):
    """Track scheduling delays for analysis"""
    delay_log_file = 'tmp/delay_log.json'
    
    try:
        os.makedirs('tmp', exist_ok=True)
        
        if os.path.exists(delay_log_file):
            with open(delay_log_file, 'r') as f:
                log = json.load(f)
        else:
            log = {'delays': []}
        
        delay_entry = {
            'scheduled_time': slot['time'],
            'actual_time': actual_time.strftime('%H:%M'),
            'delay_minutes': delay_minutes,
            'day': actual_time.strftime('%A'),
            'date': actual_time.strftime('%Y-%m-%d'),
            'priority': slot['priority'],
            'content_type': slot['type'],
            'series': slot.get('series', 'none'),
            'window_start': slot.get('window_start', slot['time']),
            'window_end': slot.get('window_end', slot['time']),
            'window_hit': True  # If we're here, we hit the window
        }
        
        log['delays'].append(delay_entry)
        
        # Keep last 100 delays
        log['delays'] = log['delays'][-100:]
        
        # Calculate statistics
        if len(log['delays']) >= 5:
            recent_delays = [d['delay_minutes'] for d in log['delays'][-30:] if isinstance(d['delay_minutes'], int)]
            if recent_delays:
                log['statistics'] = {
                    'average_delay': sum(recent_delays) / len(recent_delays),
                    'max_delay': max(recent_delays),
                    'min_delay': min(recent_delays),
                    'on_time_rate': sum(1 for d in recent_delays if d <= 15) / len(recent_delays) * 100,
                    'window_hit_rate': sum(1 for d in log['delays'][-30:] if d.get('window_hit')) / len(log['delays'][-30:]) * 100,
                    'sample_size': len(recent_delays)
                }
        
        with open(delay_log_file, 'w') as f:
            json.dump(log, f, indent=2)
        
        if delay_minutes > 60:
            print(f"⚠️ Significant delay detected: {delay_minutes} minutes")
        elif delay_minutes < 0:
            print(f"ℹ️ Workflow ran EARLY by {abs(delay_minutes)} minutes")
        else:
            print(f"ℹ️ Delay: {delay_minutes} minutes (within normal range)")
        
    except Exception as e:
        print(f"⚠️ Could not track delay: {e}")

# ===== FEATURE 3: COMPLETION RATE PREDICTION =====

def predict_completion_rate(content_type, series_name):
    """Predict completion rate based on historical data"""
    performance_file = 'tmp/content_performance.json'
    
    if not os.path.exists(performance_file):
        # No data yet, use targets from schedule
        schedule_file = 'config/posting_schedule.json'
        try:
            with open(schedule_file, 'r') as f:
                schedule = json.load(f)['schedule']
                
            for day_slots in schedule['weekly_schedule'].values():
                for slot in day_slots:
                    if slot['type'] == content_type:
                        return f"{slot.get('target_completion', '60')} (target)"
        except:
            pass
        
        return "No data"
    
    try:
        with open(performance_file, 'r') as f:
            performance = json.load(f)
        
        # Check if we have data for this content type
        if content_type in performance:
            type_data = performance[content_type]
            avg_completion = type_data.get('average_completion', 0)
            
            if avg_completion > 0:
                # Adjust based on series performance if available
                if series_name != 'none' and 'series_performance' in type_data:
                    series_data = type_data['series_performance'].get(series_name, {})
                    if series_data.get('average_completion', 0) > 0:
                        return f"{series_data['average_completion']:.1f}% (series avg)"
                
                return f"{avg_completion:.1f}% (type avg)"
        
        return "No data"
        
    except Exception as e:
        print(f"⚠️ Prediction error: {e}")
        return "Error"

# ===== FEATURE 4: AUTO SCHEDULE ADJUSTMENT =====

def check_schedule_recommendations():
    """Check if there are schedule adjustment recommendations"""
    recommendations_file = 'tmp/schedule_recommendations.json'
    
    if not os.path.exists(recommendations_file):
        return 'false'
    
    try:
        with open(recommendations_file, 'r') as f:
            recommendations = json.load(f)
        
        pending = recommendations.get('pending_recommendations', [])
        
        if pending:
            print(f"💡 Found {len(pending)} schedule recommendations")
            return 'true'
        
        return 'false'
        
    except Exception as e:
        print(f"⚠️ Error checking recommendations: {e}")
        return 'false'

def find_next_scheduled_post(weekly_schedule, current_time):
    """Find and display next scheduled posting window"""
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_day = current_time.strftime('%A')
    current_day_index = days_order.index(current_day)
    
    # Check remaining slots today
    if current_day in weekly_schedule:
        for slot in weekly_schedule[current_day]:
            window_end_str = slot.get('window_end', slot['time'])
            window_end_hour, window_end_minute = map(int, window_end_str.split(':'))
            window_end = current_time.replace(
                hour=window_end_hour,
                minute=window_end_minute,
                second=0,
                microsecond=0
            )
            if window_end > current_time:
                return f"{current_day} {slot['time']}-{window_end_str} UTC ({slot.get('series', slot['type'])})"
    
    # Check next days
    for i in range(1, 8):
        next_day_index = (current_day_index + i) % 7
        next_day = days_order[next_day_index]
        if next_day in weekly_schedule and weekly_schedule[next_day]:
            first_slot = weekly_schedule[next_day][0]
            return f"{next_day} {first_slot['time']} UTC ({first_slot.get('series', first_slot['type'])})"
    
    return "No upcoming posts scheduled"

def set_github_output(
    should_post='false',
    priority='low',
    content_type='off_schedule',
    series='none',
    episode_number=0,
    current_time='N/A',
    delay_minutes=0,
    target_completion='N/A',
    predicted_completion='N/A',
    has_recommendations='false'
):
    """Write outputs for GitHub Actions with FULL Package 4 metadata"""
    outputs = {
        'should_post': should_post,
        'priority': priority,
        'content_type': content_type,
        'series': series,
        'episode_number': episode_number,
        'current_time': current_time,
        'delay_minutes': delay_minutes,
        'target_completion': target_completion,
        'predicted_completion': predicted_completion,
        'has_recommendations': has_recommendations
    }
    
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            for key, value in outputs.items():
                f.write(f'{key}={value}\n')
    else:
        print("--- GITHUB_OUTPUT (local run) ---")
        for key, value in outputs.items():
            print(f"{key}={value}")

if __name__ == "__main__":
    check_schedule()