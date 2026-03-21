# Cut Preview Contrast Adaptation Implementation Proposal

Date: 2026-03-21
Status: Proposed (for review)

## 1. Goal
Improve preview guideline visibility by dynamically choosing guide color based on local image content under each guide.

## 2. Proposed Rendering Strategy
Use a two-layer guide style:
1. Primary stroke: color selected from a contrast palette against sampled background pixels.
2. Fallback halo: thin opposing outline behind the primary stroke when contrast is marginal.

This preserves stable-looking guides while adapting to dark/light/mixed documents.

## 3. Sampling Model
For each guide line in preview-canvas coordinates:
- Sample points along the line at fixed intervals (`sample_step_px`, e.g. 16 px).
- For each point, sample a small neighborhood (e.g. 3x3) from the rendered preview bitmap.
- Compute relative luminance for each sample pixel.
- Aggregate luminance using median (more robust against spikes).

This yields a representative luminance profile per guide line.

## 4. Color Selection Algorithm
Candidate primary colors (ordered by brand preference):
- `#0F8F84` (current theme focus teal)
- `#FFFFFF`
- `#111111`
- `#FFD54A`
- `#FF4D6D`

For each candidate color:
- Compute WCAG contrast ratio against sampled luminance values.
- Score candidate by worst-case sampled contrast (maximin strategy).
- Select color with highest score.

Fallback halo rule:
- If selected color worst-case contrast < `2.5`, add halo.
- Halo color = black or white, whichever gives higher contrast to the same samples.
- Draw halo first (width 3), then primary line (width 1-2).

## 5. Integration Points
Current code target: `guidecut_ui.py`, method `_render_preview`.

Add helper functions (suggested location: `guidecut_runner.py` for testability):
- `relative_luminance(rgb: tuple[int, int, int]) -> float`
- `contrast_ratio(l1: float, l2: float) -> float`
- `sample_line_luminance(image: Image.Image, x0: int, y0: int, x1: int, y1: int, step: int = 16) -> list[float]`
- `choose_guide_style(samples: list[float]) -> tuple[str, str | None]` returns `(stroke_color, halo_color_or_none)`

UI flow update:
1. Render preview image to canvas.
2. For each guide line, obtain sampled luminance from rendered preview bitmap.
3. Choose style with `choose_guide_style`.
4. Draw optional halo then guide line.

## 6. Performance Guardrails
- Perform sampling on resized preview image (not full source image).
- Limit samples per line (e.g. max 128 points).
- Recompute on resize/target change only.
- For resize-triggered recompute, defer work until resize settles (user releases drag/hold-click); avoid recomputing on every intermediate mouse-move geometry event.
- Cache per-line chosen style for the current render frame if multiple redraw calls happen in quick succession.

## 7. Edge Cases
- Tiny preview dimensions: skip sampling and use default theme guide color.
- Uniform images (all dark/all light): color selection still deterministic.
- Highly noisy images: median aggregation + halo fallback stabilizes visibility.
- Transparency: sample from composited RGB preview image (already converted).

## 8. Test Plan
Add unit tests in `test_guidecut_runner.py` for helper functions:
1. Relative luminance monotonicity for black/gray/white.
2. Contrast ratio sanity checks (`black` vs `white` > `light gray` vs `white`).
3. Style selection picks light stroke on dark samples.
4. Style selection picks dark stroke on light samples.
5. Halo requested when all candidate contrasts are below threshold.

Add functional smoke test (logic-level):
- Given synthetic preview lines over dark and light backgrounds, chosen styles differ and stay non-empty.

## 9. Rollout Notes
- Keep current static color as fallback path.
- Gate new behavior behind a small internal flag in code for easy rollback if rendering artifacts appear.
