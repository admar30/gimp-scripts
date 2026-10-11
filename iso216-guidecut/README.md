# ISO216 Guidecut

Guidecut is also available as a client-only React web app:

- Hosted app: <https://admar30.github.io/gimp-scripts/>
- Web source and development instructions: [`../guidecut-webapp`](../guidecut-webapp/README.md)

The web app processes selected files entirely inside the browser. It does not
upload artwork to a server.

## ISO216 Guidecut CLI

`iso216_guidecut.py` splits a source file into ISO216 tile grids and exports a
single multi-page PDF (one tile per page).

### Specs
- Tool spec: `docs/specs/iso216-guideline-cutter-tool-spec.md`
- UI spec: `docs/specs/guidecut-ui-spec.md`
- UI theme spec: `docs/specs/guidecut-ui-theme-spec.md`

### Requirements
- Python 3
- Pillow (`PIL`)

### Usage
```powershell
python iso216-guidecut/cli/iso216_guidecut.py <input_path> <target_format>
```

Example:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a1
```

Optional explicit output path:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a1 --output C:\path\poster-cut.pdf
```

Optional custom grid mode:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png --grid-cols 3 --grid-rows 4
```

Mode selection rules:
- Choose exactly one grid mode:
  - Preset mode: `<target_format>` (`a3|a2|a1|a0`)
  - Custom mode: `--grid-cols` + `--grid-rows` (`1..32` each)
- Preset target and custom grid flags are mutually exclusive.

Optional expand-to-format pre-crop:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a1 --expand-to-format
```

Optional expand bias (`0..100`, default `50`):
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a1 --expand-to-format --expand-bias-percent 35
```

Expand bias semantics:
- `0%`: preserve left/top content, trim right/bottom.
- `100%`: preserve right/bottom content, trim left/top.

Optional transform-cut mode:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a2 --transform-cut --block-col 1 --block-row 0
```

Transform-cut mode keeps the guide grid fixed, transforms the source image underneath it, and exports the selected zero-based guide blocks as pages in one PDF.

To export multiple blocks, repeat `--block COL,ROW`; page order is top-to-bottom, then left-to-right, regardless of argument order. The older `--block-col` / `--block-row` flags remain available for one block, but cannot be combined with `--block`.

```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a2 --transform-cut --block 1,1 --block 0,0
```

Transform options:
```powershell
python iso216-guidecut/cli/iso216_guidecut.py C:\path\poster.png a2 --transform-cut --transform-offset-x 24 --transform-offset-y -12 --transform-rotation-deg 8 --transform-scale 1.15 --block-col 1 --block-row 0
```

Transform semantics:
- `--transform-offset-x` / `--transform-offset-y`: pan the source image in pixels under the fixed guide grid.
- `--transform-rotation-deg`: rotate the source image around its center.
- `--transform-scale`: uniform zoom factor; must be greater than `0`.
- `--block-col` / `--block-row`: selected guide block, zero-based from top-left.
- `--block COL,ROW`: repeatable selected guide block, zero-based from top-left.

### UI
Launch the desktop UI:

From the `gimp-scripts` repo root:
```powershell
python iso216-guidecut/app/guidecut_ui.py
```

From inside the `iso216-guidecut` folder:
```powershell
python app/guidecut_ui.py
```

UI interactions in current pass:
- Input path supports manual typing and `Browse...` file picker.
- Target format selector supports `A3`, `A2`, `A1`, `A0` with an adjacent tooltip button showing tiles/pages and A4-relative size.
- `Custom Grid` toggle reveals manual `Cols`/`Rows` entry fields and disables preset selector while active.
- Custom grid tooltip shows `Grid: CxR` and `Tiles/pages` for current values.
- `Specify output directory` toggle reveals/hides explicit output controls.
- Output directory supports manual typing and `Browse Output...`; missing directories are auto-created on run.
- `Open Folder` resolves to explicit output directory when enabled and set, otherwise resolves from input path (file parent or folder path).
- `Expand to Format` toggle enables pre-crop to ISO ratio before guides/tiles are computed.
- Expand bias slider (`0..100`) appears only when expand mode is on; slider is disabled when source has no excess trim axis.
- `Transform Cut` toggle reveals source transform controls (`X`, `Y`, `Rot`, `Scale`), active block controls (`Col`, `Row`), `Reset`, and `Select All`.
- With transform mode enabled, preview keeps guides fixed and transforms the source image underneath. Click a block to select only it; Ctrl+click a block to add or remove it without clearing other selections. `Select All` selects every block. Editing `Col`/`Row` selects that single block.
- In transform mode, left drag pans the image in the pointer's direction, right drag rotates (right/down clockwise), and the mouse wheel zooms (up/in, down/out). A left click without dragging still selects a block. Pan takes priority over expand-bias dragging while transform mode is enabled.
- With transform mode enabled, `Run` exports the selected blocks as pages in one PDF. Deselecting every block prevents a run until at least one is selected.
- `Run` executes in a background thread and streams stdout/stderr to the status panel.
- Post-run input behavior keeps only the source folder path (filename cleared) to speed up selecting the next file.
- Post-run expand behavior resets to defaults (`Expand to Format` off, bias `50%`).
- Custom grid mode/values are session-only (not persisted across app restart) and are kept after run.
- `Show preview` toggle appears only when `Input File` resolves to an existing file.
- Enabling preview opens a right-side preview panel, expanding the app to the right without compressing left-side controls.
- Preview panel includes a draggable vertical divider for resizing UI-vs-preview width allocation.
- Preview panel auto-fits width to rendered content on open and avoids cumulative window-size drift across reopen/restart cycles.
- Preview displays guide overlays for the selected target format and updates when target format changes.
- Preview uses a bounded image bitmap for responsive transforms; guide positions and export still use the source's original pixel dimensions.
- With expand mode enabled, preview renders cropped working area and guides against cropped geometry.
- Preview image drag along excess trim axis updates expand bias live and stays synchronized with the slider.
- Guide overlays use adaptive contrast sampling (with optional halo stroke) for visibility on dark/light/mixed documents.
- Preview redraw during resize is responsive; heavier contrast recompute is deferred until resize settles.
- Preview toggle state is not persisted; it resets off/hidden on startup when no valid file is selected.
- Persistent settings on close/reopen: target format, output toggle/value, input-folder context, window geometry (size/position), preview split ratio, and expand settings.

### Supported targets
- `a3`
- `a2`
- `a1`
- `a0`

Custom mode:
- `--grid-cols <1..32>`
- `--grid-rows <1..32>`

### Behavior
- Detects portrait/landscape/square orientation from source dimensions.
- Uses alternating-axis bisection to determine preset tile grids.
- Uses explicit `cols x rows` when custom mode is selected.
- Computes deterministic guide positions in pixels.
- Exports a single multi-page PDF beside input by default:
  - `<input-stem>-guidecut-<target>-<YYYYMMDD-HHMMSS>.pdf`
- Custom-grid outputs use token `grid-CxR` in place of target:
  - `<input-stem>-guidecut-grid-<cols>x<rows>-<YYYYMMDD-HHMMSS>.pdf`
- Transform-cut outputs append the selected block coordinate:
  - `<input-stem>-guidecut-<target-or-grid>-block-<col>-<row>-<YYYYMMDD-HHMMSS>.pdf`
- Multi-block transform outputs append the number of selected blocks:
  - `<input-stem>-guidecut-<target-or-grid>-blocks-<count>-<YYYYMMDD-HHMMSS>.pdf`
- Page order is top-to-bottom, left-to-right.
- If a timestamped output filename already exists, appends `-1`, `-2`, etc.
