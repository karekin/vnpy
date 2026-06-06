-- ============================================================================
-- Unified schema for vnpy web services.
-- Layers: oltp (transactional), olap (analytical), dim (shared dimensions).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS oltp;
CREATE SCHEMA IF NOT EXISTS olap;
CREATE SCHEMA IF NOT EXISTS dim;

-- ============================================================================
-- dim — Shared dimension tables (unchanged from tenx_hunter pipeline)
-- ============================================================================

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

-- ============================================================================
-- oltp — Transactional tables (high-frequency CRUD, user-facing state)
-- ============================================================================

-- ---- Social Hot Stocks (snapshot cache) ----

CREATE TABLE IF NOT EXISTS oltp.social_hot_stock_snapshot (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_label TEXT NOT NULL,
    source_filter TEXT NOT NULL,
    source_url TEXT NOT NULL,
    window_hours INTEGER NOT NULL,
    refresh_seconds INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    fetched_at_epoch DOUBLE PRECISION NOT NULL,
    count INTEGER NOT NULL,
    provider_pages INTEGER NOT NULL,
    provider_pages_fetched INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    items_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_social_hot_lookup
    ON oltp.social_hot_stock_snapshot (source, source_filter, item_count, fetched_at_epoch DESC, id DESC);

-- ---- Investment Copilot ----

CREATE TABLE IF NOT EXISTS oltp.copilot_policy (
    id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oltp.copilot_action_decision (
    action_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    user_note TEXT NOT NULL DEFAULT '',
    decision_reason TEXT NOT NULL DEFAULT '',
    snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oltp.ledger_account (
    account_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oltp.ledger_holding (
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, symbol, asset_type)
);

CREATE TABLE IF NOT EXISTS oltp.ledger_cashflow (
    event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---- Smart Allocation ----

CREATE TABLE IF NOT EXISTS oltp.allocation_profile (
    id TEXT PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS oltp.allocation_recommendation_status (
    profile_id TEXT NOT NULL,
    recommendation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    user_note TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (profile_id, recommendation_id)
);

-- ---- CB Quant (templates, jobs, task management) ----

CREATE TABLE IF NOT EXISTS oltp.cb_strategy_template (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    owner TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_cb_template_updated
    ON oltp.cb_strategy_template (updated_at DESC);

CREATE TABLE IF NOT EXISTS oltp.cb_strategy_template_config (
    template_id TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    config_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS oltp.cb_backtest_job (
    job_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    combo_id TEXT NOT NULL,
    rule_pack_id TEXT NOT NULL,
    template TEXT NOT NULL,
    "window" TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    business_date TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TEXT,
    eta TEXT,
    worker TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    setting_json JSONB NOT NULL,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_cb_backtest_job_status
    ON oltp.cb_backtest_job (status, business_date, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_oltp_cb_backtest_job_combo
    ON oltp.cb_backtest_job (combo_id);

CREATE TABLE IF NOT EXISTS oltp.cb_optimize_batch (
    batch_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_cb_opt_batch_status
    ON oltp.cb_optimize_batch (status, created_at DESC);

CREATE TABLE IF NOT EXISTS oltp.cb_optimize_task (
    task_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_cb_opt_task_status
    ON oltp.cb_optimize_task (status, created_at DESC);

CREATE TABLE IF NOT EXISTS oltp.cb_optimize_shard (
    shard_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    sequence INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oltp_cb_opt_shard_task
    ON oltp.cb_optimize_shard (task_id, stage, sequence ASC);
CREATE INDEX IF NOT EXISTS idx_oltp_cb_opt_shard_status
    ON oltp.cb_optimize_shard (status, created_at DESC);

-- ---- TenX Hunter user state (migrated from dwd/ods) ----

CREATE TABLE IF NOT EXISTS oltp.user_watch_action_raw (
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
    raw_payload JSONB
);

CREATE TABLE IF NOT EXISTS oltp.user_watchlist_state_current (
    user_id TEXT NOT NULL,
    security_id INTEGER NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,
    latest_action_time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, security_id)
);

CREATE TABLE IF NOT EXISTS oltp.user_alert_rule_current (
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

CREATE TABLE IF NOT EXISTS oltp.user_event_monitor_event_current (
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

CREATE INDEX IF NOT EXISTS idx_oltp_user_event_monitor
    ON oltp.user_event_monitor_event_current (user_id, market, event_time);

CREATE TABLE IF NOT EXISTS oltp.user_research_report_current (
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
    UNIQUE (user_id, market, symbol)
);

CREATE TABLE IF NOT EXISTS oltp.user_discover_candidate_current (
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

-- ============================================================================
-- olap — Analytical tables (batch reads/writes, time-series, aggregations)
-- ============================================================================

-- ---- Social Hot Stocks (item history) ----

CREATE TABLE IF NOT EXISTS olap.social_hot_stock_item_history (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES oltp.social_hot_stock_snapshot(id),
    symbol TEXT NOT NULL,
    mentions INTEGER NOT NULL,
    upvotes INTEGER NOT NULL,
    mention_change DOUBLE PRECISION,
    mention_change_pct DOUBLE PRECISION,
    rank_24h_ago INTEGER,
    heat_score DOUBLE PRECISION,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_olap_social_hot_item_symbol
    ON olap.social_hot_stock_item_history (symbol, fetched_at DESC);

-- ---- Smart Allocation (snapshots & cashflow) ----

CREATE TABLE IF NOT EXISTS olap.allocation_snapshot (
    id BIGSERIAL PRIMARY KEY,
    profile_id TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_olap_alloc_snapshot_profile
    ON olap.allocation_snapshot (profile_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS olap.allocation_cashflow_event (
    id BIGSERIAL PRIMARY KEY,
    profile_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

-- ---- CB Quant (results & analysis) ----

CREATE TABLE IF NOT EXISTS olap.cb_backtest_leaderboard (
    combo_id TEXT NOT NULL,
    rule_pack_id TEXT NOT NULL,
    "window" TEXT NOT NULL,
    business_date TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (combo_id, rule_pack_id, "window")
);

CREATE INDEX IF NOT EXISTS idx_olap_cb_lb_date
    ON olap.cb_backtest_leaderboard (business_date, updated_at DESC);

CREATE TABLE IF NOT EXISTS olap.cb_optimize_result (
    task_id TEXT NOT NULL,
    combo_id TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (task_id, combo_id)
);

CREATE INDEX IF NOT EXISTS idx_olap_cb_opt_result_rank
    ON olap.cb_optimize_result (task_id, rank ASC);

CREATE TABLE IF NOT EXISTS olap.cb_optimize_shard_result (
    task_id TEXT NOT NULL,
    shard_id TEXT NOT NULL,
    combo_id TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (task_id, shard_id, combo_id)
);

CREATE INDEX IF NOT EXISTS idx_olap_cb_opt_shard_result
    ON olap.cb_optimize_shard_result (task_id, shard_id, rank ASC);

CREATE TABLE IF NOT EXISTS olap.cb_optimize_top_bond (
    task_id TEXT NOT NULL,
    bond_id TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (task_id, bond_id)
);

CREATE INDEX IF NOT EXISTS idx_olap_cb_opt_top_bond
    ON olap.cb_optimize_top_bond (task_id, rank ASC);

CREATE TABLE IF NOT EXISTS olap.cb_optimize_task_analysis_snapshot (
    task_id TEXT PRIMARY KEY,
    combo_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_name TEXT NOT NULL,
    window_name TEXT NOT NULL,
    benchmark_name TEXT NOT NULL,
    initial_capital_wan DOUBLE PRECISION NOT NULL,
    used_range_start TEXT,
    used_range_end TEXT,
    summary_json JSONB NOT NULL,
    detail_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---- CB Tushare (market data) ----

CREATE TABLE IF NOT EXISTS olap.ts_trade_calendar (
    cal_date TEXT PRIMARY KEY,
    is_open BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_cal_open
    ON olap.ts_trade_calendar (is_open, cal_date);

CREATE TABLE IF NOT EXISTS olap.ts_cb_basic (
    ts_code TEXT PRIMARY KEY,
    bond_short_name TEXT,
    stk_code TEXT,
    maturity_date TEXT,
    issue_size TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS olap.ts_cb_daily_ods (
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (trade_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_cb_daily_date
    ON olap.ts_cb_daily_ods (trade_date);

CREATE TABLE IF NOT EXISTS olap.ts_stock_daily_ods (
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (trade_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_stock_daily_date
    ON olap.ts_stock_daily_ods (trade_date);

CREATE TABLE IF NOT EXISTS olap.ts_stock_daily_basic_ods (
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (trade_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_stock_basic_date
    ON olap.ts_stock_daily_basic_ods (trade_date);

CREATE TABLE IF NOT EXISTS olap.ts_cb_factor_daily (
    trade_date TEXT NOT NULL,
    bond_id TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (trade_date, bond_id)
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_cb_factor_date
    ON olap.ts_cb_factor_daily (trade_date);

CREATE TABLE IF NOT EXISTS olap.ts_cb_event_ods (
    event_type TEXT NOT NULL,
    biz_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    row_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    PRIMARY KEY (event_type, biz_date, ts_code, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_olap_ts_cb_event_type_date
    ON olap.ts_cb_event_ods (event_type, biz_date);

CREATE TABLE IF NOT EXISTS olap.ts_sync_log (
    id BIGSERIAL PRIMARY KEY,
    sync_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mode TEXT NOT NULL,
    source TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    trade_days INTEGER NOT NULL,
    cb_daily_rows INTEGER NOT NULL DEFAULT 0,
    stock_daily_rows INTEGER NOT NULL DEFAULT 0,
    event_rows INTEGER NOT NULL DEFAULT 0,
    factor_rows INTEGER NOT NULL DEFAULT 0,
    snapshot_rows INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT ''
);

-- ---- CB History (daily snapshots) ----

CREATE TABLE IF NOT EXISTS olap.cb_daily_snapshot (
    trade_date TEXT NOT NULL,
    bond_id TEXT NOT NULL,
    source TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, bond_id)
);

CREATE INDEX IF NOT EXISTS idx_olap_cb_daily_snap_date
    ON olap.cb_daily_snapshot (trade_date);

CREATE TABLE IF NOT EXISTS olap.cb_sync_log (
    id BIGSERIAL PRIMARY KEY,
    sync_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mode TEXT NOT NULL,
    source TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    upserted INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT ''
);

-- ---- TenX Hunter ODS (raw ingestion layer) ----

CREATE TABLE IF NOT EXISTS olap.us_equity_price_daily_raw (
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

CREATE TABLE IF NOT EXISTS olap.security_financial_statement_raw (
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

CREATE TABLE IF NOT EXISTS olap.sec_filing_document_raw (
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

CREATE TABLE IF NOT EXISTS olap.security_news_article_raw (
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

CREATE TABLE IF NOT EXISTS olap.security_institutional_activity_raw (
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

CREATE TABLE IF NOT EXISTS olap.us_analyst_estimate_raw (
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

CREATE TABLE IF NOT EXISTS olap.us_earnings_calendar_raw (
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

-- ---- TenX Hunter DWD (processed detail layer) ----

CREATE TABLE IF NOT EXISTS olap.security_market_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_price_technical_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_financial_quarterly (
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

CREATE TABLE IF NOT EXISTS olap.security_estimate_current (
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

CREATE TABLE IF NOT EXISTS olap.security_earnings_calendar_current (
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

CREATE TABLE IF NOT EXISTS olap.security_event_timeline (
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

CREATE TABLE IF NOT EXISTS olap.security_document_signal (
    signal_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES olap.security_event_timeline(event_id),
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

-- ---- TenX Hunter DWS (aggregation layer) ----

CREATE TABLE IF NOT EXISTS olap.security_feature_daily (
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
    turnover_rate NUMERIC(10,4),
    risk_count INTEGER NOT NULL,
    negative_event_count INTEGER NOT NULL,
    theme_count INTEGER NOT NULL,
    positive_signal_count INTEGER NOT NULL,
    PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE IF NOT EXISTS olap.security_score_component_daily (
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

CREATE TABLE IF NOT EXISTS olap.theme_heat_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_candidate_rank_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_target_range_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_key_level_daily (
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

CREATE TABLE IF NOT EXISTS olap.security_scenario_path_daily (
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

-- ---- TenX Hunter ADS (application layer) ----

CREATE TABLE IF NOT EXISTS olap.candidate_pool_daily (
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

CREATE TABLE IF NOT EXISTS olap.research_card_current (
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

CREATE TABLE IF NOT EXISTS olap.price_map_current (
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

CREATE TABLE IF NOT EXISTS olap.price_map_history_daily (
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

CREATE TABLE IF NOT EXISTS olap.price_map_hit_review_daily (
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

CREATE TABLE IF NOT EXISTS olap.watchlist_alert_daily (
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

CREATE TABLE IF NOT EXISTS olap.theme_radar_daily (
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
