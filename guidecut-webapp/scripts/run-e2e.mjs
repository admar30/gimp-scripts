import { spawn } from "node:child_process";
import process from "node:process";

const host = "127.0.0.1";
const port = "4173";
const url = `http://${host}:${port}/gimp-scripts/`;
const server = spawn(
  process.execPath,
  ["node_modules/vite/bin/vite.js", "preview", "--host", host, "--port", port],
  { stdio: "inherit" },
);

async function waitForServer() {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

let exitCode;
try {
  await waitForServer();
  const playwright = spawn(
    process.execPath,
    ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)],
    {
      stdio: "inherit",
      env: { ...process.env, GUIDECUT_E2E_EXTERNAL: "1" },
    },
  );
  exitCode = await new Promise((resolve) => playwright.on("exit", (code) => resolve(code ?? 1)));
} finally {
  server.kill();
}

process.exit(exitCode ?? 1);
