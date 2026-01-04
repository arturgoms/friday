"""
Friday Core API - OpenAI-compatible proxy with tool execution.

Thin proxy that:
1. Accepts OpenAI-format requests
2. Adds tool definitions from registry  
3. Forwards to vLLM
4. Executes tool calls
5. Loops until done
6. Returns OpenAI-format response
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.config import get_config
from src.core.history import ConversationHistory
from src.core.loader import load_tools
from src.core.registry import build_tool_definitions, get_tool, get_tool_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Friday Core API", version="3.0")

# Global instances
history: Optional[ConversationHistory] = None
vllm_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global history, vllm_client
    
    logger.info("[STARTUP] Friday Core API starting...")
    
    # Load configuration
    config = get_config()
    
    # Load all tools
    loaded = load_tools()
    tool_count = len(get_tool_registry())
    logger.info(f"[STARTUP] Loaded {tool_count} tools from {len(loaded)} modules")
    
    # Initialize history storage
    history = ConversationHistory()
    
    # Initialize vLLM client
    vllm_client = httpx.AsyncClient(base_url=config.llm.base_url, timeout=120.0)
    
    logger.info(f"[STARTUP] vLLM endpoint: {config.llm.base_url}")
    logger.info("[STARTUP] Friday Core API ready!")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global vllm_client
    
    if vllm_client:
        await vllm_client.aclose()
    
    logger.info("[SHUTDOWN] Friday Core API stopped")


# ============================================================================
# Request/Response Models
# ============================================================================

class Message(BaseModel):
    """Chat message."""
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None


class ChatRequest(BaseModel):
    """OpenAI-compatible chat request."""
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.6
    max_tokens: Optional[int] = 2048
    tools: Optional[List[Dict]] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    """OpenAI-compatible chat response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict]
    usage: Optional[Dict] = None


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    tool_count = len(get_tool_registry())
    
    return {
        "status": "healthy",
        "tools_loaded": tool_count,
        "version": "3.0"
    }


# ============================================================================
# Chat Completion (OpenAI-compatible)
# ============================================================================

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> ChatResponse:
    """OpenAI-compatible chat completions endpoint with tool execution.
    
    This endpoint:
    1. Adds tool definitions to the request
    2. Forwards to vLLM
    3. Executes any tool calls
    4. Loops until vLLM returns a final response
    5. Saves to history
    """
    if vllm_client is None:
        raise HTTPException(status_code=500, detail="vLLM client not initialized")
    
    logger.info(f"[CHAT] Request with {len(request.messages)} messages")
    
    # Build tool definitions from registry
    tool_definitions = build_tool_definitions()
    
    # Prepare messages for vLLM
    messages = [msg.dict(exclude_none=True) for msg in request.messages]
    
    # Add system message if not present
    if not messages or messages[0].get("role") != "system":
        from datetime import datetime
        
        config = get_config()
        tz = config.get_timezone()
        now = datetime.now(tz)
        
        system_prompt = f"""You are Friday, an AI assistant.

Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}

Use tools to answer user questions. After getting the information from tools, provide a clear answer. Do NOT call unnecessary tools."""
        
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })
    
    # Multi-turn tool execution loop
    max_turns = 10
    turn = 0
    
    while turn < max_turns:
        # Build vLLM request
        vllm_request = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "tools": tool_definitions,
            "tool_choice": "auto"
        }
        
        # Call vLLM
        try:
            response = await vllm_client.post(
                "/chat/completions",
                json=vllm_request
            )
            response.raise_for_status()
            vllm_response = response.json()
        except Exception as e:
            logger.error(f"[CHAT] vLLM call failed: {e}")
            raise HTTPException(status_code=502, detail=f"vLLM error: {str(e)}")
        
        # Extract assistant message
        choice = vllm_response["choices"][0]
        assistant_message = choice["message"]
        
        # Check for tool calls
        tool_calls = assistant_message.get("tool_calls", [])
        
        if not tool_calls:
            # No tool calls, we're done
            logger.info(f"[CHAT] Completed after {turn} turns")
            
            # Save to history (extract user/assistant messages)
            if len(request.messages) > 0:
                user_msg = request.messages[-1].content
                assistant_msg = assistant_message.get("content", "")
                
                if history:
                    history.add_message("default", "user", user_msg, request.model)
                    history.add_message("default", "assistant", assistant_msg, request.model)
            
            return ChatResponse(**vllm_response)
        
        # Execute tools
        turn += 1
        logger.info(f"[CHAT] Turn {turn}/{max_turns}: {len(tool_calls)} tool(s)")
        
        # Add assistant message with tool calls
        messages.append(assistant_message)
        
        # Execute each tool
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]
            tool_id = tool_call["id"]
            
            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError as e:
                logger.error(f"[CHAT] Invalid tool args for {tool_name}: {e}")
                result = f"Error: Invalid arguments - {str(e)}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result
                })
                continue
            
            logger.info(f"[CHAT]   → {tool_name}({tool_args})")
            
            # Execute tool
            try:
                tool_func = get_tool(tool_name)
                result = tool_func(**tool_args)
                
                # Ensure result is string
                if not isinstance(result, str):
                    result = json.dumps(result)
                
                # Log result preview
                result_preview = result[:150]
                if len(result) > 150:
                    result_preview += "..."
                logger.info(f"[CHAT]   ← {result_preview}")
                
            except KeyError:
                logger.error(f"[CHAT] Tool not found: {tool_name}")
                result = f"Error: Tool '{tool_name}' not found"
            except Exception as e:
                logger.error(f"[CHAT] Tool {tool_name} failed: {e}")
                result = f"Error: {str(e)}"
            
            # Add tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result
            })
    
    # Hit max turns
    logger.warning(f"[CHAT] Reached max turns ({max_turns})")
    
    # Return a default response
    return ChatResponse(
        id="chatcmpl-max-turns",
        created=0,
        model=request.model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "I've completed multiple tool calls. Please ask me to continue if needed."
            },
            "finish_reason": "stop"
        }]
    )


# ============================================================================
# Legacy /chat Endpoint (for Friday CLI compatibility)
# ============================================================================

class LegacyChatRequest(BaseModel):
    """Legacy chat request format."""
    text: str


@app.post("/chat")
async def legacy_chat(request: LegacyChatRequest):
    """Legacy chat endpoint for Friday CLI compatibility.
    
    This wraps the OpenAI-compatible endpoint for easier CLI usage.
    """
    # Convert to OpenAI format
    openai_request = ChatRequest(
        model="NousResearch/Hermes-4-14B",
        messages=[
            Message(role="user", content=request.text)
        ]
    )
    
    # Call OpenAI-compatible endpoint
    response = await chat_completions(openai_request)
    
    # Extract text from response
    text = response.choices[0]["message"]["content"]
    
    # Return simple format
    return {
        "text": text,
        "mode": "chat"
    }


# ============================================================================
# List Tools
# ============================================================================

@app.get("/v1/tools")
async def list_tools():
    """List all registered tools."""
    tools = get_tool_registry()
    
    return {
        "tools": [
            {
                "name": name,
                "description": func.__doc__ or "No description"
            }
            for name, func in tools.items()
        ],
        "count": len(tools)
    }
