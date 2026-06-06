"""Unified PostgreSQL connection manager for all web services.

Replaces per-service SQLite stores with a shared PG connection.
Connection parameters come from the same PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD
environment variables already used by tenx_hunter.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError as exc:  # pragma: no cover
    raise ModuleNotFoundError(
        "psycopg is required. Install with: pip install psycopg[binary]"
    ) from exc


@dataclass(frozen=True)
class DbSettings:
    """Minimal PG connection settings shared across all stores."""

    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_database} "
            f"user={self.pg_user} password={self.pg_password}"
        )


def load_db_settings() -> DbSettings:
    """Load PG connection settings from environment variables."""
    import os

    return DbSettings(
        pg_host=os.getenv("PGHOST", "localhost"),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=os.getenv("PGDATABASE", "tenx"),
        pg_user=os.getenv("PGUSER", "tenx"),
        pg_password=os.getenv("PGPASSWORD", "tenx"),
    )


@contextmanager
def connect(settings: DbSettings) -> Iterator[psycopg.Connection]:
    """Yield a psycopg connection with dict rows. Auto-commit on success, rollback on error."""
    conn = psycopg.connect(settings.pg_dsn, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
