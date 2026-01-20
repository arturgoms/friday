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
┌─────────────────────────────────────────────────────────────────────┐
│                         Friday AI System                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────┐                                             │
│  │   vLLM Server       │  ← Hermes-4-14B (192.168.1.18:8000)        │
│  │   (Remote Machine)  │     OpenAI-compatible API                   │
│  └──────────┬──────────┘                                             │
│             │ HTTP/REST                                               │
│    ┌────────┴────────────────────────────────┐                       │
│    │              Docker Host                 │                       │
│    │  ┌──────────────────────────────────┐  │                       │
│    │  │      Docker Compose Stack         │  │                       │
│    │  │                                    │  │                       │
│    │  │  ┌────────────┐  ┌─────────────┐ │  │                       │
│    │  │  │ friday-    │  │ friday-     │ │  │                       │
│    │  │  │ telegram   │  │ awareness   │ │  │                       │
│    │  │  │            │  │             │ │  │                       │
│    │  │  │ • Bot      │  │ • Collectors│ │  │                       │
│    │  │  │ • Agent    │  │ • Analyzers │ │  │                       │
│    │  │  │ • History  │  │ • Scheduler │ │  │                       │
│    │  │  │ • Journal  │  │ • Delivery  │ │  │                       │
│    │  │  └─────┬──────┘  └──────┬──────┘ │  │                       │
│    │  │        │                 │        │  │                       │
│    │  │        └────────┬────────┘        │  │                       │
│    │  │                 │                 │  │                       │
│    │  │        ┌────────▼────────┐        │  │                       │
│    │  │        │  Shared Volumes │        │  │                       │
│    │  │        │  • data/        │        │  │                       │
│    │  │        │  • logs/        │        │  │                       │
│    │  │        │  • vault/       │        │  │                       │
│    │  │        └─────────────────┘        │  │                       │
│    │  └──────────────────────────────────┘  │                       │
│    │                                         │                       │
│    │  ┌──────────┐                          │                       │
│    │  │   CLI    │  ← ./friday wrapper      │                       │
│    │  │ (docker  │     auto-detects Docker  │                       │
│    │  │  exec)   │                          │                       │
│    │  └──────────┘                          │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                       │
│  ┌──────────────────────────────────────────────────┐               │
│  │ Centralized Database (SQLite)                    │               │
│  │ - conversation_history, facts, insights          │               │
│  │ - snapshots, deliveries, journal_threads         │               │
│  └──────────────────────────────────────────────────┘               │
│                                                                       │
│  ┌──────────────────────────────────────────────────┐               │
│  │ Agent Tools (85 tools across 13 modules)         │               │
│  │ ✓ Calendar     ✓ Weather      ✓ Health           │               │
│  │ ✓ System       ✓ Memory       ✓ People           │               │
│  │ ✓ Vault        ✓ Web          ✓ Media            │               │
│  │ ✓ Daily Brief  ✓ Investments  ✓ Journal          │               │
│  │ ✓ Utils        ✓ Sensors      ✓ Knowledge        │               │
│  └──────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Overview

**1. vLLM Server (Remote)**
- Serves Hermes-4-14B model on remote machine (`192.168.1.18:8000`)
- OpenAI-compatible API
- Keeps GPU workload separate from main server

**2. Docker Containers**
- **friday-telegram**: Telegram bot interface with conversation history
- **friday-awareness**: Proactive insights engine with scheduled reports

**3. CLI Interface**
- `./friday` wrapper auto-detects Docker and routes commands
- Runs inside container via `docker exec`

**4. Core Agent** (`src/core/agent.py`)
- Pydantic-AI agent with 85 registered tools
- Manages conversation context
- Auto-snapshot system for data tools

**5. Tools** (`src/tools/`)
- Modular tool system using `@agent.tool` decorators
- 13 modules: calendar, health, investments, journal, weather, vault, etc.
- Auto-registration on import

**6. Awareness Engine** (`src/awareness/`)
- Collects data from health, calendar, portfolio, homelab, weather
- Generates insights based on thresholds
- Decision engine with quiet hours and notification budgets
- Scheduled reports system (journal threads, briefings)

**7. Database** (`src/core/database.py`)
- Centralized SQLite database in shared volume
- Schema migration support
- Unified storage for all Friday components

---

## 📦 Prerequisites

### System Requirements
- **OS**: Linux (tested on Ubuntu/Debian)
- **RAM**: 8GB minimum for Docker host
- **Storage**: 10GB+ free space

### Software Dependencies
- **Docker**: 24.0+ with Docker Compose
- **Git**: For cloning repository

### Remote vLLM Server (separate machine)
- **GPU**: NVIDIA GPU with CUDA
- **RAM**: 32GB+ recommended
- **vLLM**: Running Hermes-4-14B model

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

### 2. Configure Environment
Create `.env` file in project root:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Key variables to configure:
```bash
# LLM Configuration (point to your vLLM server)
LLM_BASE_URL=http://192.168.1.18:8000/v1
LLM_MODEL_NAME=NousResearch/Hermes-4-14B

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_USER_ID=your_user_id

# Vault (Obsidian notes path on host)
VAULT_PATH=/path/to/your/obsidian/vault
```

### 3. Create Docker Network
```bash
# Create the external network (if not exists)
docker network create exposed
```

### 4. Build and Start Services
```bash
# Build images
docker compose build

# Start services
docker compose up -d
```

### 5. Verify Installation
```bash
# Check service status
./friday status

# Check logs
docker compose logs -f
```

### Quick Start Summary
```bash
git clone <repository-url>
cd friday
cp .env.example .env
# Edit .env with your settings
docker network create exposed
docker compose up -d
./friday status
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
# List all database tables
./friday db-tables

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
# Show system status (containers, vLLM, tools)
./friday status

# View logs via Docker
docker compose logs -f                    # All services
docker compose logs -f telegram-bot       # Specific service
docker compose logs --tail=100            # Last 100 lines

# Restart containers
docker compose restart
docker compose restart telegram-bot
```

### Testing
```bash
# Run all tests
./friday test

# Run specific module tests
./friday test health
./friday test sensors

# Run with options
./friday test -v                 # Verbose output
./friday test --cov              # With coverage report
./friday test --failed           # Re-run only failed tests
./friday test -k "none_values"   # Run tests matching keyword
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

### Docker Compose Services

| Service | Container | Description |
|---------|-----------|-------------|
| `telegram-bot` | `friday-telegram` | Telegram bot interface |
| `awareness-engine` | `friday-awareness` | Proactive insights, scheduled reports |

### Remote Service

| Service | Location | Description |
|---------|----------|-------------|
| vLLM | `192.168.1.18:8000` | LLM inference server (Hermes-4-14B) |

### Common Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a specific service
docker compose restart telegram-bot
docker compose restart awareness-engine

# View logs
docker compose logs -f                    # All services
docker compose logs -f telegram-bot       # Specific service
docker compose logs --tail=50 awareness-engine

# Rebuild after code changes
docker compose build && docker compose up -d

# Check status
./friday status
```

### Container Details

**friday-telegram**
- Telegram bot with conversation history
- Journal system with voice transcription
- Agent with 85 tools
- Mounts: `data/`, `logs/`, `vault/`, Docker socket

**friday-awareness**
- Data collectors (health, calendar, portfolio, weather, homelab)
- Insight analyzers (thresholds, calendar, sleep, stress)
- Scheduled reports (morning briefing, evening report, journal)
- Decision engine (quiet hours, notification budgets)
- Mounts: `data/`, `logs/`, `vault/`, Docker socket

---

## 👨‍💻 Development

### Test Coverage

Friday includes a comprehensive test suite with **284 tests** covering all **79 tools**:

```bash
# Run all tests (284 tests in ~60 seconds)
./friday test

# Run specific module
./friday test health      # 41 tests
./friday test sensors     # 35 tests
./friday test investments # 28 tests (all mocked, no real API calls)

# Test statistics
# - Total tools tested: 79/79 (100%)
# - Total tests: 284
# - Pass rate: 100%
# - Execution time: ~60 seconds
```

**Test Modules:**
- ✅ `test_health.py` - Health/Garmin tools (41 tests)
- ✅ `test_daily_briefing.py` - Morning/evening reports (34 tests)
- ✅ `test_sensors.py` - System monitoring (35 tests)
- ✅ `test_investments.py` - Portfolio tracking (28 tests) - **No real API calls**
- ✅ `test_calendar.py` - Calendar operations (27 tests)
- ✅ `test_utils.py` - Date/time utilities (24 tests)
- ✅ `test_media.py` - Image/speech generation (23 tests)
- ✅ `test_people.py` - Contact management (22 tests)
- ✅ `test_journal.py` - Journal system (17 tests)
- ✅ `test_vault.py` - Obsidian integration (11 tests)
- ✅ `test_weather.py` - Weather data (8 tests)
- ✅ `test_system.py` - System tools (7 tests)
- ✅ `test_memory.py` - Facts/knowledge (4 tests)
- ✅ `test_web_tools.py` - Web search (3 tests)

**Key Features:**
- **None-value detection**: Every tool tested for None values in return data
- **Mocked external APIs**: No real API calls during tests (investments, weather, etc.)
- **Fast execution**: All tests run in ~60 seconds
- **100% pass rate**: All tools validated and working

### Project Structure

```
friday/
├── .env                      # Environment variables
├── settings.py               # Main configuration
├── friday                    # CLI wrapper script (auto-detects Docker)
├── Dockerfile                # Container image definition
├── docker-compose.yml        # Service orchestration
├── requirements-docker.txt   # Python dependencies for containers
├── Pipfile                   # Pipenv dependencies (local dev)
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
│   └── tests/               # Test suite (284 tests, 100% coverage)
│       ├── conftest.py      # Shared test fixtures
│       └── tools/           # Tool tests (79 tools tested)
│           ├── test_health.py          # 41 tests
│           ├── test_daily_briefing.py  # 34 tests
│           ├── test_sensors.py         # 35 tests
│           ├── test_investments.py     # 28 tests
│           ├── test_calendar.py        # 27 tests
│           ├── test_utils.py           # 24 tests
│           ├── test_media.py           # 23 tests
│           ├── test_people.py          # 22 tests
│           ├── test_journal.py         # 17 tests
│           ├── test_vault.py           # 11 tests
│           ├── test_weather.py         # 8 tests
│           ├── test_system.py          # 7 tests
│           ├── test_memory.py          # 4 tests
│           └── test_web_tools.py       # 3 tests
│
├── data/                    # Data directory (Docker volume)
│   └── friday.db           # SQLite database
│
├── logs/                    # Log files (Docker volume)
│
└── vault/                   # Obsidian vault (mounted from host)
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

3. **Rebuild and restart containers**:
```bash
docker compose build && docker compose up -d
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

2. **Restart awareness container**:
```bash
docker compose restart awareness-engine
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

### Container Issues

**Check container status**:
```bash
docker compose ps
docker compose logs --tail=50 telegram-bot
docker compose logs --tail=50 awareness-engine
```

**Restart containers**:
```bash
docker compose restart
# Or rebuild if code changed
docker compose build && docker compose up -d
```

**Shell into container**:
```bash
docker exec -it friday-telegram /bin/bash
docker exec -it friday-awareness /bin/bash
```

### vLLM Not Responding

```bash
# Check endpoint from Docker host
curl http://192.168.1.18:8000/v1/models

# Check from inside container
docker exec friday-telegram curl http://192.168.1.18:8000/v1/models
```

Verify `LLM_BASE_URL` in `.env` points to your vLLM server.

### Telegram Bot Not Responding

```bash
# Check logs
docker compose logs -f telegram-bot

# Verify environment
docker exec friday-telegram env | grep TELEGRAM

# Check authorization
# Verify TELEGRAM_USER_ID in .env matches your Telegram user ID
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
./friday db-tables

# View recent entries
./friday db-list conversation_history --limit 10

# Database is at data/friday.db
```

### Permission Issues

If containers can't write to volumes:
```bash
# Check ownership (should be 1000:1000)
ls -la data/ logs/

# Fix if needed
sudo chown -R 1000:1000 data/ logs/
```

### CLI Commands

```bash
# Get help
./friday --help
./friday tool --help
./friday schedule-trigger --help

# Check tool parameters
./friday tool-info <tool-name>

# The CLI auto-detects Docker and runs via docker exec
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
