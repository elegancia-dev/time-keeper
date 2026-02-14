#!/bin/bash
# Install the native messaging host manifest for Chrome on macOS.
#
# Usage:
#   ./install-host.sh [extension-id]
#
# The extension ID is shown on chrome://extensions when developer mode is on.
# If omitted, you'll need to edit the manifest manually.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_DIR="$SCRIPT_DIR/native-host"
MANIFEST_SRC="$HOST_DIR/com.timekeeper.work_logger.json"
HOST_SCRIPT="$HOST_DIR/work_logger_host.py"

CHROME_NATIVE_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"

# Ensure host script is executable
chmod +x "$HOST_SCRIPT"

# Update path in manifest to absolute path of the host script
MANIFEST_DEST="$CHROME_NATIVE_DIR/com.timekeeper.work_logger.json"
mkdir -p "$CHROME_NATIVE_DIR"

# Build the manifest with correct absolute path and extension ID
EXTENSION_ID="${1:-UPDATE_WITH_YOUR_EXTENSION_ID}"

cat > "$MANIFEST_DEST" << EOF
{
  "name": "com.timekeeper.work_logger",
  "description": "Work Logger native messaging host for time-keeper",
  "path": "$HOST_SCRIPT",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXTENSION_ID/"]
}
EOF

echo "Installed native messaging host manifest to:"
echo "  $MANIFEST_DEST"
echo ""
echo "Host script: $HOST_SCRIPT"
if [ "$EXTENSION_ID" = "UPDATE_WITH_YOUR_EXTENSION_ID" ]; then
  echo ""
  echo "WARNING: No extension ID provided."
  echo "  Usage: ./install-host.sh <your-extension-id>"
  echo "  Find your extension ID at chrome://extensions (enable Developer mode)"
fi
