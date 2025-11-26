#!/bin/bash

# Friday AI monitoring script

echo "======================================="
echo "   Friday AI System Monitor"
echo "======================================="
echo ""

# Check vLLM
echo "🤖 vLLM Status:"
if pgrep -f "vllm.entrypoints" > /dev/null; then
    echo "  ✅ Running (PID: $(pgrep -f vllm.entrypoints))"
    curl -s http://localhost:8000/v1/models | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  Model: {d['data'][0]['id']}\")" 2>/dev/null || echo "  ⚠️  API not responding"
else
    echo "  ❌ Not running"
fi
echo ""

# Check Friday
echo "🚀 Friday API Status:"
if pgrep -f "python main.py" > /dev/null; then
    echo "  ✅ Running (PID: $(pgrep -f 'python main.py'))"
    
    # Get health info
    HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$HEALTH" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  LLM: {d['llm_status']}\"); print(f\"  Vault: {d['vault_path']}\"); print(f\"  Chunks: {d['obsidian_chunks']}\"); print(f\"  Memories: {d['memory_entries']}\")"
    else
        echo "  ⚠️  API not responding"
    fi
else
    echo "  ❌ Not running"
fi
echo ""

# Check GPU
echo "🎮 GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader | while read line; do
        echo "  $line"
    done
else
    echo "  ⚠️  nvidia-smi not found"
fi
echo ""

# Check file watcher
echo "👁️  File Watcher:"
DEBUG=$(curl -s http://localhost:8080/admin/debug 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$DEBUG" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  Status: {'✅ Active' if d.get('file_watcher_running') else '❌ Inactive'}\"); print(f\"  Pending: {d.get('pending_files', 0)} files\"); print(f\"  Watching: {d.get('num_md_files', 0)} markdown files\")"
else
    echo "  ⚠️  Cannot check status"
fi
echo ""

# Check disk usage
echo "💾 Disk Usage:"
du -sh /home/artur/friday/chroma_db 2>/dev/null | awk '{print "  ChromaDB: " $1}'
du -sh /home/artur/my-brain 2>/dev/null | awk '{print "  Vault: " $1}'
echo ""

echo "======================================="
echo "Run './test_friday.sh' for full test"
echo "======================================="
