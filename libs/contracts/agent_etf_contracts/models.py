from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StrategyStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"


class AuditVerdict(StrEnum):
    passed = "pass"
    dissent = "dissent"


class ApprovalStatus(StrEnum):
    pending = "pending"
    step1_complete = "step1_complete"
    step2_complete = "step2_complete"
    approved = "approved"
    expired = "expired"
    rejected = "rejected"


class ApprovalAction(StrEnum):
    create = "create"
    rebalance = "rebalance"
    update = "update"


class DecisionTileStatus(StrEnum):
    empty = "empty"
    in_progress = "in_progress"
    resolved = "resolved"
    needs_user_input = "needs_user_input"
    blocked_by_council = "blocked_by_council"


class IdeationSessionStatus(StrEnum):
    drafting = "drafting"
    ready_to_convert = "ready_to_convert"
    converted = "converted"


class MessageRole(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    council = "council"


class ModelProviderFamily(StrEnum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"


class ModelProposalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    superseded = "superseded"


class IdeaSpec(BaseModel):
    id: str
    user_id: str
    raw_idea: str
    objective: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list)
    cadence_recommendation: str | None = None
    clarity_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpecGap(BaseModel):
    field: str
    reason: str
    question: str


class CandidateInstrument(BaseModel):
    symbol: str
    name: str
    asset_type: str
    exchange: str
    relevance_score: float
    rationale: str
    sources: list[str] = Field(default_factory=list)


class StrategyDefinition(BaseModel):
    id: str
    user_id: str
    idea_id: str
    name: str
    status: StrategyStatus = StrategyStatus.draft
    universe: list[CandidateInstrument] = Field(default_factory=list)
    weighting_method: str
    rebalance_rule: str
    update_rule: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StrategyArtifact(BaseModel):
    strategy_id: str
    git_commit: str
    config_hash: str
    source_code: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditReport(BaseModel):
    stage: str
    model: str
    verdict: AuditVerdict
    reasons: list[str] = Field(default_factory=list)
    content_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalBundle(BaseModel):
    id: str
    strategy_id: str
    action: ApprovalAction
    intent_hash: str
    target_allocations: dict[str, float]
    cooldown_seconds: int
    step1_at: datetime | None = None
    step2_at: datetime | None = None
    step3_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserPermissionProfile(BaseModel):
    user_id: str
    broker: str
    account_id: str
    tradable_asset_types: list[str] = Field(default_factory=list)
    tradable_markets: list[str] = Field(default_factory=list)
    max_leverage: float = 1.0
    allow_short: bool = False
    user_limits: dict[str, Any] = Field(default_factory=dict)


class OrderPreviewItem(BaseModel):
    symbol: str
    target_weight: float
    action: str


class OrderPreviewResponse(BaseModel):
    strategy_id: str
    action: str
    orders: list[OrderPreviewItem]


class BacktestRequest(BaseModel):
    min_years: int = 10
    override_min_history: bool = False


class BacktestMetrics(BaseModel):
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float
    years_of_history: int


class TimeframePerformance(BaseModel):
    timeframe: str
    strategy_return: float
    benchmark_returns: dict[str, float] = Field(default_factory=dict)


class BacktestRun(BaseModel):
    strategy_id: str
    assumptions: dict[str, Any]
    metrics: BacktestMetrics
    benchmark_metrics: dict[str, BacktestMetrics]
    timeframe_performance: list[TimeframePerformance] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioPerformanceResponse(BaseModel):
    portfolio_id: str
    strategies: dict[str, BacktestMetrics]
    benchmarks: dict[str, BacktestMetrics]


class StrategyListItem(BaseModel):
    id: str
    name: str
    status: StrategyStatus
    created_at: datetime
    universe_size: int
    last_backtest_cagr: float | None = None


class StrategyListResponse(BaseModel):
    strategies: list[StrategyListItem]


class StrategySummaryResponse(BaseModel):
    strategy: StrategyDefinition
    idea: IdeaSpec | None = None
    audits: list[AuditReport] = Field(default_factory=list)
    proposal_bullets: list[str] = Field(default_factory=list)
    latest_backtest: BacktestRun | None = None
    latest_bundle: ApprovalBundle | None = None
    latest_order_preview: OrderPreviewResponse | None = None


class DecisionTile(BaseModel):
    key: str
    title: str
    status: DecisionTileStatus
    summary: str
    bullets: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CouncilSummary(BaseModel):
    stage: str
    headline: str
    passed: bool
    reports: list[AuditReport] = Field(default_factory=list)
    active_model_set_id: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdeationMessage(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdeationSession(BaseModel):
    id: str
    user_id: str
    title: str
    status: IdeationSessionStatus = IdeationSessionStatus.drafting
    raw_thesis: str = ""
    decision_tiles: list[DecisionTile] = Field(default_factory=list)
    council_summary: CouncilSummary | None = None
    linked_index_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HoldingsSummary(BaseModel):
    symbol: str
    name: str
    weight: float
    asset_type: str
    exchange: str


class IndexSummary(BaseModel):
    id: str
    strategy_id: str
    name: str
    status: StrategyStatus
    thesis_summary: str
    holdings_count: int
    rebalance_cadence: str
    created_at: datetime
    latest_cagr: float | None = None


class IndexDetail(BaseModel):
    id: str
    strategy_id: str
    name: str
    status: StrategyStatus
    thesis_summary: str
    holdings: list[HoldingsSummary] = Field(default_factory=list)
    performance: list[TimeframePerformance] = Field(default_factory=list)
    benchmark_summary: dict[str, BacktestMetrics] = Field(default_factory=dict)
    rebalance_cadence: str
    approval_status: ApprovalStatus | None = None
    council_summary: CouncilSummary | None = None
    created_at: datetime
    updated_at: datetime


class ModelCatalogEntry(BaseModel):
    id: str
    provider: ModelProviderFamily
    family: str
    label: str
    openrouter_slug: str
    official_doc_url: str
    is_stable: bool = True
    supports_text: bool = True
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovedModelSet(BaseModel):
    id: str
    openai_model: ModelCatalogEntry
    anthropic_model: ModelCatalogEntry
    google_model: ModelCatalogEntry
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "active"


class PendingModelSetProposal(BaseModel):
    id: str
    current_set_id: str | None = None
    proposed_set: ApprovedModelSet
    rationale: str
    status: ModelProposalStatus = ModelProposalStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None


class CreateIdeaRequest(BaseModel):
    user_id: str = "operator"
    raw_idea: str


class ClarifyIdeaRequest(BaseModel):
    answers: dict[str, Any]


class IdeaStatusResponse(BaseModel):
    idea: IdeaSpec
    gaps: list[SpecGap]
    ready_for_strategy: bool


class CreateStrategyFromIdeaResponse(BaseModel):
    strategy: StrategyDefinition
    audits: list[AuditReport]
    proposal_bullets: list[str]


class ApprovalStepRequest(BaseModel):
    token: str


class ApprovalBundleResponse(BaseModel):
    bundle: ApprovalBundle


class ManualActionResponse(BaseModel):
    strategy_id: str
    action: ApprovalAction
    loops_attempted: int
    escalated: bool
    escalation_summary: str | None = None
    bundle: ApprovalBundle


class BrokerLinkRequest(BaseModel):
    user_id: str = "operator"
    account_id: str


class BrokerLimitsRequest(BaseModel):
    user_limits: dict[str, Any]


class CreateIdeationSessionRequest(BaseModel):
    user_id: str = "operator"
    title: str | None = None


class AppendIdeationMessageRequest(BaseModel):
    content: str


class IdeationSessionListResponse(BaseModel):
    sessions: list[IdeationSession]


class IdeationSessionDetailResponse(BaseModel):
    session: IdeationSession
    messages: list[IdeationMessage] = Field(default_factory=list)


class ConvertIdeationSessionResponse(BaseModel):
    session: IdeationSession
    index: IndexDetail


class IndexListResponse(BaseModel):
    indexes: list[IndexSummary]


class CurrentModelSetResponse(BaseModel):
    model_set: ApprovedModelSet


class ModelProposalListResponse(BaseModel):
    proposals: list[PendingModelSetProposal]


class ModelRefreshResponse(BaseModel):
    catalog: list[ModelCatalogEntry]
    current: ApprovedModelSet
    proposal: PendingModelSetProposal | None = None


class DevResetResponse(BaseModel):
    cleared: bool
    message: str


class DevSeedRequest(BaseModel):
    scenario: str = "blank"


class DevSeedResponse(BaseModel):
    scenario: str
    created_session_id: str | None = None
    created_index_id: str | None = None
    message: str


class DevEvent(BaseModel):
    id: str
    category: str
    action: str
    request_id: str | None = None
    test_run_id: str | None = None
    route: str | None = None
    status_code: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DevEventListResponse(BaseModel):
    events: list[DevEvent] = Field(default_factory=list)
