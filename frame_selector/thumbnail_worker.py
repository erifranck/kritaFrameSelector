"""
Thumbnail Worker — Producer-Consumer Pattern.

Owns the async thumbnail generation queue.  The docker enqueues a batch
of (doc_name, layer_id, frame_number, source_id) entries; the worker drains
the queue one entry at a time using a single-shot QTimer so Krita's
projection has time to update between each capture.

Each entry carries its own (doc_name, layer_id) context so a single
Refresh call can generate thumbnails for *all* animated layers, not just
the currently active one.

source_id is the internal .kra content reference (e.g. 'layer5.f3').
Using it as the cache key means a thumbnail stays valid even if the user
repositions the frame on the timeline.

Signal flow:
    Docker.request_thumbnails(entries)
        → Worker filters out already-cached entries
        → Timer fires every LOAD_INTERVAL_MS
            → Worker resolves node by UUID, calls get_frame_thumbnail()
            → Worker stores result in ThumbnailCache under source_id key
            → Worker emits thumbnail_ready(doc_name, layer_id, frame_number, pixmap)
        → Docker._on_thumbnail_ready updates the grid item if context matches
"""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

# Gap between consecutive thumbnail captures (ms).
# Gives Krita's rendering engine time to flush the projection update
# triggered by setCurrentTime() + refreshProjection() before reading
# pixel data for the next frame.
LOAD_INTERVAL_MS = 150


class ThumbnailWorker(QObject):
    """
    Sequential, timer-driven thumbnail loader.

    Uses a single-shot timer (not a repeating one) to avoid recursive
    re-entry: QApplication.processEvents() inside get_frame_thumbnail()
    cannot fire the next tick while the current tick is still executing.

    Queue entries are (doc_name, layer_id, frame_number, source_id) tuples.
    layer_id doubles as the UUID used to locate the node in the document tree
    and as the ThumbnailCache bucket key.
    """

    # Emits (doc_name, layer_id, frame_number, QPixmap) when a thumbnail is ready.
    thumbnail_ready = pyqtSignal(str, str, int, object)

    def __init__(self, frame_manager, thumbnail_cache, parent=None):
        super().__init__(parent)

        self._frame_manager = frame_manager
        self._cache = thumbnail_cache

        # Queue of (doc_name, layer_id, frame_number, source_id) tuples
        self._queue: list = []

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_next)

    # ── Public API ────────────────────────────────────────────────────────────

    def request_thumbnails(self, entries: list):
        """Replace the current queue with a new batch.

        Frames already present in the cache are skipped — the caller is
        responsible for rendering those from cache before calling this.

        Args:
            entries: List of (doc_name, layer_id, frame_number, source_id).
                     Each entry carries its own document + layer context so
                     thumbnails can be generated for multiple layers in one
                     Refresh pass.
        """
        self.cancel()

        # Only queue entries whose source_id is not yet cached
        self._queue = [
            (dn, lid, fn, sid)
            for dn, lid, fn, sid in entries
            if not self._cache.has(dn, lid, sid)
        ]

        if self._queue:
            self._timer.start(LOAD_INTERVAL_MS)

    def cancel(self):
        """Stop any in-progress loading and clear the queue."""
        self._timer.stop()
        self._queue.clear()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process_next(self):
        """Load one thumbnail, store it in cache, emit signal, reschedule."""
        if not self._queue:
            return

        doc_name, layer_id, frame_number, source_id = self._queue.pop(0)

        # Double-check cache (DrawingMonitor might have refreshed it already)
        pixmap = self._cache.get(doc_name, layer_id, source_id)

        if pixmap is None:
            # Resolve the node by UUID so we can generate thumbnails for any
            # layer, not just the one currently active in the UI.
            node = self._frame_manager.get_node_by_uuid(layer_id)
            pixmap = self._frame_manager.get_frame_thumbnail(
                frame_number, node=node
            )
            if pixmap is not None:
                self._cache.put(doc_name, layer_id, source_id, pixmap)

        if pixmap is not None:
            self.thumbnail_ready.emit(doc_name, layer_id, frame_number, pixmap)

        # Reschedule only after this callback fully returns so that
        # processEvents() inside get_frame_thumbnail() cannot cause
        # recursive re-entry.
        if self._queue:
            self._timer.start(LOAD_INTERVAL_MS)