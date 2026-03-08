"""可转债市场快照归一化逻辑。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS

_TRUE_LIKE = {"1", "true", "t", "yes", "y"}
_FALSE_LIKE = {"0", "false", "f", "no", "n", ""}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """宽松地把任意值转成 float，失败时返回默认值。"""
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def _normalize_yn_flag(value: Any, *, default: str = "N") -> str:
    """把各种真假值统一成历史兼容字段使用的 `Y/N` 标志。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return "Y" if value else "N"
    text = str(value).strip()
    if not text:
        return default
    upper = text.upper()
    if upper in {"Y", "N"}:
        return upper
    lower = text.lower()
    if lower in _TRUE_LIKE:
        return "Y"
    if lower in _FALSE_LIKE:
        return "N"
    return default


def _normalize_tf_flag(value: Any, *, default: str = "False") -> str:
    """把各种真假值统一成字符串形式的 `True/False`。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return "True" if value else "False"
    text = str(value).strip()
    if not text:
        return default
    if text in {"True", "False"}:
        return text
    lower = text.lower()
    if lower in _TRUE_LIKE:
        return "True"
    if lower in _FALSE_LIKE:
        return "False"
    return default


def _ensure_float_column(frame: pd.DataFrame, column: str, default: float) -> None:
    """保证 DataFrame 中指定列存在且可转成数值。"""
    if column not in frame.columns:
        frame[column] = default
        return
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(default)


def normalize_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """把快照库中的行数据统一归一化成策略核心可直接消费的格式。

    目标不是恢复历史文件格式，而是保证：
    - 字段名与当前筛债/回测逻辑对齐
    - 缺失字段能被补默认值
    - 字段类型足够稳定，避免在评分或回测中反复兜底
    """
    if frame.empty:
        return frame

    df = frame.copy()
    if "cb_code" not in df.columns:
        return df

    df["cb_code"] = df["cb_code"].astype(str).str.strip()
    if df.index.name != "cb_code":
        df = df.set_index("cb_code", drop=False)

    for key, default in SNAPSHOT_FIELD_DEFAULTS.items():
        if key not in df.columns:
            df[key] = default

    df["cb_name"] = df["cb_name"].fillna(SNAPSHOT_FIELD_DEFAULTS["cb_name"]).astype(str)
    df["is_unlist"] = df["is_unlist"].apply(_normalize_yn_flag)
    df["last_is_unlist"] = df["last_is_unlist"].apply(_normalize_yn_flag)
    df["is_ransom_flag"] = df["is_ransom_flag"].apply(_normalize_tf_flag)
    df["date_return_distance"] = df["date_return_distance"].fillna(SNAPSHOT_FIELD_DEFAULTS["date_return_distance"]).astype(str)
    df["date_remain_distance"] = df["date_remain_distance"].fillna(SNAPSHOT_FIELD_DEFAULTS["date_remain_distance"]).astype(str)
    df["date_convert_distance"] = df["date_convert_distance"].fillna(SNAPSHOT_FIELD_DEFAULTS["date_convert_distance"]).astype(str)
    df["issue_date"] = df["issue_date"].fillna(SNAPSHOT_FIELD_DEFAULTS["issue_date"]).astype(str).str.slice(0, 10)
    df["is_call"] = df["is_call"].fillna("").astype(str)
    df["market"] = df["market"].fillna("").astype(str)
    df["rating"] = df["rating"].fillna("").astype(str)
    df["market_source"] = df["market_source"].fillna("").astype(str)
    if "redeem_remain_days" in df.columns:
        df["redeem_remain_days"] = pd.to_numeric(df["redeem_remain_days"], errors="coerce")

    for key, default in {
        "price": SNAPSHOT_FIELD_DEFAULTS["price"],
        "cb_percent": SNAPSHOT_FIELD_DEFAULTS["cb_percent"],
        "premium_rate": SNAPSHOT_FIELD_DEFAULTS["premium_rate"],
        "convert_stock_price": SNAPSHOT_FIELD_DEFAULTS["convert_stock_price"],
        "old_style": SNAPSHOT_FIELD_DEFAULTS["old_style"],
        "pb": SNAPSHOT_FIELD_DEFAULTS["pb"],
        "stock_stdevry": SNAPSHOT_FIELD_DEFAULTS["stock_stdevry"],
        "stock_price": SNAPSHOT_FIELD_DEFAULTS["stock_price"],
        "stock_percent": SNAPSHOT_FIELD_DEFAULTS["stock_percent"],
        "remain_amount": SNAPSHOT_FIELD_DEFAULTS["remain_amount"],
        "remain_to_cap": SNAPSHOT_FIELD_DEFAULTS["remain_to_cap"],
        "market_cap": SNAPSHOT_FIELD_DEFAULTS["market_cap"],
        "new_style": SNAPSHOT_FIELD_DEFAULTS["new_style"],
        "rate_expire": SNAPSHOT_FIELD_DEFAULTS["rate_expire"],
        "rate_expire_aftertax": SNAPSHOT_FIELD_DEFAULTS["rate_expire_aftertax"],
        "rate_return": SNAPSHOT_FIELD_DEFAULTS["rate_return"],
        "volume": SNAPSHOT_FIELD_DEFAULTS["volume"],
    }.items():
        _ensure_float_column(df, key, default)

    if "cb_to_pb" not in df.columns:
        df["cb_to_pb"] = pd.NA
    df["cb_to_pb"] = pd.to_numeric(df["cb_to_pb"], errors="coerce")

    derived_cb_to_pb = pd.Series(float("nan"), index=df.index, dtype="float64")
    if "new_style" in df.columns:
        positive_mask = df["new_style"] > 0
        derived_cb_to_pb.loc[positive_mask] = df.loc[positive_mask, "price"] / df.loc[positive_mask, "new_style"]

    invalid_mask = df["cb_to_pb"].isna() | (df["cb_to_pb"] <= 0)
    df.loc[invalid_mask, "cb_to_pb"] = derived_cb_to_pb.loc[invalid_mask]
    df["cb_to_pb"] = pd.to_numeric(df["cb_to_pb"], errors="coerce").fillna(1.0)
    return df
