from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

MODULE_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = MODULE_ROOT / "app"
CLI_DIR = MODULE_ROOT / "cli"
for _module_dir in (APP_DIR, CLI_DIR):
    _path_text = str(_module_dir)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

from guidecut_runner import (
    CUSTOM_GRID_MAX,
    CUSTOM_GRID_MIN,
    DEFAULT_UI_STATE,
    browse_initial_directory,
    build_command,
    build_output_pdf_path,
    clamp_expand_bias_percent,
    choose_guide_style,
    contrast_ratio,
    expand_crop_for_source,
    expand_excess_axis,
    GUIDE_CONTRAST_HALO_THRESHOLD,
    load_ui_state,
    normalize_target_format,
    open_folder,
    open_folder_command,
    pan_offsets_from_preview_drag,
    parse_transform_cut_options,
    preview_block_for_point,
    effective_preview_state,
    relative_luminance,
    preview_guides_for_source,
    resolve_input_folder_from_field,
    resolve_existing_input_file,
    resolve_open_folder,
    resolve_output_directory,
    retained_input_value_after_run,
    rotation_from_preview_drag,
    run_command_streaming,
    sample_line_luminance,
    save_ui_state,
    scale_from_preview_scroll,
    scaled_preview_crop_box,
    scale_transform_for_preview,
    sanitize_preview_split_ratio,
    sanitize_expand_bias_percent,
    sanitize_ui_state,
    persisted_input_directory,
    preset_grid_for_orientation,
    resolve_custom_grid,
    sanitize_window_geometry,
    selected_block_rect_for_grid,
    tooltip_text_for_custom_grid,
    tooltip_text_for_format,
)
from iso216_guidecut import Rect, TransformCutOptions


def test_preview_geometry_tracks_original_pixels_after_downsampling() -> None:
    crop = Rect(1000, 500, 3000, 2500)
    assert scaled_preview_crop_box(crop, (4000, 3000), (1600, 1200)) == (400, 200, 1200, 1000)

    options = TransformCutOptions(offset_x_px=200, offset_y_px=-90, rotation_deg=15, scale=1.25)
    preview = scale_transform_for_preview(options, (2000, 2000), (800, 800))
    assert preview.offset_x_px == 80
    assert preview.offset_y_px == -36
    assert preview.rotation_deg == options.rotation_deg
    assert preview.scale == options.scale


def test_preview_transform_pointer_directions() -> None:
    assert pan_offsets_from_preview_drag((10, -5), (20, -10), (400, 200), (4000, 1000)) == (210, -55)
    assert rotation_from_preview_drag(0, (20, 0)) == -6
    assert rotation_from_preview_drag(0, (0, 20)) == -6
    assert rotation_from_preview_drag(0, (-20, -20)) == 12
    assert scale_from_preview_scroll(1, 1) == pytest.approx(1.1)
    assert scale_from_preview_scroll(1, -1) == pytest.approx(1 / 1.1)
    assert scale_from_preview_scroll(100, 1) == pytest.approx(110)
    assert scale_from_preview_scroll(0.01, -1) == pytest.approx(0.01 / 1.1)


def test_normalize_target_format() -> None:
    assert normalize_target_format("A1") == "a1"
    with pytest.raises(ValueError):
        normalize_target_format("a5")


@pytest.mark.parametrize(
    ("target", "tiles", "multiple"),
    [
        ("a3", "2", "2x A4"),
        ("a2", "4", "4x A4"),
        ("a1", "8", "8x A4"),
        ("a0", "16", "16x A4"),
    ],
)
def test_tooltip_text_for_format(target: str, tiles: str, multiple: str) -> None:
    text = tooltip_text_for_format(target)
    assert target.upper() in text
    assert f"Tiles/pages: {tiles}" in text
    assert f"Sheet size: {multiple}" in text


def test_tooltip_text_for_custom_grid() -> None:
    text = tooltip_text_for_custom_grid(3, 4)
    assert "Custom Grid" in text
    assert "Grid: 3x4" in text
    assert "Tiles/pages: 12" in text


def test_tooltip_text_for_custom_grid_invalid() -> None:
    text = tooltip_text_for_custom_grid(None, None)
    assert f"{CUSTOM_GRID_MIN}-{CUSTOM_GRID_MAX}" in text


def test_resolve_output_directory_explicit() -> None:
    input_path = Path("C:/input/poster.png")
    resolved = resolve_output_directory(input_path, explicit_enabled=True, explicit_dir_value="C:/out")
    assert resolved == Path("C:/out").resolve()


def test_resolve_output_directory_fallback() -> None:
    input_path = Path("C:/input/poster.png")
    resolved = resolve_output_directory(input_path, explicit_enabled=False, explicit_dir_value="C:/out")
    assert resolved == Path("C:/input").resolve()


def test_resolve_output_directory_enabled_but_empty_uses_input_parent() -> None:
    input_path = Path("C:/input/poster.png")
    resolved = resolve_output_directory(input_path, explicit_enabled=True, explicit_dir_value=" ")
    assert resolved == Path("C:/input").resolve()


def test_retained_input_value_after_run_returns_parent() -> None:
    value = retained_input_value_after_run(Path("C:/maps/arena.avif"))
    assert value == str(Path("C:/maps").resolve())


def test_resolve_input_folder_from_field_nonexistent_file_path_returns_parent() -> None:
    resolved = resolve_input_folder_from_field("C:/maps/arena.avif")
    assert resolved == Path("C:/maps").resolve()


def test_resolve_input_folder_from_field_nonexistent_dir_path_returns_dir() -> None:
    resolved = resolve_input_folder_from_field("C:/maps/")
    assert resolved == Path("C:/maps").resolve()


def test_resolve_input_folder_from_field_existing_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self).replace("\\", "/").endswith("/in/maps")

    def fake_is_dir(self: Path) -> bool:
        return fake_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "is_dir", fake_is_dir, raising=False)

    resolved = resolve_input_folder_from_field("C:/in/maps")
    assert str(resolved).replace("\\", "/").endswith("/in/maps")


def test_resolve_existing_input_file_returns_none_for_empty_or_missing() -> None:
    assert resolve_existing_input_file("") is None
    assert resolve_existing_input_file("C:/missing/nope.avif") is None


def test_resolve_existing_input_file_returns_path_for_existing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self).replace("\\", "/").endswith("/in/maps/arena.avif")

    def fake_is_file(self: Path) -> bool:
        return fake_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "is_file", fake_is_file, raising=False)

    resolved = resolve_existing_input_file("C:/in/maps/arena.avif")
    assert resolved is not None
    assert str(resolved).replace("\\", "/").endswith("/in/maps/arena.avif")


def test_effective_preview_state_for_missing_input() -> None:
    visible, enabled, file_path = effective_preview_state("C:/missing/nope.avif", True)
    assert visible is False
    assert enabled is False
    assert file_path is None


def test_effective_preview_state_for_existing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self).replace("\\", "/").endswith("/in/maps/arena.avif")

    def fake_is_file(self: Path) -> bool:
        return fake_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "is_file", fake_is_file, raising=False)

    visible, enabled, file_path = effective_preview_state("C:/in/maps/arena.avif", True)
    assert visible is True
    assert enabled is True
    assert file_path is not None


def test_preview_guides_for_source_uses_orientation_and_target_grid() -> None:
    cols, rows, vertical, horizontal = preview_guides_for_source(1000, 500, "A2")
    assert cols == 2
    assert rows == 2
    assert vertical == [500]
    assert horizontal == [250]

    cols, rows, vertical, horizontal = preview_guides_for_source(500, 1000, "A3")
    assert cols == 1
    assert rows == 2
    assert vertical == []
    assert horizontal == [500]


def test_preview_guides_for_source_with_custom_grid() -> None:
    cols, rows, vertical, horizontal = preview_guides_for_source(
        1200,
        600,
        target_format=None,
        custom_grid_cols=3,
        custom_grid_rows=2,
    )
    assert cols == 3
    assert rows == 2
    assert vertical == [400, 800]
    assert horizontal == [300]


def test_resolve_custom_grid() -> None:
    assert resolve_custom_grid("3", "4") == (3, 4)
    with pytest.raises(ValueError):
        resolve_custom_grid("0", "4")
    with pytest.raises(ValueError):
        resolve_custom_grid("3", "")


def test_preset_grid_for_orientation() -> None:
    assert preset_grid_for_orientation("A3", "portrait") == (1, 2)
    assert preset_grid_for_orientation("A3", "landscape") == (2, 1)


def test_browse_initial_directory_none_for_empty_or_non_existing() -> None:
    assert browse_initial_directory("") is None
    assert browse_initial_directory("C:/missing/nope.avif") is None


def test_browse_initial_directory_returns_existing_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self).replace("\\", "/").endswith("/maps")

    def fake_is_dir(self: Path) -> bool:
        return fake_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "is_dir", fake_is_dir, raising=False)

    result = browse_initial_directory("C:/maps")
    assert result is not None
    assert result.replace("\\", "/").endswith("/maps")


def test_sanitize_ui_state_defaults_on_bad_values() -> None:
    state = sanitize_ui_state(
        {
            "target_format": "a9",
            "specify_output_dir": "notabool",
            "output_dir": None,
        }
    )
    assert state["target_format"] == DEFAULT_UI_STATE["target_format"]
    assert state["specify_output_dir"] is False
    assert state["output_dir"] == ""
    assert state["input_dir"] == ""
    assert state["window_geometry"] == ""
    assert state["preview_split_ratio"] == DEFAULT_UI_STATE["preview_split_ratio"]
    assert state["expand_to_format"] is DEFAULT_UI_STATE["expand_to_format"]
    assert state["expand_bias_percent"] == DEFAULT_UI_STATE["expand_bias_percent"]


def test_sanitize_window_geometry_accepts_valid_and_rejects_invalid() -> None:
    assert sanitize_window_geometry("1280x720+50+60") == "1280x720+50+60"
    assert sanitize_window_geometry("1024x768-10+20") == "1024x768-10+20"
    assert sanitize_window_geometry("900x600") == "900x600"
    assert sanitize_window_geometry("abc") == ""
    assert sanitize_window_geometry("1200x800+10") == ""


def test_sanitize_preview_split_ratio_bounds_and_defaults() -> None:
    assert sanitize_preview_split_ratio(0.8) == 0.8
    assert sanitize_preview_split_ratio("1.25") == 1.25
    assert sanitize_preview_split_ratio(0.1) == DEFAULT_UI_STATE["preview_split_ratio"]
    assert sanitize_preview_split_ratio("bad") == DEFAULT_UI_STATE["preview_split_ratio"]


def test_sanitize_expand_bias_percent_bounds_and_defaults() -> None:
    assert sanitize_expand_bias_percent(0) == 0.0
    assert sanitize_expand_bias_percent(100) == 100.0
    assert sanitize_expand_bias_percent(-5) == 0.0
    assert sanitize_expand_bias_percent(105) == 100.0
    assert sanitize_expand_bias_percent("bad") == DEFAULT_UI_STATE["expand_bias_percent"]


def test_expand_helpers_return_expected_axis_and_crop() -> None:
    assert expand_excess_axis(1000, 500) == "x"
    assert expand_excess_axis(500, 1000) == "y"
    crop = expand_crop_for_source(1000, 500, 50)
    assert crop.excess_px > 0
    assert crop.axis == "x"


def test_clamp_expand_bias_percent_from_runner() -> None:
    assert clamp_expand_bias_percent(-10) == 0.0
    assert clamp_expand_bias_percent(120) == 100.0
    assert clamp_expand_bias_percent("bad", default=33.0) == 33.0


def test_relative_luminance_monotonicity_black_gray_white() -> None:
    black = relative_luminance((0, 0, 0))
    gray = relative_luminance((127, 127, 127))
    white = relative_luminance((255, 255, 255))
    assert black < gray < white


def test_contrast_ratio_sanity() -> None:
    black = relative_luminance((0, 0, 0))
    white = relative_luminance((255, 255, 255))
    light_gray = relative_luminance((220, 220, 220))
    assert contrast_ratio(white, black) > contrast_ratio(white, light_gray)


def test_choose_guide_style_prefers_light_stroke_for_dark_samples() -> None:
    stroke, halo = choose_guide_style([0.01, 0.02, 0.03, 0.04])
    assert stroke == "#FFFFFF"
    assert halo is None


def test_choose_guide_style_prefers_dark_stroke_for_light_samples() -> None:
    stroke, halo = choose_guide_style([0.93, 0.95, 0.97])
    assert stroke == "#111111"
    assert halo is None


def test_choose_guide_style_adds_halo_for_low_worst_case_contrast() -> None:
    samples = [
        relative_luminance((15, 143, 132)),
        relative_luminance((255, 255, 255)),
        relative_luminance((17, 17, 17)),
        relative_luminance((255, 213, 74)),
        relative_luminance((255, 77, 109)),
    ]
    stroke, halo = choose_guide_style(samples)
    assert halo is not None
    assert halo != stroke
    assert GUIDE_CONTRAST_HALO_THRESHOLD > 1.0


def test_sample_line_luminance_and_style_selection_vary_by_background() -> None:
    image = Image.new("RGB", (80, 20), (255, 255, 255))
    for x in range(0, 40):
        for y in range(0, 20):
            image.putpixel((x, y), (10, 10, 10))

    dark_samples = sample_line_luminance(image, 10, 0, 10, 19, step=4)
    light_samples = sample_line_luminance(image, 70, 0, 70, 19, step=4)
    assert dark_samples and light_samples

    dark_style = choose_guide_style(dark_samples)
    light_style = choose_guide_style(light_samples)
    assert dark_style[0] != light_style[0]


def test_persisted_input_directory_strips_filename() -> None:
    value = persisted_input_directory("C:/maps/arena.avif")
    assert value == str(Path("C:/maps").resolve())


def test_save_and_load_ui_state_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = Path("C:/state/guidecut_ui_state.json")
    storage: dict[str, str] = {}

    def fake_mkdir(self: Path, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    def fake_write_text(self: Path, text: str, *args, **kwargs) -> int:  # noqa: ANN002, ANN003
        storage[str(self)] = text
        return len(text)

    def fake_exists(self: Path) -> bool:
        return str(self) in storage

    def fake_read_text(self: Path, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return storage[str(self)]

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)
    monkeypatch.setattr(Path, "write_text", fake_write_text, raising=False)
    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)

    save_ui_state(
        state_path,
        target_format="A1",
        specify_output_dir=True,
        output_dir="C:/out",
        input_dir="C:/maps/arena.avif",
        window_geometry="1280x720+80+90",
        preview_split_ratio=0.75,
        expand_to_format=True,
        expand_bias_percent=65.0,
    )
    loaded = load_ui_state(state_path)
    assert loaded["target_format"] == "a1"
    assert loaded["specify_output_dir"] is True
    assert loaded["output_dir"] == "C:/out"
    assert loaded["input_dir"] == str(Path("C:/maps").resolve())
    assert loaded["window_geometry"] == "1280x720+80+90"
    assert loaded["preview_split_ratio"] == 0.75
    assert loaded["expand_to_format"] is True
    assert loaded["expand_bias_percent"] == 65.0


def test_load_ui_state_returns_defaults_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = Path("C:/state/missing_state.json")
    monkeypatch.setattr(Path, "exists", lambda _self: False, raising=False)
    loaded = load_ui_state(missing)
    assert loaded == DEFAULT_UI_STATE


def test_load_ui_state_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = Path("C:/state/bad_state.json")
    monkeypatch.setattr(Path, "exists", lambda _self: True, raising=False)
    monkeypatch.setattr(Path, "read_text", lambda _self, **_kwargs: "{", raising=False)
    with pytest.raises(RuntimeError):
        load_ui_state(state_path)


def test_build_output_pdf_path_uses_timestamp_and_collision_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = Path("C:/input/poster.png")
    output_dir = Path("C:/out")
    now = dt.datetime(2026, 3, 21, 17, 20, 0, tzinfo=dt.timezone.utc)

    occupied: set[str] = set()

    def fake_exists(self: Path) -> bool:
        return self.name in occupied

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)

    first = build_output_pdf_path(input_path, "a2", output_dir, now_local=now)
    assert first.name == "poster-guidecut-a2-20260321-172000.pdf"

    occupied.add(first.name)
    second = build_output_pdf_path(input_path, "a2", output_dir, now_local=now)
    assert second.name == "poster-guidecut-a2-20260321-172000-1.pdf"


def test_build_output_pdf_path_custom_grid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = Path("C:/input/poster.png")
    output_dir = Path("C:/out")
    now = dt.datetime(2026, 3, 21, 17, 20, 0, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(Path, "exists", lambda _self: False, raising=False)
    output = build_output_pdf_path(
        input_path,
        target_format=None,
        output_dir=output_dir,
        custom_grid_cols=3,
        custom_grid_rows=4,
        now_local=now,
    )
    assert output.name == "poster-guidecut-grid-3x4-20260321-172000.pdf"


def test_build_output_pdf_path_transform_block_token(monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = Path("C:/input/poster.png")
    output_dir = Path("C:/out")
    now = dt.datetime(2026, 3, 21, 17, 20, 0, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(Path, "exists", lambda _self: False, raising=False)
    output = build_output_pdf_path(
        input_path,
        target_format="a2",
        output_dir=output_dir,
        transform_cut=True,
        transform_block_col=1,
        transform_block_row=0,
        now_local=now,
    )
    assert output.name == "poster-guidecut-a2-block-1-0-20260321-172000.pdf"


def test_build_output_pdf_path_multiple_transform_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _self: False, raising=False)
    output = build_output_pdf_path(
        Path("C:/input/poster.png"),
        target_format="a2",
        output_dir=Path("C:/out"),
        transform_cut=True,
        transform_blocks=((0, 0), (1, 1)),
        now_local=dt.datetime(2026, 3, 21, 17, 20, 0, tzinfo=dt.timezone.utc),
    )
    assert output.name == "poster-guidecut-a2-blocks-2-20260321-172000.pdf"


def test_build_command_without_output() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="a3",
        output_path=None,
    )
    assert command == ["python", "iso216_guidecut.py", "C:\\in\\file.avif", "a3"]


def test_build_command_custom_grid_mode() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format=None,
        custom_grid_cols=3,
        custom_grid_rows=4,
        output_path=None,
    )
    assert command == [
        "python",
        "iso216_guidecut.py",
        "C:\\in\\file.avif",
        "--grid-cols",
        "3",
        "--grid-rows",
        "4",
    ]


def test_build_command_with_output() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="a1",
        output_path=Path("C:/out/custom.pdf"),
    )
    assert command == [
        "python",
        "iso216_guidecut.py",
        "C:\\in\\file.avif",
        "a1",
        "--output",
        "C:\\out\\custom.pdf",
    ]


def test_build_command_normalizes_target_case() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="A2",
        output_path=None,
    )
    assert command[-1] == "a2"


def test_build_command_with_expand_args() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="A2",
        output_path=None,
        expand_to_format=True,
        expand_bias_percent=33.5,
    )
    assert "--expand-to-format" in command
    assert "--expand-bias-percent" in command
    bias_index = command.index("--expand-bias-percent")
    assert command[bias_index + 1] == "33.5"


def test_build_command_with_transform_cut_args() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="A2",
        output_path=None,
        transform_cut=True,
        transform_offset_x=12.5,
        transform_offset_y=-3,
        transform_rotation_deg=22,
        transform_scale=1.25,
        transform_block_col=1,
        transform_block_row=0,
    )
    assert "--transform-cut" in command
    assert command[command.index("--transform-offset-x") + 1] == "12.5"
    assert command[command.index("--transform-offset-y") + 1] == "-3"
    assert command[command.index("--transform-rotation-deg") + 1] == "22"
    assert command[command.index("--transform-scale") + 1] == "1.25"
    assert command[command.index("--block-col") + 1] == "1"
    assert command[command.index("--block-row") + 1] == "0"


def test_build_command_with_multiple_transform_blocks() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.png"),
        target_format="A2",
        transform_cut=True,
        transform_blocks=((1, 1), (0, 0), (1, 0), (1, 0)),
    )
    assert [command[index + 1] for index, item in enumerate(command[:-1]) if item == "--block"] == [
        "0,0", "1,0", "1,1"
    ]
    assert "--block-col" not in command
    assert "--block-row" not in command
    with pytest.raises(ValueError, match="at least one block"):
        build_command(
            "python", Path("iso216_guidecut.py"), Path("C:/in/file.png"),
            target_format="A2", transform_cut=True, transform_blocks=(),
        )


def test_build_command_keeps_mouse_transform_precision() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.png"),
        target_format="A2",
        output_path=None,
        transform_cut=True,
        transform_offset_x=1234.567,
        transform_rotation_deg=-12.345,
        transform_scale=1.234567,
    )
    assert command[command.index("--transform-offset-x") + 1] == "1234.567"
    assert command[command.index("--transform-rotation-deg") + 1] == "-12.345"
    assert command[command.index("--transform-scale") + 1] == "1.234567"


def test_build_command_without_expand_args_when_disabled() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="A2",
        output_path=None,
        expand_to_format=False,
        expand_bias_percent=75.0,
    )
    assert "--expand-to-format" not in command
    assert "--expand-bias-percent" not in command


def test_transform_helper_parsing_and_preview_block_math() -> None:
    options = parse_transform_cut_options(
        enabled=True,
        offset_x="4.5",
        offset_y="-2",
        rotation_deg="10",
        scale="1.5",
        block_col="1",
        block_row="2",
    )
    assert options.enabled is True
    assert options.offset_x_px == 4.5
    assert options.offset_y_px == -2.0
    assert options.rotation_deg == 10.0
    assert options.scale == 1.5
    assert options.block_col == 1
    assert options.block_row == 2

    rect = selected_block_rect_for_grid(1, 1, cols=3, rows=2, width_px=900, height_px=400)
    assert rect.box == (300, 200, 600, 400)

    assert preview_block_for_point(50, 50, 0, 0, 300, 200, 3, 2) == (0, 0)
    assert preview_block_for_point(299, 199, 0, 0, 300, 200, 3, 2) == (2, 1)
    assert preview_block_for_point(301, 50, 0, 0, 300, 200, 3, 2) is None


def test_build_command_rejects_preset_custom_conflict() -> None:
    with pytest.raises(ValueError):
        build_command(
            python_executable="python",
            script_path=Path("iso216_guidecut.py"),
            input_path=Path("C:/in/file.avif"),
            target_format="A2",
            custom_grid_cols=2,
            custom_grid_rows=2,
        )


def test_resolve_open_folder_prefers_explicit_output_dir() -> None:
    folder = resolve_open_folder(
        input_path_value="C:/in/file.avif",
        explicit_enabled=True,
        explicit_dir_value="C:/target",
    )
    assert folder == Path("C:/target").resolve()


def test_resolve_open_folder_falls_back_to_input_parent() -> None:
    folder = resolve_open_folder(
        input_path_value="C:/in/file.avif",
        explicit_enabled=False,
        explicit_dir_value="",
    )
    assert folder == Path("C:/in").resolve()


def test_resolve_open_folder_uses_input_folder_when_path_is_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_exists(self: Path) -> bool:
        return str(self).replace("\\", "/").endswith("/in/maps")

    def fake_is_dir(self: Path) -> bool:
        return fake_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(Path, "is_dir", fake_is_dir, raising=False)

    folder = resolve_open_folder(
        input_path_value="C:/in/maps",
        explicit_enabled=False,
        explicit_dir_value="",
    )
    assert str(folder).replace("\\", "/").endswith("/in/maps")


def test_resolve_open_folder_errors_when_no_inputs() -> None:
    with pytest.raises(ValueError):
        resolve_open_folder(input_path_value="", explicit_enabled=False, explicit_dir_value="")


def test_open_folder_command_windows_and_mac() -> None:
    folder = Path("C:/out")
    assert open_folder_command(folder, platform_name="win32")[0] == "explorer"
    assert open_folder_command(folder, platform_name="darwin")[0] == "open"


def test_open_folder_invokes_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    folder = Path("C:/out")

    monkeypatch.setattr(Path, "exists", lambda _self: True, raising=False)
    monkeypatch.setattr(Path, "is_dir", lambda _self: True, raising=False)

    calls: list[list[str]] = []

    def fake_popen(command, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        calls.append(command)

        class DummyProcess:
            pass

        return DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    command = open_folder(folder, platform_name="darwin")
    assert command[0] == "open"
    assert calls and calls[0][0] == "open"


def test_run_command_streaming_captures_stdout_stderr_and_exit_code() -> None:
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    command = [
        sys.executable,
        "-c",
        "import sys; print('hello'); print('oops', file=sys.stderr); sys.exit(3)",
    ]
    code = run_command_streaming(
        command=command,
        cwd=Path.cwd(),
        on_stdout=stdout_lines.append,
        on_stderr=stderr_lines.append,
    )

    assert code == 3
    assert "hello" in stdout_lines
    assert "oops" in stderr_lines


def test_run_command_streaming_reports_launch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_popen(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("boom")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError):
        run_command_streaming(
            command=["python", "-c", "print('x')"],
            cwd=Path.cwd(),
            on_stdout=lambda _line: None,
            on_stderr=lambda _line: None,
        )
