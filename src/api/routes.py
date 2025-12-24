"""
Friday 3.0 API Routes

FastAPI routes for the friday-core service.

Endpoints:
    POST /chat - Main chat endpoint
    POST /alert - Alert from awareness service
    GET /health - Health check
    GET /tools - List registered tools
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from src.core.agent import close_agent, get_agent
from src.core.config import get_config
from src.core.context import get_context_builder
from src.core.loader import load_extensions
from src.core.llm import close_llm_client, get_llm_client
from src.core.registry import get_all_tool_schemas, get_sensor_registry, get_tool_registry
from src.core.vector_store import BrainIndexer, get_vector_store

# Configure logging with timezone-aware timestamps (UTC-3 / America/Sao_Paulo)
class BRTFormatter(logging.Formatter):
    """Custom formatter that uses Brazil timezone (UTC-3)."""
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.tz = timezone(timedelta(hours=-3))
    
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(BRTFormatter(
    fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logging.root.handlers = []
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)

logger = logging.getLogger("friday")


# =============================================================================
# API Key Authentication
# =============================================================================

API_KEY = os.getenv("FRIDAY_API_KEY", "")

# =============================================================================
# Telegram Notifications
# =============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID", "")


async def send_telegram_notification(message: str, level: str = "info", raw: bool = False) -> bool:
    """Send a notification to Telegram.
    
    Args:
        message: Message to send
        level: Alert level (info/warning/critical) for emoji prefix
        raw: If True, send message as-is without adding prefix
        
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
        logger.warning("Telegram not configured, skipping notification")
        return False
    
    if raw:
        formatted_message = message
    else:
        # Add emoji prefix based on level
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(level, "📢")
        formatted_message = f"{emoji} Friday Alert\n\n{message}"
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_USER_ID,
                    "text": formatted_message,
                    # No parse_mode - plain text is safer for dynamic content
                }
            )
            if response.status_code == 200:
                logger.info(f"Telegram notification sent: {level}")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_api_key(authorization: Optional[str] = Security(api_key_header)) -> bool:
    """Verify API key from Authorization header.
    
    Expects: Authorization: Bearer <api_key>
    
    If FRIDAY_API_KEY is not set, authentication is disabled.
    """
    # If no API key configured, allow all requests
    if not API_KEY:
        return True
    
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Use: Bearer <api_key>"
        )
    
    token = parts[1]
    if token != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return True


# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Friday 3.0 Core...")
    
    # Load extensions (tools and sensors)
    load_extensions()
    tool_count = len(get_tool_registry())
    sensor_count = len(get_sensor_registry())
    logger.info(f"Loaded {tool_count} tools, {sensor_count} sensors")
    
    # Initialize vector store and index brain if needed
    config = get_config()
    try:
        store = get_vector_store()
        doc_count = store.count()
        logger.info(f"Vector store initialized with {doc_count} documents")
        
        # If empty, index the brain folder
        if doc_count == 0:
            logger.info("Indexing brain folder...")
            indexer = BrainIndexer(
                brain_path=config.paths.brain,
                vector_store=store,
                chunk_size=config.memory.chunk_size,
                chunk_overlap=config.memory.chunk_overlap
            )
            stats = indexer.index_all()
            logger.info(f"Brain indexed: {stats['files_indexed']} files, {stats['chunks_created']} chunks")
    except Exception as e:
        logger.warning(f"Vector store initialization failed: {e}")
    
    # Initialize context builder and wire to agent
    context_builder = get_context_builder()
    agent = get_agent()
    agent.context_builder = context_builder.build_for_query
    logger.info("Context builder wired to agent")
    
    # Verify LLM connection
    llm = get_llm_client()
    if await llm.health_check():
        logger.info("LLM connection verified")
    else:
        logger.warning("LLM not reachable - some features may not work")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Friday 3.0 Core...")
    await close_agent()
    await close_llm_client()


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Friday 3.0",
    description="Autonomous AI Platform - Core Service",
    version="3.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """Chat request model."""
    text: str = Field(..., description="User message")
    user_id: str = Field(default="default", description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    stream: bool = Field(default=False, description="Enable streaming response")
    fresh: bool = Field(default=False, description="Clear conversation history before this message")


class ChatResponse(BaseModel):
    """Chat response model."""
    text: str = Field(..., description="Assistant response")
    mode: str = Field(..., description="Response mode (tool/code/chat)")
    tool_results: list = Field(default_factory=list, description="Tool execution results")
    iterations: int = Field(default=1, description="Number of ReAct iterations")
    error: Optional[str] = Field(default=None, description="Error message if any")


class AlertRequest(BaseModel):
    """Alert request from awareness service."""
    sensor: str = Field(..., description="Sensor that triggered the alert")
    message: str = Field(..., description="Alert message")
    level: str = Field(default="info", description="Alert level (info/warning/critical)")
    data: dict = Field(default_factory=dict, description="Additional data")


class AlertResponse(BaseModel):
    """Alert response."""
    acknowledged: bool = Field(..., description="Whether alert was acknowledged")
    action_taken: Optional[str] = Field(default=None, description="Action taken if any")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    llm_available: bool = Field(..., description="LLM service availability")
    tools_loaded: int = Field(..., description="Number of loaded tools")
    sensors_loaded: int = Field(..., description="Number of loaded sensors")


# =============================================================================
# Routes
# =============================================================================

@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs."""
    return {"message": "Friday 3.0 Core", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    llm = get_llm_client()
    llm_available = await llm.health_check()
    
    return HealthResponse(
        status="healthy",
        llm_available=llm_available,
        tools_loaded=len(get_tool_registry()),
        sensors_loaded=len(get_sensor_registry())
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, authorized: bool = Depends(verify_api_key)):
    """Main chat endpoint.
    
    Processes user messages through the Hybrid Agent which routes
    between tools, code execution, and chat based on the request.
    """
    try:
        # Log incoming request
        logger.info(f"[CHAT] Request from user={request.user_id}: {request.text[:100]}{'...' if len(request.text) > 100 else ''}")
        
        agent = get_agent()
        
        # Clear conversation if fresh=True (for single queries from CLI)
        if request.fresh:
            session = request.session_id or request.user_id
            agent.clear_conversation(session)
            logger.info(f"[CHAT] Cleared conversation for session={session}")
        
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in agent.run_stream(
                    request.text,
                    user_id=request.user_id,
                    session_id=request.session_id
                ):
                    yield chunk
            
            return StreamingResponse(generate(), media_type="text/plain")
        
        # Non-streaming response
        response = await agent.run(
            request.text,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        # Log response details
        logger.info(f"[CHAT] Response mode={response.mode}, iterations={response.iterations}")
        if response.tool_results:
            for tr in response.tool_results:
                tool_name = tr.get('tool', 'unknown')
                success = tr.get('success', False)
                result_preview = str(tr.get('result', ''))[:100]
                logger.info(f"[TOOL] {tool_name}: success={success}, result={result_preview}...")
        if response.code_results:
            for i, cr in enumerate(response.code_results):
                logger.info(f"[CODE] Block {i+1}: success={cr.success}, stdout={cr.stdout[:100] if cr.stdout else '(none)'}...")
        
        # Log response text preview
        response_preview = response.text[:150] if response.text else '(empty)'
        logger.info(f"[CHAT] Response text: {response_preview}{'...' if len(response.text or '') > 150 else ''}")
        
        return ChatResponse(
            text=response.text,
            mode=response.mode,
            tool_results=response.tool_results,
            iterations=response.iterations,
            error=response.error
        )
        
    except Exception as e:
        logger.error(f"[CHAT] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alert", response_model=AlertResponse, tags=["Alerts"])
async def receive_alert(request: AlertRequest, authorized: bool = Depends(verify_api_key)):
    """Receive alerts from the awareness service.
    
    The awareness daemon sends alerts here when sensors detect
    conditions that require attention.
    
    Warning and critical alerts are forwarded to Telegram.
    """
    try:
        logger.info(f"Alert received: {request.sensor} - {request.level}: {request.message}")
        
        action_taken = None
        
        # Forward warning, critical, and scheduled reports to Telegram
        is_scheduled_report = request.sensor.startswith("scheduled_")
        is_insights_alert = request.sensor.startswith("insights_")
        
        if request.level in ("warning", "critical") or is_scheduled_report:
            # Insights alerts are already well-formatted, pass through directly
            if is_insights_alert:
                alert_message = request.message
            else:
                # Format message with sensor data (plain text, no markdown)
                alert_message = f"[{request.level.upper()}] {request.sensor}\n\n{request.message}"
                
                # Add relevant data if present
                if request.data:
                    data_lines = [f"- {k}: {v}" for k, v in request.data.items() if k != "sensor"]
                    if data_lines:
                        alert_message += "\n\n" + "\n".join(data_lines)
            
            # Send to Telegram (insights alerts are pre-formatted, use raw mode)
            sent = await send_telegram_notification(alert_message, request.level, raw=is_insights_alert)
            if sent:
                action_taken = "telegram_notification_sent"
        
        return AlertResponse(
            acknowledged=True,
            action_taken=action_taken
        )
        
    except Exception as e:
        logger.error(f"Alert processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools", tags=["System"])
async def list_tools(authorized: bool = Depends(verify_api_key)):
    """List all registered tools and their schemas."""
    registry = get_tool_registry()
    
    return {
        "count": len(registry),
        "tools": [
            {
                "name": entry.name,
                "description": entry.description,
                "schema": entry.schema
            }
            for entry in registry.values()
        ]
    }


@app.get("/sensors", tags=["System"])
async def list_sensors(authorized: bool = Depends(verify_api_key)):
    """List all registered sensors."""
    registry = get_sensor_registry()
    
    return {
        "count": len(registry),
        "sensors": [
            {
                "name": entry.name,
                "description": entry.description,
                "interval_seconds": entry.interval_seconds,
                "enabled": entry.enabled
            }
            for entry in registry.values()
        ]
    }


@app.post("/conversation/clear", tags=["Chat"])
async def clear_conversation(
    user_id: str = "default",
    session_id: Optional[str] = None,
    authorized: bool = Depends(verify_api_key)
):
    """Clear conversation history for a session."""
    agent = get_agent()
    agent.clear_conversation(session_id or user_id)
    return {"message": "Conversation cleared"}


@app.get("/conversation/history", tags=["Chat"])
async def get_conversation_history(
    user_id: str = "default",
    session_id: Optional[str] = None,
    authorized: bool = Depends(verify_api_key)
):
    """Get conversation history for a session."""
    agent = get_agent()
    history = agent.get_conversation_history(session_id or user_id)
    return {"messages": history}


# =============================================================================
# Main Entry Point
# =============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    uvicorn.run(
        "src.api.routes:app",
        host=config.system.host,
        port=config.system.port,
        reload=config.system.debug
    )
