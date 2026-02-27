# Frame Selector - Krita Plugin

> **[Leer en Español](README_ES.md)**

A Krita plugin that lets animators **reuse frames** across the timeline with one click. It analyzes your `.kra` file to detect unique frames, displays them as thumbnail cards, and lets you clone any frame to the current timeline position.

**The killer feature?** Cloned frames in Krita share memory \u2014 edit one, and every clone updates automatically.

![Krita 5.x](https://img.shields.io/badge/Krita-5.x-blue)
![Python 3](https://img.shields.io/badge/Python-3-green)
![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-orange)

---

## Why Frame Selector?

If you've ever animated in Krita, you know the pain:

- **Lip sync**: Characters repeat mouth shapes (A, E, O, closed) dozens of times. Without cloning, you'd duplicate pixel data for every single frame.
- **Walk/run cycles**: Reuse the same leg positions across a loop without manually copying frames.
- **Blinking & expressions**: A character blinks every few seconds \u2014 that's the same 2-3 frames over and over.
- **Background holds**: Keep a static background across hundreds of frames without wasting memory.

Frame Selector makes this workflow **fast and visual**. Scan your document, see all unique frames as cards, click to clone.

---

## How It Works

1. **Scan**: The plugin saves your document and reads the `.kra` file (which is a ZIP archive internally). It parses `maindoc.xml` and each layer's `keyframes.xml` to detect which frames are unique and which are clones.

2. **Display**: Unique frames appear as thumbnail cards in the Docker panel. Empty/transparent frames are automatically filtered out.

3. **Clone**: Click any card, and the plugin clones that frame to the **current timeline position** on the **active layer**. The clone shares pixel data with the original \u2014 zero extra memory cost.

4. **Auto-refresh**: If a frame has moved or been modified, the plugin detects the stale state and re-scans automatically.

---

## Installation

### Method 1: ZIP Import (Recommended)

This is the standard way to install Krita Python plugins.

1. Go to the [Releases](../../releases) page and download `frame_selector.zip`
2. Open Krita
3. Go to **Tools > Scripts > Import Python Plugin from File...**
4. Select the downloaded `frame_selector.zip`
5. Restart Krita
6. Go to **Settings > Configure Krita > Python Plugin Manager**
7. Enable **Frame Selector**
8. Restart Krita once more

The Docker panel will appear under **Settings > Dockers > Frame Selector**.

### Method 2: install.sh (For Developers)

If you cloned the repo and want to install directly:

```bash
git clone https://github.com/your-username/KritaFrameSelector.git
cd KritaFrameSelector
chmod +x install.sh
./install.sh
```

The script auto-detects your OS (macOS, Linux, Windows/MSYS) and copies the plugin files to the correct Krita directory:

| OS      | Default path                                  |
| ------- | --------------------------------------------- |
| macOS   | `~/Library/Application Support/krita/pykrita` |
| Linux   | `~/.local/share/krita/pykrita`                |
| Windows | `%APPDATA%/krita/pykrita`                     |

You can also pass a custom path:

```bash
./install.sh /path/to/your/krita/pykrita
```

After running the script, restart Krita and enable the plugin in **Settings > Configure Krita > Python Plugin Manager**.

---

## Usage

1. Open an animation document in Krita (must have at least one paint layer with keyframes)
2. Open the **Frame Selector** Docker panel (**Settings > Dockers > Frame Selector**)
3. Click the **\u21bb Refresh** button to scan the active document
4. Unique frames appear as thumbnail cards in the panel
5. Navigate to the desired timeline position
6. Click a frame card to **clone it** to the current position on the active layer

### Tips

- **Edit once, update everywhere**: Since clones share pixel data, painting on any clone updates all instances. This is a core Krita feature that Frame Selector leverages.
- **Refresh after changes**: If you add/remove frames manually, hit Refresh to re-scan.
- **Active layer matters**: The clone is always placed on the currently selected layer.

---

## Project Structure

```
KritaFrameSelector/
\u251c\u2500\u2500 frame_selector/                  # Plugin package
\u2502   \u251c\u2500\u2500 __init__.py                  # Krita plugin entry point
\u2502   \u251c\u2500\u2500 frame_manager.py             # Frame scanning & smart cloning logic
\u2502   \u251c\u2500\u2500 frame_selector_docker.py     # Docker panel UI (Qt)
\u2502   \u251c\u2500\u2500 frame_store.py               # Persistent JSON storage for registered frames
\u2502   \u251c\u2500\u2500 frame_thumbnail_delegate.py  # Custom card rendering for frame thumbnails
\u2502   \u251c\u2500\u2500 krita_parser.py              # .kra file forensic analyzer (ZIP/XML parsing)
\u2502   \u2514\u2500\u2500 manual.html                  # Plugin manual
\u251c\u2500\u2500 frame_selector.desktop           # Krita plugin descriptor
\u251c\u2500\u2500 install.sh                       # Developer installation script
\u251c\u2500\u2500 README.md                        # This file
\u2514\u2500\u2500 README_ES.md                     # Spanish version
```

---

## Technical Details

### How .kra Clone Detection Works

A `.kra` file is a ZIP archive. Inside it:

- **`maindoc.xml`** describes the layer tree structure
- **`<layerN>.keyframes.xml`** files describe keyframe timing per layer

In a `keyframes.xml` file, each `<keyframe>` element has a `time` (timeline position) and a `frame` attribute (pixel data reference). When two keyframes point to the **same `frame` value**, they are clones \u2014 sharing identical pixel data in memory.

```xml
<!-- These two keyframes are clones (both reference "layer5") -->
<keyframe time="0" frame="layer5" />
<keyframe time="24" frame="layer5" />

<!-- This one is unique (references different data) -->
<keyframe time="12" frame="layer5.f12" />
```

The plugin reads these files to build a map of unique vs. cloned frames, filters out empty frames (file size < 100 bytes in the ZIP), and presents only meaningful frames to the user.

---

## Requirements

- **Krita 5.x** or later
- **Python 3** (bundled with Krita)

No external dependencies required.

---

## License

This project is licensed under the GPL-3.0 License - the same license as Krita itself.

---

## Contributing

Contributions are welcome! Feel free to open issues or pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request
