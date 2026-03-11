# Cloud SQL Proxy Runbook

## Purpose

Local development must connect to Postgres through Cloud SQL Auth Proxy, not by directly opening the Cloud SQL public endpoint to the current network.

This is the approved local access path for `Agentic Indexing`.

## Why This Exists

Using a public authorized network entry ties database reachability to the public IP of the network you happen to be on. That is brittle and, on shared networks, broader than necessary.

The proxy is safer because:

1. It binds locally on `127.0.0.1`.
2. It authenticates to Google Cloud using your `gcloud` login.
3. It still requires the Postgres username and password.
4. It allows us to remove temporary IP allowlist entries from Cloud SQL.

The proxy does not replace database credentials. It replaces the network-trust shortcut.

## Current Connection Model

1. Cloud SQL instance: `agentic-etf:us-central1:agentic-etf-pg-dev`
2. Local proxy listener: `127.0.0.1:5432`
3. Local app DSN target: `postgresql://agent_etf_app:<password>@127.0.0.1:5432/agent_etf`
4. Cloud SQL authorized networks: empty for this dev instance

## Prerequisites

1. `gcloud` installed locally
2. Authenticated `gcloud` user with access to the `agentic-etf` project
3. `cloud-sql-proxy` installed locally
4. Local `.env` file populated with:
   - `CLOUD_SQL_CONNECTION_NAME`
   - `DATABASE_URL`

## Start The Proxy

From the repo root:

```bash
make db-proxy
```

That runs:

```bash
cloud-sql-proxy --gcloud-auth --address 127.0.0.1 --port 5432 $CLOUD_SQL_CONNECTION_NAME
```

Expected startup behavior:

1. Proxy reports it is authorizing with `gcloud` user credentials.
2. Proxy reports it is listening on `127.0.0.1:5432`.
3. Proxy reports it is ready for new connections.

## Start The App

In a second terminal:

```bash
make migrate
make run-api
```

The API should connect through the proxy because `DATABASE_URL` points to `127.0.0.1:5432`.

## Verification

Minimum verification after any database access change:

1. Start proxy with `make db-proxy`
2. Run `make migrate`
3. Run `make test`
4. Confirm API health:

```bash
curl http://localhost:8000/healthz
```

If those pass, the local DB path is functioning.

## Failure Modes

### Proxy does not start

Likely causes:

1. `gcloud` is not installed
2. `cloud-sql-proxy` is not installed
3. local port `5432` is already in use
4. active `gcloud` user does not have access to the project

Checks:

```bash
gcloud config get-value project
gcloud auth list
lsof -iTCP:5432 -sTCP:LISTEN -n -P
```

### Proxy starts but app cannot connect

Likely causes:

1. `DATABASE_URL` is malformed
2. Postgres username or password is wrong
3. database name is wrong
4. proxy is not the process actually bound to `5432`

Checks:

1. Verify `.env` points at `127.0.0.1:5432`
2. Verify `CLOUD_SQL_CONNECTION_NAME` matches the instance
3. Re-run `make migrate`

### It worked yesterday and stopped today

Likely causes:

1. `gcloud` session expired or changed user
2. proxy is not running
3. local `.env` changed
4. Cloud SQL IAM/project access changed

Checks:

```bash
gcloud auth list
gcloud config get-value project
```

## Security Rules

1. Do not reintroduce a broad Cloud SQL authorized-network allowlist for convenience.
2. Do not commit `.env` or raw database credentials.
3. Do not treat the proxy as sufficient auth on its own; the DB password remains required.
4. If a credential is pasted into chat or another insecure channel, rotate it.
5. Prefer Google-authenticated local proxy access over public-IP access for all development work.

## Operational Notes

1. The proxy is a local foreground process right now. If you close the terminal, DB access stops.
2. The repo command is [Makefile](/Users/nateoswalt/agent-etf/Makefile).
3. The environment template is [.env.example](/Users/nateoswalt/agent-etf/.env.example).
4. The root setup guide is [README.md](/Users/nateoswalt/agent-etf/README.md).
