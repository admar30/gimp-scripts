export const ISO216_ASPECT_RATIO = Math.SQRT2;
export const CUSTOM_GRID_MIN = 1;
export const CUSTOM_GRID_MAX = 32;
export const DEFAULT_EXPAND_BIAS_PERCENT = 50;

export const TARGET_SPLITS = {
  A3: 1,
  A2: 2,
  A1: 3,
  A0: 4,
} as const;

export type TargetFormat = keyof typeof TARGET_SPLITS;
export type Orientation = "portrait" | "landscape" | "square";
export type ExcessAxis = "x" | "y" | null;

export interface Rect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export type GridSelection =
  | { mode: "preset"; target: TargetFormat }
  | { mode: "custom"; cols: number; rows: number };

export interface ExpandOptions {
  enabled: boolean;
  biasPercent: number;
}

export interface CropResult {
  rect: Rect;
  axis: ExcessAxis;
  excessPx: number;
  leadingTrimPx: number;
  trailingTrimPx: number;
  biasPercent: number;
}

export interface GridGeometry {
  cols: number;
  rows: number;
  verticalGuides: number[];
  horizontalGuides: number[];
  tiles: Rect[];
}

export function detectOrientation(width: number, height: number): Orientation {
  if (width > height) return "landscape";
  if (height > width) return "portrait";
  return "square";
}

export function validateCustomDimension(value: number): number {
  if (!Number.isInteger(value) || value < CUSTOM_GRID_MIN || value > CUSTOM_GRID_MAX) {
    throw new Error(`Grid dimensions must be integers from ${CUSTOM_GRID_MIN} to ${CUSTOM_GRID_MAX}.`);
  }
  return value;
}

export function computeGrid(target: TargetFormat, orientation: Orientation): [number, number] {
  let cols = 1;
  let rows = 1;
  let axis: "x" | "y" = orientation === "landscape" ? "x" : "y";
  for (let index = 0; index < TARGET_SPLITS[target]; index += 1) {
    if (axis === "x") {
      cols *= 2;
      axis = "y";
    } else {
      rows *= 2;
      axis = "x";
    }
  }
  return [cols, rows];
}

export function resolveGrid(selection: GridSelection, width: number, height: number): [number, number] {
  if (selection.mode === "custom") {
    return [validateCustomDimension(selection.cols), validateCustomDimension(selection.rows)];
  }
  return computeGrid(selection.target, detectOrientation(width, height));
}

export function partitionEdges(size: number, parts: number): number[] {
  return Array.from({ length: parts + 1 }, (_, index) => Math.round((index * size) / parts));
}

export function computeGuides(
  width: number,
  height: number,
  cols: number,
  rows: number,
): [number[], number[]] {
  const vertical = Array.from({ length: cols - 1 }, (_, index) =>
    Math.round(((index + 1) * width) / cols),
  );
  const horizontal = Array.from({ length: rows - 1 }, (_, index) =>
    Math.round(((index + 1) * height) / rows),
  );
  return [vertical, horizontal];
}

export function computeTileCrop(
  col: number,
  row: number,
  cols: number,
  rows: number,
  width: number,
  height: number,
): Rect {
  const xEdges = partitionEdges(width, cols);
  const yEdges = partitionEdges(height, rows);
  return { x0: xEdges[col], y0: yEdges[row], x1: xEdges[col + 1], y1: yEdges[row + 1] };
}

export function orderedTileCoordinates(cols: number, rows: number): Array<[number, number]> {
  return Array.from({ length: rows }, (_, row) =>
    Array.from({ length: cols }, (_, col) => [col, row] as [number, number]),
  ).flat();
}

export function buildGridGeometry(
  width: number,
  height: number,
  selection: GridSelection,
): GridGeometry {
  const [cols, rows] = resolveGrid(selection, width, height);
  const [verticalGuides, horizontalGuides] = computeGuides(width, height, cols, rows);
  return {
    cols,
    rows,
    verticalGuides,
    horizontalGuides,
    tiles: orderedTileCoordinates(cols, rows).map(([col, row]) =>
      computeTileCrop(col, row, cols, rows, width, height),
    ),
  };
}

export function clampBias(value: unknown, fallback = DEFAULT_EXPAND_BIAS_PERCENT): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(100, parsed));
}

export function isNearIso216Ratio(width: number, height: number, tolerance = 0.03): boolean {
  if (width <= 0 || height <= 0) return false;
  return Math.abs(Math.max(width, height) / Math.min(width, height) - ISO216_ASPECT_RATIO) <= tolerance;
}

export function computeExpandCrop(width: number, height: number, biasValue: unknown): CropResult {
  if (width <= 0 || height <= 0) throw new Error("Image dimensions must be positive.");
  const orientation = detectOrientation(width, height);
  const targetRatio = orientation === "landscape" ? ISO216_ASPECT_RATIO : 1 / ISO216_ASPECT_RATIO;
  const sourceRatio = width / height;
  const biasPercent = clampBias(biasValue);
  const fullRect = { x0: 0, y0: 0, x1: width, y1: height };

  if (
    isNearIso216Ratio(width, height, 0.001) ||
    Math.abs(sourceRatio - targetRatio) <= 1e-12
  ) {
    return {
      rect: fullRect,
      axis: null,
      excessPx: 0,
      leadingTrimPx: 0,
      trailingTrimPx: 0,
      biasPercent,
    };
  }

  if (sourceRatio > targetRatio) {
    const retainedWidth = Math.max(1, Math.min(width, Math.round(height * targetRatio)));
    const excessPx = Math.max(0, width - retainedWidth);
    const leadingTrimPx = Math.max(0, Math.min(excessPx, Math.round(excessPx * (biasPercent / 100))));
    const trailingTrimPx = excessPx - leadingTrimPx;
    return {
      rect: { x0: leadingTrimPx, y0: 0, x1: width - trailingTrimPx, y1: height },
      axis: excessPx ? "x" : null,
      excessPx,
      leadingTrimPx,
      trailingTrimPx,
      biasPercent,
    };
  }

  const retainedHeight = Math.max(1, Math.min(height, Math.round(width / targetRatio)));
  const excessPx = Math.max(0, height - retainedHeight);
  const leadingTrimPx = Math.max(0, Math.min(excessPx, Math.round(excessPx * (biasPercent / 100))));
  const trailingTrimPx = excessPx - leadingTrimPx;
  return {
    rect: { x0: 0, y0: leadingTrimPx, x1: width, y1: height - trailingTrimPx },
    axis: excessPx ? "y" : null,
    excessPx,
    leadingTrimPx,
    trailingTrimPx,
    biasPercent,
  };
}

export function effectiveCrop(width: number, height: number, options: ExpandOptions): CropResult {
  if (options.enabled) return computeExpandCrop(width, height, options.biasPercent);
  return {
    rect: { x0: 0, y0: 0, x1: width, y1: height },
    axis: null,
    excessPx: 0,
    leadingTrimPx: 0,
    trailingTrimPx: 0,
    biasPercent: clampBias(options.biasPercent),
  };
}

export function selectionToken(selection: GridSelection): string {
  return selection.mode === "preset"
    ? selection.target.toLowerCase()
    : `grid-${selection.cols}x${selection.rows}`;
}

export function buildOutputFilename(
  sourceName: string,
  selection: GridSelection,
  date = new Date(),
): string {
  const stem = sourceName.replace(/\.[^.]+$/, "") || "guidecut";
  const pad = (value: number) => String(value).padStart(2, "0");
  const stamp =
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-` +
    `${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
  return `${stem}-guidecut-${selectionToken(selection)}-${stamp}.pdf`;
}
