# Friday AI Assistant

Personal AI assistant with proactive intelligence, health monitoring, memory, and deep Obsidian integration.

## Features

### Core Intelligence
- **Two-Stage LLM Architecture**: Intent routing + response generation for accurate, efficient responses
- **RAG (Retrieval Augmented Generation)**: Query your Obsidian vault with semantic search
- **Memory System**: Markdown-based memories editable in Obsidian with conflict detection
- **Web Search**: DuckDuckGo integration for current information

### Proactive Intelligence
- **Health Monitoring**: Body Battery, HRV, sleep quality, training readiness alerts
- **Calendar Intelligence**: Upcoming event reminders, conflict detection, early morning warnings
- **Task Tracking**: Overdue and due-today task notifications
- **Weather Alerts**: Rain warnings with umbrella reminders
- **Self-Learning Alerts**: Friday creates alerts from conversations automatically

### Daily Reports
- **Morning Report** (9 AM): Calendar, tasks, sleep, recovery metrics, weather, AI insight
- **Evening Report** (11 PM): Activity summary, body battery, sleep recommendation, tomorrow's preview
- **Weekly Report** (Monday 8 AM): Training summary and fitness analysis
- **On-Demand**: Ask "morning report" or "evening report" anytime

### Integrations
- **Obsidian**: Full vault integration, note creation/update, memory storage
- **Google Calendar**: Event queries, conflict detection
- **Garmin/InfluxDB**: Health metrics from your wearable
- **Telegram**: Chat interface and proactive notifications
- **OpenWeatherMap**: Weather data for reports and alerts

## Architecture

```
friday/
├── src/
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── core/             # Config, logging
│   │   ├── models/           # Pydantic schemas
│   │   └── services/
│   │       ├── chat.py               # Main chat orchestrator
│   │       ├── intent/router.py      # Intent classification
│   │       ├── proactive_monitor.py  # Proactive alerts
│   │       ├── alert_store.py        # Dynamic alert storage
│   │       ├── memory_store.py       # Markdown memory system
│   │       ├── morning_report.py     # Daily briefing
│   │       ├── evening_report.py     # Evening summary
│   │       ├── health_coach.py       # Garmin integration
│   │       ├── calendar_service.py   # Google Calendar
│   │       ├── vector_store.py       # ChromaDB RAG
│   │       └── ...
│   ├── main.py               # FastAPI application
│   └── telegram_bot.py       # Telegram interface
├── brain/                    # Obsidian vault (synced via Syncthing)
│   ├── 1. Notes/             # Your notes
│   └── 5. Friday/
│       ├── 5.0 About/        # Friday's personality
│       ├── 5.1 Memories/     # Stored memories
│       └── 5.2 Alerts/       # Dynamic alerts
├── data/                     # Local data (tasks, reminders)
├── scripts/                  # Utility scripts
└── tests/                    # Test suite
```

## Brain Folder Structure

Friday uses a local `brain/` folder synced via Syncthing:

```
brain/
├── 1. Notes/                 # Your Obsidian vault
│   ├── Artur Gomes.md        # User profile (authoritative source)
│   └── ...
└── 5. Friday/
    ├── 5.0 About/
    │   ├── Who is Friday.md  # Friday's personality
    │   └── Capabilities.md   # What Friday can do
    ├── 5.1 Memories/         # Markdown memory files
    │   └── {id}.md           # Individual memories
    └── 5.2 Alerts/           # Dynamic alerts from conversations
        └── {id}.md           # Alert definitions
```

## Quick Start

### 1. Install Dependencies

```bash
cd /home/artur/friday
pipenv install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

Required environment variables:
- `FRIDAY_API_KEY`: API authentication key
- `LLM_BASE_URL`: vLLM server URL (default: http://localhost:8000/v1)
- `TELEGRAM_BOT_TOKEN`: For Telegram integration
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID
- `WEATHER_API_KEY`: OpenWeatherMap API key
- `WEATHER_CITY`: Your city for weather data

### 3. Start Services

```bash
# Start vLLM
./scripts/vllm/start_vllm.sh

# Start Friday
./run.sh
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8080/health
```

### Chat
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"message": "when is my birthday?"}'
```

### Reports
```bash
# Morning report
curl -X POST http://localhost:8080/chat \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"message": "morning report"}'

# Evening report
curl -X POST http://localhost:8080/chat \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"message": "evening report"}'
```

## Intent Actions

Friday understands these intents:

| Intent | Example | Description |
|--------|---------|-------------|
| `time_query` | "What time is it?" | Current time |
| `calendar_query` | "What's on my calendar?" | Calendar events |
| `reminder_create` | "Remind me in 30 minutes" | Set a reminder |
| `reminder_delete` | "Delete reminder 1" | Remove reminder |
| `memory_save` | "Remember that I like pizza" | Save a fact |
| `health_query` | "How did I sleep?" | Garmin health data |
| `web_search` | "What's the weather?" | Web search |
| `note_create` | "Create a note about..." | New Obsidian note |
| `note_update` | "Add to my note..." | Update existing note |
| `note_get` | "Show my therapy note" | Read note content |
| `morning_report` | "Morning briefing" | Daily morning report |
| `evening_report` | "Evening report" | Daily evening report |
| `general` | "Tell me about..." | General queries with RAG |

## Proactive Monitoring

Friday checks every 5 minutes for:

### Health Alerts
- Body Battery <= 20% (critical energy)
- Training Readiness < 30% (skip workouts)
- HRV 30% below average (stress indicator)
- Sleep score < 50 or < 5 hours
- Recovery time > 48 hours

### Calendar Alerts
- Event in 30 minutes (heads up)
- Event in 5 minutes (urgent)
- Overlapping events (conflicts)
- Early morning event tomorrow (evening warning)

### Task Alerts
- Urgent/high priority tasks due today
- Overdue tasks

### Weather Alerts
- Rain expected in next 6 hours

### Dynamic Alerts (Self-Learning)
Friday creates alerts from conversations:
- Mentioned dates/appointments
- Birthdays
- Health concerns
- Deadlines and commitments

## Memory System

### Saving Memories
- "Remember that my birthday is March 30" → Saved with conflict detection
- "Remember my favorite color is black" → Personalized to "Artur's favorite color is black"

### Conflict Detection
If you try to save conflicting information:
```
⚠️ I found existing memories that might conflict with "Artur's birthday is July 15":
  • "Artur's birthday is March 30"

Would you like me to:
1. Update the existing memory
2. Add anyway (keep both)
```

### Dual Source Search
For personal questions, Friday searches:
1. `Artur Gomes.md` (authoritative profile)
2. `5.1 Memories/` folder (learned facts)

## Hardware

- **GPU**: RTX 3090 24GB running Qwen2.5-7B-Instruct via vLLM
- **Model**: Qwen2.5-7B-Instruct with 16K context
- **Embeddings**: sentence-transformers (CPU)

## Documentation

See `docs/` folder for detailed setup guides:
- `QUICKSTART.md` - Getting started
- `SERVICE_MANAGEMENT.md` - systemd services
- `GOOGLE_CALENDAR_SETUP.md` - Calendar integration
- `TELEGRAM_SETUP.md` - Telegram bot setup
- `HEALTH_COACH.md` - Garmin/InfluxDB setup
- `WEB_SEARCH.md` - Web search configuration
- `TWO_STAGE_ARCHITECTURE.md` - Technical details

## Status

✅ **FULLY OPERATIONAL**
- vLLM running (Qwen2.5-7B-Instruct)
- Friday API on port 8080
- Telegram bot active
- RAG with semantic search
- Memory system with conflict detection
- Proactive monitoring (health, calendar, tasks, weather)
- Self-learning alert system
- Morning/evening reports
- Google Calendar integration
- Garmin health data integration
