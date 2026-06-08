import type { ExportOptions, ExportProgress, PdfWorkerResponse } from "./protocol";

export interface PdfJob {
  promise: Promise<Blob>;
  cancel: () => void;
}

export function createPdfJob(
  options: ExportOptions,
  onProgress: (progress: ExportProgress) => void,
): PdfJob {
  const id = crypto.randomUUID();
  let worker: Worker | null = null;
  let cancelled = false;
  let rejectJob: ((reason?: unknown) => void) | null = null;

  const fallback = async (): Promise<Blob> => {
    const { generatePdfBytes } = await import("./generator");
    const bytes = await generatePdfBytes(options, onProgress, () => cancelled);
    if (cancelled) throw new DOMException("PDF generation cancelled.", "AbortError");
    const data = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
    return new Blob([data], { type: "application/pdf" });
  };

  let promise: Promise<Blob>;
  try {
    worker = new Worker(new URL("./pdf.worker.ts", import.meta.url), { type: "module" });
    promise = new Promise<Blob>((resolve, reject) => {
      rejectJob = reject;
      if (!worker) {
        fallback().then(resolve, reject);
        return;
      }
      worker.onmessage = (event: MessageEvent<PdfWorkerResponse>) => {
        const response = event.data;
        if (response.id !== id) return;
        if (response.type === "progress") onProgress(response.progress);
        if (response.type === "complete") {
          worker?.terminate();
          worker = null;
          rejectJob = null;
          resolve(new Blob([response.data], { type: "application/pdf" }));
        }
        if (response.type === "cancelled") {
          worker?.terminate();
          worker = null;
          reject(new DOMException("PDF generation cancelled.", "AbortError"));
        }
        if (response.type === "error") {
          worker?.terminate();
          worker = null;
          if (response.message.includes("export canvas")) {
            rejectJob = null;
            fallback().then(resolve, reject);
          } else {
            reject(new Error(response.message));
          }
        }
      };
      worker.onerror = () => {
        worker?.terminate();
        worker = null;
        if (cancelled) {
          reject(new DOMException("PDF generation cancelled.", "AbortError"));
        } else {
          rejectJob = null;
          fallback().then(resolve, reject);
        }
      };
      worker.postMessage({ type: "generate", id, options });
    });
  } catch {
    promise = fallback();
  }

  return {
    promise,
    cancel: () => {
      cancelled = true;
      worker?.postMessage({ type: "cancel", id });
      worker?.terminate();
      worker = null;
      rejectJob?.(new DOMException("PDF generation cancelled.", "AbortError"));
      rejectJob = null;
    },
  };
}
