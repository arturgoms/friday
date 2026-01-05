# Telegram Interface

Telegram bot implementation for Friday using the interfaces system.

## Files

```
src/interfaces/telegram/
├── __init__.py       # Module exports
├── channel.py        # TelegramChannel implementation
└── run.py            # Entry point for systemd service
```

## Running as Service

The `run.py` file is the entry point for the systemd service:

```bash
# Start the service
systemctl --user start friday-telegram

# View logs
journalctl --user -u friday-telegram -f
```

## Running Standalone (Development)

```bash
# From project root
python -m src.interfaces.telegram.run

# Or with pipenv
pipenv run python -m src.interfaces.telegram.run
```

## How It Works

```python
User Message (Telegram)
    ↓
TelegramChannel.receive()
    ↓
run.py → handle_incoming_message()
    ↓
agent.run_sync(message)  # Pydantic-AI agent
    ↓
TelegramChannel.send(response)
    ↓
User receives response
```

## Dependencies

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `TELEGRAM_USER_ID` - Your Telegram user ID

Optional:
- `WHISPER_SERVICE_URL` - For voice message transcription

## Architecture

This implementation uses the new interfaces system, which means:
- ✅ Channel-agnostic message handling
- ✅ Easy to add fallback channels
- ✅ Testable with mock channels
- ✅ Consistent with other channels (Email, Slack, etc.)

See `src/interfaces/README.md` for more details on the interfaces system.
