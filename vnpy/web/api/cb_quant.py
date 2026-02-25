from fastapi import APIRouter, HTTPException, Query

from vnpy.web.schemas import (
    BacktestCompareResponse,
    BacktestCreateJobsRequest,
    BacktestCreateJobsResponse,
    BacktestJobListResponse,
    BacktestLeaderboardResponse,
    BacktestStatsResponse,
    BondMarketResponse,
    FactorCatalogResponse,
    FunctionCatalogResponse,
    HistoryDataSummaryResponse,
    HistorySyncResponse,
    HistorySyncStatusResponse,
    OperationResponse,
    TushareDataSummaryResponse,
    TushareSyncRequest,
    TushareSyncResponse,
    TushareSyncStatusResponse,
    StrategyOptimizeTaskCreateRequest,
    StrategyOptimizeTaskCreateResponse,
    StrategyOptimizeTaskAnalysisResponse,
    StrategyOptimizeTaskDetailResponse,
    StrategyOptimizeTaskListResponse,
    StrategyOptimizeSummaryResponse,
    StrategyExpandFactorCombosRequest,
    StrategyExpandFactorCombosResponse,
    StrategyTemplateBatchDeleteRequest,
    StrategyTemplateBatchEnableRequest,
    StrategyTemplateBatchResponse,
    StrategyTemplateConfigRequest,
    StrategyTemplateConfigResponse,
    StrategyTemplateCreateRequest,
    StrategyTemplateDetailResponse,
    StrategyTemplateListResponse,
    StrategyTemplateRow,
    StrategyTemplateUpdateRequest,
)
from vnpy.web.services import cb_catalog_service, cb_history_service, cb_market_service, cb_quant_service, cb_tushare_service

router = APIRouter(prefix="/cb-quant", tags=["cb-quant"])


@router.get("/catalog/factors", response_model=FactorCatalogResponse)
def list_factor_catalog(
    category: str = Query(default="all"),
    keyword: str = Query(default=""),
    enabled_only: bool = Query(default=False),
) -> FactorCatalogResponse:
    return cb_catalog_service.list_factors(
        category=category,
        keyword=keyword,
        enabled_only=enabled_only,
    )


@router.get("/catalog/functions", response_model=FunctionCatalogResponse)
def list_function_catalog(
    category: str = Query(default="all"),
    keyword: str = Query(default=""),
) -> FunctionCatalogResponse:
    return cb_catalog_service.list_functions(
        category=category,
        keyword=keyword,
    )


@router.get("/strategy/templates", response_model=StrategyTemplateListResponse)
def list_strategy_templates(
    keyword: str = Query(default=""),
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> StrategyTemplateListResponse:
    return cb_quant_service.list_templates(
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/strategy/templates", response_model=StrategyTemplateRow)
def create_strategy_template(
    request: StrategyTemplateCreateRequest,
) -> StrategyTemplateRow:
    return cb_quant_service.create_template(request)


@router.post("/strategy/templates/batch/enable", response_model=StrategyTemplateBatchResponse)
def batch_enable_strategy_templates(
    request: StrategyTemplateBatchEnableRequest,
) -> StrategyTemplateBatchResponse:
    affected, missing = cb_quant_service.batch_enable_templates(
        request.template_ids,
        status=request.status,
    )
    return StrategyTemplateBatchResponse(
        ok=True,
        affected=affected,
        missing_ids=missing,
        message=f"已批量启用 {affected} 个策略。",
    )


@router.post("/strategy/templates/batch/delete", response_model=StrategyTemplateBatchResponse)
def batch_delete_strategy_templates(
    request: StrategyTemplateBatchDeleteRequest,
) -> StrategyTemplateBatchResponse:
    affected, missing = cb_quant_service.batch_delete_templates(request.template_ids)
    return StrategyTemplateBatchResponse(
        ok=True,
        affected=affected,
        missing_ids=missing,
        message=f"已批量删除 {affected} 个策略。",
    )


@router.get("/strategy/templates/{template_id}", response_model=StrategyTemplateDetailResponse)
def get_strategy_template(template_id: str) -> StrategyTemplateDetailResponse:
    detail = cb_quant_service.get_template_detail(template_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return detail


@router.put("/strategy/templates/{template_id}", response_model=StrategyTemplateRow)
def update_strategy_template(
    template_id: str,
    request: StrategyTemplateUpdateRequest,
) -> StrategyTemplateRow:
    updated = cb_quant_service.update_template(template_id, request)
    if not updated:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return updated


@router.post(
    "/strategy/templates/{template_id}/expand-factor-combos",
    response_model=StrategyExpandFactorCombosResponse,
)
def expand_strategy_factor_combos(
    template_id: str,
    request: StrategyExpandFactorCombosRequest,
) -> StrategyExpandFactorCombosResponse:
    expanded = cb_quant_service.expand_template_factor_combos(template_id, request)
    if not expanded:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return expanded


@router.delete("/strategy/templates/{template_id}", response_model=OperationResponse)
def delete_strategy_template(template_id: str) -> OperationResponse:
    deleted = cb_quant_service.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return OperationResponse(ok=True, message=f"deleted template: {template_id}")


@router.get("/strategy/templates/{template_id}/config", response_model=StrategyTemplateConfigResponse)
def get_strategy_template_config(template_id: str) -> StrategyTemplateConfigResponse:
    detail = cb_quant_service.get_template_detail(template_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return detail.config


@router.put("/strategy/templates/{template_id}/config", response_model=StrategyTemplateConfigResponse)
def update_strategy_template_config(
    template_id: str,
    request: StrategyTemplateConfigRequest,
) -> StrategyTemplateConfigResponse:
    updated = cb_quant_service.update_template_config(template_id, request)
    if not updated:
        raise HTTPException(status_code=404, detail=f"template not found: {template_id}")
    return updated


@router.get("/strategy/history-summary", response_model=HistoryDataSummaryResponse)
def get_history_data_summary() -> HistoryDataSummaryResponse:
    return cb_quant_service.get_history_data_summary()


@router.post("/strategy/history-sync", response_model=HistorySyncResponse)
def trigger_history_sync() -> HistorySyncResponse:
    upserted = cb_history_service.sync_today_from_market(mode="manual")
    summary = cb_history_service.get_summary()
    return HistorySyncResponse(
        ok=True,
        mode="manual",
        source="eastmoney.push2",
        trade_date=summary.latest_trade_date or "",
        upserted=upserted,
        message=f"历史快照同步完成，最新交易日 {summary.latest_trade_date}，入库 {upserted} 条。",
    )


@router.get("/strategy/history-sync/status", response_model=HistorySyncStatusResponse)
def get_history_sync_status() -> HistorySyncStatusResponse:
    log = cb_history_service.latest_sync_log()
    if not log:
        return HistorySyncStatusResponse(has_log=False)
    return HistorySyncStatusResponse(
        has_log=True,
        sync_at=log.sync_at,
        mode=log.mode,
        source=log.source,
        trade_date=log.trade_date,
        upserted=log.upserted,
        status=log.status,
        message=log.message,
    )


@router.post("/strategy/history-sync/tushare", response_model=TushareSyncResponse)
def trigger_tushare_history_sync(
    request: TushareSyncRequest,
) -> TushareSyncResponse:
    try:
        payload = cb_tushare_service.sync_range(
            start_date=request.start_date,
            end_date=request.end_date,
            mode="manual",
            max_trade_days=request.max_trade_days,
        )
        return TushareSyncResponse.model_validate(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"tushare sync failed: {exc}") from exc


@router.get("/strategy/history-sync/tushare/status", response_model=TushareSyncStatusResponse)
def get_tushare_history_sync_status() -> TushareSyncStatusResponse:
    log = cb_tushare_service.latest_sync_log()
    if not log:
        return TushareSyncStatusResponse(has_log=False)
    return TushareSyncStatusResponse(
        has_log=True,
        sync_at=log.sync_at,
        mode=log.mode,
        source=log.source,
        start_date=log.start_date,
        end_date=log.end_date,
        trade_days=log.trade_days,
        cb_daily_rows=log.cb_daily_rows,
        stock_daily_rows=log.stock_daily_rows,
        event_rows=log.event_rows,
        factor_rows=log.factor_rows,
        snapshot_rows=log.snapshot_rows,
        status=log.status,
        message=log.message,
    )


@router.get("/strategy/history-sync/tushare/summary", response_model=TushareDataSummaryResponse)
def get_tushare_history_summary() -> TushareDataSummaryResponse:
    summary = cb_tushare_service.get_summary()
    return TushareDataSummaryResponse(
        cb_trade_days=summary.cb_trade_days,
        cb_date_start=summary.cb_date_start,
        cb_date_end=summary.cb_date_end,
        factor_trade_days=summary.factor_trade_days,
        factor_date_start=summary.factor_date_start,
        factor_date_end=summary.factor_date_end,
        event_rows=summary.event_rows,
        db_path=summary.db_path,
    )


@router.post("/strategy/optimize-tasks", response_model=StrategyOptimizeTaskCreateResponse)
def create_optimize_task(
    request: StrategyOptimizeTaskCreateRequest,
) -> StrategyOptimizeTaskCreateResponse:
    created = cb_quant_service.create_optimize_task(request)
    if not created:
        raise HTTPException(status_code=404, detail=f"template not found: {request.template_id}")
    return created


@router.get("/strategy/optimize-tasks", response_model=StrategyOptimizeTaskListResponse)
def list_optimize_tasks(
    template_id: str = Query(default="all"),
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> StrategyOptimizeTaskListResponse:
    return cb_quant_service.list_optimize_tasks(
        template_id=template_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/strategy/optimize-tasks/{task_id}", response_model=StrategyOptimizeTaskDetailResponse)
def get_optimize_task_detail(task_id: str) -> StrategyOptimizeTaskDetailResponse:
    detail = cb_quant_service.get_optimize_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"optimize task not found: {task_id}")
    return detail


@router.get("/strategy/optimize-tasks/{task_id}/analysis", response_model=StrategyOptimizeTaskAnalysisResponse)
def get_optimize_task_analysis(
    task_id: str,
    combo_id: str | None = Query(default=None),
    initial_capital_wan: float = Query(default=100.0, gt=0),
) -> StrategyOptimizeTaskAnalysisResponse:
    detail = cb_quant_service.get_optimize_task_analysis(
        task_id=task_id,
        combo_id=combo_id,
        initial_capital_wan=initial_capital_wan,
    )
    if not detail:
        raise HTTPException(status_code=404, detail=f"optimize task not found: {task_id}")
    return detail


@router.get("/strategy/optimize-summary", response_model=StrategyOptimizeSummaryResponse)
def get_optimize_summary(
    top_n: int = Query(default=20, ge=1, le=200),
    current_top_n: int = Query(default=20, ge=1, le=200),
) -> StrategyOptimizeSummaryResponse:
    return cb_quant_service.get_optimize_summary(top_n=top_n, current_top_n=current_top_n)


@router.get("/backtest/jobs", response_model=BacktestJobListResponse)
def list_backtest_jobs(
    keyword: str = Query(default=""),
    status: str = Query(default="all"),
    business_date: str = Query(default=""),
    business_date_from: str | None = Query(default=None),
    business_date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> BacktestJobListResponse:
    return cb_quant_service.list_jobs(
        keyword=keyword,
        status=status,
        business_date=business_date,
        business_date_from=business_date_from,
        business_date_to=business_date_to,
        page=page,
        page_size=page_size,
    )


@router.post("/backtest/jobs", response_model=BacktestCreateJobsResponse)
def create_backtest_jobs(
    request: BacktestCreateJobsRequest,
) -> BacktestCreateJobsResponse:
    try:
        return cb_quant_service.create_jobs(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtest/jobs/{job_id}/cancel", response_model=OperationResponse)
def cancel_backtest_job(job_id: str) -> OperationResponse:
    job = cb_quant_service.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"backtest job not found: {job_id}")
    return OperationResponse(ok=True, message=f"job {job_id} -> {job.status}")


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
