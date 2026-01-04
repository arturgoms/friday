"""
Friday Journal Handler

Manages daily journal threads, entry capture, and processing.
This module is used by both the Telegram bot and the insights engine.
"""

import logging
import os
from datetime import datetime, time
from pathlib import Path
from typing import Optional

from src.core.config import get_config, get_brt
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class JournalHandler:
    """
    Handles journal operations for Friday.
    
    Responsibilities:
    - Create daily journal threads (morning message)
    - Capture journal entries (text and voice)
    - Store entries in database
    """
    
    def __init__(self, store: Optional[InsightsStore] = None):
        """Initialize the journal handler.
        
        Args:
            store: InsightsStore instance. If None, creates a new one.
        """
        self.store = store or InsightsStore()
    
    def should_send_morning_thread(self, now: Optional[datetime] = None) -> bool:
        """Check if it's time to send the morning journal thread.
        
        Args:
            now: Current time. If None, uses datetime.now(get_brt()).
            
        Returns:
            True if within the morning thread window (10:00 AM)
        """
        if now is None:
            now = datetime.now(get_brt())
        
        # Target time: 10:00 AM
        target_time = time(10, 0)
        
        # Check if within 5 minute window
        now_minutes = now.hour * 60 + now.minute
        target_minutes = target_time.hour * 60 + target_time.minute
        
        # Check if already sent today
        today = now.strftime("%Y-%m-%d")
        existing_thread = self.store.get_journal_thread(today)
        
        return abs(now_minutes - target_minutes) <= 2 and existing_thread is None
    
    def get_morning_thread_message(self, date: Optional[datetime] = None) -> str:
        """Generate the morning journal thread message.
        
        Args:
            date: Date for the journal. If None, uses today.
            
        Returns:
            Formatted message text
        """
        if date is None:
            date = datetime.now(get_brt())
        
        # Format: "Your journal for Sunday, June 15 is ready. Reply to this message to add entries."
        day_name = date.strftime("%A")
        month_name = date.strftime("%B")
        day_num = date.day
        
        return (
            f"Your journal for {day_name}, {month_name} {day_num} is ready. "
            f"Reply to this message to add entries."
        )
    
    def save_thread_message(self, date: str, message_id: int) -> bool:
        """Save a journal thread message ID.
        
        Args:
            date: Date in YYYY-MM-DD format
            message_id: Telegram message ID
            
        Returns:
            True if saved successfully, False if already exists
        """
        return self.store.save_journal_thread(date, message_id)
    
    def get_thread_for_date(self, date: str) -> Optional[int]:
        """Get the thread message ID for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Message ID or None if not found
        """
        return self.store.get_journal_thread(date)
    
    def is_reply_to_journal_thread(self, reply_to_message_id: Optional[int], date: Optional[str] = None) -> bool:
        """Check if a message is a reply to a journal thread.
        
        Args:
            reply_to_message_id: The message ID being replied to
            date: Date to check. If None, uses today.
            
        Returns:
            True if this is a reply to today's journal thread
        """
        if reply_to_message_id is None:
            return False
        
        if date is None:
            date = datetime.now(get_brt()).strftime("%Y-%m-%d")
        
        thread_id = self.store.get_journal_thread(date)
        return thread_id == reply_to_message_id
    
    def save_entry(self, content: str, entry_type: str = "text", 
                   timestamp: Optional[datetime] = None, 
                   date: Optional[str] = None) -> bool:
        """Save a journal entry.
        
        Args:
            content: Entry content (text or transcription)
            entry_type: 'text' or 'voice'
            timestamp: When the entry was created. If None, uses now.
            date: Date for the entry. If None, uses today.
            
        Returns:
            True if saved successfully
        """
        if timestamp is None:
            timestamp = datetime.now(get_brt())
        
        if date is None:
            date = timestamp.strftime("%Y-%m-%d")
        
        # Get the thread message ID for reference
        thread_id = self.store.get_journal_thread(date)
        
        try:
            self.store.save_journal_entry(
                date=date,
                timestamp=timestamp,
                entry_type=entry_type,
                content=content,
                thread_message_id=thread_id
            )
            logger.info(f"[JOURNAL] Saved {entry_type} entry for {date}: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"[JOURNAL] Failed to save entry: {e}")
            return False
    
    def get_entries_for_date(self, date: str) -> list:
        """Get all journal entries for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of entry dicts
        """
        return self.store.get_journal_entries(date)
    
    def get_today_entries(self) -> list:
        """Get all journal entries for today.
        
        Returns:
            List of entry dicts
        """
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        return self.get_entries_for_date(today)


# Global singleton instance
_journal_handler: Optional[JournalHandler] = None


def get_journal_handler() -> JournalHandler:
    """Get the global journal handler instance."""
    global _journal_handler
    if _journal_handler is None:
        _journal_handler = JournalHandler()
    return _journal_handler
