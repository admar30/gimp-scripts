/// <reference lib="webworker" />

import { generatePdfBytes } from "./generator";
import type { PdfWorkerRequest, PdfWorkerResponse } from "./protocol";

const cancelled = new Set<string>();

self.onmessage = async (event: MessageEvent<PdfWorkerRequest>) => {
  const request = event.data;
  if (request.type === "cancel") {
    cancelled.add(request.id);
    return;
  }

  const send = (message: PdfWorkerResponse, transfer: Transferable[] = []) =>
    self.postMessage(message, { transfer });

  try {
    const bytes = await generatePdfBytes(
      request.options,
      (progress) => send({ type: "progress", id: request.id, progress }),
      () => cancelled.has(request.id),
    );
    if (cancelled.has(request.id)) {
      send({ type: "cancelled", id: request.id });
    } else {
      const data = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
      send({ type: "complete", id: request.id, data }, [data]);
    }
  } catch (error) {
    if (cancelled.has(request.id) || (error instanceof DOMException && error.name === "AbortError")) {
      send({ type: "cancelled", id: request.id });
    } else {
      send({
        type: "error",
        id: request.id,
        message: error instanceof Error ? error.message : "PDF generation failed.",
      });
    }
  } finally {
    cancelled.delete(request.id);
  }
};
