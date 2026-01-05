# Friday Communication Interfaces

A unified, extensible system for managing communication channels (Telegram, Email, Slack, etc.).

## Architecture

```
src/interfaces/
├── base.py           # Abstract base classes
├── manager.py        # Channel manager/router
├── telegram/         # Telegram implementation
│   └── channel.py
└── [future channels]
```

## Key Concepts

### 1. **Message** - Channel-agnostic message representation
```python
from src.interfaces import Message, MessageType

message = Message(
    content="Hello from Friday!",
    type=MessageType.TEXT,
    priority=MessagePriority.NORMAL
)
```

### 2. **Channel** - Abstract interface for communication
All channels implement:
- `send(message)` - Send a message
- `start()` - Begin listening for incoming messages
- `stop()` - Stop listening
- `is_available()` - Check if configured
- `register_handler(func)` - Handle incoming messages

### 3. **ChannelManager** - Routes messages between channels
```python
from src.interfaces import ChannelManager
from src.interfaces.telegram import TelegramChannel

# Create manager
manager = ChannelManager()

# Register channels
telegram = TelegramChannel()
manager.register_channel(telegram, is_default=True)

# Send message
result = await manager.send(message)
```

## Usage Examples

### Basic Setup

```python
import asyncio
from src.interfaces import ChannelManager, Message, MessageType
from src.interfaces.telegram import TelegramChannel

async def main():
    # Create manager
    manager = ChannelManager()
    
    # Add Telegram channel
    telegram = TelegramChannel()
    manager.register_channel(telegram, is_default=True)
    
    # Send a message
    message = Message(
        content="Hello! This is Friday.",
        type=MessageType.TEXT
    )
    
    result = await manager.send(message)
    
    if result.success:
        print(f"Message sent! ID: {result.message_id}")
    else:
        print(f"Failed to send: {result.error}")

asyncio.run(main())
```

### Handling Incoming Messages

```python
from src.interfaces import Message

def handle_user_message(message: Message):
    """Process incoming messages from users."""
    print(f"Received from {message.sender_name}: {message.content}")
    
    # Process with AI agent, tools, etc.
    # ...

# Register handler
telegram.register_handler(handle_user_message)

# Start listening
await telegram.start()
```

### Sending Alerts from Awareness Engine

```python
from src.interfaces import Message, MessagePriority

async def send_awareness_alert(title: str, content: str):
    """Send high-priority alert through all channels."""
    message = Message(
        content=f"⚠️ {title}\n\n{content}",
        priority=MessagePriority.URGENT
    )
    
    # Try default channel first, fallback to others if needed
    result = await manager.send(message, use_fallback=True)
    return result
```

### Broadcasting to Multiple Channels

```python
# Send to all available channels
results = await manager.broadcast(message)

for channel_id, result in results.items():
    if result.success:
        print(f"✓ Sent via {channel_id}")
    else:
        print(f"✗ Failed on {channel_id}: {result.error}")
```

### Fallback Strategy

```python
# Configure fallback order: Telegram → Email → Slack
manager.set_fallback_order(['telegram', 'email', 'slack'])

# This will try Telegram first, then Email, then Slack
result = await manager.send(message, use_fallback=True)
```

## Adding New Channels

To add a new channel (e.g., Email, Slack), create a class that inherits from `Channel`:

```python
from src.interfaces.base import Channel, Message, DeliveryResult, MessageType

class EmailChannel(Channel):
    async def send(self, message: Message) -> DeliveryResult:
        # Implement email sending
        pass
    
    async def start(self):
        # Start checking inbox
        pass
    
    async def stop(self):
        # Stop inbox monitoring
        pass
    
    def is_available(self) -> bool:
        # Check if SMTP configured
        return bool(self.config.get('smtp_host'))
    
    def supports_message_type(self, message_type: MessageType) -> bool:
        # Email supports text, images, documents
        return message_type in {
            MessageType.TEXT,
            MessageType.IMAGE,
            MessageType.DOCUMENT
        }
```

## Integration with Awareness Engine

The awareness engine can use channels to deliver insights:

```python
# In awareness/delivery/manager.py
from src.interfaces import ChannelManager, Message, MessagePriority

class DeliveryManager:
    def __init__(self, channel_manager: ChannelManager):
        self.channels = channel_manager
    
    async def deliver_insight(self, insight):
        """Deliver an insight through appropriate channel."""
        message = Message(
            content=self._format_insight(insight),
            priority=self._map_priority(insight.priority)
        )
        
        return await self.channels.send(message)
```

## Testing

Interfaces include proper abstractions for easy testing:

```python
class MockChannel(Channel):
    """Mock channel for testing."""
    
    def __init__(self):
        super().__init__("mock")
        self.sent_messages = []
    
    async def send(self, message: Message) -> DeliveryResult:
        self.sent_messages.append(message)
        return DeliveryResult(success=True, message_id="mock-123")
    
    def is_available(self) -> bool:
        return True
```

## Benefits

1. **Unified API** - Same interface for all channels
2. **Easy Extension** - Add new channels without changing existing code
3. **Fallback Support** - Automatic failover to backup channels
4. **Channel-Agnostic** - Business logic doesn't depend on specific channels
5. **Testing** - Easy to mock and test
6. **Flexibility** - Support multiple channels simultaneously

## Future Channels

Potential channels to add:
- 📧 Email (SMTP/IMAP)
- 💬 Slack
- 📱 Push Notifications (Android/iOS)
- 🔗 Webhooks (generic HTTP endpoints)
- 💻 CLI/Terminal
- 🌐 Web Dashboard (WebSocket)
