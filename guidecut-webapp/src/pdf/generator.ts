import { jsPDF } from "jspdf";
import { buildGridGeometry, effectiveCrop } from "../core/geometry";
import type { ExportOptions, ExportProgress } from "./protocol";

const A4_PORTRAIT_PX = { width: 2480, height: 3508 };
const A4_PORTRAIT_MM = { width: 210, height: 297 };

type ExportCanvas = OffscreenCanvas | HTMLCanvasElement;
type ExportContext = OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;

function createCanvas(width: number, height: number): ExportCanvas {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(width, height);
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }
  throw new Error("This browser cannot create an export canvas.");
}

async function canvasToBytes(canvas: ExportCanvas, type: "image/png" | "image/jpeg"): Promise<Uint8Array> {
  let blob: Blob;
  if ("convertToBlob" in canvas) {
    blob = await canvas.convertToBlob({ type, quality: 0.94 });
  } else {
    blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (value) => (value ? resolve(value) : reject(new Error("Unable to encode an export page."))),
        type,
        0.94,
      );
    });
  }
  return new Uint8Array(await blob.arrayBuffer());
}

function hasTransparency(context: ExportContext, width: number, height: number): boolean {
  const stripeHeight = 64;
  for (let y = 0; y < height; y += stripeHeight) {
    const data = context.getImageData(0, y, width, Math.min(stripeHeight, height - y)).data;
    for (let index = 3; index < data.length; index += 4) {
      if (data[index] < 255) return true;
    }
  }
  return false;
}

function checkCancelled(isCancelled: () => boolean): void {
  if (isCancelled()) throw new DOMException("PDF generation cancelled.", "AbortError");
}

export function resolvePageLayout(tileWidth: number, tileHeight: number) {
  const landscape = tileWidth >= tileHeight;
  const pageWidth = landscape ? A4_PORTRAIT_MM.height : A4_PORTRAIT_MM.width;
  const pageHeight = landscape ? A4_PORTRAIT_MM.width : A4_PORTRAIT_MM.height;
  const fitScale = Math.min(pageWidth / tileWidth, pageHeight / tileHeight);
  const drawWidth = tileWidth * fitScale;
  const drawHeight = tileHeight * fitScale;
  return {
    orientation: landscape ? "landscape" as const : "portrait" as const,
    pageWidth,
    pageHeight,
    drawWidth,
    drawHeight,
    x: (pageWidth - drawWidth) / 2,
    y: (pageHeight - drawHeight) / 2,
  };
}

export async function generatePdfBytes(
  options: ExportOptions,
  onProgress: (progress: ExportProgress) => void,
  isCancelled: () => boolean,
): Promise<Uint8Array> {
  onProgress({ phase: "decode", currentPage: 0, totalPages: 0 });
  const bitmap = await createImageBitmap(options.source, { imageOrientation: "from-image" });
  try {
    checkCancelled(isCancelled);
    const crop = effectiveCrop(bitmap.width, bitmap.height, options.expand);
    const workingWidth = crop.rect.x1 - crop.rect.x0;
    const workingHeight = crop.rect.y1 - crop.rect.y0;
    const geometry = buildGridGeometry(workingWidth, workingHeight, options.selection);
    const totalPages = geometry.tiles.length;
    let pdf: jsPDF | null = null;

    for (let index = 0; index < totalPages; index += 1) {
      checkCancelled(isCancelled);
      onProgress({ phase: "render", currentPage: index, totalPages });
      const tile = geometry.tiles[index];
      const tileWidth = tile.x1 - tile.x0;
      const tileHeight = tile.y1 - tile.y0;
      const layout = resolvePageLayout(tileWidth, tileHeight);
      const landscape = layout.orientation === "landscape";
      const pagePixelWidth = landscape ? A4_PORTRAIT_PX.height : A4_PORTRAIT_PX.width;
      const pagePixelHeight = landscape ? A4_PORTRAIT_PX.width : A4_PORTRAIT_PX.height;
      const scale = Math.min(1, pagePixelWidth / tileWidth, pagePixelHeight / tileHeight);
      const renderWidth = Math.max(1, Math.round(tileWidth * scale));
      const renderHeight = Math.max(1, Math.round(tileHeight * scale));
      const canvas = createCanvas(renderWidth, renderHeight);
      const context = canvas.getContext("2d", { alpha: true });
      if (!context) throw new Error("Unable to initialize the export canvas.");
      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      context.clearRect(0, 0, renderWidth, renderHeight);
      context.drawImage(
        bitmap,
        crop.rect.x0 + tile.x0,
        crop.rect.y0 + tile.y0,
        tileWidth,
        tileHeight,
        0,
        0,
        renderWidth,
        renderHeight,
      );

      const transparent = hasTransparency(context, renderWidth, renderHeight);
      const mime = transparent ? "image/png" : "image/jpeg";
      const pageBytes = await canvasToBytes(canvas, mime);
      checkCancelled(isCancelled);

      const orientation = layout.orientation;
      if (!pdf) {
        pdf = new jsPDF({ orientation, unit: "mm", format: "a4", compress: true });
        pdf.setProperties({
          title: options.metadata.title ?? options.source.name,
          author: options.metadata.author ?? "",
          subject: options.metadata.subject ?? "Guidecut A4 tile export",
          keywords: options.metadata.keywords?.join(", ") ?? "",
          creator: "Guidecut Web App",
        });
      } else {
        pdf.addPage("a4", orientation);
      }

      pdf.addImage(
        pageBytes,
        transparent ? "PNG" : "JPEG",
        layout.x,
        layout.y,
        layout.drawWidth,
        layout.drawHeight,
        undefined,
        transparent ? undefined : "MEDIUM",
      );
      onProgress({ phase: "render", currentPage: index + 1, totalPages });
    }

    if (!pdf) throw new Error("No PDF pages were generated.");
    checkCancelled(isCancelled);
    onProgress({ phase: "assemble", currentPage: totalPages, totalPages });
    return new Uint8Array(pdf.output("arraybuffer"));
  } finally {
    bitmap.close();
  }
}
