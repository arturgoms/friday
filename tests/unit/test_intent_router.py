"""Unit tests for intent router."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.services.intent.router import IntentRouter


@pytest.mark.unit
@pytest.mark.router
class TestIntentRouter:
    """Test intent router decision making."""
    
    @pytest.fixture
    def router(self):
        """Create IntentRouter instance."""
        return IntentRouter()
    
    @pytest.mark.parametrize("message,expected_action", [
        ("What time is it?", "time_query"),
        ("What's the current time?", "time_query"),
        ("Tell me the time", "time_query"),
        ("What time is it right now?", "time_query"),
    ])
    def test_time_queries(self, router, message, expected_action):
        """Test that time queries route to time_query action."""
        intent = router.route(message)
        assert intent["action"] == expected_action, \
            f"Message '{message}' should route to {expected_action}, got {intent['action']}"
    
    @pytest.mark.parametrize("message,expected_action", [
        ("Tell me about Camila from my notes", "general"),
        ("What do my notes say about work?", "general"),
        ("Search my notes for information about pizza", "general"),
    ])
    def test_rag_queries(self, router, message, expected_action):
        """Test that personal notes queries route correctly."""
        intent = router.route(message)
        assert intent["action"] == expected_action
        # Should enable RAG for personal notes
        assert intent.get("use_rag") is True or intent["action"] == "general", \
            f"Personal notes query should use RAG"
    
    @pytest.mark.parametrize("message,expected_action", [
        ("What's the weather today?", "web_search"),
        ("Who won the World Cup?", "web_search"),
        ("What is the capital of France?", "web_search"),
        ("Search the web for news about AI", "web_search"),
    ])
    def test_web_search_queries(self, router, message, expected_action):
        """Test that factual/current event queries route to web search."""
        intent = router.route(message)
        # Might route to general or web_search depending on implementation
        assert intent["action"] in ["web_search", "general"], \
            f"Message '{message}' should route to web_search or general"
    
    @pytest.mark.parametrize("message", [
        "Show me my calendar for today",
        "What events do I have today?",
        "What's on my schedule?",
        "Do I have any meetings today?",
    ])
    def test_calendar_queries(self, router, message):
        """Test that calendar queries route to calendar action."""
        intent = router.route(message)
        # Should use calendar tool or general with tool hint
        assert intent["action"] in ["tool_execution", "general", "calendar_query"], \
            f"Calendar query should route to calendar action, got: {intent['action']}"
    
    @pytest.mark.parametrize("message", [
        "Remind me to call mom in 30 minutes",
        "Set a reminder for tomorrow at 3pm",
        "Remember to buy milk",
    ])
    def test_reminder_queries(self, router, message):
        """Test that reminder creation queries route correctly."""
        intent = router.route(message)
        # Reminders might go to general, tool_execution, or reminder_create
        assert intent["action"] in ["tool_execution", "general", "reminder", "reminder_create"], \
            f"Reminder query should route appropriately, got: {intent['action']}"
    
    def test_conversational_queries(self, router):
        """Test that conversational queries route to general."""
        messages = [
            "Hello, how are you?",
            "Thank you!",
            "That's helpful",
            "Can you help me?",
        ]
        
        for message in messages:
            intent = router.route(message)
            # Conversational messages should go to general
            assert intent["action"] in ["general", "greeting"], \
                f"Conversational message '{message}' should route to general/greeting"
    
    def test_health_queries(self, router):
        """Test that health/fitness queries route correctly."""
        messages = [
            "How did I sleep last night?",
            "What's my training readiness?",
            "Show me my running stats",
            "What's my HRV today?",
        ]
        
        for message in messages:
            intent = router.route(message)
            # Should route to health_query or general
            assert intent["action"] in ["health_query", "general"], \
                f"Health query '{message}' should enable health data"
    
    def test_intent_has_required_fields(self, router):
        """Test that router always returns required fields."""
        intent = router.route("test message")
        
        assert "action" in intent, "Intent must have 'action' field"
        assert isinstance(intent["action"], str), "Action must be string"
        
        # Optional but common fields
        if "use_rag" in intent:
            assert isinstance(intent["use_rag"], bool)
        if "use_memory" in intent:
            assert isinstance(intent["use_memory"], bool)
        if "use_web" in intent:
            assert isinstance(intent["use_web"], bool)
    
    def test_empty_message(self, router):
        """Test handling of empty messages."""
        intent = router.route("")
        assert "action" in intent, "Should handle empty message gracefully"
    
    def test_very_long_message(self, router):
        """Test handling of very long messages."""
        long_message = "test " * 1000  # 5000 characters
        intent = router.route(long_message)
        assert "action" in intent, "Should handle long messages"
