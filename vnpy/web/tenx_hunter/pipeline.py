from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from .cn_sources import build_cn_stock_bundle
from .config import Settings
from .db import connect
from .options_chain import OPTION_CHAIN_SCHEMA_SQL, refresh_option_chain_for_symbol
from .price_map import build_price_map as build_price_map_snapshot
from .price_map import build_technical_snapshot
from .price_map_deerflow import (
    build_deerflow_price_map_prompt,
    extract_json_object as extract_deerflow_price_json,
    extract_latest_ai_content_from_history,
    price_map_from_deerflow_payload,
)
from .real_sources import SEC_ARCHIVES_URL, THEME_CATALOG, build_financial_snapshot_from_sec, build_real_bundle
from .scoring import build_score_components, classify_stage, explain_components
from .signals import extract_signal
from .storage import ObjectStorage

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS dwd;
CREATE SCHEMA IF NOT EXISTS dws;
CREATE SCHEMA IF NOT EXISTS ads;

CREATE TABLE IF NOT EXISTS dim.security (
    security_id INTEGER PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    exchange_name TEXT,
    cik TEXT,
    currency TEXT,
    listing_status TEXT,
    sector TEXT,
    industry TEXT,
    listed_date DATE
);

CREATE TABLE IF NOT EXISTS dim.theme (
    theme_id TEXT PRIMARY KEY,
    theme_name TEXT NOT NULL,
    parent_theme TEXT,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim.security_theme (
    security_id INTEGER NOT NULL REFERENCES dim.security(security_id),
    theme_id TEXT NOT NULL REFERENCES dim.theme(theme_id),
    source_note TEXT,
    PRIMARY KEY (security_id, theme_id)
);

CREATE TABLE IF NOT EXISTS dim.calendar (
    trade_date DATE PRIMARY KEY,
    week_of_year INTEGER,
    month_of_year INTEGER,
    quarter_of_year INTEGER
);

CREATE TABLE IF NOT EXISTS dim.factor_definition (
    factor_name TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ods.us_equity_price_daily_raw (
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(18,4),
    high NUMERIC(18,4),
    low NUMERIC(18,4),
    close NUMERIC(18,4),
    adj_close NUMERIC(18,4),
    volume BIGINT,
    currency TEXT,
    market_status TEXT,
    source_event_time TIMESTAMPTZ,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS ods.security_financial_statement_raw (
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    report_period DATE NOT NULL,
    fiscal_quarter TEXT NOT NULL,
    fiscal_year INTEGER,
    period_type TEXT,
    filed_date DATE,
    revenue NUMERIC(18,2),
    gross_margin NUMERIC(10,4),
    op_margin NUMERIC(10,4),
    fcf_margin NUMERIC(10,4),
    cash NUMERIC(18,2),
    debt NUMERIC(18,2),
    shares_outstanding NUMERIC(18,2),
    revenue_yoy NUMERIC(10,4),
    netprofit_yoy NUMERIC(10,4),
    cfo_to_np NUMERIC(10,4),
    rd_ratio_ttm NUMERIC(10,4),
    source_filing_id TEXT,
    form_type TEXT,
    currency TEXT,
    data_quality_flag TEXT,
    restatement_flag BOOLEAN,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT,
    PRIMARY KEY (symbol, report_period)
);

CREATE TABLE IF NOT EXISTS ods.sec_filing_document_raw (
    filing_id TEXT PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    cik TEXT,
    accession_number TEXT,
    filing_type TEXT NOT NULL,
    filing_date DATE,
    filing_time TIMESTAMPTZ NOT NULL,
    report_period DATE,
    title TEXT NOT NULL,
    primary_document TEXT,
    filing_url TEXT,
    object_key TEXT NOT NULL,
    content_sha256 TEXT,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT
);

CREATE TABLE IF NOT EXISTS ods.security_news_article_raw (
    news_id TEXT PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    published_time TIMESTAMPTZ NOT NULL,
    updated_time TIMESTAMPTZ,
    title TEXT NOT NULL,
    summary TEXT,
    article_url TEXT,
    language TEXT,
    author TEXT,
    publisher_name TEXT,
    publisher_homepage TEXT,
    primary_symbol TEXT,
    related_symbols JSONB,
    object_key TEXT NOT NULL,
    content_sha256 TEXT,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT
);

CREATE TABLE IF NOT EXISTS ods.security_institutional_activity_raw (
    activity_id TEXT PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    activity_time TIMESTAMPTZ NOT NULL,
    activity_type TEXT NOT NULL,
    report_period DATE,
    filing_date DATE,
    title TEXT NOT NULL,
    manager_symbol TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    manager_cik TEXT,
    filing_id TEXT NOT NULL,
    filing_type TEXT NOT NULL,
    position_value_usd NUMERIC(18,2),
    position_shares NUMERIC(18,2),
    source_url TEXT,
    object_key TEXT NOT NULL,
    content_sha256 TEXT,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT
);

CREATE TABLE IF NOT EXISTS ods.us_analyst_estimate_raw (
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    fiscal_year_offset INTEGER,
    period_label TEXT,
    revenue_estimate NUMERIC(18,2),
    eps_estimate NUMERIC(18,4),
    analyst_count INTEGER,
    currency TEXT,
    request_status TEXT,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT,
    PRIMARY KEY (symbol, snapshot_date, fiscal_year_offset)
);

CREATE TABLE IF NOT EXISTS ods.us_earnings_calendar_raw (
    event_id TEXT PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    earnings_date DATE,
    fiscal_period TEXT,
    time_of_day TEXT,
    eps_estimate NUMERIC(18,4),
    revenue_estimate NUMERIC(18,2),
    currency TEXT,
    request_status TEXT,
    source_vendor TEXT NOT NULL,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL,
    payload_hash TEXT
);

CREATE TABLE IF NOT EXISTS ods.user_watch_action_raw (
    action_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    action_time TIMESTAMPTZ NOT NULL,
    action_source TEXT,
    trigger_scene TEXT,
    session_id TEXT,
    device_id TEXT,
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS dwd.security_market_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(18,4),
    high NUMERIC(18,4),
    low NUMERIC(18,4),
    close NUMERIC(18,4),
    adj_close NUMERIC(18,4),
    volume BIGINT,
    return_1d NUMERIC(18,6),
    return_5d NUMERIC(18,6),
    distance_from_recent_high NUMERIC(18,6),
    market_cap NUMERIC(18,2),
    ps_ttm NUMERIC(18,4),
    pe_ttm NUMERIC(18,4),
    pb NUMERIC(18,4),
    turnover_rate NUMERIC(18,4),
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dwd.security_price_technical_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(18,4),
    high_52w NUMERIC(18,4),
    low_52w NUMERIC(18,4),
    position_52w NUMERIC(10,4),
    ma20 NUMERIC(18,4),
    ma60 NUMERIC(18,4),
    ma120 NUMERIC(18,4),
    ma250 NUMERIC(18,4),
    atr14 NUMERIC(18,4),
    volatility20 NUMERIC(18,6),
    support_level NUMERIC(18,4),
    resistance_level NUMERIC(18,4),
    volume_price_low NUMERIC(18,4),
    volume_price_high NUMERIC(18,4),
    valuation_percentile NUMERIC(10,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dwd.security_financial_quarterly (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    report_period DATE NOT NULL,
    revenue NUMERIC(18,2),
    revenue_yoy NUMERIC(10,4),
    netprofit_yoy NUMERIC(10,4),
    gross_margin NUMERIC(10,4),
    op_margin NUMERIC(10,4),
    fcf_margin NUMERIC(10,4),
    cfo_to_np NUMERIC(10,4),
    rd_ratio_ttm NUMERIC(10,4),
    cash NUMERIC(18,2),
    debt NUMERIC(18,2),
    net_cash NUMERIC(18,2),
    shares_outstanding NUMERIC(18,2),
    PRIMARY KEY (security_id, report_period)
);

CREATE TABLE IF NOT EXISTS dwd.security_estimate_current (
    security_id INTEGER PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    fy1_revenue_estimate NUMERIC(18,2),
    fy2_revenue_estimate NUMERIC(18,2),
    fy1_eps NUMERIC(18,4),
    fy2_eps NUMERIC(18,4),
    fy1_analyst_count INTEGER,
    fy2_analyst_count INTEGER,
    currency TEXT,
    data_quality_flag TEXT NOT NULL,
    source_vendor TEXT,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dwd.security_earnings_calendar_current (
    security_id INTEGER PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    next_earnings_date DATE,
    days_to_earnings INTEGER,
    fiscal_period TEXT,
    time_of_day TEXT,
    eps_estimate NUMERIC(18,4),
    revenue_estimate NUMERIC(18,2),
    currency TEXT,
    data_quality_flag TEXT NOT NULL,
    source_vendor TEXT,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dwd.security_event_timeline (
    event_id TEXT PRIMARY KEY,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    importance INTEGER NOT NULL,
    object_key TEXT NOT NULL,
    theme_tags JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS dwd.security_document_signal (
    signal_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES dwd.security_event_timeline(event_id),
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    risk_tags JSONB NOT NULL,
    theme_tags JSONB NOT NULL,
    evidence_path TEXT NOT NULL,
    positive_hits INTEGER NOT NULL,
    negative_hits INTEGER NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dwd.user_watchlist_state_current (
    user_id TEXT NOT NULL,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,
    latest_action_time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, security_id)
);

CREATE TABLE IF NOT EXISTS dwd.user_alert_rule_current (
    rule_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    rule_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dwd.user_event_monitor_event_current (
    monitor_event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    due_at DATE,
    priority TEXT NOT NULL,
    evidence_grade TEXT NOT NULL,
    confidence TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL,
    matched_rule TEXT NOT NULL,
    asset_relevance TEXT NOT NULL,
    event_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    structure_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    invalidation_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_event_monitor_market_time
ON dwd.user_event_monitor_event_current (user_id, market, event_time);

CREATE TABLE IF NOT EXISTS dwd.user_research_report_current (
    report_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    title TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, market, symbol)
);

CREATE TABLE IF NOT EXISTS dwd.user_discover_candidate_current (
    user_id TEXT NOT NULL,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    company_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    stage TEXT NOT NULL DEFAULT 'discovery',
    theme TEXT NOT NULL DEFAULT 'Manual',
    thesis TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    score NUMERIC(10,2) NOT NULL DEFAULT 55,
    status TEXT NOT NULL DEFAULT 'active',
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, market, symbol)
);

CREATE TABLE IF NOT EXISTS dws.security_feature_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    revenue_yoy NUMERIC(10,4),
    netprofit_yoy NUMERIC(10,4),
    op_margin NUMERIC(10,4),
    fcf_margin NUMERIC(10,4),
    cfo_to_np NUMERIC(10,4),
    rd_ratio_ttm NUMERIC(10,4),
    return_1d NUMERIC(18,6),
    return_5d NUMERIC(18,6),
    distance_from_recent_high NUMERIC(18,6),
    ps_ttm NUMERIC(18,4),
    pe_ttm NUMERIC(18,4),
    pb NUMERIC(18,4),
    turnover_rate NUMERIC(18,4),
    risk_count INTEGER NOT NULL,
    negative_event_count INTEGER NOT NULL,
    theme_count INTEGER NOT NULL,
    positive_signal_count INTEGER NOT NULL,
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dws.security_score_component_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    growth_score NUMERIC(10,2),
    quality_score NUMERIC(10,2),
    momentum_score NUMERIC(10,2),
    valuation_score NUMERIC(10,2),
    size_score NUMERIC(10,2),
    evidence_score NUMERIC(10,2),
    risk_score NUMERIC(10,2),
    theme_score NUMERIC(10,2),
    industry_prosperity_score NUMERIC(10,2),
    leader_position_score NUMERIC(10,2),
    financial_acceleration_score NUMERIC(10,2),
    cashflow_quality_score NUMERIC(10,2),
    moat_score NUMERIC(10,2),
    valuation_chip_score NUMERIC(10,2),
    total_score NUMERIC(10,2),
    stage TEXT NOT NULL,
    score_change_reason TEXT NOT NULL,
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dws.theme_heat_daily (
    theme_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    trade_date DATE NOT NULL,
    theme_name TEXT NOT NULL,
    heat_score NUMERIC(10,2) NOT NULL,
    status TEXT NOT NULL,
    symbol_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    leader_symbols JSONB NOT NULL,
    PRIMARY KEY (theme_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dws.security_candidate_rank_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    total_score NUMERIC(10,2) NOT NULL,
    stage TEXT NOT NULL,
    rank_no INTEGER NOT NULL,
    entry_reason TEXT NOT NULL,
    risk_tags JSONB NOT NULL,
    theme_tags JSONB NOT NULL,
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS dws.security_target_range_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    scenario TEXT NOT NULL,
    horizon TEXT NOT NULL,
    target_low NUMERIC(18,4),
    target_high NUMERIC(18,4),
    target_mid NUMERIC(18,4),
    upside_pct_mid NUMERIC(18,6),
    method TEXT NOT NULL,
    confidence TEXT NOT NULL,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (security_id, trade_date, scenario, horizon)
);

CREATE TABLE IF NOT EXISTS dws.security_key_level_daily (
    level_id TEXT PRIMARY KEY,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    level_type TEXT NOT NULL,
    level_low NUMERIC(18,4),
    level_high NUMERIC(18,4),
    strength TEXT NOT NULL,
    distance_pct NUMERIC(18,6),
    source TEXT NOT NULL,
    note TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dws.security_scenario_path_daily (
    path_id TEXT PRIMARY KEY,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    path_name TEXT NOT NULL,
    probability INTEGER NOT NULL,
    confidence TEXT NOT NULL,
    trigger TEXT NOT NULL,
    target_scenario TEXT NOT NULL,
    invalidation TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ads.candidate_pool_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    rank_no INTEGER NOT NULL,
    total_score NUMERIC(10,2) NOT NULL,
    stage TEXT NOT NULL,
    reason_summary TEXT NOT NULL,
    risk_tags JSONB NOT NULL,
    theme_tags JSONB NOT NULL,
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS ads.research_card_current (
    security_id INTEGER PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    thesis TEXT NOT NULL,
    key_points JSONB NOT NULL,
    risk_points JSONB NOT NULL,
    next_watch_items JSONB NOT NULL,
    evidence_refs JSONB NOT NULL,
    stage TEXT NOT NULL,
    total_score NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS ads.price_map_current (
    security_id INTEGER PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    current_price NUMERIC(18,4),
    posture TEXT NOT NULL,
    posture_label TEXT NOT NULL,
    confidence TEXT NOT NULL,
    base_target JSONB NOT NULL,
    bull_target JSONB NOT NULL,
    bear_zone JSONB NOT NULL,
    key_levels JSONB NOT NULL DEFAULT '[]'::jsonb,
    scenario_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
    invalidation_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ads.price_map_history_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    current_price NUMERIC(18,4),
    confidence TEXT NOT NULL,
    method TEXT NOT NULL,
    base_target JSONB NOT NULL,
    bull_target JSONB NOT NULL,
    bear_zone JSONB NOT NULL,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (security_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS ads.price_map_hit_review_daily (
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    review_date DATE NOT NULL,
    horizon_days INTEGER NOT NULL,
    base_hit BOOLEAN,
    bull_hit BOOLEAN,
    bear_breached BOOLEAN,
    max_close NUMERIC(18,4),
    min_close NUMERIC(18,4),
    base_target_mid NUMERIC(18,4),
    bull_target_low NUMERIC(18,4),
    bear_zone_high NUMERIC(18,4),
    hit_summary TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (security_id, snapshot_date, review_date)
);

CREATE TABLE IF NOT EXISTS ads.watchlist_alert_daily (
    alert_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    alert_message TEXT NOT NULL,
    evidence_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ads.theme_radar_daily (
    theme_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    trade_date DATE NOT NULL,
    theme_name TEXT NOT NULL,
    heat_score NUMERIC(10,2) NOT NULL,
    status TEXT NOT NULL,
    key_drivers JSONB NOT NULL,
    representative_symbols JSONB NOT NULL,
    PRIMARY KEY (theme_id, trade_date)
);
"""

DROP_AND_RECREATE_SQL = """
DROP SCHEMA IF EXISTS ads CASCADE;
DROP SCHEMA IF EXISTS dws CASCADE;
DROP SCHEMA IF EXISTS dwd CASCADE;
DROP SCHEMA IF EXISTS dim CASCADE;
DROP SCHEMA IF EXISTS ods CASCADE;
"""

FACTOR_DEFINITIONS = [
    ("growth_score", "growth", "营收同比与成长加速度", "v1"),
    ("quality_score", "quality", "经营利润率与自由现金流质量", "v1"),
    ("momentum_score", "momentum", "5日 setup 与近期高点拥挤度", "v1"),
    ("valuation_score", "valuation", "PS TTM 赔率约束", "v1"),
    ("size_score", "size", "市值弹性与十倍股赔率", "v1"),
    ("evidence_score", "evidence", "主题覆盖与正向验证强度", "v1"),
    ("risk_score", "risk", "风险标签与负面事件扣分", "v1"),
    ("theme_score", "theme", "主题暴露与主线相关性", "v1"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _enrich_financial_rows(data_dir: Path, financials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_path = data_dir / "sec_companyfacts_raw.json"
    if not raw_path.exists():
        return financials

    raw_rows = _read_json(raw_path)
    companyfacts_by_symbol = {
        _safe_str(row.get("symbol")): row.get("raw_payload")
        for row in raw_rows
        if isinstance(row, dict) and isinstance(row.get("raw_payload"), dict)
    }

    enriched: list[dict[str, Any]] = []
    for row in financials:
        symbol = _safe_str(row.get("symbol"))
        if not symbol:
            enriched.append(row)
            continue
        if row.get("filed_date") and row.get("source_filing_id") and row.get("form_type"):
            enriched.append(row)
            continue
        companyfacts = companyfacts_by_symbol.get(symbol)
        if not isinstance(companyfacts, dict):
            enriched.append(row)
            continue
        snapshot = build_financial_snapshot_from_sec(
            symbol,
            companyfacts,
            shares_outstanding_fallback=_safe_float(row.get("shares_outstanding")),
        )
        if snapshot is None:
            enriched.append(row)
            continue
        merged = dict(row)
        merged.update(
            {
                "fiscal_year": _coalesce(row.get("fiscal_year"), snapshot.fiscal_year),
                "period_type": _coalesce(row.get("period_type"), snapshot.period_type),
                "filed_date": _coalesce(row.get("filed_date"), snapshot.filed_date),
                "source_filing_id": _coalesce(row.get("source_filing_id"), snapshot.source_filing_id),
                "form_type": _coalesce(row.get("form_type"), snapshot.form_type),
                "currency": _coalesce(row.get("currency"), snapshot.currency),
                "data_quality_flag": _coalesce(row.get("data_quality_flag"), snapshot.data_quality_flag),
                "restatement_flag": _coalesce(row.get("restatement_flag"), snapshot.restatement_flag),
            }
        )
        enriched.append(merged)
    return enriched


def _enrich_news_rows(data_dir: Path, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_path = data_dir / "polygon_news_raw.json"
    if not raw_path.exists():
        return news_items

    raw_rows = _read_json(raw_path)
    raw_by_news_id = {
        _safe_str(row.get("news_id")): row.get("raw_payload")
        for row in raw_rows
        if isinstance(row, dict) and isinstance(row.get("raw_payload"), dict)
    }

    enriched: list[dict[str, Any]] = []
    for row in news_items:
        news_id = _safe_str(row.get("news_id"))
        payload = raw_by_news_id.get(news_id)
        if not isinstance(payload, dict):
            enriched.append(row)
            continue
        publisher = payload.get("publisher") if isinstance(payload.get("publisher"), dict) else {}
        merged = dict(row)
        merged.update(
            {
                "updated_time": _coalesce(row.get("updated_time"), payload.get("updated_utc")),
                "summary": _coalesce(row.get("summary"), payload.get("description"), row.get("content")),
                "article_url": _coalesce(row.get("article_url"), payload.get("article_url")),
                "language": _coalesce(row.get("language"), payload.get("language"), "en"),
                "author": _coalesce(row.get("author"), payload.get("author")),
                "publisher_name": _coalesce(row.get("publisher_name"), publisher.get("name")),
                "publisher_homepage": _coalesce(row.get("publisher_homepage"), publisher.get("homepage_url")),
                "primary_symbol": _coalesce(row.get("primary_symbol"), row.get("symbol")),
                "related_symbols": _coalesce(row.get("related_symbols"), payload.get("tickers"), [row.get("symbol")]),
                "raw_payload": payload,
            }
        )
        enriched.append(merged)
    return enriched


def _blank_to_none(value: Any) -> Any:
    return None if value == "" else value


def _json(value: Any) -> Jsonb:
    return Jsonb(_sanitize_for_json(value))


def _json_or_none(value: Any) -> Jsonb | None:
    return _json(value) if value is not None else None


def _today_iso_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _row_get(row: dict[str, Any] | Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, dict) and "raw" in value:
        value = value.get("raw")
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
        value = value.strip()
        return value or None
    return str(value)


def _normalize_date(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) >= 10:
            candidate = text[:10]
            try:
                datetime.strptime(candidate, "%Y-%m-%d")
                return candidate
            except ValueError:
                return text
    return value


def _normalize_timestamp(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(microsecond=0)
    return value


def _safe_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _normalize_json_list(value: Any) -> list[str] | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    if isinstance(value, tuple):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("[") and text.endswith("]"):
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, list):
                normalized = [str(item).strip() for item in loaded if str(item).strip()]
                return normalized or None
        normalized = [part.strip() for part in text.split(",") if part.strip()]
        return normalized or None
    return [str(value).strip()] if str(value).strip() else None


def _canonical_json_blob(value: Any) -> bytes:
    return json.dumps(_sanitize_for_json(value), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _payload_hash(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(_canonical_json_blob(value)).hexdigest()


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _nested_number(value: Any) -> float | None:
    if isinstance(value, dict) and "raw" in value:
        value = value.get("raw")
    return _blank_to_none(value)


def _infer_period_type(label: Any) -> str | None:
    text = _safe_str(label)
    if text is None:
        return None
    lowered = text.lower()
    if "q" in lowered:
        return "quarterly"
    if "y" in lowered or "annual" in lowered or "fy" in lowered:
        return "annual"
    return None


ODS_SCHEMA_SYNC_SQL = """
DROP TABLE IF EXISTS ods.security_corporate_action_polygon_raw CASCADE;
DROP TABLE IF EXISTS ods.macro_fred_observation_raw CASCADE;
DROP TABLE IF EXISTS ods.macro_fred_series_raw CASCADE;
DROP TABLE IF EXISTS ods.user_feedback_raw CASCADE;
DROP TABLE IF EXISTS ods.security_analyst_estimate_item_raw CASCADE;
DROP TABLE IF EXISTS ods.security_earnings_event_raw CASCADE;
DROP TABLE IF EXISTS ods.security_earnings_calendar_raw CASCADE;
DROP TABLE IF EXISTS ods.sec_companyfact_item_raw CASCADE;
DROP TABLE IF EXISTS ods.sec_submission_filing_raw CASCADE;
DROP TABLE IF EXISTS ods.sec_companyfacts_raw CASCADE;
DROP TABLE IF EXISTS ods.sec_submissions_raw CASCADE;
DROP TABLE IF EXISTS ods.security_news_polygon_raw CASCADE;
DROP TABLE IF EXISTS ods.theme_taxonomy_raw CASCADE;
DROP TABLE IF EXISTS ods.security_industry_mapping_raw CASCADE;
DROP TABLE IF EXISTS ods.security_symbol_master_raw CASCADE;
DROP TABLE IF EXISTS ods.security_ticker_overview_polygon_raw CASCADE;
DROP TABLE IF EXISTS ods.security_analyst_estimate_raw CASCADE;
DROP TABLE IF EXISTS dwd.security_estimate_revision_daily CASCADE;

ALTER TABLE IF EXISTS ods.us_equity_price_daily_raw ADD COLUMN IF NOT EXISTS currency TEXT;
ALTER TABLE IF EXISTS ods.us_equity_price_daily_raw ADD COLUMN IF NOT EXISTS market_status TEXT;
ALTER TABLE IF EXISTS ods.us_equity_price_daily_raw ADD COLUMN IF NOT EXISTS source_event_time TIMESTAMPTZ;
ALTER TABLE IF EXISTS ods.us_equity_price_daily_raw ADD COLUMN IF NOT EXISTS payload_hash TEXT;
ALTER TABLE IF EXISTS ods.us_equity_price_daily_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';

ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS fiscal_year INTEGER;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS period_type TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS filed_date DATE;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS source_filing_id TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS form_type TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS currency TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS data_quality_flag TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS restatement_flag BOOLEAN;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS payload_hash TEXT;
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS netprofit_yoy NUMERIC(10,4);
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS cfo_to_np NUMERIC(10,4);
ALTER TABLE IF EXISTS ods.security_financial_statement_raw ADD COLUMN IF NOT EXISTS rd_ratio_ttm NUMERIC(10,4);

ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS cik TEXT;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS accession_number TEXT;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS filing_date DATE;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS report_period DATE;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS primary_document TEXT;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS filing_url TEXT;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS content_sha256 TEXT;
ALTER TABLE IF EXISTS ods.sec_filing_document_raw ADD COLUMN IF NOT EXISTS payload_hash TEXT;

ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS updated_time TIMESTAMPTZ;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS article_url TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS author TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS publisher_name TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS publisher_homepage TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS primary_symbol TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS related_symbols JSONB;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS content_sha256 TEXT;
ALTER TABLE IF EXISTS ods.security_news_article_raw ADD COLUMN IF NOT EXISTS payload_hash TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS report_period DATE;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS filing_date DATE;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS manager_symbol TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS manager_name TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS manager_cik TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS filing_id TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS filing_type TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS position_value_usd NUMERIC(18,2);
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS position_shares NUMERIC(18,2);
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS content_sha256 TEXT;
ALTER TABLE IF EXISTS ods.security_institutional_activity_raw ADD COLUMN IF NOT EXISTS payload_hash TEXT;

ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS action_source TEXT;
ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS trigger_scene TEXT;
ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS session_id TEXT;
ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS device_id TEXT;
ALTER TABLE IF EXISTS ods.user_watch_action_raw ADD COLUMN IF NOT EXISTS ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE IF EXISTS dim.security ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dim.security ADD COLUMN IF NOT EXISTS listed_date DATE;

ALTER TABLE IF EXISTS dwd.security_market_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dwd.security_market_daily ADD COLUMN IF NOT EXISTS pe_ttm NUMERIC(18,4);
ALTER TABLE IF EXISTS dwd.security_market_daily ADD COLUMN IF NOT EXISTS pb NUMERIC(18,4);
ALTER TABLE IF EXISTS dwd.security_market_daily ADD COLUMN IF NOT EXISTS turnover_rate NUMERIC(18,4);

ALTER TABLE IF EXISTS dwd.security_financial_quarterly ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dwd.security_financial_quarterly ADD COLUMN IF NOT EXISTS netprofit_yoy NUMERIC(10,4);
ALTER TABLE IF EXISTS dwd.security_financial_quarterly ADD COLUMN IF NOT EXISTS cfo_to_np NUMERIC(10,4);
ALTER TABLE IF EXISTS dwd.security_financial_quarterly ADD COLUMN IF NOT EXISTS rd_ratio_ttm NUMERIC(10,4);

ALTER TABLE IF EXISTS dwd.security_event_timeline ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dwd.security_document_signal ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dwd.user_watchlist_state_current ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';

CREATE TABLE IF NOT EXISTS dwd.user_alert_rule_current (
    rule_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    rule_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dwd.user_event_monitor_event_current (
    monitor_event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    due_at DATE,
    priority TEXT NOT NULL,
    evidence_grade TEXT NOT NULL,
    confidence TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL,
    matched_rule TEXT NOT NULL,
    asset_relevance TEXT NOT NULL,
    event_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    structure_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
    invalidation_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_event_monitor_market_time
ON dwd.user_event_monitor_event_current (user_id, market, event_time);

ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS netprofit_yoy NUMERIC(10,4);
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS cfo_to_np NUMERIC(10,4);
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS rd_ratio_ttm NUMERIC(10,4);
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS pe_ttm NUMERIC(18,4);
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS pb NUMERIC(18,4);
ALTER TABLE IF EXISTS dws.security_feature_daily ADD COLUMN IF NOT EXISTS turnover_rate NUMERIC(18,4);

ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS industry_prosperity_score NUMERIC(10,2);
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS leader_position_score NUMERIC(10,2);
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS financial_acceleration_score NUMERIC(10,2);
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS cashflow_quality_score NUMERIC(10,2);
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS moat_score NUMERIC(10,2);
ALTER TABLE IF EXISTS dws.security_score_component_daily ADD COLUMN IF NOT EXISTS valuation_chip_score NUMERIC(10,2);

ALTER TABLE IF EXISTS dws.theme_heat_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS dws.security_candidate_rank_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';

ALTER TABLE IF EXISTS ads.candidate_pool_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ads.research_card_current ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ads.watchlist_alert_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
ALTER TABLE IF EXISTS ads.theme_radar_daily ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'US';
"""


def ensure_schema(settings: Settings) -> None:
    with connect(settings) as conn:
        conn.execute(SCHEMA_SQL)
        conn.execute(OPTION_CHAIN_SCHEMA_SQL)
        _sync_existing_ods_schema(conn, settings)


def reset_all(settings: Settings) -> None:
    ensure_schema(settings)
    with connect(settings) as conn:
        conn.execute(DROP_AND_RECREATE_SQL)
        conn.execute(SCHEMA_SQL)
        conn.execute(OPTION_CHAIN_SCHEMA_SQL)


def _clear_market_data(conn, market: str) -> None:
    conn.execute("DELETE FROM ads.price_map_hit_review_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.price_map_history_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.price_map_current WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.watchlist_alert_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.theme_radar_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.candidate_pool_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ads.research_card_current WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_scenario_path_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_key_level_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_target_range_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.theme_heat_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_candidate_rank_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_score_component_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dws.security_feature_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_price_technical_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_earnings_calendar_current WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_estimate_current WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_document_signal WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_event_timeline WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_financial_quarterly WHERE market = %s", (market,))
    conn.execute("DELETE FROM dwd.security_market_daily WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.security_institutional_activity_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.us_earnings_calendar_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.us_analyst_estimate_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.security_news_article_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.sec_filing_document_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.security_financial_statement_raw WHERE market = %s", (market,))
    conn.execute("DELETE FROM ods.us_equity_price_daily_raw WHERE market = %s", (market,))
    conn.execute(
        """
        DELETE FROM dim.security_theme
        WHERE security_id IN (SELECT security_id FROM dim.security WHERE market = %s)
        """,
        (market,),
    )
    conn.execute("DELETE FROM dim.security WHERE market = %s", (market,))


def _seed_common_dimensions(conn, trade_dates: list[str]) -> None:
    for theme_id, theme_name in THEME_CATALOG.items():
        conn.execute(
            """
            INSERT INTO dim.theme (theme_id, theme_name, parent_theme, active_flag)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (theme_id) DO UPDATE SET
                theme_name = EXCLUDED.theme_name,
                parent_theme = EXCLUDED.parent_theme,
                active_flag = EXCLUDED.active_flag
            """,
            (theme_id, theme_name, "Growth Tech", True),
        )

    for trade_date in sorted(set(trade_dates)):
        conn.execute(
            """
            INSERT INTO dim.calendar (trade_date, week_of_year, month_of_year, quarter_of_year)
            SELECT %s::date,
                   EXTRACT(WEEK FROM %s::date)::int,
                   EXTRACT(MONTH FROM %s::date)::int,
                   EXTRACT(QUARTER FROM %s::date)::int
            ON CONFLICT (trade_date) DO NOTHING
            """,
            (trade_date, trade_date, trade_date, trade_date),
        )

    for factor_name, category, description, version in FACTOR_DEFINITIONS:
        conn.execute(
            """
            INSERT INTO dim.factor_definition (factor_name, category, description, version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (factor_name) DO UPDATE SET
                category = EXCLUDED.category,
                description = EXCLUDED.description,
                version = EXCLUDED.version
            """,
            (factor_name, category, description, version),
        )


def _seed_theme_dimensions(conn, themes: list[tuple[str, str]]) -> None:
    for theme_id, theme_name in themes:
        conn.execute(
            """
            INSERT INTO dim.theme (theme_id, theme_name, parent_theme, active_flag)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (theme_id) DO UPDATE SET
                theme_name = EXCLUDED.theme_name,
                parent_theme = EXCLUDED.parent_theme,
                active_flag = EXCLUDED.active_flag
            """,
            (theme_id, theme_name, "TenX Hunter", True),
        )


def _insert_security_rows(conn, securities: list[dict[str, Any] | Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, item in enumerate(securities, start=1):
        security_id = int(_coalesce(_safe_int(_row_get(item, "security_id")), idx))
        market = _coalesce(_safe_str(_row_get(item, "market")), "US")
        symbol = _row_get(item, "symbol")
        company_name = _row_get(item, "company_name")
        exchange_name = _row_get(item, "exchange_name")
        cik = _row_get(item, "cik")
        currency = _row_get(item, "currency")
        listing_status = _coalesce(_row_get(item, "listing_status"), "active")
        sector = _row_get(item, "sector")
        industry = _row_get(item, "industry")
        listed_date = _normalize_date(_row_get(item, "listed_date"))
        conn.execute(
            """
            INSERT INTO dim.security (
                security_id, market, symbol, company_name, exchange_name, cik, currency,
                listing_status, sector, industry, listed_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (security_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                company_name = EXCLUDED.company_name,
                exchange_name = EXCLUDED.exchange_name,
                cik = EXCLUDED.cik,
                currency = EXCLUDED.currency,
                listing_status = EXCLUDED.listing_status,
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                listed_date = EXCLUDED.listed_date
            """,
            (security_id, market, symbol, company_name, exchange_name, cik, currency, listing_status, sector, industry, listed_date),
        )
        mapping[symbol] = security_id
    return mapping


def _insert_security_theme_rows(conn, security_themes: list[dict[str, str]], symbol_to_id: dict[str, int]) -> None:
    for row in security_themes:
        security_id = row.get("security_id")
        if not security_id and row.get("symbol"):
            security_id = symbol_to_id.get(row["symbol"])
        conn.execute(
            """
            INSERT INTO dim.security_theme (security_id, theme_id, source_note)
            VALUES (%s, %s, %s)
            ON CONFLICT (security_id, theme_id) DO UPDATE SET source_note = EXCLUDED.source_note
            """,
            (int(security_id), row["theme_id"], row.get("source_note")),
        )


def _insert_price_rows(conn, prices: list[Any]) -> None:
    for row in prices:
        payload = _row_get(row, "raw_payload") or (dict(row) if isinstance(row, dict) else dict(getattr(row, "__dict__", {})))
        conn.execute(
            """
            INSERT INTO ods.us_equity_price_daily_raw (
                market, symbol, trade_date, open, high, low, close, adj_close, volume,
                currency, market_status, source_event_time, source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, trade_date) DO UPDATE SET
                market = EXCLUDED.market,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                adj_close = EXCLUDED.adj_close,
                volume = EXCLUDED.volume,
                currency = EXCLUDED.currency,
                market_status = EXCLUDED.market_status,
                source_event_time = EXCLUDED.source_event_time,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _row_get(row, "trade_date"),
                _blank_to_none(_row_get(row, "open")),
                _blank_to_none(_row_get(row, "high")),
                _blank_to_none(_row_get(row, "low")),
                _blank_to_none(_row_get(row, "close")),
                _blank_to_none(_row_get(row, "adj_close")),
                _blank_to_none(_row_get(row, "volume")),
                _coalesce(_safe_str(payload.get("currency")) if isinstance(payload, dict) else None, _safe_str(_row_get(row, "currency")), "USD"),
                _coalesce(_safe_str(payload.get("market_status")) if isinstance(payload, dict) else None, _safe_str(_row_get(row, "market_status")), "closed"),
                _normalize_timestamp(_coalesce(_row_get(row, "source_event_time"), payload.get("source_event_time") if isinstance(payload, dict) else None, payload.get("timestamp") if isinstance(payload, dict) else None)),
                _coalesce(_row_get(row, "source_vendor"), "market-data"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_financial_rows(conn, financials: list[Any]) -> None:
    for row in financials:
        payload = _row_get(row, "raw_payload") or (dict(row) if isinstance(row, dict) else dict(getattr(row, "__dict__", {})))
        revenue_fact = payload.get("revenue_fact") if isinstance(payload, dict) else {}
        revenue_fact = revenue_fact if isinstance(revenue_fact, dict) else {}
        conn.execute(
            """
            INSERT INTO ods.security_financial_statement_raw (
                market, symbol, report_period, fiscal_quarter, fiscal_year, period_type,
                filed_date, revenue, gross_margin, op_margin, fcf_margin,
                cash, debt, shares_outstanding, revenue_yoy, netprofit_yoy, cfo_to_np, rd_ratio_ttm, source_filing_id,
                form_type, currency, data_quality_flag, restatement_flag,
                source_vendor, raw_payload, payload_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (symbol, report_period) DO UPDATE SET
                market = EXCLUDED.market,
                fiscal_quarter = EXCLUDED.fiscal_quarter,
                fiscal_year = EXCLUDED.fiscal_year,
                period_type = EXCLUDED.period_type,
                filed_date = EXCLUDED.filed_date,
                revenue = EXCLUDED.revenue,
                gross_margin = EXCLUDED.gross_margin,
                op_margin = EXCLUDED.op_margin,
                fcf_margin = EXCLUDED.fcf_margin,
                cash = EXCLUDED.cash,
                debt = EXCLUDED.debt,
                shares_outstanding = EXCLUDED.shares_outstanding,
                revenue_yoy = EXCLUDED.revenue_yoy,
                netprofit_yoy = EXCLUDED.netprofit_yoy,
                cfo_to_np = EXCLUDED.cfo_to_np,
                rd_ratio_ttm = EXCLUDED.rd_ratio_ttm,
                source_filing_id = EXCLUDED.source_filing_id,
                form_type = EXCLUDED.form_type,
                currency = EXCLUDED.currency,
                data_quality_flag = EXCLUDED.data_quality_flag,
                restatement_flag = EXCLUDED.restatement_flag,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _normalize_date(_row_get(row, "report_period")),
                _row_get(row, "fiscal_quarter"),
                _coalesce(_safe_int(revenue_fact.get("fy")), _safe_int(_row_get(row, "fiscal_year"))),
                _coalesce(_safe_str(_row_get(row, "period_type")), _safe_str(revenue_fact.get("fp")), _infer_period_type(_row_get(row, "fiscal_quarter"))),
                _normalize_date(_coalesce(_row_get(row, "filed_date"), revenue_fact.get("filed"))),
                _blank_to_none(_row_get(row, "revenue")),
                _blank_to_none(_row_get(row, "gross_margin")),
                _blank_to_none(_row_get(row, "op_margin")),
                _blank_to_none(_row_get(row, "fcf_margin")),
                _blank_to_none(_row_get(row, "cash")),
                _blank_to_none(_row_get(row, "debt")),
                _blank_to_none(_row_get(row, "shares_outstanding")),
                _blank_to_none(_row_get(row, "revenue_yoy")),
                _blank_to_none(_row_get(row, "netprofit_yoy")),
                _blank_to_none(_row_get(row, "cfo_to_np")),
                _blank_to_none(_row_get(row, "rd_ratio_ttm")),
                _coalesce(_safe_str(_row_get(row, "source_filing_id")), _safe_str(revenue_fact.get("accn"))),
                _coalesce(_safe_str(_row_get(row, "form_type")), _safe_str(revenue_fact.get("form"))),
                _coalesce(_safe_str(_row_get(row, "currency")), _safe_str(revenue_fact.get("unit")), "USD"),
                _coalesce(_safe_str(_row_get(row, "data_quality_flag")), "parsed" if _row_get(row, "revenue") not in (None, "") else "missing_revenue"),
                _coalesce(_safe_bool(_row_get(row, "restatement_flag")), _safe_bool(revenue_fact.get("restated"))),
                _coalesce(_row_get(row, "source_vendor"), "sec-companyfacts"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_estimate_rows(conn, estimates: list[Any]) -> None:
    for row in estimates:
        payload = _row_get(row, "raw_payload") or (dict(row) if isinstance(row, dict) else dict(getattr(row, "__dict__", {})))
        fiscal_year_offset = _safe_int(_coalesce(_row_get(row, "fiscal_year_offset"), payload.get("fiscalYearOffset") if isinstance(payload, dict) else None))
        if fiscal_year_offset is None:
            fiscal_year_offset = 2 if _safe_str(_row_get(row, "period_label")) == "+1y" else 1
        conn.execute(
            """
            INSERT INTO ods.us_analyst_estimate_raw (
                market, symbol, snapshot_date, fiscal_year_offset, period_label,
                revenue_estimate, eps_estimate, analyst_count, currency,
                request_status, source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, snapshot_date, fiscal_year_offset) DO UPDATE SET
                market = EXCLUDED.market,
                period_label = EXCLUDED.period_label,
                revenue_estimate = EXCLUDED.revenue_estimate,
                eps_estimate = EXCLUDED.eps_estimate,
                analyst_count = EXCLUDED.analyst_count,
                currency = EXCLUDED.currency,
                request_status = EXCLUDED.request_status,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _normalize_date(_row_get(row, "snapshot_date")),
                fiscal_year_offset,
                _safe_str(_row_get(row, "period_label")),
                _blank_to_none(_coalesce(_row_get(row, "next_year_revenue_estimate"), _row_get(row, "revenue_estimate"))),
                _blank_to_none(_coalesce(_row_get(row, "next_year_eps"), _row_get(row, "eps_estimate"))),
                _blank_to_none(_row_get(row, "analyst_count")),
                _coalesce(_safe_str(_row_get(row, "currency")), "USD"),
                _coalesce(_safe_str(_row_get(row, "request_status")), "unknown"),
                _coalesce(_row_get(row, "source_vendor"), "analyst-estimate"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_earnings_calendar_rows(conn, earnings_calendar: list[Any]) -> None:
    for row in earnings_calendar:
        payload = _row_get(row, "raw_payload") or (dict(row) if isinstance(row, dict) else dict(getattr(row, "__dict__", {})))
        event_id = _coalesce(
            _safe_str(_row_get(row, "event_id")),
            f"earnings::{_row_get(row, 'symbol')}::{_normalize_date(_row_get(row, 'snapshot_date'))}",
        )
        conn.execute(
            """
            INSERT INTO ods.us_earnings_calendar_raw (
                event_id, market, symbol, snapshot_date, earnings_date, fiscal_period,
                time_of_day, eps_estimate, revenue_estimate, currency,
                request_status, source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                snapshot_date = EXCLUDED.snapshot_date,
                earnings_date = EXCLUDED.earnings_date,
                fiscal_period = EXCLUDED.fiscal_period,
                time_of_day = EXCLUDED.time_of_day,
                eps_estimate = EXCLUDED.eps_estimate,
                revenue_estimate = EXCLUDED.revenue_estimate,
                currency = EXCLUDED.currency,
                request_status = EXCLUDED.request_status,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                event_id,
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _normalize_date(_row_get(row, "snapshot_date")),
                _normalize_date(_row_get(row, "earnings_date")),
                _safe_str(_row_get(row, "fiscal_period")),
                _safe_str(_row_get(row, "time_of_day")),
                _blank_to_none(_row_get(row, "eps_estimate")),
                _blank_to_none(_row_get(row, "revenue_estimate")),
                _coalesce(_safe_str(_row_get(row, "currency")), "USD"),
                _coalesce(_safe_str(_row_get(row, "request_status")), "unknown"),
                _coalesce(_row_get(row, "source_vendor"), "earnings-calendar"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_filings_rows(conn, storage: ObjectStorage | None, filings: list[Any]) -> None:
    for row in filings:
        payload = _row_get(row, "raw_payload") or {}
        payload = payload if isinstance(payload, dict) else {}
        content = _row_get(row, "content")
        object_key = _row_get(row, "object_key")
        if object_key is None and content is not None and storage is not None:
            object_key = storage.upload_text(f"filings/{_row_get(row, 'filing_id')}.txt", content)
        if content is None and object_key is not None and storage is not None:
            try:
                content = storage.download_text(object_key)
            except Exception:
                content = None
        filing_id = _safe_str(_row_get(row, "filing_id"))
        accession_number = _coalesce(
            _safe_str(_row_get(row, "accession_number")),
            _safe_str(payload.get("accessionNumber")),
            filing_id.split("-", 1)[1] if filing_id and "-" in filing_id else None,
        )
        primary_document = _coalesce(_safe_str(_row_get(row, "primary_document")), _safe_str(payload.get("primaryDocument")))
        cik = _coalesce(_safe_str(_row_get(row, "cik")), _safe_str(payload.get("cik")))
        filing_url = _safe_str(_row_get(row, "filing_url"))
        if filing_url is None and cik and accession_number and primary_document:
            try:
                filing_url = SEC_ARCHIVES_URL.format(cik=str(int(cik)), accession=accession_number.replace("-", ""), document=primary_document)
            except (TypeError, ValueError):
                filing_url = None
        filing_date = _blank_to_none(_coalesce(_row_get(row, "filing_date"), payload.get("filingDate"), _normalize_date(_row_get(row, "filing_time"))))
        content_sha256 = _coalesce(_safe_str(_row_get(row, "content_sha256")), _sha256_text(content))
        conn.execute(
            """
            INSERT INTO ods.sec_filing_document_raw (
                filing_id, market, symbol, cik, accession_number, filing_type, filing_date,
                filing_time, report_period, title, primary_document, filing_url,
                object_key, content_sha256, source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (filing_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                cik = EXCLUDED.cik,
                accession_number = EXCLUDED.accession_number,
                filing_type = EXCLUDED.filing_type,
                filing_date = EXCLUDED.filing_date,
                filing_time = EXCLUDED.filing_time,
                report_period = EXCLUDED.report_period,
                title = EXCLUDED.title,
                primary_document = EXCLUDED.primary_document,
                filing_url = EXCLUDED.filing_url,
                object_key = EXCLUDED.object_key,
                content_sha256 = EXCLUDED.content_sha256,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                filing_id,
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                cik,
                accession_number,
                _row_get(row, "filing_type"),
                filing_date,
                _row_get(row, "filing_time"),
                _blank_to_none(_coalesce(_row_get(row, "report_period"), payload.get("reportDate"))),
                _row_get(row, "title"),
                primary_document,
                filing_url,
                object_key,
                content_sha256,
                _coalesce(_row_get(row, "source_vendor"), "sec-edgar"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_news_rows(conn, storage: ObjectStorage | None, news_items: list[Any]) -> None:
    for row in news_items:
        payload = _row_get(row, "raw_payload") or {}
        payload = payload if isinstance(payload, dict) else {}
        content = _row_get(row, "content")
        object_key = _row_get(row, "object_key")
        if object_key is None and content is not None and storage is not None:
            object_key = storage.upload_text(f"news/{_row_get(row, 'news_id')}.txt", content)
        if content is None and object_key is not None and storage is not None:
            try:
                content = storage.download_text(object_key)
            except Exception:
                content = None
        publisher = payload.get("publisher") if isinstance(payload.get("publisher"), dict) else {}
        related_symbols = _normalize_json_list(_coalesce(payload.get("tickers"), _row_get(row, "related_symbols"), [_row_get(row, "symbol")]))
        content_sha256 = _coalesce(_safe_str(_row_get(row, "content_sha256")), _sha256_text(content))
        conn.execute(
            """
            INSERT INTO ods.security_news_article_raw (
                news_id, market, symbol, published_time, updated_time, title, summary,
                article_url, language, author, publisher_name, publisher_homepage,
                primary_symbol, related_symbols, object_key, content_sha256,
                source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (news_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                published_time = EXCLUDED.published_time,
                updated_time = EXCLUDED.updated_time,
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                article_url = EXCLUDED.article_url,
                language = EXCLUDED.language,
                author = EXCLUDED.author,
                publisher_name = EXCLUDED.publisher_name,
                publisher_homepage = EXCLUDED.publisher_homepage,
                primary_symbol = EXCLUDED.primary_symbol,
                related_symbols = EXCLUDED.related_symbols,
                object_key = EXCLUDED.object_key,
                content_sha256 = EXCLUDED.content_sha256,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                _row_get(row, "news_id"),
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _normalize_timestamp(_row_get(row, "published_time")),
                _normalize_timestamp(_coalesce(_row_get(row, "updated_time"), payload.get("updated_at"), payload.get("updated_utc"))),
                _row_get(row, "title"),
                _coalesce(_safe_str(_row_get(row, "summary")), _safe_str(payload.get("description")), _safe_str(content)),
                _coalesce(_safe_str(_row_get(row, "article_url")), _safe_str(payload.get("article_url")), _safe_str(payload.get("link"))),
                _coalesce(_safe_str(_row_get(row, "language")), _safe_str(payload.get("language"))),
                _coalesce(_safe_str(_row_get(row, "author")), _safe_str(payload.get("author")), _safe_str(payload.get("publisher"))),
                _coalesce(_safe_str(_row_get(row, "publisher_name")), _safe_str(publisher.get("name")), _safe_str(payload.get("publisher"))),
                _coalesce(_safe_str(_row_get(row, "publisher_homepage")), _safe_str(publisher.get("homepage_url"))),
                _coalesce(_safe_str(_row_get(row, "primary_symbol")), _safe_str(_row_get(row, "symbol")), (related_symbols or [None])[0]),
                _json_or_none(related_symbols),
                object_key,
                content_sha256,
                _coalesce(_row_get(row, "source_vendor"), "news-source"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_institutional_activity_rows(conn, storage: ObjectStorage | None, activities: list[Any]) -> None:
    for row in activities:
        payload = _row_get(row, "raw_payload") or {}
        payload = payload if isinstance(payload, dict) else {}
        content = _row_get(row, "content")
        object_key = _row_get(row, "object_key")
        if object_key is None and content is not None and storage is not None:
            object_key = storage.upload_text(f"institutional/{_row_get(row, 'activity_id')}.txt", content)
        if content is None and object_key is not None and storage is not None:
            try:
                content = storage.download_text(object_key)
            except Exception:
                content = None
        content_sha256 = _coalesce(_safe_str(_row_get(row, "content_sha256")), _sha256_text(content))
        conn.execute(
            """
            INSERT INTO ods.security_institutional_activity_raw (
                activity_id, market, symbol, activity_time, activity_type, report_period,
                filing_date, title, manager_symbol, manager_name, manager_cik, filing_id,
                filing_type, position_value_usd, position_shares, source_url, object_key,
                content_sha256, source_vendor, raw_payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (activity_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                activity_time = EXCLUDED.activity_time,
                activity_type = EXCLUDED.activity_type,
                report_period = EXCLUDED.report_period,
                filing_date = EXCLUDED.filing_date,
                title = EXCLUDED.title,
                manager_symbol = EXCLUDED.manager_symbol,
                manager_name = EXCLUDED.manager_name,
                manager_cik = EXCLUDED.manager_cik,
                filing_id = EXCLUDED.filing_id,
                filing_type = EXCLUDED.filing_type,
                position_value_usd = EXCLUDED.position_value_usd,
                position_shares = EXCLUDED.position_shares,
                source_url = EXCLUDED.source_url,
                object_key = EXCLUDED.object_key,
                content_sha256 = EXCLUDED.content_sha256,
                source_vendor = EXCLUDED.source_vendor,
                raw_payload = EXCLUDED.raw_payload,
                payload_hash = EXCLUDED.payload_hash
            """,
            (
                _row_get(row, "activity_id"),
                _coalesce(_safe_str(_row_get(row, "market")), "US"),
                _row_get(row, "symbol"),
                _normalize_timestamp(_row_get(row, "activity_time")),
                _coalesce(_safe_str(_row_get(row, "activity_type")), "institutional_activity"),
                _blank_to_none(_row_get(row, "report_period")),
                _blank_to_none(_row_get(row, "filing_date")),
                _row_get(row, "title"),
                _row_get(row, "manager_symbol"),
                _row_get(row, "manager_name"),
                _safe_str(_row_get(row, "manager_cik")),
                _row_get(row, "filing_id"),
                _coalesce(_safe_str(_row_get(row, "filing_type")), "13F-HR"),
                _blank_to_none(_row_get(row, "position_value_usd")),
                _blank_to_none(_row_get(row, "position_shares")),
                _safe_str(_row_get(row, "source_url")),
                object_key,
                content_sha256,
                _coalesce(_row_get(row, "source_vendor"), "institutional-source"),
                _json(payload),
                _payload_hash(payload),
            ),
        )


def _insert_watch_actions(conn, watch_actions: list[dict[str, Any] | Any]) -> None:
    for action in watch_actions:
        payload = _row_get(action, "raw_payload") or (dict(action) if isinstance(action, dict) else dict(getattr(action, "__dict__", {})))
        conn.execute(
            """
            INSERT INTO ods.user_watch_action_raw (
                action_id, user_id, market, symbol, action, action_time,
                action_source, trigger_scene, session_id, device_id, raw_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (action_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                action = EXCLUDED.action,
                action_time = EXCLUDED.action_time,
                action_source = EXCLUDED.action_source,
                trigger_scene = EXCLUDED.trigger_scene,
                session_id = EXCLUDED.session_id,
                device_id = EXCLUDED.device_id,
                raw_payload = EXCLUDED.raw_payload
            """,
            (
                _row_get(action, "action_id"),
                _row_get(action, "user_id"),
                _coalesce(_safe_str(_row_get(action, "market")), "US"),
                _row_get(action, "symbol"),
                _row_get(action, "action"),
                _row_get(action, "action_time"),
                _coalesce(_safe_str(_row_get(action, "action_source")), _safe_str(payload.get("action_source"))),
                _coalesce(_safe_str(_row_get(action, "trigger_scene")), _safe_str(payload.get("trigger_scene"))),
                _coalesce(_safe_str(_row_get(action, "session_id")), _safe_str(payload.get("session_id"))),
                _coalesce(_safe_str(_row_get(action, "device_id")), _safe_str(payload.get("device_id"))),
                _json(payload),
            ),
        )


def _upsert_synthetic_signal(
    conn,
    *,
    signal_id: str,
    event_id: str,
    security_id: int,
    market: str,
    symbol: str,
    event_time: Any,
    event_type: str,
    title: str,
    summary: str,
    sentiment: str,
    importance: int,
    risk_tags: list[str] | None,
    theme_tags: list[str] | None,
    object_key: str,
) -> None:
    conn.execute(
        """
        INSERT INTO dwd.security_event_timeline (
            event_id, security_id, market, symbol, event_time, event_type, title,
            source_kind, sentiment, importance, object_key, theme_tags
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO UPDATE SET
            security_id = EXCLUDED.security_id,
            market = EXCLUDED.market,
            symbol = EXCLUDED.symbol,
            event_time = EXCLUDED.event_time,
            event_type = EXCLUDED.event_type,
            title = EXCLUDED.title,
            source_kind = EXCLUDED.source_kind,
            sentiment = EXCLUDED.sentiment,
            importance = EXCLUDED.importance,
            object_key = EXCLUDED.object_key,
            theme_tags = EXCLUDED.theme_tags
        """,
        (
            event_id,
            security_id,
            market,
            symbol,
            event_time,
            event_type,
            title,
            "synthetic",
            sentiment,
            importance,
            object_key,
            _json(theme_tags or []),
        ),
    )
    conn.execute(
        """
        INSERT INTO dwd.security_document_signal (
            signal_id, event_id, security_id, market, symbol, source_kind, summary,
            sentiment, risk_tags, theme_tags, evidence_path, positive_hits, negative_hits
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (signal_id) DO UPDATE SET
            event_id = EXCLUDED.event_id,
            security_id = EXCLUDED.security_id,
            market = EXCLUDED.market,
            symbol = EXCLUDED.symbol,
            source_kind = EXCLUDED.source_kind,
            summary = EXCLUDED.summary,
            sentiment = EXCLUDED.sentiment,
            risk_tags = EXCLUDED.risk_tags,
            theme_tags = EXCLUDED.theme_tags,
            evidence_path = EXCLUDED.evidence_path,
            positive_hits = EXCLUDED.positive_hits,
            negative_hits = EXCLUDED.negative_hits,
            extracted_at = NOW()
        """,
        (
            signal_id,
            event_id,
            security_id,
            market,
            symbol,
            "synthetic",
            summary,
            sentiment,
            _json(risk_tags or []),
            _json(theme_tags or []),
            object_key,
            1 if sentiment == "positive" else 0,
            1 if sentiment == "negative" else 0,
        ),
    )


def _sync_existing_ods_schema(conn, settings: Settings) -> None:
    conn.execute(ODS_SCHEMA_SYNC_SQL)
    storage: ObjectStorage | None = None
    try:
        storage = ObjectStorage(settings)
    except Exception:
        storage = None

    backfill_specs: list[tuple[str, Any]] = [
        ("SELECT * FROM ods.us_equity_price_daily_raw", _insert_price_rows),
        ("SELECT * FROM ods.security_financial_statement_raw", _insert_financial_rows),
        ("SELECT * FROM ods.user_watch_action_raw", _insert_watch_actions),
    ]
    for sql, loader in backfill_specs:
        rows = conn.execute(sql).fetchall()
        if rows:
            loader(conn, rows)

    filing_rows = conn.execute("SELECT * FROM ods.sec_filing_document_raw").fetchall()
    if filing_rows:
        _insert_filings_rows(conn, storage, filing_rows)

    news_rows = conn.execute("SELECT * FROM ods.security_news_article_raw").fetchall()
    if news_rows:
        _insert_news_rows(conn, storage, news_rows)

    institutional_rows = conn.execute("SELECT * FROM ods.security_institutional_activity_raw").fetchall()
    if institutional_rows:
        _insert_institutional_activity_rows(conn, storage, institutional_rows)


def bootstrap_real_data(settings: Settings, reset: bool = True, market: str = "US") -> None:
    ensure_schema(settings)
    if reset:
        reset_all(settings)

    market = market.upper()
    if market == "CN":
        bundle = build_cn_stock_bundle(settings)
    else:
        us_bundle = build_real_bundle(
            symbols=settings.market_universes["US"].symbols,
            price_provider=settings.price_provider,
            start_date=settings.price_start_date,
            end_date=settings.price_end_date,
            sec_user_agent=settings.sec_user_agent,
            polygon_api_key=settings.polygon_api_key,
            include_yfinance_supplement=settings.include_yfinance_supplement,
            institutional_manager_symbols=settings.institutional_manager_symbols,
        )
        bundle = {
            "securities": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.securities
            ],
            "security_themes": us_bundle.security_themes,
            "prices": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.prices
            ],
            "financials": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.financials
            ],
            "estimates": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.estimates
            ],
            "earnings_calendar": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.earnings_calendar
            ],
            "filings": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.filings
            ],
            "news": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.news
            ],
            "institutional_activity": [
                {
                    **dict(item.__dict__),
                    "market": "US",
                }
                for item in us_bundle.institutional_activity
            ],
            "watch_actions": [
                {
                    **(dict(item.__dict__) if hasattr(item, "__dict__") else dict(item)),
                    "market": "US",
                }
                for item in us_bundle.watch_actions
            ],
        }

    storage = ObjectStorage(settings)
    storage.ensure_bucket()
    trade_dates = [_row_get(row, "trade_date") for row in bundle["prices"]]
    trade_dates.append(settings.price_end_date)

    with connect(settings) as conn:
        if not reset:
            _clear_market_data(conn, market)
        _seed_common_dimensions(conn, trade_dates)
        _seed_theme_dimensions(
            conn,
            [
                (bucket.slug.replace("-", "_"), bucket.label)
                for bucket in settings.market_universes.get(market, settings.market_universes["US"]).buckets
            ] + [("a_share_growth", "A Share Growth"), *list(THEME_CATALOG.items())],
        )
        symbol_to_id = _insert_security_rows(conn, bundle["securities"])
        if bundle["security_themes"]:
            _insert_security_theme_rows(conn, bundle["security_themes"], symbol_to_id)
        _insert_price_rows(conn, bundle["prices"])
        if bundle["financials"]:
            _insert_financial_rows(conn, bundle["financials"])
        if bundle.get("estimates"):
            _insert_estimate_rows(conn, bundle["estimates"])
        if bundle.get("earnings_calendar"):
            _insert_earnings_calendar_rows(conn, bundle["earnings_calendar"])
        if bundle["filings"]:
            _insert_filings_rows(conn, storage, bundle["filings"])
        if bundle["news"]:
            _insert_news_rows(conn, storage, bundle["news"])
        if bundle.get("institutional_activity"):
            _insert_institutional_activity_rows(conn, storage, bundle["institutional_activity"])
        if bundle["watch_actions"]:
            _insert_watch_actions(conn, bundle["watch_actions"])


def bootstrap_sample_data(settings: Settings, reset: bool = True) -> None:
    ensure_schema(settings)
    if reset:
        reset_all(settings)

    data_dir = Path(settings.sample_data_dir)
    storage = ObjectStorage(settings)
    storage.ensure_bucket()

    securities = _read_csv(data_dir / "securities.csv")
    themes = _read_csv(data_dir / "themes.csv")
    security_themes = _read_csv(data_dir / "security_themes.csv")
    prices = _read_csv(data_dir / "price_daily.csv")
    financials = _enrich_financial_rows(data_dir, _read_csv(data_dir / "financials.csv"))
    filings = _read_json(data_dir / "filings.json")
    news_items = _enrich_news_rows(data_dir, _read_json(data_dir / "news.json"))
    institutional_activity = _read_json(data_dir / "institutional_activity.json") if (data_dir / "institutional_activity.json").exists() else []
    estimates = _read_json(data_dir / "estimates.json") if (data_dir / "estimates.json").exists() else []
    earnings_calendar = _read_json(data_dir / "earnings_calendar.json") if (data_dir / "earnings_calendar.json").exists() else []
    watch_actions = _read_csv(data_dir / "watch_actions.csv")

    with connect(settings) as conn:
        symbol_to_id = _insert_security_rows(conn, securities)

        for row in themes:
            conn.execute(
                """
                INSERT INTO dim.theme (theme_id, theme_name, parent_theme, active_flag)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (theme_id) DO UPDATE SET
                    theme_name = EXCLUDED.theme_name,
                    parent_theme = EXCLUDED.parent_theme,
                    active_flag = EXCLUDED.active_flag
                """,
                (row["theme_id"], row["theme_name"], row["parent_theme"], row["active_flag"].lower() == "true"),
            )

        _insert_security_theme_rows(conn, security_themes, symbol_to_id)


        trade_dates = sorted({row["trade_date"] for row in prices})
        for trade_date in trade_dates:
            conn.execute(
                """
                INSERT INTO dim.calendar (trade_date, week_of_year, month_of_year, quarter_of_year)
                SELECT %s::date,
                       EXTRACT(WEEK FROM %s::date)::int,
                       EXTRACT(MONTH FROM %s::date)::int,
                       EXTRACT(QUARTER FROM %s::date)::int
                ON CONFLICT (trade_date) DO NOTHING
                """,
                (trade_date, trade_date, trade_date, trade_date),
            )

        for factor_name, category, description, version in FACTOR_DEFINITIONS:
            conn.execute(
                """
                INSERT INTO dim.factor_definition (factor_name, category, description, version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (factor_name) DO UPDATE SET
                    category = EXCLUDED.category,
                    description = EXCLUDED.description,
                    version = EXCLUDED.version
                """,
                (factor_name, category, description, version),
            )

        if prices:
            _insert_price_rows(conn, prices)
        if financials:
            _insert_financial_rows(conn, financials)
        if estimates:
            _insert_estimate_rows(conn, estimates)
        if earnings_calendar:
            _insert_earnings_calendar_rows(conn, earnings_calendar)
        if filings:
            _insert_filings_rows(conn, storage, filings)
        if news_items:
            _insert_news_rows(conn, storage, news_items)
        if institutional_activity:
            _insert_institutional_activity_rows(conn, storage, institutional_activity)
        if watch_actions:
            _insert_watch_actions(conn, watch_actions)


def build_dwd(settings: Settings) -> None:
    storage = ObjectStorage(settings)
    with connect(settings) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                dwd.user_watchlist_state_current,
                dwd.security_document_signal,
                dwd.security_event_timeline,
                dwd.security_earnings_calendar_current,
                dwd.security_estimate_current,
                dwd.security_financial_quarterly,
                dwd.security_market_daily
            RESTART IDENTITY CASCADE;
            """
        )

        conn.execute(
            """
            WITH latest_financial AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    shares_outstanding,
                    CASE
                        WHEN LOWER(COALESCE(period_type, '')) IN ('annual', 'fy', 'year', 'yearly')
                            THEN revenue
                        ELSE revenue * 4
                    END AS annualized_revenue
                FROM ods.security_financial_statement_raw
                ORDER BY symbol, report_period DESC
            ),
            priced AS (
                SELECT
                    s.security_id,
                    s.market,
                    p.symbol,
                    p.trade_date,
                    p.open,
                    p.high,
                    p.low,
                    p.close,
                    p.adj_close,
                    p.volume,
                    p.raw_payload,
                    LAG(p.adj_close) OVER (PARTITION BY p.symbol ORDER BY p.trade_date) AS prev_adj_close,
                    LAG(p.adj_close, 5) OVER (PARTITION BY p.symbol ORDER BY p.trade_date) AS prev_5d_adj_close,
                    MAX(p.high) OVER (
                        PARTITION BY p.symbol
                        ORDER BY p.trade_date
                        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                    ) AS recent_high,
                    lf.shares_outstanding,
                    lf.annualized_revenue
                FROM ods.us_equity_price_daily_raw p
                JOIN dim.security s ON s.symbol = p.symbol AND s.market = p.market
                LEFT JOIN latest_financial lf ON lf.symbol = p.symbol
            )
            INSERT INTO dwd.security_market_daily (
                security_id, market, symbol, trade_date, open, high, low, close, adj_close,
                volume, return_1d, return_5d, distance_from_recent_high, market_cap, ps_ttm, pe_ttm, pb, turnover_rate
            )
            SELECT
                security_id,
                market,
                symbol,
                trade_date,
                open,
                high,
                low,
                close,
                adj_close,
                volume,
                CASE WHEN prev_adj_close IS NULL OR prev_adj_close = 0 THEN NULL
                     ELSE ROUND(((adj_close - prev_adj_close) / prev_adj_close)::numeric, 6)
                END AS return_1d,
                CASE WHEN prev_5d_adj_close IS NULL OR prev_5d_adj_close = 0 THEN NULL
                     ELSE ROUND(((adj_close - prev_5d_adj_close) / prev_5d_adj_close)::numeric, 6)
                END AS return_5d,
                CASE WHEN recent_high IS NULL OR recent_high = 0 THEN NULL
                     ELSE ROUND(((adj_close / recent_high) - 1)::numeric, 6)
                END AS distance_from_recent_high,
                CASE WHEN shares_outstanding IS NULL THEN NULL
                     ELSE ROUND((adj_close * shares_outstanding)::numeric, 2)
                END AS market_cap,
                CASE WHEN shares_outstanding IS NULL OR annualized_revenue IS NULL OR annualized_revenue = 0 THEN NULL
                     ELSE ROUND(((adj_close * shares_outstanding) / annualized_revenue)::numeric, 4)
                END AS ps_ttm,
                NULLIF((raw_payload ->> 'pe_ttm'), '')::numeric AS pe_ttm,
                NULLIF((raw_payload ->> 'pb'), '')::numeric AS pb,
                NULLIF((raw_payload ->> 'turnover_rate'), '')::numeric AS turnover_rate
            FROM priced;
            """
        )

        conn.execute(
            """
            INSERT INTO dwd.security_financial_quarterly (
                security_id, market, symbol, report_period, revenue, revenue_yoy, netprofit_yoy, gross_margin,
                op_margin, fcf_margin, cfo_to_np, rd_ratio_ttm, cash, debt, net_cash, shares_outstanding
            )
            SELECT
                s.security_id,
                s.market,
                f.symbol,
                f.report_period,
                f.revenue,
                f.revenue_yoy,
                f.netprofit_yoy,
                f.gross_margin,
                f.op_margin,
                f.fcf_margin,
                f.cfo_to_np,
                f.rd_ratio_ttm,
                f.cash,
                f.debt,
                COALESCE(f.cash, 0) - COALESCE(f.debt, 0) AS net_cash,
                f.shares_outstanding
            FROM ods.security_financial_statement_raw f
            JOIN dim.security s ON s.symbol = f.symbol AND s.market = f.market;
            """
        )

        conn.execute(
            """
            WITH latest_estimate_dates AS (
                SELECT market, symbol, MAX(snapshot_date) AS snapshot_date
                FROM ods.us_analyst_estimate_raw
                GROUP BY market, symbol
            ),
            latest_estimates AS (
                SELECT e.*
                FROM ods.us_analyst_estimate_raw e
                JOIN latest_estimate_dates led
                  ON led.market = e.market
                 AND led.symbol = e.symbol
                 AND led.snapshot_date = e.snapshot_date
            )
            INSERT INTO dwd.security_estimate_current (
                security_id, market, symbol, snapshot_date,
                fy1_revenue_estimate, fy2_revenue_estimate, fy1_eps, fy2_eps,
                fy1_analyst_count, fy2_analyst_count, currency,
                data_quality_flag, source_vendor, raw_payload
            )
            SELECT
                s.security_id,
                s.market,
                e.symbol,
                MAX(e.snapshot_date) AS snapshot_date,
                MAX(e.revenue_estimate) FILTER (WHERE e.fiscal_year_offset = 1) AS fy1_revenue_estimate,
                MAX(e.revenue_estimate) FILTER (WHERE e.fiscal_year_offset = 2) AS fy2_revenue_estimate,
                MAX(e.eps_estimate) FILTER (WHERE e.fiscal_year_offset = 1) AS fy1_eps,
                MAX(e.eps_estimate) FILTER (WHERE e.fiscal_year_offset = 2) AS fy2_eps,
                MAX(e.analyst_count) FILTER (WHERE e.fiscal_year_offset = 1) AS fy1_analyst_count,
                MAX(e.analyst_count) FILTER (WHERE e.fiscal_year_offset = 2) AS fy2_analyst_count,
                COALESCE(MAX(e.currency), 'USD') AS currency,
                CASE
                    WHEN COUNT(*) FILTER (WHERE e.request_status = 'ok') > 0 THEN 'ok'
                    ELSE 'partial'
                END AS data_quality_flag,
                MAX(e.source_vendor) AS source_vendor,
                jsonb_object_agg(COALESCE(e.period_label, e.fiscal_year_offset::text), e.raw_payload) AS raw_payload
            FROM latest_estimates e
            JOIN dim.security s ON s.symbol = e.symbol AND s.market = e.market
            GROUP BY s.security_id, s.market, e.symbol;
            """
        )

        conn.execute(
            """
            WITH ranked_events AS (
                SELECT
                    e.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.market, e.symbol
                        ORDER BY
                            CASE WHEN e.earnings_date >= e.snapshot_date THEN 0 ELSE 1 END,
                            e.earnings_date NULLS LAST,
                            e.snapshot_date DESC
                    ) AS rn
                FROM ods.us_earnings_calendar_raw e
            )
            INSERT INTO dwd.security_earnings_calendar_current (
                security_id, market, symbol, snapshot_date, next_earnings_date, days_to_earnings,
                fiscal_period, time_of_day, eps_estimate, revenue_estimate, currency,
                data_quality_flag, source_vendor, raw_payload
            )
            SELECT
                s.security_id,
                s.market,
                e.symbol,
                e.snapshot_date,
                e.earnings_date AS next_earnings_date,
                CASE WHEN e.earnings_date IS NULL THEN NULL ELSE e.earnings_date - e.snapshot_date END AS days_to_earnings,
                e.fiscal_period,
                e.time_of_day,
                e.eps_estimate,
                e.revenue_estimate,
                COALESCE(e.currency, 'USD') AS currency,
                CASE WHEN e.request_status = 'ok' AND e.earnings_date IS NOT NULL THEN 'ok' ELSE 'partial' END AS data_quality_flag,
                e.source_vendor,
                e.raw_payload
            FROM ranked_events e
            JOIN dim.security s ON s.symbol = e.symbol AND s.market = e.market
            WHERE e.rn = 1;
            """
        )

        filing_rows = conn.execute(
            """
            SELECT s.security_id, s.market, f.filing_id AS source_id, f.symbol, f.filing_time AS event_time,
                   f.title, f.object_key, 'filing' AS source_kind, f.filing_type AS event_type
            FROM ods.sec_filing_document_raw f
            JOIN dim.security s ON s.symbol = f.symbol AND s.market = f.market
            ORDER BY f.filing_time
            """
        ).fetchall()

        news_rows = conn.execute(
            """
            SELECT s.security_id, s.market, n.news_id AS source_id, n.symbol, n.published_time AS event_time,
                   n.title, n.object_key, 'news' AS source_kind, 'news' AS event_type
            FROM ods.security_news_article_raw n
            JOIN dim.security s ON s.symbol = n.symbol AND s.market = n.market
            ORDER BY n.published_time
            """
        ).fetchall()

        institutional_rows = conn.execute(
            """
            SELECT s.security_id, s.market, a.activity_id AS source_id, a.symbol, a.activity_time AS event_time,
                   a.title, a.object_key, 'institutional' AS source_kind, a.filing_type AS event_type
            FROM ods.security_institutional_activity_raw a
            JOIN dim.security s ON s.symbol = a.symbol AND s.market = a.market
            ORDER BY a.activity_time
            """
        ).fetchall()

        for row in [*filing_rows, *news_rows, *institutional_rows]:
            text = storage.download_text(row["object_key"])
            signal = extract_signal(text)
            event_id = f"{row['source_kind']}::{row['source_id']}"
            conn.execute(
                """
                INSERT INTO dwd.security_event_timeline (
                    event_id, security_id, market, symbol, event_time, event_type, title,
                    source_kind, sentiment, importance, object_key, theme_tags
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    security_id = EXCLUDED.security_id,
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    event_time = EXCLUDED.event_time,
                    event_type = EXCLUDED.event_type,
                    title = EXCLUDED.title,
                    source_kind = EXCLUDED.source_kind,
                    sentiment = EXCLUDED.sentiment,
                    importance = EXCLUDED.importance,
                    object_key = EXCLUDED.object_key,
                    theme_tags = EXCLUDED.theme_tags
                """,
                (
                    event_id, row["security_id"], row["market"], row["symbol"], row["event_time"], row["event_type"],
                    row["title"], row["source_kind"], signal.sentiment, signal.importance, row["object_key"],
                    _json(signal.theme_tags),
                ),
            )
            conn.execute(
                """
                INSERT INTO dwd.security_document_signal (
                    signal_id, event_id, security_id, market, symbol, source_kind, summary,
                    sentiment, risk_tags, theme_tags, evidence_path, positive_hits, negative_hits
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE SET
                    event_id = EXCLUDED.event_id,
                    security_id = EXCLUDED.security_id,
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    source_kind = EXCLUDED.source_kind,
                    summary = EXCLUDED.summary,
                    sentiment = EXCLUDED.sentiment,
                    risk_tags = EXCLUDED.risk_tags,
                    theme_tags = EXCLUDED.theme_tags,
                    evidence_path = EXCLUDED.evidence_path,
                    positive_hits = EXCLUDED.positive_hits,
                    negative_hits = EXCLUDED.negative_hits,
                    extracted_at = NOW()
                """,
                (
                    f"signal::{row['source_kind']}::{row['source_id']}",
                    event_id,
                    row["security_id"],
                    row["market"],
                    row["symbol"],
                    row["source_kind"],
                    signal.summary,
                    signal.sentiment,
                    _json(signal.risk_tags),
                    _json(signal.theme_tags),
                    row["object_key"],
                    signal.positive_hits,
                    signal.negative_hits,
                ),
            )

        conn.execute(
            """
            WITH latest_actions AS (
                SELECT DISTINCT ON (user_id, market, symbol)
                    user_id,
                    market,
                    symbol,
                    action,
                    action_time
                FROM ods.user_watch_action_raw
                ORDER BY user_id, market, symbol, action_time DESC
            )
            INSERT INTO dwd.user_watchlist_state_current (
                user_id, security_id, market, symbol, state, latest_action_time
            )
            SELECT
                la.user_id,
                s.security_id,
                la.market,
                la.symbol,
                CASE WHEN la.action = 'watch' THEN 'watching' ELSE 'inactive' END,
                la.action_time
            FROM latest_actions la
            JOIN dim.security s ON s.symbol = la.symbol AND s.market = la.market
            WHERE la.action = 'watch';
            """
        )

        cn_theme_map_rows = conn.execute(
            """
            SELECT st.security_id, array_agg(st.theme_id ORDER BY st.theme_id) AS theme_ids
            FROM dim.security_theme st
            JOIN dim.security s ON s.security_id = st.security_id
            WHERE s.market = 'CN'
            GROUP BY st.security_id
            """
        ).fetchall()
        cn_theme_map = {row["security_id"]: row["theme_ids"] or [] for row in cn_theme_map_rows}

        cn_financial_rows = conn.execute(
            """
            SELECT security_id, symbol, report_period, revenue_yoy, netprofit_yoy, op_margin
            FROM dwd.security_financial_quarterly
            WHERE market = 'CN'
            AND report_period = (
                SELECT MAX(report_period) FROM dwd.security_financial_quarterly f2 WHERE f2.security_id = dwd.security_financial_quarterly.security_id
            )
            """
        ).fetchall()
        for row in cn_financial_rows:
            theme_tags = cn_theme_map.get(row["security_id"], [])
            revenue_yoy = float(row["revenue_yoy"] or 0.0) * 100 if row["revenue_yoy"] is not None and abs(float(row["revenue_yoy"])) <= 1 else float(row["revenue_yoy"] or 0.0)
            netprofit_yoy = float(row["netprofit_yoy"] or 0.0) * 100 if row["netprofit_yoy"] is not None and abs(float(row["netprofit_yoy"])) <= 1 else float(row["netprofit_yoy"] or 0.0)
            op_margin = float(row["op_margin"] or 0.0) * 100 if row["op_margin"] is not None and abs(float(row["op_margin"])) <= 1 else float(row["op_margin"] or 0.0)
            sentiment = "positive" if revenue_yoy >= 20 or netprofit_yoy >= 20 else "neutral"
            summary = f"最近财务披露显示营收同比 {revenue_yoy:.1f}%，净利同比 {netprofit_yoy:.1f}%，经营利润率 {op_margin:.1f}%。"
            _upsert_synthetic_signal(
                conn,
                signal_id=f"signal::synthetic::cn-financial::{row['symbol']}::{row['report_period']}",
                event_id=f"synthetic::cn-financial::{row['symbol']}::{row['report_period']}",
                security_id=row["security_id"],
                market="CN",
                symbol=row["symbol"],
                event_time=f"{row['report_period']}T09:00:00+08:00",
                event_type="financial",
                title=f"{row['symbol']} 财务兑现跟踪",
                summary=summary,
                sentiment=sentiment,
                importance=2 if sentiment == "positive" else 1,
                risk_tags=[],
                theme_tags=theme_tags,
                object_key=f"synthetic://cn/financial/{row['symbol']}/{row['report_period']}",
            )

        cn_latest_trade = conn.execute("SELECT MAX(trade_date) AS trade_date FROM dwd.security_market_daily WHERE market = 'CN'").fetchone()
        latest_cn_trade_date = cn_latest_trade["trade_date"] if cn_latest_trade else None
        if latest_cn_trade_date is not None:
            cn_market_rows = conn.execute(
                """
                SELECT security_id, symbol, trade_date, return_1d, return_5d, distance_from_recent_high
                FROM dwd.security_market_daily
                WHERE market = 'CN' AND trade_date = %s
                """,
                (latest_cn_trade_date,),
            ).fetchall()
            for row in cn_market_rows:
                theme_tags = cn_theme_map.get(row["security_id"], [])
                ret_5d = float(row["return_5d"] or 0.0) * 100 if row["return_5d"] is not None else 0.0
                dist_high = float(row["distance_from_recent_high"] or 0.0) * 100 if row["distance_from_recent_high"] is not None else 0.0
                sentiment = "positive" if ret_5d >= 3 else "negative" if ret_5d <= -5 else "neutral"
                risk_tags = ["price_cooling"] if sentiment == "negative" else []
                summary = f"最近 5 日涨跌幅 {ret_5d:.1f}%，距阶段高点 {dist_high:.1f}%。"
                _upsert_synthetic_signal(
                    conn,
                    signal_id=f"signal::synthetic::cn-market::{row['symbol']}::{row['trade_date']}",
                    event_id=f"synthetic::cn-market::{row['symbol']}::{row['trade_date']}",
                    security_id=row["security_id"],
                    market="CN",
                    symbol=row["symbol"],
                    event_time=f"{row['trade_date']}T15:00:00+08:00",
                    event_type="market",
                    title=f"{row['symbol']} 行情跟踪",
                    summary=summary,
                    sentiment=sentiment,
                    importance=2 if abs(ret_5d) >= 5 else 1,
                    risk_tags=risk_tags,
                    theme_tags=theme_tags,
                    object_key=f"synthetic://cn/market/{row['symbol']}/{row['trade_date']}",
                )


def build_dws(settings: Settings) -> None:
    with connect(settings) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                dws.security_candidate_rank_daily,
                dws.security_scenario_path_daily,
                dws.security_key_level_daily,
                dws.security_target_range_daily,
                dws.theme_heat_daily,
                dws.security_score_component_daily,
                dws.security_feature_daily,
                dwd.security_price_technical_daily
            RESTART IDENTITY CASCADE;
            """
        )
        latest_trade_dates = conn.execute(
            """
            SELECT market, MAX(trade_date) AS trade_date
            FROM dwd.security_market_daily
            GROUP BY market
            """
        ).fetchall()
        if not latest_trade_dates:
            raise RuntimeError("No market data available in dwd.security_market_daily")
        latest_trade_date_by_market = {row["market"]: row["trade_date"] for row in latest_trade_dates}

        latest_bars = conn.execute(
            """
            WITH latest AS (
                SELECT market, MAX(trade_date) AS trade_date
                FROM dwd.security_market_daily
                GROUP BY market
            )
            SELECT m.*
            FROM dwd.security_market_daily m
            JOIN latest l ON l.market = m.market AND l.trade_date = m.trade_date
            ORDER BY m.market, m.symbol
            """
        ).fetchall()

        rank_input: list[dict[str, Any]] = []

        for bar in latest_bars:
            security_id = bar["security_id"]
            symbol = bar["symbol"]
            market = bar["market"]
            trade_date = latest_trade_date_by_market[market]
            financial = conn.execute(
                """
                SELECT * FROM dwd.security_financial_quarterly
                WHERE security_id = %s
                ORDER BY report_period DESC
                LIMIT 1
                """,
                (security_id,),
            ).fetchone()
            signal_stats = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END), 0) AS negative_event_count,
                    COALESCE(SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END), 0) AS positive_signal_count,
                    COALESCE(jsonb_agg(DISTINCT risk_tags) FILTER (WHERE jsonb_array_length(risk_tags) > 0), '[]'::jsonb) AS risk_tag_groups,
                    COALESCE(jsonb_agg(DISTINCT theme_tags) FILTER (WHERE jsonb_array_length(theme_tags) > 0), '[]'::jsonb) AS theme_tag_groups
                FROM dwd.security_document_signal
                WHERE security_id = %s
                """,
                (security_id,),
            ).fetchone()
            theme_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM dim.security_theme WHERE security_id = %s",
                (security_id,),
            ).fetchone()["cnt"]

            risk_tags: list[str] = []
            for group in signal_stats["risk_tag_groups"] or []:
                risk_tags.extend(group)
            risk_tags = sorted(set(risk_tags))

            theme_tags: list[str] = []
            for group in signal_stats["theme_tag_groups"] or []:
                theme_tags.extend(group)
            dim_theme_rows = conn.execute(
                "SELECT theme_id FROM dim.security_theme WHERE security_id = %s ORDER BY theme_id",
                (security_id,),
            ).fetchall()
            theme_tags.extend(row["theme_id"] for row in dim_theme_rows)
            theme_tags = sorted(set(theme_tags))

            components = build_score_components(
                revenue_yoy=float(financial["revenue_yoy"] or 0.0) if financial and financial["revenue_yoy"] is not None else None,
                op_margin=float(financial["op_margin"] or 0.0) if financial and financial["op_margin"] is not None else None,
                fcf_margin=float(financial["fcf_margin"] or 0.0) if financial and financial["fcf_margin"] is not None else None,
                return_5d=float(bar["return_5d"] or 0.0) if bar["return_5d"] is not None else None,
                distance_from_high=float(bar["distance_from_recent_high"] or 0.0) if bar["distance_from_recent_high"] is not None else None,
                ps_ttm=float(bar["ps_ttm"] or 0.0) if bar["ps_ttm"] is not None else None,
                market_cap=float(bar["market_cap"] or 0.0) if bar["market_cap"] is not None else None,
                risk_count=len(risk_tags),
                negative_event_count=int(signal_stats["negative_event_count"] or 0),
                theme_count=int(theme_count),
                positive_signal_count=int(signal_stats["positive_signal_count"] or 0),
                market=market,
                netprofit_yoy=float(financial["netprofit_yoy"] or 0.0) if financial and financial["netprofit_yoy"] is not None else None,
                cfo_to_np=float(financial["cfo_to_np"] or 0.0) if financial and financial["cfo_to_np"] is not None else None,
                rd_ratio_ttm=float(financial["rd_ratio_ttm"] or 0.0) if financial and financial["rd_ratio_ttm"] is not None else None,
                pe_ttm=float(bar["pe_ttm"] or 0.0) if bar["pe_ttm"] is not None else None,
                pb=float(bar["pb"] or 0.0) if bar["pb"] is not None else None,
                turnover_rate=float(bar["turnover_rate"] or 0.0) if bar["turnover_rate"] is not None else None,
            )
            stage = classify_stage(
                components,
                market=market,
                ps_ttm=float(bar["ps_ttm"] or 0.0) if bar["ps_ttm"] is not None else None,
                market_cap=float(bar["market_cap"] or 0.0) if bar["market_cap"] is not None else None,
                return_5d=float(bar["return_5d"] or 0.0) if bar["return_5d"] is not None else None,
                distance_from_high=float(bar["distance_from_recent_high"] or 0.0) if bar["distance_from_recent_high"] is not None else None,
                risk_count=len(risk_tags),
                negative_event_count=int(signal_stats["negative_event_count"] or 0),
            )
            score_reason = explain_components(components, market=market)

            conn.execute(
                """
                INSERT INTO dws.security_feature_daily (
                    security_id, market, symbol, trade_date, revenue_yoy, netprofit_yoy, op_margin, fcf_margin,
                    cfo_to_np, rd_ratio_ttm, return_1d, return_5d, distance_from_recent_high, ps_ttm, pe_ttm, pb, turnover_rate,
                    risk_count, negative_event_count, theme_count, positive_signal_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    security_id,
                    market,
                    symbol,
                    trade_date,
                    financial["revenue_yoy"] if financial else None,
                    financial["netprofit_yoy"] if financial else None,
                    financial["op_margin"] if financial else None,
                    financial["fcf_margin"] if financial else None,
                    financial["cfo_to_np"] if financial else None,
                    financial["rd_ratio_ttm"] if financial else None,
                    bar["return_1d"],
                    bar["return_5d"],
                    bar["distance_from_recent_high"],
                    bar["ps_ttm"],
                    bar["pe_ttm"],
                    bar["pb"],
                    bar["turnover_rate"],
                    len(risk_tags),
                    int(signal_stats["negative_event_count"] or 0),
                    int(theme_count),
                    int(signal_stats["positive_signal_count"] or 0),
                ),
            )

            conn.execute(
                """
                INSERT INTO dws.security_score_component_daily (
                    security_id, market, symbol, trade_date, growth_score, quality_score,
                    momentum_score, valuation_score, size_score, evidence_score,
                    risk_score, theme_score, industry_prosperity_score, leader_position_score, financial_acceleration_score,
                    cashflow_quality_score, moat_score, valuation_chip_score, total_score, stage, score_change_reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    security_id,
                    market,
                    symbol,
                    trade_date,
                    components.growth,
                    components.quality,
                    components.momentum,
                    components.valuation,
                    components.size,
                    components.evidence,
                    components.risk,
                    components.theme,
                    components.industry_prosperity,
                    components.leader_position,
                    components.financial_acceleration,
                    components.cashflow_quality,
                    components.moat,
                    components.valuation_chip,
                    components.total,
                    stage,
                    score_reason,
                ),
            )

            rank_input.append(
                {
                    "security_id": security_id,
                    "market": market,
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "total_score": components.total,
                    "stage": stage,
                    "entry_reason": score_reason,
                    "risk_tags": risk_tags,
                    "theme_tags": theme_tags,
                }
            )

        ranked = sorted(rank_input, key=lambda row: (row["market"], -row["total_score"], row["symbol"]))
        grouped_ranked: dict[str, list[dict[str, Any]]] = {}
        for row in ranked:
            grouped_ranked.setdefault(row["market"], []).append(row)
        for market, rows in grouped_ranked.items():
            for idx, row in enumerate(rows, start=1):
                conn.execute(
                    """
                    INSERT INTO dws.security_candidate_rank_daily (
                        security_id, market, symbol, trade_date, total_score, stage, rank_no, entry_reason,
                        risk_tags, theme_tags
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row["security_id"],
                        market,
                        row["symbol"],
                        row["trade_date"],
                        row["total_score"],
                        row["stage"],
                        idx,
                        row["entry_reason"],
                        _json(row["risk_tags"]),
                        _json(row["theme_tags"]),
                    ),
                )

        theme_rows = conn.execute(
            """
            SELECT
                t.theme_id,
                t.theme_name,
                s.market,
                st.security_id,
                s.symbol,
                sc.total_score,
                COALESCE(sig.signal_count, 0) AS signal_count
            FROM dim.theme t
            JOIN dim.security_theme st ON st.theme_id = t.theme_id
            JOIN dim.security s ON s.security_id = st.security_id
            JOIN dws.security_score_component_daily sc ON sc.security_id = st.security_id
            LEFT JOIN (
                SELECT security_id, COUNT(*) AS signal_count
                FROM dwd.security_document_signal
                GROUP BY security_id
            ) sig ON sig.security_id = st.security_id
            ORDER BY s.market, t.theme_id, sc.total_score DESC
            """
        ).fetchall()

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in theme_rows:
            bucket = grouped.setdefault(
                (row["market"], row["theme_id"]),
                {
                    "theme_name": row["theme_name"],
                    "total_scores": [],
                    "leaders": [],
                    "signal_count": 0,
                },
            )
            bucket["total_scores"].append(float(row["total_score"]))
            bucket["leaders"].append((row["symbol"], float(row["total_score"])))
            bucket["signal_count"] += int(row["signal_count"] or 0)

        for (market, theme_id), bucket in grouped.items():
            avg_score = sum(bucket["total_scores"]) / len(bucket["total_scores"])
            if market == "CN":
                heat_score = round(avg_score * 0.9 + len(bucket["leaders"]) * 4 + bucket["signal_count"] * 2, 2)
                status = "上升" if heat_score >= 60 else "震荡" if heat_score >= 48 else "转弱"
            else:
                heat_score = round(avg_score * 0.7 + bucket["signal_count"] * 3, 2)
                status = "上升" if heat_score >= 70 else "震荡" if heat_score >= 55 else "转弱"
            leader_symbols = [symbol for symbol, _score in sorted(bucket["leaders"], key=lambda item: item[1], reverse=True)[:3]]
            conn.execute(
                """
                INSERT INTO dws.theme_heat_daily (
                    theme_id, market, trade_date, theme_name, heat_score, status,
                    symbol_count, evidence_count, leader_symbols
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    theme_id,
                    market,
                    latest_trade_date_by_market[market],
                    bucket["theme_name"],
                    heat_score,
                    status,
                    len(bucket["total_scores"]),
                    bucket["signal_count"],
                    _json(leader_symbols),
                ),
            )


def build_ads(settings: Settings) -> None:
    with connect(settings) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                ads.price_map_current,
                ads.watchlist_alert_daily,
                ads.research_card_current,
                ads.candidate_pool_daily,
                ads.theme_radar_daily
            RESTART IDENTITY CASCADE;
            """
        )
        latest_trade_dates = conn.execute(
            """
            SELECT market, MAX(trade_date) AS trade_date
            FROM dws.security_candidate_rank_daily
            GROUP BY market
            """
        ).fetchall()
        if not latest_trade_dates:
            raise RuntimeError("No ranked candidates available in dws.security_candidate_rank_daily")
        latest_trade_date_by_market = {row["market"]: row["trade_date"] for row in latest_trade_dates}

        ranked_rows = conn.execute(
            """
            SELECT *
            FROM dws.security_candidate_rank_daily
            ORDER BY market, rank_no
            """
        ).fetchall()
        grouped_ranked: dict[str, list[dict[str, Any]]] = {}
        for row in ranked_rows:
            if row["trade_date"] != latest_trade_date_by_market.get(row["market"]):
                continue
            grouped_ranked.setdefault(row["market"], []).append(row)

        for market, rows in grouped_ranked.items():
            candidates = [row for row in rows if row["stage"] != "crowded"][:20] or rows[:20]
            for new_rank, row in enumerate(candidates, start=1):
                summary = f"{row['symbol']} 主候选排名第 {new_rank}，所处阶段 {row['stage']}，核心强项：{row['entry_reason']}。"
                conn.execute(
                    """
                    INSERT INTO ads.candidate_pool_daily (
                        security_id, market, symbol, trade_date, rank_no, total_score, stage,
                        reason_summary, risk_tags, theme_tags
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row["security_id"],
                        market,
                        row["symbol"],
                        row["trade_date"],
                        new_rank,
                        row["total_score"],
                        row["stage"],
                        summary,
                        _json(row["risk_tags"]),
                        _json(row["theme_tags"]),
                    ),
                )

        securities = conn.execute("SELECT security_id, market, symbol, company_name FROM dim.security ORDER BY market, security_id").fetchall()
        for sec in securities:
            trade_date = latest_trade_date_by_market.get(sec["market"])
            if trade_date is None:
                continue
            score = conn.execute(
                """
                SELECT * FROM dws.security_score_component_daily
                WHERE security_id = %s AND trade_date = %s
                """,
                (sec["security_id"], trade_date),
            ).fetchone()
            if score is None:
                continue
            financial = conn.execute(
                """
                SELECT * FROM dwd.security_financial_quarterly
                WHERE security_id = %s
                ORDER BY report_period DESC
                LIMIT 1
                """,
                (sec["security_id"],),
            ).fetchone()
            events = conn.execute(
                """
                SELECT title, sentiment, object_key
                FROM dwd.security_event_timeline
                WHERE security_id = %s
                ORDER BY event_time DESC
                LIMIT 3
                """,
                (sec["security_id"],),
            ).fetchall()
            theme_names = conn.execute(
                """
                SELECT t.theme_name
                FROM dim.security_theme st
                JOIN dim.theme t ON t.theme_id = st.theme_id
                WHERE st.security_id = %s
                ORDER BY t.theme_name
                """,
                (sec["security_id"],),
            ).fetchall()
            thesis = (
                f"{sec['company_name']} 当前总分 {float(score['total_score']):.2f}，"
                f"所处阶段为 {score['stage']}，重点关注 {', '.join(t['theme_name'] for t in theme_names) or '成长科技'} 主线。"
            )
            key_points = [
                f"营收同比 {float(financial['revenue_yoy'] or 0) * 100:.1f}%" if financial else "等待财务数据",
                f"经营利润率 {float(financial['op_margin'] or 0) * 100:.1f}%" if financial else "等待利润率数据",
                f"当前阶段：{score['stage']}",
                f"评分强项：{score['score_change_reason']}",
            ]
            risk_points = [
                event["title"] for event in events if event["sentiment"] == "negative"
            ] or ["暂无显著负面事件"]
            next_watch_items = [
                "下一个财报窗口",
                "主题热度是否持续",
                "最新 filing / news 是否继续验证逻辑",
            ]
            evidence_refs = [event["object_key"] for event in events]
            conn.execute(
                """
                INSERT INTO ads.research_card_current (
                    security_id, market, symbol, as_of_date, thesis, key_points,
                    risk_points, next_watch_items, evidence_refs, stage, total_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (security_id) DO UPDATE SET
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    as_of_date = EXCLUDED.as_of_date,
                    thesis = EXCLUDED.thesis,
                    key_points = EXCLUDED.key_points,
                    risk_points = EXCLUDED.risk_points,
                    next_watch_items = EXCLUDED.next_watch_items,
                    evidence_refs = EXCLUDED.evidence_refs,
                    stage = EXCLUDED.stage,
                    total_score = EXCLUDED.total_score
                """,
                (
                    sec["security_id"],
                    sec["market"],
                    sec["symbol"],
                    trade_date,
                    thesis,
                    _json(key_points),
                    _json(risk_points),
                    _json(next_watch_items),
                    _json(evidence_refs),
                    score["stage"],
                    score["total_score"],
                ),
            )

        watchlist_rows = conn.execute(
            """
            WITH latest AS (
                SELECT market, MAX(trade_date) AS trade_date
                FROM ads.candidate_pool_daily
                GROUP BY market
            )
            SELECT w.user_id, w.market, w.security_id, w.symbol, c.rank_no, c.total_score, c.reason_summary,
                   c.risk_tags
            FROM dwd.user_watchlist_state_current w
            LEFT JOIN latest l ON l.market = w.market
            LEFT JOIN ads.candidate_pool_daily c
              ON c.security_id = w.security_id AND c.trade_date = l.trade_date
            WHERE w.state = 'watching'
            """
        ).fetchall()
        for row in watchlist_rows:
            risk_tags = row["risk_tags"] or []
            if risk_tags and risk_tags != []:
                conn.execute(
                    """
                    INSERT INTO ads.watchlist_alert_daily (
                        alert_id, user_id, market, symbol, trade_date, alert_type, severity,
                        alert_message, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        row["user_id"],
                        row["market"],
                        row["symbol"],
                        latest_trade_date_by_market.get(row["market"]),
                        "risk",
                        "high",
                        f"{row['symbol']} 出现风险标签：{', '.join(risk_tags)}，建议复核最新事件。",
                        _json([]),
                    ),
                )
            if row["rank_no"] is not None and row["rank_no"] <= 2:
                conn.execute(
                    """
                    INSERT INTO ads.watchlist_alert_daily (
                        alert_id, user_id, market, symbol, trade_date, alert_type, severity,
                        alert_message, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        row["user_id"],
                        row["market"],
                        row["symbol"],
                        latest_trade_date_by_market.get(row["market"]),
                        "candidate_upgrade",
                        "medium",
                        f"{row['symbol']} 进入候选池前二，当前总分 {float(row['total_score']):.2f}。",
                        _json([row["reason_summary"]]),
                    ),
                )

        themes = conn.execute(
            """
            SELECT * FROM dws.theme_heat_daily
            ORDER BY heat_score DESC
            """
        ).fetchall()
        for row in themes:
            if row["trade_date"] != latest_trade_date_by_market.get(row["market"]):
                continue
            conn.execute(
                """
                INSERT INTO ads.theme_radar_daily (
                    theme_id, market, trade_date, theme_name, heat_score, status,
                    key_drivers, representative_symbols
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["theme_id"],
                    row["market"],
                    row["trade_date"],
                    row["theme_name"],
                    row["heat_score"],
                    row["status"],
                    _json([
                        f"覆盖股票数 {row['symbol_count']}",
                        f"证据数 {row['evidence_count']}",
                    ]),
                    _json(row["leader_symbols"]),
                ),
            )


def _target_range_payload(target) -> dict[str, Any]:
    return {
        "scenario": target.scenario,
        "horizon": target.horizon,
        "low": target.target_low,
        "high": target.target_high,
        "mid": target.target_mid,
        "upside_pct_mid": target.upside_pct_mid,
        "method": target.method,
        "confidence": target.confidence,
        "assumptions": target.assumptions,
        "evidence_refs": target.evidence_refs,
    }


def _key_level_payload(level) -> dict[str, Any]:
    return {
        "level_type": level.level_type,
        "label": level.note,
        "low": level.level_low,
        "high": level.level_high,
        "strength": level.strength,
        "distance_pct": level.distance_pct,
        "source": level.source,
        "note": level.note,
        "evidence_refs": level.evidence_refs,
    }


def _scenario_path_payload(path) -> dict[str, Any]:
    return {
        "name": path.path_name,
        "probability": path.probability,
        "confidence": path.confidence,
        "trigger": path.trigger,
        "target_scenario": path.target_scenario,
        "invalidation": path.invalidation,
        "explanation": path.explanation,
        "evidence_refs": path.evidence_refs,
    }


def _price_map_with_deerflow(
    *,
    settings: Settings,
    market: str,
    symbol: str,
    trade_date: Any,
    technical: Any,
    latest_market_row: dict[str, Any],
    financial: dict[str, Any] | None,
    score: dict[str, Any] | None,
    option_summary: dict[str, Any] | None,
    estimate: dict[str, Any] | None,
    earnings_calendar: dict[str, Any] | None,
    evidence_refs: list[str],
):
    baseline = build_price_map_snapshot(
        technical,
        latest_market_row,
        financial,
        score,
        option_summary,
        estimate,
        earnings_calendar,
        evidence_refs,
    )
    if not settings.price_map_deerflow_enabled:
        return baseline

    from vnpy.web.services.deerflow_service import DeerFlowService

    thread_id = f"tenx-price-map-{market.lower()}-{symbol.lower().replace('.', '-')}-{trade_date}"
    prompt = build_deerflow_price_map_prompt(
        market=market,
        symbol=symbol,
        trade_date=trade_date,
        technical=technical,
        market_row=latest_market_row,
        financial=financial,
        score_row=score,
        option_summary=option_summary,
        estimate=estimate,
        earnings_calendar=earnings_calendar,
        evidence_refs=evidence_refs,
        baseline=baseline,
    )
    deerflow = DeerFlowService()
    result = deerflow.chat(prompt, thread_id=thread_id)
    if not result.ok:
        recovered_content = _recover_deerflow_price_map_content(deerflow, thread_id, result.error or "")
        if recovered_content:
            try:
                payload = extract_deerflow_price_json(recovered_content)
                return price_map_from_deerflow_payload(
                    fallback=baseline,
                    payload=payload,
                    current_price=technical.close,
                    deerflow_thread_id=thread_id,
                )
            except Exception as exc:
                if settings.price_map_deerflow_required:
                    raise
                baseline.explanation["deerflow"] = f"DeerFlow 延迟结果无法解析，已保留本地基线：{exc}"
                return baseline
        if settings.price_map_deerflow_required:
            raise RuntimeError(result.error or "DeerFlow price map analysis failed")
        baseline.explanation["deerflow"] = f"DeerFlow 价格解析失败，已保留本地基线：{result.error or result.backend}"
        return baseline

    try:
        payload = extract_deerflow_price_json(result.content)
        return price_map_from_deerflow_payload(
            fallback=baseline,
            payload=payload,
            current_price=technical.close,
            deerflow_thread_id=result.thread_id or thread_id,
        )
    except Exception as exc:
        if settings.price_map_deerflow_required:
            raise
        baseline.explanation["deerflow"] = f"DeerFlow 返回无法解析，已保留本地基线：{exc}"
        return baseline


def _recover_deerflow_price_map_content(deerflow: Any, thread_id: str, error: str) -> str | None:
    if "504" not in error and "timeout" not in error.lower() and "time-out" not in error.lower():
        return None
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            history = deerflow.get_history(thread_id, limit=3)
            content = extract_latest_ai_content_from_history(history)
            if content:
                return content
        except Exception:
            pass
        time.sleep(5)
    return None


def _price_map_symbol_filter() -> list[str]:
    raw = os.getenv("TENX_PRICE_MAP_SYMBOLS", "").strip()
    if not raw:
        return []
    return [item.strip().upper() for item in re.split(r"[\s,]+", raw) if item.strip()]


def build_price_map(settings: Settings) -> None:
    with connect(settings) as conn:
        symbol_filter = _price_map_symbol_filter()
        if symbol_filter:
            for table in (
                "ads.watchlist_alert_daily",
                "ads.price_map_hit_review_daily",
                "ads.price_map_history_daily",
                "ads.price_map_current",
                "dws.security_scenario_path_daily",
                "dws.security_key_level_daily",
                "dws.security_target_range_daily",
                "dwd.security_price_technical_daily",
            ):
                conn.execute(f"DELETE FROM {table} WHERE UPPER(symbol) = ANY(%s)", (symbol_filter,))
        else:
            conn.execute(
                """
                TRUNCATE TABLE
                    ads.price_map_current,
                    dws.security_scenario_path_daily,
                    dws.security_key_level_daily,
                    dws.security_target_range_daily,
                    dwd.security_price_technical_daily
                RESTART IDENTITY CASCADE;
                """
            )

        latest_trade_dates = conn.execute(
            """
            SELECT market, MAX(trade_date) AS trade_date
            FROM dwd.security_market_daily
            GROUP BY market
            """
        ).fetchall()
        latest_trade_date_by_market = {row["market"]: row["trade_date"] for row in latest_trade_dates}

        securities_sql = "SELECT security_id, market, symbol FROM dim.security"
        securities_params: tuple[Any, ...] = ()
        if symbol_filter:
            securities_sql += " WHERE UPPER(symbol) = ANY(%s)"
            securities_params = (symbol_filter,)
        securities = conn.execute(f"{securities_sql} ORDER BY market, symbol", securities_params).fetchall()
        for security in securities:
            security_id = security["security_id"]
            market = security["market"]
            trade_date = latest_trade_date_by_market.get(market)
            if trade_date is None:
                continue

            price_rows = conn.execute(
                """
                SELECT *
                FROM dwd.security_market_daily
                WHERE security_id = %s
                ORDER BY trade_date
                """,
                (security_id,),
            ).fetchall()
            technical = build_technical_snapshot([dict(row) for row in price_rows])
            if technical is None:
                continue

            latest_market_row = next((row for row in reversed(price_rows) if row["trade_date"] == trade_date), price_rows[-1])
            financial = conn.execute(
                """
                SELECT *
                FROM dwd.security_financial_quarterly
                WHERE security_id = %s
                ORDER BY report_period DESC
                LIMIT 1
                """,
                (security_id,),
            ).fetchone()
            score = conn.execute(
                """
                SELECT *
                FROM dws.security_score_component_daily
                WHERE security_id = %s AND trade_date = %s
                """,
                (security_id, trade_date),
            ).fetchone()
            evidence_rows = conn.execute(
                """
                SELECT object_key
                FROM dwd.security_event_timeline
                WHERE security_id = %s
                ORDER BY event_time DESC
                LIMIT 3
                """,
                (security_id,),
            ).fetchall()
            evidence_refs = [row["object_key"] for row in evidence_rows if row["object_key"]]
            option_summary = None
            if market == "US":
                option_row = conn.execute(
                    """
                    SELECT *
                    FROM dws.security_option_chain_summary_daily
                    WHERE market = %s AND symbol = %s
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """,
                    (market, security["symbol"]),
                ).fetchone()
                option_summary = dict(option_row) if option_row else None
            estimate = conn.execute(
                """
                SELECT *
                FROM dwd.security_estimate_current
                WHERE security_id = %s
                """,
                (security_id,),
            ).fetchone()
            earnings_calendar = conn.execute(
                """
                SELECT *
                FROM dwd.security_earnings_calendar_current
                WHERE security_id = %s
                """,
                (security_id,),
            ).fetchone()
            price_map = _price_map_with_deerflow(
                settings=settings,
                market=market,
                symbol=security["symbol"],
                trade_date=trade_date,
                technical=technical,
                latest_market_row=dict(latest_market_row),
                financial=dict(financial) if financial else None,
                score=dict(score) if score else None,
                option_summary=option_summary,
                estimate=dict(estimate) if estimate else None,
                earnings_calendar=dict(earnings_calendar) if earnings_calendar else None,
                evidence_refs=evidence_refs,
            )

            conn.execute(
                """
                INSERT INTO dwd.security_price_technical_daily (
                    security_id, market, symbol, trade_date, close, high_52w, low_52w, position_52w,
                    ma20, ma60, ma120, ma250, atr14, volatility20, support_level, resistance_level,
                    volume_price_low, volume_price_high, valuation_percentile
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    security_id,
                    market,
                    security["symbol"],
                    trade_date,
                    technical.close,
                    technical.high_52w,
                    technical.low_52w,
                    technical.position_52w,
                    technical.ma20,
                    technical.ma60,
                    technical.ma120,
                    technical.ma250,
                    technical.atr14,
                    technical.volatility20,
                    technical.support_level,
                    technical.resistance_level,
                    technical.volume_price_low,
                    technical.volume_price_high,
                    technical.valuation_percentile,
                ),
            )

            for target in price_map.targets:
                conn.execute(
                    """
                    INSERT INTO dws.security_target_range_daily (
                        security_id, market, symbol, trade_date, scenario, horizon, target_low, target_high,
                        target_mid, upside_pct_mid, method, confidence, assumptions, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        security_id,
                        market,
                        security["symbol"],
                        trade_date,
                        target.scenario,
                        target.horizon,
                        target.target_low,
                        target.target_high,
                        target.target_mid,
                        target.upside_pct_mid,
                        target.method,
                        target.confidence,
                        _json(target.assumptions),
                        _json(target.evidence_refs),
                    ),
                )

            for level in price_map.key_levels:
                conn.execute(
                    """
                    INSERT INTO dws.security_key_level_daily (
                        level_id, security_id, market, symbol, trade_date, level_type, level_low, level_high,
                        strength, distance_pct, source, note, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        level.level_id,
                        security_id,
                        market,
                        security["symbol"],
                        trade_date,
                        level.level_type,
                        level.level_low,
                        level.level_high,
                        level.strength,
                        level.distance_pct,
                        level.source,
                        level.note,
                        _json(level.evidence_refs),
                    ),
                )

            for path in price_map.scenario_paths:
                conn.execute(
                    """
                    INSERT INTO dws.security_scenario_path_daily (
                        path_id, security_id, market, symbol, trade_date, path_name, probability, confidence,
                        trigger, target_scenario, invalidation, explanation, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        path.path_id,
                        security_id,
                        market,
                        security["symbol"],
                        trade_date,
                        path.path_name,
                        path.probability,
                        path.confidence,
                        path.trigger,
                        path.target_scenario,
                        path.invalidation,
                        path.explanation,
                        _json(path.evidence_refs),
                    ),
                )

            targets_by_scenario = {target.scenario: target for target in price_map.targets}
            key_levels = [_key_level_payload(level) for level in price_map.key_levels]
            scenario_paths = [_scenario_path_payload(path) for path in price_map.scenario_paths]
            conn.execute(
                """
                INSERT INTO ads.price_map_current (
                    security_id, market, symbol, as_of_date, current_price, posture, posture_label, confidence,
                    base_target, bull_target, bear_zone, key_levels, scenario_paths, invalidation_rules,
                    evidence_refs, explanation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (security_id) DO UPDATE SET
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    as_of_date = EXCLUDED.as_of_date,
                    current_price = EXCLUDED.current_price,
                    posture = EXCLUDED.posture,
                    posture_label = EXCLUDED.posture_label,
                    confidence = EXCLUDED.confidence,
                    base_target = EXCLUDED.base_target,
                    bull_target = EXCLUDED.bull_target,
                    bear_zone = EXCLUDED.bear_zone,
                    key_levels = EXCLUDED.key_levels,
                    scenario_paths = EXCLUDED.scenario_paths,
                    invalidation_rules = EXCLUDED.invalidation_rules,
                    evidence_refs = EXCLUDED.evidence_refs,
                    explanation = EXCLUDED.explanation,
                    updated_at = NOW()
                """,
                (
                    security_id,
                    market,
                    security["symbol"],
                    trade_date,
                    technical.close,
                    price_map.posture,
                    price_map.posture_label,
                    price_map.confidence,
                    _json(_target_range_payload(targets_by_scenario["base"])),
                    _json(_target_range_payload(targets_by_scenario["bull"])),
                    _json(_target_range_payload(targets_by_scenario["bear"])),
                    _json(key_levels),
                    _json(scenario_paths),
                    _json(price_map.invalidation_rules),
                    _json(price_map.evidence_refs),
                    _json(price_map.explanation),
                ),
            )

            base_payload = _target_range_payload(targets_by_scenario["base"])
            bull_payload = _target_range_payload(targets_by_scenario["bull"])
            bear_payload = _target_range_payload(targets_by_scenario["bear"])
            conn.execute(
                """
                INSERT INTO ads.price_map_history_daily (
                    security_id, market, symbol, snapshot_date, current_price, confidence, method,
                    base_target, bull_target, bear_zone, explanation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (security_id, snapshot_date) DO UPDATE SET
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    current_price = EXCLUDED.current_price,
                    confidence = EXCLUDED.confidence,
                    method = EXCLUDED.method,
                    base_target = EXCLUDED.base_target,
                    bull_target = EXCLUDED.bull_target,
                    bear_zone = EXCLUDED.bear_zone,
                    explanation = EXCLUDED.explanation
                """,
                (
                    security_id,
                    market,
                    security["symbol"],
                    trade_date,
                    technical.close,
                    price_map.confidence,
                    base_payload["method"],
                    _json(base_payload),
                    _json(bull_payload),
                    _json(bear_payload),
                    _json(price_map.explanation),
                ),
            )

            watchlist = conn.execute(
                """
                SELECT user_id
                FROM dwd.user_watchlist_state_current
                WHERE security_id = %s AND state = 'watching'
                """,
                (security_id,),
            ).fetchall()
            if not watchlist:
                continue
            base = targets_by_scenario["base"]
            bull = targets_by_scenario["bull"]
            bear = targets_by_scenario["bear"]
            alert_type = None
            severity = "medium"
            message = None
            if bear.target_high is not None and technical.close <= bear.target_high:
                alert_type = "price_enter_bear_zone"
                severity = "high"
                message = f"{security['symbol']} 进入 Bear 风险区，建议复核价格结构与核心逻辑。"
            elif bull.target_low is not None and technical.close >= bull.target_low:
                alert_type = "price_near_bull_target"
                message = f"{security['symbol']} 已接近 Bull 目标区，注意估值拥挤与兑现风险。"
            elif base.target_low is not None and technical.close >= base.target_low:
                alert_type = "price_near_base_target"
                message = f"{security['symbol']} 已进入 Base 目标区，建议复核上方空间和无效条件。"
            elif technical.valuation_percentile is not None and technical.valuation_percentile >= 0.9:
                alert_type = "valuation_crowded"
                message = f"{security['symbol']} 估值分位进入拥挤区，目标区间置信度下降。"
            if alert_type is None or message is None:
                continue
            for item in watchlist:
                conn.execute(
                    """
                    INSERT INTO ads.watchlist_alert_daily (
                        alert_id, user_id, market, symbol, trade_date, alert_type, severity,
                        alert_message, evidence_refs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        item["user_id"],
                        market,
                        security["symbol"],
                        trade_date,
                        alert_type,
                        severity,
                        message,
                        _json(price_map.evidence_refs),
                    ),
                )
        _build_price_map_hit_review(conn)


def _json_number(payload: Any, key: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    return _safe_float(payload.get(key))


def _build_price_map_hit_review(conn) -> None:
    histories = conn.execute(
        """
        SELECT *
        FROM ads.price_map_history_daily
        ORDER BY market, symbol, snapshot_date
        """
    ).fetchall()
    for history in histories:
        future_prices = conn.execute(
            """
            SELECT trade_date, close
            FROM dwd.security_market_daily
            WHERE security_id = %s
              AND trade_date > %s
              AND trade_date <= %s::date + INTERVAL '180 days'
              AND close IS NOT NULL
            ORDER BY trade_date
            """,
            (history["security_id"], history["snapshot_date"], history["snapshot_date"]),
        ).fetchall()
        if not future_prices:
            continue
        closes = [float(row["close"]) for row in future_prices if row["close"] is not None]
        if not closes:
            continue
        review_date = future_prices[-1]["trade_date"]
        max_close = max(closes)
        min_close = min(closes)
        base_mid = _json_number(history["base_target"], "mid")
        bull_low = _json_number(history["bull_target"], "low")
        bear_high = _json_number(history["bear_zone"], "high")
        base_hit = max_close >= base_mid if base_mid is not None else None
        bull_hit = max_close >= bull_low if bull_low is not None else None
        bear_breached = min_close <= bear_high if bear_high is not None else None
        horizon_days = (review_date - history["snapshot_date"]).days
        hit_summary = (
            f"{history['symbol']} {history['snapshot_date']} 价格地图复盘："
            f"{horizon_days} 天内最高 {max_close:.2f}、最低 {min_close:.2f}，"
            f"Base {'命中' if base_hit else '未命中' if base_hit is False else '无法判断'}，"
            f"Bull {'命中' if bull_hit else '未命中' if bull_hit is False else '无法判断'}，"
            f"Bear {'触发' if bear_breached else '未触发' if bear_breached is False else '无法判断'}。"
        )
        conn.execute(
            """
            INSERT INTO ads.price_map_hit_review_daily (
                security_id, market, symbol, snapshot_date, review_date, horizon_days,
                base_hit, bull_hit, bear_breached, max_close, min_close,
                base_target_mid, bull_target_low, bear_zone_high, hit_summary, metrics
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (security_id, snapshot_date, review_date) DO UPDATE SET
                horizon_days = EXCLUDED.horizon_days,
                base_hit = EXCLUDED.base_hit,
                bull_hit = EXCLUDED.bull_hit,
                bear_breached = EXCLUDED.bear_breached,
                max_close = EXCLUDED.max_close,
                min_close = EXCLUDED.min_close,
                base_target_mid = EXCLUDED.base_target_mid,
                bull_target_low = EXCLUDED.bull_target_low,
                bear_zone_high = EXCLUDED.bear_zone_high,
                hit_summary = EXCLUDED.hit_summary,
                metrics = EXCLUDED.metrics,
                created_at = NOW()
            """,
            (
                history["security_id"],
                history["market"],
                history["symbol"],
                history["snapshot_date"],
                review_date,
                horizon_days,
                base_hit,
                bull_hit,
                bear_breached,
                max_close,
                min_close,
                base_mid,
                bull_low,
                bear_high,
                hit_summary,
                _json(
                    {
                        "history_confidence": history["confidence"],
                        "history_method": history["method"],
                        "future_close_count": len(closes),
                    }
                ),
            ),
        )


def run_all(settings: Settings) -> None:
    build_dwd(settings)
    build_dws(settings)
    build_ads(settings)
    build_price_map(settings)


def fetch_ads_preview(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    with connect(settings) as conn:
        return {
            "candidate_pool": conn.execute(
                "SELECT market, symbol, rank_no, total_score, reason_summary FROM ads.candidate_pool_daily ORDER BY market, rank_no"
            ).fetchall(),
            "research_cards": conn.execute(
                "SELECT market, symbol, total_score, thesis FROM ads.research_card_current ORDER BY market, total_score DESC"
            ).fetchall(),
            "watchlist_alerts": conn.execute(
                "SELECT user_id, market, symbol, alert_type, severity, alert_message FROM ads.watchlist_alert_daily ORDER BY created_at, market, symbol"
            ).fetchall(),
            "theme_radar": conn.execute(
                "SELECT market, theme_name, heat_score, status FROM ads.theme_radar_daily ORDER BY market, heat_score DESC"
            ).fetchall(),
            "price_maps": conn.execute(
                "SELECT market, symbol, current_price, posture_label, confidence, base_target, bear_zone FROM ads.price_map_current ORDER BY market, symbol"
            ).fetchall(),
            "price_map_hit_reviews": conn.execute(
                "SELECT market, symbol, snapshot_date, review_date, horizon_days, base_hit, bull_hit, bear_breached, hit_summary FROM ads.price_map_hit_review_daily ORDER BY market, symbol, snapshot_date DESC"
            ).fetchall(),
        }


def fetch_price_map_preview(settings: Settings, market: str, symbol: str) -> dict[str, Any] | None:
    with connect(settings) as conn:
        return conn.execute(
            """
            SELECT market, symbol, as_of_date, current_price, posture, posture_label, confidence,
                   base_target, bull_target, bear_zone, key_levels, scenario_paths,
                   invalidation_rules, evidence_refs, explanation
            FROM ads.price_map_current
            WHERE market = %s AND symbol = %s
            """,
            (market.upper(), symbol.upper()),
        ).fetchone()


def fetch_price_map_hit_review_preview(settings: Settings, market: str, symbol: str) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        return conn.execute(
            """
            SELECT market, symbol, snapshot_date, review_date, horizon_days,
                   base_hit, bull_hit, bear_breached, max_close, min_close,
                   base_target_mid, bull_target_low, bear_zone_high, hit_summary, metrics
            FROM ads.price_map_hit_review_daily
            WHERE market = %s AND symbol = %s
            ORDER BY snapshot_date DESC, review_date DESC
            LIMIT 20
            """,
            (market.upper(), symbol.upper()),
        ).fetchall()


def refresh_us_option_chains(settings: Settings, symbols: list[str] | None = None) -> list[dict[str, Any]]:
    target_symbols = symbols or settings.market_universes["US"].symbols
    results: list[dict[str, Any]] = []
    for symbol in target_symbols:
        results.append(refresh_option_chain_for_symbol(symbol, market="US", settings=settings))
    return results
