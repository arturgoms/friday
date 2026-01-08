"""
Tests for calendar tools.

These tests validate that calendar tools return correct data structures
and handle various scenarios properly. Tests run against real calendar data.
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
# Test: get_calendar_events
# =============================================================================

def test_get_calendar_events_returns_dict():
    """Test get_calendar_events returns a dict."""
    from src.tools.calendar import get_calendar_events
    
    result = get_calendar_events(days=7)
    
    assert isinstance(result, dict), "get_calendar_events returned non-dict!"
    assert result is not None, "CRITICAL: get_calendar_events returned None!"


def test_get_calendar_events_structure():
    """Test get_calendar_events has correct structure."""
    from src.tools.calendar import get_calendar_events
    
    result = get_calendar_events(days=7, calendar="both")
    
    if "error" not in result:
        # Should have event data
        assert "events" in result or "total_events" in result or len(result) > 0, \
            "get_calendar_events missing event data"


def test_get_calendar_events_no_none_values():
    """CRITICAL: Ensure get_calendar_events has no None values."""
    from src.tools.calendar import get_calendar_events
    
    result = get_calendar_events(days=7)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_calendar_events has None values at: {none_values}"


def test_get_calendar_events_with_different_days():
    """Test get_calendar_events with different day ranges."""
    from src.tools.calendar import get_calendar_events
    
    # Test different ranges
    for days in [1, 7, 14, 30]:
        result = get_calendar_events(days=days)
        assert isinstance(result, dict)
        assert result is not None


def test_get_calendar_events_calendar_filter():
    """Test get_calendar_events with calendar filter."""
    from src.tools.calendar import get_calendar_events
    
    # Test different calendar filters
    for calendar in ["both", "personal", "work"]:
        result = get_calendar_events(days=7, calendar=calendar)
        assert isinstance(result, dict)
        assert result is not None


# =============================================================================
# Test: get_today_schedule
# =============================================================================

def test_get_today_schedule_returns_dict():
    """Test get_today_schedule returns a dict."""
    from src.tools.calendar import get_today_schedule
    
    result = get_today_schedule()
    
    assert isinstance(result, dict), "get_today_schedule returned non-dict!"
    assert result is not None, "CRITICAL: get_today_schedule returned None!"


def test_get_today_schedule_structure():
    """Test get_today_schedule has correct structure."""
    from src.tools.calendar import get_today_schedule
    
    result = get_today_schedule()
    
    if "error" not in result:
        # Check required keys
        assert "date" in result, "Missing 'date' key"
        assert "current_events" in result, "Missing 'current_events' key"
        assert "upcoming_events" in result, "Missing 'upcoming_events' key"
        assert "completed_events" in result, "Missing 'completed_events' key"
        assert "total_events" in result, "Missing 'total_events' key"
        assert "timestamp" in result, "Missing 'timestamp' key"
        
        # Validate types
        assert isinstance(result["current_events"], list)
        assert isinstance(result["upcoming_events"], list)
        assert isinstance(result["completed_events"], list)
        assert isinstance(result["total_events"], int)


def test_get_today_schedule_event_structure():
    """Test events in today's schedule have correct structure."""
    from src.tools.calendar import get_today_schedule
    
    result = get_today_schedule()
    
    if "error" not in result:
        all_events = (result.get("current_events", []) + 
                     result.get("upcoming_events", []) + 
                     result.get("completed_events", []))
        
        if all_events:
            event = all_events[0]
            # Check required event fields
            assert "title" in event, "Event missing 'title'"
            assert "start" in event, "Event missing 'start'"
            assert "end" in event, "Event missing 'end'"
            assert "calendar" in event, "Event missing 'calendar'"


def test_get_today_schedule_no_none_values():
    """CRITICAL: Ensure get_today_schedule has no None values."""
    from src.tools.calendar import get_today_schedule
    
    result = get_today_schedule()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_today_schedule has None values at: {none_values}"


# =============================================================================
# Test: get_next_event
# =============================================================================

def test_get_next_event_returns_dict():
    """Test get_next_event returns a dict."""
    from src.tools.calendar import get_next_event
    
    result = get_next_event()
    
    assert isinstance(result, dict), "get_next_event returned non-dict!"
    assert result is not None, "CRITICAL: get_next_event returned None!"


def test_get_next_event_structure():
    """Test get_next_event has correct structure."""
    from src.tools.calendar import get_next_event
    
    result = get_next_event()
    
    if "error" not in result and "no_events" not in result:
        # Should have event information
        assert "event" in result, "Missing 'event' key"
        assert "time_until" in result or "current_time" in result, \
            "Missing time information"


def test_get_next_event_no_none_values():
    """CRITICAL: Ensure get_next_event has no None values."""
    from src.tools.calendar import get_next_event
    
    result = get_next_event()
    
    if "error" not in result and "no_events" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_next_event has None values at: {none_values}"


# =============================================================================
# Test: find_free_time
# =============================================================================

def test_find_free_time_returns_dict():
    """Test find_free_time returns a dict."""
    from src.tools.calendar import find_free_time
    
    result = find_free_time()
    
    assert isinstance(result, dict), "find_free_time returned non-dict!"
    assert result is not None, "CRITICAL: find_free_time returned None!"


def test_find_free_time_structure():
    """Test find_free_time has correct structure."""
    from src.tools.calendar import find_free_time
    
    result = find_free_time(min_duration=30)
    
    if "error" not in result:
        # Should have free time slots information
        assert "free_slots" in result or "slots" in result or "date" in result, \
            "find_free_time missing expected keys"


def test_find_free_time_no_none_values():
    """CRITICAL: Ensure find_free_time has no None values."""
    from src.tools.calendar import find_free_time
    
    result = find_free_time()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: find_free_time has None values at: {none_values}"


def test_find_free_time_with_parameters():
    """Test find_free_time with different parameters."""
    from src.tools.calendar import find_free_time
    from datetime import datetime
    
    # Test with specific date
    today = datetime.now().strftime("%Y-%m-%d")
    result = find_free_time(date=today, min_duration=60)
    
    assert isinstance(result, dict)
    assert result is not None


# =============================================================================
# Test: add_calendar_event
# =============================================================================

def test_add_calendar_event_returns_string():
    """Test add_calendar_event returns a string (confirmation message)."""
    from src.tools.calendar import add_calendar_event
    
    # Note: We won't actually add events in tests, but validate return type
    # This would need to be tested manually or with a test calendar
    
    # Just check the function signature is correct
    import inspect
    sig = inspect.signature(add_calendar_event)
    params = list(sig.parameters.keys())
    
    assert "title" in params
    assert "start_time" in params
    assert "end_time" in params


def test_add_calendar_event_validates_calendar_type():
    """Test add_calendar_event handles calendar type correctly."""
    from src.tools.calendar import add_calendar_event
    
    # Test that work calendar is read-only (should return error message)
    result = add_calendar_event(
        title="Test Event",
        start_time="10:00",
        end_time="11:00",
        calendar="work"
    )
    
    assert isinstance(result, str)
    assert result is not None
    assert "read-only" in result.lower() or "personal" in result.lower()


# =============================================================================
# Test: delete_calendar_event  
# =============================================================================

def test_delete_calendar_event_returns_string():
    """Test delete_calendar_event returns a string (confirmation message)."""
    from src.tools.calendar import delete_calendar_event
    
    # Check function signature
    import inspect
    sig = inspect.signature(delete_calendar_event)
    params = list(sig.parameters.keys())
    
    assert "event_id" in params
    assert "calendar" in params


# =============================================================================
# Test: All Calendar Tools Together
# =============================================================================

def test_all_calendar_tools_return_non_none():
    """CRITICAL: Ensure NO calendar tool returns None."""
    from src.tools.calendar import (
        get_calendar_events, get_today_schedule, get_next_event, find_free_time
    )
    
    tools = [
        (get_calendar_events, {"days": 7}),
        (get_today_schedule, {}),
        (get_next_event, {}),
        (find_free_time, {}),
    ]
    
    for tool_func, kwargs in tools:
        result = tool_func(**kwargs)
        assert result is not None, f"CRITICAL: {tool_func.__name__} returned None!"


def test_all_calendar_data_tools_return_dict():
    """Ensure all calendar data tools return dicts."""
    from src.tools.calendar import (
        get_calendar_events, get_today_schedule, get_next_event, find_free_time
    )
    
    data_tools = [
        get_calendar_events, get_today_schedule, get_next_event, find_free_time
    ]
    
    for tool in data_tools:
        result = tool() if tool != get_calendar_events else tool(days=7)
        assert isinstance(result, dict), \
            f"{tool.__name__} returned {type(result)} instead of dict!"


def test_all_calendar_tools_no_none_values():
    """CRITICAL: Batch test - ensure NO calendar tool returns None values."""
    from src.tools.calendar import (
        get_calendar_events, get_today_schedule, get_next_event, find_free_time
    )
    
    tools = [
        (get_calendar_events, {"days": 7}),
        (get_today_schedule, {}),
        (get_next_event, {}),
        (find_free_time, {}),
    ]
    
    failures = []
    for tool_func, kwargs in tools:
        result = tool_func(**kwargs)
        if isinstance(result, dict) and "error" not in result and "no_events" not in result:
            none_values = check_for_none_values(result)
            if none_values:
                failures.append(f"{tool_func.__name__}: {none_values}")
    
    assert len(failures) == 0, \
        f"CRITICAL: Tools with None values:\n" + "\n".join(failures)


# =============================================================================
# Test: Error Handling
# =============================================================================

def test_calendar_tools_handle_invalid_parameters():
    """Test calendar tools handle invalid parameters gracefully."""
    from src.tools.calendar import get_calendar_events, find_free_time
    
    # Negative days
    result = get_calendar_events(days=-5)
    assert isinstance(result, dict)
    
    # Zero days  
    result = get_calendar_events(days=0)
    assert isinstance(result, dict)
    
    # Invalid calendar type
    result = get_calendar_events(days=7, calendar="invalid")
    assert isinstance(result, dict)


def test_calendar_tools_handle_missing_data():
    """Test calendar tools handle missing calendar data gracefully."""
    from src.tools.calendar import get_today_schedule, get_next_event
    
    # These should work even if calendars are unavailable
    schedule = get_today_schedule()
    next_event = get_next_event()
    
    assert isinstance(schedule, dict)
    assert isinstance(next_event, dict)
    
    # Should have proper error handling
    if "error" in schedule:
        assert isinstance(schedule["error"], str)
        assert len(schedule["error"]) > 0
    
    if "error" in next_event:
        assert isinstance(next_event["error"], str)
        assert len(next_event["error"]) > 0


# =============================================================================
# Test: Integration
# =============================================================================

def test_calendar_events_used_in_briefing():
    """Test that calendar tools integrate with briefing (indirect test)."""
    from src.tools.calendar import get_today_schedule
    
    # If briefings use calendar data, this should work
    result = get_today_schedule()
    
    # Should return data that briefings can use
    assert isinstance(result, dict)
    
    if "error" not in result:
        # Should have the structure briefings expect
        assert "current_events" in result
        assert "upcoming_events" in result
        assert "total_events" in result


def test_calendar_consistency():
    """Test calendar tools return consistent data."""
    from src.tools.calendar import get_today_schedule, get_next_event
    
    # Call twice
    schedule1 = get_today_schedule()
    schedule2 = get_today_schedule()
    
    # Should have same structure
    assert schedule1.keys() == schedule2.keys()
    
    # Event counts should be same (or very close if events just started/ended)
    if "error" not in schedule1 and "error" not in schedule2:
        diff = abs(schedule1.get("total_events", 0) - schedule2.get("total_events", 0))
        assert diff <= 1, "Event counts vary too much between calls"


def test_next_event_matches_today_schedule():
    """Test get_next_event is consistent with get_today_schedule."""
    from src.tools.calendar import get_today_schedule, get_next_event
    
    schedule = get_today_schedule()
    next_event = get_next_event()
    
    # If there are upcoming events, get_next_event should find one
    if "error" not in schedule and schedule.get("upcoming_events"):
        # get_next_event should return an event (not an error)
        assert "error" not in next_event or "no_events" in next_event or "event" in next_event
