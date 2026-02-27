"""
Frame Selector Docker - Main UI Panel.

Grid of automatically detected unique frames.
Click a card to clone that frame to the current timeline position.
"""

from krita import DockWidget

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel,
    QPushButton, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QSize

from .frame_manager import FrameManager
from .frame_store import FrameStore
from .frame_thumbnail_delegate import FrameCardDelegate, CARD_SIZE
import os
import zipfile


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

        # Debounce for canvas changes
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.timeout.connect(self._on_context_changed)

        self._build_ui()

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
        self._reload_grid()

    # ─── Grid ─────────────────────────────────────────────────────

    def _reload_grid(self):
        """Reload the grid from the persistent store."""
        self._frame_grid.clear()

        if not self._has_valid_context():
            return

        frames = self._frame_store.get_frames(
            self._current_doc_name, self._current_layer_id
        )

        if not frames:
            self._set_status(
                "No frames loaded · Click 'Refresh' to scan")
            return

        for frame_number in frames:
            item = QListWidgetItem()
            item.setText(f"F {frame_number}")
            item.setToolTip(
                f"Frame {frame_number}\n"
                f"Click to clone to current position"
            )
            item.setData(Qt.UserRole, frame_number)
            item.setSizeHint(QSize(CARD_SIZE, CARD_SIZE))

            thumbnail = self._frame_manager.get_frame_thumbnail(frame_number)
            if thumbnail:
                item.setData(Qt.DecorationRole, thumbnail)

            self._frame_grid.addItem(item)

        current_time = self._frame_manager.get_current_time()
        self._set_status(
            f"{len(frames)} unique frames · Click to clone"
        )

    # ─── Actions ──────────────────────────────────────────────────

    def _on_refresh_frames(self):
        """Scan document structure and populate frames automatically."""
        if not self._has_valid_context():
            return

        self._set_status("Scanning document... (Saving)", "#8888cc")
        # Force UI update
        QApplication.processEvents()

        # 1. Scan document (this saves the file!)
        layer_data = self._frame_manager.scan_active_document(force_save=True)

        # 2. Filter for current layer
        current_layer_uuid = self._current_layer_id

        # Strip {} from uuid if present in API but not in XML (unlikely now)
        if current_layer_uuid and current_layer_uuid.startswith('{'):
            pass

        if not layer_data or current_layer_uuid not in layer_data:
            # DEBUG: Popup info if scan fails
            try:
                doc_path = self._frame_manager.active_document.fileName()
                exists = os.path.exists(doc_path)
                
                debug_info = f"File: {doc_path}\nExists: {exists}\n"
                debug_info += f"API Layer UUID: {current_layer_uuid}\n\n"
                
                if exists:
                    try:
                        with zipfile.ZipFile(doc_path, 'r') as z:
                            # Contar archivos
                            files = z.namelist()
                            debug_info += f"Zip Files: {len(files)}\n"
                            
                            # Buscar maindoc.xml
                            if "maindoc.xml" in files:
                                debug_info += "Maindoc: Found\n"
                            else:
                                debug_info += "Maindoc: MISSING!\n"
                            
                            # Buscar keyframes
                            kfs = [f for f in files if f.endswith(".keyframes.xml")]
                            debug_info += f"Keyframe files: {len(kfs)}\n"
                            
                            # Mostrar UUIDs encontrados si pudimos parsear
                            found_uuids = list(layer_data.keys())
                            debug_info += f"Found UUIDs: {found_uuids}"
                            
                    except Exception as e:
                        debug_info += f"Zip Error: {e}\n"
                
                QMessageBox.warning(self, "Debug Info", debug_info)
                
            except Exception as e:
                QMessageBox.critical(self, "Error Fatal", str(e))
                
            self._set_status("Scan failed (Check Popup)", "#e85555")
            return

        unique_frames_groups = layer_data[current_layer_uuid]['clones']

        if not unique_frames_groups:
            self._set_status("No content frames found (all empty?)", "#e8a838")
            return

        # 3. Update Store
        # Clear old frames
        self._frame_store.clear_frames(
            self._current_doc_name, self._current_layer_id
        )

        count = 0
        layer_name = self._current_layer_name or "unnamed"

        for group in unique_frames_groups:
            # group = {'source_id': '...', 'times': [0, 5], 'representative_frame': 0}
            frame_num = group['representative_frame']

            self._frame_store.add_frame(
                self._current_doc_name,
                self._current_layer_id,
                layer_name,
                frame_number=frame_num
            )
            count += 1

        self._reload_grid()
        self._set_status(f"Found {count} unique frames", "#6fbf73")

    def _on_clear_frames(self):
        """Clear all registered frames for the current layer."""
        if not self._has_valid_context():
            return

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
