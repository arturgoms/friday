"""Unit tests for reminders service."""
import pytest
import sys
import os
from datetime import datetime, timedelta
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.services.reminders import ReminderService, Reminder
from app.core.config import settings


@pytest.mark.unit
class TestReminderService:
    """Test reminder service functionality."""
    
    @pytest.fixture
    def temp_reminder_file(self):
        """Create temporary file for reminders."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def reminder_service(self, temp_reminder_file):
        """Create ReminderService with temporary storage."""
        return ReminderService(storage_path=temp_reminder_file)
    
    def test_create_reminder_with_minutes(self, reminder_service):
        """Test creating reminder X minutes from now."""
        reminder = reminder_service.create_reminder(
            message="Test reminder",
            minutes=30
        )
        
        assert reminder.message == "Test reminder"
        assert reminder.status == "pending"
        assert reminder.id is not None
        
        # Check time is approximately 30 minutes from now
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        expected_time = now + timedelta(minutes=30)
        
        time_diff = abs((reminder.remind_at - expected_time).total_seconds())
        assert time_diff < 5, "Reminder time should be approximately 30 minutes from now"
    
    def test_create_reminder_with_hours(self, reminder_service):
        """Test creating reminder X hours from now."""
        reminder = reminder_service.create_reminder(
            message="Test in 2 hours",
            hours=2
        )
        
        assert reminder.message == "Test in 2 hours"
        
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        expected_time = now + timedelta(hours=2)
        
        time_diff = abs((reminder.remind_at - expected_time).total_seconds())
        assert time_diff < 5
    
    def test_create_reminder_at_time(self, reminder_service):
        """Test creating reminder at specific time."""
        reminder = reminder_service.create_reminder(
            message="Test at 3pm",
            at_time="15:00"
        )
        
        assert reminder.remind_at.hour == 15
        assert reminder.remind_at.minute == 0
    
    def test_list_pending_reminders(self, reminder_service):
        """Test listing pending reminders."""
        # Create some reminders
        reminder_service.create_reminder("Test 1", minutes=10)
        reminder_service.create_reminder("Test 2", hours=1)
        
        pending = reminder_service.list_pending_reminders()
        
        assert len(pending) == 2
        assert all(r.status == "pending" for r in pending)
    
    def test_cancel_reminder(self, reminder_service):
        """Test cancelling a reminder."""
        reminder = reminder_service.create_reminder("Test", minutes=10)
        
        result = reminder_service.cancel_reminder(reminder.id)
        
        assert result is True
        
        # Check status changed
        pending = reminder_service.list_pending_reminders()
        assert len(pending) == 0
    
    def test_update_reminder_time(self, reminder_service):
        """Test updating reminder time."""
        reminder = reminder_service.create_reminder("Test", minutes=10)
        original_time = reminder.remind_at
        
        result = reminder_service.update_reminder_time(reminder.id, minutes=20)
        
        assert result is True
        
        # Get updated reminder
        pending = reminder_service.list_pending_reminders()
        updated = pending[0]
        
        assert updated.remind_at > original_time
    
    def test_persistence(self, temp_reminder_file):
        """Test that reminders persist to file."""
        # Create service and add reminder
        service1 = ReminderService(storage_path=temp_reminder_file)
        service1.create_reminder("Persist test", minutes=30)
        
        # Create new service instance (simulating restart)
        service2 = ReminderService(storage_path=temp_reminder_file)
        
        pending = service2.list_pending_reminders()
        assert len(pending) == 1
        assert pending[0].message == "Persist test"
    
    def test_old_reminders_cleanup(self, temp_reminder_file):
        """Test that old completed reminders are cleaned up on load."""
        # Create a reminder and mark as sent
        service = ReminderService(storage_path=temp_reminder_file)
        reminder = service.create_reminder("Old", minutes=1)
        reminder.status = "sent"
        
        # Make it old (8 days ago)
        user_tz = settings.user_timezone
        reminder.created_at = datetime.now(user_tz) - timedelta(days=8)
        service.save_reminders()
        
        # Reload - old sent reminder should be cleaned
        service2 = ReminderService(storage_path=temp_reminder_file)
        
        # Should be cleaned up
        all_reminders = service2.reminders
        assert len(all_reminders) == 0, "Old completed reminders should be cleaned up"


@pytest.mark.unit
class TestReminderModel:
    """Test Reminder data model."""
    
    def test_reminder_to_dict(self):
        """Test reminder serialization."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        reminder = Reminder(
            id="test123",
            message="Test message",
            remind_at=now,
            created_at=now,
            status="pending"
        )
        
        data = reminder.to_dict()
        
        assert data["id"] == "test123"
        assert data["message"] == "Test message"
        assert data["status"] == "pending"
        assert "remind_at" in data
        assert "created_at" in data
    
    def test_reminder_from_dict(self):
        """Test reminder deserialization."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        data = {
            "id": "test456",
            "message": "Test",
            "remind_at": now.isoformat(),
            "created_at": now.isoformat(),
            "status": "pending"
        }
        
        reminder = Reminder.from_dict(data)
        
        assert reminder.id == "test456"
        assert reminder.message == "Test"
        assert reminder.status == "pending"
        assert isinstance(reminder.remind_at, datetime)
        assert isinstance(reminder.created_at, datetime)
