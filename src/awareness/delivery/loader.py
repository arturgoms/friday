"""
Friday Insights Engine - Channel Loader

Loads and initializes delivery channels from configuration.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path to import settings
_parent_dir = Path(__file__).parent.parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings
from src.awareness.delivery.channels import DeliveryChannel, get_channel_registry

logger = logging.getLogger(__name__)


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in configuration values.
    
    Supports ${VAR_NAME} syntax.
    
    Args:
        value: Configuration value (can be str, dict, list, etc.)
        
    Returns:
        Value with environment variables expanded
    """
    if isinstance(value, str):
        # Expand ${VAR_NAME} patterns
        if "${" in value:
            import re
            def replace_env(match):
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))
            return re.sub(r'\$\{([^}]+)\}', replace_env, value)
        return value
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    else:
        return value


def load_channels_config(config_path: str | None = None) -> Dict[str, Any]:
    """Load delivery channels configuration from settings.
    
    Args:
        config_path: Ignored - kept for backwards compatibility
        
    Returns:
        Configuration dict
    """
    try:
        # Load from settings.DELIVERY_CHANNELS
        config = settings.DELIVERY_CHANNELS
        
        # Expand environment variables
        config = expand_env_vars(config)
        
        logger.info("Loaded delivery channels config from settings")
        return config
    
    except Exception as e:
        logger.error(f"Failed to load delivery channels config: {e}")
        return {"channels": [], "routing": {}}


def create_channel(channel_type: str, config: Dict[str, Any]) -> DeliveryChannel:
    """Create a delivery channel instance.
    
    Args:
        channel_type: Channel type (telegram, email, slack, etc.)
        config: Channel configuration
        
    Returns:
        Channel instance
        
    Raises:
        ValueError: If channel type is not supported
    """
    if channel_type == "telegram":
        from src.awareness.delivery.telegram import TelegramChannel
        return TelegramChannel(config)
    
    elif channel_type == "email":
        # TODO: Implement email channel
        logger.warning("Email channel not yet implemented")
        raise ValueError(f"Channel type not implemented: {channel_type}")
    
    elif channel_type == "slack":
        # TODO: Implement Slack channel
        logger.warning("Slack channel not yet implemented")
        raise ValueError(f"Channel type not implemented: {channel_type}")
    
    elif channel_type == "discord":
        # TODO: Implement Discord channel
        logger.warning("Discord channel not yet implemented")
        raise ValueError(f"Channel type not implemented: {channel_type}")
    
    elif channel_type == "webhook":
        # TODO: Implement generic webhook channel
        logger.warning("Webhook channel not yet implemented")
        raise ValueError(f"Channel type not implemented: {channel_type}")
    
    else:
        raise ValueError(f"Unknown channel type: {channel_type}")


def initialize_channels(config: Dict[str, Any] | None = None) -> int:
    """Initialize delivery channels from configuration.
    
    Args:
        config: Configuration dict. If None, loads from file.
        
    Returns:
        Number of channels initialized
    """
    if config is None:
        config = load_channels_config()
    
    registry = get_channel_registry()
    channels_data = config.get("channels", [])
    
    initialized = 0
    for channel_data in channels_data:
        channel_type = channel_data.get("type")
        enabled = channel_data.get("enabled", True)
        channel_config = channel_data.get("config", {})
        
        # Add enabled flag to config
        channel_config["enabled"] = enabled
        
        try:
            channel = create_channel(channel_type, channel_config)
            registry.register(channel)
            initialized += 1
            
            if enabled:
                logger.info(f"Initialized {channel_type} channel")
            else:
                logger.info(f"Registered {channel_type} channel (disabled)")
                
        except ValueError as e:
            logger.warning(f"Skipping channel: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize {channel_type} channel: {e}")
    
    return initialized


def get_routing_config() -> Dict[str, Any]:
    """Get routing configuration for insights/alerts/reports.
    
    Returns:
        Routing configuration dict
    """
    config = load_channels_config()
    return config.get("routing", {})
