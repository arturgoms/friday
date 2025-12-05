"""Chat service package.

This package provides the modular chat service with intent-based handlers.

The ChatOrchestrator coordinates:
1. Intent routing (via IntentRouter)
2. Handler dispatch (via HandlerRegistry)
3. Conversation management
4. Response aggregation

During migration, unhandled actions fall back to the legacy ChatService.
"""
from app.services.chat.orchestrator import ChatOrchestrator, chat_orchestrator, handler_registry
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse

# Singleton instance - use this for all chat operations
chat_service = chat_orchestrator

__all__ = [
    'ChatOrchestrator',
    'chat_orchestrator', 
    'chat_service',
    'handler_registry',
    'IntentHandler',
    'ChatContext', 
    'ChatResponse',
]
