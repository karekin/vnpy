from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    AllocationTargets,
    WheelCandidate,
    WheelCandidatePoolSource,
    WheelDailyRecommendation,
)


DEFAULT_WHEEL_UNIVERSE: tuple[tuple[str, str, Decimal], ...] = (
    ("SPY.US", "系统默认高流动性 ETF 观察池", Decimal("50000")),
    ("QQQ.US", "系统默认高流动性 ETF 观察池", Decimal("45000")),
    ("IWM.US", "系统默认高流动性 ETF 观察池", Decimal("20000")),
    ("AAPL.US", "系统默认高流动性大盘股观察池", Decimal("20000")),
    ("MSFT.US", "系统默认高流动性大盘股观察池", Decimal("45000")),
    ("GOOGL.US", "系统默认高流动性大盘股观察池", Decimal("18000")),
    ("AMD.US", "系统默认高流动性大盘股观察池", Decimal("18000")),
    ("MRVL.US", "系统默认 AI/半导体观察池", Decimal("15000")),
    ("NVDA.US", "系统默认高流动性大盘股观察池", Decimal("90000")),
)

WHEEL_METHODOLOGY: tuple[str, ...] = (
    "候选池 = 手动 Wheel 候选池 + 优质个股白名单 + 当前持仓反向观察 + 系统内置高流动性观察池。",
    "先做账户级过滤：一张现金担保 Put 不能超过 Wheel 剩余额度，也不能突破单股集中度上限。",
    "再做风险过滤：保证金触线、已有持仓超限、现金担保不足时标记 blocked。",
    "当前版本是每日规则扫描；接入真实期权链后继续过滤 DTE、Delta、IV、成交量、未平仓量和 bid/ask spread。",
)


def build_wheel_candidates(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> list[WheelCandidate]:
    wheel_available = max(targets.wheel_value - snapshot.wheel_value, Decimal("0"))
    candidates: dict[str, tuple[str, Decimal]] = {}

    for symbol, source, estimated_cash_required in DEFAULT_WHEEL_UNIVERSE:
        candidates[symbol] = (source, estimated_cash_required)

    for symbol in profile.quality_stock_symbols:
        candidates[symbol] = ("优质个股白名单", _cash_required_for_symbol(symbol, candidates))

    for symbol in profile.wheel_symbols:
        candidates[symbol] = ("手动 Wheel 候选池", _cash_required_for_symbol(symbol, candidates))

    for symbol, holding_value in snapshot.single_stock_values.items():
        if holding_value > 0:
            candidates[symbol] = ("当前持仓反向观察", _cash_required_for_symbol(symbol, candidates))

    ranked = [
        _classify_wheel_candidate(
            symbol=symbol,
            source=source,
            estimated_cash_required=estimated_cash_required,
            wheel_available=wheel_available,
            profile=profile,
            snapshot=snapshot,
            targets=targets,
        )
        for symbol, (source, estimated_cash_required) in candidates.items()
    ]
    return sorted(ranked, key=lambda item: (-item.score, item.symbol))


def build_wheel_pool_sources(profile: AllocationProfile, snapshot: AllocationSnapshot) -> list[WheelCandidatePoolSource]:
    default_symbols = tuple(symbol for symbol, _, _ in DEFAULT_WHEEL_UNIVERSE)
    holding_symbols = tuple(symbol for symbol, value in sorted(snapshot.single_stock_values.items()) if value > 0)
    sources = [
        WheelCandidatePoolSource(
            name="手动 Wheel 候选池",
            count=len(profile.wheel_symbols),
            symbols=tuple(profile.wheel_symbols),
            rule="用户明确愿意被指派并持有的标的优先进入扫描。",
        ),
        WheelCandidatePoolSource(
            name="优质个股白名单",
            count=len(profile.quality_stock_symbols),
            symbols=tuple(profile.quality_stock_symbols),
            rule="长期底仓认可的优质个股可作为 Wheel 候选，但仍受单股上限约束。",
        ),
        WheelCandidatePoolSource(
            name="当前持仓反向观察",
            count=len(holding_symbols),
            symbols=holding_symbols,
            rule="已有持仓用于判断是否适合 Covered Call 或是否已经集中度过高。",
        ),
        WheelCandidatePoolSource(
            name="系统内置高流动性观察池",
            count=len(default_symbols),
            symbols=default_symbols,
            rule="只作为每日扫描起点，不代表自动可交易；必须通过现金担保、事件风险和期权链流动性检查。",
        ),
    ]
    return sources


def build_daily_wheel_recommendation(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> WheelDailyRecommendation:
    candidates = tuple(build_wheel_candidates(profile, snapshot, targets))
    actionable_count = sum(1 for item in candidates if item.status == "candidate")
    return WheelDailyRecommendation(
        scan_date=datetime.now(timezone.utc).date().isoformat(),
        account_equity=snapshot.total_equity,
        wheel_target=targets.wheel_value,
        wheel_available=max(targets.wheel_value - snapshot.wheel_value, Decimal("0")),
        candidate_count=len(candidates),
        actionable_count=actionable_count,
        candidates=candidates,
        pool_sources=tuple(build_wheel_pool_sources(profile, snapshot)),
        methodology=WHEEL_METHODOLOGY,
    )


def _cash_required_for_symbol(symbol: str, candidates: dict[str, tuple[str, Decimal]]) -> Decimal:
    known = candidates.get(symbol)
    if known:
        return known[1]
    return Decimal("25000")


def _classify_wheel_candidate(
    *,
    symbol: str,
    source: str,
    estimated_cash_required: Decimal,
    wheel_available: Decimal,
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> WheelCandidate:
    blockers: list[str] = []
    score = 70

    if estimated_cash_required > targets.single_stock_limit:
        blockers.append(f"一张 Put 预计占用 {estimated_cash_required}，高于单股上限 {targets.single_stock_limit}。")
        score -= 30
    if estimated_cash_required > wheel_available:
        blockers.append(f"Wheel 剩余额度 {wheel_available} 不足以现金担保一张。")
        score -= 25
    if snapshot.margin_used >= targets.margin_limit:
        blockers.append("保证金已触及红线，停止新增 Sell Put。")
        score -= 30
    if symbol in snapshot.single_stock_values and snapshot.single_stock_values[symbol] > targets.single_stock_limit:
        blockers.append("当前持仓已超过单股集中度上限，不应继续增加该标的风险。")
        score -= 25

    if symbol in profile.wheel_symbols:
        score += 15
    if symbol in profile.quality_stock_symbols:
        score += 10
    if source.startswith("系统默认高流动性 ETF"):
        score += 8

    score = max(0, min(100, score))
    if blockers:
        status = "blocked"
        reason = "先处理阻断项；该标的只保留在观察队列。"
    elif estimated_cash_required <= wheel_available:
        status = "candidate"
        reason = "额度、集中度和保证金纪律允许进入期权链核验。"
    else:
        status = "watch"
        reason = "可观察，但暂不满足现金担保额度。"

    max_contracts = int(wheel_available // estimated_cash_required) if estimated_cash_required > 0 else 0
    return WheelCandidate(
        symbol=symbol,
        source=source,
        score=score,
        status=status,
        estimated_cash_required=estimated_cash_required,
        max_contracts=max_contracts,
        reason=reason,
        blockers=tuple(blockers),
    )
