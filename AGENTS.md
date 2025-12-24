# Friday 3.0 - Autonomous AI Platform

Personal AI assistant running on local Ubuntu server with RTX 3090. Quad-service architecture with vLLM inference, FastAPI core, insights/awareness daemon, and Telegram interface.

## Project Structure

- `src/api/` - FastAPI routes (`/chat`, `/alert`, `/health`)
- `src/core/` - Agent logic, LLM client, RAG, config, registry
- `src/tools/` - Action modules using `@friday_tool` decorator
- `src/sensors/` - Data input modules using `@friday_sensor` decorator
- `src/insights/` - Awareness engine (collectors, analyzers, decision, delivery)
- `src/cli.py` - Typer CLI (`./friday` command)
- `src/telegram_bot.py` - Telegram bot interface
- `config/` - JSON configs (insights.json, etc.)
- `services/` - Systemd user unit files
- `scripts/vllm/` - vLLM startup script
- `data/` - ChromaDB, SQLite (insights.db), state files
- `brain/` - Obsidian vault for RAG context

## Services

| Service | Port | Description |
|---------|------|-------------|
| `friday-vllm` | 8000 | vLLM server (Qwen2.5-7B-Instruct) |
| `friday-core` | 8080 | FastAPI brain - routing, tools, RAG |
| `friday-awareness` | - | Insights engine daemon |
| `friday-telegram` | - | Telegram bot |

All services run as systemd user units in `~/.config/systemd/user/`.

## Code Conventions

### Adding a Tool
```python
# src/tools/example.py
from src.core.registry import friday_tool

@friday_tool(name="tool_name")
def my_tool(param: str, optional: int = 10) -> str:
    """Docstring becomes LLM tool description."""
    return f"Result: {param}"
```

### Adding a Sensor
```python
# src/sensors/example.py
from src.core.registry import friday_sensor

@friday_sensor(name="sensor_name", interval_seconds=300)
def my_sensor() -> dict:
    return {"metric": 42}
```

### Adding an Insight Analyzer
```python
# src/insights/analyzers/example.py
from src.insights.analyzers.base import RealTimeAnalyzer
from src.insights.models import Insight, Priority, Category, InsightType

class MyAnalyzer(RealTimeAnalyzer):
    def __init__(self, config, store):
        super().__init__("analyzer_name", config, store)
    
    def analyze(self, data: dict) -> list[Insight]:
        # Return list of Insight objects
        pass
```

Register analyzers in `src/insights/engine.py` in the `_analyzers` or `_periodic_analyzers` dict.

## Commands

```bash
# Service management
systemctl --user status friday-core friday-vllm friday-awareness friday-telegram
systemctl --user restart friday-core
journalctl --user -u friday-core -f

# CLI
./friday status
./friday logs core
./friday chat

# Testing
pipenv run pytest tests/
```

## Configuration

- **Secrets**: `.env` (API keys, tokens - never commit)
- **Behavior**: `config.yml` (ports, paths, thresholds)
- **Insights**: `config/insights.json` (collectors, analyzers, delivery)

Key env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `FRIDAY_API_KEY`, `GOOGLE_CREDENTIALS_PATH`, `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `OPENWEATHERMAP_API_KEY`

## Timezone

All times use **America/Sao_Paulo (BRT, UTC-3)**. Use the `BRT` timezone from `src/insights/models.py`.

## Important Notes

- Uses `pipenv` for dependencies
- vLLM uses local model cache path in `scripts/vllm/start_vllm.sh` to avoid HuggingFace Hub resolution issues
- Calendar conflict detection excludes all-day events
- Insights alerts use `insights_*` sensor prefix for clean Telegram formatting
- Quiet hours: 22:00-08:00 BRT, max 5 reach-outs/day
- Reports: Morning (10:00), Evening (21:00), Weekly (Sunday 20:00) BRT
- Work calendar (Google) is READ-ONLY

## External Integrations

- Garmin health data via InfluxDB
- Google Calendar (work, read-only) + Nextcloud (personal, CalDAV)
- Glances API for homelab monitoring
- OpenWeatherMap for weather
