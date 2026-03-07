"""Phase A 轻量回测逻辑。

这里承载两条调用链共享的持仓轮动状态机：

- `run_backtest(...)`
  CLI/脚本侧使用，按日先生成候选池，再执行轻量回测。
- `run_backtest_from_candidates(...)`
  Web 优化侧使用，直接消费“交易日 -> 候选代码列表”的预计算结果，
  避免同一组参数在多窗口评估时重复生成候选池。

两者最终都会落到同一套 `_run_backtest_core(...)` 上，确保：
- 强赎、止盈止损、`until_win`、调仓频率等行为口径一致
- 后续调仓规则修改时只需要维护一处核心实现
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from vnpy.web.domain.cb_quant.phase_a_core.candidates import build_candidates
from vnpy.web.domain.cb_quant.phase_a_core.normalizer import _safe_float


@dataclass
class Holding:
    """回测持仓对象。"""

    code: str
    buy_price: float
    last_price: float
    ratio: float


def _to_float(value: object, default: float = 0.0) -> float:
    """把外部配置/快照字段尽量稳定地转成 float。"""
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _position_ratio(*, setting: dict[str, object], max_hold_num: int) -> float:
    """根据持仓数和单标的上限，计算单个仓位的目标权重。"""
    if max_hold_num <= 0:
        return 0.0
    base_ratio = 1.0 / max_hold_num
    cap_ratio = _to_float(setting.get("max_single_position_pct"), 100.0) / 100.0
    cap_ratio = max(0.0, min(1.0, cap_ratio))
    return min(base_ratio, cap_ratio if cap_ratio > 0 else base_ratio)


def _parse_iso_date(value: object) -> pd.Timestamp | None:
    """解析 ISO 日期文本，失败时返回 None。"""
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
    setting: dict[str, object],
) -> bool:
    """根据配置判断今天是否到达调仓日。"""
    if index == 0:
        return True
    freq_type = str(setting.get("rebalance_frequency_type", "trade_day") or "trade_day")
    freq_value = max(1, int(round(_to_float(setting.get("rebalance_frequency_value"), 1.0))))
    if freq_type == "trade_day":
        return (index - last_rebalance_index) >= freq_value

    current_date = _parse_iso_date(trade_date)
    previous_date = _parse_iso_date(last_rebalance_date)
    if current_date is None or previous_date is None:
        return True
    if freq_type == "calendar_day":
        return (current_date - previous_date).days >= freq_value
    if freq_type == "week":
        return (current_date - previous_date).days >= 7 * freq_value
    if freq_type == "month":
        month_delta = (current_date.year - previous_date.year) * 12 + (current_date.month - previous_date.month)
        return month_delta >= freq_value
    return (index - last_rebalance_index) >= freq_value


def _should_exit_by_price_limits(
    *,
    setting: dict[str, object],
    item: Holding,
    current_price: float,
) -> bool:
    """根据止盈/止损阈值判断是否应当强制卖出。"""
    if item.buy_price <= 0 or current_price <= 0:
        return False
    pnl_pct = (current_price - item.buy_price) / item.buy_price * 100.0
    take_profit_pct = setting.get("take_profit_pct")
    if take_profit_pct is not None and pnl_pct >= _to_float(take_profit_pct, 0.0):
        return True
    stop_loss_pct = setting.get("stop_loss_pct")
    if stop_loss_pct is not None and pnl_pct <= -_to_float(stop_loss_pct, 0.0):
        return True
    return False


def compute_daily_return(holdings: list[Holding], df_all: pd.DataFrame) -> float:
    """根据昨日持仓和今日快照计算组合当日收益。"""
    daily_ret = 0.0
    for item in holdings:
        if item.code not in df_all.index:
            continue
        row = df_all.loc[item.code]
        cur_price = _safe_float(row.get("price"), item.last_price)
        if item.last_price > 0:
            daily_ret += ((cur_price - item.last_price) / item.last_price) * item.ratio
        item.last_price = cur_price
    return round(daily_ret, 6)


def _run_backtest_core(
    *,
    dataset: list[tuple[str, pd.DataFrame]],
    candidate_code_map: dict[str, list[str]],
    setting: dict[str, object],
    max_hold_num: int,
    until_win: bool,
) -> dict[str, object]:
    """共享的轻量回测状态机。

    这层不关心候选池是实时计算出来的，还是上游已经预先算好。
    它只消费一个按交易日索引的候选代码映射，并产出优化排序所需的最小指标集。
    """
    holdings: list[Holding] = []
    per_position = _position_ratio(setting=setting, max_hold_num=max_hold_num)
    daily_returns: list[float] = []
    sell_win = 0
    sell_loss = 0
    rebalanced_days = 0
    last_rebalance_date: str | None = None
    last_rebalance_index = 0

    for index, (trade_date, df_all) in enumerate(dataset):
        # 只保留当天快照里真实存在的代码，避免历史候选池里残留停牌/缺失标的。
        ranked_codes = [code for code in candidate_code_map.get(trade_date, []) if code in df_all.index]
        ranked_set = set(ranked_codes)
        rebalance_due = _should_rebalance(
            index=index,
            trade_date=trade_date,
            last_rebalance_date=last_rebalance_date,
            last_rebalance_index=last_rebalance_index,
            setting=setting,
        )

        if index == 0:
            # 首日只负责根据候选池建立初始持仓，不计收益。
            for code in ranked_codes:
                if len(holdings) >= max_hold_num:
                    break
                row = df_all.loc[code]
                price = _safe_float(row.get("price"), 0.0)
                if price <= 0:
                    continue
                holdings.append(Holding(code=code, buy_price=price, last_price=price, ratio=per_position))
            last_rebalance_date = trade_date
            continue

        daily_returns.append(compute_daily_return(holdings, df_all))

        # 先决定已有持仓是“继续持有”还是“卖出”，再在调仓日补足空缺仓位。
        keep_list: list[Holding] = []
        sell_list: list[Holding] = []
        for item in holdings:
            if item.code not in df_all.index:
                sell_list.append(item)
                continue

            row = df_all.loc[item.code]
            cur_price = _safe_float(row.get("price"), item.last_price)
            is_ransom = str(row.get("is_ransom_flag", "False")) == "True"

            if is_ransom:
                sell_list.append(item)
                continue
            if _should_exit_by_price_limits(setting=setting, item=item, current_price=cur_price):
                sell_list.append(item)
                continue
            if until_win and cur_price <= item.buy_price:
                keep_list.append(item)
                continue
            if not rebalance_due:
                keep_list.append(item)
                continue
            if item.code in ranked_set:
                keep_list.append(item)
            else:
                sell_list.append(item)

        for item in sell_list:
            if item.code in df_all.index:
                row = df_all.loc[item.code]
                sell_price = _safe_float(row.get("price"), item.last_price)
            else:
                sell_price = item.last_price
            pnl_pct = (sell_price - item.buy_price) / item.buy_price * 100 if item.buy_price > 0 else 0
            if pnl_pct > 0:
                sell_win += 1
            else:
                sell_loss += 1

        existing_codes = {holding.code for holding in keep_list}
        if rebalance_due:
            for code in ranked_codes:
                if len(keep_list) >= max_hold_num:
                    break
                if code in existing_codes:
                    continue
                row = df_all.loc[code]
                price = _safe_float(row.get("price"), 0.0)
                if price <= 0:
                    continue
                keep_list.append(Holding(code=code, buy_price=price, last_price=price, ratio=per_position))
                existing_codes.add(code)

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
    cfg: dict[str, object],
    head_count: int,
    max_hold_num: int,
    until_win: bool,
) -> dict[str, object]:
    """执行脚本/CLI 口径的轻量回测。

    这里仍然保留“按日现算候选池”的外层入口，方便历史 CLI 和研究脚本复用；
    但真正的持仓轮动已经统一下沉到 `_run_backtest_core(...)`。
    """
    candidate_code_map: dict[str, list[str]] = {}
    for date_text, df_all in dataset:
        candidate = build_candidates(df_all, date_text, cfg, head_count)
        candidate_code_map[date_text] = (
            candidate["cb_code"].astype(str).tolist()[: max(1, head_count)] if not candidate.empty else []
        )

    setting: dict[str, object] = {
        "until_win": until_win,
        # CLI 历史口径默认按每个交易日检查是否调仓。
        "rebalance_frequency_type": "trade_day",
        "rebalance_frequency_value": 1,
    }
    return _run_backtest_core(
        dataset=dataset,
        candidate_code_map=candidate_code_map,
        setting=setting,
        max_hold_num=max_hold_num,
        until_win=until_win,
    )


def run_backtest_from_candidates(
    dataset: list[tuple[str, pd.DataFrame]],
    candidate_code_map: dict[str, list[str]],
    setting: dict[str, object],
) -> dict[str, object]:
    """执行 Web 优化链路使用的轻量回测。

    输入已经是“交易日 -> 候选代码列表”映射，因此不会重复调用 `build_candidates(...)`。
    """
    max_hold_num = max(1, int(round(_to_float(setting.get("max_hold_num"), 12.0))))
    until_win = bool(setting.get("until_win", False))
    return _run_backtest_core(
        dataset=dataset,
        candidate_code_map=candidate_code_map,
        setting=setting,
        max_hold_num=max_hold_num,
        until_win=until_win,
    )
