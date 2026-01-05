"""
Time utilities for Friday
"""

from settings import settings


def get_brt():
    """Get BRT timezone from settings."""
    return settings.TIMEZONE
