from __future__ import annotations

import json
import re
from json import JSONDecodeError
from typing import Any
from uuid import uuid4

from .price_map import KeyLevel, PriceMap, ScenarioPath, TargetRange, TechnicalSnapshot


ALLOWED_CONFIDENCE = {"low", "medium", "high"}
TARGET_SCENARIOS = ("bear", "base", "bull")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty DeerFlow price map response")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else stripped
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end < start:
            raise ValueError("DeerFlow price map response does not contain a JSON object")
        candidate = candidate[start : end + 1]

    try:
        payload = json.loads(candidate)
    except JSONDecodeError:
        repaired = candidate
        for key in ("level_type", "name", "kind", "label", "metric", "scenario", "path_name"):
            repaired = repaired.replace('},"' + key + '"', '},{"' + key + '"')
        payload = json.loads(repaired)
    if not isinstance(payload, dict):
        raise ValueError("DeerFlow price map JSON response must be an object")
    return payload


def extract_latest_ai_content_from_history(history: list[dict[str, Any]]) -> str | None:
    for checkpoint in history:
        values = checkpoint.get("values") if isinstance(checkpoint, dict) else None
        messages = None
        if isinstance(values, dict):
            messages = values.get("messages")
        if messages is None and isinstance(checkpoint, dict):
            messages = checkpoint.get("messages")
        if not isinstance(messages, list):
            continue
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("type") != "ai":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [
                    str(part.get("text")).strip()
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text" and str(part.get("text") or "").strip()
                ]
                if parts:
                    return "\n".join(parts)
    return None


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _confidence(value: Any, fallback: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_CONFIDENCE else fallback


def _target_payload(target: TargetRange) -> dict[str, Any]:
    return {
        "scenario": target.scenario,
        "horizon": target.horizon,
        "low": target.target_low,
        "high": target.target_high,
        "mid": target.target_mid,
        "upside_pct_mid": target.upside_pct_mid,
        "method": target.method,
        "confidence": target.confidence,
        "assumptions": target.assumptions,
        "evidence_refs": target.evidence_refs,
    }


def _key_level_payload(level: KeyLevel) -> dict[str, Any]:
    return {
        "level_type": level.level_type,
        "low": level.level_low,
        "high": level.level_high,
        "strength": level.strength,
        "distance_pct": level.distance_pct,
        "source": level.source,
        "note": level.note,
        "evidence_refs": level.evidence_refs,
    }


def _scenario_path_payload(path: ScenarioPath) -> dict[str, Any]:
    return {
        "name": path.path_name,
        "probability": path.probability,
        "confidence": path.confidence,
        "trigger": path.trigger,
        "target_scenario": path.target_scenario,
        "invalidation": path.invalidation,
        "explanation": path.explanation,
        "evidence_refs": path.evidence_refs,
    }


def _baseline_payload(price_map: PriceMap) -> dict[str, Any]:
    targets = {target.scenario: _target_payload(target) for target in price_map.targets}
    return {
        "posture": price_map.posture,
        "posture_label": price_map.posture_label,
        "confidence": price_map.confidence,
        "base_target": targets["base"],
        "bull_target": targets["bull"],
        "bear_zone": targets["bear"],
        "key_levels": [_key_level_payload(level) for level in price_map.key_levels],
        "scenario_paths": [_scenario_path_payload(path) for path in price_map.scenario_paths],
        "invalidation_rules": price_map.invalidation_rules,
        "evidence_refs": price_map.evidence_refs,
        "explanation": price_map.explanation,
    }


def _target_from_payload(
    *,
    scenario: str,
    payload: dict[str, Any],
    fallback: TargetRange,
    current_price: float,
    evidence_refs: list[str],
) -> TargetRange:
    low = _safe_float(payload.get("low", payload.get("target_low")))
    high = _safe_float(payload.get("high", payload.get("target_high")))
    mid = _safe_float(payload.get("mid", payload.get("target_mid")))
    if mid is None:
        values = [value for value in (low, high) if value is not None]
        mid = sum(values) / len(values) if values else fallback.target_mid
    if low is None:
        low = fallback.target_low
    if high is None:
        high = fallback.target_high
    upside = _safe_float(payload.get("upside_pct_mid"))
    if upside is None and mid is not None and current_price:
        upside = (mid - current_price) / current_price
    assumptions = payload.get("assumptions")
    if isinstance(assumptions, dict):
        assumptions = dict(assumptions)
    elif assumptions in (None, ""):
        assumptions = dict(fallback.assumptions)
    else:
        assumptions = {**dict(fallback.assumptions), "deerflow_note": str(assumptions)}
    refs = payload.get("evidence_refs")
    refs = [str(item) for item in refs] if isinstance(refs, list) else evidence_refs
    source_method = str(payload.get("method") or "").strip()
    if source_method and source_method != "deerflow_price_analysis":
        assumptions["deerflow_source_method"] = source_method

    return TargetRange(
        scenario=scenario,
        horizon=str(payload.get("horizon") or fallback.horizon or "3-6m"),
        target_low=_round(low),
        target_high=_round(high),
        target_mid=_round(mid),
        upside_pct_mid=_round(upside, 6),
        method="deerflow_price_analysis",
        confidence=_confidence(payload.get("confidence"), fallback.confidence),
        assumptions=assumptions,
        evidence_refs=refs,
    )


def _build_targets(payload: dict[str, Any], fallback: PriceMap, current_price: float, evidence_refs: list[str]) -> list[TargetRange]:
    fallback_by_scenario = {target.scenario: target for target in fallback.targets}
    payload_by_scenario = {
        "bear": payload.get("bear_zone") or payload.get("bear_target"),
        "base": payload.get("base_target"),
        "bull": payload.get("bull_target"),
    }
    targets: list[TargetRange] = []
    for scenario in TARGET_SCENARIOS:
        item = payload_by_scenario.get(scenario)
        item = item if isinstance(item, dict) else {}
        targets.append(
            _target_from_payload(
                scenario=scenario,
                payload=item,
                fallback=fallback_by_scenario[scenario],
                current_price=current_price,
                evidence_refs=evidence_refs,
            )
        )
    return targets


def _build_key_levels(payload: dict[str, Any], fallback: PriceMap, evidence_refs: list[str]) -> list[KeyLevel]:
    rows = payload.get("key_levels")
    if not isinstance(rows, list):
        return fallback.key_levels
    levels: list[KeyLevel] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        level_type = str(row.get("level_type") or row.get("type") or "").strip()
        if not level_type:
            continue
        refs = row.get("evidence_refs")
        refs = [str(item) for item in refs] if isinstance(refs, list) else evidence_refs
        levels.append(
            KeyLevel(
                level_id=str(row.get("level_id") or uuid4()),
                level_type=level_type,
                level_low=_round(_safe_float(row.get("low", row.get("level_low")))),
                level_high=_round(_safe_float(row.get("high", row.get("level_high")))),
                strength=str(row.get("strength") or "medium"),
                distance_pct=_round(_safe_float(row.get("distance_pct")), 6),
                source=str(row.get("source") or "deerflow"),
                note=str(row.get("note") or row.get("label") or level_type),
                evidence_refs=refs,
            )
        )
    return levels or fallback.key_levels


def _build_scenario_paths(payload: dict[str, Any], fallback: PriceMap, evidence_refs: list[str]) -> list[ScenarioPath]:
    rows = payload.get("scenario_paths")
    if not isinstance(rows, list):
        return fallback.scenario_paths
    paths: list[ScenarioPath] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("path_name") or "").strip()
        if not name:
            continue
        refs = row.get("evidence_refs")
        refs = [str(item) for item in refs] if isinstance(refs, list) else evidence_refs
        paths.append(
            ScenarioPath(
                path_id=str(row.get("path_id") or uuid4()),
                path_name=name,
                probability=max(0, min(100, _safe_int(row.get("probability"), 0))),
                confidence=_confidence(row.get("confidence"), fallback.confidence),
                trigger=str(row.get("trigger") or "等待价格与基本面确认"),
                target_scenario=str(row.get("target_scenario") or "base"),
                invalidation=str(row.get("invalidation") or "关键假设失效"),
                explanation=str(row.get("explanation") or ""),
                evidence_refs=refs,
            )
        )
    return paths or fallback.scenario_paths


def build_deerflow_price_map_prompt(
    *,
    market: str,
    symbol: str,
    trade_date: Any,
    technical: TechnicalSnapshot,
    market_row: dict[str, Any],
    financial: dict[str, Any] | None,
    score_row: dict[str, Any] | None,
    option_summary: dict[str, Any] | None,
    estimate: dict[str, Any] | None,
    earnings_calendar: dict[str, Any] | None,
    evidence_refs: list[str],
    baseline: PriceMap,
) -> str:
    context = {
        "task_type": "tenx_price_map_analysis",
        "market": market,
        "symbol": symbol,
        "trade_date": str(trade_date),
        "current_price": technical.close,
        "technical": technical.__dict__,
        "market_row": market_row,
        "financial": financial or {},
        "score": score_row or {},
        "option_summary": option_summary or {},
        "estimate": estimate or {},
        "earnings_calendar": earnings_calendar or {},
        "evidence_refs": evidence_refs,
        "baseline_price_map": _baseline_payload(baseline),
    }
    schema = {
        "posture": "reasonable_strong | near_base_target | crowded | high_risk | low_position_unverified",
        "posture_label": "中文短标签",
        "confidence": "low | medium | high",
        "base_target": "TargetRange object",
        "bull_target": "TargetRange object",
        "bear_zone": "TargetRange object",
        "key_levels": ["KeyLevel objects"],
        "scenario_paths": ["ScenarioPath objects, probabilities sum roughly to 100"],
        "invalidation_rules": ["objects"],
        "evidence_refs": ["strings"],
        "explanation": {"posture": "中文解释", "base": "中文解释", "bull": "中文解释", "bear": "中文解释", "next_watch": "中文解释"},
    }
    return (
        "你是 TenX Hunter 的价格地图分析器。请基于输入数据完成价格解析，输出可直接入库的 JSON。\n"
        "要求：\n"
        "1. 只返回一个 JSON object，不要 Markdown，不要解释性前后缀。\n"
        "2. 必须给出 base_target、bull_target、bear_zone 三个区间；每个区间包含 low/high/mid/upside_pct_mid/method/confidence/assumptions/evidence_refs。\n"
        "3. method 优先使用 deerflow_price_analysis；如果沿用一致预期或期权结构，请在 assumptions 里说明。\n"
        "4. key_levels 至少包含 current_price、support 或 risk zone、base target zone。\n"
        "5. scenario_paths 给出 2-4 条路径，概率为整数。\n"
        "6. 不要编造不存在的数据源；不确定时降低 confidence，并在 explanation.next_watch 里说明需要补充的证据。\n\n"
        f"输出 schema 示例：{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"输入数据：{json.dumps(context, ensure_ascii=False, default=str)}"
    )


def price_map_from_deerflow_payload(
    *,
    fallback: PriceMap,
    payload: dict[str, Any],
    current_price: float,
    deerflow_thread_id: str | None,
) -> PriceMap:
    evidence_refs = payload.get("evidence_refs")
    refs = [str(item) for item in evidence_refs] if isinstance(evidence_refs, list) else list(fallback.evidence_refs)
    if deerflow_thread_id:
        refs = [*refs, f"deerflow:{deerflow_thread_id}"]
    targets = _build_targets(payload, fallback, current_price, refs)
    key_levels = _build_key_levels(payload, fallback, refs)
    scenario_paths = _build_scenario_paths(payload, fallback, refs)
    invalidation_rules = payload.get("invalidation_rules")
    if not isinstance(invalidation_rules, list):
        invalidation_rules = fallback.invalidation_rules
    explanation = payload.get("explanation")
    if not isinstance(explanation, dict):
        explanation = dict(fallback.explanation)
    explanation = {str(key): str(value) for key, value in explanation.items()}
    explanation["deerflow"] = f"价格解析由 DeerFlow 完成，thread_id={deerflow_thread_id or 'unknown'}。"

    return PriceMap(
        posture=str(payload.get("posture") or fallback.posture),
        posture_label=str(payload.get("posture_label") or fallback.posture_label),
        confidence=_confidence(payload.get("confidence"), fallback.confidence),
        targets=targets,
        key_levels=key_levels,
        scenario_paths=scenario_paths,
        invalidation_rules=invalidation_rules,
        evidence_refs=refs,
        explanation=explanation,
    )
