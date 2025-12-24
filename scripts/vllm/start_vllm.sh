#!/bin/bash
cd /home/artur/friday

# Use local cache path to avoid HuggingFace Hub resolution issues
MODEL_PATH="/home/artur/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28"

exec /home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "Qwen/Qwen2.5-7B-Instruct" \
    --port 8000 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 16384
