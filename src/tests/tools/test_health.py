"""
Tests for health tools.

These tests validate that health tools return correct data structures
and handle edge cases properly. Tests run against real InfluxDB data
to ensure tools work correctly in production.
"""

import pytest
from datetime import datetime


# =============================================================================
# Test: get_recent_runs
# =============================================================================

def test_get_recent_runs_structure():
    """Test get_recent_runs returns correct structure."""
    from src.tools.health import get_recent_runs
    
    result = get_recent_runs(limit=5, days=30)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Either has data or error
    if "error" in result:
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0
    else:
        # Has valid structure
        assert "runs" in result
        assert "total_runs" in result
        assert "period_days" in result
        assert "timestamp" in result
        
        assert isinstance(result["runs"], list)
        assert isinstance(result["total_runs"], int)
        assert result["period_days"] == 30
        
        # If there are runs, validate structure
        if result["runs"]:
            run = result["runs"][0]
            assert "name" in run
            assert "date" in run
            assert "distance_km" in run
            assert "duration_seconds" in run
            assert "average_speed_mps" in run
            assert "average_hr_bpm" in run
            assert isinstance(run["distance_km"], (int, float))
            assert isinstance(run["duration_seconds"], int)


def test_get_recent_runs_never_none():
    """Ensure get_recent_runs never returns None."""
    from src.tools.health import get_recent_runs
    
    result = get_recent_runs()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_sleep_summary
# =============================================================================

def test_get_sleep_summary_structure():
    """Test get_sleep_summary returns correct structure."""
    from src.tools.health import get_sleep_summary
    
    result = get_sleep_summary(days=7)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    assert "sleep_nights" in result, "Missing 'sleep_nights' key"
    assert "period_days" in result
    assert "average_hours" in result
    assert "average_score" in result
    assert "nap_info" in result, "Missing 'nap_info' key"
    assert "timestamp" in result
    
    # Validate types
    assert isinstance(result["sleep_nights"], list)
    assert isinstance(result["period_days"], int)
    assert isinstance(result["average_hours"], (int, float))
    assert isinstance(result["average_score"], (int, float))
    assert result["period_days"] == 7
    
    # Validate nap_info structure
    nap_info = result["nap_info"]
    assert isinstance(nap_info, dict)
    assert "nap_detected" in nap_info
    assert "nap_duration_minutes" in nap_info
    assert isinstance(nap_info["nap_detected"], bool)
    assert isinstance(nap_info["nap_duration_minutes"], int)
    
    # If nap detected, validate additional fields
    if nap_info["nap_detected"]:
        assert "nap_start" in nap_info
        assert "nap_end" in nap_info
        assert "battery_gain" in nap_info
    
    # If there are nights, validate structure
    if result["sleep_nights"]:
        night = result["sleep_nights"][0]
        assert "date" in night
        assert "total_hours" in night
        assert "score" in night
        assert "deep_seconds" in night
        assert "light_seconds" in night
        assert "rem_seconds" in night
        assert "awake_seconds" in night


def test_get_sleep_summary_never_none():
    """Ensure get_sleep_summary never returns None."""
    from src.tools.health import get_sleep_summary
    
    result = get_sleep_summary()
    assert result is not None, "CRITICAL: Tool returned None!"


def test_get_sleep_summary_with_date_parameter():
    """Test get_sleep_summary accepts date parameter for nap detection."""
    from src.tools.health import get_sleep_summary
    from datetime import datetime, timedelta
    
    # Use yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = get_sleep_summary(days=7, date=yesterday)
    
    assert isinstance(result, dict)
    assert "nap_info" in result
    # nap_info should be for the specified date
    assert isinstance(result["nap_info"], dict)
    assert "nap_detected" in result["nap_info"]


# =============================================================================
# Test: get_recovery_status
# =============================================================================

def test_get_recovery_status_structure():
    """Test get_recovery_status returns correct structure."""
    from src.tools.health import get_recovery_status
    
    result = get_recovery_status()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        assert "timestamp" in result
        assert "training_readiness" in result
        assert "body_battery_at_wake" in result
        assert "overnight_hrv_ms" in result
        
        assert isinstance(result["body_battery_at_wake"], (int, float))
        assert isinstance(result["overnight_hrv_ms"], (int, float))
        assert isinstance(result["training_readiness"], dict)


def test_get_recovery_status_never_none():
    """Ensure get_recovery_status never returns None."""
    from src.tools.health import get_recovery_status
    
    result = get_recovery_status()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_vo2max
# =============================================================================

def test_get_vo2max_structure():
    """Test get_vo2max returns correct structure."""
    from src.tools.health import get_vo2max
    
    result = get_vo2max()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Either has data or error
    if "error" in result:
        assert isinstance(result["error"], str)
    else:
        assert "current" in result
        assert "previous" in result
        assert "trend" in result
        assert isinstance(result["current"], (int, float))


def test_get_vo2max_never_none():
    """Ensure get_vo2max never returns None."""
    from src.tools.health import get_vo2max
    
    result = get_vo2max()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_hrv_trend
# =============================================================================

def test_get_hrv_trend_structure():
    """Test get_hrv_trend returns correct structure."""
    from src.tools.health import get_hrv_trend
    
    result = get_hrv_trend(days=14)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        assert "readings" in result, "Missing 'readings' key"
        assert "current_ms" in result
        assert "average_ms" in result
        assert "min_ms" in result
        assert "max_ms" in result
        assert "trend" in result
        assert "period_days" in result
        
        assert isinstance(result["readings"], list)
        assert isinstance(result["current_ms"], (int, float))
        assert result["period_days"] == 14


def test_get_hrv_trend_never_none():
    """Ensure get_hrv_trend never returns None."""
    from src.tools.health import get_hrv_trend
    
    result = get_hrv_trend()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_stress_levels
# =============================================================================

def test_get_stress_levels_structure():
    """Test get_stress_levels returns correct structure."""
    from src.tools.health import get_stress_levels
    
    result = get_stress_levels(days=7)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    assert "daily_stress" in result, "Missing 'daily_stress' key"
    assert "overall_average" in result
    assert "overall_level" in result
    assert "current_stress" in result
    assert "period_days" in result
    
    assert isinstance(result["daily_stress"], list)
    assert isinstance(result["overall_average"], (int, float))
    assert isinstance(result["overall_level"], str)
    assert result["period_days"] == 7
    
    # If there is daily data, validate structure
    if result["daily_stress"]:
        day = result["daily_stress"][0]
        assert "date" in day
        assert "average" in day


def test_get_stress_levels_never_none():
    """Ensure get_stress_levels never returns None."""
    from src.tools.health import get_stress_levels
    
    result = get_stress_levels()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_heart_rate_summary
# =============================================================================

def test_get_heart_rate_summary_structure():
    """Test get_heart_rate_summary returns correct structure."""
    from src.tools.health import get_heart_rate_summary
    
    result = get_heart_rate_summary(days=14)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        assert "readings" in result, "Missing 'readings' key"
        assert "average_rhr_bpm" in result
        assert "min_rhr_bpm" in result
        assert "max_rhr_bpm" in result
        assert "health_level" in result
        assert "period_days" in result
        
        assert isinstance(result["readings"], list)
        assert isinstance(result["average_rhr_bpm"], (int, float))
        assert result["period_days"] == 14


def test_get_heart_rate_summary_never_none():
    """Ensure get_heart_rate_summary never returns None."""
    from src.tools.health import get_heart_rate_summary
    
    result = get_heart_rate_summary()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_activity_summary
# =============================================================================

def test_get_activity_summary_structure():
    """Test get_activity_summary returns correct structure."""
    from src.tools.health import get_activity_summary
    
    result = get_activity_summary(days=7)
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    assert "steps" in result, "Missing 'steps' key"
    assert "workouts" in result
    assert "workout_count" in result
    assert "period_days" in result
    
    assert isinstance(result["steps"], dict)
    assert isinstance(result["workouts"], list)
    assert isinstance(result["workout_count"], int)
    assert result["period_days"] == 7


def test_get_activity_summary_never_none():
    """Ensure get_activity_summary never returns None."""
    from src.tools.health import get_activity_summary
    
    result = get_activity_summary()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_steps
# =============================================================================

def test_get_steps_structure():
    """Test get_steps returns correct structure."""
    from src.tools.health import get_steps
    
    result = get_steps()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys
    assert "today" in result
    assert "average_30d" in result
    assert "vs_average" in result
    assert "vs_average_percent" in result
    
    assert isinstance(result["today"], int)
    assert isinstance(result["average_30d"], (int, float))
    assert isinstance(result["vs_average"], int)


def test_get_steps_never_none():
    """Ensure get_steps never returns None."""
    from src.tools.health import get_steps
    
    result = get_steps()
    assert result is not None, "CRITICAL: Tool returned None!"


def test_get_steps_with_date():
    """Test get_steps with specific date."""
    from src.tools.health import get_steps
    from datetime import datetime, timedelta
    
    # Use yesterday's date to ensure data exists
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = get_steps(date=yesterday)
    
    assert isinstance(result, dict)
    # May have data or error depending on sync
    assert "today" in result or "error" in result


# =============================================================================
# Test: get_body_battery
# =============================================================================

def test_get_body_battery_structure():
    """Test get_body_battery returns correct structure."""
    from src.tools.health import get_body_battery
    
    result = get_body_battery()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        assert "start" in result
        assert "end" in result
        assert "current" in result
        assert "min" in result
        assert "max" in result
        assert "readings_count" in result
        
        assert isinstance(result["start"], int)
        assert isinstance(result["current"], int)
        assert isinstance(result["min"], int)
        assert isinstance(result["max"], int)
        
        # start is the first reading (midnight), max is peak after sleep
        assert result["start"] <= result["max"], \
            "Body battery 'start' should be <= 'max'"


def test_get_body_battery_never_none():
    """Ensure get_body_battery never returns None."""
    from src.tools.health import get_body_battery
    
    result = get_body_battery()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_stress
# =============================================================================

def test_get_stress_structure():
    """Test get_stress returns correct structure with rest/stress hours."""
    from src.tools.health import get_stress
    
    result = get_stress()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        # Basic stats
        assert "average" in result
        assert "min" in result
        assert "max" in result
        assert "current" in result
        assert "readings_count" in result
        
        # New rest/stress breakdown
        assert "rest_hours" in result, "Missing rest_hours key"
        assert "stress_hours" in result, "Missing stress_hours key"
        assert "rest_pct" in result, "Missing rest_pct key"
        assert "stress_pct" in result, "Missing stress_pct key"
        
        assert isinstance(result["average"], int)
        assert isinstance(result["current"], int)
        assert isinstance(result["rest_hours"], (int, float))
        assert isinstance(result["stress_hours"], (int, float))
        assert isinstance(result["rest_pct"], int)
        assert isinstance(result["stress_pct"], int)
        
        # Percentages should add up to 100
        assert result["rest_pct"] + result["stress_pct"] == 100, "rest_pct + stress_pct should equal 100"


def test_get_stress_never_none():
    """Ensure get_stress never returns None."""
    from src.tools.health import get_stress
    
    result = get_stress()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: get_garmin_sync_status
# =============================================================================

def test_get_garmin_sync_status_structure():
    """Test get_garmin_sync_status returns correct structure."""
    from src.tools.health import get_garmin_sync_status
    
    result = get_garmin_sync_status()
    
    # Must be a dict (never None!)
    assert isinstance(result, dict), "Tool returned None instead of dict!"
    
    # Check required keys (based on actual API)
    if "error" not in result:
        assert "status" in result, "Missing 'status' key"
        assert "last_sync_time" in result
        assert "hours_ago" in result
        assert "timestamp" in result
        
        assert isinstance(result["status"], str)
        assert isinstance(result["hours_ago"], (int, float))


def test_get_garmin_sync_status_never_none():
    """Ensure get_garmin_sync_status never returns None."""
    from src.tools.health import get_garmin_sync_status
    
    result = get_garmin_sync_status()
    assert result is not None, "CRITICAL: Tool returned None!"


# =============================================================================
# Test: Composite Report Tools
# =============================================================================

def test_report_training_load_returns_string():
    """Test report_training_load returns a string."""
    from src.tools.health import report_training_load
    
    result = report_training_load(weeks=4)
    
    # Must return a string (not None!)
    assert isinstance(result, str), "Report returned None or non-string!"
    assert len(result) > 0, "Report returned empty string!"
    
    # Should contain some report keywords
    assert any(word in result for word in ["Training", "Load", "Week", "km", "No data"]), \
        "Report doesn't contain expected content"


def test_report_training_load_never_none():
    """Ensure report_training_load never returns None."""
    from src.tools.health import report_training_load
    
    result = report_training_load()
    assert result is not None, "CRITICAL: Report returned None!"


def test_report_weekly_health_returns_string():
    """Test report_weekly_health returns a string."""
    from src.tools.health import report_weekly_health
    
    result = report_weekly_health(weeks_ago=0)
    
    # Must return a string (not None!)
    assert isinstance(result, str), "Report returned None or non-string!"
    assert len(result) > 0, "Report returned empty string!"
    
    # Should contain some report keywords
    assert any(word in result for word in ["Health", "Sleep", "Week", "Steps"]), \
        "Report doesn't contain expected content"


def test_report_weekly_health_never_none():
    """Ensure report_weekly_health never returns None."""
    from src.tools.health import report_weekly_health
    
    result = report_weekly_health()
    assert result is not None, "CRITICAL: Report returned None!"


# =============================================================================
# Test: Data Completeness
# =============================================================================

def test_all_tools_return_non_none():
    """Critical test: Ensure NO tool returns None."""
    from src.tools.health import (
        get_recent_runs, get_sleep_summary, get_recovery_status, get_vo2max,
        get_hrv_trend, get_stress_levels, get_heart_rate_summary, 
        get_activity_summary, get_steps, get_body_battery, get_stress,
        get_garmin_sync_status, report_training_load, report_weekly_health
    )
    
    tools = [
        (get_recent_runs, {"limit": 5, "days": 7}),
        (get_sleep_summary, {"days": 7}),
        (get_recovery_status, {}),
        (get_vo2max, {}),
        (get_hrv_trend, {"days": 7}),
        (get_stress_levels, {"days": 7}),
        (get_heart_rate_summary, {"days": 7}),
        (get_activity_summary, {"days": 7}),
        (get_steps, {}),
        (get_body_battery, {}),
        (get_stress, {}),
        (get_garmin_sync_status, {}),
        (report_training_load, {"weeks": 2}),
        (report_weekly_health, {"weeks_ago": 0}),
    ]
    
    for tool_func, kwargs in tools:
        result = tool_func(**kwargs)
        assert result is not None, f"CRITICAL: {tool_func.__name__} returned None!"


def test_all_data_tools_return_dict():
    """Ensure all data tools return dicts (not strings or None)."""
    from src.tools.health import (
        get_recent_runs, get_sleep_summary, get_recovery_status, get_vo2max,
        get_hrv_trend, get_stress_levels, get_heart_rate_summary, 
        get_activity_summary, get_steps, get_body_battery, get_stress,
        get_garmin_sync_status
    )
    
    data_tools = [
        get_recent_runs, get_sleep_summary, get_recovery_status, get_vo2max,
        get_hrv_trend, get_stress_levels, get_heart_rate_summary,
        get_activity_summary, get_steps, get_body_battery, get_stress,
        get_garmin_sync_status
    ]
    
    for tool in data_tools:
        result = tool() if tool != get_recent_runs else tool(limit=5)
        assert isinstance(result, dict), \
            f"{tool.__name__} returned {type(result)} instead of dict!"


def test_all_report_tools_return_string():
    """Ensure all report tools return strings (not dicts or None)."""
    from src.tools.health import report_training_load, report_weekly_health
    
    report_tools = [report_training_load, report_weekly_health]
    
    for tool in report_tools:
        result = tool() if tool != report_training_load else tool(weeks=2)
        assert isinstance(result, str), \
            f"{tool.__name__} returned {type(result)} instead of string!"


# =============================================================================
# Test: None Value Detection (CRITICAL)
# =============================================================================

def check_for_none_values(data, path='', parent_key=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path, key))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path, parent_key))
    
    return none_found


def test_sleep_summary_no_none_values():
    """CRITICAL: Ensure get_sleep_summary has no None values in response."""
    from src.tools.health import get_sleep_summary
    
    result = get_sleep_summary(days=7)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_sleep_summary has None values at: {none_values}"


def test_recovery_status_no_none_values():
    """CRITICAL: Ensure get_recovery_status has no None values in response."""
    from src.tools.health import get_recovery_status
    
    result = get_recovery_status()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_recovery_status has None values at: {none_values}"


def test_hrv_trend_no_none_values():
    """CRITICAL: Ensure get_hrv_trend has no None values in response."""
    from src.tools.health import get_hrv_trend
    
    result = get_hrv_trend(days=7)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_hrv_trend has None values at: {none_values}"


def test_stress_levels_no_none_values():
    """CRITICAL: Ensure get_stress_levels has no None values in response."""
    from src.tools.health import get_stress_levels
    
    result = get_stress_levels(days=7)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_stress_levels has None values at: {none_values}"


def test_activity_summary_no_none_values():
    """CRITICAL: Ensure get_activity_summary has no None values in response."""
    from src.tools.health import get_activity_summary
    
    result = get_activity_summary(days=7)
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_activity_summary has None values at: {none_values}"


def test_body_battery_no_none_values():
    """CRITICAL: Ensure get_body_battery has no None values in response."""
    from src.tools.health import get_body_battery
    
    result = get_body_battery()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_body_battery has None values at: {none_values}"


def test_steps_no_none_values():
    """CRITICAL: Ensure get_steps has no None values in response."""
    from src.tools.health import get_steps
    
    result = get_steps()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_steps has None values at: {none_values}"


def test_all_health_tools_no_none_values():
    """CRITICAL: Batch test - ensure NO health tool returns None values."""
    from src.tools.health import (
        get_recent_runs, get_sleep_summary, get_recovery_status, get_vo2max,
        get_hrv_trend, get_stress_levels, get_heart_rate_summary, 
        get_activity_summary, get_steps, get_body_battery, get_stress,
        get_garmin_sync_status
    )
    
    tools = [
        (get_recent_runs, {"limit": 5, "days": 7}),
        (get_sleep_summary, {"days": 7}),
        (get_recovery_status, {}),
        (get_vo2max, {}),
        (get_hrv_trend, {"days": 7}),
        (get_stress_levels, {"days": 7}),
        (get_heart_rate_summary, {"days": 7}),
        (get_activity_summary, {"days": 7}),
        (get_steps, {}),
        (get_body_battery, {}),
        (get_stress, {}),
        (get_garmin_sync_status, {}),
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
# Test: Error Handling
# =============================================================================

def test_tools_handle_invalid_parameters():
    """Test tools handle invalid parameters gracefully."""
    from src.tools.health import get_sleep_summary, get_hrv_trend, get_steps
    
    # Negative days - tools should still return dict
    result = get_sleep_summary(days=-5)
    assert isinstance(result, dict)
    
    # Zero days - tools should still return dict
    result = get_hrv_trend(days=0)
    assert isinstance(result, dict)
    
    # Invalid date format - should raise ValueError, which is expected behavior
    # We test that it raises an exception rather than returning None
    try:
        result = get_steps(date="invalid-date")
        # If it doesn't raise, it should at least return a dict
        assert isinstance(result, dict)
    except ValueError:
        # Expected behavior - tool validates date format
        pass
