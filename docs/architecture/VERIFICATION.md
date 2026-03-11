# Verification Architecture

## Purpose

The browser verification stack exists to prove that the Agentic Indexing workbook is interactive after hydration and to explain failures in terms of frontend state, network traffic, and backend request handling.

## What it proves

1. Core workbook flows work across the supported browser matrix.
2. Interactive controls cause the expected state transitions.
3. Browser-visible failures produce inspectable artifacts instead of silent no-op behavior.
4. Frontend and backend behavior can be correlated by `X-Test-Run-Id` and `X-Request-Id`.

## What it does not prove

1. Production broker integrations.
2. Live third-party provider correctness.
3. Human UX quality beyond the deterministic checks in the scenario specs.

## Layers

1. API/unit tests isolate backend logic quickly.
2. Playwright core journeys gate the current workbook shell.
3. Extended browser scenarios can expand coverage without blocking every edit.

## Artifact model

Each scenario run produces:

1. Per-step structured JSON with normalized UI state, diffs, network events, and backend events.
2. Per-step text summaries of visible page content.
3. Checkpoint screenshots for key moments.
4. Per-scenario markdown and JSON summaries.
5. Playwright traces retained on failure.

## Deterministic oracle

Scenario specs and checked-in baselines are the source of truth. Baselines are updated intentionally and reviewed in PRs like code.

## Current maturity model

1. P0: workbook shell, ideation, saved indexes, model admin, and reset.
2. P1: approvals and rebalance UX.
3. P2: broker/account surfaces.
4. P3: long-running maintenance and portfolio comparison.
