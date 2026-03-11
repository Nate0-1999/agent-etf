from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from agent_etf_contracts.models import CandidateInstrument


@dataclass
class BudgetState:
    monthly_budget_usd: float
    spent_usd: float = 0.0


class OpenRouterModelService:
    """Deterministic, budget-aware council stub.

    The registry decides which provider trio is active. This service only simulates
    audit/ranking behavior for local development.
    """

    _model_cost = {
        "openai:gpt-5.4": 0.08,
        "anthropic:claude-4.6": 0.06,
        "google:gemini-3.1-pro": 0.05,
    }

    def __init__(self, monthly_budget_usd: float = 150.0) -> None:
        self._budget = BudgetState(monthly_budget_usd=monthly_budget_usd)

    @property
    def spent_usd(self) -> float:
        return self._budget.spent_usd

    def run_check(
        self,
        model: str,
        stage: str,
        payload: dict[str, object],
    ) -> tuple[bool, list[str]]:
        model_cost = self._model_cost.get(model, 0.05)
        if self._budget.spent_usd + model_cost > self._budget.monthly_budget_usd:
            return False, ["Monthly LLM budget exceeded"]

        self._budget.spent_usd += model_cost

        if payload.get("requires_user_approval") is False:
            return False, ["Missing required user approval flag"]

        if stage in {
            "candidate_ranking",
            "runtime_update",
            "runtime_rebalance",
            "session_ideation",
        }:
            candidates = payload.get("candidates")
            if isinstance(candidates, list) and len(candidates) == 0:
                return False, ["No candidate instruments available"]

        if stage == "runtime_rebalance" and not payload.get("target_allocations"):
            return False, ["Rebalance requires target allocations"]

        if stage == "session_ideation" and not str(payload.get("thesis", "")).strip():
            return False, ["Ideation thesis is blank"]

        if bool(payload.get("force_dissent_for_test")):
            stable = json.dumps(payload, sort_keys=True, default=str)
            if hashlib.sha256(stable.encode("utf-8")).hexdigest().endswith("0"):
                return False, ["Forced dissent trigger active"]

        return True, [f"{model} accepted the current session state"]

    def rank_candidates(
        self,
        raw_idea: str,
        candidates: list[CandidateInstrument],
    ) -> list[CandidateInstrument]:
        tokens = {token.lower() for token in raw_idea.replace(",", " ").split()}

        def score(candidate: CandidateInstrument) -> float:
            base = float(candidate.relevance_score)
            name_tokens = set(candidate.name.lower().split())
            overlap = len(tokens.intersection(name_tokens))
            if "equal" in tokens:
                base += 0.02
            if "index" in tokens or "indexing" in tokens:
                base += 0.01
            return float(min(1.0, base + overlap * 0.03))

        ranked = sorted(candidates, key=score, reverse=True)
        return [item.model_copy(update={"relevance_score": score(item)}) for item in ranked]

    @staticmethod
    def summarize_dissent(reports: list[dict[str, object]]) -> str:
        if not reports:
            return "No audit reports available."
        reasons: list[str] = []
        for report in reports:
            model = str(report.get("model", "unknown"))
            verdict = str(report.get("verdict", "unknown"))
            report_reasons = report.get("reasons", [])
            if isinstance(report_reasons, list):
                reason_text = "; ".join(str(reason) for reason in report_reasons)
            else:
                reason_text = str(report_reasons)
            reasons.append(f"{model}={verdict}: {reason_text}")
        return " | ".join(reasons)
