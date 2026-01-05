"""
Conversation History Manager

Manages conversation history across all communication channels.
Uses session IDs to track conversations independent of the channel.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from pydantic_ai.messages import ModelMessage

from src.core.database import Database

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation history for all users/sessions.
    
    Session IDs are channel-agnostic - a user can continue their conversation
    across different channels (Telegram, Web, Email, etc.) using the same session ID.
    """
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize conversation manager.
        
        Args:
            db: Database instance. Creates new one if not provided.
        """
        self.db = db or Database()
        self._memory_cache: Dict[str, List[ModelMessage]] = {}
        logger.info("ConversationManager initialized")
    
    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[ModelMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Unique session identifier (e.g., telegram_user_id, email, etc.)
            limit: Maximum number of messages to return (most recent first)
            
        Returns:
            List of ModelMessage objects representing the conversation history
        """
        # Check memory cache first
        if session_id in self._memory_cache:
            history = self._memory_cache[session_id]
            if limit:
                return history[-limit:]
            return history
        
        # Load from database
        rows = self.db.fetchall(
            """
            SELECT role, content, timestamp 
            FROM conversation_history 
            WHERE conversation_id = :session_id 
            ORDER BY timestamp ASC
            """ + (f" LIMIT {limit}" if limit else ""),
            {"session_id": session_id}
        )
        
        # Convert to ModelMessage objects
        # Note: This is a simplified conversion - you may need to adjust based on actual ModelMessage structure
        history = []
        for row in rows:
            # Store as dict that pydantic-ai can use
            history.append({
                "role": row[0],
                "content": row[1]
            })
        
        # Cache in memory
        self._memory_cache[session_id] = history
        
        logger.info(f"Loaded {len(history)} messages for session {session_id}")
        return history
    
    def add_messages(self, session_id: str, messages: List[ModelMessage]):
        """
        Add messages to conversation history.
        
        Args:
            session_id: Unique session identifier
            messages: List of ModelMessage objects to add
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Add to database
        for msg in messages:
            # Extract role and content from ModelMessage
            # The structure depends on pydantic-ai's ModelMessage format
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
            else:
                # If it's a pydantic-ai ModelMessage object
                role = getattr(msg, "role", "user")
                content = str(getattr(msg, "content", ""))
            
            self.db.insert("conversation_history", {
                "conversation_id": session_id,
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        # Update memory cache
        if session_id not in self._memory_cache:
            self._memory_cache[session_id] = []
        self._memory_cache[session_id].extend(messages)
        
        logger.info(f"Added {len(messages)} messages to session {session_id}")
    
    def update_history(self, session_id: str, all_messages: List[ModelMessage]):
        """
        Update the conversation history with the complete message list from agent.run().
        
        This is called after agent.run() with result.all_messages() to keep the 
        history in sync with what the agent sees.
        
        Args:
            session_id: Unique session identifier
            all_messages: Complete message history from result.all_messages()
        """
        # Get previous message count
        prev_count = len(self._memory_cache.get(session_id, []))
        
        # Update memory cache
        self._memory_cache[session_id] = all_messages
        
        # Persist new messages to database (only the delta)
        if len(all_messages) > prev_count:
            new_messages = all_messages[prev_count:]
            timestamp = datetime.utcnow().isoformat()
            
            for msg in new_messages:
                # Extract role and content from ModelMessage
                if isinstance(msg, dict):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                else:
                    # If it's a pydantic-ai ModelMessage object
                    role = getattr(msg, "role", "user")
                    content = str(getattr(msg, "content", ""))
                
                self.db.insert("conversation_history", {
                    "conversation_id": session_id,
                    "role": role,
                    "content": content,
                    "timestamp": timestamp
                })
            
            logger.info(f"Persisted {len(new_messages)} new messages for session {session_id}")
        
        logger.debug(f"Updated history cache for session {session_id} ({len(all_messages)} messages)")
    
    def clear_history(self, session_id: str):
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Unique session identifier
        """
        # Clear from database
        self.db.execute(
            "DELETE FROM conversation_history WHERE conversation_id = :session_id",
            {"session_id": session_id}
        )
        
        # Clear from memory cache
        if session_id in self._memory_cache:
            del self._memory_cache[session_id]
        
        logger.info(f"Cleared history for session {session_id}")
    
    def get_active_sessions(self, since_hours: int = 24) -> List[str]:
        """
        Get list of active session IDs.
        
        Args:
            since_hours: Only return sessions active in the last N hours
            
        Returns:
            List of session IDs
        """
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
        
        rows = self.db.fetchall(
            """
            SELECT DISTINCT conversation_id 
            FROM conversation_history 
            WHERE timestamp > :cutoff
            ORDER BY timestamp DESC
            """,
            {"cutoff": cutoff}
        )
        
        return [row[0] for row in rows]
    
    def get_session_info(self, session_id: str) -> Dict:
        """
        Get information about a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Dictionary with session info (message_count, first_message, last_message)
        """
        rows = self.db.fetchall(
            """
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM conversation_history
            WHERE conversation_id = :session_id
            """,
            {"session_id": session_id}
        )
        
        if rows and rows[0][0] > 0:
            return {
                "session_id": session_id,
                "message_count": rows[0][0],
                "first_message": rows[0][1],
                "last_message": rows[0][2]
            }
        
        return {
            "session_id": session_id,
            "message_count": 0,
            "first_message": None,
            "last_message": None
        }


# Global instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get or create the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
