"""Unit tests for date_tools service."""
import pytest
import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.services.date_tools import DateTools
from app.core.config import settings


@pytest.mark.unit
class TestDateTools:
    """Test date tools functionality."""
    
    @pytest.fixture
    def date_tools(self):
        """Create DateTools instance."""
        return DateTools()
    
    def test_get_current_time(self, date_tools):
        """Test get_current_time returns formatted time with timezone."""
        result = date_tools.get_current_time()
        
        # Should contain time in 12-hour format
        assert "AM" in result or "PM" in result
        assert ":" in result
        
        # Should contain timezone
        assert "UTC" in result
        assert "-3" in result
    
    def test_get_current_datetime(self, date_tools):
        """Test get_current_datetime returns dict with all fields."""
        result = date_tools.get_current_datetime()
        
        # Check all required fields
        assert "date" in result
        assert "time" in result
        assert "time_12h" in result
        assert "day_of_week" in result
        assert "month" in result
        assert "year" in result
        assert "timestamp" in result
        assert "iso_format" in result
        assert "timezone" in result
        
        # Verify timezone
        assert result["timezone"] == "UTC-3"
        
        # Verify date format
        assert len(result["date"]) == 10  # YYYY-MM-DD
        assert result["date"].count("-") == 2
    
    def test_days_between(self, date_tools):
        """Test days_between calculation."""
        result = date_tools.days_between("2025-03-30", "2025-11-24")
        
        # Should be 239 days
        assert result == 239
    
    def test_days_until(self, date_tools):
        """Test days_until calculation."""
        # Test with a future date
        future_date = (datetime.now(settings.user_timezone) + timedelta(days=10)).strftime("%Y-%m-%d")
        result = date_tools.days_until(future_date)
        
        assert 9 <= result <= 10  # Allow for timing
    
    def test_days_until_birthday(self, date_tools):
        """Test days_until_birthday calculation."""
        result = date_tools.days_until_birthday(3, 30)  # March 30
        
        # Should be between 0 and 365
        assert 0 <= result <= 365
    
    @pytest.mark.parametrize("date_text,expected_format", [
        ("March 30", r"\d{4}-03-30"),
        ("03/30", r"\d{4}-03-30"),
        ("2025-11-24", "2025-11-24"),
    ])
    def test_parse_date_from_text(self, date_tools, date_text, expected_format):
        """Test date parsing from various formats."""
        import re
        
        result = date_tools.parse_date_from_text(date_text)
        
        assert re.match(expected_format, result), \
            f"Expected {expected_format}, got {result}"
