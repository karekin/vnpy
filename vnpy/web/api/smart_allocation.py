from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from vnpy.web.contracts.smart_allocation import (
    SmartAllocationCallSpreadDailyRecommendationResponse,
    SmartAllocationCashflowEventRequest,
    SmartAllocationCashflowEventResponse,
    SmartAllocationDashboardResponse,
    SmartAllocationLeapsCandidateResponse,
    SmartAllocationProfileRequest,
    SmartAllocationProfileResponse,
    SmartAllocationRecommendationResponse,
    SmartAllocationRecommendationStatusRequest,
    SmartAllocationSnapshotRequest,
    SmartAllocationSnapshotResponse,
    SmartAllocationWaterfallTransferResponse,
    SmartAllocationWheelCandidateResponse,
    SmartAllocationWheelDailyRecommendationResponse,
)
import vnpy.web.services as services


router = APIRouter(prefix="/smart-allocation", tags=["smart-allocation"])


@router.get("/profiles", response_model=list[SmartAllocationProfileResponse])
def list_profiles() -> list[SmartAllocationProfileResponse]:
    return services.allocation_service.list_profiles()


@router.post("/profiles", response_model=SmartAllocationProfileResponse)
def create_profile(payload: SmartAllocationProfileRequest) -> SmartAllocationProfileResponse:
    profile = services.allocation_service.create_profile(
        age=payload.age,
        income_status=payload.income_status,
        name=payload.name,
        rebalance_threshold=payload.rebalance_threshold,
        allow_bull_market_leaps_relaxation=payload.allow_bull_market_leaps_relaxation,
        quality_stock_symbols=payload.quality_stock_symbols,
        wheel_symbols=payload.wheel_symbols,
        leaps_symbols=payload.leaps_symbols,
    )
    return services.allocation_service.get_dashboard(profile.id).profile


@router.get("/profiles/{profile_id}", response_model=SmartAllocationProfileResponse)
def get_profile(profile_id: str) -> SmartAllocationProfileResponse:
    try:
        return services.allocation_service.get_profile_response(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.put("/profiles/{profile_id}", response_model=SmartAllocationProfileResponse)
def update_profile(profile_id: str, payload: SmartAllocationProfileRequest) -> SmartAllocationProfileResponse:
    try:
        profile = services.allocation_service.update_profile(
            profile_id,
            age=payload.age,
            income_status=payload.income_status,
            name=payload.name,
            rebalance_threshold=payload.rebalance_threshold,
            allow_bull_market_leaps_relaxation=payload.allow_bull_market_leaps_relaxation,
            quality_stock_symbols=payload.quality_stock_symbols,
            wheel_symbols=payload.wheel_symbols,
            leaps_symbols=payload.leaps_symbols,
        )
        return services.allocation_service.get_dashboard(profile.id).profile
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/profiles/{profile_id}/activate", response_model=SmartAllocationProfileResponse)
def activate_profile(profile_id: str) -> SmartAllocationProfileResponse:
    try:
        return services.allocation_service.activate_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.get("/dashboard", response_model=SmartAllocationDashboardResponse)
def get_dashboard(profile_id: str | None = Query(None)) -> SmartAllocationDashboardResponse:
    try:
        return services.allocation_service.get_dashboard(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.get("/snapshots/latest", response_model=SmartAllocationSnapshotResponse)
def get_latest_snapshot(profile_id: str | None = Query(None)) -> SmartAllocationSnapshotResponse:
    try:
        return services.allocation_service.latest_snapshot_response(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/snapshots/refresh", response_model=SmartAllocationDashboardResponse)
def refresh_snapshot(
    payload: SmartAllocationSnapshotRequest,
    profile_id: str | None = Query(None),
) -> SmartAllocationDashboardResponse:
    try:
        return services.allocation_service.refresh_snapshot(profile_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/snapshots/import/legacy-position-manager", response_model=SmartAllocationDashboardResponse)
def import_legacy_position_manager_snapshot(
    payload: dict,
    profile_id: str | None = Query(None),
) -> SmartAllocationDashboardResponse:
    try:
        return services.allocation_service.refresh_from_legacy_portfolio_status(profile_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/guardrails/check", response_model=SmartAllocationDashboardResponse)
def run_guardrail_check(profile_id: str | None = Query(None)) -> SmartAllocationDashboardResponse:
    return get_dashboard(profile_id)


@router.get("/guardrails/events", response_model=SmartAllocationDashboardResponse)
def list_guardrail_events(profile_id: str | None = Query(None)) -> SmartAllocationDashboardResponse:
    return get_dashboard(profile_id)


@router.post("/recommendations/generate", response_model=SmartAllocationDashboardResponse)
def generate_recommendations(profile_id: str | None = Query(None)) -> SmartAllocationDashboardResponse:
    return get_dashboard(profile_id)


@router.get("/recommendations", response_model=list[SmartAllocationRecommendationResponse])
def list_recommendations(profile_id: str | None = Query(None)) -> list[SmartAllocationRecommendationResponse]:
    try:
        return services.allocation_service.list_recommendations(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/recommendations/{recommendation_id}/accept", response_model=list[SmartAllocationRecommendationResponse])
def accept_recommendation(
    recommendation_id: str,
    payload: SmartAllocationRecommendationStatusRequest,
    profile_id: str | None = Query(None),
) -> list[SmartAllocationRecommendationResponse]:
    try:
        return services.allocation_service.set_recommendation_status(
            profile_id,
            recommendation_id,
            status="accepted",
            user_note=payload.user_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/recommendations/{recommendation_id}/ignore", response_model=list[SmartAllocationRecommendationResponse])
def ignore_recommendation(
    recommendation_id: str,
    payload: SmartAllocationRecommendationStatusRequest,
    profile_id: str | None = Query(None),
) -> list[SmartAllocationRecommendationResponse]:
    try:
        return services.allocation_service.set_recommendation_status(
            profile_id,
            recommendation_id,
            status="ignored",
            user_note=payload.user_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/recommendations/{recommendation_id}/mark-executed", response_model=list[SmartAllocationRecommendationResponse])
def mark_recommendation_executed(
    recommendation_id: str,
    payload: SmartAllocationRecommendationStatusRequest,
    profile_id: str | None = Query(None),
) -> list[SmartAllocationRecommendationResponse]:
    try:
        return services.allocation_service.set_recommendation_status(
            profile_id,
            recommendation_id,
            status="executed",
            user_note=payload.user_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/cashflow/events", response_model=list[SmartAllocationWaterfallTransferResponse])
def record_cashflow_event(
    payload: SmartAllocationCashflowEventRequest,
    profile_id: str | None = Query(None),
) -> list[SmartAllocationWaterfallTransferResponse]:
    try:
        return services.allocation_service.record_cashflow_event(
            profile_id,
            event_type=payload.event_type,
            amount=payload.amount,
            source_bucket=payload.source_bucket,
            target_bucket=payload.target_bucket,
            symbol=payload.symbol,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.get("/cashflow/events", response_model=list[SmartAllocationCashflowEventResponse])
def list_cashflow_events(profile_id: str | None = Query(None)) -> list[SmartAllocationCashflowEventResponse]:
    try:
        return services.allocation_service.list_cashflow_event_responses(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.get("/cashflow/waterfall", response_model=SmartAllocationDashboardResponse)
def get_cashflow_waterfall(profile_id: str | None = Query(None)) -> SmartAllocationDashboardResponse:
    return get_dashboard(profile_id)


@router.get("/leaps/candidates", response_model=list[SmartAllocationLeapsCandidateResponse])
def list_leaps_candidates(profile_id: str | None = Query(None)) -> list[SmartAllocationLeapsCandidateResponse]:
    try:
        return services.allocation_service.list_leaps_candidates(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/leaps/candidates/refresh", response_model=list[SmartAllocationLeapsCandidateResponse])
def refresh_leaps_candidates(profile_id: str | None = Query(None)) -> list[SmartAllocationLeapsCandidateResponse]:
    return list_leaps_candidates(profile_id)


@router.get("/wheel/candidates", response_model=list[SmartAllocationWheelCandidateResponse])
def list_wheel_candidates(profile_id: str | None = Query(None)) -> list[SmartAllocationWheelCandidateResponse]:
    try:
        return services.allocation_service.list_wheel_candidates(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/wheel/candidates/refresh", response_model=list[SmartAllocationWheelCandidateResponse])
def refresh_wheel_candidates(profile_id: str | None = Query(None)) -> list[SmartAllocationWheelCandidateResponse]:
    return list_wheel_candidates(profile_id)


@router.get("/wheel/daily-recommendations", response_model=SmartAllocationWheelDailyRecommendationResponse)
def get_wheel_daily_recommendations(
    profile_id: str | None = Query(None),
) -> SmartAllocationWheelDailyRecommendationResponse:
    try:
        return services.allocation_service.get_daily_wheel_recommendation(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/wheel/daily-recommendations/refresh", response_model=SmartAllocationWheelDailyRecommendationResponse)
def refresh_wheel_daily_recommendations(
    profile_id: str | None = Query(None),
) -> SmartAllocationWheelDailyRecommendationResponse:
    return get_wheel_daily_recommendations(profile_id)


@router.get("/call-spread/daily-recommendations", response_model=SmartAllocationCallSpreadDailyRecommendationResponse)
def get_call_spread_daily_recommendations(
    profile_id: str | None = Query(None),
) -> SmartAllocationCallSpreadDailyRecommendationResponse:
    try:
        return services.allocation_service.get_daily_call_spread_recommendation(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}") from exc


@router.post("/call-spread/daily-recommendations/refresh", response_model=SmartAllocationCallSpreadDailyRecommendationResponse)
def refresh_call_spread_daily_recommendations(
    profile_id: str | None = Query(None),
) -> SmartAllocationCallSpreadDailyRecommendationResponse:
    return get_call_spread_daily_recommendations(profile_id)
