# Friday 3.0

Personal AI assistant running on local hardware with proactive awareness capabilities.

## Overview

Friday is an autonomous AI platform designed to run on a local Ubuntu server with GPU support. Unlike cloud-based assistants, Friday lives on your infrastructure, has persistent memory through an Obsidian vault, and can proactively reach out with insights and alerts.

### Key Features

- **Local LLM Inference** - Runs Qwen2.5-7B on your RTX 3090 via vLLM
- **Proactive Awareness** - Monitors health metrics, calendar, homelab, and weather
- **Tool Execution** - 44 tools for calendar management, health tracking, system monitoring, and more
- **Telegram Interface** - Chat with Friday from anywhere
- **RAG Integration** - Connects to your Obsidian vault for persistent context
- **Scheduled Reports** - Morning briefings, evening summaries, and weekly analysis

## Architecture

Friday runs as four independent systemd services:

| Service | Port | Description |
|---------|------|-------------|
| `friday-vllm` | 8000 | vLLM inference server with Qwen2.5-7B-Instruct |
| `friday-core` | 8080 | FastAPI brain - routing, tools, RAG |
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
   git clone https://github.com/yourusername/friday.git
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
```

### Telegram

Message your configured Telegram bot to chat with Friday.

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

## External Integrations

- **Garmin** - Health data via InfluxDB (garmin-connect-sync)
- **Google Calendar** - Work calendar (read-only)
- **Nextcloud** - Personal calendar via CalDAV
- **Glances** - Homelab server monitoring
- **OpenWeatherMap** - Weather data

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
