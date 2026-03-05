from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

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

psycopg: Any
sql: Any
dict_row: Any
Jsonb: Any

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - exercised when Postgres deps are absent.
    psycopg = None
    sql = None
    dict_row = None
    Jsonb = None


class StrategyStore(Protocol):
    def save_idea(self, idea: IdeaSpec) -> None:
        ...

    def get_idea(self, idea_id: str) -> IdeaSpec | None:
        ...

    def save_idea_gaps(self, idea_id: str, gaps: list[SpecGap]) -> None:
        ...

    def get_idea_gaps(self, idea_id: str) -> list[SpecGap]:
        ...

    def save_strategy(self, strategy: StrategyDefinition) -> None:
        ...

    def get_strategy(self, strategy_id: str) -> StrategyDefinition | None:
        ...

    def save_strategy_artifact(self, artifact: StrategyArtifact) -> None:
        ...

    def get_strategy_artifact(self, strategy_id: str) -> StrategyArtifact | None:
        ...

    def save_audit_reports(self, ref_id: str, reports: list[AuditReport]) -> None:
        ...

    def get_audit_reports(self, ref_id: str) -> list[AuditReport]:
        ...

    def save_backtest(self, run: BacktestRun) -> None:
        ...

    def get_backtest(self, strategy_id: str) -> BacktestRun | None:
        ...

    def list_backtests(self) -> dict[str, BacktestRun]:
        ...

    def save_approval_bundle(self, bundle: ApprovalBundle) -> None:
        ...

    def get_approval_bundle(self, bundle_id: str) -> ApprovalBundle | None:
        ...

    def save_permission(self, profile: UserPermissionProfile) -> None:
        ...

    def get_permission(self, user_id: str) -> UserPermissionProfile | None:
        ...


@dataclass
class InMemoryStore(StrategyStore):
    ideas: dict[str, IdeaSpec] = field(default_factory=dict)
    idea_gaps: dict[str, list[SpecGap]] = field(default_factory=dict)
    strategies: dict[str, StrategyDefinition] = field(default_factory=dict)
    strategy_artifacts: dict[str, StrategyArtifact] = field(default_factory=dict)
    audits: dict[str, list[AuditReport]] = field(default_factory=dict)
    backtests: dict[str, BacktestRun] = field(default_factory=dict)
    approval_bundles: dict[str, ApprovalBundle] = field(default_factory=dict)
    permissions: dict[str, UserPermissionProfile] = field(default_factory=dict)

    def save_idea(self, idea: IdeaSpec) -> None:
        self.ideas[idea.id] = idea

    def get_idea(self, idea_id: str) -> IdeaSpec | None:
        return self.ideas.get(idea_id)

    def save_idea_gaps(self, idea_id: str, gaps: list[SpecGap]) -> None:
        self.idea_gaps[idea_id] = gaps

    def get_idea_gaps(self, idea_id: str) -> list[SpecGap]:
        return self.idea_gaps.get(idea_id, [])

    def save_strategy(self, strategy: StrategyDefinition) -> None:
        self.strategies[strategy.id] = strategy

    def get_strategy(self, strategy_id: str) -> StrategyDefinition | None:
        return self.strategies.get(strategy_id)

    def save_strategy_artifact(self, artifact: StrategyArtifact) -> None:
        self.strategy_artifacts[artifact.strategy_id] = artifact

    def get_strategy_artifact(self, strategy_id: str) -> StrategyArtifact | None:
        return self.strategy_artifacts.get(strategy_id)

    def save_audit_reports(self, ref_id: str, reports: list[AuditReport]) -> None:
        self.audits[ref_id] = reports

    def get_audit_reports(self, ref_id: str) -> list[AuditReport]:
        return self.audits.get(ref_id, [])

    def save_backtest(self, run: BacktestRun) -> None:
        self.backtests[run.strategy_id] = run

    def get_backtest(self, strategy_id: str) -> BacktestRun | None:
        return self.backtests.get(strategy_id)

    def list_backtests(self) -> dict[str, BacktestRun]:
        return dict(self.backtests)

    def save_approval_bundle(self, bundle: ApprovalBundle) -> None:
        self.approval_bundles[bundle.id] = bundle

    def get_approval_bundle(self, bundle_id: str) -> ApprovalBundle | None:
        return self.approval_bundles.get(bundle_id)

    def save_permission(self, profile: UserPermissionProfile) -> None:
        self.permissions[profile.user_id] = profile

    def get_permission(self, user_id: str) -> UserPermissionProfile | None:
        return self.permissions.get(user_id)


class PostgresStore(StrategyStore):
    def __init__(self, dsn: str) -> None:
        if psycopg is None or sql is None or dict_row is None or Jsonb is None:
            raise RuntimeError("psycopg is required for Postgres storage")
        self._dsn = dsn

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row) as connection:
            yield connection

    @staticmethod
    def _coerce_payload(payload: object) -> object:
        return payload

    def _upsert_payload(
        self,
        table: str,
        key_column: str,
        key_value: str,
        payload: object,
    ) -> None:
        assert sql is not None
        assert Jsonb is not None
        statement = sql.SQL(
            """
            INSERT INTO {table} ({key_column}, payload, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT ({key_column})
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """
        ).format(
            table=sql.Identifier(table),
            key_column=sql.Identifier(key_column),
        )
        with self._connection() as connection:
            connection.execute(statement, (key_value, Jsonb(self._coerce_payload(payload))))

    def _fetch_payload(
        self,
        table: str,
        key_column: str,
        key_value: str,
    ) -> object | None:
        assert sql is not None
        statement = sql.SQL(
            "SELECT payload FROM {table} WHERE {key_column} = %s"
        ).format(
            table=sql.Identifier(table),
            key_column=sql.Identifier(key_column),
        )
        with self._connection() as connection:
            row = connection.execute(statement, (key_value,)).fetchone()
        if row is None:
            return None
        return cast(object, row["payload"])

    def save_idea(self, idea: IdeaSpec) -> None:
        self._upsert_payload("ideas", "id", idea.id, idea.model_dump(mode="json"))

    def get_idea(self, idea_id: str) -> IdeaSpec | None:
        payload = self._fetch_payload("ideas", "id", idea_id)
        if payload is None:
            return None
        return IdeaSpec.model_validate(payload)

    def save_idea_gaps(self, idea_id: str, gaps: list[SpecGap]) -> None:
        payload = [gap.model_dump(mode="json") for gap in gaps]
        self._upsert_payload("idea_gaps", "idea_id", idea_id, payload)

    def get_idea_gaps(self, idea_id: str) -> list[SpecGap]:
        payload = self._fetch_payload("idea_gaps", "idea_id", idea_id)
        if payload is None:
            return []
        return [SpecGap.model_validate(item) for item in cast(list[object], payload)]

    def save_strategy(self, strategy: StrategyDefinition) -> None:
        self._upsert_payload("strategies", "id", strategy.id, strategy.model_dump(mode="json"))

    def get_strategy(self, strategy_id: str) -> StrategyDefinition | None:
        payload = self._fetch_payload("strategies", "id", strategy_id)
        if payload is None:
            return None
        return StrategyDefinition.model_validate(payload)

    def save_strategy_artifact(self, artifact: StrategyArtifact) -> None:
        self._upsert_payload(
            "strategy_artifacts",
            "strategy_id",
            artifact.strategy_id,
            artifact.model_dump(mode="json"),
        )

    def get_strategy_artifact(self, strategy_id: str) -> StrategyArtifact | None:
        payload = self._fetch_payload("strategy_artifacts", "strategy_id", strategy_id)
        if payload is None:
            return None
        return StrategyArtifact.model_validate(payload)

    def save_audit_reports(self, ref_id: str, reports: list[AuditReport]) -> None:
        assert Jsonb is not None
        with self._connection() as connection:
            connection.execute("DELETE FROM audit_reports WHERE ref_id = %s", (ref_id,))
            for report in reports:
                connection.execute(
                    """
                    INSERT INTO audit_reports (ref_id, payload)
                    VALUES (%s, %s)
                    """,
                    (ref_id, Jsonb(report.model_dump(mode="json"))),
                )

    def get_audit_reports(self, ref_id: str) -> list[AuditReport]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM audit_reports
                WHERE ref_id = %s
                ORDER BY audit_id ASC
                """,
                (ref_id,),
            ).fetchall()
        return [AuditReport.model_validate(row["payload"]) for row in rows]

    def save_backtest(self, run: BacktestRun) -> None:
        self._upsert_payload(
            "backtest_runs",
            "strategy_id",
            run.strategy_id,
            run.model_dump(mode="json"),
        )

    def get_backtest(self, strategy_id: str) -> BacktestRun | None:
        payload = self._fetch_payload("backtest_runs", "strategy_id", strategy_id)
        if payload is None:
            return None
        return BacktestRun.model_validate(payload)

    def list_backtests(self) -> dict[str, BacktestRun]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT strategy_id, payload FROM backtest_runs ORDER BY strategy_id ASC"
            ).fetchall()
        return {
            str(row["strategy_id"]): BacktestRun.model_validate(row["payload"])
            for row in rows
        }

    def save_approval_bundle(self, bundle: ApprovalBundle) -> None:
        self._upsert_payload(
            "approval_bundles",
            "id",
            bundle.id,
            bundle.model_dump(mode="json"),
        )

    def get_approval_bundle(self, bundle_id: str) -> ApprovalBundle | None:
        payload = self._fetch_payload("approval_bundles", "id", bundle_id)
        if payload is None:
            return None
        return ApprovalBundle.model_validate(payload)

    def save_permission(self, profile: UserPermissionProfile) -> None:
        self._upsert_payload(
            "broker_permissions",
            "user_id",
            profile.user_id,
            profile.model_dump(mode="json"),
        )

    def get_permission(self, user_id: str) -> UserPermissionProfile | None:
        payload = self._fetch_payload("broker_permissions", "user_id", user_id)
        if payload is None:
            return None
        return UserPermissionProfile.model_validate(payload)


def build_store() -> StrategyStore:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return PostgresStore(dsn=dsn)
    return InMemoryStore()
