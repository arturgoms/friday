"""
Personal Knowledge Graph Tools

Provides tools for storing and retrieving personal facts about the user.
This creates a persistent knowledge base that the model can query and update.

Facts are stored with:
- Topic (e.g., "favorite_color", "birthday", "spouse_name")
- Value (the actual information)
- Timestamp (when it was learned/updated)
- Confidence (optional: how sure we are)

When facts are updated, we keep the history but always retrieve the latest.
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

from src.core.constants import BRT

logger = logging.getLogger(__name__)


def _get_facts_db_path() -> str:
    """Get the path to the facts database."""
    return os.path.expanduser("~/friday_facts.db")


def _init_facts_db():
    """Initialize the facts database if it doesn't exist."""
    db_path = _get_facts_db_path()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create facts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            value TEXT NOT NULL,
            category TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'user_told',
            notes TEXT
        )
    """)
    
    # Create index on topic for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_topic ON facts(topic)
    """)
    
    # Create index on category
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)
    """)
    
    conn.commit()
    conn.close()


def save_fact(
    topic: str,
    value: str,
    category: Optional[str] = None,
    confidence: float = 1.0,
    notes: Optional[str] = None
) -> str:
    """Save a new fact about the user.
    
    Use this when the user tells you information that should be remembered long-term.
    This is for personal facts, not temporary information.
    
    Examples of when to use:
    - User: "My favorite color is blue" → save_fact(topic="favorite_color", value="blue", category="preferences")
    - User: "I was born on June 15" → save_fact(topic="birthday", value="June 15", category="personal")
    - User: "My wife's name is Sarah" → save_fact(topic="wife_name", value="Sarah", category="family")
    - User: "I work at Google" → save_fact(topic="employer", value="Google", category="work")
    
    DO NOT use for:
    - Temporary information (today's weather, current meeting)
    - Information already in calendar/health data
    - Conversation context (use memory tools instead)
    
    Args:
        topic: A short identifier for this fact (e.g., "favorite_color", "birthday")
        value: The actual information
        category: Optional category (e.g., "preferences", "personal", "family", "work")
        confidence: How confident we are (0.0 to 1.0, default 1.0)
        notes: Optional additional context
        
    Returns:
        Confirmation message
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert the new fact
        cursor.execute("""
            INSERT INTO facts (topic, value, category, confidence, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (topic, value, category, confidence, notes))
        
        fact_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Saved fact: {topic} = {value} (category: {category})")
        
        return f"✅ Saved: {topic} = {value}" + (f" (category: {category})" if category else "")
        
    except Exception as e:
        logger.error(f"Error saving fact: {e}")
        return f"Error saving fact: {str(e)}"


def get_fact(topic: str) -> str:
    """Get the latest value for a specific fact.
    
    Use this when you need to retrieve a specific piece of information about the user.
    This returns the most recent value if the fact has been updated multiple times.
    
    Examples:
    - User asks: "What's my favorite color?" → get_fact(topic="favorite_color")
    - User asks: "When is my birthday?" → get_fact(topic="birthday")
    - Need to know: "What's the user's wife's name?" → get_fact(topic="wife_name")
    
    Args:
        topic: The fact topic to retrieve
        
    Returns:
        The fact value and when it was saved, or a message if not found
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the most recent fact for this topic
        cursor.execute("""
            SELECT value, category, created_at, notes
            FROM facts
            WHERE topic = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (topic,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return f"❌ I don't have any information about '{topic}'. Would you like to tell me?"
        
        value, category, created_at, notes = row
        
        result = f"📝 {topic}: {value}"
        if category:
            result += f" (category: {category})"
        if notes:
            result += f"\nNotes: {notes}"
        result += f"\nLast updated: {created_at}"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting fact: {e}")
        return f"Error retrieving fact: {str(e)}"


def search_facts(
    query: str,
    category: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search for facts matching a query.
    
    Use this when you need to find facts but don't know the exact topic name,
    or when the user asks an open-ended question about what you know.
    
    Examples:
    - User: "What do you know about my preferences?" → search_facts(query="", category="preferences")
    - User: "Tell me what you know about me" → search_facts(query="")
    - Looking for color-related facts → search_facts(query="color")
    
    Args:
        query: Search term (searches in topic, value, and notes)
        category: Optional category filter
        limit: Maximum number of results (default 10)
        
    Returns:
        List of matching facts
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Build query
        if category:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE category = ?
                  AND (topic LIKE ? OR value LIKE ? OR notes LIKE ?)
                ORDER BY created_at DESC
            """
            params = (category, f"%{query}%", f"%{query}%", f"%{query}%")
        else:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE topic LIKE ? OR value LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (f"%{query}%", f"%{query}%", f"%{query}%", limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Get latest value for each topic
        unique_topics = {}
        for topic, value, cat, created_at, notes in rows:
            if topic not in unique_topics:
                unique_topics[topic] = (value, cat, created_at, notes)
        
        conn.close()
        
        if not unique_topics:
            return f"❌ No facts found matching '{query}'" + (f" in category '{category}'" if category else "")
        
        # Format results
        result = [f"📚 Found {len(unique_topics)} facts:"]
        result.append("=" * 50)
        
        for topic, (value, cat, created_at, notes) in unique_topics.items():
            entry = f"\n📝 {topic}: {value}"
            if cat:
                entry += f" ({cat})"
            if notes:
                entry += f"\n   Notes: {notes}"
            entry += f"\n   Updated: {created_at}"
            result.append(entry)
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error searching facts: {e}")
        return f"Error searching facts: {str(e)}"


def search_knowledge(query: str, limit: int = 5) -> str:
    """Search across ALL knowledge sources: facts database AND Obsidian vault.
    
    This is the "search everywhere" tool. Use this when you need to find information
    but don't know where it might be stored.
    
    Use this when:
    - User asks about information you don't immediately know
    - You need to find something but don't know if it's in notes or facts
    - User asks "Do you know anything about X?"
    
    Examples:
    - User: "What's my favorite color?" → search_knowledge(query="favorite color")
    - User: "Tell me about my running goals" → search_knowledge(query="running goals")
    - User: "What do you know about my family?" → search_knowledge(query="family")
    
    Args:
        query: What to search for
        limit: Maximum results from each source
        
    Returns:
        Combined results from facts and vault
    """
    try:
        results = []
        results.append(f"🔍 Searching all knowledge for: '{query}'")
        results.append("=" * 60)
        
        # Search facts database
        facts_result = search_facts(query, limit=limit)
        if "No facts found" not in facts_result:
            results.append("\n📊 FACTS DATABASE:")
            results.append(facts_result)
        
        # Search vault
        try:
            from src.tools.vault import vault_search_notes
            vault_result = vault_search_notes(
                query=query,
                search_content=True,
                search_filenames=True,
                limit=limit
            )
            
            if vault_result and "No results found" not in vault_result:
                results.append("\n\n📓 OBSIDIAN VAULT:")
                results.append(vault_result)
        except Exception as vault_error:
            logger.warning(f"Vault search failed: {vault_error}")
        
        if len(results) <= 2:  # Only header, no actual results
            return f"❌ No information found about '{query}' in facts or vault.\n\n💡 If you know this information, please tell me so I can remember it!"
        
        return "\n".join(results)
        
    except Exception as e:
        logger.error(f"Error in search_knowledge: {e}")
        return f"Error searching knowledge: {str(e)}"


def list_fact_categories() -> str:
    """List all fact categories with counts.
    
    Useful for understanding what types of information we have stored.
    
    Returns:
        List of categories and how many facts in each
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, COUNT(DISTINCT topic) as count
            FROM facts
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "📚 No categorized facts yet."
        
        result = ["📚 Fact Categories:"]
        result.append("=" * 40)
        for category, count in rows:
            result.append(f"  {category}: {count} facts")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"Error: {str(e)}"
