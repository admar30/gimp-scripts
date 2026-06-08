import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_STATE, loadState, sanitizeState, saveState } from "./persistence";

describe("web UI persistence", () => {
  beforeEach(() => localStorage.clear());

  it("sanitizes invalid state", () => {
    expect(sanitizeState({ target: "A9", expandBiasPercent: 150, previewSplitRatio: 0.1 }))
      .toEqual({ ...DEFAULT_STATE, expandBiasPercent: 100 });
  });

  it("round-trips persisted settings without a file or preview state", () => {
    saveState({ target: "A1", expandEnabled: true, expandBiasPercent: 65, previewSplitRatio: 0.62 });
    expect(loadState()).toEqual({
      target: "A1",
      expandEnabled: true,
      expandBiasPercent: 65,
      previewSplitRatio: 0.62,
    });
  });
});
