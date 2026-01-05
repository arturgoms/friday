"""
Friday Insights Engine - Collectors

Collectors gather data from various sources and store snapshots
for historical analysis.
"""

from src.awareness.collectors.base import BaseCollector
from src.awareness.collectors.health import HealthCollector
from src.awareness.collectors.calendar import CalendarCollector
from src.awareness.collectors.homelab import HomelabCollector
from src.awareness.collectors.weather import WeatherCollector

__all__ = [
    "BaseCollector",
    "HealthCollector",
    "CalendarCollector",
    "HomelabCollector",
    "WeatherCollector",
]
