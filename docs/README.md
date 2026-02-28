# Documentation Index

Technical documentation for the KritaFrameSelector plugin development.

## Available Documents

| Document | Description |
|----------|-------------|
| [TIMELINE_WORKAROUND.md](TIMELINE_WORKAROUND.md) | **CRITICAL** - Explains the Qt introspection workaround to detect Timeline vs Layer panel desync and prevent destructive cloning bugs. |
| [KRITA_FORMAT_SPECS.md](KRITA_FORMAT_SPECS.md) | Deep dive into the `.kra` file format (ZIP structure, XML schemas, layer/frame storage). |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Known bugs, API limitations, and their current status (including the Timeline Mismatch fix). |

## Quick Reference

### Timeline Selection Sync (SOLVED)
- **Problem:** Krita clones frames into Timeline selection, not the Active Layer from the Layers Panel.
- **Solution:** Qt introspection via `timeline_debugger.py` to read `QAbstractItemView` selection, map layer tree to row indexes, and block cloning if mismatch detected.
- **Files involved:** `frame_selector/timeline_debugger.py`, `frame_selector_docker.py`

### Key Files
- `frame_selector/timeline_debugger.py` - Core logic for Timeline introspection
- `frame_selector/frame_manager.py` - Cloning operations
- `frame_selector/frame_selector_docker.py` - UI and validation entry point
