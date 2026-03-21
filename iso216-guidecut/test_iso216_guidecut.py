from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from iso216_guidecut import (
    build_output_path,
    compute_grid,
    compute_guides,
    compute_tile_crop,
    detect_orientation,
    ordered_tiles,
    parse_target_format,
)


def test_parse_target_format_case_insensitive() -> None:
    assert parse_target_format("A2") == "a2"
    assert parse_target_format("a0") == "a0"


def test_parse_target_format_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_target_format("a5")


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((1000, 1200), "portrait"),
        ((1200, 1000), "landscape"),
        ((1000, 1000), "square"),
    ],
)
def test_detect_orientation(size: tuple[int, int], expected: str) -> None:
    assert detect_orientation(*size) == expected


@pytest.mark.parametrize(
    ("target", "orientation", "expected"),
    [
        ("a3", "portrait", (1, 2)),
        ("a3", "landscape", (2, 1)),
        ("a2", "portrait", (2, 2)),
        ("a1", "portrait", (2, 4)),
        ("a1", "landscape", (4, 2)),
        ("a0", "portrait", (4, 4)),
        ("a0", "landscape", (4, 4)),
    ],
)
def test_compute_grid(target: str, orientation: str, expected: tuple[int, int]) -> None:
    assert compute_grid(target, orientation) == expected


def test_compute_guides() -> None:
    v, h = compute_guides(width_px=2480, height_px=3508, cols=2, rows=4)
    assert v == [1240]
    assert h == [877, 1754, 2631]


def test_compute_tile_crop_covers_full_canvas_no_gaps() -> None:
    width = 10
    height = 7
    cols = 4
    rows = 2

    # Ensure each edge aligns exactly and final bounds match source size.
    first = compute_tile_crop(0, 0, cols, rows, width, height)
    last = compute_tile_crop(cols - 1, rows - 1, cols, rows, width, height)
    assert first.x0 == 0
    assert first.y0 == 0
    assert last.x1 == width
    assert last.y1 == height


def test_ordered_tiles_row_major() -> None:
    assert ordered_tiles(cols=2, rows=2) == [(0, 0), (1, 0), (0, 1), (1, 1)]


def test_build_output_path_uses_timestamp_and_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = Path("C:/mock/poster.png")
    now = dt.datetime(2026, 3, 21, 12, 34, 56, tzinfo=dt.timezone.utc)

    occupied: set[str] = set()

    def fake_exists(path: Path) -> bool:
        return path.name in occupied

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)

    first = build_output_path(input_path, "a2", now_local=now)
    assert first.name == "poster-guidecut-a2-20260321-123456.pdf"

    occupied.add(first.name)
    second = build_output_path(input_path, "a2", now_local=now)
    assert second.name == "poster-guidecut-a2-20260321-123456-1.pdf"
