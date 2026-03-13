from __future__ import annotations

import pandas as pd

from vnpy.web.core.cb_backtest.candidate_selection import (
    build_candidate_codes,
    filter_multiple_factors,
    prepare_candidate_pool,
)
from vnpy.web.core.cb_backtest.strategy_config import build_strategy_parameters


def _row(
    *,
    bond_code: str,
    close_price: float,
    conversion_premium_pct: float,
    outstanding_amount_yi: float,
    underlying_market_cap_yi: float,
    underlying_volatility: float,
    underlying_pb: float,
    listing_date: str = "2024-01-01",
    days_to_maturity: int = 600,
    days_to_redeem: int | None = None,
) -> dict[str, object]:
    return {
        "bond_code": bond_code,
        "bond_name": f"{bond_code}转债",
        "put_status": "normal",
        "is_listed": True,
        "is_redeem_triggered": False,
        "bond_pure_value_ratio": 1.2,
        "close_price": close_price,
        "open_price": close_price - 0.5,
        "high_price": close_price + 0.5,
        "low_price": close_price - 1.0,
        "pre_close_price": close_price - 0.2,
        "bond_pct_change": 0.5,
        "pure_bond_value": 95.0,
        "option_value": 12.0,
        "underlying_close_price": 18.0,
        "conversion_price": 12.0,
        "conversion_premium_pct": conversion_premium_pct,
        "days_to_maturity": days_to_maturity,
        "days_to_redeem": days_to_redeem,
        "outstanding_amount_yi": outstanding_amount_yi,
        "issue_size_yi": outstanding_amount_yi + 1.0,
        "turnover_rate_pct": 2.0,
        "turnover_amount_wan": 4000.0,
        "outstanding_to_market_cap_ratio": 0.03,
        "ytm_to_maturity_pct": 1.5,
        "rating": "AA+",
        "volume_hand": 2000.0,
        "limit_status": 0,
        "underlying_pb": underlying_pb,
        "underlying_market_cap_yi": underlying_market_cap_yi,
        "underlying_volatility": underlying_volatility,
        "listing_date": listing_date,
        "is_tradeable": True,
    }


def test_build_candidate_codes_should_match_filter_multiple_factors_order() -> None:
    frame = pd.DataFrame(
        [
            _row(
                bond_code="110001",
                close_price=108.0,
                conversion_premium_pct=18.0,
                outstanding_amount_yi=6.0,
                underlying_market_cap_yi=80.0,
                underlying_volatility=36.0,
                underlying_pb=1.8,
            ),
            _row(
                bond_code="110002",
                close_price=118.0,
                conversion_premium_pct=28.0,
                outstanding_amount_yi=12.0,
                underlying_market_cap_yi=120.0,
                underlying_volatility=24.0,
                underlying_pb=1.2,
            ),
            _row(
                bond_code="110003",
                close_price=124.0,
                conversion_premium_pct=32.0,
                outstanding_amount_yi=24.0,
                underlying_market_cap_yi=220.0,
                underlying_volatility=18.0,
                underlying_pb=0.9,
            ),
        ]
    ).set_index("bond_code", drop=False)

    params = build_strategy_parameters({})
    prepared = prepare_candidate_pool(frame, trade_date="2026-03-11")

    codes = build_candidate_codes(prepared, strategy_parameters=params, candidate_count=2)
    ranked = filter_multiple_factors(frame, trade_date="2026-03-11", strategy_parameters=params)

    assert codes == ranked["bond_code"].astype(str).tolist()[:2]


def test_build_candidate_codes_should_keep_dynamic_factor_ordering() -> None:
    frame = pd.DataFrame(
        [
            _row(
                bond_code="120001",
                close_price=112.0,
                conversion_premium_pct=20.0,
                outstanding_amount_yi=4.0,
                underlying_market_cap_yi=90.0,
                underlying_volatility=34.0,
                underlying_pb=1.6,
                listing_date="2023-01-01",
            ),
            _row(
                bond_code="120002",
                close_price=112.0,
                conversion_premium_pct=20.0,
                outstanding_amount_yi=10.0,
                underlying_market_cap_yi=90.0,
                underlying_volatility=34.0,
                underlying_pb=1.6,
                listing_date="2025-01-01",
            ),
        ]
    ).set_index("bond_code", drop=False)

    params = build_strategy_parameters(
        {
            "selected_factor_keys": ["list_days", "remain_size"],
            "factor_values": {
                "list_days": 300,
                "remain_size": 6,
            },
        }
    )
    prepared = prepare_candidate_pool(frame, trade_date="2026-03-11")

    codes = build_candidate_codes(prepared, strategy_parameters=params, candidate_count=2)
    ranked = filter_multiple_factors(frame, trade_date="2026-03-11", strategy_parameters=params)

    assert codes == ranked["bond_code"].astype(str).tolist()[:2]
    assert codes[0] == "120001"
