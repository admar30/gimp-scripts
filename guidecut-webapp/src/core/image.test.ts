import { describe, expect, it } from "vitest";
import { validateImageFile } from "./image";

describe("input validation", () => {
  it("accepts supported raster extensions", () => {
    expect(() => validateImageFile(new File(["x"], "map.avif", { type: "image/avif" }))).not.toThrow();
  });

  it("rejects SVG and unknown formats", () => {
    expect(() => validateImageFile(new File(["x"], "map.svg", { type: "image/svg+xml" }))).toThrow(/SVG/);
    expect(() => validateImageFile(new File(["x"], "map.tiff", { type: "image/tiff" }))).toThrow(/Unsupported/);
  });
});
