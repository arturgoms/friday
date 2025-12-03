"""
InfluxDB v1 MCP Server for Health & Running Data
Provides comprehensive tools for querying Garmin health metrics and coaching analysis
"""
import json
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from influxdb import InfluxDBClient
from mcp.server import Server
from mcp.types import Tool, TextContent


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration."""
    if seconds is None or seconds == 0:
        return "0m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_pace(speed_ms: float) -> str:
    """Convert speed (m/s) to pace (min:sec/km)."""
    if speed_ms is None or speed_ms <= 0:
        return "N/A"
    pace_min_km = 1000 / (speed_ms * 60)  # minutes per km
    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/km"


def pace_to_decimal(speed_ms: float) -> float:
    """Convert speed (m/s) to pace in decimal minutes per km."""
    if speed_ms is None or speed_ms <= 0:
        return 0
    return 1000 / (speed_ms * 60)


class InfluxDBHealthMCP:
    """MCP Server for InfluxDB health/running data."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8086,
        username: str = "",
        password: str = "",
        database: str = "health"
    ):
        """Initialize InfluxDB connection."""
        self.client = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database
        )
        self.database = database
        
        # Test connection
        try:
            self.client.ping()
            print(f"Connected to InfluxDB at {host}:{port}")
        except Exception as e:
            print(f"Failed to connect to InfluxDB: {e}")
    
    def _query(self, query: str) -> List[Dict]:
        """Execute query and return points list."""
        try:
            result = self.client.query(query)
            return list(result.get_points())
        except Exception as e:
            return []

    # =========================================================================
    # RUNNING & TRAINING ANALYSIS
    # =========================================================================
    
    def get_recent_runs(self, limit: int = 10, days: int = 30) -> Dict[str, Any]:
        """Get recent running activities with details."""
        start = datetime.now() - timedelta(days=days)
        
        query = f"""
        SELECT activityName, distance, movingDuration, averageSpeed, 
               averageHR, maxHR, calories, elevationGain, aerobicTE, anaerobicTE
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        AND activityType = 'running'
        ORDER BY time DESC
        LIMIT {limit}
        """
        
        points = self._query(query)
        
        if not points:
            return {"runs": [], "message": "No running data found for this period"}
        
        runs = []
        for p in points:
            speed = p.get("averageSpeed", 0)
            runs.append({
                "name": p.get("activityName", "Run"),
                "date": p.get("time", "").split("T")[0],
                "distance_km": round(p.get("distance", 0) / 1000, 2),
                "duration": format_duration(p.get("movingDuration", 0)),
                "pace": format_pace(speed),
                "pace_decimal": round(pace_to_decimal(speed), 2),
                "avg_hr": int(p.get("averageHR", 0) or 0),
                "max_hr": int(p.get("maxHR", 0) or 0),
                "calories": int(p.get("calories", 0) or 0),
                "elevation_m": int(p.get("elevationGain", 0) or 0),
                "aerobic_te": round(p.get("aerobicTE", 0) or 0, 1),
                "anaerobic_te": round(p.get("anaerobicTE", 0) or 0, 1)
            })
        
        return {
            "runs": runs,
            "count": len(runs),
            "period_days": days
        }
    
    def get_training_load(self, weeks: int = 4) -> Dict[str, Any]:
        """Analyze weekly training load: mileage, time, intensity."""
        weekly_data = []
        
        for week in range(weeks):
            week_start = datetime.now() - timedelta(weeks=week+1)
            week_end = datetime.now() - timedelta(weeks=week)
            
            query = f"""
            SELECT distance, movingDuration, averageHR, averageSpeed, aerobicTE
            FROM ActivitySummary
            WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
            AND activityType = 'running'
            """
            
            points = self._query(query)
            
            if points:
                total_distance = sum(p.get("distance", 0) for p in points)
                total_duration = sum(p.get("movingDuration", 0) for p in points)
                avg_hr_values = [p.get("averageHR", 0) for p in points if p.get("averageHR")]
                avg_speed_values = [p.get("averageSpeed", 0) for p in points if p.get("averageSpeed")]
                avg_te = sum(p.get("aerobicTE", 0) or 0 for p in points) / len(points) if points else 0
                
                weekly_data.append({
                    "week": week + 1,
                    "week_ending": week_end.strftime("%Y-%m-%d"),
                    "total_km": round(total_distance / 1000, 2),
                    "total_time": format_duration(total_duration),
                    "total_time_hours": round(total_duration / 3600, 2),
                    "run_count": len(points),
                    "avg_hr": round(sum(avg_hr_values) / len(avg_hr_values), 0) if avg_hr_values else 0,
                    "avg_pace": format_pace(sum(avg_speed_values) / len(avg_speed_values)) if avg_speed_values else "N/A",
                    "avg_training_effect": round(avg_te, 1)
                })
            else:
                weekly_data.append({
                    "week": week + 1,
                    "week_ending": week_end.strftime("%Y-%m-%d"),
                    "total_km": 0,
                    "total_time": "0m",
                    "run_count": 0
                })
        
        # Calculate trends
        if len(weekly_data) >= 2:
            km_values = [w["total_km"] for w in weekly_data if w["total_km"] > 0]
            if len(km_values) >= 2:
                trend = "increasing" if km_values[0] > km_values[-1] else "decreasing" if km_values[0] < km_values[-1] else "stable"
            else:
                trend = "insufficient data"
        else:
            trend = "insufficient data"
        
        return {
            "weeks_analyzed": weeks,
            "weekly_data": list(reversed(weekly_data)),
            "mileage_trend": trend,
            "total_km": round(sum(w["total_km"] for w in weekly_data), 2),
            "total_runs": sum(w["run_count"] for w in weekly_data)
        }
    
    def get_pace_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Analyze pace trends and consistency."""
        start = datetime.now() - timedelta(days=days)
        
        query = f"""
        SELECT averageSpeed, distance, movingDuration, time
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        AND activityType = 'running'
        ORDER BY time DESC
        """
        
        points = self._query(query)
        
        if not points:
            return {"message": "No running data found for pace analysis"}
        
        paces = []
        for p in points:
            speed = p.get("averageSpeed", 0)
            if speed > 0:
                paces.append({
                    "date": p.get("time", "").split("T")[0],
                    "pace_decimal": pace_to_decimal(speed),
                    "pace": format_pace(speed),
                    "distance_km": round(p.get("distance", 0) / 1000, 2)
                })
        
        if not paces:
            return {"message": "No pace data available"}
        
        pace_values = [p["pace_decimal"] for p in paces]
        best_pace = min(pace_values)
        worst_pace = max(pace_values)
        avg_pace = sum(pace_values) / len(pace_values)
        
        # Calculate consistency (standard deviation)
        variance = sum((p - avg_pace) ** 2 for p in pace_values) / len(pace_values)
        std_dev = variance ** 0.5
        consistency = "very consistent" if std_dev < 0.3 else "consistent" if std_dev < 0.6 else "variable"
        
        return {
            "period_days": days,
            "run_count": len(paces),
            "average_pace": f"{int(avg_pace)}:{int((avg_pace % 1) * 60):02d}/km",
            "best_pace": f"{int(best_pace)}:{int((best_pace % 1) * 60):02d}/km",
            "slowest_pace": f"{int(worst_pace)}:{int((worst_pace % 1) * 60):02d}/km",
            "pace_std_dev": round(std_dev, 2),
            "consistency": consistency,
            "recent_runs": paces[:5]
        }
    
    def get_vo2max_progress(self, months: int = 6) -> Dict[str, Any]:
        """Track VO2 Max cardiovascular fitness over time."""
        start = datetime.now() - timedelta(days=months * 30)
        
        query = f"""
        SELECT vo2Max
        FROM DailyStats
        WHERE time >= '{start.isoformat()}Z'
        AND vo2Max > 0
        ORDER BY time ASC
        """
        
        points = self._query(query)
        
        if not points:
            return {"message": "No VO2 Max data found"}
        
        readings = []
        for p in points:
            vo2 = p.get("vo2Max")
            if vo2 and vo2 > 0:
                readings.append({
                    "date": p.get("time", "").split("T")[0],
                    "vo2max": round(vo2, 1)
                })
        
        if not readings:
            return {"message": "No valid VO2 Max readings"}
        
        values = [r["vo2max"] for r in readings]
        current = values[-1]
        starting = values[0]
        change = current - starting
        
        # Monthly averages
        monthly_data = {}
        for r in readings:
            month = r["date"][:7]  # YYYY-MM
            if month not in monthly_data:
                monthly_data[month] = []
            monthly_data[month].append(r["vo2max"])
        
        monthly_avgs = [
            {"month": m, "avg_vo2max": round(sum(v)/len(v), 1)}
            for m, v in sorted(monthly_data.items())
        ]
        
        return {
            "period_months": months,
            "current_vo2max": current,
            "starting_vo2max": starting,
            "change": round(change, 1),
            "trend": "improving" if change > 0 else "declining" if change < 0 else "stable",
            "peak_vo2max": max(values),
            "lowest_vo2max": min(values),
            "monthly_progress": monthly_avgs
        }
    
    def get_race_predictions(self) -> Dict[str, Any]:
        """Get predicted race finish times based on VO2 Max and recent performance."""
        # Get latest VO2 Max
        query = "SELECT vo2Max FROM DailyStats WHERE vo2Max > 0 ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        
        vo2max = points[0].get("vo2Max") if points else None
        
        # Get recent race prediction data from Garmin if available
        query = "SELECT * FROM RacePrediction ORDER BY time DESC LIMIT 1"
        race_points = self._query(query)
        
        if race_points:
            p = race_points[0]
            return {
                "vo2max": round(vo2max, 1) if vo2max else "N/A",
                "predictions": {
                    "5k": format_duration(p.get("time5K", 0)),
                    "10k": format_duration(p.get("time10K", 0)),
                    "half_marathon": format_duration(p.get("timeHalfMarathon", 0)),
                    "marathon": format_duration(p.get("timeMarathon", 0))
                },
                "source": "garmin_prediction"
            }
        
        # Calculate estimates from VO2 Max if no Garmin predictions
        if vo2max:
            # Rough estimates based on VO2 Max (simplified formula)
            # These are approximations
            return {
                "vo2max": round(vo2max, 1),
                "predictions": {
                    "5k": "Estimate based on VO2 Max - use recent race times for accuracy",
                    "10k": "Estimate based on VO2 Max - use recent race times for accuracy",
                    "half_marathon": "Estimate based on VO2 Max - use recent race times for accuracy",
                    "marathon": "Estimate based on VO2 Max - use recent race times for accuracy"
                },
                "note": "No Garmin race predictions available. Consider running a time trial for accurate predictions.",
                "source": "vo2max_estimate"
            }
        
        return {"message": "Insufficient data for race predictions. Need VO2 Max or recent race data."}
    
    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status, load, and recovery recommendations."""
        result = {}
        
        # Training Readiness
        query = "SELECT score, recoveryTime, hrvFactorPercent, level, sleepFactorPercent, acuteLoadPercent FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            p = points[0]
            result["training_readiness"] = {
                "score": int(p.get("score", 0)),
                "level": p.get("level", "Unknown"),
                "recovery_time_hours": int(p.get("recoveryTime", 0)),
                "hrv_factor": int(p.get("hrvFactorPercent", 0)),
                "sleep_factor": int(p.get("sleepFactorPercent", 0)),
                "acute_load_factor": int(p.get("acuteLoadPercent", 0))
            }
        
        # Training Status from Garmin
        query = "SELECT trainingStatus, trainingStatusDescription FROM DailyStats ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            p = points[0]
            result["training_status"] = {
                "status": p.get("trainingStatus", "Unknown"),
                "description": p.get("trainingStatusDescription", "")
            }
        
        # Recent training load (last 7 days vs previous 7 days)
        week1_start = datetime.now() - timedelta(days=7)
        week2_start = datetime.now() - timedelta(days=14)
        
        query = f"""
        SELECT SUM(distance) as dist, COUNT(distance) as cnt, MEAN(aerobicTE) as te
        FROM ActivitySummary
        WHERE time >= '{week1_start.isoformat()}Z'
        AND activityType = 'running'
        """
        points = self._query(query)
        week1_km = round((points[0].get("dist", 0) or 0) / 1000, 2) if points else 0
        week1_runs = int(points[0].get("cnt", 0) or 0) if points else 0
        week1_te = round(points[0].get("te", 0) or 0, 1) if points else 0
        
        query = f"""
        SELECT SUM(distance) as dist, COUNT(distance) as cnt
        FROM ActivitySummary
        WHERE time >= '{week2_start.isoformat()}Z' AND time < '{week1_start.isoformat()}Z'
        AND activityType = 'running'
        """
        points = self._query(query)
        week2_km = round((points[0].get("dist", 0) or 0) / 1000, 2) if points else 0
        
        load_change = round(((week1_km - week2_km) / week2_km * 100), 1) if week2_km > 0 else 0
        
        result["recent_load"] = {
            "this_week_km": week1_km,
            "last_week_km": week2_km,
            "load_change_pct": load_change,
            "runs_this_week": week1_runs,
            "avg_training_effect": week1_te,
            "recommendation": "Maintain" if -10 <= load_change <= 10 else "Reduce load" if load_change > 20 else "Can increase load"
        }
        
        return result
    
    def get_heart_rate_zones(self, days: int = 30) -> Dict[str, Any]:
        """Analyze time spent in different HR zones."""
        start = datetime.now() - timedelta(days=days)
        
        # Get HR zone data from activities
        query = f"""
        SELECT zone1Seconds, zone2Seconds, zone3Seconds, zone4Seconds, zone5Seconds,
               averageHR, maxHR
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        AND activityType = 'running'
        """
        
        points = self._query(query)
        
        if not points:
            return {"message": "No heart rate zone data found"}
        
        total_z1 = sum(p.get("zone1Seconds", 0) or 0 for p in points)
        total_z2 = sum(p.get("zone2Seconds", 0) or 0 for p in points)
        total_z3 = sum(p.get("zone3Seconds", 0) or 0 for p in points)
        total_z4 = sum(p.get("zone4Seconds", 0) or 0 for p in points)
        total_z5 = sum(p.get("zone5Seconds", 0) or 0 for p in points)
        total_time = total_z1 + total_z2 + total_z3 + total_z4 + total_z5
        
        avg_hr_values = [p.get("averageHR", 0) for p in points if p.get("averageHR")]
        max_hr_values = [p.get("maxHR", 0) for p in points if p.get("maxHR")]
        
        if total_time == 0:
            return {"message": "No zone time data recorded"}
        
        return {
            "period_days": days,
            "activities_analyzed": len(points),
            "zone_distribution": {
                "zone1_easy": {"time": format_duration(total_z1), "percent": round(total_z1/total_time*100, 1)},
                "zone2_aerobic": {"time": format_duration(total_z2), "percent": round(total_z2/total_time*100, 1)},
                "zone3_tempo": {"time": format_duration(total_z3), "percent": round(total_z3/total_time*100, 1)},
                "zone4_threshold": {"time": format_duration(total_z4), "percent": round(total_z4/total_time*100, 1)},
                "zone5_max": {"time": format_duration(total_z5), "percent": round(total_z5/total_time*100, 1)}
            },
            "total_training_time": format_duration(total_time),
            "avg_hr": round(sum(avg_hr_values)/len(avg_hr_values), 0) if avg_hr_values else 0,
            "max_hr_recorded": max(max_hr_values) if max_hr_values else 0,
            "polarization": "well polarized" if (total_z1+total_z2)/total_time > 0.7 else "moderate" if (total_z1+total_z2)/total_time > 0.5 else "intensity heavy"
        }
    
    def get_long_runs(self, min_distance_km: float = 15, months: int = 3) -> Dict[str, Any]:
        """Get runs over a specified distance."""
        start = datetime.now() - timedelta(days=months * 30)
        min_distance_m = min_distance_km * 1000
        
        query = f"""
        SELECT activityName, distance, movingDuration, averageSpeed, averageHR, elevationGain
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        AND activityType = 'running'
        AND distance >= {min_distance_m}
        ORDER BY time DESC
        """
        
        points = self._query(query)
        
        if not points:
            return {"runs": [], "message": f"No runs over {min_distance_km}km found in the last {months} months"}
        
        runs = []
        for p in points:
            speed = p.get("averageSpeed", 0)
            runs.append({
                "name": p.get("activityName", "Long Run"),
                "date": p.get("time", "").split("T")[0],
                "distance_km": round(p.get("distance", 0) / 1000, 2),
                "duration": format_duration(p.get("movingDuration", 0)),
                "pace": format_pace(speed),
                "avg_hr": int(p.get("averageHR", 0) or 0),
                "elevation_m": int(p.get("elevationGain", 0) or 0)
            })
        
        return {
            "min_distance_km": min_distance_km,
            "period_months": months,
            "count": len(runs),
            "runs": runs,
            "longest_km": max(r["distance_km"] for r in runs) if runs else 0
        }

    # =========================================================================
    # SLEEP & RECOVERY
    # =========================================================================
    
    def get_sleep_analysis(self, days: int = 7) -> Dict[str, Any]:
        """Get detailed sleep analysis."""
        query = f"SELECT * FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        
        points = self._query(query)
        
        if not points:
            return {"message": "No sleep data found"}
        
        sleep_records = []
        for p in points:
            deep = p.get("deepSleepSeconds", 0) or 0
            light = p.get("lightSleepSeconds", 0) or 0
            rem = p.get("remSleepSeconds", 0) or 0
            awake = p.get("awakeSleepSeconds", 0) or 0
            total = deep + light + rem
            
            sleep_records.append({
                "date": p.get("time", "").split("T")[0],
                "total_sleep": format_duration(total),
                "total_hours": round(total / 3600, 1),
                "deep_sleep": format_duration(deep),
                "light_sleep": format_duration(light),
                "rem_sleep": format_duration(rem),
                "awake_time": format_duration(awake),
                "sleep_score": p.get("sleepScore", 0),
                "resting_hr": p.get("restingHeartRate", 0),
                "hrv": p.get("avgOvernightHrv", 0),
                "spo2_avg": p.get("avgSpo2", 0),
                "awake_count": p.get("awakeCount", 0)
            })
        
        # Calculate averages
        total_hours = [r["total_hours"] for r in sleep_records]
        scores = [r["sleep_score"] for r in sleep_records if r["sleep_score"]]
        hrvs = [r["hrv"] for r in sleep_records if r["hrv"]]
        
        return {
            "days_analyzed": len(sleep_records),
            "records": sleep_records,
            "averages": {
                "avg_sleep_hours": round(sum(total_hours)/len(total_hours), 1) if total_hours else 0,
                "avg_sleep_score": round(sum(scores)/len(scores), 0) if scores else 0,
                "avg_hrv": round(sum(hrvs)/len(hrvs), 0) if hrvs else 0
            },
            "sleep_quality": "excellent" if sum(scores)/len(scores) >= 80 else "good" if sum(scores)/len(scores) >= 60 else "needs improvement" if scores else "unknown"
        }
    
    def get_recovery_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get recovery indicators: body battery, sleep quality, stress, HRV."""
        result: Dict[str, Any] = {"days_analyzed": days}
        
        # Body Battery trends
        query = f"SELECT bodyBatteryAtWakeTime, bodyBatteryHighestValue, bodyBatteryLowestValue FROM DailyStats ORDER BY time DESC LIMIT {days}"
        points = self._query(query)
        if points:
            wake_values = [p.get("bodyBatteryAtWakeTime", 0) or 0 for p in points]
            result["body_battery"] = {
                "avg_wake_level": round(sum(wake_values)/len(wake_values), 0) if wake_values else 0,
                "recent_wake_levels": wake_values[:5],
                "trend": "good" if sum(wake_values[:3])/3 >= 60 else "moderate" if sum(wake_values[:3])/3 >= 40 else "low"
            }
        
        # Sleep quality
        query = f"SELECT sleepScore, avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        points = self._query(query)
        if points:
            scores = [p.get("sleepScore", 0) or 0 for p in points]
            hrvs = [p.get("avgOvernightHrv", 0) or 0 for p in points if p.get("avgOvernightHrv")]
            result["sleep_quality"] = {
                "avg_score": round(sum(scores)/len(scores), 0) if scores else 0,
                "recent_scores": scores[:5],
                "avg_hrv": round(sum(hrvs)/len(hrvs), 0) if hrvs else 0
            }
        
        # Stress levels
        query = f"SELECT stressAvg, stressHigh, stressMedium, stressLow, restStress FROM DailyStats ORDER BY time DESC LIMIT {days}"
        points = self._query(query)
        if points:
            stress_avgs = [p.get("stressAvg", 0) or 0 for p in points if p.get("stressAvg")]
            result["stress"] = {
                "avg_stress": round(sum(stress_avgs)/len(stress_avgs), 0) if stress_avgs else 0,
                "recent_values": stress_avgs[:5],
                "level": "low" if sum(stress_avgs)/len(stress_avgs) < 30 else "moderate" if sum(stress_avgs)/len(stress_avgs) < 50 else "high" if stress_avgs else "unknown"
            }
        
        # Training readiness
        query = "SELECT score, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            result["training_readiness"] = {
                "score": int(points[0].get("score", 0)),
                "level": points[0].get("level", "Unknown")
            }
        
        return result
    
    def get_recovery_status(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive recovery status with recommendations."""
        result: Dict[str, Any] = {}
        
        # Training Readiness
        query = "SELECT score, recoveryTime, hrvFactorPercent, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            p = points[0]
            readiness_score = int(p.get("score", 0))
            result["training_readiness"] = {
                "score": readiness_score,
                "level": p.get("level", "Unknown"),
                "recovery_time_hours": int(p.get("recoveryTime", 0)),
                "hrv_factor": int(p.get("hrvFactorPercent", 0))
            }
        else:
            readiness_score = 0
        
        # Body Battery Pattern (wake vs current)
        query = "SELECT bodyBatteryAtWakeTime FROM DailyStats ORDER BY time DESC LIMIT 7"
        points = self._query(query)
        if points:
            wake_values = [p.get("bodyBatteryAtWakeTime", 0) or 0 for p in points]
            result["body_battery_pattern"] = {
                "wake_values": wake_values,
                "avg_wake": round(sum(wake_values)/len(wake_values), 0),
                "trend": "improving" if wake_values[0] > wake_values[-1] else "declining" if wake_values[0] < wake_values[-1] else "stable"
            }
        
        # Current body battery
        query = "SELECT BodyBatteryLevel FROM BodyBatteryIntraday ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            result["current_body_battery"] = int(points[0].get("BodyBatteryLevel", 0))
        
        # HRV Trends
        query = f"SELECT avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        points = self._query(query)
        if points:
            hrv_values = [p.get("avgOvernightHrv", 0) or 0 for p in points if p.get("avgOvernightHrv")]
            if hrv_values:
                result["hrv_trend"] = {
                    "recent_values": hrv_values,
                    "avg": round(sum(hrv_values)/len(hrv_values), 0),
                    "trend": "improving" if hrv_values[0] > sum(hrv_values)/len(hrv_values) else "stable" if abs(hrv_values[0] - sum(hrv_values)/len(hrv_values)) < 5 else "declining"
                }
        
        # Generate recommendations
        recommendations = []
        if readiness_score >= 75:
            recommendations.append("Ready for high-intensity training")
        elif readiness_score >= 50:
            recommendations.append("Moderate training recommended")
        elif readiness_score > 0:
            recommendations.append("Focus on recovery - light activity only")
        
        if result.get("body_battery_pattern", {}).get("avg_wake", 0) < 50:
            recommendations.append("Consider earlier bedtime for better recovery")
        
        if result.get("hrv_trend", {}).get("trend") == "declining":
            recommendations.append("HRV declining - monitor for overtraining")
        
        result["recommendations"] = recommendations if recommendations else ["Data insufficient for recommendations"]
        
        return result
    
    def get_hrv_analysis(self, days: int = 14) -> Dict[str, Any]:
        """Analyze HRV patterns for recovery assessment."""
        # Overnight HRV from sleep
        query = f"SELECT avgOvernightHrv, time FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        points = self._query(query)
        
        if not points:
            return {"message": "No HRV data found"}
        
        hrv_data = []
        for p in points:
            hrv = p.get("avgOvernightHrv", 0)
            if hrv and hrv > 0:
                hrv_data.append({
                    "date": p.get("time", "").split("T")[0],
                    "hrv": int(hrv)
                })
        
        if not hrv_data:
            return {"message": "No valid HRV readings"}
        
        values = [h["hrv"] for h in hrv_data]
        avg_hrv = sum(values) / len(values)
        
        # Calculate 7-day rolling average for trend
        recent_avg = sum(values[:7]) / min(7, len(values))
        older_avg = sum(values[7:14]) / max(1, len(values[7:14])) if len(values) > 7 else recent_avg
        
        # Calculate variability (coefficient of variation)
        variance = sum((v - avg_hrv) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5
        cv = (std_dev / avg_hrv) * 100 if avg_hrv > 0 else 0
        
        return {
            "days_analyzed": len(hrv_data),
            "readings": hrv_data,
            "statistics": {
                "average": round(avg_hrv, 0),
                "max": max(values),
                "min": min(values),
                "std_dev": round(std_dev, 1),
                "coefficient_of_variation": round(cv, 1)
            },
            "trend": {
                "recent_7day_avg": round(recent_avg, 0),
                "previous_7day_avg": round(older_avg, 0),
                "direction": "improving" if recent_avg > older_avg else "declining" if recent_avg < older_avg else "stable"
            },
            "interpretation": "High HRV variability indicates good recovery capacity" if avg_hrv > 50 else "Moderate HRV - maintain recovery focus" if avg_hrv > 30 else "Low HRV - prioritize rest and recovery"
        }

    # =========================================================================
    # HEALTH & WELLNESS
    # =========================================================================
    
    def get_weekly_health_digest(self, weeks_ago: int = 0) -> Dict[str, Any]:
        """Get comprehensive weekly health overview."""
        week_start = datetime.now() - timedelta(weeks=weeks_ago+1)
        week_end = datetime.now() - timedelta(weeks=weeks_ago)
        
        result: Dict[str, Any] = {
            "week_ending": week_end.strftime("%Y-%m-%d"),
            "week_start": week_start.strftime("%Y-%m-%d")
        }
        
        # Activities
        query = f"""
        SELECT activityType, distance, movingDuration, calories
        FROM ActivitySummary
        WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
        """
        points = self._query(query)
        if points:
            by_type = {}
            for p in points:
                atype = p.get("activityType", "other")
                if atype not in by_type:
                    by_type[atype] = {"count": 0, "distance": 0, "duration": 0, "calories": 0}
                by_type[atype]["count"] += 1
                by_type[atype]["distance"] += p.get("distance", 0) or 0
                by_type[atype]["duration"] += p.get("movingDuration", 0) or 0
                by_type[atype]["calories"] += p.get("calories", 0) or 0
            
            result["activities"] = {
                k: {
                    "count": v["count"],
                    "distance_km": round(v["distance"]/1000, 2),
                    "duration": format_duration(v["duration"]),
                    "calories": int(v["calories"])
                }
                for k, v in by_type.items()
            }
            result["total_activities"] = len(points)
            result["total_calories_burned"] = sum(p.get("calories", 0) or 0 for p in points)
        
        # Sleep averages
        query = f"""
        SELECT sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds
        FROM SleepSummary
        WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
        """
        points = self._query(query)
        if points:
            scores = [p.get("sleepScore", 0) or 0 for p in points]
            total_sleep = [
                (p.get("deepSleepSeconds", 0) or 0) + 
                (p.get("lightSleepSeconds", 0) or 0) + 
                (p.get("remSleepSeconds", 0) or 0)
                for p in points
            ]
            result["sleep"] = {
                "avg_score": round(sum(scores)/len(scores), 0) if scores else 0,
                "avg_duration_hours": round(sum(total_sleep)/len(total_sleep)/3600, 1) if total_sleep else 0,
                "nights_tracked": len(points)
            }
        
        # Stress and recovery
        query = f"""
        SELECT stressAvg, bodyBatteryAtWakeTime
        FROM DailyStats
        WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
        """
        points = self._query(query)
        if points:
            stress = [p.get("stressAvg", 0) or 0 for p in points if p.get("stressAvg")]
            bb = [p.get("bodyBatteryAtWakeTime", 0) or 0 for p in points if p.get("bodyBatteryAtWakeTime")]
            result["wellness"] = {
                "avg_stress": round(sum(stress)/len(stress), 0) if stress else 0,
                "avg_body_battery_wake": round(sum(bb)/len(bb), 0) if bb else 0,
                "days_tracked": len(points)
            }
        
        # Steps
        query = f"""
        SELECT totalSteps, totalDistanceMeters
        FROM DailyStats
        WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
        """
        points = self._query(query)
        if points:
            steps = [p.get("totalSteps", 0) or 0 for p in points]
            result["daily_activity"] = {
                "total_steps": sum(steps),
                "avg_steps": round(sum(steps)/len(steps), 0) if steps else 0,
                "days_tracked": len(points)
            }
        
        return result
    
    def get_stress_patterns(self, days: int = 7) -> Dict[str, Any]:
        """Analyze stress patterns throughout day/week."""
        query = f"SELECT stressAvg, stressHigh, stressMedium, stressLow, restStress FROM DailyStats ORDER BY time DESC LIMIT {days}"
        
        points = self._query(query)
        
        if not points:
            return {"message": "No stress data found"}
        
        daily_data = []
        for p in points:
            daily_data.append({
                "date": p.get("time", "").split("T")[0],
                "avg_stress": int(p.get("stressAvg", 0) or 0),
                "high_stress_min": int((p.get("stressHigh", 0) or 0) / 60),
                "medium_stress_min": int((p.get("stressMedium", 0) or 0) / 60),
                "low_stress_min": int((p.get("stressLow", 0) or 0) / 60),
                "rest_min": int((p.get("restStress", 0) or 0) / 60)
            })
        
        stress_values = [d["avg_stress"] for d in daily_data if d["avg_stress"] > 0]
        
        return {
            "days_analyzed": len(daily_data),
            "daily_stress": daily_data,
            "statistics": {
                "avg_stress": round(sum(stress_values)/len(stress_values), 0) if stress_values else 0,
                "max_stress": max(stress_values) if stress_values else 0,
                "min_stress": min(stress_values) if stress_values else 0
            },
            "interpretation": "Low stress levels" if sum(stress_values)/len(stress_values) < 30 else "Moderate stress" if sum(stress_values)/len(stress_values) < 50 else "High stress - consider relaxation" if stress_values else "No data"
        }
    
    def get_body_composition_trend(self, days: int = 30) -> Dict[str, Any]:
        """Get weight and body composition trends."""
        query = f"SELECT weight, bmi, bodyFatPercent, muscleMassPercent FROM BodyComposition ORDER BY time DESC LIMIT {days}"
        
        points = self._query(query)
        
        if not points:
            return {"message": "No body composition data found"}
        
        readings = []
        for p in points:
            readings.append({
                "date": p.get("time", "").split("T")[0],
                "weight_kg": round(p.get("weight", 0) or 0, 1),
                "bmi": round(p.get("bmi", 0) or 0, 1),
                "body_fat_pct": round(p.get("bodyFatPercent", 0) or 0, 1),
                "muscle_mass_pct": round(p.get("muscleMassPercent", 0) or 0, 1)
            })
        
        # Filter valid readings
        weights = [r["weight_kg"] for r in readings if r["weight_kg"] > 0]
        
        if not weights:
            return {"message": "No valid weight readings"}
        
        return {
            "readings": readings,
            "statistics": {
                "current_weight": weights[0] if weights else 0,
                "avg_weight": round(sum(weights)/len(weights), 1),
                "min_weight": min(weights),
                "max_weight": max(weights),
                "weight_change": round(weights[0] - weights[-1], 1) if len(weights) > 1 else 0
            },
            "trend": "losing" if weights[0] < weights[-1] else "gaining" if weights[0] > weights[-1] else "stable" if len(weights) > 1 else "insufficient data"
        }
    
    def get_heart_rate_trends(self, days: int = 14) -> Dict[str, Any]:
        """Analyze resting HR and HRV trends."""
        # Resting HR from sleep
        query = f"SELECT restingHeartRate, avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT {days}"
        
        points = self._query(query)
        
        if not points:
            return {"message": "No heart rate data found"}
        
        data = []
        for p in points:
            data.append({
                "date": p.get("time", "").split("T")[0],
                "resting_hr": int(p.get("restingHeartRate", 0) or 0),
                "hrv": int(p.get("avgOvernightHrv", 0) or 0)
            })
        
        rhr_values = [d["resting_hr"] for d in data if d["resting_hr"] > 0]
        hrv_values = [d["hrv"] for d in data if d["hrv"] > 0]
        
        return {
            "days_analyzed": len(data),
            "readings": data,
            "resting_hr": {
                "current": rhr_values[0] if rhr_values else 0,
                "average": round(sum(rhr_values)/len(rhr_values), 0) if rhr_values else 0,
                "min": min(rhr_values) if rhr_values else 0,
                "max": max(rhr_values) if rhr_values else 0,
                "trend": "improving" if rhr_values and rhr_values[0] < sum(rhr_values)/len(rhr_values) else "stable"
            },
            "hrv": {
                "current": hrv_values[0] if hrv_values else 0,
                "average": round(sum(hrv_values)/len(hrv_values), 0) if hrv_values else 0,
                "trend": "improving" if hrv_values and hrv_values[0] > sum(hrv_values)/len(hrv_values) else "stable"
            },
            "cardiovascular_health": "excellent" if rhr_values and sum(rhr_values)/len(rhr_values) < 55 else "good" if rhr_values and sum(rhr_values)/len(rhr_values) < 65 else "average"
        }
    
    def get_activity_overview(self, days: int = 7) -> Dict[str, Any]:
        """Get all activities, steps, calories, active time."""
        start = datetime.now() - timedelta(days=days)
        
        result: Dict[str, Any] = {"period_days": days}
        
        # Daily stats
        query = f"""
        SELECT totalSteps, totalDistanceMeters, activeCalories, highlyActiveSeconds, activeSeconds
        FROM DailyStats
        WHERE time >= '{start.isoformat()}Z'
        ORDER BY time DESC
        """
        points = self._query(query)
        if points:
            daily = []
            for p in points:
                daily.append({
                    "date": p.get("time", "").split("T")[0],
                    "steps": int(p.get("totalSteps", 0) or 0),
                    "distance_km": round((p.get("totalDistanceMeters", 0) or 0) / 1000, 2),
                    "active_calories": int(p.get("activeCalories", 0) or 0),
                    "active_time": format_duration((p.get("activeSeconds", 0) or 0) + (p.get("highlyActiveSeconds", 0) or 0))
                })
            
            steps = [d["steps"] for d in daily]
            result["daily_activity"] = daily
            result["totals"] = {
                "total_steps": sum(steps),
                "avg_steps": round(sum(steps)/len(steps), 0) if steps else 0,
                "total_distance_km": round(sum(d["distance_km"] for d in daily), 2),
                "total_active_calories": sum(d["active_calories"] for d in daily)
            }
        
        # Workouts
        query = f"""
        SELECT activityName, activityType, distance, movingDuration, calories
        FROM ActivitySummary
        WHERE time >= '{start.isoformat()}Z'
        ORDER BY time DESC
        """
        points = self._query(query)
        if points:
            workouts = []
            for p in points:
                workouts.append({
                    "name": p.get("activityName", "Activity"),
                    "type": p.get("activityType", "unknown"),
                    "date": p.get("time", "").split("T")[0],
                    "distance_km": round((p.get("distance", 0) or 0) / 1000, 2),
                    "duration": format_duration(p.get("movingDuration", 0) or 0),
                    "calories": int(p.get("calories", 0) or 0)
                })
            result["workouts"] = workouts
            result["workout_count"] = len(workouts)
        
        return result
    
    def get_wellness_score_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get fitness age, VO2 max, endurance score overview."""
        result: Dict[str, Any] = {}
        
        # Latest VO2 Max
        query = "SELECT vo2Max FROM DailyStats WHERE vo2Max > 0 ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            result["vo2max"] = round(points[0].get("vo2Max", 0), 1)
        
        # Fitness Age (if available)
        query = "SELECT fitnessAge FROM DailyStats WHERE fitnessAge > 0 ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            result["fitness_age"] = int(points[0].get("fitnessAge", 0))
        
        # Training Status
        query = "SELECT trainingStatus, trainingStatusDescription FROM DailyStats ORDER BY time DESC LIMIT 1"
        points = self._query(query)
        if points:
            result["training_status"] = {
                "status": points[0].get("trainingStatus", "Unknown"),
                "description": points[0].get("trainingStatusDescription", "")
            }
        
        # Average metrics over period
        start = datetime.now() - timedelta(days=days)
        query = f"""
        SELECT MEAN(vo2Max) as avg_vo2, MEAN(stressAvg) as avg_stress
        FROM DailyStats
        WHERE time >= '{start.isoformat()}Z'
        """
        points = self._query(query)
        if points:
            result["period_averages"] = {
                "avg_vo2max": round(points[0].get("avg_vo2", 0) or 0, 1),
                "avg_stress": round(points[0].get("avg_stress", 0) or 0, 0)
            }
        
        # Recent sleep quality
        query = f"SELECT MEAN(sleepScore) as avg_sleep FROM SleepSummary WHERE time >= '{start.isoformat()}Z'"
        points = self._query(query)
        if points:
            result["avg_sleep_score"] = round(points[0].get("avg_sleep", 0) or 0, 0)
        
        return result
    
    def compare_weeks(self, week1_ago: int = 0, week2_ago: int = 1) -> Dict[str, Any]:
        """Compare health metrics between two different weeks."""
        def get_week_data(weeks_ago: int) -> Dict:
            week_start = datetime.now() - timedelta(weeks=weeks_ago+1)
            week_end = datetime.now() - timedelta(weeks=weeks_ago)
            
            data: Dict[str, Any] = {"week_ending": week_end.strftime("%Y-%m-%d")}
            
            # Activity
            query = f"""
            SELECT SUM(distance) as dist, COUNT(distance) as cnt, SUM(calories) as cal
            FROM ActivitySummary
            WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
            AND activityType = 'running'
            """
            points = self._query(query)
            if points:
                data["running"] = {
                    "distance_km": round((points[0].get("dist", 0) or 0) / 1000, 2),
                    "run_count": int(points[0].get("cnt", 0) or 0),
                    "calories": int(points[0].get("cal", 0) or 0)
                }
            
            # Sleep
            query = f"""
            SELECT MEAN(sleepScore) as score, MEAN(deepSleepSeconds + lightSleepSeconds + remSleepSeconds) as duration
            FROM SleepSummary
            WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
            """
            points = self._query(query)
            if points:
                data["sleep"] = {
                    "avg_score": round(points[0].get("score", 0) or 0, 0),
                    "avg_hours": round((points[0].get("duration", 0) or 0) / 3600, 1)
                }
            
            # Steps and stress
            query = f"""
            SELECT MEAN(totalSteps) as steps, MEAN(stressAvg) as stress, MEAN(bodyBatteryAtWakeTime) as bb
            FROM DailyStats
            WHERE time >= '{week_start.isoformat()}Z' AND time < '{week_end.isoformat()}Z'
            """
            points = self._query(query)
            if points:
                data["daily"] = {
                    "avg_steps": round(points[0].get("steps", 0) or 0, 0),
                    "avg_stress": round(points[0].get("stress", 0) or 0, 0),
                    "avg_body_battery": round(points[0].get("bb", 0) or 0, 0)
                }
            
            return data
        
        week1_data = get_week_data(week1_ago)
        week2_data = get_week_data(week2_ago)
        
        # Calculate differences
        comparison = {
            "week1": week1_data,
            "week2": week2_data,
            "changes": {}
        }
        
        if "running" in week1_data and "running" in week2_data:
            km1 = week1_data["running"]["distance_km"]
            km2 = week2_data["running"]["distance_km"]
            comparison["changes"]["running_km"] = {
                "difference": round(km1 - km2, 2),
                "percent_change": round((km1 - km2) / km2 * 100, 1) if km2 > 0 else 0
            }
        
        if "sleep" in week1_data and "sleep" in week2_data:
            s1 = week1_data["sleep"]["avg_score"]
            s2 = week2_data["sleep"]["avg_score"]
            comparison["changes"]["sleep_score"] = {
                "difference": round(s1 - s2, 0),
                "trend": "improved" if s1 > s2 else "declined" if s1 < s2 else "stable"
            }
        
        return comparison

    # =========================================================================
    # RAW DATABASE ACCESS
    # =========================================================================
    
    def query_influxdb(self, query: str) -> Dict[str, Any]:
        """Execute any InfluxQL query directly."""
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            return {
                "query": query,
                "results": points[:100],  # Limit to 100 results
                "count": len(points),
                "truncated": len(points) > 100
            }
        except Exception as e:
            return {"error": str(e), "query": query}
    
    def list_databases(self) -> Dict[str, Any]:
        """List all databases in InfluxDB."""
        try:
            result = self.client.get_list_database()
            return {"databases": [db["name"] for db in result]}
        except Exception as e:
            return {"error": str(e)}
    
    def list_measurements(self, database: Optional[str] = None) -> Dict[str, Any]:
        """List all measurements in a database."""
        db = database or self.database
        try:
            result = self.client.query(f"SHOW MEASUREMENTS ON {db}")
            measurements = [m["name"] for m in result.get_points()]
            return {"database": db, "measurements": measurements}
        except Exception as e:
            return {"error": str(e)}
    
    def show_field_keys(self, measurement: str) -> Dict[str, Any]:
        """Show field keys for a measurement."""
        try:
            result = self.client.query(f"SHOW FIELD KEYS FROM {measurement}")
            fields = [{"field": f["fieldKey"], "type": f["fieldType"]} for f in result.get_points()]
            return {"measurement": measurement, "fields": fields}
        except Exception as e:
            return {"error": str(e)}
    
    def show_tag_keys(self, measurement: str) -> Dict[str, Any]:
        """Show tag keys for a measurement."""
        try:
            result = self.client.query(f"SHOW TAG KEYS FROM {measurement}")
            tags = [t["tagKey"] for t in result.get_points()]
            return {"measurement": measurement, "tags": tags}
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # MCP INTERFACE
    # =========================================================================
    
    def get_tools(self) -> list[Tool]:
        """Define available MCP tools."""
        return [
            # Running & Training Analysis
            Tool(
                name="get_recent_runs",
                description="Get recent running activities with pace, HR, distance, duration",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of runs to return (default: 10)"},
                        "days": {"type": "integer", "description": "Look back period in days (default: 30)"}
                    }
                }
            ),
            Tool(
                name="get_training_load",
                description="Analyze weekly mileage, total time, and training intensity",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "integer", "description": "Number of weeks to analyze (default: 4)"}
                    }
                }
            ),
            Tool(
                name="get_pace_analysis",
                description="Track pace trends, best pace, and consistency",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 30)"}
                    }
                }
            ),
            Tool(
                name="get_vo2max_progress",
                description="Track VO2 Max cardiovascular fitness over time",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "months": {"type": "integer", "description": "Number of months to analyze (default: 6)"}
                    }
                }
            ),
            Tool(
                name="get_race_predictions",
                description="Get predicted finish times for 5K, 10K, half marathon, marathon",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_training_status",
                description="Current training load, training effect, recovery time recommendations",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_heart_rate_zones",
                description="Analyze time spent in different HR zones",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 30)"}
                    }
                }
            ),
            Tool(
                name="get_long_runs",
                description="Get runs over a specified distance threshold",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "min_distance_km": {"type": "number", "description": "Minimum distance in km (default: 15)"},
                        "months": {"type": "integer", "description": "Look back period in months (default: 3)"}
                    }
                }
            ),
            
            # Sleep & Recovery
            Tool(
                name="get_sleep_analysis",
                description="Sleep quality, duration, stages (deep/light/REM), HRV, SpO2",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 7)"}
                    }
                }
            ),
            Tool(
                name="get_recovery_metrics",
                description="Body battery, sleep quality, stress, HRV recovery indicators",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 7)"}
                    }
                }
            ),
            Tool(
                name="get_recovery_status",
                description="Training readiness, body battery patterns, HRV trends, recommendations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 7)"}
                    }
                }
            ),
            Tool(
                name="get_hrv_analysis",
                description="Heart rate variability patterns for recovery assessment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 14)"}
                    }
                }
            ),
            
            # Health & Wellness
            Tool(
                name="get_weekly_health_digest",
                description="Comprehensive weekly overview: activity, sleep, stress, recovery",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "weeks_ago": {"type": "integer", "description": "0 = current week, 1 = last week, etc."}
                    }
                }
            ),
            Tool(
                name="get_stress_patterns",
                description="Stress patterns throughout day/week",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 7)"}
                    }
                }
            ),
            Tool(
                name="get_body_composition_trend",
                description="Weight, BMI, body fat %, muscle mass trends",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 30)"}
                    }
                }
            ),
            Tool(
                name="get_heart_rate_trends",
                description="Resting HR, HRV, cardiovascular health patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 14)"}
                    }
                }
            ),
            Tool(
                name="get_activity_overview",
                description="All activities, steps, calories, active time",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to analyze (default: 7)"}
                    }
                }
            ),
            Tool(
                name="get_wellness_score_summary",
                description="Fitness age, VO2 max, endurance score overview",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days for averages (default: 30)"}
                    }
                }
            ),
            Tool(
                name="compare_weeks",
                description="Compare health metrics between two different weeks",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "week1_ago": {"type": "integer", "description": "First week (0 = current, 1 = last week)"},
                        "week2_ago": {"type": "integer", "description": "Second week to compare against"}
                    }
                }
            ),
            
            # Raw Database Access
            Tool(
                name="query_influxdb",
                description="Execute any InfluxQL query directly",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "InfluxQL query to execute"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="list_databases",
                description="List all databases in InfluxDB",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="list_measurements",
                description="List all measurements in a database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name (default: current database)"}
                    }
                }
            ),
            Tool(
                name="show_field_keys",
                description="Show field keys for a measurement",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "measurement": {"type": "string", "description": "Measurement name"}
                    },
                    "required": ["measurement"]
                }
            ),
            Tool(
                name="show_tag_keys",
                description="Show tag keys for a measurement",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "measurement": {"type": "string", "description": "Measurement name"}
                    },
                    "required": ["measurement"]
                }
            )
        ]
    
    def handle_tool_call(self, tool_name: str, arguments: dict) -> str:
        """Handle MCP tool calls."""
        try:
            # Running & Training Analysis
            if tool_name == "get_recent_runs":
                result = self.get_recent_runs(
                    limit=arguments.get("limit", 10),
                    days=arguments.get("days", 30)
                )
            elif tool_name == "get_training_load":
                result = self.get_training_load(arguments.get("weeks", 4))
            elif tool_name == "get_pace_analysis":
                result = self.get_pace_analysis(arguments.get("days", 30))
            elif tool_name == "get_vo2max_progress":
                result = self.get_vo2max_progress(arguments.get("months", 6))
            elif tool_name == "get_race_predictions":
                result = self.get_race_predictions()
            elif tool_name == "get_training_status":
                result = self.get_training_status()
            elif tool_name == "get_heart_rate_zones":
                result = self.get_heart_rate_zones(arguments.get("days", 30))
            elif tool_name == "get_long_runs":
                result = self.get_long_runs(
                    min_distance_km=arguments.get("min_distance_km", 15),
                    months=arguments.get("months", 3)
                )
            
            # Sleep & Recovery
            elif tool_name == "get_sleep_analysis":
                result = self.get_sleep_analysis(arguments.get("days", 7))
            elif tool_name == "get_recovery_metrics":
                result = self.get_recovery_metrics(arguments.get("days", 7))
            elif tool_name == "get_recovery_status":
                result = self.get_recovery_status(arguments.get("days", 7))
            elif tool_name == "get_hrv_analysis":
                result = self.get_hrv_analysis(arguments.get("days", 14))
            
            # Health & Wellness
            elif tool_name == "get_weekly_health_digest":
                result = self.get_weekly_health_digest(arguments.get("weeks_ago", 0))
            elif tool_name == "get_stress_patterns":
                result = self.get_stress_patterns(arguments.get("days", 7))
            elif tool_name == "get_body_composition_trend":
                result = self.get_body_composition_trend(arguments.get("days", 30))
            elif tool_name == "get_heart_rate_trends":
                result = self.get_heart_rate_trends(arguments.get("days", 14))
            elif tool_name == "get_activity_overview":
                result = self.get_activity_overview(arguments.get("days", 7))
            elif tool_name == "get_wellness_score_summary":
                result = self.get_wellness_score_summary(arguments.get("days", 30))
            elif tool_name == "compare_weeks":
                result = self.compare_weeks(
                    week1_ago=arguments.get("week1_ago", 0),
                    week2_ago=arguments.get("week2_ago", 1)
                )
            
            # Raw Database Access
            elif tool_name == "query_influxdb":
                result = self.query_influxdb(arguments.get("query", ""))
            elif tool_name == "list_databases":
                result = self.list_databases()
            elif tool_name == "list_measurements":
                result = self.list_measurements(arguments.get("database"))
            elif tool_name == "show_field_keys":
                result = self.show_field_keys(arguments.get("measurement", ""))
            elif tool_name == "show_tag_keys":
                result = self.show_tag_keys(arguments.get("measurement", ""))
            
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


# Initialize the MCP server
def create_influxdb_mcp(config: dict) -> InfluxDBHealthMCP:
    """Create InfluxDB MCP instance."""
    return InfluxDBHealthMCP(
        host=config.get("host", "localhost"),
        port=config.get("port", 8086),
        username=config.get("username", ""),
        password=config.get("password", ""),
        database=config.get("database", "health")
    )
