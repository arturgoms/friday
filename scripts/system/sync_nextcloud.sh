#!/bin/bash

# Trigger Nextcloud file rescan after reindexing
# This ensures Nextcloud sees changes made through TrueNAS/Friday

NEXTCLOUD_HOST="192.168.1.16"
NEXTCLOUD_USER="friday"
NEXTCLOUD_PASS="flashBall3003!"
NEXTCLOUD_CONTAINER="nextcloud"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}!${NC} $1"
}

log_step() {
    echo -e "${BLUE}→${NC} $1"
}

echo "================================"
echo "Nextcloud File Rescan"
echo "================================"
echo ""

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    log_error "sshpass not found. Install it with:"
    echo "  sudo apt install -y sshpass"
    exit 1
fi

# Test connection
log_step "Testing connection to Nextcloud server..."
if ! ping -c 1 -W 2 "$NEXTCLOUD_HOST" > /dev/null 2>&1; then
    log_error "Cannot reach Nextcloud server at $NEXTCLOUD_HOST"
    exit 1
fi
log_info "Server is reachable"

# Check if Nextcloud container is running
log_step "Checking Nextcloud container status..."
CONTAINER_STATUS=$(sshpass -p "$NEXTCLOUD_PASS" ssh -o StrictHostKeyChecking=no "$NEXTCLOUD_USER@$NEXTCLOUD_HOST" "docker ps --filter name=$NEXTCLOUD_CONTAINER --format '{{.Status}}'" 2>/dev/null)

if [ -z "$CONTAINER_STATUS" ]; then
    log_error "Nextcloud container '$NEXTCLOUD_CONTAINER' is not running"
    exit 1
fi

log_info "Container is running: $CONTAINER_STATUS"

# Trigger file rescan (LinuxServer.io container has 'occ' wrapper in PATH)
log_step "Triggering Nextcloud file rescan (this may take a few minutes)..."
echo ""

sshpass -p "$NEXTCLOUD_PASS" ssh -o StrictHostKeyChecking=no "$NEXTCLOUD_USER@$NEXTCLOUD_HOST" \
    "docker exec $NEXTCLOUD_CONTAINER occ files:scan artur" 2>&1

RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo ""
    log_info "Nextcloud file rescan completed successfully"
else
    echo ""
    log_error "Rescan failed with exit code: $RESULT"
    exit 1
fi

echo ""
echo "================================"
echo "Sync Complete"
echo "================================"
