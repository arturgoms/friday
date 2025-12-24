"""
Friday 3.0 LLM Client

Async OpenAI-compatible client for communicating with vLLM or any
OpenAI-compatible inference server.

Usage:
    from src.core.llm import LLMClient, get_llm_client
    
    client = get_llm_client()
    response = await client.generate("Hello, world!")
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .config import get_config

logger = logging.getLogger(__name__)


# =============================================================================
# Response Types
# =============================================================================

@dataclass
class ToolCall:
    """Represents a tool call extracted from LLM response."""
    name: str
    arguments: Dict[str, Any]
    raw_json: str = ""


@dataclass
class CodeBlock:
    """Represents a code block extracted from LLM response."""
    language: str
    code: str


@dataclass 
class LLMResponse:
    """Structured response from LLM."""
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    
    def has_tool_call(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0
    
    def has_code(self) -> bool:
        """Check if response contains executable code blocks."""
        return len(self.code_blocks) > 0
    
    def is_chat_only(self) -> bool:
        """Check if this is a pure chat response (no tools or code)."""
        return not self.has_tool_call() and not self.has_code()


# =============================================================================
# LLM Client
# =============================================================================

class LLMClient:
    """Async client for OpenAI-compatible LLM APIs."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "dphn/Dolphin3.0-Llama3.1-8B",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 120.0
    ):
        """Initialize the LLM client.
        
        Args:
            base_url: Base URL for the OpenAI-compatible API
            model: Model name/identifier
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "application/json"}
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _parse_tool_calls(self, text: str) -> List[ToolCall]:
        """Extract tool calls from response text.
        
        Looks for JSON objects with 'tool' and 'args' keys.
        
        Args:
            text: LLM response text
            
        Returns:
            List of extracted tool calls
        """
        tool_calls = []
        text = text.strip()
        
        # Method 1: Try parsing the entire text as JSON first (most reliable for clean output)
        if text.startswith("{") and text.endswith("}"):
            try:
                obj = json.loads(text)
                if "tool" in obj and "args" in obj:
                    tool_calls.append(ToolCall(
                        name=obj["tool"],
                        arguments=obj.get("args", {}),
                        raw_json=text
                    ))
                    return tool_calls
            except json.JSONDecodeError:
                pass
        
        # Method 2: Find JSON objects that look like tool calls using balanced brace matching
        i = 0
        while i < len(text):
            if text[i] == '{':
                # Find matching closing brace
                depth = 1
                j = i + 1
                while j < len(text) and depth > 0:
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                    j += 1
                
                if depth == 0:
                    json_str = text[i:j]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict) and "tool" in obj and "args" in obj:
                            tool_calls.append(ToolCall(
                                name=obj["tool"],
                                arguments=obj.get("args", {}),
                                raw_json=json_str
                            ))
                    except json.JSONDecodeError:
                        pass
                    i = j
                else:
                    i += 1
            else:
                i += 1
        
        return tool_calls
    
    def _parse_code_blocks(self, text: str) -> List[CodeBlock]:
        """Extract code blocks from response text.
        
        Args:
            text: LLM response text
            
        Returns:
            List of extracted code blocks
        """
        code_blocks = []
        
        # Match ```language\ncode\n```
        pattern = r'```(\w*)\n(.*?)```'
        
        for match in re.finditer(pattern, text, re.DOTALL):
            language = match.group(1) or "python"  # Default to python
            code = match.group(2).strip()
            if code:
                code_blocks.append(CodeBlock(language=language, code=code))
        
        return code_blocks
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            prompt: User prompt (ignored if messages provided)
            system_prompt: Optional system prompt
            messages: Optional list of messages (overrides prompt/system_prompt)
            tools: Optional list of tool schemas for function calling
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            stop: Optional list of stop sequences
            
        Returns:
            LLMResponse with parsed text, tool calls, and code blocks
        """
        client = await self._get_client()
        
        # Build messages
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        
        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        
        if stop:
            payload["stop"] = stop
        
        # Note: We don't use native tool calling since vLLM requires special flags
        # Instead, we inject tool schemas into the system prompt and parse JSON from text
        # if tools:
        #     payload["tools"] = tools
        #     payload["tool_choice"] = "auto"
        
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract response content
            choice = data["choices"][0]
            message = choice["message"]
            text = message.get("content", "") or ""
            finish_reason = choice.get("finish_reason", "stop")
            
            # Parse tool calls and code blocks
            tool_calls = self._parse_tool_calls(text)
            code_blocks = self._parse_code_blocks(text)
            
            # Also check for native tool calls in response
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    if tc["type"] == "function":
                        func = tc["function"]
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(ToolCall(
                            name=func["name"],
                            arguments=args,
                            raw_json=json.dumps(tc)
                        ))
            
            return LLMResponse(
                text=text,
                tool_calls=tool_calls,
                code_blocks=code_blocks,
                finish_reason=finish_reason,
                usage=data.get("usage", {})
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM] API error {e.response.status_code}: {e.response.text[:200]}")
            raise
        except httpx.RequestError as e:
            logger.error(f"[LLM] Request failed to {self.base_url}: {e}")
            raise
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM.
        
        Args:
            prompt: User prompt (ignored if messages provided)
            system_prompt: Optional system prompt
            messages: Optional list of messages
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            
        Yields:
            Text chunks as they arrive
        """
        client = await self._get_client()
        
        # Build messages
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True
        }
        
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM stream error: {e.response.status_code}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the LLM API is available.
        
        Returns:
            True if API is reachable, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False


# =============================================================================
# Global Client Instance
# =============================================================================

_llm_client: Optional[LLMClient] = None
_llm_client_lock = threading.Lock()


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance (thread-safe).
    
    Loads configuration from config.yml on first call.
    
    Returns:
        LLMClient instance
    """
    global _llm_client
    
    if _llm_client is None:
        with _llm_client_lock:
            # Double-check pattern for thread safety
            if _llm_client is None:
                config = get_config()
                _llm_client = LLMClient(
                    base_url=config.llm.base_url,
                    model=config.llm.model_name,
                    temperature=config.llm.temperature,
                    max_tokens=config.llm.max_tokens
                )
                logger.info(f"LLMClient initialized: {config.llm.base_url} model={config.llm.model_name}")
    
    return _llm_client


async def close_llm_client():
    """Close the global LLM client."""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
