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
cp .env.example .env
make migrate
make test
make run-api
```

Web app:

```bash
cd apps/web
npm install
npm run dev
```

Docker dev stack:

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

## Required Configuration

- `DATABASE_URL`: required for durable Postgres-backed state.
- `OPENROUTER_API_KEY`: enables real multi-model checks through OpenRouter.
- `EXA_API_KEY`: enables live web research instead of fallback stub results.
- `IBKR` paper credentials and gateway/TWS connection details: required once the paper adapter is upgraded from stubbed previews to real broker calls.

Without these keys the app still runs, but it falls back to in-memory storage or deterministic stubs where appropriate.

## Safety Notes

- MVP is paper-first: no live money movement.
- Any order action is modeled behind a 3-step approval chain with cooldown.
- Audit councils are fail-closed: any dissent halts the stage.
