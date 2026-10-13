# ISO216 Guideline Cutter Tool Specification

Status: Draft v1.4
Date: 2026-10-10

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

### 3.3 Optional Conform to Layout Parameters
- `--conform-to-layout` (boolean flag)
- `--conform-bias-percent <0..100>` (float, default `50.0`)
- Legacy aliases: `--expand-to-format` and `--expand-bias-percent`, using the same layout-aware behaviour.

Behavior:
- When conformity is enabled, resolve a Fill frame matching the selected layout before guide/grid/tile math.
- Presets preserve the existing ISO216 canvas ratio. Custom grids choose portrait or landscape A4-shaped tiles to maximize retained source area; ties choose portrait and grid counts remain unchanged.
- Bias semantics:
  - `0%`: preserve left/top side content (trim accumulates on right/bottom).
  - `100%`: preserve right/bottom side content (trim accumulates on left/top).
  - `50%`: center trim split.
- If the source already matches the selected layout ratio (or pixel rounding yields no excess), no trim is applied.
- Conform args are ignored unless `--conform-to-layout` is set.

### 3.3.1 Optional Transform-Cut Parameters
- `--transform-cut` (boolean flag)
- `--transform-offset-x <pixels>` (float, default `0.0`)
- `--transform-offset-y <pixels>` (float, default `0.0`)
- `--transform-rotation-deg <degrees>` (float, default `0.0`)
- `--transform-scale <factor>` (float, default `1.0`, must be greater than `0`)
- `--block-col <int>` (zero-based selected block column, default `0`)
- `--block-row <int>` (zero-based selected block row, default `0`)
- `--block <col,row>` (repeatable zero-based selected block coordinate; cannot be mixed with `--block-col` / `--block-row`)

Behavior:
- Guides/grid remain a fixed cutting frame.
- The source image is transformed underneath that fixed frame.
- Transform origin is the bias-selected Fill frame centre, or the source centre when conformity is off.
- The desktop UI compensates `offset-x`/`offset-y` during rotation and scaling so the source point under the fixed preview centre remains stationary.
- `offset-x` and `offset-y` pan the transformed image in guide-space pixels.
- `rotation-deg` rotates the source in the 2D plane.
- `scale` is uniform image zoom.
- When enabled, export all selected blocks as pages of one PDF. A single selected block produces one page.
- Sort selected blocks top-to-bottom then left-to-right and ignore duplicate coordinates.
- If any selected block is outside the resolved grid, fail with a clear error. An empty selection is invalid.
- Transform mode is compatible with preset grids, custom grids, and conformity. Retain the full source and sample it through the Fill frame, allowing trimmed pixels to be panned back into view. Default transforms match ordinary Fill output.

### 3.4 Backend Requirement
- GIMP is not required.
- Default implementation backend is Pillow/Python.
- Optional future backends (including GIMP batch mode) must preserve the same CLI contract and output behavior.

## 4. Functional Requirements
### 4.1 High-Level Flow
1. Load the first source frame via the selected image backend (default: Pillow) and normalize EXIF orientation.
2. Resolve the layout, choosing auto A4 tile orientation for conformed custom grids.
3. Compute the bias-positioned Fill frame, retaining the complete source bitmap.
4. Resolve grid:
- preset mode: compute bisection grid from `target_format` and orientation.
- custom mode: use explicit `cols x rows`.
5. Compute vertical/horizontal guide positions at cut lines.
6. Generate tile crop rectangles from the guide grid.
7. If transform-cut mode is disabled, export all tiles into one multi-page PDF with deterministic page ordering.
8. If transform-cut mode is enabled, render each selected block from the transformed source underneath the fixed guide frame and export those pages in row-major order.

### 4.1.1 Conform to Layout Crop Math
- Determine working target ratio from source orientation:
  - landscape source: `sqrt(2):1`
  - portrait/square source: `1:sqrt(2)`
- For custom grids, evaluate `(cols / rows) / sqrt(2)` and `(cols / rows) * sqrt(2)` instead. Retained area fraction for source ratio `S` and target ratio `R` is `min(S/R, R/S)`; choose the higher score and portrait for ties within `1e-12`.
- Auto orientation does not depend on bias, pan, rotation or scale.
- Detect excess axis:
  - too wide -> trim on `x`
  - too tall -> trim on `y`
- Compute retained crop dimension that best matches target ratio.
- Split excess trim using `conform_bias_percent`.
- Use the resulting frame dimensions for all grid/guide/page calculations. Sample tiles from the full source; never pre-trim pixels needed by transforms.

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

Transform-cut naming:

`<input-stem>-guidecut-<target-or-grid-token>-block-<col>-<row>-<YYYYMMDD-HHMMSS>.pdf`

For multiple selected blocks:

`<input-stem>-guidecut-<target-or-grid-token>-blocks-<count>-<YYYYMMDD-HHMMSS>.pdf`

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
- In transform-cut mode, export one PDF page per selected block, in row-major order.
- Preserve color profile and metadata in export when the active backend/PDF path supports it.
- If full metadata preservation is not possible for a given input/export path, emit a warning but continue.

## 5. Validation and Error Handling
Hard failures (non-zero exit):
- Input path does not exist or is unreadable.
- Unsupported target format.
- Neither grid mode selected.
- Conflicting grid mode inputs (preset + custom together).
- Invalid custom-grid dimensions.
- Cutting frame too small to provide at least one pixel in each grid cell.
- Invalid `--conform-bias-percent` value (outside `[0,100]` or non-numeric).
- Invalid transform numeric value.
- Invalid selected transform block coordinate for resolved grid.
- Mixing repeated `--block` with legacy `--block-col` / `--block-row`.
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
7. `clamp_conform_bias_percent(value: float|int, default=50.0) -> float`
8. `parse_conform_bias_percent(value) -> float`
9. `compute_fill_crop_rect(width_px, height_px, target_ratio, bias_percent) -> FillCrop`
10. `resolve_grid_selection(target_format, grid_cols, grid_rows) -> GridSelection`
11. `build_output_path(input_path: str, target_token: str, now_local: datetime) -> output_pdf_path`
12. `export_tiles_to_multipage_pdf(image, ordered_rects, output_path, preserve_profile=True, preserve_metadata=True, transform_options=None) -> None`
13. `parse_transform_scale(value) -> float`
14. `validate_selected_block(block_col, block_row, cols, rows) -> None`
15. `render_transformed_source(image, transform_options) -> Image`
16. `selected_block_output_token(base_token, block_col, block_row) -> str`
17. `ordered_selected_blocks(blocks, cols, rows) -> list[(col, row)]`
18. `selected_blocks_output_token(base_token, blocks) -> str`
19. `resolve_layout_geometry(width_px, height_px, selection, conform_to_layout=False, bias_percent=50) -> LayoutGeometry`

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
7. When conformity is enabled, frame resolution occurs before guide/grid computation and output geometry reflects frame dimensions.
8. Fill bias endpoints are correct (`0%` left/top anchored, `100%` right/bottom anchored).
9. Custom grid mode produces exactly `cols*rows` pages and guide counts (`cols-1`, `rows-1`).
10. Transform-cut mode exports exactly one page per selected block in row-major order.
11. Single-block names include `block-<col>-<row>`; multi-block names include `blocks-<count>`.
12. Transform-cut mode leaves default multi-page output unchanged when disabled.
13. Conformed custom grids choose auto tile orientation maximizing retained content and retain the entered grid counts.
14. Transform Cut can recover pixels outside the initial Fill frame by panning; preview and exported pages share the same geometry.

## 9. Test Plan
### 9.1 Unit Tests
- Target parsing and normalization
- Orientation detection
- Grid generation by target + orientation
- Guide position math
- Page ordering generation (row-major: top-to-bottom, left-to-right)
- Filesystem-safe output filename generation
- Fill frame rectangle math for too-wide/too-tall sources
- Fill bias endpoint and clamping behavior (`0`, `50`, `100`)
- Fill no-op behaviour for matched preset/custom layouts
- Custom grid mode selection/validation and conflict handling
- Custom output token naming (`grid-CxR`)
- Transform-cut numeric parsing, output token naming, and selected block validation
- Multi-block parsing, deduplication, and row-major ordering
- Transform renderer keeps output canvas dimensions stable

### 9.2 Integration Tests
- One fixture each for `a3`, `a2`, `a1`, `a0`
- Portrait and landscape fixtures
- Verify PDF page count, page order, and bounding geometry
- Verify output PDF location (beside source)
- Verify metadata/profile preservation path on supported sample files
- Verify conformity-on run uses Fill frame dimensions for tile/page boundaries while retaining the full source
- Verify conformity-off run behavior remains unchanged from baseline
- Verify transform-cut run exports one page per selected block in row-major order
- Verify transform-cut invalid block coordinate fails

### 9.3 Regression Tests
- Timestamp format remains filesystem-safe
- Page order remains top-to-bottom, left-to-right across all targets
- Non-ISO source dimensions still process without hard failure
- Conformity arguments are only applied when `--conform-to-layout` is explicitly enabled
