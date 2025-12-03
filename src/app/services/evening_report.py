"""
Evening Report Generator
Creates comprehensive autism-friendly evening health & preparation report
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import requests
import os


def format_hours_to_hm(decimal_hours: float) -> str:
    """Convert decimal hours to Xh Ym format (e.g., 7.5 -> '7h 30m')."""
    if decimal_hours is None or decimal_hours == 0:
        return "0h 0m"
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)
    return f"{hours}h {minutes}m"


def generate_evening_report(health_coach, calendar_service, llm_service) -> str:
    """
    Generate comprehensive evening report using MCP tools data.
    
    Includes:
    - Today's activity summary (steps, floors, distance)
    - Today's workout summary (if any)
    - Body Battery status & drain
    - Stress patterns
    - Sleep recommendation based on last night
    - Tomorrow's calendar
    - Weather for tomorrow
    - AI-generated autism-friendly evening insight
    """
    from app.core.config import settings
    user_tz = settings.user_timezone
    now = datetime.now(user_tz)
    today = now.strftime("%A, %B %d, %Y")
    tomorrow = (now + timedelta(days=1)).strftime("%A, %B %d, %Y")
    
    # Collect all data
    data: Dict[str, Any] = {
        "date": today,
        "tomorrow_date": tomorrow,
        "daily_stats": None,
        "body_battery": None,
        "stress": None,
        "today_workouts": [],
        "last_sleep": None,
        "tomorrow_calendar": [],
        "weather": None,
    }
    
    # 1. TODAY'S ACTIVITY (Steps, Floors from DailyStats)
    try:
        query = f"""
        SELECT totalSteps, floorsAscended, floorsDescended, 
               activeKilocalories, totalDistanceMeters,
               bodyBatteryLowestValue, bodyBatteryHighestValue,
               bodyBatteryAtWakeTime, stressAvg, stressHigh, stressLow
        FROM DailyStats 
        ORDER BY time DESC 
        LIMIT 1
        """
        result = health_coach.client.query(query)
        points = list(result.get_points())
        if points:
            point = points[0]
            data["daily_stats"] = {
                "steps": int(point.get("totalSteps", 0) or 0),
                "floors_up": round(point.get("floorsAscended", 0) or 0, 1),
                "floors_down": round(point.get("floorsDescended", 0) or 0, 1),
                "calories": int(point.get("activeKilocalories", 0) or 0),
                "distance_km": round((point.get("totalDistanceMeters", 0) or 0) / 1000, 2),
                "body_battery_wake": int(point.get("bodyBatteryAtWakeTime", 0) or 0),
                "body_battery_high": int(point.get("bodyBatteryHighestValue", 0) or 0),
                "body_battery_low": int(point.get("bodyBatteryLowestValue", 0) or 0),
            }
            # Stress data
            stress_avg = point.get("stressAvg", 0) or 0
            stress_high = point.get("stressHigh", 0) or 0
            stress_low = point.get("stressLow", 0) or 0
            if stress_avg > 0:
                data["stress"] = {
                    "avg": int(stress_avg),
                    "high_minutes": int((stress_high or 0) / 60),
                    "low_minutes": int((stress_low or 0) / 60),
                }
    except Exception as e:
        print(f"Daily stats error: {e}")
    
    # 2. CURRENT BODY BATTERY
    try:
        query = "SELECT BodyBatteryLevel FROM BodyBatteryIntraday ORDER BY time DESC LIMIT 1"
        result = health_coach.client.query(query)
        points = list(result.get_points())
        if points:
            data["body_battery"] = int(points[0].get("BodyBatteryLevel", 0))
    except Exception as e:
        print(f"Body battery error: {e}")
    
    # 3. TODAY'S WORKOUTS
    try:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = f"""
        SELECT activityName, activityType, distance, movingDuration, 
               averageHR, calories, aerobicTE
        FROM ActivitySummary
        WHERE time >= '{today_start.isoformat()}Z'
        ORDER BY time DESC
        """
        result = health_coach.client.query(query)
        points = list(result.get_points())
        for p in points:
            if p.get("activityType") and p.get("activityType") != "No Activity":
                duration_sec = p.get("movingDuration", 0) or 0
                data["today_workouts"].append({
                    "name": p.get("activityName", "Activity"),
                    "type": p.get("activityType", ""),
                    "distance_km": round((p.get("distance", 0) or 0) / 1000, 2),
                    "duration": format_hours_to_hm(duration_sec / 3600) if duration_sec else "0m",
                    "avg_hr": int(p.get("averageHR", 0) or 0),
                    "calories": int(p.get("calories", 0) or 0),
                    "training_effect": round(p.get("aerobicTE", 0) or 0, 1)
                })
    except Exception as e:
        print(f"Today's workouts error: {e}")
    
    # 4. LAST NIGHT'S SLEEP (for recommendation)
    try:
        sleep_data = health_coach.get_sleep_data(days=1)
        if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
            data["last_sleep"] = sleep_data["sleep_records"][0]
    except Exception as e:
        print(f"Sleep data error: {e}")
    
    # 5. TOMORROW'S CALENDAR
    try:
        events = calendar_service.get_tomorrow_events()
        if events:
            for event in events:
                data["tomorrow_calendar"].append({
                    "time": event.start.strftime("%I:%M %p"),
                    "title": event.summary,
                    "location": event.location if hasattr(event, 'location') else None,
                    "url": event.url if hasattr(event, 'url') else None
                })
    except Exception as e:
        print(f"Calendar error: {e}")
    
    # 6. WEATHER FOR TOMORROW
    try:
        weather_api_key = os.getenv('WEATHER_API_KEY')
        city = os.getenv('WEATHER_CITY', 'São Paulo')
        
        if weather_api_key:
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={weather_api_key}&units=metric&lang=pt"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                forecast = response.json()
                tomorrow_forecasts = []
                tomorrow_date = (now + timedelta(days=1)).date()
                
                for entry in forecast.get('list', []):
                    entry_time = datetime.fromtimestamp(entry['dt'], tz=user_tz)
                    if entry_time.date() == tomorrow_date:
                        tomorrow_forecasts.append(entry)
                
                if tomorrow_forecasts:
                    midday = None
                    for entry in tomorrow_forecasts:
                        entry_time = datetime.fromtimestamp(entry['dt'], tz=user_tz)
                        if 10 <= entry_time.hour <= 14:
                            midday = entry
                            break
                    
                    if not midday and tomorrow_forecasts:
                        midday = tomorrow_forecasts[0]
                    
                    if midday:
                        data["weather"] = {
                            "temp": midday['main']['temp'],
                            "feels_like": midday['main']['feels_like'],
                            "description": midday['weather'][0]['description'],
                            "humidity": midday['main']['humidity'],
                            "temp_min": min(f['main']['temp_min'] for f in tomorrow_forecasts),
                            "temp_max": max(f['main']['temp_max'] for f in tomorrow_forecasts),
                        }
    except Exception as e:
        print(f"Weather fetch skipped: {e}")
    
    # Now build the report
    report_lines = []
    
    # Header
    report_lines.append(f"Good Evening!")
    report_lines.append(f"{today}")
    report_lines.append("")
    
    # TODAY'S ACTIVITY SUMMARY
    if data["daily_stats"]:
        stats = data["daily_stats"]
        report_lines.append("**Today's Activity:**")
        report_lines.append(f"- Steps: {stats['steps']:,}")
        report_lines.append(f"- Floors: {stats['floors_up']} up, {stats['floors_down']} down")
        report_lines.append(f"- Distance: {stats['distance_km']} km")
        report_lines.append(f"- Active Calories: {stats['calories']}")
        
        if stats['steps'] >= 10000:
            report_lines.append("  Great activity level today!")
        elif stats['steps'] >= 7000:
            report_lines.append("  Good movement today")
        else:
            report_lines.append("  Consider more movement tomorrow")
        report_lines.append("")
    
    # TODAY'S WORKOUTS (new section)
    if data["today_workouts"]:
        report_lines.append("**Today's Workouts:**")
        for workout in data["today_workouts"]:
            report_lines.append(f"- {workout['name']} ({workout['type']})")
            details = []
            if workout['distance_km'] > 0:
                details.append(f"{workout['distance_km']} km")
            details.append(workout['duration'])
            if workout['avg_hr'] > 0:
                details.append(f"HR: {workout['avg_hr']} bpm")
            if workout['training_effect'] > 0:
                details.append(f"TE: {workout['training_effect']}")
            report_lines.append(f"  {' | '.join(details)}")
        report_lines.append("")
    
    # BODY BATTERY
    if data["body_battery"] and data["daily_stats"]:
        bb_current = data["body_battery"]
        bb_wake = data["daily_stats"]["body_battery_wake"]
        bb_high = data["daily_stats"]["body_battery_high"]
        bb_low = data["daily_stats"]["body_battery_low"]
        
        report_lines.append("**Body Battery:**")
        report_lines.append(f"- Current: {bb_current}/100")
        report_lines.append(f"- Today's Range: {bb_low} - {bb_high}")
        report_lines.append(f"- Started at: {bb_wake}/100")
        
        drain = bb_wake - bb_current
        if drain > 0:
            report_lines.append(f"- Used: {drain} points today")
        
        if bb_current >= 50:
            report_lines.append("  Good energy remaining for evening")
        elif bb_current >= 30:
            report_lines.append("  Moderate energy - consider winding down")
        else:
            report_lines.append("  Low energy - prioritize rest")
        report_lines.append("")
    
    # STRESS SUMMARY (new section)
    if data["stress"]:
        stress = data["stress"]
        report_lines.append("**Today's Stress:**")
        report_lines.append(f"- Average: {stress['avg']}/100")
        report_lines.append(f"- High stress: {stress['high_minutes']} min | Low stress: {stress['low_minutes']} min")
        
        if stress['avg'] < 30:
            report_lines.append("  Low stress day - well managed!")
        elif stress['avg'] < 50:
            report_lines.append("  Moderate stress levels")
        else:
            report_lines.append("  High stress - focus on relaxation tonight")
        report_lines.append("")
    
    # SLEEP RECOMMENDATION
    if data["last_sleep"]:
        sleep = data["last_sleep"]
        report_lines.append("**Sleep Recommendation:**")
        report_lines.append(f"- Last night: {format_hours_to_hm(sleep['total_sleep_hours'])} (score: {sleep['sleep_score']}/100)")
        
        if sleep['sleep_score'] < 70:
            report_lines.append("  Sleep quality was low - aim for earlier bedtime tonight")
            rec_sleep = 8.5
        elif sleep['total_sleep_hours'] < 7:
            report_lines.append("  You got less than 7h - try for 8h tonight")
            rec_sleep = 8.0
        else:
            report_lines.append("  Sleep was good - maintain similar schedule")
            rec_sleep = sleep['total_sleep_hours']
        
        # Calculate bedtime recommendation based on tomorrow's earliest event
        earliest_event = None
        if data["tomorrow_calendar"]:
            for event in data["tomorrow_calendar"]:
                event_time_str = event["time"]
                try:
                    event_time = datetime.strptime(event_time_str, "%I:%M %p").time()
                    if event_time.hour >= 6:
                        earliest_event = event
                        break
                except Exception:
                    continue
        
        if earliest_event:
            event_time_str = earliest_event["time"]
            try:
                event_time = datetime.strptime(event_time_str, "%I:%M %p").time()
                tomorrow_event = now.replace(
                    hour=event_time.hour, 
                    minute=event_time.minute
                ) + timedelta(days=1)
                
                bedtime = tomorrow_event - timedelta(hours=rec_sleep + 1.5)
                report_lines.append(f"- Recommended bedtime: ~{bedtime.strftime('%I:%M %p')}")
                report_lines.append(f"  (for {format_hours_to_hm(rec_sleep)} sleep before {earliest_event['title']})")
            except Exception:
                report_lines.append(f"- Aim for {format_hours_to_hm(rec_sleep)} of sleep tonight")
        else:
            report_lines.append(f"- Aim for {format_hours_to_hm(rec_sleep)} of sleep tonight")
        
        report_lines.append("")
    
    # TOMORROW'S CALENDAR
    if data["tomorrow_calendar"]:
        report_lines.append(f"**Tomorrow's Schedule ({tomorrow}):**")
        for event in data["tomorrow_calendar"]:
            if event.get('url'):
                event_text = f"- {event['time']} - [{event['title']}]({event['url']})"
            else:
                event_text = f"- {event['time']} - {event['title']}"
            report_lines.append(event_text)
            if event['location']:
                report_lines.append(f"  {event['location']}")
    else:
        report_lines.append(f"**Tomorrow's Schedule:** No scheduled events")
    report_lines.append("")
    
    # WEATHER FOR TOMORROW
    if data["weather"]:
        w = data["weather"]
        report_lines.append("**Tomorrow's Weather:**")
        report_lines.append(f"- {w['temp_min']:.1f}C - {w['temp_max']:.1f}C")
        report_lines.append(f"- {w['description'].capitalize()}")
        report_lines.append(f"- Humidity: {w['humidity']}%")
        report_lines.append("")
    
    # AI-GENERATED EVENING INSIGHT
    report_lines.append("**Evening Insight:**")
    
    context = f"""Generate a brief, autism-friendly evening insight.

User Profile:
- Autistic (prefer clear, structured, predictable communication)
- Active runner/fitness enthusiast
- Values routine and concrete recommendations

Today's Data:
- Date: {data['date']}
- Steps: {data['daily_stats']['steps'] if data['daily_stats'] else 'N/A'}
- Floors: {data['daily_stats']['floors_up'] if data['daily_stats'] else 'N/A'}
- Workouts: {len(data['today_workouts'])} activities
- Body Battery: {data['body_battery'] if data['body_battery'] else 'N/A'}/100
- Stress Level: {data['stress']['avg'] if data['stress'] else 'N/A'}/100
- Last Sleep Score: {data['last_sleep']['sleep_score'] if data['last_sleep'] else 'N/A'}/100
- Last Sleep Duration: {format_hours_to_hm(data['last_sleep']['total_sleep_hours']) if data['last_sleep'] else 'N/A'}
- Tomorrow's Events: {len(data['tomorrow_calendar'])} scheduled
- Weather Tomorrow: {data['weather']['description'] if data['weather'] else 'N/A'}

Guidelines:
1. Focus on evening wind-down and preparation for tomorrow
2. Be clear, direct, and specific (no vague language)
3. Consider sensory sensitivities for evening routine
4. Acknowledge today's accomplishments
5. Provide structured preparation steps for tomorrow
6. Suggest concrete evening activities (reading, stretching, etc.)
7. Keep it brief (3-4 bullet points max)
"""
    
    try:
        insight = llm_service.call(
            system_prompt="You are a supportive health coach who understands autism. Be clear, direct, and structured. Focus on evening wind-down.",
            user_content=context,
            history=[],
            stream=False
        )
        report_lines.append(insight.strip())
    except Exception as e:
        report_lines.append("- Great work today! Time to wind down")
        report_lines.append("- Prepare for tomorrow and get good rest")
        print(f"AI insight generation error: {e}")
    
    report_lines.append("")
    report_lines.append("Have a restful evening!")
    
    return "\n".join(report_lines)
