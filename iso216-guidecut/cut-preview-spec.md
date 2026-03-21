# Guidecut Cut Preview Feature Spec

Status: Draft v0.1  
Date: 2026-03-21

## 1. Purpose
Add an in-app visual cut preview so users can verify tile boundaries before running Guidecut.

## 2. Scope
This feature adds a right-side preview panel and a `Show preview` toggle tied to the selected input document and current target format.

## 3. Functional Requirements
1. When a document is selected, a `Show preview` toggle appears on the right side of the app, below the input file section.
2. When `Show preview` is toggled on, a preview panel opens on the right side and displays the selected document.
3. Guideline overlays in the preview reflect the currently selected target format (`A3|A2|A1|A0`).
4. The preview panel expands/shrinks with the app window.
5. When `Show preview` is toggled off, the preview panel disappears.
6. If `Show preview` becomes hidden because `Input File` no longer resolves to an existing file, the toggle must be automatically deselected.

## 4. UI Layout
### 4.1 Main Structure
- Convert the top-level content area into a two-column layout:
  - Left: existing Guidecut controls and status area.
  - Right: preview panel (hidden by default).
- Left column remains primary and keeps current form behavior.
- Right column becomes visible only when preview is enabled.

### 4.2 Toggle Placement
- Add a `Show preview` toggle control in the left panel.
- Placement: right side of the app, directly below the input file row.
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

### 5.3 Toggle Off
- When `Show preview` is off:
  - Hide the right preview panel.
  - Keep existing left-panel controls unaffected.
- When input transitions from valid file path to non-file value (for example post-run filename clear to folder path), treat this as an automatic toggle-off event:
  - hide `Show preview`,
  - set preview state to off,
  - hide preview panel.

## 6. State and Persistence
- Do not persist preview toggle state across app restarts.
- On startup, preview defaults to off/hidden.
- `Show preview` becomes available only after a valid input file is selected.

## 7. Performance and Reliability
- Preview updates must not block the UI event loop.
- Resize handling should redraw overlay without visible lag.
- Failures in preview loading should not affect run/open-folder functionality.

## 8. Non-Goals (Initial Pass)
- Zoom/pan controls.
- Multi-page preview.
- Manual guide editing in preview.
- Exporting preview image.

## 9. Acceptance Criteria
1. Selecting a valid input file reveals `Show preview` below the input section on the right side.
2. Turning `Show preview` on opens a right-side preview panel.
3. Preview panel shows the selected document.
4. Changing target format updates visible guideline overlay immediately.
5. Resizing app resizes preview panel and redraws preview/guides correctly.
6. Turning `Show preview` off hides the panel.
7. If input no longer points to an existing file, `Show preview` is hidden and automatically deselected.
8. On startup, preview starts off/hidden until a valid input file is selected.
9. Preview load failures are surfaced in panel text and do not break normal tool execution.

## 10. Implementation Notes
- Tkinter baseline:
  - Use `Canvas` for preview drawing and guideline overlays.
  - Use existing image loading path where possible; convert to a display image for canvas.
- Keep preview logic isolated from CLI execution flow.
- Add tests for:
  - preview toggle visibility rules,
  - format-to-grid mapping,
  - overlay update triggers.
