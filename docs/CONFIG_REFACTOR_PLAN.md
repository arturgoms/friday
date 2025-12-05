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
