# ruff: noqa: E402

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import cast

from bootstrap_paths import add_project_paths

add_project_paths()

from agent_etf_contracts.models import (
    AppendIdeationMessageRequest,
    ApprovalAction,
    ApprovalBundleResponse,
    ApprovalStepRequest,
    BacktestRequest,
    BrokerLimitsRequest,
    BrokerLinkRequest,
    ClarifyIdeaRequest,
    ConvertIdeationSessionResponse,
    CreateIdeaRequest,
    CreateIdeationSessionRequest,
    CreateStrategyFromIdeaResponse,
    CurrentModelSetResponse,
    DevEventListResponse,
    DevResetResponse,
    DevSeedRequest,
    DevSeedResponse,
    IdeaStatusResponse,
    IdeationSessionDetailResponse,
    IdeationSessionListResponse,
    IndexDetail,
    IndexListResponse,
    ManualActionResponse,
    ModelProposalListResponse,
    ModelRefreshResponse,
    PortfolioPerformanceResponse,
    StrategyDefinition,
    StrategyListResponse,
    StrategySummaryResponse,
)
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from apps.api.agent_etf_api.observability import (
    make_request_id,
    recorder,
    reset_request_context,
    set_request_context,
)
from apps.api.agent_etf_api.service import ControlPlaneService

app = FastAPI(title="Agentic Indexing API", version="0.2.0")
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3100",
    "http://127.0.0.1:3100",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = ControlPlaneService()


def _assert_dev_routes_enabled() -> None:
    if os.getenv("AGENTIC_ENV", "development") == "production":
        raise HTTPException(status_code=403, detail="Dev routes are disabled in production mode")


@app.middleware("http")
async def request_observability(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-Id") or make_request_id()
    test_run_id = request.headers.get("X-Test-Run-Id")
    tokens = set_request_context(request_id, test_run_id)
    try:
        response = await call_next(request)
    except Exception:
        recorder.record(
            category="request",
            action="unhandled_exception",
            request_id=request_id,
            test_run_id=test_run_id,
            route=request.url.path,
            status_code=500,
            payload={"method": request.method},
        )
        reset_request_context(tokens)
        raise
    response.headers["X-Request-Id"] = request_id
    if test_run_id:
        response.headers["X-Test-Run-Id"] = test_run_id
    recorder.record(
        category="request",
        action="completed",
        request_id=request_id,
        test_run_id=test_run_id,
        route=request.url.path,
        status_code=response.status_code,
        payload={"method": request.method},
    )
    reset_request_context(tokens)
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ideas", response_model=IdeaStatusResponse)
def create_idea(payload: CreateIdeaRequest) -> IdeaStatusResponse:
    return service.create_idea(payload)


@app.post("/ideas/{idea_id}/clarify", response_model=IdeaStatusResponse)
def clarify_idea(idea_id: str, payload: ClarifyIdeaRequest) -> IdeaStatusResponse:
    try:
        return service.clarify_idea(idea_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/ideas/{idea_id}/status", response_model=IdeaStatusResponse)
def idea_status(idea_id: str) -> IdeaStatusResponse:
    try:
        return service.idea_status(idea_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/strategies/from-idea/{idea_id}", response_model=CreateStrategyFromIdeaResponse)
def create_strategy_from_idea(idea_id: str) -> CreateStrategyFromIdeaResponse:
    try:
        return service.create_strategy_from_idea(idea_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/strategies", response_model=StrategyListResponse)
def list_strategies() -> StrategyListResponse:
    return service.list_strategies()


@app.get("/strategies/{strategy_id}", response_model=StrategySummaryResponse)
def get_strategy(strategy_id: str) -> StrategySummaryResponse:
    try:
        return service.strategy_summary(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/strategies/{strategy_id}/approve-create", response_model=StrategyDefinition)
def approve_strategy_create(strategy_id: str) -> StrategyDefinition:
    try:
        return service.set_strategy_status(strategy_id, approved=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/strategies/{strategy_id}/deny-create", response_model=StrategyDefinition)
def deny_strategy_create(strategy_id: str) -> StrategyDefinition:
    try:
        return service.set_strategy_status(strategy_id, approved=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/strategies/{strategy_id}/backtest")
def run_backtest(strategy_id: str, payload: BacktestRequest) -> dict[str, object]:
    try:
        run = service.run_backtest(strategy_id, payload)
        return cast(dict[str, object], run.model_dump(mode="json"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/strategies/{strategy_id}/manual-update", response_model=ManualActionResponse)
def manual_update(strategy_id: str) -> ManualActionResponse:
    try:
        return service.manual_action(strategy_id, ApprovalAction.update)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/strategies/{strategy_id}/manual-rebalance", response_model=ManualActionResponse)
def manual_rebalance(strategy_id: str) -> ManualActionResponse:
    try:
        return service.manual_action(strategy_id, ApprovalAction.rebalance)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/approval-bundles/{bundle_id}/step-1", response_model=ApprovalBundleResponse)
def approval_step1(bundle_id: str, payload: ApprovalStepRequest) -> ApprovalBundleResponse:
    try:
        bundle = service.approval_step1(bundle_id, payload.token)
        return ApprovalBundleResponse(bundle=bundle)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/approval-bundles/{bundle_id}/step-2", response_model=ApprovalBundleResponse)
def approval_step2(bundle_id: str, payload: ApprovalStepRequest) -> ApprovalBundleResponse:
    try:
        bundle = service.approval_step2(bundle_id, payload.token)
        return ApprovalBundleResponse(bundle=bundle)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/approval-bundles/{bundle_id}/step-3", response_model=ApprovalBundleResponse)
def approval_step3(bundle_id: str, payload: ApprovalStepRequest) -> ApprovalBundleResponse:
    try:
        bundle = service.approval_step3(bundle_id, payload.token)
        return ApprovalBundleResponse(bundle=bundle)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ideation/sessions", response_model=IdeationSessionListResponse)
def list_ideation_sessions(user_id: str = "operator") -> IdeationSessionListResponse:
    return service.list_ideation_sessions(user_id=user_id)


@app.post("/ideation/sessions", response_model=IdeationSessionDetailResponse)
def create_ideation_session(payload: CreateIdeationSessionRequest) -> IdeationSessionDetailResponse:
    return service.create_ideation_session(payload)


@app.get("/ideation/sessions/{session_id}", response_model=IdeationSessionDetailResponse)
def get_ideation_session(session_id: str) -> IdeationSessionDetailResponse:
    try:
        return service.get_ideation_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/ideation/sessions/{session_id}/messages", response_model=IdeationSessionDetailResponse)
def append_ideation_message(
    session_id: str,
    payload: AppendIdeationMessageRequest,
) -> IdeationSessionDetailResponse:
    try:
        return service.append_ideation_message(session_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/ideation/sessions/{session_id}/convert-to-index",
    response_model=ConvertIdeationSessionResponse,
)
def convert_ideation_session(session_id: str) -> ConvertIdeationSessionResponse:
    try:
        return service.convert_ideation_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/indexes", response_model=IndexListResponse)
def list_indexes() -> IndexListResponse:
    return service.list_indexes()


@app.get("/indexes/{index_id}", response_model=IndexDetail)
def get_index(index_id: str) -> IndexDetail:
    try:
        return service.get_index(index_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/indexes/{index_id}/open-ideation", response_model=IdeationSessionDetailResponse)
def open_ideation_from_index(index_id: str) -> IdeationSessionDetailResponse:
    try:
        return service.open_ideation_from_index(index_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/models/current", response_model=CurrentModelSetResponse)
def current_models() -> CurrentModelSetResponse:
    return service.current_model_set()


@app.get("/models/proposals", response_model=ModelProposalListResponse)
def list_model_proposals() -> ModelProposalListResponse:
    return service.list_model_proposals()


@app.post("/models/refresh", response_model=ModelRefreshResponse)
def refresh_models() -> ModelRefreshResponse:
    return service.refresh_models()


@app.post("/models/proposals/{proposal_id}/approve", response_model=CurrentModelSetResponse)
def approve_model_proposal(proposal_id: str) -> CurrentModelSetResponse:
    try:
        return service.approve_model_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/dev/reset", response_model=DevResetResponse)
def dev_reset() -> DevResetResponse:
    _assert_dev_routes_enabled()
    return service.dev_reset()


@app.post("/dev/seed", response_model=DevSeedResponse)
def dev_seed(payload: DevSeedRequest) -> DevSeedResponse:
    _assert_dev_routes_enabled()
    try:
        return service.dev_seed(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/dev/events", response_model=DevEventListResponse)
def dev_events(test_run_id: str | None = None) -> DevEventListResponse:
    _assert_dev_routes_enabled()
    return DevEventListResponse(events=recorder.list_events(test_run_id=test_run_id))


@app.post("/broker-connections/ibkr/link")
def broker_link(payload: BrokerLinkRequest) -> dict[str, object]:
    profile = service.link_ibkr(payload)
    return cast(dict[str, object], profile.model_dump(mode="json"))


@app.get("/broker-connections/{user_id}/permissions")
def broker_permissions(user_id: str) -> dict[str, object]:
    profile = service.get_permissions(user_id)
    return cast(dict[str, object], profile.model_dump(mode="json"))


@app.post("/broker-connections/{user_id}/user-limits")
def set_user_limits(user_id: str, payload: BrokerLimitsRequest) -> dict[str, object]:
    profile = service.set_user_limits(user_id, payload)
    return cast(dict[str, object], profile.model_dump(mode="json"))


@app.get("/portfolios/{portfolio_id}/performance", response_model=PortfolioPerformanceResponse)
def portfolio_performance(portfolio_id: str) -> PortfolioPerformanceResponse:
    return service.portfolio_performance(portfolio_id)
