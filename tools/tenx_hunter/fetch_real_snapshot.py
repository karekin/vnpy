from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vnpy.web.tenx_hunter.config import load_settings
from vnpy.web.tenx_hunter.real_sources import build_financial_snapshot_from_sec, build_real_bundle

ENV_FILE = ROOT / 'tools' / 'tenx_hunter' / '.env.local'
OUT_DIR = ROOT / 'examples' / 'tenx_hunter_data_pipeline' / 'sample_data' / 'real_snapshot'

THEMES = {
    'ai_infra': 'AI Infra',
    'cloud': 'Cloud',
    'cybersecurity': 'Cybersecurity',
    'semis': 'Semiconductors',
}
THEME_HINTS = {
    'ai_infra': {'ai', 'gpu', 'inference', 'training', 'accelerator', 'data center', 'compute', 'sovereign ai'},
    'cloud': {'cloud', 'data platform', 'data cloud', 'lakehouse', 'warehouse', 'consumption'},
    'cybersecurity': {'security', 'endpoint', 'identity', 'threat', 'breach', 'zero trust'},
    'semis': {'semiconductor', 'chip', 'wafer', 'hbm', 'cpu', 'gpu', 'silicon', 'ip'},
}
SEC_FORMS = {'10-Q', '10-K', '8-K', '20-F', '40-F', '6-K'}
FRED_SERIES = ['FEDFUNDS', 'CPIAUCSL', 'UNRATE', 'DGS10']
def load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_symbols() -> list[str]:
    raw = os.getenv('REAL_SYMBOLS') or 'NVDA,SNOW,CRWD,ARM'
    return [part.strip().upper() for part in raw.split(',') if part.strip()]


def get_date_range() -> tuple[str, str]:
    end = os.getenv('PRICE_END_DATE')
    start = os.getenv('PRICE_START_DATE')
    if not end:
        end = now_utc().date().isoformat()
    if not start:
        start = (datetime.fromisoformat(end) - timedelta(days=10)).date().isoformat()
    return start, end


def curl_json(url: str, *, user_agent: str | None = None) -> Any:
    cmd = ['curl', '-sS', '--fail', '--retry', '4', '--retry-all-errors', '--retry-delay', '1', '--max-time', '60']
    if user_agent:
        cmd += ['-A', user_agent]
    cmd.append(url)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def safe_curl_json(url: str, *, user_agent: str | None = None) -> dict[str, Any]:
    try:
        payload = curl_json(url, user_agent=user_agent)
        if isinstance(payload, dict):
            return payload
        return {"status": "OK", "results": payload}
    except subprocess.CalledProcessError as exc:
        return {
            "status": "FETCH_ERROR",
            "message": exc.stderr.strip() if exc.stderr else str(exc),
            "url": url,
        }


def curl_text(url: str, *, user_agent: str | None = None) -> str:
    cmd = ['curl', '-sS', '--fail', '--retry', '4', '--retry-all-errors', '--retry-delay', '1', '--max-time', '60']
    if user_agent:
        cmd += ['-A', user_agent]
    cmd.append(url)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def infer_themes(*texts: str | None) -> list[str]:
    haystack = ' '.join(text or '' for text in texts).lower()
    matched = [theme_id for theme_id, hints in THEME_HINTS.items() if any(hint in haystack for hint in hints)]
    return sorted(set(matched))


def safe_float(value: Any) -> float | None:
    if value in (None, '', 'None'):
        return None
    try:
        return float(value)
    except Exception:
        return None


def latest_fact(companyfacts: dict[str, Any], candidates: list[tuple[str, str, str]]) -> dict[str, Any] | None:
    facts = companyfacts.get('facts', {})
    rows: list[dict[str, Any]] = []
    for taxonomy, tag, unit in candidates:
        for row in facts.get(taxonomy, {}).get(tag, {}).get('units', {}).get(unit, []):
            if row.get('form') in SEC_FORMS:
                rows.append(dict(row))
    if not rows:
        return None
    rows.sort(key=lambda row: (row.get('end') or '', row.get('filed') or ''))
    return rows[-1]


def previous_matching_fact(companyfacts: dict[str, Any], latest: dict[str, Any], candidates: list[tuple[str, str, str]]) -> dict[str, Any] | None:
    facts = companyfacts.get('facts', {})
    rows: list[dict[str, Any]] = []
    for taxonomy, tag, unit in candidates:
        for row in facts.get(taxonomy, {}).get(tag, {}).get('units', {}).get(unit, []):
            if row.get('form') in SEC_FORMS:
                rows.append(dict(row))
    if not rows:
        return None
    latest_fp = latest.get('fp')
    latest_fy = latest.get('fy')
    candidates_rows = [row for row in rows if row.get('fp') == latest_fp and row.get('fy') and latest_fy and row.get('fy') < latest_fy]
    if not candidates_rows:
        candidates_rows = [row for row in rows if (row.get('end') or '') < (latest.get('end') or '9999-12-31')]
    if not candidates_rows:
        return None
    candidates_rows.sort(key=lambda row: (row.get('end') or '', row.get('filed') or ''))
    return candidates_rows[-1]


def build_financial_row(symbol: str, companyfacts: dict[str, Any], shares_outstanding_fallback: float | None = None) -> dict[str, Any] | None:
    revenue_candidates = [
        ('us-gaap', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'USD'),
        ('us-gaap', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'USD'),
        ('us-gaap', 'SalesRevenueNet', 'USD'),
        ('us-gaap', 'Revenues', 'USD'),
    ]
    gross_profit_candidates = [('us-gaap', 'GrossProfit', 'USD')]
    op_income_candidates = [('us-gaap', 'OperatingIncomeLoss', 'USD')]
    cfo_candidates = [('us-gaap', 'NetCashProvidedByUsedInOperatingActivities', 'USD')]
    capex_candidates = [('us-gaap', 'PaymentsToAcquirePropertyPlantAndEquipment', 'USD')]
    cash_candidates = [('us-gaap', 'CashAndCashEquivalentsAtCarryingValue', 'USD')]
    debt_candidates = [
        ('us-gaap', 'LongTermDebtAndFinanceLeaseObligations', 'USD'),
        ('us-gaap', 'LongTermDebtAndCapitalLeaseObligations', 'USD'),
        ('us-gaap', 'LongTermDebtNoncurrent', 'USD'),
        ('us-gaap', 'LongTermDebt', 'USD'),
    ]
    shares_candidates = [('dei', 'EntityCommonStockSharesOutstanding', 'shares')]

    revenue = latest_fact(companyfacts, revenue_candidates)
    if not revenue:
        return None
    prev_revenue = previous_matching_fact(companyfacts, revenue, revenue_candidates)
    revenue_val = safe_float(revenue.get('val'))
    prev_val = safe_float(prev_revenue.get('val')) if prev_revenue else None
    revenue_yoy = None
    if revenue_val not in (None, 0) and prev_val not in (None, 0):
        revenue_yoy = (revenue_val - prev_val) / prev_val

    gross_profit = safe_float((latest_fact(companyfacts, gross_profit_candidates) or {}).get('val'))
    op_income = safe_float((latest_fact(companyfacts, op_income_candidates) or {}).get('val'))
    cfo = safe_float((latest_fact(companyfacts, cfo_candidates) or {}).get('val'))
    capex = safe_float((latest_fact(companyfacts, capex_candidates) or {}).get('val'))
    cash = safe_float((latest_fact(companyfacts, cash_candidates) or {}).get('val'))
    debt = safe_float((latest_fact(companyfacts, debt_candidates) or {}).get('val'))
    shares = safe_float((latest_fact(companyfacts, shares_candidates) or {}).get('val')) or shares_outstanding_fallback

    gross_margin = (gross_profit / revenue_val) if gross_profit is not None and revenue_val not in (None, 0) else None
    op_margin = (op_income / revenue_val) if op_income is not None and revenue_val not in (None, 0) else None
    fcf = None
    if cfo is not None and capex is not None:
        fcf = cfo - abs(capex)
    elif cfo is not None:
        fcf = cfo
    fcf_margin = (fcf / revenue_val) if fcf is not None and revenue_val not in (None, 0) else None

    return {
        'symbol': symbol,
        'report_period': revenue.get('end'),
        'fiscal_quarter': revenue.get('fp') or 'LATEST',
        'revenue': revenue_val,
        'gross_margin': gross_margin,
        'op_margin': op_margin,
        'fcf_margin': fcf_margin,
        'cash': cash,
        'debt': debt,
        'shares_outstanding': shares,
        'revenue_yoy': revenue_yoy,
        'source_vendor': 'sec-companyfacts',
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_manifest(*, symbols: list[str], start_date: str, end_date: str, mode: str) -> None:
    manifest = {
        'generated_at': now_utc().isoformat(),
        'symbols': symbols,
        'start_date': start_date,
        'end_date': end_date,
        'mode': mode,
        'files': sorted(p.name for p in OUT_DIR.iterdir()),
    }
    write_json(OUT_DIR / 'manifest.json', manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def write_bundle_snapshot(bundle: Any, *, symbols: list[str], start_date: str, end_date: str, mode: str) -> int:
    securities = [
        {
            'security_id': idx,
            'symbol': item.symbol,
            'company_name': item.company_name,
            'exchange_name': item.exchange_name or '',
            'cik': item.cik or '',
            'currency': item.currency or 'USD',
            'listing_status': item.listing_status,
            'sector': item.sector or '',
            'industry': item.industry or '',
        }
        for idx, item in enumerate(bundle.securities, start=1)
    ]
    themes = [{'theme_id': k, 'theme_name': v, 'parent_theme': 'Growth Tech', 'active_flag': 'true'} for k, v in THEMES.items()]
    prices = [
        {
            'symbol': item.symbol,
            'trade_date': item.trade_date,
            'open': item.open,
            'high': item.high,
            'low': item.low,
            'close': item.close,
            'adj_close': item.adj_close,
            'volume': item.volume,
            'source_vendor': item.source_vendor,
        }
        for item in bundle.prices
    ]
    financials = [
        {
            'symbol': item.symbol,
            'report_period': item.report_period,
            'fiscal_quarter': item.fiscal_quarter,
            'fiscal_year': item.fiscal_year,
            'period_type': item.period_type,
            'filed_date': item.filed_date,
            'revenue': item.revenue,
            'gross_margin': item.gross_margin,
            'op_margin': item.op_margin,
            'fcf_margin': item.fcf_margin,
            'cash': item.cash,
            'debt': item.debt,
            'shares_outstanding': item.shares_outstanding,
            'revenue_yoy': item.revenue_yoy,
            'source_filing_id': item.source_filing_id,
            'form_type': item.form_type,
            'currency': item.currency,
            'data_quality_flag': item.data_quality_flag,
            'restatement_flag': item.restatement_flag,
            'source_vendor': item.source_vendor,
        }
        for item in bundle.financials
    ]
    filings = [
        {
            'filing_id': item.filing_id,
            'symbol': item.symbol,
            'cik': item.cik,
            'accession_number': item.accession_number,
            'filing_type': item.filing_type,
            'filing_date': item.filing_date,
            'filing_time': item.filing_time,
            'report_period': item.report_period,
            'title': item.title,
            'primary_document': item.primary_document,
            'filing_url': item.filing_url,
            'source_vendor': item.source_vendor,
            'content': item.content,
            'raw_payload': item.raw_payload,
        }
        for item in bundle.filings
    ]
    news = [
        {
            'news_id': item.news_id,
            'symbol': item.symbol,
            'published_time': item.published_time,
            'updated_time': item.updated_time,
            'title': item.title,
            'summary': item.summary,
            'article_url': item.article_url,
            'language': item.language,
            'author': item.author,
            'publisher_name': item.publisher_name,
            'publisher_homepage': item.publisher_homepage,
            'primary_symbol': item.primary_symbol,
            'related_symbols': item.related_symbols,
            'source_vendor': item.source_vendor,
            'content': item.content,
            'raw_payload': item.raw_payload,
        }
        for item in bundle.news
    ]

    write_csv(OUT_DIR / 'securities.csv', securities, ['security_id', 'symbol', 'company_name', 'exchange_name', 'cik', 'currency', 'listing_status', 'sector', 'industry'])
    write_csv(OUT_DIR / 'themes.csv', themes, ['theme_id', 'theme_name', 'parent_theme', 'active_flag'])
    write_csv(OUT_DIR / 'security_themes.csv', bundle.security_themes, ['security_id', 'theme_id', 'source_note'])
    write_csv(OUT_DIR / 'price_daily.csv', prices, ['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'source_vendor'])
    write_csv(
        OUT_DIR / 'financials.csv',
        financials,
        [
            'symbol', 'report_period', 'fiscal_quarter', 'fiscal_year', 'period_type', 'filed_date',
            'revenue', 'gross_margin', 'op_margin', 'fcf_margin', 'cash', 'debt', 'shares_outstanding',
            'revenue_yoy', 'source_filing_id', 'form_type', 'currency', 'data_quality_flag',
            'restatement_flag', 'source_vendor',
        ],
    )
    write_csv(OUT_DIR / 'watch_actions.csv', bundle.watch_actions, ['action_id', 'user_id', 'symbol', 'action', 'action_time'])
    write_json(OUT_DIR / 'filings.json', filings)
    write_json(OUT_DIR / 'news.json', news)
    write_json(OUT_DIR / 'symbol_master_raw.json', [])
    write_json(OUT_DIR / 'industry_mapping_raw.json', [])
    write_json(
        OUT_DIR / 'theme_taxonomy_raw.json',
        [
            {
                'theme_id': theme_id,
                'source_vendor': 'theme-taxonomy',
                'raw_payload': {
                    'theme_id': theme_id,
                    'theme_name': theme_name,
                    'parent_theme': 'Growth Tech',
                    'keywords': sorted(THEME_HINTS[theme_id]),
                },
            }
            for theme_id, theme_name in THEMES.items()
        ],
    )
    write_json(OUT_DIR / 'polygon_news_raw.json', [])
    write_json(OUT_DIR / 'macro_fred.json', [])
    write_json(OUT_DIR / 'polygon_ticker_overview_raw.json', [])
    write_json(OUT_DIR / 'sec_submissions_raw.json', [{'symbol': item.symbol, 'cik': item.cik, 'source_vendor': item.source_vendor, 'raw_payload': {'mode': mode}} for item in bundle.securities if item.cik])
    write_json(OUT_DIR / 'sec_companyfacts_raw.json', [])
    write_json(OUT_DIR / 'earnings_calendar_raw.json', [])
    write_json(OUT_DIR / 'polygon_corporate_actions_raw.json', [])
    write_json(OUT_DIR / 'user_feedback_raw.json', [])
    write_manifest(symbols=symbols, start_date=start_date, end_date=end_date, mode=mode)
    return 0


def main() -> int:
    load_env_file()
    settings = load_settings()
    polygon_key = settings.polygon_api_key
    fred_key = os.getenv('FRED_API_KEY')
    sec_user_agent = settings.sec_user_agent
    if not sec_user_agent:
        raise SystemExit('SEC_USER_AGENT is required')

    symbols = settings.real_symbols
    start_date, end_date = settings.price_start_date, settings.price_end_date
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if settings.price_provider == 'polygon' and not polygon_key:
        raise SystemExit('PRICE_PROVIDER=polygon requires POLYGON_API_KEY')

    if settings.price_provider == 'yfinance' and not polygon_key:
        bundle = build_real_bundle(
            symbols=symbols,
            price_provider='yfinance',
            start_date=start_date,
            end_date=end_date,
            sec_user_agent=sec_user_agent,
            polygon_api_key=None,
            include_yfinance_supplement=settings.include_yfinance_supplement,
        )
        return write_bundle_snapshot(bundle, symbols=symbols, start_date=start_date, end_date=end_date, mode='yfinance+sec')

    ticker_map = curl_json('https://www.sec.gov/files/company_tickers.json', user_agent=sec_user_agent)
    sec_map = {}
    for row in ticker_map.values():
        ticker = str(row.get('ticker', '')).upper().strip()
        if ticker:
            sec_map[ticker] = row

    securities = []
    security_themes = []
    prices = []
    financials = []
    filings = []
    news = []
    polygon_ticker_overview_rows = []
    symbol_master_rows = []
    industry_mapping_rows = []
    theme_taxonomy_rows = []
    polygon_news_raw_rows = []
    sec_submissions_rows = []
    sec_companyfacts_rows = []
    earnings_calendar_rows = []
    macro_fred_rows = []
    polygon_corporate_actions_rows = []
    user_feedback_rows = []

    for idx, symbol in enumerate(symbols, start=1):
        overview = curl_json(f'https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={polygon_key}')
        result = overview.get('results', {})
        sec_row = sec_map.get(symbol, {})
        cik = str(result.get('cik') or sec_row.get('cik_str') or '').strip()
        polygon_ticker_overview_rows.append({
            'symbol': symbol,
            'source_vendor': 'polygon-live',
            'raw_payload': overview,
        })
        symbol_master_rows.append({
            'symbol': symbol,
            'source_vendor': 'symbol-master',
            'raw_payload': {
                'symbol': symbol,
                'company_name': result.get('name') or sec_row.get('title') or symbol,
                'exchange_name': result.get('primary_exchange') or '',
                'cik': cik,
                'currency': result.get('currency_name') or 'USD',
                'listing_status': 'active' if result.get('active', True) else 'inactive',
                'market': result.get('market'),
                'locale': result.get('locale'),
                'type': result.get('type'),
            },
        })
        industry_mapping_rows.append({
            'symbol': symbol,
            'source_vendor': 'industry-mapping',
            'raw_payload': {
                'symbol': symbol,
                'sector': result.get('sic_description') or '',
                'industry': result.get('sic_description') or '',
                'sic_code': result.get('sic_code'),
                'source': 'polygon_ticker_overview',
            },
        })
        securities.append({
            'security_id': idx,
            'symbol': symbol,
            'company_name': result.get('name') or sec_row.get('title') or symbol,
            'exchange_name': result.get('primary_exchange') or '',
            'cik': cik,
            'currency': result.get('currency_name') or 'USD',
            'listing_status': 'active' if result.get('active', True) else 'inactive',
            'sector': result.get('sic_description') or '',
            'industry': result.get('sic_description') or '',
        })

        bars = curl_json(
            f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=asc&limit=5000&apiKey={polygon_key}'
        )
        for bar in bars.get('results', []) or []:
            trade_date = datetime.fromtimestamp(bar['t'] / 1000, tz=timezone.utc).date().isoformat()
            prices.append({
                'symbol': symbol,
                'trade_date': trade_date,
                'open': bar.get('o'),
                'high': bar.get('h'),
                'low': bar.get('l'),
                'close': bar.get('c'),
                'adj_close': bar.get('c'),
                'volume': int(bar.get('v') or 0),
                'source_vendor': 'polygon-live',
            })

        polygon_news = safe_curl_json(
            f'https://api.polygon.io/v2/reference/news?ticker={symbol}&limit=5&apiKey={polygon_key}'
        )
        for item in polygon_news.get('results', []) or []:
            polygon_news_raw_rows.append({
                'news_id': item.get('id'),
                'symbol': symbol,
                'published_time': item.get('published_utc'),
                'source_vendor': 'polygon-news',
                'raw_payload': item,
            })
            news.append({
                'news_id': item.get('id'),
                'symbol': symbol,
                'published_time': item.get('published_utc'),
                'updated_time': item.get('updated_utc'),
                'title': item.get('title') or f'{symbol} news',
                'summary': item.get('description') or item.get('title') or '',
                'article_url': item.get('article_url') or '',
                'language': item.get('language') or '',
                'author': item.get('author') or '',
                'publisher_name': (item.get('publisher') or {}).get('name') or '',
                'publisher_homepage': (item.get('publisher') or {}).get('homepage_url') or '',
                'primary_symbol': symbol,
                'related_symbols': item.get('tickers') or [symbol],
                'source_vendor': 'polygon-news',
                'content': item.get('description') or item.get('title') or '',
                'raw_payload': item,
            })

        dividends = safe_curl_json(
            f'https://api.polygon.io/v3/reference/dividends?ticker={symbol}&limit=20&apiKey={polygon_key}'
        )
        for item in dividends.get('results', []) or []:
            polygon_corporate_actions_rows.append({
                'action_id': item.get('id'),
                'symbol': item.get('ticker') or symbol,
                'action_type': 'dividend',
                'event_date': item.get('ex_dividend_date') or item.get('pay_date'),
                'source_vendor': 'polygon-dividends',
                'raw_payload': item,
            })

        splits = safe_curl_json(
            f'https://api.polygon.io/v3/reference/splits?ticker={symbol}&limit=20&apiKey={polygon_key}'
        )
        for item in splits.get('results', []) or []:
            polygon_corporate_actions_rows.append({
                'action_id': item.get('id'),
                'symbol': item.get('ticker') or symbol,
                'action_type': 'split',
                'event_date': item.get('execution_date'),
                'source_vendor': 'polygon-splits',
                'raw_payload': item,
            })

        earnings_payload = safe_curl_json(
            f'https://api.polygon.io/benzinga/v1/earnings?ticker={symbol}&limit=20&apiKey={polygon_key}'
        )
        earnings_calendar_rows.append({
            'symbol': symbol,
            'snapshot_date': now_utc().date().isoformat(),
            'source_vendor': 'polygon-benzinga',
            'request_status': earnings_payload.get('status'),
            'raw_payload': earnings_payload,
        })

        if cik:
            companyfacts = curl_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json', user_agent=sec_user_agent)
            sec_companyfacts_rows.append({
                'symbol': symbol,
                'cik': cik,
                'source_vendor': 'sec-companyfacts',
                'raw_payload': companyfacts,
            })
            financial = build_financial_snapshot_from_sec(
                symbol,
                companyfacts,
                shares_outstanding_fallback=result.get('weighted_shares_outstanding'),
            )
            if financial:
                financials.append({
                    'symbol': financial.symbol,
                    'report_period': financial.report_period,
                    'fiscal_quarter': financial.fiscal_quarter,
                    'fiscal_year': financial.fiscal_year,
                    'period_type': financial.period_type,
                    'filed_date': financial.filed_date,
                    'revenue': financial.revenue,
                    'gross_margin': financial.gross_margin,
                    'op_margin': financial.op_margin,
                    'fcf_margin': financial.fcf_margin,
                    'cash': financial.cash,
                    'debt': financial.debt,
                    'shares_outstanding': financial.shares_outstanding,
                    'revenue_yoy': financial.revenue_yoy,
                    'source_filing_id': financial.source_filing_id,
                    'form_type': financial.form_type,
                    'currency': financial.currency,
                    'data_quality_flag': financial.data_quality_flag,
                    'restatement_flag': financial.restatement_flag,
                    'source_vendor': financial.source_vendor,
                })

            submissions = curl_json(f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json', user_agent=sec_user_agent)
            sec_submissions_rows.append({
                'symbol': symbol,
                'cik': cik,
                'source_vendor': 'sec-edgar',
                'raw_payload': submissions,
            })
            recent = submissions.get('filings', {}).get('recent', {})
            for index, (accession, form, filed_at, document, description) in enumerate(zip(
                recent.get('accessionNumber', []),
                recent.get('form', []),
                recent.get('filingDate', []),
                recent.get('primaryDocument', []),
                recent.get('primaryDocDescription', []),
            )):
                if form not in SEC_FORMS or not document:
                    continue
                acc_no_dash = accession.replace('-', '')
                acceptance_time = (recent.get('acceptanceDateTime') or [filed_at])[index] if index < len(recent.get('acceptanceDateTime') or []) else filed_at
                report_date = (recent.get('reportDate') or [None])[index] if index < len(recent.get('reportDate') or []) else None
                is_xbrl = bool((recent.get('isXBRL') or [0])[index]) if index < len(recent.get('isXBRL') or []) else False
                is_inline_xbrl = bool((recent.get('isInlineXBRL') or [0])[index]) if index < len(recent.get('isInlineXBRL') or []) else False
                content = curl_text(
                    f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{document}',
                    user_agent=sec_user_agent,
                )
                filings.append({
                    'filing_id': f'{symbol}-{accession}',
                    'symbol': symbol,
                    'cik': cik,
                    'accession_number': accession,
                    'filing_type': form,
                    'filing_date': filed_at,
                    'filing_time': acceptance_time or f'{filed_at}T00:00:00Z',
                    'report_period': report_date,
                    'title': description or f'{symbol} {form} filing',
                    'primary_document': document,
                    'filing_url': f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{document}',
                    'source_vendor': 'sec-edgar',
                    'content': content,
                    'raw_payload': {
                        'cik': cik,
                        'accessionNumber': accession,
                        'form': form,
                        'filingDate': filed_at,
                        'acceptanceDateTime': acceptance_time,
                        'reportDate': report_date,
                        'primaryDocument': document,
                        'primaryDocDescription': description,
                        'isXBRL': is_xbrl,
                        'isInlineXBRL': is_inline_xbrl,
                    },
                })
                if len([f for f in filings if f['symbol'] == symbol]) >= 2:
                    break

        themes = infer_themes(
            result.get('description') or '',
            result.get('sic_description') or '',
            *(f['title'] for f in filings if f['symbol'] == symbol),
        )
        for theme_id in themes:
            security_themes.append({'security_id': idx, 'theme_id': theme_id, 'source_note': f'inferred from live sources for {symbol}'})
        user_feedback_rows.append({
            'feedback_id': f'demo-feedback-{idx:03d}',
            'user_id': 'demo_user',
            'symbol': symbol,
            'feedback_type': 'seed_feedback',
            'feedback_time': now_utc().replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            'raw_payload': {
                'symbol': symbol,
                'feedback_type': 'seed_feedback',
                'note': 'Prototype placeholder feedback row for ODS completeness',
            },
        })

    watch_actions = [
        {'action_id': f'live-watch-{i:03d}', 'user_id': 'demo_user', 'symbol': symbol, 'action': 'watch', 'action_time': now_utc().replace(microsecond=0).isoformat().replace('+00:00', 'Z')}
        for i, symbol in enumerate(symbols[:3], start=1)
    ]

    write_csv(OUT_DIR / 'securities.csv', securities, ['security_id', 'symbol', 'company_name', 'exchange_name', 'cik', 'currency', 'listing_status', 'sector', 'industry'])
    write_csv(OUT_DIR / 'themes.csv', [{'theme_id': k, 'theme_name': v, 'parent_theme': 'Growth Tech', 'active_flag': 'true'} for k, v in THEMES.items()], ['theme_id', 'theme_name', 'parent_theme', 'active_flag'])
    write_csv(OUT_DIR / 'security_themes.csv', security_themes, ['security_id', 'theme_id', 'source_note'])
    write_csv(OUT_DIR / 'price_daily.csv', prices, ['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'source_vendor'])
    write_csv(
        OUT_DIR / 'financials.csv',
        financials,
        [
            'symbol', 'report_period', 'fiscal_quarter', 'fiscal_year', 'period_type', 'filed_date',
            'revenue', 'gross_margin', 'op_margin', 'fcf_margin', 'cash', 'debt', 'shares_outstanding',
            'revenue_yoy', 'source_filing_id', 'form_type', 'currency', 'data_quality_flag',
            'restatement_flag', 'source_vendor',
        ],
    )
    write_csv(OUT_DIR / 'watch_actions.csv', watch_actions, ['action_id', 'user_id', 'symbol', 'action', 'action_time'])
    write_json(OUT_DIR / 'filings.json', filings)
    write_json(OUT_DIR / 'news.json', news)
    write_json(OUT_DIR / 'symbol_master_raw.json', symbol_master_rows)
    write_json(OUT_DIR / 'industry_mapping_raw.json', industry_mapping_rows)
    theme_taxonomy_rows = [
        {
            'theme_id': theme_id,
            'source_vendor': 'theme-taxonomy',
            'raw_payload': {
                'theme_id': theme_id,
                'theme_name': theme_name,
                'parent_theme': 'Growth Tech',
                'keywords': sorted(THEME_HINTS[theme_id]),
            },
        }
        for theme_id, theme_name in THEMES.items()
    ]
    write_json(OUT_DIR / 'theme_taxonomy_raw.json', theme_taxonomy_rows)
    write_json(OUT_DIR / 'polygon_news_raw.json', polygon_news_raw_rows)
    if fred_key:
        for series_id in FRED_SERIES:
            fred = curl_json(f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json&limit=3')
            macro_fred_rows.append({
                'series_id': series_id,
                'snapshot_date': now_utc().date().isoformat(),
                'source_vendor': 'fred',
                'raw_payload': fred,
            })
    write_json(OUT_DIR / 'macro_fred.json', macro_fred_rows)
    write_json(OUT_DIR / 'polygon_ticker_overview_raw.json', polygon_ticker_overview_rows)
    write_json(OUT_DIR / 'sec_submissions_raw.json', sec_submissions_rows)
    write_json(OUT_DIR / 'sec_companyfacts_raw.json', sec_companyfacts_rows)
    write_json(OUT_DIR / 'earnings_calendar_raw.json', earnings_calendar_rows)
    write_json(OUT_DIR / 'polygon_corporate_actions_raw.json', polygon_corporate_actions_rows)
    write_json(OUT_DIR / 'user_feedback_raw.json', user_feedback_rows)
    write_manifest(symbols=symbols, start_date=start_date, end_date=end_date, mode='polygon+sec')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
