"""Chat Orchestrator - Coordinates intent routing and handler dispatch.

This is the main entry point for the chat service. It:
1. Routes user messages through the IntentRouter
2. Dispatches to appropriate IntentHandlers
3. Manages conversation history
4. Aggregates results for final LLM response (when needed)
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Type

from app.core.config import settings
from app.core.logging import logger
from app.services.intent.router import intent_router
from app.services.llm import llm_service
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse


class HandlerRegistry:
    """Registry for intent handlers.
    
    Handlers register themselves with the actions they can handle.
    The orchestrator looks up handlers by action name.
    """
    
    def __init__(self):
        self._handlers: Dict[str, IntentHandler] = {}
        self._handler_instances: Dict[Type[IntentHandler], IntentHandler] = {}
    
    def register(self, handler_class: Type[IntentHandler]) -> None:
        """Register a handler class for its declared actions."""
        # Create single instance per handler class
        if handler_class not in self._handler_instances:
            self._handler_instances[handler_class] = handler_class()
        
        handler = self._handler_instances[handler_class]
        
        for action in handler.actions:
            if action in self._handlers:
                logger.warning(
                    f"Action '{action}' already registered to {self._handlers[action].__class__.__name__}, "
                    f"overwriting with {handler_class.__name__}"
                )
            self._handlers[action] = handler
            logger.debug(f"Registered handler {handler_class.__name__} for action '{action}'")
    
    def get_handler(self, action: str) -> Optional[IntentHandler]:
        """Get the handler for a given action."""
        return self._handlers.get(action)
    
    def list_handlers(self) -> Dict[str, str]:
        """List all registered handlers and their actions."""
        return {action: handler.__class__.__name__ for action, handler in self._handlers.items()}
    
    def clear(self) -> None:
        """Clear all registered handlers (useful for testing)."""
        self._handlers.clear()
        self._handler_instances.clear()


# Global handler registry
handler_registry = HandlerRegistry()


class ChatOrchestrator:
    """Orchestrates the chat flow: intent routing -> handler dispatch -> response.
    
    The orchestrator is the main interface for the chat service. It:
    - Maintains conversation history per session
    - Routes messages through the intent router
    - Dispatches to registered handlers
    - Falls back to LLM for unhandled actions or when handlers need LLM synthesis
    """
    
    def __init__(self):
        """Initialize the chat orchestrator."""
        self.conversation_history: Dict[str, List[dict]] = {}
        self._personality: Optional[str] = None
        
        # Register all handlers
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register all available intent handlers."""
        # Import handlers here to avoid circular imports
        
        # Memory handlers
        from app.services.chat.handlers.memory import (
            MemorySaveHandler,
            MemoryAmbiguousHandler,
            MemoryListHandler,
            MemoryDeleteHandler,
        )
        handler_registry.register(MemorySaveHandler)
        handler_registry.register(MemoryAmbiguousHandler)
        handler_registry.register(MemoryListHandler)
        handler_registry.register(MemoryDeleteHandler)
        
        # Reminder handlers
        from app.services.chat.handlers.reminder import (
            ReminderCreateHandler,
            ReminderQueryHandler,
            ReminderDeleteHandler,
        )
        handler_registry.register(ReminderCreateHandler)
        handler_registry.register(ReminderQueryHandler)
        handler_registry.register(ReminderDeleteHandler)
        
        # Note handlers
        from app.services.chat.handlers.note import (
            NoteCreateHandler,
            NoteUpdateHandler,
            NoteSearchHandler,
            NoteGetHandler,
        )
        handler_registry.register(NoteCreateHandler)
        handler_registry.register(NoteUpdateHandler)
        handler_registry.register(NoteSearchHandler)
        handler_registry.register(NoteGetHandler)
        
        # Calendar handlers
        from app.services.chat.handlers.calendar import (
            CalendarQueryHandler,
            CalendarCreateHandler,
            CalendarFindFreeHandler,
            TimeQueryHandler,
        )
        handler_registry.register(CalendarQueryHandler)
        handler_registry.register(CalendarCreateHandler)
        handler_registry.register(CalendarFindFreeHandler)
        handler_registry.register(TimeQueryHandler)
        
        # Task handlers
        from app.services.chat.handlers.task import (
            TaskCreateHandler,
            TaskListHandler,
            TaskCompleteHandler,
            TaskQueryHandler,
        )
        handler_registry.register(TaskCreateHandler)
        handler_registry.register(TaskListHandler)
        handler_registry.register(TaskCompleteHandler)
        handler_registry.register(TaskQueryHandler)
        
        # Alert handlers
        from app.services.chat.handlers.alert import (
            AlertCreateHandler,
            AlertListHandler,
            AlertDeleteHandler,
        )
        handler_registry.register(AlertCreateHandler)
        handler_registry.register(AlertListHandler)
        handler_registry.register(AlertDeleteHandler)
        
        # Report handlers
        from app.services.chat.handlers.report import (
            MorningReportHandler,
            EveningReportHandler,
            VaultHealthHandler,
            BodyHealthCheckHandler,
            BudgetStatusHandler,
            BudgetResetHandler,
        )
        handler_registry.register(MorningReportHandler)
        handler_registry.register(EveningReportHandler)
        handler_registry.register(VaultHealthHandler)
        handler_registry.register(BodyHealthCheckHandler)
        handler_registry.register(BudgetStatusHandler)
        handler_registry.register(BudgetResetHandler)
        
        # Web search handler
        from app.services.chat.handlers.web_search import WebSearchHandler
        handler_registry.register(WebSearchHandler)
        
        # Health handler
        from app.services.chat.handlers.health import HealthQueryHandler
        handler_registry.register(HealthQueryHandler)
        
        # General handler (RAG, memory, greetings, general conversation)
        from app.services.chat.handlers.general import GeneralHandler
        handler_registry.register(GeneralHandler)
        
        logger.info(f"Registered {len(handler_registry.list_handlers())} handlers")
    
    @property
    def personality(self) -> str:
        """Lazy load Friday's personality from the About file."""
        if self._personality is None:
            self._personality = self._load_personality()
        return self._personality
    
    def _load_personality(self) -> str:
        """Load Friday's personality from 5.0 About/Who is Friday.md"""
        try:
            personality_path = settings.about_path / "Who is Friday.md"
            if personality_path.exists():
                content = personality_path.read_text(encoding="utf-8")
                # Remove frontmatter (between --- markers)
                if content.startswith("---"):
                    end_frontmatter = content.find("---", 3)
                    if end_frontmatter != -1:
                        content = content[end_frontmatter + 3:].strip()
                logger.info(f"Loaded Friday personality from {personality_path}")
                return content
            else:
                logger.warning(f"Personality file not found: {personality_path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load personality: {e}")
            return ""
    
    def reload_personality(self) -> str:
        """Force reload personality from file (useful after edits)."""
        self._personality = None
        return self.personality
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get or create conversation session."""
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        return session_id
    
    def get_history(self, session_id: str) -> List[dict]:
        """Get conversation history for session."""
        return self.conversation_history.get(session_id, [])
    
    def update_history(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Update conversation history."""
        history = self.conversation_history.get(session_id, [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        
        # Trim history to max length
        max_messages = settings.max_conversation_history * 2
        if len(history) > max_messages:
            history[:] = history[-max_messages:]
        
        self.conversation_history[session_id] = history
    
    def get_last_user_message(self, session_id: str) -> str:
        """Get the last user message from history (for context in follow-ups)."""
        history = self.get_history(session_id)
        for msg in reversed(history):
            if msg.get('role') == 'user':
                return msg.get('content', '')
        return ""
    
    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        use_rag: bool = True,
        use_web: bool = False,
        use_memory: bool = True,
        save_memory: bool = True,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Handle a chat message.
        
        This is the main entry point for the chat service. It:
        1. Routes the message through the intent router
        2. Dispatches to the appropriate handler(s)
        3. Returns the response
        
        Args:
            message: The user's message
            session_id: Optional session ID for conversation continuity
            use_rag: Whether to use RAG for context (passed to handlers)
            use_web: Whether to use web search (passed to handlers)
            use_memory: Whether to use memory (passed to handlers)
            save_memory: Whether to save memories from this conversation
            stream: Whether to stream the response (not yet implemented)
        
        Returns:
            Dict with response data including:
            - session_id: The session ID
            - message: The original message
            - answer: The response text
            - used_rag, used_web, used_memory, used_health: Flags
            - obsidian_chunks, memory_items: Retrieved context
            - extracted_memory: Any memory extracted from the conversation
        """
        session_id = self.get_or_create_session(session_id)
        history = self.get_history(session_id)
        last_user_msg = self.get_last_user_message(session_id)
        
        # Stage 1: Intent Routing
        logger.info(f"[Orchestrator] Routing intent for: {message[:50]}...")
        intent = intent_router.route(message, last_message=last_user_msg)
        action = intent.get('action', 'general')
        
        logger.info(f"[Orchestrator] Intent: {action}")
        
        # Build context for handlers
        context = ChatContext(
            session_id=session_id,
            message=message,
            intent=intent,
            history=history,
            last_user_message=last_user_msg,
        )
        
        # Stage 2: Handler Dispatch
        handler = handler_registry.get_handler(action)
        
        if handler:
            logger.info(f"[Orchestrator] Dispatching to handler: {handler.__class__.__name__}")
            try:
                response = handler.handle(context)
                
                # If handler returned a final response, return it
                if response.is_final:
                    # Update history with the response
                    self.update_history(session_id, message, response.answer)
                    # Ensure intent is included in response
                    response.intent = intent
                    return response.to_dict()
                
                # Handler needs LLM to generate final response
                # Use the context_for_llm provided by the handler
                logger.info(f"[Orchestrator] Handler needs LLM synthesis")
                answer = self._generate_llm_response(
                    context=context,
                    handler_context=response.context_for_llm,
                    system_prompt_override=response.system_prompt_override,
                )
                
                # Update history
                self.update_history(session_id, message, answer)
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "intent": intent,
                    "used_rag": response.used_rag,
                    "used_web": response.used_web,
                    "used_memory": response.used_memory,
                    "used_health": response.used_health,
                    "obsidian_chunks": response.obsidian_chunks,
                    "memory_items": response.memory_items,
                    "extracted_memory": response.extracted_memory,
                }
                
            except Exception as e:
                logger.error(f"Handler error: {e}", exc_info=True)
                # Return error response instead of falling back
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": f"Something went wrong: {str(e)}",
                    "intent": intent,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # No handler found - this shouldn't happen with full handler coverage
        logger.error(f"[Orchestrator] No handler for action '{action}'")
        return {
            "session_id": session_id,
            "message": message,
            "answer": f"I don't know how to handle that request (action: {action})",
            "intent": intent,
            "used_rag": False,
            "used_web": False,
            "used_memory": False,
            "used_health": False,
            "obsidian_chunks": [],
            "memory_items": [],
            "extracted_memory": None,
        }
    
    def _generate_llm_response(
        self,
        context: ChatContext,
        handler_context: str,
        system_prompt_override: Optional[str] = None,
    ) -> str:
        """Generate an LLM response using handler-provided context."""
        system_prompt = system_prompt_override or self._generate_system_prompt(context.action)
        
        if handler_context:
            user_content = f"User question:\n{context.message}\n\nContext:\n{handler_context}"
        else:
            user_content = context.message
        
        return llm_service.call(
            system_prompt=system_prompt,
            user_content=user_content,
            history=context.history,
            stream=False,
        )
    
    def _generate_system_prompt(self, action: str) -> str:
        """Generate a system prompt based on action type."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        
        base = f"Today is {today}, {current_time}.\n\n"
        
        if self.personality:
            base += f"{self.personality}\n\n"
        else:
            base += "You are Friday, a personal AI assistant for Artur Gomes.\n\n"
        
        base += (
            f"CRITICAL: The user speaking to you is Artur Gomes ({settings.authorized_user}). "
            f"All notes in the vault were written by Artur - they are HIS ideas, projects, and knowledge. "
            f"Do NOT confuse Artur with other people mentioned in his notes."
        )
        
        return f"{base}\n\nBe helpful and concise. Use Markdown formatting."
    
# Singleton instance
chat_orchestrator = ChatOrchestrator()
