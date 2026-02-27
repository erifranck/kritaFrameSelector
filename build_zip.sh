#!/bin/bash
#
# Build the distributable ZIP file for Krita's "Import Python Plugin from File..." dialog.
#
# Krita expects the ZIP to contain:
#   frame_selector/          (plugin package directory)
#     __init__.py
#     ...other .py files...
#     manual.html
#   frame_selector.desktop   (plugin descriptor at root level)
#
# Usage:
#   ./build_zip.sh              # Creates frame_selector.zip in current directory
#   ./build_zip.sh <output>     # Creates ZIP at the specified path
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-$SCRIPT_DIR/frame_selector.zip}"

echo "=== Frame Selector - ZIP Builder ==="
echo ""

# Remove old ZIP if it exists
rm -f "$OUTPUT"

# Create the ZIP with the correct structure
# -x excludes __pycache__ and other unwanted files
cd "$SCRIPT_DIR"
zip -r "$OUTPUT" \
	frame_selector.desktop \
	frame_selector/__init__.py \
	frame_selector/frame_manager.py \
	frame_selector/frame_selector_docker.py \
	frame_selector/frame_store.py \
	frame_selector/frame_thumbnail_delegate.py \
	frame_selector/krita_parser.py \
	frame_selector/manual.html \
	-x "*.pyc" "__pycache__/*" ".DS_Store"

echo ""
echo "Created: $OUTPUT"
echo ""
echo "Contents:"
unzip -l "$OUTPUT"
echo ""
echo "To install: Open Krita > Tools > Scripts > Import Python Plugin from File..."
echo "Then select: $OUTPUT"
echo ""
