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
python3 "$SCRIPT_DIR/split.py" "$@" $args

# Detect faceless mode from args
faceless=false
for arg in "$@"; do
    if [ "$arg" = "--faceless" ]; then
        faceless=true
        break
    fi
done

# Build 3MF files
for png in "$INPUT_DIR"/*.png; do
    [ -f "$png" ] || continue
    name="$(basename "$png" .png)"
    if [ "$faceless" = "true" ]; then
        python3 "$SCRIPT_DIR/build_3mf.py" --faceless "$OUTPUT_DIR/$name" "$png"
    else
        python3 "$SCRIPT_DIR/build_3mf.py" "$OUTPUT_DIR/$name" "$png"
    fi
done
