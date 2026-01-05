"""
Conversation Memory Tools

Provides tools for accessing conversation history when needed.
This approach keeps history out of the main context to avoid interfering
with function calling, but makes it available as a tool when the user
asks about past conversations.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
from datetime import datetime
from typing import Optional

from settings import settings
from src.core.database import get_db

logger = logging.getLogger(__name__)

# Session context is now passed via agent dependencies
# No need for _get_session_id() function anymore


@agent.tool
def get_conversation_history(
    ctx,
    query: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search conversation history for relevant past messages.
    
    Use this when the user asks about:
    - "What did I say about X?"
    - "What was my last message?"
    - "Did I mention Y?"
    - "What were we talking about?"
    - Any reference to past conversations
    
    Args:
        query: Optional search query to filter messages (case-insensitive)
        limit: Maximum number of messages to return (default 10, max 50)
        
    Returns:
        Formatted conversation history with timestamps and roles
        
    Example:
        User asks: "What did I ask about weather yesterday?"
        Call: get_conversation_history(query="weather", limit=5)
    """
    try:
        session_id = ctx.deps.session_id
        db = get_db()
        
        # Query conversations
        if query:
            sql = """
                SELECT timestamp, role, content 
                FROM conversation_history 
                WHERE conversation_id = :session_id AND content LIKE :query
                ORDER BY timestamp DESC 
                LIMIT :limit
            """
            params = {"session_id": session_id, "query": f"%{query}%", "limit": limit}
        else:
            sql = """
                SELECT timestamp, role, content 
                FROM conversation_history 
                WHERE conversation_id = :session_id
                ORDER BY timestamp DESC 
                LIMIT :limit
            """
            params = {"session_id": session_id, "limit": limit}
        
        rows = db.fetchall(sql, params)
        
        if not rows:
            if query:
                return f"No messages found matching '{query}' in conversation history."
            else:
                return "No conversation history found."
        
        # Format the results
        formatted = []
        formatted.append(f"📜 Conversation History ({len(rows)} messages):")
        formatted.append("=" * 50)
        
        for timestamp, role, content in reversed(rows):  # Reverse to show oldest first
            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = str(timestamp)
            
            # Truncate long messages
            content_preview = content[:200] if len(content) > 200 else content
            if len(content) > 200:
                content_preview += "..."
            
            role_emoji = "👤" if role == "user" else "🤖"
            formatted.append(f"\n{role_emoji} {role.upper()} [{time_str}]:")
            formatted.append(content_preview)
        
        return "\n".join(formatted)
        
    except Exception as e:
        logger.error(f"Error accessing conversation history: {e}")
        return f"Error accessing conversation history: {str(e)}"


@agent.tool
def get_last_user_message(ctx) -> str:
    """Get the user's last message in the conversation.
    
    Useful when the user asks:
    - "What did I just ask?"
    - "What was my last question?"
    - "Repeat my last message"
        
    Returns:
        The user's last message with timestamp
    """
    try:
        session_id = ctx.deps.session_id
        db = get_db()
        
        sql = """
            SELECT timestamp, content 
            FROM conversation_history 
            WHERE conversation_id = :session_id AND role = 'user'
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        
        row = db.fetchone(sql, {"session_id": session_id})
        
        if not row:
            return "No previous user messages found."
        
        timestamp, content = row
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = str(timestamp)
        
        return f"Your last message [{time_str}]:\n{content}"
        
    except Exception as e:
        logger.error(f"Error getting last user message: {e}")
        return f"Error: {str(e)}"


@agent.tool
def summarize_conversation(ctx, messages: int = 20) -> str:
    """Get a summary of recent conversation topics.
    
    Useful when the user asks:
    - "What have we been talking about?"
    - "Summarize our conversation"
    - "What did we discuss?"
    
    Args:
        messages: Number of recent messages to summarize (default 20)
        
    Returns:
        Summary of recent conversation topics
    """
    try:
        session_id = ctx.deps.session_id
        db = get_db()
        
        sql = """
            SELECT role, content 
            FROM conversation_history 
            WHERE conversation_id = :session_id
            ORDER BY timestamp DESC 
            LIMIT :limit
        """
        
        rows = db.fetchall(sql, {"session_id": session_id, "limit": messages})
        
        if not rows:
            return "No conversation history found."
        
        # Count message types
        user_messages = [content for role, content in rows if role == "user"]
        
        summary = []
        summary.append(f"📊 Conversation Summary (last {len(rows)} messages):")
        summary.append(f"- {len(user_messages)} user messages")
        summary.append(f"- {len(rows) - len(user_messages)} assistant responses")
        
        # Show preview of recent topics
        if user_messages:
            summary.append("\nRecent topics:")
            for i, msg in enumerate(reversed(user_messages[-5:]), 1):  # Last 5 user messages
                preview = msg[:80] if len(msg) > 80 else msg
                if len(msg) > 80:
                    preview += "..."
                summary.append(f"{i}. {preview}")
        
        return "\n".join(summary)
        
    except Exception as e:
        logger.error(f"Error summarizing conversation: {e}")
        return f"Error: {str(e)}"
