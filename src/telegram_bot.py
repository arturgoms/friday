"""
Friday AI - Telegram Bot Interface
Allows you to interact with Friday AI from your phone via Telegram
"""
import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

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
        "/stats - Show system stats\n\n"
        "*Just send me a message* to ask anything!\n\n"
        "💡 I automatically search the web when you ask about:\n"
        "• Latest/current information\n"
        "• News and updates\n"
        "• General knowledge questions\n"
        "• Weather, stocks, etc.",
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
    except Exception as e:
        logger.error(f"Message handling error: {e}")
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("✅ Friday Telegram Bot is running!")
    logger.info(f"Authorized user ID: {AUTHORIZED_USER_ID if AUTHORIZED_USER_ID else 'ALL (⚠️ Set TELEGRAM_USER_ID for security!)'}")
    logger.info("Web search enabled with automatic keyword detection")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
