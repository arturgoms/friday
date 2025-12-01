#!/bin/bash

# Check if brain folder is accessible before Friday starts
# Brain is now synced via Syncthing to ~/friday/brain/

BRAIN_PATH="/home/artur/friday/brain"
VAULT_PATH="$BRAIN_PATH/1. Notes"

echo "Checking brain folder..."

# Check if brain folder exists
if [ ! -d "$BRAIN_PATH" ]; then
    echo "ERROR: Brain folder not found at $BRAIN_PATH"
    exit 1
fi

echo "✓ Brain folder exists"

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
