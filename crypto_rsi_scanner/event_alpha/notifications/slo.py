"""SLO-style health summary for Event Alpha notification operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from . import delivery

STATUS_OK = "OK"
STATUS_DEGRADED = "DEGRADED"
STATUS_STALE = "STALE"
STATUS_BLOCKED = "BLOCKED"
STATUS_NO_SEND_CONFIG = "NO_SEND_CONFIG"


@dataclass(frozen=True)
class EventAlphaNotificationSLOResult:
    profile: str
    artifact_namespace: str
    status: str
    last_run_age_hours: float | None
    last_success_age_hours: float | None
    last_heartbeat_age_hours: float | None
    provider_backoff_count: int
    delivery_failure_count: int
    consecutive_failed_or_blocked_sends: int
    alertable_but_undelivered_count: int
    no_send_preview_runs: int
    config_blocked_runs: int
    delivery_failed_runs: int
    alertable_delivery_failures: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_action: str


def build_slo_report(
    *,
    profile: str,
    artifact_namespace: str,
    notification_runs: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    now: datetime | None = None,
    max_run_age_hours: float = 24.0,
    max_success_age_hours: float = 24.0,
) -> EventAlphaNotificationSLOResult:
    observed = _as_utc(now or datetime.now(timezone.utc))
    runs = sorted([dict(row) for row in notification_runs], key=lambda row: str(row.get("started_at") or ""), reverse=True)
    latest = runs[0] if runs else None
    success = next((row for row in runs if row.get("cycle_completed", True)), None)
    collapsed = delivery.latest_rows_by_delivery(delivery_rows)
    heartbeat = _latest_delivery(
        row for row in collapsed
        if str(row.get("lane") or "") == "health_heartbeat"
        and str(row.get("state") or "") in {delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED}
    )
    failure_count = sum(1 for row in collapsed if str(row.get("state") or "") == delivery.STATE_FAILED)
    blocked_count = sum(1 for row in collapsed if _is_delivery_blocked(row))
    provider_backoff = sum(1 for row in provider_health_rows.values() if row.get("disabled_until"))
    consecutive = _consecutive_bad(collapsed)
    run_counts = _classify_notification_runs(runs)
    alertable_undelivered = run_counts["alertable_delivery_failures"]
    last_run_age = _age_hours(latest, observed, "started_at")
    success_age = _age_hours(success, observed, "started_at")
    heartbeat_age = _age_hours(heartbeat, observed, "delivered_at", fallback="attempted_at")

    blockers: list[str] = []
    warnings: list[str] = []
    status = STATUS_OK
    if last_run_age is None or last_run_age > max_run_age_hours:
        status = STATUS_STALE
        blockers.append("latest notification run is stale or missing")
    if success_age is None or success_age > max_success_age_hours:
        status = STATUS_STALE
        blockers.append("latest successful notification run is stale or missing")
    if consecutive >= 3 or alertable_undelivered > 0:
        status = STATUS_BLOCKED
        if consecutive >= 3:
            blockers.append(f"{consecutive} consecutive failed/blocked delivery rows")
        if alertable_undelivered > 0:
            blockers.append(f"{alertable_undelivered} alertable send run(s) failed delivery")
    elif run_counts["latest_meaningful_run_status"] == "config_blocked":
        status = STATUS_NO_SEND_CONFIG if status == STATUS_OK else status
    elif provider_backoff or failure_count or blocked_count:
        status = STATUS_DEGRADED if status == STATUS_OK else status
        if provider_backoff:
            warnings.append(f"{provider_backoff} provider(s) in backoff")
        if failure_count:
            warnings.append(f"{failure_count} failed delivery row(s)")
        if blocked_count:
            warnings.append(f"{blocked_count} blocked delivery row(s)")
    if run_counts["config_blocked_runs"]:
        warnings.append(f"{run_counts['config_blocked_runs']} send-requested run(s) blocked by send configuration")
    if run_counts["no_send_preview_runs"]:
        warnings.append(f"{run_counts['no_send_preview_runs']} would-send preview run(s); no delivery expected")
    return EventAlphaNotificationSLOResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        status=status,
        last_run_age_hours=last_run_age,
        last_success_age_hours=success_age,
        last_heartbeat_age_hours=heartbeat_age,
        provider_backoff_count=provider_backoff,
        delivery_failure_count=failure_count,
        consecutive_failed_or_blocked_sends=consecutive,
        alertable_but_undelivered_count=alertable_undelivered,
        no_send_preview_runs=run_counts["no_send_preview_runs"],
        config_blocked_runs=run_counts["config_blocked_runs"],
        delivery_failed_runs=run_counts["delivery_failed_runs"],
        alertable_delivery_failures=run_counts["alertable_delivery_failures"],
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_action=_next_action(status, profile),
    )


def format_slo_report(result: EventAlphaNotificationSLOResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION SLO REPORT (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"status: {result.status}",
        f"last_run_age_hours: {_fmt(result.last_run_age_hours)}",
        f"last_success_age_hours: {_fmt(result.last_success_age_hours)}",
        f"last_heartbeat_delivery_age_hours: {_fmt(result.last_heartbeat_age_hours)}",
        f"provider_backoff_count: {result.provider_backoff_count}",
        f"delivery_failure_count: {result.delivery_failure_count}",
        f"consecutive_failed_or_blocked_sends: {result.consecutive_failed_or_blocked_sends}",
        f"would_send_preview_runs: {result.no_send_preview_runs}",
        f"config_blocked_runs: {result.config_blocked_runs}",
        f"delivery_failed_runs: {result.delivery_failed_runs}",
        f"alertable_delivery_failures: {result.alertable_delivery_failures}",
        f"alertable_but_undelivered_count: {result.alertable_but_undelivered_count}",
        "",
        "blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append(f"next_action: {result.next_action}")
    lines.append("SLO report is artifact-only; it does not send, trade, or change tiers.")
    return "\n".join(lines).rstrip()


def _consecutive_bad(rows: Iterable[Mapping[str, Any]]) -> int:
    ordered = sorted((dict(row) for row in rows), key=lambda row: str(row.get("attempted_at") or ""), reverse=True)
    count = 0
    for row in ordered:
        state = str(row.get("state") or "")
        if state == delivery.STATE_FAILED or _is_delivery_blocked(row):
            count += 1
            continue
        if state in {delivery.STATE_DELIVERED, delivery.STATE_PARTIAL_DELIVERED}:
            break
    return count


def _classify_notification_runs(runs: Iterable[Mapping[str, Any]]) -> dict[str, int | str]:
    counts = {
        "no_send_preview_runs": 0,
        "config_blocked_runs": 0,
        "delivery_failed_runs": 0,
        "alertable_delivery_failures": 0,
        "latest_meaningful_run_status": "",
    }
    for row in runs:
        would_send = _int(row.get("would_send_count"))
        send_requested = bool(row.get("send_requested"))
        send_guard_enabled = bool(row.get("send_guard_enabled"))
        delivered = _int(row.get("deliveries_delivered")) + _int(row.get("deliveries_partial_delivered"))
        failed = _int(row.get("deliveries_failed"))
        blocked = _int(row.get("deliveries_blocked"))
        duplicate_or_in_flight = _int(row.get("deliveries_skipped_duplicate")) + _int(row.get("deliveries_skipped_in_flight"))
        if would_send <= 0 and delivered <= 0 and failed <= 0 and blocked <= 0 and duplicate_or_in_flight <= 0:
            continue
        if not send_requested:
            counts["no_send_preview_runs"] += 1
            _set_latest_status_once(counts, "preview")
            continue
        if not send_guard_enabled:
            counts["config_blocked_runs"] += 1
            _set_latest_status_once(counts, "config_blocked")
            continue
        if delivered > 0:
            _set_latest_status_once(counts, "delivered")
            continue
        if delivered <= 0 and (
            failed > 0
            or _run_block_is_delivery_failure(row)
            or (duplicate_or_in_flight <= 0 and bool(row.get("block_reason")))
        ):
            counts["delivery_failed_runs"] += 1
            counts["alertable_delivery_failures"] += 1
            _set_latest_status_once(counts, "delivery_failed")
            continue
        _set_latest_status_once(counts, "skipped")
    return counts


def _set_latest_status_once(counts: dict[str, int | str], status: str) -> None:
    if not counts.get("latest_meaningful_run_status"):
        counts["latest_meaningful_run_status"] = status


def _is_delivery_blocked(row: Mapping[str, Any]) -> bool:
    if str(row.get("state") or "") != delivery.STATE_BLOCKED:
        return False
    error_class = str(row.get("error_class") or "")
    return error_class not in {"guard_blocked", "notifications_paused", "duplicate_content", "in_flight_content"}


def _run_block_is_delivery_failure(row: Mapping[str, Any]) -> bool:
    blocked = _int(row.get("deliveries_blocked"))
    if blocked <= 0:
        return False
    reason = str(row.get("block_reason") or "").casefold()
    return not any(token in reason for token in ("event alerts disabled", "not set", "notifications paused", "fixed research clock"))


def _latest_delivery(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted((dict(row) for row in rows), key=lambda row: str(row.get("delivered_at") or row.get("attempted_at") or ""), reverse=True)
    return ordered[0] if ordered else None


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


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _next_action(status: str, profile: str) -> str:
    if status == STATUS_OK:
        return f"continue scheduled target: make event-alpha-scheduler-status PROFILE={profile}"
    if status == STATUS_STALE:
        return f"run scheduled target manually: make event-alpha-notify-go-no-go PROFILE={profile}"
    if status == STATUS_BLOCKED:
        return f"inspect deliveries: make event-alpha-notification-deliveries-report PROFILE={profile}"
    if status == STATUS_NO_SEND_CONFIG:
        return f"enable send guard only when ready: make event-alpha-notify-go-no-go PROFILE={profile}"
    return f"inspect provider health: make event-alpha-provider-health-report PROFILE={profile}"
