"""
Evening Report Generator
Creates comprehensive autism-friendly evening health & preparation report
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import requests
import os


def generate_evening_report(health_coach, calendar_service, llm_service) -> str:
    """
    Generate comprehensive evening report.
    
    Includes:
    - Today's activity summary (steps, floors)
    - Body Battery status
    - Weather for tomorrow
    - Sleep recommendation based on last night
    - Tomorrow's calendar
    - AI-generated autism-friendly evening insight
    """
    from app.core.config import settings
    user_tz = settings.user_timezone
    now = datetime.now(user_tz)
    today = now.strftime("%A, %B %d, %Y")
    tomorrow = (now + timedelta(days=1)).strftime("%A, %B %d, %Y")
    
    # Collect all data
    data = {
        "date": today,
        "tomorrow_date": tomorrow,
        "daily_stats": None,
        "body_battery": None,
        "last_sleep": None,
        "tomorrow_calendar": [],
        "weather": None,
    }
    
    # 1. TODAY'S ACTIVITY (Steps, Floors from DailyStats)
    try:
        # Query today's daily stats
        query = f"""
        SELECT totalSteps, floorsAscended, floorsDescended, 
               activeKilocalories, totalDistanceMeters,
               bodyBatteryLowestValue, bodyBatteryHighestValue,
               bodyBatteryAtWakeTime
        FROM DailyStats 
        ORDER BY time DESC 
        LIMIT 1
        """
        result = health_coach.client.query(query)
        points = list(result.get_points())
        if points:
            point = points[0]
            data["daily_stats"] = {
                "steps": int(point.get("totalSteps", 0)),
                "floors_up": round(point.get("floorsAscended", 0), 1),
                "floors_down": round(point.get("floorsDescended", 0), 1),
                "calories": int(point.get("activeKilocalories", 0)),
                "distance_km": round(point.get("totalDistanceMeters", 0) / 1000, 2),
                "body_battery_wake": int(point.get("bodyBatteryAtWakeTime", 0)),
                "body_battery_high": int(point.get("bodyBatteryHighestValue", 0)),
                "body_battery_low": int(point.get("bodyBatteryLowestValue", 0)),
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
    
    # 3. LAST NIGHT'S SLEEP (for recommendation)
    try:
        sleep_data = health_coach.get_sleep_data(days=1)
        if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
            data["last_sleep"] = sleep_data["sleep_records"][0]
    except Exception as e:
        print(f"Sleep data error: {e}")
    
    # 4. TOMORROW'S CALENDAR
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
    
    # 5. WEATHER FOR TOMORROW
    try:
        weather_api_key = os.getenv('WEATHER_API_KEY')
        city = os.getenv('WEATHER_CITY', 'São Paulo')
        
        if weather_api_key:
            # Get forecast for tomorrow
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={weather_api_key}&units=metric&lang=pt"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                forecast = response.json()
                # Get tomorrow's forecast (find entries for next day)
                tomorrow_forecasts = []
                tomorrow_date = (now + timedelta(days=1)).date()
                
                for entry in forecast.get('list', []):
                    entry_time = datetime.fromtimestamp(entry['dt'], tz=user_tz)
                    if entry_time.date() == tomorrow_date:
                        tomorrow_forecasts.append(entry)
                
                if tomorrow_forecasts:
                    # Get midday forecast (around noon)
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
    report_lines.append(f"🌙 **Good Evening!**")
    report_lines.append(f"📅 {today}")
    report_lines.append("")
    
    # TODAY'S ACTIVITY SUMMARY
    if data["daily_stats"]:
        stats = data["daily_stats"]
        report_lines.append("📊 **Today's Activity:**")
        report_lines.append(f"• Steps: {stats['steps']:,}")
        report_lines.append(f"• Floors: {stats['floors_up']} up, {stats['floors_down']} down")
        report_lines.append(f"• Distance: {stats['distance_km']} km")
        report_lines.append(f"• Active Calories: {stats['calories']}")
        
        # Activity assessment
        if stats['steps'] >= 10000:
            report_lines.append("  ✅ Great activity level today!")
        elif stats['steps'] >= 7000:
            report_lines.append("  👍 Good movement today")
        else:
            report_lines.append("  💡 Consider more movement tomorrow")
        report_lines.append("")
    
    # BODY BATTERY
    if data["body_battery"] and data["daily_stats"]:
        bb_current = data["body_battery"]
        bb_wake = data["daily_stats"]["body_battery_wake"]
        bb_high = data["daily_stats"]["body_battery_high"]
        bb_low = data["daily_stats"]["body_battery_low"]
        
        report_lines.append("🔋 **Body Battery:**")
        report_lines.append(f"• Current: {bb_current}/100")
        report_lines.append(f"• Today's Range: {bb_low} → {bb_high}")
        report_lines.append(f"• Started at: {bb_wake}/100")
        
        # Evening battery assessment
        if bb_current >= 50:
            report_lines.append("  ✅ Good energy remaining for evening")
        elif bb_current >= 30:
            report_lines.append("  👍 Moderate energy - consider winding down")
        else:
            report_lines.append("  😴 Low energy - prioritize rest")
        report_lines.append("")
    
    # SLEEP RECOMMENDATION
    if data["last_sleep"]:
        sleep = data["last_sleep"]
        report_lines.append("😴 **Sleep Recommendation:**")
        report_lines.append(f"• Last night: {sleep['total_sleep_hours']}h (score: {sleep['sleep_score']}/100)")
        
        # Calculate recommended bedtime based on last night
        if sleep['sleep_score'] < 70:
            report_lines.append(f"  ⚠️ Sleep quality was low - aim for earlier bedtime tonight")
            rec_sleep = 8.5
        elif sleep['total_sleep_hours'] < 7:
            report_lines.append(f"  💡 You got less than 7h - try for 8h tonight")
            rec_sleep = 8.0
        else:
            report_lines.append(f"  ✅ Sleep was good - maintain similar schedule")
            rec_sleep = sleep['total_sleep_hours']
        
        # Calculate bedtime recommendation
        # Check tomorrow's calendar for earliest REAL event (not all-day, after 6 AM)
        earliest_event = None
        if data["tomorrow_calendar"]:
            for event in data["tomorrow_calendar"]:
                event_time_str = event["time"]
                try:
                    event_time = datetime.strptime(event_time_str, "%I:%M %p").time()
                    # Skip events before 6 AM (likely all-day events or overnight)
                    if event_time.hour >= 6:
                        earliest_event = event
                        break
                except Exception:
                    continue
        
        if earliest_event:
            # Parse earliest event time and subtract sleep time + 1.5h buffer
            event_time_str = earliest_event["time"]
            try:
                event_time = datetime.strptime(event_time_str, "%I:%M %p").time()
                tomorrow_event = now.replace(
                    hour=event_time.hour, 
                    minute=event_time.minute
                ) + timedelta(days=1)
                
                # Calculate bedtime (event time - sleep hours - 1.5h wake buffer)
                bedtime = tomorrow_event - timedelta(hours=rec_sleep + 1.5)
                report_lines.append(f"• Recommended bedtime: ~{bedtime.strftime('%I:%M %p')}")
                report_lines.append(f"  (for {rec_sleep}h sleep before {earliest_event['title']})")
            except Exception:
                report_lines.append(f"• Aim for {rec_sleep} hours of sleep tonight")
        else:
            report_lines.append(f"• Aim for {rec_sleep} hours of sleep tonight")
        
        report_lines.append("")
    
    # TOMORROW'S CALENDAR
    if data["tomorrow_calendar"]:
        report_lines.append(f"📅 **Tomorrow's Schedule ({tomorrow}):**")
        for event in data["tomorrow_calendar"]:
            # Create clickable link if URL exists (Telegram markdown format)
            if event.get('url'):
                event_text = f"• {event['time']} - [{event['title']}]({event['url']})"
            else:
                event_text = f"• {event['time']} - {event['title']}"
            report_lines.append(event_text)
            if event['location']:
                report_lines.append(f"  📍 {event['location']}")
    else:
        report_lines.append(f"📅 **Tomorrow's Schedule:** No scheduled events")
    report_lines.append("")
    
    # WEATHER FOR TOMORROW
    if data["weather"]:
        w = data["weather"]
        report_lines.append("🌤️ **Tomorrow's Weather:**")
        report_lines.append(f"• {w['temp_min']:.1f}°C - {w['temp_max']:.1f}°C")
        report_lines.append(f"• {w['description'].capitalize()}")
        report_lines.append(f"• Humidity: {w['humidity']}%")
        report_lines.append("")
    
    # AI-GENERATED EVENING INSIGHT
    report_lines.append("🧠 **Evening Insight:**")
    
    # Build context for LLM
    context = f"""Generate a brief, autism-friendly evening insight.

User Profile:
- Autistic (prefer clear, structured, predictable communication)
- Active runner/fitness enthusiast
- Values routine and concrete recommendations

Today's Data:
- Date: {data['date']}
- Steps: {data['daily_stats']['steps'] if data['daily_stats'] else 'N/A'}
- Floors: {data['daily_stats']['floors_up'] if data['daily_stats'] else 'N/A'}
- Body Battery: {data['body_battery'] if data['body_battery'] else 'N/A'}/100
- Last Sleep Score: {data['last_sleep']['sleep_score'] if data['last_sleep'] else 'N/A'}/100
- Last Sleep Duration: {data['last_sleep']['total_sleep_hours'] if data['last_sleep'] else 'N/A'}h
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
        # Fallback insight
        report_lines.append("• Great work today! Time to wind down")
        report_lines.append("• Prepare for tomorrow and get good rest")
        print(f"AI insight generation error: {e}")
    
    report_lines.append("")
    report_lines.append("Have a restful evening! 🌟")
    
    return "\n".join(report_lines)
