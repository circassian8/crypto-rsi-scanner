"""Notification-cycle summary artifacts for Event Alpha day-1 burn-in."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "event_alpha_notification_run_v1"


@dataclass(frozen=True)
class EventAlphaNotificationRunsConfig:
    path: Path


@dataclass(frozen=True)
class EventAlphaNotificationRunsReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]


def append_notification_run(
    result: Any,
    *,
    cfg: EventAlphaNotificationRunsConfig,
    profile: str,
    started_at: datetime,
    finished_at: datetime,
    telegram_ready: bool,
    send_guard_enabled: bool,
    plan: Any | None = None,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append one compact day-1 notification-cycle summary row."""
    row = notification_run_record(
        result,
        profile=profile,
        started_at=started_at,
        finished_at=finished_at,
        telegram_ready=telegram_ready,
        send_guard_enabled=send_guard_enabled,
        plan=plan,
        provider_health_rows=provider_health_rows or {},
    )
    path = cfg.path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    return row


def notification_run_record(
    result: Any,
    *,
    profile: str,
    started_at: datetime,
    finished_at: datetime,
    telegram_ready: bool,
    send_guard_enabled: bool,
    plan: Any | None = None,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    warnings = tuple(str(warning) for warning in getattr(result, "warnings", ()) or () if str(warning))
    provider_blocks = _provider_fail_fast_blocks(warnings, provider_health_rows or {})
    lane_due = dict(getattr(result, "send_lane_items_attempted", {}) or {})
    lane_sent = dict(getattr(result, "send_lane_items_delivered", {}) or {})
    if plan is not None:
        lane_due = dict(getattr(plan, "lane_counts", lane_due) or lane_due)
    cooldown_blocks = dict(getattr(result, "send_cooldown_blocks", {}) or {})
    if plan is not None:
        cooldown_blocks = dict(getattr(plan, "blocked_by_lane", cooldown_blocks) or cooldown_blocks)
    started = _as_utc(started_at)
    finished = _as_utc(finished_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "event_alpha_notification_run",
        "run_id": getattr(result, "run_id", None),
        "notification_profile": profile,
        "profile": profile,
        "run_mode": getattr(result, "run_mode", None),
        "artifact_namespace": getattr(result, "artifact_namespace", None),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "runtime_seconds": round(max(0.0, (finished - started).total_seconds()), 4),
        "cycle_completed": bool(getattr(result, "cycle_completed", True)),
        "partial_results": bool(getattr(result, "partial_results", False)),
        "scope": getattr(result, "notification_scope", None) or getattr(plan, "notification_scope", None),
        "scope_value": getattr(result, "notification_scope_value", None) or getattr(plan, "scope_value", None),
        "lane_counts_due": lane_due,
        "lane_counts_sent": lane_sent,
        "heartbeat_due": bool(getattr(result, "send_heartbeat_due", False) or getattr(plan, "heartbeat_due", False)),
        "heartbeat_sent": bool(getattr(result, "send_heartbeat_sent", False)),
        "would_send_count": _int(getattr(result, "send_would_send_items", 0))
        or _int(getattr(plan, "would_send_count", 0)),
        "block_reason": getattr(result, "send_block_reason", None),
        "cooldown_blocks": cooldown_blocks,
        "provider_fail_fast_blocks": provider_blocks,
        "provider_failure_count": len(provider_blocks),
        "runtime_budget_exhausted": any("notification_runtime_budget_exhausted" in warning for warning in warnings),
        "telegram_ready": bool(telegram_ready),
        "send_guard_enabled": bool(send_guard_enabled),
        "lock_acquired": bool(getattr(result, "notification_lock_acquired", False)),
        "skipped_due_to_active_lock": bool(getattr(result, "notification_skipped_due_to_active_lock", False)),
        "stale_lock_recovered": bool(getattr(result, "notification_stale_lock_recovered", False)),
        "delivery_records_written": _int(getattr(result, "notification_delivery_records_written", 0)),
        "deliveries_delivered": _int(getattr(result, "notification_deliveries_delivered", 0)),
        "deliveries_partial_delivered": _int(getattr(result, "notification_deliveries_partial_delivered", 0)),
        "deliveries_failed": _int(getattr(result, "notification_deliveries_failed", 0)),
        "deliveries_skipped_duplicate": _int(getattr(result, "notification_deliveries_skipped_duplicate", 0)),
        "deliveries_skipped_in_flight": _int(getattr(result, "notification_deliveries_skipped_in_flight", 0)),
        "deliveries_blocked": _int(getattr(result, "notification_deliveries_blocked", 0)),
        "warnings": tuple(dict.fromkeys(warnings)),
    }


def row_has_delivery_failures(row: Mapping[str, Any]) -> bool:
    return _int(row.get("deliveries_failed")) > 0


def load_notification_runs(path: str | Path, *, limit: int | None = None) -> EventAlphaNotificationRunsReadResult:
    p = Path(path).expanduser()
    rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_alpha_notification_run"
    ]
    rows.sort(key=lambda row: str(row.get("started_at") or ""), reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventAlphaNotificationRunsReadResult(path=p, rows_read=len(rows), rows=rows)


def format_notification_runs_report(result: EventAlphaNotificationRunsReadResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION RUNS REPORT (research-only / day-1 unvalidated)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
    ]
    if not result.rows:
        lines.append("")
        lines.append("No Event Alpha notification run rows found.")
        return "\n".join(lines)
    summary = _report_summary(result.rows)
    lines.extend([
        "profiles: " + _format_counts(summary["profiles"]),
        "scopes: " + _format_counts(summary["scopes"]),
        (
            "send totals: "
            f"lane_sent={summary['lane_sent']} "
            f"lane_due={summary['lane_due']} "
            f"would_send={summary['would_send']}"
        ),
        (
            "heartbeat: "
            f"sent={summary['heartbeat_sent']} "
            f"due={summary['heartbeat_due']}"
        ),
        (
            "degraded: "
            f"provider_failure_runs={summary['provider_failure_runs']} "
            f"partial_results={summary['partial_results']} "
            f"runtime_budget_exhausted={summary['runtime_budget_exhausted']}"
        ),
    ])
    lines.append("")
    for row in result.rows:
        lines.append(
            f"{row.get('started_at', 'unknown')} profile={row.get('notification_profile') or row.get('profile') or 'default'} "
            f"scope={row.get('scope') or 'unknown'}:{row.get('scope_value') or 'unknown'} "
            f"runtime={float(row.get('runtime_seconds') or 0):.2f}s "
            f"telegram_ready={_yes_no(bool(row.get('telegram_ready')))} "
            f"send_guard={_yes_no(bool(row.get('send_guard_enabled')))}"
        )
        due = row.get("lane_counts_due") or {}
        sent = row.get("lane_counts_sent") or {}
        lanes = sorted(set(due) | set(sent))
        if lanes:
            lines.append("  lanes: " + ", ".join(f"{lane}={_int(sent.get(lane))}/{_int(due.get(lane))}" for lane in lanes))
        lines.append(
            "  "
            f"heartbeat={_yes_no(bool(row.get('heartbeat_sent')))}/{_yes_no(bool(row.get('heartbeat_due')))} "
            f"would_send={_int(row.get('would_send_count'))} "
            f"block={row.get('block_reason') or 'none'} "
            f"cycle_completed={_yes_no(bool(row.get('cycle_completed', True)))} "
            f"partial_results={_yes_no(bool(row.get('partial_results')))} "
            f"runtime_budget_exhausted={_yes_no(bool(row.get('runtime_budget_exhausted')))}"
        )
        lines.append(
            "  "
            f"lock_acquired={_yes_no(bool(row.get('lock_acquired')))} "
            f"skipped_active_lock={_yes_no(bool(row.get('skipped_due_to_active_lock')))} "
            f"stale_lock_recovered={_yes_no(bool(row.get('stale_lock_recovered')))} "
            f"deliveries={_int(row.get('deliveries_delivered'))}d/"
            f"{_int(row.get('deliveries_failed'))}f/"
            f"{_int(row.get('deliveries_skipped_duplicate'))}dup/"
            f"{_int(row.get('deliveries_skipped_in_flight'))}flight/"
            f"{_int(row.get('deliveries_blocked'))}blocked "
            f"partial_delivered={_int(row.get('deliveries_partial_delivered'))}"
        )
        cooldown = row.get("cooldown_blocks") or {}
        if cooldown:
            lines.append("  cooldown_blocks: " + "; ".join(f"{key}={value}" for key, value in sorted(cooldown.items())))
        provider_blocks = row.get("provider_fail_fast_blocks") or []
        if provider_blocks:
            lines.append("  provider_fail_fast_blocks: " + "; ".join(str(item) for item in provider_blocks[:5]))
    lines.append("")
    lines.append("Notification runs are unvalidated research output only; trading action is NONE.")
    return "\n".join(lines).rstrip()


def _report_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    profiles: dict[str, int] = {}
    scopes: dict[str, int] = {}
    lane_sent = 0
    lane_due = 0
    would_send = 0
    heartbeat_sent = 0
    heartbeat_due = 0
    provider_failure_runs = 0
    partial_results = 0
    runtime_budget_exhausted = 0
    for row in rows:
        profile = str(row.get("notification_profile") or row.get("profile") or "default")
        profiles[profile] = profiles.get(profile, 0) + 1
        scope = f"{row.get('scope') or 'unknown'}:{row.get('scope_value') or 'unknown'}"
        scopes[scope] = scopes.get(scope, 0) + 1
        lane_sent += sum(_int(value) for value in dict(row.get("lane_counts_sent") or {}).values())
        lane_due += sum(_int(value) for value in dict(row.get("lane_counts_due") or {}).values())
        would_send += _int(row.get("would_send_count"))
        heartbeat_sent += 1 if row.get("heartbeat_sent") else 0
        heartbeat_due += 1 if row.get("heartbeat_due") else 0
        provider_failure_runs += 1 if _int(row.get("provider_failure_count")) > 0 or row.get("provider_fail_fast_blocks") else 0
        partial_results += 1 if row.get("partial_results") else 0
        runtime_budget_exhausted += 1 if row.get("runtime_budget_exhausted") else 0
    return {
        "profiles": profiles,
        "scopes": scopes,
        "lane_sent": lane_sent,
        "lane_due": lane_due,
        "would_send": would_send,
        "heartbeat_sent": heartbeat_sent,
        "heartbeat_due": heartbeat_due,
        "provider_failure_runs": provider_failure_runs,
        "partial_results": partial_results,
        "runtime_budget_exhausted": runtime_budget_exhausted,
    }


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _provider_fail_fast_blocks(
    warnings: Iterable[str],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    blocks: list[str] = [
        warning for warning in warnings
        if any(token in warning.casefold() for token in ("backoff", "failed", "failure", "timeout", "dns", "429"))
    ]
    for key, row in provider_health_rows.items():
        if row.get("disabled_until"):
            blocks.append(f"{row.get('provider_key') or key} in backoff until {row.get('disabled_until')}")
    return tuple(dict.fromkeys(blocks))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
