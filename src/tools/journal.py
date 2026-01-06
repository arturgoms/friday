"""
Friday Journal Tools

Tools for managing daily journal threads and entries.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from settings import settings
from src.core.agent import agent
from src.core.database import Database

logger = logging.getLogger(__name__)


def get_brt():
    """Get BRT timezone from settings."""
    return settings.TIMEZONE


# =============================================================================
# Journal Thread Management
# =============================================================================


@agent.tool_plain
def create_daily_journal_thread() -> str:
    """Create the daily journal thread in Telegram.
    
    This should be called once per day (typically at 8:00 AM) to create
    the journal thread for the day. Users can reply to this thread with
    their journal entries throughout the day.
    
    Returns:
        Message to send to Telegram
    """
    try:
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        weekday = datetime.now(get_brt()).strftime("%A")
        
        message = f"""📔 Daily Journal Thread - {weekday}, {today}

Good morning! This is your journal thread for today.

Reply to this message with:
• 💭 Text entries - your thoughts, reflections, notes
• 🎤 Voice messages - I'll transcribe them automatically

At the end of the day, I'll compile everything into your daily note.

Let's make today count! 🌟"""
        
        return message
        
    except Exception as e:
        logger.error(f"Error creating journal thread: {e}")
        return f"Error creating journal thread: {e}"


def save_journal_thread(date: str, message_id: int) -> bool:
    """Save journal thread message ID to database.
    
    Args:
        date: Date in YYYY-MM-DD format
        message_id: Telegram message ID
        
    Returns:
        True if saved successfully
    """
    try:
        db = Database()
        created_at = datetime.now(get_brt()).isoformat()
        
        # Use INSERT OR REPLACE to handle duplicates
        db.execute(
            'INSERT OR REPLACE INTO journal_threads (date, message_id, created_at) VALUES (:date, :message_id, :created_at)',
            {
                'date': date,
                'message_id': message_id,
                'created_at': created_at
            }
        )
        
        logger.info(f"Saved journal thread for {date}, message_id={message_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving journal thread: {e}")
        return False


def get_journal_thread_for_date(date: str) -> Optional[int]:
    """Get the journal thread message ID for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        Message ID if found, None otherwise
    """
    try:
        db = Database()
        result = db.fetchone(
            "SELECT message_id FROM journal_threads WHERE date = :date",
            {'date': date}
        )
        
        if result:
            return result[0]
        return None
        
    except Exception as e:
        logger.error(f"Error getting journal thread: {e}")
        return None


# =============================================================================
# Journal Entry Management
# =============================================================================


def save_journal_entry(
    content: str,
    entry_type: str = "text",
    thread_message_id: Optional[int] = None
) -> bool:
    """Save a journal entry to the database.
    
    Args:
        content: The text content (or transcribed audio)
        entry_type: Either "text" or "audio"
        thread_message_id: The thread message ID this is replying to
        
    Returns:
        True if saved successfully
    """
    try:
        db = Database()
        now = datetime.now(get_brt())
        
        db.insert('journal_entries', {
            'date': now.strftime("%Y-%m-%d"),
            'timestamp': now.isoformat(),
            'entry_type': entry_type,
            'content': content,
            'thread_message_id': thread_message_id
        })
        
        logger.info(f"Saved journal entry ({entry_type}): {content[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error saving journal entry: {e}")
        return False


def get_journal_entries_for_date(date: str) -> list:
    """Get all journal entries for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        List of journal entries
    """
    try:
        db = Database()
        results = db.fetchall(
            """SELECT id, timestamp, entry_type, content, thread_message_id 
               FROM journal_entries 
               WHERE date = :date 
               ORDER BY timestamp ASC""",
            {'date': date}
        )
        
        entries = []
        for row in results:
            entries.append({
                'id': row[0],
                'timestamp': row[1],
                'entry_type': row[2],
                'content': row[3],
                'thread_message_id': row[4]
            })
        
        return entries
        
    except Exception as e:
        logger.error(f"Error getting journal entries: {e}")
        return []


@agent.tool_plain
def get_todays_journal_entries() -> Dict[str, Any]:
    """Get all journal entries for today.
    
    Atomic data tool that returns today's journal entries.
    
    Returns:
        Dict with today's journal entries
    """
    try:
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        entries = get_journal_entries_for_date(today)
        
        # Count by type
        text_count = len([e for e in entries if e['entry_type'] == 'text'])
        audio_count = len([e for e in entries if e['entry_type'] == 'audio'])
        
        return {
            'date': today,
            'total_entries': len(entries),
            'text_entries': text_count,
            'audio_entries': audio_count,
            'entries': entries
        }
        
    except Exception as e:
        logger.error(f"Error getting today's journal entries: {e}")
        return {'error': str(e)}
