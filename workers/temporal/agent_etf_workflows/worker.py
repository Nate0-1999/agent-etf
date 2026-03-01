from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from workers.temporal.agent_etf_workflows.workflows import (
    ClarificationWorkflow,
    MaintenanceWorkflow,
)


async def run_worker() -> None:
    target = os.getenv("TEMPORAL_TARGET", "localhost:7233")
    client = await Client.connect(target)
    worker = Worker(
        client,
        task_queue="agent-etf",
        workflows=[ClarificationWorkflow, MaintenanceWorkflow],
        activities=[],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
