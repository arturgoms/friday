# Friday AI - Directory Structure

## Overview
The Friday AI project is now organized into logical directories for easy maintenance and navigation.

## Directory Structure

```
friday/
├── README.md                      # Main documentation
├── STRUCTURE.md                   # This file
├── .env                           # Environment variables (secrets)
├── friday                         # CLI convenience tool
│
├── src/                           # Source code
│   ├── main.py                    # Main Friday API server
│   ├── telegram_bot.py            # Telegram bot interface
│   ├── notify.py                  # Notification library
│   └── homelab_monitor.py         # Monitoring agent
│
├── scripts/                       # Utility scripts
│   ├── monitoring/                # Monitoring scripts
│   ├── system/                    # System management
│   ├── vllm/                      # vLLM management
│   └── testing/                   # Tests
│
├── services/                      # Systemd services
├── config/                        # Configuration
├── docs/                          # Documentation
├── data/                          # Data storage
└── logs/                          # Log files
```

## Friday CLI Tool

```bash
./friday status        # Show service status
./friday logs friday   # View logs
./friday notify "msg"  # Send notification
./friday report        # Status report
./friday test          # Run tests
./friday restart all   # Restart services
```

## Update Services

```bash
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
./friday restart all
```
