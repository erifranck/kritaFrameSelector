#!/bin/bash
#
# Install Frame Selector plugin to Krita's plugin directory.
#
# Usage:
#   ./install.sh          # Installs to the default Krita pykrita directory
#   ./install.sh <path>   # Installs to a custom path
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect OS and set default Krita plugin path
case "$(uname -s)" in
Darwin)
	DEFAULT_KRITA_DIR="$HOME/Library/Application Support/krita/pykrita"
	;;
Linux)
	DEFAULT_KRITA_DIR="$HOME/.local/share/krita/pykrita"
	;;
MINGW* | MSYS* | CYGWIN*)
	DEFAULT_KRITA_DIR="$APPDATA/krita/pykrita"
	;;
*)
	echo "Unknown OS. Please provide the Krita pykrita directory as argument."
	exit 1
	;;
esac

KRITA_DIR="${1:-$DEFAULT_KRITA_DIR}"

echo "=== Frame Selector - Krita Plugin Installer ==="
echo ""
echo "Target directory: $KRITA_DIR"
echo ""

# Create the target directory if it doesn't exist
mkdir -p "$KRITA_DIR"

# 1. Copy the .desktop file to pykrita root (Krita requires this!)
cp "$SCRIPT_DIR/frame_selector.desktop" "$KRITA_DIR/frame_selector.desktop"
echo "Installed: frame_selector.desktop -> $KRITA_DIR/"

# 2. Copy plugin package to pykrita/frame_selector/
PLUGIN_DIR="$KRITA_DIR/frame_selector"
rm -rf "$PLUGIN_DIR"
cp -r "$SCRIPT_DIR/frame_selector" "$PLUGIN_DIR"
echo "Installed: frame_selector/ -> $PLUGIN_DIR/"

# Remove the .desktop from inside the package (it lives at root level)
rm -f "$PLUGIN_DIR/frame_selector.desktop"

echo ""
echo "Files installed:"
echo "  $KRITA_DIR/frame_selector.desktop"
find "$PLUGIN_DIR" -type f | sort | while read f; do
	echo "  $f"
done
echo ""
echo "Done! Restart Krita and enable the plugin in:"
echo "  Settings > Configure Krita > Python Plugin Manager > Frame Selector"
echo ""
