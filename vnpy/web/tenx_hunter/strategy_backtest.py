"""期权策略历史回测引擎

逐日模拟 8 种常用期权策略，基于历史日线收盘价统计实际胜率。
策略逻辑与前端 buildStrategies() 保持一致。
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .db import connect

# ── 策略元数据 ──

STRATEGY_META: dict[str, dict[str, str]] = {
    "bull_call_spread":   {"name": "看涨价差",   "name_en": "Bull Call Spread", "direction": "偏多"},
    "bear_put_spread":    {"name": "看跌价差",   "name_en": "Bear Put Spread",  "direction": "偏空"},
    "long_call":          {"name": "买入看涨",   "name_en": "Long Call",        "direction": "看多"},
    "long_put":           {"name": "买入看跌",   "name_en": "Long Put",         "direction": "看空"},
    "long_straddle":      {"name": "买入跨式",   "name_en": "Long Straddle",    "direction": "波动"},
    "short_straddle":     {"name": "卖出跨式",   "name_en": "Short Straddle",   "direction": "中性"},
    "long_strangle":      {"name": "买入宽跨式", "name_en": "Long Strangle",    "direction": "突破"},
    "iron_condor":        {"name": "铁鹰",       "name_en": "Iron Condor",      "direction": "中性"},
    "call_butterfly":     {"name": "蝴蝶",       "name_en": "Call Butterfly",   "direction": "收敛"},
    "covered_call":       {"name": "备兑看涨",   "name_en": "Covered Call",     "direction": "偏多"},
}

# ── 工具函数 ──


def _normal_cdf(x: float) -> float:
    """正态分布累积函数近似 (Abramowitz & Stegun)"""
    a1, a2, a3, a4, a5, p = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429, 0.3275911
    sign = -1 if x < 0 else 1
    t = 1.0 / (1.0 + p * abs(x))
    y = 1.0 - (((((a5 * t + a4) * t) + a3 * t + a2) * t + a1) * t * math.exp(-x * x / 2.0))
    return 0.5 * (1.0 + sign * y)


def _fmt_pct(v: float) -> str:
    return f"{v:.1%}"


def _fmt_currency(v: float) -> str:
    return f"${v:.2f}"


# ── 核心回测逻辑 ──


def run_strategy_backtest(
    symbol: str,
    *,
    market: str = "US",
    lookback_days: int = 90,
    horizon_days: int = 30,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """主入口：获取历史数据，运行全部 8 策略回测，返回结果字典。"""

    if settings is None:
        from .config import load_settings
        settings = load_settings()

    today = date.today()
    start_date = today - timedelta(days=int(lookback_days * 1.6) + horizon_days + 30)

    notes: list[str] = []

    with connect(settings) as conn:
        # 查询日线收盘价
        price_rows = conn.execute(
            """
            SELECT trade_date, close
            FROM olap.security_market_daily
            WHERE market = %s AND symbol = %s
              AND trade_date >= %s
            ORDER BY trade_date ASC
            """,
            (market, symbol, start_date),
        ).fetchall()

        # 查询期权日线摘要（IV、flow 等）
        opt_rows = conn.execute(
            """
            SELECT trade_date, underlying_price, avg_implied_volatility,
                   call_put_volume_ratio, flow_sentiment, max_pain_strike
            FROM olap.security_option_chain_summary_daily
            WHERE market = %s AND symbol = %s
              AND trade_date >= %s
            ORDER BY trade_date ASC
            """,
            (market, symbol, start_date),
        ).fetchall()

    if not price_rows:
        return _empty_result(market, symbol, lookback_days, horizon_days, notes, "无历史日线数据")

    # 构建 价格/IV/Flow/MaxPain 映射
    price_map: dict[date, float] = {r["trade_date"]: float(r["close"]) for r in price_rows}
    sorted_dates = sorted(price_map.keys())

    iv_map: dict[date, float] = {}
    flow_map: dict[date, str] = {}
    max_pain_map: dict[date, float] = {}
    for r in opt_rows:
        d = r["trade_date"]
        if r["avg_implied_volatility"] is not None:
            iv_map[d] = float(r["avg_implied_volatility"])
        flow_map[d] = str(r["flow_sentiment"]) if r["flow_sentiment"] else "unknown"
        if r["max_pain_strike"] is not None:
            max_pain_map[d] = float(r["max_pain_strike"])

    if not opt_rows:
        notes.append("期权摘要数据缺失，IV 使用默认 40%，flow 标记为 unknown。")

    # 有效的入场日：必须有 exit_date (entry + horizon_days 的交易日)
    cutoff = today - timedelta(days=horizon_days + 5)
    entry_dates = [d for d in sorted_dates if d <= cutoff]

    if not entry_dates:
        return _empty_result(market, symbol, lookback_days, horizon_days, notes, "可回测交易日不足")

    # 逐策略模拟
    results: list[dict[str, Any]] = []
    for key, meta in STRATEGY_META.items():
        sim = _simulate_strategy(
            key,
            price_map=price_map,
            sorted_dates=sorted_dates,
            iv_map=iv_map,
            flow_map=flow_map,
            max_pain_map=max_pain_map,
            horizon_days=horizon_days,
        )
        # 生成回测逻辑文案
        current_iv = _get_latest_iv(iv_map, sorted_dates)
        current_flow = _get_latest_flow(flow_map, sorted_dates)
        sim["backtest_logic"] = _build_logic(key, meta, sim, current_iv, current_flow)
        sim["key"] = key
        sim["name"] = meta["name"]
        sim["name_en"] = meta["name_en"]
        sim["direction"] = meta["direction"]
        results.append(sim)

    return {
        "market": market,
        "symbol": symbol,
        "lookback_days": lookback_days,
        "horizon_days": horizon_days,
        "total_backtest_days": len(entry_dates),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "strategies": results,
        "notes": notes,
    }


def _simulate_strategy(
    strategy_key: str,
    *,
    price_map: dict[date, float],
    sorted_dates: list[date],
    iv_map: dict[date, float],
    flow_map: dict[date, str],
    max_pain_map: dict[date, float],
    horizon_days: int,
) -> dict[str, Any]:
    """对单个策略逐日模拟，统计胜率。"""

    wins = 0
    losses = 0
    profit_pcts: list[float] = []
    loss_pcts: list[float] = []
    all_pnls: list[float] = []
    streak_type: str | None = None
    streak_count = 0
    sample_trades: list[dict[str, Any]] = []

    # 需要足够多交易日才有 exit
    cutoff = sorted_dates[-1] - timedelta(days=horizon_days + 5)

    for entry_date in sorted_dates:
        if entry_date > cutoff:
            break

        S = price_map[entry_date]

        # 找 exit_date: entry_date + horizon_days 之后的最近交易日
        exit_date = _find_exit_date(sorted_dates, entry_date, horizon_days)
        if exit_date is None or exit_date not in price_map:
            continue

        exit_price = price_map[exit_date]

        # 获取当日 IV（缺失则用最近 5 天内的，否则默认 40%）
        iv = _get_iv_for_date(iv_map, entry_date, sorted_dates)
        flow = flow_map.get(entry_date, "unknown")
        mp = max_pain_map.get(entry_date, S)

        # 计算 strike 和 premium（与前端 buildStrategies 一致）
        strikes, premiums = _calc_strikes_premiums(S, iv, horizon_days, mp)

        # 判断盈亏
        pnl, pnl_pct, is_win = _determine_pnl(strategy_key, S, exit_price, strikes, premiums)

        if is_win:
            wins += 1
            profit_pcts.append(pnl_pct)
        else:
            losses += 1
            loss_pcts.append(abs(pnl_pct))

        all_pnls.append(pnl)

        # 连胜/连败追踪
        if streak_type == ("W" if is_win else "L"):
            streak_count += 1
        else:
            streak_type = "W" if is_win else "L"
            streak_count = 1

        # 记录交易明细（只保留最后 5 笔）
        sample_trades.append({
            "trade_date": entry_date.isoformat(),
            "entry_price": round(S, 4),
            "exit_price": round(exit_price, 4),
            "iv_on_entry": round(iv, 4) if iv else None,
            "flow_sentiment": flow,
        })

    total = wins + losses
    if total == 0:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "avg_profit_pct": 0.0, "avg_loss_pct": 0.0,
            "profit_factor": 0.0, "current_streak": "-",
            "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
            "sample_trades": [],
        }

    win_rate = wins / total
    avg_profit = sum(profit_pcts) / len(profit_pcts) if profit_pcts else 0.0
    avg_loss = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 0.0
    gross_profit = sum(profit_pcts) if profit_pcts else 0.0
    gross_loss = sum(loss_pcts) if loss_pcts else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0 if gross_profit > 0 else 0.0
    best = max(all_pnls) if all_pnls else 0.0
    worst = min(all_pnls) if all_pnls else 0.0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "avg_profit_pct": round(avg_profit, 4),
        "avg_loss_pct": round(avg_loss, 4),
        "profit_factor": round(profit_factor, 2),
        "current_streak": f"{streak_type}{streak_count}" if streak_type else "-",
        "best_trade_pct": round(best, 4),
        "worst_trade_pct": round(worst, 4),
        "sample_trades": sample_trades[-5:],
    }


def _calc_strikes_premiums(
    S: float, iv: float, days: int, max_pain: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """计算各 strike 和 premium，与前端 buildStrategies() 逻辑一致。"""
    sigma1 = S * iv * math.sqrt(days / 365.0)

    atm = S
    otm_call = S + sigma1 * 0.5
    otm_call2 = S + sigma1
    otm_put = S - sigma1 * 0.5
    otm_put2 = S - sigma1

    # BSM 近似 premium
    call_atm = S * iv * math.sqrt(days / 365.0) * 0.4
    put_atm = call_atm * 1.0  # 简化：ATM put ≈ ATM call
    call_otm = call_atm * 0.45
    put_otm = put_atm * 0.45
    call_otm2 = call_atm * 0.18
    put_otm2 = put_atm * 0.18

    strikes = {
        "atm": atm, "otm_call": otm_call, "otm_call2": otm_call2,
        "otm_put": otm_put, "otm_put2": otm_put2,
        "mid": (S + max_pain) / 2.0,
    }
    premiums = {
        "call_atm": call_atm, "put_atm": put_atm,
        "call_otm": call_otm, "put_otm": put_otm,
        "call_otm2": call_otm2, "put_otm2": put_otm2,
    }
    return strikes, premiums


def _determine_pnl(
    strategy_key: str,
    entry_price: float,
    exit_price: float,
    strikes: dict[str, float],
    premiums: dict[str, float],
) -> tuple[float, float, bool]:
    """判断单笔交易盈亏，返回 (pnl_dollar, pnl_pct, is_win)。"""
    S = entry_price

    if strategy_key == "bull_call_spread":
        net_debit = premiums["call_atm"] - premiums["call_otm"]
        be = strikes["atm"] + net_debit
        pnl = min(exit_price - be, strikes["otm_call"] - strikes["atm"] - net_debit) if exit_price > be else max(exit_price - be, -net_debit)
        pnl = max(-net_debit, min(strikes["otm_call"] - strikes["atm"] - net_debit, exit_price - strikes["atm"] - net_debit))

    elif strategy_key == "bear_put_spread":
        net_debit = premiums["put_atm"] - premiums["put_otm"]
        pnl = max(-net_debit, min(strikes["atm"] - strikes["otm_put"] - net_debit, strikes["atm"] - exit_price - net_debit))

    elif strategy_key == "long_call":
        premium = premiums["call_atm"]
        pnl = max(-premium, exit_price - strikes["atm"] - premium)

    elif strategy_key == "long_put":
        premium = premiums["put_atm"]
        pnl = max(-premium, strikes["atm"] - exit_price - premium)

    elif strategy_key == "long_straddle":
        cost = premiums["call_atm"] + premiums["put_atm"]
        move = abs(exit_price - strikes["atm"])
        pnl = move - cost

    elif strategy_key == "short_straddle":
        credit = premiums["call_atm"] + premiums["put_atm"]
        move = abs(exit_price - strikes["atm"])
        pnl = credit - move

    elif strategy_key == "long_strangle":
        cost = premiums["call_otm"] + premiums["put_otm"]
        if exit_price > strikes["otm_call"]:
            pnl = exit_price - strikes["otm_call"] - cost
        elif exit_price < strikes["otm_put"]:
            pnl = strikes["otm_put"] - exit_price - cost
        else:
            pnl = -cost

    elif strategy_key == "iron_condor":
        credit = premiums["put_otm"] + premiums["call_otm"] - premiums["put_otm2"] - premiums["call_otm2"]
        wing_width = strikes["otm_put"] - strikes["otm_put2"]
        if exit_price < strikes["otm_put2"]:
            pnl = -(wing_width - credit)
        elif exit_price > strikes["otm_call2"]:
            pnl = -(wing_width - credit)
        elif strikes["otm_put2"] <= exit_price <= strikes["otm_put"]:
            pnl = credit - (strikes["otm_put"] - exit_price)
        elif strikes["otm_call"] <= exit_price <= strikes["otm_call2"]:
            pnl = credit - (exit_price - strikes["otm_call"])
        else:
            pnl = credit  # 在区间内，收满权利金

    elif strategy_key == "call_butterfly":
        lower = strikes["mid"] - (strikes["atm"] * strikes["atm"] / S) * 0.25  # 简化
        mid_s = strikes["mid"]
        upper = strikes["mid"] + (strikes["atm"] * strikes["atm"] / S) * 0.25
        cost_bf = premiums["call_otm"] * 0.3
        if lower <= exit_price <= upper:
            pnl = min(exit_price - lower, upper - exit_price) - cost_bf
        else:
            pnl = -cost_bf

    elif strategy_key == "covered_call":
        credit = premiums["call_otm"]
        stock_pnl = exit_price - S
        call_pnl = -max(0, exit_price - strikes["otm_call"])
        pnl = stock_pnl + call_pnl + credit

    else:
        pnl = 0.0

    pnl_pct = pnl / S if S > 0 else 0.0
    is_win = pnl > 0
    return round(pnl, 4), round(pnl_pct, 4), is_win


def _find_exit_date(sorted_dates: list[date], entry: date, horizon_days: int) -> date | None:
    """找到 entry + horizon_days 之后最近的交易日。"""
    target = entry + timedelta(days=horizon_days)
    for d in sorted_dates:
        if d >= target:
            return d
    return None


def _get_iv_for_date(iv_map: dict[date, float], target: date, sorted_dates: list[date]) -> float:
    """获取目标日期的 IV，缺失则向前找 5 天，否则默认 40%。"""
    if target in iv_map:
        return iv_map[target]
    # 向前找最近 5 天
    idx = None
    for i, d in enumerate(sorted_dates):
        if d == target:
            idx = i
            break
        if d > target:
            break
    if idx is not None:
        for j in range(idx - 1, max(0, idx - 6), -1):
            d = sorted_dates[j]
            if d in iv_map:
                return iv_map[d]
    return 0.40


def _get_latest_iv(iv_map: dict[date, float], sorted_dates: list[date]) -> float:
    """获取最近的 IV 值。"""
    for d in reversed(sorted_dates):
        if d in iv_map:
            return iv_map[d]
    return 0.40


def _get_latest_flow(flow_map: dict[date, str], sorted_dates: list[date]) -> str:
    """获取最近的 flow sentiment。"""
    for d in reversed(sorted_dates):
        if d in flow_map:
            return flow_map[d]
    return "unknown"


def _build_logic(
    key: str,
    meta: dict[str, str],
    stats: dict[str, Any],
    current_iv: float,
    current_flow: str,
) -> str:
    """生成人类可读的回测逻辑推理。"""
    total = stats["total_trades"]
    if total == 0:
        return f"{meta['name']}：回测数据不足，无法统计胜率。"

    wr = stats["win_rate"]
    wins = stats["wins"]
    losses = stats["losses"]
    pf = stats["profit_factor"]
    streak = stats["current_streak"]

    # 基础段落
    parts = [
        f"过去 {total} 个交易日模拟 {meta['name']}（{meta['name_en']}），"
        f"胜率 {_fmt_pct(wr)}（{wins}胜{losses}负），盈利因子 {pf:.2f}"
    ]

    # 当前 IV 水平
    iv_pct = current_iv * 100
    if iv_pct > 45:
        parts.append(f"当前 IV {iv_pct:.0f}% 偏高")
    elif iv_pct < 25:
        parts.append(f"当前 IV {iv_pct:.0f}% 偏低")
    else:
        parts.append(f"当前 IV {iv_pct:.0f}% 适中")

    # 资金流方向
    if current_flow in ("bullish", "bearish"):
        parts.append(f"资金流 {current_flow}")

    # 胜率判断
    if wr >= 0.60:
        parts.append("历史回测支持该策略，胜率优势明显")
    elif wr >= 0.50:
        parts.append("历史胜率尚可，注意仓位管理和止损")
    else:
        parts.append("历史胜率偏低，建议谨慎或结合其他信号")

    # 连胜/连败提示
    if streak.startswith("W") and int(streak[1:]) >= 3:
        parts.append(f"当前连胜 {streak[1:]} 笔")
    elif streak.startswith("L") and int(streak[1:]) >= 3:
        parts.append(f"当前连败 {streak[1:]} 笔，注意风险")

    # 策略特有建议
    if key in ("long_straddle", "long_strangle") and iv_pct < 30:
        parts.append("IV 偏低时买入波动率策略权利金便宜，性价比高")
    if key in ("short_straddle", "iron_condor") and iv_pct > 45:
        parts.append("IV 偏高时卖出策略权利金丰厚，卖方优势明显")

    return "。".join(parts) + "。"


def _empty_result(
    market: str, symbol: str, lookback: int, horizon: int,
    notes: list[str], reason: str,
) -> dict[str, Any]:
    """无数据时返回空结果。"""
    notes.append(reason)
    return {
        "market": market,
        "symbol": symbol,
        "lookback_days": lookback,
        "horizon_days": horizon,
        "total_backtest_days": 0,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "strategies": [
            {
                "key": k, "name": m["name"], "name_en": m["name_en"],
                "direction": m["direction"],
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "avg_profit_pct": 0.0, "avg_loss_pct": 0.0,
                "profit_factor": 0.0, "current_streak": "-",
                "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
                "backtest_logic": f"{m['name']}：{reason}",
                "sample_trades": [],
            }
            for k, m in STRATEGY_META.items()
        ],
        "notes": notes,
    }
