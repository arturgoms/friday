# Friday 3.0 - Autonomous AI Platform

Personal AI assistant running on local Ubuntu server with RTX 3090. Quad-service architecture with vLLM inference, FastAPI core, insights/awareness daemon, and Telegram interface.

## Project Structure

- `src/api/` - FastAPI routes (`/chat`, `/alert`, `/health`)
- `src/core/` - Agent logic, LLM client, RAG, config, registry, shared utilities
  - `constants.py` - Shared constants (BRT timezone)
  - `influxdb.py` - Thread-safe shared InfluxDB client
  - `api_client.py` - Shared HTTP client for Friday API
  - `utils.py` - Common utilities (format_duration, format_pace, etc.)
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
- `tests/` - Pytest test suite with shared fixtures

## Services

| Service | Port | Description |
|---------|------|-------------|
| `friday-vllm` | 8000 | vLLM server (Qwen2.5-7B-Instruct) |
| `friday-core` | 8080 | FastAPI brain - routing, tools, RAG |
| `friday-awareness` | - | Insights engine daemon |
| `friday-telegram` | - | Telegram bot |

All services run as systemd user units in `~/.config/systemd/user/`.

## Code Conventions

### Conversation Memory (History as a Tool)

Friday uses a unique approach to conversation history that prevents interference with native function calling:

**How it works:**
- Conversation history is **NOT** automatically loaded into the LLM context
- History is available through **memory tools** that the model calls when needed
- This keeps the context clean and allows reliable parallel tool calling

**Memory Tools:**
- `get_conversation_history(query, limit)` - Search past messages
- `get_last_user_message()` - Get the user's last message
- `summarize_conversation(messages)` - Get a summary of recent topics

**When the model uses memory tools:**
- User asks: "What did I say about X?" → Calls `get_conversation_history(query="X")`
- User asks: "What was my last message?" → Calls `get_last_user_message()`
- User asks: "What have we discussed?" → Calls `summarize_conversation()`

**Why this approach?**
- ✅ Prevents conversation history from breaking native function calling
- ✅ More token-efficient (only loads history when needed)
- ✅ Model decides when history is relevant
- ✅ Supports reliable parallel tool execution

### Adding a Tool
```python
# src/tools/example.py
from src.core.registry import friday_tool

@friday_tool(name="tool_name")
def my_tool(param: str, optional: int = 10) -> str:
    """Docstring becomes LLM tool description."""
    return f"Result: {param}"
```

**Note:** If your tool needs access to the current session/conversation context, use the thread-local storage:
```python
from src.core.npc_agent import _session_context

def my_tool() -> str:
    session_id = getattr(_session_context, 'session_id', 'default')
    # Use session_id to access session-specific data
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

All times use **America/Sao_Paulo (BRT, UTC-3)**. Use the `BRT` timezone from `src/core/constants.py`.

## Important Notes

- Uses `pipenv` for dependencies
- vLLM uses local model cache path in `scripts/vllm/start_vllm.sh` to avoid HuggingFace Hub resolution issues
- Calendar conflict detection excludes all-day events
- Insights alerts use `insights_*` sensor prefix for clean Telegram formatting
- Quiet hours: 22:00-08:00 BRT, max 5 reach-outs/day
- Reports: Morning (10:00), Evening (21:00), Weekly (Sunday 20:00) BRT
- Work calendar (Google) is READ-ONLY
- Native function calling with `tool_choice='auto'` and `parallel_tool_calls=True`

## External Integrations

- Garmin health data via InfluxDB
- Google Calendar (work, read-only) + Nextcloud (personal, CalDAV)
- Glances API for homelab monitoring
- OpenWeatherMap for weather

## Code Patterns

### Logging Prefixes
Use consistent log prefixes for easier filtering:
- `[AGENT]` - Agent operations
- `[ALERT]` - Alert handling
- `[CHAT]` - Chat requests
- `[DELIVERY]` - Insight delivery
- `[INSIGHTS]` - Insights engine
- `[LLM]` - LLM client
- `[REPORTS]` - Report generation
- `[STORE]` - Database operations
- `[TELEGRAM]` - Telegram bot
- `[TOOL]` - Tool execution

### Thread-Safe Singletons
Use double-check locking for singleton patterns:
```python
_instance = None
_lock = threading.Lock()

def get_instance():
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = create_instance()
    return _instance
```

### Using Shared Modules

**Timezone** - Always import from constants:
```python
from src.core.constants import BRT
```

**InfluxDB** - Use shared client instead of creating connections:
```python
from src.core.influxdb import get_influx_client, query, query_latest, query_time_range
```

**Formatting utilities**:
```python
from src.core.utils import format_duration, format_pace, format_distance, truncate_text, safe_get
```

**API client**:
```python
from src.core.api_client import get_api_url, get_api_headers, FridayAPIClient
```

### Exception Handling
Always catch specific exceptions, never use bare `except:`:
```python
# Good
except ValueError as e:
    logger.error(f"[PREFIX] Specific error: {e}")

# Bad
except:
    pass
```
