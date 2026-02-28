"""
Thumbnail Cache — Persistent Repository Pattern.

Thumbnails are keyed by (doc_name, layer_id, source_id) where source_id is
the internal .kra content reference (e.g. 'layer5.f3').  This makes the
cache position-agnostic: if the user drags frame 0 to position 5, the
thumbnail is still valid because the content identity hasn't changed.

Storage layout on disk:
    <krita_config>/frame_selector_thumbs/
        <dir_key>/          ← md5(doc_name::layer_id)
            <source_id>.png ← e.g. "layer5.f3.png"

Two layers:
  1. Memory dict  — fast reads, session-lifetime
  2. Disk (PNG)   — persists across Krita restarts
"""

import hashlib
import os
import shutil

from PyQt5.QtGui import QPixmap


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_cache_dir() -> str:
    """Return the root thumbnail cache directory for the current OS."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
        base = os.path.join(
            os.path.expanduser("~"), "Library", "Application Support"
        )
    else:
        base = os.environ.get(
            "XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share"),
        )
    return os.path.join(base, "krita", "frame_selector_thumbs")


def _dir_key(doc_name: str, layer_id: str) -> str:
    """Stable, filesystem-safe directory name for a doc+layer pair."""
    return hashlib.md5(f"{doc_name}::{layer_id}".encode()).hexdigest()


# ── Cache ─────────────────────────────────────────────────────────────────────

class ThumbnailCache:
    """
    Two-layer thumbnail repository keyed by content identity, not position.

    ┌──────────────────────────────────────────────────────┐
    │  key: (doc_name, layer_id, source_id)               │
    │       e.g. ('walk.kra', '{uuid}', 'layer5.f3')      │
    │                    ↓                                 │
    │     memory dict  ──┤                                 │
    │     disk PNG     ──┘  QPixmap                        │
    └──────────────────────────────────────────────────────┘

    source_id is the internal .kra XML reference (e.g. 'layer5.f3').
    Using it instead of the frame number means the thumbnail survives
    timeline repositioning — the content identity never changes.
    """

    def __init__(self):
        self._root = _get_cache_dir()
        # mem_key → QPixmap   (mem_key = "<dir_key>/<source_id>")
        self._memory: dict[str, QPixmap] = {}

    # ── Internal path helpers ─────────────────────────────────────────────────

    def _layer_dir(self, doc_name: str, layer_id: str) -> str:
        return os.path.join(self._root, _dir_key(doc_name, layer_id))

    def _disk_path(self, doc_name: str, layer_id: str, source_id: str) -> str:
        return os.path.join(self._layer_dir(doc_name, layer_id), f"{source_id}.png")

    def _mem_key(self, doc_name: str, layer_id: str, source_id: str) -> str:
        return f"{_dir_key(doc_name, layer_id)}/{source_id}"

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self, doc_name: str, layer_id: str, source_id: str) -> "QPixmap | None":
        """Return cached pixmap (memory-first, then disk) or None."""
        key = self._mem_key(doc_name, layer_id, source_id)

        if key in self._memory:
            return self._memory[key]

        path = self._disk_path(doc_name, layer_id, source_id)
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self._memory[key] = pm   # warm the memory layer
                return pm

        return None

    def has(self, doc_name: str, layer_id: str, source_id: str) -> bool:
        """Return True if a thumbnail exists (memory or disk)."""
        key = self._mem_key(doc_name, layer_id, source_id)
        return (
            key in self._memory
            or os.path.exists(self._disk_path(doc_name, layer_id, source_id))
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def put(self, doc_name: str, layer_id: str, source_id: str, pixmap: QPixmap):
        """Store a thumbnail in memory and persist to disk."""
        key = self._mem_key(doc_name, layer_id, source_id)
        self._memory[key] = pixmap

        layer_dir = self._layer_dir(doc_name, layer_id)
        try:
            os.makedirs(layer_dir, exist_ok=True)
            pixmap.save(self._disk_path(doc_name, layer_id, source_id), "PNG")
        except OSError as e:
            print(f"[ThumbnailCache] Could not write to disk: {e}")

    # ── Invalidation ──────────────────────────────────────────────────────────

    def invalidate_entry(self, doc_name: str, layer_id: str, source_id: str):
        """Remove one thumbnail — call this after the user redraws that frame."""
        key = self._mem_key(doc_name, layer_id, source_id)
        self._memory.pop(key, None)

        path = self._disk_path(doc_name, layer_id, source_id)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            print(f"[ThumbnailCache] Could not delete thumbnail: {e}")

    def invalidate(self, doc_name: str, layer_id: str):
        """Drop all thumbnails for a doc+layer — call before a Refresh scan."""
        dk = _dir_key(doc_name, layer_id)
        stale = [k for k in self._memory if k.startswith(dk)]
        for k in stale:
            del self._memory[k]

        layer_dir = self._layer_dir(doc_name, layer_id)
        try:
            if os.path.exists(layer_dir):
                shutil.rmtree(layer_dir)
        except OSError as e:
            print(f"[ThumbnailCache] Could not remove cache dir: {e}")

    def clear(self):
        """Drop everything — memory and all disk files."""
        self._memory.clear()
        try:
            if os.path.exists(self._root):
                shutil.rmtree(self._root)
        except OSError as e:
            print(f"[ThumbnailCache] Could not clear cache root: {e}")

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._memory)

    def __repr__(self) -> str:
        return f"ThumbnailCache({len(self._memory)} in memory, root={self._root})"