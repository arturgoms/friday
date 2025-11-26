#!/bin/bash

# Friday AI Assistant startup script

cd "$(dirname "$0")"

echo "Starting Friday AI Assistant..."

# Activate pipenv and run
pipenv run python main.py
