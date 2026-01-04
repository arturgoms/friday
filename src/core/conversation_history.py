"""
Conversation history manager using SQLite.

Replaces npcpy's command_history with simpler, focused implementation.
"""

import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConversationHistory:
    """Manage conversation history in SQLite."""
    
    def __init__(self, db_path: str):
        """Initialize conversation history.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()
        logger.info(f"[HISTORY] Initialized: {db_path}")
    
    def _init_db(self):
        """Create tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on session_id for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON conversations(session_id)
            """)
            
            conn.commit()
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        """Add a message to conversation history.
        
        Args:
            session_id: Session/conversation ID
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            model: Optional model name
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations (session_id, timestamp, role, content, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, timestamp_str, role, content, model)
            )
            conn.commit()
        
        logger.debug(f"[HISTORY] Added {role} message to session {session_id}")
    
    def get_conversation(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history for a session.
        
        Args:
            session_id: Session ID
            limit: Optional limit on number of messages (most recent)
            
        Returns:
            List of message dicts with 'role', 'content', 'timestamp'
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if limit:
                query = """
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                """
                rows = conn.execute(query, (session_id, limit)).fetchall()
                rows = list(reversed(rows))  # Reverse to get chronological order
            else:
                query = """
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE session_id = ?
                    ORDER BY id ASC
                """
                rows = conn.execute(query, (session_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session.
        
        Args:
            session_id: Session ID to clear
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
        
        logger.info(f"[HISTORY] Cleared session {session_id}")
    
    def list_sessions(self, limit: int = 100) -> List[Dict[str, str]]:
        """List recent sessions.
        
        Args:
            limit: Max number of sessions to return
            
        Returns:
            List of dicts with session info
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = """
                SELECT 
                    session_id,
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM conversations
                GROUP BY session_id
                ORDER BY MAX(timestamp) DESC
                LIMIT ?
            """
            
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in rows]
