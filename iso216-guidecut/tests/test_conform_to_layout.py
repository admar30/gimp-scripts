from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
from PIL import Image

MODULE_ROOT = Path(__file__).resolve().parents[1]
for folder in (MODULE_ROOT / "cli", MODULE_ROOT / "app"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import iso216_guidecut as cli
from guidecut_runner import (
    TransformCutUiOptions,
    build_command,
    layout_for_source,
    load_ui_state,
    offsets_for_preview_center_pivot,
    oriented_source_size,
    render_layout_preview,
    sanitize_ui_state,
    save_ui_state,
)


@pytest.mark.parametrize("target", ["a3", "a2", "a1", "a0"])
@pytest.mark.parametrize("size", [(1000, 1500), (1500, 1000), (1000, 1000)])
def test_preset_fill_preserves_existing_geometry(target: str, size: tuple[int, int]) -> None:
    selection = cli.resolve_grid_selection(target, None, None)
    layout = cli.resolve_layout_geometry(*size, selection, conform_to_layout=True, bias_percent=35)
    assert (layout.cols, layout.rows) == cli.compute_grid(target, cli.detect_orientation(*size))
    assert layout.crop == cli.compute_expand_crop_rect(*size, 35)


@pytest.mark.parametrize(
    ("size", "grid", "orientation", "frame_size"),
    [
        ((1000, 1000), (3, 2), "portrait", (1000, 943)),
        ((3000, 1000), (3, 2), "landscape", (2121, 1000)),
        ((1500, 1000), (3, 2), "portrait", (1061, 1000)),
        ((1000, 2000), (1, 4), "landscape", (707, 2000)),
        ((2000, 1000), (4, 1), "portrait", (2000, 707)),
    ],
)
def test_custom_orientation_maximizes_retained_area(
    size: tuple[int, int], grid: tuple[int, int], orientation: str, frame_size: tuple[int, int],
) -> None:
    selection = cli.resolve_grid_selection(None, *grid)
    for bias in (0, 50, 100):
        layout = cli.resolve_layout_geometry(*size, selection, conform_to_layout=True, bias_percent=bias)
        assert (layout.cols, layout.rows) == grid
        assert layout.tile_orientation == orientation
        assert layout.size == frame_size
    rects = [cli.compute_tile_crop(col, row, *grid, *layout.size) for col, row in cli.ordered_tiles(*grid)]
    assert sum((rect.x1 - rect.x0) * (rect.y1 - rect.y0) for rect in rects) == math.prod(layout.size)
    tile_ratio = 1 / math.sqrt(2) if orientation == "portrait" else math.sqrt(2)
    assert (layout.size[0] / grid[0]) / (layout.size[1] / grid[1]) == pytest.approx(tile_ratio, abs=0.002)


@pytest.mark.parametrize("size", [(1000, 943), (2121, 1000)])
def test_matching_custom_layout_needs_no_trim(size: tuple[int, int]) -> None:
    layout = layout_for_source(*size, custom_grid_cols=3, custom_grid_rows=2, conform_to_layout=True)
    assert layout.size == size
    assert layout.crop.axis is None


@pytest.mark.parametrize("size, axis", [((160, 100), "x"), ((100, 160), "y")])
@pytest.mark.parametrize("bias", [0, 50, 100])
def test_fill_bias_distributes_trim(size: tuple[int, int], axis: str, bias: int) -> None:
    crop = cli.compute_fill_crop_rect(*size, 1, bias)
    assert crop.axis == axis
    assert crop.excess_px == 60
    assert crop.leading_trim_px == round(60 * bias / 100)
    assert crop.trailing_trim_px == 60 - crop.leading_trim_px


def test_conform_off_and_undersized_frame() -> None:
    layout = layout_for_source(1000, 1000, custom_grid_cols=3, custom_grid_rows=2)
    assert layout.frame.box == (0, 0, 1000, 1000)
    with pytest.raises(ValueError, match="too small"):
        layout_for_source(10, 10, custom_grid_cols=32, custom_grid_rows=1, conform_to_layout=True)


@pytest.mark.parametrize("offset, expected", [(0, (3, 0, 9, 8)), (3, (0, 0, 6, 8)), (-3, (6, 0, 12, 8))])
def test_transform_recovers_pixels_outside_fill_frame(offset: int, expected: tuple[int, int, int, int]) -> None:
    source = Image.new("RGB", (12, 8))
    source.putdata([(x * 15, y * 20, 0) for y in range(8) for x in range(12)])
    source.info["title"] = "Retained full source"
    rendered = cli.render_transformed_source(
        source, cli.TransformCutOptions(offset_x_px=offset), frame=cli.Rect(3, 0, 9, 8),
    )
    reference = source.crop(expected)
    try:
        assert rendered.tobytes() == reference.tobytes()
        assert rendered.info["title"] == source.info["title"]
    finally:
        reference.close()
        rendered.close()
        source.close()


def test_preview_samples_full_thumbnail_in_source_coordinates() -> None:
    thumbnail = Image.new("RGB", (40, 32))
    thumbnail.putdata([(x * 6, y * 7, 0) for y in range(32) for x in range(40)])
    layout = layout_for_source(80, 64, custom_grid_cols=3, custom_grid_rows=2, conform_to_layout=True)
    options = TransformCutUiOptions(enabled=True, offset_x_px=10, offset_y_px=-4, rotation_deg=25, scale=1.2)
    preview = render_layout_preview(thumbnail, (80, 64), layout, options)
    reference = cli.render_transformed_source(
        thumbnail, cli.TransformCutOptions(offset_x_px=5, offset_y_px=-2, rotation_deg=25, scale=1.2),
        frame=cli.Rect(3, 0, 37, 32),
    )
    try:
        assert preview.size == (34, 32)
        assert preview.tobytes() == reference.tobytes()
    finally:
        thumbnail.close()
        preview.close()
        reference.close()


def test_center_pivot_with_biased_frame_preserves_anchor() -> None:
    frame = cli.Rect(40, 0, 240, 300)
    old = cli.TransformCutOptions(offset_x_px=20, offset_y_px=-10, rotation_deg=15, scale=1.2)
    x, y = offsets_for_preview_center_pivot((20, -10), 15, 1.2, -35, 2)
    new = cli.TransformCutOptions(offset_x_px=x, offset_y_px=y, rotation_deg=-35, scale=2)

    def source_at_center(options: cli.TransformCutOptions) -> tuple[float, float]:
        angle = math.radians(options.rotation_deg)
        return (
            (frame.x0 + frame.x1) / 2 - (math.cos(angle) * options.offset_x_px - math.sin(angle) * options.offset_y_px) / options.scale,
            (frame.y0 + frame.y1) / 2 - (math.sin(angle) * options.offset_x_px + math.cos(angle) * options.offset_y_px) / options.scale,
        )

    assert source_at_center(new) == pytest.approx(source_at_center(old))


@pytest.mark.parametrize("flag, bias_flag", [("--conform-to-layout", "--conform-bias-percent"), ("--expand-to-format", "--expand-bias-percent")])
def test_cli_conform_aliases_use_custom_geometry_and_full_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str, bias_flag: str,
) -> None:
    source_path = tmp_path / "source.png"
    Image.new("RGB", (1000, 1000)).save(source_path)
    captured = {}

    def capture_export(image, ordered_rects, output_path, **kwargs):
        captured.update(size=image.size, rects=list(ordered_rects), **kwargs)
        return []

    monkeypatch.setattr(cli, "export_tiles_to_multipage_pdf", capture_export)
    result = cli.main([
        str(source_path), "--grid-cols", "3", "--grid-rows", "2", flag, bias_flag, "0",
        "--transform-cut", "--block", "2,1", "--block", "0,0", "--quiet",
    ])
    assert result == 0
    assert captured["size"] == (1000, 1000)
    assert captured["frame"].box == (0, 0, 1000, 943)
    assert [rect.box for rect in captured["rects"]] == [(0, 0, 333, 472), (667, 472, 1000, 943)]


def test_cli_and_preview_use_same_exif_orientation(tmp_path: Path) -> None:
    path = tmp_path / "oriented.jpg"
    image = Image.new("RGB", (120, 60), "white")
    exif = Image.Exif()
    exif[274] = 6
    image.save(path, exif=exif, dpi=(144, 144))
    source = cli._load_source_image(path)
    try:
        assert source.size == oriented_source_size(path) == (60, 120)
        assert source.getexif().get(274) is None
        assert source.info["dpi"] == (144, 144)
    finally:
        source.close()
        image.close()


def test_state_migration_and_canonical_roundtrip(tmp_path: Path) -> None:
    state = sanitize_ui_state({"expand_to_format": True, "expand_bias_percent": 35})
    assert state["conform_to_layout"] is True
    assert state["conform_bias_percent"] == 35
    assert "expand_to_format" not in state
    state = sanitize_ui_state({
        "expand_to_format": True, "expand_bias_percent": 35,
        "conform_to_layout": False, "conform_bias_percent": float("nan"),
    })
    assert state["conform_to_layout"] is False
    assert state["conform_bias_percent"] == 50
    path = tmp_path / "state.json"
    save_ui_state(path, target_format="A2", specify_output_dir=False, output_dir="", conform_to_layout=True, conform_bias_percent=72)
    assert load_ui_state(path)["conform_bias_percent"] == 72
    assert "expand_bias_percent" not in json.loads(path.read_text())


def test_runner_emits_canonical_conform_flags() -> None:
    command = build_command(
        "python", Path("iso216_guidecut.py"), Path("source.png"), None, None,
        custom_grid_cols=3, custom_grid_rows=2, conform_to_layout=True, conform_bias_percent=35,
    )
    assert "--conform-to-layout" in command
    assert command[command.index("--conform-bias-percent") + 1] == "35"
    command = build_command(
        "python", Path("iso216_guidecut.py"), Path("source.png"), "a2", None,
        conform_to_layout=False, expand_to_format=True,
    )
    assert "--conform-to-layout" not in command
