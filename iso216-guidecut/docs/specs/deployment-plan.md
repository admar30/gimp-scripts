# ISO216 Guidecut Deployment Plan

Status: Draft v0.1  
Date: 2026-03-21

## 1. Goal
Ship ISO216 Guidecut in a way that is easy for non-technical users to run on Windows, macOS and Linux, while keeping a reproducible developer workflow for source-based usage.

## 2. Deployment Strategy
Use a dual-channel release model:

1. Source channel (developer-friendly):
- Python scripts from this repo.
- Install dependency (`Pillow`) and run `iso216_guidecut.py` or `guidecut_ui.py`.

2. Binary channel (end-user-friendly):
- Build standalone desktop binaries for Windows and macOS from `guidecut_ui.py`.
- Optionally include CLI binary build if needed later.

Recommended first production target:
- UI binaries for Windows + macOS + Linux.
- Keep CLI as source-run initially.

## 3. Release Targets
1. Windows 10/11 x64
2. macOS (Apple Silicon + Intel if feasible)
3. Ubuntu, Fedora

Out of scope for first deployment:
- Installer frameworks (MSI/PKG) unless distribution friction appears

## 4. Packaging Approach
Recommended packager: PyInstaller.

Initial build style:
1. `one-folder` distribution (preferred for fewer runtime surprises).
2. Include required dynamic assets/modules (Pillow plugins, Tkinter dependencies).

Artifact naming convention:
- `guidecut-ui-win-x64-v<version>.zip`
- `guidecut-ui-macos-universal-v<version>.zip` (or split arch zips if needed)

## 5. Versioning and Release Cadence
Use semantic versioning:
- `v0.1.0` first public deployment of current feature set.
- Patch releases for bug fixes (`v0.1.1`, etc.).

Tagging rules:
1. Merge release-ready branch into `main`.
2. Create annotated tag `vX.Y.Z`.
3. Build artifacts from tagged commit only.

## 6. Build and Validation Pipeline
## 6.1 Pre-build gates
1. Unit tests pass:
- `python -m pytest -q iso216-guidecut/test_guidecut_runner.py`
- `python -m pytest -q iso216-guidecut/test_iso216_guidecut.py`
2. Static sanity:
- `python -m py_compile` over UI/runner/CLI modules.
3. Manual smoke checks (both OS targets):
- Launch UI.
- Browse + manual input.
- Target format switch.
- Run output generation.
- Preview open/close/resize/splitter behavior.
- Adaptive guide contrast visible on dark/light images.

## 6.2 Build steps (per platform)
1. Create clean virtual environment.
2. Install runtime/build dependencies (`Pillow`, `pyinstaller`).
3. Build UI executable from `guidecut_ui.py`.
4. Package output folder into versioned zip artifact.
5. Run post-build smoke test on built artifact.

## 7. Distribution and Delivery
Primary channel:
- GitHub Releases (or equivalent) with attached zip artifacts.

Release contents:
1. Windows zip artifact.
2. macOS zip artifact.
3. Checksums (`SHA256SUMS.txt`).
4. Short release notes.
5. Link to usage docs.

## 8. Documentation Updates for Deployment
Before first public release:
1. Add a dedicated "Install/Run Binaries" section to `iso216-guidecut/README.md`.
2. Add per-platform quick-start steps.
3. Document known limitations:
- First-run OS trust prompts.
- Supported input formats depend on Pillow build capabilities.

## 9. Risks and Mitigations
1. Pillow format/plugin differences across platforms:
- Mitigation: validate with representative AVIF/PNG/JPEG inputs on each target OS.
2. Tkinter packaging differences on macOS:
- Mitigation: smoke-test app startup and file dialogs on built artifacts.
3. Binary size and startup performance:
- Mitigation: start with one-folder build; optimize after first release.
4. False-positive antivirus flags (Windows):
- Mitigation: publish checksums and keep release process deterministic.

## 10. Deployment Checklist (v0.1.0)
1. Finalize release scope and version.
2. Freeze release branch from `main`.
3. Run full test + smoke suite.
4. Build Windows artifact.
5. Build macOS artifact.
6. Validate artifacts manually.
7. Update README install section.
8. Create tag `v0.1.0`.
9. Publish release with artifacts + checksums + notes.
10. Monitor first-user feedback and triage hotfixes.

## 11. Immediate Next Actions
1. Add a minimal `pyinstaller` build script for Windows/macOS in `iso216-guidecut/`.
2. Add a release checklist section to README.
3. Perform one dry-run Windows binary build and smoke test.
