import type { ExpandOptions, GridSelection } from "../core/geometry";
import type { PdfMetadata } from "../core/metadata";

export interface ExportOptions {
  source: File;
  selection: GridSelection;
  expand: ExpandOptions;
  metadata: PdfMetadata;
}

export type ExportPhase = "decode" | "render" | "assemble";

export interface ExportProgress {
  phase: ExportPhase;
  currentPage: number;
  totalPages: number;
}

export type PdfWorkerRequest =
  | { type: "generate"; id: string; options: ExportOptions }
  | { type: "cancel"; id: string };

export type PdfWorkerResponse =
  | { type: "progress"; id: string; progress: ExportProgress }
  | { type: "complete"; id: string; data: ArrayBuffer }
  | { type: "cancelled"; id: string }
  | { type: "error"; id: string; message: string };
