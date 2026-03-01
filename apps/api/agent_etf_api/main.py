# ruff: noqa: E402

from __future__ import annotations

from typing import cast

from bootstrap_paths import add_project_paths

add_project_paths()

from agent_etf_contracts.models import (
    ApprovalAction,
    ApprovalBundleResponse,
    ApprovalStepRequest,
    BacktestRequest,
    BrokerLimitsRequest,
    BrokerLinkRequest,
    ClarifyIdeaRequest,
    CreateIdeaRequest,
    CreateStrategyFromIdeaResponse,
    IdeaStatusResponse,
    ManualActionResponse,
    PortfolioPerformanceResponse,
    StrategyDefinition,
)
from fastapi import FastAPI, HTTPException

from apps.api.agent_etf_api.service import ControlPlaneService

app = FastAPI(title="agent-etf API", version="0.1.0")
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
