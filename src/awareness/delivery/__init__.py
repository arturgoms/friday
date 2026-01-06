"""
Friday Insights Engine - Delivery Layer

Handles sending insights to various channels.
"""

from src.awareness.delivery.channels import DeliveryChannel, ChannelRegistry, get_channel_registry
from src.awareness.delivery.loader import initialize_channels, load_channels_config
from src.awareness.delivery.manager import DeliveryManager
from src.awareness.delivery.telegram import TelegramChannel, TelegramSender

__all__ = [
    "DeliveryChannel",
    "ChannelRegistry",
    "get_channel_registry",
    "initialize_channels",
    "load_channels_config",
    "DeliveryManager",
    "TelegramChannel",
    "TelegramSender",  # Backward compatibility
]
