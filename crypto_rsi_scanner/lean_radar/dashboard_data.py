"""Bounded, single-transaction read model for the Lean Radar dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Mapping

from .freshness import market_scan_freshness
from .models import CalendarEvent, LeanIdea, LeanOutcome, MarketSnapshot
from .store import SCHEMA_VERSION, LeanRadarStore, LeanRadarStoreError


MAX_IDEAS = 500
MAX_OUTCOMES = MAX_IDEAS * 4
MAX_MARKETS = 250
MAX_CALENDAR_EVENTS = 500
MAX_IDEA_HISTORY_POINTS = 512
_IDEA_ID = re.compile(r"^lean-[a-z0-9-]{3,96}$")


class _LeanDashboardDataError(RuntimeError):
    """Raised when the SQLite read model cannot be rendered truthfully."""


LeanDashboardDataError = _LeanDashboardDataError


@dataclass(frozen=True)
class _LeanDashboardState:
    loaded_at: datetime
    catalog_count: int
    catalog_source_mode: str
    catalog_observed_at: str | None
    watchlist_count: int
    market_idea_freshness: str
    suppressed_active_idea_count: int
    active_ideas: tuple[LeanIdea, ...]
    recent_ideas: tuple[LeanIdea, ...]
    latest_snapshots: tuple[MarketSnapshot, ...]
    calendar_events: tuple[CalendarEvent, ...]
    outcomes: tuple[LeanOutcome, ...]
    health: Mapping[str, Mapping[str, object]]
    truncated_sections: tuple[str, ...]

    @property
    def health_status(self) -> Mapping[str, object] | None:
        return self.health.get("operator")

    @property
    def scan_status(self) -> Mapping[str, object] | None:
        return self.health.get("scan")

    @property
    def outcome_status(self) -> Mapping[str, object] | None:
        return self.health.get("outcomes")


@dataclass(frozen=True)
class _LeanIdeaDetail:
    idea: LeanIdea
    market_history: tuple[MarketSnapshot, ...]
    outcomes: tuple[LeanOutcome, ...]


def load_dashboard_state(
    store: LeanRadarStore,
    *,
    evaluated_at: datetime | None = None,
) -> _LeanDashboardState:
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LeanDashboardDataError("dashboard clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if not store.path.exists():
        raise LeanDashboardDataError("Lean Radar runtime is not initialized")
    try:
        with store.connect() as connection:
            connection.execute("BEGIN")
            _require_schema(connection)
            catalog_count = int(
                connection.execute("SELECT COUNT(*) FROM bybit_instruments").fetchone()[0]
            )
            watchlist_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM manual_watchlist WHERE enabled = 1"
                ).fetchone()[0]
            )
            metadata = dict(
                connection.execute(
                    """
                    SELECT key, value FROM meta
                    WHERE key IN (
                        'bybit_catalog_source_mode',
                        'bybit_catalog_source_observed_at'
                    )
                    """
                ).fetchall()
            )
            idea_count = int(connection.execute("SELECT COUNT(*) FROM ideas").fetchone()[0])
            idea_rows = connection.execute(
                """
                SELECT active, payload_json FROM ideas
                ORDER BY created_at DESC, idea_id LIMIT ?
                """,
                (MAX_IDEAS,),
            ).fetchall()
            snapshot_count = int(
                connection.execute(
                    "SELECT COUNT(DISTINCT canonical_asset_id) FROM market_snapshots"
                ).fetchone()[0]
            )
            snapshot_rows = connection.execute(
                """
                SELECT current.payload_json
                FROM market_snapshots AS current
                JOIN (
                    SELECT canonical_asset_id, MAX(observed_at) AS observed_at
                    FROM market_snapshots GROUP BY canonical_asset_id
                ) AS latest
                  ON current.canonical_asset_id = latest.canonical_asset_id
                 AND current.observed_at = latest.observed_at
                ORDER BY current.canonical_asset_id LIMIT ?
                """,
                (MAX_MARKETS,),
            ).fetchall()
            outcome_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM outcomes
                    WHERE idea_id IN (
                        SELECT idea_id FROM ideas
                        ORDER BY created_at DESC, idea_id LIMIT ?
                    )
                    """,
                    (MAX_IDEAS,),
                ).fetchone()[0]
            )
            outcome_rows = connection.execute(
                """
                SELECT payload_json FROM outcomes
                WHERE idea_id IN (
                    SELECT idea_id FROM ideas
                    ORDER BY created_at DESC, idea_id LIMIT ?
                )
                ORDER BY idea_id, horizon LIMIT ?
                """,
                (MAX_IDEAS, MAX_OUTCOMES),
            ).fetchall()
            calendar_count = int(
                connection.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]
            )
            calendar_rows = connection.execute(
                """
                SELECT payload_json FROM calendar_events
                ORDER BY event_time, event_id LIMIT ?
                """,
                (MAX_CALENDAR_EVENTS,),
            ).fetchall()
            health_rows = connection.execute(
                """
                SELECT component, payload_json FROM system_health
                ORDER BY component LIMIT 32
                """
            ).fetchall()
    except (LeanRadarStoreError, sqlite3.Error, OSError) as exc:
        raise LeanDashboardDataError("Lean Radar runtime could not be read") from exc

    recent_ideas: list[LeanIdea] = []
    active_ids: set[str] = set()
    for row in idea_rows:
        idea = _idea(_object(row["payload_json"], "idea"))
        recent_ideas.append(idea)
        if int(row["active"]) == 1:
            active_ids.add(idea.idea_id)
    stored_active_ideas = tuple(
        row for row in recent_ideas if row.idea_id in active_ids
    )
    snapshots = tuple(
        _snapshot(_object(row["payload_json"], "market snapshot"))
        for row in snapshot_rows
    )
    outcomes = tuple(
        _outcome(_object(row["payload_json"], "outcome")) for row in outcome_rows
    )
    calendar = tuple(
        _calendar(_object(row["payload_json"], "calendar event"))
        for row in calendar_rows
    )
    health: dict[str, Mapping[str, object]] = {}
    for row in health_rows:
        component = row["component"]
        if not isinstance(component, str) or not component:
            raise LeanDashboardDataError("stored health component is invalid")
        health[component] = _object(row["payload_json"], "health")
    try:
        market_freshness, _ = market_scan_freshness(
            health.get("scan", {}),
            evaluated_at=now,
        )
    except ValueError as exc:
        raise LeanDashboardDataError("stored scan freshness is invalid") from exc
    if market_freshness == "current":
        active_ideas = stored_active_ideas
        suppressed_active_idea_count = 0
    else:
        active_ideas = ()
        suppressed_active_idea_count = len(stored_active_ideas)
    truncated: list[str] = []
    if idea_count > MAX_IDEAS:
        truncated.append("ideas")
    if snapshot_count > MAX_MARKETS:
        truncated.append("market")
    if outcome_count > MAX_OUTCOMES:
        truncated.append("outcomes")
    if calendar_count > MAX_CALENDAR_EVENTS:
        truncated.append("calendar")
    return _LeanDashboardState(
        loaded_at=now,
        catalog_count=catalog_count,
        catalog_source_mode=metadata.get("bybit_catalog_source_mode", "unavailable"),
        catalog_observed_at=metadata.get("bybit_catalog_source_observed_at"),
        watchlist_count=watchlist_count,
        market_idea_freshness=market_freshness,
        suppressed_active_idea_count=suppressed_active_idea_count,
        active_ideas=active_ideas,
        recent_ideas=tuple(recent_ideas),
        latest_snapshots=snapshots,
        calendar_events=calendar,
        outcomes=outcomes,
        health=health,
        truncated_sections=tuple(truncated),
    )


def load_idea_detail(store: LeanRadarStore, idea_id: str) -> _LeanIdeaDetail | None:
    if not isinstance(idea_id, str) or not _IDEA_ID.fullmatch(idea_id):
        return None
    if not store.path.exists():
        raise LeanDashboardDataError("Lean Radar runtime is not initialized")
    try:
        with store.connect() as connection:
            connection.execute("BEGIN")
            _require_schema(connection)
            idea_row = connection.execute(
                "SELECT payload_json FROM ideas WHERE idea_id = ?", (idea_id,)
            ).fetchone()
            if idea_row is None:
                return None
            idea = _idea(_object(idea_row["payload_json"], "idea"))
            history_rows = connection.execute(
                """
                SELECT payload_json FROM (
                    SELECT observed_at, payload_json FROM market_snapshots
                    WHERE canonical_asset_id = ?
                    ORDER BY observed_at DESC LIMIT ?
                ) ORDER BY observed_at
                """,
                (idea.canonical_asset_id, MAX_IDEA_HISTORY_POINTS),
            ).fetchall()
            outcome_rows = connection.execute(
                """
                SELECT payload_json FROM outcomes
                WHERE idea_id = ? ORDER BY horizon
                """,
                (idea_id,),
            ).fetchall()
    except (LeanRadarStoreError, sqlite3.Error, OSError) as exc:
        raise LeanDashboardDataError("Lean Radar idea detail could not be read") from exc
    return _LeanIdeaDetail(
        idea=idea,
        market_history=tuple(
            _snapshot(_object(row["payload_json"], "market snapshot"))
            for row in history_rows
        ),
        outcomes=tuple(
            _outcome(_object(row["payload_json"], "outcome"))
            for row in outcome_rows
        ),
    )


def _require_schema(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != SCHEMA_VERSION:
        raise LeanDashboardDataError("Lean Radar runtime schema is unsupported")


def _object(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, str):
        raise LeanDashboardDataError(f"stored {label} is invalid")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LeanDashboardDataError(f"stored {label} is invalid") from exc
    if not isinstance(value, dict):
        raise LeanDashboardDataError(f"stored {label} is invalid")
    return value


def _idea(value: Mapping[str, object]) -> LeanIdea:
    payload = dict(value)
    for key in (
        "why_now",
        "supporting_facts",
        "risks",
        "missing_information",
        "what_confirms",
        "what_invalidates",
    ):
        payload[key] = tuple(payload.get(key, ()))
    try:
        return LeanIdea(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanDashboardDataError("stored idea is invalid") from exc


def _snapshot(value: Mapping[str, object]) -> MarketSnapshot:
    payload = dict(value)
    payload["sparkline_prices"] = tuple(payload.get("sparkline_prices", ()))
    try:
        return MarketSnapshot(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanDashboardDataError("stored market snapshot is invalid") from exc


def _outcome(value: Mapping[str, object]) -> LeanOutcome:
    payload = dict(value)
    payload["missing_information"] = tuple(payload.get("missing_information", ()))
    try:
        return LeanOutcome(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanDashboardDataError("stored outcome is invalid") from exc


def _calendar(value: Mapping[str, object]) -> CalendarEvent:
    payload = dict(value)
    payload["affected_symbols"] = tuple(payload.get("affected_symbols", ()))
    try:
        return CalendarEvent(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanDashboardDataError("stored calendar event is invalid") from exc


__all__ = (
    "LeanDashboardDataError",
    "load_dashboard_state",
    "load_idea_detail",
)
