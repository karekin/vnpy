"""可转债策略核心的默认配置与字段映射。"""

from __future__ import annotations

from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS, SNAPSHOT_FIELD_LABELS

# `rename_map` 现在只保留“当前标准快照字段 -> 中文语义”的映射，
# 不再承载历史 Excel/旧脚本时代的遗留字段全集。
rename_map = SNAPSHOT_FIELD_LABELS
snapshot_field_defaults = SNAPSHOT_FIELD_DEFAULTS

head_count = 10
premium_bemchmark = 25
stdevry_bemchmark = 30
stock_ratio = 0.3
bond_ratio = round(1 - stock_ratio, 2)
price_bemchmark = 115
premium_ratio = 0.3
max_price = 130

multiple_factors_config = {
    "benchmark_temperature": 50,
    "bond_ratio": bond_ratio,
    "stock_ratio": stock_ratio,
    "price_bemchmark": price_bemchmark,
    "mid_price_bemchmark": 115,
    "premium_bemchmark": premium_bemchmark,
    "premium_ratio": premium_ratio,
    "stock_stdevry_ratio": 0.2,
    "remain_ratio": 0.15,
    "stock_market_cap_ratio": 0.15,
    "stock_pb_ratio": 0.1,
    "stock_option_ratio": 0.1,
    "stock_option_bemchmark_days": 360,
    "remain_bemchmark_min": 3,
    "remain_bemchmark_max": 30,
    "remain_score_min": 0.6,
    "pb_bemchmark": 1.5,
    "pb_score_min": 0.6,
    "stock_market_cap_bemchmark_min": 30,
    "stock_market_cap_bemchmark_max": 300,
    "stock_market_cap_score_min": 0.6,
    "stock_market_cap_score_max": 1.5,
    "stock_stdevry_bemchmark": stdevry_bemchmark,
    "stock_stdevry_score_min": 0.6,
    "stock_stdevry_score_max": 1.5,
    "max_price": max_price,
    "redeem_remain_days_limit": None,
}
