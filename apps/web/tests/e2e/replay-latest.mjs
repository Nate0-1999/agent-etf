import fs from "node:fs/promises";
import path from "node:path";

const apiBase = process.env.AGENTIC_DIRECT_API_BASE ?? "http://127.0.0.1:8100";
const root = path.resolve(process.cwd(), "test-results", "verification");

async function latestDir(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  return dirs.at(-1) ?? null;
}

async function latestApiLog() {
  const run = await latestDir(root).catch(() => null);
  if (!run) {
    return null;
  }
  const runPath = path.join(root, run);
  const scenarios = (await fs.readdir(runPath, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  const scenario = scenarios.at(-1);
  if (!scenario) {
    return null;
  }
  const scenarioPath = path.join(runPath, scenario);
  const projects = (await fs.readdir(scenarioPath, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  const project = projects.at(-1);
  if (!project) {
    return null;
  }
  const projectPath = path.join(scenarioPath, project);
  const steps = (await fs.readdir(projectPath, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const candidate = path.join(projectPath, steps[index], "api-log.json");
    try {
      const raw = await fs.readFile(candidate, "utf8");
      return JSON.parse(raw);
    } catch {
      // continue
    }
  }
  return null;
}

const events = await latestApiLog();
if (!events || events.length === 0) {
  console.log("No API log found for replay.");
  process.exit(0);
}

const replayable = events.filter((event) => typeof event.path === "string" && typeof event.method === "string");
const results = [];
for (const event of replayable) {
  const method = event.method ?? "GET";
  const requestBody = typeof event.requestBody === "string" ? event.requestBody : undefined;
  try {
    const response = await fetch(`${apiBase}${event.path}`, {
      method,
      headers: {
        "Content-Type": requestBody ? "application/json" : "text/plain",
        "X-Test-Run-Id": `replay-${Date.now()}`,
      },
      body: method === "GET" || method === "HEAD" ? undefined : requestBody,
    });
    results.push({
      method,
      path: event.path,
      expectedStatus: event.status,
      replayStatus: response.status,
      replayRequestId: response.headers.get("x-request-id"),
    });
  } catch (error) {
    results.push({
      method,
      path: event.path,
      expectedStatus: event.status,
      replayStatus: null,
      replayRequestId: null,
      error: error instanceof Error ? error.message : "unknown replay failure",
    });
  }
}

const allMatched = results.every((item) => item.expectedStatus === item.replayStatus);
console.log(JSON.stringify({ apiBase, allMatched, results }, null, 2));
