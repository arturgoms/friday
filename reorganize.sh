#!/bin/bash
# Reorganize friday directory structure

echo "Starting reorganization..."

# Move source files
mv main.py src/
mv telegram_bot.py src/
mv notify.py src/
mv homelab_monitor.py src/
mv app src/

# Move scripts
mv send_notification.sh scripts/monitoring/
mv status_report.sh scripts/monitoring/
mv monitor.sh scripts/monitoring/
mv mount_truenas.sh scripts/system/
mv check_truenas.sh scripts/system/
mv sync_nextcloud.sh scripts/system/
mv start_vllm.sh scripts/vllm/
mv test_friday.sh scripts/testing/
mv get_telegram_id.py scripts/testing/
mv run.sh scripts/vllm/ 2>/dev/null || true

# Move service files
mv *.service services/

# Move config files
mv monitor_config.env config/
mv setup_commands.sh config/

# Move documentation
mv QUICKSTART.md docs/
mv MONITORING.md docs/
mv TELEGRAM_SETUP.md docs/
mv NEXTCLOUD_SETUP.md docs/

# Move data
mv chroma_db data/

# Move logs
mv *.log logs/ 2>/dev/null || true

echo "✅ Reorganization complete!"
