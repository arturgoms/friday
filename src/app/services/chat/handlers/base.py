"""Base classes for chat intent handlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class ChatContext:
    """Context passed to intent handlers."""
    session_id: str
    message: str
    intent: Dict[str, Any]
    history: List[Dict[str, str]] = field(default_factory=list)
    last_user_message: str = ""
    
    # Extracted intent data
    @property
    def action(self) -> str:
        return self.intent.get('action', 'general')
    
    @property
    def tool(self) -> Optional[str]:
        return self.intent.get('tool')
    
    @property
    def use_rag(self) -> bool:
        return self.intent.get('use_rag', False)
    
    @property
    def use_memory(self) -> bool:
        return self.intent.get('use_memory', False)
    
    @property
    def reminder_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('reminder_data')
    
    @property
    def reminder_index(self) -> Optional[int]:
        return self.intent.get('reminder_index')
    
    @property
    def memory_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('memory_data')
    
    @property
    def note_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('note_data')
    
    @property
    def task_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('task_data')
    
    @property
    def alert_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('alert_data')
    
    @property
    def calendar_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('calendar_data')
    
    @property
    def free_time_data(self) -> Optional[Dict[str, Any]]:
        return self.intent.get('free_time_data')


@dataclass
class ChatResponse:
    """Standard response from intent handlers."""
    session_id: str
    message: str
    answer: str
    
    # Flags indicating what was used
    used_rag: bool = False
    used_web: bool = False
    used_memory: bool = False
    used_health: bool = False
    
    # Context that was retrieved
    obsidian_chunks: List[Dict] = field(default_factory=list)
    memory_items: List[Dict] = field(default_factory=list)
    
    # Memory that was extracted/saved
    extracted_memory: Optional[str] = None
    
    # Intent information for feedback tracking
    intent: Optional[Dict[str, Any]] = None
    
    # Whether to skip LLM response generation (handler already produced final answer)
    is_final: bool = True
    
    # Additional context for LLM if is_final=False
    context_for_llm: str = ""
    system_prompt_override: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "message": self.message,
            "answer": self.answer,
            "intent": self.intent,
            "used_rag": self.used_rag,
            "used_web": self.used_web,
            "used_memory": self.used_memory,
            "used_health": self.used_health,
            "obsidian_chunks": self.obsidian_chunks,
            "memory_items": self.memory_items,
            "extracted_memory": self.extracted_memory,
        }


class IntentHandler(ABC):
    """Abstract base class for intent handlers.
    
    Each handler is responsible for processing a specific intent type
    and returning a ChatResponse.
    """
    
    # List of action names this handler can process
    actions: List[str] = []
    
    @abstractmethod
    def handle(self, context: ChatContext) -> ChatResponse:
        """
        Handle the intent and return a response.
        
        Args:
            context: ChatContext with message, intent, and session info
            
        Returns:
            ChatResponse with the result
        """
        pass
    
    def can_handle(self, action: str) -> bool:
        """Check if this handler can process the given action."""
        return action in self.actions
    
    def _error_response(self, context: ChatContext, error_message: str) -> ChatResponse:
        """Create a standard error response."""
        return ChatResponse(
            session_id=context.session_id,
            message=context.message,
            answer=f"❌ {error_message}",
            is_final=True
        )
    
    def _success_response(
        self, 
        context: ChatContext, 
        answer: str,
        extracted_memory: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """Create a standard success response."""
        return ChatResponse(
            session_id=context.session_id,
            message=context.message,
            answer=answer,
            extracted_memory=extracted_memory,
            is_final=True,
            **kwargs
        )
