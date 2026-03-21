from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

from guidecut_runner import (
    DEFAULT_UI_STATE,
    browse_initial_directory,
    build_command,
    build_output_pdf_path,
    load_ui_state,
    normalize_target_format,
    open_folder,
    open_folder_command,
    effective_preview_state,
    preview_guides_for_source,
    resolve_input_folder_from_field,
    resolve_existing_input_file,
    resolve_open_folder,
    resolve_output_directory,
    retained_input_value_after_run,
    run_command_streaming,
    save_ui_state,
    sanitize_preview_split_ratio,
    sanitize_ui_state,
    persisted_input_directory,
    sanitize_window_geometry,
    tooltip_text_for_format,
)


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
    )
    loaded = load_ui_state(state_path)
    assert loaded["target_format"] == "a1"
    assert loaded["specify_output_dir"] is True
    assert loaded["output_dir"] == "C:/out"
    assert loaded["input_dir"] == str(Path("C:/maps").resolve())
    assert loaded["window_geometry"] == "1280x720+80+90"
    assert loaded["preview_split_ratio"] == 0.75


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


def test_build_command_without_output() -> None:
    command = build_command(
        python_executable="python",
        script_path=Path("iso216_guidecut.py"),
        input_path=Path("C:/in/file.avif"),
        target_format="a3",
        output_path=None,
    )
    assert command == ["python", "iso216_guidecut.py", "C:\\in\\file.avif", "a3"]


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
