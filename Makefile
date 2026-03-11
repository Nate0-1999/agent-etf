PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install-py install-web lint typecheck test migrate db-proxy run-api run-web run-worker verify-ui verify-ui-all verify-ui-headed verify-ui-update-baselines verify-ui-report

install-py:
	$(PIP) install -r requirements-dev.txt

install-web:
	cd apps/web && npm install

install-playwright:
	cd apps/web && npm run install:playwright

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

verify-ui:
	cd apps/web && npm run test:e2e

verify-ui-all:
	cd apps/web && npm run test:e2e:all

verify-ui-headed:
	cd apps/web && npm run test:e2e:headed

verify-ui-update-baselines:
	cd apps/web && npm run test:e2e:update

verify-ui-report:
	cd apps/web && npm run test:e2e:report
