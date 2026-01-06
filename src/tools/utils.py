"""
Friday 3.0 Utility Tools

General utility functions for calculations, dates, and conversions.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
from datetime import datetime
from typing import Dict, Any

from settings import settings

logger = logging.getLogger(__name__)


@agent.tool_plain
def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
    """Get the current date and time in local timezone.
    
    Atomic data tool that returns structured time data.
    
    Args:
        format: strftime format string for formatted output
    
    Returns:
        Dict with current time information
    """
    now = datetime.now(settings.TIMEZONE)
    return {
        "datetime": now.isoformat(),
        "formatted": now.strftime(format),
        "timezone": str(settings.TIMEZONE),
        "unix_timestamp": int(now.timestamp()),
        "date": now.date().isoformat(),
        "time": now.time().isoformat(),
        "day_of_week": now.strftime("%A"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "second": now.second
    }


@agent.tool_plain
def calc_days_until_date(month: int, day: int, year: int = 0) -> Dict[str, Any]:
    """Calculate how many days until a specific date.
    
    Calculation tool - returns result but does NOT save snapshot (calculations are ephemeral).
    
    Use this tool when the user asks "how many days until X" or "when is X birthday".
    DO NOT try to calculate dates yourself - always use this tool.
    
    Args:
        month: Month number (1-12, where 1=January, 12=December)
        day: Day of month (1-31)
        year: Optional specific year (if not provided, assumes current or next occurrence)
    
    Returns:
        Dict with date calculation results
    
    Examples:
        - calc_days_until_date(12, 25) → Days until December 25th
        - calc_days_until_date(3, 15, 2026) → Days until March 15, 2026
    """
    try:
        now = datetime.now(settings.TIMEZONE)
        
        # Determine target year
        if year and year > 0:
            target_year = year
        else:
            # Try current year first
            target_year = now.year
            target_date = datetime(target_year, month, day, tzinfo=settings.TIMEZONE)
            
            # If date has already passed this year, use next year
            if target_date < now:
                target_year = now.year + 1
        
        # Create target date
        target_date = datetime(target_year, month, day, tzinfo=settings.TIMEZONE)
        
        # Calculate difference
        delta = target_date - now
        days_until = delta.days
        
        return {
            "target_date": target_date.date().isoformat(),
            "target_day_name": target_date.strftime("%A"),
            "target_formatted": target_date.strftime("%B %d, %Y"),
            "days_until": days_until,
            "is_today": days_until == 0,
            "is_tomorrow": days_until == 1,
            "is_past": days_until < 0,
            "current_date": now.date().isoformat(),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating days until date: {e}")
        return {"error": f"Invalid date - month={month}, day={day}, year={year}: {e}"}


@agent.tool_plain
def calc_days_between_dates(month1: int, day1: int, month2: int, day2: int) -> Dict[str, Any]:
    """Calculate the difference in days between two dates (same year).
    
    Calculation tool - returns result but does NOT save snapshot (calculations are ephemeral).
    
    Use this tool when the user asks "what's the difference between X and Y dates".
    DO NOT try to calculate date differences yourself - always use this tool.
    
    Args:
        month1: First date's month (1-12)
        day1: First date's day (1-31)
        month2: Second date's month (1-12)
        day2: Second date's day (1-31)
    
    Returns:
        Dict with date difference calculation results
    
    Examples:
        - calc_days_between_dates(12, 25, 1, 1) → Days between Dec 25 and Jan 1
        - calc_days_between_dates(3, 15, 12, 12) → Days between Mar 15 and Dec 12
    """
    try:
        now = datetime.now(settings.TIMEZONE)
        current_year = now.year
        
        # Create both dates in the same year for comparison
        date1 = datetime(current_year, month1, day1, tzinfo=settings.TIMEZONE)
        date2 = datetime(current_year, month2, day2, tzinfo=settings.TIMEZONE)
        
        # Calculate absolute difference
        delta = abs((date2 - date1).days)
        
        # Determine which is earlier
        if date1 < date2:
            earlier_date = date1
            later_date = date2
        else:
            earlier_date = date2
            later_date = date1
        
        return {
            "date1": date1.date().isoformat(),
            "date2": date2.date().isoformat(),
            "days_between": delta,
            "earlier_date": earlier_date.date().isoformat(),
            "later_date": later_date.date().isoformat(),
            "earlier_formatted": earlier_date.strftime("%B %d"),
            "later_formatted": later_date.strftime("%B %d"),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating days between dates: {e}")
        return {"error": f"Invalid dates - date1: {month1}/{day1}, date2: {month2}/{day2}: {e}"}
