#!/bin/bash
cd /home/artur/friday

# Hermes-4-14B-FP8 - Advanced reasoning, better tool calling, quantized to fit RTX 3090
MODEL_ID="NousResearch/Hermes-4-14B-FP8"

exec /home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_ID" \
    --served-model-name "NousResearch/Hermes-4-14B" \
    --port 8000 \
    --gpu-memory-utilization 0.95 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 32000 \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --enforce-eager
