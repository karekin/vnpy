from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import re
import time
from typing import Any

import pandas as pd

from vnpy.web.adapters import CrawlerPhaseABacktestAdapter
from vnpy.web.domain.cb_quant.history_store import CbHistoryStore
from vnpy.web.domain.cb_quant.tushare_store import CbTushareStore, TushareStoreSummary, TushareSyncLog
from vnpy.web.schemas import BondMarketRow


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_ymd(value: str | date | None) -> str:
    if value is None:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    return date.today().isoformat()


def _ts_code_to_code6(ts_code: str) -> str:
    text = str(ts_code or "").strip()
    if not text:
        return ""
    raw = text.split(".", 1)[0]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits.zfill(6) if digits else raw


def _to_stock_ts_code(stk_code: str, *, bond_ts_code: str) -> str:
    raw = str(stk_code or "").strip()
    if not raw:
        return ""
    if "." in raw:
        return raw
    suffix = "SH"
    bond = str(bond_ts_code or "").strip()
    if "." in bond:
        suffix = bond.split(".", 1)[1]
    return f"{raw}.{suffix}"


def _pick(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


class _TushareClient:
    def __init__(self, token: str, *, http_url: str) -> None:
        self._token = token
        self._http_url = http_url
        self._pro: Any = None

    def _ensure(self) -> Any:
        if self._pro is not None:
            return self._pro
        try:
            import tushare as ts
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("tushare package not installed, please run: pip install tushare") from exc

        ts.set_token(self._token)
        self._pro = ts.pro_api(self._token)
        # Required for some private/proxy deployments.
        self._pro._DataApi__token = self._token
        self._pro._DataApi__http_url = self._http_url
        return self._pro

    def query(self, api_name: str, **params: Any) -> pd.DataFrame:
        pro = self._ensure()
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                if hasattr(pro, api_name):
                    func = getattr(pro, api_name)
                    frame = func(**params)
                else:
                    frame = pro.query(api_name, **params)
                if frame is None:
                    return pd.DataFrame()
                if not isinstance(frame, pd.DataFrame):
                    return pd.DataFrame()
                return frame
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not self._retryable_message(str(exc)) or attempt >= 3:
                    break
                time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"tushare query failed: {api_name}, params={params}, error={last_exc}") from last_exc

    @staticmethod
    def _retryable_message(message: str) -> bool:
        text = str(message or "").lower()
        patterns = (
            "服务器内部错误",
            "请稍后重试",
            "timeout",
            "timed out",
            "max retries exceeded",
            "connection reset",
            "502",
            "503",
            "504",
        )
        return any(pattern in text for pattern in patterns)


class CbTushareService:
    """Sync tushare pro data and shape to crawler-compatible backtest snapshots."""

    def __init__(self) -> None:
        adapter = CrawlerPhaseABacktestAdapter()
        storage_dir: Path = adapter.data_dir / "_cb_quant"
        self._store = CbTushareStore(storage_dir / "cb_tushare.db")
        self._history_store = CbHistoryStore(storage_dir / "cb_snapshots.db")

    @property
    def store(self) -> CbTushareStore:
        return self._store

    def get_summary(self) -> TushareStoreSummary:
        return self._store.get_summary()

    def latest_sync_log(self) -> TushareSyncLog | None:
        return self._store.latest_sync_log()

    def load_latest_market_rows(
        self,
        *,
        min_volume_wan: float = 0.0,
        as_of: date | None = None,
    ) -> tuple[list[BondMarketRow], str]:
        target_day = as_of or date.today()
        token = self._load_token()
        resolved_http_url = str(self._load_http_url()).strip()
        client = _TushareClient(token, http_url=resolved_http_url)

        try:
            rows, trade_date = self._load_latest_market_rows_from_client(
                client=client,
                as_of=target_day,
                min_volume_wan=min_volume_wan,
            )
            if rows:
                return rows, f"tushare.pro({trade_date})"
        except Exception as exc:
            cached_rows, cached_trade_date = self._load_latest_market_rows_from_store(
                min_volume_wan=min_volume_wan,
            )
            if cached_rows and cached_trade_date:
                return cached_rows, f"tushare.store({cached_trade_date})"
            raise RuntimeError(f"tushare market load failed: {exc}") from exc

        cached_rows, cached_trade_date = self._load_latest_market_rows_from_store(
            min_volume_wan=min_volume_wan,
        )
        if cached_rows and cached_trade_date:
            return cached_rows, f"tushare.store({cached_trade_date})"
        raise RuntimeError("tushare market load failed: no rows returned")

    def sync_range(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        mode: str = "manual",
        max_trade_days: int = 1500,
        http_url: str | None = None,
        sync_events: bool = True,
    ) -> dict[str, Any]:
        token = self._load_token()
        resolved_http_url = str(http_url or self._load_http_url()).strip()
        client = _TushareClient(token, http_url=resolved_http_url)

        today = date.today()
        end = end_date or today
        start = start_date or (end - timedelta(days=90))
        if start > end:
            start, end = end, start

        start_text = start.isoformat()
        end_text = end.isoformat()
        source = f"tushare.pro@{resolved_http_url}"

        cb_daily_rows_total = 0
        stock_daily_rows_total = 0
        event_rows_total = 0
        factor_rows_total = 0
        snapshot_rows_total = 0
        trade_day_count = 0
        skipped_days: list[tuple[str, str]] = []
        last_valid_price_map: dict[str, float] = {}

        try:
            cal_df = client.query(
                "trade_cal",
                exchange="SSE",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                is_open="1",
            )
            cal_rows = self._rows(cal_df)
            self._store.upsert_trade_calendar(cal_rows)
            trade_days = self._store.list_open_trade_dates(start_date=start_text, end_date=end_text)
            if not trade_days:
                trade_days = self._fallback_trade_days(start, end)
            if max_trade_days > 0 and len(trade_days) > max_trade_days:
                trade_days = trade_days[-max_trade_days:]

            cb_basic_df = client.query("cb_basic")
            cb_basic_rows = self._rows(cb_basic_df)
            self._store.upsert_cb_basic(cb_basic_rows)
            cb_basic_map = self._store.load_cb_basic_map()
            if sync_events:
                event_rows_total += self._sync_event_ods(
                    client=client,
                    start=start,
                    end=end,
                )

            for trade_day in trade_days:
                trade_day_count += 1
                td_8 = trade_day.replace("-", "")
                try:
                    cb_daily_df = client.query("cb_daily", trade_date=td_8)
                    cb_daily_rows = self._rows(cb_daily_df)
                    if not cb_daily_rows:
                        continue
                    cb_daily_rows_total += self._store.upsert_cb_daily_ods(
                        trade_date=trade_day,
                        rows=cb_daily_rows,
                    )

                    stock_ts_codes = self._collect_stock_codes(cb_daily_rows, cb_basic_map)
                    stock_daily_map, stock_basic_map = self._load_stock_maps(
                        client=client,
                        trade_date=trade_day,
                        stock_ts_codes=stock_ts_codes,
                    )
                    stock_daily_rows_total += len(stock_daily_map)

                    factor_rows, snapshot_rows = self._build_factor_and_snapshot_rows(
                        trade_date=trade_day,
                        cb_daily_rows=cb_daily_rows,
                        cb_basic_map=cb_basic_map,
                        stock_daily_map=stock_daily_map,
                        stock_basic_map=stock_basic_map,
                        last_valid_price_map=last_valid_price_map,
                    )

                    factor_rows_total += self._store.upsert_factor_rows(trade_date=trade_day, rows=factor_rows)
                    snapshot_rows_total += self._history_store.upsert_snapshot_rows(
                        trade_date=trade_day,
                        source=source,
                        rows=snapshot_rows,
                    )
                except Exception as exc:  # noqa: BLE001
                    if self._auth_error_message(str(exc)):
                        raise
                    skipped_days.append((trade_day, str(exc)))
                    continue

            if cb_daily_rows_total <= 0 and skipped_days:
                first = skipped_days[0]
                raise RuntimeError(
                    f"all trade days failed, first_day={first[0]}, error={first[1]}"
                )

            message = (
                f"sync finished: {trade_day_count} trade days, "
                f"cb_rows={cb_daily_rows_total}, stock_rows={stock_daily_rows_total}, "
                f"event_rows={event_rows_total}, "
                f"factor_rows={factor_rows_total}, snapshot_rows={snapshot_rows_total}"
            )
            if skipped_days:
                message += f", skipped_days={len(skipped_days)}, first_skipped={skipped_days[0][0]}"
            self._store.append_sync_log(
                mode=mode,
                source=source,
                start_date=start_text,
                end_date=end_text,
                trade_days=trade_day_count,
                cb_daily_rows=cb_daily_rows_total,
                stock_daily_rows=stock_daily_rows_total,
                event_rows=event_rows_total,
                factor_rows=factor_rows_total,
                snapshot_rows=snapshot_rows_total,
                status="ok",
                message=message,
            )
            return {
                "ok": True,
                "mode": mode,
                "source": source,
                "start_date": start_text,
                "end_date": end_text,
                "trade_days": trade_day_count,
                "cb_daily_rows": cb_daily_rows_total,
                "stock_daily_rows": stock_daily_rows_total,
                "event_rows": event_rows_total,
                "factor_rows": factor_rows_total,
                "snapshot_rows": snapshot_rows_total,
                "message": message,
            }
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._store.append_sync_log(
                mode=mode,
                source=source,
                start_date=start_text,
                end_date=end_text,
                trade_days=trade_day_count,
                cb_daily_rows=cb_daily_rows_total,
                stock_daily_rows=stock_daily_rows_total,
                event_rows=event_rows_total,
                factor_rows=factor_rows_total,
                snapshot_rows=snapshot_rows_total,
                status="failed",
                message=message,
            )
            raise

    def sync_incremental(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        mode: str = "manual",
        max_trade_days: int = 90,
    ) -> dict[str, Any]:
        today = date.today()
        resolved_end = end_date or today
        resolved_start = start_date
        if resolved_start is None:
            summary = self._history_store.get_summary()
            if summary.date_end:
                try:
                    resolved_start = datetime.strptime(summary.date_end, "%Y-%m-%d").date() + timedelta(days=1)
                except ValueError:
                    resolved_start = resolved_end - timedelta(days=90)
            else:
                resolved_start = resolved_end - timedelta(days=90)

        if resolved_start > resolved_end:
            same_day = resolved_end.isoformat()
            source = f"tushare.pro@{self._load_http_url()}"
            return {
                "ok": True,
                "mode": mode,
                "source": source,
                "start_date": same_day,
                "end_date": same_day,
                "trade_days": 0,
                "cb_daily_rows": 0,
                "stock_daily_rows": 0,
                "event_rows": 0,
                "factor_rows": 0,
                "snapshot_rows": 0,
                "message": "already up to date, no incremental days to sync",
            }

        days: list[date] = []
        cursor = resolved_start
        while cursor <= resolved_end:
            days.append(cursor)
            cursor += timedelta(days=1)
        if max_trade_days > 0 and len(days) > max_trade_days:
            days = days[-max_trade_days:]
            resolved_start = days[0]

        endpoints = self._candidate_http_urls()
        total_trade_days = 0
        total_cb_daily_rows = 0
        total_stock_daily_rows = 0
        total_event_rows = 0
        total_factor_rows = 0
        total_snapshot_rows = 0
        failed_days: list[tuple[str, str]] = []
        used_sources: list[str] = []

        for index, day in enumerate(days):
            success = False
            last_error = ""
            for endpoint in endpoints:
                try:
                    payload = self.sync_range(
                        start_date=day,
                        end_date=day,
                        mode=f"{mode}-daily",
                        max_trade_days=5,
                        http_url=endpoint,
                        sync_events=(index == 0),
                    )
                    total_trade_days += int(payload.get("trade_days", 0) or 0)
                    total_cb_daily_rows += int(payload.get("cb_daily_rows", 0) or 0)
                    total_stock_daily_rows += int(payload.get("stock_daily_rows", 0) or 0)
                    total_event_rows += int(payload.get("event_rows", 0) or 0)
                    total_factor_rows += int(payload.get("factor_rows", 0) or 0)
                    total_snapshot_rows += int(payload.get("snapshot_rows", 0) or 0)
                    source = str(payload.get("source") or "")
                    if source:
                        used_sources.append(source)
                    success = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    continue
            if not success:
                failed_days.append((day.isoformat(), last_error or "unknown error"))

        if failed_days and total_cb_daily_rows <= 0:
            first = failed_days[0]
            raise RuntimeError(
                f"incremental sync failed, first_day={first[0]}, error={first[1]}"
            )

        unique_sources = sorted({item for item in used_sources if item})
        if not unique_sources:
            source_text = f"tushare.pro@{self._load_http_url()}"
        elif len(unique_sources) == 1:
            source_text = unique_sources[0]
        else:
            source_text = "multi-endpoint"

        message = (
            f"incremental sync finished: calendar_days={len(days)}, "
            f"trade_days={total_trade_days}, cb_rows={total_cb_daily_rows}, "
            f"stock_rows={total_stock_daily_rows}, event_rows={total_event_rows}, "
            f"factor_rows={total_factor_rows}, snapshot_rows={total_snapshot_rows}"
        )
        if failed_days:
            message += f", failed_days={len(failed_days)}, first_failed={failed_days[0][0]}"

        return {
            "ok": True,
            "mode": mode,
            "source": source_text,
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "trade_days": total_trade_days,
            "cb_daily_rows": total_cb_daily_rows,
            "stock_daily_rows": total_stock_daily_rows,
            "event_rows": total_event_rows,
            "factor_rows": total_factor_rows,
            "snapshot_rows": total_snapshot_rows,
            "message": message,
        }

    def _sync_event_ods(
        self,
        *,
        client: _TushareClient,
        start: date,
        end: date,
    ) -> int:
        total = 0
        start_8 = start.strftime("%Y%m%d")
        end_8 = end.strftime("%Y%m%d")
        specs: list[tuple[str, dict[str, Any]]] = [
            ("cb_issue", {}),
            ("cb_call", {"start_date": start_8, "end_date": end_8}),
            ("cb_price_chg", {"start_date": start_8, "end_date": end_8}),
            ("cb_share", {"start_date": start_8, "end_date": end_8}),
            ("cb_rate", {}),
        ]
        for api_name, params in specs:
            rows = self._query_optional_rows(client=client, api_name=api_name, **params)
            if not rows:
                continue
            total += self._store.upsert_cb_event_rows(event_type=api_name, rows=rows)
        return total

    def _load_stock_maps(
        self,
        *,
        client: _TushareClient,
        trade_date: str,
        stock_ts_codes: list[str],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        if not stock_ts_codes:
            return {}, {}
        td_8 = trade_date.replace("-", "")
        daily_rows: list[dict[str, Any]] = []
        basic_rows: list[dict[str, Any]] = []
        for chunk in self._chunk(stock_ts_codes, 80):
            ts_code = ",".join(chunk)
            daily_df = client.query("daily", ts_code=ts_code, trade_date=td_8)
            basic_df = client.query("daily_basic", ts_code=ts_code, trade_date=td_8)
            daily_rows.extend(self._rows(daily_df))
            basic_rows.extend(self._rows(basic_df))

        self._store.upsert_stock_daily_ods(trade_date=trade_date, rows=daily_rows)
        self._store.upsert_stock_daily_basic_ods(trade_date=trade_date, rows=basic_rows)

        daily_map = {str(row.get("ts_code") or ""): row for row in daily_rows if row.get("ts_code")}
        basic_map = {str(row.get("ts_code") or ""): row for row in basic_rows if row.get("ts_code")}
        return daily_map, basic_map

    def _load_latest_market_rows_from_client(
        self,
        *,
        client: _TushareClient,
        as_of: date,
        min_volume_wan: float,
    ) -> tuple[list[BondMarketRow], str]:
        cal_df = client.query(
            "trade_cal",
            exchange="SSE",
            start_date=(as_of - timedelta(days=14)).strftime("%Y%m%d"),
            end_date=as_of.strftime("%Y%m%d"),
            is_open="1",
        )
        cal_rows = self._rows(cal_df)
        trade_days = sorted({_to_ymd(row.get("cal_date")) for row in cal_rows if row.get("cal_date")})
        if not trade_days:
            trade_days = self._fallback_trade_days(as_of - timedelta(days=14), as_of)

        cb_basic_rows = self._rows(client.query("cb_basic"))
        self._store.upsert_cb_basic(cb_basic_rows)
        cb_basic_map = self._store.load_cb_basic_map()

        for trade_date in reversed(trade_days):
            cb_daily_rows = self._rows(client.query("cb_daily", trade_date=trade_date.replace("-", "")))
            if not cb_daily_rows:
                continue
            self._store.upsert_cb_daily_ods(trade_date=trade_date, rows=cb_daily_rows)
            stock_ts_codes = self._collect_stock_codes(cb_daily_rows, cb_basic_map)
            stock_daily_map, stock_basic_map = self._load_stock_maps(
                client=client,
                trade_date=trade_date,
                stock_ts_codes=stock_ts_codes,
            )
            rows = self._build_market_rows(
                trade_date=trade_date,
                cb_daily_rows=cb_daily_rows,
                cb_basic_map=cb_basic_map,
                stock_daily_map=stock_daily_map,
                stock_basic_map=stock_basic_map,
                min_volume_wan=min_volume_wan,
            )
            if rows:
                return rows, trade_date

        raise RuntimeError("tushare returned no cb_daily rows in recent trade days")

    def _load_latest_market_rows_from_store(
        self,
        *,
        min_volume_wan: float,
    ) -> tuple[list[BondMarketRow], str | None]:
        summary = self._store.get_summary()
        trade_date = summary.cb_date_end
        if not trade_date:
            return [], None

        cb_daily_map = self._store.load_trade_row_map(table="ts_cb_daily_ods", trade_date=trade_date)
        if not cb_daily_map:
            return [], trade_date

        cb_basic_map = self._store.load_cb_basic_map()
        stock_daily_map = self._store.load_trade_row_map(table="ts_stock_daily_ods", trade_date=trade_date)
        stock_basic_map = self._store.load_trade_row_map(table="ts_stock_daily_basic_ods", trade_date=trade_date)
        rows = self._build_market_rows(
            trade_date=trade_date,
            cb_daily_rows=list(cb_daily_map.values()),
            cb_basic_map=cb_basic_map,
            stock_daily_map=stock_daily_map,
            stock_basic_map=stock_basic_map,
            min_volume_wan=min_volume_wan,
        )
        return rows, trade_date

    def _build_market_rows(
        self,
        *,
        trade_date: str,
        cb_daily_rows: list[dict[str, Any]],
        cb_basic_map: dict[str, dict[str, Any]],
        stock_daily_map: dict[str, dict[str, Any]],
        stock_basic_map: dict[str, dict[str, Any]],
        min_volume_wan: float,
    ) -> list[BondMarketRow]:
        rows: list[BondMarketRow] = []
        trade_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
        for cb_row in cb_daily_rows:
            ts_code = str(_pick(cb_row, "ts_code", "bond_code", "code", default="")).strip()
            if not ts_code:
                continue

            basic = cb_basic_map.get(ts_code, {})
            if not self._is_listed_on_trade_date(basic=basic, trade_date=trade_dt):
                continue

            code6 = _ts_code_to_code6(ts_code)
            stock_ts_code = _to_stock_ts_code(str(_pick(basic, "stk_code", default="")), bond_ts_code=ts_code)
            stock_daily = stock_daily_map.get(stock_ts_code, {})
            stock_basic = stock_basic_map.get(stock_ts_code, {})

            price = self._normalize_bond_price(_safe_float(_pick(cb_row, "close", "price"), 0.0))
            if price <= 0:
                price = self._normalize_bond_price(_safe_float(_pick(cb_row, "pre_close", "preclose"), 0.0))
            if price <= 0:
                continue

            amount_raw = _safe_float(_pick(cb_row, "amount"), 0.0)
            amount_wan = round(max(0.0, amount_raw), 1) if amount_raw > 0 else 0.0
            if amount_wan < min_volume_wan:
                continue

            stock_price = _safe_float(_pick(stock_daily, "close"), 0.0)
            stock_increase_rt = _safe_float(_pick(stock_daily, "pct_chg"), 0.0)
            stock_pb = _safe_float(_pick(stock_basic, "pb", "pb_new"), 0.0)
            convert_price = _safe_float(_pick(basic, "conv_price"), 0.0)
            convert_value = round(stock_price / convert_price * 100.0, 3) if stock_price > 0 and convert_price > 0 else 0.0
            premium_rt = round((price / convert_value - 1.0) * 100.0, 2) if convert_value > 0 else 0.0
            stock_volatility = round(max(10.0, min(60.0, abs(stock_increase_rt) * 1.5 + 20.0)), 2)
            pure_bond_value_raw = _safe_float(_pick(cb_row, "bond_value", "pure_bond_value"), 0.0)
            pure_bond_value = round(self._normalize_bond_price(pure_bond_value_raw), 3) if pure_bond_value_raw > 0 else None

            remain_size_raw = _safe_float(_pick(basic, "remain_size"), 0.0)
            issue_size_raw = _safe_float(_pick(basic, "issue_size"), 0.0)
            remain_scale_yi = round(remain_size_raw / 100000000.0, 4) if remain_size_raw > 0 else None
            issue_scale_yi = round(issue_size_raw / 100000000.0, 4) if issue_size_raw > 0 else None
            circ_mv = _safe_float(_pick(stock_basic, "circ_mv"), 0.0)
            float_mv_ratio = None
            if remain_scale_yi is not None and circ_mv > 0:
                float_mv_ratio = round(remain_scale_yi * 10000.0 / circ_mv * 100.0, 2)

            maturity_text = str(_pick(basic, "maturity_date", default="")).strip()
            remain_years, _remain_distance, _return_distance = self._derive_maturity_fields(
                trade_dt=trade_dt,
                maturity_text=maturity_text,
            )
            stock_id = self._to_stock_display_id(stock_ts_code)
            listed_date = _to_ymd(_pick(basic, "list_date"))
            convert_start_date = _to_ymd(_pick(basic, "conv_start_date"))
            subscribe_date = _to_ymd(_pick(basic, "value_date", "issue_date"))

            rows.append(
                BondMarketRow(
                    bond_id=code6,
                    bond_name=str(_pick(basic, "bond_short_name", "bond_name", default=ts_code)),
                    price=round(price, 3),
                    increase_rt=round(_safe_float(_pick(cb_row, "pct_chg"), 0.0), 2),
                    stock_id=stock_id,
                    stock_name=str(_pick(basic, "stk_short_name", default="")),
                    stock_price=round(stock_price, 2) if stock_price > 0 else None,
                    stock_increase_rt=round(stock_increase_rt, 2) if stock_price > 0 else None,
                    stock_pb=round(stock_pb, 2) if stock_pb > 0 else None,
                    convert_price=round(convert_price, 3) if convert_price > 0 else None,
                    pure_bond_value=pure_bond_value,
                    premium_rt=premium_rt,
                    convert_value=convert_value,
                    dblow=round(price + premium_rt, 3),
                    option_value=None,
                    stock_volatility=stock_volatility,
                    put_trigger_price=None,
                    redeem_trigger_price=None,
                    float_mv_ratio=float_mv_ratio,
                    fund_holding_ratio=None,
                    maturity_date=_to_ymd(maturity_text) if maturity_text else None,
                    remain_years=round(remain_years, 4) if remain_years is not None else None,
                    remain_scale_yi=remain_scale_yi,
                    amount_wan=amount_wan,
                    turnover_rt=None,
                    expiry_ytm_pre_tax=None,
                    put_ytm=None,
                    volume_wan=amount_wan,
                    issue_scale_yi=issue_scale_yi,
                    rating=str(_pick(basic, "rating", default="")).strip() or None,
                    listed_date=listed_date,
                    convert_start_date=convert_start_date,
                    subscribe_date=subscribe_date,
                    source="tushare.pro",
                    update_time=datetime.now().strftime("%H:%M:%S"),
                )
            )

        rows.sort(key=lambda item: (item.amount_wan or 0.0, item.bond_id), reverse=True)
        return rows

    @staticmethod
    def _normalize_bond_price(value: float) -> float:
        if value <= 0:
            return 0.0
        return value

    @staticmethod
    def _to_stock_display_id(stock_ts_code: str) -> str:
        text = str(stock_ts_code or "").strip()
        if not text:
            return ""
        if "." not in text:
            return text
        raw, suffix = text.split(".", 1)
        market = "sh" if suffix.upper() == "SH" else "sz"
        return f"{market}{raw}"

    def _load_cb_call_map(
        self,
        *,
        trade_date: str,
        ts_codes: list[str],
    ) -> dict[str, dict[str, Any]]:
        rows = self._store.load_cb_event_rows(
            event_type="cb_call",
            ts_codes=ts_codes,
            end_date=trade_date,
        )
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            ts_code = str(row.get("ts_code") or row.get("bond_code") or row.get("code") or "").strip()
            if not ts_code or ts_code in result:
                continue
            result[ts_code] = self._parse_cb_call_event(trade_date=trade_date, row=row)
        return result

    def _parse_cb_call_event(
        self,
        *,
        trade_date: str,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        trade_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
        call_type = str(_pick(row, "call_type", default="")).strip()
        is_call = str(_pick(row, "is_call", default="")).strip()
        countdown_active = False
        risk_active = False
        if "强赎" in call_type and "不强赎" not in is_call:
            countdown_active = any(keyword in is_call for keyword in ("满足强赎", "提示强赎", "实施强赎", "强赎"))
            risk_active = any(keyword in is_call for keyword in ("已满足强赎条件", "公告实施强赎", "实施强赎"))

        remaining_candidates: list[int] = []
        for field_name in ("call_reg_date", "call_date", "payment_date"):
            value = str(_pick(row, field_name, default="")).strip()
            if not value:
                continue
            try:
                target_dt = datetime.strptime(_to_ymd(value), "%Y-%m-%d").date()
            except ValueError:
                continue
            delta = (target_dt - trade_dt).days
            if delta >= 0:
                remaining_candidates.append(delta)

        redeem_remain_days: int | None = min(remaining_candidates) if remaining_candidates else None
        if countdown_active and redeem_remain_days is None:
            # Tushare announces “已满足/提示/实施强赎”时，优先按高风险 0 天处理。
            redeem_remain_days = 0

        return {
            "call_type": call_type,
            "is_call": is_call,
            "ann_date": _to_ymd(_pick(row, "ann_date")) if _pick(row, "ann_date") else None,
            "redeem_remain_days": redeem_remain_days,
            "is_ransom_flag": "True" if risk_active else "False",
        }

    @staticmethod
    def _is_listed_on_trade_date(*, basic: dict[str, Any], trade_date: date) -> bool:
        list_date = str(_pick(basic, "list_date", default="")).strip()
        delist_date = str(_pick(basic, "delist_date", default="")).strip()
        remain_size = _safe_float(_pick(basic, "remain_size"), 0.0)
        if list_date:
            try:
                if datetime.strptime(_to_ymd(list_date), "%Y-%m-%d").date() > trade_date:
                    return False
            except ValueError:
                pass
        if delist_date:
            try:
                if datetime.strptime(_to_ymd(delist_date), "%Y-%m-%d").date() <= trade_date:
                    return False
            except ValueError:
                pass
        if remain_size <= 0:
            return False
        return True

    def _build_factor_and_snapshot_rows(
        self,
        *,
        trade_date: str,
        cb_daily_rows: list[dict[str, Any]],
        cb_basic_map: dict[str, dict[str, Any]],
        stock_daily_map: dict[str, dict[str, Any]],
        stock_basic_map: dict[str, dict[str, Any]],
        last_valid_price_map: dict[str, float] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        factor_rows: list[dict[str, Any]] = []
        snapshot_rows: list[dict[str, Any]] = []
        trade_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
        price_cache = last_valid_price_map if last_valid_price_map is not None else {}
        cb_call_map = self._load_cb_call_map(
            trade_date=trade_date,
            ts_codes=[
                str(_pick(row, "ts_code", "bond_code", "code", default="")).strip()
                for row in cb_daily_rows
                if str(_pick(row, "ts_code", "bond_code", "code", default="")).strip()
            ],
        )

        missing_prev_codes: list[str] = []
        for cb_row in cb_daily_rows:
            ts_code = str(_pick(cb_row, "ts_code", "bond_code", "code", default="")).strip()
            if not ts_code:
                continue
            code6 = _ts_code_to_code6(ts_code)
            if not code6 or code6 in price_cache:
                continue
            close_price = _safe_float(_pick(cb_row, "close", "price"), 0.0)
            pre_close_price = _safe_float(_pick(cb_row, "pre_close", "preclose"), 0.0)
            if close_price <= 0 and pre_close_price <= 0:
                missing_prev_codes.append(code6)
        if missing_prev_codes:
            previous = self._store.load_latest_valid_prices(
                before_trade_date=trade_date,
                bond_ids=missing_prev_codes,
            )
            price_cache.update(previous)

        for cb_row in cb_daily_rows:
            ts_code = str(_pick(cb_row, "ts_code", "bond_code", "code", default="")).strip()
            if not ts_code:
                continue
            code6 = _ts_code_to_code6(ts_code)
            basic = cb_basic_map.get(ts_code, {})
            stock_ts_code = _to_stock_ts_code(str(_pick(basic, "stk_code", default="")), bond_ts_code=ts_code)
            stock_daily = stock_daily_map.get(stock_ts_code, {})
            stock_basic = stock_basic_map.get(stock_ts_code, {})
            call_info = cb_call_map.get(ts_code, {})

            close_price = _safe_float(_pick(cb_row, "close", "price"), 0.0)
            pre_close_price = _safe_float(_pick(cb_row, "pre_close", "preclose"), 0.0)
            price, price_fill_source = self._normalize_price(
                close_price=close_price,
                pre_close_price=pre_close_price,
                previous_valid_price=price_cache.get(code6),
            )
            if price > 0:
                price_cache[code6] = price
            premium_rate = _safe_float(_pick(cb_row, "bond_prem", "premium_rt", "premium_rate"), 0.0)
            pure_bond_value = _safe_float(_pick(cb_row, "bond_value", "pure_bond_value"), 0.0)
            cb_to_pb = price / pure_bond_value if pure_bond_value > 0 else 1.0

            market_cap = _safe_float(_pick(stock_basic, "total_mv", "circ_mv"), 0.0)
            if market_cap > 0:
                market_cap = market_cap / 10000.0  # 万元 -> 亿元
            stock_pb = _safe_float(_pick(stock_basic, "pb", "pb_new"), 1.5)
            stock_pct_chg = _safe_float(_pick(stock_daily, "pct_chg"), 0.0)
            stock_stdevry = max(10.0, min(60.0, abs(stock_pct_chg) * 1.5 + 20.0))

            issue_size = _safe_float(_pick(basic, "issue_size", "actual_issue_scale"), 10.0)
            remain_amount = issue_size if issue_size > 0 else 10.0

            maturity_text = str(_pick(basic, "maturity_date", "maturity_dt", default="")).strip()
            issue_date = _to_ymd(_pick(basic, "list_date", "issue_date", default=trade_date))
            remain_years, remain_distance, return_distance = self._derive_maturity_fields(
                trade_dt=trade_dt,
                maturity_text=maturity_text,
            )

            factor_row = {
                "trade_date": trade_date,
                "cb_code": code6,
                "cb_name": str(_pick(basic, "bond_short_name", "bond_name", default=ts_code)),
                "stock_ts_code": stock_ts_code,
                "price": round(price, 4),
                "price_fill_source": price_fill_source,
                "premium_rate": round(premium_rate, 4),
                "cb_to_pb": round(cb_to_pb, 4),
                "pb": round(stock_pb, 4),
                "stock_stdevry": round(stock_stdevry, 4),
                "remain_amount": round(remain_amount, 4),
                "market_cap": round(market_cap, 4),
                "issue_date": issue_date,
                "date_return_distance": return_distance,
                "date_remain_distance": remain_distance,
                "remain_years": round(remain_years, 4) if remain_years is not None else None,
                "is_unlist": "N",
                "last_is_unlist": "N",
                "is_ransom_flag": str(call_info.get("is_ransom_flag", "False")),
                "is_call": str(call_info.get("is_call", "")).strip(),
                "redeem_remain_days": call_info.get("redeem_remain_days"),
                "new_style": round(pure_bond_value, 4),
                "source": "tushare.pro",
            }
            factor_rows.append(factor_row)

            # Keep crawler-compatible schema for phase_a backtest.
            snapshot_rows.append(
                {
                    **factor_row,
                }
            )

        return factor_rows, snapshot_rows

    @staticmethod
    def _normalize_price(
        *,
        close_price: float,
        pre_close_price: float,
        previous_valid_price: float | None,
    ) -> tuple[float, str]:
        if close_price > 0:
            return close_price, "close"
        if pre_close_price > 0:
            return pre_close_price, "pre_close"
        if previous_valid_price is not None and previous_valid_price > 0:
            return previous_valid_price, "prev_valid"
        return 0.0, "missing"

    @staticmethod
    def _derive_maturity_fields(*, trade_dt: date, maturity_text: str) -> tuple[float | None, str, str]:
        if not maturity_text:
            return None, "0天", "未到"
        try:
            maturity_dt = datetime.strptime(_to_ymd(maturity_text), "%Y-%m-%d").date()
        except ValueError:
            return None, "0天", "未到"
        delta_days = (maturity_dt - trade_dt).days
        years = delta_days / 365.0
        if delta_days <= 0:
            return 0.0, "0天", "回售内"
        if years <= 2.0:
            return years, f"{delta_days}天", "回售内"
        return years, f"{years:.2f}年", "未到"

    def _collect_stock_codes(
        self,
        cb_daily_rows: list[dict[str, Any]],
        cb_basic_map: dict[str, dict[str, Any]],
    ) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for row in cb_daily_rows:
            ts_code = str(_pick(row, "ts_code", "bond_code", "code", default="")).strip()
            if not ts_code:
                continue
            basic = cb_basic_map.get(ts_code, {})
            stock_ts_code = _to_stock_ts_code(str(_pick(basic, "stk_code", default="")), bond_ts_code=ts_code)
            if not stock_ts_code or stock_ts_code in seen:
                continue
            seen.add(stock_ts_code)
            results.append(stock_ts_code)
        return results

    @staticmethod
    def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame is None or frame.empty:
            return []
        clean = frame.where(pd.notnull(frame), None)
        return [dict(item) for item in clean.to_dict(orient="records")]

    @staticmethod
    def _query_optional_rows(
        *,
        client: _TushareClient,
        api_name: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        try:
            return CbTushareService._rows(client.query(api_name, **params))
        except Exception:
            return []

    @staticmethod
    def _chunk(values: list[str], size: int) -> list[list[str]]:
        if size <= 0:
            return [values]
        return [values[idx : idx + size] for idx in range(0, len(values), size)]

    @staticmethod
    def _fallback_trade_days(start: date, end: date) -> list[str]:
        days: list[str] = []
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:
                days.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return days

    @staticmethod
    def _load_token() -> str:
        from os import getenv

        local = CbTushareService._load_local_env_map()

        token = str(getenv("TUSHARE_TOKEN", "")).strip()
        if token:
            return token
        token = str(local.get("TUSHARE_TOKEN", "")).strip()
        if token:
            return token
        token = str(getenv("TUSHARE_PRO_TOKEN", "")).strip()
        if token:
            return token
        token = str(local.get("TUSHARE_PRO_TOKEN", "")).strip()
        if token:
            return token
        raise RuntimeError("TUSHARE token is empty. Please set TUSHARE_TOKEN (or TUSHARE_PRO_TOKEN).")

    @staticmethod
    def _load_http_url() -> str:
        from os import getenv

        local = CbTushareService._load_local_env_map()
        value = str(getenv("TUSHARE_HTTP_URL", "")).strip()
        if value:
            return value
        value = str(local.get("TUSHARE_HTTP_URL", "")).strip()
        if value:
            return value
        return "http://lianghua.nanyangqiankun.top"

    @staticmethod
    def _candidate_http_urls() -> list[str]:
        preferred = CbTushareService._load_http_url()
        candidates = [
            preferred,
            "https://api.tushare.pro",
            "http://api.tushare.pro",
            "https://api.waditu.com",
            "http://api.waditu.com",
        ]
        unique: list[str] = []
        seen: set[str] = set()
        for raw in candidates:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            unique.append(value)
        return unique

    @staticmethod
    def _load_local_env_map() -> dict[str, str]:
        # Optional local env file: project root /.env.tushare.local
        project_root = Path(__file__).resolve().parents[3]
        env_file = project_root / ".env.tushare.local"
        if not env_file.exists():
            return {}
        result: dict[str, str] = {}
        pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$")
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = pattern.match(line)
            if not match:
                continue
            key = match.group(1)
            value = match.group(2).strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            result[key] = value
        return result

    @staticmethod
    def _auth_error_message(message: str) -> bool:
        text = str(message or "")
        if "无效的 token" in text:
            return True
        if "token不对" in text:
            return True
        return False
