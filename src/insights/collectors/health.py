"""
Friday Insights Engine - Health Collector

Collects health data from Garmin via InfluxDB.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.insights.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Brazil timezone
BRT = timezone(timedelta(hours=-3))


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
        self._client = None
    
    def initialize(self) -> bool:
        """Connect to InfluxDB."""
        try:
            from influxdb import InfluxDBClient
            
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "influxdb_mcp.json"
            if not config_path.exists():
                logger.error(f"InfluxDB config not found: {config_path}")
                return False
            
            with open(config_path) as f:
                config = json.load(f)
            
            self._client = InfluxDBClient(
                host=config.get("host", "localhost"),
                port=config.get("port", 8086),
                username=config.get("username", ""),
                password=config.get("password", ""),
                database=config.get("database", "health")
            )
            self._client.ping()
            logger.info("HealthCollector connected to InfluxDB")
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"HealthCollector init failed: {e}")
            return False
    
    def _query(self, query: str) -> List[Dict]:
        """Execute InfluxDB query."""
        if not self._client:
            return []
        try:
            result = self._client.query(query)
            return list(result.get_points())
        except Exception as e:
            logger.error(f"InfluxDB query error: {e}")
            return []
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect current health metrics."""
        if not self._client:
            if not self.initialize():
                return None
        
        now = datetime.now(BRT)
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
        today = datetime.now(BRT).strftime("%Y-%m-%dT00:00:00Z")
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
