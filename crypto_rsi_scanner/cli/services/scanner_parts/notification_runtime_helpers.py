"""Notification runtime budgets and operator next-step rendering."""

from __future__ import annotations

from .runtime import *


class NotificationRuntimeBudget:
    """Small wall-clock budget helper for day-1 notification cycles."""

    def __init__(self, started_at: datetime, max_seconds: float) -> None:
        self.started_at = started_at.astimezone(timezone.utc) if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
        self.max_seconds = float(max_seconds or 0.0)

    def remaining_seconds(self) -> float:
        if self.max_seconds <= 0:
            return 0.0
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return max(0.0, self.max_seconds - elapsed)

    def exhausted(self) -> bool:
        return self.max_seconds <= 0 or self.remaining_seconds() <= 0

    def warning_if_low(self, stage: str) -> str | None:
        if not self.exhausted():
            return None
        clean_stage = "".join(ch if ch.isalnum() else "_" for ch in str(stage or "stage").strip().lower()).strip("_")
        return f"notification_runtime_budget_exhausted_before_{clean_stage or 'stage'}"


def _notification_runtime_budget(started_at: datetime) -> NotificationRuntimeBudget:
    return NotificationRuntimeBudget(
        started_at,
        float(getattr(config, "EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS", 120.0) or 0.0),
    )


def _notification_runtime_budget_exhausted(started_at: datetime) -> bool:
    return _notification_runtime_budget(started_at).exhausted()


def _notification_warnings_indicate_partial(warnings: Iterable[str]) -> bool:
    tokens = (
        "notification_cycle_failed_soft",
        "notification_runtime_budget_exhausted",
        "market_enrichment_live_fetch_failed",
        "failed",
        "failure",
        "timeout",
        "dns",
        "backoff",
        "429",
    )
    return any(any(token in str(warning).casefold() for token in tokens) for warning in warnings)


def format_event_alpha_notification_next_steps(
    *,
    profile: str,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    result: Any | None = None,
    notification_row: Mapping[str, Any] | None = None,
) -> str:
    """Render post-run operator commands without mutating state."""
    rows = provider_health_rows or {}
    backoff_keys = tuple(
        str(row.get("provider_key") or key)
        for key, row in rows.items()
        if row.get("disabled_until")
    )
    would_send = _int_value(
        (notification_row or {}).get("would_send_count")
        if notification_row is not None
        else getattr(result, "send_would_send_items", 0)
    )
    cards_written = len(tuple(getattr(result, "research_card_paths", ()) or ()))
    alertable = _int_value(getattr(result, "alertable", 0))
    feedback_target = _first_notification_feedback_target(result)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION NEXT STEPS",
        "=" * 76,
        f"- make event-alpha-notification-runs-report PROFILE={profile}",
        f"- make event-alpha-notification-inbox PROFILE={profile}",
        f"- make event-alpha-daily-brief PROFILE={profile}",
        f"- make event-alpha-artifact-doctor PROFILE={profile} STRICT=1",
        f"- make event-alpha-provider-health-report PROFILE={profile}",
    ]
    if backoff_keys:
        lines.append(
            f"- make event-alpha-provider-health-reset PROFILE={profile} "
            f"PROVIDER_KEY={backoff_keys[0]} CONFIRM=1"
        )
    if would_send > 0 or cards_written > 0 or alertable > 0:
        target = feedback_target or "<alert_id_or_card_id>"
        lines.append(f"- make event-feedback-watch PROFILE={profile} FEEDBACK_TARGET='{target}'")
    else:
        lines.append("- no alert/cards produced; review heartbeat status in the runs report and daily brief")
    lines.append("Research-only follow-up only; these commands do not trade, paper trade, or write normal RSI signals.")
    return "\n".join(lines).rstrip()


def _first_notification_feedback_target(result: Any | None) -> str | None:
    router_result = getattr(result, "router_result", None)
    decisions = tuple(getattr(router_result, "alertable_decisions", ()) or ())
    if not decisions:
        decisions = tuple(getattr(router_result, "decisions", ()) or ())
    for decision in decisions:
        alert_id = str(getattr(decision, "alert_id", "") or "").strip()
        if alert_id:
            return alert_id
        card_id = str(getattr(decision, "card_id", "") or "").strip()
        if card_id:
            return card_id
    for path in tuple(getattr(result, "research_card_paths", ()) or ()):
        stem = Path(path).stem
        if stem and stem != "index":
            return stem
    return None


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
