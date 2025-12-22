"""
Friday 3.0 Awareness Daemon

Background monitoring service that polls sensors and sends alerts to friday-core.
This is the "autonomic nervous system" - runs independently of user interaction.

Usage:
    python -m src.awareness

Features:
    - Polls @friday_sensor functions on defined intervals
    - Evaluates sensor data against config thresholds
    - Sends alerts to friday-core /alert endpoint
    - Cooldown system to prevent alert spam
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import get_config
from src.core.loader import load_extensions
from src.core.registry import get_sensor_registry, SensorEntry

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Brazil timezone (UTC-3)
from datetime import timezone
BRT = timezone(timedelta(hours=-3))


# =============================================================================
# Configuration
# =============================================================================

def get_api_config() -> dict:
    """Get API configuration from environment."""
    return {
        "api_url": os.getenv("FRIDAY_API_URL", "http://localhost:8080"),
        "api_key": os.getenv("FRIDAY_API_KEY", ""),
    }


API_CONFIG = get_api_config()


# =============================================================================
# Alert Cooldowns
# =============================================================================

class CooldownManager:
    """Manages alert cooldowns to prevent spam.
    
    Features:
    - Basic cooldown: Don't repeat the same alert within X minutes
    - Escalating cooldown: For persistent conditions, increase cooldown each time
    - Daily limits: Max alerts per sensor per day
    - State tracking: Only re-alert if condition changes (gets worse)
    """
    
    # Default cooldowns by alert level
    DEFAULT_COOLDOWNS = {
        "info": 60,       # 1 hour
        "warning": 120,   # 2 hours (was 30 min - too spammy)
        "critical": 30,   # 30 minutes (critical can repeat more often)
    }
    
    # Max alerts per sensor per day
    DAILY_LIMIT = 3
    
    def __init__(self, cooldown_file: Optional[Path] = None):
        """Initialize cooldown manager.
        
        Args:
            cooldown_file: Path to persist cooldowns (optional)
        """
        self.cooldown_file = cooldown_file
        self._cooldowns: Dict[str, datetime] = {}
        self._alert_counts: Dict[str, Dict[str, int]] = {}  # {date: {sensor: count}}
        self._last_values: Dict[str, Any] = {}  # Track last alert values
        self._load_cooldowns()
    
    def _load_cooldowns(self):
        """Load cooldowns from file if exists."""
        if self.cooldown_file and self.cooldown_file.exists():
            try:
                data = json.loads(self.cooldown_file.read_text())
                self._cooldowns = {
                    k: datetime.fromisoformat(v) 
                    for k, v in data.get("cooldowns", data).items()  # Backward compat
                    if isinstance(v, str)
                }
                self._alert_counts = data.get("daily_counts", {})
                self._last_values = data.get("last_values", {})
            except Exception as e:
                logger.warning(f"Failed to load cooldowns: {e}")
    
    def _save_cooldowns(self):
        """Save cooldowns to file."""
        if self.cooldown_file:
            try:
                data = {
                    "cooldowns": {k: v.isoformat() for k, v in self._cooldowns.items()},
                    "daily_counts": self._alert_counts,
                    "last_values": self._last_values,
                }
                self.cooldown_file.write_text(json.dumps(data, indent=2))
            except Exception as e:
                logger.warning(f"Failed to save cooldowns: {e}")
    
    def _get_today(self) -> str:
        """Get today's date as string."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_daily_count(self, sensor: str) -> int:
        """Get today's alert count for a sensor."""
        today = self._get_today()
        if today not in self._alert_counts:
            self._alert_counts[today] = {}
            # Clean up old dates
            old_dates = [d for d in self._alert_counts if d < today]
            for d in old_dates:
                del self._alert_counts[d]
        return self._alert_counts.get(today, {}).get(sensor, 0)
    
    def _increment_daily_count(self, sensor: str):
        """Increment today's alert count for a sensor."""
        today = self._get_today()
        if today not in self._alert_counts:
            self._alert_counts[today] = {}
        self._alert_counts[today][sensor] = self._alert_counts[today].get(sensor, 0) + 1
    
    def can_alert(self, key: str, cooldown_minutes: int = 30, sensor: str = None, level: str = "warning") -> bool:
        """Check if an alert can be sent (not in cooldown, under daily limit).
        
        Args:
            key: Unique key for this alert type (e.g., "disk_usage_critical")
            cooldown_minutes: Minimum minutes between alerts (overridden by defaults)
            sensor: Sensor name for daily limit tracking
            level: Alert level for default cooldown lookup
            
        Returns:
            True if alert can be sent, False if blocked
        """
        now = datetime.now()
        
        # Check cooldown
        if key in self._cooldowns:
            cooldown_until = self._cooldowns[key]
            if now < cooldown_until:
                return False
        
        # Check daily limit
        if sensor:
            daily_count = self._get_daily_count(sensor)
            if daily_count >= self.DAILY_LIMIT:
                logger.debug(f"Daily limit reached for {sensor} ({daily_count}/{self.DAILY_LIMIT})")
                return False
        
        return True
    
    def should_alert_on_change(self, sensor: str, current_value: Any, threshold_key: str = None) -> bool:
        """Check if we should alert based on value change.
        
        Only alerts if:
        - First time seeing this sensor
        - Value has gotten worse (higher stress, lower battery, etc.)
        
        Args:
            sensor: Sensor name
            current_value: Current metric value
            threshold_key: Optional key for the specific threshold being checked
            
        Returns:
            True if alert should fire based on change
        """
        key = f"{sensor}_{threshold_key}" if threshold_key else sensor
        last_value = self._last_values.get(key)
        
        if last_value is None:
            return True  # First time, allow alert
        
        # For numeric values, check if it got worse
        if isinstance(current_value, (int, float)) and isinstance(last_value, (int, float)):
            # Define "worse" direction per sensor type
            worse_is_higher = sensor in ("stress_level", "disk_usage", "memory_usage", "cpu_load", "gpu_temperature")
            
            if worse_is_higher:
                return current_value > last_value  # Alert if higher
            else:
                return current_value < last_value  # Alert if lower (battery, sleep score, etc.)
        
        return True  # Non-numeric, allow
    
    def mark_alerted(self, key: str, cooldown_minutes: int = None, sensor: str = None, level: str = "warning", value: Any = None):
        """Mark that an alert was sent.
        
        Args:
            key: Unique key for this alert type
            cooldown_minutes: Minutes until next alert allowed (None = use default)
            sensor: Sensor name for daily limit tracking
            level: Alert level for default cooldown
            value: The value that triggered this alert (for change tracking)
        """
        # Use default cooldown based on level if not specified
        if cooldown_minutes is None:
            cooldown_minutes = self.DEFAULT_COOLDOWNS.get(level, 120)
        
        self._cooldowns[key] = datetime.now() + timedelta(minutes=cooldown_minutes)
        
        if sensor:
            self._increment_daily_count(sensor)
        
        if value is not None:
            self._last_values[key] = value
        
        self._save_cooldowns()
    
    def clear(self, key: Optional[str] = None):
        """Clear cooldown(s).
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            self._cooldowns.pop(key, None)
            self._last_values.pop(key, None)
        else:
            self._cooldowns.clear()
            self._last_values.clear()
        self._save_cooldowns()


# =============================================================================
# Schedule Runner
# =============================================================================

class ScheduleRunner:
    """Runs tools at scheduled times (e.g., morning/evening reports).
    
    Reads schedules from config/schedules.json and executes tools at specified times.
    """
    
    def __init__(self, schedules_file: Optional[Path] = None, state_file: Optional[Path] = None):
        """Initialize schedule runner.
        
        Args:
            schedules_file: Path to schedules.json config
            state_file: Path to persist last run times
        """
        self.schedules_file = schedules_file or Path(__file__).parent.parent / "config" / "schedules.json"
        self.state_file = state_file or Path(__file__).parent.parent / "data" / "schedule_state.json"
        self._schedules = []
        self._last_runs: Dict[str, str] = {}  # {schedule_name: "YYYY-MM-DD"}
        self._load_schedules()
        self._load_state()
    
    def _load_schedules(self):
        """Load schedules from config file."""
        if self.schedules_file.exists():
            try:
                data = json.loads(self.schedules_file.read_text())
                self._schedules = data.get("schedules", [])
                logger.info(f"Loaded {len(self._schedules)} schedules")
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")
    
    def _load_state(self):
        """Load last run state from file."""
        if self.state_file.exists():
            try:
                self._last_runs = json.loads(self.state_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load schedule state: {e}")
    
    def _save_state(self):
        """Save last run state to file."""
        try:
            self.state_file.write_text(json.dumps(self._last_runs, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save schedule state: {e}")
    
    def _parse_time(self, time_str: str) -> tuple:
        """Parse time string (HH:MM) to (hour, minute)."""
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    
    def _should_run(self, schedule: dict) -> bool:
        """Check if a schedule should run now.
        
        Returns True if:
        - Schedule is enabled
        - Current time has passed the scheduled time
        - Haven't run today yet
        """
        if not schedule.get("enabled", True):
            return False
        
        name = schedule.get("name", "")
        time_str = schedule.get("time", "")
        
        if not time_str:
            return False
        
        now = datetime.now(BRT)
        today_str = now.strftime("%Y-%m-%d")
        
        # Check if already ran today
        last_run_date = self._last_runs.get(name, "")
        if last_run_date == today_str:
            return False
        
        # Check if we've passed the scheduled time
        sched_hour, sched_min = self._parse_time(time_str)
        
        # If current time is past scheduled time, run it
        if now.hour > sched_hour or (now.hour == sched_hour and now.minute >= sched_min):
            return True
        
        return False
    
    async def run_schedule(self, schedule: dict) -> Optional[str]:
        """Execute a scheduled task.
        
        Args:
            schedule: Schedule config dict
            
        Returns:
            Tool output if successful, None otherwise
        """
        name = schedule.get("name", "unknown")
        tool_name = schedule.get("tool", "")
        
        if not tool_name:
            logger.error(f"Schedule {name} has no tool defined")
            return None
        
        logger.info(f"Running scheduled task: {name} (tool: {tool_name})")
        
        try:
            # Import and get the tool from registry
            from src.core.registry import get_tool_registry
            from src.core.loader import load_extensions
            
            # Ensure extensions are loaded
            load_extensions()
            
            registry = get_tool_registry()
            tool_entry = registry.get(tool_name)
            
            if not tool_entry:
                logger.error(f"Tool not found: {tool_name}")
                return None
            
            # Execute the tool
            result = tool_entry.func()
            
            # Mark as run
            today_str = datetime.now(BRT).strftime("%Y-%m-%d")
            self._last_runs[name] = today_str
            self._save_state()
            
            return result
            
        except Exception as e:
            logger.error(f"Error running scheduled task {name}: {e}")
            return None
    
    async def check_and_run(self) -> List[tuple]:
        """Check all schedules and run any that are due.
        
        Returns:
            List of (schedule_name, result) tuples for schedules that ran
        """
        results = []
        
        for schedule in self._schedules:
            if self._should_run(schedule):
                result = await self.run_schedule(schedule)
                if result:
                    results.append((schedule.get("name", ""), result))
        
        return results


# =============================================================================
# Alert Sender
# =============================================================================

async def send_alert(
    sensor: str,
    message: str,
    level: str = "info",
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """Send alert to friday-core.
    
    Args:
        sensor: Name of the sensor that triggered the alert
        message: Alert message
        level: Alert level (info/warning/critical)
        data: Additional data
        
    Returns:
        True if alert was sent successfully
    """
    headers = {"Content-Type": "application/json"}
    if API_CONFIG["api_key"]:
        headers["Authorization"] = f"Bearer {API_CONFIG['api_key']}"
    
    payload = {
        "sensor": sensor,
        "message": message,
        "level": level,
        "data": data or {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_CONFIG['api_url']}/alert",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Alert sent: [{level}] {sensor} - {message}")
            return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


# =============================================================================
# Threshold Evaluation
# =============================================================================

class ThresholdEvaluator:
    """Evaluates sensor data against configured thresholds."""
    
    def __init__(self, config: dict):
        """Initialize with config thresholds.
        
        Args:
            config: Configuration dict with threshold values
        """
        # Hardware thresholds
        self.thresholds = {
            "disk_percent": config.get("disk_threshold_percent", 90),
            "memory_percent": config.get("memory_threshold_percent", 90),
            "cpu_load": config.get("cpu_load_threshold", 8.0),
            "gpu_temp": config.get("gpu_temp_threshold", 80),
        }
        
        # Health thresholds
        self.health_thresholds = {
            "sleep_score_warning": 65,      # Alert if sleep score below this
            "sleep_score_critical": 50,     # Critical if below this
            "sleep_hours_min": 6.0,         # Alert if less than 6 hours
            "body_battery_warning": 40,     # Alert if body battery below this
            "body_battery_critical": 25,    # Critical if below this
            "training_readiness_warning": 50,  # Alert if readiness below this
            "recovery_status_alert": ["poor"],  # Alert on these statuses
            "hrv_deviation_warning": -20,   # Alert if HRV drops more than 20%
            "stress_avg_warning": 50,       # Alert if average stress above this
            "stress_avg_critical": 65,      # Critical if above this
            "stress_high_minutes_warning": 120,  # Alert if >2 hours high stress
        }
    
    def evaluate(self, sensor_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate sensor data and return alert info if threshold exceeded.
        
        Args:
            sensor_name: Name of the sensor
            data: Sensor reading data
            
        Returns:
            Alert dict with level and message, or None if OK
        """
        if "error" in data:
            # Don't alert on health sensor errors (might just be no data yet)
            if sensor_name in ("sleep_quality", "training_readiness", "body_battery", "recovery_status"):
                return None
            return {
                "level": "warning",
                "message": f"Sensor error: {data['error']}"
            }
        
        # =====================================================================
        # Hardware Sensors
        # =====================================================================
        
        # Disk usage
        if sensor_name == "disk_usage":
            percent = data.get("percent_used", 0)
            threshold = self.thresholds["disk_percent"]
            if percent >= threshold:
                return {
                    "level": "critical" if percent >= 95 else "warning",
                    "message": f"Disk usage at {percent}% (threshold: {threshold}%)"
                }
        
        # Memory usage
        elif sensor_name == "memory_usage":
            percent = data.get("percent_used", 0)
            threshold = self.thresholds["memory_percent"]
            if percent >= threshold:
                return {
                    "level": "critical" if percent >= 95 else "warning",
                    "message": f"Memory usage at {percent}% (threshold: {threshold}%)"
                }
        
        # CPU load
        elif sensor_name == "cpu_load":
            load_5min = data.get("load_5min", 0)
            threshold = self.thresholds["cpu_load"]
            if load_5min >= threshold:
                return {
                    "level": "warning",
                    "message": f"CPU load at {load_5min} (threshold: {threshold})"
                }
        
        # GPU temperature
        elif sensor_name == "gpu_temperature":
            temp = data.get("temperature_celsius", 0)
            threshold = self.thresholds["gpu_temp"]
            if temp >= threshold:
                return {
                    "level": "critical" if temp >= 90 else "warning",
                    "message": f"GPU temperature at {temp}C (threshold: {threshold}C)"
                }
        
        # =====================================================================
        # Health Sensors
        # =====================================================================
        
        # Sleep quality
        elif sensor_name == "sleep_quality":
            score = data.get("sleep_score", 0)
            hours = data.get("total_hours", 0)
            
            # Check sleep score
            if score > 0 and score < self.health_thresholds["sleep_score_critical"]:
                return {
                    "level": "critical",
                    "message": f"Poor sleep quality! Score: {score}/100, Duration: {hours}h"
                }
            elif score > 0 and score < self.health_thresholds["sleep_score_warning"]:
                return {
                    "level": "warning",
                    "message": f"Below average sleep. Score: {score}/100, Duration: {hours}h"
                }
            
            # Check sleep duration
            if hours > 0 and hours < self.health_thresholds["sleep_hours_min"]:
                return {
                    "level": "warning",
                    "message": f"Short sleep duration: {hours}h (recommended: 7-9h)"
                }
        
        # Body battery
        elif sensor_name == "body_battery":
            battery = data.get("body_battery", 0)
            
            if battery > 0 and battery < self.health_thresholds["body_battery_critical"]:
                return {
                    "level": "critical",
                    "message": f"Very low energy! Body battery: {battery}/100. Consider rest."
                }
            elif battery > 0 and battery < self.health_thresholds["body_battery_warning"]:
                return {
                    "level": "warning",
                    "message": f"Low energy. Body battery: {battery}/100"
                }
        
        # Training readiness
        elif sensor_name == "training_readiness":
            score = data.get("score", 0)
            level = data.get("level", "")
            recovery_hours = data.get("recovery_hours", 0)
            
            if score > 0 and score < self.health_thresholds["training_readiness_warning"]:
                return {
                    "level": "warning",
                    "message": f"Low training readiness: {score}/100 ({level}). Recovery needed: {recovery_hours}h"
                }
        
        # Recovery status (composite)
        elif sensor_name == "recovery_status":
            status = data.get("status", "")
            hrv_deviation = data.get("hrv_deviation_percent", 0)
            
            if status in self.health_thresholds["recovery_status_alert"]:
                hrv = data.get("hrv", 0)
                rhr = data.get("resting_hr", 0)
                return {
                    "level": "warning",
                    "message": f"Poor recovery detected! HRV: {hrv}ms ({hrv_deviation:+.0f}% from baseline), RHR: {rhr}bpm"
                }
            
            # Also alert on significant HRV drop even if overall status is OK
            if hrv_deviation < self.health_thresholds["hrv_deviation_warning"]:
                return {
                    "level": "warning", 
                    "message": f"Significant HRV drop: {hrv_deviation:.0f}% below your baseline. Consider taking it easy."
                }
        
        # Stress level
        elif sensor_name == "stress_level":
            current = data.get("current_stress", 0)
            stress_avg = data.get("stress_avg", 0)
            high_stress_min = data.get("high_stress_minutes", 0)
            
            # Check current stress level first (more immediate)
            if current >= self.health_thresholds["stress_avg_critical"]:
                return {
                    "level": "critical",
                    "message": f"Very high stress right now! Current: {current}/100. Take a break!"
                }
            elif current >= self.health_thresholds["stress_avg_warning"]:
                return {
                    "level": "warning",
                    "message": f"Elevated stress detected. Current: {current}/100, Daily avg: {stress_avg}"
                }
            
            # Alert on prolonged high stress regardless of current level
            if high_stress_min >= self.health_thresholds["stress_high_minutes_warning"]:
                return {
                    "level": "warning",
                    "message": f"Prolonged high stress today: {high_stress_min} minutes. Consider relaxation."
                }
        
        # =====================================================================
        # Weather Sensors
        # =====================================================================
        
        elif sensor_name == "weather_forecast":
            rain_expected = data.get("rain_expected", False)
            rain_prob = data.get("rain_probability", 0)
            rain_time = data.get("rain_time", "")
            rain_desc = data.get("rain_description", "rain")
            city = data.get("city", "your area")
            
            # Alert if rain is expected with >20% probability
            if rain_expected and rain_prob > 0.2:
                prob_pct = int(rain_prob * 100)
                return {
                    "level": "warning",  # Use warning so it gets sent to Telegram
                    "message": f"🌧️ Rain expected in {city} around {rain_time} ({prob_pct}% chance - {rain_desc}). Consider taking an umbrella!"
                }
        
        # =====================================================================
        # Calendar - Upcoming Events
        # =====================================================================
        
        elif sensor_name == "upcoming_events":
            events_soon = data.get("events_soon", [])
            
            if events_soon:
                alerts = []
                for event in events_soon:
                    minutes = event.get("minutes_until", 0)
                    title = event.get("title", "Event")
                    calendar = event.get("calendar", "")
                    location = event.get("location", "")
                    
                    cal_icon = "🏠" if calendar == "personal" else "💼"
                    loc_str = f" at {location}" if location else ""
                    
                    if minutes <= 5:
                        alerts.append(f"🔴 {cal_icon} Starting NOW: {title}{loc_str}")
                    elif minutes <= 15:
                        alerts.append(f"⏰ {cal_icon} In {minutes} min: {title}{loc_str}")
                
                if alerts:
                    return {
                        "level": "warning",
                        "message": "\n".join(alerts)
                    }
        
        # =====================================================================
        # Garmin Sync Status
        # =====================================================================
        
        elif sensor_name == "garmin_sync_status":
            status = data.get("status", "")
            hours = data.get("hours_since_sync", 0)
            last_sync = data.get("last_sync_time", "")
            
            # Alert if sync is stale (>12 hours)
            if status == "stale" or hours >= 12:
                # Format the time nicely
                try:
                    from datetime import datetime
                    sync_time = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                    time_str = sync_time.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = last_sync
                
                return {
                    "level": "warning",
                    "message": f"⚠️ Garmin sync is stale! Last data: {hours:.1f} hours ago ({time_str}). Check if Garmin Connect is syncing to InfluxDB."
                }
        
        # =====================================================================
        # Homelab Services
        # =====================================================================
        
        elif sensor_name == "homelab_services":
            down_services = data.get("down_services", [])
            down_count = data.get("down", 0)
            total = data.get("total_services", 0)
            
            if down_count > 0:
                # Build message with service details
                services_list = ", ".join(down_services)
                
                # Get error details for down services
                details = []
                for svc in data.get("services", []):
                    if svc.get("status") == "down":
                        err = svc.get("error", "Unknown error")
                        details.append(f"  - {svc['name']}: {err}")
                
                details_str = "\n".join(details) if details else ""
                
                if down_count >= 3:
                    return {
                        "level": "critical",
                        "message": f"🔴 Multiple homelab services DOWN! ({down_count}/{total})\n{details_str}"
                    }
                else:
                    return {
                        "level": "warning",
                        "message": f"⚠️ Homelab service(s) DOWN: {services_list}\n{details_str}"
                    }
        
        # =====================================================================
        # Remote Server Hardware
        # =====================================================================
        
        elif sensor_name == "remote_server_hardware":
            servers = data.get("servers", [])
            
            alerts = []
            level = "warning"
            
            for srv in servers:
                name = srv.get("display_name", srv.get("server", "Unknown"))
                
                # Check if server is unreachable
                if srv.get("status") != "ok":
                    alerts.append(f"🔴 {name}: {srv.get('error', 'Unreachable')}")
                    level = "critical"
                    continue
                
                # Check disk usage (most critical)
                disk_pct = srv.get("disk_percent", 0)
                if disk_pct >= 95:
                    alerts.append(f"🔴 {name}: Disk CRITICAL at {disk_pct}%!")
                    level = "critical"
                elif disk_pct >= 90:
                    alerts.append(f"⚠️ {name}: Disk high at {disk_pct}%")
                
                # Check memory usage
                mem_pct = srv.get("memory_percent", 0)
                if mem_pct >= 95:
                    alerts.append(f"🔴 {name}: Memory CRITICAL at {mem_pct}%!")
                    level = "critical"
                elif mem_pct >= 90:
                    alerts.append(f"⚠️ {name}: Memory high at {mem_pct}%")
                
                # Check CPU (sustained high load)
                cpu_pct = srv.get("cpu_percent", 0)
                load_5min = srv.get("load_5min", 0)
                cores = srv.get("cpu_cores", 1)
                
                # Alert if load average exceeds cores (system overloaded)
                if load_5min > cores * 2:
                    alerts.append(f"🔴 {name}: System overloaded! Load: {load_5min:.1f} ({cores} cores)")
                    level = "critical"
                elif load_5min > cores:
                    alerts.append(f"⚠️ {name}: High load: {load_5min:.1f} ({cores} cores)")
            
            if alerts:
                return {
                    "level": level,
                    "message": "\n".join(alerts)
                }
        
        return None


# =============================================================================
# Sensor Runner
# =============================================================================

class SensorRunner:
    """Runs sensors on their defined intervals."""
    
    def __init__(
        self,
        cooldown_manager: CooldownManager,
        evaluator: ThresholdEvaluator
    ):
        """Initialize sensor runner.
        
        Args:
            cooldown_manager: Cooldown manager for alerts
            evaluator: Threshold evaluator
        """
        self.cooldown_manager = cooldown_manager
        self.evaluator = evaluator
        self._last_run: Dict[str, float] = {}
        self._running = False
    
    def _should_run(self, sensor: SensorEntry) -> bool:
        """Check if sensor should run based on interval."""
        now = time.time()
        last = self._last_run.get(sensor.name, 0)
        return (now - last) >= sensor.interval_seconds
    
    async def run_sensor(self, sensor: SensorEntry) -> Optional[Dict[str, Any]]:
        """Run a single sensor and process the result.
        
        Args:
            sensor: Sensor entry to run
            
        Returns:
            Sensor data if run, None if skipped
        """
        if not sensor.enabled:
            return None
        
        if not self._should_run(sensor):
            return None
        
        try:
            # Run the sensor function
            data = sensor.func()
            self._last_run[sensor.name] = time.time()
            
            logger.debug(f"Sensor {sensor.name}: {data}")
            
            # Evaluate against thresholds
            alert = self.evaluator.evaluate(sensor.name, data)
            
            if alert:
                level = alert["level"]
                cooldown_key = f"{sensor.name}_{level}"
                
                # Get the primary metric value for change tracking
                alert_value = self._get_primary_value(sensor.name, data)
                
                # Check if we should alert (cooldown + daily limit + value change)
                can_alert = self.cooldown_manager.can_alert(
                    cooldown_key, 
                    sensor=sensor.name, 
                    level=level
                )
                
                # For persistent conditions (like stress), also check if value changed
                is_persistent_sensor = sensor.name in ("stress_level", "body_battery", "recovery_status")
                if can_alert and is_persistent_sensor:
                    can_alert = self.cooldown_manager.should_alert_on_change(
                        sensor.name, alert_value, level
                    )
                    if not can_alert:
                        logger.debug(f"Alert {cooldown_key} skipped - condition unchanged")
                
                if can_alert:
                    # Send alert
                    await send_alert(
                        sensor=sensor.name,
                        message=alert["message"],
                        level=level,
                        data=data
                    )
                    self.cooldown_manager.mark_alerted(
                        cooldown_key, 
                        sensor=sensor.name, 
                        level=level,
                        value=alert_value
                    )
                else:
                    logger.debug(f"Alert {cooldown_key} blocked by cooldown/limit")
            
            return data
            
        except Exception as e:
            logger.error(f"Error running sensor {sensor.name}: {e}")
            return {"error": str(e)}
    
    def _get_primary_value(self, sensor_name: str, data: Dict[str, Any]) -> Any:
        """Extract the primary metric value from sensor data for change tracking."""
        value_keys = {
            "stress_level": "current_stress",
            "body_battery": "body_battery",
            "sleep_quality": "sleep_score",
            "training_readiness": "score",
            "recovery_status": "hrv_deviation_percent",
            "disk_usage": "percent_used",
            "memory_usage": "percent_used",
            "cpu_load": "load_5min",
            "gpu_temperature": "temperature_celsius",
        }
        key = value_keys.get(sensor_name)
        return data.get(key) if key else None
    
    async def run_all(self):
        """Run all enabled sensors that are due."""
        registry = get_sensor_registry()
        
        for sensor in registry.values():
            await self.run_sensor(sensor)
    
    async def loop(self, interval: float = 10.0):
        """Main sensor polling loop.
        
        Args:
            interval: How often to check sensors (seconds)
        """
        self._running = True
        logger.info("Awareness daemon started")
        
        while self._running:
            try:
                await self.run_all()
            except Exception as e:
                logger.error(f"Error in sensor loop: {e}")
            
            await asyncio.sleep(interval)
        
        logger.info("Awareness daemon stopped")
    
    def stop(self):
        """Stop the sensor loop."""
        self._running = False


# =============================================================================
# Main Daemon
# =============================================================================

class AwarenessDaemon:
    """Main awareness daemon class."""
    
    def __init__(self):
        """Initialize the daemon."""
        self.config = get_config()
        
        # Load sensors
        load_extensions()
        registry = get_sensor_registry()
        logger.info(f"Loaded {len(registry)} sensors")
        
        # Initialize components
        cooldown_file = Path(self.config.paths.data) / "alert_cooldowns.json"
        self.cooldown_manager = CooldownManager(cooldown_file)
        
        self.evaluator = ThresholdEvaluator({
            "disk_threshold_percent": self.config.sensors.disk_threshold_percent,
            "gpu_temp_threshold": self.config.sensors.gpu_temp_threshold,
        })
        
        self.runner = SensorRunner(self.cooldown_manager, self.evaluator)
        
        # Initialize schedule runner
        self.scheduler = ScheduleRunner()
        
        # Setup signal handlers
        self._setup_signals()
    
    def _setup_signals(self):
        """Setup signal handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.runner.stop()
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    
    async def run(self):
        """Run the daemon."""
        # Check API connectivity first
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{API_CONFIG['api_url']}/health")
                if response.status_code == 200:
                    logger.info("Connected to friday-core API")
                else:
                    logger.warning("friday-core API returned non-200 status")
        except Exception as e:
            logger.warning(f"Could not connect to friday-core: {e}")
            logger.warning("Continuing anyway - alerts may fail to send")
        
        # Start combined loop (sensors + schedules)
        check_interval = self.config.sensors.check_interval_default / 10  # Check more frequently than min interval
        check_interval = max(5.0, min(check_interval, 30.0))  # Clamp between 5-30 seconds
        
        await self._main_loop(interval=check_interval)
    
    async def _main_loop(self, interval: float = 10.0):
        """Main loop that runs sensors and checks schedules.
        
        Args:
            interval: How often to check sensors (seconds)
        """
        self.runner._running = True
        logger.info("Awareness daemon started (sensors + schedules)")
        
        while self.runner._running:
            try:
                # Run sensors
                await self.runner.run_all()
                
                # Check and run schedules
                scheduled_results = await self.scheduler.check_and_run()
                
                for schedule_name, result in scheduled_results:
                    # Send scheduled report via alert endpoint
                    await send_alert(
                        sensor=f"scheduled_{schedule_name}",
                        message=result,
                        level="info",
                        data={"schedule": schedule_name}
                    )
                    logger.info(f"Sent scheduled report: {schedule_name}")
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            
            await asyncio.sleep(interval)
        
        logger.info("Awareness daemon stopped")


def main():
    """Entry point for the awareness daemon."""
    logger.info("Starting Friday Awareness Daemon...")
    logger.info(f"API URL: {API_CONFIG['api_url']}")
    
    daemon = AwarenessDaemon()
    
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
