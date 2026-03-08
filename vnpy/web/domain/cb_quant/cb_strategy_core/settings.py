"""Phase A 默认配置与字段映射。"""

from __future__ import annotations

# item 字段与中文列名的一一映射，主要用于读取 crawler 的 Excel 快照。
rename_map = {
    "cb_code": "可转债代码",
    "cb_name": "可转债名称",
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "industry": "行业",
    "price": "转债价格",
    "premium_rate": "转股溢价率",
    "stock_stdevry": "正股波动率",
    "cb_to_pb": "转股价格/每股净资产",
    "date_remain_distance": "距离到期时间",
    "date_return_distance": "距离回售时间",
    "rate_expire": "到期收益率",
    "rate_expire_aftertax": "税后到期收益率",
    "remain_to_cap": "转债剩余/市值比例",
    "is_repair_flag": "是否满足下修条件",
    "repair_flag_remark": "下修备注",
    "pre_ransom_remark": "预满足强赎备注",
    "is_ransom_flag": "是否满足强赎条件",
    "ransom_flag_remark": "强赎备注",
    "remain_amount": "剩余规模",
    "market_cap": "股票市值",
    "last_price": "上期转债价格",
    "last_cb_percent": "较上期涨跌幅",
    "cb_percent": "转债涨跌幅",
    "stock_price": "股价",
    "stock_percent": "股价涨跌幅",
    "last_stock_price": "上期股价",
    "last_stock_percent": "较上期股价涨跌幅",
    "arbitrage_percent": "日内套利",
    "convert_stock_price": "转股价格",
    "pb": "市净率",
    "market": "市场",
    "remain_price": "剩余本息",
    "remain_price_tax": "税后剩余本息",
    "is_unlist": "未发行",
    "last_is_unlist": "上期未发行",
    "issue_date": "发行日期",
    "date_convert_distance": "距离转股时间",
    "rate_return": "回售收益率",
    "old_style": "老式双底",
    "new_style": "新式双底",
    "rating": "债券评级",
    "id": "id",
    "cb_id": "id",
    "weight_score": "多因子得分",
}

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
