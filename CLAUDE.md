# CLAUDE.md — Project Context for AI Assistant
**Project:** KritaFrameSelector — Krita Python Plugin for Animation Frame Reuse
**Version:** 1.0

---

## Project Overview
A Krita plugin (Python) that analyzes `.kra` animation files to detect unique frames vs clones, displays them as thumbnails in a Docker panel, and allows one-click cloning to the current timeline position.

**Core Value:** Krita clones share memory — editing one updates all instances. This plugin makes that workflow visual and fast.

---

## Architecture

```
KritaFrameSelector/
├── frame_selector/
│   ├── __init__.py           # Plugin entry point (registers Docker)
│   ├── krita_parser.py       # .kra ZIP/XML forensic analyzer
│   ├── frame_manager.py      # Core logic: scan, clone, validate
│   ├── frame_store.py        # JSON persistence for registered frames
│   ├── frame_selector_docker.py  # Qt UI (Docker panel)
│   ├── frame_thumbnail_delegate.py # Custom card rendering
│   ├── timeline_debugger.py  # Timeline selection introspection (Qt hack)
│   ├── thumbnail_cache.py    # Persistent thumbnail storage
│   ├── thumbnail_worker.py   # Async thumbnail generation
│   ├── drawing_monitor.py    # Detects user drawing to auto-refresh
│   └── manual.html           # Plugin help
├── docs/                     # Technical documentation
│   ├── KRITA_FORMAT_SPECS.md # .kra file format deep dive
│   ├── TIMELINE_WORKAROUND.md # Timeline selection sync solution
│   └── KNOWN_ISSUES.md      # Known bugs and API limitations
├── frame_selector.desktop    # Krita plugin descriptor
├── install.sh                # Developer install script
├── build_zip.sh              # Build distributable ZIP
├── README.md                 # English documentation
├── README_ES.md              # Spanish documentation
├── CLAUDE.md                 # AI context (this file)
└── AGENT.md                  # AI developer guide
```

---

## Key Technical Decisions

1. **Forensic .kra Analysis:** Plugin saves document first, then reads ZIP directly. Does NOT rely on Krita's internal APIs for frame metadata.

2. **Clone Detection:** In `keyframes.xml`, if two `<keyframe>` elements share the same `frame` attribute value, they are clones (Many-to-One mapping).

3. **Namespace-Agnostic XML Parsing:** Krita's `maindoc.xml` uses `xmlns="http://www.calligra.org/DTD/krita"`. Use `tree.iter()` + check `elem.tag.endswith('layer')` instead of `findall(".//layer")`.

4. **Empty Frame Filtering:** Frames with file size < 100 bytes in the ZIP are considered empty/transparent placeholders.

5. **Frame Name vs Timeline Position:** Internal filenames (e.g., `layer5.f3`) do NOT correspond to timeline positions. Always trust the `time` attribute in `keyframes.xml`.

6. **Debugging:** Python `print()` doesn't show reliably in Krita Log Viewer on macOS. Use `QMessageBox.information()` for debug popups.

---

## Plugin Installation

### ZIP Import (Users)
```bash
./build_zip.sh  # Creates frame_selector.zip
# Tools > Scripts > Import Python Plugin from File... > select ZIP
```

### Developer Install
```bash
./install.sh  # Auto-detects OS (macOS/Linux/Windows)
```

---

## Important Gotchas

- **File Lock:** `.kra` must be saved before analysis. Krita holds a write lock.
- **Active Layer:** Clones are always placed on the currently selected layer.
- **Refresh Required:** After manual frame changes, user must click Refresh button.
- **Dependencies:** No external deps — uses Krita's bundled Python + PyQt5.

---

## Common Tasks

- **Add new feature:** Edit files in `frame_selector/` directory.
- **Build release ZIP:** Run `./build_zip.sh` — produces `frame_selector.zip` with correct structure.
- **Debug UI:** Use `QMessageBox` for popup alerts instead of `print()`.
- **Test:** Requires running inside Krita's Python environment.

---

## Context Detection System

The plugin uses a multi-layered approach to detect document and layer changes:

### 1. Canvas Change Detection (`canvasChanged`)
- Krita calls `canvasChanged(canvas)` when the active document changes
- This triggers `_on_context_changed()` via a debounced timer (300ms)
- Updates document name, layer ID, and reloads the grid

### 2. Layer Change Detection (Polling)
- **Problem:** Krita does NOT provide a signal when user switches layers in the layer panel
- **Solution:** Polling timer that checks active layer every 500ms
- Implemented in `frame_selector_docker.py`:
  - `_layer_polling_timer`: QTimer that runs continuously
  - `_check_layer_change()`: Compares current layer ID with stored ID
  - Triggers grid reload when layer changes

### 3. Context Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    FrameSelectorDocker                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    canvasChanged    ┌─────────────────┐  │
│  │ Krita Event  │ ─────────────────►   │ _on_context_   │  │
│  │ (document    │                      │ changed()      │  │
│  │  change)     │                      └────────┬────────┘  │
│  └──────────────┘                              │            │
│                                               │            │
│                                               ▼            │
│                                      ┌─────────────────┐    │
│                                      │ Update context  │    │
│                                      │ + start timer   │    │
│                                      └────────┬────────┘    │
│                                               │            │
│  ┌──────────────┐    every 500ms    ┌────────▼────────┐   │
│  │ _layer_      │ ◄───────────────── │ _check_layer_   │   │
│  │ polling_     │                    │ change()        │   │
│  │ timer       │                    └─────────────────┘   │
│  └──────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. Key Variables

| Variable | Type | Description |
|----------|------|-------------|
| `_current_doc_name` | str \| None | Current document filename |
| `_current_layer_id` | str \| None | Active layer UUID (persists across renames) |
| `_current_layer_name` | str \| None | Active layer display name |

### 5. What Happens When Layer Changes

1. Timer fires every 500ms
2. Gets current layer ID via `FrameManager.get_layer_id()`
3. Compares with stored `_current_layer_id`
4. If different:
   - Updates `_current_layer_id` and `_current_layer_name`
   - Updates label (e.g., "document.kra · Layer2")
   - Calls `_reload_grid()` to show frames from new layer
   - Updates status message

### 6. Smart Cache Behavior

- When user clicks "Refresh", plugin scans ALL layers and stores frames for each
- Frames are persisted in `FrameStore` (JSON)
- When switching layers, `_reload_grid()` loads frames for the new layer from storage
- Thumbnails are cached in `ThumbnailCache` and loaded asynchronously
