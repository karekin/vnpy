"""可转债策略核心。

这个包承接 `vnpy cb-quant` 当前仍在运行时使用的核心能力：
- 默认参数配置
- 市场快照归一化
- 候选池生成
- 轻量回测
- CLI 兼容入口
"""

from vnpy.web.core.cb_backtest.backtest import (
    Holding,
    compute_daily_return,
    run_backtest,
    run_backtest_from_candidates,
)
from vnpy.web.core.cb_backtest.candidates import build_candidates, build_strategy_parameters
from vnpy.web.core.cb_backtest.cli import (
    GLOBAL_TARGET,
    build_optimization_setting,
    evaluate_setting,
    key_func,
    main,
    parse_args,
    save_results,
)
from vnpy.web.core.cb_backtest.normalizer import normalize_market_frame
from vnpy.web.core.cb_backtest.settings import (
    BacktestRuntimeConfig,
    StrategyParameters,
    build_runtime_config,
    multiple_factors_config,
    rename_map,
)

__all__ = [
    "GLOBAL_TARGET",
    "BacktestRuntimeConfig",
    "Holding",
    "StrategyParameters",
    "build_candidates",
    "build_optimization_setting",
    "build_runtime_config",
    "build_strategy_parameters",
    "compute_daily_return",
    "evaluate_setting",
    "key_func",
    "main",
    "multiple_factors_config",
    "normalize_market_frame",
    "parse_args",
    "rename_map",
    "run_backtest",
    "run_backtest_from_candidates",
    "save_results",
]
