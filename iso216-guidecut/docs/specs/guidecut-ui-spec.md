# Guidecut UI Specification

Status: Draft v1.1
Date: 2026-10-10

## 1. Purpose
Design a simple desktop UI for running `iso216_guidecut.py` without requiring terminal use.

Current pass covers core run controls, preview integration, and conform-to-layout controls.

## 2. Scope (Initial Feature Pass)
1. File search/input field:
- Supports manual keyboard path entry.
- Supports file navigation/browse dialog.
2. Target format dropdown:
- Lists supported values as uppercase display labels: `A3`, `A2`, `A1`, `A0`.
2.1 Custom grid controls:
- `Custom Grid` toggle.
- `Cols` and `Rows` numeric inputs shown only when custom mode is enabled.
- Allowed range per value: `1..32`.
- Preset selector is disabled while custom mode is enabled.
3. Run button:
- Executes the script using selected file path + selected format.
4. Optional output directory controls:
- Toggle to enable explicit output directory mode.
- Hidden output-directory field tied to the toggle.
- If output-directory field is empty, default output location is the source file directory.
5. Open folder button:
- Opens source file folder by default.
- Opens explicit output directory when selected.
6. Target format tooltip:
- Cursor-hover-activated tooltip next to format selector.
- Shows selected format details:
  - Number of generated tiles/pages.
  - Relative sheet size compared to A4.
7. Usage instructions:
- Show a short usage hint above the input field.
- Keep instruction text concise and always visible.
8. Session persistence:
- On app close, persist selected target format, output settings, input-folder context, and window size/desktop location.
- On next app launch, restore persisted target format, output settings, input-folder context, and window size/desktop location.
9. Conform to Layout controls:
- `Conform to Layout` toggle in main form.
- Hidden trim-bias slider shown inline on the same row as the conformity toggle when conformity is enabled.
- Slider range `0..100`, default `50.0`.
- If source has no excess trim axis for the selected layout, slider is disabled and shown as no-op.
- Custom grids show resolved A4 tile orientation next to `Cols/Rows` while conformity is enabled; the format tooltip includes tile orientation and layout ratio.
10. Custom-grid mode behavior:
- First time custom mode is enabled in a session, initialize `Cols/Rows` from current preset grid.
- Keep current custom values after run completion.
- Do not persist custom mode/values across app restart.
11. Transform-cut controls:
- `Transform Cut` toggle.
- Hidden transform controls shown when enabled:
  - `X`: source image horizontal pan in pixels.
  - `Y`: source image vertical pan in pixels.
  - `Rot`: source image rotation in degrees around the preview centre.
  - `Scale`: uniform source image zoom factor around the preview centre.
  - `Col`: active block column, zero-based.
  - `Row`: active block row, zero-based.
- `Reset` button restores transform defaults and selects the first block only.
- `Select All` button selects every block in the current grid.

## 3. Non-Goals (Initial Pass)
- Batch mode (multiple files).
- Advanced export options.
- Multi-file queueing and scheduling.

## 4. Layout
Current layout in the implemented UI:

### 4.1 Window and Container Structure
- The main window contains one root app frame with:
  - primary control panel (always visible),
  - optional preview splitter + preview panel (visible when preview is enabled).
- Without preview, the primary panel fills the available window width and height.
- The panel uses a 3-column grid:
  - Column 0: field labels.
  - Column 1: primary input controls (expands horizontally).
  - Column 2: auxiliary actions (`Browse...`, info button, etc.).

### 4.2 Row-by-Row Element Placement
1. Row 0: usage instructions label, spanning all 3 columns.
2. Row 1: `Input File` label (col 0), rounded input field (col 1), `Browse...` button (col 2).
3. Row 3: `Specify output directory` toggle on the left, `Show preview` toggle on the right.
4. Row 4: output-directory row (hidden by default), spanning all 3 columns.
- Inside row 4:
  - rounded output-directory field (expanding left section),
  - `Browse Output...` button (right section).
5. Row 5: `Conform to Layout` row:
  - left: `Conform to Layout` toggle,
  - right: Fill-bias slider cluster (hidden unless conformity is enabled).
6. Row 6: `Custom Grid` row:
  - left: `Custom Grid` toggle,
  - right: `Cols` / `Rows` fields (hidden unless custom mode is enabled), followed by auto tile orientation when conformity is enabled.
7. Row 7: `Transform Cut` row:
  - left: `Transform Cut` toggle,
  - right: transform controls (`X`, `Y`, `Rot`, `Scale`, `Col`, `Row`, `Reset`, `Select All`) hidden unless transform mode is enabled.
8. Row 8: action row, spanning all 3 columns.
- Inside row 8:
  - compact `Target Format` cluster at the left edge:
    - `Target Format` label,
    - fixed-width rounded dropdown (non-expanding) sized tightly to its clickable area,
    - info tooltip button placed immediately next to the dropdown with minimal gap.
  - flexible spacer between target-format cluster and action buttons,
  - `Open Folder` button,
  - `Run` button on the far right.
9. Row 9: status/output region, spanning all 3 columns and expanding vertically.

### 4.3 Resize Behavior
- The panel expands with the window.
- Primary field column (column 1) grows horizontally.
- Status/output region (row 8) takes additional vertical space.
- Layout must not include an unused expanding right-side spacer area.
- Target-format dropdown width remains fixed and does not stretch with window resize.
- Target-format dropdown must not render non-clickable dead padding inside its visual bounds.

## 5. Field Behavior
### 5.1 File Path Field
- Accept any typed path.
- On `Run`, validate:
  - Not empty.
  - Exists.
  - Is a file.
- If invalid, show inline/status error and do not run.

### 5.2 Browse Button
- Opens native file picker.
- Default open location:
  - If input field currently contains a folder path, open that folder.
  - If input field contains a file path, open its parent folder.
  - Otherwise use system default.
- On file selection, writes absolute path into path field.
- User can still edit the populated path manually.

### 5.3 Format Dropdown
- Required selection.
- Display values restricted to `A3|A2|A1|A0`.
- Default selection: `A2`.
- Internal format handling remains case-insensitive and normalizes to canonical lowercase for script invocation.
- Adjacent tooltip trigger (for example `i` icon) is required.
- Tooltip activates on cursor hover.
- Tooltip content reflects current selected format:
  - `A3`: `2` tiles/pages, sheet area is `2x A4`.
  - `A2`: `4` tiles/pages, sheet area is `4x A4`.
  - `A1`: `8` tiles/pages, sheet area is `8x A4`.
  - `A0`: `16` tiles/pages, sheet area is `16x A4`.
- Tooltip content must update immediately when format selection changes.
- When `Custom Grid` is enabled, dropdown is disabled.

### 5.4 Run Button
- Enabled only when validation passes, or alternatively always enabled with validation on click.
- On click:
  - Build command params from current field values.
  - Execute script.
  - Stream process output into status area.
- While command is running:
  - Disable `Run`.
  - Re-enable when process exits.

### 5.4.1 Grid Mode Validation
- Exactly one grid mode must be active for run:
  - Preset mode: target format selected.
  - Custom mode: valid `Cols` and `Rows` values.
- In custom mode:
  - both `Cols` and `Rows` are required,
  - values must be integers in `1..32`.

### 5.5 Output Directory Toggle + Hidden Field
- Toggle default state: off.
- When off:
  - Output-directory field remains hidden.
  - UI does not pass explicit output path args.
  - Script default behavior determines output path (same folder as source file).
- When on:
  - Reveal output-directory field and `Browse Output...`.
  - User may enter directory manually or choose via folder picker.
  - If field is empty at run time, fall back to source-file directory.
  - If field is non-empty and directory does not exist, create it automatically.

### 5.6 Post-Run State Behavior
- After each run attempt (success or failure):
  - Remove filename from `Input File` value and keep only source folder path.
  - This retained folder path becomes the default `Browse...` location for selecting the next file.
  - Keep currently selected `Target Format`.
  - Keep `Specify output directory` toggle state.
  - Keep `Output Directory` field value unchanged.

### 5.7 Open Folder Button
- Resolves target folder with this priority:
  - If `Specify output directory` is enabled and `Output Directory` is non-empty, use `Output Directory`.
  - Otherwise, use folder represented by `Input File` value:
    - if `Input File` is a file path, use its parent
    - if `Input File` is already a folder path, use that folder
- On click:
  - Open the resolved folder in the system file explorer.
  - Support Windows and macOS.
- If no valid folder can be resolved:
  - Show a clear status error and do not attempt to open explorer.

### 5.8 Usage Instructions
- Show static helper text above the input section.
- Minimum content:
  - choose input file
  - choose target format
  - optional output directory
  - run

### 5.9 Persistence Across App Restart
- Persist these values on app close:
  - `Target Format`
  - `Specify output directory` toggle state
  - `Output Directory` value
  - `Conform to Layout` toggle state
  - `Fill bias percent`
- `Input File` folder context only (filename is removed before persist)
- Window geometry (`width x height + x + y`) for size and desktop position
- Restore these values on startup.
- Do not persist input filename.
- Do not persist custom-grid toggle or custom cols/rows values.
- If persisted data is missing/invalid:
  - fall back to defaults (`A2`, toggle off, empty output directory, empty input-folder context, platform default window placement/size).

### 5.10 Conform to Layout UX Behavior
- Toggle off:
  - conformity arguments are not sent to CLI,
  - slider row stays hidden.
- Toggle on:
  - slider row is shown,
  - slider value controls trim-bias percentage (`0..100`).
- Bias semantics in UI must match CLI:
  - `0%` preserves left/top side,
  - `100%` preserves right/bottom side.
- Document-scoped session behavior:
  - turning conformity off then on for the same selected file retains current bias,
  - changing the selected input document resets conformity toggle to off and bias to `50%`,
  - after run completion, reset conformity toggle to off and bias to `50%` (input filename is already cleared to folder context).
- No per-file cross-restart memory is required.
- Presets retain existing ISO216 ratio and bisection rules.
- Custom target ratio is `(cols / rows) * tile_ratio`, where portrait tiles use `1/sqrt(2)` and landscape tiles use `sqrt(2)`.
- Auto chooses the orientation retaining more source area; ties choose portrait. Source orientation is normalized from EXIF first. Column/row counts do not change.
- Orientation depends only on original source dimensions and grid, never bias or transforms.
- Grid/preset changes recompute the frame and trim axis while retaining bias.
- Invalid/incomplete custom dimensions retain the last valid preview, disable the bias slider, and block Run.
- Saved `expand_to_format`/`expand_bias_percent` keys migrate to `conform_to_layout`/`conform_bias_percent`; save only canonical names.
- Fill is the only fitting behaviour in this pass; Fit/padding is deferred.

### 5.11 Transform-Cut UX Behavior
- Toggle off:
  - transform arguments are not sent to CLI,
  - output remains the normal full multi-page tile PDF.
- Toggle on:
  - transform controls are shown,
  - preview keeps guide/grid layer fixed,
  - preview transforms the source image underneath the fixed guides,
  - the full source remains available behind the Fill frame, including pixels outside its initial bounds,
  - zero pan/rotation and scale `1` match ordinary Fill output; bias sets the source anchor and transforms apply on top,
  - all selected blocks are highlighted,
  - a plain click selects only that block and updates `Col` and `Row`,
  - Ctrl+click adds or removes that block without clearing other selections,
  - editing `Col` or `Row` selects the entered block alone,
  - `Select All` selects every block in the current grid,
  - left click and drag pans the source image in the same direction as the pointer, with offsets measured in original source pixels,
  - right click and drag rotates the source; right/down is clockwise and left/up is counterclockwise,
  - scrolling up zooms in and scrolling down zooms out, updating `Scale`,
  - rotation and scaling keep the source point beneath the preview centre stationary, including when `Rot` or `Scale` is edited directly,
  - `X` and `Y` are adjusted automatically on rotation/scale changes so preview and exported PDF use the same anchored transform,
  - mouse manipulation updates the corresponding `X`, `Y`, `Rot`, and `Scale` controls live,
  - when conform-to-layout is also active, left drag pans the source instead of changing trim bias; the trim-bias slider remains available,
  - run exports selected blocks as pages in one PDF, ordered top-to-bottom then left-to-right, regardless of selection order,
  - an empty selection is allowed while editing but blocks Run with a clear error.
- Defaults:
  - `X = 0`
  - `Y = 0`
  - `Rot = 0`
  - `Scale = 1`
  - `Col = 0`
  - `Row = 0`
- Transform values are session controls and are not persisted across app restart.
- Selected block coordinates are zero-based from top-left guide space and must be valid for the current resolved grid. Selections outside a changed grid are removed; if a nonempty selection would become empty, the first block is selected.
- Reset restores transform defaults and first-block selection without changing layout or bias.

## 6. Script Integration Contract
Base command form:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>"
```

With explicit output directory enabled:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>" --output "<output_path>"
```

With conformity enabled:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>" --conform-to-layout --conform-bias-percent "<0..100>"
```

With custom-grid mode enabled:

```powershell
python iso216_guidecut.py "<input_path>" --grid-cols "<1..32>" --grid-rows "<1..32>"
```

With transform-cut mode enabled:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>" --transform-cut --transform-offset-x "<px>" --transform-offset-y "<px>" --transform-rotation-deg "<deg>" --transform-scale "<factor>" --block "<col,row>" [--block "<col,row>" ...]
```

Execution details:
- Working directory: `iso216-guidecut` folder.
- Must preserve quoted file paths to support spaces.
- Capture stdout/stderr and display both in status area.
- Output path construction when explicit output directory is provided:
  - `<output_dir>\<input-stem>-guidecut-<target-format>-<YYYYMMDD-HHMMSS>.pdf`
- If explicit output-directory field is empty, do not pass `--output`; use script default location (source file directory).
- Pass conformity args only when conformity toggle is enabled.
- Pass transform args and one `--block` per selected block only when transform toggle is enabled.
- Pass either preset target argument or custom grid args, never both.
- Exit code handling:
  - `0`: success message with generated output path.
  - non-zero: error message with stderr content.

## 7. Error Handling Requirements
- File path invalid: block run, show clear message.
- Output directory invalid/unwritable: block run or surface script error clearly.
- Open folder action with invalid/non-existent target: show clear status error.
- Unsupported format: should not occur via dropdown, but still handle script error gracefully.
- Script runtime failure: show error output in status area.
- Missing Python/runtime/script file: show actionable error text.
- Persisted-state load/save failure: log warning in status area and continue with defaults/current state.

## 8. Accessibility and UX Baseline
- Keyboard navigation support:
  - `Tab` between controls.
  - `Enter` while focused on `Run` triggers run.
  - `Enter` while focused on `Open Folder` opens resolved folder.
- Format details tooltip should also be reachable without mouse (focusable info control).
- Clear focus state for all controls.
- Action buttons must use rounded corners to match field styling.
- Rounded buttons should be rendered as single-layer controls (no nested native button border inside a rounded wrapper).
- Status text must remain readable after multiple runs (append log with separators).

## 9. Acceptance Criteria (Initial Pass)
1. User can type a file path manually and run successfully.
2. User can choose a file via browse dialog and run successfully.
3. User can select any supported format from dropdown.
4. User can enable output-directory toggle and provide directory via typing or browse.
5. When output-directory field is empty, output defaults to source file location.
6. `Run` invokes `iso216_guidecut.py` with correct parameters, including optional `--output` only when needed.
7. UI displays both success output and error output from the script.
8. After each run, input field retains only source folder path (filename removed), and `Browse...` opens from that folder.
9. `Open Folder` opens source folder by default and explicit output directory when selected.
10. Hovering format tooltip control shows the selected format's tile count and A4-relative size.
11. A simple usage instruction block is visible above the input field.
12. After app restart, target format, output settings, and input-folder context are restored from previous session.
13. After app restart, window size and desktop location are restored from previous session when valid persisted geometry exists.
14. Enabling `Conform to Layout` reveals bias slider and running passes conformity args to CLI.
15. Bias slider and preview interactions stay synchronized for the active document (document change and post-run reset behavior are enforced).
16. Enabling `Transform Cut` reveals transform controls and running passes transform args to CLI.
17. With `Transform Cut` enabled, preview highlights all selected blocks; plain click replaces the selection, Ctrl+click toggles one block, and `Select All` selects the grid.
18. With `Transform Cut` enabled, run exports selected blocks in row-major page order, and rejects an empty selection.

## 10. Suggested Implementation Notes
- Recommended stack for first implementation: Python `tkinter` (no extra dependency).
- Keep UI logic separate from process execution logic:
  - `ui.py` for widgets and event wiring.
  - `runner.py` for command construction/execution.
- Persist settings in a small local JSON file (for example `guidecut_ui_state.json` in the tool directory or user config path).
