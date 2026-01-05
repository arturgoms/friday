"""
Friday Insights Engine

Unified system for data collection, analysis, and proactive reach-outs.
"""

from src.awareness.models import Insight, Snapshot, Delivery, InsightType, Priority, Category

# Don't import InsightsEngine by default to avoid import errors from incomplete dependencies
# from src.awareness.engine import InsightsEngine

__all__ = [
    # "InsightsEngine",  # Import directly when needed
    "Insight",
    "Snapshot", 
    "Delivery",
    "InsightType",
    "Priority",
    "Category",
]
