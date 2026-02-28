# Krita API & Development Documentation

This skill contains the master list of documentation and references for extending, testing, and debugging Krita Python plugins, including core UI and Qt patching.

## Documentation Reference Table

| Resource | Description | Tags | URL |
|----------|-------------|------|-----|
| **Krita Python Classes** | Complete API reference for Krita's exposed Python classes (e.g., `Document`, `Node`, `Krita`) | `krita-api`, `python`, `classes` | [Link](https://apidoc.krita.maou-maou.fr/kapi-class-Document.html) |
| **PyQt5 Reference** | Complete index of PyQt5 documentation for creating UI dockers, signals, slots, and handling events. | `qt`, `pyqt5`, `ui` | [Link](https://www.riverbankcomputing.com/static/Docs/PyQt5/) |
| **Krita Unit Tests & Signals** | Official guide on how to structure unit tests and use signals/slots in Krita plugins. | `testing`, `unit-tests`, `signals` | [Link](https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html#a-note-on-unit-tests) |
| **Patching Qt for Krita** | Advanced guide on how to patch Krita's custom Qt fork (useful if we encounter deep UI bugs). | `qt-patch`, `c++`, `core-dev` | [Link](https://docs.krita.org/en/untranslatable_pages/how_to_patch_qt.html#how-to-patch-qt) |

## Key Concepts for KritaFrameSelector
- Use **Krita Python Classes** to explore methods available for `Document` and `Node` (e.g., timeline and selection states).
- Use **PyQt5 Reference** for any custom Docker or UI manipulation.
- If we hit a wall with native API limitations (like the timeline selection bug), we might need to explore **Unit Tests & Signals** or deeply inspect Qt objects.
