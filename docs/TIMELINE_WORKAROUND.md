# The Timeline Selection Workaround

This document explains a critical workaround implemented in `KritaFrameSelector` to solve a destructive bug related to Krita's native frame cloning system.

## The Problem: The "Desynced Playhead" Bug

Krita maintains **two completely separate selection states** for layers:
1. **The Active Node** (`doc.activeNode()`): The layer currently highlighted in the standard Layers Docker.
2. **The Timeline Selection**: The specific cell (row + column) highlighted in the Animation Timeline Docker.

When triggering Krita's native action `copy_frames_as_clones` (which we use to share memory between frames), Krita **ignores the Active Node**. Instead, it pastes the clone into whatever row happens to be selected in the Timeline Docker. 

If a user selects Layer A in the Timeline, but then clicks Layer B in the Layers panel, they become **desynced**. If the plugin attempts to clone a frame while desynced, Krita pastes the frame into the wrong layer, destroying the user's animation.

## The Solution: Qt Introspection + Layer Tree Mapping

Because Krita's Python API does not provide a `.timelineSelection()` method, we must hack our way into the Timeline Docker using PyQt5 introspection to read the selected row, and then manually calculate which layer that row corresponds to.

### File Structure Reference

| File | Purpose | Key Methods |
|------|---------|-------------|
| `frame_selector/timeline_debugger.py` | Core logic to hack into the Timeline Docker and map the layer tree to row indexes. | `_explore_timeline_internals()`, `get_timeline_layer_order()`, `validate_clone_target()` |
| `frame_selector/frame_manager.py` | *Future integration:* Will use the debugger to abort cloning if a mismatch is detected. | `clone_frame_to_position()` |

---

## How It Works (Flowchart)

When the user attempts to clone a frame (or click Refresh for debugging), the plugin executes the following sequence:

```mermaid
graph TD
    Start[User clicks clone] --> A[Get Active Layer]
    A --> |doc.activeNode()| B(Active Node UUID & Name)
    
    Start --> C[Get Timeline Docker]
    C --> |Krita.instance().dockers()| D{Find Docker named\n'Animation Timeline'}
    D --> E[Find QAbstractItemView]
    E --> |selectionModel().selectedIndexes()| F(Selected Row Index)
    
    B --> G[Traverse Krita Layer Tree]
    G --> |Reverse Z-Index Order| H(Map UUIDs to Row Indexes)
    
    H --> I{Does Active Node Row\nmatch Timeline Row?}
    F --> I
    
    I -->|Yes| J[Allow Clone Action]
    I -->|No| K[Abort Clone\nShow Warning Mismatch!]
```

## 1. Reading the Timeline Selection

In `timeline_debugger.py`, we iterate through Krita's dockers to find the timeline.

```python
# Pseudo-code representation
for docker in Krita.instance().dockers():
    if "Timeline" in docker.windowTitle():
        # Find the table/tree views inside it
        views = docker.findChildren(QAbstractItemView)
        for view in views:
            indexes = view.selectionModel().selectedIndexes()
            if indexes:
                return indexes[0].row()  # Returns an integer (e.g., 2)
```

## 2. Mapping the Layer Tree

The Timeline Docker displays layers in a specific top-to-bottom visual order. 
To convert the Timeline's `Row: 2` into a Krita Layer UUID, we traverse the document's node tree.

- We skip the `root` node.
- Krita's `childNodes()` returns layers bottom-to-top (Z-index). The Timeline displays them top-to-bottom.
- We reverse the children `reversed(node.childNodes())` and increment a counter (`current_row`) for every layer we encounter.

```
Visual Layer Stack      Timeline Row    Krita Z-Index List
-----------------------------------------------------------
Layer 3                 Row 0           Index 2
Layer 2                 Row 1           Index 1
Layer 1                 Row 2           Index 0
```

## 3. The Validation Check

Finally, `validate_clone_target()` checks:
Is the row mapped to `doc.activeNode()` equal to the row reported by the Qt ItemView?

- **If MATCH:** Safe to clone.
- **If MISMATCH:** The user must be warned to click on the correct layer in the timeline before cloning, otherwise they risk ruining another layer.

---
*Note: This behavior relies on Krita's internal UI structure not changing significantly. If a future Krita update drastically changes the Animation Timeline Docker class names or views, `timeline_debugger.py` will need to be updated.*
