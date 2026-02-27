"""
Thumbnail Cache — Repository Pattern.

Single source of truth for in-memory frame thumbnails.
Keyed by (doc_name, layer_id, frame_number) so entries survive layer
renames and are scoped to the correct document and layer.

Intentionally has no Krita API dependency — it only stores QPixmap objects
handed to it by ThumbnailWorker. This keeps it easy to test in isolation.
"""

from PyQt5.QtGui import QPixmap


class ThumbnailCache:
    """
    In-memory store for frame thumbnail pixmaps.

    ┌─────────────────────────────────────────┐
    │  (doc_name, layer_id, frame_number)     │
    │            ↓                            │
    │          QPixmap                        │
    └─────────────────────────────────────────┘
    """

    def __init__(self):
        self._store: dict[tuple, QPixmap] = {}

    # ── Read ──────────────────────────────────────────────────────

    def get(self, doc_name: str, layer_id: str, frame_number: int) -> QPixmap | None:
        """Return the cached pixmap or None if not yet generated."""
        return self._store.get((doc_name, layer_id, frame_number))

    def has(self, doc_name: str, layer_id: str, frame_number: int) -> bool:
        """Return True if a pixmap is already cached for this frame."""
        return (doc_name, layer_id, frame_number) in self._store

    # ── Write ─────────────────────────────────────────────────────

    def put(self, doc_name: str, layer_id: str, frame_number: int, pixmap: QPixmap):
        """Store a generated thumbnail."""
        self._store[(doc_name, layer_id, frame_number)] = pixmap

    # ── Invalidation ──────────────────────────────────────────────

    def invalidate(self, doc_name: str, layer_id: str):
        """Drop all cached thumbnails for a given document+layer.

        Call this before a Refresh scan so stale images don't persist
        when the frame set changes.
        """
        stale = [
            k for k in self._store
            if k[0] == doc_name and k[1] == layer_id
        ]
        for k in stale:
            del self._store[k]

    def clear(self):
        """Drop every cached thumbnail (e.g. on plugin shutdown)."""
        self._store.clear()

    # ── Diagnostics ───────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"ThumbnailCache({len(self._store)} entries)"