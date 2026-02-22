from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Iterable, TypeVar

from vnpy.web.schemas import (
    BacktestCompareResponse,
    BacktestCompareRow,
    BacktestCreateJobsRequest,
    BacktestCreateJobsResponse,
    BacktestJobListResponse,
    BacktestJobRow,
    BacktestLeaderboardResponse,
    BacktestLeaderboardRow,
    BacktestStatsResponse,
    CandidateListResponse,
    CandidateRow,
    WindowName,
)


T = TypeVar("T")


def _paginate(items: list[T], page: int, page_size: int) -> list[T]:
    safe_page = max(1, page)
    safe_size = max(1, page_size)
    start = (safe_page - 1) * safe_size
    return items[start : start + safe_size]


def _now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _now_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


class CbQuantService:
    """In-memory mock service for frontend-backend integration."""

    def __init__(self) -> None:
        self._lock: Lock = Lock()
        self._seq: int = 7

        self._candidates: list[CandidateRow] = [
            CandidateRow(rank=1, template="双低稳健A", combo_id="CMB-102883", est_combos=86400, pass_rate=9.3, window="full"),
            CandidateRow(rank=2, template="双低+评级", combo_id="CMB-202551", est_combos=98304, pass_rate=8.7, window="3y"),
            CandidateRow(rank=3, template="低价低溢价轮动", combo_id="CMB-140301", est_combos=145920, pass_rate=7.9, window="full"),
            CandidateRow(rank=4, template="双低回撤保护", combo_id="CMB-883102", est_combos=110592, pass_rate=8.2, window="1y"),
            CandidateRow(rank=5, template="小盘债容量版", combo_id="CMB-553210", est_combos=73728, pass_rate=9.1, window="3y"),
            CandidateRow(rank=6, template="流动性优先", combo_id="CMB-033421", est_combos=57600, pass_rate=10.8, window="1y"),
            CandidateRow(rank=7, template="低溢价动量", combo_id="CMB-932811", est_combos=122880, pass_rate=6.6, window="full"),
            CandidateRow(rank=8, template="高波动降权", combo_id="CMB-502102", est_combos=69120, pass_rate=7.1, window="1y"),
        ]

        self._jobs: list[BacktestJobRow] = [
            BacktestJobRow(job_id="BT-20260221-001", strategy_id="STR-001", combo_id="CMB-102883", rule_pack_id="RP-BASE-001", template="双低稳健A", window="2018-2025", status="running", progress=62, started_at="09:31:05", eta="7m", worker="wk-01"),
            BacktestJobRow(job_id="BT-20260221-002", strategy_id="STR-002", combo_id="CMB-202551", rule_pack_id="RP-RISK-203", template="双低+评级", window="近3年", status="queued", progress=0, started_at="09:33:15", eta="--", worker="wk-02"),
            BacktestJobRow(job_id="BT-20260221-003", strategy_id="STR-003", combo_id="CMB-140301", rule_pack_id="RP-FAST-112", template="低价低溢价轮动", window="近1年", status="finished", progress=100, started_at="09:15:22", eta="done", worker="wk-03"),
            BacktestJobRow(job_id="BT-20260221-004", strategy_id="STR-004", combo_id="CMB-033421", rule_pack_id="RP-LIQ-088", template="流动性优先", window="2018-2025", status="failed", progress=44, started_at="08:56:40", eta="stopped", worker="wk-04"),
            BacktestJobRow(job_id="BT-20260221-005", strategy_id="STR-005", combo_id="CMB-883102", rule_pack_id="RP-DD-157", template="双低回撤保护", window="近3年", status="running", progress=81, started_at="09:02:11", eta="3m", worker="wk-05"),
            BacktestJobRow(job_id="BT-20260221-006", strategy_id="STR-006", combo_id="CMB-553210", rule_pack_id="RP-CAP-119", template="小盘债容量版", window="近1年", status="finished", progress=100, started_at="08:21:53", eta="done", worker="wk-01"),
            BacktestJobRow(job_id="BT-20260221-007", strategy_id="STR-007", combo_id="CMB-932811", rule_pack_id="RP-MOM-076", template="低溢价动量", window="2018-2025", status="queued", progress=0, started_at="09:40:14", eta="--", worker="wk-03"),
        ]

        self._leaderboard: list[BacktestLeaderboardRow] = [
            BacktestLeaderboardRow(rank=1, strategy_id="STR-001", combo_id="CMB-102883", rule_pack_id="RP-BASE-001", template="双低稳健A", cagr=0.342, mdd=0.192, calmar=1.78, win_rate=62.4, turnover=0.29, recent_1y=0.271, robust_score=92.2, window="full"),
            BacktestLeaderboardRow(rank=2, strategy_id="STR-002", combo_id="CMB-202551", rule_pack_id="RP-RISK-203", template="双低+评级", cagr=0.331, mdd=0.185, calmar=1.79, win_rate=61.2, turnover=0.27, recent_1y=0.259, robust_score=90.9, window="3y"),
            BacktestLeaderboardRow(rank=3, strategy_id="STR-005", combo_id="CMB-883102", rule_pack_id="RP-DD-157", template="双低回撤保护", cagr=0.316, mdd=0.169, calmar=1.87, win_rate=59.8, turnover=0.25, recent_1y=0.246, robust_score=89.8, window="1y"),
            BacktestLeaderboardRow(rank=4, strategy_id="STR-003", combo_id="CMB-140301", rule_pack_id="RP-FAST-112", template="低价低溢价轮动", cagr=0.354, mdd=0.222, calmar=1.59, win_rate=60.1, turnover=0.33, recent_1y=0.221, robust_score=86.4, window="full"),
            BacktestLeaderboardRow(rank=5, strategy_id="STR-004", combo_id="CMB-033421", rule_pack_id="RP-LIQ-088", template="流动性优先", cagr=0.288, mdd=0.141, calmar=2.04, win_rate=57.6, turnover=0.21, recent_1y=0.208, robust_score=85.2, window="3y"),
            BacktestLeaderboardRow(rank=6, strategy_id="STR-006", combo_id="CMB-553210", rule_pack_id="RP-CAP-119", template="小盘债容量版", cagr=0.301, mdd=0.201, calmar=1.49, win_rate=58.8, turnover=0.26, recent_1y=0.193, robust_score=82.9, window="1y"),
            BacktestLeaderboardRow(rank=7, strategy_id="STR-007", combo_id="CMB-932811", rule_pack_id="RP-MOM-076", template="低溢价动量", cagr=0.278, mdd=0.236, calmar=1.18, win_rate=54.1, turnover=0.38, recent_1y=0.161, robust_score=77.5, window="full"),
        ]

        self._compare: list[BacktestCompareRow] = [
            BacktestCompareRow(metric="CAGR", category="return", baseline=0.214, candidate_a=0.342, candidate_b=0.331, candidate_c=0.316),
            BacktestCompareRow(metric="近1年收益", category="return", baseline=0.112, candidate_a=0.271, candidate_b=0.259, candidate_c=0.246),
            BacktestCompareRow(metric="最大回撤", category="risk", baseline=0.286, candidate_a=0.192, candidate_b=0.185, candidate_c=0.169),
            BacktestCompareRow(metric="Calmar", category="risk", baseline=0.750, candidate_a=1.780, candidate_b=1.790, candidate_c=1.870),
            BacktestCompareRow(metric="年化换手", category="trade", baseline=0.440, candidate_a=0.290, candidate_b=0.270, candidate_c=0.250),
            BacktestCompareRow(metric="胜率", category="trade", baseline=0.490, candidate_a=0.624, candidate_b=0.612, candidate_c=0.598),
        ]

    def list_candidates(self, keyword: str = "", window: str = "all") -> CandidateListResponse:
        rows: list[CandidateRow] = []
        needle = keyword.strip().lower()

        for row in self._candidates:
            if window != "all" and row.window != window:
                continue
            if needle:
                raw = f"{row.template}|{row.combo_id}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        return CandidateListResponse(items=rows, total=len(rows))

    def list_jobs(
        self,
        keyword: str = "",
        status: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> BacktestJobListResponse:
        rows: list[BacktestJobRow] = []
        needle = keyword.strip().lower()

        for row in self._jobs:
            if status != "all" and row.status != status:
                continue
            if needle:
                raw = f"{row.job_id}|{row.strategy_id}|{row.combo_id}|{row.rule_pack_id}|{row.template}|{row.worker}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return BacktestJobListResponse(items=paged, total=total, page=page, page_size=page_size)

    def list_leaderboard(
        self,
        keyword: str = "",
        window: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> BacktestLeaderboardResponse:
        rows: list[BacktestLeaderboardRow] = []
        needle = keyword.strip().lower()

        for row in self._leaderboard:
            if window != "all" and row.window != window:
                continue
            if needle:
                raw = f"{row.strategy_id}|{row.combo_id}|{row.rule_pack_id}|{row.template}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return BacktestLeaderboardResponse(items=paged, total=total, page=page, page_size=page_size)

    def list_compare(self, keyword: str = "", category: str = "all") -> BacktestCompareResponse:
        rows: list[BacktestCompareRow] = []
        needle = keyword.strip().lower()

        for row in self._compare:
            if category != "all" and row.category != category:
                continue
            if needle and needle not in row.metric.lower():
                continue
            rows.append(row)

        return BacktestCompareResponse(items=rows, total=len(rows))

    def get_stats(self) -> BacktestStatsResponse:
        running = sum(1 for row in self._jobs if row.status == "running")
        queued = sum(1 for row in self._jobs if row.status == "queued")
        finished = sum(1 for row in self._jobs if row.status == "finished")
        failed = sum(1 for row in self._jobs if row.status == "failed")
        rule_pack_count = len({row.rule_pack_id for row in self._jobs})
        top_cagr = max((row.cagr for row in self._leaderboard), default=0.0)

        return BacktestStatsResponse(
            running_jobs=running,
            queued_jobs=queued,
            finished_jobs=finished,
            failed_jobs=failed,
            rule_pack_count=rule_pack_count,
            top_cagr=top_cagr,
        )

    def create_jobs(self, request: BacktestCreateJobsRequest) -> BacktestCreateJobsResponse:
        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]

        candidate = self._find_candidate(request.combo_id)
        template_name = request.template or (candidate.template if candidate else "未命名模板")
        rule_pack_id = request.rule_pack_id or self._build_rule_pack_id(request)

        with self._lock:
            created: list[BacktestJobRow] = []
            for window_name in windows:
                self._seq += 1
                seq = self._seq
                job = BacktestJobRow(
                    job_id=f"BT-{_now_yyyymmdd()}-{seq:03d}",
                    strategy_id=f"STR-{seq:03d}",
                    combo_id=request.combo_id,
                    rule_pack_id=rule_pack_id,
                    template=template_name,
                    window=self._window_label(window_name),
                    status="queued",
                    progress=0,
                    started_at=_now_hms(),
                    eta="--",
                    worker=f"wk-0{(seq % 5) + 1}",
                )
                created.append(job)

            self._jobs = [*created, *self._jobs]

        message = (
            f"已入队 {len(created)} 个窗口任务（每个窗口 1 条）："
            f"{request.combo_id} × {rule_pack_id}"
        )

        return BacktestCreateJobsResponse(
            batch_id=f"BATCH-{_now_yyyymmdd()}-{self._seq:03d}",
            combo_id=request.combo_id,
            rule_pack_id=rule_pack_id,
            source_mode=request.source_mode,
            created_count=len(created),
            windows=windows,
            jobs=created,
            message=message,
        )

    def _find_candidate(self, combo_id: str) -> CandidateRow | None:
        for row in self._candidates:
            if row.combo_id == combo_id:
                return row
        return None

    def _build_rule_pack_id(self, request: BacktestCreateJobsRequest) -> str:
        mode_prefix = {
            "inherit": "INH",
            "candidate": "CAN",
            "custom": "CUS",
        }.get(request.source_mode, "CAN")

        est = request.est_strategies or 251220
        digest = str(est).zfill(6)[-6:]
        return f"RP-{mode_prefix}-{digest}"

    @staticmethod
    def _normalize_windows(values: Iterable[WindowName]) -> list[WindowName]:
        seen: set[WindowName] = set()
        normalized: list[WindowName] = []

        for value in values:
            if value in seen:
                continue
            seen.add(value)
            normalized.append(value)

        return normalized

    @staticmethod
    def _window_label(window_name: WindowName) -> str:
        if window_name == "full":
            return "2018-2025"
        if window_name == "3y":
            return "近3年"
        return "近1年"
