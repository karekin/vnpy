"""Phase A 策略核心。

这个包承接原 Phase A 策略中对 `vnpy cb-quant` 仍有运行时价值的部分：
- 默认参数配置
- 市场快照归一化
- 候选池生成
- 轻量回测
- CLI 兼容入口
"""

from vnpy.web.domain.cb_quant.phase_a_core.backtest import (
    Holding,
    compute_daily_return,
    run_backtest,
    run_backtest_from_candidates,
)
from vnpy.web.domain.cb_quant.phase_a_core.candidates import build_candidates, build_strategy_config
from vnpy.web.domain.cb_quant.phase_a_core.cli import (
    GLOBAL_TARGET,
    build_optimization_setting,
    evaluate_setting,
    key_func,
    main,
    parse_args,
    save_results,
)
from vnpy.web.domain.cb_quant.phase_a_core.normalizer import normalize_market_frame
from vnpy.web.domain.cb_quant.phase_a_core.settings import multiple_factors_config, rename_map

__all__ = [
    "GLOBAL_TARGET",
    "Holding",
    "build_candidates",
    "build_optimization_setting",
    "build_strategy_config",
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
