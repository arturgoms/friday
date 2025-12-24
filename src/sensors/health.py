"""
Friday 3.0 Health Sensors

Garmin health data sensors for the awareness engine.
Monitors sleep, recovery, training readiness, and body battery.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.core.constants import BRT
from src.core.influxdb import get_influx_client, query_latest, query
from src.core.registry import friday_sensor

logger = logging.getLogger(__name__)


# =============================================================================
# Health Sensors
# =============================================================================

@friday_sensor(name="sleep_quality", interval_seconds=3600)  # Check hourly
def check_sleep_quality() -> Dict[str, Any]:
    """Check last night's sleep quality from Garmin.
    
    Monitors:
    - Sleep score (alert if < 60)
    - Total sleep duration (alert if < 6 hours)
    - Deep sleep percentage
    
    Returns:
        Dictionary with sleep quality data
    """
    try:
        data = query_latest(
            "SleepSummary",
            "sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds, avgOvernightHrv, restingHeartRate, time"
        )
        
        if not data:
            return {"sensor": "sleep_quality", "error": "No sleep data available"}
        
        deep = data.get("deepSleepSeconds", 0) or 0
        light = data.get("lightSleepSeconds", 0) or 0
        rem = data.get("remSleepSeconds", 0) or 0
        total_seconds = deep + light + rem
        total_hours = total_seconds / 3600
        
        sleep_score = data.get("sleepScore", 0) or 0
        hrv = data.get("avgOvernightHrv", 0) or 0
        rhr = data.get("restingHeartRate", 0) or 0
        
        # Calculate deep sleep percentage
        deep_percent = (deep / total_seconds * 100) if total_seconds > 0 else 0
        
        return {
            "sensor": "sleep_quality",
            "sleep_score": sleep_score,
            "total_hours": round(total_hours, 1),
            "deep_sleep_percent": round(deep_percent, 1),
            "hrv": hrv,
            "resting_hr": rhr,
            "date": data.get("time", "").split("T")[0]
        }
        
    except Exception as e:
        return {"sensor": "sleep_quality", "error": str(e)}


@friday_sensor(name="training_readiness", interval_seconds=3600)  # Check hourly
def check_training_readiness() -> Dict[str, Any]:
    """Check training readiness from Garmin.
    
    Monitors:
    - Training readiness score (alert if < 50)
    - Recovery time
    - HRV status
    
    Returns:
        Dictionary with training readiness data
    """
    try:
        data = query_latest(
            "TrainingReadiness",
            "score, level, recoveryTime, hrvFactorPercent, sleepScoreFactorPercent, time"
        )
        
        if not data:
            return {"sensor": "training_readiness", "error": "No training readiness data"}
        
        score = data.get("score", 0) or 0
        level = data.get("level", "UNKNOWN")
        recovery_time = data.get("recoveryTime", 0) or 0
        hrv_factor = data.get("hrvFactorPercent", 0) or 0
        sleep_factor = data.get("sleepScoreFactorPercent", 0) or 0
        
        return {
            "sensor": "training_readiness",
            "score": score,
            "level": level,
            "recovery_hours": recovery_time,
            "hrv_factor": hrv_factor,
            "sleep_factor": sleep_factor,
            "date": data.get("time", "").split("T")[0]
        }
        
    except Exception as e:
        return {"sensor": "training_readiness", "error": str(e)}


@friday_sensor(name="body_battery", interval_seconds=1800)  # Check every 30 min
def check_body_battery() -> Dict[str, Any]:
    """Check body battery level from Garmin.
    
    Monitors:
    - Body battery at wake (alert if < 40)
    - Current stress levels
    
    Returns:
        Dictionary with body battery data
    """
    try:
        data = query_latest(
            "DailyStats",
            "bodyBatteryAtWakeTime, stressAvg, totalSteps, time"
        )
        
        if not data:
            return {"sensor": "body_battery", "error": "No body battery data"}
        
        body_battery = data.get("bodyBatteryAtWakeTime", 0) or 0
        stress_avg = data.get("stressAvg", 0) or 0
        steps = data.get("totalSteps", 0) or 0
        
        return {
            "sensor": "body_battery",
            "body_battery": body_battery,
            "stress_avg": stress_avg,
            "steps": steps,
            "date": data.get("time", "").split("T")[0]
        }
        
    except Exception as e:
        return {"sensor": "body_battery", "error": str(e)}


@friday_sensor(name="recovery_status", interval_seconds=3600)  # Check hourly
def check_recovery_status() -> Dict[str, Any]:
    """Check overall recovery status combining multiple metrics.
    
    This is a composite sensor that evaluates:
    - HRV trend (comparing to baseline)
    - Resting heart rate trend
    - Sleep quality trend
    
    Returns:
        Dictionary with recovery assessment
    """
    try:
        # Get latest sleep data for HRV and RHR
        sleep_data = query_latest(
            "SleepSummary",
            "avgOvernightHrv, restingHeartRate, sleepScore"
        )
        
        if not sleep_data:
            return {"sensor": "recovery_status", "error": "No recovery data"}
        
        hrv = sleep_data.get("avgOvernightHrv", 0) or 0
        rhr = sleep_data.get("restingHeartRate", 0) or 0
        sleep_score = sleep_data.get("sleepScore", 0) or 0
        
        # Get 7-day HRV average for comparison
        try:
            hrv_points = query("SELECT mean(avgOvernightHrv) as avg_hrv FROM SleepSummary WHERE time > now() - 7d")
            hrv_baseline = hrv_points[0].get("avg_hrv", hrv) if hrv_points else hrv
        except Exception as e:
            logger.debug(f"Failed to get HRV baseline, using current value: {e}")
            hrv_baseline = hrv
        
        # Calculate HRV deviation from baseline
        hrv_deviation = ((hrv - hrv_baseline) / hrv_baseline * 100) if hrv_baseline > 0 else 0
        
        # Determine recovery status
        if hrv_deviation < -15 or rhr > 65 or sleep_score < 50:
            status = "poor"
        elif hrv_deviation < -5 or rhr > 58 or sleep_score < 70:
            status = "fair"
        elif hrv_deviation > 5 and rhr < 55 and sleep_score > 80:
            status = "excellent"
        else:
            status = "good"
        
        return {
            "sensor": "recovery_status",
            "status": status,
            "hrv": hrv,
            "hrv_baseline": round(hrv_baseline, 1),
            "hrv_deviation_percent": round(hrv_deviation, 1),
            "resting_hr": rhr,
            "sleep_score": sleep_score
        }
        
    except Exception as e:
        return {"sensor": "recovery_status", "error": str(e)}


@friday_sensor(name="garmin_sync_status", interval_seconds=1800)  # Check every 30 min
def check_garmin_sync_status() -> Dict[str, Any]:
    """Check if Garmin data is syncing properly.
    
    Monitors the last HeartRateIntraday record to detect sync issues.
    Alert if last sync is older than 12 hours.
    
    Returns:
        Dictionary with sync status
    """
    try:
        # Query the last heart rate intraday record
        points = query('SELECT last("HeartRate") FROM "HeartRateIntraday"')
        
        if not points:
            return {
                "sensor": "garmin_sync_status",
                "status": "no_data",
                "error": "No HeartRateIntraday data found"
            }
        
        last_point = points[0]
        last_time_str = last_point.get("time", "")
        
        # Parse the timestamp
        # InfluxDB returns ISO format: 2024-01-15T10:30:00Z
        try:
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            # Try alternative parsing for non-standard formats
            logger.debug(f"ISO parse failed for '{last_time_str}', trying dateutil: {e}")
            from dateutil import parser
            last_time = parser.parse(last_time_str)
        
        # Calculate hours since last sync
        now = datetime.now(timezone.utc)
        time_diff = now - last_time
        hours_since_sync = time_diff.total_seconds() / 3600
        
        # Determine sync status
        if hours_since_sync < 2:
            status = "healthy"
        elif hours_since_sync < 6:
            status = "delayed"
        elif hours_since_sync < 12:
            status = "warning"
        else:
            status = "stale"
        
        return {
            "sensor": "garmin_sync_status",
            "status": status,
            "last_sync_time": last_time.isoformat(),
            "hours_since_sync": round(hours_since_sync, 1),
            "last_heart_rate": last_point.get("last", 0)
        }
        
    except Exception as e:
        return {"sensor": "garmin_sync_status", "error": str(e)}


@friday_sensor(name="stress_level", interval_seconds=1800)  # Check every 30 min
def check_stress_level() -> Dict[str, Any]:
    """Check current stress levels from Garmin.
    
    Monitors:
    - Current stress level (from intraday)
    - Daily stress durations (high/medium/low/rest)
    
    Returns:
        Dictionary with stress data
    """
    try:
        # Get current stress from intraday data
        current_stress = query_latest("StressIntraday", "stressLevel, time")
        
        # Get daily stress breakdown
        daily_data = query_latest(
            "DailyStats",
            "highStressDuration, mediumStressDuration, lowStressDuration, restStressDuration, time"
        )
        
        if not current_stress and not daily_data:
            return {"sensor": "stress_level", "error": "No stress data available"}
        
        # Current stress level (0-100)
        current = current_stress.get("stressLevel", 0) if current_stress else 0
        
        # Daily durations (in seconds)
        high_sec = daily_data.get("highStressDuration", 0) or 0 if daily_data else 0
        med_sec = daily_data.get("mediumStressDuration", 0) or 0 if daily_data else 0
        low_sec = daily_data.get("lowStressDuration", 0) or 0 if daily_data else 0
        rest_sec = daily_data.get("restStressDuration", 0) or 0 if daily_data else 0
        
        # Convert to minutes
        high_min = round(high_sec / 60)
        rest_min = round(rest_sec / 60)
        
        # Calculate weighted average from durations if available
        total_sec = high_sec + med_sec + low_sec + rest_sec
        if total_sec > 0:
            # Approximate stress values: high=70, med=45, low=25, rest=10
            stress_avg = round((high_sec * 70 + med_sec * 45 + low_sec * 25 + rest_sec * 10) / total_sec)
        else:
            stress_avg = current
        
        # Determine stress status based on current reading
        if current >= 60:
            status = "high"
        elif current >= 40:
            status = "moderate"
        elif current >= 25:
            status = "normal"
        else:
            status = "low"
        
        return {
            "sensor": "stress_level",
            "current_stress": current,
            "stress_avg": stress_avg,
            "status": status,
            "high_stress_minutes": high_min,
            "rest_minutes": rest_min,
            "date": daily_data.get("time", "").split("T")[0] if daily_data else ""
        }
        
    except Exception as e:
        return {"sensor": "stress_level", "error": str(e)}
