"""
Friday Insights Engine - Telegram Sender

Sends insights and reports to Telegram.
"""

import os
import logging
from typing import Optional
from datetime import datetime

from src.insights.models import Insight, Priority, Category

logger = logging.getLogger(__name__)


class TelegramSender:
    """
    Sends messages to Telegram via the Friday Core API.
    
    Uses the existing /alert endpoint which handles
    Telegram bot integration.
    """
    
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize sender.
        
        Args:
            api_url: URL of Friday Core API. Defaults to localhost:8080
            api_key: API key for authentication
        """
        self.api_url = api_url or os.getenv("FRIDAY_API_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("FRIDAY_API_KEY", "")
    
    async def send_insight(self, insight: Insight) -> bool:
        """Send an insight to Telegram.
        
        Args:
            insight: The insight to send
            
        Returns:
            True if sent successfully
        """
        import httpx
        
        # Format the message
        message = self._format_insight(insight)
        
        # Determine alert level for API
        level = self._priority_to_level(insight.priority)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/alert",
                    json={
                        "message": message,
                        "level": level,
                        "sensor": f"insights_{insight.category.value}",
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Sent insight to Telegram: {insight.title}")
                    return True
                else:
                    logger.error(f"Failed to send insight: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False
    
    async def send_report(self, report_text: str, report_type: str) -> bool:
        """Send a scheduled report to Telegram.
        
        Args:
            report_text: Formatted report content
            report_type: "morning", "evening", or "weekly"
            
        Returns:
            True if sent successfully
        """
        import httpx
        
        sensor_name = f"scheduled_{report_type}_report"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/alert",
                    json={
                        "message": report_text,
                        "level": "info",
                        "sensor": sensor_name,
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Sent {report_type} report to Telegram")
                    return True
                else:
                    logger.error(f"Failed to send report: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending report: {e}")
            return False
    
    def send_insight_sync(self, insight: Insight) -> bool:
        """Synchronous version of send_insight."""
        import httpx
        
        message = self._format_insight(insight)
        level = self._priority_to_level(insight.priority)
        
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.api_url}/alert",
                    headers=headers,
                    json={
                        "message": message,
                        "level": level,
                        "sensor": f"insights_{insight.category.value}",
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Sent insight to Telegram: {insight.title}")
                    return True
                else:
                    logger.error(f"Failed to send insight: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False
    
    def send_report_sync(self, report_text: str, report_type: str) -> bool:
        """Synchronous version of send_report."""
        import httpx
        
        sensor_name = f"scheduled_{report_type}_report"
        
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.api_url}/alert",
                    headers=headers,
                    json={
                        "message": report_text,
                        "level": "info",
                        "sensor": sensor_name,
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Sent {report_type} report to Telegram")
                    return True
                else:
                    logger.error(f"Failed to send report: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending report: {e}")
            return False
    
    def _format_insight(self, insight: Insight) -> str:
        """Format an insight for Telegram.
        
        Returns clean, concise message without excessive formatting.
        """
        # Priority emoji
        emoji = {
            Priority.URGENT: "🚨",
            Priority.HIGH: "⚠️",
            Priority.MEDIUM: "📊",
            Priority.LOW: "ℹ️",
        }.get(insight.priority, "•")
        
        # Build concise message: emoji + title + message on same/next line
        # If message is short, put on same line; otherwise new line
        if len(insight.message) < 60 and "\n" not in insight.message:
            return f"{emoji} {insight.title}: {insight.message}"
        else:
            return f"{emoji} {insight.title}\n{insight.message}"
    
    def _priority_to_level(self, priority: Priority) -> str:
        """Convert Priority to API alert level."""
        return {
            Priority.URGENT: "critical",
            Priority.HIGH: "warning",
            Priority.MEDIUM: "info",
            Priority.LOW: "info",
        }.get(priority, "info")
