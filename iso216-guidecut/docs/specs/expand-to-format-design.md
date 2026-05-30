# Guidecut Expand-to-Format Design

Status: Draft v0.1  
Date: 2026-05-30

## 1. Purpose
Add an optional "Expand to Format" mode that crops non-ISO-ratio source files to ISO216 aspect ratio before guide generation/export.

This solves cases where input files include dead space and users want control over which edge loses more content.

## 2. User-Facing Requirements
1. Add a new UI toggle: `Expand to Format`.
2. When enabled, crop source area to ISO216 ratio before guide/tile generation.
3. Cropping bias is controlled by a hidden slider:
- default `50%` (center crop),
- adjustable from one side to the opposite side on the excess axis.
4. When disabled, behavior returns to current default (no pre-crop).
5. In preview mode, user can drag the preview image along the excess axis:
- dragging updates crop bias,
- slider and preview remain synchronized.

## 3. Terminology
1. **Expand to Format**: UI label only. Implementation is a pre-crop to ISO ratio (no canvas extension).
2. **Excess axis**: axis trimmed to reach target ISO ratio.
3. **Bias percent**: percent of total trim removed from the "leading" edge:
- horizontal trim: leading edge = left,
- vertical trim: leading edge = top.

## 4. Target Ratio Rules
ISO216 uses a long-side/short-side ratio of `sqrt(2)`.

For a source image `(width, height)`:
1. Preserve detected orientation (landscape/portrait/square).
2. Compute target width/height ratio for that orientation:
- landscape: `target_ratio = sqrt(2)` (`width / height`),
- portrait/square: `target_ratio = 1 / sqrt(2)`.
3. Crop only one axis to satisfy the ratio:
- if source is too wide, trim width,
- if source is too tall, trim height.

## 5. Crop Geometry
Given:
- source size `(W, H)`,
- target ratio `R = target_width / target_height`,
- bias `P` in `[0, 100]`.

### 5.1 Determine retained dimensions
1. If `W / H > R` (too wide):
- `new_h = H`
- `new_w = round(H * R)`
- `excess = W - new_w` (horizontal trim)
2. Else if `W / H < R` (too tall):
- `new_w = W`
- `new_h = round(W / R)`
- `excess = H - new_h` (vertical trim)
3. Else:
- already matching ratio, `excess = 0`, no-op crop.

### 5.2 Bias to crop edges
1. `leading_trim = round(excess * (P / 100.0))`
2. `trailing_trim = excess - leading_trim`

Crop rectangle:
1. Horizontal trim:
- `x0 = leading_trim`, `x1 = W - trailing_trim`, `y0 = 0`, `y1 = H`
2. Vertical trim:
- `x0 = 0`, `x1 = W`, `y0 = leading_trim`, `y1 = H - trailing_trim`

Default `P = 50` yields centered crop.

## 6. CLI Contract Changes
File: `iso216-guidecut/cli/iso216_guidecut.py`

Add optional args:
1. `--expand-to-format` (flag)
2. `--expand-bias-percent <float>` (default `50.0`)

Rules:
1. If `--expand-to-format` is not set, ignore bias and keep current behavior.
2. Validate bias range `[0, 100]`; out-of-range is a clear non-zero error.
3. If enabled:
- compute crop rect,
- crop working image before grid/guides/tile computation,
- run existing guide/tile flow on cropped image.

Logging:
1. Emit crop summary in non-quiet mode:
- axis trimmed,
- original size,
- cropped size,
- bias percent.

## 7. App/Runner Contract Changes
File: `iso216-guidecut/app/guidecut_runner.py`

### 7.1 Build command support
Extend `build_command(...)` with:
1. `expand_to_format: bool = False`
2. `expand_bias_percent: float = 50.0`

When enabled, append:
```text
--expand-to-format --expand-bias-percent <value>
```

### 7.2 Shared crop math helpers
Add pure helpers for UI + tests:
1. `compute_expand_crop_rect(width_px, height_px, bias_percent) -> RectLike`
2. `expand_excess_axis(width_px, height_px) -> "x" | "y" | None`
3. `clamp_expand_bias(value) -> float`

These helpers let preview and CLI share identical geometry behavior.

### 7.3 Persisted UI state additions
Extend `DEFAULT_UI_STATE` and sanitize/load/save:
1. `expand_to_format: bool` (default `False`)
2. `expand_bias_percent: float` (default `50.0`)

## 8. UI Changes
File: `iso216-guidecut/app/guidecut_ui.py`

## 8.1 New controls
1. Add `Expand to Format` toggle.
2. Add hidden slider row shown only when toggle is enabled.
3. Slider range `0..100`, default `50`.
4. Slider label should describe active trim axis when known:
- horizontal trim: `Left/Right Trim`
- vertical trim: `Top/Bottom Trim`

## 8.2 Behavior
1. Toggle off:
- hide slider,
- use uncropped source for run + preview.
2. Toggle on:
- show slider,
- crop applies to run + preview.
3. If input is missing/invalid:
- keep slider hidden or disabled to avoid ambiguous state.
4. If no excess exists for selected source:
- slider disabled (or remains visible with note: "No trim needed").

## 8.3 Run integration
`_resolve_run_inputs` and command construction pass new options into `build_command`.

## 9. Preview Integration
File: `iso216-guidecut/app/guidecut_ui.py`

## 9.1 Render model
When expand mode is on:
1. Compute crop rect on source pixels using shared helper.
2. Preview should represent the cropped result area.
3. Guide overlay uses cropped dimensions (not original source dimensions).

## 9.2 Drag-to-adjust behavior
Drag only when:
1. preview visible,
2. expand mode enabled,
3. source loaded,
4. excess axis exists.

Bindings on preview canvas:
1. `<ButtonPress-1>`: start drag (capture start bias and pointer position)
2. `<B1-Motion>`: update bias continuously
3. `<ButtonRelease-1>`: finalize bias

Mapping:
1. Convert pointer delta in preview pixels to source-pixel offset using current preview scale.
2. Clamp effective leading trim to `[0, excess]`.
3. Convert back to bias percent:
- `bias = (leading_trim / excess) * 100`.
4. Update slider variable from drag and re-render preview.

Direction conventions:
1. Horizontal trim: dragging image right increases left trim.
2. Vertical trim: dragging image down increases top trim.

## 9.3 Slider/drag synchronization
1. Slider change updates preview crop immediately.
2. Drag updates slider live.
3. Keep one source of truth: `expand_bias_percent`.

## 10. Reliability and Performance
1. Reuse existing preview debounce pattern where possible.
2. Recompute crop geometry cheaply (pure math only).
3. Avoid blocking UI thread with heavy image operations outside existing preview flow.
4. Preserve existing preview contrast behavior after crop mapping.

## 11. Edge Cases
1. Already ISO-ratio image:
- no excess trim; crop is full image.
2. Very small images:
- ensure computed retained dimensions remain >= 1 pixel.
3. Bias endpoints:
- `0%`: all trim from trailing edge,
- `100%`: all trim from leading edge.
4. Square images:
- treat as portrait orientation baseline for target ratio selection.
5. Expand toggle on + preview off:
- feature still applies to run output.

## 12. Test Plan
## 12.1 CLI/unit tests (`tests/test_iso216_guidecut.py`)
1. Crop rect math for:
- too wide source,
- too tall source,
- near-ratio/no-op.
2. Bias mapping:
- 0, 50, 100 endpoints.
3. Grid/tile count unchanged by expand flag for same target format.
4. Exported page dimensions reflect cropped working canvas.

## 12.2 Runner tests (`tests/test_guidecut_runner.py`)
1. `build_command` includes expand args only when enabled.
2. Bias sanitization/clamping.
3. UI state save/load roundtrip includes expand settings.

## 12.3 UI smoke coverage
1. Toggle visibility and slider hide/show.
2. Slider affects preview crop.
3. Drag affects slider value and preview crop.
4. Toggle off resets to uncropped preview/rendering behavior.

## 13. Implementation Sequence
1. Add crop math + CLI args in `cli/iso216_guidecut.py`.
2. Add shared runner helpers and command/state support in `app/guidecut_runner.py`.
3. Add UI toggle + slider and run integration in `app/guidecut_ui.py`.
4. Add preview crop render + drag interaction in `app/guidecut_ui.py`.
5. Add/adjust tests.
6. Update `iso216-guidecut/README.md` and relevant specs with final user-facing behavior.

## 14. Out of Scope (This Pass)
1. Rotation/orientation override controls.
2. Multi-page source document independent trim per page.
3. Arbitrary custom target aspect ratios beyond ISO216.
