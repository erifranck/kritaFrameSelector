"""
Thumbnail Worker — Producer-Consumer Pattern.

Owns the async thumbnail generation queue.  The docker enqueues a batch
of (frame_number, source_id) entries; the worker drains the queue one entry
at a time using a single-shot QTimer so Krita's projection has time to
update between each capture.

source_id is the internal .kra content reference (e.g. 'layer5.f3').
Using it as the cache key means a thumbnail stays valid even if the user
repositions the frame on the timeline.

Signal flow:
    Docker.request_thumbnails(entries)
        → Worker filters out already-cached entries
        → Timer fires every LOAD_INTERVAL_MS
            → Worker calls FrameManager.get_frame_thumbnail(frame_number)
            → Worker stores result in ThumbnailCache under source_id key
            → Worker emits thumbnail_ready(frame_number, pixmap)
        → Docker._on_thumbnail_ready sets DecorationRole on the grid item
"""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

# Gap between consecutive thumbnail captures (ms).
# Gives Krita's rendering engine time to flush the projection update
# triggered by setCurrentTime() + refreshProjection() before reading
# pixel data for the next frame.
LOAD_INTERVAL_MS = 80


class ThumbnailWorker(QObject):
    """
    Sequential, timer-driven thumbnail loader.

    Uses a single-shot timer (not a repeating one) to avoid recursive
    re-entry: QApplication.processEvents() inside get_frame_thumbnail()
    cannot fire the next tick while the current tick is still executing.

    Queue entries are (frame_number, source_id) tuples.
    source_id is used as the ThumbnailCache key; frame_number is used
    only to navigate Krita's timeline for pixel capture.
    """

    # Emits (frame_number, QPixmap) when a thumbnail is ready.
    thumbnail_ready = pyqtSignal(int, object)

    def __init__(self, frame_manager, thumbnail_cache, parent=None):
        super().__init__(parent)

        self._frame_manager = frame_manager
        self._cache = thumbnail_cache

        # Queue of (frame_number, source_id) pairs waiting to be loaded
        self._queue: list = []
        self._doc_name: "str | None" = None
        self._layer_id: "str | None" = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_next)

    # ── Public API ────────────────────────────────────────────────────────────

    def request_thumbnails(
        self,
        doc_name: str,
        layer_id: str,
        frame_entries: list,   # list[tuple[int, str]]  (frame_number, source_id)
    ):
        """Replace the current queue with a new batch.

        Frames already present in the cache are skipped — the caller is
        responsible for rendering those from cache before calling this.

        Args:
            doc_name:      Document filename (e.g. 'walk_cycle.kra').
            layer_id:      Layer UUID string.
            frame_entries: Ordered list of (frame_number, source_id) pairs.
        """
        self.cancel()

        self._doc_name = doc_name
        self._layer_id = layer_id

        # Only queue entries whose source_id is not yet cached
        self._queue = [
            (f, s) for f, s in frame_entries
            if not self._cache.has(doc_name, layer_id, s)
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

        frame_number, source_id = self._queue.pop(0)

        # Guard: context may have changed while the timer was pending
        if not self._doc_name or not self._layer_id:
            self._queue.clear()
            return

        # Double-check cache (DrawingMonitor might have refreshed it already)
        pixmap = self._cache.get(self._doc_name, self._layer_id, source_id)

        if pixmap is None:
            pixmap = self._frame_manager.get_frame_thumbnail(frame_number)
            if pixmap is not None:
                self._cache.put(
                    self._doc_name, self._layer_id, source_id, pixmap
                )

        if pixmap is not None:
            self.thumbnail_ready.emit(frame_number, pixmap)

        # Reschedule only after this callback fully returns so that
        # processEvents() inside get_frame_thumbnail() cannot cause
        # recursive re-entry.
        if self._queue:
            self._timer.start(LOAD_INTERVAL_MS)