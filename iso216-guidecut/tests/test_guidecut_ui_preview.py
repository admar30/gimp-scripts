from __future__ import annotations

import queue
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from guidecut_ui import GuidecutApp, PREVIEW_MAX_EDGE_PX


def test_preview_worker_caps_bitmap_and_keeps_oriented_source_size(tmp_path: Path) -> None:
    source_path = tmp_path / "rotated.jpg"
    source = Image.new("RGB", (2000, 1000), "white")
    exif = Image.Exif()
    exif[274] = 6
    source.save(source_path, exif=exif)

    events: queue.Queue = queue.Queue()
    app = SimpleNamespace(_event_queue=events, _resample_filter=GuidecutApp._resample_filter)
    GuidecutApp._preview_load_worker(app, 1, source_path)

    channel, payload = events.get_nowait()
    assert channel == "preview_loaded"
    image = payload["image"]
    try:
        assert payload["size"] == (1000, 2000)
        assert image.size == (800, PREVIEW_MAX_EDGE_PX)
    finally:
        image.close()
