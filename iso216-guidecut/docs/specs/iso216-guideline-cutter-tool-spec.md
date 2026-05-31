# ISO216 Guideline Cutter Tool Specification

Status: Draft v1.2  
Date: 2026-05-31

## 1. Purpose
This tool takes an input document/image and a target ISO216 format (`a3`, `a2`, `a1`, or `a0`), computes guide positions that represent bisection cut lines, and exports all tiles into a single multi-page PDF intended for A4 printing and physical assembly.

The source file may have non-standard internal dimensions. The tool does not reject non-ISO dimensions and does not require a strict A-series aspect ratio.

## 2. References
- GIMP guide concept reference (optional backend context):
  - https://docs.gimp.org/2.10/en/gimp-concepts-image-guides.html
- GIMP guide creation functions (optional backend context):
  - https://docs.gimp.org/2.10/en/script-fu-guide-new.html
  - https://docs.gimp.org/2.10/en/script-fu-guide-new-percent.html
- GIMP slicing concept (optional backend context): https://docs.gimp.org/2.10/en/plug-in-guillotine.html
- ISO216 paper sizes: https://ms-kb.msd.unimelb.edu.au/print-room/file-preperation/understanding-paper-size

## 3. CLI Contract
### 3.1 Required Parameters
1. `input_path`
2. Exactly one grid mode:
- preset mode via `target_format`
- custom mode via `--grid-cols` + `--grid-rows`

### 3.2 Preset `target_format` Rules
- Accepted values: `a3`, `a2`, `a1`, `a0`
- Case-insensitive input is allowed (`A2` accepted, normalized to `a2`)
- Any other value must fail with a clear error message and non-zero exit code

### 3.2.1 Custom Grid Rules
- `--grid-cols` and `--grid-rows` are required together.
- Allowed integer range per dimension: `1..32`.
- Preset and custom modes are mutually exclusive.

### 3.3 Optional Expand-to-Format Parameters
- `--expand-to-format` (boolean flag)
- `--expand-bias-percent <0..100>` (float, default `50.0`)

Behavior:
- When expand mode is enabled, pre-crop source to ISO216 aspect ratio before guide/grid/tile math.
- Bias semantics:
  - `0%`: preserve left/top side content (trim accumulates on right/bottom).
  - `100%`: preserve right/bottom side content (trim accumulates on left/top).
  - `50%`: center trim split.
- If the source already matches ISO ratio (or no excess trim axis exists), no crop is applied.
- Expand args are ignored unless `--expand-to-format` is set.

### 3.4 Backend Requirement
- GIMP is not required.
- Default implementation backend is Pillow/Python.
- Optional future backends (including GIMP batch mode) must preserve the same CLI contract and output behavior.

## 4. Functional Requirements
### 4.1 High-Level Flow
1. Load source file via the selected image backend (default: Pillow).
2. If expand mode is enabled, compute and apply pre-crop rectangle to enforce ISO216 ratio.
3. Detect orientation from working dimensions (cropped dimensions when expand is enabled).
4. Resolve grid:
- preset mode: compute bisection grid from `target_format` and orientation.
- custom mode: use explicit `cols x rows`.
5. Compute vertical/horizontal guide positions at cut lines.
6. Generate tile crop rectangles from the guide grid.
7. Export all tiles into one multi-page PDF with deterministic page ordering.

### 4.1.1 Expand-to-Format Crop Math
- Determine working target ratio from source orientation:
  - landscape source: `sqrt(2):1`
  - portrait/square source: `1:sqrt(2)`
- Detect excess axis:
  - too wide -> trim on `x`
  - too tall -> trim on `y`
- Compute retained crop dimension that best matches target ratio.
- Split excess trim using `expand_bias_percent`.
- Apply the resulting crop rectangle before all grid/guide/page calculations.

### 4.2 Orientation Detection
Implement a dedicated function before guide placement:

`detect_orientation(width_px, height_px) -> "portrait" | "landscape" | "square"`

Rules:
- `width_px > height_px` -> `landscape`
- `height_px > width_px` -> `portrait`
- equal -> `square` (handled as `portrait` default behavior)

Orientation determines the first bisection axis for odd split counts.

### 4.3 Bisection and Grid Logic
Map target format to split count:
- `a3`: 1 split
- `a2`: 2 splits
- `a1`: 3 splits
- `a0`: 4 splits

Bisection rule:
- Repeatedly bisect by alternating axis each step.
- Start axis is the long axis:
  - `portrait`/`square`: split `y` first
  - `landscape`: split `x` first

This yields:

| Target | Portrait/Square Grid (cols x rows) | Landscape Grid (cols x rows) | Tile Count |
|---|---:|---:|---:|
| a3 | 1 x 2 | 2 x 1 | 2 |
| a2 | 2 x 2 | 2 x 2 | 4 |
| a1 | 2 x 4 | 4 x 2 | 8 |
| a0 | 4 x 4 | 4 x 4 | 16 |

Guide counts:
- Vertical guides = `cols - 1`
- Horizontal guides = `rows - 1`

Guide positions:
- Vertical guide `i` at `x = round(i * width_px / cols)`, `i = 1..cols-1`
- Horizontal guide `j` at `y = round(j * height_px / rows)`, `j = 1..rows-1`

### 4.4 Output Naming and Location
Create one output PDF beside the input file.

Preset naming:

`<input-stem>-guidecut-<target-format>-<YYYYMMDD-HHMMSS>.pdf`

Custom naming:

`<input-stem>-guidecut-grid-<cols>x<rows>-<YYYYMMDD-HHMMSS>.pdf`

Requirements:
- Datetime uses local system timezone.
- Datetime string must be filesystem-safe (no colons or spaces).

Page ordering:
- Pages are emitted in row-major order, top-to-bottom then left-to-right.

Example for `a2` (2x2) page sequence:
- page 1 -> top-left
- page 2 -> top-right
- page 3 -> bottom-left
- page 4 -> bottom-right

### 4.5 Export Requirements
- Export one multi-page PDF containing every tile as one page.
- Preserve color profile and metadata in export when the active backend/PDF path supports it.
- If full metadata preservation is not possible for a given input/export path, emit a warning but continue.

## 5. Validation and Error Handling
Hard failures (non-zero exit):
- Input path does not exist or is unreadable.
- Unsupported target format.
- Neither grid mode selected.
- Conflicting grid mode inputs (preset + custom together).
- Invalid custom-grid dimensions.
- Invalid `--expand-bias-percent` value (outside `[0,100]` or non-numeric).
- Output file path cannot be created/written.
- Export failure for any page or final combined PDF write.

Soft warnings (continue):
- Source dimensions are non-ISO ratio.
- Partial metadata preservation limits in export backend.

## 6. Suggested Internal Functions
1. `parse_target_format(value: str) -> str`
2. `detect_orientation(width_px: int, height_px: int) -> str`
3. `compute_grid(target: str, orientation: str) -> (cols: int, rows: int)`
4. `compute_guides(width_px: int, height_px: int, cols: int, rows: int) -> (v_guides, h_guides)`
5. `compute_tile_crop(col_ltr: int, row_ttb: int, cols: int, rows: int, width_px: int, height_px: int) -> Rect`
6. `ordered_tiles(cols: int, rows: int) -> list[(col_ltr, row_ttb)]`  (row-major: top-to-bottom, left-to-right)
7. `clamp_expand_bias_percent(value: float|int, default=50.0) -> float`
8. `parse_expand_bias_percent(value) -> float`
9. `compute_expand_crop_rect(width_px: int, height_px: int, bias_percent: float|int) -> ExpandCrop`
10. `resolve_grid_selection(target_format, grid_cols, grid_rows) -> GridSelection`
11. `build_output_path(input_path: str, target_token: str, now_local: datetime) -> output_pdf_path`
12. `export_tiles_to_multipage_pdf(image, ordered_rects, output_path, preserve_profile=True, preserve_metadata=True) -> None`

## 7. Non-Functional Requirements
- Deterministic output naming and page ordering.
- Repeatable geometry for same input/target and timestamp.
- Clear, concise log output suitable for CLI use.
- No destructive modification of the original input file.

## 8. Acceptance Criteria
1. Given a valid input and target `a3|a2|a1|a0`, the tool creates one output PDF.
2. Output PDF name matches `<input-stem>-guidecut-<target-format>-<YYYYMMDD-HHMMSS>.pdf`.
3. PDF page count equals expected tile count and follows top-to-bottom, left-to-right order.
4. Guides are created at the expected bisection positions.
5. Orientation detection changes split axis selection correctly for odd split counts (`a3`, `a1`).
6. Color profile and metadata are preserved when supported; warnings are logged otherwise.
7. When expand mode is enabled, crop occurs before guide/grid computation and output geometry reflects cropped dimensions.
8. Expand bias endpoints are correct (`0%` left/top anchored, `100%` right/bottom anchored).
9. Custom grid mode produces exactly `cols*rows` pages and guide counts (`cols-1`, `rows-1`).

## 9. Test Plan
### 9.1 Unit Tests
- Target parsing and normalization
- Orientation detection
- Grid generation by target + orientation
- Guide position math
- Page ordering generation (row-major: top-to-bottom, left-to-right)
- Filesystem-safe output filename generation
- Expand crop rectangle math for too-wide/too-tall sources
- Expand bias endpoint and clamping behavior (`0`, `50`, `100`)
- Expand no-op behavior for already ISO-ratio sources
- Custom grid mode selection/validation and conflict handling
- Custom output token naming (`grid-CxR`)

### 9.2 Integration Tests
- One fixture each for `a3`, `a2`, `a1`, `a0`
- Portrait and landscape fixtures
- Verify PDF page count, page order, and bounding geometry
- Verify output PDF location (beside source)
- Verify metadata/profile preservation path on supported sample files
- Verify expand-on run uses cropped working geometry for tile/page boundaries
- Verify expand-off run behavior remains unchanged from baseline

### 9.3 Regression Tests
- Timestamp format remains filesystem-safe
- Page order remains top-to-bottom, left-to-right across all targets
- Non-ISO source dimensions still process without hard failure
- Expand arguments are only applied when `--expand-to-format` is explicitly enabled
