#!/bin/bash
# Quick script to send notifications from command line
# Usage: ./send_notification.sh "Your message here" [severity]
# Severity: info, warning, error, success, critical

MESSAGE="$1"
SEVERITY="${2:-info}"

cd /home/artur/friday
~/.local/share/virtualenvs/friday/bin/python << PYEOF
import sys
sys.path.insert(0, '/home/artur/friday/src')
from notify import FridayNotifier
notifier = FridayNotifier()
notifier.send_alert("Manual Alert", "$MESSAGE", "$SEVERITY")
PYEOF

echo "Notification sent!"
