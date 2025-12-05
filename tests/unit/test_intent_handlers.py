"""Unit tests for individual intent handlers."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.chat.handlers.base import ChatContext, ChatResponse


# ============================================================================
# Memory Handlers Tests
# ============================================================================

class TestMemorySaveHandler:
    """Tests for MemorySaveHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.memory import MemorySaveHandler
        return MemorySaveHandler()
    
    @pytest.fixture
    def context(self):
        return ChatContext(
            session_id='test-session',
            message='remember that I like pizza',
            intent={
                'action': 'memory_save',
                'memory_data': {'content': 'I like pizza', 'tags': ['food', 'preference']}
            },
            history=[],
            last_user_message='',
        )
    
    def test_save_memory_success(self, handler, context):
        """Test successful memory save."""
        with patch('app.services.chat.handlers.memory.MemoryStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_memory.return_value = ('mem-123', None)  # No conflicts
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'remember' in response.answer.lower() or 'got it' in response.answer.lower()
            assert response.extracted_memory is not None
    
    def test_save_memory_with_conflict(self, handler, context):
        """Test memory save with conflict detection."""
        with patch('app.services.chat.handlers.memory.MemoryStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_memory.return_value = (
                None, 
                [{'id': 'old-mem', 'content': 'I hate pizza'}]  # Conflict
            )
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'conflict' in response.answer.lower() or 'existing' in response.answer.lower()
    
    def test_save_memory_no_data(self, handler):
        """Test memory save with no memory_data."""
        context = ChatContext(
            session_id='test',
            message='remember something',
            intent={'action': 'memory_save', 'memory_data': None},
            history=[],
            last_user_message='',
        )
        
        response = handler.handle(context)
        
        assert response.is_final is True
        assert 'error' in response.answer.lower() or 'no' in response.answer.lower()
    
    def test_personalize_memory(self, handler):
        """Test that first-person pronouns are replaced with user name."""
        content = "my birthday is march 30"
        result = handler._personalize_memory(content)
        
        assert "Artur" in result
        assert "my" not in result.lower()


class TestMemoryListHandler:
    """Tests for MemoryListHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.memory import MemoryListHandler
        return MemoryListHandler()
    
    def test_list_memories_with_results(self, handler):
        """Test listing memories when some exist."""
        context = ChatContext(
            session_id='test',
            message='what do you remember?',
            intent={'action': 'memory_list'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.memory.MemoryStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.list_memories.return_value = [
                {'id': 'mem-1', 'content': 'User likes pizza'},
                {'id': 'mem-2', 'content': 'User works at Counterpart'},
            ]
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'pizza' in response.answer.lower()
            assert response.used_memory is True
    
    def test_list_memories_empty(self, handler):
        """Test listing memories when none exist."""
        context = ChatContext(
            session_id='test',
            message='what do you remember?',
            intent={'action': 'memory_list'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.memory.MemoryStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.list_memories.return_value = []
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'haven\'t' in response.answer.lower() or 'no' in response.answer.lower()


# ============================================================================
# Reminder Handlers Tests
# ============================================================================

class TestReminderCreateHandler:
    """Tests for ReminderCreateHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.reminder import ReminderCreateHandler
        return ReminderCreateHandler()
    
    def test_create_reminder_minutes(self, handler):
        """Test creating a reminder with minutes."""
        context = ChatContext(
            session_id='test',
            message='remind me to call mom in 30 minutes',
            intent={
                'action': 'reminder_create',
                'reminder_data': {'message': 'call mom', 'time_spec': '30 minutes'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.reminder.reminder_service') as mock_service:
            mock_service.create_reminder.return_value = Mock(id='rem-123')
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'reminder' in response.answer.lower()
            assert 'call mom' in response.answer.lower()
            mock_service.create_reminder.assert_called_once()
    
    def test_create_reminder_hours(self, handler):
        """Test creating a reminder with hours."""
        context = ChatContext(
            session_id='test',
            message='remind me to check email in 2 hours',
            intent={
                'action': 'reminder_create',
                'reminder_data': {'message': 'check email', 'time_spec': '2 hours'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.reminder.reminder_service') as mock_service:
            mock_service.create_reminder.return_value = Mock(id='rem-123')
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'reminder' in response.answer.lower()
    
    def test_create_reminder_absolute_time(self, handler):
        """Test creating a reminder with absolute time."""
        context = ChatContext(
            session_id='test',
            message='remind me to take medicine at 3pm',
            intent={
                'action': 'reminder_create',
                'reminder_data': {'message': 'take medicine', 'time_spec': '3pm'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.reminder.reminder_service') as mock_service:
            mock_service.create_reminder.return_value = Mock(id='rem-123')
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'reminder' in response.answer.lower()
    
    def test_create_reminder_invalid_time(self, handler):
        """Test creating a reminder with invalid time spec."""
        context = ChatContext(
            session_id='test',
            message='remind me to do something',
            intent={
                'action': 'reminder_create',
                'reminder_data': {'message': 'do something', 'time_spec': 'invalid'}
            },
            history=[],
            last_user_message='',
        )
        
        response = handler.handle(context)
        
        assert response.is_final is True
        assert 'couldn\'t' in response.answer.lower() or 'try' in response.answer.lower()


class TestReminderDeleteHandler:
    """Tests for ReminderDeleteHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.reminder import ReminderDeleteHandler
        return ReminderDeleteHandler()
    
    def test_delete_reminder_by_index(self, handler):
        """Test deleting a reminder by index."""
        context = ChatContext(
            session_id='test',
            message='delete reminder 1',
            intent={'action': 'reminder_delete', 'reminder_index': 0},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.reminder.reminder_service') as mock_service:
            mock_reminder = Mock(id='rem-123', message='call mom')
            mock_service.list_pending_reminders.return_value = [mock_reminder]
            mock_service.cancel_reminder.return_value = True
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'deleted' in response.answer.lower()
    
    def test_delete_all_reminders(self, handler):
        """Test deleting all reminders."""
        context = ChatContext(
            session_id='test',
            message='delete all reminders',
            intent={'action': 'reminder_delete', 'reminder_index': -999},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.reminder.reminder_service') as mock_service:
            mock_service.list_pending_reminders.return_value = [
                Mock(id='rem-1', message='reminder 1'),
                Mock(id='rem-2', message='reminder 2'),
            ]
            mock_service.cancel_reminder.return_value = True
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'deleted' in response.answer.lower()
            assert '2' in response.answer


# ============================================================================
# Note Handlers Tests
# ============================================================================

class TestNoteCreateHandler:
    """Tests for NoteCreateHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.note import NoteCreateHandler
        return NoteCreateHandler()
    
    def test_create_note_success(self, handler):
        """Test successful note creation."""
        context = ChatContext(
            session_id='test',
            message='create a note about Python',
            intent={
                'action': 'note_create',
                'note_data': {'title': 'Python Notes', 'content': '', 'tags': ['python']}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.note.obsidian_service') as mock_service:
            mock_service.create_note.return_value = '/path/to/note.md'
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'created' in response.answer.lower()
            assert 'Python' in response.answer


class TestNoteGetHandler:
    """Tests for NoteGetHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.note import NoteGetHandler
        return NoteGetHandler()
    
    def test_get_note_found(self, handler):
        """Test getting an existing note."""
        context = ChatContext(
            session_id='test',
            message='get my Python note',
            intent={
                'action': 'note_get',
                'note_data': {'title': 'Python'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.note.obsidian_service') as mock_service:
            mock_service.get_note.return_value = {
                'title': 'Python Notes',
                'content': '---\ntags: python\n---\n\nPython is great!'
            }
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'Python' in response.answer
    
    def test_get_note_not_found(self, handler):
        """Test getting a non-existent note."""
        context = ChatContext(
            session_id='test',
            message='get my nonexistent note',
            intent={
                'action': 'note_get',
                'note_data': {'title': 'nonexistent'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.note.obsidian_service') as mock_service:
            mock_service.get_note.return_value = None
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'not found' in response.answer.lower()


# ============================================================================
# Calendar Handlers Tests
# ============================================================================

class TestCalendarQueryHandler:
    """Tests for CalendarQueryHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.calendar import CalendarQueryHandler
        return CalendarQueryHandler()
    
    def test_query_today_events(self, handler):
        """Test querying today's events."""
        context = ChatContext(
            session_id='test',
            message="what's on my calendar today?",
            intent={'action': 'calendar_query', 'tool': 'calendar_today'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.calendar.calendar_service') as mock_service:
            mock_event = Mock()
            mock_event.start = datetime.now()
            mock_event.summary = 'Team Meeting'
            mock_event.location = 'Conference Room'
            mock_service.get_today_events.return_value = [mock_event]
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'Team Meeting' in response.answer
    
    def test_query_no_events(self, handler):
        """Test querying when no events exist."""
        context = ChatContext(
            session_id='test',
            message="what's on my calendar today?",
            intent={'action': 'calendar_query', 'tool': 'calendar_today'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.calendar.calendar_service') as mock_service:
            mock_service.get_today_events.return_value = []
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'no events' in response.answer.lower()


class TestTimeQueryHandler:
    """Tests for TimeQueryHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.calendar import TimeQueryHandler
        return TimeQueryHandler()
    
    def test_get_current_time(self, handler):
        """Test getting current time."""
        context = ChatContext(
            session_id='test',
            message='what time is it?',
            intent={'action': 'time_query', 'tool': 'current_time'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.date_tools.date_tools') as mock_tools:
            mock_tools.get_current_time.return_value = 'It is 2:30 PM on Friday, December 5, 2025'
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert '2:30' in response.answer or 'PM' in response.answer


# ============================================================================
# Task Handlers Tests
# ============================================================================

class TestTaskCreateHandler:
    """Tests for TaskCreateHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.task import TaskCreateHandler
        return TaskCreateHandler()
    
    def test_create_task_success(self, handler):
        """Test successful task creation."""
        context = ChatContext(
            session_id='test',
            message='add task: buy groceries',
            intent={
                'action': 'task_create',
                'task_data': {'title': 'buy groceries', 'priority': 'medium', 'context': 'errands'}
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.task.task_manager') as mock_manager:
            mock_task = Mock(id='task-123', title='buy groceries')
            mock_manager.create_task.return_value = mock_task
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'created' in response.answer.lower()
            assert 'groceries' in response.answer.lower()
    
    def test_create_task_no_title(self, handler):
        """Test creating task without title."""
        context = ChatContext(
            session_id='test',
            message='add task',
            intent={
                'action': 'task_create',
                'task_data': {'title': '', 'priority': 'medium'}
            },
            history=[],
            last_user_message='',
        )
        
        response = handler.handle(context)
        
        assert response.is_final is True
        assert 'specify' in response.answer.lower() or 'error' in response.answer.lower()


class TestTaskListHandler:
    """Tests for TaskListHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.task import TaskListHandler
        return TaskListHandler()
    
    def test_list_tasks_with_results(self, handler):
        """Test listing tasks when some exist."""
        context = ChatContext(
            session_id='test',
            message='what are my tasks?',
            intent={'action': 'task_list', 'tool': 'task_list'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.task.task_manager') as mock_manager:
            from app.services.task_manager import TaskStatus, TaskPriority
            
            mock_task = Mock()
            mock_task.title = 'Buy groceries'
            mock_task.status = TaskStatus.TODO
            mock_task.priority = TaskPriority.MEDIUM
            mock_task.due_date = None
            
            mock_manager.list_tasks.return_value = [mock_task]
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'groceries' in response.answer.lower()


# ============================================================================
# Alert Handlers Tests
# ============================================================================

class TestAlertCreateHandler:
    """Tests for AlertCreateHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.alert import AlertCreateHandler
        return AlertCreateHandler()
    
    def test_create_recurring_alert(self, handler):
        """Test creating a recurring alert."""
        context = ChatContext(
            session_id='test',
            message='remind me every Monday to review tasks',
            intent={
                'action': 'alert_create',
                'alert_data': {
                    'title': 'Weekly task review',
                    'description': 'Review tasks every Monday',
                    'trigger_date': 'Monday',
                    'recurring': 'weekly'
                }
            },
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.alert.alert_store') as mock_store:
            mock_alert = Mock(alert_id='alert-123')
            mock_store.create_alert.return_value = mock_alert
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'created' in response.answer.lower()
            assert 'weekly' in response.answer.lower()


# ============================================================================
# Report Handlers Tests
# ============================================================================

class TestVaultHealthHandler:
    """Tests for VaultHealthHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.report import VaultHealthHandler
        return VaultHealthHandler()
    
    def test_vault_health_check(self, handler):
        """Test vault health check."""
        context = ChatContext(
            session_id='test',
            message="how's my vault?",
            intent={'action': 'vault_health'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.obsidian_knowledge.obsidian_knowledge') as mock_knowledge:
            mock_knowledge.run_health_check.return_value = {
                'health_score': 85,
                'status': 'good',
                'summary': {
                    'inbox_backlog': 5,
                    'stale_notes': 10,
                    'missing_tags': 3,
                    'misplaced_notes': 2,
                },
                'recommendations': ['Process inbox notes', 'Review stale notes'],
            }
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert '85' in response.answer
            assert 'inbox' in response.answer.lower()


class TestBudgetStatusHandler:
    """Tests for BudgetStatusHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.report import BudgetStatusHandler
        return BudgetStatusHandler()
    
    def test_budget_status(self, handler):
        """Test budget status check."""
        context = ChatContext(
            session_id='test',
            message='show skipped alerts',
            intent={'action': 'budget_status'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.proactive_monitor.proactive_monitor') as mock_monitor:
            mock_monitor.get_budget_stats.return_value = {
                'date': 'today',
                'messages_sent': 3,
                'remaining': 2,
                'user_responses': 2,
                'ignored': 1,
            }
            mock_monitor.get_skipped_alerts.return_value = []
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert 'budget' in response.answer.lower()
            assert '3' in response.answer  # messages_sent


# ============================================================================
# Web Search Handler Tests
# ============================================================================

class TestWebSearchHandler:
    """Tests for WebSearchHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.web_search import WebSearchHandler
        return WebSearchHandler()
    
    def test_web_search_success(self, handler):
        """Test successful web search."""
        context = ChatContext(
            session_id='test',
            message='what is the latest news about AI?',
            intent={'action': 'web_search'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.web_search.web_search_service') as mock_search:
            mock_search.search.return_value = (
                "Title: AI Breakthrough\n"
                "Snippet: New AI model released...\n"
                "URL: https://example.com/ai"
            )
            
            with patch('app.services.chat.handlers.web_search.llm_service') as mock_llm:
                mock_llm.call.return_value = "Here's the latest AI news: A new model was released."
                
                response = handler.handle(context)
                
                assert response.is_final is True
                assert response.used_web is True
                assert 'AI' in response.answer
                mock_search.search.assert_called_once()
    
    def test_web_search_no_results(self, handler):
        """Test web search with no results."""
        context = ChatContext(
            session_id='test',
            message='xyzabc123nonexistent',
            intent={'action': 'web_search'},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.web_search.web_search_service') as mock_search:
            mock_search.search.return_value = ""
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert response.used_web is True
            assert "couldn't find" in response.answer.lower()


# ============================================================================
# Health Query Handler Tests
# ============================================================================

class TestHealthQueryHandler:
    """Tests for HealthQueryHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.health import HealthQueryHandler
        return HealthQueryHandler()
    
    def test_health_query_sleep(self, handler):
        """Test health query for sleep data."""
        context = ChatContext(
            session_id='test',
            message='how did I sleep last night?',
            intent={'action': 'health_query'},
            history=[],
            last_user_message='',
        )
        
        # Mock the health coach
        mock_coach = MagicMock()
        mock_coach.get_sleep_data.return_value = {
            'sleep_records': [{
                'date': '2024-01-15',
                'total_sleep': '7h 30m',
                'total_sleep_hours': 7.5,
                'deep_sleep': '1h 45m',
                'deep_sleep_hours': 1.75,
                'light_sleep': '4h 0m',
                'light_sleep_hours': 4.0,
                'rem_sleep': '1h 45m',
                'rem_sleep_hours': 1.75,
                'sleep_score': 82,
                'quality': 'excellent',
                'awake_count': 2,
                'awake_time_min': 15,
                'restless_moments': 25,
                'resting_hr': 52,
                'hrv': 55,
                'avg_sleep_stress': 18,
                'body_battery_change': 65,
                'avg_spo2': 96,
                'lowest_spo2': 92,
                'avg_respiration': 14,
            }]
        }
        
        handler._health_coach = mock_coach
        
        with patch('app.services.chat.handlers.health.llm_service') as mock_llm:
            mock_llm.call.return_value = "You slept 7h 30m with a score of 82 (excellent)."
            
            response = handler.handle(context)
            
            assert response.is_final is True
            assert response.used_health is True
            mock_coach.get_sleep_data.assert_called()
    
    def test_health_query_no_data(self, handler):
        """Test health query when no data is available."""
        context = ChatContext(
            session_id='test',
            message='how is my recovery?',
            intent={'action': 'health_query'},
            history=[],
            last_user_message='',
        )
        
        # Mock health coach returning empty data
        mock_coach = MagicMock()
        mock_coach.get_sleep_data.return_value = {'sleep_records': []}
        mock_coach.get_recovery_status.return_value = {}
        mock_coach.get_running_summary.return_value = {}
        mock_coach.get_recent_activities.return_value = {'activities': []}
        
        handler._health_coach = mock_coach
        
        response = handler.handle(context)
        
        assert response.is_final is True
        assert response.used_health is True
        assert "couldn't fetch" in response.answer.lower()


# ============================================================================
# General Handler Tests
# ============================================================================

class TestGeneralHandler:
    """Tests for GeneralHandler."""
    
    @pytest.fixture
    def handler(self):
        from app.services.chat.handlers.general import GeneralHandler
        return GeneralHandler()
    
    def test_general_greeting(self, handler):
        """Test general handler with a simple greeting."""
        context = ChatContext(
            session_id='test',
            message='hey friday!',
            intent={'action': 'general', 'use_rag': False, 'use_memory': False},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.general.llm_service') as mock_llm:
            mock_llm.call.return_value = "Hey! What's up?"
            
            with patch('app.services.chat.handlers.general.conversation_memory') as mock_conv:
                mock_conv.get_context_for_message.return_value = ""
                
                with patch('app.services.chat.handlers.general.relationship_tracker') as mock_rel:
                    mock_rel.get_context_for_llm.return_value = ""
                    mock_rel.detect_mood.return_value = MagicMock(value="neutral")
                    
                    with patch('app.services.chat.handlers.general.opinion_store') as mock_op:
                        mock_op.get_context_for_llm.return_value = ""
                        
                        with patch('app.services.chat.handlers.general.obsidian_knowledge') as mock_obs:
                            mock_obs.get_context_for_llm.return_value = ""
                            
                            with patch('app.services.chat.handlers.general.post_chat_processor'):
                                with patch.object(handler, '_load_personality', return_value="You are Friday."):
                                    response = handler.handle(context)
                                    
                                    assert response.is_final is True
                                    assert "Hey" in response.answer
    
    def test_general_with_rag(self, handler):
        """Test general handler with RAG enabled."""
        context = ChatContext(
            session_id='test',
            message='what are my project ideas?',
            intent={'action': 'general', 'use_rag': True, 'use_memory': False},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.chat.handlers.general.vector_store') as mock_vs:
            mock_vs.query_obsidian.return_value = (
                "Project idea: Build a personal AI assistant",
                [{'content': 'AI assistant project', 'source': 'Projects.md'}]
            )
            
            with patch('app.services.chat.handlers.general.llm_service') as mock_llm:
                mock_llm.call.return_value = "Your project ideas include building a personal AI assistant."
                
                with patch('app.services.chat.handlers.general.conversation_memory') as mock_conv:
                    mock_conv.get_context_for_message.return_value = ""
                    
                    with patch('app.services.chat.handlers.general.relationship_tracker') as mock_rel:
                        mock_rel.get_context_for_llm.return_value = ""
                        mock_rel.detect_mood.return_value = MagicMock(value="neutral")
                        
                        with patch('app.services.chat.handlers.general.opinion_store') as mock_op:
                            mock_op.get_context_for_llm.return_value = ""
                            
                            with patch('app.services.chat.handlers.general.obsidian_knowledge') as mock_obs:
                                mock_obs.get_context_for_llm.return_value = ""
                                
                                with patch('app.services.chat.handlers.general.post_chat_processor'):
                                    with patch.object(handler, '_load_personality', return_value=""):
                                        response = handler.handle(context)
                                        
                                        assert response.is_final is True
                                        assert response.used_rag is True
                                        assert len(response.obsidian_chunks) > 0
    
    def test_general_with_memory(self, handler):
        """Test general handler with memory search enabled."""
        context = ChatContext(
            session_id='test',
            message='when is my birthday?',
            intent={'action': 'general', 'use_rag': False, 'use_memory': True},
            history=[],
            last_user_message='',
        )
        
        with patch('app.services.memory_store.MemoryStore') as MockMemoryStore:
            mock_store = MagicMock()
            mock_store.search_memories.return_value = [
                {'id': '1', 'content': 'Birthday is March 30', 'full_content': 'Birthday is March 30'}
            ]
            MockMemoryStore.return_value = mock_store
            
            with patch('app.services.chat.handlers.general.llm_service') as mock_llm:
                mock_llm.call.return_value = "Your birthday is March 30."
                
                with patch('app.services.chat.handlers.general.conversation_memory') as mock_conv:
                    mock_conv.get_context_for_message.return_value = ""
                    
                    with patch('app.services.chat.handlers.general.relationship_tracker') as mock_rel:
                        mock_rel.get_context_for_llm.return_value = ""
                        mock_rel.detect_mood.return_value = MagicMock(value="neutral")
                        
                        with patch('app.services.chat.handlers.general.opinion_store') as mock_op:
                            mock_op.get_context_for_llm.return_value = ""
                            
                            with patch('app.services.chat.handlers.general.obsidian_knowledge') as mock_obs:
                                mock_obs.get_context_for_llm.return_value = ""
                                
                                with patch('app.services.chat.handlers.general.post_chat_processor'):
                                    with patch.object(handler, '_load_user_profile', return_value=''):
                                        with patch.object(handler, '_load_personality', return_value=""):
                                            response = handler.handle(context)
                                            
                                            assert response.is_final is True
                                            assert response.used_memory is True
    
    def test_general_who_am_i(self, handler):
        """Test general handler with 'who am I' query loads user profile."""
        context = ChatContext(
            session_id='test',
            message='who am I?',
            intent={'action': 'general', 'use_rag': True, 'use_memory': True},
            history=[],
            last_user_message='',
        )
        
        with patch.object(handler, '_load_user_profile') as mock_profile:
            mock_profile.return_value = "# Artur Gomes\nSoftware engineer..."
            
            with patch('app.services.chat.handlers.general.vector_store') as mock_vs:
                mock_vs.query_obsidian.return_value = ("", [])
                
                with patch('app.services.memory_store.MemoryStore') as MockMemoryStore:
                    mock_store = MagicMock()
                    mock_store.search_memories.return_value = []
                    MockMemoryStore.return_value = mock_store
                    
                    with patch('app.services.chat.handlers.general.llm_service') as mock_llm:
                        mock_llm.call.return_value = "You are Artur Gomes, a software engineer."
                        
                        with patch('app.services.chat.handlers.general.conversation_memory') as mock_conv:
                            mock_conv.get_context_for_message.return_value = ""
                            
                            with patch('app.services.chat.handlers.general.relationship_tracker') as mock_rel:
                                mock_rel.get_context_for_llm.return_value = ""
                                mock_rel.detect_mood.return_value = MagicMock(value="neutral")
                                
                                with patch('app.services.chat.handlers.general.opinion_store') as mock_op:
                                    mock_op.get_context_for_llm.return_value = ""
                                    
                                    with patch('app.services.chat.handlers.general.obsidian_knowledge') as mock_obs:
                                        mock_obs.get_context_for_llm.return_value = ""
                                        
                                        with patch('app.services.chat.handlers.general.post_chat_processor'):
                                            with patch.object(handler, '_load_personality', return_value=""):
                                                response = handler.handle(context)
                                                
                                                mock_profile.assert_called()
                                                assert response.is_final is True
