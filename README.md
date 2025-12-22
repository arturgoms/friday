# Friday AI Assistant

A self-hosted personal AI assistant with proactive intelligence, health monitoring, persistent memory, and deep Obsidian integration. Designed for privacy-first homelab deployment.

## What It Does

Friday is more than a chatbot—it's a proactive personal assistant that:
- **Anticipates needs** via health, calendar, and pattern monitoring
- **Remembers facts** about you with conflict detection
- **Integrates deeply** with Obsidian, Google Calendar, and Garmin wearables
- **Learns from feedback** to improve over time

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACES                       │
│   Telegram Bot  │  REST API  │  OpenWebUI (OpenAI API)  │
└────────────────────────┬────────────────────────────────┘
                         ▼
              ┌────────────────────┐
              │  Chat Orchestrator │
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │   Intent Router    │  ← Stage 1: Classify (30+ intents)
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │  Handler Registry  │  ← Stage 2: Execute + Respond
              └─────────┬──────────┘
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐
    │ Health  │   │ Calendar │   │ Memory   │
    │ Coach   │   │ Service  │   │ + RAG    │
    └────┬────┘   └────┬─────┘   └────┬─────┘
         ▼              ▼              ▼
    InfluxDB       Google Cal      ChromaDB
    (Garmin)          API         VectorStore
```

**Two-Stage LLM**: Intent classification → Context-aware response generation

## Folder Structure

```
friday/
├── src/
│   ├── main.py                    # FastAPI server entry point
│   ├── telegram_bot.py            # Telegram interface
│   └── app/
│       ├── api/routes.py          # REST endpoints
│       ├── core/config.py         # Configuration (Pydantic)
│       └── services/
│           ├── chat/
│           │   ├── orchestrator.py    # Main chat logic
│           │   └── handlers/          # 12 intent handlers
│           ├── intent/router.py       # Intent classification
│           ├── llm.py                 # vLLM client
│           ├── vector_store.py        # ChromaDB RAG
│           ├── memory_store.py        # Markdown memories
│           ├── health_coach.py        # Garmin/InfluxDB
│           ├── awareness_engine.py    # Proactive monitoring
│           ├── morning_report.py      # Daily briefings
│           └── task_manager.py        # GTD-style tasks
├── data/                          # SQLite DBs, memories
├── config/                        # External service configs
├── scripts/                       # Utility scripts
├── services/                      # systemd unit files
├── tests/                         # Unit + integration tests
└── mcp/                           # MCP server integrations
```

## Capabilities

| Category | Features |
|----------|----------|
| **Chat** | Natural conversation, RAG from Obsidian vault, web search |
| **Memory** | Save/query facts, conflict detection, dual-source search |
| **Calendar** | Query events, find free time, detect conflicts |
| **Tasks** | GTD-style management (priority, context, energy level) |
| **Reminders** | Time-based notifications via Telegram |
| **Notes** | Create/update Obsidian notes, semantic search |
| **Health** | Sleep, HRV, body battery, training readiness (Garmin) |
| **Reports** | Morning (9AM) and evening (11PM) automated briefings |
| **Proactive** | Alerts for health, calendar, weather, deadlines |

## Proactive Monitoring

Runs every 5 minutes via **Awareness Engine**:

- **Health**: Low body battery, poor sleep, high stress (HRV)
- **Calendar**: 30min/5min reminders, conflicts, early morning warnings
- **Tasks**: Overdue and urgent task notifications
- **Weather**: Rain forecasts with umbrella reminders
- **Self-learning**: Extracts dates/commitments from conversations

## Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | vLLM + Qwen2.5-14B-Instruct (local, RTX 3090) |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 |
| **Vector DB** | ChromaDB |
| **Storage** | SQLite (tasks, feedback), Markdown (memories) |
| **Health Data** | InfluxDB (via garmin-db-connect) |
| **API** | FastAPI (OpenAI-compatible endpoints) |
| **Interface** | Telegram Bot, REST API, OpenWebUI |

## Quick Start

```bash
# Install
pipenv install

# Configure
cp .env.example .env
# Edit: FRIDAY_API_KEY, TELEGRAM_BOT_TOKEN, LLM_BASE_URL, etc.

# Run
./scripts/vllm/start_vllm.sh  # Start LLM server
./friday                       # Start Friday
```

## CLI Tool

```bash
./friday status        # Service status
./friday logs friday   # View logs
./friday notify "msg"  # Send Telegram notification
./friday restart all   # Restart services
```

## Key Intents

| Intent | Example |
|--------|---------|
| `memory_save` | "Remember that I prefer dark mode" |
| `calendar_query` | "What's on my calendar tomorrow?" |
| `health_query` | "How did I sleep last night?" |
| `task_create` | "Add a task to buy groceries" |
| `reminder_create` | "Remind me in 30 minutes" |
| `note_create` | "Create a note about project ideas" |
| `web_search` | "Search for Python async best practices" |
| `morning_report` | "Give me my morning briefing" |

## Feedback Loop

Users can thumbs-up/down responses via Telegram. Negative feedback triggers a correction flow, and the system synthesizes learnings to improve future responses.
