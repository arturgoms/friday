"""
Friday 3.0 Test Configuration

Shared fixtures and configuration for pytest.
"""

import os
import sys
import pytest
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up common environment variables for testing."""
    monkeypatch.setenv("FRIDAY_API_URL", "http://localhost:8080")
    monkeypatch.setenv("FRIDAY_API_KEY", "test-api-key")
    monkeypatch.setenv("INFLUXDB_PASSWORD", "test-password")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_USER_ID", "12345678")


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value=MagicMock(
        text="Test response",
        tool_calls=[],
        code_blocks=[],
        finish_reason="stop",
        usage={"total_tokens": 100}
    ))
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_influx_client():
    """Create a mock InfluxDB client."""
    mock = MagicMock()
    mock.ping = MagicMock(return_value=True)
    mock.query = MagicMock(return_value=MagicMock(
        get_points=MagicMock(return_value=iter([]))
    ))
    return mock


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx async client."""
    mock = AsyncMock()
    mock.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"text": "response"})
    ))
    mock.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={})
    ))
    return mock


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def temp_insights_db(tmp_path: Path):
    """Create a temporary insights database."""
    from src.insights.store import InsightsStore
    
    db_path = tmp_path / "test_insights.db"
    store = InsightsStore(db_path)
    yield store
    # Cleanup handled by tmp_path fixture


@pytest.fixture
def temp_vector_store(tmp_path: Path):
    """Create a temporary vector store."""
    from src.core.vector_store import VectorStore
    
    store = VectorStore(persist_directory=str(tmp_path / "chroma"))
    yield store


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_health_data():
    """Sample health data for testing."""
    return {
        "sleep": {
            "sleepScore": 85,
            "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "avgOvernightHrv": 45,
            "restingHeartRate": 52
        },
        "stress": {
            "stressLevel": 35,
            "highStressDuration": 1800,
            "mediumStressDuration": 7200,
            "lowStressDuration": 10800,
            "restStressDuration": 14400
        },
        "body_battery": {
            "bodyBatteryAtWakeTime": 75,
            "stressAvg": 32
        },
        "training_readiness": {
            "score": 72,
            "level": "MODERATE",
            "recoveryTime": 24
        }
    }


@pytest.fixture
def sample_calendar_events():
    """Sample calendar events for testing."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    return [
        {
            "title": "Team Meeting",
            "start": now + timedelta(hours=1),
            "end": now + timedelta(hours=2),
            "calendar": "work"
        },
        {
            "title": "Dentist",
            "start": now + timedelta(days=1, hours=10),
            "end": now + timedelta(days=1, hours=11),
            "calendar": "personal"
        }
    ]


@pytest.fixture
def sample_insight():
    """Create a sample insight for testing."""
    from src.insights.models import Insight, Priority, Category, InsightType
    from datetime import datetime
    from src.core.constants import BRT
    
    return Insight(
        title="Test Insight",
        message="This is a test insight message",
        priority=Priority.MEDIUM,
        category=Category.HEALTH,
        insight_type=InsightType.THRESHOLD,
        source="test",
        created_at=datetime.now(BRT)
    )
