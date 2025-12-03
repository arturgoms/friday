"""
Feedback Store - Track user feedback on AI responses.

Stores thumbs up/down reactions to help calibrate and improve responses.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from app.core.logging import logger


class FeedbackStore:
    """Store and analyze user feedback on AI responses."""
    
    def __init__(self, db_path: str = None):
        """Initialize feedback store."""
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "feedback.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    message_id TEXT,
                    user_message TEXT NOT NULL,
                    ai_response TEXT NOT NULL,
                    feedback TEXT NOT NULL CHECK(feedback IN ('up', 'down')),
                    context_type TEXT,
                    intent_action TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp 
                ON feedback(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type 
                ON feedback(feedback)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_intent 
                ON feedback(intent_action)
            """)
            
            conn.commit()
    
    def add_feedback(
        self,
        user_message: str,
        ai_response: str,
        feedback: str,  # 'up' or 'down'
        message_id: str = None,
        context_type: str = None,
        intent_action: str = None,
        metadata: Dict[str, Any] = None
    ) -> int:
        """
        Record user feedback on a response.
        
        Args:
            user_message: The original user question/message
            ai_response: Friday's response
            feedback: 'up' (thumbs up) or 'down' (thumbs down)
            message_id: Optional telegram message ID for reference
            context_type: Type of context used (health, rag, web, etc.)
            intent_action: The intent action that was triggered
            metadata: Additional metadata (health metrics, etc.)
        
        Returns:
            The feedback record ID
        """
        if feedback not in ('up', 'down'):
            raise ValueError("Feedback must be 'up' or 'down'")
        
        timestamp = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO feedback 
                (timestamp, message_id, user_message, ai_response, feedback, 
                 context_type, intent_action, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, message_id, user_message, ai_response, feedback,
                context_type, intent_action, metadata_json
            ))
            conn.commit()
            
            logger.info(f"Feedback recorded: {feedback} for intent={intent_action}")
            return cursor.lastrowid
    
    def get_feedback_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get feedback statistics for the last N days.
        
        Returns summary of thumbs up/down by category.
        """
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Overall stats
            overall = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN feedback = 'up' THEN 1 ELSE 0 END) as thumbs_up,
                    SUM(CASE WHEN feedback = 'down' THEN 1 ELSE 0 END) as thumbs_down
                FROM feedback
                WHERE timestamp >= ?
            """, (cutoff,)).fetchone()
            
            # Stats by intent action
            by_intent = conn.execute("""
                SELECT 
                    intent_action,
                    COUNT(*) as total,
                    SUM(CASE WHEN feedback = 'up' THEN 1 ELSE 0 END) as thumbs_up,
                    SUM(CASE WHEN feedback = 'down' THEN 1 ELSE 0 END) as thumbs_down
                FROM feedback
                WHERE timestamp >= ? AND intent_action IS NOT NULL
                GROUP BY intent_action
                ORDER BY total DESC
            """, (cutoff,)).fetchall()
            
            # Stats by context type
            by_context = conn.execute("""
                SELECT 
                    context_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN feedback = 'up' THEN 1 ELSE 0 END) as thumbs_up,
                    SUM(CASE WHEN feedback = 'down' THEN 1 ELSE 0 END) as thumbs_down
                FROM feedback
                WHERE timestamp >= ? AND context_type IS NOT NULL
                GROUP BY context_type
                ORDER BY total DESC
            """, (cutoff,)).fetchall()
            
            return {
                "period_days": days,
                "overall": {
                    "total": overall["total"],
                    "thumbs_up": overall["thumbs_up"],
                    "thumbs_down": overall["thumbs_down"],
                    "approval_rate": round(overall["thumbs_up"] / overall["total"] * 100, 1) if overall["total"] > 0 else 0
                },
                "by_intent": [
                    {
                        "intent": row["intent_action"],
                        "total": row["total"],
                        "thumbs_up": row["thumbs_up"],
                        "thumbs_down": row["thumbs_down"],
                        "approval_rate": round(row["thumbs_up"] / row["total"] * 100, 1) if row["total"] > 0 else 0
                    }
                    for row in by_intent
                ],
                "by_context": [
                    {
                        "context": row["context_type"],
                        "total": row["total"],
                        "thumbs_up": row["thumbs_up"],
                        "thumbs_down": row["thumbs_down"],
                        "approval_rate": round(row["thumbs_up"] / row["total"] * 100, 1) if row["total"] > 0 else 0
                    }
                    for row in by_context
                ]
            }
    
    def get_negative_feedback(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent negative feedback for review.
        
        Useful for identifying areas that need improvement.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            rows = conn.execute("""
                SELECT *
                FROM feedback
                WHERE feedback = 'down'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "user_message": row["user_message"],
                    "ai_response": row["ai_response"][:500] + "..." if len(row["ai_response"]) > 500 else row["ai_response"],
                    "context_type": row["context_type"],
                    "intent_action": row["intent_action"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                }
                for row in rows
            ]
    
    def get_feedback_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback record by telegram message ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            row = conn.execute("""
                SELECT * FROM feedback WHERE message_id = ?
            """, (message_id,)).fetchone()
            
            if row:
                return dict(row)
            return None


# Singleton instance
_feedback_store = None

def get_feedback_store() -> FeedbackStore:
    """Get feedback store singleton."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store
