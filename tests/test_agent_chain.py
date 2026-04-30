from __future__ import annotations

import pytest

from vnpy.web.agent_chain.temporal_worker import (
    _calculate_portfolio_fit,
    _extract_json_object,
    _normalize_symbols,
    validate_agent_json,
)


def test_extract_json_object_should_accept_fenced_json() -> None:
    payload = _extract_json_object(
        """
        ```json
        {"symbol":"AAPL","wheel_review":{"status":"wheel_watch"},"leaps_review":{"status":"leaps_watch"}}
        ```
        """
    )

    assert payload["symbol"] == "AAPL"
    assert payload["wheel_review"]["status"] == "wheel_watch"


def test_extract_json_object_should_reject_non_json_text() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _extract_json_object("not a structured response")


def test_normalize_symbols_should_dedupe_and_default() -> None:
    assert _normalize_symbols("aapl, msft\nAAPL") == ["AAPL", "MSFT"]
    assert _normalize_symbols("")[:2] == ["AAPL", "MSFT"]


def test_calculate_portfolio_fit_should_allow_recommend_when_budget_fits() -> None:
    fit = _calculate_portfolio_fit(
        symbol="MSFT",
        option_summary={"underlying_price": 90, "flow_sentiment": "bullish"},
        profile={"wheel_symbols": ["MSFT.US"], "quality_stock_symbols": ["MSFT.US"], "leaps_symbols": []},
        snapshot={
            "total_equity": 100000,
            "wheel_value": 5000,
            "leaps_value": 0,
            "margin_used": 0,
            "single_stock_values": {},
        },
        targets={
            "wheel_value": 20000,
            "leaps_value": 5000,
            "single_stock_limit": 10000,
            "margin_limit": 25000,
        },
        guardrails=[],
    )

    assert fit["status"] == "eligible"
    assert fit["recommendation_gate"] == "recommend_allowed"
    assert fit["estimated_cash_required_for_one_put"] == 9000


def test_calculate_portfolio_fit_should_block_when_snapshot_missing() -> None:
    fit = _calculate_portfolio_fit(
        symbol="AAPL",
        option_summary={"underlying_price": 180},
        profile={},
        snapshot={"total_equity": 0},
        targets={},
        guardrails=[],
    )

    assert fit["status"] == "unconfigured"
    assert fit["recommendation_gate"] == "no_recommend"


def test_validate_agent_json_should_downgrade_recommend_when_portfolio_gate_blocks() -> None:
    parsed = validate_agent_json(
        {
            "symbol": "MSFT",
            "content": """
            {
              "symbol": "MSFT",
              "daily_target_review": {"status": "recommend", "rank_reason": "strong chain"},
              "wheel_review": {"status": "wheel_actionable"},
              "leaps_review": {"status": "leaps_researchable"},
              "manual_checks": [],
              "data_quality": "ok"
            }
            """,
            "market_context": {
                "portfolio_context": {
                    "portfolio_fit": {
                        "status": "unconfigured",
                        "recommendation_gate": "no_recommend",
                        "reason": "missing snapshot",
                        "blockers": ["portfolio_snapshot_missing"],
                    }
                }
            },
        }
    )

    assert parsed["daily_target_review"]["status"] == "avoid"
    assert parsed["daily_target_review"]["portfolio_gate_adjustment"]["from"] == "recommend"
