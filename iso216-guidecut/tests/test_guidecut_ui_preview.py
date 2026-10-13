from __future__ import annotations

import queue
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from guidecut_ui import GuidecutApp, PREVIEW_MAX_EDGE_PX
from guidecut_runner import TransformCutUiOptions


class FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class FakeControl:
    def __init__(self) -> None:
        self.visible = False
        self.disabled = False
        self.text = ""

    def grid(self) -> None:
        self.visible = True

    def grid_remove(self) -> None:
        self.visible = False

    def state(self, states: list[str]) -> None:
        self.disabled = "disabled" in states

    def configure(self, *, text: str) -> None:
        self.text = text


def test_conform_ui_controls_retain_bias_and_follow_custom_layout(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    next_source = tmp_path / "next.png"
    Image.new("RGB", (2, 2)).save(source)
    Image.new("RGB", (2, 2)).save(next_source)
    app = GuidecutApp.__new__(GuidecutApp)
    app.input_var = FakeVar(str(source))
    app.conform_to_layout_var = FakeVar(True)
    app.conform_bias_var = FakeVar(50)
    app.conform_bias_label_var = FakeVar("")
    app.custom_tile_orientation_var = FakeVar("")
    app.custom_grid_var = FakeVar(True)
    app.custom_cols_var = FakeVar("3")
    app.custom_rows_var = FakeVar("2")
    app.target_var = FakeVar("A2")
    app.transform_cut_var = FakeVar(False)
    app.show_preview_var = FakeVar(False)
    app.conform_row = FakeControl()
    app.conform_scale = FakeControl()
    app.conform_bias_label = FakeControl()
    app.custom_tile_orientation_label = FakeControl()
    app.info_tooltip = SimpleNamespace(refresh=lambda: None)
    app._preview_panel_visible = False
    app._preview_source_image = None
    app._current_input_source_size = lambda: (1000, 1000)

    app._on_conform_toggle()
    assert app.conform_row.visible
    assert not app.conform_scale.disabled
    assert app.custom_tile_orientation_var.get() == "Tiles: Portrait (Auto)"
    app._set_conform_bias_percent(35, rerender=False, fast_preview=False)
    app.conform_to_layout_var.set(False)
    app._on_conform_toggle()
    assert not app.conform_row.visible
    app.conform_to_layout_var.set(True)
    app._on_conform_toggle()
    assert app.conform_bias_var.get() == 35

    app.custom_cols_var.set("")
    app._on_custom_grid_value_changed()
    assert app.conform_scale.disabled
    assert app.custom_tile_orientation_var.get() == "Tiles: pending"
    app.custom_cols_var.set("1")
    app.custom_rows_var.set("4")
    app._on_custom_grid_value_changed()
    assert app.conform_bias_var.get() == 35
    assert app.custom_tile_orientation_var.get() == "Tiles: Landscape (Auto)"

    app.custom_cols_var.set("3")
    app.custom_rows_var.set("2")
    app._current_input_source_size = lambda: (1000, 943)
    app._update_conform_slider_state()
    assert app.conform_scale.disabled
    assert app.conform_bias_label.text == "Trim Bias (No excess edge)"

    app._active_input_document = str(source.resolve())
    app._sync_conform_document_state()
    assert app.conform_bias_var.get() == 35
    app.input_var.set(str(next_source))
    app._sync_conform_document_state()
    assert not app.conform_to_layout_var.get()
    assert app.conform_bias_var.get() == 50


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


def test_transform_preview_click_drag_rotate_and_wheel() -> None:
    app = GuidecutApp.__new__(GuidecutApp)
    app.transform_cut_var = SimpleNamespace(get=lambda: True)
    app._preview_panel_visible = True
    app._preview_source_image = Image.new("RGB", (400, 200))
    app._last_preview_display_box = (0, 0, 400, 200)
    app._last_preview_working_size = (4000, 1000)
    app._transform_drag_mode = None
    app._transform_drag_start_options = None
    app._transform_drag_moved = False
    app._conform_drag_active = True
    app._current_transform_grid = lambda: (2, 2)
    options = TransformCutUiOptions(enabled=True, scale=1)
    app._current_transform_options = lambda *, strict: options
    updates: list[dict] = []
    selections: list[tuple[int, int]] = []
    app._set_transform_control_values = lambda **values: updates.append(values)
    app._select_transform_block_from_preview = lambda event: selections.append((event.x, event.y))

    try:
        app._on_preview_drag_start(SimpleNamespace(x=50, y=50))
        app._on_preview_drag_motion(SimpleNamespace(x=70, y=40))
        app._on_preview_drag_end(SimpleNamespace(x=70, y=40))
        assert updates[-1] == {"offset_x": 200, "offset_y": -50}
        assert selections == []
        assert not app._conform_drag_active

        app._on_preview_drag_start(SimpleNamespace(x=60, y=60))
        app._on_preview_drag_end(SimpleNamespace(x=60, y=60))
        assert selections == [(60, 60)]

        app._on_preview_rotate_start(SimpleNamespace(x=50, y=50))
        app._on_preview_rotate_motion(SimpleNamespace(x=70, y=50))
        app._on_preview_rotate_end(SimpleNamespace(x=70, y=50))
        assert updates[-1] == {"rotation": -6}

        assert app._on_preview_mouse_wheel(SimpleNamespace(x=50, y=50, delta=120)) == "break"
        assert updates[-1]["scale"] == 1.1
        assert app._on_preview_mouse_wheel(SimpleNamespace(x=50, y=50, delta=-1)) == "break"
        assert updates[-1]["scale"] < 1
    finally:
        app._preview_source_image.close()


def test_rotation_and_zoom_controls_pivot_at_preview_center() -> None:
    app = GuidecutApp.__new__(GuidecutApp)
    app.transform_cut_var = SimpleNamespace(get=lambda: True)
    app.transform_offset_x_var = FakeVar("0")
    app.transform_offset_y_var = FakeVar("0")
    app.transform_rotation_var = FakeVar("0")
    app.transform_scale_var = FakeVar("1")
    app.transform_block_col_var = FakeVar("0")
    app.transform_block_row_var = FakeVar("0")
    app._last_valid_transform_options = TransformCutUiOptions(enabled=True)
    app._updating_transform_vars = False
    app._preview_panel_visible = False
    app._preview_source_image = None

    app._set_transform_control_values(offset_x=40, offset_y=20)
    app._set_transform_control_values(rotation=90)
    assert float(app.transform_offset_x_var.get()) == pytest.approx(20)
    assert float(app.transform_offset_y_var.get()) == pytest.approx(-40)

    app._set_transform_control_values(scale=2)
    assert float(app.transform_offset_x_var.get()) == pytest.approx(40)
    assert float(app.transform_offset_y_var.get()) == pytest.approx(-80)

    app._preview_point_in_image = lambda _event: True
    assert app._change_preview_scale(SimpleNamespace(), 1) == "break"
    assert float(app.transform_scale_var.get()) == pytest.approx(2.2)
    assert float(app.transform_offset_x_var.get()) == pytest.approx(44)
    assert float(app.transform_offset_y_var.get()) == pytest.approx(-88)

    app.transform_rotation_var.set("180")
    app._on_transform_value_changed()
    assert float(app.transform_offset_x_var.get()) == pytest.approx(-88)
    assert float(app.transform_offset_y_var.get()) == pytest.approx(-44)

    app.transform_scale_var.set("")
    app._on_transform_value_changed()
    assert app._last_valid_transform_options.scale == pytest.approx(2.2)
    app.transform_scale_var.set("1")
    app._on_transform_value_changed()
    assert float(app.transform_offset_x_var.get()) == pytest.approx(-40)
    assert float(app.transform_offset_y_var.get()) == pytest.approx(-20)

    app._updating_transform_selection_fields = False
    app._selected_transform_blocks = {(0, 0)}
    app._reset_transform_state()
    assert app._last_valid_transform_options == TransformCutUiOptions(enabled=True)
    app._set_transform_control_values(rotation=90)
    assert app.transform_offset_x_var.get() == "0"
    assert app.transform_offset_y_var.get() == "0"


def test_ctrl_click_toggles_blocks_and_select_all() -> None:
    app = GuidecutApp.__new__(GuidecutApp)
    app.transform_cut_var = SimpleNamespace(get=lambda: True)
    app.transform_block_col_var = FakeVar("0")
    app.transform_block_row_var = FakeVar("0")
    app._selected_transform_blocks = {(0, 0)}
    app._updating_transform_selection_fields = False
    app._last_preview_display_box = (0, 0, 200, 200)
    app._last_preview_grid = (2, 2)
    app._preview_panel_visible = False
    app._preview_source_image = None
    app._current_transform_grid = lambda: (2, 2)

    app._select_transform_block_from_preview(SimpleNamespace(x=150, y=50, state=0))
    assert app._selected_transform_blocks == {(1, 0)}
    app._select_transform_block_from_preview(SimpleNamespace(x=50, y=150, state=0x0004))
    assert app._selected_transform_blocks == {(1, 0), (0, 1)}
    assert (app.transform_block_col_var.get(), app.transform_block_row_var.get()) == ("0", "1")
    app._select_transform_block_from_preview(SimpleNamespace(x=150, y=50, state=0x0004))
    assert app._selected_transform_blocks == {(0, 1)}
    app._select_transform_block_from_preview(SimpleNamespace(x=50, y=150, state=0x0004))
    assert app._selected_transform_blocks == set()

    app._select_all_transform_blocks()
    assert app._selected_transform_blocks == {(0, 0), (1, 0), (0, 1), (1, 1)}
    app.transform_block_col_var.set("1")
    app.transform_block_row_var.set("1")
    app._on_transform_block_fields_changed()
    assert app._selected_transform_blocks == {(1, 1)}
    app._current_transform_grid = lambda: (1, 1)
    app._clamp_transform_block_to_current_grid()
    assert app._selected_transform_blocks == {(0, 0)}
    app._on_preview_rotate_start(SimpleNamespace(x=50, y=50, state=0x0004))
    assert app._selected_transform_blocks == set()
    app._on_preview_control_middle_click(SimpleNamespace(x=50, y=50, state=0x0004))
    assert app._selected_transform_blocks == {(0, 0)}
