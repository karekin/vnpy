"""可转债策略轻量回测逻辑。

这个模块负责把“单日候选债列表”进一步变成“跨时间的持仓收益统计”。
整体流程可以概括为：
1. 先基于每日全市场快照生成候选债池。
2. 按调仓周期决定当天是否需要换仓。
3. 在持仓层面处理强赎、止盈止损、继续持有等规则。
4. 逐日累计收益、回撤、胜率等回测指标。

这里刻意保持实现轻量，不模拟成交滑点、手续费、分笔撮合等更细市场细节，
目标是为策略参数筛选和粗粒度效果验证提供一个足够稳定、足够快的回测内核。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from vnpy.web.core.cb_backtest.candidate_selection import (
    build_tradeable_mask,
    filter_multiple_factors,
)
from vnpy.web.core.cb_backtest.normalizer import _safe_float
from vnpy.web.core.cb_backtest.strategy_config import BacktestRuntimeConfig, StrategyParameters


@dataclass
class Holding:
    """单个持仓的最小状态单元。

    字段含义：
    - `bond_code`: 可转债代码，用于和当日行情表做匹配。
    - `buy_price`: 建仓价格，用于止盈止损和卖出盈亏统计。
    - `last_price`: 上一个估值时点价格，用于计算“今日相对昨日”的收益。
    - `ratio`: 该持仓占组合的固定权重，当前实现采用等权近似。
    """
    bond_code: str
    buy_price: float
    last_price: float
    ratio: float


def _to_float(value: object, default: float = 0.0) -> float:
    """轻量的数值转换工具，用于运行期参数比较场景。"""
    try:
        # `None` 明确表示无值，直接回退到默认值。
        if value is None:
            return float(default)
        # 其它情况尽量转成浮点数，兼容字符串数字等常见输入。
        return float(value)
    except Exception:
        # 回测运行时不希望因为单个参数脏值导致整体崩溃，因此失败时兜底。
        return float(default)


def _position_ratio(*, runtime_config: BacktestRuntimeConfig) -> float:
    """根据运行配置计算单只持仓的目标仓位比例。"""
    # 最大持仓数若非法为 0 或负数，则无法分配仓位，直接返回 0。
    if runtime_config.max_hold_count <= 0:
        return 0.0
    # 等权思路下，单只仓位的自然上限是“1 / 最大持仓数”。
    base_ratio = 1.0 / runtime_config.max_hold_count
    # 同时还要受到“单只最大仓位百分比”的约束，并把输入裁剪到 0~1 范围。
    cap_ratio = max(0.0, min(1.0, runtime_config.max_position_pct / 100.0))
    # 取两者更严格的那个，保证同时满足“等权”和“单票上限”。
    return min(base_ratio, cap_ratio if cap_ratio > 0 else base_ratio)


def _parse_iso_date(value: object) -> pd.Timestamp | None:
    """把交易日输入解析为归一化后的日期对象。"""
    # 空值无法参与日期差计算，直接返回 `None`。
    if value in (None, ""):
        return None
    try:
        # `normalize()` 会把时分秒归零，便于只按自然日维度比较。
        return pd.Timestamp(str(value)).normalize()
    except Exception:
        # 非法日期统一视为解析失败，让上层决定如何兜底。
        return None


def _should_rebalance(
    *,
    index: int,
    trade_date: str,
    last_rebalance_date: str | None,
    last_rebalance_index: int,
    runtime_config: BacktestRuntimeConfig,
) -> bool:
    """判断当前交易日是否触发调仓。"""
    # 第一天天然需要建仓，因此直接视为调仓日。
    if index == 0:
        return True
    # 按交易日调仓时，直接使用样本索引差值判断最直观，也不会受节假日影响。
    if runtime_config.rebalance_interval_type == "trade_day":
        return (index - last_rebalance_index) >= runtime_config.rebalance_interval_value

    # 其余周期类型都需要先把日期字符串解析成可计算的日期对象。
    current_date = _parse_iso_date(trade_date)
    previous_date = _parse_iso_date(last_rebalance_date)
    # 如果任意日期解析失败，为了避免长时间不调仓，这里选择保守地返回 True。
    if current_date is None or previous_date is None:
        return True
    # 按自然日调仓：比较自然日差值。
    if runtime_config.rebalance_interval_type == "calendar_day":
        return (current_date - previous_date).days >= runtime_config.rebalance_interval_value
    # 按周调仓：近似按 7 * N 天判断即可。
    if runtime_config.rebalance_interval_type == "week":
        return (current_date - previous_date).days >= 7 * runtime_config.rebalance_interval_value
    # 按月调仓：使用“月份编号差”判断，避免受每月天数不同影响。
    if runtime_config.rebalance_interval_type == "month":
        month_delta = (current_date.year - previous_date.year) * 12 + (current_date.month - previous_date.month)
        return month_delta >= runtime_config.rebalance_interval_value
    # 未识别的周期类型回退到“按交易日间隔”处理，保证逻辑可继续运行。
    return (index - last_rebalance_index) >= runtime_config.rebalance_interval_value


def _should_exit_by_price_limits(
    *,
    runtime_config: BacktestRuntimeConfig,
    item: Holding,
    current_price: float,
) -> bool:
    """根据止盈止损配置判断当前持仓是否应卖出。"""
    # 买入价或当前价无效时，无法计算收益率，不触发价格退出。
    if item.buy_price <= 0 or current_price <= 0:
        return False
    # 以建仓价为基准计算当前累计盈亏百分比。
    pnl_pct = (current_price - item.buy_price) / item.buy_price * 100.0
    # 达到止盈阈值则卖出。
    if runtime_config.take_profit_pct is not None and pnl_pct >= _to_float(runtime_config.take_profit_pct, 0.0):
        return True
    # 触及止损阈值同样卖出，注意止损配置是正数，这里要与负收益率比较。
    if runtime_config.stop_loss_pct is not None and pnl_pct <= -_to_float(runtime_config.stop_loss_pct, 0.0):
        return True
    return False


def compute_daily_return(holdings: list[Holding], df_all: pd.DataFrame) -> float:
    """根据当日收盘价更新持仓，并计算组合当日收益率。"""
    daily_ret = 0.0
    # 遍历所有持仓，逐只累加“价格涨跌幅 * 仓位占比”。
    for item in holdings:
        # 当日行情中找不到该债时，跳过本只持仓；价格维持上一次值不变。
        if item.bond_code not in df_all.index:
            continue
        row = df_all.loc[item.bond_code]
        # 读取当日收盘价；若缺失则继续沿用上一次价格，避免收益序列断裂。
        cur_price = _safe_float(row.get("close_price"), item.last_price)
        # 只有上一日价格有效时，才能计算今日相对昨日收益。
        if item.last_price > 0:
            daily_ret += ((cur_price - item.last_price) / item.last_price) * item.ratio
        # 不论是否调仓，都把最新价格写回持仓，作为下一日收益计算基准。
        item.last_price = cur_price
    # 回测指标输出保留到 6 位小数，足够表达日收益率精度。
    return round(daily_ret, 6)


def build_candidates(
    df_all: pd.DataFrame,
    trade_date: str,
    strategy_parameters: StrategyParameters,
    candidate_count: int,
) -> pd.DataFrame:
    """给定单日全市场快照，生成按得分排序的候选债列表。

    这里把“单日筛债”作为回测模块的直接组成部分保留在本文件内：
    - `scoring.py` 专注单日过滤与打分公式；
    - `backtest.py` 负责把单日候选进一步接入多日持仓轮动。
    """
    try:
        df_candidate = filter_multiple_factors(
            df_all,
            trade_date=trade_date,
            strategy_parameters=strategy_parameters,
        )
    except KeyError:
        # 关键字段缺失时返回空结果，保持回测流程可继续向下执行。
        return pd.DataFrame(columns=df_all.columns)

    if candidate_count > 0:
        df_candidate = df_candidate.head(candidate_count)
    return df_candidate


def _is_tradeable_row(row: pd.Series) -> bool:
    if "is_tradeable" in row.index:
        return bool(row.get("is_tradeable", False)) and _safe_float(row.get("close_price"), 0.0) > 0
    return bool(build_tradeable_mask(pd.DataFrame([row])).iloc[0])


def _run_backtest_core(
    *,
    dataset: list[tuple[str, pd.DataFrame]],
    candidate_code_map: dict[str, list[str]],
    runtime_config: BacktestRuntimeConfig,
) -> dict[str, object]:
    """执行回测主循环。

    输入说明：
    - `dataset`: 已按时间顺序组织的市场快照序列，每项为 `(trade_date, df_all)`。
    - `candidate_code_map`: 每个交易日对应的候选债代码列表，通常已经按得分降序排列。
    - `runtime_config`: 调仓周期、持仓数量、止盈止损等运行期配置。
    """
    # 当前持仓列表。整个回测过程中它会随卖出和买入不断更新。
    holdings: list[Holding] = []
    # 预先算好单只持仓的目标仓位，避免每日循环重复计算。
    per_position = _position_ratio(runtime_config=runtime_config)
    # 记录每日组合收益率，后续据此计算累计收益和最大回撤。
    daily_returns: list[float] = []
    # 统计平仓中盈利/亏损的次数，用于计算简单胜率。
    sell_win = 0
    sell_loss = 0
    # 记录实际发生调仓的天数。
    rebalanced_days = 0
    # 保存最近一次调仓日的日期与样本索引，供下次判断是否到调仓周期。
    last_rebalance_date: str | None = None
    last_rebalance_index = 0

    # 按交易日顺序逐日推进回测。
    for index, (trade_date, df_all) in enumerate(dataset):
        # 只保留“既在候选列表中、又确实存在于当日行情表”的债券代码。
        ranked_codes = [code for code in candidate_code_map.get(trade_date, []) if code in df_all.index]
        # 转成集合后，便于后续快速判断某持仓今日是否仍在候选池中。
        ranked_set = set(ranked_codes)
        # 先判断今天是否到了应调仓的时间点。
        rebalance_due = _should_rebalance(
            index=index,
            trade_date=trade_date,
            last_rebalance_date=last_rebalance_date,
            last_rebalance_index=last_rebalance_index,
            runtime_config=runtime_config,
        )

        # 第一个交易日不计算收益，只负责按照候选列表完成初始建仓。
        if index == 0:
            for bond_code in ranked_codes:
                # 达到持仓上限后停止继续买入。
                if len(holdings) >= runtime_config.max_hold_count:
                    break
                row = df_all.loc[bond_code]
                if not _is_tradeable_row(row):
                    continue
                price = _safe_float(row.get("close_price"), 0.0)
                # 价格无效的标的不参与建仓。
                if price <= 0:
                    continue
                # 初始持仓的买入价和上一价都设为建仓当日价格。
                holdings.append(Holding(bond_code=bond_code, buy_price=price, last_price=price, ratio=per_position))
            # 首日建仓本身就视作一次调仓起点。
            last_rebalance_date = trade_date
            continue

        # 从第二个交易日起，先基于持仓的昨收与今收计算当天组合收益。
        daily_returns.append(compute_daily_return(holdings, df_all))

        # `keep_list` 表示今日收盘后仍要保留的持仓，`sell_list` 表示需要卖出的持仓。
        keep_list: list[Holding] = []
        sell_list: list[Holding] = []
        for item in holdings:
            # 如果当日行情里已经没有这只债，保守起见视为退出持仓。
            if item.bond_code not in df_all.index:
                sell_list.append(item)
                continue

            row = df_all.loc[item.bond_code]
            if not _is_tradeable_row(row):
                keep_list.append(item)
                continue
            cur_price = _safe_float(row.get("close_price"), item.last_price)
            # 强赎状态优先级最高，一旦触发直接卖出。
            is_redeem_triggered = bool(row.get("is_redeem_triggered", False))

            if is_redeem_triggered:
                sell_list.append(item)
                continue
            # 其次检查止盈止损规则。
            if _should_exit_by_price_limits(runtime_config=runtime_config, item=item, current_price=cur_price):
                sell_list.append(item)
                continue
            # 若启用了“未盈利前继续持有”，则即便今天应调仓、且已不在候选池，也先保留。
            if runtime_config.hold_until_profit and cur_price <= item.buy_price:
                keep_list.append(item)
                continue
            # 今天不是调仓日时，不因为候选池变化而主动换仓。
            if not rebalance_due:
                keep_list.append(item)
                continue
            # 到了调仓日时，仍在候选池中的持仓继续保留，否则卖出腾位。
            if item.bond_code in ranked_set:
                keep_list.append(item)
            else:
                sell_list.append(item)

        # 对所有卖出的持仓统计一次盈亏结果，用于后续胜率计算。
        for item in sell_list:
            if item.bond_code in df_all.index:
                row = df_all.loc[item.bond_code]
                sell_price = _safe_float(row.get("close_price"), item.last_price)
            else:
                # 若缺少当日价格，就退化使用最近一次有效价格估算离场收益。
                sell_price = item.last_price
            pnl_pct = (sell_price - item.buy_price) / item.buy_price * 100 if item.buy_price > 0 else 0
            if pnl_pct > 0:
                sell_win += 1
            else:
                sell_loss += 1

        # 收集仍持有代码，防止补仓时重复买入已保留的持仓。
        existing_codes = {holding.bond_code for holding in keep_list}
        if rebalance_due:
            # 调仓日按候选排序顺序补足仓位，直到达到持仓上限。
            for bond_code in ranked_codes:
                if len(keep_list) >= runtime_config.max_hold_count:
                    break
                if bond_code in existing_codes:
                    continue
                row = df_all.loc[bond_code]
                if not _is_tradeable_row(row):
                    continue
                price = _safe_float(row.get("close_price"), 0.0)
                if price <= 0:
                    continue
                # 新买入持仓的“买入价”和“上一价”都从当日价格开始。
                keep_list.append(Holding(bond_code=bond_code, buy_price=price, last_price=price, ratio=per_position))
                existing_codes.add(bond_code)

        # 用新的持仓列表覆盖旧持仓，进入下一交易日。
        holdings = keep_list
        if rebalance_due:
            # 只有真正到调仓周期时，才更新最近调仓记录。
            rebalanced_days += 1
            last_rebalance_date = trade_date
            last_rebalance_index = index

    # 根据每日收益率序列累计净值，并同步计算最大回撤。
    equity = 1.0
    max_equity = 1.0
    max_dd = 0.0
    for ret in daily_returns:
        # 净值按复利方式滚动。
        equity *= 1 + ret
        # 记录历史最高净值，供回撤计算使用。
        max_equity = max(max_equity, equity)
        # 当前回撤 = 当前净值 / 历史最高净值 - 1，通常为 0 或负数。
        drawdown = equity / max_equity - 1
        max_dd = min(max_dd, drawdown)

    # 将净值与交易统计转换为更易读的百分比指标。
    total_return_pct = (equity - 1) * 100
    max_drawdown_pct = abs(max_dd) * 100
    trade_count = sell_win + sell_loss
    win_rate = (sell_win / trade_count * 100) if trade_count else 0.0
    # 当前 `calmar_like` 和 `return_drawdown_ratio` 等价，都表示收益回撤比。
    calmar_like = total_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0.0
    return_drawdown_ratio = total_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0.0

    # 输出保持为简单字典，便于服务层和 API 直接透传。
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
    """从全市场数据直接执行一次完整回测。

    该入口会先调用候选池构建逻辑，再把候选结果交给统一的回测主循环。
    适合“给定市场快照和策略参数，直接得到回测结果”的常规场景。
    """
    candidate_code_map: dict[str, list[str]] = {}
    for trade_date, df_all in dataset:
        # 先按单日快照生成候选债列表。
        candidate = build_candidates(
            df_all,
            trade_date,
            strategy_parameters,
            runtime_config.candidate_count,
        )
        # 只保留候选表中的债券代码，并再次按运行配置截断数量。
        candidate_code_map[trade_date] = (
            candidate["bond_code"].astype(str).tolist()[: runtime_config.candidate_count] if not candidate.empty else []
        )
    # 候选池准备完成后，统一交给核心回测引擎处理。
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
    """直接使用外部给定的候选池执行回测。

    适用于以下场景：
    - 候选池已经由别的流程预先生成；
    - 需要复用同一候选池反复测试不同运行参数；
    - 做调试时希望跳过筛债阶段，专注验证持仓/调仓逻辑。
    """
    return _run_backtest_core(
        dataset=dataset,
        candidate_code_map=candidate_code_map,
        runtime_config=runtime_config,
    )
