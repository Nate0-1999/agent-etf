from __future__ import annotations

import os
from uuid import uuid4

from agent_etf_audit import AuditCouncil
from agent_etf_backtest import DeterministicBacktestEngine
from agent_etf_brokers import IbkrPaperAdapter
from agent_etf_contracts.models import (
    ApprovalAction,
    ApprovalBundle,
    AuditReport,
    BacktestRequest,
    BacktestRun,
    BrokerLimitsRequest,
    BrokerLinkRequest,
    ClarifyIdeaRequest,
    CreateIdeaRequest,
    CreateStrategyFromIdeaResponse,
    IdeaSpec,
    IdeaStatusResponse,
    ManualActionResponse,
    PortfolioPerformanceResponse,
    SpecGap,
    StrategyDefinition,
    StrategyStatus,
    UserPermissionProfile,
)
from agent_etf_contracts.store import InMemoryStore
from agent_etf_execution import DeterministicStrategyCompiler, ExecutionService
from agent_etf_llm_gateway import OpenRouterModelService
from agent_etf_research import ExaSearchProvider, ResearchService


def _default_models() -> list[str]:
    return [
        "openai:gpt-5",
        "anthropic:claude-sonnet-4",
        "google:gemini-2.5-pro",
    ]


class ControlPlaneService:
    def __init__(self) -> None:
        max_loops = os.getenv("AUDIT_MAX_RETRY_LOOPS", "3")
        self._max_loops = int(max_loops)
        self._step3_cooldown = int(os.getenv("APPROVAL_STEP3_COOLDOWN_SECONDS", "600"))

        self.store = InMemoryStore()
        self.broker = IbkrPaperAdapter()
        self.models = OpenRouterModelService(monthly_budget_usd=150.0)
        self.search = ExaSearchProvider()
        self.research = ResearchService(search_provider=self.search, model_service=self.models)
        self.compiler = DeterministicStrategyCompiler()
        self.backtest_engine = DeterministicBacktestEngine()
        self.execution = ExecutionService(broker=self.broker)

        self._model_list = _default_models()

    def _find_gaps(self, idea: IdeaSpec) -> list[SpecGap]:
        gaps: list[SpecGap] = []

        if not idea.objective:
            gaps.append(
                SpecGap(
                    field="objective",
                    reason="Objective is required to map idea into investable exposure.",
                    question="What is the exact investment objective for this idea?",
                )
            )

        if "allowed_assets" not in idea.constraints:
            gaps.append(
                SpecGap(
                    field="constraints.allowed_assets",
                    reason="Asset eligibility must be explicit for deterministic filtering.",
                    question="Which asset classes should be allowed?",
                )
            )

        if not idea.cadence_recommendation:
            gaps.append(
                SpecGap(
                    field="cadence_recommendation",
                    reason="Strategy update cadence must be explicit and user-approvable.",
                    question="What update cadence should be used initially?",
                )
            )

        return gaps

    @staticmethod
    def _recommend_cadence(raw_idea: str) -> str | None:
        normalized = raw_idea.lower()
        if "high frequency" in normalized or "intraday" in normalized:
            return "weekly_review"
        if "thematic" in normalized or "equal weight" in normalized:
            return "monthly_review"
        if "long-term" in normalized:
            return "quarterly_review"
        return None

    def _compute_clarity(self, gaps: list[SpecGap], required_fields: int = 3) -> float:
        complete = max(0, required_fields - len(gaps))
        return round(complete / required_fields, 4)

    def create_idea(self, request: CreateIdeaRequest) -> IdeaStatusResponse:
        idea_id = str(uuid4())
        idea = IdeaSpec(
            id=idea_id,
            user_id=request.user_id,
            raw_idea=request.raw_idea,
            objective=request.raw_idea.strip() if len(request.raw_idea.split()) >= 4 else None,
            cadence_recommendation=self._recommend_cadence(request.raw_idea),
        )

        if "asset" in request.raw_idea.lower() or "etf" in request.raw_idea.lower():
            idea.constraints["allowed_assets"] = ["etf", "equity", "future"]

        gaps = self._find_gaps(idea)
        idea.clarity_score = self._compute_clarity(gaps=gaps)

        self.store.ideas[idea_id] = idea
        self.store.idea_gaps[idea_id] = gaps

        return IdeaStatusResponse(
            idea=idea,
            gaps=gaps,
            ready_for_strategy=idea.clarity_score >= 0.85,
        )

    def clarify_idea(self, idea_id: str, request: ClarifyIdeaRequest) -> IdeaStatusResponse:
        if idea_id not in self.store.ideas:
            raise KeyError("Idea not found")

        idea = self.store.ideas[idea_id]
        answers = request.answers

        if "objective" in answers:
            idea.objective = str(answers["objective"])

        if "allowed_assets" in answers:
            value = answers["allowed_assets"]
            if isinstance(value, list):
                idea.constraints["allowed_assets"] = value
            else:
                idea.constraints["allowed_assets"] = [str(value)]

        if "cadence_recommendation" in answers:
            idea.cadence_recommendation = str(answers["cadence_recommendation"])

        if "exclusions" in answers and isinstance(answers["exclusions"], list):
            idea.exclusions = [str(item) for item in answers["exclusions"]]

        gaps = self._find_gaps(idea)
        idea.clarity_score = self._compute_clarity(gaps=gaps)

        self.store.ideas[idea_id] = idea
        self.store.idea_gaps[idea_id] = gaps

        return IdeaStatusResponse(
            idea=idea,
            gaps=gaps,
            ready_for_strategy=idea.clarity_score >= 0.85,
        )

    def idea_status(self, idea_id: str) -> IdeaStatusResponse:
        if idea_id not in self.store.ideas:
            raise KeyError("Idea not found")

        idea = self.store.ideas[idea_id]
        gaps = self.store.idea_gaps.get(idea_id, [])
        return IdeaStatusResponse(
            idea=idea,
            gaps=gaps,
            ready_for_strategy=idea.clarity_score >= 0.85,
        )

    def _ensure_permissions(self, user_id: str) -> UserPermissionProfile:
        profile = self.store.permissions.get(user_id)
        if profile is None:
            profile = self.broker.link_account(user_id=user_id, account_id="paper-default")
            self.store.permissions[user_id] = profile
        return profile

    @staticmethod
    def _normalize_name(text: str) -> str:
        clean = " ".join(text.strip().split())
        return clean[:72] if clean else "Untitled Strategy"

    def create_strategy_from_idea(self, idea_id: str) -> CreateStrategyFromIdeaResponse:
        status = self.idea_status(idea_id)
        if not status.ready_for_strategy:
            raise ValueError("Idea clarity threshold not reached")

        idea = status.idea
        permissions = self._ensure_permissions(idea.user_id)
        candidates = self.research.discover_candidates(idea=idea, permissions=permissions)

        candidate_payload = {
            "idea_id": idea.id,
            "requires_user_approval": True,
            "candidates": [item.model_dump(mode="json") for item in candidates],
        }
        council = AuditCouncil(provider=self.models, models=self._model_list)
        result = council.evaluate(stage="candidate_ranking", payload=candidate_payload)
        if not result.passed:
            self.store.audits[idea_id] = result.reports
            raise ValueError("Audit council dissent while generating strategy proposal")

        strategy_id = str(uuid4())
        strategy = StrategyDefinition(
            id=strategy_id,
            user_id=idea.user_id,
            idea_id=idea.id,
            name=self._normalize_name(idea.raw_idea),
            status=StrategyStatus.draft,
            universe=candidates,
            weighting_method="equal_weight",
            rebalance_rule="user_approved_schedule",
            update_rule="agent_recommended_user_approved",
        )

        artifact = self.compiler.compile(strategy)

        self.store.strategies[strategy_id] = strategy
        self.store.strategy_artifacts[strategy_id] = artifact
        self.store.audits[strategy_id] = result.reports

        bullets = [
            f"Strategy name: {strategy.name}",
            f"Universe candidates: {len(strategy.universe)}",
            f"Weighting: {strategy.weighting_method}",
            f"Cadence recommendation: {idea.cadence_recommendation}",
            "Order actions require 3-step approval with cooldown",
        ]

        return CreateStrategyFromIdeaResponse(
            strategy=strategy,
            audits=result.reports,
            proposal_bullets=bullets,
        )

    def set_strategy_status(self, strategy_id: str, approved: bool) -> StrategyDefinition:
        strategy = self._strategy(strategy_id)
        strategy.status = StrategyStatus.active if approved else StrategyStatus.paused
        self.store.strategies[strategy_id] = strategy
        return strategy

    def run_backtest(self, strategy_id: str, request: BacktestRequest) -> BacktestRun:
        strategy = self._strategy(strategy_id)
        run = self.backtest_engine.run(
            strategy=strategy,
            min_years=request.min_years,
            override_min_history=request.override_min_history,
        )
        self.store.backtests[strategy_id] = run
        return run

    def _strategy(self, strategy_id: str) -> StrategyDefinition:
        if strategy_id not in self.store.strategies:
            raise KeyError("Strategy not found")
        return self.store.strategies[strategy_id]

    @staticmethod
    def _equal_weights(strategy: StrategyDefinition) -> dict[str, float]:
        if not strategy.universe:
            return {}
        size = len(strategy.universe)
        weight = round(1.0 / size, 6)
        return {item.symbol: weight for item in strategy.universe}

    def _run_runtime_council(
        self,
        strategy: StrategyDefinition,
        stage: str,
    ) -> tuple[bool, list[AuditReport]]:
        council = AuditCouncil(provider=self.models, models=self._model_list)
        payload = {
            "strategy_id": strategy.id,
            "requires_user_approval": True,
            "candidates": [item.model_dump(mode="json") for item in strategy.universe],
            "target_allocations": self._equal_weights(strategy),
        }
        result = council.evaluate(stage=stage, payload=payload)
        return result.passed, result.reports

    def manual_action(self, strategy_id: str, action: ApprovalAction) -> ManualActionResponse:
        strategy = self._strategy(strategy_id)

        all_reports: list[AuditReport] = []
        stage = "runtime_update" if action == ApprovalAction.update else "runtime_rebalance"

        for attempt in range(1, self._max_loops + 1):
            passed, reports = self._run_runtime_council(strategy=strategy, stage=stage)
            all_reports.extend(reports)
            if passed:
                bundle = self.execution.create_bundle(
                    strategy_id=strategy.id,
                    action=action,
                    target_allocations=self._equal_weights(strategy),
                    cooldown_seconds=self._step3_cooldown,
                )
                self.store.approval_bundles[bundle.id] = bundle
                self.store.audits[strategy.id] = all_reports
                return ManualActionResponse(
                    strategy_id=strategy.id,
                    action=action,
                    loops_attempted=attempt,
                    escalated=False,
                    bundle=bundle,
                )

        summary = self.models.summarize_dissent(
            [report.model_dump(mode="json") for report in all_reports]
        )
        blocked_bundle = self.execution.create_bundle(
            strategy_id=strategy.id,
            action=action,
            target_allocations={},
            cooldown_seconds=self._step3_cooldown,
        )
        blocked_bundle.status = blocked_bundle.status.rejected
        self.store.approval_bundles[blocked_bundle.id] = blocked_bundle
        self.store.audits[strategy.id] = all_reports

        return ManualActionResponse(
            strategy_id=strategy.id,
            action=action,
            loops_attempted=self._max_loops,
            escalated=True,
            escalation_summary=summary,
            bundle=blocked_bundle,
        )

    def approval_step1(self, bundle_id: str, token: str) -> ApprovalBundle:
        bundle = self._bundle(bundle_id)
        updated = self.execution.apply_step1(bundle=bundle, token=token)
        self.store.approval_bundles[bundle_id] = updated
        return updated

    def approval_step2(self, bundle_id: str, token: str) -> ApprovalBundle:
        bundle = self._bundle(bundle_id)
        updated = self.execution.apply_step2(bundle=bundle, token=token)
        self.store.approval_bundles[bundle_id] = updated
        return updated

    def approval_step3(self, bundle_id: str, token: str) -> ApprovalBundle:
        bundle = self._bundle(bundle_id)
        updated = self.execution.apply_step3(bundle=bundle, token=token)
        self.store.approval_bundles[bundle_id] = updated
        return updated

    def _bundle(self, bundle_id: str) -> ApprovalBundle:
        if bundle_id not in self.store.approval_bundles:
            raise KeyError("Approval bundle not found")
        return self.store.approval_bundles[bundle_id]

    def link_ibkr(self, request: BrokerLinkRequest) -> UserPermissionProfile:
        profile = self.broker.link_account(user_id=request.user_id, account_id=request.account_id)
        self.store.permissions[request.user_id] = profile
        return profile

    def get_permissions(self, user_id: str) -> UserPermissionProfile:
        return self._ensure_permissions(user_id)

    def set_user_limits(self, user_id: str, request: BrokerLimitsRequest) -> UserPermissionProfile:
        profile = self._ensure_permissions(user_id)
        profile.user_limits.update(request.user_limits)
        self.store.permissions[user_id] = profile
        return profile

    def portfolio_performance(self, portfolio_id: str) -> PortfolioPerformanceResponse:
        strategy_metrics = {
            strategy_id: run.metrics for strategy_id, run in self.store.backtests.items()
        }

        benchmark_metrics: dict[str, object] = {}
        if self.store.backtests:
            first = next(iter(self.store.backtests.values()))
            benchmark_metrics = first.benchmark_metrics

        return PortfolioPerformanceResponse(
            portfolio_id=portfolio_id,
            strategies=strategy_metrics,
            benchmarks=benchmark_metrics,
        )
