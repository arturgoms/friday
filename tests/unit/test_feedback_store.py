"""
Unit tests for FeedbackStore corrections functionality.
"""
import pytest
import tempfile
import os
from pathlib import Path


class TestFeedbackStoreCorrections:
    """Test the corrections table and methods."""
    
    @pytest.fixture
    def feedback_store(self):
        """Create a feedback store with a temporary database."""
        from app.services.feedback_store import FeedbackStore
        
        # Use temp file for test database
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        store = FeedbackStore(db_path=db_path)
        yield store
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_add_correction(self, feedback_store):
        """Test adding a correction to negative feedback."""
        # First add negative feedback
        feedback_id = feedback_store.add_feedback(
            user_message="What's on my calendar?",
            ai_response="You have no events.",
            feedback="down",
            intent_action="calendar_query"
        )
        
        # Add correction
        correction_id = feedback_store.add_correction(
            feedback_id=feedback_id,
            correction_text="You missed my dentist appointment at 3pm"
        )
        
        assert correction_id is not None
        assert correction_id > 0
    
    def test_get_unprocessed_corrections(self, feedback_store):
        """Test retrieving unprocessed corrections."""
        # Add feedback and corrections
        feedback_id1 = feedback_store.add_feedback(
            user_message="What's the weather?",
            ai_response="I don't know.",
            feedback="down",
            intent_action="general"
        )
        feedback_store.add_correction(
            feedback_id=feedback_id1,
            correction_text="You should search the web for weather"
        )
        
        feedback_id2 = feedback_store.add_feedback(
            user_message="Set a reminder",
            ai_response="Done!",
            feedback="down",
            intent_action="reminder_create"
        )
        feedback_store.add_correction(
            feedback_id=feedback_id2,
            correction_text="You didn't ask for the time"
        )
        
        corrections = feedback_store.get_unprocessed_corrections()
        
        assert len(corrections) == 2
        assert all(c["user_message"] for c in corrections)
        assert all(c["correction_text"] for c in corrections)
    
    def test_mark_corrections_processed(self, feedback_store):
        """Test marking corrections as processed."""
        # Add feedback and correction
        feedback_id = feedback_store.add_feedback(
            user_message="Test",
            ai_response="Test response",
            feedback="down"
        )
        correction_id = feedback_store.add_correction(
            feedback_id=feedback_id,
            correction_text="Test correction"
        )
        
        # Should have 1 unprocessed
        assert len(feedback_store.get_unprocessed_corrections()) == 1
        
        # Mark as processed
        count = feedback_store.mark_corrections_processed(
            [correction_id],
            learning_id="learn_test_001"
        )
        
        assert count == 1
        
        # Should have 0 unprocessed now
        assert len(feedback_store.get_unprocessed_corrections()) == 0
    
    def test_get_corrections_for_feedback(self, feedback_store):
        """Test getting corrections linked to a specific feedback."""
        feedback_id = feedback_store.add_feedback(
            user_message="Test",
            ai_response="Response",
            feedback="down"
        )
        
        # Add multiple corrections for same feedback
        feedback_store.add_correction(feedback_id, "First correction")
        feedback_store.add_correction(feedback_id, "Second correction")
        
        corrections = feedback_store.get_corrections_for_feedback(feedback_id)
        
        assert len(corrections) == 2
        assert any("First" in c["correction_text"] for c in corrections)
        assert any("Second" in c["correction_text"] for c in corrections)
    
    def test_get_correction_stats(self, feedback_store):
        """Test correction statistics."""
        # Add some feedback and corrections
        for intent in ["calendar_query", "calendar_query", "general"]:
            fid = feedback_store.add_feedback(
                user_message="Test",
                ai_response="Response",
                feedback="down",
                intent_action=intent
            )
            feedback_store.add_correction(fid, f"Correction for {intent}")
        
        stats = feedback_store.get_correction_stats()
        
        assert stats["total"] == 3
        assert stats["pending"] == 3
        assert stats["processed"] == 0
        assert len(stats["by_intent"]) > 0
    
    def test_get_recent_negative_with_corrections(self, feedback_store):
        """Test getting negative feedback with associated corrections."""
        # Add negative feedback without correction
        feedback_store.add_feedback(
            user_message="Question without correction",
            ai_response="Bad response",
            feedback="down"
        )
        
        # Add negative feedback with correction
        fid = feedback_store.add_feedback(
            user_message="Question with correction",
            ai_response="Also bad",
            feedback="down"
        )
        feedback_store.add_correction(fid, "Here's how to fix it")
        
        results = feedback_store.get_recent_negative_with_corrections(limit=10)
        
        assert len(results) == 2
        
        # Find the one with correction
        with_correction = [r for r in results if r.get("correction")]
        assert len(with_correction) == 1
        assert "fix it" in with_correction[0]["correction"]


class TestFeedbackStoreBasic:
    """Test basic feedback store functionality."""
    
    @pytest.fixture
    def feedback_store(self):
        """Create a feedback store with a temporary database."""
        from app.services.feedback_store import FeedbackStore
        
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        store = FeedbackStore(db_path=db_path)
        yield store
        
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_add_positive_feedback(self, feedback_store):
        """Test adding positive feedback."""
        feedback_id = feedback_store.add_feedback(
            user_message="Hello",
            ai_response="Hi there!",
            feedback="up"
        )
        
        assert feedback_id is not None
        assert feedback_id > 0
    
    def test_add_negative_feedback(self, feedback_store):
        """Test adding negative feedback."""
        feedback_id = feedback_store.add_feedback(
            user_message="Help me",
            ai_response="I can't help with that",
            feedback="down",
            intent_action="general",
            context_type="none"
        )
        
        assert feedback_id is not None
    
    def test_invalid_feedback_type(self, feedback_store):
        """Test that invalid feedback types are rejected."""
        with pytest.raises(ValueError):
            feedback_store.add_feedback(
                user_message="Test",
                ai_response="Response",
                feedback="invalid"
            )
    
    def test_get_feedback_stats(self, feedback_store):
        """Test feedback statistics calculation."""
        # Add mix of feedback
        for _ in range(3):
            feedback_store.add_feedback(
                user_message="Good",
                ai_response="Thanks",
                feedback="up",
                intent_action="general"
            )
        
        feedback_store.add_feedback(
            user_message="Bad",
            ai_response="Sorry",
            feedback="down",
            intent_action="general"
        )
        
        stats = feedback_store.get_feedback_stats(days=30)
        
        assert stats["overall"]["total"] == 4
        assert stats["overall"]["thumbs_up"] == 3
        assert stats["overall"]["thumbs_down"] == 1
        assert stats["overall"]["approval_rate"] == 75.0
    
    def test_get_negative_feedback(self, feedback_store):
        """Test retrieving negative feedback."""
        feedback_store.add_feedback(
            user_message="Bad query",
            ai_response="Bad response",
            feedback="down"
        )
        
        negative = feedback_store.get_negative_feedback(limit=10)
        
        assert len(negative) == 1
        assert negative[0]["user_message"] == "Bad query"
    
    def test_get_feedback_by_message_id(self, feedback_store):
        """Test retrieving feedback by message ID."""
        feedback_store.add_feedback(
            user_message="Test",
            ai_response="Response",
            feedback="up",
            message_id="msg_12345"
        )
        
        result = feedback_store.get_feedback_by_message_id("msg_12345")
        
        assert result is not None
        assert result["user_message"] == "Test"
        
        # Non-existent
        assert feedback_store.get_feedback_by_message_id("nonexistent") is None
