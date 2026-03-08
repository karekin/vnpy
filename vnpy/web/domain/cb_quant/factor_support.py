from __future__ import annotations

from enum import Enum


class FactorSupportLevel(str, Enum):
    STRONG = "strong"
    DISABLED = "disabled"


# 当前优先保障“基础因子”这批指标的真实可用性。
# 这一组既是模板页允许勾选的强支持因子，也是“直接生成双因子策略”时的来源集合。
STRONG_SUPPORTED_FACTOR_KEYS: tuple[str, ...] = (
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
)

_STRONG_SUPPORTED_FACTOR_KEY_SET: frozenset[str] = frozenset(STRONG_SUPPORTED_FACTOR_KEYS)


def factor_support_level(factor_key: str) -> FactorSupportLevel:
    if factor_key in _STRONG_SUPPORTED_FACTOR_KEY_SET:
        return FactorSupportLevel.STRONG
    return FactorSupportLevel.DISABLED


def is_template_selectable_factor(factor_key: str) -> bool:
    return factor_support_level(factor_key) == FactorSupportLevel.STRONG
