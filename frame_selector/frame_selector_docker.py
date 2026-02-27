"""
Frame Selector Docker - Main UI Panel.

Grid of user-registered frame cards. The user explicitly adds
frames they want available for cloning. Click a card to clone
that frame to the current timeline position. Click [×] to remove.
"""

from krita import DockWidget

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel,
    QPushButton, QApplication, QMessageBox  # <--- Agregamos QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QSize

from .frame_manager import FrameManager
from .frame_store import FrameStore
from .frame_thumbnail_delegate import FrameCardDelegate, CARD_SIZE, REMOVE_ROLE
import os
import zipfile


class FrameSelectorDocker(DockWidget):
    """
    Docker widget: user-managed grid of frame cards.

    ┌────────────────────────────────────┐
    │  doc.kra · walk_cycle              │
    ├────────────────────────────────────┤
    │  [+ Add]  [↻ Refresh]  [Clear]     │
    ├────────────────────────────────────┤
    │  ┌─────[×]┐ ┌─────[×]┐            │
    │  │  F0    │ │  F6    │            │
    │  └────────┘ └────────┘            │
    ├────────────────────────────────────┤
    │  2 frames · Click to clone         │
    └────────────────────────────────────┘

    - "Add Frame": registers the current playhead frame
    - "Refresh": scans .kra file to find real unique frames (auto-populate)
    - "Clear Frames": removes all registered frames for this layer
    - Click a card: clones that frame to current playhead position
    - Click [×]: removes that frame from the registry
    - Data persists per document + layer UUID
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

        self._btn_add = QPushButton("+ Add")
        self._btn_add.setToolTip(
            "Register the current playhead frame for cloning"
        )
        self._btn_add.setStyleSheet(
            "QPushButton { background-color: #3a6b35; color: white; "
            "padding: 6px 12px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4a8b45; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_add.clicked.connect(self._on_add_frame)
        btn_row.addWidget(self._btn_add)

        self._btn_refresh = QPushButton("↻ Refresh")
        self._btn_refresh.setToolTip(
            "Scan document for real unique frames (saves document)"
        )
        self._btn_refresh.setStyleSheet(
            "QPushButton { background-color: #3a506b; color: white; "
            "padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #4a608b; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_refresh.clicked.connect(self._on_refresh_frames)
        btn_row.addWidget(self._btn_refresh)

        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setToolTip(
            "Remove all registered frames for this layer"
        )
        self._btn_clear.setStyleSheet(
            "QPushButton { background-color: #6b3535; color: white; "
            "padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #8b4545; }"
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

        # Listen for data changes (remove button sets REMOVE_ROLE)
        self._frame_grid.model().dataChanged.connect(self._on_data_changed)

        layout.addWidget(self._frame_grid, stretch=1)

        # ── Status bar ──
        self._status_label = QLabel("Add frames to get started")
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
            self._btn_add.setEnabled(False)
            self._btn_refresh.setEnabled(False)
            self._btn_clear.setEnabled(False)
            self._frame_grid.clear()
            self._set_status("Open a document with animation")
            return

        display_name = self._current_layer_name or "unnamed"
        self._lbl_layer.setText(
            f"{self._current_doc_name} · {display_name}"
        )
        self._btn_add.setEnabled(True)
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
                "No frames registered · Click '+ Add' or 'Refresh'")
            return

        for frame_number in frames:
            item = QListWidgetItem()
            item.setText(f"F {frame_number}")
            item.setToolTip(
                f"Frame {frame_number}\n"
                f"Click to clone · [×] to remove"
            )
            item.setData(Qt.UserRole, frame_number)
            item.setSizeHint(QSize(CARD_SIZE, CARD_SIZE))

            thumbnail = self._frame_manager.get_frame_thumbnail(frame_number)
            if thumbnail:
                item.setData(Qt.DecorationRole, thumbnail)

            self._frame_grid.addItem(item)

        current_time = self._frame_manager.get_current_time()
        self._set_status(
            f"{len(frames)} frames · Position: {current_time} · Click to clone"
        )

    # ─── Actions ──────────────────────────────────────────────────

    def _on_add_frame(self):
        """Register the current playhead frame."""
        if not self._has_valid_context():
            return

        current_time = self._frame_manager.get_current_time()
        layer_name = self._current_layer_name or "unnamed"

        added = self._frame_store.add_frame(
            self._current_doc_name,
            self._current_layer_id,
            layer_name,
            current_time
        )

        if added:
            self._reload_grid()
            self._set_status(f"Frame {current_time} registered", "#6fbf73")
        else:
            self._set_status(
                f"Frame {current_time} already registered", "#e8a838"
            )

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

        # Strip {} from uuid if present, Krita sometimes includes them
        if current_layer_uuid and current_layer_uuid.startswith('{'):
            # Standardize UUID format just in case
            pass

        if not layer_data or current_layer_uuid not in layer_data:
            # DEBUG: Si falla, mostramos popup con toda la info
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
                            kfs = [f for f in files if f.endswith(
                                ".keyframes.xml")]
                            debug_info += f"Keyframe files: {len(kfs)}\n"

                            # Mostrar UUIDs encontrados si pudimos parsear
                            found_uuids = list(layer_data.keys())
                            debug_info += f"Found UUIDs: {found_uuids}"

                    except Exception as e:
                        debug_info += f"Zip Error: {e}\n"

                # Mostrar el popup
                QMessageBox.warning(self, "Debug Info", debug_info)

            except Exception as e:
                # Si todo explota, mostrar eso
                QMessageBox.critical(self, "Error Fatal", str(e))

            self._set_status("Scan failed (Check Popup)", "#e85555")
            return

        unique_frames_groups = layer_data[current_layer_uuid]['clones']

        if not unique_frames_groups:
            self._set_status("No content frames found (all empty?)", "#e8a838")
            return

        # 3. Update Store
        # Clear old manual frames
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
        # Check if remove flag was set by the delegate
        if item.data(REMOVE_ROLE):
            # Clear the flag and skip — removal handled by _on_data_changed
            item.setData(REMOVE_ROLE, None)
            return

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

    def _on_data_changed(self, top_left, bottom_right, roles):
        """Handle data changes from the delegate (remove button)."""
        if REMOVE_ROLE not in roles:
            return

        if not self._has_valid_context():
            return

        index = top_left
        frame_number = index.data(Qt.UserRole)

        if frame_number is None:
            return

        removed = self._frame_store.remove_frame(
            self._current_doc_name,
            self._current_layer_id,
            frame_number
        )

        if removed:
            self._reload_grid()
            self._set_status(
                f"Frame {frame_number} removed", "#e8a838"
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
