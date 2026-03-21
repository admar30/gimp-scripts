# ISO216 Guidecut

## ISO216 Guidecut CLI

`iso216_guidecut.py` splits a source file into ISO216 tile grids and exports a
single multi-page PDF (one tile per page).

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
