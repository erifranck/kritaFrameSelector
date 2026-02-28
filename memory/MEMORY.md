# KritaFrameSelector — Session Memory

## Project structure
- `frame_selector/frame_selector_docker.py` — main Docker UI (DockWidget)
- `frame_selector/frame_manager.py` — Krita API bridge (thumbnails, cloning, scanning)
- `frame_selector/krita_parser.py` — forensic .kra ZIP parser (no Krita API)
- `frame_selector/thumbnail_worker.py` — async sequential thumbnail queue (QTimer)
- `frame_selector/thumbnail_cache.py` — two-layer cache (memory + disk PNG)
- `frame_selector/frame_store.py` — persistent JSON registry of frame positions
- `frame_selector/frame_thumbnail_delegate.py` — card renderer (shows `?` when pixmap is None)
- `frame_selector/drawing_monitor.py` — polls doc composite hash to detect drawing

## Architecture: thumbnail flow
1. User clicks Refresh → `_on_refresh_frames` scans ALL animated layers via KritaParser
2. Stores frame positions in FrameStore (JSON), queues entries for ThumbnailWorker
3. Worker entry format: `(doc_name, layer_id, frame_number, source_id)` — one queue for all layers
4. Worker resolves node by UUID (`get_node_by_uuid`), calls `get_frame_thumbnail(frame_number, node=node)`
5. Signal: `thumbnail_ready(doc_name, layer_id, frame_number, pixmap)` — docker filters by current layer
6. Cache key: `(doc_name, layer_id, source_id)` — content-stable, survives timeline repositioning

## Key bug fix: `?` thumbnail placeholder
- Root cause: `refreshProjection()` + single `processEvents()` is not enough — Krita's pipeline is async
- Fix: retry loop in `get_frame_thumbnail` — up to 12 `(refreshProjection + processEvents)` cycles until `node.bounds()` is non-empty

## Multi-layer scanning (added)
- Refresh now scans ALL animated layers (not just active), stores & caches all of them
- Switching layers shows cached thumbnails instantly without another Refresh
- `get_node_by_uuid(uuid)` traverses the node tree to find any layer by UUID

## Persistence
- `ThumbnailCache` saves PNGs to `~/Library/Application Support/krita/frame_selector_thumbs/` (macOS)
- `FrameStore` saves JSON to `~/Library/Application Support/krita/frame_selector_data.json` (macOS)
- Both survive Krita restarts

## .kra format key facts (from KRITA_FORMAT_SPECS.md)
- `.kra` is a ZIP; `maindoc.xml` has layer tree; `layer*/keyframes.xml` has frame mappings
- `keyframe time=` is the timeline position; `frame=` is the content ID (many-to-one → clones)
- Empty frames: file_size < 100 bytes in the ZIP → skip
- Namespace: `xmlns="http://www.calligra.org/DTD/krita"` — use `elem.tag.endswith('layer')` not findall