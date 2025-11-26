# Friday AI Test Suite

This directory contains the test suite for Friday AI Assistant, built with pytest.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (fast, no external dependencies)
│   └── test_date_tools.py   # Tests for date/time utilities
└── integration/             # Integration tests (require running API)
    └── test_api_integration.py  # API endpoint tests
```

## Running Tests

### All Tests
```bash
friday test
# or
pytest tests/
```

### Unit Tests Only (Fast)
```bash
friday test unit
# or
pytest -m unit tests/
```

### Integration Tests Only
```bash
friday test integration
# or
pytest -m integration tests/
```

### Specific Test Markers
```bash
pytest -m router tests/      # Intent router tests
pytest -m rag tests/         # RAG/Obsidian tests
pytest -m memory tests/      # Memory system tests
pytest -m time tests/        # Date/time tests
```

### With Coverage
```bash
pytest --cov=src --cov-report=html tests/
```

## Test Categories

### Unit Tests
- **Fast**: Run in milliseconds
- **Isolated**: No external dependencies
- **Pure logic**: Test individual functions and classes

Example: `test_date_tools.py` - Tests date parsing, timezone handling, etc.

### Integration Tests
- **Require API**: Friday service must be running
- **Test real behavior**: Actual HTTP requests and responses
- **Test intent router**: Validates router makes correct decisions
- **Test end-to-end flows**: Memory creation, RAG retrieval, etc.

## Writing New Tests

### Unit Test Template
```python
import pytest

@pytest.mark.unit
class TestMyFeature:
    def test_something(self):
        result = my_function()
        assert result == expected_value
```

### Integration Test Template
```python
import pytest

@pytest.mark.integration
@pytest.mark.rag  # Add specific markers
class TestMyAPIFeature:
    def test_api_endpoint(self, api_client, check_api_running):
        response = api_client.chat("test message")
        assert response["answer"] != ""
```

## Fixtures

### Available Fixtures (from conftest.py)

- **api_client**: HTTP client for making API requests
- **api_base_url**: Base URL (http://localhost:8080)
- **api_key**: Authentication key
- **api_headers**: Common HTTP headers
- **check_api_running**: Ensures API is running before tests
- **test_memory_id**: Creates and cleans up a test memory

## Best Practices

1. **Use markers**: Tag tests with appropriate markers (@pytest.mark.unit, @pytest.mark.integration, etc.)
2. **Test router naturally**: Don't force flags (use_rag, use_memory) - let the router decide
3. **Clean up**: Use fixtures for setup/teardown of test data
4. **Be specific**: Check for actual expected content, not just "any answer"
5. **Fast unit tests**: Keep unit tests under 100ms each
6. **Descriptive names**: Test names should explain what they verify

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```bash
# Fast check (unit only)
pytest -m unit tests/

# Full test suite
pytest tests/ --tb=short
```

## Debugging Failed Tests

### Verbose output
```bash
pytest tests/ -v
```

### Show full traceback
```bash
pytest tests/ --tb=long
```

### Stop on first failure
```bash
pytest tests/ -x
```

### Run specific test
```bash
pytest tests/integration/test_api_integration.py::TestRAGSystem::test_rag_query_triggers_rag -v
```

### Debug with pdb
```bash
pytest tests/ --pdb
```
