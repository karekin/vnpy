from __future__ import annotations

from enum import Enum


class FactorSupportLevel(str, Enum):
    STRONG = "strong"
    DISABLED = "disabled"


# 当前优先保障“基础因子”这批指标的真实可用性。前端模板页只允许选择这一组，
# 批量展开策略时也只会基于这一组生成子集组合。
STRONG_SUPPORTED_FACTOR_KEYS: frozenset[str] = frozenset(
    {
        "dblow",
        "conv_prem",
        "bond_prem",
        "theory_bias",
        "theory_value",
        "option_value",
        "pure_value",
        "conv_value",
        "conv_price",
        "close",
        "open",
        "high",
        "low",
        "pre_close",
        "pct_chg",
        "vol",
        "amount",
        "turnover",
        "cap_mv_rate",
        "ytm",
        "theory_conv_prem",
        "mod_conv_prem",
        "left_years",
        "remain_size",
        "issue_size",
        "remain_cap",
        "list_days",
        "limit",
    }
)


def factor_support_level(factor_key: str) -> FactorSupportLevel:
    if factor_key in STRONG_SUPPORTED_FACTOR_KEYS:
        return FactorSupportLevel.STRONG
    return FactorSupportLevel.DISABLED


def is_template_selectable_factor(factor_key: str) -> bool:
    return factor_support_level(factor_key) == FactorSupportLevel.STRONG
