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
            # Track original message type (before transcription)
            original_message_type = message.type
            
            # Handle voice messages - transcribe to text first
            if message.type == MessageType.AUDIO and message.attachments:
                from src.tools.media import transcribe_audio
                import tempfile
                import httpx
                
                # Download the voice file from Telegram
                voice_url = message.attachments[0]
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.ogg')
                
                try:
                    # Download voice file
                    with httpx.Client(timeout=30) as client:
                        response = client.get(voice_url)
                        temp_audio.write(response.content)
                        temp_audio.flush()
                    
                    # Transcribe
                    transcribed_text = transcribe_audio(temp_audio.name)
                    
                    # Replace message content with transcribed text
                    message.content = transcribed_text
                    message.type = MessageType.TEXT
                    
                    logger.info(f"Voice message transcribed: {transcribed_text[:100]}")
                    
                finally:
                    import os
                    temp_audio.close()
                    os.unlink(temp_audio.name)
            
            # Check if this message is a reply to today's journal thread
            reply_to_id = self.telegram.get_reply_to_message_id(message)
            if reply_to_id:
                from src.tools.journal import get_journal_thread_for_date, save_journal_entry
                from src.utils.time import get_brt
                from datetime import datetime
                
                today = datetime.now(get_brt()).strftime("%Y-%m-%d")
                thread_id = get_journal_thread_for_date(today)
                
                if thread_id and str(thread_id) == str(reply_to_id):
                    # This is a journal entry!
                    entry_type = "audio" if original_message_type == MessageType.AUDIO else "text"
                    save_journal_entry(
                        content=message.content,
                        entry_type=entry_type,
                        thread_message_id=int(reply_to_id)
                    )
                    logger.info(f"✓ Saved journal entry ({entry_type}, {len(message.content)} chars)")
                    
                    # Send acknowledgment without processing with agent
                    response = Message(
                        content="✅ Journal entry saved!",
                        type=MessageType.TEXT,
                        reply_to=reply_to_id
                    )
                    await self.telegram.send(response)
                    return  # Don't process with agent
            
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
            
            # Check if generate_speech or generate_image was called by examining the result data
            import re
            from pathlib import Path
            
            audio_file_path = None
            image_file_path = None
            
            # Method 1: Check if response contains [AUDIO:...] or [IMAGE:...] markers
            audio_match = re.search(r'\[AUDIO:([^\]]+)\]', result.output)
            if audio_match:
                audio_file_path = audio_match.group(1)
            
            image_match = re.search(r'\[IMAGE:([^\]]+)\]', result.output)
            if image_match:
                image_file_path = image_match.group(1)
            
            # Method 2: Check if generate_speech or generate_image was called in THIS request
            # Only look in the NEW messages from this request (not history)
            generate_speech_called = False
            generate_image_called = False
            
            if not audio_file_path or not image_file_path:
                # Get only the new messages from this turn (not the full history)
                all_msgs = result.all_messages()
                # The new messages are at the end - typically last 2-4 messages
                new_messages = all_msgs[-10:] if len(all_msgs) > 10 else all_msgs
                
                for msg in new_messages:
                    # Check if this is a tool response message
                    if hasattr(msg, 'parts'):
                        for part in msg.parts:
                            # Check tool names
                            if hasattr(part, 'tool_name'):
                                if part.tool_name == 'generate_speech':
                                    generate_speech_called = True
                                    if not audio_file_path and hasattr(part, 'content'):
                                        content_str = str(part.content)
                                        match = re.search(r'\[AUDIO:([^\]]+)\]', content_str)
                                        if match:
                                            audio_file_path = match.group(1)
                                elif part.tool_name == 'generate_image':
                                    generate_image_called = True
                                    if not image_file_path and hasattr(part, 'content'):
                                        content_str = str(part.content)
                                        match = re.search(r'\[IMAGE:([^\]]+)\]', content_str)
                                        if match:
                                            image_file_path = match.group(1)
            
            # Method 3: Check for recently created files ONLY if the tool was actually called
            import time
            if not audio_file_path and generate_speech_called:
                media_dir = Path("/home/artur/friday/data/media")
                if media_dir.exists():
                    audio_files = sorted(media_dir.glob("speech_*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if audio_files:
                        # Get the most recent audio file (created in last 5 seconds - must be from THIS request)
                        most_recent = audio_files[0]
                        age_seconds = time.time() - most_recent.stat().st_mtime
                        if age_seconds < 5:  # Stricter: must be very recent
                            audio_file_path = str(most_recent)
                            logger.info(f"Found recently generated audio file: {audio_file_path} (age: {age_seconds:.1f}s)")
            
            if not image_file_path and generate_image_called:
                media_dir = Path("/home/artur/friday/data/media")
                if media_dir.exists():
                    image_files = sorted(media_dir.glob("image_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if image_files:
                        # Get the most recent image file (created in last 10 seconds for images - they take longer)
                        most_recent = image_files[0]
                        age_seconds = time.time() - most_recent.stat().st_mtime
                        if age_seconds < 10:
                            image_file_path = str(most_recent)
                            logger.info(f"Found recently generated image file: {image_file_path} (age: {age_seconds:.1f}s)")
            
            # Send audio if we found a file
            if audio_file_path:
                # Verify the file actually exists before trying to send
                import time
                audio_file = Path(audio_file_path)
                if not audio_file.exists():
                    logger.warning(f"Audio file path found but file doesn't exist: {audio_file_path}")
                    # Try to find the actual most recent file
                    media_dir = Path("/home/artur/friday/data/media")
                    audio_files = sorted(media_dir.glob("speech_*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if audio_files and (time.time() - audio_files[0].stat().st_mtime < 5):
                        audio_file_path = str(audio_files[0])
                        logger.info(f"Using actual recent file: {audio_file_path}")
                    else:
                        audio_file_path = None
            
            # Process audio sending if we have a valid file
            if audio_file_path:
                # Remove the [AUDIO:...] marker from the text (if present)
                text_content = re.sub(r'\[AUDIO:[^\]]+\]\n?', '', result.output).strip()
                
                # Send audio file first
                audio_message = Message(
                    content=audio_file_path,
                    type=MessageType.AUDIO,
                    reply_to=message.metadata.get('telegram_message_id')
                )
                audio_result = await self.telegram.send(audio_message)
                
                # Clean up audio file after sending
                try:
                    import os
                    audio_file = Path(audio_file_path)
                    if audio_file.exists():
                        os.unlink(audio_file)
                        logger.info(f"🗑️ Deleted audio file: {audio_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio file {audio_file_path}: {e}")
                
                if audio_result.success:
                    logger.info(f"✓ Audio sent successfully: {audio_file_path}")
                else:
                    logger.error(f"✗ Failed to send audio: {audio_result.error}")
                    # If audio fails, send text with error
                    text_content = f"⚠️ Failed to send audio file.\n\n{text_content}"
                
                # Also send text if there's accompanying text
                if text_content:
                    text_message = Message(
                        content=text_content,
                        type=MessageType.TEXT,
                        reply_to=message.metadata.get('telegram_message_id')
                    )
                    await self.telegram.send(text_message)
            
            # Handle image sending (similar to audio)
            elif image_file_path:
                # Verify file exists
                image_file = Path(image_file_path)
                if not image_file.exists():
                    logger.warning(f"Image file path found but file doesn't exist: {image_file_path}")
                    media_dir = Path("/home/artur/friday/data/media")
                    image_files = sorted(media_dir.glob("image_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if image_files and (time.time() - image_files[0].stat().st_mtime < 10):
                        image_file_path = str(image_files[0])
                        logger.info(f"Using actual recent image: {image_file_path}")
                    else:
                        image_file_path = None
            
            if image_file_path:
                # Remove [IMAGE:...] marker from text
                text_content = re.sub(r'\[IMAGE:[^\]]+\]\n?', '', result.output).strip()
                # Also remove HTML-style img tags
                text_content = re.sub(r'<image[^>]*>', '', text_content).strip()
                
                # Send image (path goes in attachments, caption in content)
                caption = text_content if text_content else "Generated image"
                image_message = Message(
                    content=caption,
                    type=MessageType.IMAGE,
                    attachments=[image_file_path],
                    reply_to=message.metadata.get('telegram_message_id')
                )
                image_result = await self.telegram.send(image_message)
                
                # Clean up image file
                try:
                    import os
                    if Path(image_file_path).exists():
                        os.unlink(image_file_path)
                        logger.info(f"🗑️ Deleted image file: {image_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete image {image_file_path}: {e}")
                
                if image_result.success:
                    logger.info(f"✓ Image sent successfully: {image_file_path}")
                else:
                    logger.error(f"✗ Failed to send image: {image_result.error}")
                    # If image sending failed, send error as text
                    error_message = Message(
                        content=f"⚠️ Failed to send image.\n\n{text_content}",
                        type=MessageType.TEXT,
                        reply_to=message.metadata.get('telegram_message_id')
                    )
                    await self.telegram.send(error_message)
            
            else:
                # Regular text response
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
