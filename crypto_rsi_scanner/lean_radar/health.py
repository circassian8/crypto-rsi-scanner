"""Persist one bounded operator-health truth without crossing a provider boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from .config import LeanRadarSettings
from .freshness import market_scan_freshness
from .market_data import LIVE_AUTH_ENV, live_provider_authorized
from .safety import SAFETY_COUNTERS
from .store import LeanRadarStore, LeanRadarStoreError
from .telegram import LeanTelegramError, telegram_readiness


def refresh_system_health(
    store: LeanRadarStore,
    settings: LeanRadarSettings,
    *,
    environ: Mapping[str, str] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, object]:
    """Inspect local state, persist it when possible, and make no provider call."""

    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LeanRadarStoreError("system health evaluation time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    authorized = live_provider_authorized(environ)
    if not store.path.exists():
        return {
            "status": "setup_required",
            "component": "operator",
            "checked_at": now.isoformat(),
            "last_scan_at": None,
            "next_scan_at": None,
            "data_freshness": "unavailable",
            "current_authorization_status": "present" if authorized else "absent",
            "current_authorization_checked_at": now.isoformat(),
            "current_provider_call_eligibility": "catalog_missing",
            "no_send": True,
            "telegram_mode": "disabled_no_send",
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "errors": ["Confirmed Bybit USDT-perpetual catalog is missing"],
            "next_safe_command": (
                "CONFIRM=1 make lean-radar-bybit-universe-import "
                "LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json"
            ),
            "research_only": True,
            **SAFETY_COUNTERS,
        }

    errors: list[str] = []
    catalog = store.catalog_status()
    try:
        calendar = store.calendar_status(evaluated_at=now)
    except (LeanRadarStoreError, TypeError, ValueError):
        calendar = {
            "status": "unavailable_invalid",
            "event_count": 0,
            "upcoming_event_count": 0,
            "next_event_at": None,
        }
        errors.append("Calendar state could not be validated")
    scan = store.last_scan_status()
    outcomes = store.health_status("outcomes")
    last_telegram = store.health_status("telegram")
    try:
        telegram = telegram_readiness(
            store,
            environ=environ,
            evaluated_at=now,
        )
    except LeanTelegramError:
        telegram = {
            "status": "unavailable_invalid",
            "preview_ready": False,
            "preview_message_count": 0,
            "send_guard_enabled": False,
            "telegram_token_present": False,
            "telegram_recipient_configured": False,
            "current_send_eligibility": "blocked",
            "send_blockers": ["Telegram state could not be validated"],
        }
        errors.append("Telegram state could not be validated")
    last_scan_at = _text_time(scan, "observed_at") if scan else None
    next_scan_at = _text_time(scan, "next_scan_at") if scan else None
    if scan is None:
        freshness, age_seconds = "unavailable", None
    else:
        try:
            scan_freshness, age_seconds = market_scan_freshness(
                scan,
                evaluated_at=now,
                default_cadence_minutes=settings.cadence_minutes,
            )
        except ValueError as exc:
            raise LeanRadarStoreError("stored scan freshness is invalid") from exc
        freshness = "fresh" if scan_freshness == "current" else scan_freshness
    if catalog.get("status") != "ready":
        errors.append("Confirmed Bybit USDT-perpetual catalog is not ready")
    if scan is None:
        errors.append("No completed or attempted Lean Radar scan is recorded")
    elif scan.get("status") not in {"complete", "ready"}:
        errors.append("The latest scan did not complete")
    if freshness in {"stale", "future_invalid", "invalid_cadence"}:
        errors.append("Market observations are not current")
    if not authorized:
        errors.append(f"Current provider authorization is absent ({LIVE_AUTH_ENV})")
    if outcomes and outcomes.get("status") == "blocked":
        errors.append("Outcome evidence is blocked")

    cadence_eligible = next_scan_at is None or now >= _time(next_scan_at)
    eligibility = _provider_eligibility(
        authorized=authorized,
        catalog=catalog,
        cadence_eligible=cadence_eligible,
    )
    last_provider_attempted = bool(scan and scan.get("provider_call_attempted") is True)
    last_provider_succeeded = bool(scan and scan.get("provider_call_succeeded") is True)
    payload = {
        "status": "ready" if not errors else "attention",
        "component": "operator",
        "checked_at": now.isoformat(),
        "last_scan_at": last_scan_at,
        "next_scan_at": next_scan_at,
        "last_scan_status": scan.get("status") if scan else "not_run",
        "last_scan_source_mode": scan.get("source_mode") if scan else None,
        "last_scan_id": scan.get("scan_id") if scan else None,
        "last_provider_call_attempted": last_provider_attempted,
        "last_provider_call_succeeded": last_provider_succeeded,
        "last_provider_attempted_at": (
            scan.get("provider_attempted_at") if scan else None
        ),
        "data_freshness": freshness,
        "data_age_seconds": age_seconds,
        "cadence_minutes": settings.cadence_minutes,
        "cadence_eligible": cadence_eligible,
        "current_authorization_status": "present" if authorized else "absent",
        "current_authorization_checked_at": now.isoformat(),
        "current_provider_call_eligibility": eligibility,
        "bybit_universe": {
            "status": catalog.get("status"),
            "instrument_count": catalog.get("instrument_count", 0),
            "source_mode": catalog.get("source_mode"),
            "source_observed_at": catalog.get("source_observed_at"),
        },
        "coin_gecko": {
            "current_authorization_status": "present" if authorized else "absent",
            "last_call_attempted": last_provider_attempted,
            "last_call_succeeded": last_provider_succeeded,
            "last_call_at": scan.get("provider_attempted_at") if scan else None,
        },
        "calendar": {
            "status": calendar.get("status"),
            "event_count": calendar.get("event_count", 0),
            "upcoming_event_count": calendar.get("upcoming_event_count", 0),
            "next_event_at": calendar.get("next_event_at"),
        },
        "outcomes": {
            "status": outcomes.get("status") if outcomes else "not_run",
            "matured_count": outcomes.get("matured_count", 0) if outcomes else 0,
            "pending_count": outcomes.get("pending_count", 0) if outcomes else 0,
            "unresolved_count": (
                outcomes.get("unresolved_count", 0) if outcomes else 0
            ),
        },
        "telegram": {
            "status": telegram.get("status"),
            "preview_ready": telegram.get("preview_ready", False),
            "preview_message_count": telegram.get("preview_message_count", 0),
            "send_guard_enabled": telegram.get("send_guard_enabled", False),
            "token_present": telegram.get("telegram_token_present", False),
            "recipient_configured": telegram.get(
                "telegram_recipient_configured", False
            ),
            "current_send_eligibility": telegram.get(
                "current_send_eligibility", "blocked"
            ),
            "last_send_status": (
                last_telegram.get("status") if last_telegram else "not_run"
            ),
            "last_send_checked_at": (
                last_telegram.get("checked_at") if last_telegram else None
            ),
        },
        "no_send": True,
        "telegram_mode": (
            "guarded_send_ready"
            if telegram.get("current_send_eligibility") == "eligible"
            else "preview_only"
            if telegram.get("preview_ready")
            else "setup_required"
        ),
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "errors": errors,
        "next_safe_command": _next_safe_command(
            catalog=catalog,
            authorized=authorized,
            cadence_eligible=cadence_eligible,
        ),
        "research_only": True,
        **{
            **SAFETY_COUNTERS,
            "telegram_sends": (
                int(last_telegram.get("telegram_sends", 0))
                if last_telegram
                else 0
            ),
        },
    }
    store.record_health("operator", payload)
    return payload


def _provider_eligibility(
    *,
    authorized: bool,
    catalog: Mapping[str, object],
    cadence_eligible: bool,
) -> str:
    if catalog.get("status") != "ready":
        return "catalog_missing"
    if catalog.get("source_mode") == "fixture":
        return "fixture_catalog_blocked"
    if not authorized:
        return "authorization_absent"
    if not cadence_eligible:
        return "cadence_wait"
    return "eligible"


def _next_safe_command(
    *,
    catalog: Mapping[str, object],
    authorized: bool,
    cadence_eligible: bool,
) -> str:
    if catalog.get("status") != "ready":
        return (
            "CONFIRM=1 make lean-radar-bybit-universe-import "
            "LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json"
        )
    if catalog.get("source_mode") == "fixture":
        return "import a genuine Bybit catalog before any live scan"
    if not authorized:
        return (
            "authorize CoinGecko under the existing provider policy, then run "
            "make lean-radar-readiness"
        )
    if not cadence_eligible:
        return "run make lean-radar-health after the displayed next-scan time"
    return "make lean-radar-scan"


def _text_time(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    _time(value)
    return value


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanRadarStoreError("stored health timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanRadarStoreError("stored health timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = ("refresh_system_health",)
