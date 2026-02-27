"""
Thumbnail Worker — Producer-Consumer Pattern.

Owns the async thumbnail generation queue.  The docker enqueues a batch
of frame numbers; the worker drains the queue one frame at a time using a
single-shot QTimer so Krita's projection has time to update between each
capture (repeated-timer or direct-loop approaches cause stale reads).

Signal flow:
    Docker.request_thumbnails(frames)
        → Worker queues frames not already in cache
        → Timer fires every LOAD_INTERVAL_MS
            → Worker calls FrameManager.get_frame_thumbnail()
            → Worker stores result in ThumbnailCache
            → Worker emits thumbnail_ready(frame_number, pixmap)
        → Docker._on_thumbnail_ready sets DecorationRole on the grid item
"""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

# Gap between consecutive thumbnail captures (ms).
# Gives Krita's rendering engine time to flush the projection update
# triggered by setCurrentTime() + refreshProjection() before we read
# pixel data for the next frame.
LOAD_INTERVAL_MS = 80


class ThumbnailWorker(QObject):
    """
    Sequential, timer-driven thumbnail loader.

    Uses a single-shot timer (not a repeating one) to avoid recursive
    re-entry: QApplication.processEvents() inside get_frame_thumbnail()
    cannot fire the next tick while the current tick is still executing.

    ┌──────────────┐  request_thumbnails()  ┌──────────────┐
    │    Docker    │ ─────────────────────→ │    Worker    │
    │              │                        │  (queue)     │
    │              │ ←──────────────────── │              │
    │              │   thumbnail_ready()    │  ↓ timer     │
    └──────────────┘                        │  FrameManager│
                                            └──────────────┘
    """

    # Emits (frame_number, QPixmap) when a thumbnail is ready.
    # Uses `object` instead of `QPixmap` because pyqtSignal does not
    # accept QPixmap as a type argument in all PyQt5 builds.
    thumbnail_ready = pyqtSignal(int, object)

    def __init__(self, frame_manager, thumbnail_cache, parent=None):
        """
        Args:
            frame_manager:   FrameManager instance for pixel capture.
            thumbnail_cache: ThumbnailCache instance for read/write.
            parent:          Optional QObject parent (docker widget).
        """
        super().__init__(parent)

        self._frame_manager = frame_manager
        self._cache = thumbnail_cache

        self._queue: list[int] = []
        self._doc_name: str | None = None
        self._layer_id: str | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_next)

    # ── Public API ────────────────────────────────────────────────

    def request_thumbnails(
        self,
        doc_name: str,
        layer_id: str,
        frame_numbers: list[int],
    ):
        """Replace the current queue with a new batch of frames.

        Frames already present in the cache are skipped immediately —
        the caller is responsible for rendering them from cache before
        calling this method.

        Args:
            doc_name:      Document filename (e.g. 'walk_cycle.kra').
            layer_id:      Layer UUID string.
            frame_numbers: Ordered list of frame numbers to load.
        """
        self.cancel()

        self._doc_name = doc_name
        self._layer_id = layer_id

        # Only queue frames that are not already cached
        self._queue = [
            f for f in frame_numbers
            if not self._cache.has(doc_name, layer_id, f)
        ]

        if self._queue:
            self._timer.start(LOAD_INTERVAL_MS)

    def cancel(self):
        """Stop any in-progress loading and clear the queue."""
        self._timer.stop()
        self._queue.clear()

    # ── Internal ──────────────────────────────────────────────────

    def _process_next(self):
        """Load one thumbnail, store it, emit the signal, reschedule."""
        if not self._queue:
            return

        frame_number = self._queue.pop(0)

        # Guard: context may have changed while the timer was pending
        if not self._doc_name or not self._layer_id:
            self._queue.clear()
            return

        # Double-check cache (another code path may have populated it)
        pixmap = self._cache.get(self._doc_name, self._layer_id, frame_number)

        if pixmap is None:
            pixmap = self._frame_manager.get_frame_thumbnail(frame_number)
            if pixmap is not None:
                self._cache.put(
                    self._doc_name, self._layer_id, frame_number, pixmap
                )

        if pixmap is not None:
            self.thumbnail_ready.emit(frame_number, pixmap)

        # Schedule the next frame only after this callback fully returns,
        # so processEvents() inside get_frame_thumbnail() cannot cause
        # recursive re-entry here.
        if self._queue:
            self._timer.start(LOAD_INTERVAL_MS)