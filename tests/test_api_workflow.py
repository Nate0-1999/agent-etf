from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.agent_etf_api.main import app
from apps.api.agent_etf_api.service import ControlPlaneService


def new_client() -> tuple[TestClient, ControlPlaneService]:
    import apps.api.agent_etf_api.main as main_module

    main_module.service = ControlPlaneService()
    return TestClient(app), main_module.service


def seed_strategy(client: TestClient) -> str:
    create = client.post(
        "/ideas",
        json={
            "user_id": "operator",
            "raw_idea": "Create an equal weight thematic metals etf strategy with monthly cadence",
        },
    )
    assert create.status_code == 200
    idea_id = create.json()["idea"]["id"]

    response = client.post(f"/strategies/from-idea/{idea_id}")
    assert response.status_code == 200
    strategy_id = response.json()["strategy"]["id"]
    return str(strategy_id)


def test_idea_clarification_and_strategy_creation() -> None:
    client, _ = new_client()

    create = client.post("/ideas", json={"user_id": "operator", "raw_idea": "metals"})
    assert create.status_code == 200
    idea_id = create.json()["idea"]["id"]
    assert create.json()["ready_for_strategy"] is False

    clarify = client.post(
        f"/ideas/{idea_id}/clarify",
        json={
            "answers": {
                "objective": "Build a diversified heavy metals idea portfolio",
                "allowed_assets": ["etf", "equity", "future"],
                "cadence_recommendation": "monthly_review",
            }
        },
    )
    assert clarify.status_code == 200
    assert clarify.json()["ready_for_strategy"] is True

    strategy = client.post(f"/strategies/from-idea/{idea_id}")
    assert strategy.status_code == 200
    body = strategy.json()
    assert len(body["strategy"]["universe"]) > 0
    assert len(body["audits"]) >= 1


def test_backtest_enforces_min_history_unless_overridden() -> None:
    client, _ = new_client()
    strategy_id = seed_strategy(client)

    failed = client.post(
        f"/strategies/{strategy_id}/backtest",
        json={"min_years": 25, "override_min_history": False},
    )
    assert failed.status_code == 400

    passed = client.post(
        f"/strategies/{strategy_id}/backtest",
        json={"min_years": 25, "override_min_history": True},
    )
    assert passed.status_code == 200


def test_manual_rebalance_uses_three_step_approval_chain() -> None:
    client, service = new_client()
    service._step3_cooldown = 0

    strategy_id = seed_strategy(client)
    response = client.post(f"/strategies/{strategy_id}/manual-rebalance")
    assert response.status_code == 200
    bundle_id = response.json()["bundle"]["id"]

    s1 = client.post(f"/approval-bundles/{bundle_id}/step-1", json={"token": "pw+totp"})
    assert s1.status_code == 200
    assert s1.json()["bundle"]["status"] == "step1_complete"

    s2 = client.post(f"/approval-bundles/{bundle_id}/step-2", json={"token": "oob"})
    assert s2.status_code == 200
    assert s2.json()["bundle"]["status"] == "step2_complete"

    s3 = client.post(f"/approval-bundles/{bundle_id}/step-3", json={"token": "final"})
    assert s3.status_code == 200
    assert s3.json()["bundle"]["status"] == "approved"


def test_runtime_dissent_escalates_and_blocks_bundle() -> None:
    client, service = new_client()
    strategy_id = seed_strategy(client)

    def forced_dissent(
        model: str,
        stage: str,
        payload: dict[str, object],
    ) -> tuple[bool, list[str]]:
        return False, [f"forced dissent {model} {stage}"]

    service.models.run_check = forced_dissent  # type: ignore[method-assign]

    response = client.post(f"/strategies/{strategy_id}/manual-update")
    assert response.status_code == 200

    body = response.json()
    assert body["escalated"] is True
    assert body["loops_attempted"] == service._max_loops
    assert body["bundle"]["status"] == "rejected"


def test_portfolio_performance_contains_benchmarks() -> None:
    client, _ = new_client()
    strategy_id = seed_strategy(client)

    backtest = client.post(
        f"/strategies/{strategy_id}/backtest",
        json={"min_years": 10, "override_min_history": False},
    )
    assert backtest.status_code == 200

    perf = client.get("/portfolios/operator/performance")
    assert perf.status_code == 200
    body = perf.json()
    assert "sp500" in body["benchmarks"]
    assert strategy_id in body["strategies"]
