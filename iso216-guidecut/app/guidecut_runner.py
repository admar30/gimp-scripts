#!/usr/bin/env python3
"""
Runner helpers for the ISO216 Guidecut UI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Callable, Sequence

MODULE_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = MODULE_ROOT / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

from iso216_guidecut import (
    clamp_expand_bias_percent as cli_clamp_expand_bias_percent,
    compute_expand_crop_rect,
    compute_grid,
    compute_guides,
    detect_orientation,
    parse_target_format,
)


SUPPORTED_FORMATS = ("a3", "a2", "a1", "a0")

FORMAT_DETAILS = {
    "a3": {"tiles": 2, "a4_multiple": 2},
    "a2": {"tiles": 4, "a4_multiple": 4},
    "a1": {"tiles": 8, "a4_multiple": 8},
    "a0": {"tiles": 16, "a4_multiple": 16},
}

DEFAULT_UI_STATE = {
    "target_format": "a2",
    "specify_output_dir": False,
    "output_dir": "",
    "input_dir": "",
    "window_geometry": "",
    "preview_split_ratio": 0.5,
    "expand_to_format": False,
    "expand_bias_percent": 50.0,
}

GUIDE_PRIMARY_CANDIDATES = (
    "#0F8F84",
    "#FFFFFF",
    "#111111",
    "#FFD54A",
    "#FF4D6D",
)
GUIDE_HALO_CANDIDATES = ("#111111", "#FFFFFF")
GUIDE_CONTRAST_HALO_THRESHOLD = 2.5


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = color.strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        raise ValueError(f"Invalid color value: {color}")
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _channel_linear(value: int) -> float:
        normalized = max(0.0, min(255.0, float(value))) / 255.0
        if normalized <= 0.04045:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    r_lin = _channel_linear(rgb[0])
    g_lin = _channel_linear(rgb[1])
    b_lin = _channel_linear(rgb[2])
    return (0.2126 * r_lin) + (0.7152 * g_lin) + (0.0722 * b_lin)


def contrast_ratio(l1: float, l2: float) -> float:
    a = max(0.0, min(1.0, float(l1)))
    b = max(0.0, min(1.0, float(l2)))
    light, dark = (a, b) if a >= b else (b, a)
    return (light + 0.05) / (dark + 0.05)


def sample_line_luminance(
    image,  # noqa: ANN001
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    step: int = 16,
    neighborhood_radius: int = 1,
    max_points: int = 128,
) -> list[float]:
    if image is None or not hasattr(image, "size"):
        return []

    width, height = image.size
    if width <= 0 or height <= 0:
        return []

    if image.mode != "RGB":
        rgb_image = image.convert("RGB")
    else:
        rgb_image = image

    pixels = rgb_image.load()
    if pixels is None:
        return []

    x0 = max(0, min(width - 1, int(x0)))
    x1 = max(0, min(width - 1, int(x1)))
    y0 = max(0, min(height - 1, int(y0)))
    y1 = max(0, min(height - 1, int(y1)))

    radius = max(0, int(neighborhood_radius))
    step_px = max(1, int(step))
    max_samples = max(1, int(max_points))

    dx = x1 - x0
    dy = y1 - y0
    line_len = max(abs(dx), abs(dy))
    if line_len == 0:
        sample_count = 1
    else:
        sample_count = max(2, (line_len // step_px) + 1)
        sample_count = min(sample_count, max_samples)

    samples: list[float] = []
    for index in range(sample_count):
        t = 0.0 if sample_count == 1 else index / (sample_count - 1)
        sample_x = int(round(x0 + (dx * t)))
        sample_y = int(round(y0 + (dy * t)))

        nx0 = max(0, sample_x - radius)
        nx1 = min(width - 1, sample_x + radius)
        ny0 = max(0, sample_y - radius)
        ny1 = min(height - 1, sample_y + radius)

        local_luminance: list[float] = []
        for ny in range(ny0, ny1 + 1):
            for nx in range(nx0, nx1 + 1):
                pixel = pixels[nx, ny]
                if isinstance(pixel, int):
                    rgb = (pixel, pixel, pixel)
                else:
                    rgb = tuple(pixel[:3])
                local_luminance.append(relative_luminance(rgb))

        if local_luminance:
            samples.append(float(median(local_luminance)))

    return samples


def choose_guide_style(samples: Sequence[float]) -> tuple[str, str | None]:
    default = (GUIDE_PRIMARY_CANDIDATES[0], None)
    if not samples:
        return default

    normalized_samples: list[float] = []
    for value in samples:
        try:
            normalized_samples.append(max(0.0, min(1.0, float(value))))
        except (TypeError, ValueError):
            continue
    if not normalized_samples:
        return default

    best_color = GUIDE_PRIMARY_CANDIDATES[0]
    best_score = -1.0
    for candidate in GUIDE_PRIMARY_CANDIDATES:
        candidate_luminance = relative_luminance(_hex_to_rgb(candidate))
        worst_contrast = min(contrast_ratio(candidate_luminance, sample) for sample in normalized_samples)
        if worst_contrast > best_score:
            best_score = worst_contrast
            best_color = candidate

    halo_color: str | None = None
    if best_score < GUIDE_CONTRAST_HALO_THRESHOLD:
        halo_best_score = -1.0
        for candidate in GUIDE_HALO_CANDIDATES:
            if candidate.lower() == best_color.lower():
                continue
            candidate_luminance = relative_luminance(_hex_to_rgb(candidate))
            worst_contrast = min(contrast_ratio(candidate_luminance, sample) for sample in normalized_samples)
            if worst_contrast > halo_best_score:
                halo_best_score = worst_contrast
                halo_color = candidate
    return best_color, halo_color


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
    expand_to_format: bool = False,
    expand_bias_percent: float | int = 50.0,
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
    if expand_to_format:
        bias = clamp_expand_bias_percent(expand_bias_percent)
        command.extend(["--expand-to-format", "--expand-bias-percent", f"{bias:.4g}"])
    return command


def retained_input_value_after_run(input_path: Path) -> str:
    return str(input_path.parent.resolve())


def _resolve_path_lenient(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def resolve_input_folder_from_field(input_path_value: str) -> Path:
    input_text = input_path_value.strip()
    if not input_text:
        raise ValueError("Input path is empty.")

    raw = Path(input_text).expanduser()
    candidate = _resolve_path_lenient(raw)

    if candidate.exists():
        return candidate if candidate.is_dir() else candidate.parent

    if input_text.endswith(("\\", "/")):
        return candidate
    if candidate.suffix:
        return candidate.parent
    return candidate


def resolve_existing_input_file(input_path_value: str) -> Path | None:
    input_text = input_path_value.strip()
    if not input_text:
        return None

    raw = Path(input_text).expanduser()
    candidate = _resolve_path_lenient(raw)
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def effective_preview_state(input_path_value: str, show_preview_requested: bool) -> tuple[bool, bool, Path | None]:
    file_path = resolve_existing_input_file(input_path_value)
    if file_path is None:
        return False, False, None
    return True, bool(show_preview_requested), file_path


def preview_guides_for_source(
    width_px: int,
    height_px: int,
    target_format: str,
) -> tuple[int, int, list[int], list[int]]:
    target = normalize_target_format(target_format)
    orientation = detect_orientation(width_px, height_px)
    cols, rows = compute_grid(target, orientation)
    vertical, horizontal = compute_guides(width_px, height_px, cols, rows)
    return cols, rows, vertical, horizontal


def clamp_expand_bias_percent(value, default: float | int = 50.0) -> float:  # noqa: ANN001
    return cli_clamp_expand_bias_percent(value, default=float(default))


def expand_excess_axis(width_px: int, height_px: int, bias_percent: float | int = 50.0) -> str | None:
    crop_info = compute_expand_crop_rect(width_px, height_px, bias_percent)
    return crop_info.axis


def expand_crop_for_source(width_px: int, height_px: int, bias_percent: float | int = 50.0):
    return compute_expand_crop_rect(width_px, height_px, clamp_expand_bias_percent(bias_percent))


def browse_initial_directory(input_path_value: str) -> str | None:
    if not input_path_value.strip():
        return None
    try:
        folder = resolve_input_folder_from_field(input_path_value)
    except ValueError:
        return None
    if folder.exists() and folder.is_dir():
        return str(folder)
    return None


def persisted_input_directory(input_path_value: str) -> str:
    input_text = input_path_value.strip()
    if not input_text:
        return ""
    try:
        return str(resolve_input_folder_from_field(input_text))
    except ValueError:
        return ""


def sanitize_window_geometry(value: str) -> str:
    geometry = value.strip()
    if not geometry:
        return ""
    # Accept "WxH+X+Y", "WxH-X+Y", etc. and "WxH" fallback.
    if re.fullmatch(r"\d+x\d+(?:[+-]\d+[+-]\d+)?", geometry):
        return geometry
    return ""


def sanitize_preview_split_ratio(value) -> float:  # noqa: ANN001
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return float(DEFAULT_UI_STATE["preview_split_ratio"])
    if not (0.2 <= ratio <= 3.0):
        return float(DEFAULT_UI_STATE["preview_split_ratio"])
    return ratio


def sanitize_expand_bias_percent(value) -> float:  # noqa: ANN001
    return clamp_expand_bias_percent(value, default=float(DEFAULT_UI_STATE["expand_bias_percent"]))


def _coerce_bool(value) -> bool:  # noqa: ANN001
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return False


def sanitize_ui_state(raw: dict | None) -> dict:
    state = dict(DEFAULT_UI_STATE)
    if not isinstance(raw, dict):
        return state

    target = raw.get("target_format", state["target_format"])
    try:
        state["target_format"] = normalize_target_format(str(target))
    except ValueError:
        state["target_format"] = DEFAULT_UI_STATE["target_format"]

    state["specify_output_dir"] = _coerce_bool(raw.get("specify_output_dir", state["specify_output_dir"]))
    output_dir = raw.get("output_dir", state["output_dir"])
    state["output_dir"] = str(output_dir).strip() if output_dir is not None else ""
    input_dir = raw.get("input_dir", state["input_dir"])
    state["input_dir"] = persisted_input_directory(str(input_dir) if input_dir is not None else "")
    window_geometry = raw.get("window_geometry", state["window_geometry"])
    state["window_geometry"] = sanitize_window_geometry(str(window_geometry) if window_geometry is not None else "")
    state["preview_split_ratio"] = sanitize_preview_split_ratio(raw.get("preview_split_ratio"))
    state["expand_to_format"] = _coerce_bool(raw.get("expand_to_format", state["expand_to_format"]))
    state["expand_bias_percent"] = sanitize_expand_bias_percent(raw.get("expand_bias_percent"))
    return state


def load_ui_state(state_path: Path) -> dict:
    if not state_path.exists():
        return dict(DEFAULT_UI_STATE)

    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Unable to read UI state file '{state_path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"UI state file is invalid JSON ('{state_path}'): {exc}") from exc

    return sanitize_ui_state(raw)


def save_ui_state(
    state_path: Path,
    *,
    target_format: str,
    specify_output_dir: bool,
    output_dir: str,
    input_dir: str = "",
    window_geometry: str = "",
    preview_split_ratio: float | int = 0.5,
    expand_to_format: bool = False,
    expand_bias_percent: float | int = 50.0,
) -> None:
    state = sanitize_ui_state(
        {
            "target_format": target_format,
            "specify_output_dir": specify_output_dir,
            "output_dir": output_dir,
            "input_dir": input_dir,
            "window_geometry": window_geometry,
            "preview_split_ratio": preview_split_ratio,
            "expand_to_format": expand_to_format,
            "expand_bias_percent": expand_bias_percent,
        }
    )
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to save UI state file '{state_path}': {exc}") from exc


def resolve_open_folder(input_path_value: str, explicit_enabled: bool, explicit_dir_value: str) -> Path:
    explicit_dir = explicit_dir_value.strip()
    if explicit_enabled and explicit_dir:
        return Path(explicit_dir).expanduser().resolve()

    if not input_path_value.strip():
        raise ValueError("No folder can be resolved. Provide an input file or explicit output directory.")

    return resolve_input_folder_from_field(input_path_value)


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
