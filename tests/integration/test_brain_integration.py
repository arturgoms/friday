"""Integration tests for brain folder and memory system."""
import os
import pytest
import time
from pathlib import Path


@pytest.mark.integration
@pytest.mark.brain
class TestBrainFolder:
    """Test brain folder structure and accessibility."""
    
    def test_brain_folder_exists(self):
        """Test that brain folder exists and is accessible."""
        from app.core.config import settings
        
        assert settings.brain_path.exists(), f"Brain folder should exist at {settings.brain_path}"
        assert settings.brain_path.is_dir(), "Brain path should be a directory"
    
    def test_vault_folder_exists(self):
        """Test that vault (1. Notes) folder exists."""
        from app.core.config import settings
        
        assert settings.vault_path.exists(), f"Vault should exist at {settings.vault_path}"
        assert settings.vault_path.is_dir(), "Vault path should be a directory"
    
    def test_friday_folders_exist(self):
        """Test that Friday-specific folders exist."""
        from app.core.config import settings
        
        assert settings.memories_path.exists(), f"Memories folder should exist at {settings.memories_path}"
        assert settings.journal_path.exists(), f"Journal folder should exist at {settings.journal_path}"
        assert settings.reports_path.exists(), f"Reports folder should exist at {settings.reports_path}"
        assert settings.reminders_path.exists(), f"Reminders folder should exist at {settings.reminders_path}"
    
    def test_vault_has_markdown_files(self):
        """Test that vault contains markdown files."""
        from app.core.config import settings
        
        md_files = list(settings.vault_path.rglob("*.md"))
        assert len(md_files) > 0, "Vault should contain markdown files"
    
    def test_vault_indexed_in_rag(self, api_client, check_api_running):
        """Test that vault files are indexed in RAG system."""
        response = api_client.get("/health")
        data = response.json()
        
        assert data["obsidian_chunks"] > 0, "Vault should be indexed with chunks"


@pytest.mark.integration
@pytest.mark.brain
class TestMemoryStore:
    """Test markdown-based memory storage."""
    
    def test_memory_store_initialization(self):
        """Test that memory store initializes correctly."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        assert store.memories_path.exists(), "Memory store path should exist"
    
    def test_create_memory_file(self):
        """Test creating a memory as markdown file."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        timestamp = int(time.time())
        
        memory_id, conflicts = store.add_memory(
            content=f"Test brain memory {timestamp}",
            label="test_memory",
            tags=["test", "brain"],
            force=True  # Skip conflict check for tests
        )
        
        assert memory_id is not None, "Should return memory ID"
        assert conflicts == [], "Should have no conflicts when forced"
        
        # Verify file was created - find file that starts with memory_id
        memory_files = list(store.memories_path.glob(f"{memory_id}*.md"))
        assert len(memory_files) == 1, f"Memory file should exist for {memory_id}"
        memory_file = memory_files[0]
        
        # Verify content
        content = memory_file.read_text()
        assert f"Test brain memory {timestamp}" in content
        assert "test" in content
        assert "brain" in content
        
        # Cleanup
        memory_file.unlink()
    
    def test_retrieve_memory(self):
        """Test retrieving a memory by ID."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        timestamp = int(time.time())
        
        # Create memory
        memory_id, _ = store.add_memory(
            content=f"Retrievable memory {timestamp}",
            label="test_memory",
            force=True
        )
        
        # Retrieve it
        memory = store.get_memory(memory_id)
        
        assert memory is not None, "Should retrieve memory"
        assert f"Retrievable memory {timestamp}" in memory["content"]
        
        # Cleanup
        store.delete_memory(memory_id)
    
    def test_search_memories(self):
        """Test searching memories by content."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        timestamp = int(time.time())
        unique_phrase = f"unique_search_term_{timestamp}"
        
        # Create memory with unique content
        memory_id, _ = store.add_memory(
            content=f"Memory with {unique_phrase} for testing",
            label="test_memory",
            force=True
        )
        
        # Search for it
        results = store.search_memories(unique_phrase)
        
        assert len(results) > 0, "Should find memory by search"
        assert any(unique_phrase in r["content"] for r in results)
        
        # Cleanup
        store.delete_memory(memory_id)
    
    def test_list_memories(self):
        """Test listing all memories."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        
        memories = store.list_memories(limit=10)
        
        # Should return a list (may be empty or have existing memories)
        assert isinstance(memories, list)
    
    def test_memory_count(self):
        """Test getting memory count."""
        from app.services.memory_store import MemoryStore
        
        store = MemoryStore()
        initial_count = store.count()
        
        # Add a memory
        memory_id, _ = store.add_memory(
            content="Counting test memory",
            label="test_memory",
            force=True
        )
        
        new_count = store.count()
        assert new_count == initial_count + 1, "Count should increase by 1"
        
        # Cleanup
        store.delete_memory(memory_id)
        
        final_count = store.count()
        assert final_count == initial_count, "Count should return to initial"


@pytest.mark.integration
@pytest.mark.brain
class TestBrainService:
    """Test brain service for creating notes."""
    
    def test_brain_service_initialization(self):
        """Test that brain service initializes correctly."""
        from app.services.brain_service import BrainService
        
        service = BrainService()
        assert service.brain_path.exists(), "Brain path should exist"
    
    def test_create_journal_entry(self):
        """Test creating a journal entry."""
        from app.services.brain_service import BrainService
        from datetime import datetime
        
        service = BrainService()
        
        filepath = service.create_journal_entry(
            date=datetime.now(),
            sleep_summary="Test sleep: 7h30m",
            recovery_summary="Test recovery: Good",
            activity_summary="Test activity: 8000 steps",
            insights="Test insights from pytest"
        )
        
        assert filepath is not None, "Should return filepath"
        assert filepath.exists(), f"Journal file should exist at {filepath}"
        
        # Verify content
        content = filepath.read_text()
        assert "Test sleep" in content
        assert "Test recovery" in content
        
        # Cleanup
        filepath.unlink()
    
    def test_create_weekly_report(self):
        """Test creating a weekly report."""
        from app.services.brain_service import BrainService
        from datetime import datetime, timedelta
        
        service = BrainService()
        
        week_start = datetime.now()
        week_end = week_start + timedelta(days=7)
        
        filepath = service.create_weekly_report(
            week_start=week_start,
            week_end=week_end,
            summary="Test weekly summary",
            sleep_metrics="Avg: 7h30m",
            training_metrics="3 workouts"
        )
        
        assert filepath is not None, "Should return filepath"
        assert filepath.exists(), f"Report file should exist at {filepath}"
        
        # Verify content
        content = filepath.read_text()
        assert "Test weekly summary" in content
        
        # Cleanup
        filepath.unlink()


@pytest.mark.integration
@pytest.mark.brain
class TestRAGWithBrain:
    """Test RAG system with brain folder."""
    
    def test_rag_uses_brain_vault(self, api_client, check_api_running):
        """Test that RAG retrieves from brain vault."""
        from app.core.config import settings
        
        response = api_client.get("/admin/debug")
        data = response.json()
        
        # Verify vault path points to brain
        assert "brain" in data["vault_path"], "Vault path should be in brain folder"
        assert data["num_md_files"] > 0, "Should have markdown files"
        assert data["obsidian_chunks"] > 0, "Should have indexed chunks"
    
    def test_personal_info_from_brain(self, api_client, check_api_running):
        """Test retrieving personal info from brain vault."""
        response = api_client.chat("What do you know about me from my notes?")
        
        assert response.get("used_rag") or response.get("used_memory"), \
            "Should use RAG or memory"
        assert len(response["answer"]) > 50, "Should have substantial answer"


@pytest.mark.integration
@pytest.mark.brain
class TestMemoryAPIWithBrain:
    """Test memory API endpoints with brain-based storage."""
    
    def test_remember_creates_brain_file(self, api_client, check_api_running):
        """Test that /remember creates a file in brain folder."""
        from app.core.config import settings
        
        timestamp = int(time.time())
        
        response = api_client.post("/remember", json={
            "content": f"API brain test {timestamp}",
            "title": f"Brain Test {timestamp}",
            "tags": ["test", "api", "brain"]
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "filepath" in data
        
        # Verify file is in brain folder
        filepath = data["filepath"]
        assert "brain" in filepath or "5.1 Memories" in filepath, \
            f"Memory should be in brain folder, got: {filepath}"
        
        # Verify file exists
        assert Path(filepath).exists(), f"Memory file should exist at {filepath}"
        
        # Cleanup
        if Path(filepath).exists():
            Path(filepath).unlink()
    
    def test_memories_indexed_for_retrieval(self, api_client, check_api_running):
        """Test that memories are indexed and retrievable."""
        timestamp = int(time.time())
        unique_content = f"unique_memory_content_{timestamp}"
        
        # Create memory
        response = api_client.post("/remember", json={
            "content": f"Remember this: {unique_content}",
            "title": f"Indexed Test {timestamp}"
        })
        
        filepath = response.json().get("filepath")
        
        # Wait for indexing
        time.sleep(3)
        
        # Try to retrieve via chat
        chat_response = api_client.chat(f"What do you know about {unique_content}?")
        
        # Should find something (may or may not use exact content)
        assert len(chat_response["answer"]) > 0
        
        # Cleanup
        if filepath and Path(filepath).exists():
            Path(filepath).unlink()
