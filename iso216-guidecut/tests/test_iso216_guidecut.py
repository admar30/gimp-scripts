from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import pytest
from PIL import Image

MODULE_ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = MODULE_ROOT / "cli"
CLI_PATH = str(CLI_DIR)
if CLI_PATH not in sys.path:
    sys.path.insert(0, CLI_PATH)

import iso216_guidecut as guidecut_module
from iso216_guidecut import (
    build_output_path,
    clamp_expand_bias_percent,
    compute_expand_crop_rect,
    compute_grid,
    compute_guides,
    compute_tile_crop,
    detect_orientation,
    is_near_iso216_ratio,
    main,
    parse_expand_bias_percent,
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


def test_is_near_iso216_ratio_true_for_a4_shape() -> None:
    assert is_near_iso216_ratio(2480, 3508)


def test_is_near_iso216_ratio_false_for_wide_shape() -> None:
    assert not is_near_iso216_ratio(1920, 1080)


def test_parse_expand_bias_percent_accepts_range() -> None:
    assert parse_expand_bias_percent("0") == 0.0
    assert parse_expand_bias_percent(50) == 50.0
    assert parse_expand_bias_percent(100.0) == 100.0


def test_parse_expand_bias_percent_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_expand_bias_percent("x")
    with pytest.raises(ValueError):
        parse_expand_bias_percent(-1)
    with pytest.raises(ValueError):
        parse_expand_bias_percent(101)


def test_clamp_expand_bias_percent_clamps_bounds() -> None:
    assert clamp_expand_bias_percent(-20) == 0.0
    assert clamp_expand_bias_percent(120) == 100.0
    assert clamp_expand_bias_percent("bad", default=42.0) == 42.0


def test_compute_expand_crop_rect_for_too_wide_source() -> None:
    crop = compute_expand_crop_rect(1000, 500, 0)
    assert crop.axis == "x"
    assert crop.excess_px > 0
    assert crop.leading_trim_px == 0
    assert crop.trailing_trim_px == crop.excess_px
    assert crop.rect.y0 == 0 and crop.rect.y1 == 500


def test_compute_expand_crop_rect_for_too_tall_source() -> None:
    crop = compute_expand_crop_rect(500, 1000, 100)
    assert crop.axis == "y"
    assert crop.excess_px > 0
    assert crop.leading_trim_px == crop.excess_px
    assert crop.trailing_trim_px == 0
    assert crop.rect.x0 == 0 and crop.rect.x1 == 500


def test_compute_expand_crop_rect_center_bias_splits_trim() -> None:
    crop = compute_expand_crop_rect(1000, 500, 50.0)
    assert crop.excess_px > 0
    assert abs(crop.leading_trim_px - crop.trailing_trim_px) <= 1


def test_compute_expand_crop_rect_noop_for_iso_ratio() -> None:
    crop = compute_expand_crop_rect(2480, 3508, 50)
    assert crop.axis is None
    assert crop.excess_px == 0
    assert crop.rect.box == (0, 0, 2480, 3508)


def test_main_expand_off_keeps_original_geometry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "wide.png"
    output_path = tmp_path / "out.pdf"
    Image.new("RGB", (1200, 500), "white").save(input_path)

    captured: dict[str, object] = {}

    def fake_crop_rect(_w: int, _h: int, _bias: float) -> None:
        raise AssertionError("compute_expand_crop_rect should not be called when expand mode is disabled.")

    def fake_export(
        image,  # noqa: ANN001
        ordered_rects,  # noqa: ANN001
        output_path: Path,  # noqa: ARG001
        preserve_profile: bool = True,  # noqa: FBT001, FBT002
        preserve_metadata: bool = True,  # noqa: FBT001, FBT002
    ) -> list[str]:
        captured["size"] = image.size
        captured["rects"] = list(ordered_rects)
        captured["preserve_profile"] = preserve_profile
        captured["preserve_metadata"] = preserve_metadata
        return []

    monkeypatch.setattr(guidecut_module, "compute_expand_crop_rect", fake_crop_rect)
    monkeypatch.setattr(guidecut_module, "export_tiles_to_multipage_pdf", fake_export)

    exit_code = main([str(input_path), "a3", "--output", str(output_path), "--quiet"])
    assert exit_code == 0
    assert captured["size"] == (1200, 500)
    rects = captured["rects"]
    assert rects[0].box == (0, 0, 600, 500)
    assert rects[1].box == (600, 0, 1200, 500)
    assert captured["preserve_profile"] is True
    assert captured["preserve_metadata"] is True


def test_main_expand_on_uses_cropped_geometry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "wide.png"
    output_path = tmp_path / "out.pdf"
    Image.new("RGB", (1200, 500), "white").save(input_path)

    captured: dict[str, object] = {}

    def fake_export(
        image,  # noqa: ANN001
        ordered_rects,  # noqa: ANN001
        output_path: Path,  # noqa: ARG001
        preserve_profile: bool = True,  # noqa: FBT001, FBT002
        preserve_metadata: bool = True,  # noqa: FBT001, FBT002
    ) -> list[str]:
        captured["size"] = image.size
        captured["rects"] = list(ordered_rects)
        captured["preserve_profile"] = preserve_profile
        captured["preserve_metadata"] = preserve_metadata
        return []

    monkeypatch.setattr(guidecut_module, "export_tiles_to_multipage_pdf", fake_export)

    exit_code = main(
        [
            str(input_path),
            "a3",
            "--output",
            str(output_path),
            "--expand-to-format",
            "--expand-bias-percent",
            "50",
            "--quiet",
        ]
    )
    assert exit_code == 0
    expected_width = int(round(500 * math.sqrt(2.0)))
    assert captured["size"] == (expected_width, 500)
    rects = captured["rects"]
    assert rects[0].y0 == 0
    assert rects[0].y1 == 500
    assert rects[-1].x1 == expected_width
    assert captured["preserve_profile"] is True
    assert captured["preserve_metadata"] is True
