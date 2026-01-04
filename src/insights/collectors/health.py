"""
Friday Insights Engine - Health Collector

Collects health data from Garmin via InfluxDB.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from src.core.config import get_brt
from src.core.influxdb import get_influx_client, query as influx_query
from src.insights.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class HealthCollector(BaseCollector):
    """
    Collects health metrics from Garmin data stored in InfluxDB.
    
    Data collected:
    - Current stress level
    - Body battery
    - Heart rate
    - Sleep data (most recent)
    - Training readiness
    - Sync status
    """
    
    def __init__(self):
        super().__init__("health")
    
    def initialize(self) -> bool:
        """Connect to InfluxDB via shared client."""
        client = get_influx_client()
        if client:
            self._initialized = True
            logger.info("[HEALTH_COLLECTOR] Initialized with shared InfluxDB client")
            return True
        logger.error("[HEALTH_COLLECTOR] Failed to get InfluxDB client")
        return False
    
    def _query(self, query_str: str) -> List[Dict]:
        """Execute InfluxDB query via shared client."""
        return influx_query(query_str)
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect current health metrics."""
        if not self._initialized:
            if not self.initialize():
                return None
        
        now = datetime.now(get_brt())
        today_str = now.strftime("%Y-%m-%d")
        
        data = {
            "collected_at": now.isoformat(),
            "sync_status": self._get_sync_status(),
            "stress": self._get_stress(),
            "body_battery": self._get_body_battery(),
            "heart_rate": self._get_heart_rate(),
            "sleep": self._get_sleep(),
            "training_readiness": self._get_training_readiness(),
            "daily_stats": self._get_daily_stats(today_str),
        }
        
        return data
    
    def _get_sync_status(self) -> Dict[str, Any]:
        """Check Garmin sync freshness."""
        points = self._query('SELECT last("HeartRate") FROM "HeartRateIntraday"')
        
        if not points:
            return {"status": "unknown", "hours_ago": None}
        
        last_time_str = points[0].get("time", "")
        if not last_time_str:
            return {"status": "unknown", "hours_ago": None}
        
        try:
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            hours_ago = (now_utc - last_time).total_seconds() / 3600
            
            if hours_ago < 1:
                status = "current"
            elif hours_ago < 6:
                status = "recent"
            elif hours_ago < 12:
                status = "stale"
            else:
                status = "very_stale"
            
            return {
                "status": status,
                "hours_ago": round(hours_ago, 1),
                "last_sync": last_time.isoformat(),
            }
        except Exception:
            return {"status": "error", "hours_ago": None}
    
    def _get_stress(self) -> Dict[str, Any]:
        """Get current and daily stress."""
        # Current stress
        current = self._query("SELECT last(stressLevel) FROM StressIntraday")
        current_stress = int(current[0].get("last", 0)) if current else 0
        
        # Daily average
        today = datetime.now(get_brt()).strftime("%Y-%m-%dT00:00:00Z")
        daily = self._query(f"""
            SELECT stressAvg, highStressDuration, restStressDuration 
            FROM DailyStats WHERE time >= '{today}' 
            ORDER BY time DESC LIMIT 1
        """)
        
        if daily:
            return {
                "current": current_stress,
                "daily_avg": int(daily[0].get("stressAvg", 0) or 0),
                "high_stress_minutes": int((daily[0].get("highStressDuration", 0) or 0) / 60),
                "rest_minutes": int((daily[0].get("restStressDuration", 0) or 0) / 60),
            }
        
        return {"current": current_stress, "daily_avg": 0}
    
    def _get_body_battery(self) -> Dict[str, Any]:
        """Get current body battery."""
        current = self._query('SELECT last("BodyBatteryLevel") FROM "BodyBatteryIntraday"')
        
        if current:
            return {
                "current": int(current[0].get("last", 0) or 0),
                "time": current[0].get("time", ""),
            }
        return {"current": 0}
    
    def _get_heart_rate(self) -> Dict[str, Any]:
        """Get current heart rate."""
        current = self._query('SELECT last("HeartRate") FROM "HeartRateIntraday"')
        
        if current:
            return {
                "current": int(current[0].get("last", 0) or 0),
                "time": current[0].get("time", ""),
            }
        return {"current": 0}
    
    def _get_sleep(self) -> Dict[str, Any]:
        """Get most recent sleep data."""
        points = self._query("""
            SELECT sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds,
                   avgOvernightHrv, restingHeartRate
            FROM SleepSummary ORDER BY time DESC LIMIT 1
        """)
        
        if not points:
            return {}
        
        p = points[0]
        deep = p.get("deepSleepSeconds", 0) or 0
        light = p.get("lightSleepSeconds", 0) or 0
        rem = p.get("remSleepSeconds", 0) or 0
        
        return {
            "date": p.get("time", "").split("T")[0],
            "score": int(p.get("sleepScore", 0) or 0),
            "total_hours": round((deep + light + rem) / 3600, 1),
            "deep_minutes": int(deep / 60),
            "rem_minutes": int(rem / 60),
            "hrv": int(p.get("avgOvernightHrv", 0) or 0),
            "rhr": int(p.get("restingHeartRate", 0) or 0),
        }
    
    def _get_training_readiness(self) -> Dict[str, Any]:
        """Get training readiness."""
        points = self._query("SELECT score, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1")
        
        if points:
            return {
                "score": int(points[0].get("score", 0) or 0),
                "level": points[0].get("level", ""),
            }
        return {}
    
    def _get_daily_stats(self, date: str) -> Dict[str, Any]:
        """Get daily activity stats."""
        points = self._query(f"""
            SELECT totalSteps, totalDistanceMeters, activeMinutes, 
                   bodyBatteryAtWakeTime
            FROM DailyStats WHERE time >= '{date}T00:00:00Z'
            ORDER BY time DESC LIMIT 1
        """)
        
        if points:
            p = points[0]
            return {
                "steps": int(p.get("totalSteps", 0) or 0),
                "distance_km": round((p.get("totalDistanceMeters", 0) or 0) / 1000, 1),
                "active_minutes": int(p.get("activeMinutes", 0) or 0),
                "wake_body_battery": int(p.get("bodyBatteryAtWakeTime", 0) or 0),
            }
        return {}
