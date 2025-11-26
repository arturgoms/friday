"""Health & Running Coach Service using Garmin InfluxDB data"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from influxdb import InfluxDBClient


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
                
                return {
                    "period": f"Last {days} days",
                    "run_count": len(points),
                    "total_distance_km": round(total_distance / 1000, 2),
                    "total_time_hours": round(total_time / 3600, 2),
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
                
                activities.append({
                    "name": point.get("activityName", "Unknown"),
                    "type": point.get("activityType", "Unknown"),
                    "distance_km": round(dist / 1000, 2) if dist else 0,
                    "duration_min": round(duration / 60, 0) if duration else 0,
                    "pace_min_km": round(60 / (speed * 3.6), 2) if speed > 0 else 0,
                    "avg_hr": round(point.get("averageHR", 0), 0),
                    "calories": round(point.get("calories", 0), 0),
                    "date": point.get("time", "").split("T")[0]
                })
            
            return {"activities": activities}
        except Exception as e:
            return {"error": str(e)}
    
    def get_sleep_data(self, days: int = 1) -> Dict[str, Any]:
        """Get recent sleep data."""
        query = f"SELECT * FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        
        try:
            result = self.client.query(query)
            sleep_data = []
            
            for point in result.get_points():
                deep = point.get("deepSleepSeconds", 0)
                light = point.get("lightSleepSeconds", 0)
                rem = point.get("remSleepSeconds", 0)
                awake = point.get("awakeSleepSeconds", 0)
                total_sleep = deep + light + rem
                
                sleep_data.append({
                    "date": point.get("time", "").split("T")[0],
                    "total_sleep_hours": round(total_sleep / 3600, 1),
                    "deep_sleep_hours": round(deep / 3600, 1),
                    "light_sleep_hours": round(light / 3600, 1),
                    "rem_sleep_hours": round(rem / 3600, 1),
                    "awake_time_min": round(awake / 60, 0),
                    "sleep_score": point.get("sleepScore", 0),
                    "resting_hr": point.get("restingHeartRate", 0),
                    "hrv": point.get("avgOvernightHrv", 0),
                    "awake_count": point.get("awakeCount", 0)
                })
            
            return {"sleep_records": sleep_data}
        except Exception as e:
            return {"error": str(e)}
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get recovery indicators."""
        recovery_data = {}
        
        # Training Readiness
        query = "SELECT value as readiness FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                recovery_data["training_readiness"] = round(points[0].get("readiness", 0), 0)
        except:
            pass
        
        # Body Battery
        query = "SELECT value as battery FROM BodyBatteryIntraday ORDER BY time DESC LIMIT 1"
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                recovery_data["body_battery"] = round(points[0].get("battery", 0), 0)
        except:
            pass
        
        # Recent Sleep
        sleep_data = self.get_sleep_data(days=1)
        if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
            last_sleep = sleep_data["sleep_records"][0]
            recovery_data["last_sleep_hours"] = last_sleep["total_sleep_hours"]
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
