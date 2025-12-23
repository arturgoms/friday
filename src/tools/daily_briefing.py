"""
Friday 3.0 Daily Briefing Tools

Morning and evening reports with personalized insights.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.registry import friday_tool

logger = logging.getLogger(__name__)

# Brazil timezone (UTC-3)
BRT = timezone(timedelta(hours=-3))


# =============================================================================
# InfluxDB Helper
# =============================================================================

_influx_client = None

def _get_influx_client():
    """Get or create InfluxDB client."""
    global _influx_client
    
    if _influx_client is not None:
        return _influx_client
    
    try:
        from influxdb import InfluxDBClient
        
        config_path = Path(__file__).parent.parent.parent / "config" / "influxdb_mcp.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            return None
        
        _influx_client = InfluxDBClient(
            host=config.get("host", "localhost"),
            port=config.get("port", 8086),
            username=config.get("username", ""),
            password=config.get("password", ""),
            database=config.get("database", "health")
        )
        _influx_client.ping()
        return _influx_client
        
    except Exception as e:
        logger.error(f"InfluxDB connection error: {e}")
        return None


def _query(query: str) -> List[Dict]:
    """Execute InfluxDB query."""
    client = _get_influx_client()
    if not client:
        return []
    try:
        result = client.query(query)
        return list(result.get_points())
    except Exception as e:
        logger.error(f"Query error: {e}")
        return []


def _format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration."""
    if not seconds:
        return "0m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h"
    return f"{minutes}m"


# =============================================================================
# Morning Report
# =============================================================================

def _check_garmin_sync_freshness() -> tuple:
    """Check if Garmin data is fresh enough for today's report.
    
    Returns:
        (is_fresh, hours_ago, last_sync_time_str)
    """
    query = 'SELECT last("HeartRate") FROM "HeartRateIntraday"'
    points = _query(query)
    
    if not points:
        return False, None, None
    
    point = points[0]
    last_time_str = point.get("time", "")
    
    if not last_time_str:
        return False, None, None
    
    try:
        from datetime import timezone as tz
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        now_utc = datetime.now(tz.utc)
        hours_ago = (now_utc - last_time).total_seconds() / 3600
        
        # Convert to BRT for display
        last_time_brt = last_time.astimezone(BRT)
        time_str = last_time_brt.strftime("%H:%M")
        
        # Consider fresh if synced within last 6 hours
        is_fresh = hours_ago < 6
        return is_fresh, hours_ago, time_str
        
    except Exception:
        return False, None, None


@friday_tool(name="get_morning_report")
def get_morning_report() -> str:
    """Get morning briefing with sleep, energy, calendar, and weather."""
    now = datetime.now(BRT)
    today_str = now.strftime("%Y-%m-%d")
    
    lines = [
        f"Good morning, Artur! It's {now.strftime('%A, %B %d')}.",
        ""
    ]
    
    insights = []
    warnings = []
    
    # --- Check Garmin sync freshness ---
    garmin_fresh, hours_ago, last_sync_time = _check_garmin_sync_freshness()
    
    if not garmin_fresh:
        if hours_ago is not None:
            lines.append(f"⚠️ GARMIN DATA STALE (last sync: {hours_ago:.1f}h ago at {last_sync_time})")
            lines.append("Health metrics below may be outdated. Sync your watch!")
            lines.append("")
            warnings.append("Garmin data is stale - sync your watch.")
        else:
            lines.append("⚠️ GARMIN SYNC UNAVAILABLE")
            lines.append("Could not verify data freshness.")
            lines.append("")
    
    # --- Sleep ---
    lines.append("🛏️ LAST NIGHT'S SLEEP")
    
    sleep_query = """
    SELECT sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds,
           avgOvernightHrv, restingHeartRate, time
    FROM SleepSummary ORDER BY time DESC LIMIT 1
    """
    sleep_data = _query(sleep_query)
    
    sleep_score = 0
    if not garmin_fresh:
        lines.append("  Data unavailable (Garmin not synced)")
    elif sleep_data:
        sleep = sleep_data[0]
        sleep_date = sleep.get("time", "").split("T")[0]
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        if sleep_date in [today_str, yesterday]:
            deep = sleep.get("deepSleepSeconds", 0) or 0
            light = sleep.get("lightSleepSeconds", 0) or 0
            rem = sleep.get("remSleepSeconds", 0) or 0
            total_hours = (deep + light + rem) / 3600
            
            sleep_score = sleep.get("sleepScore", 0) or 0
            hrv = int(sleep.get("avgOvernightHrv", 0) or 0)
            rhr = int(sleep.get("restingHeartRate", 0) or 0)
            
            if sleep_score >= 80:
                quality = "Excellent night!"
                insights.append("Great sleep - you're ready for a productive day.")
            elif sleep_score >= 65:
                quality = "Good night"
            elif sleep_score >= 50:
                quality = "Fair night"
                warnings.append("Sleep was below average. Consider earlier bedtime tonight.")
            else:
                quality = "Rough night"
                warnings.append("Poor sleep - take it easy today.")
            
            lines.append(f"Score: {sleep_score}/100 ({quality})")
            lines.append(f"Duration: {total_hours:.1f}h (Deep: {_format_duration(deep)}, REM: {_format_duration(rem)})")
            lines.append(f"HRV: {hrv}ms | RHR: {rhr}bpm")
        else:
            lines.append(f"  Data outdated ({sleep_date})")
    else:
        lines.append("  No sleep data available")
    
    # --- Energy & Recovery ---
    lines.append("")
    lines.append("🔋 ENERGY")
    
    if not garmin_fresh:
        lines.append("  Data unavailable (Garmin not synced)")
    else:
        bb_query = "SELECT bodyBatteryAtWakeTime, time FROM DailyStats ORDER BY time DESC LIMIT 1"
        bb_data = _query(bb_query)
        
        body_battery = 0
        if bb_data:
            bb_date = bb_data[0].get("time", "").split("T")[0]
            if bb_date == today_str:
                body_battery = int(bb_data[0].get("bodyBatteryAtWakeTime", 0) or 0)
                
                if body_battery >= 80:
                    bb_desc = "Fully charged!"
                    insights.append("High energy - great day for challenging tasks.")
                elif body_battery >= 60:
                    bb_desc = "Good levels"
                elif body_battery >= 40:
                    bb_desc = "Moderate"
                else:
                    bb_desc = "Low - pace yourself"
                    warnings.append("Low energy - avoid overexertion.")
                
                lines.append(f"Body Battery: {body_battery}/100 ({bb_desc})")
            else:
                lines.append(f"  Data from {bb_date} (not today)")
        
        tr_query = "SELECT score, level, time FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        tr_data = _query(tr_query)
        
        if tr_data:
            tr_date = tr_data[0].get("time", "").split("T")[0]
            if tr_date == today_str:
                tr_score = int(tr_data[0].get("score", 0) or 0)
                tr_level = tr_data[0].get("level", "")
                lines.append(f"Training Readiness: {tr_score}/100 ({tr_level})")
                
                if tr_score < 50:
                    warnings.append("Low training readiness - rest or light activity only.")
    
    # --- Calendar ---
    lines.append("")
    lines.append("📅 TODAY'S SCHEDULE")
    
    try:
        from src.tools.calendar import get_calendar_manager
        
        manager = get_calendar_manager()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        events = manager.get_all_events(start, end)
        
        if events:
            meeting_count = 0
            for event in events:
                if event.all_day:
                    lines.append(f"  📌 {event.title}")
                else:
                    cal_icon = "🏠" if event.calendar == "personal" else "💼"
                    lines.append(f"  {cal_icon} {event.start.strftime('%H:%M')}-{event.end.strftime('%H:%M')}: {event.title}")
                    meeting_count += 1
            
            if meeting_count > 5:
                warnings.append(f"Heavy meeting day ({meeting_count}). Block time for breaks.")
        else:
            lines.append("  No events - open day!")
            insights.append("Clear calendar - good for deep work.")
            
    except Exception as e:
        lines.append(f"  Calendar unavailable")
    
    # --- Weather ---
    lines.append("")
    lines.append("🌤️ WEATHER")
    
    try:
        from src.tools.weather import get_current_weather, will_it_rain
        
        weather = get_current_weather()
        if weather:
            for line in weather.split('\n')[1:5]:
                if line.strip() and not line.startswith('='):
                    lines.append(f"  {line.strip()}")
        
        rain_info = will_it_rain()
        if rain_info and "expected" in rain_info.lower():
            lines.append(f"  ☔ Rain expected - bring umbrella!")
            warnings.append("Rain expected today.")
            
    except Exception:
        lines.append("  Weather unavailable")
    
    # --- Insights ---
    if warnings or insights:
        lines.append("")
        lines.append("💡 FOR TODAY")
        for w in warnings:
            lines.append(f"  ⚠️ {w}")
        for i in insights:
            lines.append(f"  ✨ {i}")
    
    return "\n".join(lines)


# =============================================================================
# Evening Report
# =============================================================================

@friday_tool(name="get_evening_report")
def get_evening_report() -> str:
    """Get evening report with activity summary and sleep recommendations."""
    now = datetime.now(BRT)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    lines = [
        f"Good evening, Artur! Here's your day summary.",
        ""
    ]
    
    sleep_factors = {
        "stress": 0,
        "steps": 0,
        "active_minutes": 0,
        "meetings": 0,
        "body_battery": 50,
        "high_stress_min": 0,
    }
    
    # --- Check Garmin sync freshness ---
    garmin_fresh, hours_ago, last_sync_time = _check_garmin_sync_freshness()
    
    if not garmin_fresh:
        if hours_ago is not None:
            lines.append(f"⚠️ GARMIN DATA STALE (last sync: {hours_ago:.1f}h ago at {last_sync_time})")
            lines.append("Activity metrics below may be incomplete. Sync your watch!")
            lines.append("")
        else:
            lines.append("⚠️ GARMIN SYNC UNAVAILABLE")
            lines.append("")
    
    # --- Activity ---
    lines.append("🏃 ACTIVITY")
    
    steps_query = f"""
    SELECT totalSteps, totalDistanceMeters
    FROM DailyStats
    WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC LIMIT 1
    """
    steps_data = _query(steps_query)
    
    if steps_data:
        steps = int(steps_data[0].get("totalSteps", 0) or 0)
        distance = (steps_data[0].get("totalDistanceMeters", 0) or 0) / 1000
        sleep_factors["steps"] = steps
        
        if steps >= 10000:
            steps_note = "Great!"
        elif steps >= 7000:
            steps_note = "Good"
        elif steps >= 5000:
            steps_note = "Moderate"
        else:
            steps_note = "Low"
        
        lines.append(f"Steps: {steps:,} ({steps_note}) | Distance: {distance:.1f}km")
    
    activity_query = f"""
    SELECT activityName, movingDuration, calories
    FROM ActivitySummary
    WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    """
    activities = _query(activity_query)
    
    if activities:
        total_active = sum(a.get("movingDuration", 0) or 0 for a in activities)
        sleep_factors["active_minutes"] = int(total_active / 60)
        
        for a in activities:
            name = a.get("activityName", "Activity")
            dur = _format_duration(a.get("movingDuration", 0) or 0)
            cal = int(a.get("calories", 0) or 0)
            if dur != "0m":
                lines.append(f"  🏋️ {name}: {dur}, {cal} cal")
    
    # --- Stress ---
    lines.append("")
    lines.append("😰 STRESS")
    
    stress_query = f"""
    SELECT stressAvg, highStressDuration, restStressDuration
    FROM DailyStats
    WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC LIMIT 1
    """
    stress_data = _query(stress_query)
    
    if stress_data:
        stress_avg = int(stress_data[0].get("stressAvg", 0) or 0)
        high_sec = stress_data[0].get("highStressDuration", 0) or 0
        rest_sec = stress_data[0].get("restStressDuration", 0) or 0
        
        sleep_factors["stress"] = stress_avg
        sleep_factors["high_stress_min"] = int(high_sec / 60)
        
        if stress_avg < 30:
            stress_note = "Relaxed day"
        elif stress_avg < 50:
            stress_note = "Moderate"
        else:
            stress_note = "Stressful day"
        
        lines.append(f"Average: {stress_avg}/100 ({stress_note})")
        lines.append(f"High stress: {_format_duration(high_sec)} | Rest: {_format_duration(rest_sec)}")
    
    current_query = "SELECT stressLevel FROM StressIntraday ORDER BY time DESC LIMIT 1"
    current = _query(current_query)
    if current:
        curr_stress = int(current[0].get("stressLevel", 0) or 0)
        sleep_factors["current_stress"] = curr_stress
        lines.append(f"Current: {curr_stress}/100")
    
    # --- Body Battery ---
    lines.append("")
    lines.append("🔋 ENERGY")
    
    bb_query = 'SELECT "BodyBatteryLevel" FROM "BodyBatteryIntraday" ORDER BY time DESC LIMIT 1'
    bb_current = _query(bb_query)
    
    bb_wake_query = f"""
    SELECT bodyBatteryAtWakeTime 
    FROM DailyStats 
    WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC LIMIT 1
    """
    bb_wake = _query(bb_wake_query)
    
    if bb_current:
        current_bb = int(bb_current[0].get("BodyBatteryLevel", 0) or 0)
        sleep_factors["body_battery"] = current_bb
        
        if bb_wake:
            wake_bb = int(bb_wake[0].get("bodyBatteryAtWakeTime", 0) or 0)
            drain = wake_bb - current_bb
            lines.append(f"Current: {current_bb}/100 (started at {wake_bb}, used {drain})")
        else:
            lines.append(f"Current: {current_bb}/100")
    
    # --- Meetings ---
    lines.append("")
    lines.append("📅 MEETINGS")
    
    try:
        from src.tools.calendar import get_calendar_manager
        
        manager = get_calendar_manager()
        end = now.replace(hour=23, minute=59, second=59)
        events = manager.get_all_events(today_start, end)
        
        meetings = [e for e in events if not e.all_day]
        meeting_count = len(meetings)
        sleep_factors["meetings"] = meeting_count
        
        total_min = sum((e.end - e.start).total_seconds() / 60 for e in meetings)
        
        lines.append(f"{meeting_count} meetings, {_format_duration(total_min * 60)} total")
            
    except Exception:
        lines.append("Calendar unavailable")
    
    # --- Sleep Recommendation ---
    lines.append("")
    lines.append("💤 SLEEP RECOMMENDATION")
    
    tips = []
    bedtime_adj = 0
    
    if sleep_factors["stress"] > 50:
        tips.append("High stress - wind down early with relaxation")
        bedtime_adj -= 30
    
    if sleep_factors["meetings"] > 5:
        tips.append("Many meetings - give your brain screen-free time before bed")
        bedtime_adj -= 15
    
    if sleep_factors["steps"] < 5000 and sleep_factors["active_minutes"] < 30:
        tips.append("Low activity - a short walk could help sleep quality")
    
    if sleep_factors["active_minutes"] > 60:
        tips.append("Good workout - your body needs quality recovery sleep")
        bedtime_adj -= 15
    
    if sleep_factors["body_battery"] < 30:
        tips.append("Low energy - prioritize early bedtime")
        bedtime_adj -= 30
    
    if sleep_factors.get("high_stress_min", 0) > 120:
        tips.append("Extended stress - avoid screens 1h before bed")
    
    if not tips:
        tips.append("Normal day - stick to your regular schedule")
    
    normal_bedtime = now.replace(hour=22, minute=30, second=0, microsecond=0)
    suggested = normal_bedtime + timedelta(minutes=bedtime_adj)
    if suggested < now:
        suggested = now + timedelta(minutes=30)
    
    lines.append(f"Suggested bedtime: {suggested.strftime('%H:%M')}")
    
    for tip in tips:
        lines.append(f"  • {tip}")
    
    # Forecast
    good = []
    if sleep_factors["stress"] < 40:
        good.append("low stress")
    if sleep_factors["body_battery"] > 30:
        good.append("energy reserves")
    if sleep_factors["active_minutes"] >= 30:
        good.append("physical activity")
    
    if len(good) >= 2:
        lines.append(f"Outlook: Good ({', '.join(good)})")
    else:
        lines.append("Outlook: May need extra wind-down time")
    
    return "\n".join(lines)
