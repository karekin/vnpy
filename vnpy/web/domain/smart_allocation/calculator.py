from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from vnpy.web.domain.smart_allocation.models import AllocationProfile, AllocationTargets, IncomeStatus


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_from(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def calculate_allocation_targets(profile: AllocationProfile, total_equity: Decimal) -> AllocationTargets:
    dca_ratio = Decimal(min(profile.age + 20, 70)) / Decimal("100")
    cash_ratio = Decimal("0.05") if profile.income_status == IncomeStatus.STABLE else Decimal("0.10")
    options_ratio = Decimal("1.00") - dca_ratio - cash_ratio

    dca_value = money(total_equity * dca_ratio)
    cash_value = money(total_equity * cash_ratio)
    options_value = money(total_equity * options_ratio)

    return AllocationTargets(
        dca_ratio=ratio(dca_ratio),
        cash_ratio=ratio(cash_ratio),
        options_ratio=ratio(options_ratio),
        dca_value=dca_value,
        cash_value=cash_value,
        options_value=options_value,
        qqqm_value=money(dca_value * Decimal("0.30")),
        voo_value=money(dca_value * Decimal("0.30")),
        quality_stock_value=money(dca_value * Decimal("0.40")),
        single_stock_limit=money(dca_value * Decimal("0.10")),
        wheel_value=money(options_value * Decimal("0.80")),
        leaps_value=money(options_value * Decimal("0.20")),
        margin_limit=money(total_equity * Decimal("0.25")),
    )
