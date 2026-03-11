import { expect, test } from "@playwright/test";

import {
  ScenarioRecorder,
  installBrowserProbe,
  loadScenarioSpec,
  makeTestRunId,
  projectEnabled,
} from "./support/harness";

const PROMPT =
  "Build a quality-focused industrial innovation index using liquid ETFs and large-cap equities, equal weight, monthly review, benchmark against the S&P 500 and gold, and keep hard multi-step approvals for any rebalance.";

test.describe("@core workbook verification", () => {
  test("workbook flow is interactive across supported browsers", async ({ page }, testInfo) => {
    const spec = await loadScenarioSpec("workbook-core");
    test.skip(!projectEnabled(spec, testInfo.project.name), `Project ${testInfo.project.name} not in scenario`);

    const testRunId = makeTestRunId(spec, testInfo.project.name);
    await installBrowserProbe(page, testRunId);

    const recorder = new ScenarioRecorder(spec, page, testInfo, testRunId);
    await recorder.initialize();

    let status: "passed" | "failed" = "failed";
    try {
      await recorder.resetAndSeed(spec.seed);
      await page.goto("/");
      await expect(page.getByTestId("saved-indexes-tab")).toBeVisible();
      await recorder.captureStep("initial-load", "Load workbook shell", ["saved indexes tab visible"], {
        screenshot: true,
      });
      await recorder.expectMobileLayout();

      await page.getByTestId("new-idea-button").click();
      await expect(page.getByTestId("ideation-layout")).toBeVisible();
      await recorder.captureStep("create-idea-tab", "Create a new ideation tab", ["ideation layout opened"], {
        screenshot: true,
      });

      await page.getByTestId("message-input").fill(PROMPT);
      await page.getByTestId("send-message-button").click();
      await expect(page.getByTestId("decision-tile-thesis")).toContainText("Build a quality-focused");
      await recorder.captureStep("send-message", "Send chat prompt and update workbook", [
        "thesis tile updated",
        "session ready for conversion",
      ], { screenshot: true });

      await page.getByTestId("toggle-council-details-button").click();
      await expect(page.getByText("pass").first()).toBeVisible();
      await recorder.captureStep("toggle-council", "Expand council details", ["council details visible"]);

      await page.getByTestId("convert-session-button").click();
      await expect(page.getByTestId("saved-indexes-list")).toContainText("Build a quality-focused");
      await recorder.captureStep("convert-session", "Convert ideation session to saved index", [
        "saved index created",
        "saved index detail visible",
      ], { screenshot: true });

      await page.getByTestId("open-new-ideation-from-index-button").click();
      await expect(page.getByTestId("chat-rail")).toBeVisible();
      await recorder.captureStep("reopen-ideation", "Open new ideation from saved index", [
        "new ideation tab opened from saved index",
      ]);

      await page.getByTestId("model-badge-button").click();
      await expect(page.getByTestId("model-admin-panel")).toBeVisible();
      await page.getByTestId("refresh-model-registry-button").click();
      const proposalButton = page.locator('[data-testid^="approve-model-proposal-"]').first();
      await expect(proposalButton).toBeVisible();
      await proposalButton.click();
      await recorder.captureStep("model-admin", "Refresh and approve model registry proposal", [
        "proposal generated in test mode",
        "proposal approved",
      ], { screenshot: true });

      await page.getByTestId("clear-runtime-button").click();
      await expect(page.getByText("No saved indexes yet.")).toBeVisible();
      await recorder.captureStep("reset-runtime", "Clear local runtime data", [
        "blank state restored",
      ], { screenshot: true });

      status = "passed";
    } finally {
      await recorder.finalize(status);
    }
  });
});
