# Guidecut Web App

Guidecut Web App is a client-only React version of ISO216 Guidecut. It divides
one raster image into A4 print tiles and produces a single multi-page PDF.

Hosted app: <https://admar30.github.io/gimp-scripts/>

## Privacy

Selected images are decoded and processed locally in the browser. The app has
no upload endpoint, account system, analytics, or cloud storage.

## Features

- File picker and drag-and-drop input.
- JPEG, PNG, WebP, AVIF, GIF, and BMP input when supported by the browser.
- First-frame processing for animated images.
- ISO presets: A3, A2, A1, and A0.
- Custom grids from 1 to 32 columns and rows.
- Expand-to-format cropping with adjustable left/top to right/bottom bias.
- Drag-to-adjust crop bias inside the preview.
- Adaptive high-contrast cut guides with optional halo strokes.
- Always-on preview after image selection, resizable on desktop and stacked on mobile.
- Cancellable local PDF generation with progress reporting.
- One A4 PDF page per tile in top-to-bottom, left-to-right order.
- Best-effort transfer of basic title, author, subject, and keyword metadata.

## Browser Limitations

- Files are selected through the browser; manual filesystem paths are not available.
- The output is downloaded through the browser instead of written to an explicit directory.
- Exact ICC profiles and complete source metadata cannot be preserved after canvas processing.
- PDF and TIFF input are not supported.
- AVIF and BMP decoding depends on browser support.

## Development

Requirements:

- Node.js 22 or newer
- npm

From this directory:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite. The GitHub Pages production base path is
`/gimp-scripts/`.

## Verification

```powershell
npm run lint
npm run typecheck
npm run test:run
npm run build
npm run test:e2e
```

Playwright browsers must be installed once:

```powershell
npx playwright install
```

The existing Python parity suite can be run from `iso216-guidecut`:

```powershell
python -m pytest -q --basetemp .pytest_tmp
```

## GitHub Pages Deployment

The Pages workflow builds this directory and publishes `dist` whenever web app
changes reach `main`. In the GitHub repository settings, set **Pages > Source**
to **GitHub Actions** once. No server or runtime secrets are required.

## Resource Limits

- Maximum compressed input size: 250 MiB.
- Maximum decoded image area: 100 megapixels.
- Exports above 32 pages or inputs above 50 MiB display a large-job warning.

PDF rendering is capped at the pixel dimensions of 300 DPI A4 per page to
bound memory use while retaining print-quality output.
