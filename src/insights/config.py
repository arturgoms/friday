"""
Friday Insights Engine - Configuration

Loads and validates configuration from config/insights.json
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    """Configuration for a single collector."""
    interval_seconds: int = 300
    enabled: bool = True


@dataclass
class ThresholdConfig:
    """Threshold configuration for an alert."""
    warning: float
    critical: float
    sustained_minutes: Optional[int] = None  # For stress, etc.


@dataclass
class AnalyzerConfig:
    """Configuration for an analyzer."""
    enabled: bool = True
    min_days: Optional[int] = None  # Min data for correlations
    min_samples: Optional[int] = None  # Min samples for analysis
    alert_days: Optional[int] = None  # For resource trend alerts


@dataclass
class DecisionConfig:
    """Configuration for the decision engine."""
    max_reach_outs_per_day: int = 5
    quiet_hours_start: time = field(default_factory=lambda: time(22, 0))
    quiet_hours_end: time = field(default_factory=lambda: time(8, 0))
    cooldown_minutes: int = 60
    batch_low_priority: bool = True
    min_confidence: float = 0.7  # Min confidence for correlations


@dataclass
class DeliveryConfig:
    """Configuration for delivery schedules."""
    morning_report_enabled: bool = True
    morning_report_time: time = field(default_factory=lambda: time(10, 0))
    evening_report_enabled: bool = True
    evening_report_time: time = field(default_factory=lambda: time(21, 0))
    weekly_report_enabled: bool = True
    weekly_report_day: str = "sunday"
    weekly_report_time: time = field(default_factory=lambda: time(20, 0))
    journal_thread_enabled: bool = True
    journal_thread_time: time = field(default_factory=lambda: time(10, 0))
    daily_note_enabled: bool = True
    daily_note_time: time = field(default_factory=lambda: time(23, 59))


@dataclass
class JournalConfig:
    """Configuration for journal system."""
    habits: List[str] = field(default_factory=lambda: [
        "Read",
        "Exercise",
        "Quality time with wife",
        "Quality time with pets",
        "Play games",
        "Meditation"
    ])
    health_targets: Dict[str, Any] = field(default_factory=lambda: {
        "sleep_hours": 7,
        "stress_avg": 40,
        "steps": 8000
    })


@dataclass
class InsightsConfig:
    """Main configuration for the insights engine."""
    
    # Collector settings
    collectors: Dict[str, CollectorConfig] = field(default_factory=dict)
    
    # Threshold settings
    thresholds: Dict[str, Any] = field(default_factory=dict)
    
    # Analyzer settings
    analyzers: Dict[str, AnalyzerConfig] = field(default_factory=dict)
    
    # Decision engine settings
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    
    # Delivery settings
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)
    
    # Journal settings
    journal: JournalConfig = field(default_factory=JournalConfig)
    
    # General
    timezone: str = "America/Sao_Paulo"
    snapshot_retention_days: int = 90
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "InsightsConfig":
        """Load configuration from JSON file.
        
        Args:
            config_path: Path to config file. Defaults to config/insights.json
            
        Returns:
            InsightsConfig instance
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "insights.json"
        
        if not config_path.exists():
            logger.warning(f"Config not found at {config_path}, using defaults")
            return cls._default_config()
        
        try:
            with open(config_path) as f:
                data = json.load(f)
            return cls._from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            return cls._default_config()
    
    @classmethod
    def _default_config(cls) -> "InsightsConfig":
        """Create default configuration."""
        return cls(
            collectors={
                "health": CollectorConfig(interval_seconds=300),
                "calendar": CollectorConfig(interval_seconds=120),
                "homelab": CollectorConfig(interval_seconds=120),
                "weather": CollectorConfig(interval_seconds=600),
            },
            thresholds={
                "disk_percent": {"warning": 85, "critical": 95},
                "memory_percent": {"warning": 90, "critical": 95},
                "cpu_load": {"warning": 8.0, "critical": 12.0},
                "stress": {"warning": 50, "critical": 70, "sustained_minutes": 120},
                "body_battery": {"warning": 30, "critical": 20},
                "sleep_score": {"warning": 50, "critical": 40},
                "garmin_sync_stale_hours": 12,
                "services_down": {"warning": 1, "critical": 3},
            },
            analyzers={
                "sleep_correlator": AnalyzerConfig(enabled=True, min_days=7),
                "exercise_impact": AnalyzerConfig(enabled=True, min_samples=5),
                "resource_trend": AnalyzerConfig(enabled=True, alert_days=30),
                "calendar_analyzer": AnalyzerConfig(enabled=True),
            },
            decision=DecisionConfig(),
            delivery=DeliveryConfig(),
        )
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "InsightsConfig":
        """Create config from dictionary."""
        config = cls._default_config()
        
        # Parse collectors
        if "collection" in data:
            for name, coll_data in data["collection"].items():
                config.collectors[name] = CollectorConfig(
                    interval_seconds=coll_data.get("interval_seconds", 300),
                    enabled=coll_data.get("enabled", True)
                )
        
        # Parse thresholds
        if "thresholds" in data:
            config.thresholds = data["thresholds"]
        
        # Parse analyzers
        if "analyzers" in data:
            for name, ana_data in data["analyzers"].items():
                config.analyzers[name] = AnalyzerConfig(
                    enabled=ana_data.get("enabled", True),
                    min_days=ana_data.get("min_days"),
                    min_samples=ana_data.get("min_samples"),
                    alert_days=ana_data.get("alert_days"),
                )
        
        # Parse decision config
        if "decision" in data:
            dec = data["decision"]
            quiet_start = cls._parse_time(dec.get("quiet_hours", {}).get("start", "22:00"))
            quiet_end = cls._parse_time(dec.get("quiet_hours", {}).get("end", "08:00"))
            
            config.decision = DecisionConfig(
                max_reach_outs_per_day=dec.get("max_reach_outs_per_day", 5),
                quiet_hours_start=quiet_start,
                quiet_hours_end=quiet_end,
                cooldown_minutes=dec.get("cooldown_minutes", 60),
                batch_low_priority=dec.get("batch_low_priority", True),
                min_confidence=dec.get("min_confidence", 0.7),
            )
        
        # Parse delivery config
        if "delivery" in data:
            del_data = data["delivery"]
            
            morning = del_data.get("morning_report", {})
            evening = del_data.get("evening_report", {})
            weekly = del_data.get("weekly_report", {})
            journal_thread = del_data.get("journal_thread", {})
            daily_note = del_data.get("daily_note", {})
            
            config.delivery = DeliveryConfig(
                morning_report_enabled=morning.get("enabled", True),
                morning_report_time=cls._parse_time(morning.get("time", "10:00")),
                evening_report_enabled=evening.get("enabled", True),
                evening_report_time=cls._parse_time(evening.get("time", "21:00")),
                weekly_report_enabled=weekly.get("enabled", True),
                weekly_report_day=weekly.get("day", "sunday"),
                weekly_report_time=cls._parse_time(weekly.get("time", "20:00")),
                journal_thread_enabled=journal_thread.get("enabled", True),
                journal_thread_time=cls._parse_time(journal_thread.get("time", "10:00")),
                daily_note_enabled=daily_note.get("enabled", True),
                daily_note_time=cls._parse_time(daily_note.get("time", "23:59")),
            )
        
        # Parse journal config
        if "journal" in data:
            journal_data = data["journal"]
            config.journal = JournalConfig(
                habits=journal_data.get("habits", JournalConfig().habits),
                health_targets=journal_data.get("health_targets", JournalConfig().health_targets),
            )
        
        # General settings
        config.timezone = data.get("timezone", "America/Sao_Paulo")
        config.snapshot_retention_days = data.get("snapshot_retention_days", 90)
        
        return config
    
    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse HH:MM string to time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    
    def get_threshold(self, name: str, level: str = "warning") -> Optional[float]:
        """Get a threshold value.
        
        Args:
            name: Threshold name (e.g., "disk_percent")
            level: "warning" or "critical"
            
        Returns:
            Threshold value or None
        """
        threshold = self.thresholds.get(name)
        if isinstance(threshold, dict):
            return threshold.get(level)
        return threshold
    
    def is_analyzer_enabled(self, name: str) -> bool:
        """Check if an analyzer is enabled."""
        analyzer = self.analyzers.get(name)
        return analyzer.enabled if analyzer else False
