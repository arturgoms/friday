#!/bin/bash
source .env

curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {"command": "start", "description": "Show welcome message"},
      {"command": "help", "description": "Show detailed help"},
      {"command": "remember", "description": "Save a memory"},
      {"command": "sync", "description": "Sync Nextcloud files"},
      {"command": "stats", "description": "Show system status"}
    ]
  }'
echo ""
