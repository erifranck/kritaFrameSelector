# Known Issues & API Limitations

> **Status Update (Feb 2026):** The Timeline Mismatch issue has been **RESOLVED** via Qt introspection! See [TIMELINE_WORKAROUND.md](TIMELINE_WORKAROUND.md) for the full technical explanation.

---

## Timeline Cursor vs Active Layer Mismatch (Clone Bug)

### Description
There is a fundamental disconnect between Krita's **Layers Panel** and the **Timeline Docker** that cannot be resolved via the current Krita Python API. 

When a user clicks on a cell in the Timeline Docker, that row becomes the target for timeline actions. However, doing so **does not necessarily change the active layer** (`doc.activeNode()`). 

### The Bug Scenario
1. The user selects **Layer B** in the Layers Panel (making it the active node).
2. The Frame Selector plugin reads Layer B and displays its frames.
3. The user clicks on a frame cell in the Timeline Docker that belongs to **Layer A's** row.
4. The user clicks a frame card in the plugin to clone it.
5. The plugin executes Krita's native actions: `copy_frames_as_clones` and `paste_frames`.
6. **Result:** Krita copies and pastes the frame into **Layer A** (the timeline selection), completely ignoring that **Layer B** is the active node.

### Why this is a blocker
The Krita Python API provides:
- `doc.currentTime()` -> Gets the column (frame number).
- `doc.activeNode()` -> Gets the active layer from the Layers panel.

**The API DOES NOT provide:**
- Any method to read which row/cell is currently highlighted in the Timeline Docker.
- Any method to force the Timeline Docker's selection to sync with `activeNode()`.
- A direct data-level method to clone a frame (e.g., `node.cloneFrame(time)`). We are forced to use UI actions (`action("copy_frames_as_clones").trigger()`), which rely on the UI's internal state.

### SOLUTION IMPLEMENTED ✅

We solved this using **Qt introspection**:
1. Use `Krita.instance().dockers()` to find the Timeline Docker
2. Use `findChildren(QAbstractItemView)` to locate the internal selection model
3. Read `selectionModel().selectedIndexes()` to get the current row/column
4. Manually traverse the Krita layer tree to map layer UUIDs to timeline row indexes
5. Compare the calculated row for `doc.activeNode()` vs the timeline selection
6. **Block cloning and show a warning** if there's a mismatch

See [TIMELINE_WORKAROUND.md](TIMELINE_WORKAROUND.md) for the complete technical details.

---

## Future Ideas to Explore (Other Limitations)

1. **Post-Clone Heuristic Validation (Undo Hack):**
   - Save the state/hash/bounds of the target frame on `activeNode()` before cloning.
   - Execute the clone actions.
   - Check if the `activeNode()` actually received the new clone data.
   - If not, it means Krita pasted it into another layer. Trigger `doc.undo()` immediately and show an error to the user: *"Timeline cursor is on the wrong layer. Please click a cell in the active layer's row."*

2. **Undocumented API Research:**
   - Investigate Krita's C++ source code to see if there are undocumented PyQt signals or QObjects accessible via `Krita.instance().dockers()` to read the timeline selection.

3. **Direct XML Manipulation:**
   - Bypass Krita's memory and edit `keyframes.xml` directly, then force Krita to reload the document. (Highly disruptive to workflow, but guarantees exact placement).