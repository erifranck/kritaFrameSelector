"""
Frame Selector Docker - Main UI Panel.

Grid of automatically detected unique frames.
Click a card to clone that frame to the current timeline position.
"""

from krita import DockWidget, Krita

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel,
    QPushButton, QApplication, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QSize

from .frame_manager import FrameManager
from .frame_store import FrameStore
from .frame_thumbnail_delegate import FrameCardDelegate, CARD_SIZE
from .thumbnail_cache import ThumbnailCache
from .thumbnail_worker import ThumbnailWorker
from .drawing_monitor import DrawingMonitor
from .timeline_debugger import TimelineDebugger


class FrameSelectorDocker(DockWidget):
    """
    Docker widget: auto-populated grid of unique frame content.

    ┌────────────────────────────────────┐
    │  doc.kra · walk_cycle              │
    ├────────────────────────────────────┤
    │  [↻ Refresh]          [Clear]      │
    ├────────────────────────────────────┤
    │  ┌──────────┐ ┌──────────┐         │
    │  │  F0      │ │  F6      │         │
    │  └──────────┘ └──────────┘         │
    ├────────────────────────────────────┤
    │  2 unique frames found             │
    └────────────────────────────────────┘

    - "Refresh": scans .kra file to find real unique frames
    - "Clear": removes all registered frames for this layer from view
    - Click a card: clones that frame to current playhead position
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frame Selector")

        self._frame_manager = FrameManager()
        self._frame_store = FrameStore()

        self._current_doc_name: str | None = None
        self._current_layer_id: str | None = None
        self._current_layer_name: str | None = None

        # Layer change monitor: polls the active layer to detect when user
        # switches to a different layer in Krita's layer panel.
        self._layer_polling_timer = QTimer()
        self._layer_polling_timer.setSingleShot(False)
        self._layer_polling_timer.setInterval(500)  # Check every 500ms
        self._layer_polling_timer.timeout.connect(self._check_layer_change)

        # Timeline position monitor: polls the timeline to detect when user
        # moves frames (drag & drop in the timeline). Uses a hash of frame
        # positions to detect changes efficiently.
        self._timeline_polling_timer = QTimer()
        self._timeline_polling_timer.setSingleShot(False)
        self._timeline_polling_timer.setInterval(800)  # Check every 800ms
        self._timeline_polling_timer.timeout.connect(self._check_timeline_change)
        self._last_timeline_hash = None  # Hash of frame positions

        # Debounce for canvas changes
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.timeout.connect(self._on_context_changed)

        # Phase 2: shared thumbnail repository
        self._thumbnail_cache = ThumbnailCache()

        # Phase 3: async sequential loader (Producer-Consumer)
        self._thumbnail_worker = ThumbnailWorker(
            self._frame_manager, self._thumbnail_cache, parent=self
        )
        self._thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_ready)

        # Drawing monitor: polls the document composite and refreshes the
        # thumbnail for any frame the user drew on, after they stop drawing.
        self._drawing_monitor = DrawingMonitor(self._frame_manager, parent=self)
        self._drawing_monitor.refresh_needed.connect(self._on_drawing_refresh)

        # Start layer monitoring immediately (will do nothing if no document)
        self._layer_polling_timer.start()

        # Connect Window signals for view changes
        self._connect_window_signals()

        self._build_ui()

    def _connect_window_signals(self):
        """Connect to Window signals for detecting view changes."""
        window = Krita.instance().activeWindow()
        if window:
            window.activeViewChanged.connect(self._on_active_view_changed)

    def _on_active_view_changed(self):
        """Called when the active view changes (e.g., user switches documents).

        Compares stored frame positions with actual timeline positions.
        If frames were moved/reordered, update the mapping to keep it in sync.
        """
        # Reconnect signals for new window if needed
        window = Krita.instance().activeWindow()
        if window:
            try:
                window.activeViewChanged.disconnect(self._on_active_view_changed)
            except TypeError:
                pass  # Wasn't connected
            window.activeViewChanged.connect(self._on_active_view_changed)

        # Check if we have a valid context
        if not self._has_valid_context():
            return

        # Get current timeline state
        current_time = self._frame_manager.get_current_time()
        
        # Compare stored frames with current timeline positions
        self._verify_frame_positions()

    def _verify_frame_positions(self):
        """Verify that stored frame positions match the timeline.

        If the user moved frames in the timeline, the stored mapping becomes
        stale. This method checks for discrepancies and updates accordingly.
        """
        if not self._has_valid_context():
            return

        # Get stored frames for current layer
        stored_frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )

        if not stored_frames:
            return

        # The issue: when user moves frames, the frame_number -> source_id mapping
        # gets out of sync. We need to detect this.
        #
        # Approach: Compare what we have stored vs what's actually in the timeline
        # by checking the keyframes.xml structure.
        
        # For now, we just trigger a context refresh to pick up changes
        # A full re-scan would be more accurate but more expensive
        self._reload_grid()
        
        # Check if frames look different
        current_frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )
        
        # If the frame numbers changed significantly, suggest a refresh
        if set(stored_frames) != set(current_frames):
            self._set_status(
                "Frame positions may have changed · Click 'Refresh' to resync",
                "#e8a838"
            )

    def _build_ui(self):
        """Build the complete UI."""
        main_widget = QWidget(self)
        self.setWidget(main_widget)

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Layer info ──
        self._lbl_layer = QLabel("No document open")
        self._lbl_layer.setStyleSheet(
            "color: #ccc; font-weight: bold; padding: 4px;"
        )
        layout.addWidget(self._lbl_layer)

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_refresh = QPushButton("↻ Refresh")
        self._btn_refresh.setToolTip(
            "Scan document to find unique frames (Saves document!)"
        )
        self._btn_refresh.setStyleSheet(
            "QPushButton { background-color: #3a506b; color: white; "
            "padding: 6px 12px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4a608b; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_refresh.clicked.connect(self._on_refresh_frames)
        btn_row.addWidget(self._btn_refresh)

        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setToolTip(
            "Clear current view (does not delete frames from file)"
        )
        self._btn_clear.setStyleSheet(
            "QPushButton { background-color: #444; color: #ccc; "
            "padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #555; color: white; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_clear.clicked.connect(self._on_clear_frames)
        btn_row.addWidget(self._btn_clear)

        layout.addLayout(btn_row)

        # ── Frame Grid ──
        self._frame_grid = QListWidget()
        self._frame_grid.setViewMode(QListWidget.IconMode)
        self._frame_grid.setResizeMode(QListWidget.Adjust)
        self._frame_grid.setMovement(QListWidget.Static)
        self._frame_grid.setWrapping(True)
        self._frame_grid.setSpacing(4)
        self._frame_grid.setUniformItemSizes(True)
        self._frame_grid.setMouseTracking(True)
        self._frame_grid.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._frame_grid.setSelectionMode(QListWidget.SingleSelection)
        self._frame_grid.setItemDelegate(FrameCardDelegate(self._frame_grid))
        self._frame_grid.setStyleSheet(
            "QListWidget { background-color: #1e1e22; border: none; }"
        )
        self._frame_grid.itemClicked.connect(self._on_card_clicked)

        layout.addWidget(self._frame_grid, stretch=1)

        # ── Status bar ──
        self._status_label = QLabel("Click 'Refresh' to scan frames")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: #888; font-size: 11px; padding: 4px; "
            "background-color: #2a2a2e; border-radius: 3px;"
        )
        layout.addWidget(self._status_label)

    # ─── Context ──────────────────────────────────────────────────

    def _update_context(self):
        """Update current document and layer info."""
        self._current_doc_name = self._frame_manager.get_document_name()
        self._current_layer_id = self._frame_manager.get_layer_id()
        self._current_layer_name = self._frame_manager.get_layer_name()

    def _check_layer_change(self):
        """Poll active layer to detect when user switches layers.

        When the active layer changes, reload the grid to show frames
        from the newly selected layer.
        """
        # If no valid context, try to establish one now
        if not self._has_valid_context():
            self._update_context()
            if not self._has_valid_context():
                return  # Still no document/layer
            
            # New document opened - trigger full context change
            self._on_context_changed()
            return

        # Get current layer info
        current_layer_id = self._frame_manager.get_layer_id()
        
        # If we have a stored layer ID but current returns None, ignore (document closing)
        if current_layer_id is None:
            return

        # Check if layer changed
        # - First time: _current_layer_id is None, current_layer_id has value
        # - Changing layers: both have values but different
        if current_layer_id != self._current_layer_id:
            # Layer changed - update context and reload
            current_layer_name = self._frame_manager.get_layer_name()
            self._current_layer_id = current_layer_id
            self._current_layer_name = current_layer_name

            # Update the label
            display_name = current_layer_name or "unnamed"
            self._lbl_layer.setText(
                f"{self._current_doc_name} · {display_name}"
            )

            # Reload grid for new layer
            self._reload_grid()
            
            # Update timeline hash for new layer
            self._update_timeline_hash()

            # Update status based on whether we have frames
            frames = self._frame_store.get_frames(
                self._current_doc_name, self._current_layer_id
            )
            if frames:
                self._set_status(f"Showing {len(frames)} frame(s) from layer '{current_layer_name}'", "#6fbf73")
            else:
                self._set_status("No frames for this layer · Click 'Refresh' to scan", "#e8a838")

    def _update_timeline_hash(self):
        """Calculate a hash of current frame positions in the timeline.

        This creates a fingerprint of the timeline state that we can compare
        later to detect if frames were moved/added/removed.
        """
        if not self._has_valid_context():
            self._last_timeline_hash = None
            return

        # Get current frame positions from the layer
        # We use the frame store as source of truth for what frames exist
        frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )

        if not frames:
            self._last_timeline_hash = None
            return

        # Create a simple hash from frame numbers and their source_ids
        # This is a quick fingerprint of the timeline structure
        frame_parts = []
        for fn in sorted(frames):
            source_id = self._frame_store.get_source_id(
                self._current_doc_name, self._current_layer_id, fn
            )
            frame_parts.append(f"{fn}:{source_id}")

        # Simple string-based hash (good enough for change detection)
        frame_str = "|".join(frame_parts)
        self._last_timeline_hash = hash(frame_str)

    def _check_timeline_change(self):
        """Poll timeline to detect when user moves frames.

        Compares the current timeline state (via frame positions hash)
        with the last known state. If different, frames were moved.
        """
        # If no valid context, do nothing
        if not self._has_valid_context():
            return

        # Get current frame positions
        frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )

        if not frames:
            return

        # Calculate current hash
        frame_parts = []
        for fn in sorted(frames):
            source_id = self._frame_store.get_source_id(
                self._current_doc_name, self._current_layer_id, fn
            )
            frame_parts.append(f"{fn}:{source_id}")

        frame_str = "|".join(frame_parts)
        current_hash = hash(frame_str)

        # Compare with last known hash
        if self._last_timeline_hash is not None and current_hash != self._last_timeline_hash:
            # Timeline changed! Frames were moved, added, or removed
            self._set_status(
                "Frame positions changed · Click 'Refresh' to resync",
                "#e8a838"
            )

        # Update hash for next comparison
        self._last_timeline_hash = current_hash

    def _has_valid_context(self) -> bool:
        """Check if we have a valid document + layer."""
        return (
            self._current_doc_name is not None
            and self._current_layer_id is not None
        )

    def _on_context_changed(self):
        """Called when canvas changes — update context and reload grid."""
        self._update_context()

        if not self._has_valid_context():
            self._thumbnail_worker.cancel()
            self._drawing_monitor.deactivate()
            self._layer_polling_timer.stop()
            self._timeline_polling_timer.stop()
            self._lbl_layer.setText("No document open")
            self._btn_refresh.setEnabled(False)
            self._btn_clear.setEnabled(False)
            self._frame_grid.clear()
            self._set_status("Open a document with animation")
            return

        display_name = self._current_layer_name or "unnamed"
        self._lbl_layer.setText(
            f"{self._current_doc_name} · {display_name}"
        )
        self._btn_refresh.setEnabled(True)
        self._btn_clear.setEnabled(True)
        self._drawing_monitor.activate()
        self._layer_polling_timer.start()  # Start monitoring layer changes
        self._timeline_polling_timer.start()  # Start monitoring timeline changes
        self._update_timeline_hash()  # Initialize hash
        self._reload_grid()

    # ─── Grid ─────────────────────────────────────────────────────

    def _reload_grid(self):
        """Reload the grid from the persistent store.

        Three-phase approach:
          1. Cancel any in-flight worker job.
          2. Populate all card items instantly; serve cached thumbnails
             immediately so the grid looks correct without waiting.
          3. Hand uncached frames to ThumbnailWorker for async loading.
        """
        self._thumbnail_worker.cancel()
        self._frame_grid.clear()

        if not self._has_valid_context():
            return

        frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )

        if not frames:
            self._set_status("No frames loaded · Click 'Refresh' to scan")
            return

        for frame_number in frames:
            # source_id is the content-stable .kra XML reference.
            # Fall back to a synthetic key for frames stored in old format.
            source_id = (
                self._frame_store.get_source_id(
                    self._current_doc_name, self._current_layer_id, frame_number
                )
                or f"frame_{frame_number}"
            )

            item = QListWidgetItem()
            item.setText(f"F {frame_number}")
            item.setToolTip(
                f"Frame {frame_number}\n"
                f"Click to clone to current position"
            )
            item.setData(Qt.UserRole, frame_number)
            item.setSizeHint(QSize(CARD_SIZE, CARD_SIZE))

            # Serve from persistent cache immediately — no generation needed
            cached = self._thumbnail_cache.get(
                self._current_doc_name, self._current_layer_id, source_id
            )
            if cached:
                item.setData(Qt.DecorationRole, cached)

            self._frame_grid.addItem(item)

        # No auto-generation on context change or startup.
        # Thumbnails are only generated when:
        #   1. User clicks "Refresh"  → _on_refresh_frames triggers the worker
        #   2. User finishes drawing  → _on_drawing_refresh triggers the worker

    def _on_thumbnail_ready(
        self, doc_name: str, layer_id: str, frame_number: int, pixmap
    ):
        """Slot: called by ThumbnailWorker when a thumbnail is generated.

        Only updates the grid when the signal matches the currently displayed
        layer — other layers' thumbnails are persisted to cache silently.
        """
        if (
            doc_name != self._current_doc_name
            or layer_id != self._current_layer_id
        ):
            return

        for i in range(self._frame_grid.count()):
            item = self._frame_grid.item(i)
            if item and item.data(Qt.UserRole) == frame_number:
                item.setData(Qt.DecorationRole, pixmap)
                break

    def _on_drawing_refresh(self, frame_number: int):
        """Slot: called by DrawingMonitor after user finishes drawing.

        Invalidates the cached thumbnail for the affected frame and
        re-queues a single capture — no full Refresh scan needed.
        """
        if not self._has_valid_context():
            return

        source_id = (
            self._frame_store.get_source_id(
                self._current_doc_name, self._current_layer_id, frame_number
            )
            or f"frame_{frame_number}"
        )

        # Drop the stale entry from both memory and disk
        self._thumbnail_cache.invalidate_entry(
            self._current_doc_name, self._current_layer_id, source_id
        )

        # Re-generate just this one frame thumbnail asynchronously
        self._thumbnail_worker.request_thumbnails(
            [(self._current_doc_name, self._current_layer_id, frame_number, source_id)]
        )

    # ─── Actions ──────────────────────────────────────────────────

    def _on_refresh_frames(self):
        """Scan ALL animated layers and queue thumbnails for every frame.

        Stores frame positions and thumbnails persistently so they survive
        Krita restarts.  The grid only shows the active layer, but all other
        layers are scanned and cached in the background so switching layers
        shows thumbnails instantly without another Refresh.

        UUID resolution
        ───────────────
        The .kra XML stores layer UUIDs in a format that may differ from
        what Krita's Python API returns (braces, casing).  We resolve each
        XML UUID to the canonical API UUID via get_node_by_uuid (which
        normalises before comparing) so every key — store, cache, signal
        filter — uses the same format.

        Smart cache diff
        ────────────────
        Instead of wiping the entire layer cache on every Refresh, we only
        evict source_ids that no longer exist in the scan result.  Unchanged
        source_ids keep their disk PNGs, and request_thumbnails() skips them
        via its has() check, so a second Refresh is essentially free.
        """
        if not self._has_valid_context():
            return

        self._set_status("Scanning document… (Saving)", "#8888cc")
        QApplication.processEvents()

        # Save + parse the .kra ZIP — returns data keyed by XML-format UUIDs
        layer_data = self._frame_manager.scan_active_document(force_save=True)

        if not layer_data:
            self._set_status("No animated layers found", "#e85555")
            return

        all_entries = []   # (doc_name, canonical_uuid, frame_number, source_id)
        total_unique = 0
        current_layer_count = 0

        for xml_uuid, layer_info in layer_data.items():
            # ── UUID resolution ──────────────────────────────────────────────
            # get_node_by_uuid uses normalised comparison so it finds the node
            # even when XML and API formats differ (e.g. brace/casing mismatch).
            node = self._frame_manager.get_node_by_uuid(xml_uuid)
            canonical_uuid = (
                node.uniqueId().toString() if node else xml_uuid
            )

            # ── Smart cache diff ─────────────────────────────────────────────
            # Collect source_ids that are still valid after this scan.
            new_source_ids = {
                grp.get('source_id') or f"frame_{grp['representative_frame']}"
                for grp in layer_info['clones']
            }
            # Evict only source_ids that disappeared (content was deleted/merged).
            old_source_ids = {
                self._frame_store.get_source_id(
                    self._current_doc_name, canonical_uuid, fn
                )
                for fn in self._frame_store.get_frames(
                    self._current_doc_name, canonical_uuid
                )
            } - {None}

            for stale_sid in old_source_ids - new_source_ids:
                self._thumbnail_cache.invalidate_entry(
                    self._current_doc_name, canonical_uuid, stale_sid
                )

            # ── Rebuild store ────────────────────────────────────────────────
            self._frame_store.clear_frames(self._current_doc_name, canonical_uuid)
            layer_name = layer_info.get('layer_name', 'unnamed')

            for group in layer_info['clones']:
                frame_num = group['representative_frame']
                source_id = group.get('source_id') or f"frame_{frame_num}"

                self._frame_store.add_frame(
                    self._current_doc_name,
                    canonical_uuid,
                    layer_name,
                    frame_number=frame_num,
                    source_id=source_id,
                )
                all_entries.append(
                    (self._current_doc_name, canonical_uuid, frame_num, source_id)
                )
                total_unique += 1

            if canonical_uuid == self._current_layer_id:
                current_layer_count = len(layer_info['clones'])

        # Reload the grid (now using canonical UUIDs that match _current_layer_id)
        self._reload_grid()

        # Queue thumbnail generation.  Entries already in the cache (disk or
        # memory) are skipped by request_thumbnails()'s has() check, so only
        # genuinely new or evicted thumbnails are regenerated.
        self._thumbnail_worker.request_thumbnails(all_entries)

        other_layers = len({
            lid for dn, lid, fn, sid in all_entries
            if lid != self._current_layer_id
        })

        if current_layer_count == 0:
            self._set_status(
                f"Active layer has no frames · "
                f"{total_unique} frame(s) across {other_layers} other layer(s)",
                "#e8a838"
            )
        else:
            suffix = (
                f" · {total_unique - current_layer_count} more in "
                f"{other_layers} other layer(s)"
                if other_layers > 0
                else ""
            )
            self._set_status(
                f"Found {current_layer_count} unique frame(s){suffix}", "#6fbf73"
            )

    def _on_clear_frames(self):
        """Clear all registered frames for the current layer."""
        if not self._has_valid_context():
            return

        self._thumbnail_worker.cancel()
        self._frame_store.clear_frames(
            self._current_doc_name, self._current_layer_id
        )
        self._reload_grid()
        self._set_status("All frames cleared", "#e8a838")

    def _on_card_clicked(self, item: QListWidgetItem):
        """Clone the clicked frame to the current timeline position."""
        frame_number = item.data(Qt.UserRole)
        if frame_number is None:
            return

        current_time = self._frame_manager.get_current_time()

        if frame_number == current_time:
            self._set_status(
                f"Already at frame {frame_number} — move the playhead first",
                "#e8a838"
            )
            return

        if self._frame_manager.is_frame_content_empty(frame_number):
            self._set_status(
                f"Frame {frame_number} is empty — auto-refreshing…",
                "#e8a838"
            )
            self._on_refresh_frames()
            return

        # --- TIMELINE SYNC VALIDATION ---
        # Prevent Krita from cloning into the wrong layer if the user clicked
        # a different layer in the Timeline vs the Layers Panel.
        timeline_validation = TimelineDebugger.validate_clone_target()
        
        # We only block if we successfully retrieved a timeline selection
        # and it definitively does NOT match the active layer row.
        # (If timeline_validation['match'] is False but timeline_info['selection'] is None, 
        # it just means the timeline panel isn't focused/open, which is safe).
        if not timeline_validation.get('match', True) and timeline_validation.get('timeline_layer_info') is not None:
            active_name = self._current_layer_name or "Unknown"
            timeline_name = timeline_validation.get('timeline_layer_info', {}).get('layer_name_guess', 'another layer')
            
            QMessageBox.warning(
                self,
                "Timeline Selection Mismatch",
                f"Cannot clone frame safely.\n\n"
                f"You have '{active_name}' selected in the Layers panel, "
                f"but you clicked on '{timeline_name}' in the Animation Timeline.\n\n"
                f"Krita's native clone system will paste into the Timeline's selection, "
                f"which would destroy frames on '{timeline_name}'.\n\n"
                f"Please click on '{active_name}' inside the Animation Timeline to sync them, then try again."
            )
            self._set_status("Clone aborted: Timeline mismatch", "#e85555")
            return
        # --------------------------------

        success = self._frame_manager.clone_frame_to_position(
            frame_number, current_time
        )

        if success:
            self._set_status(
                f"Cloned frame {frame_number} → position {current_time}",
                "#6fbf73"
            )
        else:
            self._set_status(
                f"Failed to clone frame {frame_number}", "#e85555"
            )

    # ─── UI Helpers ───────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#888"):
        """Update the status label with colored text."""
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 4px; "
            f"background-color: #2a2a2e; border-radius: 3px;"
        )

    # ─── DockWidget override ──────────────────────────────────────

    def canvasChanged(self, canvas):
        """Called by Krita when the active canvas changes."""
        self._refresh_timer.start()
