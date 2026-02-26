"""
Frame Manager - Core logic for frame operations.

Handles generating thumbnails and cloning frames using Krita's
native clone actions (copy_frames_as_clones + paste_frames).

Frame registration/persistence is handled by FrameStore.
"""

from krita import Krita, Document, Node
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QSize


THUMBNAIL_SIZE = QSize(128, 128)


class FrameManager:
    """
    Krita API bridge for frame operations.

    Responsibilities:
    - Generate thumbnails for specific frames
    - Clone frames using Krita's native clone system
    - Provide access to document/node state
    """

    def __init__(self):
        self._app = Krita.instance()

    @property
    def active_document(self) -> Document | None:
        return self._app.activeDocument()

    @property
    def active_node(self) -> Node | None:
        doc = self.active_document
        if doc:
            return doc.activeNode()
        return None

    def get_document_name(self) -> str | None:
        """Get the current document filename (e.g. 'walk_cycle.kra')."""
        doc = self.active_document
        if not doc:
            return None
        name = doc.fileName()
        if name:
            # Extract just the filename from full path
            import os
            return os.path.basename(name)
        # Unsaved document: use the document name
        return doc.name() or "untitled"

    def get_layer_name(self) -> str | None:
        """Get the active layer name."""
        node = self.active_node
        return node.name() if node else None

    def _trigger_action(self, action_name: str) -> bool:
        """Trigger a Krita action by name."""
        action = self._app.action(action_name)
        if action:
            action.trigger()
            return True
        print(f"[FrameSelector] Action '{action_name}' not found")
        return False

    def get_frame_thumbnail(self, frame_number: int, size: QSize = None) -> QPixmap | None:
        """
        Generate a thumbnail for a specific frame.

        Temporarily navigates to the frame, captures pixel data,
        and restores the original position.
        """
        doc = self.active_document
        node = self.active_node
        if not doc or not node:
            return None

        target_size = size or THUMBNAIL_SIZE
        original_time = doc.currentTime()

        try:
            doc.setCurrentTime(frame_number)

            bounds = node.bounds()
            if bounds.isEmpty():
                return None

            pixel_data = node.projectionPixelData(
                bounds.x(), bounds.y(),
                bounds.width(), bounds.height()
            )

            if not pixel_data or len(pixel_data) == 0:
                return None

            image = QImage(
                pixel_data,
                bounds.width(),
                bounds.height(),
                QImage.Format_ARGB32
            )

            scaled = image.scaled(
                target_size,
                aspectRatioMode=1,  # Qt.KeepAspectRatio
                transformMode=1     # Qt.SmoothTransformation
            )

            return QPixmap.fromImage(scaled)

        finally:
            doc.setCurrentTime(original_time)

    def clone_frame_to_position(self, source_frame: int, target_frame: int) -> bool:
        """
        Clone a frame using Krita's native clone system.

        1. Navigate to source → copy_frames_as_clones
        2. Navigate to target → paste_frames
        3. Restore original position

        Creates a real clone frame (shared memory reference).
        """
        doc = self.active_document
        if not doc:
            return False

        original_time = doc.currentTime()

        try:
            doc.setCurrentTime(source_frame)
            if not self._trigger_action("copy_frames_as_clones"):
                return False

            doc.setCurrentTime(target_frame)
            if not self._trigger_action("paste_frames"):
                return False

            doc.refreshProjection()
            return True

        except Exception as e:
            print(f"[FrameSelector] Error cloning frame: {e}")
            return False

        finally:
            doc.setCurrentTime(original_time)

    def get_current_time(self) -> int:
        """Get the current timeline position."""
        doc = self.active_document
        return doc.currentTime() if doc else 0

    def get_animation_length(self) -> int:
        """Get total animation length in frames."""
        doc = self.active_document
        return doc.animationLength() if doc else 0
