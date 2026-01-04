"""
Conversation history storage for Friday.

Simple SQLite-based storage for conversation messages.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationHistory:
    """Simple conversation history storage."""
    
    def __init__(self, db_path: str = "~/friday_history.db"):
        """Initialize history storage.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path).expanduser()
        self._init_db()
        logger.info(f"[HISTORY] Initialized: {self.db_path}")
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    model TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON messages(session_id, timestamp)
            """)
            conn.commit()
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model: Optional[str] = None
    ):
        """Add a message to history.
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            model: Model name (optional)
        """
        timestamp = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp, model) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, timestamp, model)
            )
            conn.commit()
    
    def get_conversation(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dicts with keys: role, content, timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT role, content, timestamp 
                FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit)
            )
            
            rows = cursor.fetchall()
            # Reverse to get chronological order
            messages = [
                {"role": row[0], "content": row[1], "timestamp": row[2]}
                for row in reversed(rows)
            ]
            
            return messages
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()
        
        logger.info(f"[HISTORY] Cleared session: {session_id}")
