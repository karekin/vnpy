"""Phase A 候选池生成逻辑。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.web.domain.cb_quant.cb_strategy_core.normalizer import _safe_float
from vnpy.web.domain.cb_quant.cb_strategy_core.scoring import filter_multiple_factors
from vnpy.web.domain.cb_quant.cb_strategy_core.settings import multiple_factors_config


def build_strategy_config(setting: dict[str, Any]) -> dict[str, Any]:
    """把外部参数组合转成多因子配置。"""
    cfg = dict(multiple_factors_config)
    stock_ratio = _safe_float(setting["stock_ratio"], cfg["stock_ratio"])
    bond_ratio = round(1 - stock_ratio, 2)

    cfg["price_bemchmark"] = max(0.01, _safe_float(setting["price_bemchmark"], cfg["price_bemchmark"]))
    cfg["premium_bemchmark"] = max(0.01, _safe_float(setting["premium_bemchmark"], cfg["premium_bemchmark"]))
    cfg["stock_ratio"] = stock_ratio
    cfg["bond_ratio"] = bond_ratio
    cfg["premium_ratio"] = _safe_float(setting["premium_ratio"], cfg["premium_ratio"])
    cfg["stock_stdevry_bemchmark"] = max(
        0.01,
        _safe_float(setting["stock_stdevry_bemchmark"], cfg["stock_stdevry_bemchmark"]),
    )
    cfg["max_price"] = _safe_float(setting["max_price"], cfg["max_price"])
    cfg["remain_ratio"] = _safe_float(setting["remain_ratio"], cfg["remain_ratio"])
    cfg["redeem_remain_days_limit"] = setting.get("redeem_remain_days_limit", cfg.get("redeem_remain_days_limit"))
    return cfg


def build_candidates(df_all: pd.DataFrame, date_text: str, cfg: dict[str, Any], head_count: int) -> pd.DataFrame:
    """给定单日全市场快照，生成按得分排序的候选债列表。"""
    try:
        df_candidate = filter_multiple_factors(
            df_all.copy(),
            date=date_text,
            multiple_factors_config=cfg,
        )
    except KeyError:
        return pd.DataFrame(columns=df_all.columns)

    if head_count > 0:
        df_candidate = df_candidate.head(head_count)
    return df_candidate
