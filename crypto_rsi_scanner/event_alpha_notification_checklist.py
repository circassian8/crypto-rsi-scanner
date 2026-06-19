"""Startup checklist for Event Alpha day-1 notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import event_alpha_notifications, event_provider_status


@dataclass(frozen=True)
class EventAlphaNotificationChecklistResult:
    ready_to_notify_now: bool
    profile: str
    artifact_namespace: str
    send_guard_enabled: bool
    telegram_ready: bool
    provider_ready_event_sources: int
    provider_ready_enrichment_sources: int
    llm_budget_status: str
    card_auto_write: bool
    artifact_doctor_status: str
    cooldown_status: dict[str, dict[str, Any]]
    provider_backoff_rows: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_commands: tuple[str, ...] = ()


def build_notification_checklist(
    *,
    profile: str,
    artifact_namespace: str,
    send_guard_enabled: bool,
    telegram_ready: bool,
    provider_status: event_provider_status.EventDiscoveryProviderStatus,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None,
    plan: event_alpha_notifications.EventAlphaNotificationPlan,
    llm_budget_status: str,
    card_auto_write: bool,
    artifact_doctor_status: str,
    preflight_blockers: tuple[str, ...] = (),
    preflight_warnings: tuple[str, ...] = (),
) -> EventAlphaNotificationChecklistResult:
    """Build a day-1 notification startup checklist without sending."""
    blockers: list[str] = list(preflight_blockers)
    warnings: list[str] = list(preflight_warnings)
    if not send_guard_enabled:
        blockers.append("actual notify requires RSI_EVENT_ALERTS_ENABLED=1")
    if not telegram_ready:
        blockers.append("actual notify requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS")
    heartbeat_enabled = bool(plan.cooldown_status.get(event_alpha_notifications.LANE_HEALTH_HEARTBEAT) is not None)
    if provider_status.ready_event_source_count <= 0 and not heartbeat_enabled:
        blockers.append("no ready event sources and health heartbeat is disabled")
    elif provider_status.ready_event_source_count <= 0:
        warnings.append("no ready event sources; heartbeat-only notification mode can still report health")
    if profile == "notify_llm" and "OPENAI_API_KEY" in " ".join(blockers):
        blockers.append("use PROFILE=notify_no_key until OPENAI_API_KEY is configured")
    backoff_rows = tuple(
        f"{row.get('provider_key') or key} disabled_until={row.get('disabled_until')}"
        for key, row in (provider_health_rows or {}).items()
        if row.get("disabled_until")
    )
    if backoff_rows:
        warnings.append("one or more providers are currently in backoff")
    commands = [
        f"make event-alpha-preflight PROFILE={profile}",
        f"make event-alpha-notification-checklist PROFILE={profile}",
        f"RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE={profile}",
    ]
    if profile == "notify_llm":
        commands.append("RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-llm")
    else:
        commands.append("RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key")
    return EventAlphaNotificationChecklistResult(
        ready_to_notify_now=not blockers,
        profile=profile,
        artifact_namespace=artifact_namespace,
        send_guard_enabled=send_guard_enabled,
        telegram_ready=telegram_ready,
        provider_ready_event_sources=provider_status.ready_event_source_count,
        provider_ready_enrichment_sources=provider_status.ready_enrichment_count,
        llm_budget_status=llm_budget_status,
        card_auto_write=card_auto_write,
        artifact_doctor_status=artifact_doctor_status,
        cooldown_status=dict(plan.cooldown_status),
        provider_backoff_rows=backoff_rows,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_commands=tuple(commands),
    )


def format_notification_checklist(result: EventAlphaNotificationChecklistResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION STARTUP CHECKLIST (research-only / DAY-1 UNVALIDATED)",
        "=" * 76,
        f"READY_TO_NOTIFY_NOW: {_yes_no(result.ready_to_notify_now)}",
        "Validation status: DAY-1 UNVALIDATED",
        "Trading action: NONE",
        f"profile: {result.profile}",
        f"namespace: {result.artifact_namespace}",
        f"send_guard_enabled: {_yes_no(result.send_guard_enabled)}",
        f"telegram_ready: {_yes_no(result.telegram_ready)}",
        (
            "source_readiness: "
            f"event_sources={result.provider_ready_event_sources} "
            f"enrichment_sources={result.provider_ready_enrichment_sources}"
        ),
        f"llm_budget: {result.llm_budget_status}",
        f"research_cards_auto_write: {_yes_no(result.card_auto_write)}",
        f"artifact_doctor_status: {result.artifact_doctor_status}",
        "",
        "cooldown state:",
    ]
    for lane in event_alpha_notifications.LANES:
        status = result.cooldown_status.get(lane, {})
        lines.append(
            f"- {lane}: due={_yes_no(bool(status.get('due')))} "
            f"sent_today={status.get('sent_today', 0)} "
            f"meta_key={status.get('meta_key') or 'unknown'} "
            f"reason={status.get('reason') or 'unknown'}"
        )
    lines.extend(["", "provider health/backoff:"])
    lines.extend(f"- {row}" for row in result.provider_backoff_rows) if result.provider_backoff_rows else lines.append("- none")
    lines.extend(["", "blockers:"])
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.extend(["", "next commands:"])
    lines.extend(f"- {item}" for item in result.next_commands)
    lines.append("Review before acting. This checklist does not send, trade, paper trade, write normal RSI signals, or create TRIGGERED_FADE.")
    return "\n".join(lines).rstrip()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
