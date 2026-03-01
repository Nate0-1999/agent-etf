PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install-py lint typecheck test run-api run-worker

install-py:
	$(PIP) install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy .

test:
	$(PYTHON) -m pytest

run-api:
	$(PYTHON) -m uvicorn apps.api.agent_etf_api.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	$(PYTHON) -m workers.temporal.agent_etf_workflows.worker
