"""
Friday Insights Engine - Collectors

Collectors gather data from various sources and store snapshots
for historical analysis.
"""

from src.insights.collectors.base import BaseCollector
from src.insights.collectors.health import HealthCollector
from src.insights.collectors.calendar import CalendarCollector
from src.insights.collectors.homelab import HomelabCollector
from src.insights.collectors.weather import WeatherCollector

__all__ = [
    "BaseCollector",
    "HealthCollector",
    "CalendarCollector",
    "HomelabCollector",
    "WeatherCollector",
]
