import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(process.cwd(), 'test-results', 'verification');

async function latestRunDir() {
  try {
    const entries = await fs.readdir(root, { withFileTypes: true });
    const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
    return dirs.at(-1) ?? null;
  } catch {
    return null;
  }
}

const run = await latestRunDir();
if (!run) {
  console.log('No verification runs found.');
  process.exit(0);
}

const runPath = path.join(root, run);
const scenarios = await fs.readdir(runPath, { withFileTypes: true });
for (const scenario of scenarios.filter((entry) => entry.isDirectory())) {
  const scenarioPath = path.join(runPath, scenario.name);
  const projects = await fs.readdir(scenarioPath, { withFileTypes: true });
  for (const project of projects.filter((entry) => entry.isDirectory())) {
    const summaryPath = path.join(scenarioPath, project.name, 'summary.md');
    try {
      const summary = await fs.readFile(summaryPath, 'utf8');
      console.log(summary.trim());
      console.log('');
      try {
        const summaryJson = JSON.parse(await fs.readFile(path.join(scenarioPath, project.name, 'summary.json'), 'utf8'));
        if (summaryJson.failureClassification && summaryJson.failureClassification !== 'none') {
          console.log(`Failure classification: ${summaryJson.failureClassification}`);
          console.log('');
        }
      } catch {
        // ignore missing structured summaries
      }
    } catch {
      // ignore missing summaries
    }
  }
}
