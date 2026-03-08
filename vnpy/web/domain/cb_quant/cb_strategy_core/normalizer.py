"""可转债市场快照归一化逻辑。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def _ensure_float_column(frame: pd.DataFrame, column: str, default: float) -> None:
    if column not in frame.columns:
        frame[column] = default
        return
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _ensure_bool_column(frame: pd.DataFrame, column: str, default: bool) -> None:
    if column not in frame.columns:
        frame[column] = default
    frame[column] = frame[column].apply(lambda value: bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "t", "yes", "y"})


def normalize_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """把快照库中的行数据统一归一化成策略核心可直接消费的格式。"""
    if frame.empty:
        return frame

    df = frame.copy()
    if "bond_code" not in df.columns:
        return df

    df["bond_code"] = df["bond_code"].astype(str).str.strip()
    if df.index.name != "bond_code":
        df = df.set_index("bond_code", drop=False)

    for key, default in SNAPSHOT_FIELD_DEFAULTS.items():
        if key not in df.columns:
            df[key] = default

    for key, default in {
        "close_price": SNAPSHOT_FIELD_DEFAULTS["close_price"],
        "bond_pct_change": SNAPSHOT_FIELD_DEFAULTS["bond_pct_change"],
        "conversion_premium_pct": SNAPSHOT_FIELD_DEFAULTS["conversion_premium_pct"],
        "conversion_price": SNAPSHOT_FIELD_DEFAULTS["conversion_price"],
        "pure_bond_value": SNAPSHOT_FIELD_DEFAULTS["pure_bond_value"],
        "option_value": SNAPSHOT_FIELD_DEFAULTS["option_value"],
        "bond_pure_value_ratio": SNAPSHOT_FIELD_DEFAULTS["bond_pure_value_ratio"],
        "underlying_volatility": SNAPSHOT_FIELD_DEFAULTS["underlying_volatility"],
        "underlying_close_price": SNAPSHOT_FIELD_DEFAULTS["underlying_close_price"],
        "underlying_pct_change": SNAPSHOT_FIELD_DEFAULTS["underlying_pct_change"],
        "underlying_pb": SNAPSHOT_FIELD_DEFAULTS["underlying_pb"],
        "underlying_market_cap_yi": SNAPSHOT_FIELD_DEFAULTS["underlying_market_cap_yi"],
        "outstanding_amount_yi": SNAPSHOT_FIELD_DEFAULTS["outstanding_amount_yi"],
        "outstanding_to_market_cap_ratio": SNAPSHOT_FIELD_DEFAULTS["outstanding_to_market_cap_ratio"],
        "days_to_maturity": SNAPSHOT_FIELD_DEFAULTS["days_to_maturity"],
        "days_to_conversion_start": SNAPSHOT_FIELD_DEFAULTS["days_to_conversion_start"],
        "ytm_to_maturity_pct": SNAPSHOT_FIELD_DEFAULTS["ytm_to_maturity_pct"],
        "ytm_to_maturity_after_tax_pct": SNAPSHOT_FIELD_DEFAULTS["ytm_to_maturity_after_tax_pct"],
        "ytm_to_put_pct": SNAPSHOT_FIELD_DEFAULTS["ytm_to_put_pct"],
        "turnover_amount_wan": SNAPSHOT_FIELD_DEFAULTS["turnover_amount_wan"],
    }.items():
        _ensure_float_column(df, key, float(default))

    df["days_to_maturity"] = pd.to_numeric(df["days_to_maturity"], errors="coerce").fillna(0).astype(int).clip(lower=0)
    df["days_to_conversion_start"] = (
        pd.to_numeric(df["days_to_conversion_start"], errors="coerce").fillna(0).astype(int).clip(lower=0)
    )
    if "days_to_redeem" in df.columns:
        df["days_to_redeem"] = pd.to_numeric(df["days_to_redeem"], errors="coerce")

    _ensure_bool_column(df, "is_listed", True)
    _ensure_bool_column(df, "was_listed_prev_day", True)
    _ensure_bool_column(df, "is_redeem_triggered", False)

    for key in {
        "bond_name",
        "underlying_stock_code",
        "underlying_stock_name",
        "listing_date",
        "put_status",
        "redeem_status",
        "market",
        "rating",
        "data_source",
    }:
        df[key] = df[key].fillna(SNAPSHOT_FIELD_DEFAULTS[key]).astype(str).str.strip()

    invalid_ratio = df["bond_pure_value_ratio"].isna() | (df["bond_pure_value_ratio"] <= 0)
    derived_ratio = pd.Series(float("nan"), index=df.index, dtype="float64")
    positive_mask = df["pure_bond_value"] > 0
    derived_ratio.loc[positive_mask] = df.loc[positive_mask, "close_price"] / df.loc[positive_mask, "pure_bond_value"]
    df.loc[invalid_ratio, "bond_pure_value_ratio"] = derived_ratio.loc[invalid_ratio]
    df["bond_pure_value_ratio"] = pd.to_numeric(df["bond_pure_value_ratio"], errors="coerce").fillna(1.0)
    return df
