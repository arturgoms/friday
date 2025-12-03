"""Health & Running Coach Service using Garmin InfluxDB data"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from influxdb import InfluxDBClient
from app.core.logging import logger


def format_hours_to_hm(decimal_hours: float) -> str:
    """Convert decimal hours to Xh Ym format (e.g., 7.5 -> '7h 30m')."""
    if decimal_hours is None or decimal_hours == 0:
        return "0h 0m"
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)
    return f"{hours}h {minutes}m"


class HealthCoachService:
    """Service for health coaching using Garmin data from InfluxDB."""
    
    def __init__(self, config: dict):
        """Initialize connection to InfluxDB."""
        self.client = InfluxDBClient(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database=config["database"]
        )
        self.database = config["database"]
        
        try:
            self.client.ping()
            print(f"✅ Health Coach connected to InfluxDB ({config['host']})")
        except Exception as e:
            print(f"❌ Failed to connect to InfluxDB: {e}")
    
    def get_running_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get running summary."""
        start = datetime.now() - timedelta(days=days)
        
        query = f"""
        SELECT distance, movingDuration, averageSpeed, averageHR, calories
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        AND activityType = 'running'
        """
        
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            
            if points:
                total_distance = sum(p.get("distance", 0) for p in points)
                total_time = sum(p.get("movingDuration", 0) for p in points)
                avg_speed = sum(p.get("averageSpeed", 0) for p in points) / len(points)
                avg_hr = sum(p.get("averageHR", 0) for p in points if p.get("averageHR")) / len([p for p in points if p.get("averageHR")]) if any(p.get("averageHR") for p in points) else 0
                total_calories = sum(p.get("calories", 0) for p in points)
                
                total_time_hours = total_time / 3600
                return {
                    "period": f"Last {days} days",
                    "run_count": len(points),
                    "total_distance_km": round(total_distance / 1000, 2),
                    "total_time": format_hours_to_hm(total_time_hours),
                    "total_time_hours": round(total_time_hours, 2),  # Keep for calculations
                    "avg_speed_kmh": round(avg_speed * 3.6, 2),
                    "avg_pace_min_km": round(60 / (avg_speed * 3.6), 2) if avg_speed > 0 else 0,
                    "avg_heart_rate": round(avg_hr, 0),
                    "total_calories": round(total_calories, 0)
                }
            return {"message": "No running data found for this period"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_recent_activities(self, limit: int = 5) -> Dict[str, Any]:
        """Get recent activities."""
        query = f"""
        SELECT activityName, activityType, distance, movingDuration,
               averageSpeed, averageHR, calories, time
        FROM ActivitySummary
        WHERE activityType != 'No Activity'
        ORDER BY time DESC
        LIMIT {limit}
        """
        
        try:
            result = self.client.query(query)
            activities = []
            
            for point in result.get_points():
                dist = point.get("distance", 0)
                duration = point.get("movingDuration", 0)
                speed = point.get("averageSpeed", 0)
                duration_hours = duration / 3600 if duration else 0
                
                activities.append({
                    "name": point.get("activityName", "Unknown"),
                    "type": point.get("activityType", "Unknown"),
                    "distance_km": round(dist / 1000, 2) if dist else 0,
                    "duration": format_hours_to_hm(duration_hours),
                    "duration_min": round(duration / 60, 0) if duration else 0,  # Keep for compatibility
                    "pace_min_km": round(60 / (speed * 3.6), 2) if speed > 0 else 0,
                    "avg_hr": round(point.get("averageHR", 0), 0),
                    "calories": round(point.get("calories", 0), 0),
                    "date": point.get("time", "").split("T")[0]
                })
            
            return {"activities": activities}
        except Exception as e:
            return {"error": str(e)}
    
    def get_sleep_data(self, days: int = 1) -> Dict[str, Any]:
        """Get recent sleep data with comprehensive metrics."""
        query = f"SELECT * FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        
        try:
            result = self.client.query(query)
            sleep_data = []
            
            for point in result.get_points():
                deep = point.get("deepSleepSeconds", 0) or 0
                light = point.get("lightSleepSeconds", 0) or 0
                rem = point.get("remSleepSeconds", 0) or 0
                awake = point.get("awakeSleepSeconds", 0) or 0
                total_sleep = deep + light + rem
                
                total_hours = total_sleep / 3600
                deep_hours = deep / 3600
                light_hours = light / 3600
                rem_hours = rem / 3600
                
                sleep_score = point.get("sleepScore", 0) or 0
                awake_count = point.get("awakeCount", 0) or 0
                restless_moments = point.get("restlessMomentsCount", 0) or 0
                
                # Determine sleep quality assessment
                if sleep_score >= 80:
                    quality = "excellent"
                elif sleep_score >= 70:
                    quality = "good"
                elif sleep_score >= 60:
                    quality = "fair"
                else:
                    quality = "poor"
                
                sleep_data.append({
                    "date": point.get("time", "").split("T")[0],
                    # Duration data
                    "total_sleep": format_hours_to_hm(total_hours),
                    "total_sleep_hours": round(total_hours, 1),
                    "deep_sleep": format_hours_to_hm(deep_hours),
                    "deep_sleep_hours": round(deep_hours, 1),
                    "light_sleep": format_hours_to_hm(light_hours),
                    "light_sleep_hours": round(light_hours, 1),
                    "rem_sleep": format_hours_to_hm(rem_hours),
                    "rem_sleep_hours": round(rem_hours, 1),
                    # Quality metrics
                    "sleep_score": sleep_score,
                    "quality": quality,
                    # Disruption metrics
                    "awake_time_min": int(awake / 60),
                    "awake_count": awake_count,
                    "restless_moments": restless_moments,
                    # Recovery metrics
                    "resting_hr": point.get("restingHeartRate", 0) or 0,
                    "hrv": point.get("avgOvernightHrv", 0) or 0,
                    "avg_sleep_stress": point.get("avgSleepStress", 0) or 0,
                    "body_battery_change": point.get("bodyBatteryChange", 0) or 0,
                    # Breathing metrics
                    "avg_spo2": point.get("averageSpO2Value", 0) or 0,
                    "lowest_spo2": point.get("lowestSpO2Value", 0) or 0,
                    "avg_respiration": point.get("averageRespirationValue", 0) or 0,
                })
            
            return {"sleep_records": sleep_data}
        except Exception as e:
            return {"error": str(e)}
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get recovery indicators from multiple sources."""
        recovery_data = {}
        
        # Training Readiness (includes recovery time, HRV factor)
        query = "SELECT score, recoveryTime, hrvFactorPercent, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                point = points[0]
                recovery_data["training_readiness"] = int(point.get("score", 0))
                recovery_data["recovery_time"] = int(point.get("recoveryTime", 0))
                recovery_data["hrv_factor_percent"] = int(point.get("hrvFactorPercent", 0))
                recovery_data["readiness_level"] = point.get("level", "Unknown")
        except Exception as e:
            logger.debug(f"Training readiness query failed: {e}")
        
        # Body Battery from DailyStats (more comprehensive than intraday)
        query = "SELECT bodyBatteryAtWakeTime, bodyBatteryHighestValue, bodyBatteryLowestValue FROM DailyStats ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                point = points[0]
                recovery_data["body_battery_wake"] = int(point.get("bodyBatteryAtWakeTime", 0))
                recovery_data["body_battery_highest"] = int(point.get("bodyBatteryHighestValue", 0))
                recovery_data["body_battery_lowest"] = int(point.get("bodyBatteryLowestValue", 0))
        except Exception as e:
            logger.debug(f"Body battery from DailyStats query failed: {e}")
        
        # Current Body Battery from intraday
        query = "SELECT BodyBatteryLevel FROM BodyBatteryIntraday ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                recovery_data["body_battery"] = int(points[0].get("BodyBatteryLevel", 0))
        except Exception as e:
            logger.debug(f"Body battery current query failed: {e}")
        
        # HRV - Calculate 7-day average from intraday data
        query = "SELECT MEAN(hrvValue) as hrv_avg FROM HRV_Intraday WHERE time >= now() - 7d"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points and points[0].get("hrv_avg"):
                recovery_data["hrv_7day_avg"] = int(points[0]["hrv_avg"])
        except Exception as e:
            logger.debug(f"HRV weekly average query failed: {e}")
        
        # Latest HRV reading
        query = "SELECT hrvValue FROM HRV_Intraday ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                recovery_data["hrv_latest"] = int(points[0].get("hrvValue", 0))
        except Exception as e:
            logger.debug(f"HRV latest query failed: {e}")
        
        # Recent Sleep
        sleep_data = self.get_sleep_data(days=1)
        if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
            last_sleep = sleep_data["sleep_records"][0]
            recovery_data["last_sleep"] = last_sleep["total_sleep"]  # Formatted string
            recovery_data["last_sleep_hours"] = last_sleep["total_sleep_hours"]  # For calculations
            recovery_data["sleep_score"] = last_sleep["sleep_score"]
            recovery_data["resting_hr"] = last_sleep["resting_hr"]
            recovery_data["hrv"] = last_sleep["hrv"]
        
        return recovery_data
    
    def generate_coaching_summary(self) -> str:
        """Generate comprehensive coaching summary."""
        lines = []
        lines.append("🏃 FRIDAY AI - YOUR RUNNING COACH")
        lines.append("=" * 50)
        
        # Running Summary
        summary = self.get_running_summary(days=30)
        if "run_count" in summary:
            lines.append("\n📊 LAST 30 DAYS:")
            lines.append(f"  • Runs: {summary['run_count']}")
            lines.append(f"  • Distance: {summary['total_distance_km']} km")
            lines.append(f"  • Time: {summary['total_time_hours']} hours")
            lines.append(f"  • Avg Pace: {summary['avg_pace_min_km']} min/km")
            lines.append(f"  • Avg HR: {summary['avg_heart_rate']} bpm")
            lines.append(f"  • Calories: {summary['total_calories']}")
        
        # Recent Activities
        activities = self.get_recent_activities(limit=3)
        if "activities" in activities and activities["activities"]:
            lines.append("\n🏃 RECENT ACTIVITIES:")
            for act in activities["activities"][:3]:
                lines.append(f"  • {act['date']}: {act['name']} ({act['type']})")
                if act['distance_km'] > 0:
                    lines.append(f"    {act['distance_km']}km, {act['duration_min']}min, {act['pace_min_km']} min/km")
        
        # Recovery
        recovery = self.get_recovery_status()
        if recovery:
            lines.append("\n💤 RECOVERY STATUS:")
            for key, value in recovery.items():
                lines.append(f"  • {key.replace('_', ' ').title()}: {value}")
        
        lines.append("\n" + "=" * 50)
        return "\n".join(lines)


# Singleton
_health_coach = None

def get_health_coach():
    """Get health coach instance."""
    global _health_coach
    if _health_coach is None:
        with open("/home/artur/friday/config/influxdb_mcp.json") as f:
            config = json.load(f)
        _health_coach = HealthCoachService(config)
    return _health_coach
