import { expect, test } from "@playwright/test";
import { PDFDocument } from "pdf-lib";

const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAACgAAAA8CAIAAACb22+3AAAAZUlEQVR4nO3NMQHDQADEsI/RFGdBFG/XHAFniEVA1+f7O0/gkfUUizCzu2INXrWKNXjVKtbgVatYg1etYg1etYo1eNUq1uBVq1iDV61iDV61ijV41SrW4FWrWINXrWINXnVeHv8BNHQBuNw2mbQAAAAASUVORK5CYII=";

test("uploads locally, previews guides, and downloads a four-page A2 PDF", async ({ page }, testInfo) => {
  const outboundRequests: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (/^https?:/.test(url) && !url.startsWith("http://127.0.0.1:4173")) {
      outboundRequests.push(url);
    }
  });

  const response = await page.goto("/gimp-scripts/");
  expect(response?.status()).toBe(200);
  await page.locator('input[type="file"]').setInputFiles({
    name: "fixture.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_BASE64, "base64"),
  });
  await expect(page.getByText("fixture.png")).toBeVisible();
  await page.getByText("Expand to format", { exact: true }).click();
  const bias = page.getByLabel("Trim bias");
  await expect(bias).toHaveValue("50");
  await expect(page.getByRole("heading", { name: "Cut preview" })).toBeVisible();
  await expect(page.getByText("Show preview", { exact: true })).toHaveCount(0);
  if (testInfo.project.name === "mobile") {
    await bias.fill("75");
    await expect(bias).toHaveValue("75");
    await expect(page.getByText("Vertical trim 75%")).toBeVisible();
  } else {
    const previewCanvas = page.getByLabel("Cut preview");
    const bounds = await previewCanvas.boundingBox();
    await page.mouse.move(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
    await page.mouse.down();
    await page.mouse.move(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height * 0.75);
    await page.mouse.up();
    expect(Number(await bias.inputValue())).toBeGreaterThan(50);
  }

  await page.getByRole("button", { name: "Generate PDF" }).click();
  const link = page.getByRole("link", { name: "Download PDF" });
  await expect(link).toBeVisible({ timeout: 30_000 });
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^fixture-guidecut-a2-\d{8}-\d{6}\.pdf$/);

  const path = await download.path();
  expect(path).not.toBeNull();
  const bytes = await (await import("node:fs/promises")).readFile(path!);
  const pdf = await PDFDocument.load(bytes);
  expect(pdf.getPageCount()).toBe(4);
  for (const pdfPage of pdf.getPages()) {
    const { width, height } = pdfPage.getSize();
    expect(Math.min(width, height)).toBeCloseTo(595.28, 0);
    expect(Math.max(width, height)).toBeCloseTo(841.89, 0);
  }
  expect(outboundRequests).toEqual([]);
});

test("stacks the preview below controls on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const response = await page.goto("/gimp-scripts/");
  expect(response?.status()).toBe(200);
  await page.locator('input[type="file"]').setInputFiles({
    name: "mobile.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_BASE64, "base64"),
  });
  const controls = page.locator(".control-panel");
  const preview = page.locator(".preview-panel");
  await expect(preview).toBeVisible();
  const controlBox = await controls.boundingBox();
  const previewBox = await preview.boundingBox();
  expect(previewBox!.y).toBeGreaterThanOrEqual(controlBox!.y + controlBox!.height - 2);
});
