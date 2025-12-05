# Chat Service Refactoring Plan

## 1. Overview

The `ChatService` class in `src/app/services/chat.py` has grown too large, handling all chat-related logic in a single monolithic class. This makes it difficult to maintain, test, and extend.

This refactoring aims to modularize the chat service by breaking it down into smaller, more manageable components. We will introduce a new pattern where each intent is handled by a dedicated class, making the system more scalable and easier to debug.

## 2. Proposed Architecture

### 2.1. Intent Handlers

We will create a new directory at `src/app/services/chat/handlers` to house our intent handler classes. Each class will be responsible for the logic of a specific intent (e.g., `memory_save`, `note_create`).

All handlers will inherit from a common `IntentHandler` base class:

```python
# src/app/services/chat/handlers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class IntentHandler(ABC):
    """Abstract base class for intent handlers."""

    @abstractmethod
    def handle(self, message: str, session_id: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the intent and return a response."""
        pass
```

### 2.2. Chat Orchestrator

The `ChatService` will be refactored into a `ChatOrchestrator`, which will be responsible for:

-   **Intent Routing**: Determining the user's intent(s). The router will be updated to return a list of intents.
-   **Handler Dispatching**: Instantiating and calling the appropriate handler for each intent.
-   **Conversation Management**: Managing the conversation history.
-   **Response Aggregation**: Collecting results from all handlers and synthesizing them into a final response.

This will significantly reduce the complexity of the main `chat` method.

### 2.3. Handling Multiple Intents

To handle complex user requests that involve multiple actions (e.g., "Set a reminder and check my calendar"), the system will be enhanced as follows:

1.  **Intent Router Enhancement**: The `intent_router` will be modified to return a list of all detected intents, ordered by priority, instead of just a single intent.
2.  **Iterative Dispatch**: The `ChatOrchestrator` will iterate through the list of intents. For each intent, it will invoke the corresponding handler.
3.  **Result Aggregation**: The orchestrator will collect the results from each handler. These results can be direct answers (e.g., from a tool) or context to be passed to the LLM.
4.  **Final Response Generation**: All aggregated results and context will be passed to the final response generation stage (the LLM), which will synthesize them into a single, coherent answer for the user.

This allows Friday to handle multi-part questions gracefully and provide comprehensive responses.

### 2.4. Benefits

-   **Improved Modularity**: Each intent's logic is self-contained.
-   **Easier Maintenance**: Changes to one intent won't affect others.
-   **Better Testability**: Handlers can be tested in isolation.
-   **Enhanced Scalability**: New intents can be added by creating new handler classes.

## 3. Refactoring Steps

1.  **Create Handler Directory**:
    -   `mkdir -p src/app/services/chat/handlers`
    -   `touch src/app/services/chat/handlers/__init__.py`

2.  **Implement Base Handler**:
    -   Create `src/app/services/chat/handlers/base.py` with the `IntentHandler` abstract class.

3.  **Migrate Intent Logic**:
    -   For each intent in `chat.py` (e.g., `memory_save`, `note_create`), create a corresponding handler class in the `handlers` directory.
    -   Move the relevant logic from `chat.py` into the `handle` method of the new class.

4.  **Refactor ChatService**:
    -   Rename `ChatService` to `ChatOrchestrator`.
    -   Update the `chat` method to dispatch intents to the appropriate handlers.

5.  **Update Dependencies**:
    -   Update any parts of the application that use `ChatService` to use the new `ChatOrchestrator` and its handlers.

## 4. Example: `MemorySaveHandler`

```python
# src/app/services/chat/handlers/memory_save.py
from .base import IntentHandler
from app.services.memory_store import MemoryStore

class MemorySaveHandler(IntentHandler):
    def handle(self, message: str, session_id: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        # Logic for saving memories, handling conflicts, etc.
        pass
```

This structured approach will ensure a smooth and effective refactoring process.
