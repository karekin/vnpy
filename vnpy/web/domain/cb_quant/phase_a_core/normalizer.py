"""Phase A 市场快照归一化逻辑。"""

from __future__ import annotations

from typing import Any

import pandas as pd

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
    """把各种真假值统一成 crawler 习惯的 `Y/N` 标志。"""
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
    """把 crawler / Web 快照统一归一化成 Phase A 兼容格式。"""
    if frame.empty:
        return frame

    df = frame.copy()
    if "cb_code" not in df.columns:
        return df

    df["cb_code"] = df["cb_code"].astype(str).str.strip()
    if df.index.name != "cb_code":
        df = df.set_index("cb_code", drop=False)

    for key, default in {
        "cb_name": "",
        "is_unlist": "N",
        "last_is_unlist": "N",
        "is_ransom_flag": "False",
        "date_return_distance": "未到",
        "date_remain_distance": "0天",
        "issue_date": "2022-01-01",
    }.items():
        if key not in df.columns:
            df[key] = default

    df["cb_name"] = df["cb_name"].fillna("").astype(str)
    df["is_unlist"] = df["is_unlist"].apply(_normalize_yn_flag)
    df["last_is_unlist"] = df["last_is_unlist"].apply(_normalize_yn_flag)
    df["is_ransom_flag"] = df["is_ransom_flag"].apply(_normalize_tf_flag)
    df["date_return_distance"] = df["date_return_distance"].fillna("未到").astype(str)
    df["date_remain_distance"] = df["date_remain_distance"].fillna("0天").astype(str)
    df["issue_date"] = df["issue_date"].fillna("2022-01-01").astype(str).str.slice(0, 10)

    for key, default in {
        "price": 0.0,
        "premium_rate": 0.0,
        "pb": 1.5,
        "stock_stdevry": 30.0,
        "remain_amount": 10.0,
        "market_cap": 100.0,
        "new_style": 0.0,
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
