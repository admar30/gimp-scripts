import { useEffect, useRef, useState } from "react";
import { PreviewCanvas } from "./components/PreviewCanvas";
import {
  buildGridGeometry,
  buildOutputFilename,
  clampBias,
  computeGrid,
  detectOrientation,
  effectiveCrop,
  type GridSelection,
  type TargetFormat,
} from "./core/geometry";
import { decodeImage, FILE_ACCEPT, type DecodedImage } from "./core/image";
import { readPdfMetadata, type PdfMetadata } from "./core/metadata";
import { loadState, saveState } from "./core/persistence";
import { createPdfJob, type PdfJob } from "./pdf/client";
import type { ExportProgress } from "./pdf/protocol";

const FORMAT_DETAILS: Record<TargetFormat, { pages: number; multiple: number }> = {
  A3: { pages: 2, multiple: 2 },
  A2: { pages: 4, multiple: 4 },
  A1: { pages: 8, multiple: 8 },
  A0: { pages: 16, multiple: 16 },
};

function App() {
  const [initialState] = useState(loadState);
  const [file, setFile] = useState<File | null>(null);
  const [decoded, setDecoded] = useState<DecodedImage | null>(null);
  const [metadata, setMetadata] = useState<PdfMetadata>({});
  const [target, setTarget] = useState<TargetFormat>(initialState.target);
  const [customMode, setCustomMode] = useState(false);
  const [customCols, setCustomCols] = useState(2);
  const [customRows, setCustomRows] = useState(2);
  const [expandEnabled, setExpandEnabled] = useState(initialState.expandEnabled);
  const [bias, setBias] = useState(initialState.expandBiasPercent);
  const [splitRatio, setSplitRatio] = useState(initialState.previewSplitRatio);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("Choose an image to begin.");
  const [draggingFile, setDraggingFile] = useState(false);
  const [progress, setProgress] = useState<ExportProgress | null>(null);
  const [job, setJob] = useState<PdfJob | null>(null);
  const [download, setDownload] = useState<{ url: string; name: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const splitDragRef = useRef(false);

  const selection: GridSelection = customMode
    ? { mode: "custom", cols: customCols, rows: customRows }
    : { mode: "preset", target };
  const crop = decoded
    ? effectiveCrop(decoded.width, decoded.height, { enabled: expandEnabled, biasPercent: bias })
    : null;
  const geometry = decoded && crop
    ? buildGridGeometry(crop.rect.x1 - crop.rect.x0, crop.rect.y1 - crop.rect.y0, selection)
    : null;
  const formatDetails = FORMAT_DETAILS[target];
  const pageCount = geometry?.tiles.length ?? (customMode ? customCols * customRows : formatDetails.pages);
  const largeJobWarning = pageCount > 32 || (file?.size ?? 0) > 50 * 1024 * 1024;

  useEffect(() => {
    saveState({
      target,
      expandEnabled,
      expandBiasPercent: bias,
      previewSplitRatio: splitRatio,
    });
  }, [target, expandEnabled, bias, splitRatio]);

  useEffect(() => () => decoded?.close(), [decoded]);
  useEffect(() => () => {
    if (download) URL.revokeObjectURL(download.url);
  }, [download]);

  const clearDownload = () => {
    if (download) URL.revokeObjectURL(download.url);
    setDownload(null);
  };

  const chooseFile = async (nextFile: File) => {
    job?.cancel();
    clearDownload();
    setError("");
    setProgress(null);
    setNotice("Decoding image locally...");
    setExpandEnabled(false);
    setBias(50);
    decoded?.close();
    setDecoded(null);
    setFile(nextFile);
    try {
      const [nextDecoded, nextMetadata] = await Promise.all([
        decodeImage(nextFile),
        readPdfMetadata(nextFile),
      ]);
      setDecoded(nextDecoded);
      setMetadata(nextMetadata);
      setNotice("Image ready. Configure the cuts, preview, then generate the PDF.");
    } catch (cause) {
      setFile(null);
      setMetadata({});
      setError(cause instanceof Error ? cause.message : "Unable to read this image.");
      setNotice("Choose another image.");
    }
  };

  const clearFile = () => {
    job?.cancel();
    decoded?.close();
    clearDownload();
    setFile(null);
    setDecoded(null);
    setMetadata({});
    setProgress(null);
    setError("");
    setNotice("Choose an image to begin.");
  };

  const toggleCustom = (enabled: boolean) => {
    if (enabled && !customMode) {
      const orientation = decoded ? detectOrientation(decoded.width, decoded.height) : "portrait";
      const [cols, rows] = computeGrid(target, orientation);
      setCustomCols(cols);
      setCustomRows(rows);
    }
    setCustomMode(enabled);
  };

  const generate = () => {
    if (!file || !decoded || job) return;
    if (customCols < 1 || customCols > 32 || customRows < 1 || customRows > 32) {
      setError("Custom grid values must be integers from 1 to 32.");
      return;
    }
    clearDownload();
    setError("");
    setNotice("Generating the PDF on this device...");
    const filename = buildOutputFilename(file.name, selection);
    const nextJob = createPdfJob(
      {
        source: file,
        selection,
        expand: { enabled: expandEnabled, biasPercent: bias },
        metadata,
      },
      setProgress,
    );
    setJob(nextJob);
    nextJob.promise
      .then((blob) => {
        setDownload({ url: URL.createObjectURL(blob), name: filename });
        setNotice(`PDF ready: ${filename}`);
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          setNotice("PDF generation cancelled.");
        } else {
          setError(cause instanceof Error ? cause.message : "PDF generation failed.");
          setNotice("The export did not complete.");
        }
      })
      .finally(() => {
        setJob(null);
        setProgress(null);
      });
  };

  const startSplit = (event: React.PointerEvent<HTMLDivElement>) => {
    splitDragRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveSplit = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!splitDragRef.current || !workspaceRef.current) return;
    const bounds = workspaceRef.current.getBoundingClientRect();
    setSplitRatio(Math.max(0.35, Math.min(0.72, (event.clientX - bounds.left) / bounds.width)));
  };
  const endSplit = () => {
    splitDragRef.current = false;
  };

  const progressPercent = progress?.totalPages
    ? Math.round((progress.currentPage / progress.totalPages) * 100)
    : progress
      ? 3
      : 0;

  return (
    <main className="app-shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">ISO 216 poster tiling</p>
          <h1>Guidecut</h1>
        </div>
        <div className="privacy-seal">
          <span className="privacy-dot" />
          Local processing only
        </div>
      </header>

      <div
        className={`workspace ${decoded ? "has-preview" : ""}`}
        ref={workspaceRef}
        style={decoded ? { "--control-ratio": splitRatio } as React.CSSProperties : undefined}
      >
        <section className="control-panel" aria-label="Guidecut controls">
          <div className="intro">
            <p className="step-index">01 / SOURCE</p>
            <h2>Turn one image into printable A4 sections.</h2>
            <p>Select an image, choose its intended sheet size or a custom grid, inspect the cuts, then generate one multi-page PDF.</p>
          </div>

          <div
            className={`drop-zone ${draggingFile ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
            onDragEnter={(event) => { event.preventDefault(); setDraggingFile(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDraggingFile(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDraggingFile(false);
              const dropped = event.dataTransfer.files[0];
              if (dropped) void chooseFile(dropped);
            }}
          >
            <input
              ref={fileInputRef}
              className="visually-hidden"
              type="file"
              accept={FILE_ACCEPT}
              onChange={(event) => {
                const selected = event.target.files?.[0];
                if (selected) void chooseFile(selected);
                event.currentTarget.value = "";
              }}
            />
            {file && decoded ? (
              <>
                <div className="file-mark">IMG</div>
                <div className="file-copy">
                  <strong>{file.name}</strong>
                  <span>
                    {decoded.width.toLocaleString()} x {decoded.height.toLocaleString()} px
                    {" / "}
                    {(file.size / 1024 / 1024).toFixed(1)} MiB
                  </span>
                </div>
                <div className="file-actions">
                  <button className="button button-quiet" type="button" onClick={() => fileInputRef.current?.click()}>
                    Replace
                  </button>
                  <button className="button button-quiet" type="button" onClick={clearFile}>
                    Clear
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="upload-symbol"><span /></div>
                <strong>Drop artwork here</strong>
                <span>JPEG, PNG, WebP, AVIF, GIF or BMP. First frame only.</span>
                <button className="button button-secondary" type="button" onClick={() => fileInputRef.current?.click()}>
                  Choose image
                </button>
              </>
            )}
          </div>

          <div className="configuration">
            <p className="step-index">02 / CUT MAP</p>
            <div className="control-grid">
              <div className="field-group">
                <div className="field-heading">
                  <label htmlFor="target-format">Target format</label>
                  <span className="tooltip-anchor" tabIndex={0} aria-label="Target format details">
                    ?
                    <span className="tooltip">
                      <strong>{target}</strong>
                      <span>{formatDetails.pages} tiles / pages</span>
                      <span>{formatDetails.multiple}x the area of A4</span>
                    </span>
                  </span>
                </div>
                <select
                  id="target-format"
                  value={target}
                  disabled={customMode}
                  onChange={(event) => setTarget(event.target.value as TargetFormat)}
                >
                  <option>A3</option>
                  <option>A2</option>
                  <option>A1</option>
                  <option>A0</option>
                </select>
              </div>

              <label className="toggle-card">
                <input type="checkbox" checked={customMode} onChange={(event) => toggleCustom(event.target.checked)} />
                <span className="switch" />
                <span>
                  <strong>Custom grid</strong>
                  <small>Set columns and rows directly</small>
                </span>
              </label>

              {customMode && (
                <div className="custom-fields">
                  <label>
                    Columns
                    <input
                      aria-label="Columns"
                      type="number"
                      min="1"
                      max="32"
                      value={customCols}
                      onChange={(event) => setCustomCols(Number(event.target.value))}
                    />
                  </label>
                  <span>x</span>
                  <label>
                    Rows
                    <input
                      aria-label="Rows"
                      type="number"
                      min="1"
                      max="32"
                      value={customRows}
                      onChange={(event) => setCustomRows(Number(event.target.value))}
                    />
                  </label>
                </div>
              )}

              <label className="toggle-card expand-card">
                <input
                  type="checkbox"
                  checked={expandEnabled}
                  onChange={(event) => setExpandEnabled(event.target.checked)}
                />
                <span className="switch" />
                <span>
                  <strong>Expand to format</strong>
                  <small>Crop dead space to the ISO ratio</small>
                </span>
                {expandEnabled && (
                  <div className="bias-control">
                    <input
                      aria-label="Trim bias"
                      type="range"
                      min="0"
                      max="100"
                      step="0.5"
                      disabled={!crop?.axis}
                      value={bias}
                      onChange={(event) => setBias(clampBias(event.target.value))}
                    />
                    <output>{bias.toFixed(0)}%</output>
                  </div>
                )}
              </label>

            </div>
          </div>

          <div className="export-card">
            <div>
              <p className="step-index">03 / OUTPUT</p>
              <h3>{pageCount.toLocaleString()} A4 {pageCount === 1 ? "page" : "pages"}</h3>
              <p>{notice}</p>
            </div>
            {error && <div className="message error-message" role="alert">{error}</div>}
            {largeJobWarning && (
              <div className="message warning-message">
                Large export: generation may take several minutes and use significant memory.
              </div>
            )}
            <div className="metadata-note">
              Color is retained visually. Browser canvas export cannot preserve the exact source ICC profile or every metadata field.
            </div>
            {progress && (
              <div className="progress-block" aria-live="polite">
                <div>
                  <span>{progress.phase === "decode" ? "Decoding" : progress.phase === "assemble" ? "Assembling PDF" : "Rendering pages"}</span>
                  <span>{progressPercent}%</span>
                </div>
                <progress value={progressPercent} max="100" />
              </div>
            )}
            <div className="export-actions">
              {job ? (
                <button className="button button-danger" type="button" onClick={() => job.cancel()}>
                  Cancel export
                </button>
              ) : (
                <button className="button button-primary" type="button" disabled={!decoded} onClick={generate}>
                  Generate PDF
                </button>
              )}
              {download && (
                <a className="button button-download" href={download.url} download={download.name}>
                  Download PDF
                </a>
              )}
            </div>
          </div>
        </section>

        {decoded && (
          <>
            <div
              className="splitter"
              role="separator"
              aria-label="Resize preview"
              aria-orientation="vertical"
              onPointerDown={startSplit}
              onPointerMove={moveSplit}
              onPointerUp={endSplit}
              onPointerCancel={endSplit}
            />
            <aside className="preview-panel">
              <div className="preview-header">
                <div>
                  <p className="step-index">LIVE PROOF</p>
                  <h2>Cut preview</h2>
                </div>
                <span>{geometry?.cols} x {geometry?.rows} grid</span>
              </div>
              <PreviewCanvas
                image={decoded}
                selection={selection}
                expand={{ enabled: expandEnabled, biasPercent: bias }}
                onBiasChange={(value) => setBias(clampBias(value))}
              />
            </aside>
          </>
        )}
      </div>

      <footer>
        <span>Files stay on this device.</span>
        <a href="https://github.com/admar30/gimp-scripts">Source on GitHub</a>
      </footer>
    </main>
  );
}

export default App;
