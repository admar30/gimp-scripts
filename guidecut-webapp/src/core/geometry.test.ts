import { describe, expect, it } from "vitest";
import fixtures from "../../fixtures/geometry.json";
import {
  buildGridGeometry,
  buildOutputFilename,
  clampBias,
  computeExpandCrop,
  computeGrid,
  computeGuides,
  computeTileCrop,
  detectOrientation,
  orderedTileCoordinates,
  validateCustomDimension,
  type Orientation,
  type TargetFormat,
} from "./geometry";

describe("Guidecut geometry parity", () => {
  it.each(fixtures.orientations)("detects $expected orientation", ({ width, height, expected }) => {
    expect(detectOrientation(width, height)).toBe(expected);
  });

  it.each(fixtures.presetGrids)(
    "maps $target $orientation to $cols x $rows",
    ({ target, orientation, cols, rows }) => {
      expect(computeGrid(target as TargetFormat, orientation as Orientation)).toEqual([cols, rows]);
    },
  );

  it("uses the same rounded guide positions as Python", () => {
    const value = fixtures.guides;
    expect(computeGuides(value.width, value.height, value.cols, value.rows)).toEqual([
      value.vertical,
      value.horizontal,
    ]);
  });

  it("partitions fractional pixels without gaps", () => {
    const tiles = buildGridGeometry(10, 7, { mode: "custom", cols: 4, rows: 2 }).tiles;
    expect(tiles[0]).toEqual({ x0: 0, y0: 0, x1: 3, y1: 4 });
    expect(tiles.at(-1)).toEqual({ x0: 8, y0: 4, x1: 10, y1: 7 });
  });

  it("orders pages top-to-bottom then left-to-right", () => {
    expect(orderedTileCoordinates(2, 2)).toEqual([[0, 0], [1, 0], [0, 1], [1, 1]]);
    expect(computeTileCrop(1, 1, 2, 2, 100, 80)).toEqual({ x0: 50, y0: 40, x1: 100, y1: 80 });
  });

  it.each(fixtures.cropCases)("matches crop case %#", (value) => {
    const crop = computeExpandCrop(value.width, value.height, value.bias);
    expect(crop.axis).toBe(value.axis);
    if ("leading" in value) expect(crop.leadingTrimPx).toBe(value.leading);
    if ("trailing" in value) expect(crop.trailingTrimPx).toBe(value.trailing);
    if ("excess" in value) expect(crop.excessPx).toBe(value.excess);
    if (value.bias === 50 && crop.excessPx) {
      expect(Math.abs(crop.leadingTrimPx - crop.trailingTrimPx)).toBeLessThanOrEqual(1);
    }
  });

  it("clamps bias and validates custom dimensions", () => {
    expect(clampBias(-4)).toBe(0);
    expect(clampBias(120)).toBe(100);
    expect(clampBias("bad", 42)).toBe(42);
    expect(validateCustomDimension(32)).toBe(32);
    expect(() => validateCustomDimension(33)).toThrow();
  });

  it("builds deterministic local-time filenames", () => {
    const date = new Date(2026, 2, 21, 12, 34, 56);
    expect(buildOutputFilename("poster.png", { mode: "preset", target: "A2" }, date))
      .toBe("poster-guidecut-a2-20260321-123456.pdf");
    expect(buildOutputFilename("poster.png", { mode: "custom", cols: 3, rows: 4 }, date))
      .toBe("poster-guidecut-grid-3x4-20260321-123456.pdf");
  });
});
