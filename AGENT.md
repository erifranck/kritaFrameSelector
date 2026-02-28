# AGENT.md — AI Agent Instructions for KritaFrameSelector

This document provides guidance for AI agents working on the KritaFrameSelector codebase. It assumes you have familiarity with Python, PyQt5/Qt, and basic plugin development concepts.

---

## Working with This Codebase

### Environment Context
- **Runtime:** Krita's embedded Python 3 environment (NOT your system Python)
- **Available Modules:** `krita`, `PyQt5`, standard library only
- **No external dependencies** — do NOT add `pip install` commands

### Key Files & Responsibilities

| File | Purpose |
|------|---------|
| `krita_parser.py` | Opens `.kra` as ZIP, parses XML, detects unique frames vs clones |
| `frame_manager.py` | Orchestrates scanning, cloning, validates frame content |
| `frame_selector_docker.py` | Qt Docker panel UI — buttons, list view, refresh logic |
| `frame_thumbnail_delegate.py` | Custom rendering for frame cards in the list |

---

## Code Patterns & Conventions

### 1. XML Parsing (Namespace-Agnostic)
```python
# WRONG — namespace breaks findall
tree.findall(".//layer")

# CORRECT — iterate and check tag ending
for elem in tree.iter():
    if elem.tag.endswith("layer"):
        # process layer
```

### 2. Clone Detection Logic
Read `keyframes.xml` for each layer. Track unique `frame` IDs:
- First occurrence of `frame="X"` = **unique frame**
- Subsequent occurrences = **clones**

### 3. Empty Frame Detection
Check ZIP file size before processing:
```python
zip_info = zipfile.getinfo(frame_filename)
if zip_info.file_size < 100:
    # skip — empty/transparent placeholder
```

### 4. Debugging in Krita
```python
# print() is unreliable on macOS Krita Log Viewer
from PyQt5.QtWidgets import QMessageBox
QMessageBox.information(None, "Debug", f"Value: {variable}")
```

---

## Testing Workflows

### Manual Testing (Required)
1. Open Krita
2. Enable plugin: Settings → Configure Krita → Python Plugin Manager
3. Create/open an animation with multiple frames
4. Use the Docker panel to scan and clone frames

### Quick Validation Checklist
- [ ] Plugin loads without errors in Krita
- [ ] Refresh button scans and populates unique frames
- [ ] Clicking a frame card clones it to current timeline position
- [ ] Clones share memory (edit one, others update)
- [ ] Empty frames are filtered out
- [ ] Layer switching updates the grid automatically

---

## Layer Change Detection

Krita does NOT provide signals for layer panel changes, so the plugin uses polling:

### Implementation
```python
# In frame_selector_docker.py
self._layer_polling_timer = QTimer()
self._layer_polling_timer.setInterval(500)  # Check every 500ms
self._layer_polling_timer.timeout.connect(self._check_layer_change)

def _check_layer_change(self):
    current_layer_id = self._frame_manager.get_layer_id()
    if current_layer_id != self._current_layer_id:
        # Layer changed - reload grid
        self._reload_grid()
```

### Key Points
- Timer starts automatically when plugin loads
- Compares `node.uniqueId().toString()` between current and stored
- UUID survives layer renames (different from layer name)
- If no frames for new layer, shows "Click 'Refresh' to scan" message

### Adding a New UI Button
1. Edit `frame_selector_docker.py`
2. Add button to layout in `create_ui()` or similar method
3. Connect signal: `button.clicked.connect(self.handler_method)`
4. Implement handler in the same class

### Modifying Clone Detection
1. Edit `krita_parser.py` — function `detect_unique_frames()`
2. The logic relies on comparing `frame` attribute values in XML
3. Changes here affect what appears in the Docker panel

### Changing Thumbnail Rendering
1. Edit `frame_thumbnail_delegate.py`
2. Modify `paint()` method for visual changes
3. This uses Qt's delegate pattern for list items

---

## Critical Warnings

⚠️ **DO NOT** assume local Python environment matches Krita's
- Your machine: `python3 --version` → 3.x
- Krita's Python: different path, different packages
- Test inside Krita, not in terminal

⚠️ **DO NOT** use `print()` for debug on macOS
- Use `QMessageBox.information()` instead

⚠️ **DO NOT** read `.kra` without saving first
- Krita holds file lock; document must be saved
- Plugin calls `document.save()` before analyzing

---

## Build & Release

### Creating Distributable ZIP
```bash
./build_zip.sh
# Output: frame_selector.zip
# Structure: frame_selector.desktop + frame_selector/ package
```

### Git Commit Convention
- Use clear, concise commit messages
- Prefix: `Add`, `Fix`, `Refactor`, `Drop` (as seen in recent history)
- Example: `Drop(docker-panel): frame add and remove buttons`

---

## Reference Documents

- `KRITA_FORMAT_SPECS.md` — Full technical spec of .kra internal format
- `CLAUDE.md` — Project context for the primary AI assistant
