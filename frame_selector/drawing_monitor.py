"""
Drawing Monitor — detects when the user has finished drawing.

Because Krita's Python API does not expose per-stroke events, this module
uses a lightweight polling strategy:

  1. Poll every POLL_MS (1 000 ms) — take a 16×16 composite snapshot of
     the document using doc.thumbnail().  At 256 pixels this is cheap.

  2. Hash the raw pixel bytes with MD5 and compare with the previous hash.
     If the hash changed, the user has drawn something on the current frame.

  3. Reset a single-shot debounce timer (IDLE_MS = 2 000 ms) on every
     detected change.  When the debounce fires the user has been idle for
     at least IDLE_MS — emit refresh_needed(frame_number).

  4. The docker responds by invalidating that frame's disk/memory cache
     entry and re-queuing a single thumbnail regeneration.

During the drawing process (between changes) the debounce keeps getting
reset, so no thumbnail capture happens while the user is actively drawing.
"""

import hashlib

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


POLL_MS = 1_000   # how often to sample the document composite
IDLE_MS = 10_000   # how long to wait after the last detected change


class DrawingMonitor(QObject):
    """
    Polls the active document for content changes and emits
    refresh_needed(frame_number) after the user stops drawing.

    Usage:
        monitor.activate()   — start watching the active document
        monitor.deactivate() — stop (e.g. on document/layer switch)
    """

    # Emitted when content change detected AND user has been idle ≥ IDLE_MS.
    # frame_number is the timeline position that was current at the time of
    # the last detected change.
    refresh_needed = pyqtSignal(int)

    def __init__(self, frame_manager, parent=None):
        super().__init__(parent)

        self._frame_manager = frame_manager

        self._last_hash: "bytes | None" = None
        self._pending_frame: "int | None" = None

        # Poll: samples the document composite regularly
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_MS)
        self._poll_timer.timeout.connect(self._on_poll)

        # Debounce: fires only after IDLE_MS of no detected changes
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(IDLE_MS)
        self._debounce.timeout.connect(self._on_idle)

    # ── Public API ────────────────────────────────────────────────────────────

    def activate(self):
        """Start monitoring the active document."""
        self._last_hash = None
        self._pending_frame = None
        self._poll_timer.start()

    def deactivate(self):
        """Stop monitoring (call on layer/document switch or docker close)."""
        self._poll_timer.stop()
        self._debounce.stop()
        self._last_hash = None
        self._pending_frame = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_poll(self):
        """Sample the document and detect content changes."""
        doc = self._frame_manager.active_document
        if not doc:
            return

        # doc.thumbnail(w, h) returns a QImage of the current composite at
        # the current time.  16×16 = 256 px — negligible cost.
        img = doc.thumbnail(16, 16)
        if not img or img.isNull():
            return

        current_hash = self._hash_image(img)
        if current_hash is None:
            return

        if self._last_hash is not None and current_hash != self._last_hash:
            # Content changed since last poll — record frame and reset debounce.
            # Resetting means the debounce only fires after IDLE_MS of *no*
            # further changes, i.e. after the user stops drawing.
            self._pending_frame = doc.currentTime()
            self._debounce.start()   # start() on a running single-shot resets it

        self._last_hash = current_hash

    def _on_idle(self):
        """Debounce fired — user has been idle; trigger thumbnail refresh."""
        if self._pending_frame is not None:
            self.refresh_needed.emit(self._pending_frame)
            self._pending_frame = None

    @staticmethod
    def _hash_image(img) -> "bytes | None":
        """Return a fast MD5 digest of the raw pixel bytes, or None on error."""
        try:
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            return hashlib.md5(bytes(ptr)).digest()
        except Exception:
            return None
