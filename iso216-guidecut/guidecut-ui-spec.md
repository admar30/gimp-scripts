# Guidecut UI Specification

Status: Draft v0.7  
Date: 2026-03-21

## 1. Purpose
Design a simple desktop UI for running `iso216_guidecut.py` without requiring terminal use.

Initial pass focuses on collecting required script inputs, optional output-directory preference, and executing the tool.

## 2. Scope (Initial Feature Pass)
1. File search/input field:
- Supports manual keyboard path entry.
- Supports file navigation/browse dialog.
2. Target format dropdown:
- Lists supported values: `a3`, `a2`, `a1`, `a0`.
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
- On app close, persist selected target format and output settings.
- On next app launch, restore persisted target format and output settings.

## 3. Non-Goals (Initial Pass)
- Batch mode (multiple files).
- Advanced export options.
- Visual preview of tile layout.

## 4. UI Layout (v1)
Top-to-bottom layout:
1. Usage instructions (short static text).
2. `Input File` label.
3. File path text field (single-line editable).
4. `Browse...` button (opens file picker dialog).
5. `Target Format` label.
6. Format dropdown (`a3`, `a2`, `a1`, `a0`) with adjacent info/tooltip trigger.
7. `Specify output directory` toggle (checkbox/switch).
8. `Output Directory` text field (hidden by default, visible when toggle is enabled).
9. `Browse Output...` button (hidden with output-directory field).
10. `Open Folder` button.
11. `Run` button.
12. Status/output area (read-only text region for success/errors).

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
- Values restricted to `a3|a2|a1|a0`.
- Default selection: `a2`.
- Adjacent tooltip trigger (for example `i` icon) is required.
- Tooltip activates on cursor hover.
- Tooltip content reflects current selected format:
  - `a3`: `2` tiles/pages, sheet area is `2x A4`.
  - `a2`: `4` tiles/pages, sheet area is `4x A4`.
  - `a1`: `8` tiles/pages, sheet area is `8x A4`.
  - `a0`: `16` tiles/pages, sheet area is `16x A4`.
- Tooltip content must update immediately when format selection changes.

### 5.4 Run Button
- Enabled only when validation passes, or alternatively always enabled with validation on click.
- On click:
  - Build command params from current field values.
  - Execute script.
  - Stream process output into status area.
- While command is running:
  - Disable `Run`.
  - Re-enable when process exits.

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
- Restore these values on startup.
- Do not persist `Input File` path.
- If persisted data is missing/invalid:
  - fall back to defaults (`a2`, toggle off, empty output directory).

## 6. Script Integration Contract
Base command form:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>"
```

With explicit output directory enabled:

```powershell
python iso216_guidecut.py "<input_path>" "<target_format>" --output "<output_path>"
```

Execution details:
- Working directory: `iso216-guidecut` folder.
- Must preserve quoted file paths to support spaces.
- Capture stdout/stderr and display both in status area.
- Output path construction when explicit output directory is provided:
  - `<output_dir>\<input-stem>-guidecut-<target-format>-<YYYYMMDD-HHMMSS>.pdf`
- If explicit output-directory field is empty, do not pass `--output`; use script default location (source file directory).
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
12. After app restart, target format and output settings are restored from previous session.

## 10. Suggested Implementation Notes
- Recommended stack for first implementation: Python `tkinter` (no extra dependency).
- Keep UI logic separate from process execution logic:
  - `ui.py` for widgets and event wiring.
  - `runner.py` for command construction/execution.
- Persist settings in a small local JSON file (for example `guidecut_ui_state.json` in the tool directory or user config path).
