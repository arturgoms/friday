#!/bin/bash
cd /home/artur/friday
exec /home/artur/.local/share/virtualenvs/friday/bin/python -m vllm.entrypoints.openai.api_server \
    --model dphn/Dolphin3.0-Llama3.1-8B \
    --port 8000 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code \
    --dtype auto \
    --max-model-len 16384
