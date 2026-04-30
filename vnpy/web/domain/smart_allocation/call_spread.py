from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from vnpy.web.domain.smart_allocation.calculator import money
from vnpy.web.domain.smart_allocation.models import AllocationProfile, AllocationSnapshot, AllocationTargets


DEFAULT_CALL_SPREAD_UNIVERSE: tuple[tuple[str, str], ...] = (
    ("PLTR.US", "系统默认 AI/数据平台 Call Spread 观察池"),
    ("UCO.US", "当前账户低价高波动观察池"),
    ("AAPL.US", "系统默认高流动性大盘股观察池"),
    ("MSFT.US", "系统默认高流动性大盘股观察池"),
    ("NVDA.US", "系统默认 AI/半导体观察池"),
    ("QQQ.US", "系统默认高流动性 ETF 观察池"),
    ("SPY.US", "系统默认高流动性 ETF 观察池"),
)

CALL_SPREAD_METHODOLOGY: tuple[str, ...] = (
    "Call Spread 与 Wheel 并列，但风控口径不同：最大亏损是净权利金，不是一张 Put 的现金担保金额。",
    "可用资金取期权目标缺口、现金超额和保证金余量三者最小值，避免把长期仓位或应急现金误当期权弹药。",
    "单笔风险上限取可用资金的 50%、账户权益的 8% 和 1000 美元三者最小值。",
    "优先选择 7-60 DTE、买入腿接近平值、上方卖出腿、净权利金低于单笔风险上限且成交/OI 活跃的组合。",
)


@dataclass(frozen=True)
class CallSpreadBudget:
    options_gap: Decimal
    cash_excess: Decimal
    margin_room: Decimal
    available: Decimal
    per_trade_limit: Decimal


@dataclass(frozen=True)
class CallSpreadCandidate:
    symbol: str
    source: str
    score: int
    status: str
    expiration_date: str | None
    long_strike: Decimal | None
    short_strike: Decimal | None
    net_debit: Decimal
    max_profit: Decimal
    max_loss: Decimal
    reward_risk: Decimal
    break_even: Decimal | None
    max_contracts: int
    underlying_price: Decimal | None
    reason: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class CallSpreadDailyRecommendation:
    scan_date: str
    account_equity: Decimal
    options_available: Decimal
    per_trade_limit: Decimal
    candidate_count: int
    actionable_count: int
    candidates: tuple[CallSpreadCandidate, ...]
    methodology: tuple[str, ...]


def normalize_us_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    return value if value.endswith(".US") else f"{value}.US"


def raw_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    return value[:-3] if value.endswith(".US") else value


def calculate_call_spread_budget(
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
) -> CallSpreadBudget:
    options_gap = max(targets.options_value - snapshot.options_value, Decimal("0"))
    cash_excess = max(snapshot.cash_value - targets.cash_value, Decimal("0"))
    margin_room = max(targets.margin_limit - snapshot.margin_used, Decimal("0"))
    available = min(options_gap, cash_excess, margin_room)
    per_trade_limit = min(available * Decimal("0.50"), snapshot.total_equity * Decimal("0.08"), Decimal("1000"))
    return CallSpreadBudget(
        options_gap=money(options_gap),
        cash_excess=money(cash_excess),
        margin_room=money(margin_room),
        available=money(available),
        per_trade_limit=money(max(per_trade_limit, Decimal("0"))),
    )


def build_call_spread_daily_recommendation(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
    *,
    option_chains: dict[str, list[dict[str, Any]]] | None = None,
    option_summaries: dict[str, dict[str, Any]] | None = None,
) -> CallSpreadDailyRecommendation:
    option_chains = option_chains or {}
    option_summaries = option_summaries or {}
    budget = calculate_call_spread_budget(snapshot, targets)
    candidates = tuple(
        sorted(
            [
                _build_candidate(
                    symbol=symbol,
                    source=source,
                    snapshot=snapshot,
                    targets=targets,
                    budget=budget,
                    rows=option_chains.get(raw_symbol(symbol), []),
                    summary=option_summaries.get(raw_symbol(symbol), {}),
                )
                for symbol, source in _call_spread_universe(profile, snapshot)
            ],
            key=lambda item: ({"candidate": 0, "watch": 1, "blocked": 2}.get(item.status, 9), -item.score, item.symbol),
        )
    )
    return CallSpreadDailyRecommendation(
        scan_date=datetime.now(timezone.utc).date().isoformat(),
        account_equity=snapshot.total_equity,
        options_available=budget.available,
        per_trade_limit=budget.per_trade_limit,
        candidate_count=len(candidates),
        actionable_count=sum(1 for item in candidates if item.status == "candidate"),
        candidates=candidates,
        methodology=CALL_SPREAD_METHODOLOGY,
    )


def _call_spread_universe(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
) -> list[tuple[str, str]]:
    candidates: dict[str, str] = {}
    for symbol, source in DEFAULT_CALL_SPREAD_UNIVERSE:
        candidates[normalize_us_symbol(symbol)] = source
    for symbol in profile.quality_stock_symbols:
        candidates[normalize_us_symbol(symbol)] = "优质个股白名单"
    for symbol in profile.wheel_symbols:
        candidates[normalize_us_symbol(symbol)] = "手动 Wheel/Call Spread 候选池"
    for symbol in profile.leaps_symbols:
        candidates[normalize_us_symbol(symbol)] = "手动 LEAPS/Call Spread 候选池"
    for symbol, holding_value in snapshot.single_stock_values.items():
        if holding_value > 0:
            candidates[normalize_us_symbol(symbol)] = "当前持仓方向性观察"
    return sorted(candidates.items())


def list_call_spread_symbols(
    profile: AllocationProfile,
    snapshot: AllocationSnapshot,
) -> list[str]:
    return [raw_symbol(symbol) for symbol, _source in _call_spread_universe(profile, snapshot)]


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    return number if number >= 0 else None


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _build_candidate(
    *,
    symbol: str,
    source: str,
    snapshot: AllocationSnapshot,
    targets: AllocationTargets,
    budget: CallSpreadBudget,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> CallSpreadCandidate:
    normalized_symbol = normalize_us_symbol(symbol)
    underlying_price = _decimal(summary.get("underlying_price"))
    if underlying_price is None:
        underlying_price = next((_decimal(row.get("underlying_price")) for row in rows if _decimal(row.get("underlying_price"))), None)
    holding_value = snapshot.single_stock_values.get(normalized_symbol, Decimal("0"))
    blockers: list[str] = []
    if budget.per_trade_limit <= 0:
        blockers.append("期权可用资金不足，不能新增 Call Spread。")
    if holding_value > targets.single_stock_limit:
        blockers.append("当前该标的持仓已超过单股集中度上限，暂不新增方向性风险。")
    spread = _select_best_spread(rows=rows, underlying_price=underlying_price, per_trade_limit=budget.per_trade_limit)
    if spread is None:
        blockers.append("没有找到符合预算和流动性的 Call Spread 组合。")
        return CallSpreadCandidate(
            symbol=normalized_symbol,
            source=source,
            score=max(0, int((Decimal(str(summary.get("selection_score") or 0)) * Decimal("0.45")))),
            status="blocked" if blockers else "watch",
            expiration_date=None,
            long_strike=None,
            short_strike=None,
            net_debit=Decimal("0"),
            max_profit=Decimal("0"),
            max_loss=Decimal("0"),
            reward_risk=Decimal("0"),
            break_even=None,
            max_contracts=0,
            underlying_price=underlying_price,
            reason="先补齐期权链或等待更合适的价差结构。",
            blockers=tuple(blockers),
        )

    score = _score_spread(summary=summary, spread=spread, budget=budget, blockers=blockers)
    status = "candidate" if not blockers and spread["max_loss"] <= budget.per_trade_limit else "blocked" if blockers else "watch"
    reason = (
        "净权利金风险在单笔上限内，且期权链流动性/方向评分支持进入实盘前核验。"
        if status == "candidate"
        else "保留观察；先处理阻断项或等待更合适的价差价格。"
    )
    return CallSpreadCandidate(
        symbol=normalized_symbol,
        source=source,
        score=score,
        status=status,
        expiration_date=spread["expiration_date"].isoformat(),
        long_strike=spread["long_strike"],
        short_strike=spread["short_strike"],
        net_debit=money(spread["net_debit"]),
        max_profit=money(spread["max_profit"]),
        max_loss=money(spread["max_loss"]),
        reward_risk=spread["reward_risk"].quantize(Decimal("0.01")),
        break_even=money(spread["break_even"]),
        max_contracts=int(budget.per_trade_limit // spread["max_loss"]) if spread["max_loss"] > 0 else 0,
        underlying_price=underlying_price,
        reason=reason,
        blockers=tuple(blockers),
    )


def _select_best_spread(
    *,
    rows: list[dict[str, Any]],
    underlying_price: Decimal | None,
    per_trade_limit: Decimal,
) -> dict[str, Any] | None:
    if underlying_price is None or per_trade_limit <= 0:
        return None
    calls_by_expiration: dict[date, list[dict[str, Any]]] = {}
    today = date.today()
    for row in rows:
        expiration = _date(row.get("expiration_date"))
        strike = _decimal(row.get("strike"))
        ask = _decimal(row.get("ask"))
        bid = _decimal(row.get("bid"))
        if expiration is None or strike is None or ask is None or bid is None:
            continue
        dte = (expiration - today).days
        if dte < 7 or dte > 60:
            continue
        if strike < underlying_price * Decimal("0.95") or strike > underlying_price * Decimal("1.25"):
            continue
        calls_by_expiration.setdefault(expiration, []).append({**row, "strike": strike, "ask": ask, "bid": bid, "dte": dte})

    best: dict[str, Any] | None = None
    for expiration, calls in calls_by_expiration.items():
        sorted_calls = sorted(calls, key=lambda item: item["strike"])
        for long_call in sorted_calls:
            for short_call in sorted_calls:
                if short_call["strike"] <= long_call["strike"]:
                    continue
                if long_call["strike"] > underlying_price * Decimal("1.08"):
                    continue
                if short_call["strike"] > underlying_price * Decimal("1.25"):
                    continue
                width = (short_call["strike"] - long_call["strike"]) * Decimal("100")
                if width < Decimal("500") or width > Decimal("3000"):
                    continue
                net_debit = (long_call["ask"] - short_call["bid"]) * Decimal("100")
                if net_debit < Decimal("50") or net_debit > per_trade_limit:
                    continue
                max_profit = width - net_debit
                if max_profit <= 0:
                    continue
                reward_risk = max_profit / net_debit
                liquidity = _decimal(long_call.get("volume")) or Decimal("0")
                liquidity += _decimal(long_call.get("open_interest")) or Decimal("0")
                liquidity += _decimal(short_call.get("volume")) or Decimal("0")
                liquidity += _decimal(short_call.get("open_interest")) or Decimal("0")
                dte_score = Decimal("20") if 14 <= long_call["dte"] <= 45 else Decimal("12")
                moneyness_penalty = abs(long_call["strike"] - underlying_price) / underlying_price * Decimal("100")
                score = reward_risk * Decimal("12") + min(liquidity / Decimal("1000"), Decimal("30")) + dte_score - moneyness_penalty
                candidate = {
                    "expiration_date": expiration,
                    "long_strike": long_call["strike"],
                    "short_strike": short_call["strike"],
                    "net_debit": net_debit,
                    "max_loss": net_debit,
                    "max_profit": max_profit,
                    "reward_risk": reward_risk,
                    "break_even": long_call["strike"] + net_debit / Decimal("100"),
                    "score": score,
                }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
    return best


def _score_spread(
    *,
    summary: dict[str, Any],
    spread: dict[str, Any],
    budget: CallSpreadBudget,
    blockers: list[str],
) -> int:
    base = Decimal(str(summary.get("selection_score") or 50))
    reward_bonus = min(spread["reward_risk"] * Decimal("5"), Decimal("18"))
    budget_bonus = Decimal("10") if spread["max_loss"] <= budget.per_trade_limit else Decimal("-20")
    flow_bonus = Decimal("8") if summary.get("flow_sentiment") == "bullish" else Decimal("0")
    penalty = Decimal("25") if blockers else Decimal("0")
    return int(max(Decimal("0"), min(Decimal("100"), base + reward_bonus + budget_bonus + flow_bonus - penalty)))
