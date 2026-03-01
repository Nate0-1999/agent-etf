from __future__ import annotations

from dataclasses import dataclass, field

from agent_etf_contracts.models import (
    ApprovalBundle,
    AuditReport,
    BacktestRun,
    IdeaSpec,
    SpecGap,
    StrategyArtifact,
    StrategyDefinition,
    UserPermissionProfile,
)


@dataclass
class InMemoryStore:
    ideas: dict[str, IdeaSpec] = field(default_factory=dict)
    idea_gaps: dict[str, list[SpecGap]] = field(default_factory=dict)
    strategies: dict[str, StrategyDefinition] = field(default_factory=dict)
    strategy_artifacts: dict[str, StrategyArtifact] = field(default_factory=dict)
    audits: dict[str, list[AuditReport]] = field(default_factory=dict)
    backtests: dict[str, BacktestRun] = field(default_factory=dict)
    approval_bundles: dict[str, ApprovalBundle] = field(default_factory=dict)
    permissions: dict[str, UserPermissionProfile] = field(default_factory=dict)
