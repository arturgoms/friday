#!/bin/bash

# Check if TrueNAS vault is mounted (non-root version)
# This runs before Friday starts to ensure the vault is accessible

MOUNT_POINT="/mnt/friday-pool"
VAULT_PATH="$MOUNT_POINT/artur/secure/my-brain"

echo "Checking TrueNAS mount..."

# Check if mounted
if ! mountpoint -q "$MOUNT_POINT"; then
    echo "ERROR: TrueNAS not mounted at $MOUNT_POINT"
    echo "Please run: sudo mount -a"
    exit 1
fi

echo "✓ TrueNAS mounted"

# Check if vault is accessible
if [ ! -d "$VAULT_PATH" ]; then
    echo "ERROR: Vault not accessible at $VAULT_PATH"
    exit 1
fi

echo "✓ Vault accessible"

# Count files
MD_COUNT=$(find "$VAULT_PATH" -name "*.md" -type f 2>/dev/null | wc -l)
echo "✓ Found $MD_COUNT markdown files"

exit 0
