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
    
    @pytest.mark.parametrize("message", [
        "Tell me about Camila from my notes",
        "What do my notes say about work?",
        "Search my notes for information about pizza",
    ])
    def test_rag_queries(self, router, message):
        """Test that personal notes queries route correctly."""
        intent = router.route(message)
        # Should route to general, note_search, or similar RAG-enabled action
        assert intent["action"] in ["general", "note_search", "rag_query"], \
            f"Personal notes query '{message}' should route to RAG-enabled action, got: {intent['action']}"
        # Should enable RAG for personal notes
        assert intent.get("use_rag") is True or intent["action"] in ["general", "note_search"], \
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
        "Remember to send the email in an hour",
    ])
    def test_reminder_queries(self, router, message):
        """Test that reminder creation queries (with time) route to reminder_create."""
        intent = router.route(message)
        assert intent["action"] == "reminder_create", \
            f"Reminder query with time should route to reminder_create, got: {intent['action']}"
        assert intent.get("reminder_data") is not None, \
            "Reminder should have reminder_data"
    
    @pytest.mark.parametrize("message", [
        "Remember that I like pizza",
        "Remember my favorite color is black",
        "Remember that Camila is my wife",
    ])
    def test_memory_save_queries(self, router, message):
        """Test that 'remember that' (facts) route to memory_save."""
        intent = router.route(message)
        assert intent["action"] == "memory_save", \
            f"Memory save query should route to memory_save, got: {intent['action']}"
        assert intent.get("memory_data") is not None, \
            "Memory save should have memory_data"
    
    def test_know_phrasing_routes_to_memory_or_general(self, router):
        """Test that 'I want you to know...' phrasings are handled reasonably.
        
        These may route to memory_save or general depending on LLM interpretation.
        Both are acceptable since memory extraction happens in post-processing.
        """
        intent = router.route("I want you to know I work at Counterpart")
        assert intent["action"] in ["memory_save", "general"], \
            f"Should route to memory_save or general, got: {intent['action']}"
    
    @pytest.mark.parametrize("message", [
        "Remember to buy milk",
        "Remember to call mom",
    ])
    def test_ambiguous_remember_queries(self, router, message):
        """Test that 'remember to [action]' without time routes to memory_ambiguous."""
        intent = router.route(message)
        assert intent["action"] == "memory_ambiguous", \
            f"Ambiguous 'remember to' (no time) should route to memory_ambiguous, got: {intent['action']}"
        assert intent.get("memory_data") is not None, \
            "Ambiguous query should have memory_data for clarification"
    
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
            # Should route to health_query, body_health_check, or general
            assert intent["action"] in ["health_query", "body_health_check", "general"], \
                f"Health query '{message}' should enable health data, got: {intent['action']}"
    
    def test_who_am_i_query(self, router):
        """Test that 'Who am I?' queries use RAG to fetch user profile from notes.
        
        These queries should retrieve from 'Artur Gomes.md' and understand that
        the user (Artur) wrote all the notes - they are his ideas/projects.
        """
        messages = [
            "Who am I?",
            "Tell me about myself",
            "What do you know about me?",
        ]
        
        for message in messages:
            intent = router.route(message)
            # Should use RAG to look up user's personal notes (Artur Gomes.md)
            assert intent["action"] in ["general", "note_search", "rag_query"], \
                f"Identity query '{message}' should route to RAG-enabled action, got: {intent['action']}"
    
    def test_who_are_you_query(self, router):
        """Test that 'Who are you?' queries route appropriately.
        
        These queries should retrieve from '5.0 About/' folder which contains
        Friday's identity, capabilities, and purpose.
        """
        messages = [
            "Who are you?",
            "What is your name?",
            "Tell me about yourself",
            "What can you do?",
        ]
        
        for message in messages:
            intent = router.route(message)
            # Can route to general (system prompt) or RAG (About folder)
            assert intent["action"] in ["general", "note_search", "rag_query"], \
                f"Assistant identity query '{message}' should route appropriately, got: {intent['action']}"
    
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
