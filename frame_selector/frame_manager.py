"""
Frame Manager - Core logic for frame operations.

Handles generating thumbnails and cloning frames using Krita's
native clone actions (copy_frames_as_clones + paste_frames).

Frame registration/persistence is handled by FrameStore.
"""

from krita import Krita, Document, Node
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication
from .krita_parser import KritaParser
import os


THUMBNAIL_SIZE = QSize(128, 128)


class FrameManager:
    """
    Krita API bridge for frame operations.

    Responsibilities:
    - Generate thumbnails for specific frames
    - Clone frames using Krita's native clone system
    - Provide access to document/node state
    - Analyze document structure (.kra) to find clones
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
            return os.path.basename(name)
        # Unsaved document: use the document name
        return doc.name() or "untitled"

    def get_layer_name(self) -> str | None:
        """Get the active layer name (for display)."""
        node = self.active_node
        return node.name() if node else None

    def get_layer_id(self) -> str | None:
        """Get the active layer's unique ID (survives renames)."""
        node = self.active_node
        if node:
            return node.uniqueId().toString()
        return None

    def _trigger_action(self, action_name: str) -> bool:
        """Trigger a Krita action by name."""
        action = self._app.action(action_name)
        if action:
            action.trigger()
            return True
        print(f"[FrameSelector] Action '{action_name}' not found")
        return False

    def scan_active_document(self, force_save=True) -> dict:
        """
        Analiza el documento activo en busca de frames clonados.

        Args:
            force_save (bool): Si es True, guarda el documento antes de analizar
                             para asegurar consistencia entre memoria y disco.

        Returns:
            dict: Estructura de clones por capa (ver KritaParser.get_layer_clones)
        """
        doc = self.active_document
        if not doc:
            return {}

        file_path = doc.fileName()
        if not file_path:
            print("[FrameSelector] Documento no guardado. No se puede analizar.")
            return {}

        # Guardamos para asegurar que el ZIP en disco tenga la info actual
        if force_save and doc.modified():
            doc.save()

        # Usamos nuestro parser forense
        parser = KritaParser(file_path)
        return parser.get_layer_clones()

    def get_frame_thumbnail(self, frame_number: int, size: QSize = None) -> QPixmap | None:
        """
        Generate a thumbnail for a specific frame.

        Navigates to the frame, forces a projection refresh so Krita's
        rendering engine catches up before reading pixel data.

        Caching is handled externally by ThumbnailCache / ThumbnailWorker.
        """
        doc = self.active_document
        node = self.active_node
        if not doc or not node:
            return None

        target_size = size or THUMBNAIL_SIZE
        original_time = doc.currentTime()

        try:
            doc.setCurrentTime(frame_number)
            # Force Krita's rendering pipeline to update for the new time
            # before we read pixel data — without this the projection is stale.
            doc.refreshProjection()
            QApplication.processEvents()

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

            if image.isNull():
                return None

            return QPixmap.fromImage(
                image.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        except Exception as e:
            print(f"[FrameSelector] Thumbnail error for frame {frame_number}: {e}")
            return None

        finally:
            doc.setCurrentTime(original_time)

    def is_frame_content_empty(self, frame_number: int) -> bool:
        """Return True if the active layer has no content at frame_number.

        Uses a lightweight bounds check (no pixel data read) to decide
        whether the frame is blank or missing before attempting a clone.
        """
        doc = self.active_document
        node = self.active_node
        if not doc or not node:
            return True

        original_time = doc.currentTime()
        try:
            doc.setCurrentTime(frame_number)
            doc.refreshProjection()
            QApplication.processEvents()
            return node.bounds().isEmpty()
        except Exception:
            return True
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

    def smart_clone_frame(self, candidate_frames: list[int], target_frame: int) -> bool:
        """
        Clona un frame eligiendo inteligentemente la fuente más cercana.

        Args:
            candidate_frames: Lista de tiempos donde existe este contenido.
            target_frame: Dónde queremos pegar el clon.

        Returns:
            bool: True si tuvo éxito.
        """
        if not candidate_frames:
            return False

        # Encontrar el frame candidato más cercano al target
        # Esto minimiza el salto en la línea de tiempo
        best_source = min(candidate_frames,
                          key=lambda x: abs(x - target_frame))

        print(
            f"[FrameSelector] Smart Clone: Usando fuente {best_source} para destino {target_frame}")
        return self.clone_frame_to_position(best_source, target_frame)

    def get_current_time(self) -> int:
        """Get the current timeline position."""
        doc = self.active_document
        return doc.currentTime() if doc else 0

    def get_animation_length(self) -> int:
        """Get total animation length in frames."""
        doc = self.active_document
        return doc.animationLength() if doc else 0
