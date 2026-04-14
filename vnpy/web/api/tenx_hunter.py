from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vnpy.web.contracts.tenx_hunter import TenxResearchCardResponse, TenxWorkspaceSnapshotResponse
import vnpy.web.services as services

router = APIRouter(prefix="/tenx-hunter", tags=["tenx-hunter"])


@router.get("/workspace", response_model=TenxWorkspaceSnapshotResponse)
def get_tenx_workspace() -> TenxWorkspaceSnapshotResponse:
    return services.tenx_service.get_workspace_snapshot()


@router.get("/research/{symbol}", response_model=TenxResearchCardResponse)
def get_tenx_research_card(symbol: str) -> TenxResearchCardResponse:
    card = services.tenx_service.get_research_card(symbol)
    if card is None:
        raise HTTPException(status_code=404, detail=f"research card not found: {symbol}")
    return card
