"""
Friday AI - Notification System
Send alerts and notifications via Telegram
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")

class FridayNotifier:
    """Send notifications via Telegram"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.user_id = TELEGRAM_USER_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, message: str, parse_mode: str = "Markdown", disable_web_page_preview: bool = True):
        """Send a message to the authorized user"""
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.user_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_web_page_preview
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return False
    
    def send_alert(self, title: str, message: str, severity: str = "info"):
        """Send an alert with severity level"""
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
            "critical": "🚨"
        }
        
        emoji = emoji_map.get(severity, "📢")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        formatted_message = (
            f"{emoji} *{title}*\n"
            f"{message}\n\n"
            f"🕐 {timestamp}"
        )
        
        return self.send_message(formatted_message)
    
    def send_system_status(self, status_dict: dict):
        """Send system status report"""
        message = "📊 *System Status Report*\n\n"
        
        for key, value in status_dict.items():
            if isinstance(value, bool):
                icon = "✅" if value else "❌"
                message += f"{icon} {key}\n"
            else:
                message += f"• {key}: `{value}`\n"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message += f"\n🕐 {timestamp}"
        
        return self.send_message(message)

# Convenience function for quick notifications
def notify(message: str, severity: str = "info"):
    """Quick notification function"""
    notifier = FridayNotifier()
    return notifier.send_alert("Homelab Alert", message, severity)

if __name__ == "__main__":
    # Test notification
    notifier = FridayNotifier()
    notifier.send_alert("Test Alert", "Notification system is working!", "success")
