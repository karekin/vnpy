from __future__ import annotations

from decimal import Decimal

from vnpy.web.domain.smart_allocation.models import AllocationProfile, LeapsCandidate


def classify_leaps_candidate(profile: AllocationProfile, symbol: str, rsi: Decimal) -> LeapsCandidate:
    if rsi < Decimal("35"):
        return LeapsCandidate(symbol=symbol, rsi=rsi, status="researchable", reason="RSI < 35，进入 LEAPS 可研究区。")
    if profile.allow_bull_market_leaps_relaxation and rsi < Decimal("40"):
        return LeapsCandidate(symbol=symbol, rsi=rsi, status="watch", reason="牛市放宽规则下 RSI < 40，仅观察不直接执行。")
    return LeapsCandidate(symbol=symbol, rsi=rsi, status="not_ready", reason="RSI 未进入 LEAPS 纪律区间。")
