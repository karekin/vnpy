from __future__ import annotations

from typing import Any

from vnpy.web.domain.smart_allocation.calculator import decimal_from
from vnpy.web.domain.smart_allocation.models import AllocationProfile, AllocationSnapshot


def _position_value(position: dict[str, Any]) -> Any:
    if "value" in position:
        return position["value"]
    quantity = decimal_from(position.get("quantity", position.get("qty", 0)))
    price = decimal_from(position.get("avg_price", position.get("current_price", 0)))
    return quantity * price


def snapshot_from_legacy_portfolio_status(
    profile: AllocationProfile,
    payload: dict[str, Any],
) -> AllocationSnapshot:
    """Convert a legacy smart-position payload into vnpy allocation state."""

    positions = payload.get("positions") or payload.get("detailed_positions") or []
    qqqm_symbol = profile.qqqm_symbol.upper()
    voo_symbol = profile.voo_symbol.upper()
    quality_symbols = {symbol.upper() for symbol in profile.quality_stock_symbols}
    wheel_symbols = {symbol.upper() for symbol in profile.wheel_symbols}
    leaps_symbols = {symbol.upper() for symbol in profile.leaps_symbols}

    dca_value = decimal_from(0)
    options_value = decimal_from(0)
    wheel_value = decimal_from(0)
    leaps_value = decimal_from(0)
    unclassified_value = decimal_from(0)
    single_stock_values = {}

    for position in positions:
        symbol = str(position.get("symbol") or "").upper()
        value = decimal_from(_position_value(position))
        if not symbol or value <= 0:
            continue
        if symbol in {qqqm_symbol, voo_symbol} or symbol in quality_symbols:
            dca_value += value
            if symbol not in {qqqm_symbol, voo_symbol}:
                single_stock_values[symbol] = value
        elif symbol in wheel_symbols:
            wheel_value += value
            options_value += value
        elif symbol in leaps_symbols:
            leaps_value += value
            options_value += value
        else:
            unclassified_value += value

    cash_value = decimal_from(payload.get("available_cash", payload.get("cash_value", 0)))
    total_equity = decimal_from(payload.get("total_capital", payload.get("total_equity", cash_value + dca_value + options_value + unclassified_value)))

    return AllocationSnapshot(
        total_equity=total_equity,
        cash_value=cash_value,
        dca_value=dca_value,
        options_value=options_value,
        wheel_value=wheel_value,
        leaps_value=leaps_value,
        margin_used=decimal_from(payload.get("margin_used", 0)),
        unclassified_value=unclassified_value,
        single_stock_values=single_stock_values,
    )
