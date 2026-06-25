"""Scheduler status helpers for Event Alpha notification burn-in."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_notification_delivery as delivery


@dataclass(frozen=True)
class EventAlphaSchedulerStatusResult:
    profile: str
    artifact_namespace: str
    latest_run_age_hours: float | None
    latest_success_age_hours: float | None
    latest_delivery_age_hours: float | None
    lock_state: str
    lock_message: str
    provider_backoff_count: int
    health_guard_status: str
    scheduled_target_exists: bool
    suggested_command: str
    warnings: tuple[str, ...]


def build_scheduler_status(
    *,
    profile: str,
    artifact_namespace: str,
    run_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    lock_status: Any,
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    health_guard_status: str,
    scheduled_target_exists: bool,
    now: datetime | None = None,
) -> EventAlphaSchedulerStatusResult:
    observed = _as_utc(now or datetime.now(timezone.utc))
    rows = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    latest_run = _latest(rows)
    latest_success = _latest([row for row in rows if row.get("success", True) and row.get("cycle_completed", True)])
    latest_delivery = _latest_delivery(delivery_rows)
    backoff = sum(1 for row in provider_health_rows.values() if row.get("disabled_until"))
    warnings: list[str] = []
    if latest_run is None:
        warnings.append("no run ledger rows found")
    if latest_success is None:
        warnings.append("no successful run rows found")
    if str(getattr(lock_status, "state", "")) in {"held", "active"}:
        warnings.append("notification run lock is currently held")
    if backoff:
        warnings.append(f"{backoff} provider(s) in backoff")
    if not scheduled_target_exists:
        warnings.append("scheduled Make target was not found")
    return EventAlphaSchedulerStatusResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        latest_run_age_hours=_age_hours(latest_run, observed, "started_at"),
        latest_success_age_hours=_age_hours(latest_success, observed, "started_at"),
        latest_delivery_age_hours=_age_hours(latest_delivery, observed, "delivered_at", fallback="attempted_at"),
        lock_state=str(getattr(lock_status, "state", "unknown") or "unknown"),
        lock_message=str(getattr(lock_status, "message", "") or ""),
        provider_backoff_count=backoff,
        health_guard_status=str(health_guard_status or "unknown"),
        scheduled_target_exists=bool(scheduled_target_exists),
        suggested_command=scheduled_command(profile),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_scheduler_status(result: EventAlphaSchedulerStatusResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SCHEDULER STATUS (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"latest_run_age_hours: {_fmt_age(result.latest_run_age_hours)}",
        f"latest_success_age_hours: {_fmt_age(result.latest_success_age_hours)}",
        f"latest_notification_delivery_age_hours: {_fmt_age(result.latest_delivery_age_hours)}",
        f"lock: {result.lock_state} - {result.lock_message or 'unknown'}",
        f"provider_backoff_count: {result.provider_backoff_count}",
        f"health_guard_status: {result.health_guard_status}",
        f"scheduled_target_exists: {_yes_no(result.scheduled_target_exists)}",
        f"suggested_command: {result.suggested_command}",
        "",
        "warnings:",
    ]
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("Scheduler status does not install or send anything.")
    return "\n".join(lines).rstrip()


def scheduled_command(profile: str | None) -> str:
    if profile == "notify_llm_quality":
        return "make event-alpha-notify-llm-quality-scheduled"
    if profile == "notify_llm":
        return "make event-alpha-notify-llm-scheduled"
    return "make event-alpha-notify-no-key-scheduled"


def generate_launchd_plist(*, profile: str, repo_path: str | Path, python_path: str | Path | None = None) -> str:
    """Return a dry-run launchd plist with no embedded secrets."""
    target = scheduled_command(profile).replace("make ", "", 1)
    label = f"com.nasrenkaraf.crypto-rsi-scanner.event-alpha.{profile or 'notify_no_key'}"
    cwd = Path(repo_path).expanduser()
    python = Path(python_path).expanduser() if python_path else cwd / ".venv/bin/python"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{html.escape(label)}</string>
  <key>WorkingDirectory</key><string>{html.escape(str(cwd))}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/make</string>
    <string>{html.escape(target)}</string>
    <string>PYTHON={html.escape(str(python))}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>10</integer></dict>
  <key>StandardOutPath</key><string>{html.escape(str(cwd / 'event_alpha_notify.out.log'))}</string>
  <key>StandardErrorPath</key><string>{html.escape(str(cwd / 'event_alpha_notify.err.log'))}</string>
</dict>
</plist>
"""


def _latest(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted((dict(row) for row in rows), key=lambda row: str(row.get("started_at") or ""), reverse=True)
    return ordered[0] if ordered else None


def _latest_delivery(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    latest = [
        row for row in delivery.latest_rows_by_delivery(rows)
        if str(row.get("state") or "") in {delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED}
    ]
    latest.sort(key=lambda row: str(row.get("delivered_at") or row.get("attempted_at") or ""), reverse=True)
    return latest[0] if latest else None


def _age_hours(row: Mapping[str, Any] | None, now: datetime, key: str, *, fallback: str | None = None) -> float | None:
    if row is None:
        return None
    ts = _parse_iso(row.get(key) or (row.get(fallback) if fallback else None))
    if ts is None:
        return None
    return max(0.0, (_as_utc(now) - ts).total_seconds() / 3600.0)


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _fmt_age(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
