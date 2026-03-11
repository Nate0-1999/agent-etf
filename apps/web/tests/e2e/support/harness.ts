import fs from "node:fs/promises";
import path from "node:path";

import { expect, type Page, type TestInfo } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8100";
const RESULTS_ROOT = path.resolve(process.cwd(), "test-results", "verification");
const UPDATE_BASELINES = process.env.UPDATE_VERIFICATION_BASELINES === "1";

export type ScenarioSpec = {
  id: string;
  seed: string;
  projects: string[];
  steps: Array<{ id: string; label: string }>;
  assertions: string[];
  baseline_refs: string[];
  artifact_policy: Record<string, string | boolean>;
};

type VerificationState = {
  route: string;
  activeTab: string;
  openTabs: string[];
  savedIndexCount: number;
  selectedIndexName: string | null;
  showModelAdmin: boolean;
  pendingModelProposalCount: number;
  error: string | null;
  isBusy: boolean;
  session: {
    title: string | null;
    status: string | null;
    messageCount: number;
    councilHeadline: string | null;
    tileStatuses: Record<string, string>;
  } | null;
} | null;

type Snapshot = {
  state: VerificationState;
  bodyText: string;
  apiLog: Array<Record<string, unknown>>;
  renderEvents: number[];
};

type StepRecord = {
  timestamp: string;
  scenarioId: string;
  testRunId: string;
  project: string;
  stepId: string;
  label: string;
  route: string | null;
  actionSummary: string;
  state: VerificationState;
  diff: string[];
  consoleEvents: Array<Record<string, unknown>>;
  networkEvents: Array<Record<string, unknown>>;
  backendEvents: Array<Record<string, unknown>>;
  assertions: string[];
  attachments: string[];
};

type BaselineFile = {
  scenario: string;
  checkpoints: Record<string, VerificationState>;
};

export async function loadScenarioSpec(name: string): Promise<ScenarioSpec> {
  const filePath = path.resolve(process.cwd(), "tests", "e2e", "scenarios", `${name}.json`);
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw) as ScenarioSpec;
}

export async function installBrowserProbe(page: Page, testRunId: string): Promise<void> {
  await page.addInitScript(({ providedTestRunId }) => {
    window.__AGENTIC_INDEXING_TEST_RUN_ID__ = providedTestRunId;
    window.__AGENTIC_INDEXING_API_LOG__ = [];
    const renderEvents: number[] = [];
    (window as Window & { __AGENTIC_INDEXING_RENDER_EVENTS__?: number[] }).__AGENTIC_INDEXING_RENDER_EVENTS__ = renderEvents;
    const mark = () => {
      const now = Date.now();
      renderEvents.push(now);
      window.__AGENTIC_INDEXING_LAST_RENDER_AT__ = now;
      if (renderEvents.length > 100) {
        renderEvents.splice(0, renderEvents.length - 100);
      }
    };
    const observer = new MutationObserver(() => {
      window.requestAnimationFrame(mark);
    });
    document.addEventListener("DOMContentLoaded", () => {
      mark();
      observer.observe(document.documentElement, {
        subtree: true,
        childList: true,
        attributes: true,
        characterData: true,
      });
    });
  }, { providedTestRunId: testRunId });
}

export function makeTestRunId(spec: ScenarioSpec, projectName: string): string {
  const safeProject = projectName.replace(/[^a-z0-9-]+/gi, "-").toLowerCase();
  return `${spec.id}-${safeProject}-${Date.now()}`;
}

export function projectEnabled(spec: ScenarioSpec, projectName: string): boolean {
  return spec.projects.includes(projectName);
}

function isMobileProject(projectName: string): boolean {
  return projectName.includes("mobile");
}

function diffStates(previous: VerificationState, next: VerificationState): string[] {
  if (previous === null && next === null) {
    return [];
  }
  if (previous === null) {
    return ["initial-state"];
  }
  if (next === null) {
    return ["state-cleared"];
  }
  const diffs: string[] = [];
  const keys: Array<keyof NonNullable<VerificationState>> = [
    "route",
    "activeTab",
    "openTabs",
    "savedIndexCount",
    "selectedIndexName",
    "showModelAdmin",
    "pendingModelProposalCount",
    "error",
    "isBusy",
    "session",
  ];
  for (const key of keys) {
    if (JSON.stringify(previous[key]) !== JSON.stringify(next[key])) {
      diffs.push(String(key));
    }
  }
  return diffs;
}

function condensedText(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, 4000);
}

async function waitForUiSettle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(150);
  await page.waitForFunction(() => {
    const last = window.__AGENTIC_INDEXING_LAST_RENDER_AT__ ?? 0;
    return Date.now() - last > 150;
  });
}

async function snapshotPage(page: Page): Promise<Snapshot> {
  return page.evaluate(() => ({
    state: window.__AGENTIC_INDEXING_TEST_STATE__ ?? null,
    bodyText: document.body.innerText,
    apiLog: window.__AGENTIC_INDEXING_API_LOG__ ?? [],
    renderEvents: (window as Window & { __AGENTIC_INDEXING_RENDER_EVENTS__?: number[] }).__AGENTIC_INDEXING_RENDER_EVENTS__ ?? [],
  }));
}

export class ScenarioRecorder {
  private readonly runDir: string;
  private readonly scenarioDir: string;
  private readonly baselinePath: string;
  private previousState: VerificationState = null;
  private previousConsoleCount = 0;
  private previousNetworkCount = 0;
  private previousBackendCount = 0;
  private readonly consoleEvents: Array<Record<string, unknown>> = [];
  private readonly networkEvents: Array<Record<string, unknown>> = [];
  private readonly steps: StepRecord[] = [];

  constructor(
    private readonly spec: ScenarioSpec,
    private readonly page: Page,
    private readonly testInfo: TestInfo,
    private readonly testRunId: string,
  ) {
    this.runDir = path.join(RESULTS_ROOT, testRunId);
    this.scenarioDir = path.join(this.runDir, spec.id, testInfo.project.name);
    this.baselinePath = path.resolve(
      process.cwd(),
      "tests",
      "e2e",
      "baselines",
      spec.baseline_refs[0] ?? `${spec.id}.json`,
    );
  }

  async initialize(): Promise<void> {
    await fs.mkdir(this.scenarioDir, { recursive: true });
    this.page.on("console", (message) => {
      this.consoleEvents.push({
        type: message.type(),
        text: message.text(),
        location: message.location(),
      });
    });
    this.page.on("pageerror", (error) => {
      this.consoleEvents.push({ type: "pageerror", text: error.message });
    });
    this.page.on("response", async (response) => {
      const url = response.url();
      if (!url.startsWith(API_BASE) && !url.startsWith(this.testInfo.project.use?.baseURL ?? "")) {
        return;
      }
      this.networkEvents.push({
        url,
        status: response.status(),
        method: response.request().method(),
        requestId: response.headers()["x-request-id"] ?? null,
      });
    });
  }

  async resetAndSeed(seed: string): Promise<void> {
    await this.page.request.post(`${API_BASE}/dev/reset`);
    await this.page.request.post(`${API_BASE}/dev/seed`, { data: { scenario: seed } });
  }

  async captureStep(
    stepId: string,
    label: string,
    assertions: string[],
    options?: { screenshot?: boolean },
  ): Promise<VerificationState> {
    await waitForUiSettle(this.page);
    const snapshot = await snapshotPage(this.page);
    const backendResponse = await this.page.request.get(`${API_BASE}/dev/events?test_run_id=${this.testRunId}`);
    const backendBody = (await backendResponse.json()) as { events?: Array<Record<string, unknown>> };
    const backendEvents = backendBody.events ?? [];

    const stepDir = path.join(this.scenarioDir, stepId);
    await fs.mkdir(stepDir, { recursive: true });

    const attachments: string[] = [];
    if (options?.screenshot) {
      const screenshotPath = path.join(stepDir, "checkpoint.png");
      await this.page.screenshot({ path: screenshotPath, fullPage: true });
      attachments.push(path.relative(this.scenarioDir, screenshotPath));
    }

    const stepRecord: StepRecord = {
      timestamp: new Date().toISOString(),
      scenarioId: this.spec.id,
      testRunId: this.testRunId,
      project: this.testInfo.project.name,
      stepId,
      label,
      route: snapshot.state?.route ?? null,
      actionSummary: label,
      state: snapshot.state,
      diff: diffStates(this.previousState, snapshot.state),
      consoleEvents: this.consoleEvents.slice(this.previousConsoleCount),
      networkEvents: this.networkEvents.slice(this.previousNetworkCount),
      backendEvents: backendEvents.slice(this.previousBackendCount),
      assertions,
      attachments,
    };
    await fs.writeFile(path.join(stepDir, "step.json"), JSON.stringify(stepRecord, null, 2));
    await fs.writeFile(path.join(stepDir, "body.txt"), condensedText(snapshot.bodyText));
    await fs.writeFile(path.join(stepDir, "api-log.json"), JSON.stringify(snapshot.apiLog, null, 2));

    this.steps.push(stepRecord);
    this.previousState = snapshot.state;
    this.previousConsoleCount = this.consoleEvents.length;
    this.previousNetworkCount = this.networkEvents.length;
    this.previousBackendCount = backendEvents.length;

    await this.assertBaseline(stepId, snapshot.state);
    return snapshot.state;
  }

  async assertHealthy(options?: { allowApiErrors?: boolean }): Promise<void> {
    const recentConsole = this.consoleEvents.slice(this.previousConsoleCount);
    const recentNetwork = this.networkEvents.slice(this.previousNetworkCount);
    const consoleErrors = recentConsole.filter((event) => event.type === "error" || event.type === "pageerror");
    if (consoleErrors.length > 0) {
      throw new Error(`Console errors detected: ${JSON.stringify(consoleErrors)}`);
    }
    if (!options?.allowApiErrors) {
      const failed = recentNetwork.filter((event) => typeof event.status === "number" && Number(event.status) >= 400);
      if (failed.length > 0) {
        throw new Error(`Unexpected failed responses detected: ${JSON.stringify(failed)}`);
      }
    }
  }

  async expectMobileLayout(): Promise<void> {
    if (!isMobileProject(this.testInfo.project.name)) {
      return;
    }
    const state = await snapshotPage(this.page);
    if (state.state?.route === "ideation") {
      await expect(this.page.getByTestId("chat-rail")).toBeVisible();
      await expect(this.page.getByTestId("workbook-canvas")).toBeVisible();
      return;
    }
    await expect(this.page.getByTestId("saved-indexes-layout")).toBeVisible();
  }

  private async assertBaseline(stepId: string, state: VerificationState): Promise<void> {
    let baseline: BaselineFile = { scenario: this.spec.id, checkpoints: {} };
    try {
      baseline = JSON.parse(await fs.readFile(this.baselinePath, "utf8")) as BaselineFile;
    } catch {
      baseline = { scenario: this.spec.id, checkpoints: {} };
    }
    if (UPDATE_BASELINES) {
      baseline.checkpoints[stepId] = state;
      await fs.mkdir(path.dirname(this.baselinePath), { recursive: true });
      await fs.writeFile(this.baselinePath, JSON.stringify(baseline, null, 2));
      return;
    }
    expect(baseline.checkpoints[stepId]).toEqual(state);
  }

  async finalize(status: "passed" | "failed"): Promise<void> {
    const lines = [
      `# Verification Summary: ${this.spec.id}`,
      "",
      `- Status: ${status}`,
      `- Project: ${this.testInfo.project.name}`,
      `- Test run: ${this.testRunId}`,
      `- Steps captured: ${this.steps.length}`,
      "",
      "## Step timeline",
      ...this.steps.flatMap((step) => [
        `- ${step.stepId}: ${step.label}`,
        `  route=${step.route ?? "unknown"}; diff=${step.diff.join(", ") || "none"}; console=${step.consoleEvents.length}; network=${step.networkEvents.length}; backend=${step.backendEvents.length}`,
      ]),
    ];
    await fs.writeFile(path.join(this.scenarioDir, "summary.md"), `${lines.join("\n")}\n`);
    await fs.writeFile(
      path.join(this.scenarioDir, "summary.json"),
      JSON.stringify({ scenario: this.spec.id, project: this.testInfo.project.name, status, testRunId: this.testRunId, steps: this.steps }, null, 2),
    );
  }
}
