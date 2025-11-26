#!/bin/bash
# Send a status report on demand
cd /home/artur/friday
~/.local/share/virtualenvs/friday/bin/python -c "import sys; sys.path.insert(0, 'src'); from homelab_monitor import HomelabMonitor; HomelabMonitor().send_status_report()"
echo "Status report sent!"
