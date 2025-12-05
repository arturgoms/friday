"""Tests for the conversation memory system."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from app.services.conversation_memory import (
    ConversationMemoryStore,
    ConversationEvent,
    ConversationEventType,
)


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_store(temp_storage, monkeypatch):
    """Create a conversation memory store with temp storage."""
    # Patch the storage path
    monkeypatch.setattr(
        "app.services.conversation_memory.settings.friday_path",
        temp_storage
    )
    store = ConversationMemoryStore()
    return store


class TestConversationEvent:
    """Tests for ConversationEvent dataclass."""
    
    def test_to_dict_and_back(self):
        """Test serialization roundtrip."""
        event = ConversationEvent(
            id="test123",
            event_type=ConversationEventType.CORRECTION_RECEIVED,
            timestamp=datetime.now(),
            topic="Test Topic",
            user_message="That's wrong",
            friday_response="I said something",
            what_was_wrong="The thing I said",
            correct_answer="The right answer",
            lesson_learned="Don't make this mistake",
        )
        
        # Convert to dict and back
        data = event.to_dict()
        restored = ConversationEvent.from_dict(data)
        
        assert restored.id == event.id
        assert restored.event_type == event.event_type
        assert restored.topic == event.topic
        assert restored.what_was_wrong == event.what_was_wrong
        assert restored.correct_answer == event.correct_answer
    
    def test_to_context_string_correction(self):
        """Test context string for correction."""
        event = ConversationEvent(
            id="test123",
            event_type=ConversationEventType.CORRECTION_RECEIVED,
            timestamp=datetime.now(),
            topic="User's birthday",
            user_message="No, my birthday is March 15",
            friday_response="Your birthday is March 10",
            what_was_wrong="Said birthday was March 10",
            correct_answer="Birthday is March 15",
            lesson_learned="Remember: Birthday is March 15",
        )
        
        context = event.to_context_string()
        
        assert "CORRECTION" in context
        assert "March 10" in context
        assert "March 15" in context
    
    def test_to_context_string_advice(self):
        """Test context string for advice."""
        event = ConversationEvent(
            id="test123",
            event_type=ConversationEventType.ADVICE_GIVEN,
            timestamp=datetime.now(),
            topic="Running schedule",
            user_message="How should I train?",
            friday_response="You should run 3 times per week",
        )
        
        context = event.to_context_string()
        
        assert "ADVICE I GAVE" in context
        assert "Running schedule" in context


class TestConversationMemoryStore:
    """Tests for ConversationMemoryStore."""
    
    def test_add_correction(self, memory_store):
        """Test adding a correction."""
        event = memory_store.add_correction(
            topic="Favorite color",
            user_message="No, my favorite color is blue, not red",
            friday_response="Your favorite color is red",
            what_was_wrong="Said favorite color was red",
            correct_answer="Favorite color is blue",
            lesson_learned="Remember: Artur's favorite color is blue",
        )
        
        assert event.id is not None
        assert event.event_type == ConversationEventType.CORRECTION_RECEIVED
        assert event.what_was_wrong == "Said favorite color was red"
        
        # Check it was saved
        corrections = memory_store.get_recent_corrections(days=1)
        assert len(corrections) == 1
        assert corrections[0].id == event.id
    
    def test_add_advice(self, memory_store):
        """Test adding advice."""
        event = memory_store.add_advice(
            topic="Sleep improvement",
            user_message="How can I sleep better?",
            friday_response="Try going to bed at the same time every night",
            follow_up_days=7,
            tags=["health", "sleep"],
        )
        
        assert event.id is not None
        assert event.event_type == ConversationEventType.ADVICE_GIVEN
        assert event.follow_up_date is not None
    
    def test_add_commitment(self, memory_store):
        """Test adding a commitment."""
        event = memory_store.add_commitment(
            topic="Exercise",
            user_message="I'll start running tomorrow",
            friday_response="Great! I'll check in with you about it",
            commitment="User will start running",
            follow_up_days=3,
        )
        
        assert event.id is not None
        assert event.context == "User will start running"
    
    def test_add_important_moment(self, memory_store):
        """Test adding an important moment."""
        event = memory_store.add_important_moment(
            topic="Relationship discussion",
            user_message="I'm worried about my marriage",
            friday_response="I understand. Would you like to talk about it?",
            context="User expressed concern about marriage - sensitive topic",
            tags=["emotional", "relationship"],
        )
        
        assert event.id is not None
        assert event.event_type == ConversationEventType.IMPORTANT_MOMENT
    
    def test_get_corrections_for_topic(self, memory_store):
        """Test finding corrections by topic."""
        # Add corrections on different topics
        memory_store.add_correction(
            topic="Birthday",
            user_message="My birthday is March 15",
            friday_response="Wrong date",
            what_was_wrong="Wrong date",
            correct_answer="March 15",
        )
        memory_store.add_correction(
            topic="Favorite food",
            user_message="I like pizza",
            friday_response="Wrong food",
            what_was_wrong="Wrong food",
            correct_answer="Pizza",
        )
        
        # Search for birthday corrections
        results = memory_store.get_corrections_for_topic("birthday")
        
        assert len(results) == 1
        assert "Birthday" in results[0].topic
    
    def test_get_pending_follow_ups(self, memory_store):
        """Test getting pending follow-ups."""
        # Add a commitment with past follow-up date
        memory_store.add_commitment(
            topic="Test",
            user_message="I'll do it",
            friday_response="OK",
            commitment="Do the thing",
            follow_up_days=-1,  # Yesterday
        )
        
        # Add a commitment with future follow-up date
        memory_store.add_commitment(
            topic="Test2",
            user_message="I'll do it later",
            friday_response="OK",
            commitment="Do the other thing",
            follow_up_days=7,  # Next week
        )
        
        pending = memory_store.get_pending_follow_ups()
        
        # Only the past one should be pending
        assert len(pending) == 1
        assert pending[0].context == "Do the thing"
    
    def test_mark_followed_up(self, memory_store):
        """Test marking an event as followed up."""
        event = memory_store.add_commitment(
            topic="Test",
            user_message="I'll do it",
            friday_response="OK",
            commitment="Do the thing",
            follow_up_days=-1,
        )
        
        # Initially pending
        assert len(memory_store.get_pending_follow_ups()) == 1
        
        # Mark as followed up
        result = memory_store.mark_followed_up(event.id)
        assert result is True
        
        # No longer pending
        assert len(memory_store.get_pending_follow_ups()) == 0
    
    def test_get_context_for_message(self, memory_store):
        """Test getting relevant context for a message."""
        # Add a correction about birthdays
        memory_store.add_correction(
            topic="Birthday",
            user_message="My birthday is March 15",
            friday_response="Is it March 10?",
            what_was_wrong="Said March 10",
            correct_answer="March 15",
            lesson_learned="Birthday is March 15",
        )
        
        # Ask about birthday
        context = memory_store.get_context_for_message("When is my birthday?")
        
        assert "CORRECTION" in context
        assert "March 15" in context
    
    def test_get_context_for_unrelated_message(self, memory_store):
        """Test that unrelated messages get no context."""
        memory_store.add_correction(
            topic="Birthday",
            user_message="My birthday is March 15",
            friday_response="Is it March 10?",
            what_was_wrong="Said March 10",
            correct_answer="March 15",
        )
        
        # Ask about something unrelated
        context = memory_store.get_context_for_message("What's the weather?")
        
        assert context == ""
    
    def test_persistence(self, memory_store, temp_storage):
        """Test that data persists across instances."""
        # Add a correction
        memory_store.add_correction(
            topic="Test",
            user_message="Wrong!",
            friday_response="Oops",
            what_was_wrong="Something",
            correct_answer="Something else",
        )
        
        # Create new instance (simulating restart)
        from app.services.conversation_memory import ConversationMemoryStore
        new_store = ConversationMemoryStore()
        
        # Data should still be there
        corrections = new_store.get_recent_corrections()
        assert len(corrections) == 1
    
    def test_search_memories(self, memory_store):
        """Test searching across all memory types."""
        memory_store.add_correction(
            topic="Running pace",
            user_message="I can run faster",
            friday_response="Your pace is slow",
            what_was_wrong="Underestimated pace",
            correct_answer="Pace is actually good",
        )
        memory_store.add_advice(
            topic="Running training",
            user_message="How to improve?",
            friday_response="Run more hills",
        )
        memory_store.add_important_moment(
            topic="Career change",
            user_message="Thinking about new job",
            friday_response="Let's discuss",
            context="Considering career change",
        )
        
        # Search for running
        results = memory_store.search_memories("running")
        assert len(results) == 2  # Should find both running-related events
        
        # Search for career
        results = memory_store.search_memories("career")
        assert len(results) == 1
    
    def test_get_stats(self, memory_store):
        """Test getting statistics."""
        memory_store.add_correction(
            topic="Test", user_message="Wrong", friday_response="Oops",
            what_was_wrong="X", correct_answer="Y"
        )
        memory_store.add_advice(
            topic="Test", user_message="Help", friday_response="OK"
        )
        memory_store.add_commitment(
            topic="Test", user_message="I will", friday_response="Good",
            commitment="Do it", follow_up_days=-1
        )
        
        stats = memory_store.get_stats()
        
        assert stats["corrections"] == 1
        assert stats["advice_given"] == 1
        assert stats["commitments"] == 1
        assert stats["pending_follow_ups"] == 1
    
    def test_get_all_corrections_context(self, memory_store):
        """Test getting all corrections as context."""
        memory_store.add_correction(
            topic="Fact 1",
            user_message="Wrong!",
            friday_response="Oops",
            what_was_wrong="X",
            correct_answer="Y",
            lesson_learned="Remember Y not X",
        )
        memory_store.add_correction(
            topic="Fact 2",
            user_message="No!",
            friday_response="My bad",
            what_was_wrong="A",
            correct_answer="B",
            lesson_learned="Remember B not A",
        )
        
        context = memory_store.get_all_corrections_context()
        
        assert "Things I've Been Corrected On" in context
        assert "Remember Y not X" in context
        assert "Remember B not A" in context
