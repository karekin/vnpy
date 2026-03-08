from __future__ import annotations

from vnpy.web.domain.cb_quant.strategy_factor_registry import (
    FactorSupportLevel,
    STRATEGY_FACTOR_MAP,
    TEMPLATE_SELECTABLE_FACTOR_KEYS,
)


# 模板页允许直接选择的强支持因子，统一从策略因子 registry 推导。
STRONG_SUPPORTED_FACTOR_KEYS: tuple[str, ...] = TEMPLATE_SELECTABLE_FACTOR_KEYS


def factor_support_level(factor_key: str) -> FactorSupportLevel:
    definition = STRATEGY_FACTOR_MAP.get(str(factor_key).strip())
    if definition is None:
        return FactorSupportLevel.DISABLED
    return definition.support_level


def is_template_selectable_factor(factor_key: str) -> bool:
    definition = STRATEGY_FACTOR_MAP.get(str(factor_key).strip())
    if definition is None:
        return False
    return definition.template_selectable
