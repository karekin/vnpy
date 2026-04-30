from __future__ import annotations

from decimal import Decimal

from vnpy.web.domain.smart_allocation.calculator import money
from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    AllocationTargets,
    CashflowEvent,
    WaterfallTransfer,
)


def plan_waterfall_transfer(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
    event: CashflowEvent,
) -> list[WaterfallTransfer]:
    del profile
    remaining = money(event.amount)
    transfers: list[WaterfallTransfer] = []

    if remaining <= 0:
        return transfers

    cash_gap = max(targets.cash_value - snapshot.cash_value, Decimal("0"))
    if cash_gap > 0:
        cash_amount = min(remaining, cash_gap)
        transfers.append(
            WaterfallTransfer(
                amount=money(cash_amount),
                source_bucket=event.source_bucket,
                target_bucket="cash",
                target_sub_bucket=None,
                reason="现金流瀑布优先补满现金仓位。",
            )
        )
        remaining = money(remaining - cash_amount)

    if remaining <= 0:
        return transfers

    dca_splits = [
        ("qqqm", Decimal("0.30"), "现金补满后的溢出资金注入 QQQM。"),
        ("voo", Decimal("0.30"), "现金补满后的溢出资金注入 VOO。"),
        ("quality_stock", Decimal("0.40"), "现金补满后的溢出资金注入优质个股池。"),
    ]
    allocated = Decimal("0")
    for index, (sub_bucket, split, reason) in enumerate(dca_splits):
        amount = remaining - allocated if index == len(dca_splits) - 1 else money(remaining * split)
        allocated += amount
        transfers.append(
            WaterfallTransfer(
                amount=money(amount),
                source_bucket=event.source_bucket,
                target_bucket="dca",
                target_sub_bucket=sub_bucket,
                reason=reason,
            )
        )

    return transfers
