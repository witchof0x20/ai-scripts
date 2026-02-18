#!/bin/sh
# Process all PNGs in input/ into SVG layers in output/<name>/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_DIR="$SCRIPT_DIR/input"
OUTPUT_DIR="$SCRIPT_DIR/output"

args=""
for png in "$INPUT_DIR"/*.png; do
    [ -f "$png" ] || continue
    name="$(basename "$png" .png)"
    args="$args $png $OUTPUT_DIR/$name"
done

if [ -z "$args" ]; then
    echo "No PNGs found in $INPUT_DIR/" >&2
    exit 1
fi

# shellcheck disable=SC2086
python3 "$SCRIPT_DIR/split.py" $args
