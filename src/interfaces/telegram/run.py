"""
Friday Telegram Bot

Entry point for running the Telegram bot as a service.
Uses the new interfaces system for communication.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.interfaces.base import Message, MessageType
from src.interfaces.manager import ChannelManager
from src.interfaces.telegram.channel import TelegramChannel
from src.core.agent import agent, AgentDeps
from src.core.conversation import get_conversation_manager
from settings import settings

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)


class FridayTelegramBot:
    """Friday Telegram bot using the new interfaces system."""
    
    def __init__(self):
        self.manager = ChannelManager()
        self.telegram = TelegramChannel()
        self.conversation_manager = get_conversation_manager()
        
    async def handle_incoming_message(self, message: Message):
        """
        Process incoming messages from Telegram.
        
        Args:
            message: Incoming message from user
        """
        logger.info(f"Processing message from {message.sender_name}: {message.content[:50]}...")
        
        try:
            # Use sender_id as session_id (channel-agnostic)
            session_id = message.sender_id
            
            # Get conversation history for this session
            history = self.conversation_manager.get_history(session_id)
            logger.info(f"Loaded {len(history)} messages from history for session {session_id}")
            
            # Create dependencies with session_id for tools
            deps = AgentDeps(session_id=session_id)
            
            # Run the AI agent with the user's message, history, and dependencies
            result = await agent.run(message.content, message_history=history, deps=deps)
            
            # Update conversation history with the complete message list
            # result.all_messages() contains: old history + user message + assistant response
            self.conversation_manager.update_history(session_id, result.all_messages())
            
            # Send the response back (pydantic-ai returns result.output, not result.data)
            response = Message(
                content=result.output,
                type=MessageType.TEXT,
                reply_to=message.metadata.get('telegram_message_id')
            )
            
            delivery_result = await self.telegram.send(response)
            
            if delivery_result.success:
                logger.info(f"✓ Response sent successfully (msg_id: {delivery_result.message_id}): {result.output[:100]}...")
            else:
                logger.error(f"✗ Failed to send response: {delivery_result.error}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
            # Send error message to user
            error_response = Message(
                content="Sorry, I encountered an error processing your message. Please try again.",
                type=MessageType.TEXT
            )
            await self.telegram.send(error_response)
    
    async def start(self):
        """Start the Telegram bot."""
        logger.info("Starting Friday Telegram Bot...")
        
        # Check configuration
        if not self.telegram.is_available():
            logger.error("Telegram not configured! Check TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID")
            sys.exit(1)
        
        logger.info(f"Telegram bot configured for user(s): {self.telegram.allowed_user_ids}")
        
        # Register message handler
        self.telegram.register_handler(self.handle_incoming_message)
        
        # Register channel with manager
        self.manager.register_channel(self.telegram, is_default=True)
        
        # Start listening
        try:
            await self.manager.start_all()
            logger.info("Telegram bot is running. Press Ctrl+C to stop.")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            await self.manager.stop_all()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            await self.manager.stop_all()
            sys.exit(1)


async def main():
    """Main entry point."""
    bot = FridayTelegramBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
