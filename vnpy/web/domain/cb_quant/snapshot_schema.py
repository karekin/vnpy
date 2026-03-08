"""可转债日级快照的标准字段定义。

这份 schema 是 `cb_daily_snapshot.payload_json` 的唯一标准来源。
所有写库路径都应把原始行整理成这里定义的字段集合，避免：

- 不同数据源写出不同字段名
- 历史兼容字段无限累积
- 策略核心和本地快照回退读取到的字段口径不一致
"""

from __future__ import annotations

from typing import Any


SNAPSHOT_FIELD_DEFAULTS: dict[str, Any] = {
    "cb_code": "",
    "cb_name": "",
    "stock_code": "",
    "stock_name": "",
    "price": 0.0,
    "cb_percent": 0.0,
    "premium_rate": 0.0,
    "convert_stock_price": 0.0,
    "new_style": 0.0,
    "old_style": 0.0,
    "cb_to_pb": 1.0,
    "stock_stdevry": 30.0,
    "stock_price": 0.0,
    "stock_percent": 0.0,
    "pb": 1.5,
    "market_cap": 0.0,
    "remain_amount": 10.0,
    "remain_to_cap": 0.0,
    "issue_date": "2022-01-01",
    "date_return_distance": "未到",
    "date_remain_distance": "0天",
    "date_convert_distance": "已到",
    "is_unlist": "N",
    "last_is_unlist": "N",
    "is_ransom_flag": "False",
    "is_call": "",
    "redeem_remain_days": None,
    "rate_expire": 0.0,
    "rate_expire_aftertax": 0.0,
    "rate_return": 0.0,
    "market": "",
    "rating": "",
    "volume": 0.0,
    "market_source": "",
}


SNAPSHOT_FIELD_LABELS: dict[str, str] = {
    "cb_code": "可转债代码",
    "cb_name": "可转债名称",
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "price": "转债价格",
    "cb_percent": "转债涨跌幅",
    "premium_rate": "转股溢价率",
    "convert_stock_price": "转股价格",
    "new_style": "纯债价值",
    "old_style": "期权价值",
    "cb_to_pb": "转债价格/纯债价值",
    "stock_stdevry": "正股波动率",
    "stock_price": "股价",
    "stock_percent": "股价涨跌幅",
    "pb": "市净率",
    "market_cap": "股票市值",
    "remain_amount": "剩余规模",
    "remain_to_cap": "转债剩余/市值比例",
    "issue_date": "发行日期",
    "date_return_distance": "距离回售时间",
    "date_remain_distance": "距离到期时间",
    "date_convert_distance": "距离转股时间",
    "is_unlist": "未发行",
    "last_is_unlist": "上期未发行",
    "is_ransom_flag": "是否满足强赎条件",
    "is_call": "强赎状态",
    "redeem_remain_days": "强赎剩余天数",
    "rate_expire": "到期收益率",
    "rate_expire_aftertax": "税后到期收益率",
    "rate_return": "回售收益率",
    "market": "市场",
    "rating": "债券评级",
    "volume": "成交额",
    "market_source": "行情来源",
}


_FLOAT_FIELDS = {
    "price",
    "cb_percent",
    "premium_rate",
    "convert_stock_price",
    "new_style",
    "old_style",
    "cb_to_pb",
    "stock_stdevry",
    "stock_price",
    "stock_percent",
    "pb",
    "market_cap",
    "remain_amount",
    "remain_to_cap",
    "rate_expire",
    "rate_expire_aftertax",
    "rate_return",
    "volume",
}
_TEXT_FIELDS = {
    "cb_code",
    "cb_name",
    "stock_code",
    "stock_name",
    "issue_date",
    "date_return_distance",
    "date_remain_distance",
    "date_convert_distance",
    "is_call",
    "market",
    "rating",
    "market_source",
}
_YN_FIELDS = {"is_unlist", "last_is_unlist"}
_TF_FIELDS = {"is_ransom_flag"}


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def _normalize_yn(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "Y" if value else "N"
    text = str(value).strip().upper()
    if text in {"Y", "N"}:
        return text
    if text in {"TRUE", "T", "YES", "1"}:
        return "Y"
    if text in {"FALSE", "F", "NO", "0"}:
        return "N"
    return default


def _normalize_tf(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "True" if value else "False"
    text = str(value).strip()
    if text in {"True", "False"}:
        return text
    upper = text.upper()
    if upper in {"TRUE", "T", "YES", "1"}:
        return "True"
    if upper in {"FALSE", "F", "NO", "0"}:
        return "False"
    return default


def normalize_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    """把任意来源的快照行收口到标准字段集合。"""
    normalized: dict[str, Any] = {}
    source = str(row.get("market_source") or row.get("source") or "").strip()

    for key, default in SNAPSHOT_FIELD_DEFAULTS.items():
        value = row.get(key, default)
        if key == "market_source":
            value = source
        elif key in _FLOAT_FIELDS:
            value = _safe_float(value, float(default))
        elif key in _TEXT_FIELDS:
            value = str(value or default).strip()
        elif key in _YN_FIELDS:
            value = _normalize_yn(value, str(default))
        elif key in _TF_FIELDS:
            value = _normalize_tf(value, str(default))
        elif key == "redeem_remain_days":
            if value in (None, "", "None"):
                value = None
            else:
                try:
                    value = int(float(value))
                except Exception:
                    value = None
        normalized[key] = value

    normalized["cb_code"] = str(normalized["cb_code"]).strip()
    normalized["stock_code"] = str(normalized["stock_code"]).strip()
    normalized["issue_date"] = str(normalized["issue_date"] or SNAPSHOT_FIELD_DEFAULTS["issue_date"])[:10]
    normalized["date_return_distance"] = str(
        normalized["date_return_distance"] or SNAPSHOT_FIELD_DEFAULTS["date_return_distance"]
    )
    normalized["date_remain_distance"] = str(
        normalized["date_remain_distance"] or SNAPSHOT_FIELD_DEFAULTS["date_remain_distance"]
    )
    normalized["date_convert_distance"] = str(
        normalized["date_convert_distance"] or SNAPSHOT_FIELD_DEFAULTS["date_convert_distance"]
    )

    if normalized["cb_to_pb"] <= 0:
        pure_bond_value = float(normalized["new_style"])
        price = float(normalized["price"])
        normalized["cb_to_pb"] = round(price / pure_bond_value, 4) if pure_bond_value > 0 else 1.0

    return normalized
