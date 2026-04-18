from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from vnpy.web.services.cb_tushare_service import CbTushareService, _TushareClient
from vnpy.web.tenx_hunter.config import Settings
from vnpy.web.tenx_hunter.universe import ResolvedUniverse


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_iso_date(value: Any) -> str | None:
    text = _safe_str(value)
    if text is None:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    return text


def _to_ts_date(value: str) -> str:
    return value.replace("-", "")


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value in (None, ""):
            continue
        return value
    return None


def _query(client: _TushareClient, api_name: str, **params: Any) -> pd.DataFrame:
    frame = client.query(api_name, **params)
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame.copy()


def _load_trade_days(client: _TushareClient, start_date: str, end_date: str) -> list[str]:
    frame = _query(
        client,
        "trade_cal",
        exchange="SSE",
        start_date=_to_ts_date(start_date),
        end_date=_to_ts_date(end_date),
        is_open="1",
    )
    if frame.empty:
        return [end_date]
    return sorted(filter(None, (_to_iso_date(item) for item in frame["cal_date"].tolist())))


def _select_latest_row(frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty:
        return None
    ordered = frame.copy()
    sort_keys = [key for key in ("end_date", "ann_date", "f_ann_date", "trade_date") if key in ordered.columns]
    if sort_keys:
        ordered = ordered.sort_values(sort_keys, ascending=False)
    row = ordered.iloc[0]
    return {key: row[key] for key in ordered.columns}


def _build_security_rows(stock_basic: pd.DataFrame, market: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in stock_basic.iterrows():
        symbol = _safe_str(row.get("ts_code"))
        if symbol is None:
            continue
        rows.append(
            {
                "market": market,
                "symbol": symbol,
                "company_name": _coalesce(_safe_str(row.get("name")), symbol),
                "exchange_name": _safe_str(row.get("exchange")),
                "cik": None,
                "currency": "CNY",
                "listing_status": _safe_str(row.get("list_status")) or "L",
                "sector": _coalesce(_safe_str(row.get("industry")), _safe_str(row.get("market"))),
                "industry": _safe_str(row.get("industry")),
                "listed_date": _to_iso_date(row.get("list_date")),
                "raw_payload": row.to_dict(),
            }
        )
    return rows


def _bucket_theme_map(universe: ResolvedUniverse) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for bucket in universe.buckets:
        theme_id = bucket.slug.replace("-", "_")
        for symbol in bucket.symbols:
            mapping.setdefault(symbol, []).append(theme_id)
    return mapping


def _build_security_theme_rows(
    *,
    stock_basic: pd.DataFrame,
    universe: ResolvedUniverse,
) -> list[dict[str, str]]:
    bucket_map = _bucket_theme_map(universe)
    fallback_rules = {
        "半导体": "advanced_manufacturing",
        "元件": "ai_compute",
        "汽车": "ev_supply_chain",
        "医疗": "innovation_healthcare",
        "生物": "innovation_healthcare",
    }
    rows: list[dict[str, str]] = []
    for _, item in stock_basic.iterrows():
        symbol = _safe_str(item.get("ts_code"))
        if symbol is None:
            continue
        themes = set(bucket_map.get(symbol, []))
        industry = _safe_str(item.get("industry")) or ""
        for keyword, theme_id in fallback_rules.items():
            if keyword in industry:
                themes.add(theme_id)
        if not themes:
            themes.add("a_share_growth")
        for theme_id in sorted(themes):
            rows.append(
                {
                    "symbol": symbol,
                    "theme_id": theme_id,
                    "source_note": "tushare-industry+universe",
                }
            )
    return rows


def _build_price_rows(
    *,
    market: str,
    symbols: set[str],
    daily_by_date: dict[str, pd.DataFrame],
    daily_basic_by_date: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade_date, daily_frame in sorted(daily_by_date.items()):
        if daily_frame.empty:
            continue
        basic_frame = daily_basic_by_date.get(trade_date, pd.DataFrame())
        basic_map = {
            _safe_str(item.get("ts_code")): item
            for item in basic_frame.to_dict("records")
            if _safe_str(item.get("ts_code"))
        }
        for item in daily_frame.to_dict("records"):
            symbol = _safe_str(item.get("ts_code"))
            if symbol is None or symbol not in symbols:
                continue
            basic = basic_map.get(symbol, {})
            rows.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": _safe_float(item.get("open")),
                    "high": _safe_float(item.get("high")),
                    "low": _safe_float(item.get("low")),
                    "close": _safe_float(item.get("close")),
                    "adj_close": _safe_float(item.get("close")),
                    "volume": _safe_float(item.get("vol")),
                    "currency": "CNY",
                    "market_status": "closed",
                    "source_event_time": f"{trade_date}T15:00:00Z",
                    "source_vendor": "tushare-stock",
                    "raw_payload": {
                        **item,
                        "pe_ttm": _safe_float(_coalesce(basic.get("pe_ttm"), basic.get("pe"))),
                        "pb": _safe_float(_coalesce(basic.get("pb"), basic.get("pb_new"))),
                        "turnover_rate": _safe_float(_coalesce(basic.get("turnover_rate"), basic.get("turnover_rate_f"))),
                        "total_mv": _safe_float(basic.get("total_mv")),
                        "circ_mv": _safe_float(basic.get("circ_mv")),
                    },
                }
            )
    return rows


def _build_financial_row(
    *,
    market: str,
    symbol: str,
    fina_indicator: dict[str, Any] | None,
    income: dict[str, Any] | None,
    balancesheet: dict[str, Any] | None,
    cashflow: dict[str, Any] | None,
) -> dict[str, Any] | None:
    source_row = fina_indicator or income or balancesheet or cashflow
    if source_row is None:
        return None

    end_date = _to_iso_date(_coalesce(
        (fina_indicator or {}).get("end_date"),
        (income or {}).get("end_date"),
        (balancesheet or {}).get("end_date"),
        (cashflow or {}).get("end_date"),
    ))
    if end_date is None:
        return None

    revenue = _safe_float(_coalesce((income or {}).get("revenue"), (income or {}).get("total_revenue")))
    net_profit = _safe_float(_coalesce((income or {}).get("n_income_attr_p"), (income or {}).get("n_income")))
    cfo = _safe_float(_coalesce((cashflow or {}).get("n_cashflow_act"), (cashflow or {}).get("n_cash_flows_fnc_act")))
    cash = _safe_float(_coalesce((balancesheet or {}).get("money_cap"), (balancesheet or {}).get("total_cur_assets")))
    debt = _safe_float(_coalesce((balancesheet or {}).get("total_liab"), (balancesheet or {}).get("st_borr")))
    shares = _safe_float(_coalesce((balancesheet or {}).get("total_share"), (fina_indicator or {}).get("total_share")))

    cfo_to_np = None
    if net_profit not in (None, 0) and cfo is not None:
        cfo_to_np = cfo / net_profit

    return {
        "market": market,
        "symbol": symbol,
        "report_period": end_date,
        "fiscal_quarter": _coalesce(_safe_str((source_row or {}).get("end_type")), "Q4"),
        "fiscal_year": int(end_date[:4]),
        "period_type": "annual" if end_date.endswith("-12-31") else "quarterly",
        "filed_date": _to_iso_date(_coalesce(
            (fina_indicator or {}).get("ann_date"),
            (income or {}).get("ann_date"),
            (balancesheet or {}).get("ann_date"),
            (cashflow or {}).get("ann_date"),
        )),
        "revenue": revenue,
        "gross_margin": _safe_float((fina_indicator or {}).get("grossprofit_margin")),
        "op_margin": _safe_float((fina_indicator or {}).get("op_of_gr")),
        "fcf_margin": (cfo / revenue) if cfo is not None and revenue not in (None, 0) else None,
        "cash": cash,
        "debt": debt,
        "shares_outstanding": shares,
        "revenue_yoy": _safe_float(_coalesce((fina_indicator or {}).get("tr_yoy"), (fina_indicator or {}).get("or_yoy"))),
        "netprofit_yoy": _safe_float((fina_indicator or {}).get("netprofit_yoy")),
        "cfo_to_np": cfo_to_np,
        "rd_ratio_ttm": _safe_float(_coalesce((fina_indicator or {}).get("rd_exp"), (fina_indicator or {}).get("rd_exp_ratio"))),
        "source_filing_id": None,
        "form_type": "tushare-financial",
        "currency": "CNY",
        "data_quality_flag": "parsed",
        "restatement_flag": False,
        "source_vendor": "tushare-stock",
        "raw_payload": {
            "fina_indicator": fina_indicator or {},
            "income": income or {},
            "balancesheet": balancesheet or {},
            "cashflow": cashflow or {},
        },
    }


def build_cn_stock_bundle(settings: Settings) -> dict[str, Any]:
    market = "CN"
    universe = settings.market_universes["CN"]
    symbols = set(universe.symbols)
    client = _TushareClient(CbTushareService._load_token(), http_url=CbTushareService._load_http_url())

    stock_basic = _query(client, "stock_basic", exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,market,exchange,list_status,list_date")
    if not stock_basic.empty:
        stock_basic = stock_basic[stock_basic["ts_code"].isin(symbols)]

    trade_days = _load_trade_days(client, settings.price_start_date, settings.price_end_date)
    daily_by_date: dict[str, pd.DataFrame] = {}
    daily_basic_by_date: dict[str, pd.DataFrame] = {}
    for trade_date in trade_days:
        daily_frame = _query(client, "daily", trade_date=_to_ts_date(trade_date))
        if not daily_frame.empty:
            daily_by_date[trade_date] = daily_frame[daily_frame["ts_code"].isin(symbols)]
        basic_frame = _query(client, "daily_basic", trade_date=_to_ts_date(trade_date))
        if not basic_frame.empty:
            daily_basic_by_date[trade_date] = basic_frame[basic_frame["ts_code"].isin(symbols)]

    financials: list[dict[str, Any]] = []
    for symbol in sorted(symbols):
        fina_indicator = _select_latest_row(_query(client, "fina_indicator", ts_code=symbol))
        income = _select_latest_row(_query(client, "income", ts_code=symbol))
        balancesheet = _select_latest_row(_query(client, "balancesheet", ts_code=symbol))
        cashflow = _select_latest_row(_query(client, "cashflow", ts_code=symbol))
        row = _build_financial_row(
            market=market,
            symbol=symbol,
            fina_indicator=fina_indicator,
            income=income,
            balancesheet=balancesheet,
            cashflow=cashflow,
        )
        if row is not None:
            financials.append(row)

    return {
        "securities": _build_security_rows(stock_basic, market),
        "security_themes": _build_security_theme_rows(stock_basic=stock_basic, universe=universe),
        "prices": _build_price_rows(market=market, symbols=symbols, daily_by_date=daily_by_date, daily_basic_by_date=daily_basic_by_date),
        "financials": financials,
        "filings": [],
        "news": [],
        "watch_actions": [],
    }
