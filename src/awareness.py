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
from typing import Any, Dict, Optional

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
    """Manages alert cooldowns to prevent spam."""
    
    def __init__(self, cooldown_file: Optional[Path] = None):
        """Initialize cooldown manager.
        
        Args:
            cooldown_file: Path to persist cooldowns (optional)
        """
        self.cooldown_file = cooldown_file
        self._cooldowns: Dict[str, datetime] = {}
        self._load_cooldowns()
    
    def _load_cooldowns(self):
        """Load cooldowns from file if exists."""
        if self.cooldown_file and self.cooldown_file.exists():
            try:
                data = json.loads(self.cooldown_file.read_text())
                self._cooldowns = {
                    k: datetime.fromisoformat(v) 
                    for k, v in data.items()
                }
            except Exception as e:
                logger.warning(f"Failed to load cooldowns: {e}")
    
    def _save_cooldowns(self):
        """Save cooldowns to file."""
        if self.cooldown_file:
            try:
                data = {k: v.isoformat() for k, v in self._cooldowns.items()}
                self.cooldown_file.write_text(json.dumps(data, indent=2))
            except Exception as e:
                logger.warning(f"Failed to save cooldowns: {e}")
    
    def can_alert(self, key: str, cooldown_minutes: int = 30) -> bool:
        """Check if an alert can be sent (not in cooldown).
        
        Args:
            key: Unique key for this alert type (e.g., "disk_usage_critical")
            cooldown_minutes: Minimum minutes between alerts
            
        Returns:
            True if alert can be sent, False if in cooldown
        """
        now = datetime.now()
        
        if key in self._cooldowns:
            cooldown_until = self._cooldowns[key]
            if now < cooldown_until:
                return False
        
        return True
    
    def mark_alerted(self, key: str, cooldown_minutes: int = 30):
        """Mark that an alert was sent.
        
        Args:
            key: Unique key for this alert type
            cooldown_minutes: Minutes until next alert allowed
        """
        self._cooldowns[key] = datetime.now() + timedelta(minutes=cooldown_minutes)
        self._save_cooldowns()
    
    def clear(self, key: Optional[str] = None):
        """Clear cooldown(s).
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            self._cooldowns.pop(key, None)
        else:
            self._cooldowns.clear()
        self._save_cooldowns()


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
                # Check cooldown
                cooldown_key = f"{sensor.name}_{alert['level']}"
                cooldown_minutes = 30 if alert["level"] == "warning" else 15
                
                if self.cooldown_manager.can_alert(cooldown_key, cooldown_minutes):
                    # Send alert
                    await send_alert(
                        sensor=sensor.name,
                        message=alert["message"],
                        level=alert["level"],
                        data=data
                    )
                    self.cooldown_manager.mark_alerted(cooldown_key, cooldown_minutes)
                else:
                    logger.debug(f"Alert {cooldown_key} in cooldown, skipping")
            
            return data
            
        except Exception as e:
            logger.error(f"Error running sensor {sensor.name}: {e}")
            return {"error": str(e)}
    
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
        
        # Start sensor loop
        check_interval = self.config.sensors.check_interval_default / 10  # Check more frequently than min interval
        check_interval = max(5.0, min(check_interval, 30.0))  # Clamp between 5-30 seconds
        
        await self.runner.loop(interval=check_interval)


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
