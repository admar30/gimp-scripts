import { describe, expect, it } from "vitest";
import { resolvePageLayout } from "./generator";

describe("A4 PDF page layout", () => {
  it("uses portrait A4 for portrait tiles", () => {
    const layout = resolvePageLayout(1000, 1414);
    expect(layout.orientation).toBe("portrait");
    expect(layout.pageWidth).toBe(210);
    expect(layout.pageHeight).toBe(297);
    expect(layout.x).toBeCloseTo(0, 1);
  });

  it("uses landscape A4 and contains nonstandard tiles without distortion", () => {
    const layout = resolvePageLayout(1600, 900);
    expect(layout.orientation).toBe("landscape");
    expect(layout.pageWidth).toBe(297);
    expect(layout.pageHeight).toBe(210);
    expect(layout.drawWidth / layout.drawHeight).toBeCloseTo(1600 / 900);
    expect(layout.drawWidth).toBeLessThanOrEqual(layout.pageWidth);
    expect(layout.drawHeight).toBeLessThanOrEqual(layout.pageHeight);
  });
});
