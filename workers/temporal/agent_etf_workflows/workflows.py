from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow


@workflow.defn
class ClarificationWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        required_fields: list[str] = payload.get("required_fields", [])
        provided: dict[str, Any] = payload.get("provided", {})
        max_rounds = int(payload.get("max_rounds", 6))

        rounds = 0
        while rounds < max_rounds:
            rounds += 1
            missing = [field for field in required_fields if not provided.get(field)]
            if not missing:
                return {
                    "status": "ready",
                    "rounds": rounds,
                    "missing": [],
                }
            await workflow.sleep(timedelta(milliseconds=5))

        return {
            "status": "escalated",
            "rounds": rounds,
            "missing": [field for field in required_fields if not provided.get(field)],
        }


@workflow.defn
class MaintenanceWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        max_loops = int(payload.get("max_loops", 3))
        attempts = 0

        while attempts < max_loops:
            attempts += 1
            council_passed = bool(payload.get("council_passed", True))
            if council_passed:
                return {"status": "proposal_ready", "attempts": attempts}
            await workflow.sleep(timedelta(milliseconds=5))

        return {
            "status": "needs_user_intervention",
            "attempts": attempts,
        }
