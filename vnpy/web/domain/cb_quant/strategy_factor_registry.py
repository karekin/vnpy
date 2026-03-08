from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FactorSupportLevel(str, Enum):
    STRONG = "strong"
    DISABLED = "disabled"


class StrategyFactorKind(str, Enum):
    SCORE = "score"
    STRATEGY_PARAMETER = "strategy_parameter"
    RUNTIME_PARAMETER = "runtime_parameter"


class StrategyScoreMode(str, Enum):
    LOWER_BETTER = "lower_better"
    HIGHER_BETTER = "higher_better"
    ABS_LOWER_BETTER = "abs_lower_better"
    RATING = "rating"


@dataclass(frozen=True)
class StrategyFactorDefinition:
    factor_key: str
    kind: StrategyFactorKind
    label: str
    setting_key: str | None = None
    score_mode: StrategyScoreMode | None = None
    template_selectable: bool = False
    support_level: FactorSupportLevel = FactorSupportLevel.DISABLED
    value_type: str = "number"
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    enum_values: tuple[str, ...] = ()


def build_strategy_factor_usage_hint(definition: StrategyFactorDefinition) -> str:
    if definition.kind == StrategyFactorKind.SCORE:
        return "评分因子：进入 factor_values，在候选打分阶段参与动态评分。"
    if definition.kind == StrategyFactorKind.STRATEGY_PARAMETER:
        return "策略参数：直接写入筛债配置，影响阈值、权重和候选过滤。"
    return "运行参数：直接写入回测执行配置，影响持仓、调仓和止盈止损。"


def _score_factor(
    *,
    factor_key: str,
    label: str,
    score_mode: StrategyScoreMode,
    template_selectable: bool = True,
    support_level: FactorSupportLevel = FactorSupportLevel.STRONG,
    min_value: float | None = None,
    max_value: float | None = None,
    step: float | None = None,
    value_type: str = "number",
    enum_values: tuple[str, ...] = (),
) -> StrategyFactorDefinition:
    return StrategyFactorDefinition(
        factor_key=factor_key,
        kind=StrategyFactorKind.SCORE,
        label=label,
        score_mode=score_mode,
        template_selectable=template_selectable,
        support_level=support_level,
        value_type=value_type,
        min_value=min_value,
        max_value=max_value,
        step=step,
        enum_values=enum_values,
    )


def _setting_factor(
    *,
    factor_key: str,
    label: str,
    kind: StrategyFactorKind,
    template_selectable: bool = False,
    support_level: FactorSupportLevel = FactorSupportLevel.DISABLED,
    min_value: float | None = None,
    max_value: float | None = None,
    step: float | None = None,
    value_type: str = "number",
    enum_values: tuple[str, ...] = (),
) -> StrategyFactorDefinition:
    return StrategyFactorDefinition(
        factor_key=factor_key,
        kind=kind,
        label=label,
        setting_key=factor_key,
        template_selectable=template_selectable,
        support_level=support_level,
        value_type=value_type,
        min_value=min_value,
        max_value=max_value,
        step=step,
        enum_values=enum_values,
    )


STRATEGY_FACTOR_DEFINITIONS: tuple[StrategyFactorDefinition, ...] = (
    _score_factor(
        factor_key="dblow",
        label="双低",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=100,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="conv_prem",
        label="转股溢价率",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=0,
        max_value=40,
        step=2,
    ),
    _score_factor(
        factor_key="bond_prem",
        label="纯债溢价率",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=0,
        max_value=30,
        step=2,
    ),
    _score_factor(
        factor_key="theory_bias",
        label="理论偏离度",
        score_mode=StrategyScoreMode.ABS_LOWER_BETTER,
        min_value=0,
        max_value=20,
        step=2,
    ),
    _score_factor(
        factor_key="theory_value",
        label="理论价值",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=80,
        max_value=160,
        step=5,
    ),
    _score_factor(
        factor_key="option_value",
        label="期权价值",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=5,
        max_value=40,
        step=2,
    ),
    _score_factor(
        factor_key="pure_value",
        label="纯债价值",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=70,
        max_value=130,
        step=5,
    ),
    _score_factor(
        factor_key="conv_value",
        label="转股价值",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=80,
        max_value=160,
        step=5,
    ),
    _score_factor(
        factor_key="conv_price",
        label="转股价格",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=5,
        max_value=30,
        step=1,
    ),
    _score_factor(
        factor_key="close",
        label="收盘价",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=90,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="open",
        label="开盘价",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=90,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="high",
        label="最高价",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=90,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="low",
        label="最低价",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=90,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="pre_close",
        label="前收价",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=90,
        max_value=180,
        step=5,
    ),
    _score_factor(
        factor_key="pct_chg",
        label="涨跌幅",
        score_mode=StrategyScoreMode.ABS_LOWER_BETTER,
        min_value=0,
        max_value=10,
        step=1,
    ),
    _score_factor(
        factor_key="vol",
        label="成交量",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=100,
        max_value=100000,
        step=5000,
    ),
    _score_factor(
        factor_key="amount",
        label="成交额",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=1000,
        max_value=50000,
        step=1000,
    ),
    _score_factor(
        factor_key="turnover",
        label="换手率",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=0.2,
        max_value=8.0,
        step=0.2,
    ),
    _score_factor(
        factor_key="cap_mv_rate",
        label="转债市占比",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=1,
        max_value=80,
        step=1,
    ),
    _score_factor(
        factor_key="ytm",
        label="到期收益率",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=0,
        max_value=8,
        step=0.5,
    ),
    _score_factor(
        factor_key="theory_conv_prem",
        label="理论溢价率",
        score_mode=StrategyScoreMode.ABS_LOWER_BETTER,
        min_value=0,
        max_value=30,
        step=2,
    ),
    _score_factor(
        factor_key="mod_conv_prem",
        label="修正溢价率",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=0,
        max_value=40,
        step=2,
    ),
    _score_factor(
        factor_key="left_years",
        label="剩余年限",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=0.5,
        max_value=6,
        step=0.5,
    ),
    _score_factor(
        factor_key="remain_size",
        label="剩余规模",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=1,
        max_value=80,
        step=1,
    ),
    _score_factor(
        factor_key="issue_size",
        label="发行规模",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=1,
        max_value=120,
        step=2,
    ),
    _score_factor(
        factor_key="remain_cap",
        label="剩余市值",
        score_mode=StrategyScoreMode.LOWER_BETTER,
        min_value=1,
        max_value=120,
        step=2,
    ),
    _score_factor(
        factor_key="list_days",
        label="上市天数",
        score_mode=StrategyScoreMode.HIGHER_BETTER,
        min_value=30,
        max_value=1500,
        step=30,
    ),
    _score_factor(
        factor_key="limit",
        label="涨跌停标记",
        score_mode=StrategyScoreMode.ABS_LOWER_BETTER,
        min_value=-1,
        max_value=1,
        step=1,
    ),
    _score_factor(
        factor_key="rating",
        label="评级",
        score_mode=StrategyScoreMode.RATING,
        template_selectable=False,
        support_level=FactorSupportLevel.DISABLED,
        value_type="enum",
        enum_values=("AA", "AA+", "AAA"),
    ),
    _setting_factor(
        factor_key="price_benchmark",
        label="价格基准",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=106,
        max_value=124,
        step=2,
    ),
    _setting_factor(
        factor_key="premium_benchmark",
        label="溢价率基准",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=16,
        max_value=34,
        step=2,
    ),
    _setting_factor(
        factor_key="stock_weight",
        label="股性总权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=0.20,
        max_value=0.35,
        step=0.05,
    ),
    _setting_factor(
        factor_key="premium_weight",
        label="溢价率权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=0.15,
        max_value=0.35,
        step=0.05,
    ),
    _setting_factor(
        factor_key="volatility_benchmark",
        label="波动率基准",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=20,
        max_value=35,
        step=5,
    ),
    _setting_factor(
        factor_key="max_candidate_price",
        label="候选价格上限",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=130,
        max_value=200,
        step=10,
    ),
    _setting_factor(
        factor_key="outstanding_amount_weight",
        label="剩余规模权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
        min_value=0.10,
        max_value=0.20,
        step=0.05,
    ),
    _setting_factor(
        factor_key="volatility_weight",
        label="波动率权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="market_cap_weight",
        label="市值权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="pb_weight",
        label="PB 权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="option_time_weight",
        label="期权时间权重",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="option_days_benchmark",
        label="期权时间基准天数",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="outstanding_amount_min_yi",
        label="剩余规模下限",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="outstanding_amount_max_yi",
        label="剩余规模上限",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="outstanding_amount_score_min",
        label="剩余规模最低分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="pb_benchmark",
        label="PB 基准",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="pb_score_min",
        label="PB 最低分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="market_cap_min_yi",
        label="市值下限",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="market_cap_max_yi",
        label="市值上限",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="market_cap_score_min",
        label="市值最低分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="market_cap_score_max",
        label="市值最高分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="volatility_score_min",
        label="波动率最低分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="volatility_score_max",
        label="波动率最高分",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="exclude_redeem_days_below",
        label="剔除强赎剩余天数阈值",
        kind=StrategyFactorKind.STRATEGY_PARAMETER,
    ),
    _setting_factor(
        factor_key="rebalance_interval_type",
        label="调仓间隔类型",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
        value_type="enum",
        enum_values=("trade_day", "calendar_day", "week", "month"),
    ),
    _setting_factor(
        factor_key="rebalance_interval_value",
        label="调仓间隔值",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
    ),
    _setting_factor(
        factor_key="max_position_pct",
        label="单仓上限",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
    ),
    _setting_factor(
        factor_key="max_hold_count",
        label="最大持仓数",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
        min_value=5,
        max_value=10,
        step=5,
    ),
    _setting_factor(
        factor_key="candidate_count",
        label="候选数",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
        min_value=5,
        max_value=15,
        step=5,
    ),
    _setting_factor(
        factor_key="take_profit_pct",
        label="止盈阈值",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
    ),
    _setting_factor(
        factor_key="stop_loss_pct",
        label="止损阈值",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
    ),
    _setting_factor(
        factor_key="hold_until_profit",
        label="未盈利继续持有",
        kind=StrategyFactorKind.RUNTIME_PARAMETER,
        value_type="enum",
        enum_values=("true", "false"),
    ),
)

STRATEGY_FACTOR_MAP: dict[str, StrategyFactorDefinition] = {
    definition.factor_key: definition for definition in STRATEGY_FACTOR_DEFINITIONS
}

TEMPLATE_SELECTABLE_FACTOR_KEYS: tuple[str, ...] = tuple(
    definition.factor_key
    for definition in STRATEGY_FACTOR_DEFINITIONS
    if definition.template_selectable
)


def get_strategy_factor_definition(factor_key: str) -> StrategyFactorDefinition | None:
    return STRATEGY_FACTOR_MAP.get(str(factor_key).strip())


def require_strategy_factor_definition(factor_key: str) -> StrategyFactorDefinition:
    definition = get_strategy_factor_definition(factor_key)
    if definition is None:
        raise RuntimeError(f"unsupported strategy factor: {factor_key}")
    return definition
