# Friday AI - Quick Start

## Installation & Setup

```bash
cd /home/artur/friday

# 1. Install dependencies
pipenv install

# 2. Configure (if needed)
cp .env.example .env
nano .env

# 3. Start vLLM
./start_vllm.sh

# 4. Start Friday (in another terminal)
./run.sh
```

## Basic Usage

### Health Check
```bash
curl http://localhost:8080/health | python3 -m json.tool
```

### Chat with RAG
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What do I know about Django?"}'
```

### Save a Memory
```bash
curl -X POST http://localhost:8080/remember \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Important note here",
    "title": "Memory Title",
    "tags": ["tag1", "tag2"]
  }'
```

### Reindex Vault
```bash
curl -X POST http://localhost:8080/admin/reindex
```

## System Services (Auto-start)

```bash
# Copy service files
sudo cp friday/vllm.service friday/friday.service /etc/systemd/system/

# Enable services
sudo systemctl enable vllm friday

# Start services
sudo systemctl start vllm friday

# Check status
sudo systemctl status vllm friday
```

## Nextcloud Sync

See [NEXTCLOUD_SETUP.md](NEXTCLOUD_SETUP.md) for mounting your Nextcloud vault.

Quick setup:
```bash
# 1. Install davfs2
sudo bash setup_nextcloud_sync.sh

# 2. Configure credentials
nano ~/.davfs2/secrets

# 3. Mount
mount /home/artur/nextcloud-obsidian

# 4. Update Friday
nano .env  # Set VAULT_PATH=/home/artur/nextcloud-obsidian
```

## Useful Commands

```bash
# Check GPU usage
nvidia-smi

# Check what's running
ps aux | grep -E "(vllm|python main.py)"

# View logs
tail -f friday.log
tail -f vllm.log

# Stop everything
pkill -f vllm.entrypoints
pkill -f "python main.py"

# Run all tests
./test_friday.sh
```

## Current Setup

- **Model**: Qwen2.5-7B-Instruct (16K context)
- **GPU**: RTX 3090 24GB (~21GB used)
- **Vault**: ~/my-brain (170 files, 1016 chunks)
- **Features**: RAG, Auto-reindex, Memory, Web search, Streaming
- **Status**: ✅ Fully operational
