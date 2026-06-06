from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha1
from typing import Any
from zoneinfo import ZoneInfo

from vnpy.web.contracts.tenx_hunter import TenxAlertSeverity
from vnpy.web.tenx_hunter.real_sources import request_json


FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
NVIDIA_NEWS_URL = "https://nvidianews.nvidia.com/"
TRUMP_MONITOR_URL = "https://open-cabinet.org/officials/trump-donald-j"

WATCHLIST_RELATED_TO_NVIDIA = {"NVDA", "MU", "AMD", "AVGO", "TSM", "ARM", "SMCI", "PLTR", "DELL", "IBM"}


@dataclass(frozen=True)
class EventMonitorSource:
    key: str
    label: str
    source: str
    source_url: str
    status: str
    detail: str
    updated_at: str


@dataclass(frozen=True)
class EventMonitorRule:
    key: str
    label: str
    event_type: str
    priority: TenxAlertSeverity
    scope: str
    cadence: str
    source: str
    source_url: str
    enabled: bool = True


@dataclass(frozen=True)
class EventMonitorEvent:
    event_id: str
    market: str
    symbol: str
    event_type: str
    title: str
    summary: str
    event_time: datetime
    due_at: date | None
    priority: TenxAlertSeverity
    evidence_grade: str
    confidence: str
    source: str
    source_url: str
    status: str
    matched_rule: str
    asset_relevance: str
    event_layer: list[str]
    structure_layer: list[str]
    execution_layer: list[str]
    invalidation_signals: list[str]
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventMonitorSnapshot:
    snapshot_at: datetime
    source_status: list[EventMonitorSource]
    rules: list[EventMonitorRule]
    events: list[EventMonitorEvent]
    notes: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def event_digest(*parts: str) -> str:
    return sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def format_utc_label(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def monitor_rules() -> list[EventMonitorRule]:
    return [
        EventMonitorRule(
            key="macro.fomc",
            label="美联储议息会议",
            event_type="macro-fomc",
            priority="P1",
            scope="US 组合全局",
            cadence="每日检查未来 45 天",
            source="Federal Reserve",
            source_url=FED_FOMC_URL,
        ),
        EventMonitorRule(
            key="watchlist.earnings",
            label="观察池财报日",
            event_type="earnings",
            priority="P2",
            scope="仅观察池股票",
            cadence="每日检查未来 45 天",
            source="Yahoo Finance earnings calendar",
            source_url="https://finance.yahoo.com/calendar/earnings/",
        ),
        EventMonitorRule(
            key="political.trump",
            label="特朗普公开声援 / 持仓披露",
            event_type="political-trump",
            priority="P2",
            scope="观察池 + 已确认政治信号",
            cadence="每轮刷新复核证据等级",
            source="Open Cabinet / OGE + curated public mention queue",
            source_url=TRUMP_MONITOR_URL,
        ),
        EventMonitorRule(
            key="executive.jensen",
            label="黄仁勋 / NVIDIA 公开事件",
            event_type="executive-jensen",
            priority="P2",
            scope="NVDA 与观察池内 AI/半导体暴露",
            cadence="GDELT 新闻检索 + 官方新闻页复核",
            source="GDELT Doc API + NVIDIA Newsroom",
            source_url=NVIDIA_NEWS_URL,
        ),
    ]


def _fomc_decision_datetime(day: date) -> datetime:
    eastern = ZoneInfo("America/New_York")
    local = datetime.combine(day, time(14, 0), tzinfo=eastern)
    return local.astimezone(timezone.utc)


def build_fomc_events(*, market: str, today: date | None = None, horizon_days: int = 180) -> list[EventMonitorEvent]:
    today = today or date.today()
    # Fallback calendar is intentionally small and explicit; source URL remains the Fed calendar for human verification.
    decision_dates = [
        date(2026, 1, 28),
        date(2026, 3, 18),
        date(2026, 4, 29),
        date(2026, 6, 17),
        date(2026, 7, 29),
        date(2026, 9, 16),
        date(2026, 10, 28),
        date(2026, 12, 9),
    ]
    end = today + timedelta(days=horizon_days)
    events: list[EventMonitorEvent] = []
    for day in decision_dates:
        if day < today or day > end:
            continue
        due_at = day - timedelta(days=3)
        events.append(
            EventMonitorEvent(
                event_id=f"fomc::{day.isoformat()}",
                market=market,
                symbol="US-MARKET",
                event_type="macro-fomc",
                title=f"FOMC 议息会议决议窗口 {day.isoformat()}",
                summary="组合级宏观事件：利率路径、点阵图、记者会措辞会直接改变成长股久期和期权 IV。",
                event_time=_fomc_decision_datetime(day),
                due_at=due_at,
                priority="P1" if (day - today).days <= 14 else "P2",
                evidence_grade="A",
                confidence="high",
                source="Federal Reserve",
                source_url=FED_FOMC_URL,
                status="scheduled",
                matched_rule="macro.fomc",
                asset_relevance="影响美股组合折现率、风险偏好和高 beta 仓位暴露。",
                event_layer=["确认利率决议、点阵图和记者会是否改变市场预期", "复核成长股久期和 AI/半导体 beta 暴露"],
                structure_layer=["检查 VIX、10Y yield、美元指数和 QQQ/SPY 关键位", "复核观察池标的是否已提前 price in"],
                execution_layer=["会前降低不必要杠杆和裸期权暴露", "会后等方向和 IV 回落再表达"],
                invalidation_signals=["会议前市场已经充分定价且 IV 极端拥挤", "决议与预期一致且记者会没有新增变量"],
                raw_payload={"decision_date": day.isoformat(), "calendar_source": "fallback-fed-calendar"},
            )
        )
    return events


def build_earnings_events(
    rows: list[dict[str, Any]],
    *,
    market: str,
    today: date | None = None,
    horizon_days: int = 45,
) -> list[EventMonitorEvent]:
    today = today or date.today()
    end = today + timedelta(days=horizon_days)
    events: list[EventMonitorEvent] = []
    for row in rows:
        earnings_date = iso_date(row.get("next_earnings_date"))
        if earnings_date is None or earnings_date < today or earnings_date > end:
            continue
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        days_to = (earnings_date - today).days
        company = str(row.get("company_name") or symbol)
        fiscal_period = str(row.get("fiscal_period") or "next fiscal period")
        time_of_day = str(row.get("time_of_day") or "time TBA")
        priority: TenxAlertSeverity = "P1" if days_to <= 3 else "P2"
        events.append(
            EventMonitorEvent(
                event_id=f"earnings::{market}::{symbol}::{earnings_date.isoformat()}",
                market=market,
                symbol=symbol,
                event_type="earnings",
                title=f"{symbol} 财报日 {earnings_date.isoformat()}",
                summary=f"{company} 预计在 {earnings_date.isoformat()} 发布 {fiscal_period} 财报，时间：{time_of_day}。",
                event_time=datetime.combine(earnings_date, time(12, 0), tzinfo=timezone.utc),
                due_at=max(today, earnings_date - timedelta(days=5)),
                priority=priority,
                evidence_grade="B" if row.get("data_quality_flag") == "ok" else "C",
                confidence="medium",
                source=str(row.get("source_vendor") or "earnings-calendar"),
                source_url="https://finance.yahoo.com/calendar/earnings/",
                status="scheduled",
                matched_rule="watchlist.earnings",
                asset_relevance="观察池持仓/候选仓位的预期差窗口，可能直接影响仓位收益。",
                event_layer=["核对营收、EPS、指引和管理层口径是否形成预期差", "确认是否为持仓收益的主事件窗口"],
                structure_layer=["检查财报前 IV、OI、Max Pain 和关键支撑/阻力", "复核价格地图 Base/Bull/Bear 区间"],
                execution_layer=["财报前定义最大亏损和隔夜仓位上限", "财报后只在指引和价格结构同时确认后加仓"],
                invalidation_signals=["财报日期变更或来源为 partial", "指引低于核心假设", "财报前价格已透支且 IV 极端"],
                raw_payload=row,
            )
        )
    return events


def build_trump_events(
    mention_rows: list[Any],
    *,
    market: str,
    watchlist_symbols: set[str],
    today: date | None = None,
) -> list[EventMonitorEvent]:
    today = today or date.today()
    events: list[EventMonitorEvent] = []
    for mention in mention_rows:
        symbol = str(getattr(mention, "symbol", "")).upper()
        if not symbol:
            continue
        status = str(getattr(mention, "status", "needs-verification"))
        evidence_grade = str(getattr(mention, "evidence_grade", "D"))
        include = symbol in watchlist_symbols or status in {"confirmed", "watching"}
        if not include:
            continue
        event_day = iso_date(getattr(mention, "event_date", None)) or today
        priority: TenxAlertSeverity = "P2" if symbol in watchlist_symbols or evidence_grade in {"A", "B"} else "P3"
        confidence = "high" if evidence_grade in {"A", "B"} else "low"
        source_url = str(getattr(mention, "source_url", "") or TRUMP_MONITOR_URL)
        events.append(
            EventMonitorEvent(
                event_id=f"trump::{market}::{symbol}::{event_day.isoformat()}::{event_digest(str(getattr(mention, 'headline', '')))}",
                market=market,
                symbol=symbol,
                event_type="political-trump",
                title=f"{symbol} 特朗普相关政治信号待复核",
                summary=str(getattr(mention, "summary", "")),
                event_time=datetime.combine(event_day, time(13, 30), tzinfo=timezone.utc),
                due_at=today,
                priority=priority,
                evidence_grade=evidence_grade,
                confidence=confidence,
                source=str(getattr(mention, "source", "political-signal-queue")),
                source_url=source_url,
                status=status,
                matched_rule="political.trump",
                asset_relevance="政治声援、政策受益或披露持仓可能改变短期风险偏好；必须先核验证据等级。",
                event_layer=["核验原始发言、官方文字稿、OGE 披露或可信媒体报道", "区分持仓披露、公开点名和政策受益三类信号"],
                structure_layer=["检查消息后价格是否已充分反映", "检查成交量、期权 OI 和关键价位是否确认"],
                execution_layer=["D 级截图只允许作为线索提醒", "升级到 B/A 证据后再考虑进入事件交易表达"],
                invalidation_signals=["无法找到原始出处", "媒体语境与股票催化无关", "价格已透支且没有基本面跟进"],
                raw_payload={
                    "headline": str(getattr(mention, "headline", "")),
                    "verification_note": str(getattr(mention, "verification_note", "")),
                    "next_action": str(getattr(mention, "next_action", "")),
                    "watchlist_rule": str(getattr(mention, "watchlist_rule", "")),
                },
            )
        )
    return events


def fetch_gdelt_articles(query: str, *, max_records: int = 5, timeout: int = 8) -> list[dict[str, Any]]:
    payload = request_json(
        GDELT_DOC_URL,
        params={
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": max_records,
            "sort": "HybridRel",
        },
        timeout=timeout,
    )
    articles = payload.get("articles", [])
    return articles if isinstance(articles, list) else []


def build_jensen_events(
    articles: list[dict[str, Any]],
    *,
    market: str,
    watchlist_symbols: set[str],
    today: date | None = None,
) -> list[EventMonitorEvent]:
    if not articles:
        return []
    today = today or date.today()
    related_symbols = sorted(watchlist_symbols & WATCHLIST_RELATED_TO_NVIDIA)
    primary_symbol = "NVDA" if "NVDA" in watchlist_symbols else (related_symbols[0] if related_symbols else "NVDA")
    first = articles[0]
    title = str(first.get("title") or "NVIDIA / Jensen Huang public signal")
    url = str(first.get("url") or NVIDIA_NEWS_URL)
    domain = str(first.get("domain") or "GDELT")
    seen_date = iso_date(str(first.get("seendate") or "")[:8]) or today
    relevance = (
        f"观察池相关暴露：{', '.join(related_symbols)}。"
        if related_symbols
        else "影响 AI 基础设施、半导体和高 beta 成长股风险偏好。"
    )
    return [
        EventMonitorEvent(
            event_id=f"jensen::{market}::{seen_date.isoformat()}::{event_digest(title, url)}",
            market=market,
            symbol=primary_symbol,
            event_type="executive-jensen",
            title="黄仁勋 / NVIDIA 公开事件待复核",
            summary=title,
            event_time=datetime.combine(seen_date, time(13, 30), tzinfo=timezone.utc),
            due_at=today,
            priority="P2",
            evidence_grade="B",
            confidence="medium",
            source=f"GDELT / {domain}",
            source_url=url,
            status="needs-review",
            matched_rule="executive.jensen",
            asset_relevance=relevance,
            event_layer=["确认黄仁勋公开发言、NVIDIA 官方新闻或可信媒体报道的原文", "判断是否改变 AI/半导体需求、供给或资本开支预期"],
            structure_layer=["复核 NVDA、SOXX、观察池半导体标的的关键价位", "检查消息后是否出现量价和期权结构确认"],
            execution_layer=["先更新观察池研究卡和价格地图", "只有当发言改变预期差时才升级为交易提醒"],
            invalidation_signals=["只是重复旧观点", "没有影响订单、供给、需求或政策的新增信息", "市场已充分反映且情绪拥挤"],
            raw_payload={"articles": articles[:5]},
        )
    ]


def build_event_monitor_snapshot(
    *,
    market: str,
    watchlist_symbols: set[str],
    earnings_rows: list[dict[str, Any]],
    political_mentions: list[Any],
    today: date | None = None,
    fetch_remote: bool = True,
) -> EventMonitorSnapshot:
    today = today or date.today()
    snapshot_at = utc_now()
    sources = [
        EventMonitorSource(
            key="fed.fomc",
            label="FOMC 官方日程",
            source="Federal Reserve",
            source_url=FED_FOMC_URL,
            status="ok",
            detail="使用内置 2026 FOMC 决议日程作为本地 fallback，复核链接指向官方日历。",
            updated_at=format_utc_label(snapshot_at),
        ),
        EventMonitorSource(
            key="watchlist.earnings",
            label="观察池财报日",
            source="DWD earnings calendar",
            source_url="https://finance.yahoo.com/calendar/earnings/",
            status="ok" if earnings_rows else "degraded",
            detail="从 dwd.security_earnings_calendar_current 读取观察池股票的下一次财报日。",
            updated_at=format_utc_label(snapshot_at),
        ),
        EventMonitorSource(
            key="political.trump",
            label="特朗普政治信号",
            source="Open Cabinet / curated public mention queue",
            source_url=TRUMP_MONITOR_URL,
            status="ok",
            detail="公开披露与点名线索按证据等级进入提醒，D 级只作为待核实线索。",
            updated_at=format_utc_label(snapshot_at),
        ),
    ]

    events = [
        *build_fomc_events(market=market, today=today),
        *build_earnings_events(earnings_rows, market=market, today=today),
        *build_trump_events(political_mentions, market=market, watchlist_symbols=watchlist_symbols, today=today),
    ]
    notes = ["事件监听只围绕资产收益相关变量：宏观利率、观察池财报、政治声援/披露、高管公开发言。"]

    try:
        articles = fetch_gdelt_articles('"Jensen Huang" OR "NVIDIA CEO"') if fetch_remote else []
        events.extend(build_jensen_events(articles, market=market, watchlist_symbols=watchlist_symbols, today=today))
        sources.append(
            EventMonitorSource(
                key="executive.jensen",
                label="黄仁勋公开事件",
                source="GDELT Doc API + NVIDIA Newsroom",
                source_url=NVIDIA_NEWS_URL,
                status="ok" if articles else "degraded",
                detail="通过 GDELT 检索公开报道，再用 NVIDIA 官方新闻页人工复核。" if fetch_remote else "页面加载不触发远程新闻检索；由手动刷新或 scheduler 更新。",
                updated_at=format_utc_label(snapshot_at),
            )
        )
    except Exception as exc:
        if fetch_remote:
            notes.append(f"GDELT 黄仁勋检索失败：{exc}")
        sources.append(
            EventMonitorSource(
                key="executive.jensen",
                label="黄仁勋公开事件",
                source="GDELT Doc API + NVIDIA Newsroom",
                source_url=NVIDIA_NEWS_URL,
                status="degraded",
                detail="远程新闻检索暂不可用，保留官方新闻页作为人工复核入口。",
                updated_at=format_utc_label(snapshot_at),
            )
        )

    events = sorted(events, key=lambda item: (item.event_time, item.priority, item.symbol))
    return EventMonitorSnapshot(
        snapshot_at=snapshot_at,
        source_status=sources,
        rules=monitor_rules(),
        events=events,
        notes=notes,
    )
