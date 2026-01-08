"""
Tests for utils tools.

These tests validate date/time utility functions work correctly
and return proper data structures.
"""

import pytest
from datetime import datetime, timedelta


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures."""
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# Test: get_current_time
# =============================================================================

def test_get_current_time_returns_dict():
    """Test get_current_time returns a dict."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    assert isinstance(result, dict), "get_current_time returned non-dict!"
    assert result is not None, "CRITICAL: get_current_time returned None!"


def test_get_current_time_structure():
    """Test get_current_time has correct structure."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    # Check required keys
    assert "datetime" in result, "Missing 'datetime' key"
    assert "formatted" in result, "Missing 'formatted' key"
    assert "timezone" in result, "Missing 'timezone' key"
    assert "date" in result, "Missing 'date' key"
    assert "time" in result, "Missing 'time' key"
    assert "day_of_week" in result, "Missing 'day_of_week' key"
    
    # Validate types
    assert isinstance(result["datetime"], str)
    assert isinstance(result["formatted"], str)
    assert isinstance(result["timezone"], str)
    assert isinstance(result["year"], int)
    assert isinstance(result["month"], int)
    assert isinstance(result["day"], int)


def test_get_current_time_no_none_values():
    """CRITICAL: Ensure get_current_time has no None values."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    none_values = check_for_none_values(result)
    assert len(none_values) == 0, \
        f"CRITICAL: get_current_time has None values at: {none_values}"


def test_get_current_time_default_format():
    """Test get_current_time with default format."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    # Default format should be YYYY-MM-DD HH:MM:SS
    formatted = result.get("formatted", "")
    
    # Should have date and time parts
    assert len(formatted) >= 10, "Formatted time too short"
    assert "-" in formatted or "/" in formatted, "No date separator"
    assert ":" in formatted, "No time separator"


def test_get_current_time_custom_format():
    """Test get_current_time with custom format."""
    from src.tools.utils import get_current_time
    
    result = get_current_time(format="%Y-%m-%d")
    
    # Should have formatted output
    assert "formatted" in result
    formatted = result["formatted"]
    
    # Should be date only (10 chars: YYYY-MM-DD)
    assert len(formatted) == 10, f"Expected YYYY-MM-DD format, got: {formatted}"


def test_get_current_time_has_valid_date_components():
    """Test get_current_time returns valid date components."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    # Validate ranges
    assert 1 <= result["month"] <= 12, "Invalid month"
    assert 1 <= result["day"] <= 31, "Invalid day"
    assert 0 <= result["hour"] <= 23, "Invalid hour"
    assert 0 <= result["minute"] <= 59, "Invalid minute"
    assert 0 <= result["second"] <= 59, "Invalid second"
    assert result["year"] > 2020, "Invalid year"


def test_get_current_time_day_of_week():
    """Test get_current_time returns valid day of week."""
    from src.tools.utils import get_current_time
    
    result = get_current_time()
    
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert result["day_of_week"] in valid_days, \
        f"Invalid day of week: {result.get('day_of_week')}"


# =============================================================================
# Test: calc_days_until_date
# =============================================================================

def test_calc_days_until_date_returns_dict():
    """Test calc_days_until_date returns a dict."""
    from src.tools.utils import calc_days_until_date
    
    result = calc_days_until_date(month=12, day=25)
    
    assert isinstance(result, dict), "calc_days_until_date returned non-dict!"
    assert result is not None, "CRITICAL: calc_days_until_date returned None!"


def test_calc_days_until_date_structure():
    """Test calc_days_until_date has correct structure."""
    from src.tools.utils import calc_days_until_date
    
    result = calc_days_until_date(month=12, day=25)
    
    if "error" not in result:
        # Check required keys
        assert "target_date" in result, "Missing 'target_date' key"
        assert "days_until" in result, "Missing 'days_until' key"
        assert "target_day_name" in result, "Missing 'target_day_name' key"
        assert "is_today" in result, "Missing 'is_today' key"
        assert "is_tomorrow" in result, "Missing 'is_tomorrow' key"
        
        # Validate types
        assert isinstance(result["days_until"], int)
        assert isinstance(result["is_today"], bool)
        assert isinstance(result["is_tomorrow"], bool)


def test_calc_days_until_date_no_none_values():
    """CRITICAL: Ensure calc_days_until_date has no None values."""
    from src.tools.utils import calc_days_until_date
    
    result = calc_days_until_date(month=12, day=25)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: calc_days_until_date has None values at: {none_values}"


def test_calc_days_until_date_future_date():
    """Test calc_days_until_date with future date."""
    from src.tools.utils import calc_days_until_date
    from datetime import datetime
    
    now = datetime.now()
    # Use a date in the future
    future_month = (now.month % 12) + 1
    
    result = calc_days_until_date(month=future_month, day=15)
    
    if "error" not in result:
        # Days until should be positive for future dates
        assert result["days_until"] >= 0, "Future date should have positive days_until"
        assert result["is_today"] == False, "Future date should not be today"


def test_calc_days_until_date_with_year():
    """Test calc_days_until_date with specific year."""
    from src.tools.utils import calc_days_until_date
    
    result = calc_days_until_date(month=12, day=25, year=2027)
    
    if "error" not in result:
        assert "2027" in result["target_date"], "Year not correctly set"
        assert isinstance(result["days_until"], int)


def test_calc_days_until_date_invalid_date():
    """Test calc_days_until_date with invalid date."""
    from src.tools.utils import calc_days_until_date
    
    # Invalid month
    result = calc_days_until_date(month=13, day=1)
    assert "error" in result, "Should return error for invalid month"
    
    # Invalid day
    result = calc_days_until_date(month=2, day=30)
    assert "error" in result, "Should return error for invalid day"


# =============================================================================
# Test: calc_days_between_dates
# =============================================================================

def test_calc_days_between_dates_returns_dict():
    """Test calc_days_between_dates returns a dict."""
    from src.tools.utils import calc_days_between_dates
    
    result = calc_days_between_dates(month1=1, day1=1, month2=1, day2=10)
    
    assert isinstance(result, dict), "calc_days_between_dates returned non-dict!"
    assert result is not None, "CRITICAL: calc_days_between_dates returned None!"


def test_calc_days_between_dates_structure():
    """Test calc_days_between_dates has correct structure."""
    from src.tools.utils import calc_days_between_dates
    
    result = calc_days_between_dates(month1=1, day1=1, month2=1, day2=10)
    
    if "error" not in result:
        # Check required keys
        assert "days_between" in result, "Missing 'days_between' key"
        assert "date1" in result, "Missing 'date1' key"
        assert "date2" in result, "Missing 'date2' key"
        assert "earlier_date" in result, "Missing 'earlier_date' key"
        assert "later_date" in result, "Missing 'later_date' key"
        
        # Validate types
        assert isinstance(result["days_between"], int)


def test_calc_days_between_dates_no_none_values():
    """CRITICAL: Ensure calc_days_between_dates has no None values."""
    from src.tools.utils import calc_days_between_dates
    
    result = calc_days_between_dates(month1=1, day1=1, month2=1, day2=10)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: calc_days_between_dates has None values at: {none_values}"


def test_calc_days_between_dates_calculation():
    """Test calc_days_between_dates calculates correctly."""
    from src.tools.utils import calc_days_between_dates
    
    # January 1 to January 10 = 9 days
    result = calc_days_between_dates(month1=1, day1=1, month2=1, day2=10)
    
    if "error" not in result:
        assert result["days_between"] == 9, \
            f"Expected 9 days, got {result['days_between']}"


def test_calc_days_between_dates_same_date():
    """Test calc_days_between_dates with same date."""
    from src.tools.utils import calc_days_between_dates
    
    result = calc_days_between_dates(month1=5, day1=15, month2=5, day2=15)
    
    if "error" not in result:
        assert result["days_between"] == 0, "Same date should be 0 days"


def test_calc_days_between_dates_invalid():
    """Test calc_days_between_dates with invalid dates."""
    from src.tools.utils import calc_days_between_dates
    
    # Invalid month
    result = calc_days_between_dates(month1=13, day1=1, month2=1, day2=1)
    assert "error" in result, "Should return error for invalid month"
    
    # Invalid day
    result = calc_days_between_dates(month1=2, day1=30, month2=3, day2=1)
    assert "error" in result, "Should return error for invalid day"


# =============================================================================
# Test: All Utils Tools Together
# =============================================================================

def test_all_utils_tools_return_non_none():
    """CRITICAL: Ensure NO utils tool returns None."""
    from src.tools.utils import (
        get_current_time, calc_days_until_date, calc_days_between_dates
    )
    
    tools = [
        (get_current_time, {}),
        (calc_days_until_date, {"month": 12, "day": 25}),
        (calc_days_between_dates, {"month1": 1, "day1": 1, "month2": 1, "day2": 10}),
    ]
    
    for tool_func, kwargs in tools:
        result = tool_func(**kwargs)
        assert result is not None, f"CRITICAL: {tool_func.__name__} returned None!"


def test_all_utils_tools_return_dict():
    """Ensure all utils tools return dicts."""
    from src.tools.utils import (
        get_current_time, calc_days_until_date, calc_days_between_dates
    )
    
    tools = [
        get_current_time, calc_days_until_date, calc_days_between_dates
    ]
    
    for tool in tools:
        if tool == get_current_time:
            result = tool()
        elif tool == calc_days_until_date:
            result = tool(month=12, day=25)
        else:  # calc_days_between_dates
            result = tool(month1=1, day1=1, month2=1, day2=10)
        
        assert isinstance(result, dict), \
            f"{tool.__name__} returned {type(result)} instead of dict!"


def test_all_utils_tools_no_none_values():
    """CRITICAL: Batch test - ensure NO utils tool returns None values."""
    from src.tools.utils import (
        get_current_time, calc_days_until_date, calc_days_between_dates
    )
    
    tools = [
        (get_current_time, {}),
        (calc_days_until_date, {"month": 12, "day": 25}),
        (calc_days_between_dates, {"month1": 1, "day1": 1, "month2": 1, "day2": 10}),
    ]
    
    failures = []
    for tool_func, kwargs in tools:
        result = tool_func(**kwargs)
        if isinstance(result, dict) and "error" not in result:
            none_values = check_for_none_values(result)
            if none_values:
                failures.append(f"{tool_func.__name__}: {none_values}")
    
    assert len(failures) == 0, \
        f"CRITICAL: Tools with None values:\n" + "\n".join(failures)


# =============================================================================
# Test: Time Consistency
# =============================================================================

def test_get_current_time_consistency():
    """Test get_current_time returns consistent time."""
    from src.tools.utils import get_current_time
    import time
    
    result1 = get_current_time()
    time.sleep(0.1)  # Small delay
    result2 = get_current_time()
    
    # Both should succeed
    assert isinstance(result1, dict)
    assert isinstance(result2, dict)
    
    # Should have same date components (unless test runs at midnight)
    # At minimum, year should be same
    assert result1["year"] == result2["year"]


def test_date_calculations_are_deterministic():
    """Test date calculations return same result when called multiple times."""
    from src.tools.utils import calc_days_between_dates
    
    result1 = calc_days_between_dates(month1=1, day1=1, month2=6, day2=1)
    result2 = calc_days_between_dates(month1=1, day1=1, month2=6, day2=1)
    
    if "error" not in result1 and "error" not in result2:
        assert result1["days_between"] == result2["days_between"], \
            "Date calculation not deterministic"
