# Configuration Refactoring Plan

## 1. Overview

Currently, Friday's configuration is spread across multiple locations:
-   The `src/app/core/config.py` file, which uses Pydantic and loads from environment variables.
-   An `.env` file for environment-specific settings.
-   Hardcoded values (e.g., paths, URLs, magic strings) scattered throughout the codebase.

This makes the application difficult to manage, configure, and deploy in different environments. This plan outlines a refactoring process to create a unified, flexible, and centralized configuration system.

## 2. Proposed Architecture: Layered Configuration

We will implement a layered configuration system that loads settings from multiple sources with a clear order of precedence. This provides both a solid foundation and the flexibility to override settings for different environments (e.g., development, testing, production).

The loading order will be:
1.  **Default Values**: Defined directly in the Pydantic `Settings` class in `config.py`. These serve as the base configuration.
2.  **`config.yml` File**: A YAML file will be introduced to provide a human-readable way to manage the primary configuration. Its values will override the defaults.
3.  **Environment Variables**: Any environment variables (loaded from `.env` or set in the shell) will override values from `config.yml`. This is the highest level of precedence and is ideal for secrets and environment-specific settings.

## 3. Implementation Steps

1.  **Create `config.example.yml`**:
    -   A `config.example.yml` file will be created in the project's root directory.
    -   This file will serve as a template, documenting all available configuration options and their default values.
    -   It will be checked into version control.

2.  **Update `.gitignore`**:
    -   The actual `config.yml` file, which will contain the user's specific settings and secrets, will be added to the `.gitignore` file to prevent it from being committed.

3.  **Refactor the Configuration Loader (`config.py`)**:
    -   The `Settings` class will be updated to use a library like `PyYAML` to read the `config.yml` file.
    -   The loading logic will be implemented to respect the precedence order (Defaults -> YAML -> Env Vars).

4.  **Consolidate Hardcoded Values**:
    -   A systematic search of the codebase will be performed to identify all hardcoded values.
    -   Each hardcoded value will be moved into the `config.example.yml` and the Pydantic `Settings` class.
    -   The code will be refactored to reference the central `settings` object instead of the hardcoded value (e.g., `settings.data.tasks_db_path` instead of `/home/artur/friday/data/tasks.db`).

## 4. Example Snippets

**`config.example.yml`:**
```yaml
# ----------------------------------
# Friday Configuration
# ----------------------------------

# Paths
# All paths should be absolute or relative to the project root.
paths:
  brain: /home/artur/friday/brain
  data: /home/artur/friday/data
  logs: /home/artur/friday/logs

# LLM Service
llm:
  base_url: http://localhost:8000/v1
  model_name: "Qwen/Qwen2.5-14B-Instruct"
  temperature: 0.3

# API Key (can be overridden by environment variable FRIDAY_API_KEY)
auth:
  api_key: "your-secret-key-here"
```

This approach will result in a cleaner, more maintainable, and easily configurable application.

## 5. Testing Strategy

Configuration is foundational—errors here can break everything. Testing must be thorough.

### 5.1. Unit Tests

Create new test files in `tests/unit/`:

-   **`test_config.py`**: Test the configuration loading system.
    -   Test default values are applied correctly.
    -   Test YAML file loading and parsing.
    -   Test environment variable overrides.
    -   Test precedence order (defaults < YAML < env vars).
    -   Test handling of missing `config.yml` file.
    -   Test validation of required fields.
    -   Test handling of invalid YAML syntax.

### 5.2. Test Fixtures

Create fixtures for different configuration scenarios:

```python
@pytest.fixture
def minimal_config_yaml(tmp_path):
    config = tmp_path / "config.yml"
    config.write_text("""
paths:
  brain: /test/brain
llm:
  model_name: "test-model"
""")
    return config

@pytest.fixture
def full_config_yaml(tmp_path):
    # Complete config with all options
    ...
```

### 5.3. Integration Tests

-   **`test_config_integration.py`**: Test that all services correctly use the centralized config.
    -   Test that services start with different configurations.
    -   Test that path references are resolved correctly.

## 6. CLI (`friday` script) Updates

The `friday` CLI will be extended to provide configuration inspection and validation tools.

### 6.1. New Commands

```bash
# Show current configuration (with secrets masked)
friday config show
# Output:
#   paths:
#     brain: /home/artur/friday/brain
#     data: /home/artur/friday/data
#   llm:
#     base_url: http://localhost:8000/v1
#     model_name: Qwen/Qwen2.5-14B-Instruct
#   auth:
#     api_key: ****...****

# Validate configuration file
friday config validate
# Output:
#   ✅ config.yml is valid
#   ✅ All required paths exist
#   ✅ LLM service reachable

# Show where a specific config value comes from
friday config source llm.model_name
# Output:
#   llm.model_name = "Qwen/Qwen2.5-14B-Instruct"
#   Source: config.yml (line 12)

# Generate a config.yml from current settings
friday config generate
# Output: Creates config.yml with current effective settings

# Show differences between config.yml and defaults
friday config diff
# Output: Lists all non-default values
```

### 6.2. Implementation

Add a new `config)` case to the `friday` script:

```bash
config)
    ACTION="${2:-show}"
    case "$ACTION" in
        show)
            # Display current config with masked secrets
            ;;
        validate)
            # Validate config file and dependencies
            ;;
        source)
            KEY="$3"
            # Show source of a specific config value
            ;;
        generate)
            # Generate config.yml from current settings
            ;;
        diff)
            # Show non-default values
            ;;
        *)
            echo "Usage: friday config [show|validate|source|generate|diff]"
            ;;
    esac
    ;;
```
