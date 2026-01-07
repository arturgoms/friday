# Friday AI Assistant - Agent Development Guide

This guide is for AI coding agents working on the Friday codebase. It provides essential commands, code style guidelines, and best practices.

---

## 🚀 Quick Commands

### Build & Environment
```bash
# Install dependencies
pipenv install

# Install dev dependencies
pipenv install --dev

# Activate virtual environment
pipenv shell

# Check Python version (requires 3.12)
python --version
```

### Testing
```bash
# Run all tests
pipenv run pytest

# Run tests with coverage
pipenv run pytest --cov=src --cov-report=html

# Run a single test file
pipenv run pytest src/tests/tools/test_memory.py

# Run a specific test function
pipenv run pytest src/tests/tools/test_memory.py::test_get_conversation_history_success

# Run tests matching a pattern
pipenv run pytest -k "test_memory"

# Verbose output with print statements
pipenv run pytest -v -s

# Stop on first failure
pipenv run pytest -x

# Run async tests (already configured with pytest-asyncio)
pipenv run pytest src/tests/
```

### Services
```bash
# Check system status
./friday status

# View logs
./friday logs                    # All services
./friday logs friday-telegram    # Specific service

# Restart services
./friday restart all
./friday restart friday-telegram
```

### Development Tools
```bash
# List all available tools
./friday tools

# Test a tool directly
./friday tool get_current_weather

# Interactive chat for testing
./friday chat

# Database operations
./friday db-list conversation_history --limit 10
./friday db-query "SELECT * FROM facts"
```

---

## 📝 Code Style Guidelines

### General Principles
- **Python 3.12+** syntax and features
- **Type hints** required for all function parameters and return values
- **Docstrings** required for all public functions, classes, and modules
- **Google-style docstrings** with Args, Returns, Raises sections
- **No linters configured** - use common Python best practices

### Module Structure
```python
"""
Module Title - Brief Description

Longer description explaining the module's purpose,
architecture patterns, and usage examples.
"""

import sys
from pathlib import Path

# Add parent directory to path (when needed)
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# Import from settings (always after path setup)
from settings import settings

# Standard library imports
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Third-party imports
from sqlalchemy import text

# Local imports
from src.core.agent import agent
from src.core.database import Database

logger = logging.getLogger(__name__)
```

### Import Ordering
1. **System path manipulation** (if needed)
2. **Settings import** (after path setup)
3. **Standard library** imports (alphabetical)
4. **Third-party library** imports (alphabetical)
5. **Local/project** imports (from src.*)
6. **Logger initialization** at module level

### Naming Conventions
- **Functions**: `snake_case` - e.g., `get_calendar_events()`, `store_fact()`
- **Classes**: `PascalCase` - e.g., `CalendarManager`, `AwarenessEngine`
- **Constants**: `UPPER_SNAKE_CASE` - e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`
- **Private functions**: Prefix with `_` - e.g., `_connect()`, `_initialize_schema()`
- **Tool functions**: Descriptive verbs - e.g., `get_`, `search_`, `report_`, `create_`

### Type Hints
```python
from typing import Any, Dict, List, Optional, Tuple

# Always include return type
def get_recent_runs(limit: int = 10, days: int = 30) -> Dict[str, Any]:
    """Get recent running activities."""
    pass

# Use Optional for nullable values
def find_event(event_id: str) -> Optional[Dict[str, Any]]:
    """Find event by ID, returns None if not found."""
    pass

# Complex types
def process_data(
    items: List[Dict[str, Any]],
    config: Optional[Dict[str, str]] = None
) -> Tuple[bool, str]:
    """Process data items with optional config."""
    pass
```

### Docstrings
```python
def get_sleep_summary(days: int = 7, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get sleep summary for the specified period.
    
    Atomic data tool that returns structured sleep data from InfluxDB.
    Includes sleep score, duration, stages, and recovery metrics.
    
    Args:
        days: Number of days to look back (default: 7)
        date: Optional specific date in YYYY-MM-DD format (default: today)
    
    Returns:
        Dict containing:
            - nights: List of sleep records with scores, duration, stages
            - averages: Average metrics across the period
            - trends: Direction indicators (improving/declining)
    
    Raises:
        ValueError: If date format is invalid
        ConnectionError: If InfluxDB is unavailable
    """
    pass
```

### Error Handling
```python
# Return error dicts for user-facing tools
def get_weather() -> Dict[str, Any]:
    """Get current weather."""
    try:
        data = fetch_weather()
        return {"weather": data}
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return {"error": f"Failed to fetch weather: {str(e)}"}

# Let exceptions bubble for internal functions
def _fetch_from_api(url: str) -> Dict:
    """Internal API fetch (raises on error)."""
    response = httpx.get(url)
    response.raise_for_status()  # Let it raise
    return response.json()
```

---

## 🛠️ Tool Development

### Creating a New Tool
1. Add function to appropriate module in `src/tools/`
2. Use `@agent.tool_plain` decorator for agent-callable tools
3. Import the module in `src/core/agent.py`
4. Restart services

```python
from src.core.agent import agent

@agent.tool_plain
def my_new_tool(param: str) -> Dict[str, Any]:
    """
    Brief description for the LLM to understand when to use this tool.
    
    Args:
        param: Description of parameter
        
    Returns:
        Dict with results or error key
    """
    try:
        result = do_something(param)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool failed: {e}")
        return {"error": str(e)}
```

### Tool Best Practices
- **Return dicts** with clear keys (not raw strings when possible)
- **Include error key** in dict on failures: `{"error": "message"}`
- **Use logger** for debugging, not print statements
- **Accept optional date parameters** as `YYYY-MM-DD` strings, default to None (today)
- **Keep tools atomic** - one clear purpose per tool
- **Make tools stateless** - no instance variables

---

## 🗄️ Database Operations

### Using the Database
```python
from src.core.database import Database

def my_function():
    db = Database()  # Uses settings.PATHS["data"] / "friday.db"
    
    # Query
    results = db.query("SELECT * FROM facts WHERE category = ?", ("health",))
    
    # Insert
    db.insert("facts", {
        "category": "health",
        "subject": "sleep",
        "content": "User sleeps 8 hours average"
    })
    
    # Access row data using ._mapping
    for row in results:
        print(row._mapping['category'])
```

### Testing with Database
```python
import pytest

def test_with_database(test_db):
    """Use test_db fixture for in-memory database."""
    test_db.insert("conversation_history", {
        "conversation_id": "default",
        "timestamp": "2024-01-10T10:00:00",
        "role": "user",
        "content": "Test message"
    })
    
    results = test_db.query("SELECT * FROM conversation_history")
    assert len(results) == 1
```

---

## 🧪 Testing Guidelines

### Test File Organization
- Place tests in `src/tests/` matching source structure
- Name test files `test_<module>.py`
- Use descriptive test names: `test_<function>_<scenario>`

### Test Patterns
```python
def test_success_case(mock_dependency):
    """Test happy path."""
    result = function_under_test()
    assert "expected" in result

def test_error_handling():
    """Test error cases."""
    result = function_with_error()
    assert "error" in result

def test_with_fixtures(test_db, mock_httpx_get):
    """Use fixtures for setup."""
    # Fixtures available: test_db, mock_httpx_get, mock_settings, etc.
    pass
```

### Available Fixtures (see `src/tests/conftest.py`)
- `test_db` - In-memory database
- `populated_test_db` - Database with sample conversation data
- `mock_httpx_get` - Mock HTTP GET requests
- `mock_settings` - Settings object
- `temp_vault_dir` - Temporary vault directory

---

## 🏗️ Architecture Notes

### Key Patterns
- **Channel-based architecture** - All interfaces inherit from `Channel` base class
- **Tool-first design** - Agent has 79 registered tools, no direct code execution
- **Centralized database** - Single `Database` class for all persistence
- **Scheduled reports** - Cron-based scheduling in awareness engine
- **Type safety** - Pydantic-AI with type hints throughout

### Critical Files
- `settings.py` - All configuration (loads from `.env`)
- `src/core/agent.py` - Agent initialization and tool registration
- `src/core/database.py` - Database schema and operations
- `src/awareness/engine.py` - Proactive insights orchestrator
- `src/interfaces/cli/commands.py` - CLI commands (~700 lines)

### Configuration
- Environment: `.env` file at project root
- Settings: `settings.py` (Django-style configuration)
- Services: Systemd user services in `services/`
- Database: SQLite at `data/friday.db`

---

## ⚠️ Important Gotchas

1. **Path setup required** - Most modules need parent directory in sys.path
2. **Import settings after path** - Always set up path before importing settings
3. **SQLAlchemy rows** - Use `._mapping` to access row data as dict
4. **Timezone aware** - Use `settings.TIMEZONE` for datetime operations
5. **Tool decorator** - Use `@agent.tool_plain` NOT `@agent.tool` for simple tools
6. **No amend commits** - Avoid `git commit --amend` unless explicitly requested
7. **Date parameters** - Accept as strings `"YYYY-MM-DD"`, default to None (today)
8. **Return dicts** - Tools should return dicts with clear keys, not raw strings

---

## 📚 Additional Resources

- **Main README**: `/home/artur/friday/README.md` - Full system documentation
- **Interface Guide**: `src/interfaces/README.md` - Channel architecture
- **Settings**: `settings.py` - Configuration reference
- **Test Examples**: `src/tests/tools/` - Well-tested tool examples

---

**When in doubt, follow existing patterns in the codebase. Consistency is key.**
