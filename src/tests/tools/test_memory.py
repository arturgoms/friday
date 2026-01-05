"""
Tests for memory tools.

These tests use the centralized database module with in-memory databases.
"""

import pytest
from unittest.mock import patch


def test_get_conversation_history_success(populated_test_db, mock_get_db):
    """Test retrieving conversation history."""
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history()
    
    assert "weather" in result.lower()
    assert "python news" in result.lower()
    assert "4 messages" in result.lower()


def test_get_conversation_history_with_query(populated_test_db, mock_get_db):
    """Test searching conversation history with query."""
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history(query="weather")
    
    assert "weather" in result.lower()
    # Should find 2 messages (user question + assistant response)
    assert "2 messages" in result.lower()


def test_get_conversation_history_no_results(test_db, mock_get_db):
    """Test conversation history with no results (empty db)."""
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history()
    
    assert "no conversation history" in result.lower()


def test_get_conversation_history_no_matching_query(populated_test_db, mock_get_db):
    """Test conversation history with query that matches nothing."""
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history(query="nonexistent")
    
    assert "no messages found" in result.lower()
    assert "nonexistent" in result.lower()


def test_get_conversation_history_limits_results(test_db, mock_get_db):
    """Test that result limit is enforced."""
    # Insert 20 messages
    for i in range(20):
        test_db.insert('conversation_history', {
            'conversation_id': 'default',
            'timestamp': f'2024-01-10T10:{i:02d}:00',
            'role': 'user',
            'content': f'Message {i}'
        })
    
    from src.tools.memory import get_conversation_history
    
    # Request only 5 messages
    result = get_conversation_history(limit=5)
    
    assert "5 messages" in result.lower()


def test_get_last_user_message_success(populated_test_db, mock_get_db):
    """Test retrieving last user message."""
    from src.tools.memory import get_last_user_message
    
    result = get_last_user_message()
    
    # Should return the most recent user message
    assert "Python news" in result
    assert "last message" in result.lower()


def test_get_last_user_message_no_messages(test_db, mock_get_db):
    """Test when there are no user messages."""
    from src.tools.memory import get_last_user_message
    
    result = get_last_user_message()
    
    assert "no" in result.lower()


def test_summarize_conversation_success(populated_test_db, mock_get_db):
    """Test conversation summarization."""
    from src.tools.memory import summarize_conversation
    
    result = summarize_conversation(messages=20)
    
    assert "summary" in result.lower()
    assert "4 messages" in result.lower()  # Total messages
    assert "2 user messages" in result.lower()  # User message count


def test_summarize_conversation_shows_topics(populated_test_db, mock_get_db):
    """Test that summary shows recent topics."""
    from src.tools.memory import summarize_conversation
    
    result = summarize_conversation()
    
    assert "recent topics" in result.lower()
    assert ("weather" in result.lower() or "python" in result.lower())


def test_summarize_conversation_no_history(test_db, mock_get_db):
    """Test summarization with no history."""
    from src.tools.memory import summarize_conversation
    
    result = summarize_conversation()
    
    assert "no conversation history" in result.lower()


def test_memory_truncates_long_messages(test_db, mock_get_db):
    """Test that very long messages are truncated in display."""
    # Insert a very long message
    long_content = "A" * 300
    test_db.insert('conversation_history', {
        'conversation_id': 'default',
        'timestamp': '2024-01-10T10:00:00',
        'role': 'user',
        'content': long_content
    })
    
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history()
    
    # Should be truncated and show ellipsis
    assert "..." in result
    # Should not show the full 300 characters
    assert len(result) < 350


def test_conversation_history_formatting(populated_test_db, mock_get_db):
    """Test that conversation history is formatted correctly."""
    from src.tools.memory import get_conversation_history
    
    result = get_conversation_history()
    
    # Check for emojis and formatting
    assert "👤" in result or "🤖" in result  # Role emojis
    assert "USER" in result.upper()
    assert "ASSISTANT" in result.upper()
    assert "2024-01-10" in result  # Timestamp


def test_get_last_user_message_with_multiple_users(test_db, mock_get_db):
    """Test getting last user message when multiple user messages exist."""
    # Insert multiple user messages
    messages = [
        {'conversation_id': 'default', 'timestamp': '2024-01-10T10:00:00', 
         'role': 'user', 'content': 'First message'},
        {'conversation_id': 'default', 'timestamp': '2024-01-10T10:01:00', 
         'role': 'user', 'content': 'Second message'},
        {'conversation_id': 'default', 'timestamp': '2024-01-10T10:02:00', 
         'role': 'user', 'content': 'Third message'},
    ]
    
    for msg in messages:
        test_db.insert('conversation_history', msg)
    
    from src.tools.memory import get_last_user_message
    
    result = get_last_user_message()
    
    # Should get the most recent one
    assert "Third message" in result
    assert "10:02" in result
