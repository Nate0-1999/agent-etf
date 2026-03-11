# ruff: noqa: E402

from __future__ import annotations

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
    DevResetResponse,
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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from apps.api.agent_etf_api.service import ControlPlaneService

app = FastAPI(title="Agentic Indexing API", version="0.2.0")
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = ControlPlaneService()


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
    return service.dev_reset()


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
