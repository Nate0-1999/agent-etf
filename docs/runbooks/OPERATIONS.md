# Operations Runbook

## Mandatory Reading

- Cloud SQL local access procedure: [CLOUD_SQL_PROXY.md](/Users/nateoswalt/agent-etf/docs/runbooks/CLOUD_SQL_PROXY.md)

## Start Stack

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

## API Health Check

```bash
curl http://localhost:8000/healthz
```

## Worker Health

Worker logs should show polling for task queue `agent-etf`.

## Failure Handling

- If audit council fails repeatedly, inspect escalation summary logs.
- If approval step expires, restart approval bundle creation.
- If the API cannot reach Postgres, do not add a temporary public network allowlist first. Validate the proxy path in [CLOUD_SQL_PROXY.md](/Users/nateoswalt/agent-etf/docs/runbooks/CLOUD_SQL_PROXY.md).
