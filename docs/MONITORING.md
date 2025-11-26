# Friday AI - Homelab Monitoring & Notifications

## Overview
Friday can now send you Telegram notifications about your homelab status!

## Features

### Automated Monitoring
- **Service Health**: vLLM, Friday API, Telegram Bot
- **GPU Monitoring**: Temperature, utilization, memory usage
- **Disk Space**: Root partition and TrueNAS mount
- **System Memory**: RAM usage tracking
- **Friday API**: Vault chunks, memories, health status

### Alert System
- Automatic alerts when thresholds are exceeded
- Smart cooldown to prevent spam (5 min between same alerts)
- Severity levels: info, warning, error, success, critical

## Quick Start

### Send a Manual Notification
```bash
cd friday
./send_notification.sh "Your message here" warning
```

### Get Status Report
```bash
cd friday
./status_report.sh
```

### Test from Python
```python
from notify import FridayNotifier

notifier = FridayNotifier()
notifier.send_alert("Test", "This is a test!", "success")
```

## Install Monitoring Service

To enable continuous monitoring:

```bash
# Copy service file
sudo cp friday/homelab-monitor.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable homelab-monitor.service
sudo systemctl start homelab-monitor.service

# Check status
sudo systemctl status homelab-monitor.service

# View logs
tail -f friday/homelab_monitor.log
```

## Configuration

Edit `monitor_config.env` to adjust thresholds:

```env
GPU_TEMP_THRESHOLD=85       # Alert if GPU temp > 85°C
GPU_UTIL_THRESHOLD=95       # Alert if GPU util > 95%
DISK_USAGE_THRESHOLD=90     # Alert if disk > 90% full
MEMORY_THRESHOLD=90         # Alert if RAM > 90% used
CHECK_INTERVAL=300          # Check every 5 minutes
```

## Alert Thresholds (Current)

- 🌡️ **GPU Temperature**: 85°C
- 📊 **GPU Utilization**: 95%
- 💾 **Disk Usage**: 90%
- 🧠 **Memory Usage**: 90%
- ⏱️ **Check Interval**: 300 seconds (5 min)
- 🔕 **Alert Cooldown**: 300 seconds (5 min)

## Use Cases

### Script Integration
Add to any script:
```bash
#!/bin/bash
# Your script here
if [ $? -ne 0 ]; then
    cd /home/artur/friday
    ./send_notification.sh "Script failed!" error
fi
```

### Cron Jobs
Add to crontab for scheduled reports:
```bash
# Daily status report at 9 AM
0 9 * * * /home/artur/friday/status_report.sh

# Weekly backup notification
0 0 * * 0 /home/artur/friday/send_notification.sh "Weekly backup starting" info
```

### Python Scripts
```python
from notify import FridayNotifier, notify

# Quick notification
notify("Backup complete!", "success")

# Detailed alert
notifier = FridayNotifier()
notifier.send_alert(
    "Backup Status",
    "Backed up 1.2TB in 45 minutes\nAll systems nominal",
    "success"
)
```

## Available Functions

### notify.py

**FridayNotifier class:**
- `send_message(message, parse_mode="Markdown")` - Send raw message
- `send_alert(title, message, severity)` - Send formatted alert
- `send_system_status(status_dict)` - Send status report

**Quick function:**
- `notify(message, severity)` - One-line notification

### homelab_monitor.py

**HomelabMonitor class:**
- `check_services()` - Check systemd services
- `check_gpu()` - Monitor GPU stats
- `check_disk_usage()` - Check disk space
- `check_memory()` - Check RAM usage
- `check_friday_api()` - Check Friday health
- `send_status_report()` - Send comprehensive report
- `run_monitoring_cycle()` - Run one check cycle
- `start(interval)` - Start continuous monitoring

## Examples

### Example 1: Backup Script
```bash
#!/bin/bash
./send_notification.sh "Starting backup..." info

rsync -av /data /backup
if [ $? -eq 0 ]; then
    ./send_notification.sh "Backup successful!" success
else
    ./send_notification.sh "Backup failed!" error
fi
```

### Example 2: GPU Training Notification
```python
from notify import notify

# Start training
notify("GPU training started", "info")

# ... your training code ...

notify(f"Training complete! Loss: {final_loss:.4f}", "success")
```

### Example 3: Docker Container Monitor
```bash
#!/bin/bash
CONTAINER="nextcloud"

if ! docker ps | grep -q $CONTAINER; then
    cd /home/artur/friday
    ./send_notification.sh "Docker container $CONTAINER is down!" critical
fi
```

## Monitoring Service

The monitoring service (when installed) will:
1. Check all systems every 5 minutes
2. Send alerts when thresholds are exceeded
3. Respect cooldown periods to avoid spam
4. Track alert history
5. Log all activity to `homelab_monitor.log`

### Service Commands
```bash
# Start
sudo systemctl start homelab-monitor.service

# Stop
sudo systemctl stop homelab-monitor.service

# Restart
sudo systemctl restart homelab-monitor.service

# View logs
journalctl -u homelab-monitor.service -f
tail -f friday/homelab_monitor.log
```

## Troubleshooting

**Notifications not arriving?**
1. Check bot token in `.env`
2. Check user ID in `.env`
3. Test: `./send_notification.sh "test" info`
4. Check logs: `tail homelab_monitor.log`

**Service not starting?**
1. Check service status: `sudo systemctl status homelab-monitor.service`
2. Check logs: `journalctl -u homelab-monitor.service -n 50`
3. Verify python path in service file
4. Test manually: `python homelab_monitor.py report`

## Future Enhancements

Possible additions:
- [ ] Web dashboard for monitoring
- [ ] Historical data and graphs
- [ ] Email notifications as backup
- [ ] Integration with other homelab services
- [ ] Custom monitoring plugins
- [ ] Predictive alerts using AI
- [ ] Mobile app integration

---

**Created**: 2025-11-22
**Status**: Production Ready
