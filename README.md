# Friday AI Assistant

Personal homelab AI with RAG, memory, web search, and conversation history.

## Features

- **RAG (Retrieval Augmented Generation)**: Query your Obsidian vault
- **Automatic Reindexing**: File watcher detects changes and reindexes automatically
  - Debounced (5 seconds after last change)
  - Incremental updates (only changed files)
  - Processes changes every 10 seconds
- **Memory System**: Store and retrieve personal memories as Obsidian notes
- **Web Search**: DuckDuckGo integration for fresh information
- **Conversation History**: Multi-turn conversations with context
- **Streaming Responses**: Real-time response generation
- **Production Ready**: Logging, error handling, health checks
- **Modular Architecture**: Clean separation of concerns

## Architecture

```
friday/
├── app/
│   ├── api/          # API routes
│   ├── core/         # Config, logging
│   ├── models/       # Pydantic schemas
│   └── services/     # Business logic
│       ├── chat.py
│       ├── embeddings.py
│       ├── llm.py
│       ├── obsidian.py
│       ├── vector_store.py
│       └── web_search.py
├── chroma_db/        # Vector database
├── main.py           # Application entry point
└── .env              # Configuration
```

## Setup

### 1. Install Dependencies

```bash
cd /home/artur/friday
pipenv install
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Start vLLM Server

```bash
./start_vllm.sh
```

Or use systemd:

```bash
sudo cp vllm.service /etc/systemd/system/
sudo systemctl enable vllm
sudo systemctl start vllm
```

### 4. Start Friday

```bash
./run.sh
```

Or use systemd:

```bash
sudo cp friday.service /etc/systemd/system/
sudo systemctl enable friday
sudo systemctl start friday
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8080/health
```

### Chat
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What do I know about Django?",
    "use_rag": true,
    "use_memory": true,
    "use_web": false
  }'
```

### Remember Something
```bash
curl -X POST http://localhost:8080/remember \
  -H "Content-Type: application/json" \
  -d '{
    "content": "My favorite color is blue",
    "title": "Favorite Color",
    "tags": ["personal", "preferences"]
  }'
```

### Rebuild Index
```bash
curl -X POST http://localhost:8080/admin/reindex
```

## Configuration

Key settings in `app/core/config.py`:

- `vault_path`: Path to Obsidian vault (can be Nextcloud-mounted)
- `llm_base_url`: vLLM server URL
- `llm_model_name`: Model to use
- `top_k_obsidian`: Number of docs to retrieve
- `max_conversation_history`: Conversation context size

### Nextcloud Integration

To sync your vault across devices, see **[NEXTCLOUD_SETUP.md](NEXTCLOUD_SETUP.md)** for:
- WebDAV mounting (recommended)
- Nextcloud desktop client
- Rclone advanced setup
- Troubleshooting tips

## Hardware

- **Primary**: RTX 3090 24GB (runs Qwen2.5-7B-Instruct + Friday)
  - GPU Usage: ~21GB/24GB
  - Embedding model runs on CPU to save VRAM
- **Secondary**: RTX 3060 12GB (future distributed setup)

## Current Status

✅ **FULLY OPERATIONAL**
✅ vLLM running (Qwen2.5-7B-Instruct, 16K context)
✅ Friday API on port 8080
✅ RAG with 1015 chunks indexed (169 markdown files)
✅ Memory system active (3 entries)
✅ Health monitoring working
✅ Tested: RAG queries working perfectly
✅ Tested: Memory creation in Obsidian vault working

## Reindexing

Three ways to reindex:

1. **Automatic (default)**: File watcher detects changes and reindexes
   - Watches: Create, modify, delete operations
   - Debounce: 5 seconds after last change
   - Frequency: Processes pending changes every 10 seconds

2. **Manual full rebuild**: 
   ```bash
   curl -X POST http://localhost:8080/admin/reindex
   ```

3. **On memory creation**: `/remember` endpoint indexes immediately

Check watcher status:
```bash
curl http://localhost:8080/admin/debug | python3 -m json.tool
# Shows: file_watcher_running, pending_files, obsidian_chunks
```

## Next Steps

1. ✅ ~~Start vLLM server~~ (DONE)
2. ✅ ~~Add automatic reindexing~~ (DONE)
3. Test chat with web search enabled
4. Configure systemd services for auto-start
5. Set up distributed GPU inference (3060 server)
6. Add more advanced features (agentic workflows, tool use, function calling)
