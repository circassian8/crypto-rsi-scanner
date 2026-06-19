"""Freshness and safety guard for Event Alpha daily burn-in runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts, event_watchlist


@dataclass(frozen=True)
class EventAlphaHealthGuardConfig:
    max_run_age_hours: float = 6.0
    max_success_age_hours: float = 12.0
    require_profile: str | None = None


@dataclass(frozen=True)
class EventAlphaHealthGuardResult:
    status: str
    observed_at: str
    latest_run_at: str | None
    latest_success_at: str | None
    latest_profile: str | None
    required_profile: str | None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_command: str = "make event-alpha-cycle-profile PROFILE=no_key_live"


def evaluate_health_guard(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    cfg: EventAlphaHealthGuardConfig | None = None,
    now: datetime | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
) -> EventAlphaHealthGuardResult:
    """Classify the latest Event Alpha operating state as healthy/degraded/stale/blocked."""
    guard = cfg or EventAlphaHealthGuardConfig()
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    runs = sorted(
        event_alpha_artifacts.filter_artifact_rows(
            run_rows,
            profile=guard.require_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_legacy_artifacts=include_legacy_artifacts,
        ),
        key=lambda row: str(row.get("started_at") or row.get("finished_at") or ""),
        reverse=True,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        profile=guard.require_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    reason_codes: list[str] = []
    warnings: list[str] = []
    if not runs:
        return EventAlphaHealthGuardResult(
            status="BLOCKED",
            observed_at=observed.isoformat(),
            latest_run_at=None,
            latest_success_at=None,
            latest_profile=None,
            required_profile=guard.require_profile,
            reason_codes=("no_run_ledger",),
            next_command=_cycle_command(guard.require_profile),
        )
    latest = runs[0]
    latest_run_at = _dt(latest.get("started_at") or latest.get("finished_at"))
    latest_success = next((row for row in runs if bool(row.get("success"))), None)
    latest_success_at = _dt((latest_success or {}).get("started_at") or (latest_success or {}).get("finished_at"))
    latest_profile = str(latest.get("profile") or "default")
    if latest_run_at is None:
        reason_codes.append("latest_run_time_missing")
    elif _age_hours(observed, latest_run_at) > guard.max_run_age_hours:
        reason_codes.append("latest_run_stale")
    if latest_success_at is None:
        reason_codes.append("no_successful_run")
    elif _age_hours(observed, latest_success_at) > guard.max_success_age_hours:
        reason_codes.append("latest_success_stale")
    if guard.require_profile and latest_profile != guard.require_profile:
        reason_codes.append("profile_mismatch")
        warnings.append(f"latest profile {latest_profile!r} does not match required {guard.require_profile!r}")
    health_rows = provider_health_rows or {}
    for key, row in health_rows.items():
        failures = _int(row.get("consecutive_failures"))
        if row.get("disabled_until"):
            reason_codes.append("provider_backoff")
            warnings.append(f"provider {row.get('provider_key') or key} is in backoff")
        elif failures:
            reason_codes.append("provider_failures")
            warnings.append(f"provider {row.get('provider_key') or key} has {failures} consecutive failure(s)")
    skipped_budget = sum(_int(row.get("skipped_due_budget")) for row in llm_budget_rows)
    if skipped_budget:
        reason_codes.append("llm_budget_skipped")
        warnings.append(f"LLM budget skipped rows: {skipped_budget}")
    if any(_int(row.get("alertable")) > 0 for row in runs[:3]) and not alerts:
        reason_codes.append("missing_alert_snapshots")
    for row in runs[:3]:
        if _int(row.get("alertable")) <= 0:
            continue
        run_id = str(row.get("run_id") or "")
        matching = sum(1 for alert in alerts if str(alert.get("run_id") or "") == run_id and run_id)
        availability = event_alpha_artifacts.classify_snapshot_availability(
            row,
            None,
            matching,
        )
        if availability not in {
            event_alpha_artifacts.SNAPSHOT_AVAILABLE,
            event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY,
        }:
            reason_codes.append("missing_alert_snapshots")
    stale_active = _stale_watchlist_count(watchlist_entries, observed, max_age_hours=48.0)
    if stale_active:
        reason_codes.append("stale_watchlist_entries")
        warnings.append(f"active watchlist entries stale: {stale_active}")
    status = _status(reason_codes)
    return EventAlphaHealthGuardResult(
        status=status,
        observed_at=observed.isoformat(),
        latest_run_at=latest_run_at.isoformat() if latest_run_at else None,
        latest_success_at=latest_success_at.isoformat() if latest_success_at else None,
        latest_profile=latest_profile,
        required_profile=guard.require_profile,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_command=_next_command(status, guard.require_profile, reason_codes),
    )


def format_health_guard_report(result: EventAlphaHealthGuardResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA HEALTH GUARD (research-only)",
        "=" * 76,
        f"status: {result.status}",
        f"observed_at: {result.observed_at}",
        f"latest_run_at: {result.latest_run_at or 'none'}",
        f"latest_success_at: {result.latest_success_at or 'none'}",
        f"profile: {result.latest_profile or 'none'}",
        f"required_profile: {result.required_profile or 'none'}",
        "reason_codes: " + (", ".join(result.reason_codes) if result.reason_codes else "none"),
    ]
    if result.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.extend([
        "",
        f"next_command: {result.next_command}",
        "Health guard reports freshness and safety only; it does not send, trade, paper trade, or alter tiers.",
    ])
    return "\n".join(lines).rstrip()


def _status(reason_codes: list[str]) -> str:
    if not reason_codes:
        return "HEALTHY"
    if any(code in reason_codes for code in ("no_run_ledger", "no_successful_run")):
        return "BLOCKED"
    if any(code in reason_codes for code in ("latest_run_stale", "latest_success_stale")):
        return "STALE"
    return "DEGRADED"


def _next_command(status: str, profile: str | None, reason_codes: list[str]) -> str:
    if status in {"BLOCKED", "STALE"}:
        return _cycle_command(profile)
    if "missing_alert_snapshots" in reason_codes:
        return "make event-alpha-alerts-report"
    if "provider_backoff" in reason_codes or "provider_failures" in reason_codes:
        return f"make event-alpha-status PROFILE={profile or 'no_key_live'}"
    if "llm_budget_skipped" in reason_codes:
        return f"make event-alpha-daily-brief PROFILE={profile or 'full_llm_live'}"
    return f"make event-alpha-daily-brief PROFILE={profile or 'no_key_live'}"


def _cycle_command(profile: str | None) -> str:
    return f"make event-alpha-cycle-profile PROFILE={profile or 'no_key_live'}"


def _stale_watchlist_count(
    entries: Iterable[event_watchlist.EventWatchlistEntry],
    observed: datetime,
    *,
    max_age_hours: float,
) -> int:
    active = {
        event_watchlist.EventWatchlistState.RADAR.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.EVENT_PASSED.value,
        event_watchlist.EventWatchlistState.ARMED.value,
    }
    count = 0
    for entry in entries:
        if entry.state not in active:
            continue
        parsed = _dt(entry.last_seen_at)
        if parsed is not None and _age_hours(observed, parsed) > max_age_hours:
            count += 1
    return count


def _age_hours(now: datetime, when: datetime) -> float:
    return max(0.0, (now - when).total_seconds() / 3600.0)


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
