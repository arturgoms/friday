# Friday AI Assistant

**Your Personal AI Assistant with Memory, Tools, and Multi-Channel Communication**

Friday is an intelligent AI assistant built on **Hermes-4-14B** via vLLM, featuring conversation history, multi-channel communication, 79 tools, an awareness engine for proactive insights, and a comprehensive CLI for system management.

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [CLI Commands](#cli-commands)
- [Tools](#tools)
- [Journal System](#journal-system)
- [Scheduled Reports](#scheduled-reports)
- [Services](#services)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

### Core Capabilities
- **🤖 Local LLM**: Runs Hermes-4-14B locally via vLLM (no cloud API needed)
- **💬 Multi-Channel**: Telegram bot + comprehensive CLI interface
- **🧠 Conversation Memory**: Channel-agnostic session tracking with full history persistence
- **🛠️ 79 Tools**: Calendar, weather, health, investments, journal, system monitoring, and more
- **📊 Awareness Engine**: Proactive insights from health data, calendar, portfolio metrics, etc.
- **🗄️ Centralized Database**: SQLite-based storage for conversations, facts, insights, and snapshots
- **⚡ Powerful CLI**: Manage services, execute tools, query database, trigger scheduled reports
- **📔 Journal System**: Daily journal threads with voice transcription and automatic note generation
- **🔌 Extensible**: Easy to add new tools, channels, and data collectors

### Intelligence Features
- **Context-Aware**: Maintains conversation history across messages
- **Tool Chaining**: Agent can use multiple tools to answer complex questions
- **Proactive Alerts**: Awareness engine monitors thresholds and sends notifications
- **Smart Scheduling**: Respects quiet hours and daily notification budgets
- **Health Integration**: Garmin data via InfluxDB for comprehensive health insights
- **Portfolio Tracking**: Investment monitoring with DLP API integration
- **Markdown Formatting**: All messages properly formatted for Telegram

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
│    ┌────┴────────────────────────────────┐                  │
│    │                                      │                  │
│  ┌─▼──────────┐    ┌──────────┐   ┌─────▼─────────┐       │
│  │  Telegram  │    │   CLI    │   │   Awareness    │       │
│  │ Interface  │    │Interface │   │   Engine       │       │
│  │            │    │          │   │                │       │
│  │  • Recv    │    │• Tools   │   │ ┌────────────┐ │       │
│  │  • Agent   │    │• DB Ops  │   │ │ Collectors │ │       │
│  │  • Send    │    │• Schedule│   │ │ - Health   │ │       │
│  │  • History │    │• Status  │   │ │ - Calendar │ │       │
│  │  • Journal │    │• Logs    │   │ │ - Homelab  │ │       │
│  └────────────┘    └──────────┘   │ │ - Weather  │ │       │
│       ▲                            │ │ - Portfolio│ │       │
│       │                            │ └────────────┘ │       │
│       │                            │                │       │
│       │                            │ ┌────────────┐ │       │
│       │                            │ │ Analyzers  │ │       │
│       │                            │ │ - Threshold│ │       │
│       │                            │ │ - Calendar │ │       │
│       │                            │ └────────────┘ │       │
│       │                            │                │       │
│       │                            │ ┌────────────┐ │       │
│       │                            │ │ Decision   │ │       │
│       │                            │ │ Engine     │ │       │
│       │                            │ │ - Budget   │ │       │
│       │                            │ │ - Priority │ │       │
│       │                            │ │ - Quiet hrs│ │       │
│       │                            │ └────────────┘ │       │
│       │                            │                │       │
│       └────────────────────────────┤ Scheduled    │       │
│                                    │ Reports      │       │
│                                    │ - Journal    │       │
│                                    │ - Briefings  │       │
│                                    └──────────────┘       │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Centralized Database (SQLite)                    │    │
│  │ - conversation_history: Full message history     │    │
│  │ - facts: User knowledge/preferences              │    │
│  │ - insights: Generated observations               │    │
│  │ - snapshots: Point-in-time data captures         │    │
│  │ - deliveries: Notification tracking              │    │
│  │ - journal_threads: Journal message tracking      │    │
│  │ - journal_entries: Daily journal entries         │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Agent Tools (79 tools across 13 modules)         │    │
│  │ ✓ Calendar     ✓ Weather      ✓ Health           │    │
│  │ ✓ System       ✓ Memory       ✓ People           │    │
│  │ ✓ Vault        ✓ Web          ✓ Media            │    │
│  │ ✓ Daily Brief  ✓ Investments  ✓ Journal          │    │
│  │ ✓ Utils        ✓ Sensors                         │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

### Component Overview

**1. vLLM Server**
- Serves Hermes-4-14B model on `localhost:8000`
- OpenAI-compatible API
- ~14B parameters, optimized for local inference

**2. Communication Interfaces**
- **Telegram Interface** (`src/interfaces/telegram/`): Bot interface with conversation history
- **CLI Interface** (`src/interfaces/cli/`): Comprehensive command-line tools

**3. Core Agent** (`src/core/agent.py`)
- Pydantic-AI agent with 79 registered tools
- Manages conversation context
- Auto-snapshot system for data tools

**4. Conversation Manager** (`src/core/conversation.py`)
- Channel-agnostic session tracking
- Persists full conversation history to database

**5. Tools** (`src/tools/`)
- Modular tool system using `@agent.tool` decorators
- 13 modules: calendar, health, investments, journal, weather, vault, etc.
- Auto-registration on import

**6. Awareness Engine** (`src/awareness/`)
- Collects data from health, calendar, portfolio, homelab, weather
- Generates insights based on thresholds
- Decision engine with quiet hours and notification budgets
- Scheduled reports system (journal threads, briefings)

**7. Journal System** (`src/tools/journal.py`)
- Daily thread creation at 8:00 AM
- Voice message transcription via Whisper
- Automatic note generation at 11:50 PM
- Obsidian vault integration

**8. Database** (`src/core/database.py`)
- Centralized SQLite database
- Schema migration support
- Unified storage for all Friday components

---

## 📦 Prerequisites

### System Requirements
- **OS**: Linux (tested on Ubuntu/Debian)
- **RAM**: 16GB minimum (32GB recommended for vLLM)
- **GPU**: NVIDIA GPU with CUDA recommended for faster inference
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
typer
rich

# Tools
caldav
icalendar
pytz
httpx
influxdb-client
openai-whisper

# Optional
sentence-transformers
numpy
```

### External Services (Optional)
- **Telegram Bot**: Token from [@BotFather](https://t.me/BotFather)
- **InfluxDB**: For health data storage (Garmin sync)
- **CalDAV**: For calendar integration (Google/Nextcloud)
- **OpenWeatherMap**: For weather data
- **DLP API**: For investment portfolio tracking

---

## 🚀 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd friday
```

### 2. Install Dependencies
```bash
pipenv install
```

### 3. Configure Environment
Create `.env` file in project root:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Download Model
The model will be auto-downloaded by vLLM on first start.

### 5. Initialize Database
```bash
pipenv run python -c "from src.core.database import Database; Database()"
```

### 6. Install Services
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

### 7. Verify Installation
```bash
# Using CLI
./friday status

# Check logs
./friday logs
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

#### Core Settings
```bash
# User Information
USER_NAME=Artur
USER_TIMEZONE=America/Sao_Paulo
TELEGRAM_USER_ID=your_telegram_user_id

# LLM Configuration
LLM_MODEL_NAME=NousResearch/Hermes-4-14B
LLM_BASE_URL=http://localhost:8000/v1
LLM_TEMPERATURE=0.6
LLM_MAX_TOKENS=4096

# Paths
PATHS_ROOT=/home/artur/friday
PATHS_DATA=/home/artur/friday/data
PATHS_LOGS=/home/artur/friday/logs
PATHS_VAULT=/home/artur/brain
```

#### Telegram
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

#### Calendar (CalDAV)
```bash
NEXTCLOUD_CALDAV_URL=https://your-nextcloud.com/remote.php/dav/
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password
```

#### Weather
```bash
OPENWEATHERMAP_API_KEY=your_api_key
WEATHER_LOCATION=Curitiba,BR
```

#### Health (Garmin/InfluxDB)
```bash
INFLUXDB_HOST=192.168.1.16
INFLUXDB_PORT=8088
INFLUXDB_DATABASE=GarminStats
```

#### Investments
```bash
DLP_API_KEY=your_dlp_api_key
DLP_API_BASE_URL=https://api.dlombelloplanilhas.com
```

### Settings File (`settings.py`)

Main configuration in `settings.py`:
- **Paths**: Data, logs, vault locations
- **User**: Name, timezone, profile, relationships
- **LLM**: Model, base URL, parameters
- **Services**: API keys for external services
- **Awareness**: Thresholds, quiet hours, notification budgets
- **Scheduled Reports**: Journal threads, briefings, note generation

---

## 💬 Usage

### Telegram Bot

Send messages to your Friday bot on Telegram:

**Basic Conversation:**
```
You: Hi Friday
Friday: Hello! How can I assist you today?
```

**Using Tools:**
```
You: What's the weather like?
Friday: The weather in Curitiba is cloudy with a temperature of 24.92°C...

You: What's on my calendar today?
Friday: [Retrieves and displays calendar events]

You: Show my portfolio
Friday: [Displays investment portfolio summary]
```

**Journal Entries:**
```
Daily at 8:00 AM, Friday sends a journal thread.
Reply to the thread throughout the day with:
• Text entries
• Voice messages (auto-transcribed)

At 11:50 PM, Friday compiles into Obsidian note.
```

---

## 🖥️ CLI Commands

The Friday CLI provides comprehensive system management:

### Tool Execution
```bash
# List all tools (grouped by module)
./friday tools

# Search for specific tools
./friday tools --search health

# Get tool details and parameters
./friday tool-info get_sleep_summary

# Execute a tool
./friday tool get_current_weather

# Execute with parameters
./friday tool get_sleep_summary days=7

# Execute and send to Telegram
./friday tool will_it_rain --send telegram
```

### Interactive Chat
```bash
# Start interactive chat session
./friday chat

# One-off query
./friday run "what's the weather?"
```

### Scheduled Reports
```bash
# List all scheduled reports
./friday schedule-list

# Show report details
./friday schedule-status journal_thread

# Manually trigger any report
./friday schedule-trigger journal_thread
./friday schedule-trigger morning_briefing
./friday schedule-trigger generate_daily_journal_note
```

### Database Operations
```bash
# List rows from any table
./friday db-list journal_entries --limit 10
./friday db-list snapshots --where "source='calendar'"

# Execute raw SQL
./friday db-query "SELECT * FROM insights WHERE priority='high'"

# Delete rows
./friday db-delete journal_entries "date='2026-01-05'" --yes
./friday db-delete snapshots "id=123"
```

### System Management
```bash
# Show system status (services, GPU, tools)
./friday status

# View logs
./friday logs                    # All services
./friday logs friday-telegram    # Specific service
./friday logs --no-follow        # Don't follow

# Restart services
./friday restart all
./friday restart friday-telegram
```

---

## 🛠️ Tools

Friday includes **79 tools across 13 modules**:

### Calendar (6 tools)
- `get_calendar_events()`: Upcoming events
- `get_today_schedule()`: Today's schedule
- `add_calendar_event()`: Create event
- `delete_calendar_event()`: Remove event
- `find_free_time()`: Available time slots
- `get_next_event()`: Next upcoming event

### Weather (2 tools)
- `get_current_weather()`: Current conditions
- `get_weather_forecast()`: Multi-day forecast

### Health (14 tools)
- `get_sleep_summary()`: Sleep analysis
- `get_recovery_status()`: Recovery metrics
- `get_body_battery()`: Energy levels
- `get_stress()`: Stress levels
- `get_steps()`: Step count
- `get_recent_runs()`: Running activities
- `get_vo2max()`: VO2 Max trend
- `get_hrv_trend()`: HRV analysis
- `get_heart_rate_summary()`: HR data
- `get_activity_summary()`: Daily activity
- `get_stress_levels()`: Stress patterns
- `report_training_load()`: Training analysis
- `report_weekly_health()`: Weekly summary
- `get_garmin_sync_status()`: Sync status

### Investments (13 tools)
- `get_portfolio()`: Full portfolio
- `get_portfolio_summary()`: Summary stats
- `get_portfolio_history()`: Performance over time
- `get_operations()`: Transaction history
- `get_earnings()`: Dividends/proventos
- `get_darf()`: Tax reports
- `get_irpf()`: Tax reports
- `list_wallets()`: All wallets
- And more...

### Journal (2 tools)
- `create_daily_journal_thread()`: Create daily thread
- `get_todays_journal_entries()`: Today's entries

### Daily Briefing (2 tools)
- `report_morning_briefing()`: Morning summary
- `report_evening_briefing()`: Evening recap

### System (5 tools)
- `get_current_time()`: Current time
- `check_external_service()`: Service monitoring
- `send_notification()`: Send alerts
- `clear_conversation_history()`: Reset history

### Memory (5 tools)
- `search_facts()`: Search knowledge
- `store_fact()`: Save information
- `update_fact()`: Update knowledge
- `delete_fact()`: Remove information
- `list_all_facts()`: All stored facts

### Vault (5 tools)
- `vault_search_notes()`: Search Obsidian
- `vault_read_note()`: Read note
- `vault_create_note()`: Create note
- `vault_write_note()`: Write note
- `vault_append_note()`: Append to note

### Web (3 tools)
- `web_search()`: Search engine
- `web_fetch()`: Fetch webpage
- `web_news()`: News search

### Media (3 tools)
- `generate_image()`: Stable Diffusion
- `generate_speech()`: Text-to-speech
- `transcribe_audio()`: Speech-to-text

### People (2 tools)
- `calculate_age()`: Age calculation
- Birthday tracking

### Utils (11 tools)
- Date calculations
- Time utilities
- Format conversions

---

## 📔 Journal System

Friday includes a comprehensive journal system:

### Daily Flow
1. **8:00 AM**: Friday sends journal thread to Telegram
2. **Throughout day**: Reply to thread with:
   - Text entries (thoughts, notes, events)
   - Voice messages (automatically transcribed)
3. **11:50 PM**: Friday compiles entries into Obsidian note

### Features
- **Voice Transcription**: Whisper automatically transcribes voice messages
- **AI Enhancement**: Translates Portuguese→English, improves clarity
- **Context Integration**: Weather, health metrics, calendar, steps
- **Habit Detection**: Automatically detects habits from entries
- **Markdown Format**: Clean Obsidian-compatible notes
- **Database Tracking**: Thread message IDs saved for reply detection

### Manual Triggers
```bash
# Create journal thread now
./friday schedule-trigger journal_thread

# Generate today's note now
./friday schedule-trigger generate_daily_journal_note

# View entries
./friday db-list journal_entries --where "date='2026-01-07'"
```

### Generated Note Structure
```markdown
---
date: '2026-01-07'
day: Wednesday
habits: [exercise, reading]
sleep: 8.1h
sleep_score: 81
tags: [time/daily, area/friday]
weather: broken clouds, 24°C
---

## Health
- Sleep: 8.1h (score: 81)
- Body Battery: 43%→81%
- Stress: 22
- Training Readiness: 99 (PRIME)
- HRV: 49ms
- Steps: 432

## Calendar
[Your events]

## Journal
### Events
- [Your events from entries]

### Thoughts
- [Your thoughts]

### Reminders
- [Your reminders]
```

---

## 📅 Scheduled Reports

Friday automatically sends reports via Telegram:

| Report | Schedule | Channels | Description |
|--------|----------|----------|-------------|
| `journal_thread` | 8:00 AM daily | Telegram | Daily journal thread |
| `morning_briefing` | 10:00 AM daily | Telegram | Morning summary with health, calendar, weather |
| `evening_report` | 9:00 PM daily | Telegram | Evening recap with sleep recommendation |
| `generate_daily_journal_note` | 11:50 PM daily | None | Compiles journal into Obsidian note |

### Manual Triggers
```bash
# Trigger any report manually
./friday schedule-trigger morning_briefing

# View all scheduled reports
./friday schedule-list

# Check report status
./friday schedule-status morning_briefing
```

---

## 🎛️ Services

### friday-vllm.service
Serves the LLM model via vLLM on `localhost:8000`

**Commands**:
```bash
systemctl --user start friday-vllm.service
systemctl --user status friday-vllm.service
./friday restart friday-vllm
```

### friday-telegram.service
Telegram bot interface

**Logs**: `logs/friday-telegram.log` or `./friday logs friday-telegram`

### friday-awareness.service
Proactive insights, scheduled reports, portfolio monitoring

**Logs**: `logs/friday-awareness.log` or `./friday logs friday-awareness`

---

## 👨‍💻 Development

### Project Structure

```
friday/
├── .env                      # Environment variables
├── settings.py               # Main configuration
├── friday                    # CLI wrapper script
├── Pipfile                   # Pipenv dependencies
├── Pipfile.lock
│
├── src/
│   ├── core/
│   │   ├── agent.py         # Pydantic-AI agent (79 tools)
│   │   ├── conversation.py  # Conversation manager
│   │   ├── database.py      # Database layer
│   │   ├── embeddings.py    # Embeddings model
│   │   ├── influxdb.py      # InfluxDB client
│   │   ├── utils.py         # Core utilities
│   │   └── vault.py         # Vault operations
│   │
│   ├── interfaces/          # Communication channels
│   │   ├── base.py          # Base channel class
│   │   ├── manager.py       # Interface manager
│   │   ├── telegram/        # Telegram bot interface
│   │   │   ├── channel.py   # Telegram channel
│   │   │   └── receiver.py  # Message receiver
│   │   └── cli/             # CLI interface
│   │       ├── channel.py   # CLI channel
│   │       ├── commands.py  # All CLI commands (~700 lines)
│   │       └── run.py       # Entry point
│   │
│   ├── tools/               # Agent tools (79 tools across 16 files)
│   │   ├── calendar.py      # Calendar operations (6 tools)
│   │   ├── weather.py       # Weather data (2 tools)
│   │   ├── health.py        # Garmin/health metrics (14 tools)
│   │   ├── investments.py   # Portfolio tracking (13 tools)
│   │   ├── journal.py       # Journal system (2 tools)
│   │   ├── daily_briefing.py # Morning/evening reports (2 tools)
│   │   ├── system.py        # System monitoring (4 tools)
│   │   ├── memory.py        # Facts/knowledge (5 tools)
│   │   ├── knowledge.py     # Advanced knowledge search
│   │   ├── vault.py         # Obsidian integration (5 tools)
│   │   ├── web.py           # Web search/fetch (3 tools)
│   │   ├── media.py         # Image/speech generation (3 tools)
│   │   ├── people.py        # Contact management (2 tools)
│   │   ├── sensors.py       # Hardware/homelab sensors (10 tools)
│   │   └── utils.py         # Date/time utilities (11 tools)
│   │
│   ├── awareness/           # Proactive insights engine
│   │   ├── engine.py        # Main awareness loop
│   │   ├── store.py         # Data persistence
│   │   ├── models.py        # Data models
│   │   ├── analyzers/       # Insight generators
│   │   │   ├── base.py
│   │   │   ├── calendar.py  # Calendar insights
│   │   │   ├── daily_journal.py # Journal analysis
│   │   │   ├── resources.py # Resource monitoring
│   │   │   ├── sleep.py     # Sleep insights
│   │   │   ├── stress.py    # Stress analysis
│   │   │   └── thresholds.py # Threshold monitoring
│   │   ├── decision/        # Delivery decision logic
│   │   │   ├── budget.py    # Notification budgets
│   │   │   └── engine.py    # Decision engine
│   │   └── delivery/        # Delivery channels
│   │       ├── channels.py  # Channel registry
│   │       ├── loader.py    # Channel loader
│   │       ├── manager.py   # Delivery manager
│   │       └── telegram.py  # Telegram delivery
│   │
│   ├── config/              # Configuration
│   │   └── system_prompts.py # Agent system prompts
│   │
│   ├── utils/               # Shared utilities
│   │   └── time.py          # Time utilities
│   │
│   └── tests/               # Test suite
│       └── ...
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
│   ├── friday-awareness.log
│   └── friday-vllm.log
│
└── brain/                   # Obsidian vault
    └── 2. Time/
        └── 2.2 Daily/       # Daily journal notes (YYYY-MM-DD.md)
```

### Adding a New Tool

1. **Create tool in `src/tools/`**:
```python
from src.core.agent import agent

@agent.tool_plain
def my_function(param: str) -> str:
    """
    Tool description for the LLM.
    
    Args:
        param: Parameter description
        
    Returns:
        Result description
    """
    return f"Result: {param}"
```

2. **Import in `src/core/agent.py`**:
```python
from src.tools import my_module
```

3. **Restart services**:
```bash
./friday restart all
```

4. **Test**:
```bash
./friday tools --search my_function
./friday tool my_function param=test
```

### Adding a Scheduled Report

1. **Add to `settings.py` scheduled_reports**:
```python
{
    "name": "my_report",
    "tool": "src.tools.my_module.my_report_function",
    "schedule": "0 12 * * *",  # Noon daily
    "enabled": True,
    "channels": ["telegram"],
    "description": "My custom report",
}
```

2. **Restart awareness**:
```bash
./friday restart friday-awareness
```

3. **Test manually**:
```bash
./friday schedule-trigger my_report
```

---

## 🔧 Troubleshooting

### Check System Status
```bash
./friday status
```

### Services Not Starting

**Check vLLM first**:
```bash
systemctl --user status friday-vllm.service
```

**Common issues**:
- Out of memory: Reduce `--max-model-len` or `--gpu-memory-utilization`
- CUDA errors: Check GPU drivers
- Port in use: Change port in service file

### Telegram Bot Not Responding

```bash
# Check service
./friday logs friday-telegram

# Verify vLLM
curl http://localhost:8000/v1/models

# Check authorization
# Verify TELEGRAM_USER_ID in .env
```

### Tool Not Found

```bash
# List all tools
./friday tools

# Check if module is imported in agent.py
grep "from src.tools import" src/core/agent.py
```

### Database Issues

```bash
# Check tables
./friday db-query ".schema"

# View recent entries
./friday db-list conversation_history --limit 10
```

### CLI Commands

```bash
# Get help
./friday --help
./friday tool --help
./friday schedule-trigger --help

# Check tool parameters
./friday tool-info <tool-name>
```

---

## 📚 Additional Resources

- **Pydantic-AI**: https://ai.pydantic.dev/
- **vLLM**: https://docs.vllm.ai/
- **Hermes-4-14B**: https://huggingface.co/NousResearch/Hermes-4-14B

---

## 🙏 Acknowledgments

- **NousResearch** for Hermes models
- **vLLM Team** for fast inference
- **Pydantic** for Pydantic-AI framework
- **Python Telegram Bot** maintainers

---

**Built with ❤️ for personal AI assistance**
