"""
Friday Insights Engine - Delivery Channels

Abstract base class and implementations for delivering insights,
alerts, and reports through various channels (Telegram, Email, Slack, etc.)
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.awareness.models import Insight

logger = logging.getLogger(__name__)


class DeliveryChannel(ABC):
    """
    Abstract base class for delivery channels.
    
    Delivery channels are responsible for sending insights, alerts,
    and reports to external services (Telegram, email, Slack, etc.)
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize channel.
        
        Args:
            name: Channel name (e.g., "telegram", "email")
            config: Channel-specific configuration
        """
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)
    
    @abstractmethod
    async def send_insight(self, insight: Insight) -> bool:
        """Send an insight through this channel.
        
        Args:
            insight: The insight to send
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def send_alert(self, message: str, level: str = "info") -> bool:
        """Send an alert through this channel.
        
        Args:
            message: Alert message
            level: Alert level (info, warning, critical)
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def send_report(self, report_text: str, report_type: str) -> bool:
        """Send a scheduled report through this channel.
        
        Args:
            report_text: Formatted report content
            report_type: Report type (morning, evening, weekly, etc.)
            
        Returns:
            True if sent successfully
        """
        pass
    
    def send_insight_sync(self, insight: Insight) -> bool:
        """Synchronous version of send_insight.
        
        Default implementation that can be overridden.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_insight(insight))
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.send_insight(insight))
    
    def send_alert_sync(self, message: str, level: str = "info") -> bool:
        """Synchronous version of send_alert.
        
        Default implementation that can be overridden.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_alert(message, level))
        except RuntimeError:
            return asyncio.run(self.send_alert(message, level))
    
    def send_report_sync(self, report_text: str, report_type: str) -> bool:
        """Synchronous version of send_report.
        
        Default implementation that can be overridden.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_report(report_text, report_type))
        except RuntimeError:
            return asyncio.run(self.send_report(report_text, report_type))
    
    def test_connection(self) -> bool:
        """Test if the channel is properly configured and reachable.
        
        Returns:
            True if connection test succeeds
        """
        return True


class ChannelRegistry:
    """Registry for delivery channels."""
    
    def __init__(self):
        self._channels: Dict[str, DeliveryChannel] = {}
    
    def register(self, channel: DeliveryChannel) -> None:
        """Register a delivery channel.
        
        Args:
            channel: The channel to register
        """
        self._channels[channel.name] = channel
        logger.info(f"Registered delivery channel: {channel.name} (enabled={channel.enabled})")
    
    def get(self, name: str) -> Optional[DeliveryChannel]:
        """Get a channel by name.
        
        Args:
            name: Channel name
            
        Returns:
            The channel or None if not found
        """
        return self._channels.get(name)
    
    def get_enabled_channels(self) -> list[DeliveryChannel]:
        """Get all enabled channels.
        
        Returns:
            List of enabled channels
        """
        return [ch for ch in self._channels.values() if ch.enabled]
    
    def list_channels(self) -> list[str]:
        """List all registered channel names.
        
        Returns:
            List of channel names
        """
        return list(self._channels.keys())


# Global registry instance
_registry = ChannelRegistry()


def get_channel_registry() -> ChannelRegistry:
    """Get the global channel registry."""
    return _registry
