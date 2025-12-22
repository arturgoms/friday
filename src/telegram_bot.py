"""
Friday AI - Telegram Bot Interface
Allows you to interact with Friday AI from your phone via Telegram
"""
import os
import sys
import logging
import requests
import tempfile
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FRIDAY_API_URL = os.getenv("FRIDAY_API_URL", "http://localhost:8080")
AUTHORIZED_USER_ID = os.getenv("TELEGRAM_USER_ID")  # Your Telegram user ID
FRIDAY_API_KEY = os.getenv("FRIDAY_API_KEY", None)

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handlers if they haven't been added yet
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler('/home/artur/friday/logs/telegram_bot.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Web search trigger keywords
WEB_SEARCH_KEYWORDS = [
    'search', 'find', 'look up', 'google', 'web',
    'latest', 'recent', 'current', 'news', 'today',
    'what is', 'who is', 'where is', 'when is', 'how to',
    'weather', 'forecast', 'stock', 'price',
    'happening', 'update', 'information about'
]


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    if not AUTHORIZED_USER_ID:
        return True  # If no user ID set, allow all (not recommended for production)
    return str(user_id) == str(AUTHORIZED_USER_ID)


def should_use_web_search(message: str) -> bool:
    """Determine if the message should trigger web search."""
    message_lower = message.lower()
    
    # Check if any keyword is in the message
    for keyword in WEB_SEARCH_KEYWORDS:
        if keyword in message_lower:
            return True
    
    # Check if message starts with question words
    question_starters = ['what', 'who', 'where', 'when', 'why', 'how']
    first_word = message_lower.split()[0] if message_lower.split() else ''
    if first_word in question_starters:
        # Additional check: if it's about general knowledge, use web
        general_terms = ['is the', 'are the', 'was the', 'were the', 'does', 'did']
        if any(term in message_lower for term in general_terms):
            return True
    
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ Unauthorized. This bot is private.\n"
            f"Your user ID: {user_id}"
        )
        return
    
    await update.message.reply_text(
        "🤖 *Friday AI Assistant*\n\n"
        "I'm your personal AI assistant with access to your notes and memories.\n\n"
        "*Available Commands:*\n"
        "/start - Show this message\n"
        "/help - Show help\n"
        "/remember <text> - Save a memory\n"
        "/reminders - List all pending reminders\n"
        "/sync - Sync with Nextcloud\n"
        "/stats - Show system stats\n"
        "/feedback - View feedback statistics\n\n"
        "*Just send me a message* to ask anything!\n\n"
        "💡 Use 👍/👎 buttons to rate my answers and help me improve!\n\n"
        "🌐 I automatically search the web when you ask about:\n"
        "• Latest/current information\n"
        "• News and updates\n"
        "• General knowledge questions",
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_authorized(update.effective_user.id):
        return
    
    await update.message.reply_text(
        "💡 *How to use Friday AI:*\n\n"
        "📝 *Ask questions:*\n"
        "Just send me any message and I'll search your notes and memories to answer.\n\n"
        "🌐 *Web Search:*\n"
        "I automatically search the web when you use keywords like:\n"
        "• search, find, look up\n"
        "• latest, current, recent, news\n"
        "• what is, who is, where is\n"
        "• weather, stock prices\n\n"
        "💾 *Save memories:*\n"
        "/remember Your important note here\n\n"
        "🔄 *Sync Nextcloud:*\n"
        "/sync - Force Nextcloud to rescan files\n\n"
        "📊 *Check status:*\n"
        "/stats - See system statistics\n\n"
        "*Examples:*\n"
        "• \"What's the latest news about AI?\" 🌐 (uses web)\n"
        "• \"What do my notes say about Django?\" 📚 (uses notes)\n"
        "• \"Search for Python tutorials\" 🌐 (uses web)\n"
        "• \"Remember: Meeting with team tomorrow at 3pm\" 💾",
        parse_mode='Markdown'
    )


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remember command."""
    if not is_authorized(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide text to remember.\n\n"
            "Example: /remember My favorite color is blue"
        )
        return
    
    text = ' '.join(context.args)
    
    try:
        headers = {}
        if FRIDAY_API_KEY:
            headers['X-API-Key'] = FRIDAY_API_KEY
        
        response = requests.post(
            f"{FRIDAY_API_URL}/remember",
            json={"content": text, "tags": ["telegram"]},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            await update.message.reply_text(
                f"✅ Memory saved!\n\n_\"{text[:100]}...\"_",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ Failed to save memory: {response.status_code}"
            )
    except Exception as e:
        logger.error(f"Remember error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sync command."""
    if not is_authorized(update.effective_user.id):
        return
    
    await update.message.reply_text("🔄 Syncing with Nextcloud... (this may take a minute)")
    
    try:
        headers = {}
        if FRIDAY_API_KEY:
            headers['X-API-Key'] = FRIDAY_API_KEY
        
        response = requests.post(
            f"{FRIDAY_API_URL}/admin/sync-nextcloud",
            headers=headers,
            timeout=300
        )
        
        if response.status_code == 200:
            await update.message.reply_text("✅ Nextcloud sync completed!")
        else:
            await update.message.reply_text(f"❌ Sync failed: {response.status_code}")
    except Exception as e:
        logger.error(f"Sync error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reminders command - list all pending reminders."""
    if not is_authorized(update.effective_user.id):
        return
    
    try:
        from app.services.reminders import reminder_service
        
        pending = reminder_service.list_pending_reminders()
        
        if not pending:
            await update.message.reply_text("📋 No pending reminders.")
            return
        
        msg = "🔔 *Pending Reminders*\n\n"
        for i, reminder in enumerate(sorted(pending, key=lambda r: r.remind_at), 1):
            remind_at = reminder.remind_at.strftime("%a %d %b %H:%M")
            msg += f"{i}. {reminder.message}\n   ⏰ {remind_at}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Reminders error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    if not is_authorized(update.effective_user.id):
        return
    
    try:
        headers = {}
        if FRIDAY_API_KEY:
            headers['X-API-Key'] = FRIDAY_API_KEY
        
        response = requests.get(
            f"{FRIDAY_API_URL}/health",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"📊 *System Status*\n\n"
                f"🤖 LLM: {data['llm_status']}\n"
                f"📁 Vault: {data['vault_exists'] and '✅' or '❌'}\n"
                f"📝 Chunks: {data['obsidian_chunks']}\n"
                f"💾 Memories: {data['memory_entries']}\n"
                f"📂 Path: `{data['vault_path']}`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to get stats")
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages (questions to Friday)."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    user_message = update.message.text
    user_id = update.effective_user.id
    
    # Check if we're awaiting a correction
    correction_state = context.user_data.get("awaiting_correction")
    if correction_state:
        # Check if correction request has expired (5 minutes)
        correction_time = datetime.fromisoformat(correction_state["timestamp"])
        if datetime.now() - correction_time < timedelta(minutes=5):
            # This message might be a correction - check if it looks like feedback
            # Short messages or messages that start with "you should" etc. are likely corrections
            is_correction = (
                len(user_message) < 500 and  # Not a new conversation
                not should_use_web_search(user_message) and  # Not a search query
                any(phrase in user_message.lower() for phrase in [
                    "you should", "should have", "instead", "wrong", "correct", 
                    "actually", "meant", "wanted", "expected", "better if",
                    "next time", "don't", "do not", "please"
                ]) or len(user_message) < 200  # Short messages are likely corrections
            )
            
            if is_correction:
                # Store the correction
                try:
                    from app.services.feedback_store import get_feedback_store
                    feedback_store = get_feedback_store()
                    
                    feedback_store.add_correction(
                        feedback_id=correction_state["feedback_id"],
                        correction_text=user_message
                    )
                    
                    # Clear the correction state
                    del context.user_data["awaiting_correction"]
                    
                    await update.message.reply_text(
                        "Got it! I'll learn from this feedback. Thanks for helping me improve!"
                    )
                    logger.info(f"Correction recorded for feedback {correction_state['feedback_id']}")
                    return
                    
                except Exception as e:
                    logger.error(f"Error storing correction: {e}")
                    # Continue with normal message handling
        
        # Clear expired correction state
        if "awaiting_correction" in context.user_data:
            del context.user_data["awaiting_correction"]
    
    # Detect if web search should be used
    use_web = should_use_web_search(user_message)
    
    logger.info(f"Question from {update.effective_user.first_name} (ID: {user_id}): {user_message} [Web: {use_web}]")
    
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    try:
        headers = {}
        if FRIDAY_API_KEY:
            headers['X-API-Key'] = FRIDAY_API_KEY
        
        response = requests.post(
            f"{FRIDAY_API_URL}/chat",
            json={
                "message": user_message,
                "use_rag": True,
                "use_memory": True,
                "use_web": use_web,
                "save_memory": True
            },
            headers=headers,
            timeout=120  # Increased timeout for web searches
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data['answer']
            
            # Log the answer for debugging
            logger.info(f"Friday's response: {answer[:200]}")
            
            # Add context info
            context_info = []
            if data.get('used_rag'):
                context_info.append("📚 Notes")
            if data.get('used_memory'):
                context_info.append("💭 Memory")
            if data.get('used_health'):
                context_info.append("🏃 Health Data")
            if data.get('used_web'):
                context_info.append("🌐 Web")
            
            footer = f"\n\n_{' + '.join(context_info)}_" if context_info else ""
            
            # Create feedback buttons
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍", callback_data=f"feedback:up"),
                    InlineKeyboardButton("👎", callback_data=f"feedback:down")
                ]
            ])
            
            # Store context for feedback (in memory for now, could use context.user_data)
            if not hasattr(context, 'bot_data'):
                context.bot_data = {}
            
            # Split long messages
            if len(answer) > 4000:
                chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
                for chunk in chunks[:-1]:
                    await update.message.reply_text(chunk)
                # Add buttons only to last message
                sent_msg = await update.message.reply_text(
                    chunks[-1] + footer, 
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                sent_msg = await update.message.reply_text(
                    answer + footer, 
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            
            # Store message context for feedback
            context.bot_data[f"msg_{sent_msg.message_id}"] = {
                "user_message": user_message,
                "ai_response": answer,
                "context_type": "health" if data.get('used_health') else "rag" if data.get('used_rag') else "general",
                "intent_action": data.get('intent', {}).get('action', 'unknown') if isinstance(data.get('intent'), dict) else 'unknown'
            }
        else:
            await update.message.reply_text(
                f"❌ Error: {response.status_code}\n{response.text[:200]}"
            )
    except Exception as e:
        logger.error(f"Message handling error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    try:
        # Send typing indicator while processing
        await update.message.chat.send_action(action="typing")
        
        # Get voice message file
        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        
        # Download to temporary file
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            await voice_file.download_to_drive(tmp_path)
        
        try:
            # Transcribe using external Whisper service
            whisper_url = os.getenv('WHISPER_SERVICE_URL')
            
            logger.info(f"Whisper URL from env: {whisper_url}")
            
            if not whisper_url:
                await update.message.reply_text(
                    "❌ Voice transcription not configured. Please set WHISPER_SERVICE_URL in .env file\n"
                    "Example: WHISPER_SERVICE_URL=http://your-server:8001"
                )
                return
            
            # Send audio file to Whisper service using curl (workaround for urllib3 bug)
            # Using onerahmet/openai-whisper-asr-webservice API format
            logger.info(f"Sending audio file to {whisper_url}/asr")
            logger.info(f"File path: {tmp_path}, exists: {os.path.exists(tmp_path)}")
            
            import subprocess
            import json
            
            curl_result = subprocess.run([
                'curl', '-s', '-X', 'POST',
                '--http1.1',  # Force HTTP/1.1
                '-m', '120',  # Timeout
                f'{whisper_url}/asr?task=transcribe&language=pt&output=json',
                '-F', f'audio_file=@{tmp_path}'
            ], capture_output=True, text=True, timeout=130)
            
            logger.info(f"Curl return code: {curl_result.returncode}")
            logger.info(f"Curl stdout: {curl_result.stdout[:500] if curl_result.stdout else 'empty'}")
            
            if curl_result.returncode != 0:
                logger.error(f"Curl stderr: {curl_result.stderr}")
                await update.message.reply_text(
                    f"❌ Transcription failed: {curl_result.stderr[:200]}"
                )
                return
            
            # Parse response - the API returns JSON with "text" field
            try:
                transcribe_data = json.loads(curl_result.stdout)
                transcribed_text = transcribe_data.get('text', curl_result.stdout)
            except json.JSONDecodeError:
                # If not JSON, the response might be plain text
                transcribed_text = curl_result.stdout.strip()
            
            if not transcribed_text:
                await update.message.reply_text(
                    f"❌ Transcription failed: empty response"
                )
                return
            
            logger.info(f"Voice transcribed via Whisper service: {transcribed_text}")
            
            # Process the transcribed text as a regular message (no extra messages)
            user_id = update.effective_user.id
            use_web = should_use_web_search(transcribed_text)
            
            logger.info(f"Voice message from {update.effective_user.first_name} (ID: {user_id}): {transcribed_text} [Web: {use_web}]")
            
            # Send typing indicator
            await update.message.chat.send_action(action="typing")
            
            # Call Friday API
            headers = {}
            if FRIDAY_API_KEY:
                headers['X-API-Key'] = FRIDAY_API_KEY
            
            response = requests.post(
                f"{FRIDAY_API_URL}/chat",
                json={
                    "message": transcribed_text,
                    "use_rag": True,
                    "use_memory": True,
                    "use_web": use_web,
                    "save_memory": True
                },
                headers=headers,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data['answer']
                
                logger.info(f"Friday's response: {answer[:200]}")
                
                # Add context info
                context_info = []
                if data.get('used_rag'):
                    context_info.append("📚 Notes")
                if data.get('used_memory'):
                    context_info.append("💭 Memory")
                if data.get('used_health'):
                    context_info.append("🏃 Health Data")
                if data.get('used_web'):
                    context_info.append("🌐 Web")
                
                footer = f"\n\n_{' + '.join(context_info)}_" if context_info else ""
                
                # Split long messages
                if len(answer) > 4000:
                    chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                    if footer:
                        await update.message.reply_text(footer, parse_mode='Markdown')
                else:
                    await update.message.reply_text(answer + footer, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    f"❌ Error: {response.status_code}\n{response.text[:200]}"
                )
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Voice message handling error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error processing voice message: {str(e)}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks (feedback, ack, alert_feedback)."""
    query = update.callback_query
    await query.answer()
    
    if not is_authorized(query.from_user.id):
        return
    
    callback_data = query.data
    
    # Handle chat response feedback callbacks
    if callback_data.startswith("feedback:"):
        await handle_feedback_callback(query, context)
    
    # Handle alert acknowledgment callbacks
    elif callback_data.startswith("ack:"):
        await handle_ack_callback(query, context)
    
    # Handle proactive alert feedback callbacks
    elif callback_data.startswith("alert_feedback:"):
        await handle_alert_feedback_callback(query, context)


async def handle_feedback_callback(query, context):
    """Handle feedback button clicks."""
    callback_data = query.data
    feedback_type = callback_data.split(":")[1]  # 'up' or 'down'
    
    if feedback_type == "done":
        return  # Already processed
    
    if feedback_type == "skip_correction":
        # User declined to provide correction
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👎 Thanks for feedback!", callback_data="feedback:done")]
            ])
        )
        # Clear correction state
        if "awaiting_correction" in context.user_data:
            del context.user_data["awaiting_correction"]
        return
    
    message_id = query.message.message_id
    chat_id = query.message.chat_id
    
    # Get stored context for this message
    msg_key = f"msg_{message_id}"
    msg_context = context.bot_data.get(msg_key, {})
    
    try:
        # Store feedback
        from app.services.feedback_store import get_feedback_store
        feedback_store = get_feedback_store()
        
        feedback_id = feedback_store.add_feedback(
            user_message=msg_context.get("user_message", "Unknown"),
            ai_response=msg_context.get("ai_response", "Unknown"),
            feedback=feedback_type,
            message_id=str(message_id),
            context_type=msg_context.get("context_type"),
            intent_action=msg_context.get("intent_action")
        )
        
        if feedback_type == "up":
            # Thumbs up - just thank them
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👍 Thanks for feedback!", callback_data="feedback:done")]
                ])
            )
        else:
            # Thumbs down - ask for correction
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👎 Feedback received", callback_data="feedback:done")]
                ])
            )
            
            # Store state for correction flow
            context.user_data["awaiting_correction"] = {
                "feedback_id": feedback_id,
                "message_id": message_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # Ask for correction
            await context.bot.send_message(
                chat_id=chat_id,
                text="Thanks for the feedback. What should I have done differently? (Reply to help me learn, or just send your next message to skip)",
                reply_to_message_id=message_id
            )
        
        logger.info(f"Feedback recorded: {feedback_type} for message {message_id}")
        
        # Clean up stored context
        if msg_key in context.bot_data:
            del context.bot_data[msg_key]
            
    except Exception as e:
        logger.error(f"Error storing feedback: {e}")
        await query.edit_message_reply_markup(reply_markup=None)


async def handle_ack_callback(query, context):
    """Handle alert acknowledgment button clicks."""
    callback_data = query.data
    alert_key = callback_data.split(":", 1)[1]  # Get everything after "ack:"
    
    try:
        # Import the awareness engine to acknowledge the alert
        from app.services.awareness_engine import awareness_engine
        awareness_engine.acknowledge_alert(alert_key)
        
        # Update the message to show it's been acknowledged
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✓ Acknowledged", callback_data="ack:done")]
            ])
        )
        
        logger.info(f"Alert acknowledged: {alert_key}")
        
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        # Still remove the button even if there's an error
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass


async def handle_alert_feedback_callback(query, context):
    """Handle feedback button clicks on proactive alerts."""
    callback_data = query.data
    # Format: alert_feedback:up:alert_key or alert_feedback:down:alert_key
    parts = callback_data.split(":", 2)
    
    if len(parts) < 3:
        return
    
    feedback_type = parts[1]  # 'up' or 'down'
    alert_key = parts[2]
    
    if feedback_type == "done":
        return  # Already processed
    
    try:
        # Record alert feedback
        from app.services.awareness_engine import awareness_engine
        
        # Track alert feedback in the budget system
        awareness_engine.record_alert_feedback(alert_key, feedback_type)
        
        # Get the alert message for context
        message_text = query.message.text if query.message else "Unknown alert"
        
        # Also store in feedback store for analysis
        from app.services.feedback_store import get_feedback_store
        feedback_store = get_feedback_store()
        
        feedback_id = feedback_store.add_feedback(
            user_message=f"[PROACTIVE ALERT] {alert_key}",
            ai_response=message_text[:1000] if message_text else "Unknown",
            feedback=feedback_type,
            message_id=str(query.message.message_id) if query.message else None,
            context_type="proactive_alert",
            intent_action=f"alert_{alert_key.split('_')[0]}" if '_' in alert_key else "alert"
        )
        
        # Store context for potential correction
        if feedback_type == "down":
            context.user_data["awaiting_correction"] = {
                "feedback_id": feedback_id,
                "message_id": query.message.message_id if query.message else None,
                "timestamp": datetime.now().isoformat(),
                "is_alert": True,
                "alert_key": alert_key
            }
        
        # Update the message to show feedback received
        emoji = "👍" if feedback_type == "up" else "👎"
        
        # Keep the Ack button but update the feedback row
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✓ Got it", callback_data=f"ack:{alert_key}")],
                [InlineKeyboardButton(f"{emoji} Feedback recorded", callback_data="alert_feedback:done:")]
            ])
        )
        
        logger.info(f"Alert feedback recorded: {feedback_type} for alert {alert_key}")
        
        # If thumbs down, prompt for correction
        if feedback_type == "down" and query.message:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Thanks for the feedback on this alert. What made it unhelpful? (Reply to help me improve, or just send your next message to skip)",
                reply_to_message_id=query.message.message_id
            )
        
    except Exception as e:
        logger.error(f"Error storing alert feedback: {e}")


async def feedback_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /feedback command - show feedback statistics."""
    if not is_authorized(update.effective_user.id):
        return
    
    try:
        from app.services.feedback_store import get_feedback_store
        feedback_store = get_feedback_store()
        
        stats = feedback_store.get_feedback_stats(days=30)
        
        overall = stats["overall"]
        msg = f"📊 *Feedback Stats (Last 30 Days)*\n\n"
        msg += f"*Overall:*\n"
        msg += f"- Total responses rated: {overall['total']}\n"
        msg += f"- 👍 Thumbs up: {overall['thumbs_up']}\n"
        msg += f"- 👎 Thumbs down: {overall['thumbs_down']}\n"
        msg += f"- Approval rate: {overall['approval_rate']}%\n\n"
        
        if stats["by_intent"]:
            msg += "*By Intent:*\n"
            for item in stats["by_intent"][:5]:
                msg += f"- {item['intent']}: {item['approval_rate']}% ({item['total']} ratings)\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    logger.info("Starting Friday Telegram Bot...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("sync", sync_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("feedback", feedback_stats_command))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^(feedback:|ack:|alert_feedback:)"))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))  # Voice messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("✅ Friday Telegram Bot is running!")
    logger.info(f"Authorized user ID: {AUTHORIZED_USER_ID if AUTHORIZED_USER_ID else 'ALL (⚠️ Set TELEGRAM_USER_ID for security!)'}")
    logger.info("Web search enabled with automatic keyword detection")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
