from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
import requests

from vnpy.web.contracts.tenx_hunter import (
    TenxAlertCenterResponse,
    TenxAlertCreateRequest,
    TenxDeerFlowChatRequest,
    TenxDeerFlowChatResponse,
    TenxDeerFlowHistoryRequest,
    TenxDeerFlowSearchRequest,
    TenxDiscoverCandidateCreateRequest,
    TenxEarningsDeskResponse,
    TenxEarningsLensResponse,
    TenxStrategyBacktestResponse,
    TenxEventMonitorResponse,
    TenxMarketSentimentResponse,
    TenxMutationResponse,
    TenxPoliticalSignalResponse,
    TenxPriceMapResponse,
    TenxResearchCardResponse,
    TenxResearchReportResponse,
    TenxResearchReportUploadResponse,
    TenxWatchlistMutationRequest,
    TenxWatchlistUpdateRequest,
    TenxWorkspaceSnapshotResponse,
)
import vnpy.web.services as services

router = APIRouter(prefix="/tenx-hunter", tags=["tenx-hunter"])


def _has_multipart_support() -> bool:
    try:
        from python_multipart import __version__ as python_multipart_version

        assert python_multipart_version > "0.0.12"
        return True
    except (ImportError, AssertionError):
        pass

    try:
        from multipart import __version__ as multipart_version
        from multipart.multipart import parse_options_header

        assert multipart_version
        assert parse_options_header
        return True
    except (ImportError, AssertionError):
        return False


_HAS_MULTIPART = _has_multipart_support()


def _raise_deerflow_http_error(error: requests.HTTPError) -> None:
    response = error.response
    status_code = response.status_code if response is not None else 502
    detail = "DeerFlow request failed."

    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                detail = payload["detail"]
            else:
                detail = response.text or detail
        except ValueError:
            detail = response.text or detail

    raise HTTPException(status_code=status_code, detail=detail) from error


@router.get("/workspace", response_model=TenxWorkspaceSnapshotResponse)
def get_tenx_workspace(market: str = Query("CN")) -> TenxWorkspaceSnapshotResponse:
    return services.tenx_service.get_workspace_snapshot(market)


@router.get("/market-sentiment", response_model=TenxMarketSentimentResponse)
def get_market_sentiment(market: str = Query("US")) -> TenxMarketSentimentResponse:
    return services.sentiment_service.get_snapshot(market)


@router.get("/political-signals", response_model=TenxPoliticalSignalResponse)
def get_political_signals(market: str = Query("US"), person: str = Query("trump")) -> TenxPoliticalSignalResponse:
    return services.political_service.get_snapshot(market, person)


@router.get("/event-monitor", response_model=TenxEventMonitorResponse)
def get_event_monitor(market: str = Query("US")) -> TenxEventMonitorResponse:
    return services.tenx_service.get_event_monitor(market)


@router.get("/earnings-lens", response_model=TenxEarningsLensResponse)
def get_earnings_lens(market: str = Query("US")) -> TenxEarningsLensResponse:
    return services.tenx_service.get_earnings_lens(market)


@router.get("/earnings-desk", response_model=TenxEarningsDeskResponse)
def get_earnings_desk(market: str = Query("US"), horizon: int = Query(45)) -> TenxEarningsDeskResponse:
    return services.tenx_service.get_earnings_desk(market, horizon_days=horizon)


@router.get("/strategy-backtest", response_model=TenxStrategyBacktestResponse)
def get_strategy_backtest(
    symbol: str = Query(..., description="股票代码"),
    market: str = Query("US"),
    lookback_days: int = Query(90, description="回测回溯天数"),
    horizon_days: int = Query(30, description="模拟持仓天数"),
) -> TenxStrategyBacktestResponse:
    """对单只股票运行 8 种期权策略的历史回测，返回逐策略胜率。"""
    return services.tenx_service.get_strategy_backtest(
        market, symbol, lookback_days=lookback_days, horizon_days=horizon_days,
    )


@router.post("/event-monitor/refresh", response_model=TenxEventMonitorResponse)
def refresh_event_monitor(market: str = Query("US")) -> TenxEventMonitorResponse:
    return services.tenx_service.refresh_event_monitor(market, fetch_remote=True)


@router.get("/research/{symbol}", response_model=TenxResearchCardResponse)
def get_tenx_research_card(symbol: str, market: str = Query("CN")) -> TenxResearchCardResponse:
    card = services.tenx_service.get_research_card(market, symbol)
    if card is None:
        raise HTTPException(status_code=404, detail=f"research card not found: {market}:{symbol}")
    return card


@router.post("/discover", response_model=TenxMutationResponse)
def create_discover_candidate(payload: TenxDiscoverCandidateCreateRequest) -> TenxMutationResponse:
    try:
        return services.tenx_service.create_discover_candidate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reports/{symbol}", response_model=TenxResearchReportResponse)
def get_tenx_research_report(symbol: str, market: str = Query("CN")) -> TenxResearchReportResponse:
    report = services.tenx_service.get_research_report(market, symbol)
    if report is None:
        raise HTTPException(status_code=404, detail=f"research report not found: {market}:{symbol}")
    return report


if _HAS_MULTIPART:

    @router.post("/reports/{symbol}", response_model=TenxResearchReportUploadResponse)
    def upload_tenx_research_report(
        symbol: str,
        market: str = Query("CN"),
        file: UploadFile = File(...),
    ) -> TenxResearchReportUploadResponse:
        try:
            content = file.file.read()
            return services.tenx_service.save_research_report(
                market,
                symbol,
                file.filename or f"{symbol.upper()}.md",
                content,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

else:

    @router.post("/reports/{symbol}", response_model=TenxMutationResponse)
    def upload_tenx_research_report_unavailable(symbol: str, market: str = Query("CN")) -> TenxMutationResponse:
        raise HTTPException(
            status_code=503,
            detail="TenX research report uploads require the optional python-multipart package.",
        )


@router.get("/price-map/{symbol}", response_model=TenxPriceMapResponse)
def get_tenx_price_map(symbol: str, market: str = Query("CN")) -> TenxPriceMapResponse:
    price_map = services.tenx_service.get_price_map(market, symbol)
    if price_map is None:
        raise HTTPException(status_code=404, detail=f"price map not found: {market}:{symbol}")
    return price_map


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


@router.post("/deerflow/chat", response_model=TenxDeerFlowChatResponse)
def deerflow_chat(payload: TenxDeerFlowChatRequest) -> TenxDeerFlowChatResponse:
    try:
        result = services.deerflow_agent_service.chat(
            payload.prompt,
            thread_id=payload.thread_id,
            files=[item.model_dump() for item in payload.files],
        )
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)
    return TenxDeerFlowChatResponse(
        ok=result.ok,
        content=result.content,
        backend=result.backend,
        thread_id=result.thread_id,
        error=result.error,
    )


@router.post("/deerflow/stream")
def deerflow_stream(payload: TenxDeerFlowChatRequest) -> StreamingResponse:
    try:
        thread_id, iterator = services.deerflow_agent_service.stream(
            payload.prompt,
            thread_id=payload.thread_id,
            files=[item.model_dump() for item in payload.files],
        )
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)

    def generate():
        yield f"event: metadata\ndata: {{\"thread_id\": \"{thread_id}\"}}\n\n"
        for line in iterator:
            if line is None:
                continue
            yield f"{line}\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/deerflow/state")
def deerflow_state(thread_id: str = Query(...)) -> dict:
    try:
        return services.deerflow_agent_service.get_state(thread_id)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)


@router.post("/deerflow/history")
def deerflow_history(payload: TenxDeerFlowHistoryRequest) -> list[dict]:
    try:
        return services.deerflow_agent_service.get_history(payload.thread_id, limit=payload.limit)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)


@router.post("/deerflow/threads/search")
def deerflow_threads_search(payload: TenxDeerFlowSearchRequest) -> list[dict]:
    try:
        return services.deerflow_agent_service.search_threads(limit=payload.limit, metadata=payload.metadata)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)


@router.get("/deerflow/uploads")
def deerflow_uploads(thread_id: str = Query(...)) -> dict:
    try:
        return services.deerflow_agent_service.list_uploads(thread_id)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)


if _HAS_MULTIPART:

    @router.post("/deerflow/uploads")
    def deerflow_upload_files(
        thread_id: str = Query(...),
        files: list[UploadFile] = File(...),
    ) -> dict:
        try:
            return services.deerflow_agent_service.upload_files(thread_id, files)
        except requests.HTTPError as error:
            _raise_deerflow_http_error(error)

else:

    @router.post("/deerflow/uploads")
    def deerflow_upload_files_unavailable(thread_id: str = Query(...)) -> dict:
        raise HTTPException(
            status_code=503,
            detail="DeerFlow file uploads require the optional python-multipart package.",
        )


@router.get("/deerflow/artifact")
def deerflow_artifact(
    thread_id: str = Query(...),
    path: str = Query(...),
    download: bool = Query(False),
) -> StreamingResponse:
    try:
        response = services.deerflow_agent_service.get_artifact(thread_id, path, download=download)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)

    headers: dict[str, str] = {}
    content_type = response.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type
    content_disposition = response.headers.get("content-disposition")
    if content_disposition:
        headers["Content-Disposition"] = content_disposition

    return StreamingResponse(
        response.iter_content(chunk_size=8192),
        media_type=content_type,
        headers=headers,
    )
