"""SQLite connection setup for :class:`crypto_rsi_scanner.storage.Storage`."""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import _SCHEMA


def _clean(value: object) -> object:
    """Coerce pandas/NumPy NaN to None so SQLite stores NULL, not a NaN float."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ConnectionMixin:
    def __init__(self, db_path: Path):
        # timeout: wait (don't immediately error) when another process holds the lock.
        self.conn = sqlite3.connect(str(db_path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        # The daily scan (launchd) and the always-on bot listener share this one
        # SQLite file. WAL lets a reader and a writer proceed concurrently without
        # "database is locked"; busy_timeout backs the rarer writer/writer overlap.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
