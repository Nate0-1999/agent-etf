import { expect, test } from "@playwright/test";

import {
  ScenarioRecorder,
  installBrowserProbe,
  loadScenarioSpec,
  makeTestRunId,
  projectEnabled,
} from "./support/harness";

const PROMPT =
  "Build a diversified infrastructure index using liquid ETFs and large-cap equities with monthly review.";

test.describe("workbook error verification", () => {
  test("handles injected API failures without silent no-op state", async ({ page }, testInfo) => {
    const spec = await loadScenarioSpec("workbook-errors");
    test.skip(!projectEnabled(spec, testInfo.project.name), `Project ${testInfo.project.name} not in scenario`);

    const testRunId = makeTestRunId(spec, testInfo.project.name);
    await installBrowserProbe(page, testRunId);

    const recorder = new ScenarioRecorder(spec, page, testInfo, testRunId);
    await recorder.initialize();

    let status: "passed" | "failed" = "failed";
    try {
      await recorder.resetAndSeed(spec.seed);
      await page.goto("/");
      await page.getByTestId("new-idea-button").click();

      await page.route("**/ideation/sessions/*/messages", async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Injected message failure" }),
        });
      }, { times: 1 });
      await page.getByTestId("message-input").fill(PROMPT);
      await page.getByTestId("send-message-button").click();
      await expect(page.getByTestId("error-banner")).toContainText("Injected message failure");
      await recorder.captureStep("chat-api-error", "Inject message submission API failure", [
        "error banner visible after chat failure",
      ], { screenshot: true });

      await page.unroute("**/ideation/sessions/*/messages");
      await page.getByTestId("message-input").fill(PROMPT);
      await page.getByTestId("send-message-button").click();
      await expect(page.getByTestId("convert-session-button")).toBeVisible();

      await page.route("**/ideation/sessions/*/convert-to-index", async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Injected conversion failure" }),
        });
      }, { times: 1 });
      await page.getByTestId("convert-session-button").click();
      await expect(page.getByTestId("error-banner")).toContainText("Injected conversion failure");
      await recorder.captureStep("convert-api-error", "Inject conversion API failure", [
        "error banner visible after conversion failure",
      ], { screenshot: true });

      await page.unroute("**/ideation/sessions/*/convert-to-index");
      await page.getByTestId("model-badge-button").click();
      await page.getByTestId("clear-runtime-button").click();
      await expect(page.getByText("No saved indexes yet.")).toBeVisible();
      await recorder.captureStep("reset-stale-state", "Reset after stale UI state", [
        "blank state restored after failure path",
      ], { screenshot: true });

      status = "passed";
    } finally {
      await recorder.finalize(status);
    }
  });
});
