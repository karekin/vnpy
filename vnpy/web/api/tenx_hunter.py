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
    TenxMutationResponse,
    TenxResearchCardResponse,
    TenxWatchlistMutationRequest,
    TenxWatchlistUpdateRequest,
    TenxWorkspaceSnapshotResponse,
)
import vnpy.web.services as services

router = APIRouter(prefix="/tenx-hunter", tags=["tenx-hunter"])


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


@router.post("/deerflow/uploads")
def deerflow_upload_files(
    thread_id: str = Query(...),
    files: list[UploadFile] = File(...),
) -> dict:
    try:
        return services.deerflow_agent_service.upload_files(thread_id, files)
    except requests.HTTPError as error:
        _raise_deerflow_http_error(error)


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
