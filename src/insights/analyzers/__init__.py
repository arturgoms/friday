"""
Friday Insights Engine - Analyzers

Analyzers process collected data to generate insights.
"""

from src.insights.analyzers.base import (
    BaseAnalyzer,
    RealTimeAnalyzer,
    PeriodicAnalyzer,
    ScheduledAnalyzer,
)
from src.insights.analyzers.thresholds import ThresholdAnalyzer
from src.insights.analyzers.stress import StressAnalyzer
from src.insights.analyzers.calendar import CalendarAnalyzer
from src.insights.analyzers.sleep import SleepCorrelationAnalyzer
from src.insights.analyzers.resources import ResourceTrendAnalyzer

__all__ = [
    "BaseAnalyzer",
    "RealTimeAnalyzer",
    "PeriodicAnalyzer",
    "ScheduledAnalyzer",
    "ThresholdAnalyzer",
    "StressAnalyzer",
    "CalendarAnalyzer",
    "SleepCorrelationAnalyzer",
    "ResourceTrendAnalyzer",
]
