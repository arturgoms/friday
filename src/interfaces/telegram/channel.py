"""
Telegram Channel Implementation

Provides Telegram bot integration for Friday using python-telegram-bot.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.interfaces.base import (
    Channel, Message, DeliveryResult, MessageType, MessagePriority,
    ChannelNotAvailableError
)
from settings import settings

logger = logging.getLogger(__name__)


class TelegramChannel(Channel):
    """
    Telegram bot channel implementation.
    
    Features:
    - Send/receive text messages
    - Handle commands
    - Support for rich media (images, audio, etc.)
    - Thread support (reply to messages)
    """
    
    def __init__(
        self,
        channel_id: str = "telegram",
        bot_token: Optional[str] = None,
        allowed_user_ids: Optional[list] = None
    ):
        """
        Initialize Telegram channel.
        
        Args:
            channel_id: Unique identifier for this channel
            bot_token: Telegram bot token (from settings if None)
            allowed_user_ids: List of allowed Telegram user IDs (from settings if None)
        """
        config = {
            'bot_token': bot_token or settings.TELEGRAM_BOT_TOKEN,
            'allowed_user_ids': allowed_user_ids or [settings.TELEGRAM_USER_ID]
        }
        super().__init__(channel_id, config)
        
        self.bot_token = self.config['bot_token']
        # Convert allowed_user_ids to integers (Telegram API returns int user IDs)
        self.allowed_user_ids = [int(uid) if isinstance(uid, str) else uid 
                                  for uid in self.config['allowed_user_ids']]
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
    
    def is_available(self) -> bool:
        """Check if Telegram is configured and available."""
        return bool(self.bot_token and self.allowed_user_ids)
    
    def supports_message_type(self, message_type: MessageType) -> bool:
        """Check if this message type is supported."""
        supported = {
            MessageType.TEXT,
            MessageType.IMAGE,
            MessageType.AUDIO,
            MessageType.VIDEO,
            MessageType.DOCUMENT,
            MessageType.LOCATION
        }
        return message_type in supported
    
    async def send(self, message: Message) -> DeliveryResult:
        """
        Send a message via Telegram.
        
        Args:
            message: Message to send
            
        Returns:
            DeliveryResult with success status and message ID
        """
        if not self.is_available():
            return DeliveryResult(
                success=False,
                error="Telegram channel not configured"
            )
        
        if not self.bot:
            self.bot = Bot(token=self.bot_token)
        
        try:
            # Determine which user to send to
            chat_id = self.allowed_user_ids[0] if self.allowed_user_ids else None
            if not chat_id:
                return DeliveryResult(
                    success=False,
                    error="No valid chat ID configured"
                )
            
            # Send based on message type
            sent_message = None
            
            if message.type == MessageType.TEXT:
                sent_message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=message.content,
                    reply_to_message_id=message.reply_to if message.reply_to else None
                )
            
            elif message.type == MessageType.IMAGE and message.attachments:
                sent_message = await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=message.attachments[0],
                    caption=message.content if message.content else None,
                    reply_to_message_id=message.reply_to if message.reply_to else None
                )
            
            elif message.type == MessageType.DOCUMENT and message.attachments:
                sent_message = await self.bot.send_document(
                    chat_id=chat_id,
                    document=message.attachments[0],
                    caption=message.content if message.content else None,
                    reply_to_message_id=message.reply_to if message.reply_to else None
                )
            
            elif message.type == MessageType.AUDIO:
                # For audio, content should be the file path
                from pathlib import Path
                audio_path = Path(message.content)
                
                if not audio_path.exists():
                    return DeliveryResult(
                        success=False,
                        error=f"Audio file not found: {audio_path}"
                    )
                
                # Send as voice message (more suitable for TTS)
                with open(audio_path, 'rb') as audio_file:
                    sent_message = await self.bot.send_voice(
                        chat_id=chat_id,
                        voice=audio_file,
                        reply_to_message_id=message.reply_to if message.reply_to else None
                    )
            
            else:
                return DeliveryResult(
                    success=False,
                    error=f"Unsupported message type: {message.type}"
                )
            
            return DeliveryResult(
                success=True,
                message_id=str(sent_message.message_id),
                timestamp=datetime.now(),
                metadata={'chat_id': chat_id}
            )
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return DeliveryResult(
                success=False,
                error=str(e)
            )
    
    async def start(self):
        """Start the Telegram bot (begin polling for messages)."""
        if not self.is_available():
            raise ChannelNotAvailableError("Telegram channel not configured")
        
        self.logger.info("Starting Telegram bot...")
        
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        self.bot = self.application.bot
        
        # Register handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text_message
        ))
        self.application.add_handler(MessageHandler(
            filters.VOICE,
            self._handle_voice_message
        ))
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        self._is_running = True
        self.logger.info("Telegram bot started successfully")
    
    async def stop(self):
        """Stop the Telegram bot."""
        if not self.application:
            return
        
        self.logger.info("Stopping Telegram bot...")
        
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        
        self._is_running = False
        self.logger.info("Telegram bot stopped")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        
        if user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return
        
        await update.message.reply_text(
            "👋 Hello! I'm Friday, your personal AI assistant.\n\n"
            "Send me a message and I'll help you out!"
        )
    
    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        user_id = update.effective_user.id
        
        self.logger.info(f"Received message from user_id={user_id}, allowed={self.allowed_user_ids}")
        
        if user_id not in self.allowed_user_ids:
            self.logger.warning(f"User {user_id} not authorized")
            return
        
        # Convert Telegram message to our Message format
        message = Message(
            content=update.message.text,
            type=MessageType.TEXT,
            timestamp=update.message.date,
            sender_id=str(user_id),
            sender_name=update.effective_user.first_name,
            channel=self.channel_id,
            metadata={
                'telegram_message_id': update.message.message_id,
                'chat_id': update.effective_chat.id
            }
        )
        
        # Pass to registered handlers
        self._handle_incoming_message(message)
    
    async def _handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming voice messages."""
        user_id = update.effective_user.id
        
        if user_id not in self.allowed_user_ids:
            return
        
        # Get voice file
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        message = Message(
            content="[Voice message]",
            type=MessageType.AUDIO,
            timestamp=update.message.date,
            sender_id=str(user_id),
            sender_name=update.effective_user.first_name,
            channel=self.channel_id,
            attachments=[file.file_path],
            metadata={
                'telegram_message_id': update.message.message_id,
                'chat_id': update.effective_chat.id,
                'duration': voice.duration,
                'mime_type': voice.mime_type
            }
        )
        
        self._handle_incoming_message(message)
