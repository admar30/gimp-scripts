import { clampBias, type TargetFormat } from "./geometry";

const STORAGE_KEY = "guidecut-webapp-state-v1";

export interface PersistedState {
  target: TargetFormat;
  expandEnabled: boolean;
  expandBiasPercent: number;
  previewSplitRatio: number;
}

export const DEFAULT_STATE: PersistedState = {
  target: "A2",
  expandEnabled: false,
  expandBiasPercent: 50,
  previewSplitRatio: 0.56,
};

export function sanitizeState(value: unknown): PersistedState {
  if (!value || typeof value !== "object") return { ...DEFAULT_STATE };
  const raw = value as Partial<PersistedState>;
  const target = ["A3", "A2", "A1", "A0"].includes(String(raw.target))
    ? (raw.target as TargetFormat)
    : DEFAULT_STATE.target;
  const ratio = Number(raw.previewSplitRatio);
  return {
    target,
    expandEnabled: raw.expandEnabled === true,
    expandBiasPercent: clampBias(raw.expandBiasPercent),
    previewSplitRatio:
      Number.isFinite(ratio) && ratio >= 0.35 && ratio <= 0.72
        ? ratio
        : DEFAULT_STATE.previewSplitRatio,
  };
}

export function loadState(): PersistedState {
  try {
    return sanitizeState(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null"));
  } catch {
    return { ...DEFAULT_STATE };
  }
}

export function saveState(state: PersistedState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeState(state)));
}
