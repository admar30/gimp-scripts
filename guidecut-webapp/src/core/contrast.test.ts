import { describe, expect, it } from "vitest";
import { chooseGuideStyle, contrastRatio, relativeLuminance } from "./contrast";

describe("adaptive guide contrast", () => {
  it("prefers white over dark content and black over light content", () => {
    expect(chooseGuideStyle([0.01, 0.02]).stroke).toBe("#FFFFFF");
    expect(chooseGuideStyle([0.94, 0.98]).stroke).toBe("#111111");
  });

  it("adds a halo for mixed low-worst-case contrast", () => {
    const samples = [
      relativeLuminance([15, 143, 132]),
      relativeLuminance([255, 255, 255]),
      relativeLuminance([17, 17, 17]),
      relativeLuminance([255, 213, 74]),
      relativeLuminance([255, 77, 109]),
    ];
    const style = chooseGuideStyle(samples);
    expect(style.halo).not.toBeNull();
    expect(style.halo).not.toBe(style.stroke);
  });

  it("calculates WCAG contrast ratios", () => {
    expect(contrastRatio(1, 0)).toBe(21);
  });
});
