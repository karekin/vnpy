from __future__ import annotations

from datetime import datetime, timezone

from vnpy.web.tenx_hunter.options_chain import _normalize_option_rows, rank_option_targets, summarize_option_chain


def test_summarize_option_chain_should_score_liquid_bullish_chain() -> None:
    rows = [
        {
            "symbol": "AAPL",
            "market": "US",
            "trade_date": "2026-04-30",
            "expiration_date": "2026-05-15",
            "option_type": "call",
            "strike": 190.0,
            "bid": 2.4,
            "ask": 2.6,
            "volume": 5000,
            "open_interest": 12000,
            "implied_volatility": 0.32,
            "underlying_price": 188.0,
        },
        {
            "symbol": "AAPL",
            "market": "US",
            "trade_date": "2026-04-30",
            "expiration_date": "2026-05-15",
            "option_type": "put",
            "strike": 180.0,
            "bid": 1.1,
            "ask": 1.2,
            "volume": 1000,
            "open_interest": 4000,
            "implied_volatility": 0.34,
            "underlying_price": 188.0,
        },
    ]

    summary = summarize_option_chain(rows, symbol="AAPL", market="US", trade_date="2026-04-30")

    assert summary["contract_count"] == 2
    assert summary["flow_sentiment"] == "bullish"
    assert summary["call_put_volume_ratio"] == 5.0
    assert summary["wheel_rule_score"]["status"] == "wheel_actionable"
    assert summary["leaps_rule_score"]["status"] == "leaps_researchable"


def test_normalize_option_rows_should_flatten_yahoo_payload() -> None:
    rows = _normalize_option_rows(
        symbol="AAPL",
        market="US",
        trade_date="2026-04-30",
        source_event_time=datetime(2026, 4, 30, tzinfo=timezone.utc),
        result={
            "quote": {"regularMarketPrice": 188.0, "currency": "USD"},
            "options": [
                {
                    "expirationDate": 1778803200,
                    "calls": [
                        {
                            "contractSymbol": "AAPL260515C00190000",
                            "strike": 190,
                            "bid": 2.4,
                            "ask": 2.6,
                            "lastTradeDate": 1777593600,
                            "volume": 500,
                            "openInterest": 1200,
                            "impliedVolatility": 0.3,
                            "inTheMoney": False,
                            "contractSize": "REGULAR",
                        }
                    ],
                    "puts": [],
                }
            ],
        },
    )

    assert rows[0]["contract_symbol"] == "AAPL260515C00190000"
    assert rows[0]["expiration_date"] == "2026-05-15"
    assert rows[0]["option_type"] == "call"
    assert rows[0]["underlying_price"] == 188.0


def test_rank_option_targets_should_choose_highest_score_per_symbol() -> None:
    ranked = rank_option_targets(
        [
            {"symbol": "AAPL", "selection_score": 50, "liquidity_score": 90, "data_quality_flag": "ok"},
            {"symbol": "NVDA", "selection_score": 80, "liquidity_score": 70, "data_quality_flag": "ok"},
            {"symbol": "AAPL", "selection_score": 60, "liquidity_score": 80, "data_quality_flag": "ok"},
        ],
        top_n=2,
    )

    assert [item["symbol"] for item in ranked] == ["NVDA", "AAPL"]
    assert ranked[1]["selection_score"] == 60
