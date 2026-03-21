from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

from guidecut_runner import (
    build_command,
    build_output_pdf_path,
    normalize_target_format,
    open_folder,
    open_folder_command,
    resolve_open_folder,
    resolve_output_directory,
    run_command_streaming,
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
