"""
Friday 3.0 Health Tools

Garmin health data tools using InfluxDB.
Provides access to running, sleep, recovery, and wellness metrics.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from settings import settings
from src.core.influxdb import query as _query
from src.core.utils import format_duration, format_pace

logger = logging.getLogger(__name__)


# =============================================================================
# Running & Training Tools
# =============================================================================

@agent.tool_plain
def get_recent_runs(limit: int = 10, days: int = 30) -> Dict[str, Any]:
    """Get recent running activities with pace, HR, distance, and duration.
    
    Atomic data tool that returns structured running activity data.
    
    Args:
        limit: Number of runs to return (default: 10)
        days: Look back period in days (default: 30)
    
    Returns:
        Dict with list of runs and summary statistics
    """
    start = datetime.now(settings.TIMEZONE) - timedelta(days=days)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = f"""
    SELECT activityName, distance, movingDuration, averageSpeed, 
           averageHR, maxHR, calories, elevationGain, aerobicTE, time
    FROM ActivitySummary
    WHERE time >= '{start_str}'
    AND activityType = 'running'
    ORDER BY time DESC
    LIMIT {limit}
    """
    
    points = _query(query)
    
    if not points:
        return {"error": "No running data found for this period"}
    
    runs = []
    for p in points:
        runs.append({
            "name": p.get('activityName', 'Run'),
            "date": p.get('time', '').split('T')[0],
            "distance_km": round(p.get("distance", 0) / 1000, 2),
            "duration_seconds": int(p.get("movingDuration", 0) or 0),
            "average_speed_mps": round(p.get("averageSpeed", 0), 2),
            "average_hr_bpm": int(p.get("averageHR", 0) or 0),
            "max_hr_bpm": int(p.get("maxHR", 0) or 0),
            "calories": int(p.get('calories', 0) or 0),
            "elevation_gain_m": int(p.get('elevationGain', 0) or 0),
            "aerobic_te": round(p.get('aerobicTE', 0) or 0, 1)
        })
    
    return {
        "runs": runs,
        "total_runs": len(runs),
        "period_days": days,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


@agent.tool_plain
def report_training_load(weeks: int = 4) -> str:
    """Analyze weekly training load: mileage, time, and intensity.
    
    COMPOSITE REPORT: Returns formatted string for display.
    
    Args:
        weeks: Number of weeks to analyze (default: 4)
    
    Returns:
        Weekly training load breakdown as formatted string
    """
    lines = [f"Training Load (Last {weeks} Weeks):", "=" * 50]
    total_km = 0
    total_runs = 0
    
    for week in range(weeks):
        week_start = datetime.now(settings.TIMEZONE) - timedelta(weeks=week+1)
        week_end = datetime.now(settings.TIMEZONE) - timedelta(weeks=week)
        
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


@agent.tool_plain
def get_vo2max() -> Dict[str, Any]:
    """Get current VO2 Max and recent trend.
    
    Atomic data tool that returns structured VO2 Max data.
    
    Returns:
        Dict with current vo2max, trend, and change over 30 days
    """
    # Get latest VO2 Max
    query = "SELECT vo2Max FROM DailyStats WHERE vo2Max > 0 ORDER BY time DESC LIMIT 1"
    points = _query(query)
    
    if not points:
        return {"error": "No VO2 Max data found"}
    
    current = round(points[0].get("vo2Max", 0), 1)
    
    # Get trend (last 30 days)
    start = datetime.now(settings.TIMEZONE) - timedelta(days=30)
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
        change = round(current - first, 1)
        trend = "improving" if change > 0 else "declining" if change < 0 else "stable"
    else:
        trend = "insufficient_data"
        change = 0
    
    return {
        "current": current,
        "unit": "ml/kg/min",
        "trend_30d": trend,
        "change_30d": change,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


# =============================================================================
# Sleep & Recovery Tools
# =============================================================================

@agent.tool_plain
def get_sleep_summary(days: int = 7) -> Dict[str, Any]:
    """Get sleep analysis including quality, duration, and stages.
    
    Atomic data tool that returns structured sleep data.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Dict with sleep data including daily breakdown and averages
    """
    query = f"SELECT * FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return {"error": "No sleep data found"}
    
    sleep_data = []
    total_hours = []
    scores = []
    
    for p in points:
        deep = p.get("deepSleepSeconds", 0) or 0
        light = p.get("lightSleepSeconds", 0) or 0
        rem = p.get("remSleepSeconds", 0) or 0
        awake = p.get("awakeSleepSeconds", 0) or 0
        total = deep + light + rem
        hours = total / 3600
        total_hours.append(hours)
        
        score = p.get("sleepScore", 0) or 0
        scores.append(score)
        
        sleep_data.append({
            "date": p.get("time", "").split("T")[0],
            "total_hours": round(hours, 2),
            "score": int(score),
            "deep_seconds": int(deep),
            "light_seconds": int(light),
            "rem_seconds": int(rem),
            "awake_seconds": int(awake)
        })
    
    avg_hours = sum(total_hours) / len(total_hours) if total_hours else 0
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return {
        "sleep_nights": sleep_data,
        "period_days": days,
        "average_hours": round(avg_hours, 2),
        "average_score": round(avg_score, 0),
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


@agent.tool_plain
def get_recovery_status() -> Dict[str, Any]:
    """Get current recovery status including body battery, HRV, and training readiness.
    
    Atomic data tool that returns structured recovery metrics.
    
    Returns:
        Dict with recovery metrics: training_readiness, body_battery, hrv, stress
    """
    result = {
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }
    
    # Training Readiness
    query = "SELECT score, recoveryTime, hrvFactorPercent, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        p = points[0]
        result["training_readiness"] = {
            "score": int(p.get('score', 0) or 0),
            "level": p.get('level', 'unknown'),
            "recovery_time_hours": int(p.get('recoveryTime', 0) or 0),
            "hrv_factor_percent": int(p.get('hrvFactorPercent', 0) or 0)
        }
    
    # Body Battery
    query = "SELECT bodyBatteryAtWakeTime FROM DailyStats ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        result["body_battery_at_wake"] = int(points[0].get("bodyBatteryAtWakeTime", 0) or 0)
    
    # HRV
    query = "SELECT avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        result["overnight_hrv_ms"] = int(points[0].get("avgOvernightHrv", 0) or 0)
    
    # Stress
    query = "SELECT stressAvg FROM DailyStats ORDER BY time DESC LIMIT 1"
    points = _query(query)
    if points:
        stress = int(points[0].get("stressAvg", 0) or 0)
        stress_level = "low" if stress < 30 else "moderate" if stress < 50 else "high"
        result["stress"] = {
            "average": stress,
            "level": stress_level
        }
    
    return result


@agent.tool_plain
def get_hrv_trend(days: int = 14) -> Dict[str, Any]:
    """Analyze heart rate variability patterns for recovery assessment.
    
    Atomic data tool that returns structured HRV trend data.
    
    Args:
        days: Number of days to analyze (default: 14)
    
    Returns:
        Dict with HRV readings, average, range, and trend
    """
    query = f"SELECT avgOvernightHrv, time FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return {"error": "No HRV data found"}
    
    hrv_data = []
    for p in points:
        hrv = p.get("avgOvernightHrv", 0)
        if hrv and hrv > 0:
            hrv_data.append({
                "date": p.get("time", "").split("T")[0],
                "hrv_ms": int(hrv)
            })
    
    if not hrv_data:
        return {"error": "No valid HRV readings"}
    
    values = [h["hrv_ms"] for h in hrv_data]
    avg_hrv = sum(values) / len(values)
    
    # Calculate trend
    recent_avg = sum(values[:7]) / min(7, len(values))
    older_avg = sum(values[7:14]) / max(1, len(values[7:14])) if len(values) > 7 else recent_avg
    
    if recent_avg > older_avg:
        trend = "improving"
    elif recent_avg < older_avg:
        trend = "declining"
    else:
        trend = "stable"
    
    return {
        "readings": hrv_data,
        "current_ms": values[0],
        "average_ms": round(avg_hrv, 0),
        "min_ms": min(values),
        "max_ms": max(values),
        "trend": trend,
        "recent_avg_ms": round(recent_avg, 0),
        "older_avg_ms": round(older_avg, 0),
        "period_days": days,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


# =============================================================================
# Health & Wellness Tools
# =============================================================================

@agent.tool_plain
def report_weekly_health(weeks_ago: int = 0) -> str:
    """Get comprehensive weekly health overview.
    
    COMPOSITE REPORT: Returns formatted string for display.
    
    Args:
        weeks_ago: 0 = current week, 1 = last week, etc.
    
    Returns:
        Weekly health digest including activity, sleep, stress, and recovery as formatted string
    """
    week_start = datetime.now(settings.TIMEZONE) - timedelta(weeks=weeks_ago+1)
    week_end = datetime.now(settings.TIMEZONE) - timedelta(weeks=weeks_ago)
    
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


@agent.tool_plain
def get_stress_levels(days: int = 7) -> Dict[str, Any]:
    """Analyze stress patterns.
    
    Atomic data tool that returns structured stress data.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Dict with daily stress levels, durations, and overall statistics
    """
    # Get daily stress durations
    query = f"SELECT highStressDuration, mediumStressDuration, lowStressDuration, restStressDuration, time FROM DailyStats ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return {"error": "No stress data found"}
    
    daily_stress = []
    stress_avgs = []
    
    for p in points:
        date = p.get("time", "").split("T")[0]
        
        # Get durations in seconds
        high_sec = p.get("highStressDuration", 0) or 0
        med_sec = p.get("mediumStressDuration", 0) or 0
        low_sec = p.get("lowStressDuration", 0) or 0
        rest_sec = p.get("restStressDuration", 0) or 0
        
        # Calculate weighted average stress
        total_sec = high_sec + med_sec + low_sec + rest_sec
        if total_sec > 0:
            # Approximate stress values: high=70, med=45, low=25, rest=10
            avg = round((high_sec * 70 + med_sec * 45 + low_sec * 25 + rest_sec * 10) / total_sec)
        else:
            avg = 0
        stress_avgs.append(avg)
        
        daily_stress.append({
            "date": date,
            "average": avg,
            "high_duration_seconds": int(high_sec),
            "medium_duration_seconds": int(med_sec),
            "low_duration_seconds": int(low_sec),
            "rest_duration_seconds": int(rest_sec)
        })
    
    overall = sum(stress_avgs) / len(stress_avgs) if stress_avgs else 0
    level = "low" if overall < 30 else "moderate" if overall < 50 else "high"
    
    # Get current stress from intraday
    current_query = "SELECT stressLevel FROM StressIntraday ORDER BY time DESC LIMIT 1"
    current_points = _query(current_query)
    current_stress = int(current_points[0].get("stressLevel", 0)) if current_points else None
    
    return {
        "daily_stress": daily_stress,
        "overall_average": round(overall, 0),
        "overall_level": level,
        "current_stress": current_stress,
        "period_days": days,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


@agent.tool_plain
def get_heart_rate_summary(days: int = 14) -> Dict[str, Any]:
    """Get resting heart rate and cardiovascular health trends.
    
    Atomic data tool that returns structured heart rate data.
    
    Args:
        days: Number of days to analyze (default: 14)
    
    Returns:
        Dict with daily RHR readings, averages, and health assessment
    """
    query = f"SELECT restingHeartRate, avgOvernightHrv, time FROM SleepSummary ORDER BY time DESC LIMIT {days}"
    points = _query(query)
    
    if not points:
        return {"error": "No heart rate data found"}
    
    daily_readings = []
    rhr_values = []
    
    for p in points:
        date = p.get("time", "").split("T")[0]
        rhr = int(p.get("restingHeartRate", 0) or 0)
        hrv = int(p.get("avgOvernightHrv", 0) or 0)
        
        if rhr > 0:
            rhr_values.append(rhr)
            daily_readings.append({
                "date": date,
                "resting_hr_bpm": rhr,
                "hrv_ms": hrv
            })
    
    if not rhr_values:
        return {"error": "No valid heart rate readings"}
    
    avg_rhr = sum(rhr_values) / len(rhr_values)
    health_level = "excellent" if avg_rhr < 55 else "good" if avg_rhr < 65 else "average"
    
    return {
        "readings": daily_readings,
        "average_rhr_bpm": round(avg_rhr, 0),
        "min_rhr_bpm": min(rhr_values),
        "max_rhr_bpm": max(rhr_values),
        "health_level": health_level,
        "period_days": days,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


# =============================================================================
# Activity Overview
# =============================================================================

@agent.tool_plain
def get_activity_summary(days: int = 7) -> Dict[str, Any]:
    """Get all activities, steps, and calories for a period.
    
    Atomic data tool that returns structured activity data.
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Dict with steps, workouts, and activity statistics
    """
    start = datetime.now(settings.TIMEZONE) - timedelta(days=days)
    
    # Daily stats
    query = f"""
    SELECT totalSteps, totalDistanceMeters, activeCalories
    FROM DailyStats
    WHERE time >= '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC
    """
    points = _query(query)
    
    steps_data = []
    if points:
        steps_data = [int(p.get("totalSteps", 0) or 0) for p in points]
    
    # Workouts
    query = f"""
    SELECT activityName, activityType, distance, movingDuration, calories, time
    FROM ActivitySummary
    WHERE time >= '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    ORDER BY time DESC
    """
    points = _query(query)
    
    workouts = []
    if points:
        for p in points:
            workouts.append({
                "name": p.get("activityName", "Activity"),
                "type": p.get("activityType", ""),
                "date": p.get("time", "").split("T")[0],
                "distance_km": round((p.get("distance", 0) or 0) / 1000, 2),
                "duration_seconds": int(p.get("movingDuration", 0) or 0),
                "calories": int(p.get("calories", 0) or 0)
            })
    
    return {
        "steps": {
            "total": sum(steps_data) if steps_data else 0,
            "average_per_day": round(sum(steps_data) / len(steps_data), 0) if steps_data else 0,
            "daily_values": steps_data
        },
        "workouts": workouts,
        "workout_count": len(workouts),
        "period_days": days,
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


@agent.tool_plain
def get_garmin_sync_status() -> Dict[str, Any]:
    """Check when Garmin data was last synced to InfluxDB.
    
    Atomic data tool that returns structured sync status data.
    
    Returns:
        Dict with sync status including last_sync_time, hours_ago, status, last_hr
    """
    # Query for the most recent heart rate data point
    query = 'SELECT last("HeartRate") FROM "HeartRateIntraday"'
    
    points = _query(query)
    
    if not points:
        return {"error": "No Garmin data found in InfluxDB. Sync may not be configured."}
    
    point = points[0]
    last_time_str = point.get("time", "")
    last_hr = point.get("last", 0)
    
    if not last_time_str:
        return {"error": "Could not determine last sync time."}
    
    # Parse the timestamp
    try:
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_ago = (now - last_time).total_seconds() / 3600
        
        # Convert to local timezone for display
        last_time_local = last_time.astimezone(settings.TIMEZONE)
        
        if hours_ago < 1:
            status = "current"
        elif hours_ago < 6:
            status = "recent"
        elif hours_ago < 12:
            status = "stale"
        else:
            status = "critical"
        
        return {
            "status": status,
            "last_sync_time": last_time_local.isoformat(),
            "hours_ago": round(hours_ago, 1),
            "last_heart_rate": int(last_hr),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
        
    except Exception as e:
        return {"error": f"Error parsing sync time: {e}"}
