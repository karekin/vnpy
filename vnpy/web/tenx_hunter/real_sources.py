from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import gzip
import json
import re
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import requests as _requests_lib


SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SEC_ARCHIVES_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json"
POLYGON_OVERVIEW_URL = "https://api.polygon.io/v3/reference/tickers/{ticker}"
POLYGON_BARS_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

ACCEPTED_SEC_FORMS = {"10-Q", "10-K", "8-K", "20-F", "40-F", "6-K"}
ACCEPTED_13F_FORMS = {"13F-HR", "13F-HR/A"}
THEME_CATALOG = {
    "ai_infra": "AI Infra",
    "cloud": "Cloud",
    "cybersecurity": "Cybersecurity",
    "semis": "Semiconductors",
}
THEME_HINTS = {
    "ai_infra": {"ai", "gpu", "inference", "training", "accelerator", "data center", "compute", "sovereign ai"},
    "cloud": {"cloud", "data platform", "data cloud", "lakehouse", "warehouse", "consumption"},
    "cybersecurity": {"security", "endpoint", "threat", "identity", "breach", "zero trust"},
    "semis": {"semiconductor", "chip", "wafer", "hbm", "cpu", "gpu", "silicon", "ip"},
}
COMPANY_SUFFIXES = (
    " CORPORATION",
    " CORP",
    " INCORPORATED",
    " INC",
    " COMPANY",
    " CO",
    " LIMITED",
    " LTD",
    " HOLDINGS",
    " HOLDING",
    " GROUP",
    " PLC",
    " N V",
    " NV",
    " S A",
    " SA",
)


@dataclass(frozen=True)
class SecuritySeed:
    symbol: str
    company_name: str
    exchange_name: str | None
    cik: str | None
    currency: str | None
    listing_status: str
    sector: str | None
    industry: str | None
    description: str | None
    shares_outstanding: float | None = None
    source_vendor: str = "real-source"


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    trade_date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adj_close: float | None
    volume: int | None
    source_vendor: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class FinancialSnapshot:
    symbol: str
    report_period: str
    fiscal_quarter: str
    fiscal_year: int | None
    period_type: str | None
    filed_date: str | None
    revenue: float | None
    gross_margin: float | None
    op_margin: float | None
    fcf_margin: float | None
    cash: float | None
    debt: float | None
    shares_outstanding: float | None
    revenue_yoy: float | None
    source_filing_id: str | None
    form_type: str | None
    currency: str | None
    data_quality_flag: str | None
    restatement_flag: bool | None
    source_vendor: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class EstimateSnapshot:
    symbol: str
    snapshot_date: str
    fiscal_year_offset: int | None
    next_year_revenue_estimate: float | None
    next_year_eps: float | None
    analyst_count: int | None
    currency: str | None
    period_label: str | None
    request_status: str | None
    source_vendor: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class EarningsCalendarEvent:
    event_id: str
    symbol: str
    snapshot_date: str
    earnings_date: str | None
    fiscal_period: str | None
    time_of_day: str | None
    eps_estimate: float | None
    revenue_estimate: float | None
    currency: str | None
    request_status: str | None
    source_vendor: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class FilingRecord:
    filing_id: str
    symbol: str
    cik: str | None
    accession_number: str | None
    filing_type: str
    filing_date: str | None
    filing_time: str
    report_period: str | None
    title: str
    primary_document: str | None
    filing_url: str | None
    source_vendor: str
    content: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NewsRecord:
    news_id: str
    symbol: str
    published_time: str
    updated_time: str | None
    title: str
    summary: str | None
    article_url: str | None
    language: str | None
    author: str | None
    publisher_name: str | None
    publisher_homepage: str | None
    primary_symbol: str | None
    related_symbols: list[str] | None
    source_vendor: str
    content: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class InstitutionalActivityRecord:
    activity_id: str
    symbol: str
    activity_time: str
    activity_type: str
    report_period: str | None
    filing_date: str | None
    title: str
    manager_symbol: str
    manager_name: str
    manager_cik: str | None
    filing_id: str
    filing_type: str
    position_value_usd: float | None
    position_shares: float | None
    source_url: str | None
    source_vendor: str
    content: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class RealBootstrapBundle:
    securities: list[SecuritySeed]
    security_themes: list[dict[str, str]]
    prices: list[PriceBar]
    financials: list[FinancialSnapshot]
    estimates: list[EstimateSnapshot]
    earnings_calendar: list[EarningsCalendarEvent]
    filings: list[FilingRecord]
    news: list[NewsRecord]
    institutional_activity: list[InstitutionalActivityRecord]
    watch_actions: list[dict[str, str]]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def default_date_range() -> tuple[str, str]:
    end = _now_utc().date()
    start = end - timedelta(days=10)
    return start.isoformat(), end.isoformat()


def normalize_symbols(raw: str | None) -> list[str]:
    value = raw or "NVDA,SNOW,CRWD,ARM"
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def infer_theme_ids(*texts: str | None) -> list[str]:
    haystack = " ".join(text or "" for text in texts).lower()
    matched = [theme_id for theme_id, hints in THEME_HINTS.items() if any(hint in haystack for hint in hints)]
    return sorted(set(matched))


def _request(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout: int = 30) -> bytes:
    full_url = url
    if params:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        joiner = "&" if "?" in url else "?"
        full_url = f"{url}{joiner}{query}"
    try:
        import requests  # type: ignore

        response = requests.get(full_url, headers=headers or {}, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception:
        request = Request(full_url, headers=headers or {})
        with urlopen(request, timeout=timeout) as response:
            return response.read()


def _decode_payload(data: bytes) -> str:
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="ignore")


def request_json(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    return json.loads(_decode_payload(_request(url, headers=headers, params=params, timeout=timeout)))


def request_text(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout: int = 30) -> str:
    return _decode_payload(_request(url, headers=headers, params=params, timeout=timeout))


def _sec_headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    }


def padded_cik(cik: str | int) -> str:
    return str(cik).strip().zfill(10)


def fetch_sec_ticker_map(user_agent: str) -> dict[str, dict[str, Any]]:
    payload = request_json(SEC_TICKER_MAP_URL, headers=_sec_headers(user_agent))
    mapping: dict[str, dict[str, Any]] = {}
    for row in payload.values():
        ticker = str(row.get("ticker", "")).upper().strip()
        if ticker:
            mapping[ticker] = row
    return mapping


def fetch_sec_submissions(cik: str, user_agent: str) -> dict[str, Any]:
    return request_json(SEC_SUBMISSIONS_URL.format(cik=padded_cik(cik)), headers=_sec_headers(user_agent))


def fetch_sec_companyfacts(cik: str, user_agent: str) -> dict[str, Any]:
    return request_json(SEC_COMPANYFACTS_URL.format(cik=padded_cik(cik)), headers=_sec_headers(user_agent))


def fetch_sec_filing_document(cik: str, accession_number: str, primary_document: str, user_agent: str) -> str:
    accession = accession_number.replace("-", "")
    url = SEC_ARCHIVES_URL.format(cik=str(int(cik)), accession=accession, document=primary_document)
    return request_text(url, headers=_sec_headers(user_agent), timeout=60)


def fetch_sec_filing_index(cik: str, accession_number: str, user_agent: str) -> dict[str, Any]:
    accession = accession_number.replace("-", "")
    return request_json(
        SEC_ARCHIVES_INDEX_URL.format(cik=str(int(cik)), accession=accession),
        headers=_sec_headers(user_agent),
        timeout=60,
    )


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _iso_datetime(value: Any) -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_date(value: Any) -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return str(value)
    return dt.date().isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if hasattr(value, "item") and not isinstance(value, (int, float, str)):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _safe_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _normalize_company_key(value: Any) -> str | None:
    text = _safe_str(value)
    if text is None:
        return None
    normalized = text.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _company_name_aliases(value: Any) -> list[str]:
    normalized = _normalize_company_key(value)
    if normalized is None:
        return []
    aliases = {normalized}
    for suffix in COMPANY_SUFFIXES:
        if normalized.endswith(suffix):
            trimmed = normalized[: -len(suffix)].strip()
            if trimmed:
                aliases.add(trimmed)
    return sorted(aliases, key=len, reverse=True)


def _build_company_title_map(ticker_map: dict[str, dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for ticker, row in ticker_map.items():
        for alias in _company_name_aliases(row.get("title")):
            mapping.setdefault(alias, ticker)
    return mapping


def _infer_period_type(label: str | None) -> str | None:
    text = _safe_str(label)
    if text is None:
        return None
    lowered = text.lower()
    if "q" in lowered:
        return "quarterly"
    if lowered in {"fy", "annual"} or "y" in lowered:
        return "annual"
    return None


def _list_get(values: Any, index: int) -> Any:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _raw_number(value: Any) -> float | None:
    if isinstance(value, dict) and "raw" in value:
        value = value.get("raw")
    return _safe_float(value)


def _sec_filing_url(cik: str | None, accession_number: str | None, primary_document: str | None) -> str | None:
    if not cik or not accession_number or not primary_document:
        return None
    try:
        normalized_cik = str(int(str(cik).strip()))
    except (TypeError, ValueError):
        return None
    return SEC_ARCHIVES_URL.format(cik=normalized_cik, accession=accession_number.replace("-", ""), document=primary_document)


def _sec_13f_information_table_url(cik: str | None, accession_number: str | None, table_document: str | None) -> str | None:
    return _sec_filing_url(cik, accession_number, table_document)


def _latest_fact(companyfacts: dict[str, Any], candidates: list[tuple[str, str, str]]) -> dict[str, Any] | None:
    facts = companyfacts.get("facts", {})
    records: list[dict[str, Any]] = []
    for taxonomy, tag, unit in candidates:
        rows = facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
        for row in rows:
            if row.get("form") in ACCEPTED_SEC_FORMS:
                normalized = dict(row)
                normalized["taxonomy"] = taxonomy
                normalized["tag"] = tag
                normalized["unit"] = unit
                records.append(normalized)
    if not records:
        return None
    records.sort(key=lambda row: (_parse_datetime(row.get("end")) or datetime.min, _parse_datetime(row.get("filed")) or datetime.min))
    return records[-1]


def _previous_matching_fact(companyfacts: dict[str, Any], latest: dict[str, Any], candidates: list[tuple[str, str, str]]) -> dict[str, Any] | None:
    facts = companyfacts.get("facts", {})
    rows: list[dict[str, Any]] = []
    for taxonomy, tag, unit in candidates:
        for row in facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, []):
            if row.get("form") not in ACCEPTED_SEC_FORMS:
                continue
            rows.append(dict(row))
    if not rows:
        return None
    latest_fp = latest.get("fp")
    latest_fy = latest.get("fy")
    candidates_rows = [
        row for row in rows
        if row.get("fp") == latest_fp and row.get("fy") is not None and latest_fy is not None and row.get("fy") < latest_fy
    ]
    if not candidates_rows:
        candidates_rows = [row for row in rows if (_parse_datetime(row.get("end")) or datetime.min) < (_parse_datetime(latest.get("end")) or datetime.max)]
    if not candidates_rows:
        return None
    candidates_rows.sort(key=lambda row: (_parse_datetime(row.get("end")) or datetime.min, _parse_datetime(row.get("filed")) or datetime.min))
    return candidates_rows[-1]


def build_financial_snapshot_from_sec(
    symbol: str,
    companyfacts: dict[str, Any],
    *,
    shares_outstanding_fallback: float | None = None,
) -> FinancialSnapshot | None:
    revenue_candidates = [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
        ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax", "USD"),
        ("us-gaap", "SalesRevenueNet", "USD"),
        ("us-gaap", "Revenues", "USD"),
    ]
    gross_profit_candidates = [("us-gaap", "GrossProfit", "USD")]
    op_income_candidates = [("us-gaap", "OperatingIncomeLoss", "USD")]
    cash_flow_candidates = [("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "USD")]
    capex_candidates = [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD")]
    cash_candidates = [("us-gaap", "CashAndCashEquivalentsAtCarryingValue", "USD")]
    debt_candidates = [
        ("us-gaap", "LongTermDebtAndFinanceLeaseObligations", "USD"),
        ("us-gaap", "LongTermDebtAndCapitalLeaseObligations", "USD"),
        ("us-gaap", "LongTermDebtNoncurrent", "USD"),
        ("us-gaap", "LongTermDebt", "USD"),
    ]
    shares_candidates = [
        ("dei", "EntityCommonStockSharesOutstanding", "shares"),
        ("us-gaap", "CommonStockSharesOutstanding", "shares"),
    ]

    revenue_row = _latest_fact(companyfacts, revenue_candidates)
    if revenue_row is None:
        return None
    previous_revenue = _previous_matching_fact(companyfacts, revenue_row, revenue_candidates)
    revenue = _safe_float(revenue_row.get("val"))
    previous_revenue_val = _safe_float(previous_revenue.get("val")) if previous_revenue else None
    revenue_yoy = None
    if revenue is not None and previous_revenue_val not in (None, 0):
        revenue_yoy = (revenue - previous_revenue_val) / previous_revenue_val

    gross_profit = _safe_float((_latest_fact(companyfacts, gross_profit_candidates) or {}).get("val"))
    op_income = _safe_float((_latest_fact(companyfacts, op_income_candidates) or {}).get("val"))
    operating_cash = _safe_float((_latest_fact(companyfacts, cash_flow_candidates) or {}).get("val"))
    capex = _safe_float((_latest_fact(companyfacts, capex_candidates) or {}).get("val"))
    cash = _safe_float((_latest_fact(companyfacts, cash_candidates) or {}).get("val"))
    debt = _safe_float((_latest_fact(companyfacts, debt_candidates) or {}).get("val"))
    shares_outstanding = _safe_float((_latest_fact(companyfacts, shares_candidates) or {}).get("val"))
    if shares_outstanding is None:
        shares_outstanding = shares_outstanding_fallback

    gross_margin = (gross_profit / revenue) if gross_profit is not None and revenue not in (None, 0) else None
    op_margin = (op_income / revenue) if op_income is not None and revenue not in (None, 0) else None
    fcf = None
    if operating_cash is not None and capex is not None:
        fcf = operating_cash - abs(capex)
    elif operating_cash is not None:
        fcf = operating_cash
    fcf_margin = (fcf / revenue) if fcf is not None and revenue not in (None, 0) else None

    fiscal_quarter = _safe_str(revenue_row.get("fp")) or "LATEST"
    report_period = _iso_date(revenue_row.get("end"))
    raw_payload = {
        "entityName": companyfacts.get("entityName"),
        "revenue_fact": revenue_row,
        "previous_revenue_fact": previous_revenue,
        "gross_profit": gross_profit,
        "operating_income": op_income,
        "operating_cash_flow": operating_cash,
        "capex": capex,
        "cash": cash,
        "debt": debt,
        "shares_outstanding": shares_outstanding,
    }
    return FinancialSnapshot(
        symbol=symbol,
        report_period=report_period,
        fiscal_quarter=fiscal_quarter,
        fiscal_year=_safe_int(revenue_row.get("fy")),
        period_type=_infer_period_type(fiscal_quarter),
        filed_date=_iso_date(revenue_row.get("filed")),
        revenue=revenue,
        gross_margin=gross_margin,
        op_margin=op_margin,
        fcf_margin=fcf_margin,
        cash=cash,
        debt=debt,
        shares_outstanding=shares_outstanding,
        revenue_yoy=revenue_yoy,
        source_filing_id=_safe_str(revenue_row.get("accn")),
        form_type=_safe_str(revenue_row.get("form")),
        currency=_safe_str(revenue_row.get("unit")) or "USD",
        data_quality_flag="parsed" if revenue is not None else "missing_revenue",
        restatement_flag=_safe_bool(revenue_row.get("restated")),
        source_vendor="sec-companyfacts",
        raw_payload=raw_payload,
    )


def build_filings_from_submissions(symbol: str, cik: str, submissions: dict[str, Any], user_agent: str, *, limit: int = 2) -> list[FilingRecord]:
    recent = submissions.get("filings", {}).get("recent", {})
    records: list[FilingRecord] = []
    recent_count = len(recent.get("form", [])) if isinstance(recent.get("form"), list) else 0
    for index in range(recent_count):
        accession = _safe_str(_list_get(recent.get("accessionNumber"), index))
        form = _safe_str(_list_get(recent.get("form"), index))
        filed_at = _list_get(recent.get("filingDate"), index)
        acceptance_time = _list_get(recent.get("acceptanceDateTime"), index) or filed_at
        report_date = _list_get(recent.get("reportDate"), index)
        document = _safe_str(_list_get(recent.get("primaryDocument"), index))
        description = _safe_str(_list_get(recent.get("primaryDocDescription"), index))
        if form not in ACCEPTED_SEC_FORMS or not document:
            continue
        try:
            content = fetch_sec_filing_document(cik, accession, document, user_agent)
        except Exception as exc:  # pragma: no cover - network dependent fallback
            content = f"Failed to fetch filing content for {symbol} {form}: {exc}"
        title = _safe_str(description) or f"{symbol} {form} filing"
        filing_id = f"{symbol}-{accession}" if accession else f"{symbol}-{form}-{index + 1}"
        records.append(
            FilingRecord(
                filing_id=filing_id,
                symbol=symbol,
                cik=_safe_str(cik),
                accession_number=accession,
                filing_type=form,
                filing_date=_iso_date(filed_at),
                filing_time=_iso_datetime(acceptance_time),
                report_period=_iso_date(report_date) if report_date else None,
                title=title,
                primary_document=document,
                filing_url=_sec_filing_url(cik, accession, document),
                source_vendor="sec-edgar",
                content=content,
                raw_payload={
                    "cik": _safe_str(cik),
                    "accessionNumber": accession,
                    "form": form,
                    "filingDate": filed_at,
                    "acceptanceDateTime": acceptance_time,
                    "reportDate": report_date,
                    "primaryDocument": document,
                    "primaryDocDescription": description,
                    "isXBRL": _safe_bool(_list_get(recent.get("isXBRL"), index)),
                    "isInlineXBRL": _safe_bool(_list_get(recent.get("isInlineXBRL"), index)),
                },
            )
        )
        if len(records) >= limit:
            break
    return records


def fetch_sec_13f_information_table(cik: str, accession_number: str, user_agent: str) -> tuple[str | None, list[dict[str, Any]]]:
    index_payload = fetch_sec_filing_index(cik, accession_number, user_agent)
    directory = index_payload.get("directory") if isinstance(index_payload, dict) else {}
    items = directory.get("item") if isinstance(directory, dict) else []
    table_document: str | None = None
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _safe_str(item.get("name"))
            lowered = (name or "").lower()
            if lowered == "information_table.xml":
                table_document = name
                break
        if table_document is None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = _safe_str(item.get("name"))
                lowered = (name or "").lower()
                if lowered.endswith(".xml") and "information" in lowered:
                    table_document = name
                    break
    if table_document is None:
        return None, []

    xml_text = request_text(
        SEC_ARCHIVES_URL.format(cik=str(int(cik)), accession=accession_number.replace("-", ""), document=table_document),
        headers=_sec_headers(user_agent),
        timeout=60,
    )
    root = ElementTree.fromstring(xml_text)
    namespace_uri = root.tag.split("}", 1)[0].strip("{") if root.tag.startswith("{") else ""
    namespace = {"ns": namespace_uri} if namespace_uri else {}

    def _find_text(node: ElementTree.Element, path: str) -> str | None:
        target = node.find(path, namespace) if namespace else node.find(path)
        if target is None or target.text is None:
            return None
        return target.text.strip() or None

    holdings: list[dict[str, Any]] = []
    info_tables = root.findall("ns:infoTable", namespace) if namespace else root.findall("infoTable")
    for row in info_tables:
        holdings.append(
            {
                "nameOfIssuer": _find_text(row, "ns:nameOfIssuer" if namespace else "nameOfIssuer"),
                "titleOfClass": _find_text(row, "ns:titleOfClass" if namespace else "titleOfClass"),
                "cusip": _find_text(row, "ns:cusip" if namespace else "cusip"),
                "value": _find_text(row, "ns:value" if namespace else "value"),
                "sshPrnamt": _find_text(row, "ns:shrsOrPrnAmt/ns:sshPrnamt" if namespace else "shrsOrPrnAmt/sshPrnamt"),
                "sshPrnamtType": _find_text(row, "ns:shrsOrPrnAmt/ns:sshPrnamtType" if namespace else "shrsOrPrnAmt/sshPrnamtType"),
                "investmentDiscretion": _find_text(row, "ns:investmentDiscretion" if namespace else "investmentDiscretion"),
            }
        )
    return table_document, holdings


def build_institutional_activity_from_submissions(
    *,
    manager_symbol: str,
    manager_name: str,
    manager_cik: str,
    submissions: dict[str, Any],
    title_to_ticker: dict[str, str],
    universe_symbols: set[str],
    user_agent: str,
    limit: int = 1,
) -> list[InstitutionalActivityRecord]:
    recent = submissions.get("filings", {}).get("recent", {})
    records: list[InstitutionalActivityRecord] = []
    seen_symbols: set[tuple[str, str]] = set()
    filings_seen = 0

    for index, form in enumerate(recent.get("form", []) or []):
        if form not in ACCEPTED_13F_FORMS:
            continue
        accession = _list_get(recent.get("accessionNumber"), index)
        if not accession:
            continue
        filing_date = _list_get(recent.get("filingDate"), index)
        filing_time = _list_get(recent.get("acceptanceDateTime"), index) or filing_date
        report_period = _list_get(recent.get("reportDate"), index)
        try:
            table_document, holdings = fetch_sec_13f_information_table(manager_cik, accession, user_agent)
        except Exception:
            continue

        for holding in holdings:
            issuer_name = _safe_str(holding.get("nameOfIssuer"))
            if issuer_name is None:
                continue
            held_symbol = next((title_to_ticker.get(alias) for alias in _company_name_aliases(issuer_name) if alias in title_to_ticker), None)
            if held_symbol is None or held_symbol not in universe_symbols:
                continue
            dedupe_key = (accession, held_symbol)
            if dedupe_key in seen_symbols:
                continue
            seen_symbols.add(dedupe_key)

            value_usd = _safe_float(holding.get("value"))
            share_count = _safe_float(holding.get("sshPrnamt"))
            title = f"{manager_symbol} 13F disclosed a {held_symbol} holding"
            value_text = f"${value_usd:,.0f}" if value_usd is not None else "an undisclosed value"
            shares_text = f"{share_count:,.0f} shares" if share_count is not None else "an undisclosed share count"
            period_text = report_period or filing_date or "the latest quarter"
            content = (
                f"{manager_name} ({manager_symbol}) filed {form} for {period_text} and disclosed a holding in "
                f"{held_symbol} ({issuer_name}). Reported position value was about {value_text} with {shares_text}."
            )
            records.append(
                InstitutionalActivityRecord(
                    activity_id=f"{manager_symbol}-{accession}-{held_symbol}",
                    symbol=held_symbol,
                    activity_time=_iso_datetime(filing_time),
                    activity_type="13f_holding",
                    report_period=_iso_date(report_period) if report_period else None,
                    filing_date=_iso_date(filing_date) if filing_date else None,
                    title=title,
                    manager_symbol=manager_symbol,
                    manager_name=manager_name,
                    manager_cik=manager_cik,
                    filing_id=f"{manager_symbol}-{accession}",
                    filing_type=form,
                    position_value_usd=value_usd,
                    position_shares=share_count,
                    source_url=_sec_13f_information_table_url(manager_cik, accession, table_document),
                    source_vendor="sec-13f",
                    content=content,
                    raw_payload={
                        "manager_symbol": manager_symbol,
                        "manager_name": manager_name,
                        "manager_cik": manager_cik,
                        "accessionNumber": accession,
                        "filingDate": filing_date,
                        "acceptanceDateTime": filing_time,
                        "reportDate": report_period,
                        "holding": holding,
                    },
                )
            )
        filings_seen += 1
        if filings_seen >= limit:
            break
    return records


def _value_from_frame(frame: Any, index_key: str, column_key: str) -> float | None:
    if frame is None:
        return None
    try:
        if hasattr(frame, "empty") and frame.empty:
            return None
        if index_key in frame.index and column_key in frame.columns:
            return _safe_float(frame.loc[index_key, column_key])
    except Exception:
        return None
    return None


def _normalize_yfinance_timestamp(value: Any) -> str:
    if value is None:
        return _iso_datetime(None)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return _iso_datetime(value)


_YAHOO_SESSION: requests.Session | None = None
_YAHOO_CRUMB: str | None = None
_YAHOO_CRUMB_FETCHED_AT: float = 0


def _yahoo_session() -> tuple[_requests_lib.Session, str | None]:
    """返回带 cookie 的 session 和 crumb；crumb 获取失败时返回 None（降级为无认证）。"""
    global _YAHOO_SESSION, _YAHOO_CRUMB, _YAHOO_CRUMB_FETCHED_AT

    # crumb 有效期约 10 分钟，提前 2 分钟刷新
    if _YAHOO_SESSION and _YAHOO_CRUMB and (time.time() - _YAHOO_CRUMB_FETCHED_AT) < 480:
        return _YAHOO_SESSION, _YAHOO_CRUMB

    browser_ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )
    session = _requests_lib.Session()
    session.headers.update({
        "User-Agent": browser_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    # Step 1: 访问首页获取 cookie
    try:
        session.get("https://finance.yahoo.com/", timeout=15)
    except Exception:
        pass

    # Step 2: 获取 crumb
    crumb = None
    try:
        crumb_resp = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers={"Accept": "*/*"},
            timeout=10,
        )
        if crumb_resp.status_code == 200 and crumb_resp.text.strip():
            crumb = crumb_resp.text.strip()
    except Exception:
        pass

    _YAHOO_SESSION = session
    _YAHOO_CRUMB = crumb
    _YAHOO_CRUMB_FETCHED_AT = time.time()
    return session, crumb


def _yahoo_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (TenX Hunter Demo)",
        "Accept": "application/json, text/plain, */*",
    }



def _nested_raw(value: Any) -> Any:
    if isinstance(value, dict) and "raw" in value:
        return value.get("raw")
    return value


def build_estimate_snapshot_from_yahoo_summary(
    symbol: str,
    summary_result: dict[str, Any],
    *,
    snapshot_date: str,
    source_vendor: str = "yfinance-demo",
) -> EstimateSnapshot:
    earnings_trend = (summary_result.get("earningsTrend") or {}).get("trend") or []
    if not isinstance(earnings_trend, list):
        earnings_trend = []
    trend_entries = [entry for entry in earnings_trend if isinstance(entry, dict)]

    selected_entry = next((entry for entry in trend_entries if _safe_str(entry.get("period")) in {"+1y", "0y"}), trend_entries[0] if trend_entries else {})
    revenue_estimate_block = selected_entry.get("revenueEstimate") if isinstance(selected_entry.get("revenueEstimate"), dict) else {}
    earnings_estimate_block = selected_entry.get("earningsEstimate") if isinstance(selected_entry.get("earningsEstimate"), dict) else {}
    analyst_count = _safe_int(_raw_number(revenue_estimate_block.get("numberOfAnalysts"))) or _safe_int(_raw_number(earnings_estimate_block.get("numberOfAnalysts")))
    currency = _safe_str((summary_result.get("price") or {}).get("currency")) or _safe_str(summary_result.get("currency")) or "USD"
    period_label = _safe_str(selected_entry.get("period")) or "+1y"
    request_status = "ok" if trend_entries else "missing_trend"

    return EstimateSnapshot(
        symbol=symbol,
        snapshot_date=_iso_date(snapshot_date),
        fiscal_year_offset=2 if period_label == "+1y" else 1 if period_label == "0y" else None,
        next_year_revenue_estimate=_raw_number(revenue_estimate_block.get("avg")),
        next_year_eps=_raw_number(earnings_estimate_block.get("avg")),
        analyst_count=analyst_count,
        currency=currency,
        period_label=period_label,
        request_status=request_status,
        source_vendor=source_vendor,
        raw_payload={
            "currency": currency,
            "period": period_label,
            "analystCount": analyst_count,
            "revenueEstimate": revenue_estimate_block,
            "earningsEstimate": earnings_estimate_block,
            "earningsTrend": trend_entries,
            "status": request_status,
        },
    )


def build_estimate_snapshots_from_yahoo_summary(
    symbol: str,
    summary_result: dict[str, Any],
    *,
    snapshot_date: str,
    source_vendor: str = "yfinance-demo",
) -> list[EstimateSnapshot]:
    earnings_trend = (summary_result.get("earningsTrend") or {}).get("trend") or []
    if not isinstance(earnings_trend, list):
        earnings_trend = []
    entries = [entry for entry in earnings_trend if isinstance(entry, dict)]
    wanted_periods = [("0y", 1), ("+1y", 2)]
    currency = _safe_str((summary_result.get("price") or {}).get("currency")) or _safe_str(summary_result.get("currency")) or "USD"
    snapshots: list[EstimateSnapshot] = []
    for period_label, fiscal_year_offset in wanted_periods:
        entry = next((item for item in entries if _safe_str(item.get("period")) == period_label), None)
        if entry is None:
            continue
        revenue_estimate_block = entry.get("revenueEstimate") if isinstance(entry.get("revenueEstimate"), dict) else {}
        earnings_estimate_block = entry.get("earningsEstimate") if isinstance(entry.get("earningsEstimate"), dict) else {}
        analyst_count = _safe_int(_raw_number(revenue_estimate_block.get("numberOfAnalysts"))) or _safe_int(_raw_number(earnings_estimate_block.get("numberOfAnalysts")))
        request_status = "ok" if revenue_estimate_block or earnings_estimate_block else "missing_estimate"
        snapshots.append(
            EstimateSnapshot(
                symbol=symbol,
                snapshot_date=_iso_date(snapshot_date),
                fiscal_year_offset=fiscal_year_offset,
                next_year_revenue_estimate=_raw_number(revenue_estimate_block.get("avg")),
                next_year_eps=_raw_number(earnings_estimate_block.get("avg")),
                analyst_count=analyst_count,
                currency=currency,
                period_label=period_label,
                request_status=request_status,
                source_vendor=source_vendor,
                raw_payload={
                    "currency": currency,
                    "period": period_label,
                    "fiscalYearOffset": fiscal_year_offset,
                    "analystCount": analyst_count,
                    "revenueEstimate": revenue_estimate_block,
                    "earningsEstimate": earnings_estimate_block,
                    "status": request_status,
                },
            )
        )
    if snapshots:
        return snapshots
    fallback = build_estimate_snapshot_from_yahoo_summary(
        symbol,
        summary_result,
        snapshot_date=snapshot_date,
        source_vendor=source_vendor,
    )
    return [fallback] if fallback.request_status == "ok" else []


def _first_earnings_date(raw_dates: Any) -> tuple[str | None, str | None]:
    if not isinstance(raw_dates, list) or not raw_dates:
        return None, None
    first = raw_dates[0]
    if isinstance(first, dict):
        raw = first.get("raw")
        date_value = _iso_date(datetime.fromtimestamp(raw, tz=timezone.utc)) if isinstance(raw, (int, float)) else _safe_str(first.get("fmt"))
        return date_value, _safe_str(first.get("fmt"))
    return _iso_date(first), None


def build_earnings_calendar_from_yahoo_summary(
    symbol: str,
    summary_result: dict[str, Any],
    *,
    snapshot_date: str,
    source_vendor: str = "yfinance-demo",
) -> EarningsCalendarEvent | None:
    calendar = summary_result.get("calendarEvents") if isinstance(summary_result.get("calendarEvents"), dict) else {}
    earnings = calendar.get("earnings") if isinstance(calendar.get("earnings"), dict) else {}
    earnings_date, earnings_date_label = _first_earnings_date(earnings.get("earningsDate"))
    currency = _safe_str((summary_result.get("price") or {}).get("currency")) or _safe_str(summary_result.get("currency")) or "USD"
    request_status = "ok" if earnings_date else "missing_earnings_date"
    if request_status != "ok" and not earnings:
        return None
    fiscal_period = _safe_str(earnings.get("earningsQuarter")) or _safe_str(earnings.get("fiscalQuarter"))
    return EarningsCalendarEvent(
        event_id=f"yf-calendar::{symbol}::{_iso_date(snapshot_date)}",
        symbol=symbol,
        snapshot_date=_iso_date(snapshot_date),
        earnings_date=earnings_date,
        fiscal_period=fiscal_period,
        time_of_day=_safe_str(earnings.get("timeOfDay")) or earnings_date_label,
        eps_estimate=_raw_number(earnings.get("earningsAverage")),
        revenue_estimate=_raw_number(earnings.get("revenueAverage")),
        currency=currency,
        request_status=request_status,
        source_vendor=source_vendor,
        raw_payload={
            "currency": currency,
            "calendarEvents": calendar,
            "status": request_status,
        },
    )



def fetch_yfinance_bundle(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    include_estimates: bool = False,
) -> tuple[list[SecuritySeed], list[PriceBar], list[NewsRecord]] | tuple[list[SecuritySeed], list[PriceBar], list[NewsRecord], list[EstimateSnapshot], list[EarningsCalendarEvent]]:
    securities: list[SecuritySeed] = []
    prices: list[PriceBar] = []
    news_items: list[NewsRecord] = []
    estimates: list[EstimateSnapshot] = []
    earnings_calendar: list[EarningsCalendarEvent] = []

    start_dt = (_parse_datetime(start_date) or _now_utc()).replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = ((_parse_datetime(end_date) or _now_utc()).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    headers = _yahoo_headers()

    # 尝试获取带 crumb 认证的 session
    yf_session, yf_crumb = _yahoo_session()
    use_session = yf_session is not None

    def _yf_get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """用 session + crumb 发起 Yahoo API 请求，失败时降级为无认证。"""
        p = dict(params or {})
        if yf_crumb:
            p["crumb"] = yf_crumb
        if use_session:
            resp = yf_session.get(url, params=p, headers=headers, timeout=20)
            resp.raise_for_status()
            return json.loads(_decode_payload(resp.content))
        return request_json(url, headers=headers, params=p)

    for symbol in symbols:
        quote_result: dict[str, Any] = {}
        try:
            quote_payload = _yf_get(YAHOO_QUOTE_URL, {"symbols": symbol})
            quote_result = ((quote_payload.get("quoteResponse") or {}).get("result") or [{}])[0]
        except Exception:
            quote_result = {}

        summary_result: dict[str, Any] = {}
        try:
            summary_payload = _yf_get(
                YAHOO_QUOTE_SUMMARY_URL.format(symbol=symbol),
                {"modules": "assetProfile,price,defaultKeyStatistics,financialData,earningsTrend,calendarEvents"},
            )
            summary_result = ((summary_payload.get("quoteSummary") or {}).get("result") or [{}])[0]
        except Exception:
            summary_result = {}
        if include_estimates and summary_result:
            estimates.extend(
                build_estimate_snapshots_from_yahoo_summary(
                    symbol,
                    summary_result,
                    snapshot_date=end_date,
                    source_vendor="yfinance-demo",
                )
            )
            earnings_event = build_earnings_calendar_from_yahoo_summary(
                symbol,
                summary_result,
                snapshot_date=end_date,
                source_vendor="yfinance-demo",
            )
            if earnings_event is not None:
                earnings_calendar.append(earnings_event)

        asset_profile = summary_result.get("assetProfile") or summary_result.get("summaryProfile") or {}
        price_module = summary_result.get("price") or {}
        default_stats = summary_result.get("defaultKeyStatistics") or {}
        try:
            chart_payload = _yf_get(
                YAHOO_CHART_URL.format(symbol=symbol),
                {
                    "period1": int(start_dt.timestamp()),
                    "period2": int(end_dt.timestamp()),
                    "interval": "1d",
                    "includeAdjustedClose": "true",
                    "events": "div,splits",
                },
            )
        except Exception:
            chart_payload = {}
        chart_result = ((chart_payload.get("chart") or {}).get("result") or [{}])[0]
        meta = chart_result.get("meta") or {}

        search_payload: dict[str, Any] = {}
        try:
            search_payload = _yf_get(YAHOO_SEARCH_URL, {"q": symbol, "newsCount": 3, "quotesCount": 1})
        except Exception:
            search_payload = {}

        search_quote = next(
            (
                item for item in (search_payload.get("quotes") or [])
                if _safe_str(item.get("symbol")) == symbol
            ),
            (search_payload.get("quotes") or [{}])[0],
        )

        company_name = (
            _safe_str(quote_result.get("longName"))
            or _safe_str(quote_result.get("shortName"))
            or _safe_str(_nested_raw(price_module.get("longName")))
            or _safe_str(search_quote.get("longname"))
            or _safe_str(search_quote.get("shortname"))
            or symbol
        )
        securities.append(
            SecuritySeed(
                symbol=symbol,
                company_name=company_name,
                exchange_name=(
                    _safe_str(meta.get("exchangeName"))
                    or _safe_str(quote_result.get("fullExchangeName"))
                    or _safe_str(quote_result.get("exchange"))
                    or _safe_str(search_quote.get("exchDisp"))
                ),
                cik=_safe_str(quote_result.get("cik")),
                currency=_safe_str(meta.get("currency")) or _safe_str(quote_result.get("currency")) or "USD",
                listing_status="active",
                sector=_safe_str(asset_profile.get("sector")),
                industry=_safe_str(asset_profile.get("industry")),
                description=_safe_str(asset_profile.get("longBusinessSummary")),
                shares_outstanding=_safe_float(_nested_raw(default_stats.get("sharesOutstanding")) or quote_result.get("sharesOutstanding")),
                source_vendor="yfinance-demo",
            )
        )

        timestamps = chart_result.get("timestamp") or []
        quote_rows = ((chart_result.get("indicators") or {}).get("quote") or [{}])[0]
        adjclose_rows = (((chart_result.get("indicators") or {}).get("adjclose") or [{}])[0] or {}).get("adjclose") or []
        opens = quote_rows.get("open") or []
        highs = quote_rows.get("high") or []
        lows = quote_rows.get("low") or []
        closes = quote_rows.get("close") or []
        volumes = quote_rows.get("volume") or []
        for idx, ts in enumerate(timestamps):
            close = _safe_float(closes[idx] if idx < len(closes) else None)
            open_ = _safe_float(opens[idx] if idx < len(opens) else None)
            high = _safe_float(highs[idx] if idx < len(highs) else None)
            low = _safe_float(lows[idx] if idx < len(lows) else None)
            adj_close = _safe_float(adjclose_rows[idx] if idx < len(adjclose_rows) else None) or close
            volume = _safe_int(volumes[idx] if idx < len(volumes) else None)
            if all(value is None for value in (open_, high, low, close, adj_close)):
                continue
            prices.append(
                PriceBar(
                    symbol=symbol,
                    trade_date=datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    adj_close=adj_close,
                    volume=volume,
                    source_vendor="yfinance-demo",
                    raw_payload={
                        "timestamp": ts,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": close,
                        "adj_close": adj_close,
                        "volume": volume,
                    },
                )
            )

        for idx, item in enumerate(search_payload.get("news") or [], start=1):
            title = _safe_str(item.get("title")) or f"{symbol} Yahoo Finance news {idx}"
            summary = _safe_str(item.get("summary")) or title
            published = item.get("providerPublishTime") or item.get("pubDate") or _now_utc().timestamp()
            news_items.append(
                NewsRecord(
                    news_id=_safe_str(item.get("uuid")) or _safe_str(item.get("id")) or f"{symbol}-yf-news-{idx}",
                    symbol=symbol,
                    published_time=_normalize_yfinance_timestamp(published),
                    updated_time=None,
                    title=title,
                    summary=summary,
                    article_url=_safe_str(item.get("link")),
                    language=_safe_str(item.get("language")),
                    author=None,
                    publisher_name=_safe_str(item.get("publisher")),
                    publisher_homepage=None,
                    primary_symbol=symbol,
                    related_symbols=[symbol],
                    source_vendor="yfinance-demo",
                    content=summary,
                    raw_payload=item,
                )
            )

    if include_estimates:
        return securities, prices, news_items, estimates, earnings_calendar
    return securities, prices, news_items


def fetch_polygon_news(symbols: list[str], api_key: str, *, limit: int = 5) -> list[NewsRecord]:
    news_items: list[NewsRecord] = []
    for symbol in symbols:
        payload = request_json(
            "https://api.polygon.io/v2/reference/news",
            params={"ticker": symbol, "limit": limit, "apiKey": api_key},
            headers={"Accept": "application/json"},
        )
        for idx, item in enumerate(payload.get("results", []) or [], start=1):
            publisher = item.get("publisher") if isinstance(item.get("publisher"), dict) else {}
            summary = _safe_str(item.get("description")) or _safe_str(item.get("title"))
            related_symbols = [
                ticker.strip().upper()
                for ticker in item.get("tickers", []) or [symbol]
                if isinstance(ticker, str) and ticker.strip()
            ] or [symbol]
            news_items.append(
                NewsRecord(
                    news_id=_safe_str(item.get("id")) or f"{symbol}-polygon-news-{idx}",
                    symbol=symbol,
                    published_time=_iso_datetime(item.get("published_utc")),
                    updated_time=_iso_datetime(item.get("updated_utc")) if item.get("updated_utc") else None,
                    title=_safe_str(item.get("title")) or f"{symbol} news {idx}",
                    summary=summary,
                    article_url=_safe_str(item.get("article_url")),
                    language=_safe_str(item.get("language")),
                    author=_safe_str(item.get("author")),
                    publisher_name=_safe_str(publisher.get("name")),
                    publisher_homepage=_safe_str(publisher.get("homepage_url")),
                    primary_symbol=symbol,
                    related_symbols=related_symbols,
                    source_vendor="polygon-news",
                    content=summary or _safe_str(item.get("title")) or "",
                    raw_payload=item,
                )
            )
    return news_items


def fetch_polygon_bundle(symbols: list[str], start_date: str, end_date: str, api_key: str) -> tuple[list[SecuritySeed], list[PriceBar]]:
    securities: list[SecuritySeed] = []
    prices: list[PriceBar] = []
    for symbol in symbols:
        overview = request_json(
            POLYGON_OVERVIEW_URL.format(ticker=symbol),
            params={"apiKey": api_key},
            headers={"Accept": "application/json"},
        ).get("results", {})
        securities.append(
            SecuritySeed(
                symbol=symbol,
                company_name=_safe_str(overview.get("name")) or symbol,
                exchange_name=_safe_str(overview.get("primary_exchange")),
                cik=_safe_str(overview.get("cik")),
                currency=_safe_str(overview.get("currency_name")) or "USD",
                listing_status="active" if overview.get("active", True) else "inactive",
                sector=_safe_str(overview.get("sic_description")),
                industry=_safe_str(overview.get("sic_description")),
                description=_safe_str(overview.get("description")),
                shares_outstanding=_safe_float(overview.get("weighted_shares_outstanding")),
                source_vendor="polygon",
            )
        )
        payload = request_json(
            POLYGON_BARS_URL.format(ticker=symbol, start=start_date, end=end_date),
            params={
                "adjusted": "true",
                "sort": "asc",
                "limit": 5000,
                "apiKey": api_key,
            },
            headers={"Accept": "application/json"},
        )
        for bar in payload.get("results", []) or []:
            trade_date = datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc).date().isoformat()
            prices.append(
                PriceBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=_safe_float(bar.get("o")),
                    high=_safe_float(bar.get("h")),
                    low=_safe_float(bar.get("l")),
                    close=_safe_float(bar.get("c")),
                    adj_close=_safe_float(bar.get("c")),
                    volume=_safe_int(bar.get("v")),
                    source_vendor="polygon",
                    raw_payload=bar,
                )
            )
    return securities, prices


def build_real_bundle(
    *,
    symbols: list[str],
    price_provider: str,
    start_date: str,
    end_date: str,
    sec_user_agent: str,
    polygon_api_key: str | None,
    include_yfinance_supplement: bool = True,
    institutional_manager_symbols: list[str] | None = None,
) -> RealBootstrapBundle:
    ticker_map = fetch_sec_ticker_map(sec_user_agent)
    title_to_ticker = _build_company_title_map(ticker_map)

    yfinance_securities: list[SecuritySeed] = []
    yfinance_prices: list[PriceBar] = []
    yfinance_news: list[NewsRecord] = []
    yfinance_estimates: list[EstimateSnapshot] = []
    yfinance_earnings_calendar: list[EarningsCalendarEvent] = []
    polygon_securities: list[SecuritySeed] = []
    polygon_prices: list[PriceBar] = []
    polygon_news: list[NewsRecord] = []

    if price_provider == "polygon":
        if not polygon_api_key:
            raise RuntimeError("PRICE_PROVIDER=polygon 需要设置 POLYGON_API_KEY")
        polygon_securities, polygon_prices = fetch_polygon_bundle(symbols, start_date, end_date, polygon_api_key)
        polygon_news = fetch_polygon_news(symbols, polygon_api_key)
        if include_yfinance_supplement:
            yfinance_securities, _unused_prices, yfinance_news, yfinance_estimates, yfinance_earnings_calendar = fetch_yfinance_bundle(symbols, start_date, end_date, include_estimates=True)
    elif price_provider == "yfinance":
        yfinance_securities, yfinance_prices, yfinance_news, yfinance_estimates, yfinance_earnings_calendar = fetch_yfinance_bundle(symbols, start_date, end_date, include_estimates=True)
    else:
        raise RuntimeError(f"Unsupported price provider: {price_provider}")

    by_symbol_security: dict[str, SecuritySeed] = {}
    for ticker in symbols:
        sec_row = ticker_map.get(ticker, {})
        candidate = next((row for row in polygon_securities if row.symbol == ticker), None) or next((row for row in yfinance_securities if row.symbol == ticker), None)
        by_symbol_security[ticker] = SecuritySeed(
            symbol=ticker,
            company_name=(candidate.company_name if candidate else None) or _safe_str(sec_row.get("title")) or ticker,
            exchange_name=(candidate.exchange_name if candidate else None),
            cik=(candidate.cik if candidate else None) or (_safe_str(sec_row.get("cik_str")) if sec_row else None),
            currency=(candidate.currency if candidate else None) or "USD",
            listing_status=(candidate.listing_status if candidate else "active"),
            sector=(candidate.sector if candidate else None),
            industry=(candidate.industry if candidate else None),
            description=(candidate.description if candidate else None),
            shares_outstanding=(candidate.shares_outstanding if candidate else None),
            source_vendor=(candidate.source_vendor if candidate else "sec+yfinance"),
        )

    prices = polygon_prices if price_provider == "polygon" else yfinance_prices
    financials: list[FinancialSnapshot] = []
    filings: list[FilingRecord] = []
    institutional_activity: list[InstitutionalActivityRecord] = []
    security_themes: list[dict[str, str]] = []

    for index, symbol in enumerate(symbols, start=1):
        security = by_symbol_security[symbol]
        if not security.cik:
            continue
        companyfacts = fetch_sec_companyfacts(security.cik, sec_user_agent)
        submissions = fetch_sec_submissions(security.cik, sec_user_agent)
        financial = build_financial_snapshot_from_sec(
            symbol,
            companyfacts,
            shares_outstanding_fallback=security.shares_outstanding,
        )
        if financial:
            financials.append(financial)
        symbol_filings = build_filings_from_submissions(symbol, security.cik, submissions, sec_user_agent, limit=2)
        filings.extend(symbol_filings)
        themes = infer_theme_ids(
            security.company_name,
            security.sector,
            security.industry,
            security.description,
            *(filing.title for filing in symbol_filings),
            *(news.title for news in [*polygon_news, *yfinance_news] if news.symbol == symbol),
        )
        for theme_id in themes:
            security_themes.append(
                {
                    "security_id": str(index),
                    "theme_id": theme_id,
                    "source_note": f"inferred from real-source metadata for {symbol}",
                }
            )

    manager_symbols = [symbol.strip().upper() for symbol in (institutional_manager_symbols or ["NVDA"]) if symbol and symbol.strip()]
    universe_symbols = {symbol.upper() for symbol in symbols}
    for manager_symbol in manager_symbols:
        manager_row = ticker_map.get(manager_symbol, {})
        manager_cik = _safe_str(manager_row.get("cik_str"))
        if manager_cik is None:
            continue
        try:
            manager_submissions = fetch_sec_submissions(manager_cik, sec_user_agent)
        except Exception:
            continue
        institutional_activity.extend(
            build_institutional_activity_from_submissions(
                manager_symbol=manager_symbol,
                manager_name=_safe_str(manager_row.get("title")) or manager_symbol,
                manager_cik=manager_cik,
                submissions=manager_submissions,
                title_to_ticker=title_to_ticker,
                universe_symbols=universe_symbols,
                user_agent=sec_user_agent,
                limit=1,
            )
        )

    watch_actions = [
        {
            "action_id": f"real-watch-{idx:03d}",
            "user_id": "demo_user",
            "symbol": symbol,
            "action": "watch",
            "action_time": _iso_datetime(_now_utc()),
        }
        for idx, symbol in enumerate(symbols[:3], start=1)
    ]

    securities = [
        SecuritySeed(
            symbol=security.symbol,
            company_name=security.company_name,
            exchange_name=security.exchange_name,
            cik=security.cik,
            currency=security.currency,
            listing_status=security.listing_status,
            sector=security.sector,
            industry=security.industry,
            description=security.description,
            shares_outstanding=security.shares_outstanding,
            source_vendor=security.source_vendor,
        )
        for security in (by_symbol_security[symbol] for symbol in symbols)
    ]

    return RealBootstrapBundle(
        securities=securities,
        security_themes=security_themes,
        prices=prices,
        financials=financials,
        estimates=yfinance_estimates,
        earnings_calendar=yfinance_earnings_calendar,
        filings=filings,
        news=polygon_news or yfinance_news,
        institutional_activity=institutional_activity,
        watch_actions=watch_actions,
    )
