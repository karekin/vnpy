from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy
except ModuleNotFoundError:  # pragma: no cover - local dev may not install Temporal SDK
    activity = workflow = None  # type: ignore[assignment]
    RetryPolicy = None  # type: ignore[assignment]


TASK_QUEUE = "stock-recommendation"
DEFAULT_SYMBOLS = ("AAPL", "MSFT", "NVDA", "QQQ", "SPY")
STATUS_VALUES = {
    "daily_target_review": {"recommend", "watch", "avoid"},
    "wheel_review": {"wheel_actionable", "wheel_watch", "wheel_blocked"},
    "leaps_review": {"leaps_researchable", "leaps_watch", "leaps_blocked"},
}


class _DecoratorShim:
    def defn(self, fn: Any | None = None, **_: Any) -> Any:
        if callable(fn):
            return fn

        def _wrap(wrapped: Any) -> Any:
            return wrapped

        return _wrap

    def run(self, fn: Any) -> Any:
        return fn


if activity is None or workflow is None:
    activity = workflow = _DecoratorShim()  # type: ignore[assignment]


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _result_path() -> Path:
    configured = os.getenv("VNPY_AGENT_CHAIN_RESULTS_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".vntrader" / "agent_chain" / "strategy_fit_reviews.jsonl"


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty DeerFlow response")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else stripped
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end < start:
            raise ValueError("DeerFlow response does not contain a JSON object")
        candidate = candidate[start : end + 1]

    payload = json.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("DeerFlow JSON response must be an object")
    return payload


def _normalize_symbols(raw_symbols: str | None) -> list[str]:
    if raw_symbols is None:
        raw_symbols = os.getenv("STOCK_RECOMMENDATION_SYMBOLS", "")
    values = [item.strip().upper() for item in re.split(r"[\s,]+", raw_symbols) if item.strip()]
    return list(dict.fromkeys(values or DEFAULT_SYMBOLS))


def _build_agent_prompt(payload: dict[str, Any], market_context: dict[str, Any]) -> str:
    body = {
        "task_type": "daily_option_target_recommendation",
        "symbol": payload["symbol"],
        "trade_date": payload["trade_date"],
        "market": payload.get("market", "US"),
        "market_context": market_context,
        "wheel_rule_score": payload.get("wheel_rule_score", {}),
        "leaps_rule_score": payload.get("leaps_rule_score", {}),
        "hard_blocks": payload.get("hard_blocks", []),
        "output_schema": "daily_option_target_recommendation_v1",
    }
    return (
        "请作为只读研究 Agent 基于最新期权链摘要，评估该标的是否进入今日期权观察/操作候选。\n"
        "必须只返回一个 JSON 对象，不要输出 Markdown、自然语言前后缀或自动下单指令。\n"
        "不要给出保证收益、不要建议绕过人工复核；只输出研究结论。\n"
        "只有 portfolio_context.portfolio_fit.recommendation_gate 为 recommend_allowed，且期权链 data_quality_flag=ok 时，"
        "daily_target_review.status 才允许返回 recommend；否则只能返回 watch 或 avoid。\n"
        "JSON schema: symbol, daily_target_review{status,rank_reason,option_setup,evidence}, "
        "wheel_review{status,reason,risks}, leaps_review{status,reason,risks}, manual_checks, data_quality。\n"
        "daily_target_review.status 只能是 recommend/watch/avoid；"
        "wheel_review.status 只能是 wheel_actionable/wheel_watch/wheel_blocked；"
        "leaps_review.status 只能是 leaps_researchable/leaps_watch/leaps_blocked。\n\n"
        f"{json.dumps(body, ensure_ascii=False, indent=2, default=_json_default)}"
    )


def _blocked_agent_payload(payload: dict[str, Any], error: str) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or "").upper()
    return {
        "symbol": symbol,
        "daily_target_review": {
            "status": "avoid",
            "rank_reason": f"Agent backend unavailable: {error}",
            "option_setup": "manual_review_required",
            "evidence": ["DeerFlow did not return a successful structured result."],
        },
        "wheel_review": {
            "status": "wheel_blocked",
            "reason": "Agent review did not complete successfully.",
            "risks": ["agent_backend_unavailable"],
        },
        "leaps_review": {
            "status": "leaps_blocked",
            "reason": "Agent review did not complete successfully.",
            "risks": ["agent_backend_unavailable"],
        },
        "manual_checks": ["Retry DeerFlow analysis before using this symbol as a daily candidate."],
        "data_quality": "agent_unavailable",
    }


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value) if isinstance(value, dict) else {}


def _normalize_position_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith(".US"):
        value = value[:-3]
    return value


def _as_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _calculate_portfolio_fit(
    *,
    symbol: str,
    option_summary: dict[str, Any],
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    targets: dict[str, Any],
    guardrails: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_symbol = _normalize_position_symbol(symbol)
    total_equity = _as_number(snapshot.get("total_equity"))
    if total_equity <= 0:
        return {
            "status": "unconfigured",
            "score": 0,
            "recommendation_gate": "no_recommend",
            "reason": "Active smart-allocation snapshot has no account equity; load current positions before using daily recommendations.",
            "blockers": ["portfolio_snapshot_missing"],
        }

    single_stock_values = snapshot.get("single_stock_values") if isinstance(snapshot.get("single_stock_values"), dict) else {}
    holding_value = 0.0
    for raw_symbol, raw_value in single_stock_values.items():
        if _normalize_position_symbol(str(raw_symbol)) == normalized_symbol:
            holding_value += _as_number(raw_value)

    underlying_price = _as_number(option_summary.get("underlying_price"))
    estimated_cash_required = underlying_price * 100 if underlying_price > 0 else 0.0
    wheel_available = max(_as_number(targets.get("wheel_value")) - _as_number(snapshot.get("wheel_value")), 0.0)
    leaps_available = max(_as_number(targets.get("leaps_value")) - _as_number(snapshot.get("leaps_value")), 0.0)
    single_stock_limit = _as_number(targets.get("single_stock_limit"))
    margin_room = max(_as_number(targets.get("margin_limit")) - _as_number(snapshot.get("margin_used")), 0.0)
    quality_symbols = {_normalize_position_symbol(str(item)) for item in profile.get("quality_stock_symbols", [])}
    wheel_symbols = {_normalize_position_symbol(str(item)) for item in profile.get("wheel_symbols", [])}
    leaps_symbols = {_normalize_position_symbol(str(item)) for item in profile.get("leaps_symbols", [])}

    blockers: list[str] = []
    if margin_room <= 0:
        blockers.append("margin_room_exhausted")
    if estimated_cash_required <= 0:
        blockers.append("underlying_price_missing")
    if single_stock_limit > 0 and estimated_cash_required > single_stock_limit:
        blockers.append("one_contract_exceeds_single_stock_limit")
    if estimated_cash_required > wheel_available:
        blockers.append("wheel_budget_insufficient_for_cash_secured_put")
    if single_stock_limit > 0 and holding_value >= single_stock_limit:
        blockers.append("symbol_concentration_limit_reached")
    for violation in guardrails:
        if violation.get("blocking"):
            blockers.append(str(violation.get("rule_code") or "blocking_guardrail"))

    score = 45.0
    if normalized_symbol in wheel_symbols:
        score += 15
    if normalized_symbol in quality_symbols:
        score += 10
    if normalized_symbol in leaps_symbols:
        score += 8
    if holding_value > 0 and (single_stock_limit <= 0 or holding_value < single_stock_limit):
        score += 6
    if estimated_cash_required > 0 and estimated_cash_required <= wheel_available:
        score += 18
    else:
        score -= 16
    if single_stock_limit <= 0 or estimated_cash_required <= single_stock_limit:
        score += 12
    else:
        score -= 22
    if leaps_available > 0:
        score += 4
    if option_summary.get("flow_sentiment") == "bearish":
        score -= 8

    score = round(max(0.0, min(100.0, score)), 2)
    if blockers:
        status = "blocked"
        recommendation_gate = "no_recommend"
        reason = "Portfolio guardrails block new risk for this symbol."
    elif score >= 70:
        status = "eligible"
        recommendation_gate = "recommend_allowed"
        reason = "Portfolio budget, concentration, and margin guardrails allow this symbol to be recommended."
    else:
        status = "watch"
        recommendation_gate = "watch_only"
        reason = "Portfolio fit is acceptable for monitoring but not strong enough for an automatic daily recommendation."

    return {
        "status": status,
        "score": score,
        "recommendation_gate": recommendation_gate,
        "reason": reason,
        "blockers": blockers,
        "estimated_cash_required_for_one_put": round(estimated_cash_required, 2),
        "wheel_available": round(wheel_available, 2),
        "leaps_available": round(leaps_available, 2),
        "single_stock_limit": round(single_stock_limit, 2),
        "margin_room": round(margin_room, 2),
        "current_symbol_holding_value": round(holding_value, 2),
    }


def _load_portfolio_context(symbol: str, option_summary: dict[str, Any]) -> dict[str, Any]:
    try:
        from vnpy.web.services.smart_allocation_service import SmartAllocationService

        dashboard = SmartAllocationService().get_dashboard()
        profile = _model_to_dict(dashboard.profile)
        snapshot = _model_to_dict(dashboard.snapshot)
        targets = _model_to_dict(dashboard.targets)
        guardrails = [_model_to_dict(item) for item in dashboard.guardrails]
        fit = _calculate_portfolio_fit(
            symbol=symbol,
            option_summary=option_summary,
            profile=profile,
            snapshot=snapshot,
            targets=targets,
            guardrails=guardrails,
        )
        return {
            "profile": {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "income_status": profile.get("income_status"),
                "rebalance_threshold": profile.get("rebalance_threshold"),
                "quality_stock_symbols": profile.get("quality_stock_symbols", []),
                "wheel_symbols": profile.get("wheel_symbols", []),
                "leaps_symbols": profile.get("leaps_symbols", []),
            },
            "snapshot": {
                "total_equity": snapshot.get("total_equity"),
                "cash_value": snapshot.get("cash_value"),
                "dca_value": snapshot.get("dca_value"),
                "options_value": snapshot.get("options_value"),
                "wheel_value": snapshot.get("wheel_value"),
                "leaps_value": snapshot.get("leaps_value"),
                "margin_used": snapshot.get("margin_used"),
                "single_stock_values": snapshot.get("single_stock_values", {}),
                "open_leaps_symbols": snapshot.get("open_leaps_symbols", []),
                "snapshot_at": snapshot.get("snapshot_at"),
            },
            "targets": {
                "cash_value": targets.get("cash_value"),
                "options_value": targets.get("options_value"),
                "wheel_value": targets.get("wheel_value"),
                "leaps_value": targets.get("leaps_value"),
                "single_stock_limit": targets.get("single_stock_limit"),
                "margin_limit": targets.get("margin_limit"),
            },
            "guardrails": guardrails,
            "portfolio_fit": fit,
        }
    except Exception as exc:
        return {
            "portfolio_fit": {
                "status": "unavailable",
                "score": 0,
                "recommendation_gate": "no_recommend",
                "reason": "Smart-allocation context could not be loaded.",
                "blockers": ["portfolio_context_error"],
                "error": str(exc),
            }
        }


@activity.defn
def collect_market_context(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload["symbol"]).upper()
    market = str(payload.get("market", "US")).upper()
    trade_date = str(payload["trade_date"])
    try:
        from vnpy.web.tenx_hunter.options_chain import refresh_option_chain_for_symbol

        option_result = refresh_option_chain_for_symbol(symbol, market=market, trade_date=trade_date)
        option_summary = option_result["summary"]
        source = option_result["source"]
        notes = option_summary.get("notes", [])
    except Exception as exc:
        option_summary = {
            "symbol": symbol,
            "market": market,
            "trade_date": trade_date,
            "contract_count": 0,
            "selection_score": 0,
            "liquidity_score": 0,
            "flow_sentiment": "unknown",
            "data_quality_flag": "option_chain_error",
            "error": str(exc),
        }
        source = "option-chain-error"
        notes = ["Option chain refresh failed; Agent must treat the recommendation as blocked until data is repaired."]
    return {
        "symbol": symbol,
        "market": market,
        "trade_date": trade_date,
        "source": source,
        "option_chain_summary": option_summary,
        "portfolio_context": _load_portfolio_context(symbol, option_summary),
        "notes": notes,
    }


@activity.defn
def calculate_rule_scores(payload: dict[str, Any]) -> dict[str, Any]:
    market_context = payload.get("market_context") if isinstance(payload.get("market_context"), dict) else {}
    option_summary = (
        market_context.get("option_chain_summary")
        if isinstance(market_context.get("option_chain_summary"), dict)
        else {}
    )
    portfolio_context = (
        market_context.get("portfolio_context")
        if isinstance(market_context.get("portfolio_context"), dict)
        else {}
    )
    portfolio_fit = (
        portfolio_context.get("portfolio_fit")
        if isinstance(portfolio_context.get("portfolio_fit"), dict)
        else {}
    )
    hard_blocks = list(payload.get("hard_blocks", []))
    if portfolio_fit.get("recommendation_gate") == "no_recommend":
        hard_blocks.append(
            {
                "code": "portfolio_fit_blocks_recommendation",
                "reason": portfolio_fit.get("reason"),
                "blockers": portfolio_fit.get("blockers", []),
            }
        )
    return {
        "symbol": str(payload["symbol"]).upper(),
        "wheel_rule_score": option_summary.get("wheel_rule_score")
        or payload.get("wheel_rule_score", {"status": "needs_agent_review"}),
        "leaps_rule_score": option_summary.get("leaps_rule_score")
        or payload.get("leaps_rule_score", {"status": "needs_agent_review"}),
        "portfolio_fit": portfolio_fit,
        "hard_blocks": hard_blocks,
    }


@activity.defn
def create_deerflow_thread(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload["symbol"]).lower()
    trade_date = str(payload["trade_date"])
    thread_id = f"strategy-fit-{trade_date}-{symbol}"
    return {"thread_id": thread_id}


@activity.defn
def run_deerflow_agent_task(payload: dict[str, Any]) -> dict[str, Any]:
    from vnpy.web.services.deerflow_service import DeerFlowService

    prompt = _build_agent_prompt(payload, payload["market_context"])
    result = DeerFlowService().chat(prompt, thread_id=payload["thread_id"])
    return {
        "ok": result.ok,
        "thread_id": result.thread_id or payload["thread_id"],
        "backend": result.backend,
        "content": result.content,
        "error": result.error,
    }


@activity.defn
def poll_deerflow_result(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("ok"):
        error = str(payload.get("error") or "DeerFlow agent task failed")
        return {
            **payload,
            "ok": False,
            "content": json.dumps(_blocked_agent_payload(payload, error), ensure_ascii=False),
            "error": error,
        }
    return payload


@activity.defn
def validate_agent_json(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _extract_json_object(str(payload.get("content") or ""))
    symbol = str(parsed.get("symbol") or "").upper()
    if symbol != str(payload["symbol"]).upper():
        raise ValueError(f"symbol mismatch: expected {payload['symbol']}, got {symbol or '-'}")

    parsed.setdefault(
        "daily_target_review",
        {
            "status": "watch",
            "rank_reason": "Agent did not provide a dedicated daily target section.",
            "option_setup": "manual_review_required",
            "evidence": [],
        },
    )
    for section, allowed in STATUS_VALUES.items():
        value = parsed.get(section)
        if not isinstance(value, dict):
            raise ValueError(f"missing object: {section}")
        status = str(value.get("status") or "")
        if status not in allowed:
            raise ValueError(f"invalid {section}.status: {status}")

    parsed.setdefault("manual_checks", [])
    parsed.setdefault("data_quality", "unknown")
    market_context = payload.get("market_context") if isinstance(payload.get("market_context"), dict) else {}
    portfolio_context = (
        market_context.get("portfolio_context")
        if isinstance(market_context.get("portfolio_context"), dict)
        else {}
    )
    portfolio_fit = (
        portfolio_context.get("portfolio_fit")
        if isinstance(portfolio_context.get("portfolio_fit"), dict)
        else {}
    )
    if (
        portfolio_fit.get("recommendation_gate") != "recommend_allowed"
        and parsed["daily_target_review"].get("status") == "recommend"
    ):
        parsed["daily_target_review"]["status"] = "avoid" if portfolio_fit.get("status") in {"blocked", "unconfigured", "unavailable"} else "watch"
        parsed["daily_target_review"]["portfolio_gate_adjustment"] = {
            "from": "recommend",
            "to": parsed["daily_target_review"]["status"],
            "reason": portfolio_fit.get("reason") or "Portfolio fit gate does not allow recommendations.",
            "blockers": portfolio_fit.get("blockers", []),
        }
        parsed["manual_checks"].append("Portfolio fit gate downgraded the Agent recommendation; refresh account snapshot before acting.")
    return parsed


@activity.defn
def save_recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    path = _result_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": payload["batch_id"],
        "workflow_id": payload["workflow_id"],
        "symbol": payload["symbol"],
        "trade_date": payload["trade_date"],
        "market": payload.get("market", "US"),
        "deerflow_thread_id": payload["thread_id"],
        "market_context": payload.get("market_context", {}),
        "result": payload["result"],
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
    from vnpy.web.tenx_hunter.options_chain import persist_agent_recommendation

    persist_agent_recommendation(row=row)
    return {"ok": True, "path": str(path), "symbol": payload["symbol"]}


@workflow.defn
class StockRecommendationWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        activity_timeout = timedelta(minutes=10)
        short_retry = RetryPolicy(maximum_attempts=2) if RetryPolicy is not None else None
        context = await workflow.execute_activity(
            collect_market_context,
            payload,
            start_to_close_timeout=activity_timeout,
            retry_policy=short_retry,
        )
        scores = await workflow.execute_activity(
            calculate_rule_scores,
            {**payload, "market_context": context},
            start_to_close_timeout=activity_timeout,
            retry_policy=short_retry,
        )
        thread = await workflow.execute_activity(
            create_deerflow_thread,
            payload,
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=short_retry,
        )
        agent_result = await workflow.execute_activity(
            run_deerflow_agent_task,
            {**payload, **scores, **thread, "market_context": context},
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=short_retry,
        )
        completed = await workflow.execute_activity(
            poll_deerflow_result,
            {**payload, **agent_result},
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=short_retry,
        )
        parsed = await workflow.execute_activity(
            validate_agent_json,
            {**payload, **completed, "market_context": context},
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=short_retry,
        )
        return await workflow.execute_activity(
            save_recommendation,
            {
                **payload,
                "thread_id": completed["thread_id"],
                "market_context": context,
                "result": parsed,
                "workflow_id": workflow.info().workflow_id,
            },
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=short_retry,
        )


@workflow.defn
class DailyStockRecommendationBatchWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbols = payload.get("symbols") or list(DEFAULT_SYMBOLS)
        batch_id = payload.get("batch_id") or workflow.info().workflow_id
        trade_date = payload.get("trade_date") or workflow.now().date().isoformat()
        results: list[dict[str, Any]] = []
        for symbol in symbols:
            child_payload = {
                **payload,
                "symbol": str(symbol).upper(),
                "symbols": None,
                "batch_id": batch_id,
                "trade_date": trade_date,
            }
            try:
                result = await workflow.execute_child_workflow(
                    StockRecommendationWorkflow.run,
                    child_payload,
                    id=f"{batch_id}-{str(symbol).lower()}",
                    task_queue=payload.get("task_queue") or TASK_QUEUE,
                )
            except Exception as exc:
                result = {"ok": False, "symbol": str(symbol).upper(), "error": str(exc)}
            results.append(result)
        return {"batch_id": batch_id, "count": len(results), "results": results}


async def _connect_client() -> Any:
    from temporalio.client import Client

    address = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(address, namespace=namespace)


async def _run_worker(args: argparse.Namespace) -> None:
    from temporalio.worker import Worker

    client = await _connect_client()
    worker = Worker(
        client,
        task_queue=args.task_queue,
        workflows=[DailyStockRecommendationBatchWorkflow, StockRecommendationWorkflow],
        activity_executor=ThreadPoolExecutor(max_workers=int(os.getenv("TEMPORAL_ACTIVITY_WORKERS", "8"))),
        activities=[
            collect_market_context,
            calculate_rule_scores,
            create_deerflow_thread,
            run_deerflow_agent_task,
            poll_deerflow_result,
            validate_agent_json,
            save_recommendation,
        ],
    )
    print(f"Temporal worker polling task queue: {args.task_queue}", flush=True)
    await worker.run()


async def _start_batch(args: argparse.Namespace) -> None:
    client = await _connect_client()
    trade_date = args.trade_date or date.today().isoformat()
    symbols = _normalize_symbols(args.symbols)
    payload = {
        "batch_id": args.batch_id or f"daily-stock-recommendation-{trade_date}-{uuid4().hex[:8]}",
        "trade_date": trade_date,
        "market": args.market,
        "symbols": symbols,
        "task_queue": args.task_queue,
    }
    handle = await client.start_workflow(
        DailyStockRecommendationBatchWorkflow.run,
        payload,
        id=payload["batch_id"],
        task_queue=args.task_queue,
    )
    print(json.dumps({"workflow_id": handle.id, "run_id": handle.result_run_id, "payload": payload}, ensure_ascii=False))


async def _create_schedule(args: argparse.Namespace) -> None:
    from temporalio.client import Schedule, ScheduleActionStartWorkflow, ScheduleSpec

    client = await _connect_client()
    symbols = _normalize_symbols(args.symbols)
    payload = {
        "batch_id": "scheduled-daily-stock-recommendation",
        "trade_date": "",
        "market": args.market,
        "symbols": symbols,
        "task_queue": args.task_queue,
    }
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            DailyStockRecommendationBatchWorkflow.run,
            payload,
            id="daily-stock-recommendation",
            task_queue=args.task_queue,
        ),
        spec=ScheduleSpec(
            cron_expressions=[args.cron],
            time_zone_name=args.time_zone,
        ),
    )
    await client.create_schedule(args.schedule_id, schedule)
    print(json.dumps({"schedule_id": args.schedule_id, "cron": args.cron, "time_zone": args.time_zone}, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run VN.PY smart-allocation long task chain on Temporal.")
    parser.add_argument("--task-queue", default=os.getenv("TEMPORAL_TASK_QUEUE", TASK_QUEUE))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("worker", help="Run the Temporal worker.")

    run_daily = subparsers.add_parser("run-daily", help="Start a daily batch workflow.")
    run_daily.add_argument("--trade-date", default="")
    run_daily.add_argument("--market", default=os.getenv("STOCK_RECOMMENDATION_MARKET", "US"))
    run_daily.add_argument("--symbols", default=os.getenv("STOCK_RECOMMENDATION_SYMBOLS", ""))
    run_daily.add_argument("--batch-id", default="")

    schedule = subparsers.add_parser("create-schedule", help="Create the daily Temporal Schedule.")
    schedule.add_argument("--schedule-id", default=os.getenv("STOCK_RECOMMENDATION_SCHEDULE_ID", "daily-stock-recommendation"))
    schedule.add_argument("--cron", default=os.getenv("STOCK_RECOMMENDATION_CRON", "0 8 * * 1-5"))
    schedule.add_argument("--time-zone", default=os.getenv("STOCK_RECOMMENDATION_TIME_ZONE", "Asia/Shanghai"))
    schedule.add_argument("--market", default=os.getenv("STOCK_RECOMMENDATION_MARKET", "US"))
    schedule.add_argument("--symbols", default=os.getenv("STOCK_RECOMMENDATION_SYMBOLS", ""))
    return parser


async def _async_main(args: argparse.Namespace) -> None:
    if args.command == "worker":
        await _run_worker(args)
    elif args.command == "run-daily":
        await _start_batch(args)
    elif args.command == "create-schedule":
        await _create_schedule(args)
    else:  # pragma: no cover - argparse prevents this
        raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    if not hasattr(workflow, "execute_activity"):
        raise SystemExit("Temporal SDK is not installed. Install deploy/requirements-worker.txt or run the worker image.")
    asyncio.run(_async_main(_build_parser().parse_args()))
