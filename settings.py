"""
Friday Configuration Settings

Django-style settings module that consolidates all configuration.
Loads from a single .env file at the project root.

Usage:
    from settings import settings
    print(settings.TELEGRAM_BOT_TOKEN)
"""

import os
from pathlib import Path
from typing import Any, Dict, List

import pytz
from dotenv import load_dotenv

# ==============================================================================
# Base Configuration
# ==============================================================================

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


# ==============================================================================
# Core System Settings
# ==============================================================================

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))


# ==============================================================================
# Paths Configuration
# ==============================================================================

PATHS = {
    "root": Path(os.getenv("PATHS_ROOT", BASE_DIR)),
    "brain": Path(os.getenv("PATHS_BRAIN", BASE_DIR / "brain")),
    "data": Path(os.getenv("PATHS_DATA", BASE_DIR / "data")),
    "logs": Path(os.getenv("PATHS_LOGS", BASE_DIR / "logs")),
    "config": Path(os.getenv("PATHS_CONFIG", BASE_DIR / "src" / "config")),
}


# ==============================================================================
# User Configuration
# ==============================================================================

USER = {
    "name": os.getenv("USER_NAME", "Artur"),
    "profile_file": os.getenv("USER_PROFILE_FILE", "Artur Gomes.md"),
    "timezone": os.getenv("USER_TIMEZONE", "America/Sao_Paulo"),
}

# Timezone object
TIMEZONE = pytz.timezone(USER["timezone"])


# ==============================================================================
# LLM Configuration
# ==============================================================================

LLM = {
    "model_name": os.getenv("LLM_MODEL_NAME", "NousResearch/Hermes-4-14B"),
    "base_url": os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
}


# ==============================================================================
# API Configuration
# ==============================================================================

FRIDAY_API_URL = os.getenv("FRIDAY_API_URL", "http://localhost:8080")
FRIDAY_API_KEY = os.getenv("FRIDAY_API_KEY", "")


# ==============================================================================
# External Services - Telegram
# ==============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID", "")


# ==============================================================================
# External Services - Calendar
# ==============================================================================

# Nextcloud CalDAV
NEXTCLOUD_CALDAV_URL = os.getenv("NEXTCLOUD_CALDAV_URL", "")
NEXTCLOUD_USERNAME = os.getenv("NEXTCLOUD_USERNAME", "")
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "")

# Google Calendar
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


# ==============================================================================
# External Services - Weather
# ==============================================================================

OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Curitiba")


# ==============================================================================
# External Services - AI/ML
# ==============================================================================

WHISPER_SERVICE_URL = os.getenv("WHISPER_SERVICE_URL", "")
STABLE_DIFFUSION_URL = os.getenv("STABLE_DIFFUSION_URL", "")
SEARXNG_URL = os.getenv("SEARXNG_URL", "https://searxng.arturgomes.com")


# ==============================================================================
# External Services - Databases
# ==============================================================================

# InfluxDB Configuration
INFLUXDB = {
    "host": os.getenv("INFLUXDB_HOST", "192.168.1.16"),
    "port": int(os.getenv("INFLUXDB_PORT", "8088")),
    "username": os.getenv("INFLUXDB_USERNAME", "artur"),
    "password": os.getenv("INFLUXDB_PASSWORD", ""),
    "database": os.getenv("INFLUXDB_DATABASE", "GarminStats"),
}


# ==============================================================================
# Vault Configuration
# ==============================================================================

VAULT_PATH = Path(os.getenv("VAULT_PATH", BASE_DIR / "brain"))


# ==============================================================================
# Delivery Channels Configuration
# ==============================================================================

DELIVERY_CHANNELS = {
    "channels": [{"type": "telegram", "enabled": True, "config": {}}],
    "routing": {
        "insights": {
            "urgent": ["telegram"],
            "high": ["telegram"],
            "medium": ["telegram"],
            "low": ["telegram"],
        },
        "alerts": {
            "critical": ["telegram"],
            "warning": ["telegram"],
            "info": ["telegram"],
        },
        "reports": {
            "morning": ["telegram"],
            "evening": ["telegram"],
            "weekly": ["telegram"],
        },
    },
}


# ==============================================================================
# External Services Monitoring
# ==============================================================================

EXTERNAL_SERVICES = [
    {
        "name": "Portainer",
        "url": "http://192.168.1.16:9000",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Traefik",
        "url": "http://traefik.arturgomes.com/",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Dashy",
        "url": "https://dashy.arturgomes.com/",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Home Assistant",
        "url": "http://192.168.1.16:8123",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Immich",
        "url": "http://192.168.1.16:3001",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "n8n",
        "url": "http://192.168.1.16:5678",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Grafana",
        "url": "http://192.168.1.16:8087",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "InfluxDB",
        "url": "http://192.168.1.16:8086/health",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "InfluxDB 1.x",
        "url": "http://192.168.1.16:8088/ping",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Prometheus",
        "url": "http://192.168.1.16:9090",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Graphite",
        "url": "http://192.168.1.16:8050",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Whisper ASR",
        "url": "http://192.168.1.16:8001",
        "type": "http",
        "timeout": 10,
        "check_interval": 300,
    },
    {
        "name": "Stable Diffusion",
        "url": "http://192.168.1.16:8002",
        "type": "http",
        "timeout": 10,
        "check_interval": 300,
    },
    {
        "name": "Open WebUI",
        "url": "http://192.168.1.16:8010",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "SearXNG",
        "url": "http://192.168.1.16:8888",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Syncthing",
        "url": "http://192.168.1.16:8384",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    },
    {
        "name": "Glances",
        "url": "http://192.168.1.16:61208/api/4/status",
        "type": "http",
        "timeout": 5,
        "check_interval": 300,
    }
]


# ==============================================================================
# Awareness Engine Configuration
# ==============================================================================

AWARENESS = {
    # Data source tools - atomic tools that return dict, saved as snapshots
    "data_sources": [
        {
            "name": "recovery_status",
            "tool": "src.tools.health.get_recovery_status",
            "schedule": "*/5 * * * *",  # Every 5 minutes
            "enabled": True,
            "analyzers": ["stress_monitor", "threshold"],
            "description": "Current health metrics from Garmin (training readiness, body battery, HRV, stress)",
        },
        {
            "name": "sleep_tracking",
            "tool": "src.tools.health.get_sleep_summary",
            "schedule": "0 9 * * *",  # Daily at 9:00 AM
            "enabled": True,
            "analyzers": ["sleep_correlator"],
            "description": "Latest sleep data with sleep score and stages",
        },
        {
            "name": "calendar_sync",
            "tool": "src.tools.calendar.get_today_schedule",
            "schedule": "*/10 * * * *",  # Every 10 minutes
            "enabled": True,
            "analyzers": ["calendar_reminder"],
            "description": "Today's calendar events",
        },
        {
            "name": "weather_updates",
            "tool": "src.tools.weather.get_current_weather",
            "schedule": "0 */1 * * *",  # Every hour
            "enabled": True,
            "analyzers": [],
            "description": "Current weather conditions",
        },
        {
            "name": "system_monitoring",
            "tool": "src.tools.system.get_friday_status",
            "schedule": "*/5 * * * *",  # Every 5 minutes
            "enabled": True,
            "analyzers": ["threshold", "resource_trend"],
            "description": "Friday server status (disk, CPU, memory)",
        },
        {
            "name": "homelab_monitoring",
            "tool": "src.tools.sensors.get_all_homelab_servers",
            "schedule": "*/10 * * * *",  # Every 10 minutes
            "enabled": True,
            "analyzers": ["threshold"],
            "description": "Homelab server hardware stats",
        },
        {
            "name": "external_services",
            "tool": "src.tools.sensors.get_all_external_services",
            "schedule": "*/15 * * * *",  # Every 15 minutes
            "enabled": True,
            "analyzers": ["threshold"],
            "description": "External services health checks (Portainer, Home Assistant, Dashy, etc.)",
        },
    ],

    # Scheduled reports - composite tools that return formatted strings
    "scheduled_reports": [
        {
            "name": "morning_briefing",
            "tool": "src.tools.daily_briefing.report_morning_briefing",
            "schedule": "0 10 * * *",  # Daily at 10:00 AM
            "enabled": True,
            "channels": ["telegram"],
            "description": "Daily morning briefing with health, calendar, weather",
        },
        {
            "name": "evening_report",
            "tool": "src.tools.daily_briefing.report_evening_briefing",
            "schedule": "0 21 * * *",  # Daily at 9:00 PM
            "enabled": True,
            "channels": ["telegram"],
            "description": "Evening report with sleep recommendation",
        },
    ],

    # Analyzer configuration
    "analyzers": {
        "threshold": {
            "enabled": True,
            "description": "Alert when metrics exceed configured thresholds",
        },
        "stress_monitor": {
            "enabled": True,
            "sustained_minutes": 120,  # Alert if stress high for 2 hours
            "description": "Monitor sustained high stress periods",
        },
        "calendar_reminder": {
            "enabled": True,
            "remind_minutes": [60, 15],  # Remind 1 hour and 15 minutes before
            "description": "Send reminders for upcoming events",
        },
        "sleep_correlator": {
            "enabled": True,
            "min_days": 7,
            "description": "Find correlations between activities and sleep quality",
        },
        "exercise_impact": {
            "enabled": True,
            "min_samples": 5,
            "description": "Analyze how exercise affects recovery and energy",
        },
        "resource_trend": {
            "enabled": True,
            "alert_days": 30,
            "description": "Alert on concerning resource usage trends",
        },
    },

    # Decision engine settings
    "decision": {
        "max_reach_outs_per_day": 5,
        "quiet_hours": {"start": "22:00", "end": "08:00"},
        "cooldown_minutes": 60,
        "batch_low_priority": True,
        "min_confidence": 0.7,
        "scheduled_reports_respect_quiet_hours": False,  # Scheduled reports ignore quiet hours
    },

    # Thresholds for alerts
    "thresholds": {
        "disk_percent": {"warning": 85, "critical": 95},
        "memory_percent": {"warning": 90, "critical": 95},
        "cpu_load": {"warning": 8.0, "critical": 12.0},
        "stress": {"warning": 50, "critical": 70, "sustained_minutes": 120},
        "body_battery": {"warning": 30, "critical": 20},
        "sleep_score": {"warning": 50, "critical": 40},
        "garmin_sync_stale_hours": 12,
        "services_down": {"warning": 1, "critical": 2},  # Alert on ANY service down, critical if 2+
    },

    # Storage settings
    "snapshot_retention_days": 90,
}


# ==============================================================================
# Legacy Schedules Configuration (DEPRECATED - use AWARENESS instead)
# ==============================================================================

SCHEDULES = [
    {
        "name": "morning_report",
        "time": "10:00",
        "tool": "get_morning_report",
        "enabled": True,
        "description": "Daily morning briefing",
    },
    {
        "name": "evening_report",
        "time": "21:00",
        "tool": "get_evening_report",
        "enabled": True,
        "description": "Daily evening report with sleep recommendation",
    },
]


# ==============================================================================
# Calibration Tables for Health Metrics
# ==============================================================================

CALIBRATION = {
    "_description": "Calibration tables for LLM interpretation of metrics. Adjust based on personal baselines.",
    "_updated": "2024-12-02",
    "health": {
        "sleep": {
            "score": {
                "excellent": {
                    "min": 80,
                    "max": 100,
                    "description": "Excellent sleep, well recovered",
                },
                "good": {
                    "min": 70,
                    "max": 79,
                    "description": "Good sleep, adequate recovery",
                },
                "fair": {
                    "min": 60,
                    "max": 69,
                    "description": "Fair sleep, may feel somewhat tired",
                },
                "poor": {
                    "min": 0,
                    "max": 59,
                    "description": "Poor sleep, likely to feel fatigued",
                },
            },
            "duration_hours": {
                "optimal": {
                    "min": 7,
                    "max": 9,
                    "description": "Optimal sleep duration",
                },
                "adequate": {"min": 6, "max": 7, "description": "Minimally adequate"},
                "short": {
                    "min": 0,
                    "max": 6,
                    "description": "Sleep deprived, affects recovery and performance",
                },
            },
            "deep_sleep_percent": {
                "excellent": {
                    "min": 20,
                    "max": 100,
                    "description": "Excellent deep sleep for physical recovery",
                },
                "good": {"min": 15, "max": 20, "description": "Good deep sleep"},
                "low": {
                    "min": 0,
                    "max": 15,
                    "description": "Low deep sleep, may affect physical recovery",
                },
            },
            "rem_sleep_percent": {
                "excellent": {
                    "min": 20,
                    "max": 100,
                    "description": "Excellent REM for cognitive recovery",
                },
                "good": {"min": 15, "max": 20, "description": "Good REM sleep"},
                "low": {
                    "min": 0,
                    "max": 15,
                    "description": "Low REM, may affect memory and mood",
                },
            },
            "awake_count": {
                "good": {"min": 0, "max": 2, "description": "Minimal disruptions"},
                "moderate": {
                    "min": 3,
                    "max": 4,
                    "description": "Some disruptions, normal range",
                },
                "high": {
                    "min": 5,
                    "max": 100,
                    "description": "Frequent awakenings, fragmented sleep",
                },
            },
            "awake_time_min": {
                "good": {"min": 0, "max": 20, "description": "Minimal time awake"},
                "moderate": {
                    "min": 21,
                    "max": 40,
                    "description": "Moderate time awake",
                },
                "high": {
                    "min": 41,
                    "max": 1000,
                    "description": "Significant time awake, reduces sleep quality",
                },
            },
            "restless_moments": {
                "low": {"min": 0, "max": 30, "description": "Calm sleep"},
                "moderate": {"min": 31, "max": 60, "description": "Some restlessness"},
                "high": {
                    "min": 61,
                    "max": 1000,
                    "description": "Very restless, may indicate discomfort or stress",
                },
            },
        },
        "recovery": {
            "training_readiness": {
                "prime": {
                    "min": 80,
                    "max": 100,
                    "description": "Ready for high intensity training",
                },
                "ready": {
                    "min": 60,
                    "max": 79,
                    "description": "Ready for moderate training",
                },
                "fair": {
                    "min": 40,
                    "max": 59,
                    "description": "Consider lighter training",
                },
                "low": {
                    "min": 0,
                    "max": 39,
                    "description": "Focus on recovery, avoid intense training",
                },
            },
            "body_battery": {
                "high": {"min": 70, "max": 100, "description": "High energy reserves"},
                "moderate": {"min": 40, "max": 69, "description": "Moderate energy"},
                "low": {
                    "min": 20,
                    "max": 39,
                    "description": "Low energy, consider rest",
                },
                "depleted": {
                    "min": 0,
                    "max": 19,
                    "description": "Very low, prioritize rest",
                },
            },
            "body_battery_wake": {
                "excellent": {
                    "min": 80,
                    "max": 100,
                    "description": "Excellent overnight recovery",
                },
                "good": {"min": 60, "max": 79, "description": "Good recovery"},
                "fair": {"min": 40, "max": 59, "description": "Incomplete recovery"},
                "poor": {
                    "min": 0,
                    "max": 39,
                    "description": "Poor recovery, may need rest day",
                },
            },
            "hrv_ms": {
                "_note": "HRV is highly individual. These are general ranges. User baseline: ~50ms",
                "high": {
                    "min": 60,
                    "max": 200,
                    "description": "High HRV, good recovery state",
                },
                "normal": {"min": 40, "max": 59, "description": "Normal HRV range"},
                "low": {
                    "min": 0,
                    "max": 39,
                    "description": "Low HRV, may indicate stress or fatigue",
                },
            },
            "resting_hr_bpm": {
                "_note": "Lower is generally better for trained individuals. User baseline: ~49bpm",
                "excellent": {
                    "min": 0,
                    "max": 50,
                    "description": "Excellent cardiovascular fitness",
                },
                "good": {"min": 51, "max": 60, "description": "Good fitness level"},
                "average": {"min": 61, "max": 70, "description": "Average fitness"},
                "elevated": {
                    "min": 71,
                    "max": 200,
                    "description": "Elevated, may indicate stress or illness",
                },
            },
            "recovery_time_hours": {
                "recovered": {"min": 0, "max": 0, "description": "Fully recovered"},
                "short": {"min": 1, "max": 24, "description": "Minor recovery needed"},
                "moderate": {
                    "min": 25,
                    "max": 48,
                    "description": "Moderate recovery period",
                },
                "extended": {
                    "min": 49,
                    "max": 1000,
                    "description": "Extended recovery, avoid hard training",
                },
            },
        },
        "stress": {
            "average": {
                "low": {"min": 0, "max": 25, "description": "Low stress, well managed"},
                "moderate": {
                    "min": 26,
                    "max": 50,
                    "description": "Moderate stress levels",
                },
                "high": {
                    "min": 51,
                    "max": 75,
                    "description": "High stress, consider relaxation",
                },
                "very_high": {
                    "min": 76,
                    "max": 100,
                    "description": "Very high stress, take action to reduce",
                },
            },
            "sleep_stress": {
                "restful": {"min": 0, "max": 15, "description": "Very restful sleep"},
                "calm": {"min": 16, "max": 25, "description": "Calm sleep"},
                "moderate": {
                    "min": 26,
                    "max": 40,
                    "description": "Some stress during sleep",
                },
                "high": {
                    "min": 41,
                    "max": 100,
                    "description": "High stress during sleep, affects recovery",
                },
            },
        },
        "breathing": {
            "spo2_avg_percent": {
                "normal": {
                    "min": 95,
                    "max": 100,
                    "description": "Normal oxygen saturation",
                },
                "low": {"min": 90, "max": 94, "description": "Slightly low, monitor"},
                "concerning": {
                    "min": 0,
                    "max": 89,
                    "description": "Low SpO2, may need medical attention",
                },
            },
            "spo2_lowest_percent": {
                "normal": {"min": 90, "max": 100, "description": "Normal dips"},
                "low": {
                    "min": 85,
                    "max": 89,
                    "description": "Low dips, may indicate sleep apnea",
                },
                "concerning": {
                    "min": 0,
                    "max": 84,
                    "description": "Significant desaturation, consult doctor",
                },
            },
            "respiration_rate": {
                "normal": {
                    "min": 12,
                    "max": 20,
                    "description": "Normal breathing rate",
                },
                "low": {"min": 0, "max": 11, "description": "Low respiration"},
                "elevated": {
                    "min": 21,
                    "max": 100,
                    "description": "Elevated, may indicate stress or illness",
                },
            },
        },
        "running": {
            "training_effect_aerobic": {
                "overreaching": {
                    "min": 5.0,
                    "max": 5.0,
                    "description": "Overreaching, extended recovery needed",
                },
                "highly_improving": {
                    "min": 4.0,
                    "max": 4.9,
                    "description": "Highly improving fitness",
                },
                "improving": {
                    "min": 3.0,
                    "max": 3.9,
                    "description": "Improving fitness",
                },
                "maintaining": {
                    "min": 2.0,
                    "max": 2.9,
                    "description": "Maintaining fitness",
                },
                "minor": {"min": 1.0, "max": 1.9, "description": "Minor benefit"},
                "none": {"min": 0, "max": 0.9, "description": "No aerobic benefit"},
            },
            "weekly_mileage_km": {
                "_note": "Depends on training goals. Adjust based on user's typical volume",
                "high": {"min": 50, "max": 1000, "description": "High volume week"},
                "moderate": {"min": 30, "max": 49, "description": "Moderate volume"},
                "light": {"min": 15, "max": 29, "description": "Light training week"},
                "recovery": {"min": 0, "max": 14, "description": "Recovery/rest week"},
            },
        },
        "activity": {
            "daily_steps": {
                "very_active": {
                    "min": 12000,
                    "max": 100000,
                    "description": "Very active day",
                },
                "active": {
                    "min": 10000,
                    "max": 11999,
                    "description": "Active day, hit common goal",
                },
                "moderate": {
                    "min": 7000,
                    "max": 9999,
                    "description": "Moderately active",
                },
                "light": {"min": 4000, "max": 6999, "description": "Light activity"},
                "sedentary": {"min": 0, "max": 3999, "description": "Sedentary day"},
            }
        },
    },
    "response_guidelines": {
        "tone": {
            "style": "direct and concise",
            "avoid": [
                "Based on...",
                "According to the data...",
                "It appears that...",
                "I can see that...",
            ],
            "prefer": [
                "Your sleep was...",
                "You slept...",
                "Sleep score: 68 (fair)...",
            ],
        },
        "analysis": {
            "always_mention": [
                "The primary metric and its interpretation",
                "Key issues if any",
                "Actionable suggestion if relevant",
            ],
            "avoid": [
                "Repeating all numbers without analysis",
                "Generic advice not tied to data",
                "Overly positive spin on poor metrics",
            ],
        },
    },
}


# ==============================================================================
# Settings Class for Easy Access
# ==============================================================================


class Settings:
    """
    Settings accessor class similar to Django's settings.
    Provides attribute-style access to all configuration values.
    """

    def __init__(self):
        # Copy all module-level variables to this instance
        current_module = __import__(__name__)
        for key in dir(current_module):
            if key.isupper() or key in ["TIMEZONE", "BASE_DIR"]:
                setattr(self, key, getattr(current_module, key))

    def __repr__(self):
        return f"<Settings module>"


# Create singleton settings instance
settings = Settings()
