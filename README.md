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

## Safety Notes

- MVP is paper-first: no live money movement.
- Any order action is modeled behind a 3-step approval chain with cooldown.
- Audit councils are fail-closed: any dissent halts the stage.
