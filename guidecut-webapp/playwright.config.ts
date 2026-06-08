import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  workers: 2,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:4173/gimp-scripts/",
    trace: "on-first-retry",
  },
  webServer: process.env.GUIDECUT_E2E_EXTERNAL
    ? undefined
    : {
        command: "npm run build && node node_modules/vite/bin/vite.js preview --host 127.0.0.1",
        url: "http://127.0.0.1:4173/gimp-scripts/",
        reuseExistingServer: !process.env.CI,
      },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
  ],
});
