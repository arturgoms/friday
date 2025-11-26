#!/bin/bash

# Start vLLM server with Qwen model

MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8000
GPU_MEMORY_UTILIZATION=0.85

echo "Starting vLLM server..."
echo "Model: $MODEL"
echo "Port: $PORT"
echo "GPU: RTX 3090 24GB"

pipenv run python -m vllm.entrypoints.openai.api_server \
    --model $MODEL \
    --port $PORT \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 16384
