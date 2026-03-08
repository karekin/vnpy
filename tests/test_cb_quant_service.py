from __future__ import annotations

from datetime import date
from threading import Lock
from typing import Any

import pytest

from vnpy.web.adapters.crawler_phase_a_adapter import CrawlerPhaseABacktestAdapter
from vnpy.web.schemas import (
    BacktestCreateJobsRequest,
    BacktestJobRow,
    CandidateRow,
    JobStatus,
    StrategyParamSpaceRow,
    StrategyOptimizeTaskCreateRequest,
    StrategyTemplateConfigRequest,
    StrategyTemplateConfigResponse,
    StrategyOptimizeTaskRow,
    StrategyTemplateRow,
)
from vnpy.web.services.cb_quant_service import CbQuantService


class _DummyStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []
        self.saved_optimize: list[dict[str, Any]] = []
        self.saved_templates: list[dict[str, Any]] = []

    def upsert_job(self, *, row: dict[str, Any], context: dict[str, Any]) -> None:
        self.saved.append({"row": row, "context": context})

    def upsert_optimize_task(self, *, row: dict[str, Any]) -> None:
        self.saved_optimize.append(row)

    def get_job_context(self, job_id: str) -> dict[str, Any] | None:
        return None

    def replace_templates_and_configs(self, *, templates: list[dict[str, Any]], configs: dict[str, dict[str, Any]]) -> None:
        self.saved_templates = templates


class _DummyExecutor:
    def __init__(self) -> None:
        self.submitted: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, func: Any, *args: Any) -> None:
        self.submitted.append((func, args))


class _DummyAdapter:
    @staticmethod
    def default_setting() -> dict[str, Any]:
        return {"price_benchmark": 110.0}


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
    service._template_seq = 1
    service._opt_task_seq = 0
    service._optimize_tasks = []
    service._optimize_results = {}
    service._optimize_top_bonds = {}
    service._adapter = _DummyAdapter()
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
            lambda **_kwargs: {"price_benchmark": 110.0, "premium_benchmark": 25.0},
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
        assert service._store.saved[0]["context"]["setting"]["price_benchmark"] == 110.0
        assert len(service._executor.submitted) == 1

    def test_create_jobs_should_support_one_week_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = _build_service()
        service._candidates = [_candidate(combo_id="CMB-000001", template="实盘模板", template_id="TPL-001")]
        monkeypatch.setattr(
            service,
            "_resolve_setting_for_combo",
            lambda **_kwargs: {"price_benchmark": 110.0, "premium_benchmark": 25.0},
        )

        request = BacktestCreateJobsRequest(
            combo_id="CMB-000001",
            template="实盘模板",
            windows=["1w"],
            business_date=date(2026, 2, 25),
        )
        payload = service.create_jobs(request)

        assert payload.created_count == 1
        assert payload.jobs[0].window == "近1周"
        assert service._store.saved[0]["context"]["window_name"] == "1w"


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

    def test_normalize_template_config_should_preserve_dblow_and_normalize_legacy_typo(self) -> None:
        service = _build_service()

        normalized = service._normalize_template_config(
            StrategyTemplateConfigResponse(
                template_id="TPL-001",
                factor_keys=["dblow", "stock_stdevry_bemchmark"],
                expression_draft="",
                parameter_space=[
                    StrategyParamSpaceRow(
                        factor_key="dblow",
                        value_type="number",
                        enabled=True,
                        min_value=100.0,
                        max_value=180.0,
                        step=5.0,
                        enum_values=[],
                    ),
                    StrategyParamSpaceRow(
                        factor_key="stock_stdevry_bemchmark",
                        value_type="number",
                        enabled=True,
                        min_value=20.0,
                        max_value=35.0,
                        step=5.0,
                        enum_values=[],
                    ),
                ],
                combo_size=0,
                updated_at="2026-03-08 12:00",
            )
        )

        assert normalized.factor_keys == ["dblow", "volatility_benchmark"]
        assert [row.factor_key for row in normalized.parameter_space] == ["dblow", "volatility_benchmark"]
        assert normalized.parameter_space[0].min_value == 100.0
        assert normalized.parameter_space[0].max_value == 180.0

    def test_build_setting_from_factor_values_should_preserve_selected_raw_factors(self) -> None:
        service = _build_service()
        setting = service._build_setting_from_factor_values(
            {
                "dblow": 130.0,
                "option_value": 12.5,
                "theory_bias": 3.0,
                "pre_close": 118.0,
            }
        )

        assert setting["selected_factor_keys"] == ["dblow", "option_value", "theory_bias", "pre_close"]
        assert setting["factor_values"]["dblow"] == 130.0
        assert setting["option_value"] == 12.5

    def test_expand_template_factor_combos_should_skip_non_strong_supported_factors(self) -> None:
        service = _build_service()
        service._template_configs["TPL-001"] = StrategyTemplateConfigResponse(
            template_id="TPL-001",
            factor_keys=["dblow", "bias_5", "open"],
            expression_draft="",
            parameter_space=[
                StrategyParamSpaceRow(
                    factor_key="dblow",
                    value_type="number",
                    enabled=True,
                    min_value=100.0,
                    max_value=110.0,
                    step=10.0,
                    enum_values=[],
                ),
                StrategyParamSpaceRow(
                    factor_key="bias_5",
                    value_type="number",
                    enabled=True,
                    min_value=1.0,
                    max_value=2.0,
                    step=1.0,
                    enum_values=[],
                ),
                StrategyParamSpaceRow(
                    factor_key="open",
                    value_type="number",
                    enabled=True,
                    min_value=100.0,
                    max_value=110.0,
                    step=10.0,
                    enum_values=[],
                ),
            ],
            combo_size=0,
            updated_at="2026-03-08 12:00",
        )

        payload = service.expand_template_factor_combos(
            "TPL-001",
            type("Req", (), {"min_factor_count": 1, "max_factor_count": 2, "max_strategies": None})(),
        )

        assert payload is not None
        assert payload.created_count == 3
        assert "暂未强支持因子" in payload.message
        created_factor_sets = [cfg.factor_keys for key, cfg in service._template_configs.items() if key != "TPL-001"]
        assert ["dblow"] in created_factor_sets
        assert ["open"] in created_factor_sets
        assert ["dblow", "open"] in created_factor_sets


class TestWindowHelpers:
    def test_slice_dataset_should_support_one_week_window(self) -> None:
        dataset = [
            ("2026-02-20", object()),
            ("2026-02-24", object()),
            ("2026-02-27", object()),
            ("2026-03-02", object()),
            ("2026-03-06", object()),
        ]

        sliced = CrawlerPhaseABacktestAdapter._slice_dataset(
            dataset=dataset,
            window_name="1w",
            start_date=None,
            end_date=None,
        )

        assert [item[0] for item in sliced] == ["2026-02-27", "2026-03-02", "2026-03-06"]

    def test_pick_stage1_window_should_prefer_shorter_window(self) -> None:
        assert CbQuantService._pick_stage1_window(["full", "3y", "1y", "1w"]) == "1w"


class TestOptimizeRestartRecovery:
    def test_mark_unfinished_optimize_tasks_as_failed_after_restart(self) -> None:
        service = _build_service()
        service._optimize_tasks = [
            StrategyOptimizeTaskRow(
                task_id="OPT-20260226-0001",
                template_id="TPL-001",
                template_name="实盘模板",
                status="queued",
                progress=0,
                total_combinations=68,
                evaluated_combinations=0,
                windows=["1y"],
                start_date=None,
                end_date=None,
                eta="--",
                message="任务已入队",
                created_at="2026-02-26 00:00",
                started_at=None,
                finished_at=None,
            ),
            StrategyOptimizeTaskRow(
                task_id="OPT-20260226-0002",
                template_id="TPL-001",
                template_name="实盘模板",
                status="finished",
                progress=100,
                total_combinations=68,
                evaluated_combinations=68,
                windows=["1y"],
                start_date=None,
                end_date=None,
                eta="done",
                message="ok",
                created_at="2026-02-26 00:01",
                started_at="2026-02-26 00:01",
                finished_at="2026-02-26 00:10",
            ),
        ]
        service._optimize_results = {}
        service._optimize_top_bonds = {}

        service._mark_unfinished_optimize_tasks_as_failed_after_restart()

        statuses = {row.task_id: row.status for row in service._optimize_tasks}
        assert statuses["OPT-20260226-0001"] == "failed"
        assert statuses["OPT-20260226-0002"] == "finished"


class TestOptimizeTaskSubmit:
    def test_create_optimize_task_should_mark_failed_when_submit_error(self) -> None:
        service = _build_service()

        class _FailingExecutor:
            def submit(self, *_args: Any, **_kwargs: Any) -> None:
                raise RuntimeError("executor closed")

        service._executor = _FailingExecutor()
        request = StrategyOptimizeTaskCreateRequest(
            template_id="TPL-001",
            windows=["1y"],
            max_combinations=1,
            top_n=5,
            current_top_n=5,
        )

        payload = service.create_optimize_task(request)

        assert payload is not None
        assert payload.task.status == "failed"
        assert "提交执行失败" in payload.message
