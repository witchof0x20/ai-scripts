#!/bin/sh
# Generate 3MF files from all input PNGs and upload to a remote destination via scp.
# Usage: ./generate_and_upload.sh server:path/to/dir/
set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 DESTINATION" >&2
    echo "  e.g. $0 myserver:prints/claudemoji/" >&2
    exit 1
fi

DEST="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Generating 3MFs ==="
sh "$SCRIPT_DIR/split_all.sh"

ZIP="$SCRIPT_DIR/output/claudemoji.zip"
echo ""
echo "=== Zipping 3MFs ==="
cd "$SCRIPT_DIR/output"
zip -j "$ZIP" ./*/*.3mf
cd "$SCRIPT_DIR"

echo ""
echo "=== Uploading to $DEST ==="
scp "$ZIP" "$DEST"

echo ""
echo "Done! Uploaded claudemoji.zip to $DEST"
