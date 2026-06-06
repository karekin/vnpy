"""Base class for PostgreSQL-backed stores.

Replaces the per-service SQLite + Lock pattern with a unified PgStore
that uses psycopg and the shared vnpy.web.db connection manager.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from .db import DbSettings, connect


_SCHEMA_SQL_PATH = Path(__file__).resolve().parent / "schema.sql"


def _jsonb(value: Any) -> Jsonb:
    """Wrap a Python object as a psycopg Jsonb value."""
    return Jsonb(value)


class PgStore:
    """Base class providing PG connection and schema bootstrap.

    Subclasses should set ``_SCHEMA_PREFIX`` (e.g. ``"oltp"``) if they
    need to scope ``_ensure_schema()`` to a subset of tables.
    """

    def __init__(self, settings: DbSettings) -> None:
        self._settings = settings

    def _connect(self):
        """Return a context-managed psycopg connection."""
        return connect(self._settings)

    @staticmethod
    def ensure_full_schema(settings: DbSettings) -> None:
        """Execute schema.sql to create all oltp/olap/dim tables."""
        sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        with connect(settings) as conn:
            conn.execute(sql)

    @staticmethod
    def ensure_full_schema_from_conn(conn) -> None:
        """Execute schema.sql using an existing connection."""
        sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        conn.execute(sql)
