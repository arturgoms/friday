#!/bin/bash
cd /home/artur/friday

# Hermes-3-Llama-3.1-8B - Excellent for function calling
MODEL_ID="NousResearch/Hermes-3-Llama-3.1-8B"

exec /home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_ID" \
    --served-model-name "$MODEL_ID" \
    --port 8000 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 16384 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
