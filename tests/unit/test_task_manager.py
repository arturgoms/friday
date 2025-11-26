"""Unit tests for task_manager service."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from app.services.task_manager import TaskManager
from app.core.config import settings


@pytest.fixture
def temp_task_db(tmp_path):
    """Create a temporary task database for testing."""
    db_path = tmp_path / "test_tasks.db"
    return db_path


@pytest.fixture
def task_manager(temp_task_db):
    """Create a task manager with temporary database."""
    tm = TaskManager(db_path=str(temp_task_db))
    yield tm
    # Cleanup after test
    if temp_task_db.exists():
        temp_task_db.unlink()


class TestTaskCreation:
    """Test task creation functionality."""
    
    def test_create_basic_task(self, task_manager):
        """Test creating a basic task with minimal info."""
        task_id = task_manager.create_task(
            title="Test task",
            description="This is a test"
        )
        
        assert task_id is not None
        task = task_manager.get_task(task_id)
        assert task["title"] == "Test task"
        assert task["description"] == "This is a test"
        assert task["status"] == "pending"
        assert task["priority"] == "Medium"
    
    def test_create_task_with_priority(self, task_manager):
        """Test creating task with different priorities."""
        for priority in ["Low", "Medium", "High", "Urgent"]:
            task_id = task_manager.create_task(
                title=f"Task with {priority} priority",
                priority=priority
            )
            task = task_manager.get_task(task_id)
            assert task["priority"] == priority
    
    def test_create_task_with_context(self, task_manager):
        """Test creating task with context."""
        task_id = task_manager.create_task(
            title="Work task",
            context="work"
        )
        task = task_manager.get_task(task_id)
        assert task["context"] == "work"
    
    def test_create_task_with_natural_language_due_date(self, task_manager):
        """Test creating task with natural language due dates."""
        # Test "tomorrow"
        task_id = task_manager.create_task(
            title="Task due tomorrow",
            due_date_str="tomorrow"
        )
        task = task_manager.get_task(task_id)
        
        # Due date should be tomorrow
        user_tz = settings.user_timezone
        tomorrow = (datetime.now(user_tz) + timedelta(days=1)).date()
        task_due = datetime.fromisoformat(task["due_date"]).date()
        assert task_due == tomorrow
    
    def test_create_task_with_project_and_people(self, task_manager):
        """Test creating task with project and people."""
        task_id = task_manager.create_task(
            title="Team meeting",
            project="Friday AI",
            people=["Alice", "Bob"]
        )
        task = task_manager.get_task(task_id)
        assert task["project"] == "Friday AI"
        
        # People should be stored as JSON
        import json
        people = json.loads(task["people"])
        assert "Alice" in people
        assert "Bob" in people


class TestTaskRetrieval:
    """Test task retrieval functionality."""
    
    def test_get_nonexistent_task(self, task_manager):
        """Test getting a task that doesn't exist."""
        task = task_manager.get_task(99999)
        assert task is None
    
    def test_list_empty_tasks(self, task_manager):
        """Test listing tasks when none exist."""
        tasks = task_manager.list_tasks()
        assert tasks == []
    
    def test_list_all_tasks(self, task_manager):
        """Test listing all tasks."""
        # Create multiple tasks
        task_manager.create_task(title="Task 1")
        task_manager.create_task(title="Task 2")
        task_manager.create_task(title="Task 3")
        
        tasks = task_manager.list_tasks()
        assert len(tasks) == 3
    
    def test_filter_by_status(self, task_manager):
        """Test filtering tasks by status."""
        task_id = task_manager.create_task(title="Test task")
        task_manager.update_task(task_id, status="completed")
        
        pending = task_manager.list_tasks(status="pending")
        completed = task_manager.list_tasks(status="completed")
        
        assert len(pending) == 0
        assert len(completed) == 1
    
    def test_filter_by_priority(self, task_manager):
        """Test filtering tasks by priority."""
        task_manager.create_task(title="Low priority", priority="Low")
        task_manager.create_task(title="High priority", priority="High")
        
        high_tasks = task_manager.list_tasks(priority="High")
        assert len(high_tasks) == 1
        assert high_tasks[0]["title"] == "High priority"
    
    def test_filter_by_context(self, task_manager):
        """Test filtering tasks by context."""
        task_manager.create_task(title="Work task", context="work")
        task_manager.create_task(title="Home task", context="home")
        
        work_tasks = task_manager.list_tasks(context="work")
        assert len(work_tasks) == 1
        assert work_tasks[0]["title"] == "Work task"
    
    def test_get_today_tasks(self, task_manager):
        """Test getting tasks due today."""
        # Create task due today
        task_manager.create_task(title="Due today", due_date_str="today")
        
        # Create task due tomorrow
        task_manager.create_task(title="Due tomorrow", due_date_str="tomorrow")
        
        today_tasks = task_manager.get_today_tasks()
        assert len(today_tasks) == 1
        assert today_tasks[0]["title"] == "Due today"


class TestTaskUpdates:
    """Test task update functionality."""
    
    def test_update_task_title(self, task_manager):
        """Test updating task title."""
        task_id = task_manager.create_task(title="Original title")
        task_manager.update_task(task_id, title="Updated title")
        
        task = task_manager.get_task(task_id)
        assert task["title"] == "Updated title"
    
    def test_update_task_status(self, task_manager):
        """Test updating task status."""
        task_id = task_manager.create_task(title="Test task")
        
        task_manager.update_task(task_id, status="in_progress")
        task = task_manager.get_task(task_id)
        assert task["status"] == "in_progress"
        
        task_manager.update_task(task_id, status="completed")
        task = task_manager.get_task(task_id)
        assert task["status"] == "completed"
    
    def test_update_task_priority(self, task_manager):
        """Test updating task priority."""
        task_id = task_manager.create_task(title="Test task", priority="Low")
        task_manager.update_task(task_id, priority="Urgent")
        
        task = task_manager.get_task(task_id)
        assert task["priority"] == "Urgent"
    
    def test_update_multiple_fields(self, task_manager):
        """Test updating multiple fields at once."""
        task_id = task_manager.create_task(title="Test task")
        task_manager.update_task(
            task_id,
            title="Updated title",
            status="in_progress",
            priority="High",
            context="work"
        )
        
        task = task_manager.get_task(task_id)
        assert task["title"] == "Updated title"
        assert task["status"] == "in_progress"
        assert task["priority"] == "High"
        assert task["context"] == "work"
    
    def test_updated_at_timestamp(self, task_manager):
        """Test that updated_at timestamp changes on update."""
        task_id = task_manager.create_task(title="Test task")
        
        task1 = task_manager.get_task(task_id)
        created_at = task1["created_at"]
        updated_at_1 = task1["updated_at"]
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.1)
        
        task_manager.update_task(task_id, title="Updated")
        task2 = task_manager.get_task(task_id)
        updated_at_2 = task2["updated_at"]
        
        # created_at should not change
        assert task2["created_at"] == created_at
        # updated_at should change
        assert updated_at_2 != updated_at_1


class TestNaturalLanguageDueDates:
    """Test natural language due date parsing."""
    
    def test_parse_today(self, task_manager):
        """Test parsing 'today'."""
        task_id = task_manager.create_task(title="Test", due_date_str="today")
        task = task_manager.get_task(task_id)
        
        user_tz = settings.user_timezone
        today = datetime.now(user_tz).date()
        task_due = datetime.fromisoformat(task["due_date"]).date()
        assert task_due == today
    
    def test_parse_tomorrow(self, task_manager):
        """Test parsing 'tomorrow'."""
        task_id = task_manager.create_task(title="Test", due_date_str="tomorrow")
        task = task_manager.get_task(task_id)
        
        user_tz = settings.user_timezone
        tomorrow = (datetime.now(user_tz) + timedelta(days=1)).date()
        task_due = datetime.fromisoformat(task["due_date"]).date()
        assert task_due == tomorrow
    
    def test_parse_next_week(self, task_manager):
        """Test parsing 'next week'."""
        task_id = task_manager.create_task(title="Test", due_date_str="next week")
        task = task_manager.get_task(task_id)
        
        user_tz = settings.user_timezone
        next_week = (datetime.now(user_tz) + timedelta(days=7)).date()
        task_due = datetime.fromisoformat(task["due_date"]).date()
        assert task_due == next_week
    
    def test_parse_specific_date(self, task_manager):
        """Test parsing specific date format."""
        task_id = task_manager.create_task(title="Test", due_date_str="2024-12-25")
        task = task_manager.get_task(task_id)
        
        task_due = datetime.fromisoformat(task["due_date"]).date()
        assert task_due.year == 2024
        assert task_due.month == 12
        assert task_due.day == 25


class TestDueSoonFilter:
    """Test due_soon filtering."""
    
    def test_due_soon_filter(self, task_manager):
        """Test filtering tasks due within 7 days."""
        # Create task due today
        task_manager.create_task(title="Due today", due_date_str="today")
        
        # Create task due tomorrow
        task_manager.create_task(title="Due tomorrow", due_date_str="tomorrow")
        
        # Create task due next week
        task_manager.create_task(title="Due next week", due_date_str="next week")
        
        # Create task due in 2 weeks (should not appear)
        user_tz = settings.user_timezone
        future_date = (datetime.now(user_tz) + timedelta(days=14)).strftime("%Y-%m-%d")
        task_manager.create_task(title="Due in 2 weeks", due_date_str=future_date)
        
        # Get tasks due soon (within 7 days)
        due_soon = task_manager.list_tasks(due_soon=True)
        
        # Should have 3 tasks: today, tomorrow, and next week (7 days)
        # The 14-day task should not appear
        assert len(due_soon) >= 2  # At least today and tomorrow
        
        titles = [t["title"] for t in due_soon]
        assert "Due today" in titles
        assert "Due tomorrow" in titles
        assert "Due in 2 weeks" not in titles
