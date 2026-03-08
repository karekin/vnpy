"""可转债策略轻量回测逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from vnpy.web.domain.cb_quant.cb_strategy_core.candidates import build_candidates
from vnpy.web.domain.cb_quant.cb_strategy_core.normalizer import _safe_float
from vnpy.web.domain.cb_quant.cb_strategy_core.settings import BacktestRuntimeConfig, StrategyParameters


@dataclass
class Holding:
    bond_code: str
    buy_price: float
    last_price: float
    ratio: float


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _position_ratio(*, runtime_config: BacktestRuntimeConfig) -> float:
    if runtime_config.max_hold_count <= 0:
        return 0.0
    base_ratio = 1.0 / runtime_config.max_hold_count
    cap_ratio = max(0.0, min(1.0, runtime_config.max_position_pct / 100.0))
    return min(base_ratio, cap_ratio if cap_ratio > 0 else base_ratio)


def _parse_iso_date(value: object) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    try:
        return pd.Timestamp(str(value)).normalize()
    except Exception:
        return None


def _should_rebalance(
    *,
    index: int,
    trade_date: str,
    last_rebalance_date: str | None,
    last_rebalance_index: int,
    runtime_config: BacktestRuntimeConfig,
) -> bool:
    if index == 0:
        return True
    if runtime_config.rebalance_interval_type == "trade_day":
        return (index - last_rebalance_index) >= runtime_config.rebalance_interval_value

    current_date = _parse_iso_date(trade_date)
    previous_date = _parse_iso_date(last_rebalance_date)
    if current_date is None or previous_date is None:
        return True
    if runtime_config.rebalance_interval_type == "calendar_day":
        return (current_date - previous_date).days >= runtime_config.rebalance_interval_value
    if runtime_config.rebalance_interval_type == "week":
        return (current_date - previous_date).days >= 7 * runtime_config.rebalance_interval_value
    if runtime_config.rebalance_interval_type == "month":
        month_delta = (current_date.year - previous_date.year) * 12 + (current_date.month - previous_date.month)
        return month_delta >= runtime_config.rebalance_interval_value
    return (index - last_rebalance_index) >= runtime_config.rebalance_interval_value


def _should_exit_by_price_limits(
    *,
    runtime_config: BacktestRuntimeConfig,
    item: Holding,
    current_price: float,
) -> bool:
    if item.buy_price <= 0 or current_price <= 0:
        return False
    pnl_pct = (current_price - item.buy_price) / item.buy_price * 100.0
    if runtime_config.take_profit_pct is not None and pnl_pct >= _to_float(runtime_config.take_profit_pct, 0.0):
        return True
    if runtime_config.stop_loss_pct is not None and pnl_pct <= -_to_float(runtime_config.stop_loss_pct, 0.0):
        return True
    return False


def compute_daily_return(holdings: list[Holding], df_all: pd.DataFrame) -> float:
    daily_ret = 0.0
    for item in holdings:
        if item.bond_code not in df_all.index:
            continue
        row = df_all.loc[item.bond_code]
        cur_price = _safe_float(row.get("close_price"), item.last_price)
        if item.last_price > 0:
            daily_ret += ((cur_price - item.last_price) / item.last_price) * item.ratio
        item.last_price = cur_price
    return round(daily_ret, 6)


def _run_backtest_core(
    *,
    dataset: list[tuple[str, pd.DataFrame]],
    candidate_code_map: dict[str, list[str]],
    runtime_config: BacktestRuntimeConfig,
) -> dict[str, object]:
    holdings: list[Holding] = []
    per_position = _position_ratio(runtime_config=runtime_config)
    daily_returns: list[float] = []
    sell_win = 0
    sell_loss = 0
    rebalanced_days = 0
    last_rebalance_date: str | None = None
    last_rebalance_index = 0

    for index, (trade_date, df_all) in enumerate(dataset):
        ranked_codes = [code for code in candidate_code_map.get(trade_date, []) if code in df_all.index]
        ranked_set = set(ranked_codes)
        rebalance_due = _should_rebalance(
            index=index,
            trade_date=trade_date,
            last_rebalance_date=last_rebalance_date,
            last_rebalance_index=last_rebalance_index,
            runtime_config=runtime_config,
        )

        if index == 0:
            for bond_code in ranked_codes:
                if len(holdings) >= runtime_config.max_hold_count:
                    break
                row = df_all.loc[bond_code]
                price = _safe_float(row.get("close_price"), 0.0)
                if price <= 0:
                    continue
                holdings.append(Holding(bond_code=bond_code, buy_price=price, last_price=price, ratio=per_position))
            last_rebalance_date = trade_date
            continue

        daily_returns.append(compute_daily_return(holdings, df_all))

        keep_list: list[Holding] = []
        sell_list: list[Holding] = []
        for item in holdings:
            if item.bond_code not in df_all.index:
                sell_list.append(item)
                continue

            row = df_all.loc[item.bond_code]
            cur_price = _safe_float(row.get("close_price"), item.last_price)
            is_redeem_triggered = bool(row.get("is_redeem_triggered", False))

            if is_redeem_triggered:
                sell_list.append(item)
                continue
            if _should_exit_by_price_limits(runtime_config=runtime_config, item=item, current_price=cur_price):
                sell_list.append(item)
                continue
            if runtime_config.hold_until_profit and cur_price <= item.buy_price:
                keep_list.append(item)
                continue
            if not rebalance_due:
                keep_list.append(item)
                continue
            if item.bond_code in ranked_set:
                keep_list.append(item)
            else:
                sell_list.append(item)

        for item in sell_list:
            if item.bond_code in df_all.index:
                row = df_all.loc[item.bond_code]
                sell_price = _safe_float(row.get("close_price"), item.last_price)
            else:
                sell_price = item.last_price
            pnl_pct = (sell_price - item.buy_price) / item.buy_price * 100 if item.buy_price > 0 else 0
            if pnl_pct > 0:
                sell_win += 1
            else:
                sell_loss += 1

        existing_codes = {holding.bond_code for holding in keep_list}
        if rebalance_due:
            for bond_code in ranked_codes:
                if len(keep_list) >= runtime_config.max_hold_count:
                    break
                if bond_code in existing_codes:
                    continue
                row = df_all.loc[bond_code]
                price = _safe_float(row.get("close_price"), 0.0)
                if price <= 0:
                    continue
                keep_list.append(Holding(bond_code=bond_code, buy_price=price, last_price=price, ratio=per_position))
                existing_codes.add(bond_code)

        holdings = keep_list
        if rebalance_due:
            rebalanced_days += 1
            last_rebalance_date = trade_date
            last_rebalance_index = index

    equity = 1.0
    max_equity = 1.0
    max_dd = 0.0
    for ret in daily_returns:
        equity *= 1 + ret
        max_equity = max(max_equity, equity)
        drawdown = equity / max_equity - 1
        max_dd = min(max_dd, drawdown)

    total_return_pct = (equity - 1) * 100
    max_drawdown_pct = abs(max_dd) * 100
    trade_count = sell_win + sell_loss
    win_rate = (sell_win / trade_count * 100) if trade_count else 0.0
    calmar_like = total_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0.0
    return_drawdown_ratio = total_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0.0

    return {
        "total_return_pct": round(total_return_pct, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "return_drawdown_ratio": round(return_drawdown_ratio, 6),
        "calmar_like": round(calmar_like, 6),
        "trade_count": int(trade_count),
        "win_rate_pct": round(win_rate, 4),
        "sample_days": len(dataset),
        "rebalanced_days": rebalanced_days,
    }


def run_backtest(
    dataset: list[tuple[str, pd.DataFrame]],
    strategy_parameters: StrategyParameters,
    runtime_config: BacktestRuntimeConfig,
) -> dict[str, object]:
    candidate_code_map: dict[str, list[str]] = {}
    for trade_date, df_all in dataset:
        candidate = build_candidates(
            df_all,
            trade_date,
            strategy_parameters,
            runtime_config.candidate_count,
        )
        candidate_code_map[trade_date] = (
            candidate["bond_code"].astype(str).tolist()[: runtime_config.candidate_count] if not candidate.empty else []
        )
    return _run_backtest_core(
        dataset=dataset,
        candidate_code_map=candidate_code_map,
        runtime_config=runtime_config,
    )


def run_backtest_from_candidates(
    dataset: list[tuple[str, pd.DataFrame]],
    candidate_code_map: dict[str, list[str]],
    runtime_config: BacktestRuntimeConfig,
) -> dict[str, object]:
    return _run_backtest_core(
        dataset=dataset,
        candidate_code_map=candidate_code_map,
        runtime_config=runtime_config,
    )
