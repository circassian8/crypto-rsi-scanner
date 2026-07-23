"""One bounded Lean Radar scan with no send, trade, or RSI write path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Callable, Mapping, Sequence

from .calendar import FUTURE_CONTEXT_HOURS, PAST_CONTEXT_HOURS, context_for_idea
from .config import LeanRadarSettings
from .features import build_features
from .ideas import build_idea
from .market_data import (
    MarketDataError,
    fetch_live_market_rows,
    live_provider_authorized,
    normalize_snapshots,
)
from .setups import detect_setup
from .store import LeanRadarStore, LeanRadarStoreError
from .universe import build_universe


MarketProvider = Callable[[], tuple[Sequence[Mapping[str, object]], Mapping[str, object]]]
SAFETY_COUNTERS = {
    "telegram_sends": 0,
    "trades_created": 0,
    "orders_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}


def scan_readiness(
    store: LeanRadarStore,
    settings: LeanRadarSettings,
    *,
    source_mode: str,
    environ: Mapping[str, str] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, object]:
    now = (evaluated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    catalog = store.catalog_status()
    last = store.last_scan_status()
    next_scan = _next_scan_time(last, settings.cadence_minutes)
    cadence_ready = next_scan is None or now >= next_scan
    reasons: list[str] = []
    if catalog.get("status") != "ready":
        reasons.append("confirmed Bybit USDT-perpetual catalog is missing")
    if source_mode == "live_no_send" and not live_provider_authorized(environ):
        reasons.append("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 is absent")
    if source_mode != "fixture" and catalog.get("source_mode") == "fixture":
        reasons.append("fixture Bybit catalog cannot support a non-fixture scan")
    if not cadence_ready:
        reasons.append(f"scan cadence is waiting until {next_scan.isoformat()}")
    return {
        "status": "ready" if not reasons else "blocked",
        "reasons": reasons,
        "source_mode": source_mode,
        "catalog": catalog,
        "cadence_minutes": settings.cadence_minutes,
        "cadence_eligible": cadence_ready,
        "next_scan_at": next_scan.isoformat() if next_scan else None,
        "live_provider_authorized": live_provider_authorized(environ),
        "current_provider_call_eligibility": (
            "eligible"
            if source_mode != "live_no_send" or live_provider_authorized(environ)
            else "authorization_absent"
        ),
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "research_only": True,
        **SAFETY_COUNTERS,
    }


def run_scan(
    store: LeanRadarStore,
    settings: LeanRadarSettings,
    *,
    source_mode: str,
    rows: Sequence[Mapping[str, object]] | None = None,
    observed_at: datetime | None = None,
    evaluated_at: datetime | None = None,
    environ: Mapping[str, str] | None = None,
    provider: MarketProvider | None = None,
    catalyst_context: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if source_mode not in {"live_no_send", "imported_snapshot", "fixture"}:
        raise MarketDataError("scan source mode is invalid")
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise MarketDataError("scan evaluation time must be timezone-aware")
    readiness = scan_readiness(
        store,
        settings,
        source_mode=source_mode,
        environ=environ,
        evaluated_at=now,
    )
    if readiness["status"] != "ready":
        return readiness

    provider_call_attempted = False
    provider_call_succeeded = False
    telemetry: Mapping[str, object] = {}
    materialized: Sequence[Mapping[str, object]]
    if source_mode == "live_no_send":
        provider_call_attempted = True
        provider_attempted_at = now.astimezone(timezone.utc)
        try:
            if provider is None:
                materialized, telemetry = fetch_live_market_rows(environ=environ)
            else:
                materialized, telemetry = provider()
        except Exception:
            health = _failed_provider_health(
                now=now,
                attempted_at=provider_attempted_at,
                settings=settings,
                status="provider_failed",
                reason="live market collection failed",
                provider_call_succeeded=False,
            )
            store.record_health("scan", health)
            return health
        provider_call_succeeded = True
        market_observed_at = observed_at or datetime.now(timezone.utc)
    else:
        if rows is None:
            raise MarketDataError("local scan requires explicit market rows")
        if observed_at is None or observed_at.tzinfo is None:
            raise MarketDataError("local scan requires an explicit aware observation time")
        materialized = rows
        market_observed_at = observed_at
    market_observed_at = market_observed_at.astimezone(timezone.utc)

    if not isinstance(materialized, Sequence) or isinstance(
        materialized, (str, bytes)
    ) or not all(
        isinstance(row, Mapping) for row in materialized
    ):
        if provider_call_attempted:
            health = _failed_provider_health(
                now=now,
                attempted_at=provider_attempted_at,
                settings=settings,
                status="market_data_blocked",
                reason="provider response rows are invalid",
                provider_call_succeeded=True,
                telemetry=telemetry,
            )
            store.record_health("scan", health)
            return health
        raise MarketDataError("local market rows are invalid")
    instruments = store.list_bybit_instruments()
    try:
        universe = build_universe(
            materialized,
            instruments,
            store.list_watchlist(),
            limit=settings.top_liquid_limit,
        )
    except (TypeError, ValueError) as exc:
        if not provider_call_attempted:
            raise MarketDataError("local market universe failed validation") from exc
        health = _failed_provider_health(
            now=now,
            attempted_at=provider_attempted_at,
            settings=settings,
            status="market_data_blocked",
            reason="provider market universe failed validation",
            provider_call_succeeded=True,
            telemetry=telemetry,
        )
        store.record_health("scan", health)
        return health
    if universe.status != "ready":
        blocked = {
            **readiness,
            "status": "blocked",
            "reasons": [f"universe is {universe.status}"],
            "provider_call_attempted": provider_call_attempted,
            "provider_telemetry": dict(telemetry),
            "universe": universe.to_dict(),
        }
        if provider_call_attempted:
            health = _failed_provider_health(
                now=now,
                attempted_at=provider_attempted_at,
                settings=settings,
                status="market_data_blocked",
                reason=f"universe is {universe.status}",
                provider_call_succeeded=True,
                telemetry=telemetry,
            )
            store.record_health("scan", health)
            return {**blocked, **health, "universe": universe.to_dict()}
        return blocked
    try:
        snapshots = normalize_snapshots(
            materialized,
            universe.active_assets,
            observed_at=market_observed_at,
            source_mode=source_mode,
        )
        histories = {
            row.canonical_asset_id: store.snapshot_history(
                row.canonical_asset_id, before=row.observed_at
            )
            for row in snapshots
        }
        features = build_features(snapshots, histories, evaluated_at=now)
        try:
            calendar_events = store.list_calendar_events(
                start=market_observed_at - timedelta(hours=PAST_CONTEXT_HOURS),
                end=market_observed_at + timedelta(hours=FUTURE_CONTEXT_HOURS),
            )
            calendar_status = store.calendar_status(evaluated_at=market_observed_at)[
                "status"
            ]
            calendar_warning = None
        except (LeanRadarStoreError, TypeError, ValueError):
            calendar_events = ()
            calendar_status = "unavailable_invalid"
            calendar_warning = "calendar context could not be read; market scan continued"
        ideas = []
        for feature in features:
            detection = detect_setup(feature)
            if detection is None:
                continue
            context = (catalyst_context or {}).get(feature.snapshot.canonical_asset_id)
            calendar_context = context_for_idea(
                calendar_events,
                symbol=feature.snapshot.symbol,
                evaluated_at=market_observed_at,
            )
            ideas.append(
                build_idea(
                    feature,
                    detection,
                    catalyst_context=context,
                    calendar_context=calendar_context,
                )
            )
    except (TypeError, ValueError) as exc:
        if not provider_call_attempted:
            raise MarketDataError("local market evidence failed validation") from exc
        health = _failed_provider_health(
            now=now,
            attempted_at=provider_attempted_at,
            settings=settings,
            status="market_data_blocked",
            reason="provider market evidence failed validation",
            provider_call_succeeded=True,
            telemetry=telemetry,
        )
        store.record_health("scan", health)
        return health
    scan_identity = (
        f"{market_observed_at.isoformat()}|{source_mode}|"
        + "|".join(row.bybit_instrument for row in snapshots)
    )
    scan_id = "lean-scan-" + hashlib.sha256(scan_identity.encode("utf-8")).hexdigest()[:20]
    next_scan = market_observed_at + timedelta(minutes=settings.cadence_minutes)
    health = {
        "status": "complete",
        "component": "scan",
        "scan_id": scan_id,
        "checked_at": now.astimezone(timezone.utc).isoformat(),
        "observed_at": market_observed_at.isoformat(),
        "next_scan_at": next_scan.isoformat(),
        "source_mode": source_mode,
        "provider_call_attempted": provider_call_attempted,
        "provider_call_succeeded": provider_call_succeeded,
        "provider_attempted_at": (
            provider_attempted_at.isoformat() if provider_call_attempted else None
        ),
        "provider_telemetry": dict(telemetry),
        "market_row_count": len(materialized),
        "active_universe_count": len(universe.active_assets),
        "blocked_universe_count": len(universe.blocked_assets),
        "snapshot_count": len(snapshots),
        "idea_count": len(ideas),
        "diagnostic_idea_count": sum(
            idea.idea_type == "diagnostic" for idea in ideas
        ),
        "calendar_status": calendar_status,
        "calendar_event_count": len(calendar_events),
        "calendar_context_idea_count": sum(
            idea.calendar_context.get("status") == "attached" for idea in ideas
        ),
        "calendar_warning": calendar_warning,
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }
    store.record_scan(snapshots, ideas, health)
    return {
        **health,
        "universe": universe.to_dict(),
        "ideas": [idea.to_dict() for idea in ideas],
    }


def _next_scan_time(
    last: Mapping[str, object] | None,
    cadence_minutes: int,
) -> datetime | None:
    if not last:
        return None
    raw = last.get("observed_at") or last.get("provider_attempted_at")
    if not isinstance(raw, str):
        return None
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    return observed.astimezone(timezone.utc) + timedelta(minutes=cadence_minutes)


def _failed_provider_health(
    *,
    now: datetime,
    attempted_at: datetime,
    settings: LeanRadarSettings,
    status: str,
    reason: str,
    provider_call_succeeded: bool,
    telemetry: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "component": "scan",
        "checked_at": now.astimezone(timezone.utc).isoformat(),
        "observed_at": None,
        "provider_attempted_at": attempted_at.astimezone(timezone.utc).isoformat(),
        "next_scan_at": (
            attempted_at.astimezone(timezone.utc)
            + timedelta(minutes=settings.cadence_minutes)
        ).isoformat(),
        "source_mode": "live_no_send",
        "reason": reason,
        "provider_call_attempted": True,
        "provider_call_succeeded": provider_call_succeeded,
        "provider_telemetry": dict(telemetry or {}),
        "telegram_send_attempted": False,
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }


__all__ = (
    "SAFETY_COUNTERS",
    "MarketProvider",
    "run_scan",
    "scan_readiness",
)
