"""期权策略 DeerFlow Agent — 数据收集 → Prompt 构建 → 响应解析

复用 price_map_deerflow.py 的模式，为大模型提供完整上下文，
让其输出结构化的期权策略分析结论。
"""
from __future__ import annotations

import json
import math
import re
from json import JSONDecodeError
from typing import Any


# ── JSON 提取 ──


def extract_strategy_json(text: str) -> dict[str, Any]:
    """从 DeerFlow 响应中提取 JSON object，兼容 markdown code fence。"""
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty DeerFlow option strategy response")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else stripped
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end < start:
            raise ValueError("DeerFlow response does not contain a JSON object")
        candidate = candidate[start:end + 1]

    try:
        payload = json.loads(candidate)
    except JSONDecodeError:
        # 简单修复：尾部逗号
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        payload = json.loads(repaired)
    if not isinstance(payload, dict):
        raise ValueError("DeerFlow option strategy JSON must be an object")
    return payload


# ── Prompt 构建 ──

ALLOWED_RECOMMENDATIONS = {"strong_buy", "buy", "hold", "avoid", "strong_avoid"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_POSTURES = {"bullish_trending", "range_bound", "bearish", "volatile_breakout"}


def build_option_strategy_prompt(
    *,
    symbol: str,
    market: str,
    underlying_price: float,
    option_summary: dict[str, Any] | None,
    price_history_30d: list[dict[str, Any]],
    earnings_calendar: dict[str, Any] | None,
    score_row: dict[str, Any] | None,
    backtest_results: list[dict[str, Any]],
    current_iv: float | None,
) -> str:
    """构建发给 DeerFlow 的期权策略综合分析 prompt。

    Parameters
    ----------
    symbol : 标的代码
    underlying_price : 当前标的价格
    option_summary : 期权摘要（来自 security_option_chain_summary_daily）
    price_history_30d : 近 30 天日线 [{trade_date, close, volume}]
    earnings_calendar : 财报日历信息
    score_row : 评分数据
    backtest_results : 数值回测结果（来自 strategy_backtest.py）
    current_iv : 当前 IV
    """

    # 价格走势摘要
    if len(price_history_30d) >= 2:
        first_close = price_history_30d[0].get("close", underlying_price)
        last_close = price_history_30d[-1].get("close", underlying_price)
        price_change_pct = (last_close - first_close) / first_close * 100 if first_close else 0
        high_30d = max(r.get("close", 0) for r in price_history_30d)
        low_30d = min(r.get("close", 999999) for r in price_history_30d)
        trend_desc = f"30日变动 {price_change_pct:+.1f}%，区间 [{low_30d:.1f}, {high_30d:.1f}]"
    else:
        trend_desc = "数据不足"

    # IV 水平判断
    iv = current_iv or 0.40
    iv_pct = iv * 100
    if iv_pct > 50:
        iv_level = "极高"
    elif iv_pct > 40:
        iv_level = "偏高"
    elif iv_pct > 25:
        iv_level = "适中"
    else:
        iv_level = "偏低"

    # 回测摘要
    bt_lines = []
    for bt in backtest_results:
        key = bt.get("key", "?")
        wr = bt.get("win_rate", 0)
        total = bt.get("total_trades", 0)
        pf = bt.get("profit_factor", 0)
        bt_lines.append(f"  {key}: 胜率 {wr:.0%}（{total}笔），盈利因子 {pf:.2f}")
    bt_summary = "\n".join(bt_lines) if bt_lines else "  回测数据不足"

    # 期权摘要
    opt = option_summary or {}
    flow = opt.get("flow_sentiment", "unknown")
    cp_ratio = opt.get("call_put_volume_ratio")
    max_pain = opt.get("max_pain_strike")
    liq = opt.get("liquidity_score")
    sel = opt.get("selection_score")

    # 财报
    ec = earnings_calendar or {}
    next_earnings = ec.get("next_earnings_date", "未知")
    days_to = ec.get("days_to_earnings")

    # 评分
    score = score_row or {}
    total_score = score.get("total_score") or score.get("score")

    context = {
        "task_type": "tenx_option_strategy_analysis",
        "market": market,
        "symbol": symbol,
        "current_price": underlying_price,
        "option_summary": {
            "iv": round(iv, 4),
            "iv_level": iv_level,
            "flow_sentiment": flow,
            "call_put_volume_ratio": cp_ratio,
            "max_pain_strike": max_pain,
            "liquidity_score": liq,
            "selection_score": sel,
        },
        "price_trend_30d": trend_desc,
        "earnings": {
            "next_earnings_date": next_earnings,
            "days_to_earnings": days_to,
        },
        "selection_score": total_score,
        "backtest_summary": bt_summary,
    }

    # 策略列表（告诉 LLM 需要分析哪些策略）
    strategy_keys = [bt.get("key") for bt in backtest_results if bt.get("key")]

    schema = {
        "strategies": [
            {
                "key": "long_call",
                "name": "买入看涨",
                "recommendation": "strong_buy|buy|hold|avoid|strong_avoid",
                "confidence": "high|medium|low",
                "target_strike": "ATM / OTM+0.5σ 等",
                "target_dte": 30,
                "win_probability": 0.55,
                "risk_reward_ratio": 2.0,
                "logic": "中文分析推理，200-500字，结合IV/资金流/技术面/回测数据给出完整分析逻辑",
                "key_risks": ["风险1", "风险2"],
                "entry_condition": "入场条件描述",
                "exit_condition": "出场条件描述",
            }
        ],
        "overall_assessment": {
            "posture": "bullish_trending|range_bound|bearish|volatile_breakout",
            "best_strategy": "strategy_key",
            "summary": "200字以内综合判断，包括当前市场环境、最推荐的策略及理由",
        },
    }

    return (
        "你是 TenX Hunter 的期权策略高级分析师。\n"
        "请基于以下输入数据，对该标的的期权策略进行系统性分析。\n\n"
        "要求：\n"
        "1. 只返回一个 JSON object，不要 Markdown 包裹，不要解释性前后缀。\n"
        "2. 为每个策略给出 recommendation（strong_buy/buy/hold/avoid/strong_avoid）和 confidence。\n"
        "3. logic 是最重要的字段：用中文详细说明分析推理过程（200-500字），必须结合 IV 水平、"
        "资金流方向、技术走势、回测胜率等具体数据，给出清晰的因果关系。\n"
        "4. key_risks 列出 2-3 个主要风险点。\n"
        "5. entry_condition 和 exit_condition 给出具体的入场和出场条件。\n"
        "6. overall_assessment 给出整体市场判断和最推荐策略。\n"
        "7. 不要编造不存在的数据；不确定时降低 confidence。\n\n"
        f"需要分析的策略列表: {json.dumps(strategy_keys, ensure_ascii=False)}\n\n"
        f"输出 schema 示例:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"输入数据:\n{json.dumps(context, ensure_ascii=False, default=str, indent=2)}"
    )


# ── 响应解析 ──


def parse_option_strategy_response(payload: dict[str, Any]) -> dict[str, Any]:
    """解析 DeerFlow 返回的 JSON，校验并规范化。"""

    raw_strategies = payload.get("strategies", [])
    if not isinstance(raw_strategies, list):
        raw_strategies = []

    parsed_strategies = []
    for s in raw_strategies:
        if not isinstance(s, dict):
            continue
        rec = str(s.get("recommendation", "hold")).lower()
        if rec not in ALLOWED_RECOMMENDATIONS:
            rec = "hold"
        conf = str(s.get("confidence", "medium")).lower()
        if conf not in ALLOWED_CONFIDENCE:
            conf = "medium"

        risks = s.get("key_risks", [])
        if not isinstance(risks, list):
            risks = []

        parsed_strategies.append({
            "key": str(s.get("key", "")),
            "name": str(s.get("name", "")),
            "recommendation": rec,
            "confidence": conf,
            "target_strike": str(s.get("target_strike", "")),
            "target_dte": int(s.get("target_dte", 30)),
            "win_probability": float(s.get("win_probability", 0)),
            "risk_reward_ratio": float(s.get("risk_reward_ratio", 0)),
            "logic": str(s.get("logic", "")),
            "key_risks": [str(r) for r in risks],
            "entry_condition": str(s.get("entry_condition", "")),
            "exit_condition": str(s.get("exit_condition", "")),
        })

    # overall_assessment
    overall = payload.get("overall_assessment", {})
    if not isinstance(overall, dict):
        overall = {}
    posture = str(overall.get("posture", "range_bound")).lower()
    if posture not in ALLOWED_POSTURES:
        posture = "range_bound"

    return {
        "strategies": parsed_strategies,
        "overall_assessment": {
            "posture": posture,
            "best_strategy": str(overall.get("best_strategy", "")),
            "summary": str(overall.get("summary", "")),
        },
    }
