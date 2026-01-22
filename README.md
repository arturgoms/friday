# Friday AI Assistant

**Your Personal AI Assistant with Memory, Tools, and Multi-Channel Communication**

Friday is an intelligent AI assistant built on **Hermes-4-14B** via vLLM, featuring conversation history, multi-channel communication, 87 tools, an awareness engine for proactive insights, and a comprehensive CLI for system management.

---

## Table of Contents

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

## Features

### Core Capabilities
- **Local LLM**: Runs Hermes-4-14B locally via vLLM (no cloud API needed)
- **Multi-Channel**: Telegram bot + comprehensive CLI interface
- **Conversation Memory**: Channel-agnostic session tracking with full history persistence
- **87 Tools**: Calendar, weather, health, investments, journal, system monitoring, and more
- **Awareness Engine**: Proactive insights from health data, calendar, portfolio metrics, etc.
- **Centralized Database**: SQLite-based storage for conversations, facts, insights, and snapshots
- **Powerful CLI**: Manage services, execute tools, query database, trigger scheduled reports
- **Journal System**: Daily journal threads with voice transcription and automatic note generation
- **Extensible**: Easy to add new tools, channels, and data collectors

### Intelligence Features
- **Context-Aware**: Maintains conversation history across messages
- **Tool Chaining**: Agent can use multiple tools to answer complex questions
- **Proactive Alerts**: Awareness engine monitors thresholds and sends notifications
- **Smart Scheduling**: Respects quiet hours and daily notification budgets
- **Health Integration**: Garmin data via InfluxDB for comprehensive health insights
- **Portfolio Tracking**: Investment monitoring with DLP API integration
- **Markdown Formatting**: All messages properly formatted for Telegram

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Friday AI System                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐                                            │
│  │   vLLM Server       │  ← Hermes-4-14B (192.168.1.18:8000)       │
│  │   (Remote Machine)  │    OpenAI-compatible API                   │
│  └──────────┬──────────┘                                            │
│             │ HTTP/REST                                             │
│    ┌────────┴────────────────────────────┐                          │
│    │           Friday Host               │                          │
│    │                                     │                          │
│    │  ┌──────────────────────────────┐  │                          │
│    │  │     PM2 Process Manager      │  │                          │
│    │  │                              │  │                          │
│    │  │  ┌────────────┐  ┌─────────────┐ │                         │
│    │  │  │ friday-    │  │ friday-     │ │                         │
│    │  │  │ telegram   │  │ awareness   │ │                         │
│    │  │  │            │  │             │ │                         │
│    │  │  │ • Bot      │  │ • Collectors│ │                         │
│    │  │  │ • Agent    │  │ • Analyzers │ │                         │
│    │  │  │ • History  │  │ • Scheduler │ │                         │
│    │  │  │ • Journal  │  │ • Delivery  │ │                         │
│    │  │  └─────┬──────┘  └──────┬──────┘ │                         │
│    │  │        │                │        │                          │
│    │  │        └────────┬───────┘        │                          │
│    │  │                 │                │                          │
│    │  └─────────────────┼────────────────┘                          │
│    │                    │                                           │
│    │           ┌────────▼────────┐                                  │
│    │           │  Shared Storage │                                  │
│    │           │  • data/        │                                  │
│    │           │  • logs/        │                                  │
│    │           │  • vault/       │                                  │
│    │           └─────────────────┘                                  │
│    │                                                                │
│    │  ┌──────────┐                                                  │
│    │  │   CLI    │  ← ./friday wrapper                             │
│    │  │          │    runs Python directly                         │
│    │  └──────────┘                                                  │
│    └────────────────────────────────────────────────────────────────┘
│                                                                     │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Centralized Database (SQLite)                    │              │
│  │ - conversation_history, facts, insights          │              │
│  │ - snapshots, deliveries, journal_threads         │              │
│  └──────────────────────────────────────────────────┘              │
│                                                                     │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Agent Tools (87 tools across 13 modules)         │              │
│  │ ✓ Calendar     ✓ Weather      ✓ Health           │              │
│  │ ✓ System       ✓ Memory       ✓ People           │              │
│  │ ✓ Vault        ✓ Web          ✓ Media            │              │
│  │ ✓ Daily Brief  ✓ Investments  ✓ Journal          │              │
│  │ ✓ Utils        ✓ Sensors      ✓ Knowledge        │              │
│  └──────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Overview

**1. vLLM Server (Remote)**
- Serves Hermes-4-14B model on remote machine (`192.168.1.18:8000`)
- OpenAI-compatible API
- Keeps GPU workload separate from main server

**2. PM2 Services**
- **friday-telegram**: Telegram bot interface with conversation history
- **friday-awareness**: Proactive insights engine with scheduled reports

**3. CLI Interface**
- `./friday` wrapper runs Python CLI directly
- Full service management (start, stop, restart, logs, status)

**4. Core Agent** (`src/core/agent.py`)
- Pydantic-AI agent with 87 registered tools
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
- Centralized SQLite database
- Schema migration support
- Unified storage for all Friday components

---

## Prerequisites

### System Requirements
- **OS**: Linux (tested on Ubuntu/Debian)
- **Python**: 3.12+
- **RAM**: 4GB minimum (services use ~300MB total)
- **Storage**: 5GB+ free space

### Software Dependencies
- **Node.js**: 18+ (for PM2)
- **PM2**: Process manager (`npm install -g pm2`)
- **Git**: For cloning repository

### System Packages
```bash
# For UPS monitoring (optional)
sudo apt-get install nut-client
```

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

## Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd friday
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

Key variables:
```bash
# LLM Configuration (point to your vLLM server)
LLM_BASE_URL=http://192.168.1.18:8000/v1
LLM_MODEL_NAME=NousResearch/Hermes-4-14B

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_USER_ID=your_user_id

# Vault (Obsidian notes path)
VAULT_PATH=/path/to/your/obsidian/vault
```

### 3. Create Virtual Environment
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Install PM2
```bash
npm install -g pm2
```

### 5. Start Services
```bash
# Start all Friday services
./friday start

# Or use PM2 directly
pm2 start ecosystem.config.js
```

### 6. Setup Auto-Start (Optional)
```bash
pm2 save
pm2 startup
# Follow the instructions to enable auto-start on boot
```

### 7. Verify Installation
```bash
./friday status
```

### Quick Start Summary
```bash
git clone <repository-url>
cd friday
cp .env.example .env
# Edit .env with your settings
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install -g pm2
./friday start
./friday status
```

---

## Configuration

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
PATHS_ROOT=/srv/friday
PATHS_DATA=/srv/friday/data
PATHS_LOGS=/srv/friday/logs
PATHS_VAULT=/path/to/vault
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

---

## Usage

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

## CLI Commands

The Friday CLI provides comprehensive system management:

### Help Output
```
$ ./friday --help

Usage: python -m src.interfaces.cli.run [OPTIONS] COMMAND [ARGS]...

 Friday AI Assistant CLI

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ tool                            Execute a Friday tool directly by name.      │
│ tools                           List all available tools.                    │
│ tool-info                       Show detailed information about a specific   │
│                                 tool including parameters.                   │
│ chat                            Start an interactive chat session with       │
│                                 Friday.                                      │
│ run                             Run a natural language query through         │
│                                 Friday's agent.                              │
│ db-tables                       List all tables in the Friday database.      │
│ db-list                         List rows from any database table.           │
│ db-delete                       Delete rows from any database table.         │
│ db-query                        Execute a raw SQL query.                     │
│ schedule-trigger                Manually trigger a scheduled report.         │
│ schedule-list                   List all scheduled reports with their        │
│                                 configuration.                               │
│ schedule-status                 Show status and details for a specific       │
│                                 scheduled report.                            │
│ journal-generate                Generate a daily journal note for a specific │
│                                 date.                                        │
│ journal-entries                 List journal entries for a specific date.    │
│ journal-add                     Add a journal entry for a specific date.     │
│ status                          Show status of all Friday services, GPU, and │
│                                 tools.                                       │
│ logs                            Tail logs for Friday services.               │
│ start                           Start Friday service(s).                     │
│ stop                            Stop Friday service(s).                      │
│ restart                         Restart Friday service(s).                   │
│ test                            Run Friday test suite.                       │
│ knowledge-rebuild               Rebuild the entire knowledge index from      │
│                                 scratch.                                     │
│ knowledge-stats                 Show statistics about the knowledge index.   │
│ knowledge-search                Search the knowledge index for relevant      │
│                                 content.                                     │
│ knowledge-index-vault           Index vault notes only (incremental).        │
│ knowledge-index-people          Index person profile notes only              │
│                                 (incremental).                               │
│ knowledge-index-conversations   Index conversation history only              │
│                                 (incremental).                               │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Service Management
```bash
# Show service status
./friday status

# Start all services
./friday start

# Stop all services
./friday stop

# Restart all services
./friday restart

# Start/stop/restart specific service
./friday start telegram
./friday stop awareness
./friday restart telegram

# View logs (Friday services only)
./friday logs
./friday logs telegram -n 100
./friday logs --no-follow
```

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

## Tools

Friday includes **87 tools across 13 modules**:

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
- And more...

### Investments (13 tools)
- `get_portfolio()`: Full portfolio
- `get_portfolio_summary()`: Summary stats
- `get_portfolio_history()`: Performance over time
- `get_operations()`: Transaction history
- And more...

### Journal (2 tools)
- `create_daily_journal_thread()`: Create daily thread
- `get_todays_journal_entries()`: Today's entries

### System (5 tools)
- `get_friday_status()`: Service status
- `get_friday_logs()`: Service logs
- `get_friday_disk_usage()`: Disk usage
- `get_friday_memory_usage()`: Memory usage
- `get_friday_uptime()`: System uptime

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

---

## Journal System

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

---

## Scheduled Reports

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

## Services

### PM2 Services

| Service | Process Name | Description |
|---------|--------------|-------------|
| Telegram Bot | `friday-telegram` | Telegram bot interface |
| Awareness Engine | `friday-awareness` | Proactive insights, scheduled reports |

### Remote Service

| Service | Location | Description |
|---------|----------|-------------|
| vLLM | `192.168.1.18:8000` | LLM inference server (Hermes-4-14B) |

### Common Commands

```bash
# Start all services
./friday start

# Stop all services
./friday stop

# Restart services
./friday restart
./friday restart telegram

# View logs
./friday logs
./friday logs telegram -n 100
./friday logs --no-follow

# Check status
./friday status

# PM2 direct commands
pm2 status
pm2 logs
pm2 monit          # Real-time monitoring dashboard
pm2 restart all
```

### Service Details

**friday-telegram**
- Telegram bot with conversation history
- Journal system with voice transcription
- Agent with 87 tools
- Memory: ~140 MB

**friday-awareness**
- Data collectors (health, calendar, portfolio, weather, homelab)
- Insight analyzers (thresholds, calendar, sleep, stress)
- Scheduled reports (morning briefing, evening report, journal)
- Decision engine (quiet hours, notification budgets)
- Memory: ~125 MB

---

## Development

### Project Structure

```
friday/
├── .env                      # Environment variables
├── settings.py               # Main configuration
├── friday                    # CLI wrapper script
├── ecosystem.config.js       # PM2 process configuration
├── requirements.txt          # Python dependencies
├── Pipfile                   # Pipenv dependencies (legacy)
│
├── src/
│   ├── core/
│   │   ├── agent.py         # Pydantic-AI agent (87 tools)
│   │   ├── conversation.py  # Conversation manager
│   │   ├── database.py      # Database layer
│   │   ├── embeddings.py    # Embeddings model
│   │   ├── influxdb.py      # InfluxDB client
│   │   └── vault.py         # Vault operations
│   │
│   ├── interfaces/          # Communication channels
│   │   ├── telegram/        # Telegram bot interface
│   │   │   ├── channel.py
│   │   │   └── run.py       # Entry point
│   │   └── cli/             # CLI interface
│   │       ├── commands.py  # All CLI commands
│   │       └── run.py       # Entry point
│   │
│   ├── tools/               # Agent tools (87 tools)
│   │   ├── calendar.py
│   │   ├── weather.py
│   │   ├── health.py
│   │   ├── investments.py
│   │   ├── journal.py
│   │   ├── system.py
│   │   ├── memory.py
│   │   ├── vault.py
│   │   ├── web.py
│   │   ├── media.py
│   │   ├── people.py
│   │   ├── sensors.py
│   │   └── utils.py
│   │
│   ├── awareness/           # Proactive insights engine
│   │   ├── engine.py        # Main awareness loop
│   │   ├── store.py         # Data persistence
│   │   ├── models.py        # Data models
│   │   ├── analyzers/       # Insight generators
│   │   ├── decision/        # Delivery decision logic
│   │   └── delivery/        # Delivery channels
│   │
│   └── tests/               # Test suite
│
├── data/                    # Data directory
│   └── friday.db           # SQLite database
│
├── logs/                    # Log files
│
└── .venv/                   # Python virtual environment
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
./friday restart
```

4. **Test**:
```bash
./friday tools --search my_function
./friday tool my_function param=test
```

### Adding a Scheduled Report

Scheduled reports run automatically via the awareness engine. They can trigger any tool function at specified times.

1. **Create a tool function** (if needed):
```python
# src/tools/my_module.py
from src.core.agent import agent

@agent.tool_plain
def my_report() -> str:
    """Generate my custom report."""
    # Generate report content
    return "Report content here"
```

2. **Add report configuration in `settings.py`**:
```python
# In AWARENESS["scheduled_reports"] list:
{
    "name": "my_report",                           # Unique identifier
    "tool": "src.tools.my_module.my_report",       # Full import path
    "schedule": "0 9 * * *",                       # Cron: Daily at 9:00 AM
    "enabled": True,                               # Toggle on/off
    "channels": ["telegram"],                      # Delivery channels
    "description": "My custom daily report",       # Human description
}
```

3. **Cron schedule examples**:
```
"0 8 * * *"      # Daily at 8:00 AM
"0 */6 * * *"    # Every 6 hours
"30 9 * * 1"     # Mondays at 9:30 AM
"0 10 * * 1-5"   # Weekdays at 10:00 AM
"50 23 * * *"    # Daily at 11:50 PM
```

4. **Test the report**:
```bash
# Manually trigger
./friday schedule-trigger my_report

# Check status
./friday schedule-status my_report

# List all reports
./friday schedule-list
```

**Note:** Set `channels: []` for silent background tasks (no Telegram message).

---

## Troubleshooting

### Check System Status
```bash
./friday status
```

### Service Issues

**Check PM2 status**:
```bash
pm2 status
pm2 logs friday-telegram --lines 50
pm2 logs friday-awareness --lines 50
```

**Restart services**:
```bash
./friday restart
# Or
pm2 restart friday-telegram friday-awareness
```

**Check process details**:
```bash
pm2 show friday-telegram
pm2 show friday-awareness
```

### vLLM Not Responding

```bash
# Check endpoint
curl http://192.168.1.18:8000/v1/models
```

Verify `LLM_BASE_URL` in `.env` points to your vLLM server.

### Telegram Bot Not Responding

```bash
# Check logs
./friday logs telegram

# Verify environment
cat .env | grep TELEGRAM
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

### Missing Dependencies

```bash
# Reinstall Python dependencies
.venv/bin/pip install -r requirements.txt

# Common missing packages
.venv/bin/pip install sqlalchemy influxdb influxdb-client
```

### Log Files

Logs are stored in two places:
- `logs/friday-telegram.log` and `logs/friday-telegram-error.log`
- `logs/friday-awareness.log` and `logs/friday-awareness-error.log`

```bash
# View logs
./friday logs
tail -f logs/friday-telegram-error.log
```

---

## Additional Resources

- **Pydantic-AI**: https://ai.pydantic.dev/
- **vLLM**: https://docs.vllm.ai/
- **PM2**: https://pm2.keymetrics.io/
- **Hermes-4-14B**: https://huggingface.co/NousResearch/Hermes-4-14B

---

**Built with love for personal AI assistance**
