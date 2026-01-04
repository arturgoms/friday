"""
Friday Insights Engine - Threshold Analyzer

Real-time analyzer that checks values against configured thresholds.
Replaces the old hardcoded ThresholdEvaluator from awareness.py.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import get_brt
from src.insights.analyzers.base import RealTimeAnalyzer
from src.insights.config import InsightsConfig
from src.insights.models import (
    Category,
    Insight,
    InsightType,
    Priority,
)
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class ThresholdAnalyzer(RealTimeAnalyzer):
    """
    Analyzes current values against configured thresholds.

    Checks:
    - Health: stress, body battery, sleep score
    - System: disk usage, memory, CPU load
    - Homelab: service status, GPU temp
    - Weather: extreme conditions

    All thresholds are configurable via config/insights.json
    """

    def __init__(self, config: InsightsConfig, store: InsightsStore):
        super().__init__("threshold", config, store)

    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Check all thresholds and generate insights for violations."""
        insights = []

        # Health thresholds
        if "health" in data:
            insights.extend(self._check_health_thresholds(data["health"]))

        # System/homelab thresholds
        if "homelab" in data:
            insights.extend(self._check_homelab_thresholds(data["homelab"]))

        # Weather thresholds (extreme conditions)
        if "weather" in data:
            insights.extend(self._check_weather_thresholds(data["weather"]))

        return insights

    def _check_health_thresholds(self, health: Dict[str, Any]) -> List[Insight]:
        """Check health-related thresholds."""
        insights = []

        # Check if Garmin data is stale
        sync_info = health.get("sync", {})
        if sync_info.get("status") == "stale":
            hours_ago = sync_info.get("hours_ago", 0)
            stale_threshold = self.config.thresholds.get("garmin_sync_stale_hours", 12)

            if hours_ago >= stale_threshold:
                dedupe_key = "garmin_sync_stale"
                if not self.was_insight_delivered_recently(dedupe_key, hours=6):
                    insights.append(Insight(
                        type=InsightType.STATUS,
                        category=Category.HEALTH,
                        priority=Priority.MEDIUM,
                        title="Garmin sync stale",
                        message=f"Last sync was {hours_ago:.1f}h ago. Health data may be outdated.",
                        dedupe_key=dedupe_key,
                        data={"hours_ago": hours_ago},
                        expires_at=datetime.now(get_brt()) + timedelta(hours=6),
                    ))

        # Stress level (only if we have fresh data)
        if sync_info.get("status") == "fresh":
            stress = health.get("stress", {}).get("current")
            if stress is not None:
                insight = self._check_threshold(
                    value=stress,
                    threshold_name="stress",
                    category=Category.HEALTH,
                    title_template="Stress level {level}",
                    message_template="Current stress: {value} (threshold: {threshold})",
                    higher_is_worse=True,
                )
                if insight:
                    insights.append(insight)

            # Body battery (lower is worse)
            body_battery = health.get("body_battery", {}).get("current")
            if body_battery is not None:
                insight = self._check_threshold(
                    value=body_battery,
                    threshold_name="body_battery",
                    category=Category.HEALTH,
                    title_template="Body battery {level}",
                    message_template="Current body battery: {value}% (threshold: {threshold}%)",
                    higher_is_worse=False,
                )
                if insight:
                    insights.append(insight)

            # Sleep score (from last night)
            sleep_score = health.get("sleep", {}).get("sleep_score")
            if sleep_score is not None:
                insight = self._check_threshold(
                    value=sleep_score,
                    threshold_name="sleep_score",
                    category=Category.HEALTH,
                    title_template="Sleep quality {level}",
                    message_template="Last night's sleep score: {value} (threshold: {threshold})",
                    higher_is_worse=False,
                )
                if insight:
                    insights.append(insight)

        return insights

    def _check_homelab_thresholds(self, homelab: Dict[str, Any]) -> List[Insight]:
        """Check homelab/system thresholds."""
        insights = []

        # Services down - handle nested structure from collector
        services_data = homelab.get("services", {})
        if isinstance(services_data, dict):
            # New collector format: {"services": [...], "down_services": [...], ...}
            services = services_data.get("services", [])
            down_services = [s for s in services if s.get("status") == "down"]
        else:
            # Legacy format: direct list
            services = services_data
            down_services = [s for s in services if s.get("status") != "running"]
        if down_services:
            svc_threshold = self.config.thresholds.get("services_down", {})
            warning = svc_threshold.get("warning", 1)
            critical = svc_threshold.get("critical", 3)

            count = len(down_services)
            names = ", ".join([s.get("name", "unknown") for s in down_services[:5]])

            if count >= critical:
                level, priority = "critical", Priority.HIGH
            elif count >= warning:
                level, priority = "elevated", Priority.MEDIUM
            else:
                level, priority = None, None

            if level:
                dedupe_key = f"services_down_{count}"
                if not self.was_insight_delivered_recently(dedupe_key):
                    insights.append(Insight(
                        type=InsightType.THRESHOLD,
                        category=Category.HOMELAB,
                        priority=priority,
                        title=f"{count} service(s) down",
                        message=f"Down: {names}",
                        dedupe_key=dedupe_key,
                        data={"count": count, "services": down_services},
                        expires_at=datetime.now(get_brt()) + timedelta(hours=1),
                    ))

        # Hardware stats - check both servers and local
        hardware = homelab.get("hardware", {})
        local = homelab.get("local", {})

        # Check local disk usage first
        local_disk = local.get("disk_percent")
        if local_disk is not None:
            insight = self._check_threshold(
                value=local_disk,
                threshold_name="disk_percent",
                category=Category.HOMELAB,
                title_template="Disk (local) {level}",
                message_template="Local disk: {value:.1f}% used (threshold: {threshold}%)",
                higher_is_worse=True,
                dedupe_suffix="local",
            )
            if insight:
                insights.append(insight)

        # Check local memory
        local_mem = local.get("memory_percent")
        if local_mem is not None:
            insight = self._check_threshold(
                value=local_mem,
                threshold_name="memory_percent",
                category=Category.HOMELAB,
                title_template="Memory usage {level}",
                message_template="Memory: {value:.1f}% used (threshold: {threshold}%)",
                higher_is_worse=True,
            )
            if insight:
                insights.append(insight)

        # Check local CPU load
        local_load = local.get("load_1min")
        if local_load is not None:
            insight = self._check_threshold(
                value=local_load,
                threshold_name="cpu_load",
                category=Category.HOMELAB,
                title_template="CPU load {level}",
                message_template="1-min load: {value:.1f} (threshold: {threshold})",
                higher_is_worse=True,
            )
            if insight:
                insights.append(insight)

        # Check each server's stats
        servers = hardware.get("servers", [])
        for server in servers:
            if server.get("status") != "ok":
                continue

            server_name = server.get("name", "unknown")

            # Server disk
            disk_pct = server.get("disk_percent")
            if disk_pct is not None:
                insight = self._check_threshold(
                    value=disk_pct,
                    threshold_name="disk_percent",
                    category=Category.HOMELAB,
                    title_template=f"Disk ({server_name}) {{level}}",
                    message_template=f"{server_name} disk: {{value:.1f}}% used (threshold: {{threshold}}%)",
                    higher_is_worse=True,
                    dedupe_suffix=server_name.lower(),
                )
                if insight:
                    insights.append(insight)

            # Server memory
            mem_pct = server.get("memory_percent")
            if mem_pct is not None:
                insight = self._check_threshold(
                    value=mem_pct,
                    threshold_name="memory_percent",
                    category=Category.HOMELAB,
                    title_template=f"Memory ({server_name}) {{level}}",
                    message_template=f"{server_name}: {{value:.1f}}% memory (threshold: {{threshold}}%)",
                    higher_is_worse=True,
                    dedupe_suffix=server_name.lower(),
                )
                if insight:
                    insights.append(insight)

        return insights

    def _check_weather_thresholds(self, weather: Dict[str, Any]) -> List[Insight]:
        """Check weather for extreme conditions worth alerting about."""
        insights = []

        current = weather.get("current", {})

        # Extreme heat
        temp = current.get("temp")
        if temp is not None and temp > 35:
            dedupe_key = "weather_extreme_heat"
            if not self.was_insight_delivered_recently(dedupe_key, hours=4):
                insights.append(Insight(
                    type=InsightType.THRESHOLD,
                    category=Category.WEATHER,
                    priority=Priority.MEDIUM,
                    title="Extreme heat warning",
                    message=f"Current temperature: {temp}°C. Stay hydrated!",
                    dedupe_key=dedupe_key,
                    data={"temp": temp},
                    expires_at=datetime.now(get_brt()) + timedelta(hours=4),
                ))

        # Check for weather alerts
        alerts = weather.get("alerts", [])
        for alert in alerts:
            event = alert.get("event", "Weather alert")
            dedupe_key = f"weather_alert_{event.lower().replace(' ', '_')}"
            if not self.was_insight_delivered_recently(dedupe_key, hours=4):
                insights.append(Insight(
                    type=InsightType.THRESHOLD,
                    category=Category.WEATHER,
                    priority=Priority.HIGH,
                    title=event,
                    message=alert.get("description", "Weather alert active"),
                    dedupe_key=dedupe_key,
                    data=alert,
                    expires_at=datetime.now(get_brt()) + timedelta(hours=6),
                ))

        return insights

    def _check_threshold(
        self,
        value: float,
        threshold_name: str,
        category: Category,
        title_template: str,
        message_template: str,
        higher_is_worse: bool = True,
        dedupe_suffix: str = "",
    ) -> Optional[Insight]:
        """
        Generic threshold check.

        Args:
            value: Current value to check
            threshold_name: Name in config (e.g., "disk_percent")
            category: Insight category
            title_template: Title with {level} placeholder
            message_template: Message with {value}, {threshold} placeholders
            higher_is_worse: True if exceeding threshold is bad
            dedupe_suffix: Additional suffix for dedupe_key

        Returns:
            Insight if threshold violated, None otherwise
        """
        threshold_config = self.config.thresholds.get(threshold_name, {})

        if isinstance(threshold_config, dict):
            warning = threshold_config.get("warning")
            critical = threshold_config.get("critical")
        else:
            # Single value threshold
            warning = threshold_config
            critical = None

        if warning is None:
            return None

        # Determine if threshold is violated
        level = None
        priority = None
        threshold_value = None

        if higher_is_worse:
            if critical is not None and value >= critical:
                level, priority, threshold_value = "critical", Priority.HIGH, critical
            elif value >= warning:
                level, priority, threshold_value = "elevated", Priority.MEDIUM, warning
        else:
            # Lower is worse (e.g., body battery, sleep score)
            if critical is not None and value <= critical:
                level, priority, threshold_value = "critical", Priority.HIGH, critical
            elif value <= warning:
                level, priority, threshold_value = "low", Priority.MEDIUM, warning

        if level is None:
            return None

        # Build dedupe key
        dedupe_key = f"{threshold_name}_{level}"
        if dedupe_suffix:
            dedupe_key += f"_{dedupe_suffix}"

        # Check cooldown
        if self.was_insight_delivered_recently(dedupe_key):
            return None

        return Insight(
            type=InsightType.THRESHOLD,
            category=category,
            priority=priority,
            title=title_template.format(level=level),
            message=message_template.format(value=value, threshold=threshold_value),
            dedupe_key=dedupe_key,
            data={"value": value, "threshold": threshold_value, "level": level},
            expires_at=datetime.now(get_brt()) + timedelta(hours=2),
        )
