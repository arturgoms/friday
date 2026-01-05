# Friday AI Assistant

**Your Personal AI Assistant with Memory, Tools, and Multi-Channel Communication**

Friday is an intelligent AI assistant built on **Hermes-4-14B** via vLLM, featuring conversation history, channel-agnostic communication, 25+ tools, and an awareness engine for proactive insights.

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Message Flow](#message-flow)
- [Tools](#tools)
- [Services](#services)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

### Core Capabilities
- **🤖 Local LLM**: Runs Hermes-4-14B locally via vLLM (no cloud API needed)
- **💬 Multi-Channel**: Telegram bot with extensible channel system (email, web, CLI coming soon)
- **🧠 Conversation Memory**: Channel-agnostic session tracking with full history persistence
- **🛠️ 25+ Tools**: Calendar, weather, health, system monitoring, vault operations, and more
- **📊 Awareness Engine**: Proactive insights from health data, calendar, homelab metrics etc
- **🗄️ Centralized Database**: SQLite-based storage for conversations, facts, insights, and snapshots
- **🔌 Extensible**: Easy to add new tools, channels, and data collectors

### Intelligence Features
- **Context-Aware**: Maintains conversation history across messages
- **Tool Chaining**: Agent can use multiple tools to answer complex questions
- **Proactive Alerts**: Awareness engine monitors thresholds and sends notifications
- **Smart Scheduling**: Respects quiet hours and daily notification budgets
- **Health Integration**: Garmin data via InfluxDB for health insights

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Friday AI System                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐                                             │
│  │   vLLM      │  ← Hermes-4-14B (localhost:8000)           │
│  │   Server    │                                             │
│  └──────┬──────┘                                             │
│         │                                                     │
│    ┌────┴────────────────────────────┐                      │
│    │                                  │                      │
│  ┌─▼──────────┐              ┌───────▼────────┐            │
│  │  Telegram  │              │   Awareness     │            │
│  │  Interface │              │   Engine        │            │
│  │            │              │                 │            │
│  │  • Recv    │              │ ┌─────────────┐ │            │
│  │  • Agent   │              │ │ Collectors  │ │            │
│  │  • Send    │              │ │ - Health    │ │            │
│  │  • History │              │ │ - Calendar  │ │            │
│  └────────────┘              │ │ - Homelab   │ │            │
│       ▲                      │ │ - Weather   │ │            │
│       │                      │ └─────────────┘ │            │
│       │                      │                 │            │
│       │                      │ ┌─────────────┐ │            │
│       │                      │ │ Analyzers   │ │            │
│       │                      │ │ - Threshold │ │            │
│       │                      │ │ - Calendar  │ │            │
│       │                      │ │ - Journal   │ │            │
│       │                      │ └─────────────┘ │            │
│       │                      │                 │            │
│       │                      │ ┌─────────────┐ │            │
│       │                      │ │ Decision    │ │            │
│       │                      │ │ Engine      │ │            │
│       │                      │ │ - Budget    │ │            │
│       │                      │ │ - Priority  │ │            │
│       │                      │ │ - Quiet hrs │ │            │
│       │                      │ └─────────────┘ │            │
│       │                      │                 │            │
│       └──────────────────────┤ Delivery       │            │
│                              │ Manager         │            │
│                              └─────────────────┘            │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Centralized Database (SQLite)                    │      │
│  │ - conversation_history: Full message history     │      │
│  │ - facts: User knowledge/preferences              │      │
│  │ - insights: Generated observations               │      │
│  │ - snapshots: Point-in-time data captures         │      │
│  │ - deliveries: Notification tracking              │      │
│  │ - reach_out_budget: Daily notification limits    │      │
│  │ - journal_threads: Journal message tracking      │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Agent Tools (25+)                                 │      │
│  │ ✓ Calendar    ✓ Weather     ✓ Health             │      │
│  │ ✓ System      ✓ Memory      ✓ People             │      │
│  │ ✓ Vault       ✓ Web         ✓ Media              │      │
│  │ ✓ Daily Brief ✓ More...                          │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

**1. vLLM Server**
- Serves Hermes-4-14B model on `localhost:8000`
- OpenAI-compatible API
- ~14B parameters, quantized for local inference

**2. Telegram Interface** (`src/interfaces/telegram/`)
- Receives messages from authorized users
- Routes to AI agent with conversation history
- Sends responses back to Telegram

**3. Core Agent** (`src/core/agent.py`)
- Pydantic-AI agent with tool support
- Manages conversation context
- Routes tool calls to appropriate functions

**4. Conversation Manager** (`src/core/conversation.py`)
- Channel-agnostic session tracking
- Persists full conversation history to database
- Loads history for context in each interaction

**5. Tools** (`src/tools/`)
- Modular tool system using `@agent.tool` decorators
- Each tool module auto-registers on import
- Access to session context via dependency injection

**6. Awareness Engine** (`src/awareness/`)
- Collects data from various sources (health, calendar, homelab)
- Generates insights based on thresholds and patterns
- Decision engine determines when to notify user
- Respects quiet hours and daily notification budgets

**7. Database** (`src/core/database.py`)
- Centralized SQLite database
- Schema migration support
- Unified storage for all Friday components

---

## 📦 Prerequisites

### System Requirements
- **OS**: Linux (tested on Ubuntu/Debian)
- **RAM**: 16GB minimum (32GB recommended for vLLM)
- **GPU**: Optional (NVIDIA GPU with CUDA for faster inference)
- **Storage**: 50GB+ free space for models

### Software Dependencies
- **Python**: 3.12+
- **systemd**: For service management
- **SQLite**: 3.x (usually pre-installed)

### Required Python Packages
```bash
# Core dependencies
pydantic-ai>=0.0.14
vllm>=0.6.0
python-telegram-bot>=21.0
logfire
sqlalchemy>=2.0

# Tools
caldav
icalendar
pytz
httpx
influxdb-client

# Optional (for embeddings/knowledge)
sentence-transformers
numpy
```

### External Services (Optional)
- **Telegram Bot**: Token from [@BotFather](https://t.me/BotFather)
- **InfluxDB**: For health data storage (Garmin sync)
- **Google Calendar**: For calendar integration
- **OpenWeatherMap**: For weather data

---

## 🚀 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd friday
```

### 2. Create Virtual Environment
```bash
python3.12 -m venv ~/.local/share/virtualenvs/friday
source ~/.local/share/virtualenvs/friday/bin/activate
```

### 3. Install Dependencies
```bash
pipenv install
```

### 4. Configure Environment
Create `.env` file in project root:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Download Model
The model will be auto-downloaded by vLLM on first start. To pre-download:
```bash
# Using huggingface-cli
huggingface-cli download NousResearch/Hermes-3-Llama-3.1-8B
```

### 6. Initialize Database
```bash
python -c "from src.core.database import Database; Database()"
```

### 7. Install Services
```bash
# Copy service files
cp services/*.service ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Enable services
systemctl --user enable friday-vllm.service
systemctl --user enable friday-telegram.service
systemctl --user enable friday-awareness.service

# Start services
systemctl --user start friday-vllm.service
systemctl --user start friday-telegram.service
systemctl --user start friday-awareness.service
```

### 8. Verify Installation
```bash
# Check service status
systemctl --user status friday-vllm.service
systemctl --user status friday-telegram.service
systemctl --user status friday-awareness.service

# Check logs
tail -f logs/friday-telegram.log
tail -f logs/friday-awareness.log
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

#### Core Settings
```bash
# User Information
USER_NAME=Artur
USER_TIMEZONE=America/Sao_Paulo

# LLM Configuration
LLM_MODEL_NAME=NousResearch/Hermes-4-14B
LLM_BASE_URL=http://localhost:8000/v1
LLM_TEMPERATURE=0.6
LLM_MAX_TOKENS=4096

# Paths
PATHS_ROOT=/home/artur/friday
PATHS_DATA=/home/artur/friday/data
PATHS_LOGS=/home/artur/friday/logs
```

#### Telegram
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_telegram_user_id
```

#### Calendar
```bash
GOOGLE_CALENDAR_ID=your_calendar_id@gmail.com
# OR for Nextcloud CalDAV
NEXTCLOUD_CALDAV_URL=https://your-nextcloud.com/remote.php/dav/
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password
```

#### Weather
```bash
OPENWEATHERMAP_API_KEY=your_api_key
WEATHER_LOCATION=Curitiba,BR
```

#### Health (Optional)
```bash
INFLUXDB_HOST=192.168.1.16
INFLUXDB_PORT=8088
INFLUXDB_DATABASE=GarminStats
```

### Settings File (`settings.py`)

Main configuration is in `settings.py`. Key sections:

**Paths**: Data, logs, vault locations
**User**: Name, timezone, profile
**LLM**: Model, base URL, parameters
**Services**: Telegram, calendar, weather API keys
**Awareness**: Thresholds, quiet hours, notification budgets

---

## 💬 Usage

### Telegram Bot

Send messages to your Friday bot on Telegram. The bot supports:

**Basic Conversation:**
```
You: Hi Friday
Friday: Hello! How can I assist you today?

You: What time is it?
Friday: It's currently 10:36 AM on January 5th, 2026.
```

**Using Tools:**
```
You: What's the weather like?
Friday: The weather in Curitiba is cloudy with a temperature of 20.9°C...

You: What's on my calendar today?
Friday: [Retrieves and displays calendar events]
```

**Memory & Context:**
```
You: My favorite color is blue
Friday: ✅ I'll remember that!

You: What did I just say?
Friday: You said your favorite color is blue.
```

**System Monitoring:**
```
You: Show me system status
Friday: [CPU, memory, disk usage, service status]

You: Check Friday logs
Friday: [Recent log entries from Friday services]
```

### CLI Usage 

Run agent directly:
```bash
python -m src.core.agent "What's the weather?"
```

---

## 🔄 Message Flow

### Incoming Message Flow

```
1. Telegram receives message
   └─> TelegramChannel._handle_text_message()

2. Convert to Message object
   └─> sender_id, content, metadata extracted

3. Call registered handler
   └─> FridayTelegramBot.handle_incoming_message()

4. Get conversation history
   └─> ConversationManager.get_history(session_id)
   └─> Loads previous messages from database

5. Create agent dependencies
   └─> AgentDeps(session_id) for tool context

6. Run AI agent
   └─> agent.run(content, message_history, deps)
   └─> Agent processes with tools & history
   └─> LLM generates response (via vLLM)

7. Extract tool calls (if any)
   └─> Agent may call: weather, calendar, system, etc.
   └─> Tools use ctx.deps.session_id for context

8. Get agent response
   └─> result.output contains final response

9. Update conversation history
   └─> ConversationManager.update_history()
   └─> Persists new messages to database

10. Send response back
    └─> TelegramChannel.send(response)
    └─> Message delivered to Telegram
```

### Awareness Engine Flow

```
1. Engine runs every 10 seconds
   └─> awareness.engine.run()

2. Collect data
   └─> HealthCollector: Garmin metrics from InfluxDB
   └─> CalendarCollector: Upcoming events
   └─> HomelabCollector: Service status checks
   └─> WeatherCollector: Current conditions

3. Save snapshots
   └─> Store point-in-time data in database
   └─> Indexed by collector + timestamp

4. Run analyzers
   └─> ThresholdAnalyzer: Check metric thresholds
   └─> CalendarAnalyzer: Meeting reminders
   └─> JournalAnalyzer: Daily journal prompts

5. Generate insights
   └─> Insight objects with type, priority, message
   └─> Deduplication by dedupe_key

6. Decision engine processes
   └─> Check priority vs current time
   └─> Verify notification budget
   └─> Check quiet hours
   └─> Decide: DELIVER, QUEUE, BATCH, or SKIP

7. Delivery manager
   └─> For DELIVER: Send via Telegram
   └─> For QUEUE: Hold for later
   └─> For SKIP: Log and discard
   └─> Track delivery in database
```

### Tool Execution Flow

```
1. Agent identifies tool is needed
   └─> Based on user query and system prompt

2. Tool function called
   └─> @agent.tool decorator provides ctx
   └─> ctx.deps.session_id available for context

3. Tool executes
   └─> Access database via get_db()
   └─> Use session_id for user-specific data
   └─> Return string result

4. Agent processes tool result
   └─> LLM incorporates result into response
   └─> May call additional tools if needed

5. Final response generated
   └─> Agent returns complete answer
   └─> Includes tool results in natural language
```

---

## 🛠️ Tools

Friday includes 25+ tools across 10 modules:

### Calendar (`src/tools/calendar.py`)
- `get_todays_events()`: Today's schedule
- `get_upcoming_events()`: Future events
- `create_event()`: Add calendar event
- `search_events()`: Find events by query

### Weather (`src/tools/weather.py`)
- `get_current_weather()`: Current conditions
- `get_weather_forecast()`: Multi-day forecast
- `get_weather_alerts()`: Severe weather warnings

### Health (`src/tools/health.py`)
- `get_latest_health_metrics()`: Recent Garmin data
- `get_sleep_data()`: Sleep analysis
- `get_activity_summary()`: Daily activity stats
- `get_heart_rate_data()`: HR trends

### System (`src/tools/system.py`)
- `get_current_time()`: Current time in user timezone
- `get_disk_usage()`: Disk space info
- `get_system_info()`: CPU, memory, OS details
- `get_uptime()`: System uptime
- `get_friday_status()`: Friday services status
- `get_friday_logs()`: Recent log entries
- `get_homelab_status()`: Homelab service checks

### Memory (`src/tools/memory.py`)
- `get_conversation_history()`: Search past messages
- `get_last_user_message()`: Previous user message
- `summarize_conversation()`: Conversation summary

### People (`src/tools/people.py`)
- `list_contacts()`: All contacts
- `get_contact()`: Contact details
- `search_contacts()`: Find people

### Vault (`src/tools/vault.py`)
- `vault_search_notes()`: Search Obsidian vault
- `vault_read_note()`: Read note contents
- `vault_create_note()`: Create new note
- `vault_append_note()`: Add to existing note

### Web (`src/tools/web.py`)
- `web_search()`: DuckDuckGo search
- `fetch_url()`: Get webpage content

### Media (`src/tools/media.py`)
- `media_play()`: Play media on device
- `media_pause()`: Pause playback
- `media_next()`: Next track

### Daily Briefing (`src/tools/daily_briefing.py`)
- `get_morning_briefing()`: Morning summary
- `get_evening_summary()`: Evening recap

---

## 🎛️ Services

### friday-vllm.service

**Purpose**: Serves the LLM model via vLLM

**Location**: `~/.config/systemd/user/friday-vllm.service`

**Key Settings**:
```ini
ExecStart=/home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model NousResearch/Hermes-4-14B \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.95
```

**Commands**:
```bash
systemctl --user start friday-vllm.service
systemctl --user status friday-vllm.service
journalctl --user -u friday-vllm.service -f
```

### friday-telegram.service

**Purpose**: Telegram bot interface

**Location**: `~/.config/systemd/user/friday-telegram.service`

**Key Settings**:
```ini
ExecStartPre=/bin/bash -c 'for i in {1..30}; do curl -s http://localhost:8000/v1/models >/dev/null && exit 0; sleep 3; done; exit 1'
ExecStart=/home/artur/.local/share/virtualenvs/friday/bin/python -m src.interfaces.telegram.run
```

**Logs**: `logs/friday-telegram.log`

### friday-awareness.service

**Purpose**: Proactive insights and notifications

**Location**: `~/.config/systemd/user/friday-awareness.service`

**Key Settings**:
```ini
ExecStart=/home/artur/.local/share/virtualenvs/friday/bin/python -m src.awareness.engine
```

**Logs**: `logs/friday-awareness.log`

---

## 👨‍💻 Development

### Project Structure

```
friday/
├── .env                      # Environment variables
├── settings.py               # Main configuration
├── requirements.txt          # Python dependencies
│
├── src/
│   ├── core/
│   │   ├── agent.py         # Pydantic-AI agent
│   │   ├── conversation.py  # Conversation manager
│   │   ├── database.py      # Database layer
│   │   └── embeddings.py    # Embeddings model
│   │
│   ├── interfaces/          # Communication channels
│   │   ├── base.py          # Base channel class
│   │   ├── manager.py       # Channel manager
│   │   └── telegram/
│   │       ├── channel.py   # Telegram implementation
│   │       └── run.py       # Bot entry point
│   │
│   ├── tools/               # Agent tools (25+)
│   │   ├── calendar.py
│   │   ├── weather.py
│   │   ├── health.py
│   │   ├── system.py
│   │   ├── memory.py
│   │   └── ...
│   │
│   ├── awareness/           # Insights engine
│   │   ├── engine.py        # Main engine
│   │   ├── store.py         # Data storage
│   │   ├── collectors/      # Data collectors
│   │   ├── analyzers/       # Insight generators
│   │   ├── decision/        # Notification logic
│   │   └── delivery/        # Delivery channels
│   │
│   └── utils/
│       └── time.py          # Time utilities
│
├── services/                # Systemd service files
│   ├── friday-vllm.service
│   ├── friday-telegram.service
│   └── friday-awareness.service
│
├── data/                    # Data directory
│   └── friday.db           # SQLite database
│
├── logs/                    # Log files
│   ├── friday-telegram.log
│   └── friday-awareness.log
│
└── README.md               # This file
```

### Adding a New Tool

1. **Create tool file** in `src/tools/`:
```python
# src/tools/my_tool.py
from src.core.agent import agent
import logging

logger = logging.getLogger(__name__)

@agent.tool_plain
def my_function(param: str) -> str:
    """
    Tool description for the LLM.
    
    Args:
        param: Parameter description
        
    Returns:
        Result description
    """
    # Your implementation
    return f"Result: {param}"
```

2. **Import in agent.py**:
```python
# src/core/agent.py
from src.tools import my_tool  # Add to imports
```

3. **Restart service**:
```bash
systemctl --user restart friday-telegram.service
```

### Adding a Tool with Session Context

For tools that need access to user session:

```python
@agent.tool
def my_contextual_tool(ctx, param: str) -> str:
    """Tool with access to session."""
    session_id = ctx.deps.session_id
    
    # Use session_id for user-specific operations
    db = get_db()
    # ... your implementation
    
    return result
```

### Adding a New Communication Channel

1. **Create channel class** in `src/interfaces/`:
```python
from src.interfaces.base import Channel, Message, DeliveryResult

class MyChannel(Channel):
    def __init__(self):
        super().__init__("my_channel")
        
    async def send(self, message: Message) -> DeliveryResult:
        # Implement sending logic
        pass
        
    async def start(self):
        # Start listening for messages
        pass
        
    async def stop(self):
        # Cleanup
        pass
```

2. **Create run script**:
```python
# src/interfaces/my_channel/run.py
from src.core.agent import agent, AgentDeps
from src.core.conversation import get_conversation_manager

class MyChannelBot:
    async def handle_message(self, message: Message):
        session_id = message.sender_id
        history = self.conv_manager.get_history(session_id)
        deps = AgentDeps(session_id=session_id)
        
        result = await agent.run(
            message.content, 
            message_history=history,
            deps=deps
        )
        
        self.conv_manager.update_history(session_id, result.all_messages())
        await self.channel.send(Message(content=result.output))
```

3. **Create systemd service**
4. **Test and deploy**

---

## 🔧 Troubleshooting

### Services Not Starting

**Check vLLM first** (other services depend on it):
```bash
systemctl --user status friday-vllm.service
journalctl --user -u friday-vllm.service -n 50
```

**Common issues**:
- Out of memory: Reduce `--max-model-len` or use smaller model
- CUDA errors: Check GPU drivers, fall back to CPU
- Port already in use: Change port in service file

### Telegram Bot Not Responding

1. **Check service status**:
```bash
systemctl --user status friday-telegram.service
tail -f logs/friday-telegram.log
```

2. **Verify vLLM is running**:
```bash
curl http://localhost:8000/v1/models
```

3. **Check authorization**:
- Verify `TELEGRAM_USER_ID` in `.env` matches your Telegram user ID
- Find your ID by sending `/start` to [@userinfobot](https://t.me/userinfobot)

4. **Check conversation history**:
```bash
sqlite3 data/friday.db "SELECT COUNT(*) FROM conversation_history;"
```

### Tools Not Working

**Check if tool is loaded**:
```bash
grep "Tools loaded successfully" logs/friday-telegram.log
```

**Check for import errors**:
```bash
journalctl --user -u friday-telegram.service | grep -i error
```

**Test tool directly**:
```python
from src.tools.system import get_current_time
print(get_current_time())
```

### Database Issues

**Check database exists**:
```bash
ls -lh data/friday.db
```

**Verify schema**:
```bash
sqlite3 data/friday.db ".schema"
```

**Reset database** (⚠️ deletes all data):
```bash
rm data/friday.db
python -c "from src.core.database import Database; Database()"
```

### Memory/Performance Issues

**Check memory usage**:
```bash
systemctl --user status friday-vllm.service | grep Memory
```

**Reduce vLLM memory**:
Edit `friday-vllm.service`:
```ini
--gpu-memory-utilization 0.8  # Reduce from 0.95
--max-model-len 4096         # Reduce from 8192
```

**Use smaller model**:
```ini
--model NousResearch/Hermes-3-Llama-3.1-8B  # 8B instead of 14B
```

### Awareness Engine Issues

**Check for errors**:
```bash
tail -f logs/friday-awareness.log | grep ERROR
```

**Common issues**:
- Config errors: Check `settings.py` structure
- Database errors: Verify tables exist
- InfluxDB connection: Check `INFLUXDB_*` settings

**Disable awareness temporarily**:
```bash
systemctl --user stop friday-awareness.service
systemctl --user disable friday-awareness.service
```

---

## 📚 Additional Resources

### Documentation
- **Pydantic-AI**: https://ai.pydantic.dev/
- **vLLM**: https://docs.vllm.ai/
- **python-telegram-bot**: https://docs.python-telegram-bot.org/

### Model Information
- **Hermes-4-14B**: https://huggingface.co/NousResearch/Hermes-4-14B
- Fine-tuned for instruction following and function calling

### Community
- Report issues: Create GitHub issue
- Contribute: Pull requests welcome
- Questions: Open discussion

---

## 🙏 Acknowledgments

- **NousResearch** for Hermes models
- **vLLM Team** for fast inference
- **Pydantic** for the amazing Pydantic-AI framework
- **Python Telegram Bot** maintainers

---

## 🗺️ Roadmap

### Current Features
- ✅ Telegram interface with tools
- ✅ Conversation history
- ✅ Awareness engine
- ✅ 25+ tools
- ✅ Health/calendar integration

### Planned
- ⏳ Knowledge tool (vault integration)
- ⏳ Web interface
- ⏳ Voice input/output
- ⏳ Multi-user support
- ⏳ Plugin system
- ⏳ Docker deployment

---

**Built with ❤️ for personal AI assistance**
