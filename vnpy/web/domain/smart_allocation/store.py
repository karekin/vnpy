from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
import json
from typing import Any

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings
from vnpy.web.domain.smart_allocation.calculator import decimal_from
from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    CashflowEvent,
    IncomeStatus,
)


def _json_default(value: Any) -> str | list[Any]:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _loads(payload: str) -> dict[str, Any]:
    return json.loads(payload)


def _profile_to_payload(profile: AllocationProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "age": profile.age,
        "income_status": profile.income_status.value,
        "rebalance_threshold": str(profile.rebalance_threshold),
        "allow_bull_market_leaps_relaxation": profile.allow_bull_market_leaps_relaxation,
        "qqqm_symbol": profile.qqqm_symbol,
        "voo_symbol": profile.voo_symbol,
        "quality_stock_symbols": list(profile.quality_stock_symbols),
        "wheel_symbols": list(profile.wheel_symbols),
        "leaps_symbols": list(profile.leaps_symbols),
    }


def _profile_from_payload(payload: dict[str, Any]) -> AllocationProfile:
    return AllocationProfile(
        id=str(payload["id"]),
        name=str(payload.get("name") or "智能仓位默认方案"),
        age=int(payload.get("age") or 28),
        income_status=IncomeStatus(str(payload.get("income_status") or IncomeStatus.STABLE.value)),
        rebalance_threshold=decimal_from(payload.get("rebalance_threshold", "0.05")),
        allow_bull_market_leaps_relaxation=bool(payload.get("allow_bull_market_leaps_relaxation", False)),
        qqqm_symbol=str(payload.get("qqqm_symbol") or "QQQM.US"),
        voo_symbol=str(payload.get("voo_symbol") or "VOO.US"),
        quality_stock_symbols=tuple(payload.get("quality_stock_symbols") or ()),
        wheel_symbols=tuple(payload.get("wheel_symbols") or ()),
        leaps_symbols=tuple(payload.get("leaps_symbols") or ()),
    )


def _snapshot_to_payload(snapshot: AllocationSnapshot) -> dict[str, Any]:
    return {
        "total_equity": str(snapshot.total_equity),
        "cash_value": str(snapshot.cash_value),
        "dca_value": str(snapshot.dca_value),
        "options_value": str(snapshot.options_value),
        "wheel_value": str(snapshot.wheel_value),
        "leaps_value": str(snapshot.leaps_value),
        "margin_used": str(snapshot.margin_used),
        "unclassified_value": str(snapshot.unclassified_value),
        "single_stock_values": {key: str(value) for key, value in snapshot.single_stock_values.items()},
        "latest_rsi_by_symbol": {key: str(value) for key, value in snapshot.latest_rsi_by_symbol.items()},
        "open_leaps_symbols": list(snapshot.open_leaps_symbols),
        "source_inputs": {key: str(value) for key, value in snapshot.source_inputs.items()},
        "snapshot_at": snapshot.snapshot_at.isoformat(),
    }


def _snapshot_from_payload(payload: dict[str, Any]) -> AllocationSnapshot:
    return AllocationSnapshot(
        total_equity=decimal_from(payload.get("total_equity", 0)),
        cash_value=decimal_from(payload.get("cash_value", 0)),
        dca_value=decimal_from(payload.get("dca_value", 0)),
        options_value=decimal_from(payload.get("options_value", 0)),
        wheel_value=decimal_from(payload.get("wheel_value", 0)),
        leaps_value=decimal_from(payload.get("leaps_value", 0)),
        margin_used=decimal_from(payload.get("margin_used", 0)),
        unclassified_value=decimal_from(payload.get("unclassified_value", 0)),
        single_stock_values={key: decimal_from(value) for key, value in (payload.get("single_stock_values") or {}).items()},
        latest_rsi_by_symbol={key: decimal_from(value) for key, value in (payload.get("latest_rsi_by_symbol") or {}).items()},
        open_leaps_symbols=list(payload.get("open_leaps_symbols") or []),
        source_inputs={str(key): str(value) for key, value in (payload.get("source_inputs") or {}).items()},
        snapshot_at=datetime.fromisoformat(str(payload["snapshot_at"])) if payload.get("snapshot_at") else datetime.now().astimezone(),
    )


def _cashflow_to_payload(event: CashflowEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "amount": str(event.amount),
        "source_bucket": event.source_bucket,
        "target_bucket": event.target_bucket,
        "symbol": event.symbol,
        "note": event.note,
        "created_at": event.created_at.isoformat(),
    }


def _cashflow_from_payload(payload: dict[str, Any]) -> CashflowEvent:
    return CashflowEvent(
        event_type=str(payload.get("event_type") or "manual_adjustment"),
        amount=decimal_from(payload.get("amount", 0)),
        source_bucket=str(payload.get("source_bucket") or "options"),
        target_bucket=str(payload.get("target_bucket") or "cash"),
        symbol=payload.get("symbol"),
        note=str(payload.get("note") or ""),
        created_at=datetime.fromisoformat(str(payload["created_at"])) if payload.get("created_at") else datetime.now().astimezone(),
    )


class SmartAllocationStore(PgStore):
    """PostgreSQL-backed state store for smart allocation profiles and events."""

    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    def load_profiles(self) -> tuple[list[AllocationProfile], str | None]:
        profiles: list[AllocationProfile] = []
        active_profile_id: str | None = None
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT id, is_active, payload FROM oltp.allocation_profile ORDER BY updated_at DESC"
            ).fetchall():
                try:
                    raw = row["payload"]
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                    profile = _profile_from_payload(payload)
                except Exception:
                    continue
                profiles.append(profile)
                if row["is_active"] is True:
                    active_profile_id = str(row["id"])
        return profiles, active_profile_id

    def upsert_profile(self, profile: AllocationProfile, *, active: bool) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            if active:
                conn.execute("UPDATE oltp.allocation_profile SET is_active = FALSE")
            conn.execute(
                "INSERT INTO oltp.allocation_profile (id, is_active, updated_at, payload) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT(id) DO UPDATE SET "
                "is_active=EXCLUDED.is_active, updated_at=EXCLUDED.updated_at, payload=EXCLUDED.payload",
                (profile.id, active, now, _jsonb(_profile_to_payload(profile))),
            )

    def load_latest_snapshot(self, profile_id: str) -> AllocationSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM olap.allocation_snapshot WHERE profile_id = %s ORDER BY snapshot_at DESC, id DESC LIMIT 1",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        raw = row["payload"]
        payload = json.loads(raw) if isinstance(raw, str) else raw
        return _snapshot_from_payload(payload)

    def insert_snapshot(self, profile_id: str, snapshot: AllocationSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO olap.allocation_snapshot (profile_id, snapshot_at, payload) VALUES (%s, %s, %s)",
                (profile_id, snapshot.snapshot_at.isoformat(), _jsonb(_snapshot_to_payload(snapshot))),
            )

    def insert_cashflow_event(self, profile_id: str, event: CashflowEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO olap.allocation_cashflow_event (profile_id, event_type, created_at, payload) VALUES (%s, %s, %s, %s)",
                (profile_id, event.event_type, event.created_at.isoformat(), _jsonb(_cashflow_to_payload(event))),
            )

    def list_cashflow_events(self, profile_id: str, *, limit: int = 100) -> list[CashflowEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM olap.allocation_cashflow_event WHERE profile_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
                (profile_id, limit),
            ).fetchall()
        events: list[CashflowEvent] = []
        for row in rows:
            try:
                raw = row["payload"]
                payload = json.loads(raw) if isinstance(raw, str) else raw
                events.append(_cashflow_from_payload(payload))
            except Exception:
                continue
        return events

    def set_recommendation_status(
        self,
        profile_id: str,
        recommendation_id: str,
        *,
        status: str,
        user_note: str = "",
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {"status": status, "user_note": user_note, "updated_at": now}
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oltp.allocation_recommendation_status "
                "(profile_id, recommendation_id, status, user_note, updated_at, payload) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(profile_id, recommendation_id) DO UPDATE SET "
                "status=EXCLUDED.status, user_note=EXCLUDED.user_note, "
                "updated_at=EXCLUDED.updated_at, payload=EXCLUDED.payload",
                (profile_id, recommendation_id, status, user_note, now, _jsonb(payload)),
            )

    def load_recommendation_statuses(self, profile_id: str) -> dict[str, dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT recommendation_id, status, user_note FROM oltp.allocation_recommendation_status WHERE profile_id = %s",
                (profile_id,),
            ).fetchall()
        return {
            str(row["recommendation_id"]): {
                "status": str(row["status"] or "pending"),
                "user_note": str(row["user_note"] or ""),
            }
            for row in rows
        }
