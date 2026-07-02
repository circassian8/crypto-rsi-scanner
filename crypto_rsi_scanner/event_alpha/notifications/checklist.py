"""Startup checklist for Event Alpha day-1 notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ... import event_provider_status
from . import pipeline as event_alpha_notifications


@dataclass(frozen=True)
class EventAlphaNotificationChecklistResult:
    ready_to_preview: bool
    ready_to_notify_now: bool
    profile: str
    artifact_namespace: str
    send_guard_enabled: bool
    telegram_ready: bool
    provider_ready_event_sources: int
    provider_ready_enrichment_sources: int
    clock_status: dict[str, Any]
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
    clock_status: Mapping[str, Any] | None = None,
    preflight_blockers: tuple[str, ...] = (),
    preflight_warnings: tuple[str, ...] = (),
    cryptopanic_api_token_present: bool = False,
) -> EventAlphaNotificationChecklistResult:
    """Build a day-1 notification startup checklist without sending."""
    raw_preflight_blockers = list(preflight_blockers)
    preview_blockers = [
        blocker for blocker in raw_preflight_blockers
        if not _send_blocker(blocker)
    ]
    send_blockers = [
        _normalize_send_blocker(blocker)
        for blocker in raw_preflight_blockers
        if _send_blocker(blocker)
    ]
    blockers: list[str] = list(preview_blockers)
    warnings: list[str] = list(preflight_warnings)
    if not send_guard_enabled:
        send_blockers.append("send: blocked, RSI_EVENT_ALERTS_ENABLED missing")
    if not telegram_ready:
        send_blockers.append("send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing")
    heartbeat_enabled = bool(plan.cooldown_status.get(event_alpha_notifications.LANE_HEALTH_HEARTBEAT) is not None)
    if provider_status.ready_event_source_count <= 0 and not heartbeat_enabled:
        preview_blockers.append("no ready event sources and health heartbeat is disabled")
        blockers.append("no ready event sources and health heartbeat is disabled")
    elif provider_status.ready_event_source_count <= 0:
        warnings.append("no ready event sources; heartbeat-only notification mode can still report health")
    if profile == "notify_llm" and "OPENAI_API_KEY" in " ".join(raw_preflight_blockers):
        preview_blockers.append("use PROFILE=notify_no_key until OPENAI_API_KEY is configured")
        blockers.append("use PROFILE=notify_no_key until OPENAI_API_KEY is configured")
    if not cryptopanic_api_token_present:
        warnings.append(
            "optional CryptoPanic API token missing; not blocking notify_no_key/notify_llm, "
            "but recommended for broader catalyst coverage"
        )
    backoff_rows = tuple(
        f"{row.get('provider_key') or key} disabled_until={row.get('disabled_until')}"
        for key, row in (provider_health_rows or {}).items()
        if row.get("disabled_until")
    )
    if backoff_rows:
        warnings.append("one or more providers are currently in backoff")
    full_blockers = [*blockers, *send_blockers]
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
        ready_to_preview=not preview_blockers,
        ready_to_notify_now=not full_blockers,
        profile=profile,
        artifact_namespace=artifact_namespace,
        send_guard_enabled=send_guard_enabled,
        telegram_ready=telegram_ready,
        provider_ready_event_sources=provider_status.ready_event_source_count,
        provider_ready_enrichment_sources=provider_status.ready_enrichment_count,
        clock_status=dict(clock_status or {}),
        llm_budget_status=llm_budget_status,
        card_auto_write=card_auto_write,
        artifact_doctor_status=artifact_doctor_status,
        cooldown_status=dict(plan.cooldown_status),
        provider_backoff_rows=backoff_rows,
        blockers=tuple(dict.fromkeys(full_blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        next_commands=tuple(commands),
    )


def format_notification_checklist(result: EventAlphaNotificationChecklistResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION STARTUP CHECKLIST (research-only / DAY-1 UNVALIDATED)",
        "=" * 76,
        f"READY_TO_PREVIEW: {_yes_no(result.ready_to_preview)}",
        f"READY_TO_NOTIFY_NOW: {_yes_no(result.ready_to_notify_now)}",
        "Validation status: DAY-1 UNVALIDATED",
        "Trading action: NONE",
        f"profile: {result.profile}",
        f"namespace: {result.artifact_namespace}",
        f"send_guard_enabled: {_yes_no(result.send_guard_enabled)}",
        f"telegram_ready: {_yes_no(result.telegram_ready)}",
        _format_clock_status(result.clock_status),
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


def _send_blocker(text: str) -> bool:
    lower = str(text or "").casefold()
    return any(
        token in lower
        for token in (
            "telegram",
            "rsi_event_alerts_enabled",
            "send requested",
            "actual notify",
            "fixed research clock",
            "notification send",
        )
    )


def _normalize_send_blocker(text: str) -> str:
    lower = str(text or "").casefold()
    if "rsi_event_alerts_enabled" in lower:
        return "send: blocked, RSI_EVENT_ALERTS_ENABLED missing"
    if "telegram" in lower:
        return "send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing"
    return f"send: blocked, {text}"


def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "clock: "
        f"mode={status.get('clock_mode') or 'unknown'} "
        f"research_now={status.get('research_now') or 'unknown'} "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'} "
        f"fixed_clock_age={age_text}"
    )
