"""Pytest configuration and shared fixtures."""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Generator

try:
    import pytest
    import requests
except ImportError:
    print("Please install pytest and requests: pipenv install --dev pytest requests")
    sys.exit(1)

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# API configuration
API_BASE_URL = "http://localhost:8080"
API_KEY = os.getenv("FRIDAY_API_KEY", "5b604c9f8e2d1be2978d91b51f2b3fe70b64f2b552cea1870e764dd6016c0de9")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for API requests."""
    return API_BASE_URL


@pytest.fixture(scope="session")
def api_key() -> str:
    """API key for authenticated requests."""
    return API_KEY


@pytest.fixture(scope="session")
def api_headers(api_key: str) -> Dict[str, str]:
    """Common headers for API requests."""
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="session")
def api_client(api_base_url: str, api_headers: Dict[str, str]):
    """API client session."""
    session = requests.Session()
    session.headers.update(api_headers)
    
    class APIClient:
        """Simple API client wrapper."""
        
        def __init__(self, base_url: str, session: requests.Session):
            self.base_url = base_url
            self.session = session
        
        def get(self, endpoint: str, **kwargs) -> requests.Response:
            """GET request."""
            return self.session.get(f"{self.base_url}{endpoint}", **kwargs)
        
        def post(self, endpoint: str, **kwargs) -> requests.Response:
            """POST request."""
            return self.session.post(f"{self.base_url}{endpoint}", **kwargs)
        
        def delete(self, endpoint: str, **kwargs) -> requests.Response:
            """DELETE request."""
            return self.session.delete(f"{self.base_url}{endpoint}", **kwargs)
        
        def chat(self, message: str, **kwargs) -> Dict[str, Any]:
            """Send chat message and return JSON response."""
            payload = {"message": message}
            payload.update(kwargs)
            response = self.post("/chat", json=payload)
            response.raise_for_status()
            return response.json()
    
    return APIClient(api_base_url, session)


@pytest.fixture(scope="session")
def check_api_running(api_client):
    """Ensure API is running before tests."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = api_client.get("/health")
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
            else:
                pytest.exit("API is not running. Start it with: friday restart friday", returncode=1)
    return True


@pytest.fixture
def test_memory_id(api_client) -> Generator[str, None, None]:
    """Create a test memory and return its ID for cleanup."""
    import time
    timestamp = int(time.time())
    
    response = api_client.post("/remember", json={
        "content": f"Test memory {timestamp}: This is a test",
        "title": f"Test {timestamp}",
        "tags": ["test", "pytest"]
    })
    
    data = response.json()
    memory_file = data.get("filepath")
    
    yield memory_file
    
    # Cleanup: Find and delete the memory
    try:
        memories = api_client.get("/admin/memories?limit=200").json()
        for mem in memories.get("memories", []):
            if f"Test memory {timestamp}" in mem.get("full_content", ""):
                api_client.delete(f"/admin/memories/{mem['id']}")
                break
        
        # Also remove file if exists
        if memory_file and os.path.exists(memory_file):
            os.remove(memory_file)
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def brain_paths():
    """Provide brain folder paths for testing."""
    from app.core.config import settings
    
    return {
        "brain": settings.brain_path,
        "vault": settings.vault_path,
        "memories": settings.memories_path,
        "journal": settings.journal_path,
        "reports": settings.reports_path,
        "reminders": settings.reminders_path
    }


@pytest.fixture
def memory_store():
    """Provide memory store instance for testing."""
    from app.services.memory_store import MemoryStore
    return MemoryStore()


@pytest.fixture
def brain_service():
    """Provide brain service instance for testing."""
    from app.services.brain_service import BrainService
    return BrainService()


@pytest.fixture
def test_brain_memory(memory_store) -> Generator[Dict[str, Any], None, None]:
    """Create a test memory in brain folder and cleanup after."""
    import time
    timestamp = int(time.time())
    
    memory_id, _ = memory_store.add_memory(
        content=f"Test brain memory {timestamp}: Created by pytest fixture",
        label="pytest",
        tags=["test", "fixture"],
        force=True
    )
    
    # Find the created file (filename is just the ID now)
    memory_files = list(memory_store.memories_path.glob(f"{memory_id}*.md"))
    memory_file = memory_files[0] if memory_files else None
    
    yield {
        "id": memory_id,
        "filepath": str(memory_file) if memory_file else None,
        "timestamp": timestamp
    }
    
    # Cleanup
    try:
        if memory_file and memory_file.exists():
            memory_file.unlink()
    except Exception:
        pass



