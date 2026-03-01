from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from agent_etf_contracts.models import AuditReport, AuditVerdict


class ModelProvider(Protocol):
    def run_check(
        self,
        model: str,
        stage: str,
        payload: dict[str, object],
    ) -> tuple[bool, list[str]]:
        ...


@dataclass
class CouncilResult:
    passed: bool
    reports: list[AuditReport]


class AuditCouncil:
    """Sequential fail-closed audit council.

    Any dissent immediately fails the council.
    """

    def __init__(self, provider: ModelProvider, models: list[str]) -> None:
        self._provider = provider
        self._models = models

    def evaluate(self, stage: str, payload: dict[str, object]) -> CouncilResult:
        reports: list[AuditReport] = []
        stable = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(stable.encode("utf-8")).hexdigest()

        for model in self._models:
            ok, reasons = self._provider.run_check(model=model, stage=stage, payload=payload)
            report = AuditReport(
                stage=stage,
                model=model,
                verdict=AuditVerdict.passed if ok else AuditVerdict.dissent,
                reasons=reasons,
                content_hash=payload_hash,
            )
            reports.append(report)
            if not ok:
                return CouncilResult(passed=False, reports=reports)

        return CouncilResult(passed=True, reports=reports)
