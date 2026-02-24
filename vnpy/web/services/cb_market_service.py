from __future__ import annotations

import os
from datetime import datetime
from math import ceil

import requests

from vnpy.web.adapters import CrawlerPhaseABacktestAdapter
from vnpy.web.schemas import BondMarketResponse, BondMarketRow

EM_BOND_LIST_URL = "https://16.push2.eastmoney.com/api/qt/clist/get"
EM_BOND_META_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_STOCK_BATCH_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EM_TIMEOUT = 8
EM_PAGE_SIZE = 100
EM_STOCK_BATCH_SIZE = 120


def _to_float(value: object) -> float | None:
    if value in (None, "-", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(value: object) -> str | None:
    if value in (None, "", "-"):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _to_code6(value: object) -> str:
    text = _safe_text(value) or ""
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text
    return digits.zfill(6)


def _parse_year_text(value: object) -> float | None:
    text = _safe_text(value)
    if not text:
        return None
    text = text.replace("年", "").strip()
    return _to_float(text)


def _now_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _to_date8(value: object) -> str | None:
    if value in (None, "-", ""):
        return None
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def _to_date_str(value: object) -> str | None:
    if value in (None, "-", ""):
        return None
    raw = str(value)
    if len(raw) >= 10:
        return raw[:10]
    return None


def _calc_remain_years(maturity_date: str | None) -> float | None:
    if not maturity_date:
        return None
    try:
        maturity = datetime.strptime(maturity_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        diff = (maturity - today).days
        return round(diff / 365, 2)
    except ValueError:
        return None


def _estimate_expiry_ytm(
    price: float,
    maturity_redeem_price: float | None,
    remain_years: float | None,
) -> float | None:
    if not maturity_redeem_price or not remain_years:
        return None
    if price <= 0 or remain_years <= 0:
        return None
    try:
        return round((((maturity_redeem_price / price) ** (1 / remain_years)) - 1) * 100, 2)
    except (ValueError, ZeroDivisionError):
        return None


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[idx : idx + size] for idx in range(0, len(values), size)]


class CbMarketService:
    """Convertible-bond market data service with Eastmoney realtime source."""

    def __init__(self) -> None:
        self._session = requests.Session()
        # In many desktop/dev environments HTTP(S)_PROXY points to an unavailable local proxy.
        # Disable implicit proxy usage by default; can be re-enabled via env when needed.
        self._session.trust_env = os.getenv("VNPY_CB_HTTP_TRUST_ENV", "0") == "1"

    def _http_get(self, url: str, *, params: dict[str, str]) -> requests.Response:
        return self._session.get(url, params=params, timeout=EM_TIMEOUT)

    def list_bonds(self, min_volume_wan: float = 0.0) -> BondMarketResponse:
        snapshot_time = _now_time()
        allow_fallback = os.getenv("VNPY_CB_ALLOW_FALLBACK_MOCK", "0") == "1"

        try:
            raw_rows = self._fetch_realtime_rows()
            rating_map = self._fetch_rating_map()
            stock_metrics_map = self._fetch_stock_metrics_map(raw_rows)
            rows = self._normalize_rows(
                raw_rows,
                rating_map,
                stock_metrics_map,
                snapshot_time,
                min_volume_wan,
            )
            if rows:
                return BondMarketResponse(
                    items=rows,
                    total=len(rows),
                    source="eastmoney.push2 + eastmoney.datacenter",
                    snapshot_time=snapshot_time,
                    fallback_used=False,
                )
            raise RuntimeError("no bond rows returned from eastmoney")
        except Exception as exc:  # noqa: BLE001
            snapshot_rows, snapshot_date = self._load_rows_from_local_snapshot(
                snapshot_time=snapshot_time,
                min_volume_wan=min_volume_wan,
            )
            if snapshot_rows:
                return BondMarketResponse(
                    items=snapshot_rows,
                    total=len(snapshot_rows),
                    source=f"snapshot.local({snapshot_date})" if snapshot_date else "snapshot.local",
                    snapshot_time=snapshot_time,
                    fallback_used=True,
                    fallback_reason=f"eastmoney unavailable: {str(exc)[:160]}",
                )

            if not allow_fallback:
                raise RuntimeError(f"failed to load realtime bonds: {exc}") from exc
            fallback_rows = self._fallback_rows(snapshot_time)
            return BondMarketResponse(
                items=fallback_rows,
                total=len(fallback_rows),
                source="fallback.mock",
                snapshot_time=snapshot_time,
                fallback_used=True,
                fallback_reason=str(exc),
            )

    def _load_rows_from_local_snapshot(
        self,
        *,
        snapshot_time: str,
        min_volume_wan: float,
    ) -> tuple[list[BondMarketRow], str | None]:
        try:
            adapter = CrawlerPhaseABacktestAdapter()
            module = adapter._load_module()
            dataset = module.load_market_data(adapter.data_dir)
            if not dataset:
                return [], None

            latest_date, frame = sorted(dataset, key=lambda item: item[0])[-1]
            rows: list[BondMarketRow] = []

            for _, row in frame.iterrows():
                price = _to_float(row.get("price"))
                if price is None or price <= 0:
                    continue

                amount_wan = _to_float(row.get("market_cap"))
                if amount_wan is not None and amount_wan < min_volume_wan:
                    continue

                premium = _to_float(row.get("premium_rate")) or 0.0
                convert_value = price / (1 + premium / 100) if premium > -99 else None
                remain_years = _parse_year_text(row.get("date_remain_distance"))
                remain_scale_yi = _to_float(row.get("remain_amount"))
                expiry_ytm_pre_tax = _to_float(row.get("rate_expire_aftertax")) or _to_float(row.get("rate_expire"))
                put_ytm = _to_float(row.get("rate_return"))
                stock_market = (_safe_text(row.get("market")) or "").lower()

                rows.append(
                    BondMarketRow(
                        bond_id=_to_code6(row.get("cb_code")),
                        bond_name=_safe_text(row.get("cb_name")) or "",
                        price=round(price, 3),
                        increase_rt=round(_to_float(row.get("cb_percent")) or 0.0, 2),
                        stock_id=f"{stock_market}{_to_code6(row.get('stock_code'))}" if stock_market else _to_code6(row.get("stock_code")),
                        stock_name=_safe_text(row.get("stock_name")) or "",
                        stock_price=_to_float(row.get("stock_price")),
                        stock_increase_rt=_to_float(row.get("stock_percent")),
                        stock_pb=_to_float(row.get("pb")),
                        convert_price=_to_float(row.get("convert_stock_price")),
                        pure_bond_value=_to_float(row.get("new_style")),
                        premium_rt=round(premium, 2),
                        convert_value=round(convert_value, 3) if convert_value is not None else 0.0,
                        dblow=round(price + premium, 3),
                        option_value=_to_float(row.get("old_style")),
                        stock_volatility=_to_float(row.get("stock_stdevry")),
                        put_trigger_price=None,
                        redeem_trigger_price=None,
                        float_mv_ratio=_to_float(row.get("remain_to_cap")),
                        fund_holding_ratio=None,
                        maturity_date=None,
                        remain_years=remain_years,
                        remain_scale_yi=remain_scale_yi,
                        amount_wan=round(amount_wan, 1) if amount_wan is not None else None,
                        turnover_rt=None,
                        expiry_ytm_pre_tax=expiry_ytm_pre_tax,
                        put_ytm=put_ytm,
                        volume_wan=round(amount_wan, 1) if amount_wan is not None else 0.0,
                        issue_scale_yi=remain_scale_yi,
                        rating=_safe_text(row.get("rating")),
                        listed_date=_to_date_str(row.get("issue_date")),
                        convert_start_date=None,
                        subscribe_date=None,
                        source="snapshot.local",
                        update_time=snapshot_time,
                    )
                )

            rows.sort(key=lambda item: item.amount_wan or 0.0, reverse=True)
            return rows, latest_date
        except Exception:  # noqa: BLE001
            return [], None

    def _fetch_realtime_rows(self) -> list[dict]:
        params = {
            "pn": "1",
            "pz": str(EM_PAGE_SIZE),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "b:MK0354",
            "fields": (
                "f1,f2,f3,f5,f6,f7,f8,f12,f13,f14,f26,f152,"
                "f227,f228,f229,f230,f231,f232,f233,f234,"
                "f235,f236,f237,f238,f239,f240,f241,f242,f243"
            ),
        }

        first = self._http_get(EM_BOND_LIST_URL, params=params)
        first.raise_for_status()
        first_json = first.json()
        first_data = first_json.get("data") or {}
        total = int(first_data.get("total") or 0)
        rows: list[dict] = list(first_data.get("diff") or [])
        actual_page_size = max(1, len(rows))

        if total <= actual_page_size:
            return rows

        pages = ceil(total / actual_page_size)
        for page in range(2, pages + 1):
            params["pn"] = str(page)
            resp = self._http_get(EM_BOND_LIST_URL, params=params)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            rows.extend(data.get("diff") or [])
        return rows

    def _fetch_rating_map(self) -> dict[str, dict]:
        params = {
            "reportName": "RPT_BOND_CB_LIST",
            "columns": "SECURITY_CODE,RATING,ACTUAL_ISSUE_SCALE,EXPIRE_DATE,LISTING_DATE,TRANSFER_START_DATE,PUBLIC_START_DATE",
            "pageNumber": "1",
            "pageSize": "500",
            "sortColumns": "SECURITY_CODE",
            "sortTypes": "1",
            "source": "WEB",
            "client": "WEB",
        }

        resp = self._http_get(EM_BOND_META_URL, params=params)
        resp.raise_for_status()
        payload = resp.json().get("result") or {}
        pages = int(payload.get("pages") or 1)
        rows = list(payload.get("data") or [])

        for page in range(2, pages + 1):
            params["pageNumber"] = str(page)
            page_resp = self._http_get(EM_BOND_META_URL, params=params)
            page_resp.raise_for_status()
            page_rows = (page_resp.json().get("result") or {}).get("data") or []
            rows.extend(page_rows)

        return {
            str(item.get("SECURITY_CODE")): item
            for item in rows
            if item.get("SECURITY_CODE")
        }

    def _fetch_stock_metrics_map(self, raw_rows: list[dict]) -> dict[str, dict]:
        secids: list[str] = []
        for row in raw_rows:
            market = row.get("f233")
            stock_code = row.get("f232")
            if market in (0, 1) and stock_code:
                secids.append(f"{market}.{stock_code}")

        unique_secids = sorted(set(secids))
        if not unique_secids:
            return {}

        metrics_map: dict[str, dict] = {}
        for secid_chunk in _chunks(unique_secids, EM_STOCK_BATCH_SIZE):
            params = {
                "fltt": "2",
                "invt": "2",
                "secids": ",".join(secid_chunk),
                "fields": "f2,f3,f7,f8,f12,f13,f14,f20,f21,f23",
            }
            resp = self._http_get(EM_STOCK_BATCH_URL, params=params)
            resp.raise_for_status()
            diff = ((resp.json().get("data") or {}).get("diff")) or []
            for item in diff:
                item_market = item.get("f13")
                item_code = item.get("f12")
                if item_market in (0, 1) and item_code:
                    metrics_map[f"{item_market}.{item_code}"] = item

        return metrics_map

    def _normalize_rows(
        self,
        raw_rows: list[dict],
        rating_map: dict[str, dict],
        stock_metrics_map: dict[str, dict],
        snapshot_time: str,
        min_volume_wan: float,
    ) -> list[BondMarketRow]:
        items: list[BondMarketRow] = []
        for row in raw_rows:
            price = _to_float(row.get("f2"))
            if price is None or price <= 0:
                continue

            amount = _to_float(row.get("f6")) or 0.0
            amount_wan = amount / 10000
            if amount_wan < min_volume_wan:
                continue

            premium = _to_float(row.get("f237")) or 0.0
            convert_value = _to_float(row.get("f236"))
            if convert_value is None and premium > -100:
                convert_value = price / (1 + premium / 100)
            if convert_value is None:
                convert_value = 0.0

            code = str(row.get("f12") or "")
            bond_meta = rating_map.get(code, {})
            stock_market = row.get("f233")
            stock_code_raw = row.get("f232")
            stock_secid = f"{stock_market}.{stock_code_raw}" if stock_market in (0, 1) and stock_code_raw else ""
            stock_metrics = stock_metrics_map.get(stock_secid, {})
            issue_scale = _to_float(bond_meta.get("ACTUAL_ISSUE_SCALE"))
            rating = bond_meta.get("RATING")
            maturity_date = _to_date_str(bond_meta.get("EXPIRE_DATE"))
            remain_years = _calc_remain_years(maturity_date)
            maturity_redeem_price = _to_float(row.get("f241"))
            expiry_ytm_pre_tax = _estimate_expiry_ytm(price, maturity_redeem_price, remain_years)
            listed_date = _to_date8(row.get("f26")) or _to_date_str(bond_meta.get("LISTING_DATE"))
            convert_start_date = _to_date8(row.get("f242")) or _to_date_str(bond_meta.get("TRANSFER_START_DATE"))
            subscribe_date = _to_date8(row.get("f243")) or _to_date_str(bond_meta.get("PUBLIC_START_DATE"))
            stock_float_cap = _to_float(stock_metrics.get("f21"))
            float_mv_ratio = None
            if issue_scale and stock_float_cap and stock_float_cap > 0:
                float_mv_ratio = round((issue_scale * 100000000 / stock_float_cap) * 100, 2)

            items.append(
                BondMarketRow(
                    bond_id=code,
                    bond_name=str(row.get("f14") or ""),
                    price=round(price, 3),
                    increase_rt=round(_to_float(row.get("f3")) or 0.0, 2),
                    stock_id=str(row.get("f232") or ""),
                    stock_name=str(row.get("f234") or ""),
                    stock_price=_to_float(row.get("f229")) or _to_float(stock_metrics.get("f2")),
                    stock_increase_rt=_to_float(row.get("f230")) or _to_float(stock_metrics.get("f3")),
                    stock_pb=_to_float(stock_metrics.get("f23")),
                    convert_price=_to_float(row.get("f235")),
                    pure_bond_value=_to_float(row.get("f227")),
                    premium_rt=round(premium, 2),
                    convert_value=round(convert_value, 3),
                    dblow=round(price + premium, 3),
                    option_value=_to_float(row.get("f238")),
                    stock_volatility=_to_float(stock_metrics.get("f7")),
                    put_trigger_price=_to_float(row.get("f239")),
                    redeem_trigger_price=_to_float(row.get("f240")),
                    float_mv_ratio=float_mv_ratio,
                    fund_holding_ratio=None,
                    maturity_date=maturity_date,
                    remain_years=remain_years,
                    remain_scale_yi=issue_scale,
                    amount_wan=round(amount_wan, 1),
                    turnover_rt=_to_float(row.get("f8")),
                    expiry_ytm_pre_tax=expiry_ytm_pre_tax,
                    put_ytm=None,
                    volume_wan=round(amount_wan, 1),
                    issue_scale_yi=issue_scale,
                    rating=rating,
                    listed_date=listed_date,
                    convert_start_date=convert_start_date,
                    subscribe_date=subscribe_date,
                    source="eastmoney.push2",
                    update_time=snapshot_time,
                )
            )

        items.sort(key=lambda x: x.amount_wan or 0.0, reverse=True)
        return items

    @staticmethod
    def _fallback_rows(snapshot_time: str) -> list[BondMarketRow]:
        return [
            BondMarketRow(
                bond_id="113063",
                bond_name="赛轮转债",
                price=128.45,
                increase_rt=0.82,
                stock_id="601058",
                stock_name="赛轮轮胎",
                stock_price=11.68,
                stock_increase_rt=0.46,
                stock_pb=1.78,
                convert_price=10.40,
                pure_bond_value=98.81,
                premium_rt=14.32,
                convert_value=112.36,
                dblow=142.77,
                option_value=13.55,
                stock_volatility=None,
                put_trigger_price=8.26,
                redeem_trigger_price=15.34,
                float_mv_ratio=None,
                fund_holding_ratio=None,
                maturity_date="2028-11-01",
                remain_years=2.69,
                remain_scale_yi=19.86,
                amount_wan=32688.2,
                turnover_rt=12.7,
                expiry_ytm_pre_tax=5.9,
                put_ytm=None,
                volume_wan=32688.2,
                issue_scale_yi=19.86,
                rating="AA",
                listed_date="2022-11-24",
                convert_start_date="2023-05-08",
                subscribe_date="2022-11-02",
                source="fallback.mock",
                update_time=snapshot_time,
            ),
            BondMarketRow(
                bond_id="123107",
                bond_name="温氏转债",
                price=121.12,
                increase_rt=-0.15,
                stock_id="300498",
                stock_name="温氏股份",
                stock_price=17.82,
                stock_increase_rt=0.57,
                stock_pb=3.12,
                convert_price=34.60,
                pure_bond_value=104.31,
                premium_rt=11.48,
                convert_value=108.65,
                dblow=132.60,
                option_value=17.91,
                stock_volatility=None,
                put_trigger_price=24.13,
                redeem_trigger_price=42.88,
                float_mv_ratio=None,
                fund_holding_ratio=None,
                maturity_date="2028-10-08",
                remain_years=2.62,
                remain_scale_yi=81.62,
                amount_wan=15891.6,
                turnover_rt=5.1,
                expiry_ytm_pre_tax=4.7,
                put_ytm=None,
                volume_wan=15891.6,
                issue_scale_yi=81.62,
                rating="AAA",
                listed_date="2021-11-01",
                convert_start_date="2022-04-08",
                subscribe_date="2021-10-08",
                source="fallback.mock",
                update_time=snapshot_time,
            ),
        ]
