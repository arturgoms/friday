"""
Tests for Friday 3.0 Core Utilities

Tests the shared utility functions in src/core/utils.py
"""

import pytest


class TestFormatDuration:
    """Tests for format_duration function."""
    
    def test_format_duration_zero(self):
        """Test formatting zero seconds."""
        from src.core.utils import format_duration
        
        assert format_duration(0) == "0m"
    
    def test_format_duration_none(self):
        """Test formatting None."""
        from src.core.utils import format_duration
        
        assert format_duration(None) == "0m"
    
    def test_format_duration_minutes_only(self):
        """Test formatting minutes only."""
        from src.core.utils import format_duration
        
        assert format_duration(1800) == "30m"
        assert format_duration(2700) == "45m"
        assert format_duration(60) == "1m"
    
    def test_format_duration_hours_and_minutes(self):
        """Test formatting hours and minutes."""
        from src.core.utils import format_duration
        
        assert format_duration(3600) == "1h 0m"
        assert format_duration(5400) == "1h 30m"
        assert format_duration(7200) == "2h 0m"
        assert format_duration(9000) == "2h 30m"
    
    def test_format_duration_large_values(self):
        """Test formatting large durations."""
        from src.core.utils import format_duration
        
        assert format_duration(36000) == "10h 0m"
        assert format_duration(86400) == "24h 0m"


class TestFormatPace:
    """Tests for format_pace function."""
    
    def test_format_pace_zero(self):
        """Test formatting zero speed."""
        from src.core.utils import format_pace
        
        assert format_pace(0) == "N/A"
    
    def test_format_pace_none(self):
        """Test formatting None speed."""
        from src.core.utils import format_pace
        
        assert format_pace(None) == "N/A"
    
    def test_format_pace_negative(self):
        """Test formatting negative speed."""
        from src.core.utils import format_pace
        
        assert format_pace(-1) == "N/A"
    
    def test_format_pace_typical_running(self):
        """Test formatting typical running paces."""
        from src.core.utils import format_pace
        
        # ~5:33/km pace (3 m/s)
        result = format_pace(3.0)
        assert "/km" in result
        assert result.startswith("5:")
        
        # ~4:10/km pace (4 m/s)
        result = format_pace(4.0)
        assert "/km" in result
        assert result.startswith("4:")


class TestFormatDistance:
    """Tests for format_distance function."""
    
    def test_format_distance_zero(self):
        """Test formatting zero distance."""
        from src.core.utils import format_distance
        
        assert format_distance(0) == "0 km"
    
    def test_format_distance_none(self):
        """Test formatting None distance."""
        from src.core.utils import format_distance
        
        assert format_distance(None) == "0 km"
    
    def test_format_distance_kilometers(self):
        """Test formatting distances in km."""
        from src.core.utils import format_distance
        
        assert format_distance(5000) == "5.0 km"
        assert format_distance(10500) == "10.5 km"
        assert format_distance(21097) == "21.1 km"  # Half marathon
    
    def test_format_distance_miles(self):
        """Test formatting distances in miles."""
        from src.core.utils import format_distance
        
        result = format_distance(1609.344, unit="mi")
        assert "1.0 mi" == result


class TestTruncateText:
    """Tests for truncate_text function."""
    
    def test_truncate_short_text(self):
        """Test that short text is not truncated."""
        from src.core.utils import truncate_text
        
        text = "Hello"
        assert truncate_text(text, max_length=100) == text
    
    def test_truncate_exact_length(self):
        """Test text at exact max length."""
        from src.core.utils import truncate_text
        
        text = "Hello"
        assert truncate_text(text, max_length=5) == text
    
    def test_truncate_long_text(self):
        """Test truncating long text."""
        from src.core.utils import truncate_text
        
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")
    
    def test_truncate_custom_suffix(self):
        """Test truncating with custom suffix."""
        from src.core.utils import truncate_text
        
        text = "This is a long text"
        result = truncate_text(text, max_length=15, suffix="…")
        assert result.endswith("…")


class TestSafeGet:
    """Tests for safe_get function."""
    
    def test_safe_get_simple(self):
        """Test getting a simple key."""
        from src.core.utils import safe_get
        
        data = {"a": 1, "b": 2}
        assert safe_get(data, "a") == 1
        assert safe_get(data, "b") == 2
    
    def test_safe_get_nested(self):
        """Test getting nested keys."""
        from src.core.utils import safe_get
        
        data = {"a": {"b": {"c": 3}}}
        assert safe_get(data, "a", "b", "c") == 3
    
    def test_safe_get_missing_key(self):
        """Test getting missing key returns None."""
        from src.core.utils import safe_get
        
        data = {"a": 1}
        assert safe_get(data, "b") is None
    
    def test_safe_get_missing_nested(self):
        """Test getting missing nested key returns None."""
        from src.core.utils import safe_get
        
        data = {"a": {"b": 1}}
        assert safe_get(data, "a", "c") is None
        assert safe_get(data, "x", "y", "z") is None
    
    def test_safe_get_default(self):
        """Test getting missing key with default."""
        from src.core.utils import safe_get
        
        data = {"a": 1}
        assert safe_get(data, "b", default=0) == 0
        assert safe_get(data, "x", "y", default="missing") == "missing"
    
    def test_safe_get_none_value(self):
        """Test getting key with None value."""
        from src.core.utils import safe_get
        
        data = {"a": None}
        assert safe_get(data, "a", default="default") == "default"
