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
- `~/friday_facts.db` - Personal facts database (SQLite)
- `~/friday_history.db` - Conversation history (SQLite)

## Services

| Service | Port | Description |
|---------|------|-------------|
| `friday-vllm` | 8000 | vLLM server (Qwen2.5-7B-Instruct) |
| `friday-core` | 8080 | FastAPI brain - routing, tools, RAG |
| `friday-awareness` | - | Insights engine daemon |
| `friday-telegram` | - | Telegram bot |

All services run as systemd user units in `~/.config/systemd/user/`.

## Code Conventions

### Memory & Knowledge Architecture

Friday uses a tool-based approach for both conversation memory and personal knowledge:

#### Conversation Memory (History as a Tool)

**How it works:**
- Conversation history is **NOT** automatically loaded into the LLM context
- History is available through **memory tools** that the model calls when needed
- This keeps the context clean and allows reliable parallel tool calling

**Memory Tools:**
- `get_conversation_history(query, limit)` - Search past messages
- `get_last_user_message()` - Get the user's last message
- `summarize_conversation(messages)` - Get a summary of recent topics

**Why this approach?**
- ✅ Prevents conversation history from breaking native function calling
- ✅ More token-efficient (only loads history when needed)
- ✅ Model decides when history is relevant
- ✅ Supports reliable parallel tool execution

#### Personal Knowledge Graph - Vault Integration

**Architecture:** Vault-first hybrid storage with semantic search

Friday uses Obsidian vault as the **single source of truth** for personal knowledge:

**Storage Strategy:**
- **Simple user attributes** → `brain/1. Notes/Artur Gomes.md` frontmatter (favorite_color, favorite_team, etc.)
- **Facts about people** → Their person notes (`brain/1. Notes/[Name].md`) frontmatter
- **Complex observations** → `brain/1. Notes/Friday.md` sections (behavioral patterns, preferences)
- **Facts DB** → Index/cache with embeddings for semantic search

**Knowledge Tools:**
- `save_fact(topic, value, category)` - Save to appropriate vault location
- `get_fact(topic)` - Read from vault (always fresh)
- `search_facts(query, category)` - Search with semantic fallback
- `search_knowledge(query)` - Search facts + vault notes
- `list_fact_categories()` - List all categories

**How Facts Are Routed:**

| Fact Type | Example | Storage Location | Format |
|-----------|---------|------------------|--------|
| User attribute | favorite_color: black | Artur Gomes.md | Frontmatter field |
| Person fact | wife_birthday: 12/12 | Camila Santos.md | Frontmatter field |
| Observation | workout_preference | Friday.md | Markdown section |

**Auto-save Behavior:**
The model automatically routes facts when you share information:
- "My favorite color is blue" → `Artur Gomes.md` frontmatter: `favorite_color: blue`
- "My wife's birthday is June 12" → `[Wife Name].md` frontmatter: `birthday: 1995-06-12`
- "I prefer morning workouts" → `Friday.md` Health section as bullet point

**Person Notes:**
- Auto-created using template when referencing new people
- Follow Obsidian Operating Manual conventions
- Include tags, relationships, and proper structure
- Automatically linked with `[[Name]]` syntax

**Vector Search:**
- Facts indexed with 384-dim embeddings (sentence-transformers)
- Semantic similarity search with cosine distance
- Min similarity threshold: 0.20
- Enables queries like "family" finding wife_name, wife_birthday, best_friend

**Multi-Step Personal Queries:**
Friday automatically resolves personal references:
- "When is my team playing?" → Retrieves "Cruzeiro Esporte Clube" from vault → Searches web
- "What's my favorite restaurant's address?" → Gets name from vault → Searches web
- Uses **multi-turn tool calling** (max 3 turns) to complete complex requests

**CLI Management:**
```bash
./friday facts-list                    # List all facts
./friday facts-search <query>          # Search with semantic fallback
./friday facts-history <topic>         # Show history of changes
./friday facts-delete <topic> -y       # Delete specific fact
./friday facts-reindex                 # Reindex facts with embeddings
./friday facts-sync                    # Sync vault facts to DB (makes manual edits searchable)
./friday facts-sync --dry-run          # Preview what would be synced
./friday facts-categories              # Show categories
./friday facts-export -o backup.json   # Export to JSON

# Migration (one-time)
python scripts/migrate_facts_to_vault.py --yes
```

**Key Files:**
- `src/core/vault.py` - Vault integration (frontmatter, sections, person notes)
- `src/tools/knowledge.py` - Knowledge tools with vault routing
- `~/friday_facts.db` - Facts index with embeddings and vault references

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

# Knowledge management
./friday facts-list                    # List all facts
./friday facts-search <query>          # Search for facts
./friday facts-delete <topic> -y       # Delete specific fact
./friday facts-delete-date 2026-01-02  # Delete facts from date onwards
./friday facts-categories              # Show categories
./friday facts-export -o backup.json   # Export to JSON

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
- Multi-turn tool calling (max 3 turns) enables complex multi-step queries like "when is my team playing?"

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
