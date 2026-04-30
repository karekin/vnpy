from __future__ import annotations

from decimal import Decimal

from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    AllocationTargets,
    GuardrailViolation,
    RiskLevel,
)


def _actual_ratio(value: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal("0")
    return value / total


def _add_bucket_deviation(
    violations: list[GuardrailViolation],
    *,
    rule_code: str,
    actual_value: Decimal,
    target_value: Decimal,
    total_equity: Decimal,
    threshold: Decimal,
    message: str,
    recommended_action: str,
) -> None:
    if total_equity <= 0:
        return
    deviation = abs(_actual_ratio(actual_value, total_equity) - _actual_ratio(target_value, total_equity))
    if deviation >= threshold:
        violations.append(
            GuardrailViolation(
                rule_code=rule_code,
                risk_level=RiskLevel.ORANGE,
                message=message,
                actual_value=actual_value,
                limit_value=target_value,
                recommended_action=recommended_action,
            )
        )


def run_guardrail_checks(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    threshold = profile.rebalance_threshold

    _add_bucket_deviation(
        violations,
        rule_code="cash_bucket_deviation",
        actual_value=snapshot.cash_value,
        target_value=targets.cash_value,
        total_equity=snapshot.total_equity,
        threshold=threshold,
        message="现金仓位偏离目标超过阈值。",
        recommended_action="优先补足现金仓位，避免被迫卖出资产。",
    )
    _add_bucket_deviation(
        violations,
        rule_code="dca_bucket_deviation",
        actual_value=snapshot.dca_value,
        target_value=targets.dca_value,
        total_equity=snapshot.total_equity,
        threshold=threshold,
        message="定投仓位偏离目标超过阈值。",
        recommended_action="生成定投仓位再平衡建议。",
    )
    _add_bucket_deviation(
        violations,
        rule_code="options_bucket_deviation",
        actual_value=snapshot.options_value,
        target_value=targets.options_value,
        total_equity=snapshot.total_equity,
        threshold=threshold,
        message="期权仓位偏离目标超过阈值。",
        recommended_action="检查 Wheel/LEAPS 是否超配，期权利润不应继续滚入期权池。",
    )

    for symbol, value in snapshot.single_stock_values.items():
        if value > targets.single_stock_limit:
            violations.append(
                GuardrailViolation(
                    rule_code="single_stock_limit",
                    risk_level=RiskLevel.ORANGE,
                    message=f"{symbol} 超过单股集中度上限。",
                    actual_value=value,
                    limit_value=targets.single_stock_limit,
                    recommended_action="阻断新增该标的定投买入，并生成降集中度建议。",
                    blocking=True,
                )
            )

    if snapshot.margin_used > targets.margin_limit:
        violations.append(
            GuardrailViolation(
                rule_code="margin_limit",
                risk_level=RiskLevel.RED,
                message="保证金使用超过账户权益 25% 红线。",
                actual_value=snapshot.margin_used,
                limit_value=targets.margin_limit,
                recommended_action="停止新增保证金 Sell Put，优先降低保证金占用。",
                blocking=True,
            )
        )

    rsi_limit = Decimal("40") if profile.allow_bull_market_leaps_relaxation else Decimal("35")
    for symbol in snapshot.open_leaps_symbols:
        rsi = snapshot.latest_rsi_by_symbol.get(symbol)
        if rsi is not None and rsi >= rsi_limit:
            violations.append(
                GuardrailViolation(
                    rule_code="leaps_rsi_discipline",
                    risk_level=RiskLevel.RED,
                    message=f"{symbol} LEAPS 持仓不满足 RSI 入场纪律。",
                    actual_value=rsi,
                    limit_value=rsi_limit,
                    recommended_action="后续新增 LEAPS 必须等待 RSI 回到纪律区间。",
                    blocking=True,
                )
            )

    return violations
