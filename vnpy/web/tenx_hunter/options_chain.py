from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
import re
from typing import Any

import requests
from psycopg.types.json import Jsonb

from .config import Settings, load_settings
from .db import connect


YAHOO_OPTIONS_URLS = (
    "https://query2.finance.yahoo.com/v7/finance/options/{symbol}",
    "https://query1.finance.yahoo.com/v7/finance/options/{symbol}",
)
YAHOO_COOKIE_URL = "https://fc.yahoo.com"
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
NASDAQ_OPTIONS_URL = "https://api.nasdaq.com/api/quote/{symbol}/option-chain"

OPTION_CHAIN_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS olap;

CREATE TABLE IF NOT EXISTS olap.us_option_chain_raw (
    trade_date DATE NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    expiration_date DATE NOT NULL,
    option_type TEXT NOT NULL,
    contract_symbol TEXT NOT NULL,
    strike NUMERIC(18,4),
    currency TEXT,
    last_price NUMERIC(18,4),
    bid NUMERIC(18,4),
    ask NUMERIC(18,4),
    price_change NUMERIC(18,4),
    percent_change NUMERIC(18,6),
    volume BIGINT,
    open_interest BIGINT,
    implied_volatility NUMERIC(18,8),
    in_the_money BOOLEAN,
    contract_size TEXT,
    last_trade_time TIMESTAMPTZ,
    underlying_price NUMERIC(18,4),
    source_event_time TIMESTAMPTZ NOT NULL,
    source_vendor TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, market, symbol, expiration_date, option_type, contract_symbol)
);

CREATE TABLE IF NOT EXISTS olap.security_option_chain_summary_daily (
    trade_date DATE NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    underlying_price NUMERIC(18,4),
    expiration_count INTEGER NOT NULL,
    contract_count INTEGER NOT NULL,
    nearest_expiration DATE,
    total_call_volume BIGINT NOT NULL,
    total_put_volume BIGINT NOT NULL,
    call_put_volume_ratio NUMERIC(18,6),
    total_call_open_interest BIGINT NOT NULL,
    total_put_open_interest BIGINT NOT NULL,
    call_put_open_interest_ratio NUMERIC(18,6),
    avg_implied_volatility NUMERIC(18,8),
    max_pain_strike NUMERIC(18,4),
    liquidity_score NUMERIC(10,2) NOT NULL,
    flow_score NUMERIC(10,2) NOT NULL,
    selection_score NUMERIC(10,2) NOT NULL,
    flow_sentiment TEXT NOT NULL,
    data_quality_flag TEXT NOT NULL,
    summary_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, market, symbol)
);

CREATE TABLE IF NOT EXISTS olap.option_target_recommendation_daily (
    trade_date DATE NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    workflow_id TEXT,
    deerflow_thread_id TEXT,
    option_selection_score NUMERIC(10,2),
    agent_status TEXT,
    wheel_status TEXT,
    leaps_status TEXT,
    result_json JSONB NOT NULL,
    market_context_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, market, symbol, batch_id)
);
"""


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "").replace("$", "")
        if value in {"", "--", "N/A"}:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if value in {"", "--", "N/A"}:
            return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _epoch_to_datetime(value: Any) -> datetime | None:
    seconds = _as_int(value)
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, timezone.utc)


def _epoch_to_date(value: Any) -> date | None:
    stamp = _epoch_to_datetime(value)
    return stamp.date() if stamp else None


def _payload_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return round(float(numerator) / float(denominator), 6) if denominator else None


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _request_yahoo_options(symbol: str, *, unix_expiration: int | None, user_agent: str, timeout: float) -> dict[str, Any]:
    last_error: Exception | None = None
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": user_agent or "TenX Hunter Options Chain contact@tenxhunter.local",
    }
    trust_env = os.getenv("OPTIONS_CHAIN_TRUST_ENV", "false").strip().lower() in {"1", "true", "yes", "on"}
    for template in YAHOO_OPTIONS_URLS:
        session = requests.Session()
        session.trust_env = trust_env
        crumb = _prepare_yahoo_session(session, headers=headers, timeout=timeout)
        params: dict[str, Any] = {}
        if unix_expiration is not None:
            params["date"] = unix_expiration
        if crumb:
            params["crumb"] = crumb
        try:
            response = session.get(
                template.format(symbol=symbol),
                params=params or None,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("optionChain", {}).get("result")
            if isinstance(result, list) and result:
                return payload
            error = payload.get("optionChain", {}).get("error") or "empty optionChain.result"
            raise RuntimeError(str(error))
        except Exception as exc:  # pragma: no cover - exercised through mocked request failures
            last_error = exc
    raise RuntimeError(f"Yahoo option chain request failed for {symbol}: {last_error}")


def _prepare_yahoo_session(session: requests.Session, *, headers: dict[str, str], timeout: float) -> str | None:
    try:
        session.get(YAHOO_COOKIE_URL, headers=headers, timeout=timeout)
        response = session.get(YAHOO_CRUMB_URL, headers=headers, timeout=timeout)
        if response.ok:
            crumb = response.text.strip()
            return crumb or None
    except requests.RequestException:
        return None
    return None


def _request_nasdaq_options(symbol: str, *, timeout: float) -> dict[str, Any]:
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.nasdaq.com",
        "Referer": f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}/option-chain",
        "User-Agent": (
            os.getenv("OPTIONS_CHAIN_USER_AGENT")
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    session = requests.Session()
    session.trust_env = os.getenv("OPTIONS_CHAIN_TRUST_ENV", "false").strip().lower() in {"1", "true", "yes", "on"}
    last_error: str | None = None
    for assetclass in ("stocks", "etf"):
        response = session.get(
            NASDAQ_OPTIONS_URL.format(symbol=symbol),
            params={"assetclass": assetclass, "limit": "9999"},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        rows = data.get("table", {}).get("rows") if isinstance(data.get("table"), dict) else None
        if isinstance(rows, list):
            payload["_tenx_assetclass"] = assetclass
            return payload
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        last_error = json.dumps(status.get("bCodeMessage") or status or payload, ensure_ascii=False, default=str)
    raise RuntimeError(f"Nasdaq option chain payload does not contain table rows: {last_error}")


def _parse_nasdaq_expiration(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _parse_nasdaq_underlying_price(payload: dict[str, Any]) -> float | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    last_trade = str(data.get("lastTrade") or "")
    match = re.search(r"\$([0-9,]+(?:\.[0-9]+)?)", last_trade)
    return _as_float(match.group(1)) if match else None


def _nasdaq_contract_symbol(symbol: str, row: dict[str, Any], option_type: str) -> str:
    url = str(row.get("drillDownURL") or "")
    match = re.search(r"/([a-z]+--\d{6})([cp])(\d+)$", url, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}{option_type[0]}{match.group(3)}".upper()
    expiry = str(row.get("expiryDate") or "").replace(" ", "").upper()
    strike = str(row.get("strike") or "").replace(".", "")
    return f"{symbol}-{expiry}-{option_type[0].upper()}-{strike}"


def _normalize_nasdaq_option_rows(
    *,
    symbol: str,
    market: str,
    trade_date: str,
    payload: dict[str, Any],
    source_event_time: datetime,
) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    table = data.get("table") if isinstance(data.get("table"), dict) else {}
    raw_rows = table.get("rows") or []
    underlying_price = _parse_nasdaq_underlying_price(payload)
    expiration_date: str | None = None
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        expiration_date = _parse_nasdaq_expiration(raw_row.get("expirygroup")) or expiration_date
        strike = _as_float(raw_row.get("strike"))
        if expiration_date is None or strike is None:
            continue
        for option_type, prefix in (("call", "c_"), ("put", "p_")):
            contract_symbol = _nasdaq_contract_symbol(symbol, raw_row, option_type)
            raw_contract = {
                "contractSymbol": contract_symbol,
                "expirationDate": expiration_date,
                "optionType": option_type,
                "strike": strike,
                "lastPrice": raw_row.get(f"{prefix}Last"),
                "change": raw_row.get(f"{prefix}Change"),
                "bid": raw_row.get(f"{prefix}Bid"),
                "ask": raw_row.get(f"{prefix}Ask"),
                "volume": raw_row.get(f"{prefix}Volume"),
                "openInterest": raw_row.get(f"{prefix}Openinterest"),
                "sourceRow": raw_row,
            }
            rows.append(
                {
                    "trade_date": trade_date,
                    "market": market,
                    "symbol": symbol,
                    "expiration_date": expiration_date,
                    "option_type": option_type,
                    "contract_symbol": contract_symbol,
                    "strike": strike,
                    "currency": "USD",
                    "last_price": _as_float(raw_row.get(f"{prefix}Last")),
                    "bid": _as_float(raw_row.get(f"{prefix}Bid")),
                    "ask": _as_float(raw_row.get(f"{prefix}Ask")),
                    "price_change": _as_float(raw_row.get(f"{prefix}Change")),
                    "percent_change": None,
                    "volume": _as_int(raw_row.get(f"{prefix}Volume")),
                    "open_interest": _as_int(raw_row.get(f"{prefix}Openinterest")),
                    "implied_volatility": None,
                    "in_the_money": None,
                    "contract_size": "REGULAR",
                    "last_trade_time": None,
                    "underlying_price": underlying_price,
                    "source_event_time": source_event_time,
                    "source_vendor": "nasdaq-option-chain",
                    "payload_hash": _payload_hash(raw_contract),
                    "raw_payload": raw_contract,
                }
            )
    return rows


def _extract_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("optionChain", {}).get("result")
    if not isinstance(result, list) or not result:
        raise ValueError("Yahoo option chain payload does not contain optionChain.result")
    first = result[0]
    if not isinstance(first, dict):
        raise ValueError("Yahoo option chain result must be an object")
    return first


def _normalize_option_rows(
    *,
    symbol: str,
    market: str,
    trade_date: str,
    result: dict[str, Any],
    source_event_time: datetime,
) -> list[dict[str, Any]]:
    quote = result.get("quote") if isinstance(result.get("quote"), dict) else {}
    underlying_price = _as_float(
        quote.get("regularMarketPrice")
        or quote.get("postMarketPrice")
        or quote.get("preMarketPrice")
        or quote.get("ask")
        or quote.get("bid")
    )
    currency = quote.get("currency")
    rows: list[dict[str, Any]] = []
    for option_bucket in result.get("options") or []:
        if not isinstance(option_bucket, dict):
            continue
        expiration = _epoch_to_date(option_bucket.get("expirationDate"))
        if expiration is None:
            continue
        for option_type, raw_key in (("call", "calls"), ("put", "puts")):
            for raw_contract in option_bucket.get(raw_key) or []:
                if not isinstance(raw_contract, dict):
                    continue
                contract_symbol = str(raw_contract.get("contractSymbol") or "").strip()
                if not contract_symbol:
                    continue
                rows.append(
                    {
                        "trade_date": trade_date,
                        "market": market,
                        "symbol": symbol,
                        "expiration_date": expiration.isoformat(),
                        "option_type": option_type,
                        "contract_symbol": contract_symbol,
                        "strike": _as_float(raw_contract.get("strike")),
                        "currency": raw_contract.get("currency") or currency,
                        "last_price": _as_float(raw_contract.get("lastPrice")),
                        "bid": _as_float(raw_contract.get("bid")),
                        "ask": _as_float(raw_contract.get("ask")),
                        "price_change": _as_float(raw_contract.get("change")),
                        "percent_change": _as_float(raw_contract.get("percentChange")),
                        "volume": _as_int(raw_contract.get("volume")),
                        "open_interest": _as_int(raw_contract.get("openInterest")),
                        "implied_volatility": _as_float(raw_contract.get("impliedVolatility")),
                        "in_the_money": raw_contract.get("inTheMoney"),
                        "contract_size": raw_contract.get("contractSize"),
                        "last_trade_time": _epoch_to_datetime(raw_contract.get("lastTradeDate")),
                        "underlying_price": underlying_price,
                        "source_event_time": source_event_time,
                        "source_vendor": "yahoo-finance-options",
                        "payload_hash": _payload_hash(raw_contract),
                        "raw_payload": raw_contract,
                    }
                )
    return rows


def fetch_latest_option_chain(
    symbol: str,
    *,
    market: str = "US",
    trade_date: str | None = None,
    expiration_limit: int | None = None,
    timeout: float | None = None,
    user_agent: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    symbol = symbol.strip().upper()
    market = market.strip().upper() or "US"
    if market != "US":
        return [], {
            "symbol": symbol,
            "market": market,
            "trade_date": trade_date or date.today().isoformat(),
            "data_quality_flag": "unsupported_market",
            "notes": ["Option chain automation currently supports US-listed Yahoo Finance symbols."],
        }

    requested_trade_date = trade_date or date.today().isoformat()
    limit = expiration_limit if expiration_limit is not None else int(os.getenv("OPTIONS_CHAIN_EXPIRATION_LIMIT", "4"))
    request_timeout = timeout if timeout is not None else float(os.getenv("OPTIONS_CHAIN_REQUEST_TIMEOUT_SECONDS", "15"))
    source_event_time = datetime.now(timezone.utc)
    ua = (
        os.getenv("OPTIONS_CHAIN_USER_AGENT")
        or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    source_vendor = "yahoo-finance-options"
    try:
        first_payload = _request_yahoo_options(symbol, unix_expiration=None, user_agent=ua, timeout=request_timeout)
        first_result = _extract_result(first_payload)
        expirations = [_as_int(item) for item in first_result.get("expirationDates") or []]
        expirations = [item for item in expirations if item is not None]
        selected_expirations = expirations[: max(1, limit)]

        rows: list[dict[str, Any]] = []
        seen_expirations: set[int] = set()
        if first_result.get("options"):
            rows.extend(
                _normalize_option_rows(
                    symbol=symbol,
                    market=market,
                    trade_date=requested_trade_date,
                    result=first_result,
                    source_event_time=source_event_time,
                )
            )
            first_option = first_result.get("options", [{}])[0]
            first_expiration = _as_int(first_option.get("expirationDate")) if isinstance(first_option, dict) else None
            if first_expiration is not None:
                seen_expirations.add(first_expiration)

        for unix_expiration in selected_expirations:
            if unix_expiration in seen_expirations:
                continue
            payload = _request_yahoo_options(symbol, unix_expiration=unix_expiration, user_agent=ua, timeout=request_timeout)
            result = _extract_result(payload)
            rows.extend(
                _normalize_option_rows(
                    symbol=symbol,
                    market=market,
                    trade_date=requested_trade_date,
                    result=result,
                    source_event_time=source_event_time,
                )
            )
            seen_expirations.add(unix_expiration)
    except Exception:
        source_vendor = "nasdaq-option-chain"
        nasdaq_payload = _request_nasdaq_options(symbol, timeout=request_timeout)
        rows = _normalize_nasdaq_option_rows(
            symbol=symbol,
            market=market,
            trade_date=requested_trade_date,
            payload=nasdaq_payload,
            source_event_time=source_event_time,
        )
    summary = summarize_option_chain(rows, symbol=symbol, market=market, trade_date=requested_trade_date)
    summary["source_vendor"] = source_vendor
    return rows, summary


def _calculate_max_pain(rows: list[dict[str, Any]]) -> float | None:
    strikes = sorted({row["strike"] for row in rows if row.get("strike") is not None})
    if not strikes:
        return None
    best_strike: float | None = None
    best_pain: float | None = None
    for settlement in strikes:
        pain = 0.0
        for row in rows:
            strike = row.get("strike")
            if strike is None:
                continue
            open_interest = row.get("open_interest") or 0
            if row.get("option_type") == "call":
                pain += open_interest * max(settlement - strike, 0)
            else:
                pain += open_interest * max(strike - settlement, 0)
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = float(settlement)
    return best_strike


def summarize_option_chain(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    market: str,
    trade_date: str,
) -> dict[str, Any]:
    expirations = sorted({row["expiration_date"] for row in rows if row.get("expiration_date")})
    call_rows = [row for row in rows if row.get("option_type") == "call"]
    put_rows = [row for row in rows if row.get("option_type") == "put"]
    total_call_volume = sum(row.get("volume") or 0 for row in call_rows)
    total_put_volume = sum(row.get("volume") or 0 for row in put_rows)
    total_call_open_interest = sum(row.get("open_interest") or 0 for row in call_rows)
    total_put_open_interest = sum(row.get("open_interest") or 0 for row in put_rows)
    iv_values = [row["implied_volatility"] for row in rows if row.get("implied_volatility") is not None]
    avg_iv = round(sum(iv_values) / len(iv_values), 8) if iv_values else None
    spread_rows = [
        row
        for row in rows
        if row.get("bid") is not None and row.get("ask") is not None and (row.get("bid") or 0) >= 0 and (row.get("ask") or 0) > 0
    ]
    tight_spreads = [
        row
        for row in spread_rows
        if (float(row["ask"]) - float(row["bid"])) / max(float(row["ask"]), 0.01) <= 0.25
    ]
    spread_coverage = len(tight_spreads) / len(spread_rows) if spread_rows else 0.0
    liquidity_score = _bounded_score(
        math.log10(total_call_volume + total_put_volume + 1) * 16
        + math.log10(total_call_open_interest + total_put_open_interest + 1) * 14
        + spread_coverage * 22
        + min(len(expirations), 6) * 2
    )

    call_put_volume_ratio = _safe_ratio(total_call_volume, total_put_volume)
    call_put_open_interest_ratio = _safe_ratio(total_call_open_interest, total_put_open_interest)
    ratio_for_flow = call_put_volume_ratio if call_put_volume_ratio is not None else call_put_open_interest_ratio
    if ratio_for_flow is None:
        flow_sentiment = "unknown"
        flow_score = 45.0
    elif ratio_for_flow >= 1.35:
        flow_sentiment = "bullish"
        flow_score = min(100.0, 55.0 + (ratio_for_flow - 1.0) * 18)
    elif ratio_for_flow <= 0.75:
        flow_sentiment = "bearish"
        flow_score = max(0.0, 45.0 - (1.0 - ratio_for_flow) * 20)
    else:
        flow_sentiment = "neutral"
        flow_score = 55.0

    iv_score = 45.0 if avg_iv is None else _bounded_score(avg_iv * 100)
    selection_score = _bounded_score(liquidity_score * 0.5 + flow_score * 0.25 + iv_score * 0.15 + spread_coverage * 100 * 0.10)
    data_quality_flag = "ok" if rows and len(expirations) >= 1 else "empty"
    underlying_prices = [row["underlying_price"] for row in rows if row.get("underlying_price") is not None]
    underlying_price = underlying_prices[0] if underlying_prices else None
    max_pain = _calculate_max_pain(rows)
    status = {
        "wheel_rule_score": {
            "status": "wheel_actionable" if selection_score >= 65 and liquidity_score >= 60 else "wheel_watch" if rows else "wheel_blocked",
            "score": selection_score,
            "reason": "Based on option liquidity, implied volatility, spread coverage, and call/put flow.",
        },
        "leaps_rule_score": {
            "status": "leaps_researchable"
            if liquidity_score >= 60 and flow_sentiment in {"bullish", "neutral"}
            else "leaps_watch"
            if rows
            else "leaps_blocked",
            "score": _bounded_score(liquidity_score * 0.55 + flow_score * 0.35 + (100 - min(iv_score, 100)) * 0.10),
            "reason": "LEAPS pre-filter favors liquid chains with non-bearish flow and manageable IV.",
        },
    }
    summary = {
        "symbol": symbol,
        "market": market,
        "trade_date": trade_date,
        "underlying_price": underlying_price,
        "expiration_count": len(expirations),
        "contract_count": len(rows),
        "nearest_expiration": expirations[0] if expirations else None,
        "total_call_volume": total_call_volume,
        "total_put_volume": total_put_volume,
        "call_put_volume_ratio": call_put_volume_ratio,
        "total_call_open_interest": total_call_open_interest,
        "total_put_open_interest": total_put_open_interest,
        "call_put_open_interest_ratio": call_put_open_interest_ratio,
        "avg_implied_volatility": avg_iv,
        "max_pain_strike": max_pain,
        "liquidity_score": liquidity_score,
        "flow_score": round(flow_score, 2),
        "selection_score": selection_score,
        "flow_sentiment": flow_sentiment,
        "data_quality_flag": data_quality_flag,
        **status,
    }
    summary["notes"] = _build_summary_notes(summary)
    return summary


def _build_summary_notes(summary: dict[str, Any]) -> list[str]:
    notes = [
        f"Option chain has {summary['contract_count']} contracts across {summary['expiration_count']} expirations.",
        f"Liquidity score {summary['liquidity_score']}; flow sentiment {summary['flow_sentiment']}.",
    ]
    if summary.get("max_pain_strike") is not None:
        notes.append(f"Estimated max-pain strike is {summary['max_pain_strike']}.")
    if summary.get("data_quality_flag") != "ok":
        notes.append("Data quality is not sufficient for automated action; keep human review mandatory.")
    return notes


def ensure_option_chain_schema(conn: Any) -> None:
    conn.execute(OPTION_CHAIN_SCHEMA_SQL)


def persist_option_chain(conn: Any, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    ensure_option_chain_schema(conn)
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO olap.us_option_chain_raw (
                    trade_date, market, symbol, expiration_date, option_type, contract_symbol,
                    strike, currency, last_price, bid, ask, price_change, percent_change,
                    volume, open_interest, implied_volatility, in_the_money, contract_size,
                    last_trade_time, underlying_price, source_event_time, source_vendor,
                    payload_hash, raw_payload
                ) VALUES (
                    %(trade_date)s, %(market)s, %(symbol)s, %(expiration_date)s, %(option_type)s, %(contract_symbol)s,
                    %(strike)s, %(currency)s, %(last_price)s, %(bid)s, %(ask)s, %(price_change)s, %(percent_change)s,
                    %(volume)s, %(open_interest)s, %(implied_volatility)s, %(in_the_money)s, %(contract_size)s,
                    %(last_trade_time)s, %(underlying_price)s, %(source_event_time)s, %(source_vendor)s,
                    %(payload_hash)s, %(raw_payload)s
                )
                ON CONFLICT (trade_date, market, symbol, expiration_date, option_type, contract_symbol)
                DO UPDATE SET
                    strike = EXCLUDED.strike,
                    currency = EXCLUDED.currency,
                    last_price = EXCLUDED.last_price,
                    bid = EXCLUDED.bid,
                    ask = EXCLUDED.ask,
                    price_change = EXCLUDED.price_change,
                    percent_change = EXCLUDED.percent_change,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    implied_volatility = EXCLUDED.implied_volatility,
                    in_the_money = EXCLUDED.in_the_money,
                    contract_size = EXCLUDED.contract_size,
                    last_trade_time = EXCLUDED.last_trade_time,
                    underlying_price = EXCLUDED.underlying_price,
                    source_event_time = EXCLUDED.source_event_time,
                    source_vendor = EXCLUDED.source_vendor,
                    payload_hash = EXCLUDED.payload_hash,
                    raw_payload = EXCLUDED.raw_payload,
                    ingest_time = NOW()
                """,
                [{**row, "raw_payload": Jsonb(row["raw_payload"])} for row in rows],
            )
    conn.execute(
        """
        INSERT INTO olap.security_option_chain_summary_daily (
            trade_date, market, symbol, underlying_price, expiration_count, contract_count,
            nearest_expiration, total_call_volume, total_put_volume, call_put_volume_ratio,
            total_call_open_interest, total_put_open_interest, call_put_open_interest_ratio,
            avg_implied_volatility, max_pain_strike, liquidity_score, flow_score,
            selection_score, flow_sentiment, data_quality_flag, summary_json
        ) VALUES (
            %(trade_date)s, %(market)s, %(symbol)s, %(underlying_price)s, %(expiration_count)s, %(contract_count)s,
            %(nearest_expiration)s, %(total_call_volume)s, %(total_put_volume)s, %(call_put_volume_ratio)s,
            %(total_call_open_interest)s, %(total_put_open_interest)s, %(call_put_open_interest_ratio)s,
            %(avg_implied_volatility)s, %(max_pain_strike)s, %(liquidity_score)s, %(flow_score)s,
            %(selection_score)s, %(flow_sentiment)s, %(data_quality_flag)s, %(summary_json)s
        )
        ON CONFLICT (trade_date, market, symbol)
        DO UPDATE SET
            underlying_price = EXCLUDED.underlying_price,
            expiration_count = EXCLUDED.expiration_count,
            contract_count = EXCLUDED.contract_count,
            nearest_expiration = EXCLUDED.nearest_expiration,
            total_call_volume = EXCLUDED.total_call_volume,
            total_put_volume = EXCLUDED.total_put_volume,
            call_put_volume_ratio = EXCLUDED.call_put_volume_ratio,
            total_call_open_interest = EXCLUDED.total_call_open_interest,
            total_put_open_interest = EXCLUDED.total_put_open_interest,
            call_put_open_interest_ratio = EXCLUDED.call_put_open_interest_ratio,
            avg_implied_volatility = EXCLUDED.avg_implied_volatility,
            max_pain_strike = EXCLUDED.max_pain_strike,
            liquidity_score = EXCLUDED.liquidity_score,
            flow_score = EXCLUDED.flow_score,
            selection_score = EXCLUDED.selection_score,
            flow_sentiment = EXCLUDED.flow_sentiment,
            data_quality_flag = EXCLUDED.data_quality_flag,
            summary_json = EXCLUDED.summary_json,
            updated_at = NOW()
        """,
        {**summary, "summary_json": Jsonb(summary)},
    )


def refresh_option_chain_for_symbol(
    symbol: str,
    *,
    market: str = "US",
    trade_date: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings()
    rows, summary = fetch_latest_option_chain(
        symbol,
        market=market,
        trade_date=trade_date,
        user_agent=settings.sec_user_agent,
    )
    if market.strip().upper() == "US":
        with connect(settings) as conn:
            persist_option_chain(conn, rows, summary)
    return {
        "summary": summary,
        "contract_count": len(rows),
        "source": summary.get("source_vendor", "option-chain"),
    }


def persist_agent_recommendation(
    *,
    settings: Settings | None = None,
    row: dict[str, Any],
) -> None:
    settings = settings or load_settings()
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    market_context = row.get("market_context") if isinstance(row.get("market_context"), dict) else {}
    option_summary = market_context.get("option_chain_summary") if isinstance(market_context.get("option_chain_summary"), dict) else {}
    daily_target = result.get("daily_target_review") if isinstance(result.get("daily_target_review"), dict) else {}
    with connect(settings) as conn:
        ensure_option_chain_schema(conn)
        conn.execute(
            """
            INSERT INTO olap.option_target_recommendation_daily (
                trade_date, market, symbol, batch_id, workflow_id, deerflow_thread_id,
                option_selection_score, agent_status, wheel_status, leaps_status,
                result_json, market_context_json
            ) VALUES (
                %(trade_date)s, %(market)s, %(symbol)s, %(batch_id)s, %(workflow_id)s, %(deerflow_thread_id)s,
                %(option_selection_score)s, %(agent_status)s, %(wheel_status)s, %(leaps_status)s,
                %(result_json)s, %(market_context_json)s
            )
            ON CONFLICT (trade_date, market, symbol, batch_id)
            DO UPDATE SET
                workflow_id = EXCLUDED.workflow_id,
                deerflow_thread_id = EXCLUDED.deerflow_thread_id,
                option_selection_score = EXCLUDED.option_selection_score,
                agent_status = EXCLUDED.agent_status,
                wheel_status = EXCLUDED.wheel_status,
                leaps_status = EXCLUDED.leaps_status,
                result_json = EXCLUDED.result_json,
                market_context_json = EXCLUDED.market_context_json,
                updated_at = NOW()
            """,
            {
                "trade_date": row["trade_date"],
                "market": row.get("market", "US"),
                "symbol": row["symbol"],
                "batch_id": row["batch_id"],
                "workflow_id": row.get("workflow_id"),
                "deerflow_thread_id": row.get("deerflow_thread_id"),
                "option_selection_score": option_summary.get("selection_score"),
                "agent_status": daily_target.get("status"),
                "wheel_status": (result.get("wheel_review") or {}).get("status") if isinstance(result.get("wheel_review"), dict) else None,
                "leaps_status": (result.get("leaps_review") or {}).get("status") if isinstance(result.get("leaps_review"), dict) else None,
                "result_json": Jsonb(result),
                "market_context_json": Jsonb(market_context),
            },
        )


def rank_option_targets(summaries: list[dict[str, Any]], *, top_n: int = 5) -> list[dict[str, Any]]:
    grouped: defaultdict[str, dict[str, Any]] = defaultdict(dict)
    for summary in summaries:
        symbol = str(summary.get("symbol") or "").upper()
        if not symbol:
            continue
        current = grouped.get(symbol)
        if not current or (summary.get("selection_score") or 0) > (current.get("selection_score") or 0):
            grouped[symbol] = summary
    return sorted(
        grouped.values(),
        key=lambda item: (
            item.get("data_quality_flag") == "ok",
            item.get("selection_score") or 0,
            item.get("liquidity_score") or 0,
        ),
        reverse=True,
    )[:top_n]
