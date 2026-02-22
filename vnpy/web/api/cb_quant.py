from fastapi import APIRouter, Query

from vnpy.web.schemas import (
    BacktestCompareResponse,
    BacktestCreateJobsRequest,
    BacktestCreateJobsResponse,
    BacktestJobListResponse,
    BacktestLeaderboardResponse,
    BacktestStatsResponse,
    BondMarketResponse,
    CandidateListResponse,
)
from vnpy.web.services import cb_market_service, cb_quant_service

router = APIRouter(prefix="/cb-quant", tags=["cb-quant"])


@router.get("/strategy/candidates", response_model=CandidateListResponse)
def list_candidates(
    keyword: str = Query(default=""),
    window: str = Query(default="all"),
) -> CandidateListResponse:
    return cb_quant_service.list_candidates(keyword=keyword, window=window)


@router.get("/backtest/jobs", response_model=BacktestJobListResponse)
def list_backtest_jobs(
    keyword: str = Query(default=""),
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> BacktestJobListResponse:
    return cb_quant_service.list_jobs(
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/backtest/jobs", response_model=BacktestCreateJobsResponse)
def create_backtest_jobs(
    request: BacktestCreateJobsRequest,
) -> BacktestCreateJobsResponse:
    return cb_quant_service.create_jobs(request)


@router.get("/backtest/leaderboard", response_model=BacktestLeaderboardResponse)
def list_backtest_leaderboard(
    keyword: str = Query(default=""),
    window: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> BacktestLeaderboardResponse:
    return cb_quant_service.list_leaderboard(
        keyword=keyword,
        window=window,
        page=page,
        page_size=page_size,
    )


@router.get("/backtest/compare", response_model=BacktestCompareResponse)
def list_backtest_compare(
    keyword: str = Query(default=""),
    category: str = Query(default="all"),
) -> BacktestCompareResponse:
    return cb_quant_service.list_compare(keyword=keyword, category=category)


@router.get("/backtest/stats", response_model=BacktestStatsResponse)
def get_backtest_stats() -> BacktestStatsResponse:
    return cb_quant_service.get_stats()


@router.get("/market/bonds", response_model=BondMarketResponse)
def list_market_bonds(
    min_volume_wan: float = Query(default=0, ge=0),
) -> BondMarketResponse:
    return cb_market_service.list_bonds(min_volume_wan=min_volume_wan)
