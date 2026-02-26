"""
Frame Store - Persistent storage for registered frames.

Saves registered frame numbers per document+layer to a JSON file
in the Krita config directory. Data survives Krita restarts and
file close/reopen.

Storage structure:
{
    "<document_filename>::<layer_name>": [0, 5, 12, 24],
    "walk_cycle.kra::legs": [0, 6, 12],
    "walk_cycle.kra::arms": [0, 3, 6, 9]
}

Uses document filename (not full path) so the data follows the file
even if the user moves it to a different folder.
"""

import json
import os


def _get_store_path() -> str:
    """
    Returns the path to the JSON persistence file.

    macOS:  ~/Library/Application Support/krita/frame_selector_data.json
    Linux:  ~/.local/share/krita/frame_selector_data.json
    Windows: %APPDATA%/krita/frame_selector_data.json
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif os.uname().sysname == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get(
            "XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share")
        )

    return os.path.join(base, "krita", "frame_selector_data.json")


def _make_key(document_name: str, layer_name: str) -> str:
    """Build the storage key from document and layer names."""
    return f"{document_name}::{layer_name}"


class FrameStore:
    """
    Persistent registry of user-selected frames, indexed by
    document filename and layer name.
    """

    def __init__(self):
        self._store_path = _get_store_path()
        self._data: dict[str, list[int]] = {}
        self._load()

    def _load(self):
        """Load data from disk. If file doesn't exist, start empty."""
        try:
            if os.path.exists(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[FrameSelector] Could not load store: {e}")
            self._data = {}

    def _save(self):
        """Write current data to disk."""
        try:
            os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
            with open(self._store_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            print(f"[FrameSelector] Could not save store: {e}")

    def get_frames(self, document_name: str, layer_name: str) -> list[int]:
        """Get the list of registered frame numbers for a document+layer."""
        key = _make_key(document_name, layer_name)
        return sorted(self._data.get(key, []))

    def add_frame(self, document_name: str, layer_name: str, frame_number: int) -> bool:
        """
        Register a frame. Returns True if it was added,
        False if it was already registered.
        """
        key = _make_key(document_name, layer_name)

        if key not in self._data:
            self._data[key] = []

        if frame_number in self._data[key]:
            return False

        self._data[key].append(frame_number)
        self._data[key].sort()
        self._save()
        return True

    def remove_frame(self, document_name: str, layer_name: str, frame_number: int) -> bool:
        """Remove a single frame from the registry. Returns True if found and removed."""
        key = _make_key(document_name, layer_name)

        if key not in self._data or frame_number not in self._data[key]:
            return False

        self._data[key].remove(frame_number)

        # Clean up empty entries
        if not self._data[key]:
            del self._data[key]

        self._save()
        return True

    def clear_frames(self, document_name: str, layer_name: str):
        """Clear all registered frames for a document+layer."""
        key = _make_key(document_name, layer_name)

        if key in self._data:
            del self._data[key]
            self._save()

    def has_frame(self, document_name: str, layer_name: str, frame_number: int) -> bool:
        """Check if a frame is already registered."""
        key = _make_key(document_name, layer_name)
        return frame_number in self._data.get(key, [])
