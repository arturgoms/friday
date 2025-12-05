"""Unit tests for ChatOrchestrator and handler registry."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.chat.orchestrator import (
    ChatOrchestrator,
    HandlerRegistry,
    handler_registry,
)
from app.services.chat.handlers.base import (
    IntentHandler,
    ChatContext,
    ChatResponse,
)


class TestHandlerRegistry:
    """Tests for the HandlerRegistry class."""
    
    def test_register_handler(self):
        """Test registering a handler."""
        registry = HandlerRegistry()
        
        class TestHandler(IntentHandler):
            actions = ['test_action']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._success_response(context, "test")
        
        registry.register(TestHandler)
        
        assert 'test_action' in registry.list_handlers()
        assert registry.get_handler('test_action') is not None
    
    def test_register_multiple_actions(self):
        """Test handler with multiple actions."""
        registry = HandlerRegistry()
        
        class MultiHandler(IntentHandler):
            actions = ['action1', 'action2', 'action3']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._success_response(context, "multi")
        
        registry.register(MultiHandler)
        
        handlers = registry.list_handlers()
        assert 'action1' in handlers
        assert 'action2' in handlers
        assert 'action3' in handlers
        
        # All should point to same handler instance
        h1 = registry.get_handler('action1')
        h2 = registry.get_handler('action2')
        assert h1 is h2
    
    def test_get_nonexistent_handler(self):
        """Test getting a handler that doesn't exist."""
        registry = HandlerRegistry()
        
        assert registry.get_handler('nonexistent') is None
    
    def test_clear_handlers(self):
        """Test clearing all handlers."""
        registry = HandlerRegistry()
        
        class TestHandler(IntentHandler):
            actions = ['test']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._success_response(context, "test")
        
        registry.register(TestHandler)
        assert len(registry.list_handlers()) > 0
        
        registry.clear()
        assert len(registry.list_handlers()) == 0


class TestChatContext:
    """Tests for ChatContext dataclass."""
    
    def test_context_properties(self):
        """Test ChatContext property accessors."""
        intent = {
            'action': 'memory_save',
            'tool': None,
            'use_rag': True,
            'use_memory': True,
            'memory_data': {'content': 'test memory', 'tags': ['test']},
        }
        
        context = ChatContext(
            session_id='test-session',
            message='remember that I like pizza',
            intent=intent,
            history=[],
            last_user_message='',
        )
        
        assert context.action == 'memory_save'
        assert context.tool is None
        assert context.use_rag is True
        assert context.use_memory is True
        assert context.memory_data == {'content': 'test memory', 'tags': ['test']}
    
    def test_context_default_action(self):
        """Test default action when not in intent."""
        context = ChatContext(
            session_id='test',
            message='hello',
            intent={},
            history=[],
            last_user_message='',
        )
        
        assert context.action == 'general'


class TestChatResponse:
    """Tests for ChatResponse dataclass."""
    
    def test_response_to_dict(self):
        """Test ChatResponse.to_dict() method."""
        response = ChatResponse(
            session_id='test-session',
            message='test message',
            answer='test answer',
            used_rag=True,
            used_memory=True,
        )
        
        result = response.to_dict()
        
        assert result['session_id'] == 'test-session'
        assert result['message'] == 'test message'
        assert result['answer'] == 'test answer'
        assert result['used_rag'] is True
        assert result['used_memory'] is True
    
    def test_response_is_final_default(self):
        """Test that is_final defaults to True."""
        response = ChatResponse(
            session_id='test',
            message='test',
            answer='answer',
        )
        
        assert response.is_final is True


class TestChatOrchestrator:
    """Tests for ChatOrchestrator class."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a fresh orchestrator for testing."""
        # Create orchestrator without registering handlers
        with patch.object(ChatOrchestrator, '_register_handlers'):
            return ChatOrchestrator()
    
    def test_get_or_create_session_new(self, orchestrator):
        """Test creating a new session."""
        session_id = orchestrator.get_or_create_session()
        
        assert session_id is not None
        assert len(session_id) > 0
        assert session_id in orchestrator.conversation_history
    
    def test_get_or_create_session_existing(self, orchestrator):
        """Test getting an existing session."""
        original_id = 'test-session-123'
        orchestrator.conversation_history[original_id] = []
        
        session_id = orchestrator.get_or_create_session(original_id)
        
        assert session_id == original_id
    
    def test_update_history(self, orchestrator):
        """Test updating conversation history."""
        session_id = orchestrator.get_or_create_session('test-session')
        
        orchestrator.update_history(session_id, 'user message', 'assistant response')
        
        history = orchestrator.get_history(session_id)
        assert len(history) == 2
        assert history[0] == {'role': 'user', 'content': 'user message'}
        assert history[1] == {'role': 'assistant', 'content': 'assistant response'}
    
    def test_get_last_user_message(self, orchestrator):
        """Test getting last user message from history."""
        session_id = orchestrator.get_or_create_session('test-session')
        orchestrator.update_history(session_id, 'first message', 'response 1')
        orchestrator.update_history(session_id, 'second message', 'response 2')
        
        last_msg = orchestrator.get_last_user_message(session_id)
        
        assert last_msg == 'second message'
    
    def test_get_last_user_message_empty(self, orchestrator):
        """Test getting last user message from empty history."""
        session_id = orchestrator.get_or_create_session('test-session')
        
        last_msg = orchestrator.get_last_user_message(session_id)
        
        assert last_msg == ''


class TestGlobalHandlerRegistry:
    """Tests for the global handler registry."""
    
    def test_global_registry_has_handlers(self):
        """Test that the global registry has handlers registered."""
        # Force import of chat module to trigger registration
        from app.services.chat import handler_registry as global_registry
        
        handlers = global_registry.list_handlers()
        
        # Should have memory, reminder, note, calendar, task, alert, report handlers
        assert len(handlers) >= 20  # We have at least 28 handlers
        
        # Check some key handlers exist
        assert 'memory_save' in handlers
        assert 'reminder_create' in handlers
        assert 'note_create' in handlers
        assert 'calendar_query' in handlers
        assert 'task_create' in handlers
        assert 'alert_create' in handlers
        assert 'morning_report' in handlers


class TestIntentHandler:
    """Tests for the IntentHandler base class."""
    
    def test_can_handle_matching_action(self):
        """Test can_handle returns True for matching actions."""
        class TestHandler(IntentHandler):
            actions = ['test_action', 'other_action']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._success_response(context, "test")
        
        handler = TestHandler()
        
        assert handler.can_handle('test_action') is True
        assert handler.can_handle('other_action') is True
        assert handler.can_handle('unknown') is False
    
    def test_error_response(self):
        """Test _error_response helper method."""
        class TestHandler(IntentHandler):
            actions = ['test']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._error_response(context, "Something went wrong")
        
        handler = TestHandler()
        context = ChatContext(
            session_id='test',
            message='test',
            intent={'action': 'test'},
            history=[],
            last_user_message='',
        )
        
        response = handler.handle(context)
        
        assert 'Something went wrong' in response.answer
        assert response.is_final is True
    
    def test_success_response(self):
        """Test _success_response helper method."""
        class TestHandler(IntentHandler):
            actions = ['test']
            
            def handle(self, context: ChatContext) -> ChatResponse:
                return self._success_response(
                    context,
                    "Success!",
                    extracted_memory="test memory"
                )
        
        handler = TestHandler()
        context = ChatContext(
            session_id='test',
            message='test',
            intent={'action': 'test'},
            history=[],
            last_user_message='',
        )
        
        response = handler.handle(context)
        
        assert response.answer == "Success!"
        assert response.extracted_memory == "test memory"
        assert response.is_final is True
