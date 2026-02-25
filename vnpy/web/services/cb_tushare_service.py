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

    def sync_range(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        mode: str = "manual",
        max_trade_days: int = 1500,
    ) -> dict[str, Any]:
        token = self._load_token()
        http_url = self._load_http_url()
        client = _TushareClient(token, http_url=http_url)

        today = date.today()
        end = end_date or today
        start = start_date or (end - timedelta(days=90))
        if start > end:
            start, end = end, start

        start_text = start.isoformat()
        end_text = end.isoformat()
        source = f"tushare.pro@{http_url}"

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
                "is_ransom_flag": "False",
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
