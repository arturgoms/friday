"""Unit tests for task_manager service."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from app.services.task_manager import (
    TaskManager, Task, TaskPriority, TaskStatus, TaskContext, TaskEnergyLevel
)


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
        task = task_manager.create_task(
            title="Test task",
            description="This is a test"
        )
        
        assert task is not None
        assert task.id is not None
        assert task.title == "Test task"
        assert task.description == "This is a test"
        assert task.status == TaskStatus.TODO
        assert task.priority == TaskPriority.MEDIUM
    
    def test_create_task_with_priority(self, task_manager):
        """Test creating task with different priorities."""
        for priority in [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH, TaskPriority.URGENT]:
            task = task_manager.create_task(
                title=f"Task with {priority.name} priority",
                priority=priority
            )
            assert task.priority == priority
    
    def test_create_task_with_context(self, task_manager):
        """Test creating task with context."""
        task = task_manager.create_task(
            title="Work task",
            context=TaskContext.WORK
        )
        assert task.context == TaskContext.WORK
    
    def test_create_task_with_due_date(self, task_manager):
        """Test creating task with due date."""
        tomorrow = datetime.now() + timedelta(days=1)
        task = task_manager.create_task(
            title="Task due tomorrow",
            due_date=tomorrow
        )
        
        assert task.due_date is not None
        assert task.due_date.date() == tomorrow.date()
    
    def test_create_task_with_project_and_people(self, task_manager):
        """Test creating task with project and people."""
        task = task_manager.create_task(
            title="Team meeting",
            related_project="Friday AI",
            related_people=["Alice", "Bob"]
        )
        assert task.related_project == "Friday AI"
        assert "Alice" in task.related_people
        assert "Bob" in task.related_people


class TestTaskRetrieval:
    """Test task retrieval functionality."""
    
    def test_get_nonexistent_task(self, task_manager):
        """Test getting a task that doesn't exist."""
        task = task_manager.get_task("nonexistent-uuid")
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
        task = task_manager.create_task(title="Test task")
        task_manager.update_task_status(task.id, TaskStatus.DONE)
        
        todo_tasks = task_manager.list_tasks(status=TaskStatus.TODO)
        done_tasks = task_manager.list_tasks(status=TaskStatus.DONE)
        
        assert len(todo_tasks) == 0
        assert len(done_tasks) == 1
    
    def test_filter_by_priority(self, task_manager):
        """Test filtering tasks by priority."""
        task_manager.create_task(title="Low priority", priority=TaskPriority.LOW)
        task_manager.create_task(title="High priority", priority=TaskPriority.HIGH)
        
        high_tasks = task_manager.list_tasks(priority=TaskPriority.HIGH)
        assert len(high_tasks) == 1
        assert high_tasks[0].title == "High priority"
    
    def test_filter_by_context(self, task_manager):
        """Test filtering tasks by context."""
        task_manager.create_task(title="Work task", context=TaskContext.WORK)
        task_manager.create_task(title="Home task", context=TaskContext.HOME)
        
        work_tasks = task_manager.list_tasks(context=TaskContext.WORK)
        assert len(work_tasks) == 1
        assert work_tasks[0].title == "Work task"
    
    def test_get_today_tasks(self, task_manager):
        """Test getting tasks due today."""
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        # Create task due today
        task_manager.create_task(title="Due today", due_date=today)
        
        # Create task due tomorrow
        task_manager.create_task(title="Due tomorrow", due_date=tomorrow)
        
        today_tasks = task_manager.get_tasks_for_today()
        assert len(today_tasks) == 1
        assert today_tasks[0].title == "Due today"


class TestTaskUpdates:
    """Test task update functionality."""
    
    def test_update_task_status(self, task_manager):
        """Test updating task status."""
        task = task_manager.create_task(title="Test task")
        
        task_manager.update_task_status(task.id, TaskStatus.IN_PROGRESS)
        updated = task_manager.get_task(task.id)
        assert updated.status == TaskStatus.IN_PROGRESS
        
        task_manager.update_task_status(task.id, TaskStatus.DONE)
        updated = task_manager.get_task(task.id)
        assert updated.status == TaskStatus.DONE
    
    def test_schedule_task(self, task_manager):
        """Test scheduling a task."""
        task = task_manager.create_task(title="Schedule me")
        
        scheduled_time = datetime.now() + timedelta(hours=2)
        result = task_manager.schedule_task(task.id, scheduled_time)
        
        assert result is True
        updated = task_manager.get_task(task.id)
        assert updated.scheduled_for is not None


class TestTaskModel:
    """Test Task model functionality."""
    
    def test_task_to_dict(self, task_manager):
        """Test converting task to dictionary."""
        task = task_manager.create_task(
            title="Test task",
            description="Description",
            priority=TaskPriority.HIGH,
            context=TaskContext.WORK
        )
        
        task_dict = task.to_dict()
        
        assert task_dict["title"] == "Test task"
        assert task_dict["description"] == "Description"
        assert task_dict["priority"] == "HIGH"
        assert task_dict["context"] == "WORK"
        assert "id" in task_dict
        assert "created_at" in task_dict
    
    def test_task_from_dict(self):
        """Test creating task from dictionary."""
        data = {
            "id": "test-uuid",
            "title": "From dict",
            "description": "Test description",
            "priority": "HIGH",
            "status": "todo",  # TaskStatus uses lowercase values
            "context": "WORK",
            "energy_level": "MEDIUM",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        task = Task.from_dict(data)
        
        assert task.id == "test-uuid"
        assert task.title == "From dict"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.TODO
        assert task.context == TaskContext.WORK


class TestDueDateFiltering:
    """Test due date filtering functionality."""
    
    def test_tasks_due_today(self, task_manager):
        """Test filtering for tasks due today."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        task_manager.create_task(title="Yesterday", due_date=yesterday)
        task_manager.create_task(title="Today", due_date=today)
        task_manager.create_task(title="Tomorrow", due_date=tomorrow)
        
        today_tasks = task_manager.get_tasks_for_today()
        
        # Should only include today's task
        titles = [t.title for t in today_tasks]
        assert "Today" in titles
        assert "Yesterday" not in titles
        assert "Tomorrow" not in titles
