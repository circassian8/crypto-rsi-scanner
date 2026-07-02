"""Go/no-go readiness report for Event Alpha notification sends.

The report is diagnostic only. It does not send, rank, trade, paper trade, write
normal RSI signals, or create Event Alpha alert tiers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


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
    notifications_paused: bool
    pause_reason: str
    cooldown_status: dict[str, dict[str, Any]]
    clock_line: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_command: str
    provider_health_report_command: str
    provider_reset_command: str | None
    delivery_report_command: str
    notification_inbox_command: str
    latest_run_id: str | None = None
    latest_run_completed: bool | None = None
    notification_preview_exists: bool | None = None
    notification_preview_path_resolved: str | None = None
    notification_preview_path_source: str | None = None
    delivery_rows_have_explicit_status: bool | None = None
    canonical_delivery_identity: bool | None = None
    rejected_or_unconfirmed_selected: bool | None = None
    alertable_candidates_count: int | None = None
    would_send_lanes: tuple[str, ...] = ()
    final_recommendation: str = "NOT_READY"


RECOMMEND_READY_NO_SEND_REVIEW = "READY_FOR_NO_SEND_REVIEW"
RECOMMEND_READY_SEND = "READY_FOR_SEND"
RECOMMEND_NOT_READY = "NOT_READY"
STALE_PRE_CANONICAL_WARNING = (
    "This namespace contains pre-canonical notification delivery rows. Do not use it "
    "for send-readiness. Run notify_llm_deep_rehearsal or fixture final check."
)


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
    notifications_paused: bool = False,
    pause_reason: str = "",
    send_readiness: Any | None = None,
    delivery_rows: Iterable[Mapping[str, Any]] = (),
    delivery_history_rows: Iterable[Mapping[str, Any]] = (),
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
    real_send_blockers: list[str] = []
    if not telegram_ready:
        real_send_blockers.append("telegram config is missing")
    if not send_guard_enabled:
        real_send_blockers.append("RSI_EVENT_ALERTS_ENABLED is not set")
    if notifications_paused:
        blockers.append(f"notifications paused: {pause_reason or 'operator pause'}")
    if str(artifact_doctor_status).upper() == "BLOCKED":
        blockers.append("artifact doctor status is BLOCKED")
    if provider_sources <= 0:
        warnings.append("no active event sources; only heartbeat/would-send accounting may run")
    if backoff_count:
        warnings.append(f"{backoff_count} provider(s) currently in backoff")

    readiness_blockers = tuple(str(item) for item in getattr(send_readiness, "blockers", ()) or ())
    readiness_warnings = tuple(str(item) for item in getattr(send_readiness, "warnings", ()) or ())
    if readiness_blockers:
        blockers.extend(f"send-readiness: {item}" for item in readiness_blockers)
    warnings.extend(f"send-readiness: {item}" for item in readiness_warnings)

    delivery_rows_list = [dict(row) for row in delivery_rows if isinstance(row, Mapping)]
    delivery_history_list = [dict(row) for row in delivery_history_rows if isinstance(row, Mapping)]
    delivery_status_explicit = _delivery_rows_have_explicit_status(delivery_rows_list)
    canonical_identity = _delivery_rows_have_canonical_identity(delivery_rows_list)
    rejected_selected = _readiness_has_rejected_or_unconfirmed_candidate(readiness_blockers)
    would_send_lanes = _would_send_lanes(delivery_rows_list)
    latest_run_id = str(getattr(send_readiness, "latest_run_id", "") or "") or None
    latest_run_completed = getattr(send_readiness, "latest_run_completed", None)
    preview_path = str(getattr(send_readiness, "preview_path", "") or "") or None
    preview_exists = bool(preview_path and Path(preview_path).expanduser().exists())
    preview_source = str(getattr(send_readiness, "preview_path_source", "") or "") or None

    if send_readiness is not None:
        if not getattr(send_readiness, "ready", False):
            blockers.append("send-readiness is not ready")
        if latest_run_completed is False:
            blockers.append("latest run did not complete")
        if not preview_exists:
            blockers.append("notification preview is missing")
        if not delivery_status_explicit and delivery_rows_list:
            blockers.append("delivery rows are missing explicit status fields")
        if not canonical_identity and _has_alert_delivery_rows(delivery_rows_list):
            blockers.append("delivery rows are missing canonical identity")
        if rejected_selected:
            blockers.append("rejected-only or unconfirmed candidate selected")
    if _has_stale_pre_canonical_delivery_rows(delivery_history_list, latest_run_id=latest_run_id):
        warnings.append(STALE_PRE_CANONICAL_WARNING)

    path_blockers = [
        blocker for blocker in blockers
        if blocker in {
            "delivery ledger is not writable",
            "notification run ledger is not writable",
            "research cards directory is not writable",
        }
    ]
    ready_to_preview = not path_blockers
    ready_to_review = ready_to_preview and not blockers
    ready_to_send = ready_to_review and not real_send_blockers
    recommendation = _final_recommendation(
        send_guard_enabled=bool(send_guard_enabled),
        telegram_ready=bool(telegram_ready),
        ready_to_review=ready_to_review,
        ready_to_send=ready_to_send,
        send_readiness=send_readiness,
    )
    next_command = _next_command(str(profile or "notify_no_key"), ready_to_send)
    clean_profile = str(profile or "notify_no_key")
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
        notifications_paused=bool(notifications_paused),
        pause_reason=str(pause_reason or ""),
        cooldown_status={str(key): dict(value) for key, value in cooldown_status.items()},
        clock_line=_clock_line(clock_status),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys([*warnings, *(f"real-send blocked: {item}" for item in real_send_blockers)])),
        next_command=next_command,
        provider_health_report_command=f"make event-alpha-provider-health-report PROFILE={clean_profile}",
        provider_reset_command=(
            f"make event-alpha-provider-health-reset PROFILE={clean_profile} PROVIDER_KEY=all CONFIRM=1"
            if backoff_count > 0
            else None
        ),
        delivery_report_command=f"make event-alpha-notification-deliveries-report PROFILE={clean_profile}",
        notification_inbox_command=f"make event-alpha-notification-inbox PROFILE={clean_profile}",
        latest_run_id=latest_run_id,
        latest_run_completed=bool(latest_run_completed) if latest_run_completed is not None else None,
        notification_preview_exists=preview_exists if send_readiness is not None else None,
        notification_preview_path_resolved=preview_path,
        notification_preview_path_source=preview_source,
        delivery_rows_have_explicit_status=delivery_status_explicit if send_readiness is not None else None,
        canonical_delivery_identity=canonical_identity if send_readiness is not None else None,
        rejected_or_unconfirmed_selected=rejected_selected if send_readiness is not None else None,
        alertable_candidates_count=getattr(send_readiness, "alertable_items", None),
        would_send_lanes=would_send_lanes,
        final_recommendation=recommendation,
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
        f"final_recommendation: {result.final_recommendation}",
        f"latest_run_id: {result.latest_run_id or 'none'}",
        (
            "latest_run_completed: "
            + ("unknown" if result.latest_run_completed is None else _yes_no(result.latest_run_completed))
        ),
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
        (
            "notification_preview_exists: "
            + ("unknown" if result.notification_preview_exists is None else _yes_no(result.notification_preview_exists))
        ),
        f"notification_preview_path_resolved: {result.notification_preview_path_resolved or 'missing'}",
        f"notification_preview_path_source: {result.notification_preview_path_source or 'unknown'}",
        (
            "delivery_rows_have_explicit_status: "
            + (
                "unknown"
                if result.delivery_rows_have_explicit_status is None
                else _yes_no(result.delivery_rows_have_explicit_status)
            )
        ),
        (
            "canonical_delivery_identity: "
            + (
                "unknown"
                if result.canonical_delivery_identity is None
                else _yes_no(result.canonical_delivery_identity)
            )
        ),
        (
            "rejected_only_or_no_market_selected: "
            + (
                "unknown"
                if result.rejected_or_unconfirmed_selected is None
                else _yes_no(result.rejected_or_unconfirmed_selected)
            )
        ),
        f"alertable_candidates_count: {result.alertable_candidates_count if result.alertable_candidates_count is not None else 'unknown'}",
        f"would_send_lanes: {', '.join(result.would_send_lanes) if result.would_send_lanes else 'none'}",
        f"LLM budget: {result.llm_budget_status}",
        f"notifications_paused: {_yes_no(result.notifications_paused)}"
        + (f" ({result.pause_reason})" if result.pause_reason else ""),
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
    lines.append("operator commands:")
    lines.append(f"- provider health: {result.provider_health_report_command}")
    if result.provider_reset_command:
        lines.append(f"- provider reset: {result.provider_reset_command}")
    lines.append(f"- delivery report: {result.delivery_report_command}")
    lines.append(f"- notification inbox: {result.notification_inbox_command}")
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


def _delivery_rows_have_explicit_status(rows: Iterable[Mapping[str, Any]]) -> bool:
    rows_list = list(rows)
    if not rows_list:
        return True
    required = ("delivery_state", "status_detail", "delivery_mode", "would_send", "sent", "failed")
    return all(all(key in row and row.get(key) not in (None, "") for key in required) for row in rows_list)


def _delivery_rows_have_canonical_identity(rows: Iterable[Mapping[str, Any]]) -> bool:
    alert_lanes = {"daily_digest", "instant_escalation", "triggered_fade"}
    scoped = [row for row in rows if str(row.get("lane") or "") in alert_lanes]
    if not scoped:
        return True
    return all(
        bool(_identity_values(row, "core_opportunity_ids", "core_opportunity_id"))
        and bool(_identity_values(row, "canonical_symbols", "canonical_symbol"))
        and bool(_identity_values(row, "canonical_coin_ids", "canonical_coin_id"))
        and bool(_identity_values(row, "feedback_targets", "feedback_target"))
        for row in scoped
    )


def _identity_values(row: Mapping[str, Any], array_key: str, scalar_key: str) -> tuple[str, ...]:
    value = row.get(array_key)
    if isinstance(value, (list, tuple)):
        items = tuple(str(item).strip() for item in value if str(item).strip())
        if items:
            return items
    scalar = str(row.get(scalar_key) or "").strip()
    if not scalar:
        return ()
    return tuple(part.strip() for part in scalar.split(",") if part.strip())


def _has_alert_delivery_rows(rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(str(row.get("lane") or "") in {"daily_digest", "instant_escalation", "triggered_fade"} for row in rows)


def _has_stale_pre_canonical_delivery_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    latest_run_id: str | None,
) -> bool:
    for row in rows:
        lane = str(row.get("lane") or "").strip()
        if lane not in {"daily_digest", "instant_escalation", "triggered_fade"}:
            continue
        if latest_run_id and str(row.get("run_id") or "").strip() == latest_run_id:
            continue
        reason = str(row.get("identity_reconciliation_reason") or "").strip().casefold()
        legacy = str(row.get("legacy") or "").strip().casefold() in {"1", "true", "yes"}
        pre_canonical_reason = reason in {"legacy", "legacy_delivery", "external", "source_alert_identity_legacy"}
        missing_identity = not str(row.get("core_opportunity_id") or "").strip() or not str(
            row.get("feedback_target") or ""
        ).strip()
        missing_status = not str(row.get("delivery_state") or "").strip() or not str(
            row.get("status_detail") or ""
        ).strip()
        if legacy or pre_canonical_reason or missing_identity or missing_status:
            return True
    return False


def _readiness_has_rejected_or_unconfirmed_candidate(blockers: Iterable[str]) -> bool:
    text = "\n".join(str(item) for item in blockers).casefold()
    return any(token in text for token in ("rejected", "unconfirmed", "accepted/live confirmation", "no-market"))


def _would_send_lanes(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    lanes = []
    for row in rows:
        if bool(row.get("would_send")):
            lane = str(row.get("lane") or "").strip()
            if lane:
                lanes.append(lane)
    return tuple(dict.fromkeys(lanes))


def _final_recommendation(
    *,
    send_guard_enabled: bool,
    telegram_ready: bool,
    ready_to_review: bool,
    ready_to_send: bool,
    send_readiness: Any | None,
) -> str:
    if send_readiness is not None and not getattr(send_readiness, "ready", False):
        return RECOMMEND_NOT_READY
    if ready_to_send and send_guard_enabled and telegram_ready:
        return RECOMMEND_READY_SEND
    if ready_to_review:
        return RECOMMEND_READY_NO_SEND_REVIEW
    return RECOMMEND_NOT_READY
