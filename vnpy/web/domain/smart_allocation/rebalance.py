from __future__ import annotations

from decimal import Decimal

from vnpy.web.domain.smart_allocation.calculator import money
from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    AllocationTargets,
    RebalanceRecommendation,
)


def _ratio(value: Decimal, total: Decimal) -> float:
    if total <= 0:
        return 0.0
    return float(value / total)


def _state(snapshot: AllocationSnapshot) -> dict[str, float]:
    return {
        "cash_ratio": _ratio(snapshot.cash_value, snapshot.total_equity),
        "dca_ratio": _ratio(snapshot.dca_value, snapshot.total_equity),
        "options_ratio": _ratio(snapshot.options_value, snapshot.total_equity),
    }


def generate_recommendations(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> list[RebalanceRecommendation]:
    recommendations: list[RebalanceRecommendation] = []
    before = _state(snapshot)

    if snapshot.total_equity <= 0:
        return recommendations

    cash_deviation = (targets.cash_value - snapshot.cash_value) / snapshot.total_equity
    if cash_deviation >= profile.rebalance_threshold:
        amount = money(targets.cash_value - snapshot.cash_value)
        after_cash = snapshot.cash_value + amount
        recommendations.append(
            RebalanceRecommendation(
                id="top_up_cash:portfolio",
                recommendation_type="top_up_cash",
                priority=10,
                amount=amount,
                reason="现金仓位低于目标且偏离达到再平衡阈值。",
                before_state=before,
                after_state={
                    "cash_ratio": _ratio(after_cash, snapshot.total_equity),
                    "dca_ratio": before["dca_ratio"],
                    "options_ratio": before["options_ratio"],
                },
            )
        )

    options_excess = snapshot.options_value - targets.options_value
    if options_excess > 0 and (options_excess / snapshot.total_equity) >= profile.rebalance_threshold:
        recommendations.append(
            RebalanceRecommendation(
                id="reduce_options:portfolio",
                recommendation_type="reduce_options",
                priority=20,
                amount=money(options_excess),
                reason="期权仓位超配，期权利润应流出期权池。",
                before_state=before,
                after_state=before,
            )
        )

    for symbol, value in snapshot.single_stock_values.items():
        excess = value - targets.single_stock_limit
        if excess > 0:
            recommendations.append(
                RebalanceRecommendation(
                    id=f"reduce_single_stock:{symbol}",
                    recommendation_type="reduce_single_stock",
                    priority=5,
                    amount=money(excess),
                    symbol=symbol,
                    reason=f"{symbol} 超过定投仓位 10% 的单股上限。",
                    before_state=before,
                    after_state=before,
                )
            )

    return sorted(recommendations, key=lambda item: item.priority)
