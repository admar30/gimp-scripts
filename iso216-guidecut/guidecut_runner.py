#!/usr/bin/env python3
"""
Runner helpers for the ISO216 Guidecut UI.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from iso216_guidecut import parse_target_format


SUPPORTED_FORMATS = ("a3", "a2", "a1", "a0")

FORMAT_DETAILS = {
    "a3": {"tiles": 2, "a4_multiple": 2},
    "a2": {"tiles": 4, "a4_multiple": 4},
    "a1": {"tiles": 8, "a4_multiple": 8},
    "a0": {"tiles": 16, "a4_multiple": 16},
}


def normalize_target_format(value: str) -> str:
    return parse_target_format(value)


def tooltip_text_for_format(value: str) -> str:
    target = normalize_target_format(value)
    details = FORMAT_DETAILS[target]
    return (
        f"{target.upper()}\n"
        f"Tiles/pages: {details['tiles']}\n"
        f"Sheet size: {details['a4_multiple']}x A4"
    )


def resolve_output_directory(input_path: Path, explicit_enabled: bool, explicit_dir_value: str) -> Path:
    if explicit_enabled and explicit_dir_value.strip():
        return Path(explicit_dir_value.strip()).expanduser().resolve()
    return input_path.parent.resolve()


def build_output_pdf_path(
    input_path: Path,
    target_format: str,
    output_dir: Path,
    now_local: datetime | None = None,
) -> Path:
    target = normalize_target_format(target_format)
    now_local = now_local or datetime.now().astimezone()
    timestamp = now_local.strftime("%Y%m%d-%H%M%S")
    stem = input_path.stem

    base = output_dir / f"{stem}-guidecut-{target}-{timestamp}.pdf"
    if not base.exists():
        return base

    suffix = 1
    while True:
        candidate = output_dir / f"{stem}-guidecut-{target}-{timestamp}-{suffix}.pdf"
        if not candidate.exists():
            return candidate
        suffix += 1


def build_command(
    python_executable: str,
    script_path: Path,
    input_path: Path,
    target_format: str,
    output_path: Path | None = None,
) -> list[str]:
    target = normalize_target_format(target_format)
    command = [
        python_executable,
        str(script_path),
        str(input_path),
        target,
    ]
    if output_path is not None:
        command.extend(["--output", str(output_path)])
    return command


def resolve_open_folder(input_path_value: str, explicit_enabled: bool, explicit_dir_value: str) -> Path:
    explicit_dir = explicit_dir_value.strip()
    if explicit_enabled and explicit_dir:
        return Path(explicit_dir).expanduser().resolve()

    input_text = input_path_value.strip()
    if not input_text:
        raise ValueError("No folder can be resolved. Provide an input file or explicit output directory.")

    return Path(input_text).expanduser().resolve().parent


def open_folder_command(folder: Path, platform_name: str | None = None) -> list[str]:
    platform_name = platform_name or sys.platform
    if platform_name.startswith("win"):
        return ["explorer", str(folder)]
    if platform_name == "darwin":
        return ["open", str(folder)]
    return ["xdg-open", str(folder)]


def open_folder(folder: Path, platform_name: str | None = None) -> list[str]:
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Folder does not exist: {folder}")
    command = open_folder_command(folder, platform_name=platform_name)
    subprocess.Popen(command)  # noqa: S603
    return command


def _pump_stream(stream, callback: Callable[[str], None]) -> None:
    for line in iter(stream.readline, ""):
        text = line.rstrip("\r\n")
        if text:
            callback(text)
    stream.close()


def run_command_streaming(
    command: Sequence[str],
    cwd: Path,
    on_stdout: Callable[[str], None],
    on_stderr: Callable[[str], None],
) -> int:
    try:
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )  # noqa: S603
    except OSError as exc:
        raise RuntimeError(f"Failed to launch process: {exc}") from exc

    stdout_thread = threading.Thread(
        target=_pump_stream,
        args=(process.stdout, on_stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_pump_stream,
        args=(process.stderr, on_stderr),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    exit_code = process.wait()
    stdout_thread.join()
    stderr_thread.join()
    return exit_code
