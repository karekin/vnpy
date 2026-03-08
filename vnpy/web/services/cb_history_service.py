"""CB Quant 历史快照服务。

这个模块的职责是维护“可用于回测的日级快照库”：

1. 运行过程中，从实时行情服务拉取当日行情并落库
2. 提供摘要、日志和调度能力，供 API 与回测服务复用
3. 对所有写库数据统一映射到标准快照 schema
"""

from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

import pandas as pd

from vnpy.web.adapters import CrawlerPhaseABacktestAdapter
from vnpy.web.domain.cb_quant.history_store import CbHistoryStore, HistoryStoreSummary, HistorySyncLog


def _safe_float(value: Any, default: float = 0.0) -> float:
    """把各种外部来源字段稳妥地转成 float。"""
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_code6(value: Any) -> str:
    """把债券/股票代码统一归一成 6 位数字字符串。"""
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text
    return digits.zfill(6)


def _normalize_yn(value: Any, default: str = "N") -> str:
    """把 Y/N 风格字段标准化，兼容 bool 和多种文本写法。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return "Y" if value else "N"
    text = str(value).strip().upper()
    if text in {"Y", "N"}:
        return text
    if text in {"TRUE", "T", "YES", "1"}:
        return "Y"
    if text in {"FALSE", "F", "NO", "0"}:
        return "N"
    return default


def _normalize_tf(value: Any, default: str = "False") -> str:
    """把 True/False 风格字段标准化，兼容 bool 和多种文本写法。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return "True" if value else "False"
    text = str(value).strip()
    if text in {"True", "False"}:
        return text
    upper = text.upper()
    if upper in {"TRUE", "T", "YES", "1"}:
        return "True"
    if upper in {"FALSE", "F", "NO", "0"}:
        return "False"
    return default


class CbHistoryService:
    """回测历史快照服务。

    `CbQuantService` 本身不直接关心快照落库细节，而是通过本服务拿到
    按交易日组织的标准快照数据集。这样能把“数据同步”和“回测分析”分层。
    """

    def __init__(self) -> None:
        """初始化本地快照库、适配器和定时同步线程状态。"""
        adapter = CrawlerPhaseABacktestAdapter()
        storage_dir: Path = adapter.data_dir / "_cb_quant"
        self._store = CbHistoryStore(storage_dir / "cb_snapshots.db")
        self._adapter = adapter
        self._sync_thread: Thread | None = None
        self._stop_event: Event = Event()
        self._start_lock: Lock = Lock()
        self._poll_seconds: int = max(60, int(self._env_int("VNPY_CB_SYNC_INTERVAL_SECONDS", 60 * 30)))

    @property
    def store(self) -> CbHistoryStore:
        return self._store

    def load_market_dataset(self) -> list[tuple[str, pd.DataFrame]]:
        """返回按交易日组织的历史快照数据集。"""
        return self._store.load_market_dataset()

    def get_summary(self) -> HistoryStoreSummary:
        """返回快照库摘要信息，供前端展示数据覆盖范围。"""
        return self._store.get_summary()

    def latest_sync_log(self) -> HistorySyncLog | None:
        """返回最近一次同步日志。"""
        return self._store.latest_sync_log()

    def bootstrap_from_crawler_snapshots(self) -> int:
        """保留兼容方法名，但不再从任何旧离线快照导入历史数据。

        历史数据主路径已经统一到 `cb_snapshots.db` / `CbTushareService`。
        若数据库为空，这里不再尝试从旧离线文件补数。
        """
        summary = self._store.get_summary()
        if summary.snapshot_count > 0:
            return 0

        self._store.append_sync_log(
            mode="bootstrap",
            source="deprecated",
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            upserted=0,
            status="ok",
            message="bootstrap from legacy excel snapshots has been removed; please sync via tushare or market services",
        )
        return 0

    def sync_today_from_market(self, *, mode: str = "manual") -> int:
        """从实时行情服务抓取当日行情并写入回测快照库。"""
        # Import is local to avoid cross-service circular imports.
        from vnpy.web.services.cb_market_service import CbMarketService

        market = CbMarketService()
        response = market.list_bonds(min_volume_wan=0)
        trade_date = date.today().isoformat()
        rows = [self._market_row_to_backtest_row(item.model_dump(), trade_date) for item in response.items]
        upserted = self._store.upsert_snapshot_rows(
            trade_date=trade_date,
            source=response.source,
            rows=rows,
        )
        self._store.append_sync_log(
            mode=mode,
            source=response.source,
            trade_date=trade_date,
            upserted=upserted,
            status="ok",
            message=f"synced {upserted} rows from {response.source}",
        )
        return upserted

    def start_scheduler(self) -> None:
        """启动后台定时同步线程；重复调用是幂等的。"""
        with self._start_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                return
            self._stop_event.clear()
            self._sync_thread = Thread(
                target=self._sync_loop,
                name="cb-history-sync",
                daemon=True,
            )
            self._sync_thread.start()

    def stop_scheduler(self) -> None:
        """停止后台同步线程。"""
        self._stop_event.set()
        thread = self._sync_thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def _sync_loop(self) -> None:
        """定时轮询任务主体。

        同步失败不抛到线程外层，而是写入同步日志，避免把守护线程打死。
        """
        while not self._stop_event.wait(timeout=self._poll_seconds):
            try:
                self.sync_today_from_market(mode="scheduled")
            except Exception as exc:  # noqa: BLE001
                self._store.append_sync_log(
                    mode="scheduled",
                    source="eastmoney",
                    trade_date=date.today().isoformat(),
                    upserted=0,
                    status="failed",
                    message=str(exc),
                )

    @staticmethod
    def _frame_to_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
        """把任意 DataFrame 行转成快照表可落库的行结构。

        最终字段收口由 `CbHistoryStore.upsert_snapshot_rows(...)` 完成，
        这里主要负责把 DataFrame 行提取成 dict，并补最基本的兼容值。
        """
        rows: list[dict[str, Any]] = []
        for _, item in frame.iterrows():
            payload = item.to_dict()
            payload["bond_code"] = str(payload.get("bond_code") or "")
            payload["is_listed"] = not (_normalize_yn(payload.get("is_listed"), "Y") == "N")
            payload["was_listed_prev_day"] = not (_normalize_yn(payload.get("was_listed_prev_day"), "Y") == "N")
            payload["is_redeem_triggered"] = _normalize_tf(payload.get("is_redeem_triggered"), "False") == "True"
            if payload.get("bond_pure_value_ratio") is None:
                price = _safe_float(payload.get("close_price"), 0.0)
                pure_bond_value = _safe_float(payload.get("pure_bond_value"), 0.0)
                payload["bond_pure_value_ratio"] = round(price / pure_bond_value, 4) if pure_bond_value > 0 else 1.0
            rows.append(payload)
        return rows

    @staticmethod
    def _market_row_to_backtest_row(item: dict[str, Any], trade_date: str) -> dict[str, Any]:
        """把实时行情 schema 映射成标准回测快照行。

        这里返回的是“标准快照字段”的一个上游版本；
        真正写入 `cb_daily_snapshot.payload_json` 前还会再经过统一 schema 收口。
        """
        price = _safe_float(item.get("price"))
        pure_bond_value = _safe_float(item.get("pure_bond_value"), 0.0)
        stock_price = _safe_float(item.get("stock_price"), 0.0)
        redeem_trigger_price = _safe_float(item.get("redeem_trigger_price"), 0.0)
        turnover_rate_pct = _safe_float(item.get("turnover_rt"), 0.0)
        remain_years = item.get("remain_years")
        try:
            remain_years_f = float(remain_years) if remain_years is not None else None
        except Exception:
            remain_years_f = None

        if remain_years_f is None:
            put_status = "not_applicable"
            days_to_maturity = 0
        elif remain_years_f <= 2:
            put_status = "active"
            days_to_maturity = max(1, int(remain_years_f * 365))
        else:
            put_status = "not_reached"
            days_to_maturity = max(1, int(remain_years_f * 365))

        is_redeem_triggered = redeem_trigger_price > 0 and stock_price >= redeem_trigger_price
        bond_pure_value_ratio = 0.0
        if pure_bond_value > 0:
            bond_pure_value_ratio = round(price / pure_bond_value, 4)

        outstanding_amount_yi = _safe_float(item.get("remain_scale_yi"), 0.0)
        outstanding_to_market_cap_ratio = _safe_float(item.get("float_mv_ratio"), 0.0)
        underlying_market_cap_yi = 0.0
        if outstanding_amount_yi > 0 and outstanding_to_market_cap_ratio > 0:
            ratio = outstanding_to_market_cap_ratio / 100.0 if outstanding_to_market_cap_ratio > 1 else outstanding_to_market_cap_ratio
            if ratio > 0:
                underlying_market_cap_yi = round(outstanding_amount_yi / ratio, 4)
        issue_date = str(item.get("listed_date") or item.get("subscribe_date") or trade_date)
        stock_id = str(item.get("stock_id") or "")
        market = ""
        stock_code = stock_id
        if stock_id.startswith("sh") or stock_id.startswith("sz") or stock_id.startswith("bj"):
            market = stock_id[:2]
            stock_code = stock_id[2:]

        return {
            "bond_code": _to_code6(item.get("bond_id")),
            "bond_name": str(item.get("bond_name") or ""),
            "close_price": round(price, 3),
            "open_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "pre_close_price": 0.0,
            "bond_pct_change": _safe_float(item.get("increase_rt"), 0.0),
            "conversion_premium_pct": _safe_float(item.get("premium_rt"), 0.0),
            "conversion_price": _safe_float(item.get("convert_price"), 0.0),
            "pure_bond_value": pure_bond_value,
            "bond_pure_value_ratio": bond_pure_value_ratio if bond_pure_value_ratio > 0 else 1.0,
            "option_value": _safe_float(item.get("option_value"), 0.0),
            "underlying_volatility": _safe_float(item.get("stock_volatility"), 30.0),
            "underlying_stock_code": _to_code6(stock_code),
            "underlying_stock_name": str(item.get("stock_name") or ""),
            "underlying_close_price": _safe_float(item.get("stock_price"), 0.0),
            "underlying_pct_change": _safe_float(item.get("stock_increase_rt"), 0.0),
            "underlying_pb": _safe_float(item.get("stock_pb"), 0.0),
            "underlying_market_cap_yi": underlying_market_cap_yi,
            "outstanding_amount_yi": outstanding_amount_yi,
            "outstanding_to_market_cap_ratio": outstanding_to_market_cap_ratio,
            "listing_date": issue_date[:10],
            "put_status": put_status,
            "days_to_maturity": days_to_maturity,
            "days_to_conversion_start": 0,
            "is_listed": True,
            "was_listed_prev_day": True,
            "is_redeem_triggered": is_redeem_triggered,
            "redeem_status": "",
            "days_to_redeem": None,
            "ytm_to_maturity_after_tax_pct": _safe_float(item.get("expiry_ytm_pre_tax"), 0.0),
            "ytm_to_maturity_pct": _safe_float(item.get("expiry_ytm_pre_tax"), 0.0),
            "ytm_to_put_pct": _safe_float(item.get("put_ytm"), 0.0),
            "market": market,
            "rating": str(item.get("rating") or ""),
            "volume_hand": 0.0,
            "turnover_amount_wan": _safe_float(item.get("amount_wan"), 0.0),
            "turnover_rate_pct": turnover_rate_pct,
            "issue_size_yi": _safe_float(item.get("issue_scale_yi"), 0.0),
            "limit_status": 1 if _safe_float(item.get("increase_rt"), 0.0) >= 19.5 else -1 if _safe_float(item.get("increase_rt"), 0.0) <= -19.5 else 0,
            "data_source": str(item.get("source") or ""),
        }

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        """读取 int 环境变量，失败时回退默认值。"""
        text = os.getenv(name)
        if text is None:
            return default
        try:
            return int(text)
        except ValueError:
            return default
