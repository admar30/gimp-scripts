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


@dataclass(frozen=True)
class Rect:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


def parse_target_format(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in TARGET_SPLITS:
        allowed = ", ".join(sorted(TARGET_SPLITS))
        raise ValueError(f"Unsupported target format '{value}'. Use one of: {allowed}.")
    return normalized


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


def build_output_path(input_path: Path, target: str, now_local: datetime | None = None) -> Path:
    now_local = now_local or datetime.now().astimezone()
    timestamp = now_local.strftime("%Y%m%d-%H%M%S")
    stem = input_path.stem
    base = input_path.with_name(f"{stem}-guidecut-{target}-{timestamp}.pdf")
    if not base.exists():
        return base

    suffix = 1
    while True:
        candidate = input_path.with_name(f"{stem}-guidecut-{target}-{timestamp}-{suffix}.pdf")
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
    parser.add_argument("target_format", help="One of: a3, a2, a1, a0.")
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path = args.input_path.expanduser().resolve()

    try:
        target = parse_target_format(args.target_format)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not input_path.exists() or not input_path.is_file():
        print(f"Input path does not exist or is not a file: {input_path}", file=sys.stderr)
        return 2

    output_path = args.output.expanduser().resolve() if args.output else build_output_path(input_path, target)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        src = _load_source_image(input_path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        width_px, height_px = src.size
        orientation = detect_orientation(width_px, height_px)
        cols, rows = compute_grid(target, orientation)
        v_guides, h_guides = compute_guides(width_px, height_px, cols, rows)
        warnings: list[str] = []

        if not is_near_iso216_ratio(width_px, height_px):
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
            image=src,
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
        src.close()

    if not args.quiet:
        print(f"Input: {input_path}")
        print(f"Target format: {target}")
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
