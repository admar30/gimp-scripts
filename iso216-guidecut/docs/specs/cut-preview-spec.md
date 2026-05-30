# Guidecut Cut Preview Feature Spec

Status: Draft v0.2  
Date: 2026-05-30

## 1. Purpose
Add an in-app visual cut preview so users can verify tile boundaries before running Guidecut.

## 2. Scope
This feature adds a right-side preview panel and a `Show preview` toggle tied to the selected input document and current target format. It also integrates expand-to-format preview behavior and drag-driven trim bias adjustment.

## 3. Functional Requirements
1. When a document is selected, a `Show preview` toggle appears on the same row as `Specify output directory`, aligned to the right side.
2. When `Show preview` is toggled on, a preview panel opens on the right side and displays the selected document.
3. Guideline overlays in the preview reflect the currently selected target format (`A3|A2|A1|A0`).
4. The preview panel expands/shrinks with the app window.
5. When `Show preview` is toggled off, the preview panel disappears.
6. If `Show preview` becomes hidden because `Input File` no longer resolves to an existing file, the toggle must be automatically deselected.
7. Guideline color should adapt to preview-image color/luminance to maximize local visibility where each guide intersects image content.
8. Enabling preview must expand the app window to the right to make room for the preview panel, without compressing the existing non-preview controls.
9. While preview is visible, the divider between main UI and preview panel must be draggable so users can resize panel widths.
10. Last used UI/preview split dimensions must persist after preview collapse so re-enabling preview restores the prior split state relative to current UI-panel size.
11. On preview open, auto-fit preview panel width to the rendered preview image width (plus required panel chrome) so avoidable x-axis whitespace is removed.
12. Repeated preview show/hide cycles and app restarts must not cause cumulative window-width growth.
13. When `Expand to Format` is enabled, preview renders and guides must use the effective cropped working area.
14. While expand mode is enabled and an excess trim axis exists, dragging the preview image along the excess axis must update expand bias in real time.
15. Preview drag and expand bias slider must remain synchronized bidirectionally.

## 4. UI Layout
### 4.1 Main Structure
- Convert the top-level content area into a two-column layout:
  - Left: existing Guidecut controls and status area.
  - Right: preview panel (hidden by default).
- Left column remains primary and keeps current form behavior.
- Right column becomes visible only when preview is enabled.
- When preview is enabled, lock left-column width for that toggle session and grow the top-level window width rightward so left controls do not reflow/compress.
- Include a visible draggable vertical divider between left and right panes while preview is enabled.
- Divider and panel placement should preserve readable spacing while panel width is auto-fitted to rendered preview content on open.

### 4.2 Toggle Placement
- Add a `Show preview` toggle control in the left panel.
- Placement: same row as `Specify output directory`, right-aligned.
- Visibility rules:
  - Visible only when `Input File` currently resolves to an existing file.
  - Hidden when input is empty or invalid.
  - When hidden by these rules, force toggle value to off.

### 4.3 Preview Panel
- Located on the right side of the app.
- Contains:
  - Panel title (for example: `Cut Preview`).
  - Canvas/image surface for document preview.
  - Optional short status text (`Loading...`, `Unable to preview file`, etc.).
- The panel should stretch vertically with the app and scale preview content on resize.

## 5. Preview Behavior
### 5.1 Source Rendering
- Load the selected document into preview when:
  - `Show preview` turns on.
  - Input file changes while preview is on.
- Render fit-to-panel while preserving source aspect ratio.
- If source cannot be previewed, show a clear fallback message in the panel.

### 5.2 Guideline Overlay
- Draw guideline lines on top of preview according to current target format.
- Grid counts by target format:
  - `A3`: 2 tiles
  - `A2`: 4 tiles
  - `A1`: 8 tiles
  - `A0`: 16 tiles
- Guide orientation must follow source orientation logic used by the tool (portrait vs landscape).
- Overlay updates immediately when target format changes.
- Guide color should be selected from a high-contrast palette using sampled pixels under/near each guide path.
- If measured contrast is still weak, render a secondary outline/halo stroke behind the guide for legibility.
- Expand-mode interaction:
  - When expand mode is enabled, compute crop rectangle first, then render preview from the cropped working area.
  - Guide geometry is computed against cropped dimensions, not original source dimensions.
  - If source has no excess trim axis, drag behavior is disabled and slider is no-op/disabled.

### 5.3 Expand Drag and Slider Sync
- Drag gesture is active only when:
  - preview is visible,
  - expand mode is enabled,
  - a valid source is loaded,
  - computed crop has an excess axis (`x` or `y`).
- Drag direction:
  - excess on `x`: horizontal drag updates bias.
  - excess on `y`: vertical drag updates bias.
- Mapping:
  - drag delta maps proportionally to leading trim amount on the excess axis.
  - resulting bias is clamped to `[0,100]`.
- Synchronization:
  - drag updates slider value live,
  - slider changes redraw preview live and update effective crop.

### 5.4 Toggle Off
- When `Show preview` is off:
  - Hide the right preview panel.
  - Keep existing left-panel controls unaffected.
- When input transitions from valid file path to non-file value (for example post-run filename clear to folder path), treat this as an automatic toggle-off event:
  - hide `Show preview`,
  - set preview state to off,
  - hide preview panel.
- When preview is disabled/hidden, contract the app window from the right by the preview allocation amount.
- Divider interaction:
  - Dragging divider left/right resizes left and right pane widths.
  - Pane resize must preserve minimum usable widths for both panes.
  - Divider is only interactive while preview is visible.
- After divider resize:
  - persist current split ratio.
  - on next preview enable, restore preview width from that ratio relative to the current UI pane width.

## 6. State and Persistence
- Do not persist preview toggle state across app restarts.
- On startup, preview defaults to off/hidden.
- `Show preview` becomes available only after a valid input file is selected.
- Persist preview split ratio (UI pane vs preview pane) so split preference survives collapse/reopen and app restart.
- Expand state is persisted as part of UI state schema, but per-document memory is session-only.
- Because input filename is cleared to folder context after run/startup, expand controls naturally reset to defaults when no valid file is active.

## 7. Performance and Reliability
- Preview updates must not block the UI event loop.
- Resize handling should redraw overlay without visible lag.
- Failures in preview loading should not affect run/open-folder functionality.
- Contrast analysis for guide color should remain lightweight enough for interactive resize (sampling-based, not full-image analysis).
- Contrast recompute after panel resize should be debounce/settle-based (after resize drag ends), not on every intermediate mouse-move resize event.
- Expand drag updates should use fast redraw during motion and defer heavier contrast recompute to debounce/settle timing.

## 8. Non-Goals (Initial Pass)
- Zoom/pan controls.
- Multi-page preview.
- Manual guide editing in preview.
- Exporting preview image.

## 9. Acceptance Criteria
1. Selecting a valid input file reveals `Show preview` on the `Specify output directory` row at the right side.
2. Turning `Show preview` on opens a right-side preview panel.
3. Preview panel shows the selected document.
4. Changing target format updates visible guideline overlay immediately.
5. Resizing app resizes preview panel and redraws preview/guides correctly.
6. Turning `Show preview` off hides the panel.
7. If input no longer points to an existing file, `Show preview` is hidden and automatically deselected.
8. On startup, preview starts off/hidden until a valid input file is selected.
9. Preview load failures are surfaced in panel text and do not break normal tool execution.
10. On very dark and very light documents, guide overlays remain clearly visible without manual color selection.
11. Toggling preview on does not compress/reflow existing left-side controls; window expands rightward instead.
12. While preview is visible, dragging the divider changes UI/preview width allocation without breaking layout.
13. After preview is hidden, showing preview again restores pane split sizing based on the last saved split ratio and current UI pane width.
14. Enabling preview auto-collapses panel width to content width so avoidable horizontal whitespace is minimized.
15. Across repeated app restarts and preview toggles, window width remains stable (no progressive growth drift).
16. With expand mode enabled, preview guides align to cropped working area and match CLI crop semantics.
17. Dragging preview along excess axis updates trim bias live and remains synchronized with slider value.

## 10. Implementation Notes
- Tkinter baseline:
  - Use `Canvas` for preview drawing and guideline overlays.
  - Use existing image loading path where possible; convert to a display image for canvas.
- Keep preview logic isolated from CLI execution flow.
- Add tests for:
  - preview toggle visibility rules,
  - format-to-grid mapping,
  - overlay update triggers.
