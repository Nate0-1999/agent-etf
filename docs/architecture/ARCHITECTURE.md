# Architecture

## Core Principles

1. Paper-first execution path.
2. Fail-closed auditing for any LLM-mediated decision.
3. Deterministic strategy artifact generation.
4. Human-in-the-loop approvals for any order path.

## High-Level Components

- FastAPI control plane for strategy lifecycle APIs.
- Temporal workflows for long-running clarification/rebalance loops.
- LLM gateway with budget accounting and model-family routing.
- Research service for candidate discovery.
- Backtest service with benchmark comparison.
- Execution service with approval bundle state machine.
- Broker adapters (IBKR paper first).

## Persistence

- Postgres/Timescale for domain entities and time-series.
- Git for strategy artifact provenance.
- Immutable audit records keyed by content hash.
