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
DEFAULT_TRANSFORM_OFFSET_X_PX = 0.0
DEFAULT_TRANSFORM_OFFSET_Y_PX = 0.0
DEFAULT_TRANSFORM_ROTATION_DEG = 0.0
DEFAULT_TRANSFORM_SCALE = 1.0
DEFAULT_TRANSFORM_BLOCK_COL = 0
DEFAULT_TRANSFORM_BLOCK_ROW = 0


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


@dataclass(frozen=True)
class TransformCutOptions:
    offset_x_px: float = DEFAULT_TRANSFORM_OFFSET_X_PX
    offset_y_px: float = DEFAULT_TRANSFORM_OFFSET_Y_PX
    rotation_deg: float = DEFAULT_TRANSFORM_ROTATION_DEG
    scale: float = DEFAULT_TRANSFORM_SCALE
    block_col: int = DEFAULT_TRANSFORM_BLOCK_COL
    block_row: int = DEFAULT_TRANSFORM_BLOCK_ROW


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


def selected_block_output_token(base_token: str, block_col: int, block_row: int) -> str:
    return f"{base_token}-block-{block_col}-{block_row}"


def selected_blocks_output_token(base_token: str, blocks: Sequence[tuple[int, int]]) -> str:
    unique_blocks = set(blocks)
    if not unique_blocks:
        raise ValueError("Select at least one block for transform cut.")
    if len(unique_blocks) == 1:
        return selected_block_output_token(base_token, *next(iter(unique_blocks)))
    return f"{base_token}-blocks-{len(unique_blocks)}"


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


def parse_transform_float(value: float | int | str, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number, got '{value}'.") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be a finite number, got {parsed}.")
    return parsed


def parse_transform_scale(value: float | int | str) -> float:
    parsed = parse_transform_float(value, "Transform scale")
    if parsed <= 0.0:
        raise ValueError(f"Transform scale must be greater than 0, got {parsed}.")
    return parsed


def parse_block_index(value: int | str, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer, got '{value}'.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer, got {parsed}.")
    return parsed


def parse_block_coordinate(value: str) -> tuple[int, int]:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError(f"Block must be COL,ROW with zero-based integers, got '{value}'.")
    return parse_block_index(parts[0], "Block column"), parse_block_index(parts[1], "Block row")


def validate_selected_block(block_col: int, block_row: int, cols: int, rows: int) -> None:
    if not (0 <= block_col < cols):
        raise ValueError(f"Selected block column must be in [0, {cols - 1}], got {block_col}.")
    if not (0 <= block_row < rows):
        raise ValueError(f"Selected block row must be in [0, {rows - 1}], got {block_row}.")


def ordered_selected_blocks(
    blocks: Iterable[tuple[int, int]], cols: int, rows: int
) -> list[tuple[int, int]]:
    selected = set(blocks)
    if not selected:
        raise ValueError("Select at least one block for transform cut.")
    for col, row in selected:
        validate_selected_block(col, row, cols, rows)
    return [block for block in ordered_tiles(cols, rows) if block in selected]


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or ("transparency" in image.info)


def render_transformed_source(image: Image.Image, options: TransformCutOptions) -> Image.Image:
    """Render the transformed source underneath a fixed guide-space canvas."""
    return render_transformed_tile(image, options, Rect(0, 0, image.width, image.height))


def render_transformed_tile(image: Image.Image, options: TransformCutOptions, tile: Rect) -> Image.Image:
    """Sample one guide block directly from the transformed source."""
    width_px, height_px = image.size
    if width_px <= 0 or height_px <= 0 or tile.x1 <= tile.x0 or tile.y1 <= tile.y0:
        raise ValueError("Image and tile dimensions must be positive.")
    if not math.isfinite(options.scale) or options.scale <= 0:
        raise ValueError("Transform scale must be finite and greater than 0.")

    angle = math.radians(options.rotation_deg)
    cosine = math.cos(angle) / options.scale
    sine = math.sin(angle) / options.scale
    center_x, center_y = width_px / 2.0, height_px / 2.0
    tile_origin_x = tile.x0 - center_x - options.offset_x_px
    tile_origin_y = tile.y0 - center_y - options.offset_y_px
    transform = (
        cosine,
        -sine,
        center_x + cosine * tile_origin_x - sine * tile_origin_y,
        sine,
        cosine,
        center_y + sine * tile_origin_x + cosine * tile_origin_y,
    )

    has_alpha = _has_alpha(image)
    page_mode = "RGBA" if image.mode == "RGBA" else _pdf_capable_mode(image.mode)
    source = image if image.mode in {"RGB", "RGBA", "L", "CMYK"} else image.convert("RGBA" if has_alpha else "RGB")
    if has_alpha:
        fill = (0, 0, 0, 0)
    elif source.mode == "L":
        fill = 255
    elif source.mode == "CMYK":
        fill = (0, 0, 0, 0)
    else:
        fill = (255, 255, 255)
    resample = Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC
    try:
        rendered = source.transform(
            (tile.x1 - tile.x0, tile.y1 - tile.y0),
            Image.Transform.AFFINE,
            transform,
            resample=resample,
            fillcolor=fill,
        )
    finally:
        if source is not image:
            source.close()

    if rendered.mode != page_mode:
        normalized = rendered.convert(page_mode)
        rendered.close()
        rendered = normalized
    rendered.info = dict(image.info)
    return rendered


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
    transform_options: TransformCutOptions | None = None,
) -> list[str]:
    if not ordered_rects:
        raise ValueError("No tile rectangles provided for export.")

    info = dict(image.info)
    page_mode = _pdf_capable_mode(image.mode)
    pages: list[Image.Image] = []
    warnings: list[str] = []

    try:
        for rect in ordered_rects:
            cropped = (
                render_transformed_tile(image, transform_options, rect)
                if transform_options is not None
                else image.crop(rect.box)
            )
            try:
                page = _normalize_for_pdf(cropped, page_mode)
            finally:
                if cropped.mode != page_mode:
                    cropped.close()
            pages.append(page)
    except Exception:
        for page in pages:
            page.close()
        raise

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
    parser.add_argument(
        "--transform-cut",
        action="store_true",
        help="Transform the source under a fixed guide grid and export selected blocks.",
    )
    parser.add_argument(
        "--transform-offset-x",
        type=float,
        default=DEFAULT_TRANSFORM_OFFSET_X_PX,
        help="Transform-cut horizontal source offset in pixels.",
    )
    parser.add_argument(
        "--transform-offset-y",
        type=float,
        default=DEFAULT_TRANSFORM_OFFSET_Y_PX,
        help="Transform-cut vertical source offset in pixels.",
    )
    parser.add_argument(
        "--transform-rotation-deg",
        type=float,
        default=DEFAULT_TRANSFORM_ROTATION_DEG,
        help="Transform-cut source rotation in degrees around the source center.",
    )
    parser.add_argument(
        "--transform-scale",
        type=float,
        default=DEFAULT_TRANSFORM_SCALE,
        help="Transform-cut uniform source zoom factor. Must be greater than 0.",
    )
    parser.add_argument(
        "--block-col",
        type=int,
        default=None,
        help="Transform-cut selected block column, zero-based from the left.",
    )
    parser.add_argument(
        "--block-row",
        type=int,
        default=None,
        help="Transform-cut selected block row, zero-based from the top.",
    )
    parser.add_argument(
        "--block",
        action="append",
        metavar="COL,ROW",
        help="Selected transform-cut block. Repeat to export multiple blocks in page order.",
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

    try:
        transform_options = TransformCutOptions(
            offset_x_px=parse_transform_float(args.transform_offset_x, "Transform offset X"),
            offset_y_px=parse_transform_float(args.transform_offset_y, "Transform offset Y"),
            rotation_deg=parse_transform_float(args.transform_rotation_deg, "Transform rotation"),
            scale=parse_transform_scale(args.transform_scale),
            block_col=parse_block_index(
                DEFAULT_TRANSFORM_BLOCK_COL if args.block_col is None else args.block_col,
                "Selected block column",
            ),
            block_row=parse_block_index(
                DEFAULT_TRANSFORM_BLOCK_ROW if args.block_row is None else args.block_row,
                "Selected block row",
            ),
        )
        if args.block and not args.transform_cut:
            raise ValueError("--block requires --transform-cut.")
        if args.block and (args.block_col is not None or args.block_row is not None):
            raise ValueError("Use either repeated --block or --block-col/--block-row, not both.")
        requested_blocks = (
            [parse_block_coordinate(value) for value in args.block]
            if args.block
            else [(transform_options.block_col, transform_options.block_row)]
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not input_path.exists() or not input_path.is_file():
        print(f"Input path does not exist or is not a file: {input_path}", file=sys.stderr)
        return 2

    output_token = (
        selected_blocks_output_token(grid_selection.output_token, requested_blocks)
        if args.transform_cut
        else grid_selection.output_token
    )
    output_path = args.output.expanduser().resolve() if args.output else build_output_path(input_path, output_token)
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

        if args.transform_cut:
            selected_indices = ordered_selected_blocks(requested_blocks, cols, rows)
            selected_rects = [
                compute_tile_crop(col, row, cols, rows, width_px, height_px)
                for col, row in selected_indices
            ]
            warnings.extend(
                export_tiles_to_multipage_pdf(
                    image=working_image,
                    ordered_rects=selected_rects,
                    output_path=output_path,
                    preserve_profile=True,
                    preserve_metadata=True,
                    transform_options=transform_options,
                )
            )
        else:
            warnings.extend(
                export_tiles_to_multipage_pdf(
                    image=working_image,
                    ordered_rects=rects,
                    output_path=output_path,
                    preserve_profile=True,
                    preserve_metadata=True,
                )
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
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
        if args.transform_cut:
            print(f"Grid: {cols}x{rows} ({cols * rows} selectable blocks)")
            print(
                "Transform cut: enabled "
                f"(offset={transform_options.offset_x_px:.2f},{transform_options.offset_y_px:.2f}px, "
                f"rotation={transform_options.rotation_deg:.2f}deg, "
                f"scale={transform_options.scale:.4g}, "
                f"blocks={','.join(f'{col}:{row}' for col, row in selected_indices)})"
            )
            print(f"Output pages: {len(selected_indices)}")
        else:
            print(f"Grid: {cols}x{rows} ({cols * rows} pages)")
            print("Transform cut: disabled")
        print(f"Vertical guides (px): {_format_int_list(v_guides)}")
        print(f"Horizontal guides (px): {_format_int_list(h_guides)}")
        print(f"Output PDF: {output_path}")
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
