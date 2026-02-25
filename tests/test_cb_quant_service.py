from __future__ import annotations

from datetime import date
from threading import Lock
from typing import Any

import pytest

from vnpy.web.schemas import (
    BacktestCreateJobsRequest,
    BacktestJobRow,
    CandidateRow,
    JobStatus,
    StrategyTemplateConfigResponse,
    StrategyTemplateRow,
)
from vnpy.web.services.cb_quant_service import CbQuantService


class _DummyStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    def upsert_job(self, *, row: dict[str, Any], context: dict[str, Any]) -> None:
        self.saved.append({"row": row, "context": context})

    def get_job_context(self, job_id: str) -> dict[str, Any] | None:
        return None


class _DummyExecutor:
    def __init__(self) -> None:
        self.submitted: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, func: Any, *args: Any) -> None:
        self.submitted.append((func, args))


def _build_service() -> CbQuantService:
    service = object.__new__(CbQuantService)
    service._lock = Lock()
    service._seq = 0
    service._jobs = []
    service._job_context = {}
    service._leaderboard = []
    service._candidates = []
    service._templates = [
        StrategyTemplateRow(
            id="TPL-001",
            name="实盘模板",
            version="v1.0.0",
            status="active",
            factor_count=0,
            rebalance="weekly",
            risk_preset="balanced",
            combo_size=100,
            owner="unit-test",
            updated_at="2026-02-25 12:00",
        )
    ]
    service._template_configs = {
        "TPL-001": StrategyTemplateConfigResponse(
            template_id="TPL-001",
            factor_keys=[],
            expression_draft="",
            parameter_space=[],
            combo_size=100,
            updated_at="2026-02-25 12:00",
        )
    }
    service._store = _DummyStore()
    service._executor = _DummyExecutor()
    return service


def _candidate(*, combo_id: str, template: str, template_id: str = "TPL-001") -> CandidateRow:
    return CandidateRow(
        rank=1,
        template_id=template_id,
        template=template,
        combo_id=combo_id,
        est_combos=10,
        status="pending_backtest",
        pass_rate=None,
        window="full",
        source="generated",
        run_id="RUN-UNIT",
        generated_at="2026-02-25 12:00",
    )


def _job(*, job_id: str, combo_id: str, template: str, status: JobStatus = "queued") -> BacktestJobRow:
    return BacktestJobRow(
        job_id=job_id,
        strategy_id="STR-001",
        combo_id=combo_id,
        rule_pack_id="RP-CAN-000001",
        template=template,
        window="近1年",
        status=status,
        progress=3,
        business_date="2026-02-25",
        created_at="2026-02-25 12:00",
        started_at="",
        eta="--",
        worker="",
    )


class TestBacktestJobsRealDataOnly:
    def test_list_jobs_should_hide_legacy_or_mock_rows(self) -> None:
        service = _build_service()
        service._candidates = [_candidate(combo_id="CMB-000001", template="实盘模板")]
        service._jobs = [
            _job(job_id="BT-LEGACY-001", combo_id="CMB-VERIFY-001", template="SmokeTemplate"),
            _job(job_id="BT-REAL-001", combo_id="CMB-000001", template="实盘模板"),
        ]

        payload = service.list_jobs()

        assert payload.total == 1
        assert len(payload.items) == 1
        assert payload.items[0].job_id == "BT-REAL-001"

    def test_get_stats_should_count_visible_jobs_only(self) -> None:
        service = _build_service()
        service._candidates = [_candidate(combo_id="CMB-000001", template="实盘模板")]
        service._jobs = [
            _job(job_id="BT-LEGACY-001", combo_id="CMB-VERIFY-001", template="SmokeTemplate", status="cancelled"),
            _job(job_id="BT-REAL-001", combo_id="CMB-000001", template="实盘模板", status="running"),
        ]

        stats = service.get_stats()

        assert stats.running_jobs == 1
        assert stats.cancelled_jobs == 0


class TestBacktestCreateJobsStrictCandidate:
    def test_create_jobs_should_reject_ambiguous_combo_without_template(self) -> None:
        service = _build_service()
        service._candidates = [
            _candidate(combo_id="CMB-000001", template="模板A", template_id="TPL-001"),
            _candidate(combo_id="CMB-000001", template="模板B", template_id="TPL-002"),
        ]

        request = BacktestCreateJobsRequest(
            combo_id="CMB-000001",
            template=None,
            windows=["1y"],
            business_date=date(2026, 2, 25),
        )

        with pytest.raises(ValueError, match="unknown combo_id/template"):
            service.create_jobs(request)

    def test_create_jobs_should_use_real_candidate_template_and_persist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = _build_service()
        service._candidates = [_candidate(combo_id="CMB-000001", template="实盘模板", template_id="TPL-001")]
        monkeypatch.setattr(
            service,
            "_resolve_setting_for_combo",
            lambda **_kwargs: {"price_bemchmark": 110.0, "premium_bemchmark": 25.0},
        )

        request = BacktestCreateJobsRequest(
            combo_id="CMB-000001",
            template="实盘模板",
            windows=["1y"],
            business_date=date(2026, 2, 25),
        )
        payload = service.create_jobs(request)

        assert payload.created_count == 1
        assert payload.jobs[0].template == "实盘模板"
        assert payload.jobs[0].status == "queued"
        assert payload.jobs[0].started_at == ""
        assert payload.jobs[0].worker == ""
        assert len(service._store.saved) == 1
        assert service._store.saved[0]["context"]["setting"]["price_bemchmark"] == 110.0
        assert len(service._executor.submitted) == 1


class TestOptimizeSamplingHelpers:
    def test_sample_combo_indices_should_be_unique_and_cover_range(self) -> None:
        indices = CbQuantService._sample_combo_indices(total=1000, sample_limit=11)
        assert len(indices) == 11
        assert indices == sorted(indices)
        assert len(set(indices)) == 11
        assert indices[0] == 1
        assert indices[-1] == 1000

    def test_should_enable_stage1_screening(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = _build_service()
        monkeypatch.setenv("CBQ_OPT_STAGE1_THRESHOLD", "500")
        assert service._should_enable_stage1_screening(total=600, windows=["full", "3y", "1y"]) is True
        assert service._should_enable_stage1_screening(total=400, windows=["full", "3y", "1y"]) is False
        assert service._should_enable_stage1_screening(total=600, windows=["full"]) is False
