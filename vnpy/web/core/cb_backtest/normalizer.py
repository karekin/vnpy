"""可转债市场快照归一化逻辑。

这个模块的职责比较单一，但很关键：
1. 接住来自快照库、接口层或历史回放数据中的脏值/缺失值。
2. 把字段类型统一成后续筛债、打分模块可以稳定消费的格式。
3. 在部分关键字段缺失或异常时，用已有字段推导出一个可接受的兜底值。

之所以把这层“归一化”独立出来，是因为后续策略核心希望面对的是
“字段齐全、类型稳定、极端值已处理”的 DataFrame，而不是到处判断空值和字符串。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS


def _safe_float(value: Any, default: float = 0.0) -> float:
    """把任意输入尽量安全地转成 float。

    这里主要服务于“外部输入不完全可信”的场景：
    - `None`、空字符串等明显无值的输入，直接回退到默认值。
    - 其它值尝试走 `float(...)` 转换。
    - 一旦转换失败，不抛异常，统一返回默认值。
    """
    try:
        # `None` 代表明确缺失，直接使用调用方给出的默认值。
        if value is None:
            return default
        # 有些数据源会把缺失值写成空字符串或纯空白字符串，这里同样视为无效值。
        if isinstance(value, str) and not value.strip():
            return default
        # 对数字字符串、整数、浮点数等常见输入做统一转换。
        return float(value)
    except Exception:
        # 归一化阶段优先保证流程不中断，失败时返回兜底值而不是向外抛错。
        return default


def _ensure_float_column(frame: pd.DataFrame, column: str, default: float) -> None:
    """确保目标列存在且内容为浮点数列。"""
    # 如果整列缺失，就直接补一列默认值，保证后续访问该列不会报错。
    if column not in frame.columns:
        frame[column] = default
        return
    # 已存在的列统一做数值转换；非法值转为 NaN，再用默认值补齐。
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _ensure_bool_column(frame: pd.DataFrame, column: str, default: bool) -> None:
    """确保目标列存在且内容为布尔值列。"""
    # 缺列时先整体补默认布尔值。
    if column not in frame.columns:
        frame[column] = default
    # 兼容多种布尔表达方式：
    # - 原生 bool 直接保留语义
    # - 字符串则接受 1/true/t/yes/y 等常见真值写法
    frame[column] = frame[column].apply(lambda value: bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "t", "yes", "y"})


def normalize_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """把快照库中的行数据统一归一化成策略核心可直接消费的格式。

    处理目标包括：
    - 保证关键列存在。
    - 把价格、收益率、规模等字段统一转成数值。
    - 把若干状态字段统一转成布尔值或字符串。
    - 在纯债价值比缺失/异常时，利用债价和纯债价值做一次兜底推导。
    """
    # 空表直接原样返回，避免后续对列的访问触发异常。
    if frame.empty:
        return frame

    # 使用副本进行处理，避免调用方传入的原始 DataFrame 被原地修改。
    df = frame.copy()
    # `bond_code` 是后续索引和标识债券的核心字段；如果连它都没有，就无法继续标准化。
    if "bond_code" not in df.columns:
        return df

    # 债券代码统一转成去空白后的字符串，减少“数值代码”和“带空格字符串代码”混用问题。
    df["bond_code"] = df["bond_code"].astype(str).str.strip()
    # 若当前索引还不是债券代码，则用 `bond_code` 建立索引，便于后续按债券定位。
    if df.index.name != "bond_code":
        df = df.set_index("bond_code", drop=False)

    # 先根据快照 schema 的默认值补齐所有已知字段。
    # 这一步的目标是“列要先齐”，之后再做更细的类型归一化。
    for key, default in SNAPSHOT_FIELD_DEFAULTS.items():
        if key not in df.columns:
            df[key] = default

    # 以下字段都要求走数值化清洗。
    # 即使上一步已经补了默认值，这里仍统一做一次 `to_numeric`，
    # 以处理原始数据里可能混入的字符串、空串、非法字符等情况。
    for key, default in {
        "close_price": SNAPSHOT_FIELD_DEFAULTS["close_price"],
        "open_price": SNAPSHOT_FIELD_DEFAULTS["open_price"],
        "high_price": SNAPSHOT_FIELD_DEFAULTS["high_price"],
        "low_price": SNAPSHOT_FIELD_DEFAULTS["low_price"],
        "pre_close_price": SNAPSHOT_FIELD_DEFAULTS["pre_close_price"],
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
        "volume_hand": SNAPSHOT_FIELD_DEFAULTS["volume_hand"],
        "turnover_amount_wan": SNAPSHOT_FIELD_DEFAULTS["turnover_amount_wan"],
        "turnover_rate_pct": SNAPSHOT_FIELD_DEFAULTS["turnover_rate_pct"],
        "issue_size_yi": SNAPSHOT_FIELD_DEFAULTS["issue_size_yi"],
        "limit_status": SNAPSHOT_FIELD_DEFAULTS["limit_status"],
    }.items():
        # 每列都按“缺列补默认值，已有列强转数值”的规则处理。
        _ensure_float_column(df, key, float(default))

    # 这些字段在业务上是“天数”，因此除了转数值外，还要进一步：
    # 1. 空值补 0
    # 2. 转整数
    # 3. 不允许出现负天数
    df["days_to_maturity"] = pd.to_numeric(df["days_to_maturity"], errors="coerce").fillna(0).astype(int).clip(lower=0)
    df["days_to_conversion_start"] = (
        pd.to_numeric(df["days_to_conversion_start"], errors="coerce").fillna(0).astype(int).clip(lower=0)
    )
    # `days_to_redeem` 只在存在该列时做数值化；
    # 这里不补默认值，保留 NaN 语义给后续过滤逻辑决定是否跳过。
    if "days_to_redeem" in df.columns:
        df["days_to_redeem"] = pd.to_numeric(df["days_to_redeem"], errors="coerce")

    # 上市状态、前一日是否已上市、是否触发强赎，这几列都统一成显式布尔值。
    _ensure_bool_column(df, "is_listed", True)
    _ensure_bool_column(df, "was_listed_prev_day", True)
    _ensure_bool_column(df, "is_redeem_triggered", False)
    if "is_tradeable" in df.columns:
        _ensure_bool_column(df, "is_tradeable", False)
    else:
        df["is_tradeable"] = (
            (df["close_price"] > 0)
            & ((df["volume_hand"] > 0) | (df["turnover_amount_wan"] > 0))
        )

    # 文本类字段统一做三件事：
    # 1. 缺失值补 schema 默认值
    # 2. 转成字符串，避免后续 `str.contains` 等操作报错
    # 3. 去掉首尾空白，减少脏数据差异
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

    # 纯债价值比是后续筛债逻辑依赖的重要字段。
    # 当该字段缺失、为 NaN 或小于等于 0 时，视为无效值，需要尝试重新推导。
    invalid_ratio = df["bond_pure_value_ratio"].isna() | (df["bond_pure_value_ratio"] <= 0)
    # 先创建一列全 NaN 的推导结果，只在满足条件的行上写入真实值。
    derived_ratio = pd.Series(float("nan"), index=df.index, dtype="float64")
    # 只有纯债价值大于 0 时，`close_price / pure_bond_value` 才有可解释意义。
    positive_mask = df["pure_bond_value"] > 0
    # 用“债券现价 / 纯债价值”估算债性溢价倍数，作为兜底的纯债价值比。
    derived_ratio.loc[positive_mask] = df.loc[positive_mask, "close_price"] / df.loc[positive_mask, "pure_bond_value"]
    # 仅覆盖原本无效的记录，避免误伤已有的有效值。
    df.loc[invalid_ratio, "bond_pure_value_ratio"] = derived_ratio.loc[invalid_ratio]
    # 最后再统一做一次数值化和缺失补齐，确保该列对下游来说始终可用。
    df["bond_pure_value_ratio"] = pd.to_numeric(df["bond_pure_value_ratio"], errors="coerce").fillna(1.0)
    # 返回归一化后的新 DataFrame，供后续筛债和打分模块直接使用。
    return df
