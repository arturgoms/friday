"""
Channel Manager

Manages multiple communication channels and routes messages between them.
Provides a unified interface for sending messages through different channels.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from src.interfaces.base import (
    Channel, Message, DeliveryResult, MessagePriority,
    ChannelNotAvailableError, MessageDeliveryError
)

logger = logging.getLogger(__name__)


class ChannelManager:
    """
    Manages multiple communication channels.
    
    Handles:
    - Registering and managing multiple channels
    - Routing messages to appropriate channels
    - Fallback to alternative channels if primary fails
    - Broadcasting messages to multiple channels
    """
    
    def __init__(self):
        self._channels: Dict[str, Channel] = {}
        self._default_channel: Optional[str] = None
        self._fallback_order: List[str] = []
    
    def register_channel(self, channel: Channel, is_default: bool = False):
        """
        Register a communication channel.
        
        Args:
            channel: Channel instance to register
            is_default: If True, this becomes the default channel for sending
        """
        self._channels[channel.channel_id] = channel
        logger.info(f"Registered channel: {channel.channel_id} (type: {channel.__class__.__name__})")
        
        if is_default:
            self._default_channel = channel.channel_id
            logger.info(f"Set default channel: {channel.channel_id}")
    
    def unregister_channel(self, channel_id: str):
        """Remove a channel from the manager."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            logger.info(f"Unregistered channel: {channel_id}")
            
            # Update default if needed
            if self._default_channel == channel_id:
                self._default_channel = None
    
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Get a specific channel by ID."""
        return self._channels.get(channel_id)
    
    def list_channels(self) -> List[str]:
        """Get list of all registered channel IDs."""
        return list(self._channels.keys())
    
    def set_fallback_order(self, channel_ids: List[str]):
        """
        Set the order of channels to try if primary channel fails.
        
        Args:
            channel_ids: List of channel IDs in priority order
        """
        # Validate all channels exist
        for channel_id in channel_ids:
            if channel_id not in self._channels:
                raise ValueError(f"Channel not registered: {channel_id}")
        
        self._fallback_order = channel_ids
        logger.info(f"Set fallback order: {' -> '.join(channel_ids)}")
    
    async def send(
        self,
        message: Message,
        channel_id: Optional[str] = None,
        use_fallback: bool = True
    ) -> DeliveryResult:
        """
        Send a message through a channel.
        
        Args:
            message: Message to send
            channel_id: Specific channel to use (None = use default)
            use_fallback: If True, try fallback channels on failure
            
        Returns:
            DeliveryResult from the successful channel
            
        Raises:
            ChannelNotAvailableError: If no channels are available
            MessageDeliveryError: If message delivery fails on all channels
        """
        # Determine which channel(s) to try
        channels_to_try = []
        
        if channel_id:
            # Specific channel requested
            channels_to_try.append(channel_id)
            if use_fallback:
                channels_to_try.extend(self._fallback_order)
        elif self._default_channel:
            # Use default channel
            channels_to_try.append(self._default_channel)
            if use_fallback:
                channels_to_try.extend(self._fallback_order)
        else:
            # No default set, try all available
            channels_to_try = list(self._channels.keys())
        
        # Remove duplicates while preserving order
        channels_to_try = list(dict.fromkeys(channels_to_try))
        
        # Try each channel
        last_error = None
        for cid in channels_to_try:
            channel = self._channels.get(cid)
            
            if not channel:
                logger.warning(f"Channel not found: {cid}")
                continue
            
            if not channel.is_available():
                logger.warning(f"Channel not available: {cid}")
                continue
            
            try:
                logger.info(f"Attempting to send via {cid}")
                result = await channel.send(message)
                
                if result.success:
                    logger.info(f"Message sent successfully via {cid}: {result.message_id}")
                    return result
                else:
                    logger.warning(f"Failed to send via {cid}: {result.error}")
                    last_error = result.error
                    
            except Exception as e:
                logger.error(f"Error sending via {cid}: {e}")
                last_error = str(e)
        
        # All channels failed
        error_msg = f"Failed to deliver message on all channels. Last error: {last_error}"
        logger.error(error_msg)
        
        return DeliveryResult(
            success=False,
            error=error_msg,
            timestamp=datetime.now()
        )
    
    async def broadcast(
        self,
        message: Message,
        channel_ids: Optional[List[str]] = None
    ) -> Dict[str, DeliveryResult]:
        """
        Send a message through multiple channels.
        
        Args:
            message: Message to broadcast
            channel_ids: List of channels to use (None = all available)
            
        Returns:
            Dict mapping channel_id to DeliveryResult
        """
        if channel_ids is None:
            channel_ids = list(self._channels.keys())
        
        results = {}
        
        for channel_id in channel_ids:
            channel = self._channels.get(channel_id)
            
            if not channel or not channel.is_available():
                results[channel_id] = DeliveryResult(
                    success=False,
                    error=f"Channel not available: {channel_id}"
                )
                continue
            
            try:
                result = await channel.send(message)
                results[channel_id] = result
                
            except Exception as e:
                logger.error(f"Error broadcasting to {channel_id}: {e}")
                results[channel_id] = DeliveryResult(
                    success=False,
                    error=str(e)
                )
        
        return results
    
    async def start_all(self):
        """Start all registered channels."""
        for channel_id, channel in self._channels.items():
            try:
                logger.info(f"Starting channel: {channel_id}")
                await channel.start()
            except Exception as e:
                logger.error(f"Error starting channel {channel_id}: {e}")
    
    async def stop_all(self):
        """Stop all registered channels."""
        for channel_id, channel in self._channels.items():
            try:
                logger.info(f"Stopping channel: {channel_id}")
                await channel.stop()
            except Exception as e:
                logger.error(f"Error stopping channel {channel_id}: {e}")
    
    def get_available_channels(self) -> List[str]:
        """Get list of currently available channel IDs."""
        return [
            channel_id
            for channel_id, channel in self._channels.items()
            if channel.is_available()
        ]
    
    def __repr__(self):
        available = len(self.get_available_channels())
        total = len(self._channels)
        return f"<ChannelManager channels={total} available={available} default={self._default_channel}>"
