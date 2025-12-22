"""
Unit tests for LearningService.
"""
import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLearning:
    """Test the Learning dataclass."""
    
    def test_learning_creation(self):
        """Test creating a Learning instance."""
        from app.services.learning_service import Learning
        
        learning = Learning(
            id="learn_001",
            created_at="2025-12-05T10:00:00",
            pattern="User prefers concise answers",
            prompt_adjustment="Keep responses brief and to the point.",
            confidence=0.85,
            category="tone"
        )
        
        assert learning.id == "learn_001"
        assert learning.confidence == 0.85
        assert learning.active == True  # Default
        assert learning.source_corrections == []  # Default
    
    def test_learning_to_dict(self):
        """Test converting Learning to dictionary."""
        from app.services.learning_service import Learning
        
        learning = Learning(
            id="learn_002",
            created_at="2025-12-05T10:00:00",
            pattern="Test pattern",
            prompt_adjustment="Test adjustment",
            confidence=0.75,
            source_corrections=[1, 2, 3]
        )
        
        data = learning.to_dict()
        
        assert data["id"] == "learn_002"
        assert data["confidence"] == 0.75
        assert data["source_corrections"] == [1, 2, 3]
    
    def test_learning_from_dict(self):
        """Test creating Learning from dictionary."""
        from app.services.learning_service import Learning
        
        data = {
            "id": "learn_003",
            "created_at": "2025-12-05T10:00:00",
            "pattern": "From dict",
            "prompt_adjustment": "Adjustment from dict",
            "confidence": 0.9,
            "category": "format",
            "active": False,
            "source_corrections": [5, 6]
        }
        
        learning = Learning.from_dict(data)
        
        assert learning.id == "learn_003"
        assert learning.pattern == "From dict"
        assert learning.active == False
        assert learning.source_corrections == [5, 6]


class TestLearningService:
    """Test the LearningService."""
    
    @pytest.fixture
    def learning_service(self):
        """Create a learning service with temporary storage."""
        from app.services.learning_service import LearningService
        
        # Use temp file for test storage
        fd, json_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(json_path)  # Remove so it starts fresh
        
        service = LearningService(learnings_path=Path(json_path))
        yield service
        
        # Cleanup
        if os.path.exists(json_path):
            os.unlink(json_path)
    
    def test_initial_state(self, learning_service):
        """Test initial state of learning service."""
        assert learning_service.is_enabled() == True
        assert len(learning_service.get_all_learnings()) == 0
    
    def test_add_manual_learning(self, learning_service):
        """Test adding a manual learning."""
        learning = learning_service.add_manual_learning(
            pattern="User preference",
            prompt_adjustment="Always respond in formal language",
            confidence=1.0,
            category="manual"
        )
        
        assert learning.id.startswith("learn_")
        assert learning.confidence == 1.0
        assert learning.category == "manual"
        
        # Should be retrievable
        all_learnings = learning_service.get_all_learnings()
        assert len(all_learnings) == 1
    
    def test_remove_learning(self, learning_service):
        """Test removing a learning."""
        learning = learning_service.add_manual_learning(
            pattern="Test",
            prompt_adjustment="Test adjustment"
        )
        
        assert len(learning_service.get_all_learnings()) == 1
        
        result = learning_service.remove_learning(learning.id)
        assert result == True
        
        assert len(learning_service.get_all_learnings()) == 0
        
        # Removing non-existent should return False
        assert learning_service.remove_learning("nonexistent") == False
    
    def test_toggle_learning(self, learning_service):
        """Test enabling/disabling a specific learning."""
        learning = learning_service.add_manual_learning(
            pattern="Test",
            prompt_adjustment="Test"
        )
        
        assert learning.active == True
        
        # Disable
        learning_service.toggle_learning(learning.id, False)
        updated = learning_service.get_learning(learning.id)
        assert updated.active == False
        
        # Re-enable
        learning_service.toggle_learning(learning.id, True)
        updated = learning_service.get_learning(learning.id)
        assert updated.active == True
    
    def test_enable_disable_all(self, learning_service):
        """Test enabling/disabling the entire learning system."""
        assert learning_service.is_enabled() == True
        
        learning_service.disable_all()
        assert learning_service.is_enabled() == False
        
        learning_service.enable_all()
        assert learning_service.is_enabled() == True
    
    def test_get_active_learnings(self, learning_service):
        """Test filtering active learnings by confidence."""
        # Add learnings with different confidence levels
        learning_service.add_manual_learning(
            pattern="High confidence",
            prompt_adjustment="High",
            confidence=0.9
        )
        learning_service.add_manual_learning(
            pattern="Low confidence",
            prompt_adjustment="Low",
            confidence=0.5
        )
        
        # Default threshold is 0.7
        active = learning_service.get_active_learnings(min_confidence=0.7)
        assert len(active) == 1
        assert active[0].pattern == "High confidence"
        
        # Lower threshold
        active = learning_service.get_active_learnings(min_confidence=0.4)
        assert len(active) == 2
    
    def test_get_active_learnings_when_disabled(self, learning_service):
        """Test that no learnings are returned when system is disabled."""
        learning_service.add_manual_learning(
            pattern="Test",
            prompt_adjustment="Test",
            confidence=1.0
        )
        
        learning_service.disable_all()
        
        active = learning_service.get_active_learnings()
        assert len(active) == 0
    
    def test_get_prompt_adjustments(self, learning_service):
        """Test generating prompt adjustment text."""
        learning_service.add_manual_learning(
            pattern="Brevity",
            prompt_adjustment="Keep responses under 3 sentences",
            confidence=0.9
        )
        learning_service.add_manual_learning(
            pattern="Format",
            prompt_adjustment="Use bullet points for lists",
            confidence=0.8
        )
        
        adjustments = learning_service.get_prompt_adjustments(min_confidence=0.7)
        
        assert "User Preferences" in adjustments
        assert "Keep responses under 3 sentences" in adjustments
        assert "Use bullet points" in adjustments
    
    def test_get_prompt_adjustments_empty(self, learning_service):
        """Test that empty string is returned when no learnings."""
        adjustments = learning_service.get_prompt_adjustments()
        assert adjustments == ""
    
    def test_get_learning(self, learning_service):
        """Test retrieving a specific learning by ID."""
        learning = learning_service.add_manual_learning(
            pattern="Test",
            prompt_adjustment="Test"
        )
        
        retrieved = learning_service.get_learning(learning.id)
        assert retrieved is not None
        assert retrieved.id == learning.id
        
        # Non-existent
        assert learning_service.get_learning("nonexistent") is None
    
    def test_get_stats(self, learning_service):
        """Test getting learning statistics."""
        learning_service.add_manual_learning(
            pattern="Manual 1",
            prompt_adjustment="Adj 1",
            category="manual"
        )
        learning_service.add_manual_learning(
            pattern="Manual 2",
            prompt_adjustment="Adj 2",
            category="tone"
        )
        
        stats = learning_service.get_stats()
        
        assert stats["enabled"] == True
        assert stats["total_learnings"] == 2
        assert stats["active_learnings"] == 2
        assert "manual" in stats["by_category"]
        assert "tone" in stats["by_category"]
    
    def test_persistence(self, learning_service):
        """Test that learnings are persisted to disk."""
        from app.services.learning_service import LearningService
        
        learning_service.add_manual_learning(
            pattern="Persistent",
            prompt_adjustment="This should persist"
        )
        
        # Create new instance pointing to same file
        new_service = LearningService(learnings_path=learning_service.learnings_path)
        
        assert len(new_service.get_all_learnings()) == 1
        assert new_service.get_all_learnings()[0].pattern == "Persistent"


class TestLearningSynthesis:
    """Test learning synthesis (requires mocking LLM)."""
    
    @pytest.fixture
    def learning_service(self):
        """Create a learning service with temporary storage."""
        from app.services.learning_service import LearningService
        
        fd, json_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(json_path)
        
        service = LearningService(learnings_path=Path(json_path))
        yield service
        
        if os.path.exists(json_path):
            os.unlink(json_path)
    
    @pytest.fixture
    def feedback_store(self):
        """Create a feedback store with temporary database."""
        from app.services.feedback_store import FeedbackStore
        
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        store = FeedbackStore(db_path=db_path)
        yield store
        
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_synthesize_no_corrections(self, learning_service):
        """Test synthesis with no corrections returns empty list."""
        import asyncio
        
        with patch('app.services.feedback_store.get_feedback_store') as mock_store:
            mock_store.return_value.get_unprocessed_corrections.return_value = []
            
            result = asyncio.get_event_loop().run_until_complete(
                learning_service.synthesize_learnings()
            )
            
            assert result == []
    
    def test_synthesize_with_corrections(self, learning_service):
        """Test synthesis with corrections calls LLM and creates learnings."""
        import asyncio
        
        mock_corrections = [
            {
                "correction_id": 1,
                "feedback_id": 1,
                "correction_text": "You should be more concise",
                "user_message": "Tell me about the weather",
                "ai_response": "Let me provide a comprehensive overview...",
                "intent_action": "general"
            },
            {
                "correction_id": 2,
                "feedback_id": 2,
                "correction_text": "Keep it short",
                "user_message": "What time is it?",
                "ai_response": "The current time is...",
                "intent_action": "general"
            }
        ]
        
        mock_llm_response = '''```json
{
  "learnings": [
    {
      "pattern": "User prefers concise responses",
      "prompt_adjustment": "Keep responses brief and focused",
      "confidence": 0.85,
      "category": "tone"
    }
  ]
}
```'''
        
        with patch('app.services.feedback_store.get_feedback_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_unprocessed_corrections.return_value = mock_corrections
            mock_store.mark_corrections_processed.return_value = 2
            mock_store_fn.return_value = mock_store
            
            with patch('app.services.llm.llm_service') as mock_llm:
                mock_llm.call.return_value = mock_llm_response
                
                result = asyncio.get_event_loop().run_until_complete(
                    learning_service.synthesize_learnings()
                )
                
                assert len(result) == 1
                assert result[0].pattern == "User prefers concise responses"
                assert result[0].confidence == 0.85
                
                # Should have marked corrections as processed
                mock_store.mark_corrections_processed.assert_called_once()
    
    def test_synthesize_filters_low_confidence(self, learning_service):
        """Test that low confidence learnings are filtered out."""
        import asyncio
        
        mock_corrections = [
            {
                "correction_id": 1,
                "feedback_id": 1,
                "correction_text": "Test",
                "user_message": "Test",
                "ai_response": "Test",
                "intent_action": "general"
            }
        ]
        
        mock_llm_response = '''```json
{
  "learnings": [
    {
      "pattern": "Low confidence pattern",
      "prompt_adjustment": "Should be filtered",
      "confidence": 0.4,
      "category": "general"
    }
  ]
}
```'''
        
        with patch('app.services.feedback_store.get_feedback_store') as mock_store_fn:
            mock_store = MagicMock()
            mock_store.get_unprocessed_corrections.return_value = mock_corrections
            mock_store_fn.return_value = mock_store
            
            with patch('app.services.llm.llm_service') as mock_llm:
                mock_llm.call.return_value = mock_llm_response
                
                result = asyncio.get_event_loop().run_until_complete(
                    learning_service.synthesize_learnings()
                )
                
                # Should filter out low confidence
                assert len(result) == 0
