"""Date and time calculation tools."""
from datetime import datetime, timedelta
from typing import Dict, Any
import json


class DateTools:
    """Tools for date calculations and formatting."""
    
    def get_current_datetime(self) -> Dict[str, Any]:
        """Get current date and time information."""
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "month": now.strftime("%B"),
            "year": now.year,
            "timestamp": now.timestamp(),
            "iso_format": now.isoformat(),
        }
    
    def days_between(self, date1: str, date2: str | None = None) -> int:
        """
        Calculate days between two dates.
        
        Args:
            date1: First date in YYYY-MM-DD format
            date2: Second date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            Number of days between the dates
        """
        try:
            d1 = datetime.strptime(date1, "%Y-%m-%d")
            d2 = datetime.strptime(date2, "%Y-%m-%d") if date2 else datetime.now()
            delta = d1 - d2
            return abs(delta.days)
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}")
    
    def days_until(self, target_date: str) -> int:
        """
        Calculate days until a target date from today.
        
        Args:
            target_date: Target date in YYYY-MM-DD format
        
        Returns:
            Number of days until target date (negative if in the past)
        """
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
            today = datetime.now()
            delta = target - today
            return delta.days
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}")
    
    def days_until_birthday(self, birth_month: int, birth_day: int) -> int:
        """
        Calculate days until next birthday.
        
        Args:
            birth_month: Month of birth (1-12)
            birth_day: Day of birth (1-31)
        
        Returns:
            Number of days until next birthday
        """
        today = datetime.now()
        current_year = today.year
        
        # Try this year's birthday
        birthday = datetime(current_year, birth_month, birth_day)
        
        # If birthday has passed this year, use next year
        if birthday < today:
            birthday = datetime(current_year + 1, birth_month, birth_day)
        
        delta = birthday - today
        return delta.days
    
    def parse_date_from_text(self, date_text: str) -> str:
        """
        Parse common date formats and return YYYY-MM-DD.
        
        Supports:
        - March 30
        - 03/30
        - 3/30
        - March 30, 2025
        
        Returns:
            Date in YYYY-MM-DD format
        """
        date_text = date_text.strip()
        
        # Try common formats
        formats = [
            "%B %d",  # March 30
            "%b %d",  # Mar 30
            "%m/%d",  # 03/30
            "%B %d, %Y",  # March 30, 2025
            "%b %d, %Y",  # Mar 30, 2025
            "%Y-%m-%d",  # 2025-03-30
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_text, fmt)
                # If year not provided, use current or next year
                if parsed.year == 1900:
                    current_year = datetime.now().year
                    parsed = parsed.replace(year=current_year)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_text}")
    
    def get_tools_description(self) -> str:
        """Get description of available date tools for LLM."""
        return """
Available date calculation tools:

1. get_current_datetime() - Get current date/time info
2. days_between(date1, date2=None) - Days between two dates (YYYY-MM-DD)
3. days_until(target_date) - Days until a specific date from today
4. days_until_birthday(month, day) - Days until next birthday
5. parse_date_from_text(date_text) - Parse common date formats

Examples:
- days_until_birthday(3, 30) -> days until March 30
- days_between("2025-03-30", "2025-11-24") -> 239
"""


# Singleton instance
date_tools = DateTools()
