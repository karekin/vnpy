from __future__ import annotations

from datetime import date

from vnpy.web.services.political_signal_service import PoliticalSignalService
from vnpy.web.tenx_hunter.event_monitor import (
    build_earnings_events,
    build_event_monitor_snapshot,
    build_fomc_events,
    build_trump_events,
)


def test_fomc_events_include_next_decision_window() -> None:
    events = build_fomc_events(market="US", today=date(2026, 6, 4), horizon_days=30)

    assert events[0].event_id == "fomc::2026-06-17"
    assert events[0].priority == "P1"
    assert events[0].due_at == date(2026, 6, 14)
    assert events[0].matched_rule == "macro.fomc"


def test_watchlist_earnings_events_use_observed_symbols_only() -> None:
    rows = [
        {
            "symbol": "MU",
            "company_name": "Micron Technology",
            "next_earnings_date": "2026-06-18",
            "fiscal_period": "FY2026 Q3",
            "time_of_day": "AMC",
            "data_quality_flag": "ok",
            "source_vendor": "yahoo",
        }
    ]

    events = build_earnings_events(rows, market="US", today=date(2026, 6, 4), horizon_days=45)

    assert len(events) == 1
    assert events[0].symbol == "MU"
    assert events[0].event_type == "earnings"
    assert events[0].evidence_grade == "B"
    assert "FY2026 Q3" in events[0].summary


def test_trump_events_promote_watchlist_rumor_as_verification_alert() -> None:
    mentions = PoliticalSignalService()._mention_rows()

    events = build_trump_events(mentions, market="US", watchlist_symbols={"MU"}, today=date(2026, 6, 4))

    mu_events = [event for event in events if event.symbol == "MU"]
    assert mu_events
    assert mu_events[0].priority == "P2"
    assert mu_events[0].evidence_grade == "D"
    assert mu_events[0].matched_rule == "political.trump"


def test_event_monitor_snapshot_combines_asset_event_rules_without_remote_fetch() -> None:
    mentions = PoliticalSignalService()._mention_rows()
    earnings_rows = [
        {
            "symbol": "MU",
            "company_name": "Micron Technology",
            "next_earnings_date": "2026-06-18",
            "fiscal_period": "FY2026 Q3",
            "time_of_day": "AMC",
            "data_quality_flag": "ok",
            "source_vendor": "yahoo",
        }
    ]

    snapshot = build_event_monitor_snapshot(
        market="US",
        watchlist_symbols={"MU", "ASTS"},
        earnings_rows=earnings_rows,
        political_mentions=mentions,
        today=date(2026, 6, 4),
        fetch_remote=False,
    )

    assert {rule.key for rule in snapshot.rules} == {
        "macro.fomc",
        "watchlist.earnings",
        "political.trump",
        "executive.jensen",
    }
    assert any(event.event_type == "macro-fomc" for event in snapshot.events)
    assert any(event.event_type == "earnings" and event.symbol == "MU" for event in snapshot.events)
    assert any(event.event_type == "political-trump" and event.symbol == "MU" for event in snapshot.events)
    assert any(source.key == "executive.jensen" and source.status == "degraded" for source in snapshot.source_status)
