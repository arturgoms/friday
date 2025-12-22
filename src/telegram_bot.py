"""
Friday 3.0 Telegram Bot

A lightweight Telegram interface for Friday. This bot is intentionally "dumb" -
it has no AI logic, just forwards messages to the friday-core API and renders responses.

Usage:
    python -m src.telegram_bot

Environment Variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token from @BotFather
    TELEGRAM_ALLOWED_USERS: Comma-separated list of allowed user IDs (optional)
    FRIDAY_API_URL: URL of friday-core API (default: http://localhost:8080)
"""

import asyncio
import logging
import os
import sys
from typing import Optional, Set

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)


# =============================================================================
# Configuration
# =============================================================================

def get_config():
    """Load configuration from environment."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    # Parse allowed user ID (single user or comma-separated)
    user_id_str = os.getenv("TELEGRAM_USER_ID", "")
    allowed_users: Set[int] = set()
    if user_id_str:
        try:
            # Support both single ID and comma-separated list
            allowed_users = {int(uid.strip()) for uid in user_id_str.split(",") if uid.strip()}
        except ValueError:
            logger.warning("Invalid TELEGRAM_USER_ID format, allowing all users")
    
    return {
        "token": token,
        "api_url": os.getenv("FRIDAY_API_URL", "http://localhost:8080"),
        "api_key": os.getenv("FRIDAY_API_KEY", ""),
        "allowed_users": allowed_users,
    }


CONFIG = get_config()


# =============================================================================
# API Client
# =============================================================================

def get_api_headers() -> dict:
    """Get headers for API requests."""
    headers = {"Content-Type": "application/json"}
    if CONFIG["api_key"]:
        headers["Authorization"] = f"Bearer {CONFIG['api_key']}"
    return headers


async def call_friday_api(
    text: str,
    user_id: str,
    session_id: Optional[str] = None
) -> dict:
    """Call the friday-core API.
    
    Args:
        text: User message
        user_id: Telegram user ID
        session_id: Optional session ID for conversation continuity
        
    Returns:
        API response dict
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{CONFIG['api_url']}/chat",
            headers=get_api_headers(),
            json={
                "text": text,
                "user_id": str(user_id),
                "session_id": session_id or str(user_id),
            }
        )
        response.raise_for_status()
        return response.json()


async def check_api_health() -> bool:
    """Check if the friday-core API is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{CONFIG['api_url']}/health",
                headers=get_api_headers()
            )
            return response.status_code == 200
    except Exception:
        return False


# =============================================================================
# Authorization
# =============================================================================

def is_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    if not CONFIG["allowed_users"]:
        return True  # No restrictions if not configured
    return user_id in CONFIG["allowed_users"]


# =============================================================================
# Command Handlers
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    
    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm Friday, your AI assistant.\n\n"
        "Just send me a message and I'll help you out.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/status - Check system status\n"
        "/clear - Clear conversation history"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    user = update.effective_user
    
    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    # Check API health
    api_healthy = await check_api_health()
    
    if api_healthy:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{CONFIG['api_url']}/health")
                health = response.json()
                
            status_text = (
                "**Friday Status**\n\n"
                f"API: Online\n"
                f"LLM: {'Available' if health.get('llm_available') else 'Offline'}\n"
                f"Tools: {health.get('tools_loaded', 0)}\n"
                f"Sensors: {health.get('sensors_loaded', 0)}"
            )
        except Exception as e:
            status_text = f"API: Online\nError getting details: {e}"
    else:
        status_text = "**Friday Status**\n\nAPI: Offline\n\nThe core service is not responding."
    
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command - clears conversation history."""
    user = update.effective_user
    
    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{CONFIG['api_url']}/conversation/clear",
                params={"user_id": str(user.id)}
            )
            response.raise_for_status()
        
        await update.message.reply_text("Conversation history cleared.")
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        await update.message.reply_text("Error clearing conversation history.")


# =============================================================================
# Message Handler
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user = update.effective_user
    message = update.message
    
    if not is_authorized(user.id):
        await message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    text = message.text
    if not text:
        return
    
    logger.info(f"Message from {user.id} ({user.username}): {text[:50]}...")
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    try:
        # Call Friday API
        response = await call_friday_api(
            text=text,
            user_id=str(user.id),
            session_id=str(message.chat_id)
        )
        
        reply_text = response.get("text", "I couldn't generate a response.")
        
        # Telegram has a 4096 character limit
        if len(reply_text) > 4000:
            # Split into chunks
            chunks = [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]
            for chunk in chunks:
                await message.reply_text(chunk)
        else:
            await message.reply_text(reply_text)
        
        # Log mode for debugging
        mode = response.get("mode", "unknown")
        logger.info(f"Response mode: {mode}, iterations: {response.get('iterations', 1)}")
        
    except httpx.ConnectError:
        logger.error("Cannot connect to Friday API")
        await message.reply_text(
            "I'm having trouble connecting to my brain. "
            "The core service might be down. Please try again later."
        )
    except httpx.TimeoutException:
        logger.error("Friday API timeout")
        await message.reply_text(
            "That's taking longer than expected. Please try again."
        )
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.reply_text(
            "Sorry, I encountered an error processing your message. "
            "Please try again."
        )


# =============================================================================
# Error Handler
# =============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    logger.error(f"Update {update} caused error: {context.error}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Start the Telegram bot."""
    logger.info("Starting Friday Telegram Bot...")
    logger.info(f"API URL: {CONFIG['api_url']}")
    
    if CONFIG["allowed_users"]:
        logger.info(f"Allowed users: {CONFIG['allowed_users']}")
    else:
        logger.info("No user restrictions configured")
    
    # Create application
    application = Application.builder().token(CONFIG["token"]).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
