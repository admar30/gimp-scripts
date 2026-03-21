# ISO216 Guidecut

## ISO216 Guidecut CLI

`iso216_guidecut.py` splits a source file into ISO216 tile grids and exports a
single multi-page PDF (one tile per page).

### Specs
- Tool spec: `iso216-guideline-cutter-tool-spec.md`
- UI spec: `guidecut-ui-spec.md`
- UI theme spec: `guidecut-ui-theme-spec.md`

### Requirements
- Python 3
- Pillow (`PIL`)

### Usage
```powershell
python iso216-guidecut/iso216_guidecut.py <input_path> <target_format>
```

Example:
```powershell
python iso216-guidecut/iso216_guidecut.py C:\path\poster.png a1
```

Optional explicit output path:
```powershell
python iso216-guidecut/iso216_guidecut.py C:\path\poster.png a1 --output C:\path\poster-cut.pdf
```

### UI
Launch the desktop UI:

```powershell
python iso216-guidecut/guidecut_ui.py
```

UI features in current pass:
- Input file path by typing or browse dialog
- Target format selector (`a3`, `a2`, `a1`, `a0`) with hover tooltip details
- Optional explicit output directory (auto-created if missing)
- `Run` with background execution (UI stays responsive)
- `Open Folder` for source/output directory (Windows/macOS supported)

### Supported targets
- `a3`
- `a2`
- `a1`
- `a0`

### Behavior
- Detects portrait/landscape/square orientation from source dimensions.
- Uses alternating-axis bisection to determine tile grid.
- Computes deterministic guide positions in pixels.
- Exports a single multi-page PDF beside input by default:
  - `<input-stem>-guidecut-<target>-<YYYYMMDD-HHMMSS>.pdf`
- Page order is top-to-bottom, left-to-right.
- If a timestamped output filename already exists, appends `-1`, `-2`, etc.
