"""Go/no-go readiness report for Event Alpha notification sends.

The report is diagnostic only. It does not send, rank, trade, paper trade, write
normal RSI signals, or create Event Alpha alert tiers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EventAlphaNotificationGoNoGoResult:
    profile: str
    artifact_namespace: str
    ready_to_preview: bool
    ready_to_send_now: bool
    telegram_ready: bool
    send_guard_enabled: bool
    lock_state: str
    lock_message: str
    provider_ready_event_sources: int
    provider_ready_enrichment_sources: int
    provider_backoff_count: int
    delivery_ledger_writable: bool
    notification_run_ledger_writable: bool
    research_cards_writable: bool
    artifact_doctor_status: str
    llm_budget_status: str
    cooldown_status: dict[str, dict[str, Any]]
    clock_line: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_command: str


def build_go_no_go(
    *,
    profile: str,
    artifact_namespace: str,
    telegram_ready: bool,
    send_guard_enabled: bool,
    lock_status: Any,
    provider_status: Any,
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    delivery_ledger_path: str | Path,
    notification_run_ledger_path: str | Path,
    research_cards_dir: str | Path,
    artifact_doctor_status: str,
    cooldown_status: Mapping[str, Mapping[str, Any]],
    llm_budget_status: str,
    clock_status: Mapping[str, Any],
) -> EventAlphaNotificationGoNoGoResult:
    """Build a deterministic readiness decision from existing runtime checks."""
    lock_state = str(getattr(lock_status, "state", "unknown") or "unknown")
    lock_message = str(getattr(lock_status, "message", "") or "")
    provider_sources = int(getattr(provider_status, "ready_event_source_count", 0) or 0)
    provider_enrichment = int(getattr(provider_status, "ready_enrichment_count", 0) or 0)
    backoff_count = sum(1 for row in provider_health_rows.values() if row.get("disabled_until"))
    delivery_writable = _path_writable(Path(delivery_ledger_path).expanduser(), is_dir=False)
    runs_writable = _path_writable(Path(notification_run_ledger_path).expanduser(), is_dir=False)
    cards_writable = _path_writable(Path(research_cards_dir).expanduser(), is_dir=True)
    fixed_clock_blocked = _fixed_clock_blocked(clock_status)

    blockers: list[str] = []
    warnings: list[str] = []
    if not delivery_writable:
        blockers.append("delivery ledger is not writable")
    if not runs_writable:
        blockers.append("notification run ledger is not writable")
    if not cards_writable:
        blockers.append("research cards directory is not writable")
    if lock_state == "held":
        blockers.append("fresh notification lock is held")
    elif lock_state == "stale":
        warnings.append("notification lock is stale and can be recovered by the cycle")
    if fixed_clock_blocked:
        blockers.append("fixed research clock blocks notification sends")
    if not telegram_ready:
        blockers.append("telegram config is missing")
    if not send_guard_enabled:
        blockers.append("RSI_EVENT_ALERTS_ENABLED is not set")
    if str(artifact_doctor_status).upper() == "BLOCKED":
        blockers.append("artifact doctor status is BLOCKED")
    if provider_sources <= 0:
        warnings.append("no active event sources; only heartbeat/would-send accounting may run")
    if backoff_count:
        warnings.append(f"{backoff_count} provider(s) currently in backoff")

    path_blockers = [
        blocker for blocker in blockers
        if blocker in {
            "delivery ledger is not writable",
            "notification run ledger is not writable",
            "research cards directory is not writable",
        }
    ]
    ready_to_preview = not path_blockers
    ready_to_send = ready_to_preview and not blockers
    next_command = _next_command(str(profile or "notify_no_key"), ready_to_send)
    return EventAlphaNotificationGoNoGoResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        ready_to_preview=ready_to_preview,
        ready_to_send_now=ready_to_send,
        telegram_ready=bool(telegram_ready),
        send_guard_enabled=bool(send_guard_enabled),
        lock_state=lock_state,
        lock_message=lock_message,
        provider_ready_event_sources=provider_sources,
        provider_ready_enrichment_sources=provider_enrichment,
        provider_backoff_count=backoff_count,
        delivery_ledger_writable=delivery_writable,
        notification_run_ledger_writable=runs_writable,
        research_cards_writable=cards_writable,
        artifact_doctor_status=str(artifact_doctor_status or "unknown"),
        llm_budget_status=str(llm_budget_status or "unknown"),
        cooldown_status={str(key): dict(value) for key, value in cooldown_status.items()},
        clock_line=_clock_line(clock_status),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_command=next_command,
    )


def format_go_no_go(result: EventAlphaNotificationGoNoGoResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION GO/NO-GO (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"ready_to_preview: {_yes_no(result.ready_to_preview)}",
        f"ready_to_send_now: {_yes_no(result.ready_to_send_now)}",
        f"telegram_ready: {_yes_no(result.telegram_ready)}",
        f"send_guard_enabled: {_yes_no(result.send_guard_enabled)}",
        f"clock: {result.clock_line}",
        f"lock: {result.lock_state} - {result.lock_message or 'unknown'}",
        (
            "providers: "
            f"event_sources={result.provider_ready_event_sources} "
            f"enrichment={result.provider_ready_enrichment_sources} "
            f"backoff={result.provider_backoff_count}"
        ),
        f"delivery_ledger_writable: {_yes_no(result.delivery_ledger_writable)}",
        f"notification_run_ledger_writable: {_yes_no(result.notification_run_ledger_writable)}",
        f"research_cards_writable: {_yes_no(result.research_cards_writable)}",
        f"artifact_doctor_status: {result.artifact_doctor_status}",
        f"LLM budget: {result.llm_budget_status}",
        "",
        "cooldowns:",
    ]
    for lane, status in sorted(result.cooldown_status.items()):
        lines.append(
            f"- {lane}: due={_yes_no(bool(status.get('due')))} "
            f"sent_today={status.get('sent_today', 0)} "
            f"last={status.get('last_sent_at') or 'never'} "
            f"reason={status.get('reason') or 'unknown'}"
        )
    lines.append("")
    lines.append("blockers:")
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append(f"next: {result.next_command}")
    lines.append("Go/no-go is diagnostic only; it does not send, trade, paper trade, or write normal RSI rows.")
    return "\n".join(lines).rstrip()


def _path_writable(path: Path, *, is_dir: bool) -> bool:
    target = path if is_dir else path.parent
    current = target
    while not current.exists() and current != current.parent:
        current = current.parent
    return current.exists() and os.access(current, os.W_OK)


def _next_command(profile: str, ready_to_send: bool) -> str:
    if not ready_to_send:
        return f"make event-alpha-notify-preview PROFILE={profile}"
    if profile == "notify_no_key":
        return "RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key"
    if profile == "notify_llm":
        return "RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-llm"
    return f"RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-cycle PROFILE={profile}"


def _fixed_clock_blocked(clock_status: Mapping[str, Any]) -> bool:
    warnings = tuple(str(item) for item in clock_status.get("warnings", ()) or ())
    return any("fixed_clock_blocks_notification_send" in warning for warning in warnings)


def _clock_line(clock_status: Mapping[str, Any]) -> str:
    now = clock_status.get("now") or clock_status.get("observed_at") or "wall-clock"
    warnings = tuple(str(item) for item in clock_status.get("warnings", ()) or ())
    if warnings:
        return f"{now} warnings={'; '.join(warnings[:3])}"
    return str(now)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
