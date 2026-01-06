"""
Base classes for communication interfaces.

Provides abstract base classes for implementing different communication channels
(Telegram, Email, Slack, etc.) with a consistent API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent/received."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    COMMAND = "command"


class MessagePriority(Enum):
    """Priority levels for messages."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """Represents a message in the system.
    
    This is a channel-agnostic representation that can be converted
    to/from any specific channel format (Telegram, Email, etc.).
    """
    # Core fields
    content: str
    type: MessageType = MessageType.TEXT
    priority: MessagePriority = MessagePriority.NORMAL
    
    # Metadata
    timestamp: Optional[datetime] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    channel: Optional[str] = None
    
    # Optional fields for rich content
    attachments: List[str] = None  # URLs or file paths
    metadata: Dict[str, Any] = None
    
    # Reply/thread support
    reply_to: Optional[str] = None  # Message ID being replied to
    thread_id: Optional[str] = None  # Thread/conversation ID
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.attachments is None:
            self.attachments = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DeliveryResult:
    """Result of attempting to deliver a message."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class Channel(ABC):
    """
    Abstract base class for communication channels.
    
    All communication interfaces (Telegram, Email, Slack, etc.) should
    inherit from this class and implement its abstract methods.
    """
    
    def __init__(self, channel_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the channel.
        
        Args:
            channel_id: Unique identifier for this channel instance
            config: Channel-specific configuration
        """
        self.channel_id = channel_id
        self.config = config or {}
        self._message_handlers: List[Callable[[Message], None]] = []
        self._is_running = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def send(self, message: Message) -> DeliveryResult:
        """
        Send a message through this channel.
        
        Args:
            message: Message to send
            
        Returns:
            DeliveryResult indicating success/failure
        """
        pass
    
    @abstractmethod
    async def start(self):
        """
        Start the channel (begin listening for incoming messages).
        
        This should set up any necessary connections, webhooks, polling, etc.
        """
        pass
    
    @abstractmethod
    async def stop(self):
        """
        Stop the channel (stop listening for incoming messages).
        
        This should clean up connections and resources.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the channel is currently available/configured.
        
        Returns:
            True if the channel can be used, False otherwise
        """
        pass
    
    def register_handler(self, handler: Callable[[Message], None]):
        """
        Register a function to handle incoming messages.
        
        Args:
            handler: Function that takes a Message and processes it
        """
        self._message_handlers.append(handler)
        self.logger.info(f"Registered message handler: {handler.__name__}")
    
    def _handle_incoming_message(self, message: Message):
        """
        Process an incoming message by calling all registered handlers.
        
        Args:
            message: The incoming message to process
        """
        self.logger.info(f"Processing incoming message from {message.sender_id}")
        
        for handler in self._message_handlers:
            try:
                import asyncio
                import inspect
                
                # Check if handler is async or sync
                if inspect.iscoroutinefunction(handler):
                    # Create task for async handler
                    asyncio.create_task(handler(message))
                else:
                    # Call sync handler directly
                    handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler {handler.__name__}: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is currently running."""
        return self._is_running
    
    @abstractmethod
    def supports_message_type(self, message_type: MessageType) -> bool:
        """
        Check if this channel supports a specific message type.
        
        Args:
            message_type: Type of message to check
            
        Returns:
            True if supported, False otherwise
        """
        pass
    
    def get_reply_to_message_id(self, message: Message) -> Optional[str]:
        """
        Extract the reply-to message ID from an incoming message.
        
        This method allows each channel to implement its own logic for
        detecting if a message is a reply to another message. Useful for
        thread detection (e.g., journal entries replying to journal threads).
        
        Args:
            message: The incoming message to check
            
        Returns:
            The message ID being replied to, or None if not a reply
        """
        # Default implementation checks metadata
        if message.metadata:
            return message.metadata.get('reply_to_message_id')
        return None
    
    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.channel_id} running={self._is_running}>"


class ChannelError(Exception):
    """Base exception for channel-related errors."""
    pass


class ChannelNotAvailableError(ChannelError):
    """Raised when trying to use a channel that is not available."""
    pass


class MessageDeliveryError(ChannelError):
    """Raised when a message cannot be delivered."""
    pass
