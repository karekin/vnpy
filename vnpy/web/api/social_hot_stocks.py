from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import requests

from vnpy.web.contracts.social_hot_stocks import SocialHotStocksResponse
import vnpy.web.services as services

router = APIRouter(prefix="/social-hot-stocks", tags=["social-hot-stocks"])


@router.get("", response_model=SocialHotStocksResponse)
def get_social_hot_stocks(
    source: str = Query("apewisdom"),
    source_filter: str = Query("all-stocks", alias="filter"),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=500),
    limit: int | None = Query(None, ge=1, le=500, description="Deprecated alias for page_size."),
    refresh: bool = Query(False, description="Bypass persisted fresh snapshot and request ApeWisdom again."),
) -> SocialHotStocksResponse:
    try:
        return services.social_hot_service.get_hot_stocks(
            source=source,
            source_filter=source_filter,
            page=page,
            page_size=page_size,
            limit=limit,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"ApeWisdom request failed: {exc}") from exc
