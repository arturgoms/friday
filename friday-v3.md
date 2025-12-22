# Friday 3.0: Autonomous AI Platform Architecture

**Version:** 3.0
**Target Host:** Local Ubuntu Server (RTX 3090)
**Core Engine:** vLLM + Dolphin3.0-Llama3.1-8B

---

# 1. Executive Summary (Deep Dive)

**Friday 2.0** represents a paradigm shift from "Chatbot" to "Personal Operating System." While a standard LLM lives in a void, Friday lives **in your server, for your server**.

### 1.1. The Problem Space

Current AI assistants fail in three key areas:

1. **Amnesia (Hollowness):** They forget who you are between sessions. They offer generic advice because they lack deep context about your projects, preferences, and history.
2. **Impotence (Fragility):** They cannot *do* things. Asking an AI to "check why the server is slow" usually results in a generic list of commands to run, rather than the AI actually running them.
3. **Passivity:** They wait for input. A true assistant should tap you on the shoulder when a disk is full or a Bitcoin price target is hit, without being asked.

### 1.2. The Solution: A Hybrid OS Layer

Friday 3.0 solves these by embedding the AI directly into the host OS ecosystem.

* **Stateful Identity:** By integrating with **Obsidian**, Friday shares your "Second Brain." If you write a note about a project today, Friday knows about it tomorrow.
* **Dual-Mode Agency:**
* *Mode A (The Steward):* Uses safe, pre-compiled tools for critical data (Calendar, Tasks).
* *Mode B (The Engineer):* Uses an autonomous Code Interpreter to write and execute scripts for novel problems.


* **Sensory Awareness:** A dedicated daemon acts as a "nervous system," polling hardware and data streams 24/7 to provide proactive intelligence.

---

# 2. System Architecture (Deep Dive)

The system is architected as a **Quad-Service Micro-Platform**. This decoupling ensures that a crash in one component (e.g., the experimental Sensor loop) does not bring down the Core brain.

### 2.1. Service A: `friday-vllm` (The Engine Room)

This is the raw compute layer. It abstracts the GPU hardware away from the logic.

* **Role:** Token Generation provider.
* **Tech Stack:** `vLLM` (High-performance inference engine).
* **Responsibility:**
* Manages the 24GB VRAM of the RTX 3090.
* Exposes an OpenAI-compatible endpoint (`/v1/chat/completions`).
* Handles batching and quantization (AWQ) for speed.


* **Why Separate?** If the Python logic in `friday-core` crashes, we don't want to reload the 32GB model weights (which takes 30s+). The Engine stays hot; the Brain restarts instantly.

### 2.2. Service B: `friday-core` (The Central Nervous System)

This is the application logic. It is the only service that writes to the "Session State."

* **Role:** Logic Orchestrator & API Gateway.
* **Tech Stack:** `FastAPI`, `Uvicorn`, `Pydantic`.
* **Responsibility:**
* **Context Injection:** Queries ChromaDB/Obsidian before every request.
* **Session Management:** Keeps "Python Kernels" alive for active users.
* **Routing:** Decides whether to use a Tool or write Code.
* **API Exposure:** Provides the `:8080` endpoints for the CLI and Telegram service.



### 2.3. Service C: `friday-awareness` (The Autonomic Nervous System)

This is the background monitoring loop. It runs independently of user interaction.

* **Role:** Proactive Monitoring.
* **Tech Stack:** `Python Threading`, `Schedule`.
* **Responsibility:**
* **Polling:** Runs `@friday_sensor` functions on defined intervals (e.g., `check_disk` every 5m).
* **Evaluation:** Compares sensor data against `config.yml` thresholds.
* **Filtering:** Uses a lightweight LLM call to decide if an alert is "worthy" of interrupting the user.
* **Push:** Sends alerts to `friday-core` to be forwarded to the user.



### 2.4. Service D: `friday-telegram` (The Interface Layer)

This is a dumb client. It has zero "AI" logic.

* **Role:** User Interface.
* **Tech Stack:** `python-telegram-bot`.
* **Responsibility:**
* **Long Polling:** Maintains the connection to Telegram servers.
* **Rendering:** Formats Markdown responses from Core into Telegram messages.
* **Typing Indicators:** Shows "Friday is typing..." while the Core is thinking.


* **Resilience:** If the Core goes down for an update, the Telegram bot stays online and replies "System Maintenance" instead of crashing.

### 2.5. The Data Layer (Shared State)

Services are stateless logic; the Data Layer is where memory lives.

* **Vector Database (`data/chroma/`):** Stores embeddings of Obsidian notes. Accessed by Core for RAG.
* **User Profile (`brain/1. Notes/<username>.md`):** Markdown file in Obsidian vault with user facts. Loaded into System Prompts via RAG.
* **Logs (`logs/*.log`):** Centralized rotation logs.
* **Configuration (`config.yml`):** The single source of truth for all services (root level).

### 2.6. Communication Protocol

* **External (User -> System):** Telegram or CLI.
* **Internal (Service -> Service):** HTTP REST APIs on `localhost`.
* *Telegram*  `POST http://localhost:8080/chat` (Core)
* *Awareness*  `POST http://localhost:8080/alert` (Core)
* *Core*  `POST http://localhost:8000/v1/chat/completions` (vLLM)

This architecture ensures that **Friday 3.0** is robust, scalable, and easy to debug.

---

## 3. Configuration Strategy

We separate **Secrets** from **Behavior** to make the system easy to tune.

### A. Secrets (`.env`)

Contains sensitive keys. **Never committed to Git.**

```ini
TELEGRAM_BOT_TOKEN="123456:ABC..."
OPENAI_API_KEY="EMPTY"
GOOGLE_CREDENTIALS_PATH="/home/user/certs/google.json"

```

### B. System Behavior (`config.yml`)

Contains logic settings. **Committed to Git.**

```yaml
system:
  host: "0.0.0.0"
  port: 8080
  debug: true
  log_level: "INFO"

llm:
  model_name: "dphn/Dolphin3.0-Llama3.1-8B"
  base_url: "http://localhost:8000/v1"
  temperature: 0.3
  max_tokens: 4096

services:
  core_port: 8080
  vllm_port: 8000

memory:
  session_timeout_seconds: 3600
  rag_max_results: 5
  chroma_path: "./data/chroma"

sensors:
  check_interval_default: 300
  disk_threshold_percent: 90
  gpu_temp_threshold: 80

```

---

## 4. Core Logic: The Hybrid Router

To balance **Reliability** with **Power**, the Core Agent uses a dual-path execution model based on settings in `config.yml`.

### Path A: Deterministic Tools (Safe)

* **Trigger:** Recognized intents (e.g., "Add to calendar").
* **Mechanism:** Executes pre-written Python functions (`@friday_tool`).
* **Use Case:** Daily routine tasks.

### Path B: Code Interpreter (Autonomous)

* **Trigger:** Complex/System intents (e.g., "Check disk space").
* **Mechanism:** **ReAct Loop**. Writes Python/Bash code, executes in REPL, reads stdout.
* **Safety:** Dangerous commands (`rm`, `mv`) are gated by user confirmation.
* **Use Case:** Novel tasks, System Administration.

Here is the expanded, deep-dive documentation for the **Hybrid Router**. This specific module is the "Brain" of Friday, and getting it right is the difference between a dumb chatbot and a capable agent.

You should replace **Section 4** of the previous Master Documentation with this detailed breakdown.

---

## 4. Core Logic: The Hybrid Router (Deep Dive)

The Hybrid Router is not just a `if/else` statement. It is a **multi-stage reasoning engine** responsible for orchestrating the conversation flow.

### 4.1. The Routing Philosophy

The router creates a fork in the execution logic to balance **Safety** vs. **Capability**.

* **Safety (Path A):** We want 0% hallucination when modifying the Calendar or Database. We use **Structured Output** (JSON).
* **Capability (Path B):** We want 100% flexibility when debugging the system. We use **Generative Code** (Python).

### 4.2. The Router Class Structure (`src/core/agent.py`)

The Agent is implemented as a Python class that maintains the conversation loop.

```python
class HybridAgent:
    def __init__(self, llm_client, context_manager, tool_registry):
        self.llm = llm_client
        self.context = context_manager
        self.tools = tool_registry # The dictionary of @friday_tools
        self.interpreter = CodeInterpreter() # The Python REPL

    async def run(self, user_input: str, user_id: str):
        # 1. Build Context (RAG + Profile)
        system_context = self.context.build(user_id, user_input)
        
        # 2. Construct the Routing Prompt
        prompt = self._build_prompt(user_input, system_context)
        
        # 3. LLM Decision (Thinking Step)
        response = await self.llm.generate(prompt)
        
        # 4. Dispatch
        if response.is_tool_call():
            return await self._execute_tool(response)
        elif response.is_code_block():
            return await self._execute_interpreter(response)
        else:
            return response.text_content()

```

### 4.3. The System Prompt (The "Ghost in the Machine")

This is the most critical implementation detail. The prompt must strictly enforce the routing rules. We inject the available tool schemas dynamically.

**Implementation (`src/core/prompts.py`):**

```text
SYSTEM_PROMPT = """
You are Friday, an autonomous system agent. 

MODE 1: DETERMINISTIC TOOLS
You have access to the following functions:
{tool_schemas} 
(e.g., calendar_add, memory_save)
- IF the user request matches a tool exactly, output a JSON object: {{"tool": "name", "args": {{...}}}}
- DO NOT hallucinate tools.

MODE 2: CODE INTERPRETER
You are running on an Ubuntu server with full shell and python access.
- IF the request is complex, involves data analysis, or system administration (disk, network, files), write a Python script.
- Wrap code in ```python ... ``` blocks.
- You can import `os`, `subprocess`, `pandas`.

MODE 3: CHAT
- IF no action is required, just reply conversationally.

CONTEXT:
{user_context}
"""

```

### 4.4. Path A: Deterministic Tool Execution

This path handles known, safe operations.

**Implementation Steps:**

1. **Parse:** The Agent parses the JSON output from the LLM (e.g., `{"tool": "calendar_add", "args": {"title": "Meeting"}}`).
2. **Validate:** It checks if `calendar_add` exists in the `TOOL_REGISTRY` and if the arguments match the type hints.
3. **Execute:** It calls the actual Python function `calendar_add(title="Meeting")`.
4. **Feedback:** The return value of the function ("Event created ID: 123") is fed back to the LLM to generate the final confirmation message to the user.

**Error Handling:**

* If the tool arguments are wrong (e.g., missing "date"), the Agent automatically sends the error back to the LLM: *"Error: Missing argument 'date'. Please retry."* The LLM then self-corrects.

### 4.5. Path B: The Code Interpreter (ReAct Loop)

This path handles the "unknown." It implements a **Reasoning + Acting** loop.

**The Loop Logic:**

1. **Generate:** The LLM writes a chunk of Python code (e.g., `import shutil; total, used, free = shutil.disk_usage("/")`).
2. **Sandbox Check:** The code is passed to `src/core/sandbox.py`.
* *Regex Filter:* Checks for `rm -rf /`, `mkfs`, `:(){ :|:& };:`.
* *Confirmation:* If the config `require_confirmation` is True for file writes, the loop pauses and asks the user on Telegram.


3. **Execute:** The code runs in a persistent `InteractiveConsole` (Python REPL).
4. **Capture:** `stdout` and `stderr` are captured.
5. **Iterate:**
* If `stderr` (Error): The error is sent back to the LLM. The LLM writes a fix.
* If `stdout` (Success): The output ("Total: 100GB, Used: 90GB") is sent to the LLM.


6. **Synthesize:** The LLM reads the tool output and formulates a human answer: *"Your disk is 90% full."*

### 4.6. The "Fallthrough" Strategy

What happens when the LLM is confused?

1. **Ambiguity Check:** If the Router cannot decide between Tool or Code, it defaults to **Chat** but asks a clarifying question.
2. **Timeout:** If the Code Interpreter loops more than 5 times (trying to fix a bug), the Agent halts and reports: *"I'm stuck trying to debug the script. Here is the error..."*

### 4.7. Configuration Integration

The Router behavior is controlled via `config.yml`:

```yaml
router:
  # If true, the LLM parses the request to JSON before thinking. 
  # Slower but more accurate.
  use_structured_chain: true
  
  # Max retries if a tool call fails validation
  max_tool_retries: 3

interpreter:
  # Dangerous commands require user 'yes' in Telegram
  require_confirmation: ["os.remove", "shutil.rmtree", "subprocess"]
  
  # Timeout for any single code block execution
  execution_timeout_sec: 30

```

---

## 5. Directory Structure

```text
friday/
├── friday                      # CLI Entry Point (imports src/cli.py)
├── Pipfile                     # Dependencies
├── Pipfile.lock
├── config.yml                  # System Behavior Settings
├── config.example.yml          # Example config
├── .env                        # Secrets (API Keys)
├── logs/                       # Centralized Logging
│   ├── core.log
│   ├── awareness.log
│   ├── telegram.log
│   └── vllm.log
├── services/                   # Systemd Service Files
│   ├── friday-core.service
│   ├── friday-vllm.service
│   └── ...
├── data/                       # Persistent State
│   └── chroma/                 # Vector DB
├── brain/                      # Obsidian Vault (RAG Source + User Profile)
│   └── 1. Notes/
│       └── <username>.md       # User Profile
├── src/
│   ├── cli.py                  # CLI Logic
│   ├── core/
│   │   ├── config.py           # YAML/Env Loader
│   │   ├── registry.py         # Decorators
│   │   ├── agent.py            # Hybrid Router
│   │   └── ...
│   ├── tools/                  # Actions
│   └── sensors/                # Inputs
└── tests/                      # QA Suite

```

---

## 6. Extensibility Protocol

### Adding a Tool (Action)

Create `src/tools/network.py`:

```python
from src.core.registry import friday_tool

@friday_tool(name="check_latency")
def check_latency(host: str = "google.com"):
    """Pings a host and returns latency."""
    # Logic...
    return "45ms"

```

### Adding a Sensor (Input)

Create `src/sensors/crypto.py`:

```python
from src.core.registry import friday_sensor
from src.core.config_loader import config

@friday_sensor(name="btc_watch", interval_seconds=config['sensors']['check_interval_default'])
def watch_bitcoin():
    # Logic...
    return {"price": 95000}

```
Here is the expanded, deep-dive documentation for the **Extensibility Protocol**. This section explains the "Plugin System" that allows you to grow Friday's capabilities indefinitely without rewriting the core engine.

You should replace **Section 6** of the Master Documentation with this detailed breakdown.

---

## 6. Extensibility Protocol (Deep Dive)

Friday uses a **Decorator-based Registry Pattern**. This allows developers to add new capabilities (Tools) or data streams (Sensors) simply by creating a new Python file. No manual registration in `main.py` is required.

### 6.1. The Registry Engine (`src/core/registry.py`)

The core logic relies on Python's introspection capabilities (`inspect` module). When the system starts, it scans the `src/tools` and `src/sensors` directories.

**How it works:**

1. **Import:** The system dynamically imports every `.py` file in the extension folders.
2. **Decorate:** As the Python interpreter reads the files, the `@friday_tool` decorator executes.
3. **Register:** The decorator extracts the function's metadata (Name, Docstring, Type Hints) and stores it in a global `TOOL_REGISTRY` dictionary.
4. **Schema Gen:** It automatically converts Python Type Hints into the JSON Schema format required by the LLM (OpenAI spec).

### 6.2. Anatomy of a Tool (The "Hands")

Tools are synchronous or asynchronous Python functions that the Agent can invoke.

**Implementation Steps:**

1. **Create File:** `src/tools/finance.py`
2. **Define Function:** Standard Python function with **Type Hints** (Critical for the LLM).
3. **Decorate:** Add `@friday_tool`.

**Code Example:**

```python
from src.core.registry import friday_tool
import requests

@friday_tool(name="currency_converter")
def convert_currency(amount: float, from_currency: str, to_currency: str = "USD") -> str:
    """
    Converts a monetary amount between currencies using current exchange rates.
    
    Args:
        amount: The value to convert (e.g., 100.50)
        from_currency: The source currency code (e.g., 'BRL', 'EUR')
        to_currency: The target currency code (default: 'USD')
    """
    # 1. Logic
    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
    response = requests.get(url).json()
    rate = response["rates"][to_currency]
    result = amount * rate
    
    # 2. Return (String is best for LLM ingestion)
    return f"{amount} {from_currency} is currently {result:.2f} {to_currency}"

```

**What the LLM Sees (Auto-Generated Schema):**

The Registry automatically translates the code above into this JSON, which is injected into the System Prompt:

```json
{
  "type": "function",
  "function": {
    "name": "currency_converter",
    "description": "Converts a monetary amount between currencies using current exchange rates.",
    "parameters": {
      "type": "object",
      "properties": {
        "amount": {"type": "number", "description": "The value to convert"},
        "from_currency": {"type": "string", "description": "The source currency code"},
        "to_currency": {"type": "string", "description": "The target currency code"}
      },
      "required": ["amount", "from_currency"]
    }
  }
}

```

### 6.3. Anatomy of a Sensor (The "Eyes")

Sensors are passive data collectors used by the `friday-awareness` daemon. They do not need schemas because the LLM doesn't call them directly; the system calls them on a schedule.

**Implementation Steps:**

1. **Create File:** `src/sensors/gpu_mon.py`
2. **Dependency Injection:** You can import `config` to avoid hardcoding values.
3. **Decorate:** Add `@friday_sensor`.

**Code Example:**

```python
from src.core.registry import friday_sensor
from src.core.config_loader import config
import pynvml # Nvidia management lib

# Pull interval from config.yml, default to 60s if missing
CHECK_INTERVAL = config['sensors'].get('gpu_interval', 60)

@friday_sensor(name="gpu_thermal_watch", interval_seconds=CHECK_INTERVAL)
def check_gpu_temp():
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    temp = pynvml.nvmlDeviceGetTemperature(handle, 0)
    
    # Return a dict. The Awareness Engine looks for 'alert_level' or specific logic.
    return {
        "sensor": "gpu_temp",
        "value": temp,
        "unit": "C",
        # The Evaluation Logic can be embedded here or in the config
        "threshold": config['sensors']['gpu_temp_threshold']
    }

```

### 6.4. Accessing Secrets & Config

Tools often need API keys. **Do not hardcode them.**

* **Secrets:** Import `os` and use `os.getenv("KEY_NAME")`.
* **Behavior:** Import `src.core.config_loader.config` (The loaded YAML).

**Example:**

```python
import os
from src.core.config_loader import config

@friday_tool(name="search_web")
def search_web(query: str):
    api_key = os.getenv("TAVILY_API_KEY") # From .env
    max_results = config['tools']['search']['max_results'] # From config.yml
    # ... logic ...

```

### 6.5. Auto-Discovery Logic (`src/core/loader.py`)

To ensure new files are picked up, the `main.py` entry point runs this loader *before* starting the Agent.

```python
import pkgutil
import importlib
import src.tools
import src.sensors

def load_extensions():
    """
    Recursively finds and imports modules in src/tools and src/sensors.
    This triggers the decorators and populates the REGISTRY.
    """
    # Load Tools
    for module_info in pkgutil.iter_modules(src.tools.__path__):
        importlib.import_module(f"src.tools.{module_info.name}")
        print(f"Loaded Tool Module: {module_info.name}")

    # Load Sensors
    for module_info in pkgutil.iter_modules(src.sensors.__path__):
        importlib.import_module(f"src.sensors.{module_info.name}")
        print(f"Loaded Sensor Module: {module_info.name}")

```

### 6.6. Testing Your Extensions

We enforce a strict separation of "Tool Logic" vs "AI Logic".

* **Functional Test:** Does `currency_converter(10, 'USD', 'EUR')` actually return a string?
* *Run:* `pytest tests/functional/test_finance.py`


* **Agent Test:** Does the LLM *know* to use this tool when I ask "How many Euros is 10 Dollars?"
* *Run:* `pytest tests/agent/test_routing.py`

---

## 7. The CLI (Control Plane)

The `friday` command is the administrative bridge between the user and the background daemons. It is built using **Typer** (for robust argument parsing) and **Rich** (for beautiful, readable terminal output).

### 7.1. CLI Design Philosophy

1. **Unified Entry Point:** One command (`friday`) rules them all. No separate scripts for logs, starting, or chatting.
2. **State-Aware:** The CLI knows if the background services are dead or alive and reports it visually.
3. **Client-Server:** The CLI `chat` command is just a "dumb client." It sends text to the `friday-core` API and renders the Markdown response. It holds no logic itself.

### 7.2. Command Reference

| Command | Arguments | Description | Implementation Target |
| --- | --- | --- | --- |
| `status` | None | Dashboard of service health, PIDs, and Memory usage. | `systemctl status`, `ps` |
| `start` | `[service]` (default: `all`) | Boots up the daemon(s). | `systemctl start` |
| `stop` | `[service]` (default: `all`) | Shuts down daemon(s). | `systemctl stop` |
| `restart` | `[service]` (default: `all`) | Hard restart. Reloads `.env`. | `systemctl restart` |
| `logs` | `[service]` (default: `core`) | Tails the logs in real-time. | `journalctl -f` |
| `chat` | None | Enters interactive REPL mode. | `POST /chat` |
| `run` | `"query string"` | Sends one command, prints output, exits. | `POST /chat` |
| `config` | `view` / `edit` | Quick access to `config.yml`. | `nano config/config.yml` |

### 7.3. Implementation Logic (`src/cli.py`)

The CLI is a Python application that uses `subprocess` to talk to Linux and `httpx` to talk to the AI.

#### A. The Status Dashboard

We use `Rich.Table` to render a live-updating dashboard.

```python
# src/cli.py snippet
@app.command()
def status():
    """Checks health of the Quad-Service architecture."""
    table = Table(title="Friday 3.0 System Status", style="bold white")
    table.add_column("Service", style="cyan")
    table.add_column("State", style="magenta")
    table.add_column("PID", justify="right")
    table.add_column("Memory", justify="right")

    services = ["friday-vllm", "friday-core", "friday-awareness", "friday-telegram"]
    
    for svc in services:
        # We parse 'systemctl show' for raw data
        state, pid, mem = get_systemd_properties(svc) 
        
        # Color coding
        state_color = "green" if state == "active" else "red"
        
        table.add_row(svc, f"[{state_color}]{state}[/]", pid, mem)
        
    console.print(table)

```

#### B. The Interactive Chat Client

This allows you to chat with Friday over SSH or local terminal. It supports streaming responses (if the API supports it) or standard request/response.

```python
@app.command()
def chat():
    """Connects to the Core API for a chat session."""
    check_if_core_is_running() # Helper check
    
    console.print("[bold green]Friday 3.0 Terminal Interface[/bold green]")
    console.print(f"Connected to {config['services']['core_url']}")
    
    session_history = []
    
    while True:
        try:
            user_input = console.input("[bold blue]You > [/bold blue]")
            if user_input.lower() in ["exit", "quit"]:
                break
                
            # Show a spinner while the "Brain" thinks
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                response = api_client.post("/chat", json={"text": user_input})
                
            # Render Markdown (Code blocks, lists, bold text)
            ai_text = response.json().get("text")
            md = Markdown(ai_text)
            
            console.print("[bold green]Friday > [/bold green]")
            console.print(md)
            console.print() # Newline
            
        except KeyboardInterrupt:
            break

```

#### C. The "Run" Command (Automation)

This is crucial for piping. It allows you to use Friday in other bash scripts.

*Example Usage:* `friday run "summarize this log file" < error.log`

```python
@app.command()
def run(query: str):
    """
    Single-shot execution. Useful for piping/scripting.
    Example: friday run "Check disk space"
    """
    # If piped input exists, prepend it to query
    if not sys.stdin.isatty():
        piped_data = sys.stdin.read()
        query = f"{query}\n\nContext:\n{piped_data}"

    response = api_client.post("/chat", json={"text": query})
    print(response.json().get("text")) # Plain print for piping

```

### 7.4. Systemd Integration

The CLI does not run as root. It uses `systemctl --user`. This is safer and cleaner.

* **Log Tailing:**
The `logs` command is a wrapper around `journalctl`. This gives you robust, rotated logs without writing custom file handlers.
```python
subprocess.run(["journalctl", "--user", "-u", f"friday-{service}", "-f", "-n", "50"])

```



### 7.5. Configuration Management

Instead of hunting for the config file, the CLI provides a shortcut.

```python
@app.command()
def config(action: str = "view"):
    config_path = "config.yml"
    if action == "edit":
        # Opens in your default $EDITOR (nano/vim)
        subprocess.run([os.getenv("EDITOR", "nano"), config_path])
    else:
        # Prints syntax-highlighted YAML
        with open(config_path) as f:
            syntax = Syntax(f.read(), "yaml")
            console.print(syntax)

```

## 8. Installation & Setup

### Prerequisites

* Ubuntu 22.04+
* NVIDIA GPU (RTX 3090)
* Python 3.10+

### Step 1: Clone & Install

```bash
git clone https://github.com/your/friday.git
cd friday
chmod +x install.sh
./install.sh

```

### Step 2: Configuration

1. **Secrets:** Edit `.env` with API keys.
2. **Behavior:** Edit `config.yml` to set paths, ports, and model names.

### Step 3: Start Services

```bash
source ~/.bashrc
friday start all
friday status

```

---

## 9. Monitoring

* **Logs:** `friday/logs/*.log`
* **Traceability:** Every request is assigned a `trace_id` visible across logs.
* **Alerts:** Critical failures in `awareness` or `vllm` will trigger a Telegram alert to the user automatically (if configured).
