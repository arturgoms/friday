"""Integration tests for health coach / Garmin integration."""
import pytest


@pytest.mark.integration
@pytest.mark.health
class TestHealthCoachQueries:
    """Test health coach queries via API."""
    
    def test_sleep_query(self, api_client, check_api_running):
        """Test asking about sleep."""
        response = api_client.chat("How did I sleep last night?")
        
        answer = response["answer"].lower()
        
        # Should mention sleep
        assert any(word in answer for word in ["sleep", "rest", "hours", "night"]), \
            f"Answer should mention sleep, got: {answer[:200]}"
    
    def test_training_readiness_query(self, api_client, check_api_running):
        """Test asking about training readiness."""
        response = api_client.chat("What's my training readiness?")
        
        answer = response["answer"].lower()
        
        # Should mention readiness or training
        assert any(word in answer for word in ["training", "readiness", "ready", "workout"]), \
            f"Answer should mention training readiness, got: {answer[:200]}"
    
    def test_hrv_query(self, api_client, check_api_running):
        """Test asking about HRV."""
        response = api_client.chat("What's my HRV today?")
        
        answer = response["answer"].lower()
        
        # Should mention HRV or heart rate variability
        assert any(word in answer for word in ["hrv", "heart", "variability", "recovery"]), \
            f"Answer should mention HRV, got: {answer[:200]}"
    
    def test_body_battery_query(self, api_client, check_api_running):
        """Test asking about body battery."""
        response = api_client.chat("What's my body battery?")
        
        answer = response["answer"].lower()
        
        # Should mention body battery or energy
        assert any(word in answer for word in ["body battery", "battery", "energy"]), \
            f"Answer should mention body battery, got: {answer[:200]}"
    
    def test_running_stats_query(self, api_client, check_api_running):
        """Test asking about running stats."""
        response = api_client.chat("Show me my running stats for last week")
        
        answer = response["answer"].lower()
        
        # Should mention running or activities
        assert any(word in answer for word in ["run", "running", "distance", "pace", "activity"]), \
            f"Answer should mention running stats, got: {answer[:200]}"
    
    def test_steps_query(self, api_client, check_api_running):
        """Test asking about steps."""
        response = api_client.chat("How many steps today?")
        
        answer = response["answer"].lower()
        
        # Should mention steps or walking
        assert any(word in answer for word in ["step", "walk", "activity", "today"]), \
            f"Answer should mention steps, got: {answer[:200]}"


@pytest.mark.integration
@pytest.mark.health
@pytest.mark.slow
class TestHealthDataAvailability:
    """Test that health data is available and accessible."""
    
    def test_comprehensive_health_summary(self, api_client, check_api_running):
        """Test asking for comprehensive health summary."""
        response = api_client.chat("Give me a summary of my health data today")
        
        answer = response["answer"]
        
        # Should have substantial content
        assert len(answer) > 100, "Health summary should be comprehensive"
        
        # Should mention multiple health metrics
        answer_lower = answer.lower()
        health_terms = ["sleep", "heart", "training", "battery", "activity", "steps"]
        found_terms = [term for term in health_terms if term in answer_lower]
        
        assert len(found_terms) >= 2, \
            f"Health summary should mention multiple metrics, found: {found_terms}"
    
    def test_recovery_status_query(self, api_client, check_api_running):
        """Test asking about recovery status."""
        response = api_client.chat("Am I recovered from yesterday's workout?")
        
        answer = response["answer"].lower()
        
        # Should address recovery
        assert any(word in answer for word in [
            "recover", "recovery", "rest", "ready", "train"
        ]), f"Should address recovery, got: {answer[:200]}"


@pytest.mark.integration
@pytest.mark.health
class TestHealthCoachReports:
    """Test health coach scheduled reports."""
    
    def test_morning_report_content(self, api_client, check_api_running):
        """Test that morning report endpoint works."""
        # This would require a dedicated endpoint or manual trigger
        # For now, test via chat query
        response = api_client.chat("Give me my morning health report")
        
        answer = response["answer"]
        
        # Should have comprehensive content
        assert len(answer) > 50, "Morning report should be substantial"
    
    def test_evening_report_content(self, api_client, check_api_running):
        """Test evening report via query."""
        response = api_client.chat("Give me my evening health summary")
        
        answer = response["answer"]
        
        # Should have content
        assert len(answer) > 50, "Evening report should be substantial"
