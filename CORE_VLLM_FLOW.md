# Friday 3.0 - Core & vLLM Technical Documentation

This document explains how the friday-vllm and friday-core services work together to provide LLM-powered chat with function calling, RAG, and tool execution.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [vLLM Service](#vllm-service)
3. [Core Service](#core-service)
4. [Request Flow](#request-flow)
5. [Function Calling](#function-calling)
6. [RAG Integration](#rag-integration)
7. [Conversation History](#conversation-history)
8. [Tool System](#tool-system)
9. [Code Examples](#code-examples)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       USER INTERACTION                           │
│           (Telegram Bot / CLI / API Client)                      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ HTTP POST /chat
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FRIDAY-CORE                                │
│                    (Port 8080 - FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   API Routes │────│  NPC Agent   │────│  Tool System │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                             │                     │              │
│                             │                     │              │
│                      ┌──────┴──────┐       ┌─────┴─────┐        │
│                      │ ChromaDB    │       │ 46 Tools  │        │
│                      │ (RAG)       │       │ - Calendar│        │
│                      │ 500+ docs   │       │ - Health  │        │
│                      └─────────────┘       │ - Vault   │        │
│                                            │ - Weather │        │
│                                            │ - System  │        │
│                                            └───────────┘        │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ OpenAI-compatible API
                                 │ POST /v1/chat/completions
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FRIDAY-VLLM                                │
│                    (Port 8000 - vLLM)                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐       │
│  │   Hermes-3-Llama-3.1-8B (8.03B params)              │       │
│  │   - Native function calling support                 │       │
│  │   - 16K context window                              │       │
│  │   - Hermes tool call parser                         │       │
│  │   - 0.85 GPU memory utilization (20GB / 24GB)       │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Hardware: NVIDIA RTX 3090 (24GB VRAM)                          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Generated Response
                                 │ (Text + Tool Calls)
                                 ▼
                         ┌──────────────┐
                         │  Tool Calls  │
                         │  Executed    │
                         │  Automatically│
                         └──────────────┘
                                 │
                                 ▼
                         ┌──────────────┐
                         │  Final       │
                         │  Response    │
                         │  to User     │
                         └──────────────┘
```

---

## vLLM Service

### Purpose

The vLLM service provides high-performance LLM inference using the vLLM library, which optimizes GPU utilization and throughput for large language models.

### Configuration

**File**: `scripts/vllm/start_vllm.sh`

```bash
#!/bin/bash
cd /home/artur/friday

# Model: Hermes-3-Llama-3.1-8B
# - 8.03B parameters
# - Excellent for function calling
# - 16K context window
MODEL_ID="NousResearch/Hermes-3-Llama-3.1-8B"

exec /home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_ID" \
    --served-model-name "$MODEL_ID" \
    --port 8000 \
    --gpu-memory-utilization 0.85 \           # Use 85% of GPU memory (20GB / 24GB)
    --trust-remote-code \
    --dtype auto \                             # Auto-detect best dtype (bfloat16)
    --max-model-len 16384 \                    # 16K context window
    --enable-auto-tool-choice \                # Enable function calling
    --tool-call-parser hermes                  # Use Hermes tool call format
```

### Model Details

**Hermes-3-Llama-3.1-8B**
- **Base**: Llama 3.1 8B
- **Fine-tune**: Hermes 3 (specialized for function calling)
- **Parameters**: 8.03 billion
- **Context**: 16,384 tokens
- **VRAM Usage**: ~20GB with 85% utilization
- **Format**: Native function calling support via tool call parser

### Performance Characteristics

From logs:

```
INFO 01-02 12:30:13 [kv_cache_utils.py:1229] GPU KV cache size: 30,960 tokens
INFO 01-02 12:30:13 [kv_cache_utils.py:1234] Maximum concurrency for 16,384 tokens per request: 1.89x
INFO 01-02 12:55:43 [loggers.py:236] Engine 000: Avg prompt throughput: 1069.7 tokens/s, Avg generation throughput: 3.6 tokens/s
```

- **Prompt Processing**: ~1,070 tokens/second
- **Generation**: ~3.6 tokens/second
- **Concurrency**: 1.89x (can handle ~2 concurrent requests with full context)

### API Endpoints

vLLM exposes OpenAI-compatible endpoints:

```bash
# Health check
GET http://localhost:8000/health

# List models
GET http://localhost:8000/v1/models

# Chat completions (main endpoint)
POST http://localhost:8000/v1/chat/completions
Content-Type: application/json

{
  "model": "NousResearch/Hermes-3-Llama-3.1-8B",
  "messages": [
    {"role": "system", "content": "You are Friday..."},
    {"role": "user", "content": "What's the weather?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "description": "Get current weather for a location",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {"type": "string"}
          }
        }
      }
    }
  ],
  "tool_choice": "auto",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

### Startup Process

1. **Load Model** (~30 seconds)
   ```
   Loading safetensors checkpoint shards: 100% | 4/4 [00:01<00:00]
   Model loading took 14.9889 GiB memory and 3.190627 seconds
   ```

2. **Compile CUDA Graphs** (~10 seconds)
   ```
   Dynamo bytecode transform time: 2.30 s
   torch.compile takes 5.21 s in total
   ```

3. **Initialize KV Cache**
   ```
   Available KV cache memory: 3.78 GiB
   GPU KV cache size: 30,960 tokens
   ```

4. **Start API Server**
   ```
   Started server process [PID]
   Waiting for application startup.
   Application startup complete.
   ```

Total startup time: **~45 seconds**

### Memory Layout

**RTX 3090 24GB VRAM**:
- **Model Weights**: 14.99 GB
- **KV Cache**: 3.78 GB
- **CUDA Graphs**: ~1.5 GB
- **Overhead**: ~0.3 GB
- **Total**: 20.57 GB (85% utilization)

---

## Core Service

### Purpose

The Core service is the brain of Friday - it handles:
- API routing (FastAPI)
- LLM interaction via npcpy
- Tool registration and execution
- RAG (Retrieval Augmented Generation)
- Conversation history management
- Authentication

### Architecture

**File**: `src/api/routes.py`

```python
# FastAPI Application
app = FastAPI(
    title="Friday 3.0",
    description="Autonomous AI Platform - Core Service",
    version="3.0.0"
)

# Main components initialized at startup:
# 1. Load tools and sensors (46 tools, 15 sensors)
# 2. Initialize ChromaDB vector store (500+ documents)
# 3. Index Obsidian vault if needed
# 4. Initialize NPC agent with litellm
```

### Key Components

#### 1. API Routes

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/health` | GET | Health check, verify LLM available | No |
| `/chat` | POST | Main chat endpoint | Yes |
| `/alert` | POST | Receive alerts from awareness service | Yes |
| `/tools` | GET | List registered tools | Yes |
| `/sensors` | GET | List registered sensors | Yes |
| `/conversation/clear` | POST | Clear conversation history | Yes |
| `/conversation/history` | GET | Get conversation history | Yes |

#### 2. NPC Agent

**File**: `src/core/npc_agent.py`

The agent uses **npcpy** (NPC compiler) which provides:
- Native function calling via litellm
- Automatic conversation history (SQLite)
- Tool execution with retry logic
- Memory management (keeps last 50 messages)

```python
class FridayAgent:
    """Friday agent powered by npcpy with ChromaDB RAG."""
    
    def __init__(self):
        # Initialize NPC with 46 tools
        self.npc = NPC(
            name='Friday',
            primary_directive=self._build_base_system_prompt(),
            model=f'openai/{config.llm.model_name}',  # Points to vLLM
            provider='openai',
            tools=self.tools,  # 46 function tools
            db_conn=db_engine,  # SQLite for history
            use_global_jinxs=False,
        )
        
        # Configure memory
        self.npc.memory_length = 50  # Keep last 50 messages
        self.npc.memory_strategy = 'recent'
```

#### 3. Tool System

Tools are Python functions decorated with `@friday_tool`:

```python
from src.core.registry import friday_tool

@friday_tool(name="get_current_weather")
def get_current_weather(location: str = "Curitiba") -> str:
    """Get current weather for a location.
    
    Args:
        location: City name (default: Curitiba)
    """
    # Implementation...
    return f"Temperature: 25°C, Conditions: Clear"
```

**46 Tools Available**:

| Category | Tools | Examples |
|----------|-------|----------|
| **Calendar** (6) | Events, schedule, free time | `get_calendar_events`, `add_calendar_event` |
| **Health** (11) | Garmin data, runs, sleep, HRV | `get_recent_runs`, `get_sleep_summary` |
| **Vault** (11) | Obsidian notes management | `vault_read_note`, `vault_search_notes` |
| **Weather** (3) | Current, forecast, rain | `get_current_weather`, `will_it_rain` |
| **System** (7) | Homelab, logs, status | `get_friday_status`, `get_homelab_status` |
| **Web** (3) | Search, fetch, news | `web_search`, `web_fetch` |
| **Media** (2) | Image generation, TTS | `generate_image`, `generate_speech` |
| **Daily Briefing** (2) | Morning/evening reports | `get_morning_report` |

#### 4. ChromaDB RAG

**File**: `src/core/vector_store.py`

Vector store for semantic search over Obsidian vault:

```python
class ChromaDBVectorStore:
    """ChromaDB-backed vector store for RAG."""
    
    def __init__(self, persist_directory: str):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="friday_brain",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        )
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Semantic search for relevant documents."""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        # Returns documents with similarity scores
```

**Stats**:
- **Documents**: 500+ from Obsidian vault
- **Embedding Model**: all-MiniLM-L6-v2 (384 dimensions)
- **Chunk Size**: 1000 tokens
- **Overlap**: 200 tokens

---

## Request Flow

### Complete Chat Request Trace

Let's trace a user asking "What's the weather?"

#### 1. User Sends Message

```bash
# From Telegram bot or CLI
POST http://localhost:8080/chat
{
  "text": "What's the weather?",
  "user_id": "111514095",
  "session_id": "111514095"
}
```

#### 2. Core API Receives Request

**File**: `src/api/routes.py:293`

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, authorized: bool = Depends(verify_api_key)):
    """Main chat endpoint."""
    
    # Log request
    logger.info(f"[CHAT] Request from user={request.user_id}: {request.text}")
    
    # Get agent
    agent = get_agent()
    
    # Clear conversation if fresh=True (for CLI single queries)
    if request.fresh:
        agent.clear_conversation(request.session_id or request.user_id)
    
    # Get response from agent
    response = agent.chat(
        message=request.text,
        session_id=request.session_id or request.user_id,
        user_id=request.user_id,
        enable_rag=True
    )
    
    # Return response
    return ChatResponse(
        text=response.get('text', ''),
        mode=response.get('mode', 'chat'),
        tool_results=response.get('tool_results', []),
        iterations=1
    )
```

**Log Output**:
```
2026-01-02 09:55:32 [INFO] friday: [CHAT] Request from user=111514095: What's the weather?
```

#### 3. Agent Processes Message

**File**: `src/core/npc_agent.py:286`

```python
def chat(self, message: str, session_id: str, user_id: str, enable_rag: bool = True) -> dict:
    """Process a user message and return response."""
    
    # Step 1: Build system prompt
    base_prompt = self._build_base_system_prompt()
    
    # Step 2: Add RAG context if enabled
    if enable_rag:
        rag_context = self._get_rag_context(message)
        if rag_context:
            enhanced_prompt = f"{base_prompt}\n\n## Relevant Context\n\n{rag_context}"
        else:
            enhanced_prompt = base_prompt
    
    # Step 3: Update NPC directive
    self.npc.primary_directive = enhanced_prompt
    
    # Step 4: Load conversation history
    messages_history = self._load_history(session_id)
    
    # Step 5: Call LLM via npcpy
    logger.info("[AGENT] Calling NPC.get_llm_response()")
    response = self.npc.get_llm_response(
        message,
        messages=messages_history,
        auto_process_tool_calls=True,  # Automatically execute tools
        conversation_id=session_id
    )
    
    return response
```

**Log Output**:
```
2026-01-02 09:55:32 [INFO] src.core.npc_agent: [AGENT] Processing message from session: 111514095
2026-01-02 09:55:35 [INFO] src.core.npc_agent: [AGENT] Loaded 86 messages from history
2026-01-02 09:55:35 [INFO] src.core.npc_agent: [AGENT] Calling NPC.get_llm_response()
```

#### 4. RAG Search (Optional)

**File**: `src/core/npc_agent.py:247`

```python
def _get_rag_context(self, query: str, top_k: int = 5) -> str:
    """Retrieve relevant context from vector store."""
    
    # Search ChromaDB
    results = self.vector_store.search(query, top_k=top_k)
    
    if not results:
        return ""
    
    # Format context
    context_parts = []
    for result in results:
        source = result.get('metadata', {}).get('source', 'unknown')
        text = result['text']
        score = result.get('score', 0)
        
        # Only include high-quality matches (>0.5 similarity)
        if score > 0.5:
            context_parts.append(f"[{source}]\n{text}")
    
    if context_parts:
        logger.info(f"[AGENT] RAG: Found {len(context_parts)} relevant chunks")
        return "\n\n---\n\n".join(context_parts)
    
    return ""
```

For "What's the weather?" - RAG may find relevant notes about weather preferences, but likely won't find highly relevant context.

#### 5. NPC Calls vLLM

**npcpy** internally uses **litellm** to call vLLM:

```python
# npcpy makes this call behind the scenes
response = litellm.completion(
    model="openai/NousResearch/Hermes-3-Llama-3.1-8B",
    api_base="http://localhost:8000",
    messages=[
        {
            "role": "system",
            "content": "You are Friday, an AI assistant...\n\nCurrent time: 2026-01-02 09:55:32 BRT..."
        },
        {
            "role": "user",
            "content": "What's the weather?"
        }
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    }
                }
            }
        },
        # ... 45 more tools ...
    ],
    tool_choice="auto",
    temperature=0.7
)
```

**Log Output**:
```
2026-01-02 12:55:35 [INFO] LiteLLM: LiteLLM completion() model= NousResearch/Hermes-3-Llama-3.1-8B; provider = openai
```

#### 6. vLLM Processes Request

vLLM receives the request and:
1. Tokenizes input
2. Runs model inference
3. Detects tool call needed
4. Returns response with tool call

**Response from vLLM**:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "model": "NousResearch/Hermes-3-Llama-3.1-8B",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "get_current_weather",
              "arguments": "{\"location\": \"Curitiba\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

**Log Output**:
```
INFO:     127.0.0.1:53402 - "POST /v1/chat/completions HTTP/1.1" 200 OK
INFO 01-02 12:55:43 [loggers.py:236] Engine 000: Avg prompt throughput: 1069.7 tokens/s
```

#### 7. Tool Execution

npcpy detects the tool call and executes it automatically:

```python
# npcpy automatically calls the tool
result = get_current_weather(location="Curitiba")
# Returns: "Temperature: 25°C, Conditions: Clear sky, Humidity: 65%"
```

**Log Output**:
```
2026-01-02 09:55:39 [INFO] friday: [TOOL] get_current_weather called
```

#### 8. Second LLM Call with Tool Result

npcpy sends tool result back to LLM:

```python
response = litellm.completion(
    model="openai/NousResearch/Hermes-3-Llama-3.1-8B",
    api_base="http://localhost:8000",
    messages=[
        {"role": "system", "content": "You are Friday..."},
        {"role": "user", "content": "What's the weather?"},
        {
            "role": "assistant",
            "content": null,
            "tool_calls": [{"id": "call_abc123", "function": {"name": "get_current_weather", ...}}]
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": "Temperature: 25°C, Conditions: Clear sky, Humidity: 65%"
        }
    ],
    tools=[...],
    tool_choice="none"  # Don't call tools again
)
```

#### 9. Final Response

vLLM generates final user-facing response:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "The current weather in Curitiba is 25°C with clear skies and 65% humidity. It's a nice day!"
      },
      "finish_reason": "stop"
    }
  ]
}
```

**Log Output**:
```
2026-01-02 09:55:39 [INFO] LiteLLM: Wrapper: Completed Call, calling success_handler
2026-01-02 09:55:39 [INFO] src.core.npc_agent: [AGENT] Response generated - mode: chat, tools called: 0
2026-01-02 09:55:39 [INFO] friday: [CHAT] Response mode=chat, tools called=1
2026-01-02 09:55:39 [INFO] friday: [CHAT] Response text: The current weather in Curitiba is 25°C with clear skies and 65% humidity. It's a nice day!
```

#### 10. Save to History

npcpy automatically saves the conversation to SQLite:

```sql
INSERT INTO conversations (conversation_id, role, content, timestamp)
VALUES 
  ('111514095', 'user', 'What''s the weather?', '2026-01-02 09:55:32'),
  ('111514095', 'assistant', 'The current weather in Curitiba is 25°C with clear skies...', '2026-01-02 09:55:39');
```

#### 11. Return to User

Core API returns response to client:

```json
{
  "text": "The current weather in Curitiba is 25°C with clear skies and 65% humidity. It's a nice day!",
  "mode": "chat",
  "tool_results": [
    {
      "tool": "get_current_weather",
      "result": "Temperature: 25°C, Conditions: Clear sky, Humidity: 65%"
    }
  ],
  "iterations": 1
}
```

**Log Output**:
```
INFO:     127.0.0.1:38816 - "POST /chat HTTP/1.1" 200 OK
```

### Complete Timeline

| Time | Component | Action |
|------|-----------|--------|
| 09:55:32 | Core API | Receive request |
| 09:55:32 | Agent | Process message, load history |
| 09:55:33 | RAG | Search ChromaDB (no relevant results) |
| 09:55:35 | npcpy | Call vLLM with tools |
| 09:55:36 | vLLM | Generate response (tool call) |
| 09:55:37 | Core | Execute tool: get_current_weather |
| 09:55:38 | npcpy | Call vLLM with tool result |
| 09:55:39 | vLLM | Generate final response |
| 09:55:39 | Core | Save to history, return response |

**Total time**: ~7 seconds (includes model inference, tool execution, and history management)

---

## Function Calling

### How It Works

Function calling allows the LLM to request external tool execution:

1. **Tool Definition**: Tools are defined as JSON schemas
2. **LLM Decision**: Model decides which tool to call based on user query
3. **Argument Extraction**: Model extracts arguments from conversation
4. **Execution**: npcpy automatically executes the tool
5. **Result Integration**: Tool result is sent back to LLM
6. **Final Response**: LLM generates user-facing response with context

### Tool Schema Example

```python
@friday_tool(name="get_recent_runs")
def get_recent_runs(days: int = 7, limit: int = 5) -> str:
    """Get recent running activities from Garmin.
    
    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of runs to return (default: 5)
    
    Returns:
        Formatted string with run details (date, distance, pace, duration)
    """
    # Implementation...
```

**Auto-generated OpenAI Function Schema**:
```json
{
  "type": "function",
  "function": {
    "name": "get_recent_runs",
    "description": "Get recent running activities from Garmin.",
    "parameters": {
      "type": "object",
      "properties": {
        "days": {
          "type": "integer",
          "description": "Number of days to look back (default: 7)",
          "default": 7
        },
        "limit": {
          "type": "integer",
          "description": "Maximum number of runs to return (default: 5)",
          "default": 5
        }
      }
    }
  }
}
```

### Hermes Tool Call Format

The Hermes model uses a special format for tool calls:

**Input** (what vLLM receives):
```json
{
  "messages": [...],
  "tools": [{"type": "function", "function": {...}}],
  "tool_choice": "auto"
}
```

**Output** (what vLLM returns):
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_abc",
          "type": "function",
          "function": {
            "name": "get_recent_runs",
            "arguments": "{\"days\": 7, \"limit\": 3}"
          }
        }
      ]
    },
    "finish_reason": "tool_calls"
  }]
}
```

### Multi-Tool Calls

The model can call multiple tools in one response:

**User**: "What's the weather and my next meeting?"

**LLM Response**:
```json
{
  "tool_calls": [
    {
      "id": "call_1",
      "function": {"name": "get_current_weather", "arguments": "{}"}
    },
    {
      "id": "call_2",
      "function": {"name": "get_next_event", "arguments": "{}"}
    }
  ]
}
```

npcpy executes both tools and sends results back to LLM for synthesis.

---

## RAG Integration

### Purpose

RAG (Retrieval Augmented Generation) enhances responses with relevant information from the Obsidian vault.

### How It Works

```
User Query: "What was my best run last month?"
     │
     ▼
┌─────────────────────┐
│ Semantic Search     │
│ in ChromaDB         │
│ (all-MiniLM-L6-v2)  │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│ Top 5 Results       │
│ (similarity > 0.5)  │
├─────────────────────┤
│ [Running Log.md]    │
│ "PR: 42km in 3:15"  │
│                     │
│ [Training Plan.md]  │
│ "Goal: Marathon..." │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│ Enhanced Prompt     │
├─────────────────────┤
│ System: You are...  │
│                     │
│ Context:            │
│ [Running Log.md]    │
│ PR: 42km in 3:15... │
│                     │
│ User: What was my   │
│ best run last month?│
└─────────────────────┘
     │
     ▼
    LLM
```

### Implementation

**File**: `src/core/npc_agent.py:247`

```python
def _get_rag_context(self, query: str, top_k: int = 5) -> str:
    """Retrieve relevant context from vector store."""
    
    if self.vector_store is None:
        return ""
    
    try:
        # Semantic search in ChromaDB
        results = self.vector_store.search(query, top_k=top_k)
        
        if not results:
            return ""
        
        # Filter by similarity threshold
        context_parts = []
        for result in results:
            source = result.get('metadata', {}).get('source', 'unknown')
            text = result['text']
            score = result.get('score', 0)
            
            # Only include high-quality matches (>0.5 similarity)
            if score > 0.5:
                context_parts.append(f"[{source}]\n{text}")
        
        if context_parts:
            logger.info(f"[AGENT] RAG: Found {len(context_parts)} relevant chunks")
            return "\n\n---\n\n".join(context_parts)
        
        return ""
    except Exception as e:
        logger.warning(f"[AGENT] RAG search failed: {e}")
        return ""
```

### Vector Store Details

**File**: `src/core/vector_store.py`

```python
class ChromaDBVectorStore:
    """ChromaDB-backed vector store for semantic search."""
    
    def __init__(self, persist_directory: str):
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Create/get collection with embedding function
        self.collection = self.client.get_or_create_collection(
            name="friday_brain",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        )
    
    def add_documents(self, documents: List[str], metadata: List[Dict], ids: List[str]):
        """Add documents to the collection."""
        self.collection.add(
            documents=documents,
            metadatas=metadata,
            ids=ids
        )
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search for similar documents."""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        # Format results
        formatted = []
        for i in range(len(results['documents'][0])):
            formatted.append({
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'score': 1 - results['distances'][0][i]  # Convert distance to similarity
            })
        
        return formatted
```

### Indexing Process

**File**: `src/core/vector_store.py`

```python
class BrainIndexer:
    """Index Obsidian vault into ChromaDB."""
    
    def index_all(self) -> Dict[str, int]:
        """Index all markdown files from brain folder."""
        stats = {"files_indexed": 0, "chunks_created": 0}
        
        # Find all .md files
        md_files = list(self.brain_path.rglob("*.md"))
        
        for md_file in md_files:
            # Read file content
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                continue
            
            # Split into chunks
            chunks = self._chunk_text(content)
            
            # Add to vector store
            for i, chunk in enumerate(chunks):
                doc_id = f"{md_file.stem}_{i}"
                self.vector_store.add_documents(
                    documents=[chunk],
                    metadata=[{
                        "source": md_file.name,
                        "path": str(md_file),
                        "chunk_index": i
                    }],
                    ids=[doc_id]
                )
            
            stats["files_indexed"] += 1
            stats["chunks_created"] += len(chunks)
        
        return stats
```

### When RAG is Used

RAG is enabled by default for all chat requests. It's particularly useful for:
- ✅ **Knowledge queries** - "What did I write about X?"
- ✅ **Personal context** - "What are my goals?"
- ✅ **Historical reference** - "When did I last run a marathon?"
- ✅ **Complex reasoning** - Providing background info for better answers

---

## Conversation History

### Storage

**Database**: SQLite at `~/friday_history.db`

**Schema** (managed by npcpy):
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,              -- 'user', 'assistant', 'system', 'tool'
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,                  -- JSON
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT                     -- JSON
);

CREATE INDEX idx_conversation_id ON conversations(conversation_id);
CREATE INDEX idx_timestamp ON conversations(timestamp);
```

### Memory Management

**File**: `src/core/npc_agent.py:191`

```python
# Configure NPC memory
self.npc.memory_length = 50          # Keep last 50 messages
self.npc.memory_strategy = 'recent'  # Use most recent messages
```

### Loading History

```python
def chat(self, message: str, session_id: str, ...):
    """Process message with conversation history."""
    
    # Load history from database
    messages_history = []
    if self.npc.command_history:
        try:
            conversations = self.npc.command_history.get_conversations_by_id(session_id)
            
            # Convert to OpenAI message format
            for conv in conversations:
                messages_history.append({
                    "role": conv.get("role", "user"),
                    "content": conv.get("content", "")
                })
            
            if messages_history:
                logger.info(f"[AGENT] Loaded {len(messages_history)} messages from history")
        except Exception as e:
            logger.warning(f"[AGENT] Failed to load conversation history: {e}")
    
    # Call LLM with history
    response = self.npc.get_llm_response(
        message,
        messages=messages_history,  # Includes full conversation context
        conversation_id=session_id
    )
```

### Example History

```
User: What's the weather?
Assistant: The current weather in Curitiba is 25°C with clear skies.

User: Will it rain today?
Assistant: [calls will_it_rain() tool]
           According to the forecast, there's only a 10% chance of rain today.

User: Good, should I run?
Assistant: [has context of previous messages about weather]
           Yes! With clear skies, 25°C, and low rain probability, it's perfect for a run.
```

The agent remembers the weather discussion and uses it to provide contextual advice.

---

## Tool System

### Registration

Tools are automatically discovered and registered at startup:

**File**: `src/core/loader.py`

```python
def load_extensions():
    """Load all tools and sensors from extensions."""
    import src.tools.calendar
    import src.tools.daily_briefing
    import src.tools.health
    import src.tools.vault
    import src.tools.weather
    import src.tools.system
    import src.tools.web
    import src.tools.media
    
    # Importing modules automatically registers decorated functions
    logger.info("Extensions loaded")
```

### Tool Decorator

**File**: `src/core/registry.py`

```python
def friday_tool(name: str):
    """Decorator to register a tool function.
    
    Example:
        @friday_tool(name="get_weather")
        def get_current_weather(location: str = "Curitiba") -> str:
            '''Get current weather.'''
            return "25°C, Clear"
    """
    def decorator(func):
        # Extract function signature
        sig = inspect.signature(func)
        docstring = inspect.getdoc(func) or ""
        
        # Generate OpenAI function schema
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": docstring.split('\n')[0],  # First line of docstring
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        
        # Add parameters from function signature
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_schema = {
                "type": _python_type_to_json_type(param.annotation),
                "description": _extract_param_doc(docstring, param_name)
            }
            
            if param.default != inspect.Parameter.empty:
                param_schema["default"] = param.default
            else:
                schema["function"]["parameters"]["required"].append(param_name)
            
            schema["function"]["parameters"]["properties"][param_name] = param_schema
        
        # Register in global registry
        _tool_registry[name] = ToolEntry(
            name=name,
            func=func,
            description=docstring,
            schema=schema
        )
        
        return func
    
    return decorator
```

### Tool Categories

**46 Tools Total**:

#### Calendar (6 tools)
```python
get_calendar_events(start_date, end_date, calendar_name)
get_today_schedule()
add_calendar_event(title, start_time, end_time, calendar_name, description, location)
find_free_time(date, duration_minutes, start_hour, end_hour)
get_next_event()
delete_calendar_event(event_id, calendar_name)
```

#### Health (11 tools)
```python
get_recent_runs(days, limit)
get_training_load(days)
get_vo2max()
get_sleep_summary(days)
get_recovery_status()
get_hrv_trend(days)
get_weekly_health()
get_stress_levels(hours)
get_heart_rate_summary()
get_activity_summary(date)
get_garmin_sync_status()
```

#### Vault (11 tools)
```python
vault_read_note(note_path)
vault_write_note(note_path, content, overwrite)
vault_list_directory(directory)
vault_search_notes(query, max_results)
vault_get_frontmatter(note_path)
vault_update_frontmatter(note_path, frontmatter)
vault_manage_tags(note_path, action, tags)
vault_create_daily_note()
vault_rename_note(old_path, new_path)
vault_move_note(note_path, new_directory)
vault_delete_note(note_path)
```

#### Weather (3 tools)
```python
get_current_weather(location)
get_weather_forecast(days, location)
will_it_rain(location)
```

#### System (7 tools)
```python
get_disk_usage()
get_current_time()
get_system_info()
get_uptime()
get_memory_usage()
get_friday_logs(service, lines)
get_homelab_status()
get_friday_status()
```

#### Web (3 tools)
```python
web_search(query, num_results)
web_fetch(url)
web_news(category, country, num_articles)
```

#### Media (2 tools)
```python
generate_image(prompt, size, num_images)
generate_speech(text, lang)
```

#### Daily Briefing (2 tools)
```python
get_morning_report()
get_evening_report()
```

---

## Code Examples

### Example 1: Simple Chat (No Tools)

**Request**:
```bash
curl -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello Friday!",
    "user_id": "test-user"
  }'
```

**Response**:
```json
{
  "text": "Hello! How can I help you today?",
  "mode": "chat",
  "tool_results": [],
  "iterations": 1
}
```

**Logs**:
```
[CHAT] Request from user=test-user: Hello Friday!
[AGENT] Processing message from session: test-user
[AGENT] Loaded 0 messages from history
[AGENT] Calling NPC.get_llm_response()
LiteLLM completion() model= NousResearch/Hermes-3-Llama-3.1-8B
[AGENT] Response generated - mode: chat, tools called: 0
[CHAT] Response text: Hello! How can I help you today?
```

### Example 2: Tool Call (Weather)

**Request**:
```json
{
  "text": "What's the weather in São Paulo?",
  "user_id": "test-user"
}
```

**LLM Response 1** (tool call):
```json
{
  "tool_calls": [{
    "function": {
      "name": "get_current_weather",
      "arguments": "{\"location\": \"São Paulo\"}"
    }
  }]
}
```

**Tool Execution**:
```python
result = get_current_weather(location="São Paulo")
# Returns: "Temperature: 28°C, Conditions: Partly cloudy, Humidity: 70%"
```

**LLM Response 2** (with context):
```json
{
  "text": "The weather in São Paulo is currently 28°C with partly cloudy skies and 70% humidity. It's a warm day!"
}
```

**Logs**:
```
[CHAT] Request from user=test-user: What's the weather in São Paulo?
[AGENT] Calling NPC.get_llm_response()
[TOOL] get_current_weather called
[AGENT] Response generated - mode: chat, tools called: 1
[CHAT] Response text: The weather in São Paulo is currently 28°C...
```

### Example 3: Multi-Tool Call

**Request**:
```json
{
  "text": "What's the weather and my next meeting?",
  "user_id": "test-user"
}
```

**LLM Response 1** (multiple tool calls):
```json
{
  "tool_calls": [
    {
      "id": "call_1",
      "function": {"name": "get_current_weather", "arguments": "{}"}
    },
    {
      "id": "call_2",
      "function": {"name": "get_next_event", "arguments": "{}"}
    }
  ]
}
```

**Tool Executions**:
```python
weather = get_current_weather()
# "Temperature: 25°C, Clear"

next_event = get_next_event()
# "AI Office Hours [MM] at 14:00 (in 2 hours)"
```

**LLM Response 2**:
```json
{
  "text": "The weather is 25°C and clear. Your next meeting is 'AI Office Hours [MM]' at 14:00, which is in 2 hours."
}
```

### Example 4: RAG Context

**Request**:
```json
{
  "text": "What are my marathon goals?",
  "user_id": "test-user"
}
```

**RAG Search Results**:
```
[Training Plan.md]
Goal: Sub-3:30 marathon by April 2026
Current: 3:45 PR from last year
Plan: 16-week plan with 80km/week peak

[Running Log.md]
Recent progress: Hit 70km this week
Long run pace improving: 4:45/km sustained
```

**Enhanced System Prompt**:
```
You are Friday...

## Relevant Context from Knowledge Base

[Training Plan.md]
Goal: Sub-3:30 marathon by April 2026...

[Running Log.md]
Recent progress: Hit 70km this week...

User: What are my marathon goals?
```

**LLM Response**:
```json
{
  "text": "Your marathon goal is to run sub-3:30 by April 2026. You're currently at a 3:45 PR and following a 16-week plan with a peak of 80km/week. Your recent progress looks good - you hit 70km this week and your long run pace is improving to 4:45/km sustained."
}
```

### Example 5: Image Generation

**Request**:
```json
{
  "text": "Generate an image of a sunset over mountains",
  "user_id": "test-user"
}
```

**LLM Response 1** (tool call):
```json
{
  "tool_calls": [{
    "function": {
      "name": "generate_image",
      "arguments": "{\"prompt\": \"sunset over mountains\", \"size\": \"1024x1024\", \"num_images\": 1}"
    }
  }]
}
```

**Tool Execution**:
```python
result = generate_image(
    prompt="sunset over mountains",
    size="1024x1024",
    num_images=1
)
# Returns: "Image generated successfully! URL: http://192.168.1.16:8002/outputs/sunset_12345.png"
```

**LLM Response 2**:
```json
{
  "text": "I've generated an image of a sunset over mountains for you! You can view it here: http://192.168.1.16:8002/outputs/sunset_12345.png"
}
```

---

## Performance & Optimization

### Response Times

Typical response times for different scenarios:

| Scenario | Time | Breakdown |
|----------|------|-----------|
| **Simple chat** (no tools) | 2-3s | LLM inference: 2s, overhead: 0.5s |
| **Single tool call** | 5-7s | LLM: 2s, tool: 1s, LLM: 2s, overhead: 1s |
| **Multi-tool call** | 8-12s | LLM: 2s, tools: 2-4s, LLM: 2s, overhead: 2s |
| **With RAG** | +0.5-1s | ChromaDB search: 0.5s |
| **With history** (50 msgs) | +0.2s | SQLite query: 0.2s |

### GPU Utilization

**vLLM Metrics**:
- **Idle**: 0% GPU, 20GB VRAM (model loaded)
- **Inference**: 85-95% GPU, 20GB VRAM
- **Batch size 1**: Optimal for single-user scenario
- **Throughput**: 1,070 tokens/s prompt, 3.6 tokens/s generation

### Bottlenecks

1. **LLM Inference** - Dominates latency (2-3s per call)
   - Solution: Use smaller model for simple queries (not implemented)
   - Alternative: Batch multiple requests (not needed for single user)

2. **Tool Execution** - Variable (0.1s - 5s)
   - Fast: `get_current_time()` (~0.1s)
   - Medium: `get_calendar_events()` (~1s)
   - Slow: `web_search()` (~3-5s)

3. **Context Window** - 16K tokens max
   - Solution: Truncate history, prioritize recent messages
   - Current: Keep last 50 messages (~8K tokens)

### Optimization Tips

✅ **Enable GPU memory sharing**: 0.85 utilization balances capacity vs speed
✅ **Use CUDA graphs**: Reduces overhead (automatically done by vLLM)
✅ **Cache embeddings**: ChromaDB persists embeddings on disk
✅ **Connection pooling**: Reuse HTTP connections to vLLM
✅ **Async tool execution**: Run independent tools in parallel (not implemented)

---

## Configuration

### Environment Variables

**Core Service** (`.env`):
```bash
# LLM Configuration
OPENAI_API_KEY=not-needed                    # Placeholder for litellm
OPENAI_API_BASE=http://localhost:8000        # vLLM endpoint

# Authentication
FRIDAY_API_KEY=your-secret-api-key           # Protect API endpoints

# External Services
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_USER_ID=your-user-id
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-influxdb-token
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
OPENWEATHERMAP_API_KEY=your-api-key
WHISPER_URL=http://192.168.1.16:8001        # Speech-to-text
STABLE_DIFFUSION_URL=http://192.168.1.16:8002  # Image generation
```

### Config File

**File**: `config.yml`

```yaml
llm:
  base_url: "http://localhost:8000/v1"
  model_name: "NousResearch/Hermes-3-Llama-3.1-8B"
  temperature: 0.7
  max_tokens: 2048
  timeout: 120

system:
  host: "0.0.0.0"
  port: 8080
  debug: false

memory:
  chunk_size: 1000
  chunk_overlap: 200
  max_history_messages: 50

paths:
  brain: "/home/artur/brain"           # Obsidian vault
  vector_db: "/home/artur/friday/data/chroma"
  conversation_db: "/home/artur/friday_history.db"
```

---

## Troubleshooting

### Common Issues

#### 1. vLLM Not Starting

**Symptom**: Core service reports "LLM not available"

**Check**:
```bash
systemctl --user status friday-vllm
curl http://localhost:8000/health
```

**Common causes**:
- GPU memory not released (orphaned processes)
- Model download failed
- Port 8000 in use

**Solution**:
```bash
# Kill orphaned processes
/home/artur/friday/scripts/vllm/cleanup_vllm.sh

# Restart service
systemctl --user restart friday-vllm

# Check logs
tail -f /home/artur/friday/logs/friday-vllm.log
```

#### 2. Tool Not Found

**Symptom**: "Tool 'xyz' not found" error

**Check**:
```bash
curl http://localhost:8080/tools | jq '.tools[] | .name'
```

**Common causes**:
- Tool not imported in `src/core/npc_agent.py`
- Tool decorator missing or incorrect
- Import error in tool module

**Solution**:
```python
# Add to src/core/npc_agent.py
from src.tools.your_module import your_tool

# Add to self.tools list
self.tools = [
    # ...
    your_tool,
]
```

#### 3. Conversation History Lost

**Symptom**: Agent doesn't remember previous messages

**Check**:
```bash
sqlite3 ~/friday_history.db "SELECT COUNT(*) FROM conversations;"
```

**Common causes**:
- Database file deleted
- Session ID changing between requests
- `fresh=True` flag clearing history

**Solution**:
```bash
# Verify DB exists
ls -lh ~/friday_history.db

# Check recent conversations
sqlite3 ~/friday_history.db "SELECT conversation_id, COUNT(*) FROM conversations GROUP BY conversation_id;"
```

#### 4. RAG Not Working

**Symptom**: No context added from vault

**Check**:
```bash
curl http://localhost:8080/health | jq
# Should show vector store initialized

# Check document count
cd /home/artur/friday
pipenv run python -c "from src.core.vector_store import get_vector_store; print(get_vector_store().count())"
```

**Common causes**:
- ChromaDB not initialized
- Vault not indexed
- Similarity threshold too high

**Solution**:
```bash
# Re-index vault
pipenv run python -c "
from src.core.vector_store import get_vector_store, BrainIndexer
from src.core.config import get_config

config = get_config()
store = get_vector_store()
indexer = BrainIndexer(config.paths.brain, store)
stats = indexer.index_all()
print(f'Indexed: {stats}')
"
```

---

## Monitoring

### Health Checks

```bash
# Core service health
curl http://localhost:8080/health

# vLLM service health
curl http://localhost:8000/health

# Check all services
./friday status
```

### Logs

```bash
# Real-time logs for all services
./friday logs all -f

# Core service logs
./friday logs friday-core -n 100

# vLLM logs
./friday logs friday-vllm -n 100

# Search for errors
./friday logs friday-core -n 1000 --no-follow | grep -i error
```

### Metrics

**vLLM provides metrics**:
```bash
curl http://localhost:8000/metrics
```

**Key metrics**:
- `vllm:prompt_tokens_total` - Total prompt tokens processed
- `vllm:generation_tokens_total` - Total tokens generated
- `vllm:request_success_total` - Successful requests
- `vllm:gpu_cache_usage_perc` - KV cache utilization

---

## Summary

### Architecture

- **vLLM** (Port 8000): High-performance LLM inference with Hermes-3-Llama-3.1-8B
- **Core** (Port 8080): FastAPI brain with npcpy agent, 46 tools, ChromaDB RAG

### Request Flow

1. User → Core API (`/chat`)
2. Core → Load history + RAG context
3. Core → Call vLLM with tools
4. vLLM → Detect tool call needed
5. Core → Execute tool(s)
6. Core → Call vLLM with results
7. vLLM → Generate final response
8. Core → Save history, return to user

### Key Features

✅ **Native function calling** via Hermes model
✅ **46 tools** across 8 categories
✅ **ChromaDB RAG** with 500+ documents
✅ **SQLite history** (last 50 messages)
✅ **Automatic tool execution** via npcpy
✅ **16K context window**
✅ **~5-7s typical response time**

---

**Last Updated**: 2026-01-02  
**Author**: Friday 3.0 Core & vLLM Services
