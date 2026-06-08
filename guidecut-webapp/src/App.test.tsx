import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const closeImage = vi.fn();

vi.mock("./core/image", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./core/image")>();
  return {
    ...actual,
    decodeImage: vi.fn(async () => ({
      source: {},
      width: 1200,
      height: 800,
      close: closeImage,
    })),
  };
});

vi.mock("./core/metadata", () => ({
  readPdfMetadata: vi.fn(async () => ({ title: "Fixture map" })),
}));

vi.mock("./components/PreviewCanvas", () => ({
  PreviewCanvas: () => <div aria-label="Cut preview canvas" />,
}));

describe("Guidecut web UI", () => {
  beforeEach(() => {
    localStorage.clear();
    closeImage.mockClear();
  });

  it("shows the initial workflow and preset details", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Guidecut" })).toBeInTheDocument();
    expect(screen.getByLabelText("Target format")).toHaveValue("A2");
    expect(screen.getByRole("button", { name: "Generate PDF" })).toBeDisabled();
    expect(screen.getByText(/Files stay on this device/)).toBeInTheDocument();
  });

  it("reveals custom grid inputs and preserves page counts", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("checkbox", { name: /Custom grid/i }));
    expect(screen.getByLabelText("Columns")).toHaveValue(2);
    expect(screen.getByLabelText("Rows")).toHaveValue(2);
    await user.clear(screen.getByLabelText("Columns"));
    await user.type(screen.getByLabelText("Columns"), "3");
    await user.clear(screen.getByLabelText("Rows"));
    await user.type(screen.getByLabelText("Rows"), "4");
    expect(screen.getByRole("heading", { name: "12 A4 pages" })).toBeInTheDocument();
  });

  it("accepts a local file and exposes preview without persisting the file", async () => {
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["pixels"], "arena.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("arena.png")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Cut preview" })).toBeInTheDocument();
    expect(screen.queryByText("Show preview")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate PDF" })).toBeEnabled();
    expect(localStorage.getItem("guidecut-webapp-state-v1")).not.toContain("arena.png");
  });
});
