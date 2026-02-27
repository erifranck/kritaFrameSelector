"""
Frame Store - Persistent storage for registered frames.

Saves registered frame numbers per document+layer to a JSON file
in the Krita config directory. Data survives Krita restarts and
file close/reopen.

Storage structure:
{
    "<document_filename>::<layer_uuid>": {
        "layer_name": "legs",
        "frames": [0, 5, 12, 24]
    }
}

Uses document filename (not full path) so the data follows the file
even if the user moves it to a different folder.

Uses layer uniqueId (UUID) instead of name so the data survives
layer renames.
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


def _make_key(document_name: str, layer_id: str) -> str:
    """Build the storage key from document name and layer UUID."""
    return f"{document_name}::{layer_id}"


class FrameStore:
    """
    Persistent registry of user-selected frames, indexed by
    document filename and layer UUID.
    """

    def __init__(self):
        self._store_path = _get_store_path()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load data from disk. If file doesn't exist, start empty."""
        try:
            if os.path.exists(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                # Handle migration from old format (list) to new format (dict)
                self._data = {}
                for key, value in raw.items():
                    if isinstance(value, list):
                        # Old format: just a list of frame numbers
                        self._data[key] = {
                            "layer_name": key.split("::")[-1],
                            "frames": sorted(value)
                        }
                    elif isinstance(value, dict):
                        self._data[key] = value
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

    def _get_entry(self, document_name: str, layer_id: str) -> dict | None:
        """Get the store entry for a document+layer."""
        key = _make_key(document_name, layer_id)
        return self._data.get(key)

    def get_frames(self, document_name: str, layer_id: str) -> list[int]:
        """Get the list of registered frame numbers for a document+layer."""
        entry = self._get_entry(document_name, layer_id)
        if entry:
            return sorted(entry.get("frames", []))
        return []

    def add_frame(
        self, document_name: str, layer_id: str,
        layer_name: str, frame_number: int
    ) -> bool:
        """
        Register a frame. Returns True if it was added,
        False if it was already registered.

        layer_name is stored for display purposes only — the key
        uses layer_id (UUID) which survives renames.
        """
        key = _make_key(document_name, layer_id)

        if key not in self._data:
            self._data[key] = {
                "layer_name": layer_name,
                "frames": []
            }

        # Update the layer name in case it was renamed
        self._data[key]["layer_name"] = layer_name

        if frame_number in self._data[key]["frames"]:
            return False

        self._data[key]["frames"].append(frame_number)
        self._data[key]["frames"].sort()
        self._save()
        return True

    def remove_frame(self, document_name: str, layer_id: str, frame_number: int) -> bool:
        """Remove a single frame from the registry."""
        key = _make_key(document_name, layer_id)
        entry = self._data.get(key)

        if not entry or frame_number not in entry["frames"]:
            return False

        entry["frames"].remove(frame_number)

        # Clean up empty entries
        if not entry["frames"]:
            del self._data[key]

        self._save()
        return True

    def clear_frames(self, document_name: str, layer_id: str):
        """Clear all registered frames for a document+layer."""
        key = _make_key(document_name, layer_id)

        if key in self._data:
            del self._data[key]
            self._save()

    def has_frame(self, document_name: str, layer_id: str, frame_number: int) -> bool:
        """Check if a frame is already registered."""
        entry = self._get_entry(document_name, layer_id)
        if entry:
            return frame_number in entry.get("frames", [])
        return False
