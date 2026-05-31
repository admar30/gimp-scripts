#!/usr/bin/env python3
"""
ISO216 guideline cutter CLI.

Given an input file and target ISO216 size (a3/a2/a1/a0), split the input into
an A4-tile grid and export one multi-page PDF where each tile is one page.

Author: Adrian Mariani - 21-03-2026
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image


TARGET_SPLITS = {
    "a3": 1,
    "a2": 2,
    "a1": 3,
    "a0": 4,
}

ISO216_ASPECT_RATIO = math.sqrt(2.0)
DEFAULT_EXPAND_BIAS_PERCENT = 50.0
CUSTOM_GRID_MIN = 1
CUSTOM_GRID_MAX = 32


@dataclass(frozen=True)
class Rect:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class ExpandCrop:
    rect: Rect
    axis: str | None
    excess_px: int
    leading_trim_px: int
    trailing_trim_px: int
    bias_percent: float


@dataclass(frozen=True)
class GridSelection:
    mode: str
    target: str | None
    cols: int | None
    rows: int | None
    output_token: str


def parse_target_format(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in TARGET_SPLITS:
        allowed = ", ".join(sorted(TARGET_SPLITS))
        raise ValueError(f"Unsupported target format '{value}'. Use one of: {allowed}.")
    return normalized


def build_custom_grid_token(cols: int, rows: int) -> str:
    return f"grid-{cols}x{rows}"


def _parse_custom_grid_dimension(value: int | None, field_name: str) -> int:
    if value is None:
        raise ValueError(f"Missing required value for --{field_name}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"--{field_name} must be an integer.") from exc
    if not (CUSTOM_GRID_MIN <= parsed <= CUSTOM_GRID_MAX):
        raise ValueError(
            f"--{field_name} must be between {CUSTOM_GRID_MIN} and {CUSTOM_GRID_MAX} (got {parsed})."
        )
    return parsed


def resolve_grid_selection(
    target_format_value: str | None,
    grid_cols_value: int | None,
    grid_rows_value: int | None,
) -> GridSelection:
    target_text = (target_format_value or "").strip()
    has_target = bool(target_text)
    has_cols = grid_cols_value is not None
    has_rows = grid_rows_value is not None

    if has_target and (has_cols or has_rows):
        raise ValueError(
            "Preset target format and custom grid options are mutually exclusive. "
            "Choose either <target_format> or --grid-cols/--grid-rows."
        )

    if has_target:
        target = parse_target_format(target_text)
        return GridSelection(
            mode="preset",
            target=target,
            cols=None,
            rows=None,
            output_token=target,
        )

    if has_cols != has_rows:
        raise ValueError("Custom grid mode requires both --grid-cols and --grid-rows.")
    if has_cols and has_rows:
        cols = _parse_custom_grid_dimension(grid_cols_value, "grid-cols")
        rows = _parse_custom_grid_dimension(grid_rows_value, "grid-rows")
        return GridSelection(
            mode="custom",
            target=None,
            cols=cols,
            rows=rows,
            output_token=build_custom_grid_token(cols, rows),
        )

    raise ValueError(
        "No grid mode selected. Provide either <target_format> "
        "or both --grid-cols and --grid-rows."
    )


def detect_orientation(width_px: int, height_px: int) -> str:
    if width_px > height_px:
        return "landscape"
    if height_px > width_px:
        return "portrait"
    return "square"


def compute_grid(target: str, orientation: str) -> tuple[int, int]:
    splits = TARGET_SPLITS[target]
    cols = 1
    rows = 1
    axis = "x" if orientation == "landscape" else "y"
    for _ in range(splits):
        if axis == "x":
            cols *= 2
            axis = "y"
        else:
            rows *= 2
            axis = "x"
    return cols, rows


def _partition_edges(size_px: int, parts: int) -> list[int]:
    return [round(i * size_px / parts) for i in range(parts + 1)]


def compute_guides(width_px: int, height_px: int, cols: int, rows: int) -> tuple[list[int], list[int]]:
    vertical = [round(i * width_px / cols) for i in range(1, cols)]
    horizontal = [round(i * height_px / rows) for i in range(1, rows)]
    return vertical, horizontal


def compute_tile_crop(
    col_ltr: int,
    row_ttb: int,
    cols: int,
    rows: int,
    width_px: int,
    height_px: int,
) -> Rect:
    x_edges = _partition_edges(width_px, cols)
    y_edges = _partition_edges(height_px, rows)
    return Rect(
        x0=x_edges[col_ltr],
        y0=y_edges[row_ttb],
        x1=x_edges[col_ltr + 1],
        y1=y_edges[row_ttb + 1],
    )


def ordered_tiles(cols: int, rows: int) -> list[tuple[int, int]]:
    return [(col, row) for row in range(rows) for col in range(cols)]


def is_near_iso216_ratio(width_px: int, height_px: int, tolerance: float = 0.03) -> bool:
    if width_px <= 0 or height_px <= 0:
        return False
    ratio = max(width_px, height_px) / min(width_px, height_px)
    return abs(ratio - ISO216_ASPECT_RATIO) <= tolerance


def clamp_expand_bias_percent(value: float | int, default: float = DEFAULT_EXPAND_BIAS_PERCENT) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(0.0, min(100.0, parsed))


def parse_expand_bias_percent(value: float | int | str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expand bias percent must be a number in [0, 100], got '{value}'.") from exc
    if not (0.0 <= parsed <= 100.0):
        raise ValueError(f"Expand bias percent must be in [0, 100], got {parsed}.")
    return parsed


def _target_ratio_for_orientation(orientation: str) -> float:
    if orientation == "landscape":
        return ISO216_ASPECT_RATIO
    return 1.0 / ISO216_ASPECT_RATIO


def compute_expand_crop_rect(width_px: int, height_px: int, bias_percent: float | int) -> ExpandCrop:
    if width_px <= 0 or height_px <= 0:
        raise ValueError("Image dimensions must be positive.")

    orientation = detect_orientation(width_px, height_px)
    target_ratio = _target_ratio_for_orientation(orientation)
    bias = clamp_expand_bias_percent(bias_percent)
    source_ratio = width_px / height_px

    if is_near_iso216_ratio(width_px, height_px, tolerance=0.001):
        rect = Rect(0, 0, width_px, height_px)
        return ExpandCrop(
            rect=rect,
            axis=None,
            excess_px=0,
            leading_trim_px=0,
            trailing_trim_px=0,
            bias_percent=bias,
        )

    if math.isclose(source_ratio, target_ratio, rel_tol=0.0, abs_tol=1e-12):
        rect = Rect(0, 0, width_px, height_px)
        return ExpandCrop(
            rect=rect,
            axis=None,
            excess_px=0,
            leading_trim_px=0,
            trailing_trim_px=0,
            bias_percent=bias,
        )

    if source_ratio > target_ratio:
        # Too wide: trim horizontally.
        new_width = max(1, min(width_px, int(round(height_px * target_ratio))))
        excess = max(0, width_px - new_width)
        if excess <= 0:
            rect = Rect(0, 0, width_px, height_px)
            return ExpandCrop(
                rect=rect,
                axis=None,
                excess_px=0,
                leading_trim_px=0,
                trailing_trim_px=0,
                bias_percent=bias,
            )
        leading_trim = int(round(excess * (bias / 100.0)))
        leading_trim = max(0, min(excess, leading_trim))
        trailing_trim = excess - leading_trim
        x0 = leading_trim
        x1 = width_px - trailing_trim
        rect = Rect(x0, 0, x1, height_px)
        return ExpandCrop(
            rect=rect,
            axis="x",
            excess_px=excess,
            leading_trim_px=leading_trim,
            trailing_trim_px=trailing_trim,
            bias_percent=bias,
        )

    # Too tall: trim vertically.
    new_height = max(1, min(height_px, int(round(width_px / target_ratio))))
    excess = max(0, height_px - new_height)
    if excess <= 0:
        rect = Rect(0, 0, width_px, height_px)
        return ExpandCrop(
            rect=rect,
            axis=None,
            excess_px=0,
            leading_trim_px=0,
            trailing_trim_px=0,
            bias_percent=bias,
        )
    leading_trim = int(round(excess * (bias / 100.0)))
    leading_trim = max(0, min(excess, leading_trim))
    trailing_trim = excess - leading_trim
    y0 = leading_trim
    y1 = height_px - trailing_trim
    rect = Rect(0, y0, width_px, y1)
    return ExpandCrop(
        rect=rect,
        axis="y",
        excess_px=excess,
        leading_trim_px=leading_trim,
        trailing_trim_px=trailing_trim,
        bias_percent=bias,
    )


def build_output_path(input_path: Path, target_token: str, now_local: datetime | None = None) -> Path:
    now_local = now_local or datetime.now().astimezone()
    timestamp = now_local.strftime("%Y%m%d-%H%M%S")
    stem = input_path.stem
    base = input_path.with_name(f"{stem}-guidecut-{target_token}-{timestamp}.pdf")
    if not base.exists():
        return base

    suffix = 1
    while True:
        candidate = input_path.with_name(f"{stem}-guidecut-{target_token}-{timestamp}-{suffix}.pdf")
        if not candidate.exists():
            return candidate
        suffix += 1


def _pdf_capable_mode(mode: str) -> str:
    return mode if mode in {"1", "L", "RGB", "CMYK"} else "RGB"


def _normalize_for_pdf(image: Image.Image, mode: str) -> Image.Image:
    if image.mode == mode:
        return image
    return image.convert(mode)


def _metadata_warnings(info: dict) -> list[str]:
    warnings: list[str] = []
    # Pillow can preserve some metadata for PDF output, but not every source key.
    if info.get("exif"):
        warnings.append("EXIF metadata presence detected; PDF export may not preserve all EXIF fields.")
    if info.get("xmp"):
        warnings.append("XMP metadata presence detected; PDF export may not preserve all XMP fields.")
    return warnings


def _extract_pdf_metadata(info: dict) -> dict:
    metadata: dict = {}

    if "title" in info and info["title"]:
        metadata["title"] = str(info["title"])
    if "author" in info and info["author"]:
        metadata["author"] = str(info["author"])
    if "subject" in info and info["subject"]:
        metadata["subject"] = str(info["subject"])
    if "keywords" in info and info["keywords"]:
        metadata["keywords"] = str(info["keywords"])

    return metadata


def export_tiles_to_multipage_pdf(
    image: Image.Image,
    ordered_rects: Sequence[Rect],
    output_path: Path,
    preserve_profile: bool = True,
    preserve_metadata: bool = True,
) -> list[str]:
    if not ordered_rects:
        raise ValueError("No tile rectangles provided for export.")

    info = dict(image.info)
    page_mode = _pdf_capable_mode(image.mode)
    pages: list[Image.Image] = []
    warnings: list[str] = []

    for rect in ordered_rects:
        cropped = image.crop(rect.box)
        pages.append(_normalize_for_pdf(cropped, page_mode))

    dpi = info.get("dpi")
    resolution = None
    if isinstance(dpi, tuple) and len(dpi) == 2 and dpi[0] > 0 and dpi[1] > 0:
        resolution = float(dpi[0])

    save_kwargs = {
        "save_all": True,
        "append_images": pages[1:],
    }

    if resolution:
        save_kwargs["resolution"] = resolution

    if preserve_profile and info.get("icc_profile"):
        save_kwargs["icc_profile"] = info["icc_profile"]

    if preserve_metadata:
        save_kwargs.update(_extract_pdf_metadata(info))
        warnings.extend(_metadata_warnings(info))

    try:
        pages[0].save(output_path, "PDF", **save_kwargs)
    except TypeError as exc:
        # Some Pillow versions/plugins may reject specific kwargs (for example icc_profile).
        if "icc_profile" in save_kwargs:
            warnings.append(
                "Color profile could not be written by this Pillow build; exported without embedded ICC profile."
            )
            del save_kwargs["icc_profile"]
            pages[0].save(output_path, "PDF", **save_kwargs)
        else:
            raise RuntimeError(f"PDF export failed: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"PDF export failed: {exc}") from exc
    finally:
        for page in pages:
            page.close()

    return warnings


def _load_source_image(path: Path) -> Image.Image:
    try:
        src = Image.open(path)
    except (OSError, FileNotFoundError) as exc:
        raise RuntimeError(f"Unable to open input file: {exc}") from exc

    try:
        src.seek(0)
    except EOFError:
        pass

    # Materialize pixels up front so later crop operations are deterministic.
    src.load()
    return src


def _format_int_list(values: Iterable[int]) -> str:
    return ", ".join(str(v) for v in values) or "(none)"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Split an input image/page into ISO216 A4 tiles and export one "
            "multi-page PDF in top-to-bottom, left-to-right page order."
        )
    )
    parser.add_argument("input_path", type=Path, help="Path to source file.")
    parser.add_argument(
        "target_format",
        nargs="?",
        help="Optional preset target format: one of a3, a2, a1, a0.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output PDF path. Defaults to timestamped name beside source.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors.",
    )
    parser.add_argument(
        "--expand-to-format",
        action="store_true",
        help="Crop input to ISO216 aspect ratio before guide split.",
    )
    parser.add_argument(
        "--expand-bias-percent",
        type=float,
        default=DEFAULT_EXPAND_BIAS_PERCENT,
        help=(
            "Bias for expand crop in [0,100]. 0 keeps left/top content, "
            "100 keeps right/bottom content."
        ),
    )
    parser.add_argument(
        "--grid-cols",
        type=int,
        default=None,
        help=f"Custom grid columns ({CUSTOM_GRID_MIN}..{CUSTOM_GRID_MAX}). Requires --grid-rows.",
    )
    parser.add_argument(
        "--grid-rows",
        type=int,
        default=None,
        help=f"Custom grid rows ({CUSTOM_GRID_MIN}..{CUSTOM_GRID_MAX}). Requires --grid-cols.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path = args.input_path.expanduser().resolve()

    try:
        grid_selection = resolve_grid_selection(
            args.target_format,
            args.grid_cols,
            args.grid_rows,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        expand_bias_percent = parse_expand_bias_percent(args.expand_bias_percent)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not input_path.exists() or not input_path.is_file():
        print(f"Input path does not exist or is not a file: {input_path}", file=sys.stderr)
        return 2

    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else build_output_path(input_path, grid_selection.output_token)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        src = _load_source_image(input_path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        working_image = src
        working_image_owned = False
        original_width_px, original_height_px = src.size
        crop_info: ExpandCrop | None = None
        warnings: list[str] = []

        if args.expand_to_format:
            crop_info = compute_expand_crop_rect(original_width_px, original_height_px, expand_bias_percent)
            if crop_info.excess_px > 0:
                cropped = src.crop(crop_info.rect.box)
                # Preserve metadata/profile hints for export.
                cropped.info = dict(src.info)
                working_image = cropped
                working_image_owned = True

        width_px, height_px = working_image.size
        orientation = detect_orientation(width_px, height_px)
        if grid_selection.mode == "preset":
            assert grid_selection.target is not None
            cols, rows = compute_grid(grid_selection.target, orientation)
        else:
            assert grid_selection.cols is not None and grid_selection.rows is not None
            cols, rows = grid_selection.cols, grid_selection.rows
        v_guides, h_guides = compute_guides(width_px, height_px, cols, rows)

        if not args.expand_to_format and not is_near_iso216_ratio(width_px, height_px):
            warnings.append(
                "Source dimensions are non-ISO ratio; continuing with guide split based on source canvas."
            )

        tile_indices = ordered_tiles(cols, rows)
        rects = [
            compute_tile_crop(col, row, cols, rows, width_px, height_px)
            for col, row in tile_indices
        ]

        warnings.extend(
            export_tiles_to_multipage_pdf(
            image=working_image,
            ordered_rects=rects,
            output_path=output_path,
            preserve_profile=True,
            preserve_metadata=True,
        )
        )
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if "working_image_owned" in locals() and working_image_owned:
            working_image.close()
        src.close()

    if not args.quiet:
        print(f"Input: {input_path}")
        if grid_selection.mode == "preset":
            print(f"Target format: {grid_selection.target}")
        else:
            print(f"Target format: custom grid ({grid_selection.cols}x{grid_selection.rows})")
        if args.expand_to_format:
            if crop_info is None:
                print(f"Expand to format: enabled (bias={expand_bias_percent:.2f}%)")
            elif crop_info.excess_px <= 0:
                print(
                    f"Expand to format: enabled (bias={crop_info.bias_percent:.2f}%), "
                    "source already matches ISO ratio."
                )
            else:
                axis_label = "horizontal (left/right trim)" if crop_info.axis == "x" else "vertical (top/bottom trim)"
                print(
                    f"Expand to format: enabled (bias={crop_info.bias_percent:.2f}%), "
                    f"{axis_label}, trimmed {crop_info.excess_px}px."
                )
                print(
                    "Expanded crop: "
                    f"{crop_info.rect.x0},{crop_info.rect.y0} -> {crop_info.rect.x1},{crop_info.rect.y1} "
                    f"({original_width_px}x{original_height_px} -> {width_px}x{height_px})"
                )
        else:
            print("Expand to format: disabled")
        print(f"Orientation: {orientation}")
        print(f"Grid: {cols}x{rows} ({cols * rows} pages)")
        print(f"Vertical guides (px): {_format_int_list(v_guides)}")
        print(f"Horizontal guides (px): {_format_int_list(h_guides)}")
        print(f"Output PDF: {output_path}")
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
