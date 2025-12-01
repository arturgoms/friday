"""Reminder service for scheduling notifications."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional
from app.core.logging import logger
import threading
import time


class Reminder:
    """Reminder data structure."""
    
    def __init__(
        self,
        id: str,
        message: str,
        remind_at: datetime,
        created_at: datetime,
        status: str = "pending"
    ):
        self.id = id
        self.message = message
        self.remind_at = remind_at
        self.created_at = created_at
        self.status = status  # pending, sent, cancelled
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "message": self.message,
            "remind_at": self.remind_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Reminder':
        return cls(
            id=data["id"],
            message=data["message"],
            remind_at=datetime.fromisoformat(data["remind_at"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            status=data.get("status", "pending"),
        )


class ReminderService:
    """Service for managing reminders."""
    
    def __init__(self, storage_path: str = None):
        from app.core.config import settings
        # Use brain folder for reminders (Syncthing synced)
        if storage_path is None:
            storage_path = settings.reminders_path / "reminders.json"
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.reminders: List[Reminder] = []
        self.running = False
        self.thread = None
        self.load_reminders()
    
    def load_reminders(self):
        """Load reminders from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.reminders = [Reminder.from_dict(r) for r in data]
                    # Remove old completed reminders (older than 7 days)
                    from app.core.config import settings
                    user_tz = settings.user_timezone
                    cutoff = datetime.now(user_tz) - timedelta(days=7)
                    
                    # Make cutoff timezone-naive if needed for comparison
                    filtered_reminders = []
                    for r in self.reminders:
                        if r.status == "pending":
                            filtered_reminders.append(r)
                        else:
                            # Compare datetimes (handle both naive and aware)
                            created = r.created_at
                            if created.tzinfo is None and cutoff.tzinfo is not None:
                                created = created.replace(tzinfo=cutoff.tzinfo)
                            elif created.tzinfo is not None and cutoff.tzinfo is None:
                                cutoff = cutoff.replace(tzinfo=created.tzinfo)
                            
                            if created > cutoff:
                                filtered_reminders.append(r)
                    
                    self.reminders = filtered_reminders
                    logger.info(f"Loaded {len(self.reminders)} reminders")
            except Exception as e:
                logger.error(f"Failed to load reminders: {e}")
                self.reminders = []
        else:
            self.reminders = []
    
    def save_reminders(self):
        """Save reminders to storage."""
        try:
            with open(self.storage_path, 'w') as f:
                data = [r.to_dict() for r in self.reminders]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")
    
    def create_reminder(
        self,
        message: str,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        at_time: Optional[str] = None,
        on_date: Optional[str] = None
    ) -> Reminder:
        """
        Create a new reminder.
        
        Args:
            message: What to remind about
            minutes: Remind in X minutes from now
            hours: Remind in X hours from now
            at_time: Remind at specific time today (HH:MM format)
            on_date: Remind on specific date (YYYY-MM-DD HH:MM)
        
        Returns:
            Created reminder
        """
        # Use user's timezone
        from app.core.config import settings
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        # Calculate remind time
        if minutes:
            remind_at = now + timedelta(minutes=minutes)
        elif hours:
            remind_at = now + timedelta(hours=hours)
        elif at_time:
            # Parse HH:MM and set for today in user's timezone
            hour, minute = map(int, at_time.split(':'))
            remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If time has passed, schedule for tomorrow
            if remind_at < now:
                remind_at += timedelta(days=1)
        elif on_date:
            remind_at = datetime.fromisoformat(on_date)
        else:
            raise ValueError("Must specify when to remind (minutes, hours, at_time, or on_date)")
        
        reminder = Reminder(
            id=str(uuid.uuid4()),
            message=message,
            remind_at=remind_at,
            created_at=now,
            status="pending"
        )
        
        self.reminders.append(reminder)
        self.save_reminders()
        
        logger.info(f"Created reminder: {message} at {remind_at}")
        return reminder
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a reminder."""
        for reminder in self.reminders:
            if reminder.id == reminder_id:
                reminder.status = "cancelled"
                self.save_reminders()
                logger.info(f"Cancelled reminder: {reminder_id}")
                return True
        return False
    
    def update_reminder_time(
        self,
        reminder_id: str,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        at_time: Optional[str] = None
    ) -> bool:
        """Update the time of an existing reminder."""
        for reminder in self.reminders:
            if reminder.id == reminder_id and reminder.status == "pending":
                from app.core.config import settings
                user_tz = settings.user_timezone
                now = datetime.now(user_tz)
                
                if minutes:
                    reminder.remind_at = now + timedelta(minutes=minutes)
                elif hours:
                    reminder.remind_at = now + timedelta(hours=hours)
                elif at_time:
                    hour, minute = map(int, at_time.split(':'))
                    remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if remind_at < now:
                        remind_at += timedelta(days=1)
                    reminder.remind_at = remind_at
                
                self.save_reminders()
                logger.info(f"Updated reminder {reminder_id} to {reminder.remind_at}")
                return True
        return False
    
    def list_pending_reminders(self) -> List[Reminder]:
        """Get all pending reminders."""
        return [r for r in self.reminders if r.status == "pending"]
    
    def start_background_task(self):
        """Start background task to check and send reminders."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._check_reminders_loop, daemon=True)
        self.thread.start()
        logger.info("Reminder background task started")
    
    def stop_background_task(self):
        """Stop background task."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Reminder background task stopped")
    
    def _check_reminders_loop(self):
        """Background loop to check for due reminders."""
        while self.running:
            try:
                self._check_and_send_reminders()
            except Exception as e:
                logger.error(f"Error in reminder check loop: {e}")
            
            # Check every 30 seconds
            time.sleep(30)
    
    def _check_and_send_reminders(self):
        """Check for due reminders and send them."""
        # Use timezone-aware datetime to match reminder times
        from app.core.config import settings
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        for reminder in self.reminders:
            # Make reminder time timezone-aware if it's naive
            remind_at = reminder.remind_at
            if remind_at.tzinfo is None:
                remind_at = remind_at.replace(tzinfo=user_tz)
            
            if reminder.status == "pending" and remind_at <= now:
                try:
                    self._send_reminder(reminder)
                    reminder.status = "sent"
                    self.save_reminders()
                except Exception as e:
                    logger.error(f"Failed to send reminder {reminder.id}: {e}")
    
    def _send_reminder(self, reminder: Reminder):
        """Send a reminder via Telegram."""
        try:
            import os
            import requests
            
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            telegram_user_id = os.getenv("TELEGRAM_USER_ID")
            
            if not telegram_token or not telegram_user_id:
                logger.warning("Telegram not configured, can't send reminder")
                return
            
            message = f"🔔 *Reminder*\n\n{reminder.message}"
            
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            response = requests.post(url, json={
                "chat_id": telegram_user_id,
                "text": message,
                "parse_mode": "Markdown"
            })
            
            if response.status_code == 200:
                logger.info(f"Sent reminder: {reminder.message}")
            else:
                logger.error(f"Failed to send reminder: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")


# Singleton instance
reminder_service = ReminderService()
