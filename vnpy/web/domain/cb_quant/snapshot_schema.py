"""可转债标准快照 schema。

这份模型是 `cb_daily_snapshot.payload_json` 的唯一真源：

- 数据写库前统一规范到 `SnapshotRow`
- 策略核心和回测统一消费这些标准字段
- 中文名、默认值、类型只在这一处维护
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        """Python 3.10 fallback for enum.StrEnum."""


class SnapshotField(StrEnum):
    BOND_CODE = "bond_code"
    BOND_NAME = "bond_name"
    UNDERLYING_STOCK_CODE = "underlying_stock_code"
    UNDERLYING_STOCK_NAME = "underlying_stock_name"
    CLOSE_PRICE = "close_price"
    BOND_PCT_CHANGE = "bond_pct_change"
    CONVERSION_PREMIUM_PCT = "conversion_premium_pct"
    CONVERSION_PRICE = "conversion_price"
    PURE_BOND_VALUE = "pure_bond_value"
    OPTION_VALUE = "option_value"
    BOND_PURE_VALUE_RATIO = "bond_pure_value_ratio"
    UNDERLYING_VOLATILITY = "underlying_volatility"
    UNDERLYING_CLOSE_PRICE = "underlying_close_price"
    UNDERLYING_PCT_CHANGE = "underlying_pct_change"
    UNDERLYING_PB = "underlying_pb"
    UNDERLYING_MARKET_CAP_YI = "underlying_market_cap_yi"
    OUTSTANDING_AMOUNT_YI = "outstanding_amount_yi"
    OUTSTANDING_TO_MARKET_CAP_RATIO = "outstanding_to_market_cap_ratio"
    LISTING_DATE = "listing_date"
    PUT_STATUS = "put_status"
    DAYS_TO_MATURITY = "days_to_maturity"
    DAYS_TO_CONVERSION_START = "days_to_conversion_start"
    IS_LISTED = "is_listed"
    WAS_LISTED_PREV_DAY = "was_listed_prev_day"
    IS_REDEEM_TRIGGERED = "is_redeem_triggered"
    REDEEM_STATUS = "redeem_status"
    DAYS_TO_REDEEM = "days_to_redeem"
    YTM_TO_MATURITY_PCT = "ytm_to_maturity_pct"
    YTM_TO_MATURITY_AFTER_TAX_PCT = "ytm_to_maturity_after_tax_pct"
    YTM_TO_PUT_PCT = "ytm_to_put_pct"
    MARKET = "market"
    RATING = "rating"
    TURNOVER_AMOUNT_WAN = "turnover_amount_wan"
    DATA_SOURCE = "data_source"


class PutStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_REACHED = "not_reached"
    ACTIVE = "active"


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return int(float(value))
    except Exception:
        return default


def _to_optional_int(value: Any) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return default


class SnapshotRow(BaseModel):
    """回测快照的标准字段模型。"""

    model_config = ConfigDict(extra="ignore")

    bond_code: str = Field(default="", json_schema_extra={"label": "可转债代码"})
    bond_name: str = Field(default="", json_schema_extra={"label": "可转债名称"})
    underlying_stock_code: str = Field(default="", json_schema_extra={"label": "正股代码"})
    underlying_stock_name: str = Field(default="", json_schema_extra={"label": "正股名称"})
    close_price: float = Field(default=0.0, json_schema_extra={"label": "转债收盘价", "unit": "元"})
    bond_pct_change: float = Field(default=0.0, json_schema_extra={"label": "转债涨跌幅", "unit": "%"})
    conversion_premium_pct: float = Field(default=0.0, json_schema_extra={"label": "转股溢价率", "unit": "%"})
    conversion_price: float = Field(default=0.0, json_schema_extra={"label": "转股价", "unit": "元"})
    pure_bond_value: float = Field(default=0.0, json_schema_extra={"label": "纯债价值", "unit": "元"})
    option_value: float = Field(default=0.0, json_schema_extra={"label": "期权价值", "unit": "元"})
    bond_pure_value_ratio: float = Field(default=1.0, json_schema_extra={"label": "债价债底比"})
    underlying_volatility: float = Field(default=30.0, json_schema_extra={"label": "正股波动率"})
    underlying_close_price: float = Field(default=0.0, json_schema_extra={"label": "正股价格", "unit": "元"})
    underlying_pct_change: float = Field(default=0.0, json_schema_extra={"label": "正股涨跌幅", "unit": "%"})
    underlying_pb: float = Field(default=1.5, json_schema_extra={"label": "正股 PB"})
    underlying_market_cap_yi: float = Field(default=0.0, json_schema_extra={"label": "正股市值", "unit": "亿"})
    outstanding_amount_yi: float = Field(default=10.0, json_schema_extra={"label": "剩余规模", "unit": "亿"})
    outstanding_to_market_cap_ratio: float = Field(default=0.0, json_schema_extra={"label": "剩余规模/市值比"})
    listing_date: str = Field(default="2022-01-01", json_schema_extra={"label": "上市日期"})
    put_status: PutStatus = Field(default=PutStatus.NOT_REACHED, json_schema_extra={"label": "回售状态"})
    days_to_maturity: int = Field(default=0, json_schema_extra={"label": "距离到期天数", "unit": "天"})
    days_to_conversion_start: int = Field(default=0, json_schema_extra={"label": "距离转股开始天数", "unit": "天"})
    is_listed: bool = Field(default=True, json_schema_extra={"label": "是否已上市"})
    was_listed_prev_day: bool = Field(default=True, json_schema_extra={"label": "上一交易日是否已上市"})
    is_redeem_triggered: bool = Field(default=False, json_schema_extra={"label": "是否满足强赎条件"})
    redeem_status: str = Field(default="", json_schema_extra={"label": "强赎状态"})
    days_to_redeem: int | None = Field(default=None, json_schema_extra={"label": "距离强赎天数", "unit": "天"})
    ytm_to_maturity_pct: float = Field(default=0.0, json_schema_extra={"label": "到期收益率", "unit": "%"})
    ytm_to_maturity_after_tax_pct: float = Field(default=0.0, json_schema_extra={"label": "税后到期收益率", "unit": "%"})
    ytm_to_put_pct: float = Field(default=0.0, json_schema_extra={"label": "回售收益率", "unit": "%"})
    market: str = Field(default="", json_schema_extra={"label": "市场"})
    rating: str = Field(default="", json_schema_extra={"label": "评级"})
    turnover_amount_wan: float = Field(default=0.0, json_schema_extra={"label": "成交额", "unit": "万"})
    data_source: str = Field(default="", json_schema_extra={"label": "数据来源"})


def _build_field_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, field_info in SnapshotRow.model_fields.items():
        extra = field_info.json_schema_extra or {}
        labels[key] = str(extra.get("label") or key)
    return labels


SNAPSHOT_FIELD_LABELS: dict[str, str] = _build_field_labels()
SNAPSHOT_FIELD_DEFAULTS: dict[str, Any] = SnapshotRow().model_dump()


def normalize_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    """把任意来源的快照行收口到标准字段集合。"""
    data = dict(row)
    normalized = SnapshotRow(
        bond_code=str(data.get("bond_code") or "").strip(),
        bond_name=str(data.get("bond_name") or "").strip(),
        underlying_stock_code=str(data.get("underlying_stock_code") or "").strip(),
        underlying_stock_name=str(data.get("underlying_stock_name") or "").strip(),
        close_price=_to_float(data.get("close_price"), 0.0),
        bond_pct_change=_to_float(data.get("bond_pct_change"), 0.0),
        conversion_premium_pct=_to_float(data.get("conversion_premium_pct"), 0.0),
        conversion_price=_to_float(data.get("conversion_price"), 0.0),
        pure_bond_value=_to_float(data.get("pure_bond_value"), 0.0),
        option_value=_to_float(data.get("option_value"), 0.0),
        bond_pure_value_ratio=_to_float(data.get("bond_pure_value_ratio"), 1.0),
        underlying_volatility=_to_float(data.get("underlying_volatility"), 30.0),
        underlying_close_price=_to_float(data.get("underlying_close_price"), 0.0),
        underlying_pct_change=_to_float(data.get("underlying_pct_change"), 0.0),
        underlying_pb=_to_float(data.get("underlying_pb"), 1.5),
        underlying_market_cap_yi=_to_float(data.get("underlying_market_cap_yi"), 0.0),
        outstanding_amount_yi=_to_float(data.get("outstanding_amount_yi"), 10.0),
        outstanding_to_market_cap_ratio=_to_float(data.get("outstanding_to_market_cap_ratio"), 0.0),
        listing_date=str(data.get("listing_date") or SNAPSHOT_FIELD_DEFAULTS["listing_date"])[:10],
        put_status=PutStatus(str(data.get("put_status") or PutStatus.NOT_REACHED)),
        days_to_maturity=max(0, _to_int(data.get("days_to_maturity"), 0)),
        days_to_conversion_start=max(0, _to_int(data.get("days_to_conversion_start"), 0)),
        is_listed=_to_bool(data.get("is_listed"), True),
        was_listed_prev_day=_to_bool(data.get("was_listed_prev_day"), True),
        is_redeem_triggered=_to_bool(data.get("is_redeem_triggered"), False),
        redeem_status=str(data.get("redeem_status") or "").strip(),
        days_to_redeem=_to_optional_int(data.get("days_to_redeem")),
        ytm_to_maturity_pct=_to_float(data.get("ytm_to_maturity_pct"), 0.0),
        ytm_to_maturity_after_tax_pct=_to_float(data.get("ytm_to_maturity_after_tax_pct"), 0.0),
        ytm_to_put_pct=_to_float(data.get("ytm_to_put_pct"), 0.0),
        market=str(data.get("market") or "").strip(),
        rating=str(data.get("rating") or "").strip(),
        turnover_amount_wan=_to_float(data.get("turnover_amount_wan"), 0.0),
        data_source=str(data.get("data_source") or "").strip(),
    )
    dumped = normalized.model_dump()
    if dumped["bond_pure_value_ratio"] <= 0:
        pure_bond_value = float(dumped["pure_bond_value"])
        close_price = float(dumped["close_price"])
        dumped["bond_pure_value_ratio"] = round(close_price / pure_bond_value, 4) if pure_bond_value > 0 else 1.0
    return dumped
