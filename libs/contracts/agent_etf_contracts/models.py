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


class BacktestRequest(BaseModel):
    min_years: int = 10
    override_min_history: bool = False


class BacktestMetrics(BaseModel):
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float
    years_of_history: int


class BacktestRun(BaseModel):
    strategy_id: str
    assumptions: dict[str, Any]
    metrics: BacktestMetrics
    benchmark_metrics: dict[str, BacktestMetrics]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioPerformanceResponse(BaseModel):
    portfolio_id: str
    strategies: dict[str, BacktestMetrics]
    benchmarks: dict[str, BacktestMetrics]


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
