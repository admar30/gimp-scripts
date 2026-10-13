# Guidecut Conform to Layout Design

Status: Implemented

Date: 2026-10-13

This document replaces the original Expand to Format design. Its filename is retained so existing references continue to resolve.

## 1. Scope

One `Conform to Layout` toggle provides Fill for preset formats and custom grids. Fill trims the selected cutting frame without stretching the source. Fit/padding and manual tile-orientation overrides are deferred. This pass covers the Python CLI and desktop UI.

## 2. Layout Resolution

Resolve geometry from the original source dimensions after EXIF orientation normalization.

Preset targets preserve the existing canvas ratio and alternating bisection rules:
- Landscape source: canvas ratio `sqrt(2)`.
- Portrait/square source: canvas ratio `1/sqrt(2)`.
- Retain the existing near-ISO ratio tolerance for preset inputs.

For a custom grid `C x R`, evaluate:
- Portrait A4-shaped tiles: layout ratio `(C/R)/sqrt(2)`.
- Landscape A4-shaped tiles: layout ratio `(C/R)*sqrt(2)`.

For source ratio `S` and candidate ratio `T`, retained area fraction is `min(S/T, T/S)`. Choose the higher score, with portrait winning ties within `1e-12`. The original column/row counts stay fixed. Bias, pan, rotation and scale do not influence the orientation decision.

`LayoutGeometry` contains columns, rows, target ratio, tile orientation and a `FillCrop`. Its frame rectangle is expressed in original source pixels, and its size defines guide space. Reject a frame smaller than its grid counts to prevent empty cells.

## 3. Fill and Bias

For source dimensions `(W,H)` and target ratio `T`:
- Too wide: retain `(round(H*T), H)`.
- Too tall: retain `(W, round(W/T))`.
- Integer rounding yielding no excess is a no-op.

Clamp UI bias to `[0,100]`; the CLI rejects nonnumeric, nonfinite and out-of-range values.
- `0%`: preserve left/top; trim the right/bottom edge.
- `50%`: split trim between opposite edges.
- `100%`: preserve right/bottom; trim the left/top edge.

`leading_trim = round(excess * bias / 100)` and `trailing_trim = excess - leading_trim`. This defines a frame into the full source, rather than an irreversible cropped working image.

## 4. Full-Source Transform Rendering

Keep the full source bitmap. Let `F` be the frame dimensions, `A` the source-space frame centre, `t` the pan offset and `s` the zoom factor. Each guide-space output point samples:

```text
source_point = A + inverse_rotation(output_point - F/2 - t) / s
```

With zero pan/rotation and scale `1`, this samples the same pixels as ordinary Fill cropping. Panning can bring content outside the original frame into view. Bias defines the base anchor; transforms apply on top of it.

The renderer accepts a frame independent of source dimensions. Export samples each selected tile directly, avoiding a full-resolution transformed canvas. Ordinary export crops source rectangles translated by the frame origin.

The desktop UI adjusts X/Y during rotation and scale changes to keep the source point beneath the preview centre fixed. Reset clears transform values and selects the first block without changing layout or bias. Manual transforms retain the existing out-of-source blank/transparent fill behaviour.

## 5. CLI and Runner

Canonical options:

```text
--conform-to-layout
--conform-bias-percent <0..100>
```

Legacy `--expand-to-format` and `--expand-bias-percent` are aliases for the same layout-aware behaviour. In particular, legacy custom-grid calls now conform to the grid rather than the whole-image ISO ratio.

The runner emits canonical options. Shared helpers resolve layout geometry, read oriented source dimensions and render previews. Existing preset crop helpers remain available for compatibility.

CLI logs report Fill dimensions, bias/trim and auto custom tile orientation. PDF naming, metadata handling and top-to-bottom/left-to-right ordering remain as specified by the main tool spec.

## 6. Desktop UI

- Replace `Expand to Format` with `Conform to Layout` in the existing row.
- Keep the inline bias slider and axis-specific label beside the toggle.
- Show `Tiles: Portrait (Auto)` or `Tiles: Landscape (Auto)` beside custom Cols/Rows while conformity is enabled.
- Include auto orientation and layout ratio in the custom-grid tooltip.
- Disable bias when no trim is needed or no valid source/layout exists.
- Source, preset, custom-grid or conformity changes recompute geometry; layout changes retain the same numeric bias.
- Incomplete custom-grid entry retains the last valid preview and blocks Run. Do not substitute an ISO crop.
- Left drag adjusts bias outside Transform Cut. In Transform Cut, left drag pans the full source; right drag rotates and wheel zooms.
- Keep valid selected blocks across grid changes under existing selection rules.

## 7. Preview and Performance

Retain the complete bounded preview bitmap. Compose original-pixel guide-to-source sampling with thumbnail scaling, rather than cropping the thumbnail before transforms. This keeps preview and export geometry aligned despite thumbnail rounding.

Cache rendered preview content by source identity, original dimensions, frame rectangle and transform values. Use frame dimensions for guides, block selection and pan units. Retain adaptive guide contrast and deferred recomputation after resize/drag settles. Preserve preview opening, splitter resizing and collapse behaviour.

## 8. State and Reset Rules

Persist `conform_to_layout` and `conform_bias_percent`. Read legacy `expand_to_format` and `expand_bias_percent` when canonical fields are absent; canonical values take precedence. Save only canonical fields. Tile orientation is derived and not persisted.

Off/on retains bias for the same document. Changing documents or completing a run resets conformity off and bias to `50%`. No per-file cross-restart memory is added.

## 9. Verification

Cover preset regression, auto portrait/landscape and deterministic ties, biased frames, matched/no-op layouts, pixel partitions and undersized frames. Verify default transforms equal ordinary Fill, panning recovers excluded source pixels, thumbnail sampling matches export coordinates and centre-anchored rotation/zoom survives biased frames.

Verify canonical/legacy CLI options, state migration, custom validation, UI visibility/reset behaviour, adaptive guides, preview reopening and row-major selected-page export. Run the existing Python suite and live Tk/PDF smoke checks.
