# Friday AI - Service Management

## Quick Install

To install all Friday AI services:

```bash
cd friday
./friday install-services
```

This will:
1. Copy all service files to `/etc/systemd/system/`
2. Reload systemd daemon
3. Enable services to start on boot
4. Ask if you want to enable homelab monitoring

After installation, start the services:
```bash
./friday restart all
```

## Individual Service Management

### Install Individual Service

```bash
sudo cp services/friday.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable friday.service
sudo systemctl start friday.service
```

### Check Service Status

```bash
# All services
./friday status

# Individual service
systemctl status friday.service
systemctl status vllm.service
systemctl status telegram-bot.service
systemctl status homelab-monitor.service
```

### View Logs

```bash
# Using Friday CLI
./friday logs friday
./friday logs vllm
./friday logs telegram_bot
./friday logs homelab_monitor

# Using systemctl
journalctl -u friday.service -f
journalctl -u vllm.service -f

# Direct log files
tail -f logs/friday.log
tail -f logs/vllm.log
```

### Restart Services

```bash
# Restart all
./friday restart all

# Restart individual service
./friday restart friday
./friday restart vllm
./friday restart telegram-bot

# Or directly
sudo systemctl restart friday.service
```

### Start/Stop Services

```bash
# Start
sudo systemctl start friday.service

# Stop
sudo systemctl stop friday.service

# Enable (start on boot)
sudo systemctl enable friday.service

# Disable (don't start on boot)
sudo systemctl disable friday.service
```

## Uninstall Services

To completely remove all services:

```bash
./friday uninstall-services
```

This will:
1. Stop all running services
2. Disable services from auto-start
3. Remove service files from `/etc/systemd/system/`
4. Reload systemd daemon

**Note**: This does NOT delete your data, code, or configuration - only the systemd service files.

## Service Overview

### vllm.service
- **Purpose**: Runs the vLLM inference server with Qwen2.5-7B
- **GPU**: Uses RTX 3090 (CUDA_VISIBLE_DEVICES=0)
- **Port**: 8000
- **Dependencies**: None
- **Restart**: Automatic (30s delay)

### friday.service
- **Purpose**: Main Friday AI FastAPI server
- **Port**: 8080
- **Dependencies**: vllm.service, TrueNAS mount
- **Restart**: Automatic (10s delay)
- **Pre-check**: Verifies TrueNAS mount before starting

### telegram-bot.service
- **Purpose**: Telegram bot interface
- **Dependencies**: friday.service
- **Restart**: Automatic (10s delay)
- **Auth**: Restricted to configured user ID

### homelab-monitor.service (Optional)
- **Purpose**: Monitors system and sends alerts
- **Check Interval**: 300 seconds (5 minutes)
- **Dependencies**: friday.service
- **Restart**: Automatic (10s delay)

## Troubleshooting

### Service won't start

```bash
# Check status
systemctl status friday.service

# View recent logs
journalctl -u friday.service -n 50

# View live logs
journalctl -u friday.service -f

# Check configuration
systemctl cat friday.service
```

### Service fails after update

```bash
# Reinstall services
./friday install-services

# Reload and restart
sudo systemctl daemon-reload
./friday restart all
```

### Brain folder issue

```bash
# Check brain folder
ls -la ~/friday/brain

# Test brain check script
bash scripts/system/check_brain.sh

# Check Syncthing status
systemctl --user status syncthing
```

### Port conflicts

```bash
# Check if ports are in use
sudo lsof -i :8000  # vLLM
sudo lsof -i :8080  # Friday API

# Stop conflicting services
sudo systemctl stop friday.service
```

## Service Logs Location

All logs are stored in `/home/artur/friday/logs/`:

- `vllm.log` - vLLM server logs
- `friday.log` - Friday API logs
- `telegram_bot.log` - Telegram bot logs
- `homelab_monitor.log` - Monitoring agent logs

## Auto-Start on Boot

All enabled services will automatically start when the system boots:

1. **vllm.service** starts first
2. **friday.service** starts after vLLM and TrueNAS mount
3. **telegram-bot.service** starts after Friday API
4. **homelab-monitor.service** starts after Friday API (if enabled)

## Manual Service Control

If you prefer not to use the Friday CLI:

```bash
# Enable all services
sudo systemctl enable vllm.service friday.service telegram-bot.service

# Start all services
sudo systemctl start vllm.service
sudo systemctl start friday.service
sudo systemctl start telegram-bot.service

# Check status
systemctl status vllm.service friday.service telegram-bot.service
```

## Service Dependencies

```
vllm.service
    ↓
friday.service (also depends on TrueNAS mount)
    ↓
├── telegram-bot.service
└── homelab-monitor.service (optional)
```

Services start in order based on their dependencies.

---

**Quick Reference:**
- Install: `./friday install-services`
- Status: `./friday status`
- Restart: `./friday restart all`
- Logs: `./friday logs [service]`
- Uninstall: `./friday uninstall-services`
