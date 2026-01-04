"""
Simple LLM client for OpenAI-compatible APIs (vLLM, etc.)

Replaces npcpy dependency with direct control over LLM interactions.
"""

import logging
from typing import Dict, List, Optional, Any
import httpx
import json

logger = logging.getLogger(__name__)


class LLMClient:
    """Minimal LLM client for OpenAI-compatible APIs."""
    
    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str = "not-needed",
        timeout: float = 60.0
    ):
        """Initialize LLM client.
        
        Args:
            base_url: Base URL for API (e.g., http://localhost:8000/v1)
            model_name: Model name to use
            api_key: API key (optional for local vLLM)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        
        logger.info(f"[LLM] Initialized client: {base_url} / {model_name}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            tool_choice: Tool choice mode ('auto', 'none', or specific tool)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            **kwargs: Additional parameters to pass to API
            
        Returns:
            API response dict
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error(f"[LLM] Request timed out after {self.timeout}s")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM] HTTP error: {e.response.status_code}")
            logger.error(f"[LLM] Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[LLM] Unexpected error: {e}")
            raise
    
    def extract_message(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract message from API response.
        
        Args:
            response: API response dict
            
        Returns:
            Message dict with 'role', 'content', and optional 'tool_calls'
        """
        try:
            return response["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            logger.error(f"[LLM] Failed to extract message: {e}")
            logger.error(f"[LLM] Response: {response}")
            raise ValueError(f"Invalid API response format: {e}")
