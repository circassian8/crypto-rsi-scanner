"""One small SQLite runtime store for Lean Crypto Radar."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator, Mapping, Sequence
from uuid import uuid4

from .models import (
    IDEA_OUTCOME_STATES,
    BybitInstrument,
    CalendarEvent,
    LeanIdea,
    LeanOutcome,
    MarketSnapshot,
)
from .path_security import (
    AnchoredPath,
    LeanPathSecurityError,
    _SecureBytes,
    anchored_path,
    read_regular_bytes_at,
    require_regular_single_link,
)


SCHEMA_VERSION = 2
MAX_DATABASE_BYTES = 512 * 1024 * 1024
MAX_CYCLE_RECEIPTS = 256
MAX_CYCLE_RECEIPT_BYTES = 64 * 1024
BYBIT_CATALOG_RECOMMENDED_AGE = timedelta(hours=12)
BYBIT_CATALOG_MAXIMUM_AGE = timedelta(hours=24)
BYBIT_CATALOG_FUTURE_TOLERANCE = timedelta(minutes=5)
SNAPSHOT_FULL_DETAIL_RETENTION = timedelta(days=3)
SNAPSHOT_RETENTION = timedelta(days=14)
IDEA_OUTCOME_RETENTION = timedelta(days=180)
CALENDAR_HISTORY_RETENTION = timedelta(days=30)
NOTIFICATION_RETENTION = timedelta(days=90)
MAX_NOTIFICATION_STATES = 1_000
_RUNTIME_TABLES = (
    "bybit_instruments",
    "manual_watchlist",
    "market_snapshots",
    "ideas",
    "outcomes",
    "calendar_events",
    "notification_state",
    "system_health",
    "cycle_receipts",
)
_CYCLE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "cycle_id",
        "attempted_at",
        "completed_at",
        "cycle_evaluated_at",
        "trigger",
        "status",
        "source_mode",
        "scan_status",
        "scan_id",
        "skip_reason",
        "provider_call_attempted",
        "provider_call_succeeded",
        "snapshot_count",
        "idea_count",
        "telegram_preview_message_count",
        "telegram_send_attempted",
        "no_send",
        "research_only",
        "telegram_sends",
        "trades_created",
        "orders_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    }
)


class _LeanRadarStoreError(RuntimeError):
    """Raised when the runtime database cannot be used safely."""


LeanRadarStoreError = _LeanRadarStoreError


class LeanRadarStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()
        if not self.path.is_absolute():
            raise LeanRadarStoreError("lean radar database path must be absolute")

    def exists(self) -> bool:
        """Check the runtime leaf without following any parent or leaf symlink."""

        try:
            with anchored_path(self.path) as anchored:
                info = anchored.stat_leaf(missing_ok=True)
                if info is None:
                    return False
                require_regular_single_link(info, maximum_bytes=MAX_DATABASE_BYTES)
                return True
        except LeanPathSecurityError as exc:
            raise LeanRadarStoreError("lean radar database path is unsafe") from exc

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        try:
            with anchored_path(self.path) as anchored:
                initial = anchored.stat_leaf(missing_ok=write)
                lock_descriptor = self._open_lock(anchored, create=write)
                try:
                    fcntl.flock(
                        lock_descriptor,
                        fcntl.LOCK_EX if write else fcntl.LOCK_SH,
                    )
                    self._verify_lock(anchored, lock_descriptor)
                    anchored.verify_parent_chain()
                    original = read_regular_bytes_at(
                        anchored,
                        maximum_bytes=MAX_DATABASE_BYTES,
                        missing_ok=write,
                    )
                    if original is None and not write:
                        raise LeanRadarStoreError(
                            "lean radar database does not exist"
                        )
                    if initial is None and original is not None:
                        raise LeanRadarStoreError(
                            "lean radar database appeared while acquiring its lock"
                        )
                    if initial is not None and (
                        original is None
                        or (initial.st_dev, initial.st_ino)
                        != (original.device, original.inode)
                    ):
                        raise LeanRadarStoreError(
                            "lean radar database changed while acquiring its lock"
                        )
                    connection = sqlite3.connect(":memory:", timeout=5.0)
                    try:
                        if original is not None:
                            if not original.data:
                                raise LeanRadarStoreError(
                                    "lean radar database is empty"
                                )
                            connection.deserialize(original.data)
                        connection.row_factory = sqlite3.Row
                        connection.execute("PRAGMA foreign_keys = ON")
                        connection.execute("PRAGMA busy_timeout = 5000")
                        connection.execute("PRAGMA journal_mode = MEMORY")
                        if write:
                            self._migrate(connection)
                        else:
                            connection.execute("PRAGMA query_only = ON")
                        yield connection
                        if write:
                            connection.commit()
                            integrity = connection.execute(
                                "PRAGMA integrity_check"
                            ).fetchone()
                            if integrity is None or integrity[0] != "ok":
                                raise LeanRadarStoreError(
                                    "lean radar database integrity check failed"
                                )
                            payload = connection.serialize()
                            if len(payload) > MAX_DATABASE_BYTES:
                                raise LeanRadarStoreError(
                                    "lean radar database exceeds its size bound"
                                )
                            self._publish_database(
                                anchored,
                                payload,
                                original=original,
                            )
                        else:
                            current = read_regular_bytes_at(
                                anchored,
                                maximum_bytes=MAX_DATABASE_BYTES,
                            )
                            if (
                                current is None
                                or original is None
                                or current.device != original.device
                                or current.inode != original.inode
                                or current.sha256 != original.sha256
                            ):
                                raise LeanRadarStoreError(
                                    "lean radar database changed during read"
                                )
                        self._verify_lock(anchored, lock_descriptor)
                    finally:
                        connection.close()
                finally:
                    try:
                        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
                    finally:
                        os.close(lock_descriptor)
        except LeanRadarStoreError:
            raise
        except (LeanPathSecurityError, OSError, sqlite3.Error) as exc:
            raise LeanRadarStoreError("lean radar database is unavailable") from exc

    def catalog_status(
        self,
        *,
        evaluated_at: datetime | None = None,
    ) -> dict[str, object]:
        now = evaluated_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise LeanRadarStoreError("catalog evaluation time must be timezone-aware")
        now = now.astimezone(timezone.utc)
        if not self.exists():
            return {
                "status": "missing",
                "freshness_status": "unavailable",
                "instrument_count": 0,
                "source_mode": "unavailable",
                "source_observed_at": None,
                "source_sha256": None,
                "age_seconds": None,
                "recommended_refresh_at": None,
                "maximum_usable_until": None,
                "usable_for_scan": False,
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
        raw_observed_at = metadata.get("bybit_catalog_source_observed_at")
        observed_at = _stored_aware_time(
            raw_observed_at,
            label="Bybit catalog observation",
            missing_ok=True,
        )
        if count == 0:
            freshness_status = "unavailable"
            status = "empty"
            age_seconds = None
            recommended_refresh_at = None
            maximum_usable_until = None
        elif observed_at is None:
            freshness_status = "invalid"
            status = "invalid"
            age_seconds = None
            recommended_refresh_at = None
            maximum_usable_until = None
        else:
            age = now - observed_at
            age_seconds = age.total_seconds()
            recommended_refresh_at = (
                observed_at + BYBIT_CATALOG_RECOMMENDED_AGE
            ).isoformat()
            maximum_usable_until = (
                observed_at + BYBIT_CATALOG_MAXIMUM_AGE
            ).isoformat()
            if age < -BYBIT_CATALOG_FUTURE_TOLERANCE:
                freshness_status = "future_invalid"
                status = "invalid"
            elif age > BYBIT_CATALOG_MAXIMUM_AGE:
                freshness_status = "stale"
                status = "stale"
            elif age > BYBIT_CATALOG_RECOMMENDED_AGE:
                freshness_status = "refresh_recommended"
                status = "ready"
            else:
                freshness_status = "fresh"
                status = "ready"
        return {
            "status": status,
            "freshness_status": freshness_status,
            "instrument_count": count,
            "source_mode": metadata.get("bybit_catalog_source_mode", "unavailable"),
            "source_observed_at": raw_observed_at,
            "source_sha256": metadata.get("bybit_catalog_source_sha256"),
            "imported_at": metadata.get("bybit_catalog_imported_at"),
            "age_seconds": age_seconds,
            "recommended_refresh_at": recommended_refresh_at,
            "maximum_usable_until": maximum_usable_until,
            "usable_for_scan": status == "ready",
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
        if not self.exists():
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
        if not self.exists():
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

    def database_status(
        self,
        *,
        evaluated_at: datetime | None = None,
    ) -> dict[str, object]:
        """Return bounded local database and retention truth."""

        now = evaluated_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise LeanRadarStoreError("database status time must be timezone-aware")
        now = now.astimezone(timezone.utc)
        if not self.exists():
            return {
                "status": "missing",
                "database_size_bytes": 0,
                "maximum_database_bytes": MAX_DATABASE_BYTES,
                "row_counts": {table: 0 for table in _RUNTIME_TABLES},
                "retention_policy": _retention_policy(),
                "maintenance_candidates": {},
                "checked_at": now.isoformat(),
            }
        file_size = self._database_file_size()
        with self.connect() as connection:
            row_counts = _row_counts(connection)
            candidates = _retention_candidates(connection, evaluated_at=now)
            page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            freelist_count = int(
                connection.execute("PRAGMA freelist_count").fetchone()[0]
            )
        return {
            "status": (
                "attention"
                if file_size > int(MAX_DATABASE_BYTES * 0.9)
                else "ready"
            ),
            "database_size_bytes": file_size,
            "maximum_database_bytes": MAX_DATABASE_BYTES,
            "size_utilization_ratio": round(file_size / MAX_DATABASE_BYTES, 6),
            "page_size_bytes": page_size,
            "page_count": page_count,
            "freelist_page_count": freelist_count,
            "row_counts": row_counts,
            "retention_policy": _retention_policy(),
            "maintenance_candidates": candidates,
            "checked_at": now.isoformat(),
        }

    def maintain_database(
        self,
        *,
        evaluated_at: datetime,
        apply: bool = False,
        vacuum: bool = False,
    ) -> dict[str, object]:
        """Preview or apply the fixed retention policy.

        The default is read-only. Applying deletion/compaction is an explicit
        operator boundary; VACUUM is separately explicit.
        """

        if evaluated_at.tzinfo is None:
            raise LeanRadarStoreError("maintenance time must be timezone-aware")
        now = evaluated_at.astimezone(timezone.utc)
        if vacuum and not apply:
            raise LeanRadarStoreError("VACUUM requires confirmed maintenance")
        if not self.exists():
            return {
                "status": "setup_required",
                "apply_requested": apply,
                "vacuum_requested": vacuum,
                "database_size_bytes_before": 0,
                "database_size_bytes_after": 0,
                "retention_policy": _retention_policy(),
                "provider_call_attempted": False,
                "telegram_send_attempted": False,
                "research_only": True,
            }
        before_size = self._database_file_size()
        if not apply:
            with self.connect() as connection:
                candidates = _retention_candidates(connection, evaluated_at=now)
                counts = _row_counts(connection)
            return {
                "status": "dry_run",
                "checked_at": now.isoformat(),
                "apply_requested": False,
                "vacuum_requested": False,
                "database_size_bytes_before": before_size,
                "database_size_bytes_after": before_size,
                "row_counts_before": counts,
                "row_counts_after": counts,
                "maintenance_candidates": candidates,
                "changes": {key: 0 for key in candidates},
                "retention_policy": _retention_policy(),
                "provider_call_attempted": False,
                "telegram_send_attempted": False,
                "research_only": True,
            }
        with self.connect(write=True) as connection:
            before_counts = _row_counts(connection)
            candidates = _retention_candidates(connection, evaluated_at=now)
            changes = _apply_retention(connection, evaluated_at=now)
            connection.commit()
            if vacuum:
                connection.execute("VACUUM")
            after_counts = _row_counts(connection)
        after_size = self._database_file_size()
        return {
            "status": "complete",
            "checked_at": now.isoformat(),
            "apply_requested": True,
            "vacuum_requested": vacuum,
            "database_size_bytes_before": before_size,
            "database_size_bytes_after": after_size,
            "database_bytes_reclaimed": max(0, before_size - after_size),
            "row_counts_before": before_counts,
            "row_counts_after": after_counts,
            "maintenance_candidates": candidates,
            "changes": changes,
            "retention_policy": _retention_policy(),
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
        }

    def upsert_calendar_events(
        self,
        events: Sequence[CalendarEvent],
        *,
        imported_at: datetime | None = None,
    ) -> None:
        if not events:
            raise LeanRadarStoreError("refusing to import an empty calendar snapshot")
        source_names = {row.source_name for row in events}
        source_times = {row.source_observed_at for row in events}
        source_modes = {row.source_mode for row in events}
        source_hashes = {row.source_sha256 for row in events}
        if any(
            len(values) != 1
            for values in (source_names, source_times, source_modes, source_hashes)
        ):
            raise LeanRadarStoreError("calendar source identity is inconsistent")
        imported = (imported_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        payloads = [
            json.dumps(
                row.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            for row in events
        ]
        metadata = {
            "calendar_last_imported_at": imported.isoformat(),
            "calendar_source_name": next(iter(source_names)),
            "calendar_source_observed_at": next(iter(source_times)),
            "calendar_source_mode": next(iter(source_modes)),
            "calendar_source_sha256": next(iter(source_hashes)),
            "calendar_last_import_event_count": str(len(events)),
        }
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.executemany(
                    """
                    INSERT INTO calendar_events (event_id, event_time, payload_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        event_time = excluded.event_time,
                        payload_json = excluded.payload_json
                    """,
                    [
                        (row.event_id, row.starts_at, payload)
                        for row, payload in zip(events, payloads)
                    ],
                )
                connection.executemany(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    sorted(metadata.items()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def calendar_status(
        self,
        *,
        evaluated_at: datetime | None = None,
    ) -> dict[str, object]:
        now = (evaluated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if not self.exists():
            return {
                "status": "missing",
                "event_count": 0,
                "upcoming_event_count": 0,
                "next_event_at": None,
                "source_mode": "unavailable",
                "source_observed_at": None,
            }
        with self.connect() as connection:
            count = int(
                connection.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]
            )
            upcoming_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM calendar_events WHERE event_time >= ?",
                    (now.isoformat(),),
                ).fetchone()[0]
            )
            next_row = connection.execute(
                """
                SELECT event_time FROM calendar_events
                WHERE event_time >= ? ORDER BY event_time, event_id LIMIT 1
                """,
                (now.isoformat(),),
            ).fetchone()
            metadata = dict(
                connection.execute(
                    "SELECT key, value FROM meta WHERE key LIKE 'calendar_%'"
                ).fetchall()
            )
        return {
            "status": "ready" if upcoming_count else "no_upcoming" if count else "empty",
            "event_count": count,
            "upcoming_event_count": upcoming_count,
            "next_event_at": next_row["event_time"] if next_row else None,
            "source_name": metadata.get("calendar_source_name"),
            "source_mode": metadata.get("calendar_source_mode", "unavailable"),
            "source_observed_at": metadata.get("calendar_source_observed_at"),
            "source_sha256": metadata.get("calendar_source_sha256"),
            "last_imported_at": metadata.get("calendar_last_imported_at"),
            "last_import_event_count": int(
                metadata.get("calendar_last_import_event_count", "0")
            ),
        }

    def list_calendar_events(
        self,
        *,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> tuple[CalendarEvent, ...]:
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise LeanRadarStoreError("calendar query window is invalid")
        if not self.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM calendar_events
                WHERE event_time >= ? AND event_time <= ?
                ORDER BY event_time, event_id LIMIT ?
                """,
                (
                    start.astimezone(timezone.utc).isoformat(),
                    end.astimezone(timezone.utc).isoformat(),
                    max(1, min(limit, 1_000)),
                ),
            ).fetchall()
        events: list[CalendarEvent] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                raise LeanRadarStoreError("stored calendar event is invalid")
            payload["affected_symbols"] = tuple(payload.get("affected_symbols", ()))
            events.append(CalendarEvent(**payload))
        return tuple(events)

    def snapshot_history(
        self,
        canonical_asset_id: str,
        *,
        before: str,
        limit: int = 128,
    ) -> tuple[dict[str, object], ...]:
        if not self.exists():
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
        return self.health_status("scan")

    def health_status(self, component: str) -> dict[str, object] | None:
        if not isinstance(component, str) or not component.strip() or len(component) > 64:
            raise LeanRadarStoreError("health component is invalid")
        if not self.exists():
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM system_health WHERE component = ?",
                (component.strip(),),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise LeanRadarStoreError("stored health is invalid")
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
        *,
        outcomes: Sequence[LeanOutcome] = (),
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
        outcome_payloads = [
            json.dumps(row.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
            for row in outcomes
        ]
        idea_ids = {row.idea_id for row in ideas}
        if any(row.idea_id not in idea_ids for row in outcomes):
            raise LeanRadarStoreError("scan outcome does not belong to a current idea")
        health_json = json.dumps(
            dict(health), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        retention_time = _stored_aware_time(
            checked_at,
            label="scan health",
        )
        assert retention_time is not None
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
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO outcomes (
                        idea_id, horizon, observed_at, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (row.idea_id, row.horizon, row.end_observed_at, payload)
                        for row, payload in zip(outcomes, outcome_payloads)
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
                _apply_retention(connection, evaluated_at=retention_time)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def record_cycle_receipt(
        self,
        receipt: Mapping[str, object],
    ) -> None:
        cycle_id = receipt.get("cycle_id")
        attempted_at = receipt.get("attempted_at")
        completed_at = receipt.get("completed_at")
        trigger = receipt.get("trigger")
        status = receipt.get("status")
        if (
            not isinstance(cycle_id, str)
            or not cycle_id.startswith("lean-cycle-")
            or len(cycle_id) > 96
            or not isinstance(attempted_at, str)
            or not isinstance(completed_at, str)
            or trigger not in {"manual", "scheduled"}
            or status not in {"complete", "waiting", "blocked", "failed"}
            or receipt.get("schema_version") != "lean_cycle_receipt_v1"
            or receipt.get("no_send") is not True
            or receipt.get("research_only") is not True
            or not set(receipt).issubset(_CYCLE_RECEIPT_FIELDS)
        ):
            raise LeanRadarStoreError("cycle receipt identity is invalid")
        attempted = _stored_aware_time(attempted_at, label="cycle attempt")
        completed = _stored_aware_time(completed_at, label="cycle completion")
        assert attempted is not None and completed is not None
        if completed < attempted or completed - attempted > timedelta(hours=1):
            raise LeanRadarStoreError("cycle receipt clock is invalid")
        payload = json.dumps(
            dict(receipt),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(payload.encode("utf-8")) > MAX_CYCLE_RECEIPT_BYTES:
            raise LeanRadarStoreError("cycle receipt exceeds its size bound")
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO cycle_receipts (
                        cycle_id, attempted_at, completed_at,
                        trigger, status, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_id,
                        attempted_at,
                        completed_at,
                        trigger,
                        status,
                        payload,
                    ),
                )
                _trim_cycle_receipts(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list_cycle_receipts(
        self,
        *,
        limit: int = 32,
    ) -> tuple[dict[str, object], ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_CYCLE_RECEIPTS
        ):
            raise LeanRadarStoreError("cycle receipt limit is invalid")
        if not self.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM cycle_receipts
                ORDER BY completed_at DESC, cycle_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        receipts: list[dict[str, object]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != "lean_cycle_receipt_v1"
            ):
                raise LeanRadarStoreError("stored cycle receipt is invalid")
            receipts.append(payload)
        return tuple(receipts)

    def list_active_ideas(self) -> tuple[dict[str, object], ...]:
        return self.list_ideas(active_only=True)

    def list_ideas(
        self,
        *,
        active_only: bool = False,
    ) -> tuple[dict[str, object], ...]:
        if not self.exists():
            return ()
        where = "WHERE active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM ideas {where} ORDER BY created_at DESC, idea_id"
            ).fetchall()
        return tuple(
            payload
            for row in rows
            if isinstance((payload := json.loads(row["payload_json"])), dict)
        )

    def list_outcomes(self) -> tuple[dict[str, object], ...]:
        if not self.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM outcomes
                ORDER BY idea_id, horizon
                """
            ).fetchall()
        return tuple(
            payload
            for row in rows
            if isinstance((payload := json.loads(row["payload_json"])), dict)
        )

    def notification_states(self) -> dict[str, dict[str, object]]:
        """Return bounded, secret-free delivery state keyed by visible family."""

        if not self.exists():
            return {}
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT visible_family, last_notified_at, last_material_digest,
                       payload_json
                FROM notification_state
                ORDER BY visible_family LIMIT 1001
                """
            ).fetchall()
        if len(rows) > 1000:
            raise LeanRadarStoreError("notification state exceeds the bounded runtime")
        states: dict[str, dict[str, object]] = {}
        for row in rows:
            family = row["visible_family"]
            notified_at = row["last_notified_at"]
            material_digest = row["last_material_digest"]
            payload = json.loads(row["payload_json"])
            if (
                not isinstance(family, str)
                or not family
                or not isinstance(payload, dict)
                or payload.get("visible_family") != family
                or payload.get("schema_version") != "lean_notification_state_v1"
                or not isinstance(notified_at, str)
                or payload.get("last_notified_at") != notified_at
                or not isinstance(material_digest, str)
                or len(material_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in material_digest
                )
                or payload.get("material_digest") != material_digest
                or not isinstance(payload.get("material_snapshot"), dict)
            ):
                raise LeanRadarStoreError("stored notification state is invalid")
            states[family] = {
                **payload,
                "last_notified_at": notified_at,
                "last_material_digest": material_digest,
            }
        return states

    def record_notification_deliveries(
        self,
        updates: Sequence[Mapping[str, object]],
        *,
        delivered_at: datetime,
    ) -> None:
        """Record only fully delivered visible families in one transaction."""

        if delivered_at.tzinfo is None:
            raise LeanRadarStoreError("notification delivery time must be timezone-aware")
        when = delivered_at.astimezone(timezone.utc).isoformat()
        rows: list[tuple[str, str, str, str]] = []
        seen: set[str] = set()
        for update in updates:
            family = update.get("visible_family")
            digest = update.get("material_digest")
            snapshot = update.get("material_snapshot")
            message_type = update.get("message_type")
            if (
                not isinstance(family, str)
                or not family
                or len(family) > 160
                or family in seen
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or not isinstance(snapshot, Mapping)
                or not isinstance(message_type, str)
            ):
                raise LeanRadarStoreError("notification delivery state is invalid")
            seen.add(family)
            payload = {
                "schema_version": "lean_notification_state_v1",
                "visible_family": family,
                "message_type": message_type,
                "material_digest": digest,
                "material_snapshot": dict(snapshot),
                "last_delivery_status": "delivered",
                "last_notified_at": when,
                "research_only": True,
            }
            rows.append(
                (
                    family,
                    when,
                    digest,
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                )
            )
        if not rows:
            return
        with self.connect(write=True) as connection:
            connection.executemany(
                """
                INSERT INTO notification_state (
                    visible_family, last_notified_at,
                    last_material_digest, payload_json
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(visible_family) DO UPDATE SET
                    last_notified_at = excluded.last_notified_at,
                    last_material_digest = excluded.last_material_digest,
                    payload_json = excluded.payload_json
                """,
                rows,
            )
            _apply_notification_retention(
                connection,
                evaluated_at=delivered_at.astimezone(timezone.utc),
            )
            connection.commit()

    def acquire_notification_send_lock(
        self,
        *,
        acquired_at: datetime,
        lease_seconds: int = 600,
    ) -> str | None:
        """Claim one expiring local send lease; never stores recipient data."""

        if acquired_at.tzinfo is None or not 30 <= lease_seconds <= 3600:
            raise LeanRadarStoreError("notification send lease is invalid")
        now = acquired_at.astimezone(timezone.utc)
        owner = uuid4().hex
        expires = datetime.fromtimestamp(
            now.timestamp() + lease_seconds,
            tz=timezone.utc,
        )
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT value FROM meta WHERE key = 'lean_telegram_send_lock'"
                ).fetchone()
                if row is not None:
                    try:
                        current = json.loads(row["value"])
                        active_until = datetime.fromisoformat(
                            str(current.get("expires_at", "")).replace("Z", "+00:00")
                        )
                    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        connection.rollback()
                        raise LeanRadarStoreError(
                            "notification send lock is invalid"
                        ) from exc
                    if active_until.tzinfo is None:
                        connection.rollback()
                        raise LeanRadarStoreError(
                            "notification send lock is invalid"
                        )
                    if active_until > now:
                        connection.rollback()
                        return None
                value = json.dumps(
                    {
                        "owner": owner,
                        "acquired_at": now.isoformat(),
                        "expires_at": expires.isoformat(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("lean_telegram_send_lock", value),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return owner

    def release_notification_send_lock(self, owner: str) -> bool:
        if not isinstance(owner, str) or len(owner) != 32:
            raise LeanRadarStoreError("notification send lock owner is invalid")
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT value FROM meta WHERE key = 'lean_telegram_send_lock'"
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return False
                try:
                    value = json.loads(row["value"])
                except json.JSONDecodeError:
                    connection.rollback()
                    return False
                if not isinstance(value, dict) or value.get("owner") != owner:
                    connection.rollback()
                    return False
                connection.execute(
                    "DELETE FROM meta WHERE key = 'lean_telegram_send_lock'"
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return True

    def snapshot_window(
        self,
        canonical_asset_id: str,
        *,
        start: str,
        end: str,
        limit: int = 1_024,
    ) -> tuple[dict[str, object], ...]:
        if not self.exists():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM market_snapshots
                WHERE canonical_asset_id = ?
                  AND observed_at >= ? AND observed_at <= ?
                ORDER BY observed_at, canonical_asset_id LIMIT ?
                """,
                (canonical_asset_id, start, end, max(1, min(limit, 4_096))),
            ).fetchall()
        return tuple(
            payload
            for row in rows
            if isinstance((payload := json.loads(row["payload_json"])), dict)
        )

    def write_outcomes(
        self,
        outcomes: Sequence[LeanOutcome],
        *,
        idea_statuses: Mapping[str, str],
        health: Mapping[str, object],
    ) -> None:
        checked_at = health.get("checked_at")
        status = health.get("status")
        if not isinstance(checked_at, str) or not isinstance(status, str):
            raise LeanRadarStoreError("outcome health identity is invalid")
        if any(value not in IDEA_OUTCOME_STATES for value in idea_statuses.values()):
            raise LeanRadarStoreError("idea outcome status is invalid")
        payloads = [
            json.dumps(row.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
            for row in outcomes
        ]
        health_json = json.dumps(
            dict(health), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        with self.connect(write=True) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.executemany(
                    """
                    INSERT INTO outcomes (idea_id, horizon, observed_at, payload_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(idea_id, horizon) DO UPDATE SET
                        observed_at = excluded.observed_at,
                        payload_json = excluded.payload_json
                    """,
                    [
                        (row.idea_id, row.horizon, row.end_observed_at, payload)
                        for row, payload in zip(outcomes, payloads)
                    ],
                )
                for idea_id, outcome_status in sorted(idea_statuses.items()):
                    row = connection.execute(
                        "SELECT payload_json FROM ideas WHERE idea_id = ?",
                        (idea_id,),
                    ).fetchone()
                    if row is None:
                        raise LeanRadarStoreError("outcome references a missing idea")
                    idea_payload = json.loads(row["payload_json"])
                    if not isinstance(idea_payload, dict) or idea_payload.get("idea_id") != idea_id:
                        raise LeanRadarStoreError("stored idea identity is invalid")
                    idea_payload["outcome_status"] = outcome_status
                    connection.execute(
                        "UPDATE ideas SET payload_json = ? WHERE idea_id = ?",
                        (
                            json.dumps(
                                idea_payload,
                                sort_keys=True,
                                separators=(",", ":"),
                                allow_nan=False,
                            ),
                            idea_id,
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO system_health (component, checked_at, status, payload_json)
                    VALUES ('outcomes', ?, ?, ?)
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

    def _database_file_size(self) -> int:
        try:
            with anchored_path(self.path) as anchored:
                info = anchored.stat_leaf()
                assert info is not None
                require_regular_single_link(
                    info,
                    maximum_bytes=MAX_DATABASE_BYTES,
                )
                return int(info.st_size)
        except LeanPathSecurityError as exc:
            raise LeanRadarStoreError(
                "lean radar database path is unsafe"
            ) from exc

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
                CREATE TABLE cycle_receipts (
                    cycle_id TEXT PRIMARY KEY,
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                PRAGMA user_version = 2;
                """
            )
            connection.commit()
        elif current == 1:
            connection.executescript(
                """
                CREATE TABLE cycle_receipts (
                    cycle_id TEXT PRIMARY KEY,
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                PRAGMA user_version = 2;
                """
            )
            connection.commit()
        elif current != SCHEMA_VERSION:
            raise LeanRadarStoreError("lean radar database migration is incomplete")

    def _open_lock(self, anchored: AnchoredPath, *, create: bool) -> int:
        lock_name = f".{anchored.leaf}.lock"
        flags = (
            os.O_RDWR
            | getattr(os, "O_CLOEXEC", 0)
            | _required_os_flag("O_NOFOLLOW")
        )
        if create:
            flags |= os.O_CREAT
        try:
            before = os.stat(
                lock_name,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            before = None
        except OSError as exc:
            raise LeanRadarStoreError("lean radar database lock is unavailable") from exc
        if before is None and not create:
            raise LeanRadarStoreError("lean radar database lock is missing")
        try:
            descriptor = os.open(
                lock_name,
                flags,
                0o600,
                dir_fd=anchored.parent_fd,
            )
        except OSError as exc:
            raise LeanRadarStoreError(
                "lean radar database lock could not be opened safely"
            ) from exc
        try:
            opened = os.fstat(descriptor)
            require_regular_single_link(opened, maximum_bytes=4_096)
            if opened.st_size:
                raise LeanRadarStoreError("lean radar database lock is not empty")
            os.fchmod(descriptor, 0o600)
            named = os.stat(
                lock_name,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
            if (
                (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
                or before is not None
                and (before.st_dev, before.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                raise LeanRadarStoreError(
                    "lean radar database lock identity changed"
                )
            anchored.verify_parent_chain()
        except Exception:
            os.close(descriptor)
            raise
        return descriptor

    def _publish_database(
        self,
        anchored: AnchoredPath,
        payload: bytes,
        *,
        original: _SecureBytes | None,
    ) -> None:
        current = read_regular_bytes_at(
            anchored,
            maximum_bytes=MAX_DATABASE_BYTES,
            missing_ok=True,
        )
        if original is None:
            if current is not None:
                raise LeanRadarStoreError(
                    "lean radar database appeared during write"
                )
        elif (
            current is None
            or current.device != original.device
            or current.inode != original.inode
            or current.sha256 != original.sha256
            or current.size_bytes != original.size_bytes
        ):
            raise LeanRadarStoreError("lean radar database changed during write")

        temporary = f".{anchored.leaf}.tmp-{uuid4().hex}"
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | _required_os_flag("O_NOFOLLOW")
        )
        descriptor = os.open(
            temporary,
            flags,
            0o600,
            dir_fd=anchored.parent_fd,
        )
        published = False
        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                count = os.write(descriptor, view[written:])
                if count <= 0:
                    raise LeanRadarStoreError(
                        "lean radar database write made no progress"
                    )
                written += count
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
            staged = os.fstat(descriptor)
            require_regular_single_link(staged, maximum_bytes=MAX_DATABASE_BYTES)
            if staged.st_size != len(payload):
                raise LeanRadarStoreError("lean radar database staging is incomplete")
            named_stage = os.stat(
                temporary,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
            if (named_stage.st_dev, named_stage.st_ino) != (
                staged.st_dev,
                staged.st_ino,
            ):
                raise LeanRadarStoreError(
                    "lean radar database staging identity changed"
                )
            anchored.verify_parent_chain()
            latest = read_regular_bytes_at(
                anchored,
                maximum_bytes=MAX_DATABASE_BYTES,
                missing_ok=True,
            )
            if original is None:
                if latest is not None:
                    raise LeanRadarStoreError(
                        "lean radar database appeared before publication"
                    )
            elif (
                latest is None
                or latest.device != original.device
                or latest.inode != original.inode
                or latest.sha256 != original.sha256
            ):
                raise LeanRadarStoreError(
                    "lean radar database changed before publication"
                )
            os.replace(
                temporary,
                anchored.leaf,
                src_dir_fd=anchored.parent_fd,
                dst_dir_fd=anchored.parent_fd,
            )
            published = True
            final_named = os.stat(
                anchored.leaf,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
            if (final_named.st_dev, final_named.st_ino) != (
                staged.st_dev,
                staged.st_ino,
            ):
                raise LeanRadarStoreError(
                    "lean radar database publication identity changed"
                )
            anchored.verify_parent_chain()
            os.fsync(anchored.parent_fd)
        finally:
            os.close(descriptor)
            if not published:
                self._unlink_owned_temporary(
                    anchored,
                    temporary,
                    expected=locals().get("staged"),
                )
        verified = read_regular_bytes_at(
            anchored,
            maximum_bytes=MAX_DATABASE_BYTES,
        )
        assert verified is not None
        if (
            verified.size_bytes != len(payload)
            or verified.sha256 != hashlib.sha256(payload).hexdigest()
        ):
            raise LeanRadarStoreError(
                "lean radar database publication verification failed"
            )

    @staticmethod
    def _verify_lock(anchored: AnchoredPath, descriptor: int) -> None:
        opened = os.fstat(descriptor)
        named = os.stat(
            f".{anchored.leaf}.lock",
            dir_fd=anchored.parent_fd,
            follow_symlinks=False,
        )
        require_regular_single_link(named, maximum_bytes=4_096)
        if (
            (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or named.st_size != 0
        ):
            raise LeanRadarStoreError(
                "lean radar database lock changed during operation"
            )

    @staticmethod
    def _unlink_owned_temporary(
        anchored: AnchoredPath,
        name: str,
        *,
        expected: os.stat_result | None,
    ) -> None:
        if expected is None:
            return
        try:
            current = os.stat(
                name,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) == (expected.st_dev, expected.st_ino):
            os.unlink(name, dir_fd=anchored.parent_fd)


def _required_os_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not isinstance(value, int) or value == 0:
        raise LeanRadarStoreError(f"platform lacks required {name} support")
    return value


def _row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in _RUNTIME_TABLES
    }


def _retention_policy() -> dict[str, object]:
    return {
        "full_snapshot_detail_days": int(
            SNAPSHOT_FULL_DETAIL_RETENTION.total_seconds() // 86_400
        ),
        "snapshot_history_days": int(
            SNAPSHOT_RETENTION.total_seconds() // 86_400
        ),
        "idea_outcome_days": int(
            IDEA_OUTCOME_RETENTION.total_seconds() // 86_400
        ),
        "calendar_history_days": int(
            CALENDAR_HISTORY_RETENTION.total_seconds() // 86_400
        ),
        "notification_state_days": int(
            NOTIFICATION_RETENTION.total_seconds() // 86_400
        ),
        "maximum_notification_states": MAX_NOTIFICATION_STATES,
        "maximum_cycle_receipts": MAX_CYCLE_RECEIPTS,
        "maximum_database_bytes": MAX_DATABASE_BYTES,
        "automatic_after_successful_scan": True,
    }


def _retention_candidates(
    connection: sqlite3.Connection,
    *,
    evaluated_at: datetime,
) -> dict[str, int]:
    snapshot_full_cutoff = (
        evaluated_at - SNAPSHOT_FULL_DETAIL_RETENTION
    ).isoformat()
    snapshot_delete_cutoff = (evaluated_at - SNAPSHOT_RETENTION).isoformat()
    idea_cutoff = (evaluated_at - IDEA_OUTCOME_RETENTION).isoformat()
    calendar_cutoff = (evaluated_at - CALENDAR_HISTORY_RETENTION).isoformat()
    notification_cutoff = (evaluated_at - NOTIFICATION_RETENTION).isoformat()
    expired_notifications = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM notification_state
            WHERE last_notified_at IS NOT NULL AND last_notified_at < ?
            """,
            (notification_cutoff,),
        ).fetchone()[0]
    )
    notification_total = int(
        connection.execute("SELECT COUNT(*) FROM notification_state").fetchone()[0]
    )
    receipt_total = int(
        connection.execute("SELECT COUNT(*) FROM cycle_receipts").fetchone()[0]
    )
    return {
        "snapshots_to_compact": int(
            connection.execute(
                """
                SELECT COUNT(*) FROM market_snapshots
                WHERE observed_at < ? AND observed_at >= ?
                  AND json_array_length(payload_json, '$.sparkline_prices') > 0
                """,
                (snapshot_full_cutoff, snapshot_delete_cutoff),
            ).fetchone()[0]
        ),
        "snapshots_to_delete": int(
            connection.execute(
                "SELECT COUNT(*) FROM market_snapshots WHERE observed_at < ?",
                (snapshot_delete_cutoff,),
            ).fetchone()[0]
        ),
        "ideas_to_delete": int(
            connection.execute(
                """
                SELECT COUNT(*) FROM ideas
                WHERE created_at < ? AND active = 0
                """,
                (idea_cutoff,),
            ).fetchone()[0]
        ),
        "outcomes_to_delete": int(
            connection.execute(
                """
                SELECT COUNT(*) FROM outcomes
                WHERE idea_id IN (
                    SELECT idea_id FROM ideas
                    WHERE created_at < ? AND active = 0
                )
                """,
                (idea_cutoff,),
            ).fetchone()[0]
        ),
        "calendar_events_to_delete": int(
            connection.execute(
                "SELECT COUNT(*) FROM calendar_events WHERE event_time < ?",
                (calendar_cutoff,),
            ).fetchone()[0]
        ),
        "notification_states_to_expire": expired_notifications,
        "notification_states_over_cap": max(
            0,
            notification_total
            - expired_notifications
            - MAX_NOTIFICATION_STATES,
        ),
        "cycle_receipts_over_cap": max(
            0,
            receipt_total - MAX_CYCLE_RECEIPTS,
        ),
    }


def _apply_retention(
    connection: sqlite3.Connection,
    *,
    evaluated_at: datetime,
) -> dict[str, int]:
    snapshot_full_cutoff = (
        evaluated_at - SNAPSHOT_FULL_DETAIL_RETENTION
    ).isoformat()
    snapshot_delete_cutoff = (evaluated_at - SNAPSHOT_RETENTION).isoformat()
    idea_cutoff = (evaluated_at - IDEA_OUTCOME_RETENTION).isoformat()
    calendar_cutoff = (evaluated_at - CALENDAR_HISTORY_RETENTION).isoformat()
    compact_rows = connection.execute(
        """
        SELECT canonical_asset_id, observed_at, payload_json
        FROM market_snapshots
        WHERE observed_at < ? AND observed_at >= ?
          AND json_array_length(payload_json, '$.sparkline_prices') > 0
        ORDER BY observed_at, canonical_asset_id
        """,
        (snapshot_full_cutoff, snapshot_delete_cutoff),
    ).fetchall()
    compact_updates: list[tuple[str, str, str]] = []
    for row in compact_rows:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError as exc:
            raise LeanRadarStoreError(
                "stored snapshot cannot be compacted safely"
            ) from exc
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("sparkline_prices"), list)
        ):
            raise LeanRadarStoreError(
                "stored snapshot cannot be compacted safely"
            )
        payload["sparkline_prices"] = []
        compact_updates.append(
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                row["canonical_asset_id"],
                row["observed_at"],
            )
        )
    connection.executemany(
        """
        UPDATE market_snapshots SET payload_json = ?
        WHERE canonical_asset_id = ? AND observed_at = ?
        """,
        compact_updates,
    )
    snapshot_deleted = connection.execute(
        "DELETE FROM market_snapshots WHERE observed_at < ?",
        (snapshot_delete_cutoff,),
    ).rowcount
    outcome_deleted = connection.execute(
        """
        DELETE FROM outcomes
        WHERE idea_id IN (
            SELECT idea_id FROM ideas
            WHERE created_at < ? AND active = 0
        )
        """,
        (idea_cutoff,),
    ).rowcount
    idea_deleted = connection.execute(
        "DELETE FROM ideas WHERE created_at < ? AND active = 0",
        (idea_cutoff,),
    ).rowcount
    calendar_deleted = connection.execute(
        "DELETE FROM calendar_events WHERE event_time < ?",
        (calendar_cutoff,),
    ).rowcount
    notification_changes = _apply_notification_retention(
        connection,
        evaluated_at=evaluated_at,
    )
    receipt_deleted = _trim_cycle_receipts(connection)
    return {
        "snapshots_compacted": len(compact_updates),
        "snapshots_deleted": max(0, snapshot_deleted),
        "outcomes_deleted": max(0, outcome_deleted),
        "ideas_deleted": max(0, idea_deleted),
        "calendar_events_deleted": max(0, calendar_deleted),
        **notification_changes,
        "cycle_receipts_deleted": receipt_deleted,
    }


def _apply_notification_retention(
    connection: sqlite3.Connection,
    *,
    evaluated_at: datetime,
) -> dict[str, int]:
    cutoff = (evaluated_at - NOTIFICATION_RETENTION).isoformat()
    expired = connection.execute(
        """
        DELETE FROM notification_state
        WHERE last_notified_at IS NOT NULL AND last_notified_at < ?
        """,
        (cutoff,),
    ).rowcount
    over_cap = int(
        connection.execute("SELECT COUNT(*) FROM notification_state").fetchone()[0]
    ) - MAX_NOTIFICATION_STATES
    capped = 0
    if over_cap > 0:
        capped = connection.execute(
            """
            DELETE FROM notification_state
            WHERE visible_family IN (
                SELECT visible_family FROM notification_state
                ORDER BY
                    CASE WHEN last_notified_at IS NULL THEN 0 ELSE 1 END,
                    last_notified_at,
                    visible_family
                LIMIT ?
            )
            """,
            (over_cap,),
        ).rowcount
    return {
        "notification_states_expired": max(0, expired),
        "notification_states_capped": max(0, capped),
    }


def _trim_cycle_receipts(connection: sqlite3.Connection) -> int:
    over_cap = int(
        connection.execute("SELECT COUNT(*) FROM cycle_receipts").fetchone()[0]
    ) - MAX_CYCLE_RECEIPTS
    if over_cap <= 0:
        return 0
    deleted = connection.execute(
        """
        DELETE FROM cycle_receipts
        WHERE cycle_id IN (
            SELECT cycle_id FROM cycle_receipts
            ORDER BY completed_at, cycle_id LIMIT ?
        )
        """,
        (over_cap,),
    ).rowcount
    return max(0, deleted)


def _stored_aware_time(
    value: object,
    *,
    label: str,
    missing_ok: bool = False,
) -> datetime | None:
    if value is None and missing_ok:
        return None
    if not isinstance(value, str):
        raise LeanRadarStoreError(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanRadarStoreError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanRadarStoreError(f"{label} timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = (
    "BYBIT_CATALOG_MAXIMUM_AGE",
    "BYBIT_CATALOG_RECOMMENDED_AGE",
    "CALENDAR_HISTORY_RETENTION",
    "IDEA_OUTCOME_RETENTION",
    "MAX_CYCLE_RECEIPT_BYTES",
    "MAX_CYCLE_RECEIPTS",
    "MAX_DATABASE_BYTES",
    "MAX_NOTIFICATION_STATES",
    "NOTIFICATION_RETENTION",
    "SCHEMA_VERSION",
    "SNAPSHOT_FULL_DETAIL_RETENTION",
    "SNAPSHOT_RETENTION",
    "LeanRadarStore",
    "LeanRadarStoreError",
)
