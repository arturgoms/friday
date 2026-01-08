"""
Tests for daily briefing tools.

These tests validate that morning and evening briefing reports are generated
correctly and contain all expected sections.
"""

import pytest


# =============================================================================
# Test: report_morning_briefing
# =============================================================================

def test_report_morning_briefing_returns_string():
    """Test morning briefing returns a string."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Must return a string (not None!)
    assert isinstance(result, str), "Morning briefing returned None or non-string!"
    assert len(result) > 0, "Morning briefing returned empty string!"


def test_report_morning_briefing_never_none():
    """Ensure morning briefing never returns None."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    assert result is not None, "CRITICAL: Morning briefing returned None!"


def test_report_morning_briefing_has_greeting():
    """Test morning briefing contains greeting."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have a greeting
    assert "Good morning" in result or "morning" in result.lower(), \
        "Morning briefing missing greeting"
    
    # Should include user name
    assert "Artur" in result, "Morning briefing missing user name"


def test_report_morning_briefing_has_sleep_section():
    """Test morning briefing contains sleep section."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have sleep section
    assert "SLEEP" in result or "Sleep" in result, \
        "Morning briefing missing sleep section"
    
    # Should have sleep-related keywords (if data available)
    has_sleep_content = any(word in result for word in [
        "Score:", "Duration:", "HRV:", "RHR:", 
        "No sleep data", "unavailable"
    ])
    assert has_sleep_content, "Morning briefing missing sleep content"


def test_report_morning_briefing_has_energy_section():
    """Test morning briefing contains energy section."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have energy section
    assert "ENERGY" in result or "Energy" in result, \
        "Morning briefing missing energy section"
    
    # Should have energy-related keywords (if data available)
    has_energy_content = any(word in result for word in [
        "Body Battery", "Training Readiness", 
        "data not available", "unavailable"
    ])
    assert has_energy_content, "Morning briefing missing energy content"


def test_report_morning_briefing_has_schedule_section():
    """Test morning briefing contains schedule section."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have schedule section
    assert "SCHEDULE" in result or "Schedule" in result, \
        "Morning briefing missing schedule section"
    
    # Should have schedule-related keywords
    has_schedule_content = any(word in result for word in [
        "event", "meeting", "No events", "unavailable", "Calendar"
    ])
    assert has_schedule_content, "Morning briefing missing schedule content"


def test_report_morning_briefing_has_weather_section():
    """Test morning briefing contains weather section."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have weather section
    assert "WEATHER" in result or "Weather" in result, \
        "Morning briefing missing weather section"
    
    # Should have weather-related keywords (if data available)
    has_weather_content = any(word in result for word in [
        "°C", "Condition:", "Humidity:", 
        "unavailable", "Weather data"
    ])
    assert has_weather_content, "Morning briefing missing weather content"


def test_report_morning_briefing_length():
    """Test morning briefing has reasonable length."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should be substantial (at least 200 chars with all sections)
    assert len(result) >= 200, \
        f"Morning briefing too short ({len(result)} chars), may be missing sections"
    
    # Should not be excessively long
    assert len(result) <= 5000, \
        f"Morning briefing too long ({len(result)} chars), may have repeated content"


def test_report_morning_briefing_has_insights_or_warnings():
    """Test morning briefing may contain insights section."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # May have insights/warnings section (optional, depends on data)
    # Just verify it doesn't break if this section exists
    if "FOR TODAY" in result or "💡" in result:
        # If insights section exists, it should have content
        assert "⚠️" in result or "✨" in result, \
            "Insights section exists but has no warnings or insights"


def test_report_morning_briefing_formatting():
    """Test morning briefing has proper formatting."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should have proper line breaks
    assert "\n" in result, "Morning briefing missing line breaks"
    
    # Should have section headers (all caps or title case)
    lines = result.split("\n")
    has_headers = any(line.isupper() or line.startswith("🛏️") or line.startswith("🔋") 
                      for line in lines if line.strip())
    assert has_headers, "Morning briefing missing section headers"


# =============================================================================
# Test: report_evening_briefing
# =============================================================================

def test_report_evening_briefing_returns_string():
    """Test evening briefing returns a string."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Must return a string (not None!)
    assert isinstance(result, str), "Evening briefing returned None or non-string!"
    assert len(result) > 0, "Evening briefing returned empty string!"


def test_report_evening_briefing_never_none():
    """Ensure evening briefing never returns None."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    assert result is not None, "CRITICAL: Evening briefing returned None!"


def test_report_evening_briefing_has_greeting():
    """Test evening briefing contains greeting."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have a greeting
    assert "Good evening" in result or "evening" in result.lower(), \
        "Evening briefing missing greeting"
    
    # Should include user name
    assert "Artur" in result, "Evening briefing missing user name"


def test_report_evening_briefing_has_activity_section():
    """Test evening briefing contains activity section."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have activity section
    assert "ACTIVITY" in result or "Activity" in result, \
        "Evening briefing missing activity section"
    
    # Should have activity-related keywords
    has_activity_content = any(word in result for word in [
        "Steps:", "Distance:", "km", "cal"
    ])
    assert has_activity_content, "Evening briefing missing activity content"


def test_report_evening_briefing_has_stress_section():
    """Test evening briefing contains stress section."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have stress section
    assert "STRESS" in result or "Stress" in result, \
        "Evening briefing missing stress section"
    
    # Should have stress-related keywords
    has_stress_content = any(word in result for word in [
        "Average:", "stress", "High stress:", "Rest:"
    ])
    assert has_stress_content, "Evening briefing missing stress content"


def test_report_evening_briefing_has_energy_section():
    """Test evening briefing contains energy section."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have energy section
    assert "ENERGY" in result or "Energy" in result, \
        "Evening briefing missing energy section"
    
    # Should have energy-related keywords
    has_energy_content = any(word in result for word in [
        "Current:", "Body Battery", "used", "drain"
    ])
    assert has_energy_content, "Evening briefing missing energy content"


def test_report_evening_briefing_has_meetings_section():
    """Test evening briefing contains meetings section."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have meetings section
    assert "MEETINGS" in result or "Meetings" in result, \
        "Evening briefing missing meetings section"
    
    # Should have meeting-related keywords
    has_meeting_content = any(word in result for word in [
        "meeting", "Calendar", "unavailable"
    ])
    assert has_meeting_content, "Evening briefing missing meeting content"


def test_report_evening_briefing_has_sleep_recommendation():
    """Test evening briefing contains sleep recommendation."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have sleep recommendation section
    assert "SLEEP RECOMMENDATION" in result or "Sleep Recommendation" in result, \
        "Evening briefing missing sleep recommendation section"
    
    # Should have recommendation-related keywords
    has_recommendation_content = any(word in result for word in [
        "bedtime", "Outlook:", "stress", "energy"
    ])
    assert has_recommendation_content, \
        "Evening briefing missing sleep recommendation content"


def test_report_evening_briefing_length():
    """Test evening briefing has reasonable length."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should be substantial (at least 200 chars with all sections)
    assert len(result) >= 200, \
        f"Evening briefing too short ({len(result)} chars), may be missing sections"
    
    # Should not be excessively long
    assert len(result) <= 5000, \
        f"Evening briefing too long ({len(result)} chars), may have repeated content"


def test_report_evening_briefing_formatting():
    """Test evening briefing has proper formatting."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Should have proper line breaks
    assert "\n" in result, "Evening briefing missing line breaks"
    
    # Should have section headers
    lines = result.split("\n")
    has_headers = any(line.isupper() or line.startswith("🏃") or line.startswith("😰") 
                      for line in lines if line.strip())
    assert has_headers, "Evening briefing missing section headers"


# =============================================================================
# Test: Both Briefings Together
# =============================================================================

def test_both_briefings_return_non_none():
    """Critical test: Ensure both briefings never return None."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    assert morning is not None, "CRITICAL: Morning briefing returned None!"
    assert evening is not None, "CRITICAL: Evening briefing returned None!"


def test_both_briefings_return_strings():
    """Test both briefings return strings."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    assert isinstance(morning, str), "Morning briefing didn't return string!"
    assert isinstance(evening, str), "Evening briefing didn't return string!"


def test_both_briefings_have_different_content():
    """Test morning and evening briefings have different content."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # They should be different reports
    assert morning != evening, "Morning and evening briefings are identical!"
    
    # Morning should have specific content
    assert "Good morning" in morning, "Morning briefing missing morning greeting"
    
    # Evening should have specific content
    assert "Good evening" in evening, "Evening briefing missing evening greeting"


def test_briefings_handle_missing_data_gracefully():
    """Test briefings handle missing data without crashing."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    # Both should work even if some data sources are unavailable
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # Should still produce reports with at least greeting
    assert len(morning) >= 50, "Morning briefing too short when data missing"
    assert len(evening) >= 50, "Evening briefing too short when data missing"


# =============================================================================
# Test: Data Completeness
# =============================================================================

def test_morning_briefing_all_sections_present():
    """Test morning briefing attempts to show all sections."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Count how many main sections are present
    sections = ["SLEEP", "ENERGY", "SCHEDULE", "WEATHER"]
    present_sections = sum(1 for section in sections if section in result)
    
    # Should have at least 3 out of 4 sections (some might be unavailable)
    assert present_sections >= 3, \
        f"Morning briefing only has {present_sections}/4 sections: {sections}"


def test_evening_briefing_all_sections_present():
    """Test evening briefing attempts to show all sections."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Count how many main sections are present
    sections = ["ACTIVITY", "STRESS", "ENERGY", "MEETINGS", "SLEEP RECOMMENDATION"]
    present_sections = sum(1 for section in sections if section in result)
    
    # Should have at least 4 out of 5 sections
    assert present_sections >= 4, \
        f"Evening briefing only has {present_sections}/5 sections: {sections}"


def test_briefings_produce_consistent_output():
    """Test briefings produce consistent output when called multiple times."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    # Call twice in quick succession
    morning1 = report_morning_briefing()
    morning2 = report_morning_briefing()
    
    evening1 = report_evening_briefing()
    evening2 = report_evening_briefing()
    
    # Should be very similar (allowing for minor timestamp differences)
    # At minimum, should have same sections
    assert "SLEEP" in morning1 and "SLEEP" in morning2
    assert "ACTIVITY" in evening1 and "ACTIVITY" in evening2


# =============================================================================
# Test: Integration with Dependencies
# =============================================================================

def test_briefings_integrate_with_health_tools():
    """Test briefings successfully call health tools."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # Morning should show health data (sleep, body battery)
    has_health_data = any(word in morning for word in [
        "Score:", "Body Battery", "HRV", "RHR", "Training Readiness"
    ])
    assert has_health_data, "Morning briefing not integrating health data"
    
    # Evening should show activity data
    has_activity_data = any(word in evening for word in [
        "Steps:", "stress", "Body Battery"
    ])
    assert has_activity_data, "Evening briefing not integrating activity data"


def test_briefings_integrate_with_calendar():
    """Test briefings successfully call calendar tools."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # Both should reference calendar/schedule
    assert "SCHEDULE" in morning or "Calendar" in morning, \
        "Morning briefing not integrating calendar"
    assert "MEETINGS" in evening or "meetings" in evening, \
        "Evening briefing not integrating calendar"


def test_briefings_integrate_with_weather():
    """Test morning briefing successfully calls weather tool."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Should reference weather
    assert "WEATHER" in result, "Morning briefing not integrating weather"


# =============================================================================
# Test: None Value Detection (CRITICAL)
# =============================================================================

def test_morning_briefing_no_none_in_output():
    """CRITICAL: Ensure morning briefing doesn't contain 'None' in output."""
    from src.tools.daily_briefing import report_morning_briefing
    
    result = report_morning_briefing()
    
    # Check for literal 'None' string in output
    assert "None" not in result, \
        "CRITICAL: Morning briefing contains 'None' in output!"
    
    # Check for common None representations
    assert "null" not in result.lower(), \
        "Morning briefing contains 'null' in output"


def test_evening_briefing_no_none_in_output():
    """CRITICAL: Ensure evening briefing doesn't contain 'None' in output."""
    from src.tools.daily_briefing import report_evening_briefing
    
    result = report_evening_briefing()
    
    # Check for literal 'None' string in output
    assert "None" not in result, \
        "CRITICAL: Evening briefing contains 'None' in output!"
    
    # Check for common None representations
    assert "null" not in result.lower(), \
        "Evening briefing contains 'null' in output"


def test_briefings_no_missing_data_markers():
    """Test briefings don't show incomplete data markers."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # These patterns suggest missing/None data
    bad_patterns = [
        "None",
        ": None",
        "None/",
        "None ",
    ]
    
    for pattern in bad_patterns:
        assert pattern not in morning, \
            f"Morning briefing contains bad pattern: '{pattern}'"
        assert pattern not in evening, \
            f"Evening briefing contains bad pattern: '{pattern}'"


def test_briefings_have_valid_numeric_values():
    """Test briefings show valid numbers, not None or NaN."""
    from src.tools.daily_briefing import report_morning_briefing, report_evening_briefing
    
    morning = report_morning_briefing()
    evening = report_evening_briefing()
    
    # Check for invalid numeric representations
    invalid_numbers = ["NaN", "nan", "inf", "Infinity"]
    
    for pattern in invalid_numbers:
        assert pattern not in morning, \
            f"Morning briefing contains invalid number: '{pattern}'"
        assert pattern not in evening, \
            f"Evening briefing contains invalid number: '{pattern}'"
