from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class TechnicalSnapshot:
    close: float
    high_52w: float | None
    low_52w: float | None
    position_52w: float | None
    ma20: float | None
    ma60: float | None
    ma120: float | None
    ma250: float | None
    atr14: float | None
    volatility20: float | None
    support_level: float | None
    resistance_level: float | None
    volume_price_low: float | None
    volume_price_high: float | None
    valuation_percentile: float | None


@dataclass(frozen=True)
class TargetRange:
    scenario: str
    horizon: str
    target_low: float | None
    target_high: float | None
    target_mid: float | None
    upside_pct_mid: float | None
    method: str
    confidence: str
    assumptions: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KeyLevel:
    level_id: str
    level_type: str
    level_low: float | None
    level_high: float | None
    strength: str
    distance_pct: float | None
    source: str
    note: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScenarioPath:
    path_id: str
    path_name: str
    probability: int
    confidence: str
    trigger: str
    target_scenario: str
    invalidation: str
    explanation: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceMap:
    posture: str
    posture_label: str
    confidence: str
    targets: list[TargetRange]
    key_levels: list[KeyLevel]
    scenario_paths: list[ScenarioPath]
    invalidation_rules: list[dict[str, Any]]
    evidence_refs: list[str]
    explanation: dict[str, str]


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _pct_distance(level: float | None, current: float | None) -> float | None:
    if level is None or current in (None, 0):
        return None
    return round((level - current) / current, 6)


def _as_decimal_growth(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if abs(value) > 1 else value


def _bounded_multiple(value: float | None, fallback: float, lower: float, upper: float) -> float:
    if value is None or value <= 0:
        return fallback
    return _clamp(value, lower, upper)


def _rolling_mean(values: list[float], window: int) -> float | None:
    if not values:
        return None
    return mean(values[-min(len(values), window) :])


def _rolling_high(rows: list[dict[str, Any]], window: int) -> float | None:
    recent = rows[-min(len(rows), window) :]
    values = [_safe_float(row.get("high")) or _safe_float(row.get("close")) for row in recent]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _rolling_low(rows: list[dict[str, Any]], window: int) -> float | None:
    recent = rows[-min(len(rows), window) :]
    values = [_safe_float(row.get("low")) or _safe_float(row.get("close")) for row in recent]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def _atr(rows: list[dict[str, Any]], window: int = 14) -> float | None:
    if not rows:
        return None
    recent = rows[-min(len(rows), window + 1) :]
    true_ranges: list[float] = []
    prev_close: float | None = None
    for row in recent:
        high = _safe_float(row.get("high"))
        low = _safe_float(row.get("low"))
        close = _safe_float(row.get("close"))
        if high is None or low is None:
            prev_close = close
            continue
        ranges = [high - low]
        if prev_close is not None:
            ranges.extend([abs(high - prev_close), abs(low - prev_close)])
        true_ranges.append(max(ranges))
        prev_close = close
    return mean(true_ranges[-window:]) if true_ranges else None


def _volatility(closes: list[float], window: int = 20) -> float | None:
    if len(closes) < 2:
        return None
    recent = closes[-min(len(closes), window + 1) :]
    returns = [
        (recent[idx] - recent[idx - 1]) / recent[idx - 1]
        for idx in range(1, len(recent))
        if recent[idx - 1] != 0
    ]
    if not returns:
        return None
    return pstdev(returns) * sqrt(252) if len(returns) > 1 else abs(returns[0]) * sqrt(252)


def _valuation_percentile(rows: list[dict[str, Any]]) -> float | None:
    latest = rows[-1] if rows else {}
    latest_pe = _safe_float(latest.get("pe_ttm"))
    latest_ps = _safe_float(latest.get("ps_ttm"))
    key = "pe_ttm" if latest_pe and latest_pe > 0 else "ps_ttm"
    latest_value = latest_pe if key == "pe_ttm" else latest_ps
    if latest_value is None or latest_value <= 0:
        return None
    values = [_safe_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None and value > 0]
    if len(values) < 3:
        return None
    below_or_equal = sum(1 for value in values if value <= latest_value)
    return round(below_or_equal / len(values), 4)


def build_technical_snapshot(price_rows: list[dict[str, Any]]) -> TechnicalSnapshot | None:
    rows = [row for row in price_rows if _safe_float(row.get("close")) is not None]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row.get("trade_date"))
    closes = [_safe_float(row.get("close")) for row in rows]
    closes = [value for value in closes if value is not None]
    current = closes[-1]
    high_52w = _rolling_high(rows, 252)
    low_52w = _rolling_low(rows, 252)
    position_52w = None
    if high_52w is not None and low_52w is not None and high_52w != low_52w:
        position_52w = _clamp((current - low_52w) / (high_52w - low_52w), 0.0, 1.0)

    ma20 = _rolling_mean(closes, 20)
    ma60 = _rolling_mean(closes, 60)
    ma120 = _rolling_mean(closes, 120)
    ma250 = _rolling_mean(closes, 250)
    atr14 = _atr(rows, 14)
    volatility20 = _volatility(closes, 20)
    recent_low = _rolling_low(rows, 60)
    recent_high = _rolling_high(rows, 60)
    support_candidates = [value for value in [recent_low, ma60, ma120] if value is not None and value < current]
    resistance_candidates = [value for value in [recent_high, ma20, ma60] if value is not None and value > current]
    support = max(support_candidates) if support_candidates else recent_low
    resistance = min(resistance_candidates) if resistance_candidates else recent_high
    vwap_values = [
        ((_safe_float(row.get("close")) or 0) * (_safe_float(row.get("volume")) or 0), _safe_float(row.get("volume")) or 0)
        for row in rows[-min(len(rows), 120) :]
    ]
    volume_sum = sum(volume for _weighted, volume in vwap_values)
    volume_price = sum(weighted for weighted, _volume in vwap_values) / volume_sum if volume_sum else current
    band = atr14 or current * 0.03

    return TechnicalSnapshot(
        close=_round(current) or current,
        high_52w=_round(high_52w),
        low_52w=_round(low_52w),
        position_52w=_round(position_52w, 4),
        ma20=_round(ma20),
        ma60=_round(ma60),
        ma120=_round(ma120),
        ma250=_round(ma250),
        atr14=_round(atr14),
        volatility20=_round(volatility20, 6),
        support_level=_round(support),
        resistance_level=_round(resistance),
        volume_price_low=_round(max(volume_price - band, 0.01)),
        volume_price_high=_round(volume_price + band),
        valuation_percentile=_valuation_percentile(rows),
    )


def _confidence(technical: TechnicalSnapshot, financial: dict[str, Any] | None) -> str:
    filled = 0
    filled += 1 if technical.high_52w is not None and technical.low_52w is not None else 0
    filled += 1 if technical.ma60 is not None else 0
    filled += 1 if technical.atr14 is not None else 0
    if financial:
        filled += 1 if _safe_float(financial.get("revenue_yoy")) is not None else 0
        filled += 1 if _safe_float(financial.get("shares_outstanding")) not in (None, 0) else 0
    if filled >= 5:
        return "high"
    if filled >= 3:
        return "medium"
    return "low"


def build_target_ranges(
    technical: TechnicalSnapshot,
    market_row: dict[str, Any],
    financial: dict[str, Any] | None,
    score_row: dict[str, Any] | None,
    option_summary: dict[str, Any] | None,
    estimate: dict[str, Any] | None,
    earnings_calendar: dict[str, Any] | None,
    evidence_refs: list[str],
) -> list[TargetRange]:
    current = technical.close
    revenue_yoy = _as_decimal_growth(_safe_float((financial or {}).get("revenue_yoy")))
    netprofit_yoy = _as_decimal_growth(_safe_float((financial or {}).get("netprofit_yoy")))
    growth_inputs = [value for value in [revenue_yoy, netprofit_yoy] if value is not None]
    growth = _clamp(mean(growth_inputs), -0.2, 0.8) if growth_inputs else 0.08
    score = _safe_float((score_row or {}).get("total_score")) or 50.0
    valuation_pct = technical.valuation_percentile
    option_quality_ok = (option_summary or {}).get("data_quality_flag") == "ok"
    flow_sentiment = (option_summary or {}).get("flow_sentiment")
    flow_score = _safe_float((option_summary or {}).get("flow_score")) if option_summary else None
    call_put_ratio = _safe_float((option_summary or {}).get("call_put_volume_ratio")) if option_summary else None
    crowding_penalty = 0.10 if valuation_pct is not None and valuation_pct >= 0.85 else 0.0
    if option_quality_ok and flow_sentiment == "bearish":
        crowding_penalty += 0.04
    if option_quality_ok and flow_sentiment == "bullish" and flow_score is not None:
        crowding_penalty -= 0.02
    score_bonus = (score - 50.0) / 100.0
    options_bonus = 0.0
    if option_quality_ok and call_put_ratio is not None:
        options_bonus = _clamp((call_put_ratio - 1.0) * 0.035, -0.05, 0.06)
    base_upside = _clamp(0.08 + growth * 0.35 + score_bonus * 0.25 + options_bonus - crowding_penalty, -0.08, 0.38)
    bull_upside = _clamp(base_upside + 0.12 + max(growth, 0) * 0.25, 0.08, 0.72)
    bear_downside = _clamp(0.10 + max(-growth, 0) * 0.4 + crowding_penalty, 0.06, 0.32)
    atr = technical.atr14 or current * 0.035
    band = max(atr, current * 0.025)
    method = "hybrid"
    estimate_method = None
    estimate_base_mid = None
    estimate_bull_mid = None
    estimate_bear_mid = None
    fy1_eps = _safe_float((estimate or {}).get("fy1_eps"))
    fy2_eps = _safe_float((estimate or {}).get("fy2_eps"))
    fy1_revenue = _safe_float((estimate or {}).get("fy1_revenue_estimate"))
    fy2_revenue = _safe_float((estimate or {}).get("fy2_revenue_estimate"))
    shares_outstanding = _safe_float((financial or {}).get("shares_outstanding"))
    pe_ttm = _safe_float(market_row.get("pe_ttm"))
    ps_ttm = _safe_float(market_row.get("ps_ttm"))
    estimate_quality_ok = (estimate or {}).get("data_quality_flag") == "ok"
    if estimate_quality_ok and fy1_eps is not None and fy1_eps > 0 and (fy2_eps is None or fy2_eps > 0):
        fair_pe = _bounded_multiple(pe_ttm, 28.0, 10.0, 65.0)
        base_pe = fair_pe * (1 + score_bonus * 0.25 - crowding_penalty * 0.5)
        bull_pe = fair_pe * (1.12 + max(growth, 0) * 0.25)
        bear_pe = fair_pe * (0.72 - min(crowding_penalty, 0.12))
        estimate_base_mid = fy1_eps * _clamp(base_pe, 8.0, 75.0)
        estimate_bull_mid = (fy2_eps or fy1_eps * (1 + max(growth, 0.02))) * _clamp(bull_pe, 10.0, 85.0)
        estimate_bear_mid = fy1_eps * _clamp(bear_pe, 6.0, 55.0)
        estimate_method = "analyst_eps_pe_hybrid"
    elif estimate_quality_ok and fy1_revenue is not None and fy1_revenue > 0 and shares_outstanding not in (None, 0):
        fair_ps = _bounded_multiple(ps_ttm, 8.0, 1.0, 35.0)
        estimate_base_mid = fy1_revenue * _clamp(fair_ps * (1 + score_bonus * 0.18 - crowding_penalty * 0.5), 0.8, 40.0) / shares_outstanding
        estimate_bull_mid = (fy2_revenue or fy1_revenue * (1 + max(growth, 0.03))) * _clamp(fair_ps * 1.18, 1.0, 50.0) / shares_outstanding
        estimate_bear_mid = fy1_revenue * _clamp(fair_ps * 0.72, 0.5, 28.0) / shares_outstanding
        estimate_method = "analyst_revenue_ps_hybrid"
    if _safe_float(market_row.get("pe_ttm")) and _safe_float(market_row.get("pe_ttm")) > 0:
        method = "pe_eps_hybrid"
    elif _safe_float(market_row.get("ps_ttm")) and _safe_float(market_row.get("ps_ttm")) > 0:
        method = "ps_revenue_hybrid"
    if estimate_method is not None:
        method = estimate_method

    confidence = _confidence(technical, financial)
    if estimate_quality_ok and confidence == "low":
        confidence = "medium"

    def _range(scenario: str, mid: float, width: float) -> TargetRange:
        return TargetRange(
            scenario=scenario,
            horizon="3-6m",
            target_low=_round(max(mid - width, 0.01)),
            target_high=_round(max(mid + width, 0.01)),
            target_mid=_round(mid),
            upside_pct_mid=_round((mid - current) / current, 6) if current else None,
            method=method,
            confidence=confidence,
            assumptions={
                "current_price": current,
                "growth_rate_used": round(growth, 4),
                "score_used": round(score, 2),
                "valuation_percentile": valuation_pct,
                "option_flow_sentiment": flow_sentiment,
                "call_put_volume_ratio": call_put_ratio,
                "fy1_eps": fy1_eps,
                "fy2_eps": fy2_eps,
                "fy1_revenue_estimate": fy1_revenue,
                "fy2_revenue_estimate": fy2_revenue,
                "fy1_analyst_count": _safe_float((estimate or {}).get("fy1_analyst_count")),
                "fy2_analyst_count": _safe_float((estimate or {}).get("fy2_analyst_count")),
                "next_earnings_date": (earnings_calendar or {}).get("next_earnings_date"),
                "days_to_earnings": _safe_float((earnings_calendar or {}).get("days_to_earnings")),
            },
            evidence_refs=evidence_refs,
        )

    base_mid = current * (1 + base_upside)
    bull_mid = current * (1 + bull_upside)
    technical_bear = min(value for value in [technical.support_level, current * (1 - bear_downside)] if value is not None)
    if estimate_base_mid is not None:
        base_mid = mean([base_mid, estimate_base_mid])
    if estimate_bull_mid is not None:
        bull_mid = max(mean([bull_mid, estimate_bull_mid]), base_mid * 1.03)
    if estimate_bear_mid is not None:
        technical_bear = min(mean([technical_bear, estimate_bear_mid]), current * 0.98)
    return [
        _range("bear", technical_bear, band * 0.65),
        _range("base", base_mid, band),
        _range("bull", bull_mid, band * 1.15),
    ]


def _target(targets: list[TargetRange], scenario: str) -> TargetRange:
    return next(item for item in targets if item.scenario == scenario)


def build_key_levels(
    technical: TechnicalSnapshot,
    targets: list[TargetRange],
    option_summary: dict[str, Any] | None,
    evidence_refs: list[str],
) -> list[KeyLevel]:
    current = technical.close
    levels = [
        ("current_price", current, current, "high", "market_close", "当前价格"),
        ("support", technical.support_level, technical.support_level, "medium", "technical", "近 60 日低点 / 均线形成的支撑参考"),
        ("resistance", technical.resistance_level, technical.resistance_level, "medium", "technical", "近 60 日高点 / 均线形成的阻力参考"),
        ("bear_risk_zone", _target(targets, "bear").target_low, _target(targets, "bear").target_high, "medium", "target_range", "Bear 情景风险区"),
        ("base_target_zone", _target(targets, "base").target_low, _target(targets, "base").target_high, "medium", "target_range", "Base 情景目标区"),
        ("bull_target_zone", _target(targets, "bull").target_low, _target(targets, "bull").target_high, "low", "target_range", "Bull 情景目标区"),
    ]
    result: list[KeyLevel] = []
    for level_type, low, high, strength, source, note in levels:
        if low is None and high is None:
            continue
        mid = mean([value for value in [low, high] if value is not None])
        result.append(
            KeyLevel(
                level_id=str(uuid4()),
                level_type=level_type,
                level_low=_round(low),
                level_high=_round(high),
                strength=strength,
                distance_pct=_pct_distance(mid, current),
                source=source,
                note=note,
                evidence_refs=evidence_refs if level_type.endswith("_zone") else [],
            )
        )
    if option_summary and option_summary.get("data_quality_flag") == "ok":
        max_pain = _safe_float(option_summary.get("max_pain_strike"))
        if max_pain is not None:
            result.append(
                KeyLevel(
                    level_id=str(uuid4()),
                    level_type="max_pain",
                    level_low=_round(max_pain),
                    level_high=_round(max_pain),
                    strength="medium",
                    distance_pct=_pct_distance(max_pain, current),
                    source="options_chain",
                    note="期权 Max Pain 参考位",
                    evidence_refs=[],
                )
            )
        oi_ratio = _safe_float(option_summary.get("call_put_open_interest_ratio"))
        if oi_ratio is not None:
            result.append(
                KeyLevel(
                    level_id=str(uuid4()),
                    level_type="options_flow_bias",
                    level_low=None,
                    level_high=None,
                    strength="medium" if option_summary.get("flow_sentiment") != "unknown" else "low",
                    distance_pct=None,
                    source="options_chain",
                    note=f"期权流向 {option_summary.get('flow_sentiment')}，Call/Put OI 比 {oi_ratio:.2f}",
                    evidence_refs=[],
                )
            )
    return result


def build_invalidation_rules(
    technical: TechnicalSnapshot,
    financial: dict[str, Any] | None,
    evidence_refs: list[str],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if technical.support_level is not None:
        rules.append(
            {
                "kind": "price_structure",
                "label": "跌破关键支撑",
                "metric": "close",
                "threshold": technical.support_level,
                "severity": "high",
                "note": "收盘价跌破支撑区后，需要重新评估 Bear 情景。",
                "evidence_refs": [],
            }
        )
    revenue_yoy = _as_decimal_growth(_safe_float((financial or {}).get("revenue_yoy")))
    if revenue_yoy is not None:
        rules.append(
            {
                "kind": "fundamental",
                "label": "营收增速显著走弱",
                "metric": "revenue_yoy",
                "threshold": round(max(revenue_yoy * 0.55, 0.0), 4),
                "severity": "medium",
                "note": "下一期营收增速低于当前增速的一半时，下修目标区间。",
                "evidence_refs": evidence_refs,
            }
        )
    if technical.valuation_percentile is not None:
        rules.append(
            {
                "kind": "valuation",
                "label": "估值进入拥挤区",
                "metric": "valuation_percentile",
                "threshold": 0.9,
                "severity": "medium",
                "note": "估值分位过高时，目标区间置信度下降。",
                "evidence_refs": evidence_refs,
            }
        )
    return rules


def build_scenario_paths(
    technical: TechnicalSnapshot,
    targets: list[TargetRange],
    confidence: str,
    option_summary: dict[str, Any] | None = None,
) -> list[ScenarioPath]:
    current = technical.close
    base = _target(targets, "base")
    bull = _target(targets, "bull")
    bear = _target(targets, "bear")
    position = technical.position_52w if technical.position_52w is not None else 0.5
    crowded = position >= 0.85 or (technical.valuation_percentile is not None and technical.valuation_percentile >= 0.85)
    breakthrough_prob = 35 if not crowded else 25
    wait_prob = 40 if not crowded else 35
    if option_summary and option_summary.get("data_quality_flag") == "ok":
        if option_summary.get("flow_sentiment") == "bullish":
            breakthrough_prob += 15
            wait_prob -= 3
        elif option_summary.get("flow_sentiment") == "bearish":
            breakthrough_prob -= 8
            wait_prob -= 2
        elif option_summary.get("flow_sentiment") == "neutral":
            wait_prob += 5
        breakthrough_prob = int(_clamp(breakthrough_prob, 15, 55))
        wait_prob = int(_clamp(wait_prob, 20, 55))
    bear_prob = max(100 - breakthrough_prob - wait_prob, 20)
    return [
        ScenarioPath(
            path_id=str(uuid4()),
            path_name="突破上修",
            probability=breakthrough_prob,
            confidence=confidence,
            trigger=f"放量突破阻力区 {technical.resistance_level:.2f}" if technical.resistance_level else "突破近期阻力并获得财务或事件验证",
            target_scenario="bull",
            invalidation=f"回落至 Base 区间下沿 {base.target_low:.2f}" if base.target_low else "回落至 Base 区间下沿",
            explanation=f"若基本面继续兑现，价格有机会向 Bull 区间 {bull.target_low:.2f}-{bull.target_high:.2f} 演化。",
        ),
        ScenarioPath(
            path_id=str(uuid4()),
            path_name="震荡等待",
            probability=wait_prob,
            confidence=confidence,
            trigger="价格位于支撑与阻力之间，等待下一份财报或事件证据",
            target_scenario="base",
            invalidation="财务或事件证据明显转弱",
            explanation=f"当前更适合围绕 Base 区间 {base.target_low:.2f}-{base.target_high:.2f} 复核赔率。",
        ),
        ScenarioPath(
            path_id=str(uuid4()),
            path_name="回撤重估",
            probability=bear_prob,
            confidence=confidence,
            trigger=f"跌破支撑区 {technical.support_level:.2f}" if technical.support_level else "跌破关键趋势结构",
            target_scenario="bear",
            invalidation="重新站回支撑区并出现正向证据",
            explanation=f"若价格进入 Bear 区间 {bear.target_low:.2f}-{bear.target_high:.2f}，应优先检查原研究假设是否受损。",
        ),
    ]


def build_price_map(
    technical: TechnicalSnapshot,
    market_row: dict[str, Any],
    financial: dict[str, Any] | None,
    score_row: dict[str, Any] | None,
    option_summary: dict[str, Any] | None = None,
    estimate: dict[str, Any] | None = None,
    earnings_calendar: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
) -> PriceMap:
    refs = evidence_refs or []
    targets = build_target_ranges(technical, market_row, financial, score_row, option_summary, estimate, earnings_calendar, refs)
    base = _target(targets, "base")
    bull = _target(targets, "bull")
    bear = _target(targets, "bear")
    current = technical.close
    confidence = _confidence(technical, financial)

    if bear.target_low is not None and current <= bear.target_high:
        posture, label = "high_risk", "高风险区"
    elif bull.target_low is not None and current >= bull.target_low:
        posture, label = "crowded", "估值拥挤"
    elif base.target_low is not None and current >= base.target_low:
        posture, label = "near_base_target", "接近目标区"
    elif technical.position_52w is not None and technical.position_52w <= 0.35 and confidence == "low":
        posture, label = "low_position_unverified", "低位待验证"
    else:
        posture, label = "reasonable_strong", "合理偏强"

    option_quality_ok = (option_summary or {}).get("data_quality_flag") == "ok"
    if confidence == "low" and option_quality_ok:
        confidence = "medium"
    key_levels = build_key_levels(technical, targets, option_summary, refs)
    invalidation_rules = build_invalidation_rules(technical, financial, refs)
    scenario_paths = build_scenario_paths(technical, targets, confidence, option_summary)
    explanation = {
        "posture": f"当前价格姿态为{label}，置信度为 {confidence}。",
        "base": f"Base 区间 {base.target_low:.2f}-{base.target_high:.2f}，来自价格结构、成长速度和估值状态的混合估计。",
        "bull": f"Bull 区间需要突破阻力并获得财务或事件证据支持，上沿参考 {bull.target_high:.2f}。",
        "bear": f"Bear 区间 {bear.target_low:.2f}-{bear.target_high:.2f} 是优先复核研究假设的风险区。",
        "next_watch": "下一步重点观察财报兑现、估值拥挤度和关键支撑/阻力是否被有效突破。",
    }
    if option_summary and option_summary.get("data_quality_flag") == "ok":
        explanation["options"] = (
            f"期权链流向为 {option_summary.get('flow_sentiment')}，"
            f"流动性分 {option_summary.get('liquidity_score')}，"
            f"Max Pain {option_summary.get('max_pain_strike') or 'N/A'}。"
        )
    if estimate and estimate.get("data_quality_flag") == "ok":
        explanation["estimates"] = (
            f"一致预期已接入：FY1 EPS {estimate.get('fy1_eps') or 'N/A'}，"
            f"FY2 EPS {estimate.get('fy2_eps') or 'N/A'}，"
            f"FY1/FY2 营收预期 {estimate.get('fy1_revenue_estimate') or 'N/A'} / {estimate.get('fy2_revenue_estimate') or 'N/A'}。"
        )
    if earnings_calendar and earnings_calendar.get("data_quality_flag") in {"ok", "partial"}:
        explanation["earnings"] = (
            f"下一财报日 {earnings_calendar.get('next_earnings_date') or 'N/A'}，"
            f"距今 {earnings_calendar.get('days_to_earnings') if earnings_calendar.get('days_to_earnings') is not None else 'N/A'} 天。"
        )
    return PriceMap(
        posture=posture,
        posture_label=label,
        confidence=confidence,
        targets=targets,
        key_levels=key_levels,
        scenario_paths=scenario_paths,
        invalidation_rules=invalidation_rules,
        evidence_refs=refs,
        explanation=explanation,
    )
