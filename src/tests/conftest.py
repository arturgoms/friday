"""
Pytest configuration and shared fixtures for tool tests.

These tests are designed to run without agent dependencies,
testing the tool functions directly.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_settings():
    """Mock settings object with default configuration."""
    from settings import settings
    return settings


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API calls."""
    with patch('httpx.Client') as mock:
        yield mock


@pytest.fixture
def mock_httpx_get():
    """Mock httpx.get for simple GET requests."""
    with patch('httpx.get') as mock:
        yield mock


@pytest.fixture
def temp_vault_dir(tmp_path):
    """Create a temporary vault directory for testing."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    notes_dir = vault_dir / "1. Notes"
    notes_dir.mkdir()
    return vault_dir


@pytest.fixture
def mock_influxdb():
    """Mock InfluxDB client and queries."""
    with patch('src.core.influxdb.get_influx_client') as mock_client, \
         patch('src.core.influxdb.query') as mock_query:
        yield {'client': mock_client, 'query': mock_query}


@pytest.fixture
def mock_calendar_caldav():
    """Mock CalDAV client for calendar operations."""
    with patch('caldav.DAVClient') as mock:
        yield mock


@pytest.fixture
def mock_google_calendar():
    """Mock Google Calendar API."""
    with patch('googleapiclient.discovery.build') as mock:
        yield mock


@pytest.fixture
def sample_event_data():
    """Sample calendar event data for testing."""
    return {
        'id': 'test-event-123',
        'title': 'Test Meeting',
        'start': '2024-01-10T10:00:00',
        'end': '2024-01-10T11:00:00',
        'description': 'A test event',
        'location': 'Virtual',
    }


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        'weather': [{'main': 'Clear', 'description': 'clear sky'}],
        'main': {
            'temp': 22.5,
            'feels_like': 21.0,
            'humidity': 65,
            'pressure': 1013
        },
        'wind': {'speed': 3.5},
        'name': 'Curitiba'
    }


@pytest.fixture
def sample_health_data():
    """Sample health data from InfluxDB."""
    return [
        {
            'time': '2024-01-10T08:00:00Z',
            'SleepScore': 85,
            'DeepSleep': 1.5,
            'REMSleep': 2.0,
            'BodyBattery': 95,
            'StressLevel': 25,
        }
    ]


@pytest.fixture
def mock_agent():
    """Mock agent for decorator testing."""
    mock = Mock()
    mock.tool_plain = lambda func: func  # Passthrough decorator
    return mock


@pytest.fixture(autouse=True)
def reset_agent_decorator():
    """Reset agent decorator to passthrough for all tests."""
    # This ensures @agent.tool_plain doesn't interfere with testing
    with patch('src.core.agent.agent') as mock_agent:
        mock_agent.tool_plain = lambda func: func
        yield mock_agent


@pytest.fixture
def test_db():
    """Create an in-memory test database with schema."""
    from src.core.database import Database
    
    # Create in-memory database
    db = Database(in_memory=True)
    
    yield db
    
    # Cleanup
    db.close()


@pytest.fixture
def populated_test_db(test_db):
    """Create a test database with sample conversation data."""
    # Insert sample conversation history
    sample_messages = [
        {
            'conversation_id': 'default',
            'timestamp': '2024-01-10T10:00:00',
            'role': 'user',
            'content': 'What is the weather like?'
        },
        {
            'conversation_id': 'default',
            'timestamp': '2024-01-10T10:00:05',
            'role': 'assistant',
            'content': 'The weather is sunny and 22°C.'
        },
        {
            'conversation_id': 'default',
            'timestamp': '2024-01-10T10:01:00',
            'role': 'user',
            'content': 'Thanks! Can you search for Python news?'
        },
        {
            'conversation_id': 'default',
            'timestamp': '2024-01-10T10:01:10',
            'role': 'assistant',
            'content': 'Here are the latest Python news...'
        },
    ]
    
    for msg in sample_messages:
        test_db.insert('conversation_history', msg)
    
    yield test_db


@pytest.fixture
def mock_get_db(test_db):
    """Mock get_db() to return test database."""
    with patch('src.tools.memory.get_db', return_value=test_db):
        yield test_db
