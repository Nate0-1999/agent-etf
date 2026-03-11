from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_etf_audit import AuditCouncil
from agent_etf_backtest import DeterministicBacktestEngine
from agent_etf_brokers import IbkrPaperAdapter
from agent_etf_contracts.models import (
    AppendIdeationMessageRequest,
    ApprovalAction,
    ApprovalBundle,
    ApprovalStatus,
    ApprovedModelSet,
    AuditReport,
    BacktestRequest,
    BacktestRun,
    BrokerLimitsRequest,
    BrokerLinkRequest,
    CandidateInstrument,
    ClarifyIdeaRequest,
    ConvertIdeationSessionResponse,
    CouncilSummary,
    CreateIdeaRequest,
    CreateIdeationSessionRequest,
    CreateStrategyFromIdeaResponse,
    CurrentModelSetResponse,
    DecisionTile,
    DecisionTileStatus,
    DevResetResponse,
    DevSeedRequest,
    DevSeedResponse,
    HoldingsSummary,
    IdeaSpec,
    IdeaStatusResponse,
    IdeationMessage,
    IdeationSession,
    IdeationSessionDetailResponse,
    IdeationSessionListResponse,
    IdeationSessionStatus,
    IndexDetail,
    IndexListResponse,
    IndexSummary,
    ManualActionResponse,
    MessageRole,
    ModelProposalListResponse,
    ModelRefreshResponse,
    PortfolioPerformanceResponse,
    SpecGap,
    StrategyDefinition,
    StrategyListItem,
    StrategyListResponse,
    StrategyStatus,
    StrategySummaryResponse,
    UserPermissionProfile,
)
from agent_etf_contracts.store import StrategyStore, build_store
from agent_etf_execution import DeterministicStrategyCompiler, ExecutionService
from agent_etf_llm_gateway import OpenRouterModelRegistry, OpenRouterModelService
from agent_etf_research import ExaSearchProvider, ResearchService
from agent_etf_research.heavy_metals import derive_heavy_metal_profile

from apps.api.agent_etf_api.observability import current_request_id, current_test_run_id, recorder

_TILE_TITLES = [
    ("thesis", "Thesis"),
    ("exposure_map", "Exposure Map"),
    ("candidate_vehicles", "Candidate Vehicles"),
    ("weighting", "Weighting"),
    ("rebalance_maintenance", "Rebalance & Maintenance"),
    ("risk_constraints", "Risk & Constraints"),
    ("benchmarks", "Benchmarks"),
    ("approval_rules", "Approval Rules"),
    ("open_questions", "Open Questions"),
]
_DEFAULT_BENCHMARKS = ["sp500", "gold", "60_40", "cash"]


class ControlPlaneService:
    def __init__(self, store: StrategyStore | None = None) -> None:
        self._max_loops = int(os.getenv("AUDIT_MAX_RETRY_LOOPS", "3"))
        self._step3_cooldown = int(os.getenv("APPROVAL_STEP3_COOLDOWN_SECONDS", "600"))

        self.store = store or build_store()
        self.broker = IbkrPaperAdapter()
        self.models = OpenRouterModelService(monthly_budget_usd=150.0)
        self.model_registry = OpenRouterModelRegistry()
        self.search = ExaSearchProvider()
        self.research = ResearchService(search_provider=self.search, model_service=self.models)
        self.compiler = DeterministicStrategyCompiler()
        self.backtest_engine = DeterministicBacktestEngine()
        self.execution = ExecutionService(broker=self.broker)

        self.model_registry.ensure_current_model_set(self.store)

    def _record_event(self, action: str, payload: dict[str, Any]) -> None:
        recorder.record(
            category="service",
            action=action,
            request_id=current_request_id(),
            test_run_id=current_test_run_id(),
            payload=payload,
        )

    def _active_model_set(self) -> ApprovedModelSet:
        return self.model_registry.ensure_current_model_set(self.store)

    def _active_models(self) -> list[str]:
        return self.model_registry.approved_model_ids(self._active_model_set())

    @staticmethod
    def _normalize_name(text: str, fallback: str = "Untitled Index") -> str:
        clean = " ".join(text.strip().split())
        return clean[:72] if clean else fallback

    @staticmethod
    def _recommend_cadence(raw_idea: str) -> str | None:
        normalized = raw_idea.lower()
        if any(token in normalized for token in {"monthly", "month"}):
            return "monthly_review"
        if any(token in normalized for token in {"quarterly", "quarter"}):
            return "quarterly_review"
        if any(token in normalized for token in {"weekly", "week"}):
            return "weekly_review"
        if any(token in normalized for token in {"annual", "yearly"}):
            return "annual_review"
        if normalized:
            return "monthly_review"
        return None

    def _derive_constraints(self, raw_idea: str) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        normalized = raw_idea.lower()

        allowed_assets: list[str] = []
        if any(token in normalized for token in {"etf", "fund", "trust"}):
            allowed_assets.append("etf")
        if any(token in normalized for token in {"equity", "stock", "miners", "shares"}):
            allowed_assets.append("equity")
        if any(token in normalized for token in {"future", "futures", "commodity"}):
            allowed_assets.append("future")
        if not allowed_assets and normalized:
            allowed_assets = ["etf", "equity", "future"]
        if allowed_assets:
            constraints["allowed_assets"] = list(dict.fromkeys(allowed_assets))

        heavy_metal_profile = derive_heavy_metal_profile(raw_idea)
        if heavy_metal_profile is not None:
            constraints["periodic_table"] = heavy_metal_profile

        if "equal weight" in normalized:
            constraints["weighting_preference"] = "equal_weight"
        return constraints

    def _find_gaps(self, idea: IdeaSpec) -> list[SpecGap]:
        gaps: list[SpecGap] = []
        if not idea.objective or len(idea.objective.strip()) < 12:
            gaps.append(
                SpecGap(
                    field="objective",
                    reason=(
                        "A thesis sentence is needed before the council can structure the index."
                    ),
                    question="What exact investment thesis or theme should this index express?",
                )
            )
        if "allowed_assets" not in idea.constraints:
            gaps.append(
                SpecGap(
                    field="constraints.allowed_assets",
                    reason="Asset eligibility must be explicit for candidate discovery.",
                    question="Should this index use ETFs, equities, futures, or a mix?",
                )
            )
        if not idea.cadence_recommendation:
            gaps.append(
                SpecGap(
                    field="cadence_recommendation",
                    reason="Maintenance cadence must be user-reviewable.",
                    question="How often should this index be reviewed and rebalanced?",
                )
            )
        return gaps

    def _compute_clarity(self, gaps: list[SpecGap], required_fields: int = 3) -> float:
        complete = max(0, required_fields - len(gaps))
        return round(complete / required_fields, 4)

    def _ensure_permissions(self, user_id: str) -> UserPermissionProfile:
        profile = self.store.get_permission(user_id)
        if profile is None:
            profile = self.broker.link_account(user_id=user_id, account_id="paper-default")
            self.store.save_permission(profile)
        return profile

    def _messages_text(self, messages: list[IdeationMessage]) -> str:
        user_parts = [
            message.content.strip() for message in messages if message.role == MessageRole.user
        ]
        return "\n".join(part for part in user_parts if part)

    def _title_from_messages(self, messages: list[IdeationMessage], fallback: str) -> str:
        text = self._messages_text(messages)
        if not text:
            return fallback
        first_line = text.splitlines()[0]
        return self._normalize_name(first_line, fallback=fallback)

    def _build_idea_from_text(self, user_id: str, text: str) -> IdeaSpec:
        idea = IdeaSpec(
            id=str(uuid4()),
            user_id=user_id,
            raw_idea=text,
            objective=text.strip() if text.strip() else None,
            cadence_recommendation=self._recommend_cadence(text),
        )
        idea.constraints.update(self._derive_constraints(text))
        idea.clarity_score = self._compute_clarity(self._find_gaps(idea))
        return idea

    def _equal_weights(self, strategy: StrategyDefinition) -> dict[str, float]:
        if not strategy.universe:
            return {}
        size = len(strategy.universe)
        weight = round(1.0 / size, 6)
        return {item.symbol: weight for item in strategy.universe}

    def _proposal_bullets(self, strategy: StrategyDefinition, idea: IdeaSpec) -> list[str]:
        bullets = [
            f"Index name: {strategy.name}",
            f"Universe candidates: {len(strategy.universe)}",
            f"Weighting: {strategy.weighting_method}",
            f"Cadence recommendation: {idea.cadence_recommendation}",
            "Order actions require 3-step approval with cooldown",
        ]
        periodic_table = idea.constraints.get("periodic_table")
        if isinstance(periodic_table, dict):
            element_symbols = periodic_table.get("element_symbols", [])
            if isinstance(element_symbols, list) and element_symbols:
                bullets.insert(
                    1, "Target elements: " + ", ".join(str(item) for item in element_symbols)
                )
        return bullets

    def _build_strategy_name(self, idea: IdeaSpec) -> str:
        return self._normalize_name(idea.objective or idea.raw_idea, fallback="New Custom Index")

    def _create_strategy_for_idea(
        self, idea: IdeaSpec
    ) -> tuple[StrategyDefinition, list[AuditReport]]:
        permissions = self._ensure_permissions(idea.user_id)
        candidates = self.research.discover_candidates(idea=idea, permissions=permissions)
        candidate_payload = {
            "idea_id": idea.id,
            "requires_user_approval": True,
            "thesis": idea.objective or idea.raw_idea,
            "candidates": [item.model_dump(mode="json") for item in candidates],
        }
        council = AuditCouncil(provider=self.models, models=self._active_models())
        result = council.evaluate(stage="candidate_ranking", payload=candidate_payload)
        if not result.passed:
            self.store.save_audit_reports(idea.id, result.reports)
            raise ValueError("Audit council dissent while generating strategy proposal")

        strategy = StrategyDefinition(
            id=str(uuid4()),
            user_id=idea.user_id,
            idea_id=idea.id,
            name=self._build_strategy_name(idea),
            status=StrategyStatus.draft,
            universe=candidates,
            weighting_method=str(idea.constraints.get("weighting_preference", "equal_weight")),
            rebalance_rule="user_approved_schedule",
            update_rule="agent_recommended_user_approved",
        )
        self.store.save_strategy(strategy)
        self.store.save_strategy_artifact(self.compiler.compile(strategy))
        self.store.save_audit_reports(strategy.id, result.reports)
        return strategy, result.reports

    def create_idea(self, request: CreateIdeaRequest) -> IdeaStatusResponse:
        idea_id = str(uuid4())
        idea = IdeaSpec(
            id=idea_id,
            user_id=request.user_id,
            raw_idea=request.raw_idea,
            objective=request.raw_idea.strip() if len(request.raw_idea.split()) >= 4 else None,
            cadence_recommendation=self._recommend_cadence(request.raw_idea),
        )
        idea.constraints.update(self._derive_constraints(request.raw_idea))
        gaps = self._find_gaps(idea)
        idea.clarity_score = self._compute_clarity(gaps)
        self.store.save_idea(idea)
        self.store.save_idea_gaps(idea_id, gaps)
        return IdeaStatusResponse(
            idea=idea, gaps=gaps, ready_for_strategy=idea.clarity_score >= 0.85
        )

    def clarify_idea(self, idea_id: str, request: ClarifyIdeaRequest) -> IdeaStatusResponse:
        idea = self.store.get_idea(idea_id)
        if idea is None:
            raise KeyError("Idea not found")
        answers = request.answers
        if "objective" in answers:
            idea.objective = str(answers["objective"])
        if "allowed_assets" in answers:
            value = answers["allowed_assets"]
            idea.constraints["allowed_assets"] = value if isinstance(value, list) else [str(value)]
        if "cadence_recommendation" in answers:
            idea.cadence_recommendation = str(answers["cadence_recommendation"])
        if "exclusions" in answers and isinstance(answers["exclusions"], list):
            idea.exclusions = [str(item) for item in answers["exclusions"]]
        for key, value in self._derive_constraints(idea.objective or idea.raw_idea).items():
            if key not in idea.constraints:
                idea.constraints[key] = value
        gaps = self._find_gaps(idea)
        idea.clarity_score = self._compute_clarity(gaps)
        self.store.save_idea(idea)
        self.store.save_idea_gaps(idea_id, gaps)
        return IdeaStatusResponse(
            idea=idea, gaps=gaps, ready_for_strategy=idea.clarity_score >= 0.85
        )

    def idea_status(self, idea_id: str) -> IdeaStatusResponse:
        idea = self.store.get_idea(idea_id)
        if idea is None:
            raise KeyError("Idea not found")
        gaps = self.store.get_idea_gaps(idea_id)
        return IdeaStatusResponse(
            idea=idea, gaps=gaps, ready_for_strategy=idea.clarity_score >= 0.85
        )

    def create_strategy_from_idea(self, idea_id: str) -> CreateStrategyFromIdeaResponse:
        status = self.idea_status(idea_id)
        if not status.ready_for_strategy:
            raise ValueError("Idea clarity threshold not reached")
        strategy, reports = self._create_strategy_for_idea(status.idea)
        return CreateStrategyFromIdeaResponse(
            strategy=strategy,
            audits=reports,
            proposal_bullets=self._proposal_bullets(strategy, status.idea),
        )

    def set_strategy_status(self, strategy_id: str, approved: bool) -> StrategyDefinition:
        strategy = self._strategy(strategy_id)
        strategy.status = StrategyStatus.active if approved else StrategyStatus.paused
        self.store.save_strategy(strategy)
        return strategy

    def run_backtest(self, strategy_id: str, request: BacktestRequest) -> BacktestRun:
        strategy = self._strategy(strategy_id)
        run = self.backtest_engine.run(
            strategy=strategy,
            min_years=request.min_years,
            override_min_history=request.override_min_history,
        )
        self.store.save_backtest(run)
        return run

    def _strategy(self, strategy_id: str) -> StrategyDefinition:
        strategy = self.store.get_strategy(strategy_id)
        if strategy is None:
            raise KeyError("Strategy not found")
        return strategy

    def list_strategies(self) -> StrategyListResponse:
        items: list[StrategyListItem] = []
        for strategy in self.store.list_strategies():
            latest_backtest = self.store.get_backtest(strategy.id)
            items.append(
                StrategyListItem(
                    id=strategy.id,
                    name=strategy.name,
                    status=strategy.status,
                    created_at=strategy.created_at,
                    universe_size=len(strategy.universe),
                    last_backtest_cagr=None
                    if latest_backtest is None
                    else latest_backtest.metrics.cagr,
                )
            )
        return StrategyListResponse(strategies=items)

    def strategy_summary(self, strategy_id: str) -> StrategySummaryResponse:
        strategy = self._strategy(strategy_id)
        idea = self.store.get_idea(strategy.idea_id)
        audits = self.store.get_audit_reports(strategy.id)
        latest_backtest = self.store.get_backtest(strategy.id)
        bundles = self.store.list_approval_bundles(strategy.id)
        latest_bundle = bundles[0] if bundles else None
        order_preview = (
            self.execution.order_preview(latest_bundle) if latest_bundle is not None else None
        )
        return StrategySummaryResponse(
            strategy=strategy,
            idea=idea,
            audits=audits,
            proposal_bullets=[] if idea is None else self._proposal_bullets(strategy, idea),
            latest_backtest=latest_backtest,
            latest_bundle=latest_bundle,
            latest_order_preview=order_preview,
        )

    def _run_runtime_council(
        self, strategy: StrategyDefinition, stage: str
    ) -> tuple[bool, list[AuditReport]]:
        council = AuditCouncil(provider=self.models, models=self._active_models())
        payload = {
            "strategy_id": strategy.id,
            "requires_user_approval": True,
            "thesis": strategy.name,
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
                self.store.save_approval_bundle(bundle)
                self.store.save_audit_reports(strategy.id, all_reports)
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
        blocked_bundle.status = ApprovalStatus.rejected
        self.store.save_approval_bundle(blocked_bundle)
        self.store.save_audit_reports(strategy.id, all_reports)
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
        self.store.save_approval_bundle(updated)
        return updated

    def approval_step2(self, bundle_id: str, token: str) -> ApprovalBundle:
        bundle = self._bundle(bundle_id)
        updated = self.execution.apply_step2(bundle=bundle, token=token)
        self.store.save_approval_bundle(updated)
        return updated

    def approval_step3(self, bundle_id: str, token: str) -> ApprovalBundle:
        bundle = self._bundle(bundle_id)
        updated = self.execution.apply_step3(bundle=bundle, token=token)
        self.store.save_approval_bundle(updated)
        return updated

    def _bundle(self, bundle_id: str) -> ApprovalBundle:
        bundle = self.store.get_approval_bundle(bundle_id)
        if bundle is None:
            raise KeyError("Approval bundle not found")
        return bundle

    def link_ibkr(self, request: BrokerLinkRequest) -> UserPermissionProfile:
        profile = self.broker.link_account(user_id=request.user_id, account_id=request.account_id)
        self.store.save_permission(profile)
        return profile

    def get_permissions(self, user_id: str) -> UserPermissionProfile:
        return self._ensure_permissions(user_id)

    def set_user_limits(self, user_id: str, request: BrokerLimitsRequest) -> UserPermissionProfile:
        profile = self._ensure_permissions(user_id)
        profile.user_limits.update(request.user_limits)
        self.store.save_permission(profile)
        return profile

    def portfolio_performance(self, portfolio_id: str) -> PortfolioPerformanceResponse:
        backtests = self.store.list_backtests()
        strategy_metrics = {strategy_id: run.metrics for strategy_id, run in backtests.items()}
        benchmark_metrics: dict[str, object] = {}
        if backtests:
            first = next(iter(backtests.values()))
            benchmark_metrics = first.benchmark_metrics
        return PortfolioPerformanceResponse(
            portfolio_id=portfolio_id,
            strategies=strategy_metrics,
            benchmarks=benchmark_metrics,
        )

    def _empty_tiles(self) -> list[DecisionTile]:
        return [
            DecisionTile(
                key=key, title=title, status=DecisionTileStatus.empty, summary="Awaiting input."
            )
            for key, title in _TILE_TITLES
        ]

    def create_ideation_session(
        self, request: CreateIdeationSessionRequest
    ) -> IdeationSessionDetailResponse:
        session = IdeationSession(
            id=str(uuid4()),
            user_id=request.user_id,
            title=self._normalize_name(request.title or "New Idea", fallback="New Idea"),
            decision_tiles=self._empty_tiles(),
            council_summary=CouncilSummary(
                stage="session_ideation",
                headline="Awaiting your thesis to start the workbook.",
                passed=True,
                reports=[],
                active_model_set_id=self._active_model_set().id,
            ),
        )
        welcome = IdeationMessage(
            id=str(uuid4()),
            session_id=session.id,
            role=MessageRole.assistant,
            content=(
                "Start with the thesis, constraints, or benchmark you care about. "
                "I will populate the workbook tiles as the session becomes more specific."
            ),
        )
        self.store.save_ideation_session(session)
        self.store.save_ideation_message(welcome)
        self._record_event(
            "create_ideation_session",
            {"session_id": session.id, "title": session.title, "user_id": session.user_id},
        )
        return IdeationSessionDetailResponse(session=session, messages=[welcome])

    def list_ideation_sessions(self, user_id: str = "operator") -> IdeationSessionListResponse:
        return IdeationSessionListResponse(
            sessions=self.store.list_ideation_sessions(user_id=user_id)
        )

    def get_ideation_session(self, session_id: str) -> IdeationSessionDetailResponse:
        session = self.store.get_ideation_session(session_id)
        if session is None:
            raise KeyError("Ideation session not found")
        return IdeationSessionDetailResponse(
            session=session,
            messages=self.store.list_ideation_messages(session_id),
        )

    def _session_state(
        self,
        session: IdeationSession,
        messages: list[IdeationMessage],
    ) -> tuple[IdeationSession, list[CandidateInstrument], list[AuditReport], list[SpecGap]]:
        thesis = self._messages_text(messages)
        idea = self._build_idea_from_text(session.user_id, thesis)
        idea.id = session.id
        idea.raw_idea = thesis
        gaps = self._find_gaps(idea)
        permissions = self._ensure_permissions(session.user_id)
        candidates = self.research.discover_candidates(idea=idea, permissions=permissions)
        council = AuditCouncil(provider=self.models, models=self._active_models())
        payload = {
            "session_id": session.id,
            "requires_user_approval": True,
            "thesis": thesis,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }
        result = council.evaluate(stage="session_ideation", payload=payload)
        self.store.save_audit_reports(f"session:{session.id}", result.reports)
        next_status = (
            IdeationSessionStatus.ready_to_convert
            if idea.clarity_score >= 0.85
            else IdeationSessionStatus.drafting
        )
        tiles = self._build_tiles(
            idea=idea, candidates=candidates, gaps=gaps, council_passed=result.passed
        )
        next_session = session.model_copy(
            update={
                "title": self._title_from_messages(messages, fallback=session.title),
                "status": next_status,
                "raw_thesis": thesis,
                "decision_tiles": tiles,
                "council_summary": CouncilSummary(
                    stage="session_ideation",
                    headline=self._council_headline(result.passed, gaps, candidates),
                    passed=result.passed,
                    reports=result.reports,
                    active_model_set_id=self._active_model_set().id,
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self.store.save_ideation_session(next_session)
        self.store.save_idea(idea)
        self.store.save_idea_gaps(idea.id, gaps)
        self._record_event(
            "session_state_recomputed",
            {
                "session_id": session.id,
                "status": next_session.status,
                "candidate_count": len(candidates),
                "gap_count": len(gaps),
                "council_passed": result.passed,
            },
        )
        return next_session, candidates, result.reports, gaps

    def _council_headline(
        self,
        passed: bool,
        gaps: list[SpecGap],
        candidates: list[CandidateInstrument],
    ) -> str:
        if not passed:
            return "The council found blocking issues in the current thesis state."
        if gaps:
            return (
                "The council has enough context to proceed, but "
                f"{len(gaps)} open question(s) remain."
            )
        return (
            f"The council is aligned. {len(candidates)} candidate vehicles are currently in scope."
        )

    def _build_tiles(
        self,
        idea: IdeaSpec,
        candidates: list[CandidateInstrument],
        gaps: list[SpecGap],
        council_passed: bool,
    ) -> list[DecisionTile]:
        missing_fields = {gap.field for gap in gaps}
        weighting = str(idea.constraints.get("weighting_preference", "equal_weight"))
        exposure_bullets: list[str] = []
        periodic_table = idea.constraints.get("periodic_table")
        if isinstance(periodic_table, dict):
            names = periodic_table.get("element_names", [])
            if isinstance(names, list):
                exposure_bullets = [str(name) for name in names[:8]]
        if not exposure_bullets and idea.objective:
            exposure_bullets = [idea.objective[:120]]

        open_questions = [gap.question for gap in gaps]
        candidate_status = (
            DecisionTileStatus.resolved if candidates else DecisionTileStatus.needs_user_input
        )
        if not council_passed:
            candidate_status = DecisionTileStatus.blocked_by_council

        tile_map = {
            "thesis": DecisionTile(
                key="thesis",
                title="Thesis",
                status=DecisionTileStatus.resolved
                if idea.objective
                else DecisionTileStatus.in_progress,
                summary=idea.objective or "Describe the investment thesis in plain language.",
            ),
            "exposure_map": DecisionTile(
                key="exposure_map",
                title="Exposure Map",
                status=DecisionTileStatus.resolved
                if exposure_bullets
                else DecisionTileStatus.in_progress,
                summary="Target exposures the index is trying to capture.",
                bullets=exposure_bullets,
            ),
            "candidate_vehicles": DecisionTile(
                key="candidate_vehicles",
                title="Candidate Vehicles",
                status=candidate_status,
                summary="Tradable vehicles currently mapped to the thesis.",
                bullets=[f"{item.symbol}: {item.name}" for item in candidates[:6]],
            ),
            "weighting": DecisionTile(
                key="weighting",
                title="Weighting",
                status=DecisionTileStatus.resolved if weighting else DecisionTileStatus.in_progress,
                summary=weighting.replace("_", " "),
                bullets=["Default is equal weight until you specify otherwise."],
            ),
            "rebalance_maintenance": DecisionTile(
                key="rebalance_maintenance",
                title="Rebalance & Maintenance",
                status=DecisionTileStatus.resolved
                if idea.cadence_recommendation
                else DecisionTileStatus.needs_user_input,
                summary=idea.cadence_recommendation or "Choose a maintenance cadence.",
                bullets=["Manual trigger remains available at any time."],
            ),
            "risk_constraints": DecisionTile(
                key="risk_constraints",
                title="Risk & Constraints",
                status=(
                    DecisionTileStatus.in_progress
                    if "constraints.allowed_assets" in missing_fields
                    else DecisionTileStatus.resolved
                ),
                summary="Asset-type constraints and exclusions in scope.",
                bullets=[
                    "Allowed assets: "
                    + (", ".join(idea.constraints.get("allowed_assets", [])) or "unspecified"),
                    f"Exclusions: {', '.join(idea.exclusions) or 'none'}",
                ],
            ),
            "benchmarks": DecisionTile(
                key="benchmarks",
                title="Benchmarks",
                status=DecisionTileStatus.resolved,
                summary="Default benchmark set used for comparison.",
                bullets=_DEFAULT_BENCHMARKS,
            ),
            "approval_rules": DecisionTile(
                key="approval_rules",
                title="Approval Rules",
                status=DecisionTileStatus.resolved,
                summary="Every order path requires the same redundant user approval chain.",
                bullets=[
                    "Password + TOTP",
                    "Out-of-band confirmation",
                    "Timed final reconfirmation",
                ],
            ),
            "open_questions": DecisionTile(
                key="open_questions",
                title="Open Questions",
                status=DecisionTileStatus.needs_user_input
                if open_questions
                else DecisionTileStatus.resolved,
                summary="Outstanding questions before conversion.",
                bullets=open_questions or ["No blocking questions at the moment."],
            ),
        }
        return [tile_map[key] for key, _ in _TILE_TITLES]

    def _assistant_reply(
        self,
        session: IdeationSession,
        candidates: list[CandidateInstrument],
        gaps: list[SpecGap],
    ) -> str:
        resolved_tiles = [
            tile.title
            for tile in session.decision_tiles
            if tile.status == DecisionTileStatus.resolved
        ]
        message_parts = [
            f"Workbook updated for '{session.title}'.",
            f"Resolved tiles: {', '.join(resolved_tiles[:5]) or 'none yet'}.",
            "Candidate vehicles in scope: "
            + (", ".join(item.symbol for item in candidates[:4]) or "none yet")
            + ".",
        ]
        if gaps:
            message_parts.append("Open questions: " + " | ".join(gap.question for gap in gaps[:2]))
        else:
            message_parts.append("This session is ready to convert into a saved index draft.")
        return " ".join(message_parts)

    def append_ideation_message(
        self,
        session_id: str,
        request: AppendIdeationMessageRequest,
    ) -> IdeationSessionDetailResponse:
        session = self.store.get_ideation_session(session_id)
        if session is None:
            raise KeyError("Ideation session not found")
        user_message = IdeationMessage(
            id=str(uuid4()),
            session_id=session_id,
            role=MessageRole.user,
            content=request.content.strip(),
        )
        self.store.save_ideation_message(user_message)
        messages = self.store.list_ideation_messages(session_id)
        next_session, candidates, _, gaps = self._session_state(session, messages)
        assistant = IdeationMessage(
            id=str(uuid4()),
            session_id=session_id,
            role=MessageRole.assistant,
            content=self._assistant_reply(next_session, candidates, gaps),
        )
        self.store.save_ideation_message(assistant)
        self._record_event(
            "append_ideation_message",
            {
                "session_id": session_id,
                "message_length": len(user_message.content),
                "resulting_status": next_session.status,
            },
        )
        return IdeationSessionDetailResponse(
            session=next_session,
            messages=self.store.list_ideation_messages(session_id),
        )

    def _index_from_strategy(
        self,
        strategy: StrategyDefinition,
        session: IdeationSession,
        latest_backtest: BacktestRun,
    ) -> IndexDetail:
        bundles = self.store.list_approval_bundles(strategy.id)
        latest_bundle = bundles[0] if bundles else None
        holdings = [
            HoldingsSummary(
                symbol=item.symbol,
                name=item.name,
                weight=self._equal_weights(strategy).get(item.symbol, 0.0),
                asset_type=item.asset_type,
                exchange=item.exchange,
            )
            for item in strategy.universe
        ]
        return IndexDetail(
            id=str(uuid4()),
            strategy_id=strategy.id,
            name=strategy.name,
            status=strategy.status,
            thesis_summary=session.raw_thesis or strategy.name,
            holdings=holdings,
            performance=latest_backtest.timeframe_performance,
            benchmark_summary=latest_backtest.benchmark_metrics,
            rebalance_cadence=strategy.rebalance_rule,
            approval_status=None if latest_bundle is None else latest_bundle.status,
            council_summary=session.council_summary,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def convert_ideation_session(self, session_id: str) -> ConvertIdeationSessionResponse:
        detail = self.get_ideation_session(session_id)
        session = detail.session
        if not session.raw_thesis.strip():
            raise ValueError("Ideation session is blank")
        idea = self._build_idea_from_text(session.user_id, session.raw_thesis)
        idea.id = str(uuid4())
        self.store.save_idea(idea)
        self.store.save_idea_gaps(idea.id, self._find_gaps(idea))
        strategy, _ = self._create_strategy_for_idea(idea)
        backtest = self.backtest_engine.run(strategy, min_years=10, override_min_history=False)
        self.store.save_backtest(backtest)
        index = self._index_from_strategy(strategy, session, backtest)
        self.store.save_index(index)
        updated_session = session.model_copy(
            update={
                "status": IdeationSessionStatus.converted,
                "linked_index_id": index.id,
                "updated_at": datetime.now(UTC),
            }
        )
        self.store.save_ideation_session(updated_session)
        self._record_event(
            "convert_ideation_session",
            {
                "session_id": session_id,
                "index_id": index.id,
                "strategy_id": strategy.id,
                "holding_count": len(index.holdings),
            },
        )
        return ConvertIdeationSessionResponse(session=updated_session, index=index)

    def list_indexes(self) -> IndexListResponse:
        items = [
            IndexSummary(
                id=item.id,
                strategy_id=item.strategy_id,
                name=item.name,
                status=item.status,
                thesis_summary=item.thesis_summary,
                holdings_count=len(item.holdings),
                rebalance_cadence=item.rebalance_cadence,
                created_at=item.created_at,
                latest_cagr=next(
                    (
                        performance.strategy_return
                        for performance in item.performance
                        if performance.timeframe == "1Y"
                    ),
                    None,
                ),
            )
            for item in self.store.list_indexes()
        ]
        return IndexListResponse(indexes=items)

    def get_index(self, index_id: str) -> IndexDetail:
        index = self.store.get_index(index_id)
        if index is None:
            raise KeyError("Index not found")
        return index

    def open_ideation_from_index(self, index_id: str) -> IdeationSessionDetailResponse:
        index = self.get_index(index_id)
        session = IdeationSession(
            id=str(uuid4()),
            user_id="operator",
            title=f"Revisit {self._normalize_name(index.name, fallback='Index')}",
            raw_thesis=index.thesis_summary,
            status=IdeationSessionStatus.drafting,
            decision_tiles=self._empty_tiles(),
            council_summary=CouncilSummary(
                stage="session_ideation",
                headline="This workbook was opened from a saved index.",
                passed=True,
                reports=[],
                active_model_set_id=self._active_model_set().id,
            ),
        )
        self.store.save_ideation_session(session)
        seeded = IdeationMessage(
            id=str(uuid4()),
            session_id=session.id,
            role=MessageRole.assistant,
            content=(
                f"Opened a new ideation workbook from '{index.name}'. "
                "Add changes to the thesis, holdings, or constraints on the right."
            ),
        )
        self.store.save_ideation_message(seeded)
        self._record_event(
            "open_ideation_from_index",
            {"index_id": index_id, "session_id": session.id},
        )
        return self.append_ideation_message(
            session.id,
            AppendIdeationMessageRequest(content=index.thesis_summary),
        )

    def current_model_set(self) -> CurrentModelSetResponse:
        return CurrentModelSetResponse(model_set=self._active_model_set())

    def list_model_proposals(self) -> ModelProposalListResponse:
        return ModelProposalListResponse(proposals=self.store.list_model_proposals())

    def refresh_models(self) -> ModelRefreshResponse:
        catalog, current, proposal = self.model_registry.refresh(self.store)
        self._record_event(
            "refresh_models",
            {
                "catalog_size": len(catalog),
                "current_model_set_id": current.id,
                "proposal_id": None if proposal is None else proposal.id,
            },
        )
        return ModelRefreshResponse(catalog=catalog, current=current, proposal=proposal)

    def approve_model_proposal(self, proposal_id: str) -> CurrentModelSetResponse:
        model_set = self.model_registry.approve(self.store, proposal_id)
        self._record_event(
            "approve_model_proposal",
            {"proposal_id": proposal_id, "model_set_id": model_set.id},
        )
        return CurrentModelSetResponse(model_set=model_set)

    def dev_reset(self) -> DevResetResponse:
        self.store.clear_runtime_data()
        recorder.clear()
        self.model_registry.ensure_current_model_set(self.store)
        self._record_event("dev_reset", {"cleared": True})
        return DevResetResponse(cleared=True, message="Local runtime data cleared.")

    def dev_seed(self, request: DevSeedRequest) -> DevSeedResponse:
        scenario = request.scenario.strip().lower()
        self.store.clear_runtime_data()
        recorder.clear()
        self.model_registry.ensure_current_model_set(self.store)

        if scenario == "blank":
            self._record_event("dev_seed", {"scenario": scenario})
            return DevSeedResponse(scenario=scenario, message="Blank runtime fixture loaded.")

        session = self.create_ideation_session(
            CreateIdeationSessionRequest(user_id="operator", title="Seeded Idea")
        )

        if scenario == "draft_session":
            seeded = self.append_ideation_message(
                session.session.id,
                AppendIdeationMessageRequest(
                    content=(
                        "Build a quality-focused industrial innovation index using liquid ETFs "
                        "and large-cap equities with monthly review."
                    )
                ),
            )
            self._record_event(
                "dev_seed",
                {"scenario": scenario, "session_id": seeded.session.id},
            )
            return DevSeedResponse(
                scenario=scenario,
                created_session_id=seeded.session.id,
                message="Draft ideation session fixture loaded.",
            )

        if scenario == "saved_index":
            seeded = self.append_ideation_message(
                session.session.id,
                AppendIdeationMessageRequest(
                    content=(
                        "Build a quality-focused industrial innovation index using liquid ETFs "
                        "and large-cap equities, equal weight, monthly review, benchmarked "
                        "against the S&P 500 and gold."
                    )
                ),
            )
            converted = self.convert_ideation_session(seeded.session.id)
            self._record_event(
                "dev_seed",
                {
                    "scenario": scenario,
                    "session_id": converted.session.id,
                    "index_id": converted.index.id,
                },
            )
            return DevSeedResponse(
                scenario=scenario,
                created_session_id=converted.session.id,
                created_index_id=converted.index.id,
                message="Saved index fixture loaded.",
            )

        raise ValueError(f"Unknown dev seed scenario: {request.scenario}")
