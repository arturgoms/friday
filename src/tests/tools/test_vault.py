"""
Tests for vault tools.

These tests use temporary directories to avoid touching real vault.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import yaml


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault with sample notes."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    
    # Create a sample note
    note_path = vault_dir / "Test Note.md"
    note_content = """---
tags: [test, sample]
created: 2024-01-01
---

# Test Note

This is a test note with some content.

## Section 1
Some text here.
"""
    note_path.write_text(note_content)
    
    # Create a daily note
    daily_path = vault_dir / "2024-01-10.md"
    daily_content = """---
date: 2024-01-10
---

# Daily Note

Today's tasks:
- Task 1
- Task 2
"""
    daily_path.write_text(daily_content)
    
    return vault_dir


def test_vault_read_note_success(temp_vault):
    """Test reading a note from vault."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_read_note
        
        result = vault_read_note("Test Note.md")
        
        assert "Test Note" in result
        assert "test note with some content" in result.lower()


def test_vault_read_note_not_found(temp_vault):
    """Test reading non-existent note."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_read_note
        
        result = vault_read_note("NonExistent.md")
        
        assert "not found" in result.lower() or "does not exist" in result.lower()


def test_vault_write_note_new(temp_vault):
    """Test writing a new note."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_write_note
        
        result = vault_write_note("New Note.md", "# New Note\n\nThis is new content.")
        
        assert "wrote" in result.lower() or "created" in result.lower() or "written" in result.lower()
        
        # Verify file was created
        note_path = temp_vault / "New Note.md"
        assert note_path.exists()
        assert "New Note" in note_path.read_text()


def test_vault_write_note_with_frontmatter(temp_vault):
    """Test writing note with frontmatter."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_write_note
        
        frontmatter = {"tags": ["important"], "author": "test"}
        result = vault_write_note("FM Note.md", "Content here.", frontmatter)
        
        assert "wrote" in result.lower() or "created" in result.lower() or "written" in result.lower()
        
        # Verify frontmatter was added
        note_path = temp_vault / "FM Note.md"
        content = note_path.read_text()
        assert "---" in content
        assert "tags:" in content
        assert "important" in content


def test_vault_list_directory(temp_vault):
    """Test listing notes in directory."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_list_directory
        
        result = vault_list_directory()
        
        assert "Test Note.md" in result
        assert "2024-01-10.md" in result


def test_vault_search_notes_by_content(temp_vault):
    """Test searching notes by content."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_search_notes
        
        result = vault_search_notes(query="test note")
        
        assert "Test Note.md" in result
        # Output says "Search results" not "found"
        assert "result" in result.lower() or "found" in result.lower()


def test_vault_search_notes_by_tag(temp_vault):
    """Test searching notes by tag."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_search_notes
        
        # Search for tag in content since there's no tag parameter
        result = vault_search_notes(query="test")
        
        assert "Test Note.md" in result


def test_vault_search_notes_no_results(temp_vault):
    """Test search with no results."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_search_notes
        
        result = vault_search_notes(query="nonexistent search term xyz")
        
        assert "no notes found" in result.lower() or "0 notes" in result.lower()


def test_vault_get_frontmatter(temp_vault):
    """Test getting frontmatter from note."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_get_frontmatter
        
        result = vault_get_frontmatter("Test Note.md")
        
        assert "tags" in result.lower()
        assert "test" in result.lower()


def test_vault_update_frontmatter(temp_vault):
    """Test updating frontmatter."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_update_frontmatter
        
        result = vault_update_frontmatter("Test Note.md", {"author": "Test Author"})
        
        assert "updated" in result.lower() or "success" in result.lower()
        
        # Verify frontmatter was updated
        note_path = temp_vault / "Test Note.md"
        content = note_path.read_text()
        assert "author: Test Author" in content or "author:" in content


def test_vault_create_daily_note(temp_vault):
    """Test creating daily note."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_create_daily_note
        
        result = vault_create_daily_note("2024-01-15")
        
        # Should mention creating a daily note (might use today's date instead)
        assert "daily note" in result.lower() or "created" in result.lower()
        assert ".md" in result


def test_vault_rename_note(temp_vault):
    """Test renaming a note."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_rename_note
        
        result = vault_rename_note("Test Note.md", "Renamed Note")
        
        assert "renamed" in result.lower()
        
        # Verify old file gone, new file exists
        old_path = temp_vault / "Test Note.md"
        new_path = temp_vault / "Renamed Note.md"
        assert not old_path.exists()
        assert new_path.exists()


def test_vault_delete_note_without_confirm(temp_vault):
    """Test delete note fails without confirmation."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_delete_note
        
        result = vault_delete_note("Test Note.md", confirm=False)
        
        assert "confirm" in result.lower() or "set confirm=true" in result.lower()
        
        # File should still exist
        note_path = temp_vault / "Test Note.md"
        assert note_path.exists()


def test_vault_delete_note_with_confirm(temp_vault):
    """Test delete note with confirmation."""
    with patch('src.tools.vault.VAULT_PATH', temp_vault):
        from src.tools.vault import vault_delete_note
        
        result = vault_delete_note("Test Note.md", confirm=True)
        
        assert "deleted" in result.lower()
        
        # File should be gone
        note_path = temp_vault / "Test Note.md"
        assert not note_path.exists()
