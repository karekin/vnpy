from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError as exc:  # pragma: no cover - import guard for local envs
    raise ModuleNotFoundError(
        'TenX Hunter requires psycopg. Install `pip install -e ".[web]"` '
        "or install `psycopg[binary]` manually."
    ) from exc

from .config import Settings


@contextmanager
def connect(settings: Settings) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.pg_dsn, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
