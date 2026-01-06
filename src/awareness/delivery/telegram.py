"""
Friday Insights Engine - Telegram Channel

Delivers insights, alerts, and reports via Telegram.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Set, Dict, Any

# Add parent directory to path to import settings
_parent_dir = Path(__file__).parent.parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings

from src.awareness.models import Insight, Priority
from src.awareness.delivery.channels import DeliveryChannel

logger = logging.getLogger(__name__)


class TelegramChannel(DeliveryChannel):
    """
    Telegram delivery channel.
    
    Sends messages directly to Telegram using the Bot API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Telegram channel.
        
        Args:
            config: Configuration dict with:
                - enabled: Whether channel is enabled (default: True)
                - bot_token: Telegram bot token (or from TELEGRAM_BOT_TOKEN env)
                - chat_ids: List of chat IDs to send to (or from TELEGRAM_USER_ID env)
        """
        super().__init__("telegram", config)
        
        # Get bot token
        self.bot_token = config.get("bot_token") or settings.TELEGRAM_BOT_TOKEN
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram channel will be disabled")
            self.enabled = False
        
        # Parse chat IDs
        chat_ids_config = config.get("chat_ids", [])
        if chat_ids_config:
            # From config
            self.chat_ids = set(chat_ids_config)
        else:
            # From env var
            user_id_str = settings.TELEGRAM_USER_ID
            if user_id_str:
                try:
                    self.chat_ids = {int(uid.strip()) for uid in user_id_str.split(",") if uid.strip()}
                except ValueError:
                    logger.warning("Invalid TELEGRAM_USER_ID format")
                    self.chat_ids = set()
            else:
                self.chat_ids = set()
        
        if not self.chat_ids:
            logger.warning("No Telegram chat IDs configured, channel will be disabled")
            self.enabled = False
        
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        
        logger.info(f"Telegram channel initialized: enabled={self.enabled}, {len(self.chat_ids)} chat(s)")
    
    async def send_insight(self, insight: Insight) -> bool:
        """Send an insight to Telegram.
        
        Args:
            insight: The insight to send
            
        Returns:
            True if sent successfully to all chats
        """
        if not self.enabled:
            logger.debug("Telegram channel disabled, skipping insight")
            return False
        
        import httpx
        
        # Format the message
        message = self._format_insight(insight)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                all_success = True
                for chat_id in self.chat_ids:
                    response = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": message,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Sent insight to Telegram chat {chat_id}: {insight.title}")
                    else:
                        logger.error(f"Failed to send insight to chat {chat_id}: {response.status_code}")
                        all_success = False
                
                return all_success
                    
        except Exception as e:
            logger.error(f"Error sending insight to Telegram: {e}")
            return False
    
    async def send_alert(self, message: str, level: str = "info") -> bool:
        """Send an alert to Telegram.
        
        Args:
            message: Alert message
            level: Alert level (info, warning, critical)
            
        Returns:
            True if sent successfully to all chats
        """
        if not self.enabled:
            logger.debug("Telegram channel disabled, skipping alert")
            return False
        
        import httpx
        
        # Add emoji based on level
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
        }.get(level, "•")
        
        formatted_message = f"{emoji} {message}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                all_success = True
                for chat_id in self.chat_ids:
                    response = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": formatted_message,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Sent alert to Telegram chat {chat_id}")
                    else:
                        logger.error(f"Failed to send alert to chat {chat_id}: {response.status_code}")
                        all_success = False
                
                return all_success
                    
        except Exception as e:
            logger.error(f"Error sending alert to Telegram: {e}")
            return False
    
    async def send_report(self, report_text: str, report_type: str) -> bool:
        """Send a scheduled report to Telegram.
        
        Args:
            report_text: Formatted report content
            report_type: Report type (morning, evening, weekly, etc.)
            
        Returns:
            True if sent successfully to all chats
        """
        if not self.enabled:
            logger.debug("Telegram channel disabled, skipping report")
            return False
        
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                all_success = True
                for chat_id in self.chat_ids:
                    response = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": report_text,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Sent {report_type} report to Telegram chat {chat_id}")
                    else:
                        logger.error(f"Failed to send report to chat {chat_id}: {response.status_code}")
                        all_success = False
                
                return all_success
                    
        except Exception as e:
            logger.error(f"Error sending report to Telegram: {e}")
            return False
    
    def send_insight_sync(self, insight: Insight) -> bool:
        """Synchronous version of send_insight.
        
        Returns:
            True if sent successfully, False otherwise
        """
        message_id = self.send_insight_sync_with_id(insight)
        return message_id is not None
    
    def send_insight_sync_with_id(self, insight: Insight) -> Optional[int]:
        """Synchronous version of send_insight that returns message_id.
        
        Returns:
            Message ID if sent successfully, None otherwise
        """
        if not self.enabled:
            return None
        
        import httpx
        
        message = self._format_insight(insight)
        
        try:
            with httpx.Client(timeout=10.0) as client:
                message_id = None
                for chat_id in self.chat_ids:
                    response = client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": message,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        message_id = result.get("result", {}).get("message_id")
                        logger.info(f"Sent insight to Telegram chat {chat_id}: {insight.title} (msg_id={message_id})")
                    else:
                        logger.error(f"Failed to send insight to chat {chat_id}: {response.status_code}")
                        return None
                
                return message_id  # Return message_id from last chat (or first if only one)
                    
        except Exception as e:
            logger.error(f"Error sending insight to Telegram: {e}")
            return None
    
    def send_alert_sync(self, message: str, level: str = "info") -> bool:
        """Synchronous version of send_alert."""
        if not self.enabled:
            return False
        
        import httpx
        
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
        }.get(level, "•")
        
        formatted_message = f"{emoji} {message}"
        
        try:
            with httpx.Client(timeout=10.0) as client:
                all_success = True
                for chat_id in self.chat_ids:
                    response = client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": formatted_message,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Sent alert to Telegram chat {chat_id}")
                    else:
                        logger.error(f"Failed to send alert to chat {chat_id}: {response.status_code}")
                        all_success = False
                
                return all_success
                    
        except Exception as e:
            logger.error(f"Error sending alert to Telegram: {e}")
            return False
    
    def send_report_sync(self, report_text: str, report_type: str) -> bool:
        """Synchronous version of send_report."""
        if not self.enabled:
            return False
        
        import httpx
        
        try:
            with httpx.Client(timeout=10.0) as client:
                all_success = True
                for chat_id in self.chat_ids:
                    response = client.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": report_text,
                            "parse_mode": "Markdown"
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Sent {report_type} report to Telegram chat {chat_id}")
                    else:
                        logger.error(f"Failed to send report to chat {chat_id}: {response.status_code}")
                        all_success = False
                
                return all_success
                    
        except Exception as e:
            logger.error(f"Error sending report to Telegram: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Telegram connection by calling getMe API.
        
        Returns:
            True if connection test succeeds
        """
        if not self.enabled:
            return False
        
        import httpx
        
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.api_base}/getMe")
                if response.status_code == 200:
                    bot_info = response.json()
                    logger.info(f"Telegram connection OK: @{bot_info['result']['username']}")
                    return True
                else:
                    logger.error(f"Telegram connection failed: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False
    
    def _format_insight(self, insight: Insight) -> str:
        """Format an insight for Telegram.
        
        Returns clean, concise message with Markdown formatting.
        """
        # Priority emoji
        emoji = {
            Priority.URGENT: "🚨",
            Priority.HIGH: "⚠️",
            Priority.MEDIUM: "📊",
            Priority.LOW: "ℹ️",
        }.get(insight.priority, "•")
        
        # Build concise message
        if len(insight.message) < 60 and "\n" not in insight.message:
            return f"{emoji} {insight.title}: {insight.message}"
        else:
            return f"{emoji} {insight.title}\n{insight.message}"


# Backward compatibility alias
TelegramSender = TelegramChannel
