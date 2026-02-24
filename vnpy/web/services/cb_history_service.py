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
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_code6(value: Any) -> str:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text
    return digits.zfill(6)


class CbHistoryService:
    """Persisted daily snapshot service for backtest history."""

    def __init__(self) -> None:
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
        return self._store.load_market_dataset()

    def get_summary(self) -> HistoryStoreSummary:
        return self._store.get_summary()

    def latest_sync_log(self) -> HistorySyncLog | None:
        return self._store.latest_sync_log()

    def bootstrap_from_crawler_snapshots(self) -> int:
        # One-time import from local crawler historical snapshots when DB is empty.
        summary = self._store.get_summary()
        if summary.snapshot_count > 0:
            return 0

        module = self._adapter._load_module()
        dataset = module.load_market_data(self._adapter.data_dir)
        inserted_dates = 0
        for trade_date, frame in sorted(dataset, key=lambda item: item[0]):
            if frame.empty:
                continue
            rows = self._frame_to_rows(frame)
            upserted = self._store.upsert_snapshot_rows(
                trade_date=trade_date,
                source="crawler.xlsx",
                rows=rows,
            )
            if upserted > 0:
                inserted_dates += 1

        self._store.append_sync_log(
            mode="bootstrap",
            source="crawler.xlsx",
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            upserted=inserted_dates,
            status="ok",
            message=f"bootstrap imported {inserted_dates} trade dates from local crawler snapshots",
        )
        return inserted_dates

    def sync_today_from_market(self, *, mode: str = "manual") -> int:
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
        self._stop_event.set()
        thread = self._sync_thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def _sync_loop(self) -> None:
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
        rows: list[dict[str, Any]] = []
        for _, item in frame.iterrows():
            payload = item.to_dict()
            payload["cb_code"] = str(payload.get("cb_code") or "")
            rows.append(payload)
        return rows

    @staticmethod
    def _market_row_to_backtest_row(item: dict[str, Any], trade_date: str) -> dict[str, Any]:
        # Map realtime quote schema to crawler-style row fields used by filter/backtest.
        price = _safe_float(item.get("price"))
        pure_bond_value = _safe_float(item.get("pure_bond_value"), 0.0)
        stock_price = _safe_float(item.get("stock_price"), 0.0)
        redeem_trigger_price = _safe_float(item.get("redeem_trigger_price"), 0.0)
        remain_years = item.get("remain_years")
        try:
            remain_years_f = float(remain_years) if remain_years is not None else None
        except Exception:
            remain_years_f = None

        if remain_years_f is None:
            date_return_distance = "无权"
            date_remain_distance = "0天"
        elif remain_years_f <= 2:
            date_return_distance = "回售内"
            date_remain_distance = f"{max(1, int(remain_years_f * 365))}天"
        else:
            date_return_distance = "未到"
            date_remain_distance = f"{remain_years_f:.2f}年"

        is_ransom_flag = "True" if (redeem_trigger_price > 0 and stock_price >= redeem_trigger_price) else "False"
        cb_to_pb = 0.0
        if pure_bond_value > 0:
            cb_to_pb = round(price / pure_bond_value, 4)

        remain_amount = _safe_float(item.get("remain_scale_yi"), 0.0)
        issue_date = str(item.get("listed_date") or item.get("subscribe_date") or trade_date)
        stock_id = str(item.get("stock_id") or "")
        market = ""
        stock_code = stock_id
        if stock_id.startswith("sh") or stock_id.startswith("sz") or stock_id.startswith("bj"):
            market = stock_id[:2]
            stock_code = stock_id[2:]

        return {
            "cb_code": _to_code6(item.get("bond_id")),
            "cb_name": str(item.get("bond_name") or ""),
            "price": round(price, 3),
            "cb_percent": _safe_float(item.get("increase_rt"), 0.0),
            "premium_rate": _safe_float(item.get("premium_rt"), 0.0),
            "convert_stock_value": _safe_float(item.get("convert_value"), 0.0),
            "convert_stock_price": _safe_float(item.get("convert_price"), 0.0),
            "new_style": pure_bond_value,
            "old_style": _safe_float(item.get("option_value"), 0.0),
            "stock_stdevry": _safe_float(item.get("stock_volatility"), 30.0),
            "stock_code": _to_code6(stock_code),
            "stock_name": str(item.get("stock_name") or ""),
            "stock_price": _safe_float(item.get("stock_price"), 0.0),
            "stock_percent": _safe_float(item.get("stock_increase_rt"), 0.0),
            "pb": _safe_float(item.get("stock_pb"), 0.0),
            "market_cap": _safe_float(item.get("remain_scale_yi"), 0.0),
            "remain_amount": remain_amount,
            "remain_to_cap": _safe_float(item.get("float_mv_ratio"), 0.0),
            "issue_date": issue_date[:10],
            "date_return_distance": date_return_distance,
            "date_remain_distance": date_remain_distance,
            "date_convert_distance": "已到",
            "is_unlist": "N",
            "last_is_unlist": "N",
            "is_ransom_flag": is_ransom_flag,
            "is_repair_flag": "True",
            "repair_flag_remark": "",
            "rate_expire_aftertax": _safe_float(item.get("expiry_ytm_pre_tax"), 0.0),
            "rate_expire": _safe_float(item.get("expiry_ytm_pre_tax"), 0.0),
            "rate_return": _safe_float(item.get("put_ytm"), 0.0),
            "market": market,
            "rating": str(item.get("rating") or ""),
            "volume": _safe_float(item.get("amount_wan"), 0.0),
            "market_source": str(item.get("source") or ""),
        }

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        text = os.getenv(name)
        if text is None:
            return default
        try:
            return int(text)
        except ValueError:
            return default
