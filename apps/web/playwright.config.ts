import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const rootDir = path.resolve(__dirname, "..", "..");
const pythonBin = process.env.PYTHON_BIN ?? ".venv/bin/python";
const apiPort = process.env.PLAYWRIGHT_API_PORT ?? "8100";
const webPort = process.env.PLAYWRIGHT_WEB_PORT ?? "3100";
const apiBase = `http://127.0.0.1:${apiPort}`;
const webBase = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: webBase,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: [
    {
      command: `${pythonBin} -m uvicorn apps.api.agent_etf_api.main:app --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiBase}/healthz`,
      cwd: rootDir,
      reuseExistingServer: false,
      env: {
        ...process.env,
        AGENTIC_ENV: "development",
        AGENTIC_TEST_MODE: "1",
        APPROVAL_STEP3_COOLDOWN_SECONDS: "0",
        DATABASE_URL: "",
        OPENROUTER_API_KEY: "",
        EXA_API_KEY: "",
      },
    },
    {
      command: `npm run dev -- --hostname 127.0.0.1 --port ${webPort}`,
      url: webBase,
      cwd: __dirname,
      reuseExistingServer: false,
      env: {
        ...process.env,
        NEXT_PUBLIC_API_BASE_URL: apiBase,
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
