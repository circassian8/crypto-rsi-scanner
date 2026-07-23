"""One small SQLite runtime store for Lean Crypto Radar."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Iterator, Mapping, Sequence
from urllib.parse import quote

from .models import BybitInstrument, LeanIdea, MarketSnapshot


SCHEMA_VERSION = 1


class _LeanRadarStoreError(RuntimeError):
    """Raised when the runtime database cannot be used safely."""


LeanRadarStoreError = _LeanRadarStoreError


class LeanRadarStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()
        if not self.path.is_absolute():
            raise LeanRadarStoreError("lean radar database path must be absolute")

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._validate_existing_file(missing_ok=True)
            connection = sqlite3.connect(self.path, timeout=5.0)
        else:
            self._validate_existing_file(missing_ok=False)
            encoded = quote(str(self.path), safe="/")
            connection = sqlite3.connect(
                f"file:{encoded}?mode=ro", uri=True, timeout=5.0
            )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            if write:
                connection.execute("PRAGMA journal_mode = WAL")
                self._migrate(connection)
                os.chmod(self.path, 0o600)
            yield connection
        finally:
            connection.close()

    def catalog_status(self) -> dict[str, object]:
        if not self.path.exists():
            return {
                "status": "missing",
                "instrument_count": 0,
                "source_mode": "unavailable",
                "source_observed_at": None,
                "source_sha256": None,
            }
        try:
            with self.connect() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != SCHEMA_VERSION:
                    raise LeanRadarStoreError("lean radar database schema is unsupported")
                count = int(
                    connection.execute("SELECT COUNT(*) FROM bybit_instruments").fetchone()[0]
                )
                metadata = dict(
                    connection.execute(
                        "SELECT key, value FROM meta WHERE key LIKE 'bybit_catalog_%'"
                    ).fetchall()
                )
        except (sqlite3.Error, OSError) as exc:
            raise LeanRadarStoreError("lean radar database is unavailable") from exc
        return {
            "status": "ready" if count else "empty",
            "instrument_count": count,
            "source_mode": metadata.get("bybit_catalog_source_mode", "unavailable"),
            "source_observed_at": metadata.get("bybit_catalog_source_observed_at"),
            "source_sha256": metadata.get("bybit_catalog_source_sha256"),
            "imported_at": metadata.get("bybit_catalog_imported_at"),
        }

    def replace_bybit_catalog(
        self,
        instruments: Sequence[BybitInstrument],
        *,
        imported_at: datetime | None = None,
    ) -> None:
        if not instruments:
            raise LeanRadarStoreError("refusing to import an empty Bybit catalog")
        source_modes = {row.source_mode for row in instruments}
        source_times = {row.source_observed_at for row in instruments}
        source_hashes = {row.source_sha256 for row in instruments}
        if len(source_modes) != 1 or len(source_times) != 1 or len(source_hashes) != 1:
            raise LeanRadarStoreError("Bybit catalog source identity is inconsistent")
        imported = (imported_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM bybit_instruments")
                connection.executemany(
                    """
                    INSERT INTO bybit_instruments (
                        instrument_id, base_coin, quote_coin, settle_coin,
                        contract_type, status, tick_size, quantity_step,
                        minimum_quantity, maximum_limit_quantity,
                        maximum_market_quantity, minimum_notional_usdt,
                        source_observed_at, source_mode, source_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.instrument_id,
                            row.base_coin,
                            row.quote_coin,
                            row.settle_coin,
                            row.contract_type,
                            row.status,
                            row.tick_size,
                            row.quantity_step,
                            row.minimum_quantity,
                            row.maximum_limit_quantity,
                            row.maximum_market_quantity,
                            row.minimum_notional_usdt,
                            row.source_observed_at,
                            row.source_mode,
                            row.source_sha256,
                        )
                        for row in instruments
                    ],
                )
                metadata = {
                    "bybit_catalog_source_mode": next(iter(source_modes)),
                    "bybit_catalog_source_observed_at": next(iter(source_times)),
                    "bybit_catalog_source_sha256": next(iter(source_hashes)),
                    "bybit_catalog_imported_at": imported.isoformat(),
                }
                connection.executemany(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    sorted(metadata.items()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list_bybit_instruments(self) -> tuple[BybitInstrument, ...]:
        if not self.path.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM bybit_instruments ORDER BY base_coin, instrument_id"
            ).fetchall()
        return tuple(
            BybitInstrument(
                instrument_id=row["instrument_id"],
                base_coin=row["base_coin"],
                quote_coin=row["quote_coin"],
                settle_coin=row["settle_coin"],
                contract_type=row["contract_type"],
                status=row["status"],
                tick_size=row["tick_size"],
                quantity_step=row["quantity_step"],
                minimum_quantity=row["minimum_quantity"],
                maximum_limit_quantity=row["maximum_limit_quantity"],
                maximum_market_quantity=row["maximum_market_quantity"],
                minimum_notional_usdt=row["minimum_notional_usdt"],
                source_observed_at=row["source_observed_at"],
                source_mode=row["source_mode"],
                source_sha256=row["source_sha256"],
            )
            for row in rows
        )

    def upsert_watchlist(
        self,
        *,
        canonical_asset_id: str,
        symbol: str,
        note: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect(write=True) as connection:
            connection.execute(
                """
                INSERT INTO manual_watchlist (
                    canonical_asset_id, symbol, note, enabled, updated_at
                ) VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(canonical_asset_id) DO UPDATE SET
                    symbol = excluded.symbol,
                    note = excluded.note,
                    enabled = 1,
                    updated_at = excluded.updated_at
                """,
                (canonical_asset_id, symbol, note, now),
            )
            connection.commit()

    def list_watchlist(self) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT canonical_asset_id, symbol, note, updated_at
                FROM manual_watchlist WHERE enabled = 1
                ORDER BY canonical_asset_id
                """
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def snapshot_history(
        self,
        canonical_asset_id: str,
        *,
        before: str,
        limit: int = 128,
    ) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM market_snapshots
                WHERE canonical_asset_id = ? AND observed_at < ?
                ORDER BY observed_at DESC LIMIT ?
                """,
                (canonical_asset_id, before, max(1, min(limit, 256))),
            ).fetchall()
        parsed: list[dict[str, object]] = []
        for row in reversed(rows):
            value = json.loads(row["payload_json"])
            if isinstance(value, dict):
                parsed.append(value)
        return tuple(parsed)

    def last_scan_status(self) -> dict[str, object] | None:
        if not self.path.exists():
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM system_health WHERE component = 'scan'"
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise LeanRadarStoreError("stored scan health is invalid")
        return payload

    def record_health(
        self,
        component: str,
        health: Mapping[str, object],
    ) -> None:
        if not isinstance(component, str) or not component.strip() or len(component) > 64:
            raise LeanRadarStoreError("health component is invalid")
        checked_at = health.get("checked_at")
        status = health.get("status")
        if not isinstance(checked_at, str) or not isinstance(status, str):
            raise LeanRadarStoreError("health identity is invalid")
        payload = json.dumps(
            dict(health), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        with self.connect(write=True) as connection:
            connection.execute(
                """
                INSERT INTO system_health (component, checked_at, status, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(component) DO UPDATE SET
                    checked_at = excluded.checked_at,
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (component.strip(), checked_at, status, payload),
            )
            connection.commit()

    def record_scan(
        self,
        snapshots: Sequence[MarketSnapshot],
        ideas: Sequence[LeanIdea],
        health: Mapping[str, object],
    ) -> None:
        checked_at = health.get("checked_at")
        status = health.get("status")
        if not isinstance(checked_at, str) or not isinstance(status, str):
            raise LeanRadarStoreError("scan health identity is invalid")
        snapshot_payloads = [
            json.dumps(row.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
            for row in snapshots
        ]
        idea_payloads = [
            json.dumps(row.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
            for row in ideas
        ]
        health_json = json.dumps(
            dict(health), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.executemany(
                    """
                    INSERT INTO market_snapshots (
                        canonical_asset_id, observed_at, source_mode, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            row.canonical_asset_id,
                            row.observed_at,
                            row.source_mode,
                            payload,
                        )
                        for row, payload in zip(snapshots, snapshot_payloads)
                    ],
                )
                connection.execute("UPDATE ideas SET active = 0 WHERE active = 1")
                connection.executemany(
                    """
                    INSERT INTO ideas (
                        idea_id, created_at, expires_at, active, payload_json
                    ) VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(idea_id) DO UPDATE SET
                        expires_at = excluded.expires_at,
                        active = 1,
                        payload_json = excluded.payload_json
                    """,
                    [
                        (
                            row.idea_id,
                            row.created_at,
                            row.expires_at,
                            payload,
                        )
                        for row, payload in zip(ideas, idea_payloads)
                    ],
                )
                connection.execute(
                    """
                    INSERT INTO system_health (component, checked_at, status, payload_json)
                    VALUES ('scan', ?, ?, ?)
                    ON CONFLICT(component) DO UPDATE SET
                        checked_at = excluded.checked_at,
                        status = excluded.status,
                        payload_json = excluded.payload_json
                    """,
                    (checked_at, status, health_json),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list_active_ideas(self) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM ideas WHERE active = 1 ORDER BY created_at DESC, idea_id"
            ).fetchall()
        return tuple(
            payload
            for row in rows
            if isinstance((payload := json.loads(row["payload_json"])), dict)
        )

    def _migrate(self, connection: sqlite3.Connection) -> None:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise LeanRadarStoreError("lean radar database schema is newer than code")
        if current == 0:
            connection.executescript(
                """
                CREATE TABLE meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE bybit_instruments (
                    instrument_id TEXT PRIMARY KEY,
                    base_coin TEXT NOT NULL UNIQUE,
                    quote_coin TEXT NOT NULL,
                    settle_coin TEXT NOT NULL,
                    contract_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tick_size TEXT NOT NULL,
                    quantity_step TEXT NOT NULL,
                    minimum_quantity TEXT NOT NULL,
                    maximum_limit_quantity TEXT,
                    maximum_market_quantity TEXT,
                    minimum_notional_usdt TEXT,
                    source_observed_at TEXT NOT NULL,
                    source_mode TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL
                );
                CREATE TABLE manual_watchlist (
                    canonical_asset_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE market_snapshots (
                    canonical_asset_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_mode TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (canonical_asset_id, observed_at)
                );
                CREATE TABLE ideas (
                    idea_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE outcomes (
                    idea_id TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    observed_at TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (idea_id, horizon),
                    FOREIGN KEY (idea_id) REFERENCES ideas(idea_id)
                );
                CREATE TABLE calendar_events (
                    event_id TEXT PRIMARY KEY,
                    event_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE notification_state (
                    visible_family TEXT PRIMARY KEY,
                    last_notified_at TEXT,
                    last_material_digest TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE system_health (
                    component TEXT PRIMARY KEY,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                PRAGMA user_version = 1;
                """
            )
            connection.commit()
        elif current != SCHEMA_VERSION:
            raise LeanRadarStoreError("lean radar database migration is incomplete")

    def _validate_existing_file(self, *, missing_ok: bool) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            if missing_ok:
                return
            raise LeanRadarStoreError("lean radar database does not exist") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise LeanRadarStoreError("lean radar database must be a regular file")
        if info.st_nlink != 1:
            raise LeanRadarStoreError("lean radar database must have one hard link")


__all__ = (
    "SCHEMA_VERSION",
    "LeanRadarStore",
    "LeanRadarStoreError",
)
