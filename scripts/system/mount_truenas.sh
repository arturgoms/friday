#!/bin/bash

# Mount TrueNAS vault for Friday AI
# This ensures the vault is mounted before Friday services start

TRUENAS_IP="192.168.1.17"
SHARE="data-pool"
MOUNT_POINT="/mnt/friday-pool"
VAULT_PATH="$MOUNT_POINT/artur/secure/my-brain"
CREDENTIALS="/root/smbcredentials"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root: sudo bash $0"
    exit 1
fi

echo "================================"
echo "TrueNAS Mount Check"
echo "================================"
echo ""

# Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    log_info "Already mounted: $MOUNT_POINT"
    
    # Verify vault is accessible
    if [ -d "$VAULT_PATH" ]; then
        MD_COUNT=$(find "$VAULT_PATH" -name "*.md" -type f 2>/dev/null | wc -l)
        log_info "Vault accessible: $MD_COUNT markdown files"
        exit 0
    else
        log_warn "Mounted but vault not accessible at: $VAULT_PATH"
        log_warn "Remounting..."
        umount "$MOUNT_POINT" 2>/dev/null
    fi
fi

# Check network connectivity
log_info "Checking TrueNAS connectivity..."
if ! ping -c 1 -W 2 "$TRUENAS_IP" > /dev/null 2>&1; then
    log_error "Cannot reach TrueNAS at $TRUENAS_IP"
    log_error "Check network connection"
    exit 1
fi
log_info "TrueNAS is reachable"

# Check credentials file
if [ ! -f "$CREDENTIALS" ]; then
    log_error "Credentials file not found: $CREDENTIALS"
    log_error "Create it with:"
    echo "  echo 'username=friday' | sudo tee $CREDENTIALS"
    echo "  echo 'password=YOUR_PASSWORD' | sudo tee -a $CREDENTIALS"
    echo "  sudo chmod 600 $CREDENTIALS"
    exit 1
fi

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    mkdir -p "$MOUNT_POINT"
    chown 1000:1000 "$MOUNT_POINT"
    log_info "Created mount point: $MOUNT_POINT"
fi

# Mount the share
log_info "Mounting //$TRUENAS_IP/$SHARE..."
mount -t cifs "//$TRUENAS_IP/$SHARE" "$MOUNT_POINT" \
    -o credentials="$CREDENTIALS",uid=1000,gid=1000,dir_mode=0770,file_mode=0660,mfsymlinks

if [ $? -ne 0 ]; then
    log_error "Mount failed!"
    log_error "Check credentials in $CREDENTIALS"
    exit 1
fi

# Verify mount
if ! mountpoint -q "$MOUNT_POINT"; then
    log_error "Mount command succeeded but mount point not active"
    exit 1
fi

log_info "Successfully mounted: $MOUNT_POINT"

# Verify vault accessibility
if [ ! -d "$VAULT_PATH" ]; then
    log_error "Vault not found at: $VAULT_PATH"
    log_error "Available directories:"
    ls -la "$MOUNT_POINT/" 2>/dev/null | head -10
    exit 1
fi

# Count files
MD_COUNT=$(find "$VAULT_PATH" -name "*.md" -type f 2>/dev/null | wc -l)
log_info "Vault accessible: $MD_COUNT markdown files found"

echo ""
echo "================================"
echo "Mount Status: Ready"
echo "================================"
exit 0
