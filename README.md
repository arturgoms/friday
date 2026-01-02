# Friday 3.0

Personal AI assistant running on local hardware with proactive awareness capabilities.

## Overview

Friday is an autonomous AI platform designed to run on a local Ubuntu server with GPU support. Unlike cloud-based assistants, Friday lives on your infrastructure, has persistent memory through an Obsidian vault, and can proactively reach out with insights and alerts.

### Key Features

- **Local LLM Inference** - Runs Hermes-3-Llama-3.1-8B on your RTX 3090 via vLLM with native function calling
- **Proactive Awareness** - Monitors health metrics, calendar, homelab, and weather
- **Daily Journal System** - Zero-friction journaling with automatic daily notes in Obsidian
- **Tool Execution** - 49 tools for calendar management, health tracking, system monitoring, conversation memory, and more
- **Conversation Memory as Tools** - History accessed on-demand via tools, preventing context interference
- **Telegram Interface** - Chat with Friday from anywhere (text + voice messages)
- **RAG Integration** - Connects to your Obsidian vault for persistent context
- **Scheduled Reports** - Morning briefings, evening summaries, and weekly analysis

## Documentation

- **[TECHNICAL_FLOW.md](TECHNICAL_FLOW.md)** - Insights Engine: Message flow, sensors, collectors, and delivery system
- **[CORE_VLLM_FLOW.md](CORE_VLLM_FLOW.md)** - Core & vLLM: LLM inference, function calling, RAG, and tool execution
- **[AGENTS.md](AGENTS.md)** - Development guidelines, code conventions, and project structure

## Architecture

Friday runs as four independent systemd services:

| Service | Port | Description |
|---------|------|-------------|
| `friday-vllm` | 8000 | vLLM inference server with Hermes-3-Llama-3.1-8B |
| `friday-core` | 8080 | FastAPI brain - routing, tools, RAG, native function calling |
| `friday-awareness` | - | Insights engine daemon (collectors, analyzers, delivery) |
| `friday-telegram` | - | Telegram bot interface |

```
┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│   Friday Core   │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │   vLLM   │ │ ChromaDB │ │  Tools   │
             │  (GPU)   │ │  (RAG)   │ │ Sensors  │
             └──────────┘ └──────────┘ └──────────┘

┌─────────────────────────────────────────────────┐
│              Friday Awareness                    │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │ Collectors│─▶│ Analyzers │─▶│  Delivery   │  │
│  └───────────┘  └───────────┘  └─────────────┘  │
└─────────────────────────────────────────────────┘
```

## Requirements

- Ubuntu 22.04+ server
- NVIDIA GPU with 24GB VRAM (RTX 3090/4090)
- Python 3.12+
- pipenv

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/arturgoms/friday.git
   cd friday
   ```

2. **Install dependencies**
   ```bash
   pipenv install
   ```

3. **Configure environment**
   ```bash
   cp config.example.yml config.yml
   # Edit config.yml with your settings
   
   # Create .env with secrets
   cat > .env << EOF
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_USER_ID=your_user_id
   FRIDAY_API_KEY=your_api_key
   GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
   INFLUXDB_URL=http://localhost:8086
   INFLUXDB_TOKEN=your_influxdb_token
    INFLUXDB_PASSWORD=your_influxdb_password
    OPENWEATHERMAP_API_KEY=your_api_key
    WHISPER_URL=http://localhost:8001  # Optional: for voice transcription
    EOF
    ```

4. **Install systemd services**
   ```bash
   mkdir -p ~/.config/systemd/user
   cp services/*.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable friday-vllm friday-core friday-awareness friday-telegram
   ```

5. **Start services**
   ```bash
   systemctl --user start friday-vllm
   # Wait for model to load (~30s)
   systemctl --user start friday-core friday-awareness friday-telegram
   ```

## Usage

### CLI

```bash
# Check service status
./friday status

# View logs
./friday logs core
./friday logs vllm

# Interactive chat
./friday chat

# Journal commands
./friday journal-thread          # Send morning journal thread
./friday journal-entries          # View today's entries
./friday journal-entries -f       # Follow entries in real-time
./friday journal-note             # Generate today's daily note
./friday journal-note -d 2025-01-01  # Generate note for specific date

# Knowledge management
./friday facts-list                    # List all saved facts
./friday facts-search <query>          # Search for facts
./friday facts-delete <topic> -y       # Delete specific fact
./friday facts-delete-date 2026-01-02  # Delete facts from date onwards
./friday facts-categories              # Show categories with counts
./friday facts-export -o backup.json   # Export to JSON
```

### Telegram

Message your configured Telegram bot to chat with Friday. Supports both text and voice messages.

**Conversation Memory:**
- History is accessed on-demand via tools, not loaded into context
- Ask "What did I say about X?" → Friday calls `get_conversation_history(query="X")`
- Ask "What was my last message?" → Friday calls `get_last_user_message()`
- This approach prevents history from interfering with function calling while keeping it available when needed

### Daily Journal

Friday includes a zero-friction journaling system that creates structured daily notes in your Obsidian vault:

1. **Morning Thread (10:00 AM)** - Friday sends a Telegram message each morning
2. **Capture Entries** - Reply to the thread with text or voice messages throughout the day
3. **Daily Note (23:59)** - Friday automatically generates a structured markdown note

Daily notes include:
- Weather summary
- Health metrics (sleep, stress, steps) with anomaly detection
- Calendar events from Google and Nextcloud
- Habit tracking (exercise, reading, meditation, etc.)
- Journal entries organized into: Events, Thoughts, Ideas, Concerns, and Reminders
- Automatic extraction of tasks from "Remember to..." entries

All Portuguese entries are automatically translated to English in the final note.

### API

```bash
# Health check
curl http://localhost:8080/health

# Chat endpoint
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"message": "What is the weather like?"}'
```

## Configuration

### Main Config (`config.yml`)

```yaml
server:
  host: 0.0.0.0
  port: 8080

llm:
  base_url: http://localhost:8000/v1
  model: Qwen/Qwen2.5-7B-Instruct

brain:
  vault_path: /path/to/obsidian/vault
```

### Insights Config (`config/insights.json`)

Configure collectors, analyzers, and delivery settings for the awareness engine.

#### Journal Configuration

```json
{
  "journal": {
    "habits": [
      "Read",
      "Exercise",
      "Quality time with wife",
      "Quality time with pets",
      "Play games",
      "Meditation"
    ],
    "health_targets": {
      "min_sleep_hours": 7,
      "max_stress": 40,
      "min_steps": 8000
    }
  }
}
```

## External Integrations

- **Garmin** - Health data via InfluxDB (garmin-connect-sync)
- **Google Calendar** - Work calendar (read-only)
- **Nextcloud** - Personal calendar via CalDAV
- **Glances** - Homelab server monitoring
- **OpenWeatherMap** - Weather data
- **Whisper** - Voice transcription via whisper-asr-webservice

## Development

### Project Structure

```
friday/
├── src/
│   ├── api/           # FastAPI routes
│   ├── core/          # Agent, LLM client, config, shared utilities
│   ├── tools/         # @friday_tool modules
│   ├── sensors/       # @friday_sensor modules
│   └── insights/      # Awareness engine
│       ├── collectors/
│       ├── analyzers/
│       ├── decision/
│       └── delivery/
├── config/            # JSON configurations
├── services/          # Systemd unit files
├── scripts/           # Startup scripts
├── data/              # ChromaDB, SQLite, state files
├── logs/              # Service logs
└── tests/             # Pytest test suite
```

### Adding a Tool

```python
# src/tools/example.py
from src.core.registry import friday_tool

@friday_tool(name="example_tool")
def my_tool(param: str) -> str:
    """Tool description for LLM."""
    return f"Result: {param}"
```

### Adding a Sensor

```python
# src/sensors/example.py
from src.core.registry import friday_sensor

@friday_sensor(name="example_sensor", interval_seconds=300)
def my_sensor() -> dict:
    return {"metric": 42}
```

### Running Tests

```bash
pipenv run pytest tests/ -v
```

## Service Management

```bash
# Status
systemctl --user status friday-core friday-vllm friday-awareness friday-telegram

# Restart all
systemctl --user restart friday-vllm friday-core friday-awareness friday-telegram

# View logs
journalctl --user -u friday-core -f

# Stop all
systemctl --user stop friday-telegram friday-awareness friday-core friday-vllm
```

## Troubleshooting

### vLLM fails to start

Check for zombie GPU processes:
```bash
nvidia-smi
# If stale processes exist:
kill -9 <PID>
systemctl --user restart friday-vllm
```

### LLM unavailable in health check

Wait 30-60 seconds after starting vLLM for the model to load:
```bash
curl http://localhost:8000/v1/models
```

### Service keeps restarting

Check logs for errors:
```bash
journalctl --user -u friday-core --since "5 minutes ago"
```

## License

MIT

## Contributing

See [AGENTS.md](AGENTS.md) for code conventions and development guidelines.
