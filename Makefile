PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install-py install-web lint typecheck test migrate db-proxy run-api run-web run-worker

install-py:
	$(PIP) install -r requirements-dev.txt

install-web:
	cd apps/web && npm install

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy .

test:
	$(PYTHON) -m pytest

migrate:
	$(PYTHON) scripts/apply_migrations.py

db-proxy:
	cloud-sql-proxy --gcloud-auth --address 127.0.0.1 --port 5432 $(CLOUD_SQL_CONNECTION_NAME)

run-api:
	$(PYTHON) -m uvicorn apps.api.agent_etf_api.main:app --host 0.0.0.0 --port 8000 --reload

run-web:
	cd apps/web && npm run dev -- --hostname 0.0.0.0 --port 3000

run-worker:
	$(PYTHON) -m workers.temporal.agent_etf_workflows.worker
