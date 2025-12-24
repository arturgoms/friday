"""
Friday 3.0 Health Tools

Garmin health data tools using InfluxDB.
Provides access to running, sleep, recovery, and wellness metrics.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.core.constants import BRT
from src.core.influxdb import query as _query
from src.core.registry import friday_tool
from src.core.utils import format_duration, format_pace

logger = logging.getLogger(__name__)


# =============================================================================
# Running & Training Tools
# =============================================================================

@friday_tool(name="get_recent_runs")
def get_recent_runs(limit: int = 10, days: int = 30) -> str:
    """Get recent running activities with pace, HR, distance, and duration.
    
    Args:
        limit: Number of runs to return (default: 10)
        days: Look back period in days (default: 30)
    
    Returns:
        Recent running activities with details
    """
    start = datetime.now(BRT) - timedelta(days=days)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = f"""
    SELECT activityName, distance, movingDuration, averageSpeed, 
           averageHR, maxHR, calories, elevationGain, aerobicTE
    FROM ActivitySummary
    WHERE time >= '{start_str}'
    AND activityType = 'running'
    ORDER BY time DESC
    LIMIT {limit}
    """
    
    points = _query(query)
    
    if not points:
        return "No running data found for this period"
    
    lines = [f"Recent Runs (last {days} days):", "=" * 50]
    
    for p in points:
        speed = p.get("averageSpeed", 0)
        distance_km = round(p.get("distance", 0) / 1000, 2)
        duration = format_duration(p.get("movingDuration", 0))
        pace = format_pace(speed)
        avg_hr = int(p.get("averageHR", 0) or 0)
        
        lines.append(f"\n{p.get('activityName', 'Run')} - {p.get('time', '').split('T')[0]}")
        lines.append(f"  Distance: {distance_km} km | Duration: {duration} | Pace: {pace}")
        lines.append(f"  Avg HR: {avg_hr} bpm | Calories: {int(p.get('calories', 0) or 0)}")
    
    lines.append(f"\nTotal: {len(points)} runs")
    return "\n".join(lines)


@friday_tool(name="get_training_load")
def get_training_load(weeks: int = 4) -> str:
    """Analyze weekly training load: mileage, time, and intensity.
    
    Args:
        weeks: Number of weeks to analyze (default: 4)
    
    Returns:
        Weekly training load breakdown
    """
    lines = [f"Training Load (Last {weeks} Weeks):", "=" * 50]
    total_km = 0
    total_runs = 0
    
    for week in range(weeks):
        week_start = datetime.now(BRT) - timedelta(weeks=week+1)
        week_end = datetime.now(BRT) - timedelta(weeks=week)
        
        start_str = week_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = week_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        query = f"""
        SELECT distance, movingDuration, averageSpeed, aerobicTE
        FROM ActivitySummary
        WHERE time >= '{start_str}' AND time < '{end_str}'
        AND activityType = 'running'
        """
        
        points = _query(query)
        
        if points:
            week_distance = sum(p.get("distance", 0) for p in points) / 1000
            week_duration = sum(p.get("movingDuration", 0) for p in points)
            avg_te = sum(p.get("aerobicTE", 0) or 0 for p in points) / len(points)
            
            total_km += week_distance
            total_runs += len(points)
            
            lines.append(f"\nWeek ending {week_end.strftime('%Y-%m-%d')}:")
            lines.append(f"  {round(week_distance, 1)} km | {format_duration(week_duration)} | {len(points)} runs")
            lines.append(f"  Avg Training Effect: {round(avg_te, 1)}")
        else:
            lines.append(f"\nWeek ending {week_end.strftime('%Y-%m-%d')}: No runs")
    
    lines.append(f"\n{'=' * 50}")
    lines.append(f"Total: {round(total_km, 1)} km | {total_runs} runs")
    
    return "\n".join(lines)


@friday_tool(name="get_vo2max")
def get_vo2max() -> str:
    """Get current VO2 Max and recent trend.
    
    Returns:
        Current VO2 Max value and trend information
    """
    # Get latest VO2 Max
    query = "SELECT vo2Max FROM DailyStats WHERE vo2Max > 0 ORDER BY time DESC LIMIT 1"
    points = _query(query)
    
    if not points:
        return "No VO2 Max data found"
    
    current = round(points[0].get("vo2Max", 0), 1)
    
    # Get trend (last 30 days)
    start = datetime.now(BRT) - timedelta(days=30)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
    query = f"""
    SELECT vo2Max FROM DailyStats 
    WHERE time >= '{start_str}' AND vo2Max > 0 
    ORDER BY time ASC
    """
    points = _query(query)
    
    if len(points) > 1:
        values = [p.get("vo2Max", 0) for p in points if p.get("vo2Max")]
        first = values[0]
        change = current - first
        trend = "↑ improving" if change > 0 else "↓ declining" if change < 0 else "→ stable"
    else:
        trend = "insufficient data"
        change = 0
    
    lines = [
        "VO2 Max Status:",
        "=" * 30,
        f"Current: {current} ml/kg/min",
        f"Trend (30 days): {trend} ({'+' if change > 0 else ''}{round(change, 1)})",
    ]
    
    return "\n".join(lines)


# =============================================================================
# Sleep & Recovery Tools
# =============================================================================

@friday_tool(name="get_sleep_summary")
def get_sleep_summary(days: int = 7) -> str:
    """Get sleep analysis including quality, duration, and stages.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Sleep summary with quality scores and stage breakdown
    """
    query = f"SELECT * FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return "No sleep data found"
    
    lines = [f"Sleep Summary (Last {days} Days):", "=" * 50]
    
    total_hours = []
    scores = []
    
    for p in points:
        deep = p.get("deepSleepSeconds", 0) or 0
        light = p.get("lightSleepSeconds", 0) or 0
        rem = p.get("remSleepSeconds", 0) or 0
        total = deep + light + rem
        hours = total / 3600
        total_hours.append(hours)
        
        score = p.get("sleepScore", 0) or 0
        scores.append(score)
        
        date = p.get("time", "").split("T")[0]
        lines.append(f"\n{date}: {round(hours, 1)}h | Score: {score}")
        lines.append(f"  Deep: {format_duration(deep)} | Light: {format_duration(light)} | REM: {format_duration(rem)}")
    
    avg_hours = sum(total_hours) / len(total_hours) if total_hours else 0
    avg_score = sum(scores) / len(scores) if scores else 0
    
    lines.append(f"\n{'=' * 50}")
    lines.append(f"Average: {round(avg_hours, 1)} hours | Score: {round(avg_score, 0)}")
    
    return "\n".join(lines)


@friday_tool(name="get_recovery_status")
def get_recovery_status() -> str:
    """Get current recovery status including body battery, HRV, and training readiness.
    
    Returns:
        Current recovery metrics and recommendations
    """
    lines = ["Recovery Status:", "=" * 50]
    
    # Training Readiness
    query = "SELECT score, recoveryTime, hrvFactorPercent, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        p = points[0]
        lines.append(f"\nTraining Readiness: {p.get('level', 'Unknown')} ({int(p.get('score', 0))})")
        lines.append(f"  Recovery time needed: {int(p.get('recoveryTime', 0))} hours")
        lines.append(f"  HRV factor: {int(p.get('hrvFactorPercent', 0))}%")
    
    # Body Battery
    query = "SELECT bodyBatteryAtWakeTime FROM DailyStats ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        bb = int(points[0].get("bodyBatteryAtWakeTime", 0) or 0)
        lines.append(f"\nBody Battery at Wake: {bb}")
    
    # HRV
    query = "SELECT avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        hrv = int(points[0].get("avgOvernightHrv", 0) or 0)
        lines.append(f"Overnight HRV: {hrv} ms")
    
    # Stress
    query = "SELECT stressAvg FROM DailyStats ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        stress = int(points[0].get("stressAvg", 0) or 0)
        stress_level = "low" if stress < 30 else "moderate" if stress < 50 else "high"
        lines.append(f"Stress Level: {stress_level} ({stress})")
    
    return "\n".join(lines)


@friday_tool(name="get_hrv_trend")
def get_hrv_trend(days: int = 14) -> str:
    """Analyze heart rate variability patterns for recovery assessment.
    
    Args:
        days: Number of days to analyze (default: 14)
    
    Returns:
        HRV trend analysis
    """
    query = f"SELECT avgOvernightHrv, time FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return "No HRV data found"
    
    hrv_data = []
    for p in points:
        hrv = p.get("avgOvernightHrv", 0)
        if hrv and hrv > 0:
            hrv_data.append({
                "date": p.get("time", "").split("T")[0],
                "hrv": int(hrv)
            })
    
    if not hrv_data:
        return "No valid HRV readings"
    
    values = [h["hrv"] for h in hrv_data]
    avg_hrv = sum(values) / len(values)
    
    # Calculate trend
    recent_avg = sum(values[:7]) / min(7, len(values))
    older_avg = sum(values[7:14]) / max(1, len(values[7:14])) if len(values) > 7 else recent_avg
    
    if recent_avg > older_avg:
        trend = "↑ improving"
    elif recent_avg < older_avg:
        trend = "↓ declining"
    else:
        trend = "→ stable"
    
    lines = [
        f"HRV Analysis (Last {days} Days):",
        "=" * 40,
        f"Current: {values[0]} ms",
        f"Average: {round(avg_hrv, 0)} ms",
        f"Range: {min(values)} - {max(values)} ms",
        f"Trend: {trend}",
        "",
        "Recent readings:"
    ]
    
    for h in hrv_data[:7]:
        lines.append(f"  {h['date']}: {h['hrv']} ms")
    
    return "\n".join(lines)


# =============================================================================
# Health & Wellness Tools
# =============================================================================

@friday_tool(name="get_weekly_health")
def get_weekly_health(weeks_ago: int = 0) -> str:
    """Get comprehensive weekly health overview.
    
    Args:
        weeks_ago: 0 = current week, 1 = last week, etc.
    
    Returns:
        Weekly health digest including activity, sleep, stress, and recovery
    """
    week_start = datetime.now(BRT) - timedelta(weeks=weeks_ago+1)
    week_end = datetime.now(BRT) - timedelta(weeks=weeks_ago)
    
    lines = [
        f"Weekly Health Digest",
        f"Week: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
        "=" * 50
    ]
    
    start_str = week_start.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = week_end.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Running
    query = f"""
    SELECT distance, movingDuration, calories
    FROM ActivitySummary
    WHERE time >= '{start_str}' AND time < '{end_str}'
    AND activityType = 'running'
    """
    points = _query(query)
    if points:
        total_km = sum(p.get("distance", 0) for p in points) / 1000
        total_duration = sum(p.get("movingDuration", 0) for p in points)
        total_cal = sum(p.get("calories", 0) or 0 for p in points)
        lines.append(f"\n🏃 Running: {round(total_km, 1)} km | {format_duration(total_duration)} | {len(points)} runs")
        lines.append(f"   Calories burned: {int(total_cal)}")
    
    # Sleep
    query = f"""
    SELECT sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds
    FROM SleepSummary
    WHERE time >= '{start_str}' AND time < '{end_str}'
    """
    points = _query(query)
    if points:
        scores = [p.get("sleepScore", 0) or 0 for p in points]
        total_sleep = [
            (p.get("deepSleepSeconds", 0) or 0) + 
            (p.get("lightSleepSeconds", 0) or 0) + 
            (p.get("remSleepSeconds", 0) or 0)
            for p in points
        ]
        avg_score = sum(scores) / len(scores) if scores else 0
        avg_hours = sum(total_sleep) / len(total_sleep) / 3600 if total_sleep else 0
        lines.append(f"\n😴 Sleep: {round(avg_hours, 1)}h avg | Score: {round(avg_score, 0)}")
    
    # Steps & Stress
    query = f"""
    SELECT totalSteps, stressAvg, bodyBatteryAtWakeTime
    FROM DailyStats
    WHERE time >= '{start_str}' AND time < '{end_str}'
    """
    points = _query(query)
    if points:
        steps = [p.get("totalSteps", 0) or 0 for p in points]
        stress = [p.get("stressAvg", 0) or 0 for p in points if p.get("stressAvg")]
        bb = [p.get("bodyBatteryAtWakeTime", 0) or 0 for p in points if p.get("bodyBatteryAtWakeTime")]
        
        lines.append(f"\n👟 Steps: {sum(steps):,} total | {round(sum(steps)/len(steps), 0):,} avg/day")
        if stress:
            lines.append(f"😰 Stress: {round(sum(stress)/len(stress), 0)} avg")
        if bb:
            lines.append(f"🔋 Body Battery (wake): {round(sum(bb)/len(bb), 0)} avg")
    
    return "\n".join(lines)


@friday_tool(name="get_stress_levels")
def get_stress_levels(days: int = 7) -> str:
    """Analyze stress patterns.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Stress level analysis
    """
    # Get daily stress durations
    query = f"SELECT highStressDuration, mediumStressDuration, lowStressDuration, restStressDuration FROM DailyStats ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return "No stress data found"
    
    lines = [f"Stress Analysis (Last {days} Days):", "=" * 40]
    
    stress_avgs = []
    for p in points:
        date = p.get("time", "").split("T")[0]
        
        # Get durations in seconds
        high_sec = p.get("highStressDuration", 0) or 0
        med_sec = p.get("mediumStressDuration", 0) or 0
        low_sec = p.get("lowStressDuration", 0) or 0
        rest_sec = p.get("restStressDuration", 0) or 0
        
        # Convert to minutes
        high_min = int(high_sec / 60)
        rest_min = int(rest_sec / 60)
        
        # Calculate weighted average stress
        total_sec = high_sec + med_sec + low_sec + rest_sec
        if total_sec > 0:
            # Approximate stress values: high=70, med=45, low=25, rest=10
            avg = round((high_sec * 70 + med_sec * 45 + low_sec * 25 + rest_sec * 10) / total_sec)
        else:
            avg = 0
        stress_avgs.append(avg)
        
        lines.append(f"\n{date}: Avg {avg}")
        lines.append(f"  High stress: {high_min}m | Rest: {rest_min}m")
    
    if stress_avgs:
        overall = sum(stress_avgs) / len(stress_avgs)
        level = "low" if overall < 30 else "moderate" if overall < 50 else "high"
        lines.append(f"\n{'=' * 40}")
        lines.append(f"Overall: {level} (avg: {round(overall, 0)})")
    
    # Get current stress from intraday
    current_query = "SELECT stressLevel FROM StressIntraday ORDER BY time DESC LIMIT 1"
    current_points = _query(current_query)
    if current_points:
        current = current_points[0].get("stressLevel", 0)
        lines.append(f"Current stress: {current}/100")
    
    return "\n".join(lines)


@friday_tool(name="get_heart_rate_summary")
def get_heart_rate_summary(days: int = 14) -> str:
    """Get resting heart rate and cardiovascular health trends.
    
    Args:
        days: Number of days to analyze (default: 14)
    
    Returns:
        Heart rate trend analysis
    """
    query = f"SELECT restingHeartRate, avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return "No heart rate data found"
    
    lines = [f"Heart Rate Summary (Last {days} Days):", "=" * 45]
    
    rhr_values = []
    for p in points:
        date = p.get("time", "").split("T")[0]
        rhr = int(p.get("restingHeartRate", 0) or 0)
        hrv = int(p.get("avgOvernightHrv", 0) or 0)
        
        if rhr > 0:
            rhr_values.append(rhr)
            lines.append(f"{date}: RHR {rhr} bpm | HRV {hrv} ms")
    
    if rhr_values:
        avg_rhr = sum(rhr_values) / len(rhr_values)
        health = "excellent ❤️" if avg_rhr < 55 else "good 💚" if avg_rhr < 65 else "average 💛"
        
        lines.append(f"\n{'=' * 45}")
        lines.append(f"Average RHR: {round(avg_rhr, 0)} bpm")
        lines.append(f"Range: {min(rhr_values)} - {max(rhr_values)} bpm")
        lines.append(f"Cardiovascular health: {health}")
    
    return "\n".join(lines)


# =============================================================================
# Activity Overview
# =============================================================================

@friday_tool(name="get_activity_summary")
def get_activity_summary(days: int = 7) -> str:
    """Get all activities, steps, and calories for a period.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Activity summary with steps, workouts, and calories
    """
    start = datetime.now(BRT) - timedelta(days=days)
    
    lines = [f"Activity Summary (Last {days} Days):", "=" * 50]
    
    # Daily stats
    query = f"""
    SELECT totalSteps, totalDistanceMeters, activeCalories
    FROM DailyStats
    WHERE time >= '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC
    """
    points = _query(query)
    
    if points:
        steps = [p.get("totalSteps", 0) or 0 for p in points]
        lines.append(f"\n👟 Steps:")
        lines.append(f"   Total: {sum(steps):,}")
        lines.append(f"   Average: {round(sum(steps)/len(steps), 0):,}/day")
    
    # Workouts
    query = f"""
    SELECT activityName, activityType, distance, movingDuration, calories
    FROM ActivitySummary
    WHERE time >= '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC
    """
    points = _query(query)
    
    if points:
        lines.append(f"\n🏋️ Workouts ({len(points)} total):")
        for p in points[:5]:  # Show last 5
            name = p.get("activityName", "Activity")
            atype = p.get("activityType", "")
            dist = round((p.get("distance", 0) or 0) / 1000, 1)
            dur = format_duration(p.get("movingDuration", 0) or 0)
            cal = int(p.get("calories", 0) or 0)
            
            lines.append(f"   {name} ({atype}): {dist}km | {dur} | {cal} cal")
    
    return "\n".join(lines)


@friday_tool(name="get_garmin_sync_status")
def get_garmin_sync_status() -> str:
    """Check when Garmin data was last synced to InfluxDB.
    
    Returns:
        Last sync time and status
    """
    # Query for the most recent heart rate data point
    query = 'SELECT last("HeartRate") FROM "HeartRateIntraday"'
    
    points = _query(query)
    
    if not points:
        return "No Garmin data found in InfluxDB. Sync may not be configured."
    
    point = points[0]
    last_time_str = point.get("time", "")
    last_hr = point.get("last", 0)
    
    if not last_time_str:
        return "Could not determine last sync time."
    
    # Parse the timestamp
    try:
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_ago = (now - last_time).total_seconds() / 3600
        
        # Convert to BRT for display
        last_time_brt = last_time.astimezone(BRT)
        time_str = last_time_brt.strftime("%Y-%m-%d %H:%M BRT")
        
        if hours_ago < 1:
            status = "Current"
        elif hours_ago < 6:
            status = "Recent"
        elif hours_ago < 12:
            status = "Getting stale"
        else:
            status = "STALE - needs attention"
        
        return (
            f"Garmin Sync Status: {status}\n"
            f"Last sync: {time_str} ({hours_ago:.1f} hours ago)\n"
            f"Last heart rate: {last_hr} bpm"
        )
        
    except Exception as e:
        return f"Error parsing sync time: {e}"
