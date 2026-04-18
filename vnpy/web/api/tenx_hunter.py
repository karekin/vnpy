from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vnpy.web.contracts.tenx_hunter import (
    TenxAlertCenterResponse,
    TenxAlertCreateRequest,
    TenxMutationResponse,
    TenxResearchCardResponse,
    TenxWatchlistMutationRequest,
    TenxWatchlistUpdateRequest,
    TenxWorkspaceSnapshotResponse,
)
import vnpy.web.services as services

router = APIRouter(prefix="/tenx-hunter", tags=["tenx-hunter"])


@router.get("/workspace", response_model=TenxWorkspaceSnapshotResponse)
def get_tenx_workspace(market: str = Query("CN")) -> TenxWorkspaceSnapshotResponse:
    return services.tenx_service.get_workspace_snapshot(market)


@router.get("/research/{symbol}", response_model=TenxResearchCardResponse)
def get_tenx_research_card(symbol: str, market: str = Query("CN")) -> TenxResearchCardResponse:
    card = services.tenx_service.get_research_card(market, symbol)
    if card is None:
        raise HTTPException(status_code=404, detail=f"research card not found: {market}:{symbol}")
    return card


@router.get("/alerts", response_model=TenxAlertCenterResponse)
def get_tenx_alerts(market: str = Query("CN")) -> TenxAlertCenterResponse:
    return services.tenx_service.list_alerts(market)


@router.post("/watchlist", response_model=TenxMutationResponse)
def create_watchlist(payload: TenxWatchlistMutationRequest) -> TenxMutationResponse:
    try:
        return services.tenx_service.create_watchlist(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/watchlist/{symbol}", response_model=TenxMutationResponse)
def update_watchlist(symbol: str, payload: TenxWatchlistUpdateRequest) -> TenxMutationResponse:
    try:
        return services.tenx_service.update_watchlist(symbol, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/alerts", response_model=TenxMutationResponse)
def create_alert(payload: TenxAlertCreateRequest) -> TenxMutationResponse:
    return services.tenx_service.create_alert(payload)
