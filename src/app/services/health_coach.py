"""Health & Running Coach Service using Garmin InfluxDB data"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from influxdb import InfluxDBClient
from app.core.config import settings
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
    
    def get_stress_data(self) -> Dict[str, Any]:
        """Get current and recent stress levels."""
        stress_data = {}
        
        # Current/recent stress (last valid reading in past hour)
        query = """
        SELECT stressLevel FROM StressIntraday 
        WHERE time >= now() - 1h AND stressLevel > 0
        ORDER BY time DESC LIMIT 1
        """
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points:
                stress_data["current_stress"] = int(points[0].get("stressLevel", 0))
        except Exception as e:
            logger.debug(f"Current stress query failed: {e}")
        
        # Average stress today (last 12 hours, excluding -1 values)
        query = """
        SELECT MEAN(stressLevel) as avg_stress 
        FROM StressIntraday 
        WHERE time >= now() - 12h AND stressLevel > 0
        """
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points and points[0].get("avg_stress"):
                stress_data["avg_stress_today"] = int(points[0]["avg_stress"])
        except Exception as e:
            logger.debug(f"Average stress query failed: {e}")
        
        # 7-day average for comparison
        query = """
        SELECT MEAN(stressLevel) as avg_stress 
        FROM StressIntraday 
        WHERE time >= now() - 7d AND stressLevel > 0
        """
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points and points[0].get("avg_stress"):
                stress_data["avg_stress_7day"] = int(points[0]["avg_stress"])
        except Exception as e:
            logger.debug(f"7-day stress query failed: {e}")
        
        # High stress duration today (stress > 60)
        query = """
        SELECT COUNT(stressLevel) as high_stress_count
        FROM StressIntraday 
        WHERE time >= now() - 12h AND stressLevel > 60
        """
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            if points and points[0].get("high_stress_count"):
                # Each reading is ~3 minutes apart, so multiply by 3 for approximate minutes
                stress_data["high_stress_minutes"] = int(points[0]["high_stress_count"]) * 3
        except Exception as e:
            logger.debug(f"High stress duration query failed: {e}")
        
        return stress_data
    
    def run_health_check(self) -> Dict[str, Any]:
        """
        Run comprehensive health check and return a score with recommendations.
        Similar to vault health check but for physical health.
        
        Returns:
            Dict with health_score (0-100), status, issues, and recommendations
        """
        issues = []
        recommendations = []
        score_penalty = 0
        details = {}
        
        try:
            # === 1. Recovery Status ===
            recovery = self.get_recovery_status()
            details["recovery"] = recovery
            
            # Body Battery
            if 'body_battery' in recovery:
                bb = recovery['body_battery']
                details["body_battery"] = bb
                
                if bb <= 10:
                    issues.append(f"Critical energy: Body Battery at {bb}/100")
                    recommendations.append("🔴 URGENT: Stop and rest immediately. Your energy is critically low.")
                    score_penalty += 40
                elif bb <= 20:
                    issues.append(f"Very low energy: Body Battery at {bb}/100")
                    recommendations.append("Take it easy today. Avoid intense activities and prioritize rest.")
                    score_penalty += 25
                elif bb <= 35:
                    issues.append(f"Low energy: Body Battery at {bb}/100")
                    recommendations.append("Consider reducing workload. A short break or nap would help.")
                    score_penalty += 15
                elif bb <= 50:
                    score_penalty += 5  # Minor penalty
            
            # Training Readiness
            if 'training_readiness' in recovery:
                tr = recovery['training_readiness']
                details["training_readiness"] = tr
                
                if tr < 20:
                    issues.append(f"Very low training readiness: {tr}/100")
                    recommendations.append("Skip workouts today. Your body needs full recovery.")
                    score_penalty += 20
                elif tr < 40:
                    issues.append(f"Low training readiness: {tr}/100")
                    recommendations.append("Light activity only - stretching or a gentle walk.")
                    score_penalty += 10
                elif tr < 60:
                    score_penalty += 5
            
            # Recovery Time
            if 'recovery_time' in recovery:
                rt = recovery['recovery_time']
                details["recovery_time_hours"] = rt
                
                if rt > 72:
                    issues.append(f"Extended recovery needed: {rt}h remaining")
                    recommendations.append("Focus on sleep, hydration, and nutrition. Your body is still recovering.")
                    score_penalty += 15
                elif rt > 48:
                    issues.append(f"High recovery time: {rt}h remaining")
                    score_penalty += 8
            
            # HRV
            if 'hrv_latest' in recovery and 'hrv_7day_avg' in recovery:
                hrv = recovery['hrv_latest']
                hrv_avg = recovery['hrv_7day_avg']
                details["hrv"] = hrv
                details["hrv_7day_avg"] = hrv_avg
                
                if hrv_avg > 0:
                    hrv_ratio = hrv / hrv_avg
                    if hrv_ratio < 0.6:
                        issues.append(f"HRV significantly below average: {hrv}ms vs {hrv_avg}ms avg")
                        recommendations.append("High stress indicator. Consider meditation, deep breathing, or reducing demands.")
                        score_penalty += 20
                    elif hrv_ratio < 0.75:
                        issues.append(f"HRV below average: {hrv}ms vs {hrv_avg}ms avg")
                        score_penalty += 10
            
            # === 2. Sleep Data ===
            sleep_data = self.get_sleep_data(days=1)
            if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
                sleep = sleep_data["sleep_records"][0]
                details["last_sleep"] = sleep
                
                sleep_score = sleep.get('sleep_score', 0)
                sleep_hours = sleep.get('total_sleep_hours', 0)
                deep_hours = sleep.get('deep_sleep_hours', 0)
                
                # Sleep score
                if sleep_score < 40:
                    issues.append(f"Very poor sleep: score {sleep_score}/100")
                    recommendations.append("Rough night. Take it easy, avoid caffeine, and prioritize early bedtime tonight.")
                    score_penalty += 25
                elif sleep_score < 60:
                    issues.append(f"Poor sleep quality: score {sleep_score}/100")
                    recommendations.append("Sleep wasn't great. Consider a lighter day and earlier bedtime.")
                    score_penalty += 15
                elif sleep_score < 70:
                    score_penalty += 5
                
                # Sleep duration
                if sleep_hours < 4:
                    issues.append(f"Severe sleep deficit: only {sleep_hours}h")
                    recommendations.append("Critical: You need rest. Consider a nap if possible.")
                    score_penalty += 30
                elif sleep_hours < 5.5:
                    issues.append(f"Short sleep: only {sleep_hours}h")
                    recommendations.append("Sleep deficit detected. Try to get to bed early tonight.")
                    score_penalty += 15
                elif sleep_hours < 6.5:
                    score_penalty += 5
                
                # Deep sleep (should be ~15-20% of total)
                if sleep_hours > 0 and deep_hours / sleep_hours < 0.10:
                    issues.append(f"Low deep sleep: only {deep_hours}h ({int(deep_hours/sleep_hours*100)}%)")
                    recommendations.append("Deep sleep was low. Avoid alcohol and screens before bed.")
                    score_penalty += 10
            
            # === 3. Recent Activity ===
            activities = self.get_recent_activities(limit=7)
            if "activities" in activities:
                recent = activities["activities"]
                details["recent_activities"] = len(recent)
                
                # Check for overtraining (too many intense days)
                intense_days = sum(1 for a in recent if a.get('avg_hr', 0) > 150)
                if intense_days >= 5:
                    issues.append(f"Possible overtraining: {intense_days} high-intensity sessions in 7 days")
                    recommendations.append("Consider a rest day. Too many intense sessions can lead to burnout.")
                    score_penalty += 15
                
                # Check for inactivity
                if len(recent) == 0 or (len(recent) == 1 and recent[0].get('date', '') < (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')):
                    issues.append("No recent activity detected")
                    recommendations.append("Try to move today - even a short walk helps.")
                    score_penalty += 10
            
            # === 4. Stress Data ===
            stress_data = self.get_stress_data()
            if stress_data:
                current_stress = stress_data.get("current_stress")
                avg_stress_today = stress_data.get("avg_stress_today")
                avg_stress_7day = stress_data.get("avg_stress_7day")
                high_stress_minutes = stress_data.get("high_stress_minutes", 0)
                
                # Add to details
                if current_stress:
                    details["current_stress"] = current_stress
                if avg_stress_today:
                    details["avg_stress_today"] = avg_stress_today
                if avg_stress_7day:
                    details["avg_stress_7day"] = avg_stress_7day
                if high_stress_minutes:
                    details["high_stress_minutes"] = high_stress_minutes
                
                # Check current stress level (Garmin scale: 0-100, >60 is high)
                if current_stress and current_stress >= 80:
                    issues.append(f"Very high current stress: {current_stress}/100")
                    recommendations.append("🧘 Take a break now. Try deep breathing: 4 seconds in, 7 hold, 8 out.")
                    score_penalty += 20
                elif current_stress and current_stress >= 60:
                    issues.append(f"Elevated stress: {current_stress}/100")
                    recommendations.append("Stress is elevated. Consider a short walk or stepping away from work.")
                    score_penalty += 10
                
                # Check average stress today vs 7-day average
                if avg_stress_today and avg_stress_7day and avg_stress_7day > 0:
                    stress_ratio = avg_stress_today / avg_stress_7day
                    if stress_ratio > 1.4:  # 40% above average
                        issues.append(f"Today's stress ({avg_stress_today}) is much higher than usual ({avg_stress_7day} avg)")
                        recommendations.append("Unusually stressful day. Prioritize winding down tonight.")
                        score_penalty += 15
                    elif stress_ratio > 1.2:  # 20% above average
                        issues.append(f"Stress above average today: {avg_stress_today} vs {avg_stress_7day} usual")
                        score_penalty += 8
                
                # Check prolonged high stress
                if high_stress_minutes and high_stress_minutes > 120:  # More than 2 hours of high stress
                    issues.append(f"Prolonged high stress: {high_stress_minutes} minutes today")
                    recommendations.append("You've been stressed for a while. Schedule a real break - not just scrolling.")
                    score_penalty += 15
                elif high_stress_minutes and high_stress_minutes > 60:
                    issues.append(f"Significant high stress period: {high_stress_minutes} minutes")
                    score_penalty += 8
        
        except Exception as e:
            logger.error(f"Error running health check: {e}", exc_info=True)
            issues.append(f"Error fetching some health data: {str(e)}")
        
        # Calculate final score
        health_score = max(0, 100 - score_penalty)
        
        # Determine status
        if health_score >= 80:
            status = "healthy"
            status_emoji = "🟢"
        elif health_score >= 60:
            status = "good"
            status_emoji = "🟡"
        elif health_score >= 40:
            status = "needs_attention"
            status_emoji = "🟠"
        else:
            status = "needs_rest"
            status_emoji = "🔴"
        
        # Add positive recommendation if healthy
        if not recommendations:
            recommendations.append("Looking good! You're well-rested and recovered. Great day for activity!")
        
        result = {
            "health_score": health_score,
            "status": status,
            "status_emoji": status_emoji,
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
            "checked_at": datetime.now().isoformat(),
        }
        
        logger.info(f"Health check complete: score={health_score}, status={status}")
        return result
    
    def get_health_summary_for_llm(self) -> str:
        """Get a formatted health check summary for display or LLM context."""
        result = self.run_health_check()
        
        lines = [
            f"## Health Status: {result['status'].replace('_', ' ').title()} {result['status_emoji']} ({result['health_score']}/100)",
            ""
        ]
        
        # Key metrics
        details = result.get("details", {})
        if details:
            lines.append("### Current Metrics")
            if "body_battery" in details:
                lines.append(f"- Body Battery: {details['body_battery']}/100")
            if "training_readiness" in details:
                lines.append(f"- Training Readiness: {details['training_readiness']}/100")
            if "hrv" in details:
                hrv_avg = details.get('hrv_7day_avg', 'N/A')
                lines.append(f"- HRV: {details['hrv']}ms (7-day avg: {hrv_avg}ms)")
            if "recovery_time_hours" in details:
                lines.append(f"- Recovery Time: {details['recovery_time_hours']}h")
            if "last_sleep" in details:
                sleep = details["last_sleep"]
                lines.append(f"- Last Sleep: {sleep.get('total_sleep', 'N/A')} (score: {sleep.get('sleep_score', 'N/A')})")
            lines.append("")
        
        # Issues
        if result["issues"]:
            lines.append("### Issues Found")
            for issue in result["issues"]:
                lines.append(f"- ⚠️ {issue}")
            lines.append("")
        
        # Recommendations
        lines.append("### Recommendations")
        for rec in result["recommendations"]:
            lines.append(f"- {rec}")
        
        return "\n".join(lines)

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
        config_file = settings.paths.config / settings.services.influxdb_config_file
        with open(config_file) as f:
            config = json.load(f)
        _health_coach = HealthCoachService(config)
    return _health_coach
