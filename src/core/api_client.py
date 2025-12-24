"""
Friday 3.0 API Client

Shared utilities for communicating with friday-core API.
Used by CLI, Telegram bot, and awareness daemon.

Usage:
    from src.core.api_client import get_api_url, get_api_headers, FridayAPIClient
    
    # Simple usage
    url = get_api_url()
    headers = get_api_headers()
    
    # Full client
    client = FridayAPIClient()
    response = await client.chat("Hello!")
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default API URL (local friday-core service)
DEFAULT_API_URL = "http://localhost:8080"

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30.0

# Long timeout for chat requests that may involve tool execution
CHAT_TIMEOUT = 120.0


def get_api_url() -> str:
    """Get the friday-core API URL from environment or default.
    
    Returns:
        API URL string
    """
    return os.getenv("FRIDAY_API_URL", DEFAULT_API_URL)


def get_api_key() -> str:
    """Get the API key from environment.
    
    Returns:
        API key string (empty if not set)
    """
    return os.getenv("FRIDAY_API_KEY", "")


def get_api_headers() -> Dict[str, str]:
    """Get headers for API requests including authentication.
    
    Returns:
        Headers dict with Content-Type and optional Authorization
    """
    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


class FridayAPIClient:
    """Async HTTP client for friday-core API.
    
    Provides methods for chat, alerts, and health checks.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """Initialize the API client.
        
        Args:
            base_url: API base URL (default: from FRIDAY_API_URL env)
            api_key: API key (default: from FRIDAY_API_KEY env)
            timeout: Default request timeout in seconds
        """
        self.base_url = base_url or get_api_url()
        self.api_key = api_key or get_api_key()
        self.timeout = timeout
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def chat(
        self,
        text: str,
        user_id: str = "api",
        session_id: Optional[str] = None,
        fresh: bool = False,
        stream: bool = False,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Send a chat message to friday-core.
        
        Args:
            text: Message text
            user_id: User identifier
            session_id: Session ID for conversation continuity
            fresh: Clear conversation history before this message
            stream: Enable streaming response
            timeout: Request timeout (default: CHAT_TIMEOUT)
            
        Returns:
            API response dict with 'text', 'mode', etc.
        """
        import httpx
        
        payload = {
            "text": text,
            "user_id": user_id,
            "session_id": session_id or user_id,
            "fresh": fresh,
            "stream": stream
        }
        
        async with httpx.AsyncClient(timeout=timeout or CHAT_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/chat",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def send_alert(
        self,
        sensor: str,
        message: str,
        level: str = "info",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send an alert to friday-core.
        
        Args:
            sensor: Sensor name that generated the alert
            message: Alert message
            level: Alert level (info/warning/critical)
            data: Additional data
            
        Returns:
            True if alert was sent successfully
        """
        import httpx
        
        payload = {
            "sensor": sensor,
            "message": message,
            "level": level,
            "data": data or {}
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/alert",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"[API_CLIENT] Failed to send alert: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if friday-core is healthy.
        
        Returns:
            True if API is responding
        """
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
