"""
Morning Report Generator
Creates comprehensive autism-friendly morning health & schedule report
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import requests
import os


def generate_morning_report(health_coach, calendar_service, llm_service) -> str:
    """
    Generate comprehensive morning report.
    
    Includes:
    - Today's calendar
    - Today's reminders
    - Sleep quality
    - Training readiness (Garmin)
    - HRV status
    - Body Battery
    - Recovery time
    - Weather
    - AI-generated autism-friendly insight
    """
    user_tz = timezone(timedelta(hours=-3))
    now = datetime.now(user_tz)
    today = now.strftime("%A, %B %d, %Y")
    
    # Collect all data
    data = {
        "date": today,
        "calendar": [],
        "reminders": [],
        "sleep": None,
        "recovery": None,
        "weather": None,
    }
    
    # 1. CALENDAR
    try:
        events = calendar_service.get_today_events()
        if events:
            for event in events:
                data["calendar"].append({
                    "time": event.start.strftime("%I:%M %p"),
                    "title": event.summary,
                    "location": event.location if hasattr(event, 'location') else None,
                    "url": event.url if hasattr(event, 'url') else None
                })
    except Exception as e:
        print(f"Calendar error: {e}")
    
    # 2. REMINDERS FOR TODAY
    try:
        from app.services.reminders import reminder_service
        pending = reminder_service.list_pending_reminders()
        
        # Filter for today's reminders (from now until end of day)
        # Get the date we're reporting for (in case this runs early morning, we want full day)
        report_date = now.date()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        for reminder in pending:
            # Handle timezone-aware/naive datetime comparison
            remind_at = reminder.remind_at
            if remind_at.tzinfo is None and now.tzinfo is not None:
                remind_at = remind_at.replace(tzinfo=now.tzinfo)
            elif remind_at.tzinfo is not None and now.tzinfo is None:
                remind_at = remind_at.replace(tzinfo=None)
            
            # Check if reminder is on the same day we're reporting for
            if start_of_day <= remind_at <= end_of_day:
                data["reminders"].append({
                    "time": remind_at.strftime("%I:%M %p"),
                    "message": reminder.message
                })
    except Exception as e:
        print(f"Reminders error: {e}")
    
    # 3. SLEEP DATA
    try:
        sleep_data = health_coach.get_sleep_data(days=1)
        if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
            data["sleep"] = sleep_data["sleep_records"][0]
    except Exception as e:
        print(f"Sleep data error: {e}")
    
    # 3. RECOVERY STATUS (includes Training Readiness, HRV, Body Battery, Recovery Time)
    try:
        data["recovery"] = health_coach.get_recovery_status()
    except Exception as e:
        print(f"Recovery data error: {e}")
    
    # 4. WEATHER
    try:
        weather_api_key = os.getenv('WEATHER_API_KEY')
        city = os.getenv('WEATHER_CITY', 'São Paulo')  # Default to São Paulo
        
        if weather_api_key:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric&lang=pt"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                weather = response.json()
                data["weather"] = {
                    "temp": weather['main']['temp'],
                    "feels_like": weather['main']['feels_like'],
                    "description": weather['weather'][0]['description'],
                    "humidity": weather['main']['humidity']
                }
    except Exception as e:
        print(f"Weather fetch skipped: {e}")
    
    # Now build the report
    report_lines = []
    
    # Header
    report_lines.append(f"☀️ **Good Morning!**")
    report_lines.append(f"📅 {today}")
    report_lines.append("")
    
    # CALENDAR
    if data["calendar"]:
        report_lines.append("📅 **Today's Schedule:**")
        for event in data["calendar"]:
            # Create clickable link if URL exists (Telegram markdown format)
            if event.get('url'):
                event_text = f"• {event['time']} - [{event['title']}]({event['url']})"
            else:
                event_text = f"• {event['time']} - {event['title']}"
            report_lines.append(event_text)
            if event['location']:
                report_lines.append(f"  📍 {event['location']}")
    else:
        report_lines.append("📅 **Today's Schedule:** No scheduled events")
    report_lines.append("")
    
    # REMINDERS
    if data["reminders"]:
        report_lines.append("⏰ **Today's Reminders:**")
        for reminder in data["reminders"]:
            report_lines.append(f"• {reminder['time']} - {reminder['message']}")
        report_lines.append("")
    
    # SLEEP
    if data["sleep"]:
        sleep = data["sleep"]
        report_lines.append("😴 **Last Night's Sleep:**")
        report_lines.append(f"• Duration: {sleep['total_sleep_hours']} hours")
        report_lines.append(f"• Sleep Score: {sleep['sleep_score']}/100")
        report_lines.append(f"• Deep: {sleep['deep_sleep_hours']}h | REM: {sleep['rem_sleep_hours']}h")
        report_lines.append(f"• Resting HR: {sleep['resting_hr']} bpm")
        
        # Sleep quality note
        if sleep['sleep_score'] >= 80:
            report_lines.append("  ✅ Excellent recovery!")
        elif sleep['sleep_score'] >= 70:
            report_lines.append("  👍 Good sleep quality")
        else:
            report_lines.append("  ⚠️ Consider prioritizing rest today")
        report_lines.append("")
    
    # RECOVERY & TRAINING READINESS
    if data["recovery"]:
        recovery = data["recovery"]
        report_lines.append("💪 **Recovery & Readiness:**")
        
        if 'training_readiness' in recovery:
            tr = recovery['training_readiness']
            report_lines.append(f"• Training Readiness: {tr}/100")
            if tr >= 75:
                report_lines.append("  ✅ Ready for intense training")
            elif tr >= 50:
                report_lines.append("  👍 Moderate workout recommended")
            else:
                report_lines.append("  ⚠️ Focus on recovery today")
        
        # HRV Status
        if 'hrv_7day_avg' in recovery:
            hrv_avg = recovery['hrv_7day_avg']
            hrv_latest = recovery.get('hrv_latest', 0)
            report_lines.append(f"• HRV: {hrv_latest} ms (7-day avg: {hrv_avg} ms)")
        elif 'hrv_latest' in recovery:
            report_lines.append(f"• HRV: {recovery['hrv_latest']} ms")
        
        # Body Battery with wake/current comparison
        if 'body_battery' in recovery and 'body_battery_wake' in recovery:
            bb_current = recovery['body_battery']
            bb_wake = recovery['body_battery_wake']
            bb_change = bb_current - bb_wake
            sign = "+" if bb_change >= 0 else ""
            report_lines.append(f"• Body Battery: {bb_current}/100 ({sign}{bb_change} since wake at {bb_wake})")
        elif 'body_battery' in recovery:
            bb = recovery['body_battery']
            report_lines.append(f"• Body Battery: {bb}/100")
        
        if 'recovery_time' in recovery and recovery['recovery_time'] > 0:
            rt = recovery['recovery_time']
            report_lines.append(f"• Recovery Time: {rt} hours remaining")
        
        report_lines.append("")
    
    # WEATHER
    if data["weather"]:
        w = data["weather"]
        report_lines.append("🌤️ **Weather Today:**")
        report_lines.append(f"• {w['temp']:.1f}°C (feels like {w['feels_like']:.1f}°C)")
        report_lines.append(f"• {w['description'].capitalize()}")
        report_lines.append(f"• Humidity: {w['humidity']}%")
        report_lines.append("")
    
    # AI-GENERATED INSIGHT (autism-friendly)
    report_lines.append("🧠 **Today's Personalized Insight:**")
    
    # Build context for LLM
    context = f"""Generate a brief, autism-friendly insight for the morning report.

User Profile:
- Autistic (prefer clear, structured, predictable communication)
- Active runner/fitness enthusiast
- Values routine and concrete recommendations

Today's Data:
- Date: {data['date']}
- Calendar: {len(data['calendar'])} events scheduled
- Sleep Score: {data['sleep']['sleep_score'] if data['sleep'] else 'N/A'}/100
- Sleep Duration: {data['sleep']['total_sleep_hours'] if data['sleep'] else 'N/A'} hours
- Training Readiness: {data['recovery'].get('training_readiness', 'N/A') if data['recovery'] else 'N/A'}/100
- Body Battery: {data['recovery'].get('body_battery', 'N/A') if data['recovery'] else 'N/A'}/100
- Weather: {data['weather']['description'] if data['weather'] else 'N/A'}, {data['weather']['temp'] if data['weather'] else 'N/A'}°C

Guidelines:
1. Be clear, direct, and specific (no vague language)
2. Provide structured, actionable recommendations
3. Consider sensory sensitivities (weather, crowds, etc.)
4. Acknowledge any scheduling demands
5. Suggest concrete coping strategies if day seems challenging
6. Be encouraging but realistic
7. Keep it brief (3-4 bullet points max)
"""
    
    try:
        insight = llm_service.call(
            system_prompt="You are a supportive health coach who understands autism. Be clear, direct, and structured.",
            user_content=context,
            history=[],
            stream=False
        )
        report_lines.append(insight.strip())
    except Exception as e:
        # Fallback insight
        report_lines.append("• Your health metrics look good for today")
        report_lines.append("• Stay hydrated and maintain your routine")
        print(f"AI insight generation error: {e}")
    
    report_lines.append("")
    report_lines.append("Have a great day! 🌟")
    
    return "\n".join(report_lines)
