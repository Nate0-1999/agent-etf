# Playwright Verification Runbook

## Install

```bash
make install-web
make install-playwright
```

## Core commands

```bash
make verify-ui
make verify-ui-all
make verify-ui-headed
make verify-ui-update-baselines
make verify-ui-report
make replay-ui-latest
```

## Local behavior

The verification profile starts one managed stack:

1. FastAPI on `127.0.0.1:8100` with in-memory state and test mode enabled.
2. Next.js on `127.0.0.1:3100`.
3. The browser talks only to Next.js on `3100`; Next proxies app requests to FastAPI on `8100`.

Cloud SQL and live provider calls are not required for browser verification.

## Artifacts

Artifacts are written under `apps/web/test-results/verification/` and include:

1. `step.json`
2. `body.txt`
3. `api-log.json`
4. `summary.md`
5. `summary.json`
6. checkpoint screenshots when captured

Use `make verify-ui-report` to print the latest summaries. Use `make replay-ui-latest` to replay the latest recorded browser API log directly against a running FastAPI server; set `AGENTIC_DIRECT_API_BASE` if you want to target `8000` instead of the default verification port `8100`.

## Reading failures

Start with the scenario `summary.md`, then inspect:

1. the last failing step's `step.json`
2. the related `body.txt`
3. the Playwright trace
4. backend events from the same `X-Test-Run-Id`
5. proxy response headers in `step.json` network events and the failure classification in `summary.json`

## Adding a scenario

1. Add a spec in `apps/web/tests/e2e/scenarios/`.
2. Add or update a baseline in `apps/web/tests/e2e/baselines/`.
3. Implement the scenario in `apps/web/tests/e2e/*.spec.ts`.
4. Run `make verify-ui-update-baselines` if the expected state changed intentionally.
