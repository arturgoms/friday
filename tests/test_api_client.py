"""
Tests for Friday 3.0 API Client

Tests the shared API client utilities in src/core/api_client.py
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGetApiUrl:
    """Tests for get_api_url function."""
    
    def test_default_url(self):
        """Test default API URL when env not set."""
        from src.core.api_client import get_api_url
        
        with patch.dict("os.environ", {}, clear=True):
            # Should return default even if env var is missing
            url = get_api_url()
            assert url == "http://localhost:8080"
    
    def test_custom_url(self):
        """Test custom API URL from environment."""
        from src.core.api_client import get_api_url
        
        with patch.dict("os.environ", {"FRIDAY_API_URL": "http://custom:9000"}):
            url = get_api_url()
            assert url == "http://custom:9000"


class TestGetApiKey:
    """Tests for get_api_key function."""
    
    def test_no_key(self):
        """Test when no API key is set."""
        from src.core.api_client import get_api_key
        
        with patch.dict("os.environ", {}, clear=True):
            key = get_api_key()
            assert key == ""
    
    def test_with_key(self):
        """Test when API key is set."""
        from src.core.api_client import get_api_key
        
        with patch.dict("os.environ", {"FRIDAY_API_KEY": "test-key-123"}):
            key = get_api_key()
            assert key == "test-key-123"


class TestGetApiHeaders:
    """Tests for get_api_headers function."""
    
    def test_headers_without_key(self):
        """Test headers when no API key is set."""
        from src.core.api_client import get_api_headers
        
        with patch.dict("os.environ", {}, clear=True):
            headers = get_api_headers()
            assert headers["Content-Type"] == "application/json"
            assert "Authorization" not in headers
    
    def test_headers_with_key(self):
        """Test headers when API key is set."""
        from src.core.api_client import get_api_headers
        
        with patch.dict("os.environ", {"FRIDAY_API_KEY": "my-secret-key"}):
            headers = get_api_headers()
            assert headers["Content-Type"] == "application/json"
            assert headers["Authorization"] == "Bearer my-secret-key"


class TestFridayAPIClient:
    """Tests for FridayAPIClient class."""
    
    def test_init_defaults(self):
        """Test client initialization with defaults."""
        from src.core.api_client import FridayAPIClient
        
        with patch.dict("os.environ", {}, clear=True):
            client = FridayAPIClient()
            assert client.base_url == "http://localhost:8080"
            assert client.api_key == ""
            assert client.timeout == 30.0
    
    def test_init_custom(self):
        """Test client initialization with custom values."""
        from src.core.api_client import FridayAPIClient
        
        client = FridayAPIClient(
            base_url="http://custom:9000",
            api_key="test-key",
            timeout=60.0
        )
        assert client.base_url == "http://custom:9000"
        assert client.api_key == "test-key"
        assert client.timeout == 60.0
    
    def test_get_headers_with_key(self):
        """Test _get_headers method with API key."""
        from src.core.api_client import FridayAPIClient
        
        client = FridayAPIClient(api_key="my-key")
        headers = client._get_headers()
        
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer my-key"
    
    def test_get_headers_without_key(self):
        """Test _get_headers method without API key."""
        from src.core.api_client import FridayAPIClient
        
        with patch.dict("os.environ", {"FRIDAY_API_KEY": ""}, clear=False):
            client = FridayAPIClient(api_key="")
            headers = client._get_headers()
            
            assert headers["Content-Type"] == "application/json"
            assert "Authorization" not in headers


@pytest.mark.asyncio
class TestFridayAPIClientAsync:
    """Async tests for FridayAPIClient."""
    
    async def test_chat_success(self):
        """Test successful chat request."""
        from src.core.api_client import FridayAPIClient
        
        client = FridayAPIClient(base_url="http://test:8080")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Hello!", "mode": "chat"}
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await client.chat("Hello", user_id="test")
            
            assert result["text"] == "Hello!"
            assert result["mode"] == "chat"
    
    async def test_send_alert_success(self):
        """Test successful alert send."""
        from src.core.api_client import FridayAPIClient
        
        client = FridayAPIClient(base_url="http://test:8080")
        
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await client.send_alert(
                sensor="test_sensor",
                message="Test alert",
                level="warning"
            )
            
            assert result is True
    
    @pytest.mark.skip(reason="Requires running API server or complex mocking")
    async def test_send_alert_failure(self):
        """Test failed alert send - requires live server."""
        pass
    
    async def test_health_check_success(self):
        """Test successful health check."""
        from src.core.api_client import FridayAPIClient
        
        client = FridayAPIClient(base_url="http://test:8080")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            result = await client.health_check()
            
            assert result is True
    
    @pytest.mark.skip(reason="Requires running API server or complex mocking")
    async def test_health_check_failure(self):
        """Test failed health check - requires live server."""
        pass
