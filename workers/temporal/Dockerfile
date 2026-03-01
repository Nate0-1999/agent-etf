FROM python:3.11-slim

WORKDIR /app

COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

COPY . /app

CMD ["python", "-m", "workers.temporal.agent_etf_workflows.worker"]
