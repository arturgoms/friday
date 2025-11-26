"""Integration tests for calendar services."""
import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
class TestCalendarIntegration:
    """Test calendar integration via API."""
    
    def test_calendar_today_query(self, api_client, check_api_running):
        """Test asking for today's calendar."""
        response = api_client.chat("What's on my calendar today?")
        
        answer = response["answer"].lower()
        
        # Should mention calendar/schedule/events
        assert any(word in answer for word in ["calendar", "schedule", "event", "today"]), \
            f"Answer should mention calendar/schedule, got: {answer[:200]}"
    
    def test_calendar_tomorrow_query(self, api_client, check_api_running):
        """Test asking for tomorrow's calendar."""
        response = api_client.chat("What do I have tomorrow?")
        
        answer = response["answer"].lower()
        
        # Should mention tomorrow
        assert "tomorrow" in answer or "no events" in answer or "nothing" in answer, \
            f"Answer should address tomorrow's schedule, got: {answer[:200]}"
    
    def test_calendar_next_event_query(self, api_client, check_api_running):
        """Test asking for next event."""
        response = api_client.chat("What's my next event?")
        
        answer = response["answer"]
        
        # Should have meaningful response
        assert len(answer) > 20, "Should have substantial answer"
        assert any(word in answer.lower() for word in ["event", "meeting", "calendar", "no", "nothing"]), \
            "Should mention events or lack thereof"
    
    def test_calendar_week_query(self, api_client, check_api_running):
        """Test asking for this week's schedule."""
        response = api_client.chat("Show me my schedule for this week")
        
        answer = response["answer"]
        
        # Should respond about the week
        assert len(answer) > 20
        assert any(word in answer.lower() for word in ["week", "schedule", "event", "calendar"]), \
            "Should address weekly schedule"


@pytest.mark.integration
class TestCalendarTools:
    """Test calendar tool execution."""
    
    def test_specific_date_query(self, api_client, check_api_running):
        """Test asking about specific date."""
        # Ask about a date in the future
        future_date = (datetime.now() + timedelta(days=7)).strftime("%B %d")
        
        response = api_client.chat(f"Do I have anything on {future_date}?")
        
        answer = response["answer"]
        assert len(answer) > 0, "Should respond to specific date query"
    
    def test_time_until_next_event(self, api_client, check_api_running):
        """Test asking when next event is."""
        response = api_client.chat("When is my next meeting?")
        
        answer = response["answer"].lower()
        
        # Should mention time or no events
        assert any(word in answer for word in [
            "next", "event", "meeting", "no", "nothing", "don't have", 
            "hour", "minute", "day", "tomorrow", "today"
        ]), f"Should mention timing or no events, got: {answer[:200]}"
