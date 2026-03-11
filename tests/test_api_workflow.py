# ruff: noqa: E402

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from bootstrap_paths import add_project_paths

add_project_paths()
os.environ["DATABASE_URL"] = ""

from agent_etf_contracts.models import ModelCatalogEntry, ModelProviderFamily
from agent_etf_contracts.store import InMemoryStore, build_store

from apps.api.agent_etf_api.main import app
from apps.api.agent_etf_api.service import ControlPlaneService


def new_client() -> tuple[TestClient, ControlPlaneService]:
    import apps.api.agent_etf_api.main as main_module

    main_module.service = ControlPlaneService(store=InMemoryStore())
    return TestClient(app), main_module.service


def create_session(client: TestClient) -> str:
    response = client.post("/ideation/sessions", json={"user_id": "operator", "title": "New Idea"})
    assert response.status_code == 200
    return str(response.json()["session"]["id"])


def test_ideation_session_starts_blank_and_persists_messages() -> None:
    client, _ = new_client()
    session_id = create_session(client)

    detail = client.get(f"/ideation/sessions/{session_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["session"]["title"] == "New Idea"
    assert body["messages"][0]["role"] == "assistant"

    updated = client.post(
        f"/ideation/sessions/{session_id}/messages",
        json={
            "content": (
                "Build an equal weight industrial metals index using ETFs "
                "and miners with monthly reviews."
            )
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert len(updated_body["messages"]) >= 3
    assert updated_body["session"]["raw_thesis"]
    assert any(
        tile["key"] == "candidate_vehicles" for tile in updated_body["session"]["decision_tiles"]
    )


def test_convert_session_to_index_and_list_saved_indexes() -> None:
    client, _ = new_client()
    session_id = create_session(client)

    post = client.post(
        f"/ideation/sessions/{session_id}/messages",
        json={
            "content": (
                "Create a diversified precious metals indexing strategy "
                "with equal weight ETFs and futures and monthly review."
            )
        },
    )
    assert post.status_code == 200

    convert = client.post(f"/ideation/sessions/{session_id}/convert-to-index")
    assert convert.status_code == 200
    converted = convert.json()
    index_id = converted["index"]["id"]
    assert converted["session"]["status"] == "converted"
    assert converted["index"]["holdings"]
    assert converted["index"]["performance"]

    listing = client.get("/indexes")
    assert listing.status_code == 200
    assert any(item["id"] == index_id for item in listing.json()["indexes"])

    detail = client.get(f"/indexes/{index_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    timeframes = {row["timeframe"] for row in detail_body["performance"]}
    assert {"1M", "1Y", "Since Inception"}.issubset(timeframes)


def test_saved_index_can_open_new_ideation_session() -> None:
    client, _ = new_client()
    session_id = create_session(client)
    client.post(
        f"/ideation/sessions/{session_id}/messages",
        json={
            "content": (
                "Build an infrastructure materials index with equal weights and quarterly review."
            )
        },
    )
    converted = client.post(f"/ideation/sessions/{session_id}/convert-to-index")
    index_id = converted.json()["index"]["id"]

    reopened = client.post(f"/indexes/{index_id}/open-ideation")
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["session"]["id"] != session_id
    assert body["session"]["raw_thesis"]
    assert any(message["role"] == "assistant" for message in body["messages"])


def test_model_refresh_creates_proposal_and_approval_switches_active_set() -> None:
    client, service = new_client()

    def newer_catalog() -> list[ModelCatalogEntry]:
        return [
            ModelCatalogEntry(
                id="openai-gpt-5.5",
                provider=ModelProviderFamily.openai,
                family="GPT-5",
                label="GPT-5.5",
                openrouter_slug="gpt-5.5",
                official_doc_url="https://developers.openai.com/api/docs/models",
            ),
            ModelCatalogEntry(
                id="anthropic-claude-4.7",
                provider=ModelProviderFamily.anthropic,
                family="Claude 4",
                label="Claude 4.7",
                openrouter_slug="claude-4.7",
                official_doc_url="https://platform.claude.com/docs/en/about-claude/models/overview",
            ),
            ModelCatalogEntry(
                id="google-gemini-3.2-pro",
                provider=ModelProviderFamily.google,
                family="Gemini 3",
                label="Gemini 3.2 Pro",
                openrouter_slug="gemini-3.2-pro",
                official_doc_url="https://ai.google.dev/gemini-api/docs/models",
            ),
        ]

    service.model_registry.fetch_catalog = newer_catalog  # type: ignore[method-assign]

    refresh = client.post("/models/refresh")
    assert refresh.status_code == 200
    body = refresh.json()
    assert body["proposal"] is not None
    proposal_id = body["proposal"]["id"]

    approved = client.post(f"/models/proposals/{proposal_id}/approve")
    assert approved.status_code == 200
    current = approved.json()["model_set"]
    assert current["openai_model"]["label"] == "GPT-5.5"
    assert current["anthropic_model"]["label"] == "Claude 4.7"
    assert current["google_model"]["label"] == "Gemini 3.2 Pro"


def test_dev_reset_clears_sessions_and_indexes() -> None:
    client, _ = new_client()
    session_id = create_session(client)
    client.post(
        f"/ideation/sessions/{session_id}/messages",
        json={"content": "Build a mining royalty index with monthly review."},
    )
    client.post(f"/ideation/sessions/{session_id}/convert-to-index")

    reset = client.post("/dev/reset")
    assert reset.status_code == 200
    assert reset.json()["cleared"] is True

    sessions = client.get("/ideation/sessions")
    assert sessions.status_code == 200
    assert sessions.json()["sessions"] == []

    indexes = client.get("/indexes")
    assert indexes.status_code == 200
    assert indexes.json()["indexes"] == []


def test_dev_seed_saved_index_creates_fixture_and_events() -> None:
    client, _ = new_client()

    seeded = client.post("/dev/seed", json={"scenario": "saved_index"})
    assert seeded.status_code == 200
    payload = seeded.json()
    assert payload["created_session_id"] is not None
    assert payload["created_index_id"] is not None

    indexes = client.get("/indexes")
    assert indexes.status_code == 200
    assert len(indexes.json()["indexes"]) == 1

    events = client.get("/dev/events")
    assert events.status_code == 200
    assert any(event["action"] == "dev_seed" for event in events.json()["events"])


def test_request_id_header_is_returned() -> None:
    client, _ = new_client()

    response = client.get("/healthz", headers={"X-Test-Run-Id": "test-run-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-Id"].startswith("req-")
    assert response.headers["X-Test-Run-Id"] == "test-run-123"


def test_strategy_summary_no_longer_exposes_artifact() -> None:
    client, _ = new_client()
    create = client.post(
        "/ideas",
        json={
            "user_id": "operator",
            "raw_idea": "Build a diversified metals index with ETFs, miners, and monthly cadence",
        },
    )
    strategy = client.post(f"/strategies/from-idea/{create.json()['idea']['id']}")
    strategy_id = strategy.json()["strategy"]["id"]
    summary = client.get(f"/strategies/{strategy_id}")
    assert summary.status_code == 200
    assert "artifact" not in summary.json()


def test_build_store_defaults_to_in_memory_when_database_is_unset() -> None:
    previous = os.environ.pop("DATABASE_URL", None)
    try:
        store = build_store()
    finally:
        if previous is not None:
            os.environ["DATABASE_URL"] = previous
    assert isinstance(store, InMemoryStore)
