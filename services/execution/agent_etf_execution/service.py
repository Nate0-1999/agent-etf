from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from agent_etf_brokers import BrokerAdapter
from agent_etf_contracts.models import ApprovalAction, ApprovalBundle, ApprovalStatus


class ApprovalStateError(ValueError):
    pass


class ExecutionService:
    def __init__(self, broker: BrokerAdapter) -> None:
        self._broker = broker

    @staticmethod
    def build_intent_hash(
        strategy_id: str,
        action: ApprovalAction,
        target_allocations: dict[str, float],
    ) -> str:
        stable = json.dumps(
            {
                "strategy_id": strategy_id,
                "action": action.value,
                "target_allocations": target_allocations,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()

    def create_bundle(
        self,
        strategy_id: str,
        action: ApprovalAction,
        target_allocations: dict[str, float],
        cooldown_seconds: int,
    ) -> ApprovalBundle:
        return ApprovalBundle(
            id=str(uuid4()),
            strategy_id=strategy_id,
            action=action,
            intent_hash=self.build_intent_hash(
                strategy_id=strategy_id,
                action=action,
                target_allocations=target_allocations,
            ),
            target_allocations=target_allocations,
            cooldown_seconds=cooldown_seconds,
            status=ApprovalStatus.pending,
        )

    def apply_step1(self, bundle: ApprovalBundle, token: str) -> ApprovalBundle:
        if not token:
            raise ApprovalStateError("Step 1 token required")
        if bundle.status != ApprovalStatus.pending:
            raise ApprovalStateError("Step 1 only allowed from pending status")

        return bundle.model_copy(
            update={
                "step1_at": datetime.now(UTC),
                "status": ApprovalStatus.step1_complete,
            }
        )

    def apply_step2(self, bundle: ApprovalBundle, token: str) -> ApprovalBundle:
        if not token:
            raise ApprovalStateError("Step 2 token required")
        if bundle.status != ApprovalStatus.step1_complete:
            raise ApprovalStateError("Step 2 only allowed after step 1")

        return bundle.model_copy(
            update={
                "step2_at": datetime.now(UTC),
                "status": ApprovalStatus.step2_complete,
            }
        )

    def apply_step3(self, bundle: ApprovalBundle, token: str) -> ApprovalBundle:
        if not token:
            raise ApprovalStateError("Step 3 token required")
        if bundle.status != ApprovalStatus.step2_complete:
            raise ApprovalStateError("Step 3 only allowed after step 2")
        if bundle.step2_at is None:
            raise ApprovalStateError("Step 2 timestamp missing")

        elapsed = (datetime.now(UTC) - bundle.step2_at).total_seconds()
        if elapsed < bundle.cooldown_seconds:
            raise ApprovalStateError(
                f"Step 3 cooldown not reached: {elapsed:.0f}s/{bundle.cooldown_seconds}s"
            )

        approved_bundle = bundle.model_copy(
            update={
                "step3_at": datetime.now(UTC),
                "status": ApprovalStatus.approved,
            }
        )
        self._broker.submit_paper_orders(approved_bundle)
        return approved_bundle

    def order_preview(self, bundle: ApprovalBundle) -> dict[str, object]:
        preview = self._broker.build_order_preview(bundle)
        return {
            "strategy_id": preview.strategy_id,
            "action": preview.action,
            "orders": preview.orders,
        }
