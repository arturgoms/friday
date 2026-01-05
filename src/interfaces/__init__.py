"""
Communication Interfaces

Provides a unified system for managing different communication channels
(Telegram, Email, Slack, etc.) with a consistent API.
"""

from src.interfaces.base import (
    Channel,
    Message,
    MessageType,
    MessagePriority,
    DeliveryResult,
    ChannelError,
    ChannelNotAvailableError,
    MessageDeliveryError
)
from src.interfaces.manager import ChannelManager

__all__ = [
    'Channel',
    'Message',
    'MessageType',
    'MessagePriority',
    'DeliveryResult',
    'ChannelError',
    'ChannelNotAvailableError',
    'MessageDeliveryError',
    'ChannelManager',
]
