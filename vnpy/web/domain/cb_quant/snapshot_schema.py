"""可转债标准快照 schema。

这份模型是 `cb_daily_snapshot.payload_json` 的唯一真源：

- 数据写库前统一规范到 `SnapshotRow`
- 策略核心和回测统一消费这些标准字段
- 中文名、默认值、类型只在这一处维护
"""

from __future__ import annotations

from enum import Enum
import re
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
    OPEN_PRICE = "open_price"
    HIGH_PRICE = "high_price"
    LOW_PRICE = "low_price"
    PRE_CLOSE_PRICE = "pre_close_price"
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
    VOLUME_HAND = "volume_hand"
    TURNOVER_AMOUNT_WAN = "turnover_amount_wan"
    TURNOVER_RATE_PCT = "turnover_rate_pct"
    ISSUE_SIZE_YI = "issue_size_yi"
    LIMIT_STATUS = "limit_status"
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


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _to_code6(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else text


def _to_yi_amount(value: Any, default: float = 0.0) -> float:
    amount = _to_float(value, default)
    if abs(amount) >= 10_000:
        return amount / 100_000_000.0
    return amount


def _to_put_status(value: Any) -> PutStatus:
    text = str(value or "").strip()
    if not text:
        return PutStatus.NOT_REACHED
    if text in {PutStatus.NOT_APPLICABLE.value, "无权"}:
        return PutStatus.NOT_APPLICABLE
    if text in {PutStatus.ACTIVE.value, "回售内"}:
        return PutStatus.ACTIVE
    if text in {PutStatus.NOT_REACHED.value, "未到", "已到"}:
        return PutStatus.NOT_REACHED
    try:
        return PutStatus(text)
    except Exception:
        return PutStatus.NOT_REACHED


def _to_days_to_maturity(data: dict[str, Any]) -> int:
    direct = _pick(data, "days_to_maturity")
    if direct not in (None, "", "None"):
        return max(0, _to_int(direct, 0))

    remain_years = _pick(data, "remain_years")
    if remain_years not in (None, "", "None"):
        years = _to_float(remain_years, 0.0)
        if years > 0:
            return max(0, int(round(years * 365.0)))

    text = str(_pick(data, "date_remain_distance", default="")).strip()
    if not text:
        return 0
    day_match = re.search(r"(-?\d+)\s*天", text)
    if day_match:
        return max(0, int(day_match.group(1)))
    year_match = re.search(r"(-?\d+(?:\.\d+)?)\s*年", text)
    if year_match:
        return max(0, int(round(float(year_match.group(1)) * 365.0)))
    return 0


def _to_is_listed(data: dict[str, Any], *, prev_day: bool = False) -> bool:
    standard_key = "was_listed_prev_day" if prev_day else "is_listed"
    legacy_key = "last_is_unlist" if prev_day else "is_unlist"
    if standard_key in data:
        return _to_bool(data.get(standard_key), True)
    legacy = str(data.get(legacy_key) or "").strip().upper()
    if legacy in {"Y", "TRUE", "T", "YES", "1"}:
        return False
    if legacy in {"N", "FALSE", "F", "NO", "0"}:
        return True
    return True


class SnapshotRow(BaseModel):
    """回测快照的标准字段模型。"""

    model_config = ConfigDict(extra="ignore")

    bond_code: str = Field(default="", json_schema_extra={"label": "可转债代码"})
    bond_name: str = Field(default="", json_schema_extra={"label": "可转债名称"})
    underlying_stock_code: str = Field(default="", json_schema_extra={"label": "正股代码"})
    underlying_stock_name: str = Field(default="", json_schema_extra={"label": "正股名称"})
    close_price: float = Field(default=0.0, json_schema_extra={"label": "转债收盘价", "unit": "元"})
    open_price: float = Field(default=0.0, json_schema_extra={"label": "转债开盘价", "unit": "元"})
    high_price: float = Field(default=0.0, json_schema_extra={"label": "转债最高价", "unit": "元"})
    low_price: float = Field(default=0.0, json_schema_extra={"label": "转债最低价", "unit": "元"})
    pre_close_price: float = Field(default=0.0, json_schema_extra={"label": "转债前收盘价", "unit": "元"})
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
    volume_hand: float = Field(default=0.0, json_schema_extra={"label": "成交量", "unit": "手"})
    turnover_amount_wan: float = Field(default=0.0, json_schema_extra={"label": "成交额", "unit": "万"})
    turnover_rate_pct: float = Field(default=0.0, json_schema_extra={"label": "换手率", "unit": "%"})
    issue_size_yi: float = Field(default=0.0, json_schema_extra={"label": "发行规模", "unit": "亿"})
    limit_status: int = Field(default=0, json_schema_extra={"label": "涨跌停标记"})
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
        bond_code=_to_code6(_pick(data, "bond_code", "cb_code")),
        bond_name=str(_pick(data, "bond_name", "cb_name", default="")).strip(),
        underlying_stock_code=_to_code6(_pick(data, "underlying_stock_code", "stock_id", "stock_code", "stock_ts_code")),
        underlying_stock_name=str(_pick(data, "underlying_stock_name", "stock_name", default="")).strip(),
        close_price=_to_float(_pick(data, "close_price", "price"), 0.0),
        open_price=_to_float(_pick(data, "open_price", "open"), 0.0),
        high_price=_to_float(_pick(data, "high_price", "high"), 0.0),
        low_price=_to_float(_pick(data, "low_price", "low"), 0.0),
        pre_close_price=_to_float(_pick(data, "pre_close_price", "pre_close", "preclose"), 0.0),
        bond_pct_change=_to_float(_pick(data, "bond_pct_change", "cb_percent", "increase_rt"), 0.0),
        conversion_premium_pct=_to_float(_pick(data, "conversion_premium_pct", "premium_rate", "premium_rt", "bond_prem"), 0.0),
        conversion_price=_to_float(_pick(data, "conversion_price", "convert_price"), 0.0),
        pure_bond_value=_to_float(_pick(data, "pure_bond_value", "new_style", "bond_value", "pure_value"), 0.0),
        option_value=_to_float(_pick(data, "option_value", "old_style"), 0.0),
        bond_pure_value_ratio=_to_float(_pick(data, "bond_pure_value_ratio", "cb_to_pb"), 1.0),
        underlying_volatility=_to_float(_pick(data, "underlying_volatility", "stock_stdevry", "stock_volatility"), 30.0),
        underlying_close_price=_to_float(_pick(data, "underlying_close_price", "stock_price"), 0.0),
        underlying_pct_change=_to_float(_pick(data, "underlying_pct_change", "stock_percent", "stock_increase_rt"), 0.0),
        underlying_pb=_to_float(_pick(data, "underlying_pb", "pb"), 1.5),
        underlying_market_cap_yi=_to_yi_amount(_pick(data, "underlying_market_cap_yi", "market_cap"), 0.0),
        outstanding_amount_yi=_to_yi_amount(_pick(data, "outstanding_amount_yi", "remain_amount"), 10.0),
        outstanding_to_market_cap_ratio=_to_float(_pick(data, "outstanding_to_market_cap_ratio", "float_mv_ratio"), 0.0),
        listing_date=str(_pick(data, "listing_date", "issue_date", default=SNAPSHOT_FIELD_DEFAULTS["listing_date"]))[:10],
        put_status=_to_put_status(_pick(data, "put_status", "date_return_distance")),
        days_to_maturity=_to_days_to_maturity(data),
        days_to_conversion_start=max(0, _to_int(_pick(data, "days_to_conversion_start"), 0)),
        is_listed=_to_is_listed(data, prev_day=False),
        was_listed_prev_day=_to_is_listed(data, prev_day=True),
        is_redeem_triggered=_to_bool(_pick(data, "is_redeem_triggered", "is_ransom_flag"), False),
        redeem_status=str(_pick(data, "redeem_status", "ransom_flag_remark", default="")).strip(),
        days_to_redeem=_to_optional_int(_pick(data, "days_to_redeem", "redeem_remain_days")),
        ytm_to_maturity_pct=_to_float(_pick(data, "ytm_to_maturity_pct", "rate_expire", "expiry_ytm_pre_tax"), 0.0),
        ytm_to_maturity_after_tax_pct=_to_float(_pick(data, "ytm_to_maturity_after_tax_pct", "rate_expire_aftertax"), 0.0),
        ytm_to_put_pct=_to_float(_pick(data, "ytm_to_put_pct", "rate_return", "put_ytm"), 0.0),
        market=str(_pick(data, "market", default="")).strip(),
        rating=str(_pick(data, "rating", default="")).strip(),
        volume_hand=_to_float(_pick(data, "volume_hand", "vol"), 0.0),
        turnover_amount_wan=_to_float(_pick(data, "turnover_amount_wan", "amount_wan"), 0.0),
        turnover_rate_pct=_to_float(_pick(data, "turnover_rate_pct", "turnover_rt"), 0.0),
        issue_size_yi=_to_yi_amount(_pick(data, "issue_size_yi", "issue_scale_yi", "issue_size"), 0.0),
        limit_status=_to_int(_pick(data, "limit_status", "limit"), 0),
        data_source=str(_pick(data, "data_source", "source", default="")).strip(),
    )
    dumped = normalized.model_dump()
    if dumped["pre_close_price"] <= 0:
        pct = float(dumped["bond_pct_change"])
        divisor = 1.0 + pct / 100.0
        if abs(divisor) > 1e-6:
            dumped["pre_close_price"] = round(float(dumped["close_price"]) / divisor, 4)
    if dumped["issue_size_yi"] <= 0 and dumped["outstanding_amount_yi"] > 0:
        dumped["issue_size_yi"] = float(dumped["outstanding_amount_yi"])
    if dumped["bond_pure_value_ratio"] <= 0:
        pure_bond_value = float(dumped["pure_bond_value"])
        close_price = float(dumped["close_price"])
        dumped["bond_pure_value_ratio"] = round(close_price / pure_bond_value, 4) if pure_bond_value > 0 else 1.0
    if dumped["limit_status"] == 0:
        pct = float(dumped["bond_pct_change"])
        if pct >= 19.5:
            dumped["limit_status"] = 1
        elif pct <= -19.5:
            dumped["limit_status"] = -1
    return dumped
