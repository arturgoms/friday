# Friday AI - Telegram Bot Setup

## 📱 Quick Setup Guide

### Step 1: Create Your Telegram Bot

1. Open Telegram and message **@BotFather**
2. Send: `/newbot`
3. Choose a name: `Friday AI` (or whatever you like)
4. Choose a username: `your_friday_bot` (must end in 'bot')
5. **Copy the token** you receive (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Telegram User ID

1. Message **@userinfobot** on Telegram
2. It will reply with your user ID (a number like `123456789`)
3. **Copy this number**

### Step 3: Configure Friday

Add these lines to `/home/artur/friday/.env`:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here
FRIDAY_API_URL=http://localhost:8080
```

### Step 4: Test the Bot

```bash
cd /home/artur/friday
pipenv run python telegram_bot.py
```

You should see:
```
✅ Friday Telegram Bot is running!
```

### Step 5: Test on Telegram

1. Find your bot on Telegram (search for the username you created)
2. Send: `/start`
3. You should get a welcome message!
4. Try asking: "What do I know about Python?"

### Step 6: Run as Service (Optional)

Once it's working, set it up to run automatically:

```bash
# Copy service file
sudo cp telegram-bot.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

# Check status
sudo systemctl status telegram-bot
```

## 📋 Available Commands

- **`/start`** - Welcome message and help
- **`/help`** - Show available commands
- **`/remember <text>`** - Save a memory to your Obsidian vault
- **`/sync`** - Trigger Nextcloud file rescan
- **`/stats`** - Show Friday AI statistics

## 💬 Usage Examples

**Ask questions:**
```
You: What do I know about Django?
Friday: Based on your notes, Django is...
```

**Save memories:**
```
You: /remember My new server IP is 192.168.1.100
Friday: ✅ Memory saved!
```

**Check status:**
```
You: /stats
Friday: 📊 Friday AI Status
🤖 LLM: healthy
📝 Chunks: 1018
💾 Memories: 11
```

## 🔒 Security Notes

- **TELEGRAM_USER_ID** restricts the bot to only you
- Keep your **TELEGRAM_BOT_TOKEN** private
- The bot only works locally (Friday API on localhost)
- Consider setting **FRIDAY_API_KEY** for extra security

## 🛠️ Troubleshooting

**Bot doesn't respond:**
```bash
# Check if bot is running
ps aux | grep telegram_bot

# Check logs
tail -f /home/artur/friday/telegram_bot.log

# Check Friday API
curl http://localhost:8080/health
```

**"Unauthorized" message:**
- Make sure TELEGRAM_USER_ID in .env matches your ID
- Restart the bot after changing .env

**Bot is slow:**
- Friday might be processing a large query
- Check Friday logs: `tail -f /home/artur/friday/friday.log`

## 🚀 Next Steps

- ✅ Voice message support (transcribe and send to Friday)
- ✅ Image analysis (send images, Friday describes them)
- ✅ Document upload (add PDFs to your knowledge base)
- ✅ Scheduled reminders
- ✅ Multi-user support (family members)
