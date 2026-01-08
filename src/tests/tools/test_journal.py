"""
Tests for Friday Journal Tools

Tests journal management tools for creating daily threads and retrieving entries.

Tools tested:
- create_daily_journal_thread() - Create daily journal thread message
- get_todays_journal_entries() - Get all today's journal entries
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.journal import (
    create_daily_journal_thread,
    get_todays_journal_entries,
)


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# Journal Thread Tests
# =============================================================================

def test_create_daily_journal_thread_returns_str():
    """Test journal thread creation returns a string."""
    result = create_daily_journal_thread()
    assert isinstance(result, str)
    assert result is not None
    assert len(result) > 0


def test_create_daily_journal_thread_contains_expected_content():
    """Test journal thread message contains expected content."""
    result = create_daily_journal_thread()
    
    # Check for key elements
    assert "Daily Journal Thread" in result
    assert "journal" in result.lower() or "Journal" in result
    assert "entry" in result.lower() or "entries" in result.lower()
    
    # Should contain date or weekday
    today = datetime.now()
    weekday = today.strftime("%A")
    date_str = today.strftime("%Y-%m-%d")
    
    # Should have either weekday or date (or both)
    assert weekday in result or date_str in result


def test_create_daily_journal_thread_format():
    """Test journal thread message has proper format."""
    result = create_daily_journal_thread()
    
    # Should be multi-line
    assert "\n" in result
    
    # Should have reasonable length (not empty, not too short)
    assert len(result) > 50


def test_create_daily_journal_thread_consistency():
    """Test journal thread message is consistent across calls."""
    result1 = create_daily_journal_thread()
    result2 = create_daily_journal_thread()
    
    # Same date should give same message (on same day)
    assert result1 == result2


def test_create_daily_journal_thread_no_error():
    """Test journal thread creation doesn't return error message."""
    result = create_daily_journal_thread()
    
    # Should not contain error indicators
    assert "Error" not in result or "error" not in result.lower()


# =============================================================================
# Journal Entries Tests
# =============================================================================

def test_get_todays_journal_entries_returns_dict():
    """Test today's journal entries returns a dict."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = []
        
        result = get_todays_journal_entries()
        assert isinstance(result, dict)
        assert result is not None


def test_get_todays_journal_entries_structure_empty():
    """Test today's journal entries structure when empty."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = []
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            assert "date" in result
            assert "total_entries" in result
            assert "text_entries" in result
            assert "audio_entries" in result
            assert "entries" in result
            
            # Type checks
            assert isinstance(result["date"], str)
            assert isinstance(result["total_entries"], int)
            assert isinstance(result["text_entries"], int)
            assert isinstance(result["audio_entries"], int)
            assert isinstance(result["entries"], list)
            
            # Value checks
            assert result["total_entries"] == 0
            assert result["text_entries"] == 0
            assert result["audio_entries"] == 0
            assert len(result["entries"]) == 0


def test_get_todays_journal_entries_structure_with_text():
    """Test today's journal entries structure with text entries."""
    mock_entries = [
        {
            'id': 1,
            'timestamp': '2024-01-10T10:00:00',
            'entry_type': 'text',
            'content': 'Test text entry',
            'thread_message_id': 123
        },
        {
            'id': 2,
            'timestamp': '2024-01-10T11:00:00',
            'entry_type': 'text',
            'content': 'Another text entry',
            'thread_message_id': 123
        }
    ]
    
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = mock_entries
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            assert result["total_entries"] == 2
            assert result["text_entries"] == 2
            assert result["audio_entries"] == 0
            assert len(result["entries"]) == 2
            
            # Check entry structure
            for entry in result["entries"]:
                assert "id" in entry
                assert "timestamp" in entry
                assert "entry_type" in entry
                assert "content" in entry


def test_get_todays_journal_entries_structure_with_audio():
    """Test today's journal entries structure with audio entries."""
    mock_entries = [
        {
            'id': 1,
            'timestamp': '2024-01-10T10:00:00',
            'entry_type': 'audio',
            'content': 'Transcribed audio content',
            'thread_message_id': 123
        }
    ]
    
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = mock_entries
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            assert result["total_entries"] == 1
            assert result["text_entries"] == 0
            assert result["audio_entries"] == 1
            assert len(result["entries"]) == 1


def test_get_todays_journal_entries_structure_mixed():
    """Test today's journal entries with mixed text and audio."""
    mock_entries = [
        {
            'id': 1,
            'timestamp': '2024-01-10T10:00:00',
            'entry_type': 'text',
            'content': 'Text entry',
            'thread_message_id': 123
        },
        {
            'id': 2,
            'timestamp': '2024-01-10T11:00:00',
            'entry_type': 'audio',
            'content': 'Audio entry',
            'thread_message_id': 123
        },
        {
            'id': 3,
            'timestamp': '2024-01-10T12:00:00',
            'entry_type': 'text',
            'content': 'Another text',
            'thread_message_id': 123
        }
    ]
    
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = mock_entries
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            assert result["total_entries"] == 3
            assert result["text_entries"] == 2
            assert result["audio_entries"] == 1
            assert len(result["entries"]) == 3


def test_get_todays_journal_entries_date_format():
    """Test today's journal entries date format."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = []
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            date_str = result["date"]
            # Should be YYYY-MM-DD format
            assert len(date_str) == 10
            assert date_str[4] == '-'
            assert date_str[7] == '-'
            
            # Should be valid date
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                valid_date = True
            except ValueError:
                valid_date = False
            
            assert valid_date, f"Invalid date format: {date_str}"


def test_get_todays_journal_entries_consistency():
    """Test today's journal entries is consistent across calls."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_entries = [
            {
                'id': 1,
                'timestamp': '2024-01-10T10:00:00',
                'entry_type': 'text',
                'content': 'Test',
                'thread_message_id': 123
            }
        ]
        mock_get.return_value = mock_entries
        
        result1 = get_todays_journal_entries()
        result2 = get_todays_journal_entries()
        
        # Should be identical
        assert result1 == result2


# =============================================================================
# None Value Detection Tests
# =============================================================================

def test_get_todays_journal_entries_no_none_values_empty():
    """CRITICAL: Ensure today's journal entries has no None values (empty case)."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = []
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: get_todays_journal_entries has None values at: {none_values}"


def test_get_todays_journal_entries_no_none_values_with_data():
    """CRITICAL: Ensure today's journal entries has no None values (with data)."""
    mock_entries = [
        {
            'id': 1,
            'timestamp': '2024-01-10T10:00:00',
            'entry_type': 'text',
            'content': 'Test entry',
            'thread_message_id': 123
        },
        {
            'id': 2,
            'timestamp': '2024-01-10T11:00:00',
            'entry_type': 'audio',
            'content': 'Audio entry',
            'thread_message_id': 123
        }
    ]
    
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = mock_entries
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: get_todays_journal_entries has None values at: {none_values}"


def test_all_journal_tools_no_none_values():
    """CRITICAL: Batch test - check all journal tools for None values."""
    errors = []
    
    # Test create_daily_journal_thread (returns string, not dict)
    result = create_daily_journal_thread()
    # String shouldn't be None
    if result is None:
        errors.append("create_daily_journal_thread returned None")
    
    # Test get_todays_journal_entries
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = [
            {
                'id': 1,
                'timestamp': '2024-01-10T10:00:00',
                'entry_type': 'text',
                'content': 'Test',
                'thread_message_id': 123
            }
        ]
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            none_vals = check_for_none_values(result)
            if none_vals:
                errors.append(f"get_todays_journal_entries: {none_vals}")
    
    # Assert no errors found
    assert len(errors) == 0, \
        f"CRITICAL: Found None values in journal tools:\n" + "\n".join(errors)


# =============================================================================
# Edge Cases
# =============================================================================

def test_get_todays_journal_entries_handles_database_error():
    """Test journal entries handles database errors gracefully."""
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.side_effect = Exception("Database error")
        
        result = get_todays_journal_entries()
        
        # Should return error dict
        assert isinstance(result, dict)
        assert "error" in result


def test_get_todays_journal_entries_entry_counts_accurate():
    """Test journal entries counts are accurate."""
    mock_entries = [
        {'id': 1, 'timestamp': '2024-01-10T10:00:00', 'entry_type': 'text', 'content': 'A', 'thread_message_id': 123},
        {'id': 2, 'timestamp': '2024-01-10T11:00:00', 'entry_type': 'text', 'content': 'B', 'thread_message_id': 123},
        {'id': 3, 'timestamp': '2024-01-10T12:00:00', 'entry_type': 'audio', 'content': 'C', 'thread_message_id': 123},
        {'id': 4, 'timestamp': '2024-01-10T13:00:00', 'entry_type': 'audio', 'content': 'D', 'thread_message_id': 123},
        {'id': 5, 'timestamp': '2024-01-10T14:00:00', 'entry_type': 'audio', 'content': 'E', 'thread_message_id': 123},
    ]
    
    with patch('src.tools.journal.get_journal_entries_for_date') as mock_get:
        mock_get.return_value = mock_entries
        
        result = get_todays_journal_entries()
        
        if "error" not in result:
            # Verify counts
            assert result["total_entries"] == 5
            assert result["text_entries"] == 2
            assert result["audio_entries"] == 3
            assert result["text_entries"] + result["audio_entries"] == result["total_entries"]
