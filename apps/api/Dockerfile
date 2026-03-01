FROM python:3.11-slim

WORKDIR /app

COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

COPY . /app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "apps.api.agent_etf_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
