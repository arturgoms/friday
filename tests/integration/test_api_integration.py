"""Integration tests for Friday API endpoints."""
import pytest
import time


@pytest.mark.integration
class TestAPIHealth:
    """Test API health and status endpoints."""
    
    def test_health_endpoint(self, api_client, check_api_running):
        """Test that health endpoint returns running status."""
        response = api_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "running"
        assert "llm_status" in data
        assert "vault_path" in data
        assert "obsidian_chunks" in data
        assert data["obsidian_chunks"] > 0, "Obsidian vault should be indexed"
    
    def test_debug_endpoint(self, api_client, check_api_running):
        """Test debug endpoint returns system information."""
        response = api_client.get("/admin/debug")
        assert response.status_code == 200
        
        data = response.json()
        assert "vault_path" in data
        assert "num_md_files" in data
        assert "obsidian_chunks" in data
        assert "memory_entries" in data


@pytest.mark.integration
@pytest.mark.router
class TestIntentRouter:
    """Test intent router functionality."""
    
    def test_rag_query_triggers_rag(self, api_client, check_api_running):
        """Test that asking about personal notes triggers RAG."""
        response = api_client.chat("Tell me about Camila from my notes")
        
        assert response["used_rag"] is True, "Should use RAG for personal notes query"
        answer = response["answer"].lower()
        
        # Should contain specific information about YOUR Camila
        assert any(keyword in answer for keyword in [
            "veterinarian", "vet", "camilafds1995@gmail.com", "wife"
        ]), f"Answer should contain specific info about Camila, got: {answer[:200]}"
        
        # Should NOT be about Queen Camilla
        assert "queen" not in answer, "Should not retrieve Queen Camila from web"
    
    def test_time_query_triggers_tool(self, api_client, check_api_running):
        """Test that asking for time triggers time tool."""
        response = api_client.chat("What time is it right now?")
        
        answer = response["answer"]
        
        # Should contain a time
        import re
        time_pattern = r'\d{1,2}:\d{2}\s*[AP]M'
        assert re.search(time_pattern, answer, re.IGNORECASE), \
            f"Answer should contain time in HH:MM AM/PM format, got: {answer}"
        
        # Should mention timezone
        assert any(tz in answer for tz in ["UTC-3", "BRT", "timezone"]), \
            "Answer should mention timezone"
    
    def test_memory_query_uses_memory(self, api_client, check_api_running, test_memory_id):
        """Test that memory queries retrieve from memory."""
        # Wait for indexing
        time.sleep(3)
        
        response = api_client.chat("What test memories do I have?")
        
        # Should use memory (though it might also use RAG)
        answer = response["answer"].lower()
        assert "test" in answer, f"Should mention test memories, got: {answer[:200]}"


@pytest.mark.integration
@pytest.mark.rag
class TestRAGSystem:
    """Test RAG/Obsidian integration."""
    
    def test_rag_retrieves_personal_info(self, api_client, check_api_running):
        """Test RAG retrieves information from personal notes."""
        response = api_client.chat("What do you know about me from my notes?")
        
        answer = response["answer"].lower()
        
        # Should use RAG
        assert response.get("used_rag") or response.get("used_memory"), \
            "Should use RAG or memory for personal info query"
        
        # Should have actual content (not empty)
        assert len(answer) > 50, "Answer should contain substantial information"
    
    @pytest.mark.parametrize("query,expected_keywords", [
        ("Tell me about Camila", ["veterinarian", "wife", "email"]),
        ("When is my birthday?", ["march", "30"]),
        ("Where do I work?", ["counterpart"]),
    ])
    def test_specific_personal_queries(self, api_client, check_api_running, query, expected_keywords):
        """Test specific queries about personal information."""
        response = api_client.chat(query)
        answer = response["answer"].lower()
        
        # At least one expected keyword should be present
        found_keywords = [kw for kw in expected_keywords if kw in answer]
        assert found_keywords, \
            f"Answer should contain at least one of {expected_keywords}, got: {answer[:200]}"


@pytest.mark.integration
@pytest.mark.memory
class TestMemorySystem:
    """Test memory creation and retrieval."""
    
    def test_create_memory(self, api_client, check_api_running):
        """Test creating a new memory."""
        timestamp = int(time.time())
        
        response = api_client.post("/remember", json={
            "content": f"Test memory {timestamp}: I love pytest",
            "title": f"Pytest Test {timestamp}",
            "tags": ["test", "pytest"]
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "filepath" in data
        assert "chunks_indexed" in data
        
        # Cleanup
        try:
            memories = api_client.get("/admin/memories?limit=200").json()
            for mem in memories.get("memories", []):
                if f"Test memory {timestamp}" in mem.get("full_content", ""):
                    api_client.delete(f"/admin/memories/{mem['id']}")
                    break
        except Exception:
            pass
    
    def test_list_memories(self, api_client, check_api_running):
        """Test listing memories."""
        response = api_client.get("/admin/memories?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "memories" in data
        assert "count" in data
        assert isinstance(data["memories"], list)
    
    def test_memory_retrieval_in_chat(self, api_client, check_api_running, test_memory_id):
        """Test that memories are retrieved in chat."""
        # Wait for indexing
        time.sleep(3)
        
        response = api_client.chat("What do you remember about tests?")
        
        # Should have an answer
        assert len(response["answer"]) > 0
        
        # Might use memory or RAG
        assert response.get("used_memory") or response.get("used_rag"), \
            "Should use memory or RAG for memory retrieval query"


@pytest.mark.integration
@pytest.mark.time
class TestDateTimeSystem:
    """Test date/time functionality."""
    
    def test_current_time_accuracy(self, api_client, check_api_running):
        """Test that current time is accurate."""
        from datetime import datetime
        from app.core.config import settings
        
        # Get system time
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        system_hour = now.strftime("%I").lstrip("0")
        
        # Ask Friday
        response = api_client.chat("What time is it?")
        answer = response["answer"]
        
        # Check if hour matches (within same hour is acceptable)
        assert system_hour in answer or now.strftime("%H") in answer, \
            f"Answer should contain current hour {system_hour}, got: {answer}"
    
    def test_timezone_awareness(self, api_client, check_api_running):
        """Test that Friday is timezone aware."""
        response = api_client.chat("What's the current time with timezone?")
        answer = response["answer"]
        
        # Should mention UTC-3 or BRT
        assert any(tz in answer for tz in ["UTC-3", "BRT", "Brasília"]), \
            f"Answer should mention timezone, got: {answer}"
