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
    CUSTOM_GRID_MAX,
    CUSTOM_GRID_MIN,
    build_output_path,
    build_custom_grid_token,
    clamp_expand_bias_percent,
    compute_expand_crop_rect,
    compute_grid,
    compute_guides,
    compute_tile_crop,
    detect_orientation,
    is_near_iso216_ratio,
    main,
    ordered_selected_blocks,
    parse_block_index,
    parse_block_coordinate,
    parse_expand_bias_percent,
    parse_transform_scale,
    ordered_tiles,
    parse_target_format,
    render_transformed_source,
    render_transformed_tile,
    Rect,
    resolve_grid_selection,
    selected_block_output_token,
    selected_blocks_output_token,
    TransformCutOptions,
    validate_selected_block,
)


def test_parse_target_format_case_insensitive() -> None:
    assert parse_target_format("A2") == "a2"
    assert parse_target_format("a0") == "a0"


def test_parse_target_format_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_target_format("a5")


def test_build_custom_grid_token() -> None:
    assert build_custom_grid_token(3, 4) == "grid-3x4"


def test_resolve_grid_selection_for_preset_mode() -> None:
    selection = resolve_grid_selection("A2", None, None)
    assert selection.mode == "preset"
    assert selection.target == "a2"
    assert selection.cols is None
    assert selection.rows is None
    assert selection.output_token == "a2"


def test_resolve_grid_selection_for_custom_mode() -> None:
    selection = resolve_grid_selection(None, 3, 4)
    assert selection.mode == "custom"
    assert selection.target is None
    assert selection.cols == 3
    assert selection.rows == 4
    assert selection.output_token == "grid-3x4"


def test_resolve_grid_selection_rejects_conflicts_or_missing() -> None:
    with pytest.raises(ValueError):
        resolve_grid_selection("a2", 3, 4)
    with pytest.raises(ValueError):
        resolve_grid_selection(None, 3, None)
    with pytest.raises(ValueError):
        resolve_grid_selection(None, None, None)


def test_resolve_grid_selection_rejects_out_of_range_custom_dims() -> None:
    with pytest.raises(ValueError):
        resolve_grid_selection(None, CUSTOM_GRID_MIN - 1, 2)
    with pytest.raises(ValueError):
        resolve_grid_selection(None, 2, CUSTOM_GRID_MAX + 1)


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


def test_selected_block_output_token() -> None:
    assert selected_block_output_token("a2", 1, 0) == "a2-block-1-0"


def test_multiple_block_selection_order_and_naming() -> None:
    assert parse_block_coordinate("2,1") == (2, 1)
    assert ordered_selected_blocks([(2, 1), (1, 0), (0, 0), (2, 1)], 3, 2) == [
        (0, 0), (1, 0), (2, 1)
    ]
    assert selected_blocks_output_token("a2", [(1, 0)]) == "a2-block-1-0"
    assert selected_blocks_output_token("a2", [(0, 0), (1, 1)]) == "a2-blocks-2"
    assert selected_blocks_output_token("a2", [(1, 0), (1, 0)]) == "a2-block-1-0"
    with pytest.raises(ValueError):
        parse_block_coordinate("1:0")
    with pytest.raises(ValueError):
        ordered_selected_blocks([], 2, 2)
    with pytest.raises(ValueError):
        ordered_selected_blocks([(2, 0)], 2, 2)
    assert selected_block_output_token("grid-3x4", 2, 3) == "grid-3x4-block-2-3"


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


def test_transform_argument_parsing_and_block_validation() -> None:
    assert parse_transform_scale("1.25") == 1.25
    assert parse_block_index("2", "Selected block column") == 2
    validate_selected_block(1, 0, cols=2, rows=2)
    with pytest.raises(ValueError):
        parse_transform_scale("0")
    with pytest.raises(ValueError):
        parse_block_index("-1", "Selected block column")
    with pytest.raises(ValueError):
        validate_selected_block(2, 0, cols=2, rows=2)


def test_render_transformed_source_preserves_canvas_size() -> None:
    image = Image.new("RGB", (40, 20), "white")
    rendered = render_transformed_source(
        image,
        TransformCutOptions(offset_x_px=5, offset_y_px=-2, rotation_deg=15, scale=1.1),
    )
    try:
        assert rendered.size == image.size
        assert rendered.mode == "RGB"
    finally:
        rendered.close()


def test_render_transformed_tile_preserves_offset_and_rotation() -> None:
    image = Image.new("RGB", (6, 4))
    image.putdata([(x * 30, y * 50, 10) for y in range(4) for x in range(6)])

    shifted = render_transformed_tile(image, TransformCutOptions(offset_x_px=1), Rect(0, 0, 3, 2))
    rotated = render_transformed_tile(image, TransformCutOptions(rotation_deg=90), Rect(1, 1, 5, 3))
    try:
        assert shifted.size == (3, 2)
        assert shifted.getpixel((0, 0)) == (255, 255, 255)
        assert shifted.getpixel((1, 0)) == image.getpixel((0, 0))
        assert rotated.tobytes() == image.rotate(90).crop((1, 1, 5, 3)).tobytes()
    finally:
        shifted.close()
        rotated.close()


def test_render_transformed_tile_retains_alpha_and_limits_canvas() -> None:
    image = Image.new("RGBA", (8, 8), (12, 34, 56, 255))
    rendered = render_transformed_tile(
        image,
        TransformCutOptions(offset_x_px=4, scale=1000),
        Rect(0, 0, 2, 2),
    )
    try:
        assert rendered.size == (2, 2)
        assert rendered.mode == "RGBA"
    finally:
        rendered.close()

    transparent = render_transformed_tile(image, TransformCutOptions(offset_x_px=20), Rect(0, 0, 2, 2))
    try:
        assert transparent.getpixel((0, 0))[3] == 0
    finally:
        transparent.close()


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


def test_main_custom_grid_mode_uses_explicit_dimensions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "wide.png"
    output_path = tmp_path / "out.pdf"
    Image.new("RGB", (1200, 500), "white").save(input_path)

    captured: dict[str, object] = {}

    def fake_compute_grid(_target: str, _orientation: str) -> tuple[int, int]:
        raise AssertionError("compute_grid should not be called in custom grid mode.")

    def fake_export(
        image,  # noqa: ANN001
        ordered_rects,  # noqa: ANN001
        output_path: Path,  # noqa: ARG001
        preserve_profile: bool = True,  # noqa: FBT001, FBT002
        preserve_metadata: bool = True,  # noqa: FBT001, FBT002
    ) -> list[str]:
        captured["size"] = image.size
        captured["rects"] = list(ordered_rects)
        return []

    monkeypatch.setattr(guidecut_module, "compute_grid", fake_compute_grid)
    monkeypatch.setattr(guidecut_module, "export_tiles_to_multipage_pdf", fake_export)

    exit_code = main(
        [
            str(input_path),
            "--grid-cols",
            "3",
            "--grid-rows",
            "2",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert captured["size"] == (1200, 500)
    rects = captured["rects"]
    assert len(rects) == 6
    assert rects[-1].box == (800, 250, 1200, 500)


def test_main_transform_cut_exports_selected_single_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        transform_options: TransformCutOptions | None = None,
    ) -> list[str]:
        captured["size"] = image.size
        captured["rects"] = list(ordered_rects)
        captured["preserve_profile"] = preserve_profile
        captured["preserve_metadata"] = preserve_metadata
        captured["transform_options"] = transform_options
        return []

    monkeypatch.setattr(guidecut_module, "export_tiles_to_multipage_pdf", fake_export)

    exit_code = main(
        [
            str(input_path),
            "a2",
            "--output",
            str(output_path),
            "--transform-cut",
            "--transform-offset-x",
            "10",
            "--transform-offset-y",
            "-5",
            "--transform-rotation-deg",
            "12",
            "--transform-scale",
            "1.1",
            "--block-col",
            "1",
            "--block-row",
            "0",
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert captured["size"] == (1200, 500)
    rects = captured["rects"]
    assert len(rects) == 1
    assert rects[0].box == (600, 0, 1200, 250)
    assert isinstance(captured["transform_options"], TransformCutOptions)
    assert captured["preserve_profile"] is True
    assert captured["preserve_metadata"] is True


def test_main_transform_cut_multiple_blocks_follow_page_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "source.png"
    Image.new("RGB", (1200, 500), "white").save(input_path)
    captured: dict[str, object] = {}

    def fake_export(image, ordered_rects, output_path, **kwargs):  # noqa: ANN001
        captured["rects"] = [rect.box for rect in ordered_rects]
        captured["transform"] = kwargs["transform_options"]
        return []

    monkeypatch.setattr(guidecut_module, "export_tiles_to_multipage_pdf", fake_export)
    exit_code = main(
        [
            str(input_path), "a2", "--transform-cut",
            "--block", "1,1", "--block", "1,0", "--block", "0,0", "--block", "1,0", "--quiet",
        ]
    )
    assert exit_code == 0
    assert captured["rects"] == [
        (0, 0, 600, 250), (600, 0, 1200, 250), (600, 250, 1200, 500)
    ]
    assert isinstance(captured["transform"], TransformCutOptions)


def test_main_rejects_mixed_legacy_and_multiple_block_flags(tmp_path: Path) -> None:
    input_path = tmp_path / "source.png"
    Image.new("RGB", (100, 100), "white").save(input_path)
    assert main([str(input_path), "a2", "--transform-cut", "--block", "0,0", "--block-col", "0", "--quiet"]) == 2


def test_main_transform_cut_rejects_out_of_range_block(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.png"
    output_path = tmp_path / "out.pdf"
    Image.new("RGB", (1200, 500), "white").save(input_path)

    exit_code = main(
        [
            str(input_path),
            "a3",
            "--output",
            str(output_path),
            "--transform-cut",
            "--block-col",
            "2",
            "--block-row",
            "0",
            "--quiet",
        ]
    )
    assert exit_code == 2


def test_main_rejects_conflicting_or_missing_grid_mode(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.png"
    Image.new("RGB", (1200, 500), "white").save(input_path)

    conflict = main([str(input_path), "a2", "--grid-cols", "2", "--grid-rows", "2", "--quiet"])
    missing = main([str(input_path), "--quiet"])
    partial = main([str(input_path), "--grid-cols", "2", "--quiet"])

    assert conflict == 2
    assert missing == 2
    assert partial == 2
