import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const rootDir = path.resolve(__dirname, "..", "..");
const pythonBin = process.env.PYTHON_BIN ?? ".venv/bin/python";
const apiPort = process.env.PLAYWRIGHT_API_PORT ?? "8100";
const webPort = process.env.PLAYWRIGHT_WEB_PORT ?? "3100";
const apiBase = `http://127.0.0.1:${apiPort}`;
const webBase = `http://127.0.0.1:${webPort}`;
const stackCommand = `${pythonBin} scripts/run_agentic_stack.py verification --api-port ${apiPort} --web-port ${webPort} --host 127.0.0.1`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: webBase,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: [
    {
      command: stackCommand,
      cwd: rootDir,
      url: webBase,
      reuseExistingServer: false,
      env: {
        ...process.env,
        PYTHON_BIN: pythonBin,
        PLAYWRIGHT_API_PORT: apiPort,
        PLAYWRIGHT_WEB_PORT: webPort,
      },
    },
  ],
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit-desktop",
      use: { ...devices["Desktop Safari"] },
    },
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 7"] },
    },
    {
      name: "mobile-safari",
      use: { ...devices["iPhone 14"] },
    },
  ],
});
