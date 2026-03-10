# agent-etf

Paper-first, safety-first agentic workflow for turning user investment ideas into user-approved strategy proposals, deterministic strategy artifacts, backtests, and strictly gated execution flows.

## Monorepo Layout

- `apps/web`: Next.js dashboard and approval UX
- `apps/api`: FastAPI control plane
- `workers/temporal`: Temporal workflows and workers
- `services/research`: investment vehicle discovery and normalization
- `services/backtest`: backtesting and benchmark comparison
- `services/execution`: approval bundle orchestration and broker execution prep
- `services/llm-gateway`: OpenRouter-facing model routing and budget guardrails
- `libs/contracts`: shared schemas/types
- `libs/broker-adapters`: broker interfaces and IBKR paper adapter
- `libs/audit`: multi-model sequential council audit logic
- `infra/docker-compose`: local development stack
- `docs`: architecture, runbooks, threat model

## Quick Start

```bash
make install-py
make install-web
make db-proxy
make migrate
make test
make run-api
make run-web
```

For the exact local database access model and security rules, read [docs/runbooks/CLOUD_SQL_PROXY.md](/Users/nateoswalt/agent-etf/docs/runbooks/CLOUD_SQL_PROXY.md) before changing any Cloud SQL networking or local DB setup.

Local URLs:

- API: `http://127.0.0.1:8000`
- Web: `http://localhost:3000`
- The web dashboard includes a one-click heavy-metals draft flow and will also load saved strategies from Postgres on refresh.

Docker dev stack:

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

## Required Configuration

- `CLOUD_SQL_CONNECTION_NAME`: required when using `make db-proxy` against Cloud SQL.
- `DATABASE_URL`: required for durable Postgres-backed state.
- `OPENROUTER_API_KEY`: enables real multi-model checks through OpenRouter.
- `EXA_API_KEY`: enables live web research instead of fallback stub results.
- `IBKR` paper credentials and gateway/TWS connection details: required once the paper adapter is upgraded from stubbed previews to real broker calls.

Without these keys the app still runs, but it falls back to in-memory storage or deterministic stubs where appropriate.

## Cloud SQL Proxy

Use the proxy for local development instead of connecting directly to the Cloud SQL public endpoint:

```bash
export CLOUD_SQL_CONNECTION_NAME=agentic-etf:us-central1:agentic-etf-pg-dev
make db-proxy
```

Then point `DATABASE_URL` at `127.0.0.1:5432`. This keeps local access tied to your Google auth instead of a temporary authorized network entry for your current public IP.

This is not optional documentation. The full operational and security procedure is in [docs/runbooks/CLOUD_SQL_PROXY.md](/Users/nateoswalt/agent-etf/docs/runbooks/CLOUD_SQL_PROXY.md).

## Safety Notes

- MVP is paper-first: no live money movement.
- Any order action is modeled behind a 3-step approval chain with cooldown.
- Audit councils are fail-closed: any dissent halts the stage.
