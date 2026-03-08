"""可转债策略核心配置模型。

这个模块只负责“参数定义”和“参数清洗”两件事：
1. 用 Pydantic 模型声明筛债参数与回测运行参数。
2. 在外部传入原始 dict 时，把数据规范化成核心模块可以稳定消费的对象。

由于这些配置会同时被 API、服务层、CLI 和回测核心复用，因此这里尽量把
默认值、边界约束和兜底逻辑集中在一处，避免不同入口出现参数口径不一致。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vnpy.web.domain.cb_quant.strategy_factor_registry import StrategyFactorKind, get_strategy_factor_definition
from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS, SNAPSHOT_FIELD_LABELS


# 历史上前端和部分调用方使用 `rename_map` 这个名字，这里继续保留别名以兼容旧代码。
rename_map = SNAPSHOT_FIELD_LABELS
# 默认因子值同样直接复用快照字段定义中的默认配置，避免多处维护。
snapshot_field_defaults = SNAPSHOT_FIELD_DEFAULTS


class StrategyParameters(BaseModel):
    """筛债打分阶段使用的参数。

    这组参数只影响“如何从单日全市场快照中挑出候选可转债”，
    不负责仓位控制、调仓频率、止盈止损等回测执行细节。
    """

    # 允许外部传入额外字段，但在模型中忽略掉，方便兼容旧版 setting 或前端冗余参数。
    model_config = ConfigDict(extra="ignore")

    # 股性总权重。它控制股性相关多个因子在总分中的整体影响力。
    stock_weight: float = Field(default=0.3, ge=0)
    # 债性总权重。当前会根据 `1 - stock_weight` 自动回算，外部传入值最终不一定保留。
    bond_weight: float = Field(default=0.7, ge=0)
    # 债券价格基准。债价越接近或低于该值，债性得分越高。
    price_benchmark: float = Field(default=115.0, gt=0)
    # 转股溢价率基准。溢价率越接近或低于该值，通常越有利于得分。
    premium_benchmark: float = Field(default=25.0, gt=0)
    # 溢价率因子在股性子分中的权重。
    premium_weight: float = Field(default=0.3, ge=0)
    # 正股波动率基准。波动率越接近或高于该值，通常意味着弹性更强。
    volatility_benchmark: float = Field(default=30.0, gt=0)
    # 波动率因子在股性子分中的权重。
    volatility_weight: float = Field(default=0.2, ge=0)
    # 剩余规模因子权重。用于平衡流动性与弹性。
    outstanding_amount_weight: float = Field(default=0.15, ge=0)
    # 正股市值因子权重。用于惩罚过大或过小的正股体量。
    market_cap_weight: float = Field(default=0.15, ge=0)
    # PB 因子权重。PB 越接近策略偏好的估值区间，得分越好。
    pb_weight: float = Field(default=0.1, ge=0)
    # 剩余期权时间因子权重。存续时间越充足，通常越有利于转债期权价值。
    option_time_weight: float = Field(default=0.1, ge=0)
    # 期权时间价值的基准天数；低于该阈值后会开始扣分。
    option_days_benchmark: float = Field(default=360.0, gt=0)
    # 剩余规模下限，单位是“亿元”。
    outstanding_amount_min_yi: float = Field(default=3.0, ge=0)
    # 剩余规模上限，单位是“亿元”。
    outstanding_amount_max_yi: float = Field(default=30.0, ge=0)
    # 当剩余规模过大时，规模因子允许被压低到的最低分。
    outstanding_amount_score_min: float = Field(default=0.6, ge=0)
    # 正股 PB 基准值。
    pb_benchmark: float = Field(default=1.5, gt=0)
    # PB 因子的最低分下限，避免极端值把总分拉得过低。
    pb_score_min: float = Field(default=0.6, ge=0)
    # 正股市值下限，单位是“亿元”。
    market_cap_min_yi: float = Field(default=30.0, ge=0)
    # 正股市值上限，单位是“亿元”。
    market_cap_max_yi: float = Field(default=300.0, ge=0)
    # 市值因子的最低分下限。
    market_cap_score_min: float = Field(default=0.6, ge=0)
    # 市值因子的最高分上限，允许适度放大但不无限拔高。
    market_cap_score_max: float = Field(default=1.5, ge=0)
    # 波动率因子的最低分下限。
    volatility_score_min: float = Field(default=0.6, ge=0)
    # 波动率因子的最高分上限。
    volatility_score_max: float = Field(default=1.5, ge=0)
    # 候选债允许的最高价格。高于该价格的标的不进入最终候选池。
    max_candidate_price: float = Field(default=130.0, gt=0)
    # 若设置该值，则过滤掉距离赎回日小于等于该阈值的标的；`None` 表示不启用。
    exclude_redeem_days_below: int | None = Field(default=None, ge=0)
    # 前端模板中被显式选中的动态因子 key 列表，主要用于展示和回显。
    selected_factor_keys: list[str] = Field(default_factory=list)
    # 动态因子阈值或目标值配置，会在基础多因子分之上额外参与打分。
    factor_values: dict[str, Any] = Field(default_factory=dict)


class BacktestRuntimeConfig(BaseModel):
    """回测执行阶段使用的参数。

    这组参数不参与候选债打分，而是决定：
    - 何时调仓
    - 最多持有几只债
    - 单只仓位上限
    - 是否启用止盈止损
    """

    # 同样忽略未知字段，保证服务层传整包 setting 时不会因为冗余键而失败。
    model_config = ConfigDict(extra="ignore")

    # 调仓间隔类型：
    # - `trade_day` 按交易日计数
    # - `calendar_day` 按自然日计数
    # - `week` 按周计数
    # - `month` 按月计数
    rebalance_interval_type: str = "trade_day"
    # 调仓间隔数值，必须大于等于 1。
    rebalance_interval_value: int = Field(default=1, ge=1)
    # 单只持仓允许占总资产的最大百分比，范围 0~100。
    max_position_pct: float = Field(default=20.0, ge=0, le=100)
    # 同时持有的最大标的数量。
    max_hold_count: int = Field(default=12, ge=1)
    # 每次从候选池中最多取多少只债进入可买列表。
    candidate_count: int = Field(default=12, ge=1)
    # 回测执行时同样可以带上赎回过滤参数，便于和筛债逻辑共用同一个 setting。
    exclude_redeem_days_below: int | None = Field(default=None, ge=0)
    # 止盈百分比，例如 10 表示浮盈达到 10% 时卖出；`None` 表示不启用。
    take_profit_pct: float | None = Field(default=None, ge=0)
    # 止损百分比，例如 5 表示亏损达到 5% 时卖出；`None` 表示不启用。
    stop_loss_pct: float | None = Field(default=None, ge=0)
    # 为 True 时，调仓日若持仓仍未盈利，则即使掉出候选池也继续持有。
    hold_until_profit: bool = False


def default_strategy_parameters() -> StrategyParameters:
    """生成一份默认筛债参数。

    这里额外做一次 `bond_weight` 回算，确保默认对象内部始终满足
    “债性权重 = 1 - 股性权重”的业务约束。
    """

    # 先按模型默认值构造参数对象。
    params = StrategyParameters()
    # 债性权重不是独立配置源，而是根据股性权重动态推导。
    params.bond_weight = round(max(0.0, 1.0 - params.stock_weight), 2)
    return params


def build_strategy_parameters(values: dict[str, Any] | StrategyParameters | None = None) -> StrategyParameters:
    """把外部输入整理成标准的 `StrategyParameters`。

    支持三类输入：
    - `None`：使用默认值
    - `dict`：常见于 API / 前端传参
    - `StrategyParameters`：常见于内部二次传递
    """

    # 如果已经是模型对象，复制一份深拷贝，避免后续清洗时修改调用方原对象。
    if isinstance(values, StrategyParameters):
        params = values.model_copy(deep=True)
    else:
        # 其它情况统一交给 Pydantic 做类型校验与默认值填充。
        params = StrategyParameters.model_validate(values or {})
        if isinstance(values, dict):
            # 动态因子 key 强制转成字符串，避免前端传数字或其它类型时污染内部键名。
            selected_factor_keys = values.get("selected_factor_keys") or []
            # 动态因子配置表同样要求键是字符串，值保持原样交给后续打分逻辑解释。
            factor_values = values.get("factor_values") or {}
            params.selected_factor_keys = []
            for item in selected_factor_keys:
                factor_key = str(item).strip()
                if not factor_key:
                    continue
                if get_strategy_factor_definition(factor_key) is None:
                    continue
                params.selected_factor_keys.append(factor_key)

            params.factor_values = {}
            for key, value in factor_values.items():
                factor_key = str(key).strip()
                definition = get_strategy_factor_definition(factor_key)
                if definition is None or definition.kind != StrategyFactorKind.SCORE:
                    continue
                params.factor_values[factor_key] = value
    # 无论外部是否显式传了 bond_weight，这里都以 stock_weight 为准重新计算。
    params.bond_weight = round(max(0.0, 1.0 - float(params.stock_weight)), 2)
    # 几个“基准值”参与除法计算，至少收敛到一个极小正数，避免后续出现除零或负基准。
    params.price_benchmark = max(0.01, float(params.price_benchmark))
    params.premium_benchmark = max(0.01, float(params.premium_benchmark))
    params.volatility_benchmark = max(0.01, float(params.volatility_benchmark))
    return params


def build_runtime_config(values: dict[str, Any] | BacktestRuntimeConfig | None = None) -> BacktestRuntimeConfig:
    """把外部输入整理成标准的 `BacktestRuntimeConfig`。"""

    # 模型对象走深拷贝，dict/None 走统一校验入口。
    if isinstance(values, BacktestRuntimeConfig):
        config = values.model_copy(deep=True)
    else:
        config = BacktestRuntimeConfig.model_validate(values or {})
    # 最大持仓数最少保留 1，避免出现“不能持有任何标的”的无效配置。
    config.max_hold_count = max(1, int(config.max_hold_count))
    # 候选池数量不允许小于最大持仓数，否则会导致调仓时无足够候选可补齐仓位。
    config.candidate_count = max(config.max_hold_count, int(config.candidate_count))
    # 调仓间隔同样最少为 1。
    config.rebalance_interval_value = max(1, int(config.rebalance_interval_value))
    # 仓位百分比强制截断到 0~100。
    config.max_position_pct = max(0.0, min(100.0, float(config.max_position_pct)))
    return config


# 旧代码会直接读取这个 dict 作为默认多因子配置，因此继续在模块加载时导出一份普通字典。
multiple_factors_config = default_strategy_parameters().model_dump()
