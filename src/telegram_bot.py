"""
Friday 3.0 Telegram Bot

A lightweight Telegram interface for Friday. This bot is intentionally "dumb" -
it has no AI logic, just forwards messages to the friday-core API and renders responses.

Supports:
- Text messages
- Voice messages (transcribed via Whisper service)

Usage:
    python -m src.telegram_bot

Environment Variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token from @BotFather
    TELEGRAM_ALLOWED_USERS: Comma-separated list of allowed user IDs (optional)
    FRIDAY_API_URL: URL of friday-core API (default: http://localhost:8080)
    WHISPER_SERVICE_URL: URL of Whisper transcription service (optional)
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
        "whisper_url": os.getenv("WHISPER_SERVICE_URL", ""),
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
    
    voice_info = ""
    if CONFIG["whisper_url"]:
        voice_info = "You can also send voice messages!\n\n"
    
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm Friday, your AI assistant.\n\n"
        f"Just send me a message and I'll help you out. {voice_info}"
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
# Voice Transcription
# =============================================================================

async def transcribe_voice(audio_bytes: bytes) -> Optional[str]:
    """Transcribe audio using Whisper service.
    
    Args:
        audio_bytes: Audio file bytes (OGG format from Telegram)
        
    Returns:
        Transcribed text or None if failed
    """
    if not CONFIG["whisper_url"]:
        logger.warning("Whisper service URL not configured")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Send audio to Whisper service
            # Most Whisper services accept multipart form data
            files = {"file": ("voice.ogg", audio_bytes, "audio/ogg")}
            
            response = await client.post(
                f"{CONFIG['whisper_url']}/transcribe",
                files=files
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Handle different response formats
            if isinstance(result, dict):
                text = result.get("text") or result.get("transcription") or result.get("result", "")
            else:
                text = str(result)
            
            return text.strip() if text else None
            
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Whisper service at {CONFIG['whisper_url']}")
        return None
    except httpx.TimeoutException:
        logger.error("Whisper service timeout")
        return None
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None


# =============================================================================
# Message Handlers
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
    
    logger.info(f"[TELEGRAM] Message from user {user.id} (@{user.username}): {text[:50]}{'...' if len(text) > 50 else ''}")
    
    await process_user_input(message, context, text, user)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages and audio files."""
    user = update.effective_user
    message = update.message
    
    if not is_authorized(user.id):
        await message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    # Handle both voice messages and audio files
    voice = message.voice
    audio = message.audio
    
    if not voice and not audio:
        return
    
    # Get file info
    if voice:
        file_id = voice.file_id
        duration = voice.duration
        audio_type = "voice"
    else:
        file_id = audio.file_id
        duration = audio.duration or 0
        audio_type = "audio"
    
    logger.info(f"[TELEGRAM] Voice message from user {user.id} (@{user.username}): {duration}s {audio_type}")
    
    # Check if Whisper is configured
    if not CONFIG["whisper_url"]:
        await message.reply_text(
            "Voice messages are not supported - Whisper service not configured."
        )
        return
    
    # Show typing indicator while processing
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    try:
        # Download the audio file from Telegram
        audio_file = await context.bot.get_file(file_id)
        audio_bytes = await audio_file.download_as_bytearray()
        
        logger.info(f"Downloaded {audio_type} file: {len(audio_bytes)} bytes")
        
        # Transcribe the audio
        transcribed_text = await transcribe_voice(bytes(audio_bytes))
        
        if not transcribed_text:
            await message.reply_text(
                "Sorry, I couldn't understand the audio. Please try again or send a text message."
            )
            return
        
        logger.info(f"Transcribed: {transcribed_text[:100]}...")
        
        # Show what was heard (helps user verify transcription)
        await message.reply_text(f"🎤 I heard: \"{transcribed_text}\"")
        
        # Process the transcribed text as a regular message
        await process_user_input(message, context, transcribed_text, user)
        
    except Exception as e:
        logger.error(f"Error processing {audio_type} message: {e}")
        await message.reply_text(
            "Sorry, I had trouble processing your voice message. Please try again."
        )


async def process_user_input(message, context, text: str, user) -> None:
    """Process user input (from text or transcribed voice) and send response.
    
    Args:
        message: Telegram message object
        context: Telegram context
        text: User's input text
        user: Telegram user object
    """
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
        
        # Check for media attachments (image or audio)
        import re
        
        # Check for image
        image_match = re.search(r'\[IMAGE:([^\]]+)\]', reply_text)
        if image_match:
            image_path = image_match.group(1)
            # Remove the [IMAGE:...] tag from text
            clean_text = re.sub(r'\[IMAGE:[^\]]+\]\s*', '', reply_text)
            
            # Send image
            try:
                with open(image_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=message.chat_id,
                        photo=photo,
                        caption=clean_text if clean_text.strip() else None
                    )
                logger.info(f"[TELEGRAM] Sent image: {image_path}")
                return
            except Exception as e:
                logger.error(f"[TELEGRAM] Failed to send image: {e}")
                await message.reply_text(f"{clean_text}\n\n(Failed to send image)")
                return
        
        # Check for audio
        audio_match = re.search(r'\[AUDIO:([^\]]+)\]', reply_text)
        if audio_match:
            audio_path = audio_match.group(1)
            # Remove the [AUDIO:...] tag from text
            clean_text = re.sub(r'\[AUDIO:[^\]]+\]\s*', '', reply_text)
            
            # Send audio as voice message
            try:
                with open(audio_path, 'rb') as audio:
                    await context.bot.send_voice(
                        chat_id=message.chat_id,
                        voice=audio,
                        caption=clean_text if clean_text.strip() else None
                    )
                logger.info(f"[TELEGRAM] Sent audio: {audio_path}")
                return
            except Exception as e:
                logger.error(f"[TELEGRAM] Failed to send audio: {e}")
                await message.reply_text(f"{clean_text}\n\n(Failed to send audio)")
                return
        
        # Regular text response (no media)
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
    
    if CONFIG["whisper_url"]:
        logger.info(f"Whisper service: {CONFIG['whisper_url']}")
    else:
        logger.info("Voice messages disabled (no Whisper service configured)")
    
    # Create application
    application = Application.builder().token(CONFIG["token"]).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
