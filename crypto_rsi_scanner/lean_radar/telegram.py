"""Concise Telegram projection, preview, and explicitly guarded delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import hashlib
import json
import os
from typing import Callable, Mapping, Sequence
from urllib.parse import quote, urlsplit

from .models import CalendarEvent, LeanIdea
from .safety import SAFETY_COUNTERS
from .store import LeanRadarStore, LeanRadarStoreError


MESSAGE_TYPES = (
    "urgent_review",
    "watchlist_update",
    "daily_digest",
    "risk_calendar",
)
SEND_GUARD_ENV = "RSI_EVENT_ALERTS_ENABLED"
DASHBOARD_URL_ENV = "RSI_LEAN_RADAR_DASHBOARD_URL"
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8766"
MATERIAL_SCORE_DELTA = 8.0
MAX_ITEMS_PER_MESSAGE = 4
COOLDOWN_MINUTES = {
    "urgent_review": 120,
    "watchlist_update": 360,
    "daily_digest": 720,
    "risk_calendar": 240,
}

_ROUTE_MESSAGE = {
    "urgent_review": "urgent_review",
    "watchlist": "watchlist_update",
    "daily_digest": "daily_digest",
    "risk_calendar": "risk_calendar",
}
_IDEA_LABELS = {
    "market_breakout_long": "Market breakout",
    "relative_strength_long": "Relative-strength leader",
    "pullback_or_mean_reversion": "Pullback / mean reversion",
    "rapid_market_anomaly": "Rapid market anomaly",
    "exhaustion_or_fade_review": "Exhaustion / fade review",
    "selloff_or_risk_warning": "Selloff / risk warning",
    "calendar_risk": "Scheduled risk",
    "dashboard_watch": "Developing watch",
    "diagnostic": "Data diagnostic",
}
_IDEA_FAMILIES = {
    "market_breakout_long": "upside_momentum",
    "relative_strength_long": "upside_momentum",
    "rapid_market_anomaly": "upside_momentum",
    "pullback_or_mean_reversion": "pullback",
    "exhaustion_or_fade_review": "fade_review",
    "selloff_or_risk_warning": "downside_risk",
    "calendar_risk": "scheduled_risk",
    "dashboard_watch": "developing_watch",
    "diagnostic": "diagnostic",
}


class _LeanTelegramError(RuntimeError):
    """Raised when Telegram state cannot be projected or sent safely."""


LeanTelegramError = _LeanTelegramError


@dataclass(frozen=True)
class _DueItem:
    item_id: str
    visible_family: str
    message_type: str
    material_digest: str
    material_snapshot: Mapping[str, object]
    due_reason: str
    broad_group: str
    idea: LeanIdea | None = None
    event: CalendarEvent | None = None


def build_telegram_plan(
    store: LeanRadarStore,
    *,
    environ: Mapping[str, str] | None = None,
    evaluated_at: datetime | None = None,
    dashboard_url: str | None = None,
) -> dict[str, object]:
    """Build one read-only, no-send plan from canonical persisted Lean ideas."""

    now = _aware_now(evaluated_at)
    base_url = _dashboard_url(
        dashboard_url
        if dashboard_url is not None
        else (environ or os.environ).get(DASHBOARD_URL_ENV, DEFAULT_DASHBOARD_URL)
    )
    if not store.path.exists():
        return _empty_plan(
            now,
            status="setup_required",
            dashboard_url=base_url,
            reason="Lean Radar runtime is not initialized",
        )
    try:
        states = store.notification_states()
        raw_ideas = store.list_active_ideas()
        scan = store.last_scan_status() or {}
        calendar = store.list_calendar_events(
            start=now,
            end=now + timedelta(hours=24),
            limit=500,
        )
    except LeanRadarStoreError as exc:
        raise LeanTelegramError("Lean Radar notification state is unavailable") from exc

    ideas = tuple(_idea(row) for row in raw_ideas)
    due: list[_DueItem] = []
    suppression: dict[str, int] = {}
    eligible_ideas = 0
    for idea in sorted(
        ideas,
        key=lambda row: (row.urgency_score, row.actionability_score, row.idea_id),
        reverse=True,
    ):
        if _time(idea.expires_at) <= now:
            _count(suppression, "expired")
            continue
        message_type = _ROUTE_MESSAGE.get(idea.telegram_route)
        if message_type is None:
            _count(suppression, "dashboard_only")
            continue
        eligible_ideas += 1
        item, reason = _idea_due(idea, message_type, states, now)
        if item is None:
            _count(suppression, reason)
        else:
            due.append(item)

    for event in calendar:
        item, reason = _calendar_due(event, states, now)
        if item is None:
            _count(suppression, reason)
        else:
            due.append(item)

    messages = _messages(due, dashboard_url=base_url, evaluated_at=now)
    fixture_item_count = sum(
        1
        for row in due
        if (
            row.idea is not None
            and row.idea.source_context.get("market_source_mode") == "fixture"
        )
        or (row.event is not None and row.event.source_mode == "fixture")
    )
    untrusted_source_item_count = sum(
        1
        for row in due
        if (
            row.idea is not None
            and row.idea.source_context.get("market_source_mode")
            not in {"live_no_send", "imported_snapshot", "fixture"}
        )
        or (
            row.event is not None
            and row.event.source_mode
            not in {"live_no_send", "imported_snapshot", "fixture"}
        )
    )
    included_ids = tuple(
        item_id
        for message in messages
        for item_id in message["item_ids"]  # type: ignore[index]
    )
    if len(included_ids) != len(due) or len(set(included_ids)) != len(due):
        raise LeanTelegramError("Telegram grouping lost or duplicated a due item")
    return {
        "schema_version": "lean_telegram_plan_v1",
        "status": "ready" if messages else "ready_empty",
        "evaluated_at": now.isoformat(),
        "source_mode": scan.get("source_mode", "unavailable"),
        "active_idea_count": len(ideas),
        "eligible_idea_count": eligible_ideas,
        "upcoming_calendar_event_count": len(calendar),
        "due_item_count": len(due),
        "message_count": len(messages),
        "messages": messages,
        "fixture_item_count": fixture_item_count,
        "untrusted_source_item_count": untrusted_source_item_count,
        "suppressed_count": sum(suppression.values()),
        "suppression_reasons": dict(sorted(suppression.items())),
        "material_score_delta": MATERIAL_SCORE_DELTA,
        "cooldown_minutes": dict(COOLDOWN_MINUTES),
        "hard_urgent_daily_cap": None,
        "dashboard_url": base_url,
        "send_requested": False,
        "send_attempted": False,
        "telegram_send_attempted": False,
        "provider_call_attempted": False,
        "database_write_attempted": False,
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }


def telegram_readiness(
    store: LeanRadarStore,
    *,
    environ: Mapping[str, str] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, object]:
    """Inspect preview and guarded-send readiness without sending or writing."""

    values = os.environ if environ is None else environ
    now = _aware_now(evaluated_at)
    plan = build_telegram_plan(store, environ=values, evaluated_at=now)
    guard = _enabled(values.get(SEND_GUARD_ENV))
    token_present = bool(values.get("TELEGRAM_BOT_TOKEN", "").strip())
    recipient_count = len(_recipients(values))
    source_mode = str(plan.get("source_mode", "unavailable"))
    blockers: list[str] = []
    if plan["status"] == "setup_required":
        blockers.append("Lean Radar runtime is not initialized")
    if source_mode == "fixture":
        blockers.append("fixture market state cannot be sent")
    if int(plan.get("fixture_item_count", 0)):
        blockers.append("fixture ideas or calendar context cannot be sent")
    if int(plan.get("untrusted_source_item_count", 0)):
        blockers.append("one or more due items lack trusted live/imported source mode")
    if not guard:
        blockers.append(f"{SEND_GUARD_ENV}=1 is not present")
    if not token_present:
        blockers.append("Telegram bot token is not configured")
    if recipient_count == 0:
        blockers.append("Telegram recipient is not configured")
    if plan["status"] != "setup_required" and not plan["message_count"]:
        blockers.append("no notification messages are currently due")
    send_ready = not blockers and int(plan["message_count"]) > 0
    if plan["status"] == "setup_required":
        status = "setup_required"
    elif send_ready:
        status = "send_ready"
    else:
        status = "preview_ready"
    if plan["status"] == "setup_required":
        next_command = "make lean-radar-readiness"
    elif not plan["message_count"]:
        next_command = "make lean-radar-scan"
    elif send_ready:
        next_command = (
            "RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 "
            "make lean-radar-telegram-send"
        )
    else:
        next_command = "make lean-radar-telegram-preview"
    return {
        "schema_version": "lean_telegram_readiness_v1",
        "status": status,
        "checked_at": now.isoformat(),
        "preview_ready": plan["status"] != "setup_required",
        "preview_message_count": plan["message_count"],
        "preview_due_item_count": plan["due_item_count"],
        "source_mode": source_mode,
        "send_guard_enabled": guard,
        "telegram_token_present": token_present,
        "telegram_recipient_configured": recipient_count > 0,
        "telegram_recipient_count": recipient_count,
        "current_send_eligibility": "eligible" if send_ready else "blocked",
        "send_blockers": blockers,
        "confirmation_required": True,
        "next_safe_command": next_command,
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "database_write_attempted": False,
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }


def send_telegram_plan(
    store: LeanRadarStore,
    *,
    confirm: bool,
    environ: Mapping[str, str] | None = None,
    evaluated_at: datetime | None = None,
    send_fn: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Deliver only after confirmation, the existing guard, and configuration."""

    values = os.environ if environ is None else environ
    now = _aware_now(evaluated_at)
    readiness = telegram_readiness(store, environ=values, evaluated_at=now)
    blockers = list(readiness["send_blockers"])
    if not confirm:
        blockers.insert(0, "explicit confirmation is required")
    if blockers or readiness["current_send_eligibility"] != "eligible":
        return {
            **readiness,
            "status": "blocked",
            "send_blockers": blockers,
            "send_requested": bool(confirm),
            "send_attempted": False,
            "telegram_send_attempted": False,
            "delivered_message_count": 0,
            "failed_message_count": 0,
        }
    owner = store.acquire_notification_send_lock(acquired_at=now)
    if owner is None:
        return {
            **readiness,
            "status": "blocked_in_progress",
            "send_blockers": ["another Lean Radar Telegram send is in progress"],
            "send_requested": True,
            "send_attempted": False,
            "telegram_send_attempted": False,
            "delivered_message_count": 0,
            "failed_message_count": 0,
        }
    delivered = 0
    failed = 0
    attempted = 0
    results: list[dict[str, object]] = []
    try:
        plan = build_telegram_plan(store, environ=values, evaluated_at=now)
        if not plan["message_count"]:
            result = {
                **readiness,
                "status": "no_due_messages",
                "send_requested": True,
                "send_attempted": False,
                "telegram_send_attempted": False,
                "delivered_message_count": 0,
                "failed_message_count": 0,
            }
            store.record_health("telegram", _send_health(result, checked_at=now))
            return result
        sender = send_fn or _default_sender()
        recipients = _recipients(values)
        for message in plan["messages"]:
            if not isinstance(message, Mapping):
                raise LeanTelegramError("Telegram plan message is invalid")
            attempted += 1
            outcome = _send_one(sender, str(message["body"]), recipients)
            success = bool(outcome["success"])
            if success:
                updates = message.get("state_updates")
                if not isinstance(updates, Sequence):
                    raise LeanTelegramError("Telegram delivery state is invalid")
                store.record_notification_deliveries(updates, delivered_at=now)
                delivered += 1
            else:
                failed += 1
            results.append(
                {
                    "message_id": message["message_id"],
                    "message_type": message["message_type"],
                    "attempted": outcome["attempted"],
                    "success": success,
                    "recipient_count": outcome["recipient_count"],
                    "delivered_count": outcome["delivered_count"],
                    "failed_count": outcome["failed_count"],
                    "error_class": outcome["error_class"],
                }
            )
        status = "complete" if failed == 0 else "partial_failure" if delivered else "failed"
        result = {
            "schema_version": "lean_telegram_send_result_v1",
            "status": status,
            "checked_at": now.isoformat(),
            "send_requested": True,
            "send_attempted": attempted > 0,
            "telegram_send_attempted": attempted > 0,
            "attempted_message_count": attempted,
            "delivered_message_count": delivered,
            "failed_message_count": failed,
            "results": results,
            "provider_call_attempted": False,
            "database_write_attempted": True,
            "no_send": False,
            "research_only": True,
            "telegram_sends": delivered,
            "trades_created": 0,
            "orders_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
        }
        store.record_health("telegram", _send_health(result, checked_at=now))
        return result
    finally:
        store.release_notification_send_lock(owner)


def render_telegram_preview(plan: Mapping[str, object]) -> str:
    lines = [
        "Lean Crypto Radar · Telegram preview",
        f"Status: {plan.get('status', 'unknown')}",
        (
            f"Would send {plan.get('message_count', 0)} message(s) covering "
            f"{plan.get('due_item_count', 0)} due item(s)"
        ),
        "No send attempted.",
    ]
    reason = plan.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")
    messages = plan.get("messages")
    if isinstance(messages, Sequence):
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, Mapping):
                continue
            lines.extend(("", f"--- Message {index} ---", str(message.get("body", ""))))
    suppressed = plan.get("suppression_reasons")
    if isinstance(suppressed, Mapping) and suppressed:
        human = ", ".join(
            f"{_human(str(key))}: {value}" for key, value in suppressed.items()
        )
        lines.extend(("", f"Suppressed safely: {human}"))
    lines.append("Research only · human decision required · not a trade instruction")
    return "\n".join(lines)


def render_telegram_readiness(readiness: Mapping[str, object]) -> str:
    blockers = readiness.get("send_blockers")
    blocker_text = (
        "; ".join(str(value) for value in blockers)
        if isinstance(blockers, Sequence) and blockers
        else "none"
    )
    return "\n".join(
        (
            "Lean Crypto Radar · Telegram readiness",
            f"Status: {readiness.get('status', 'unknown')}",
            f"Preview messages: {readiness.get('preview_message_count', 0)}",
            (
                "Configuration: send guard "
                f"{'enabled' if readiness.get('send_guard_enabled') else 'disabled'} · "
                f"token {'present' if readiness.get('telegram_token_present') else 'absent'} · "
                f"recipient {'present' if readiness.get('telegram_recipient_configured') else 'absent'}"
            ),
            f"Real-send blockers: {blocker_text}",
            f"Next: {readiness.get('next_safe_command', 'make lean-radar-telegram-preview')}",
            "Readiness only · no provider call · no send · research only",
        )
    )


def _idea_due(
    idea: LeanIdea,
    message_type: str,
    states: Mapping[str, Mapping[str, object]],
    now: datetime,
) -> tuple[_DueItem | None, str]:
    family = f"asset:{idea.symbol}:{_IDEA_FAMILIES[idea.idea_type]}"
    snapshot = _idea_material(idea)
    digest = _digest(snapshot)
    reason = _due_reason(states.get(family), snapshot, message_type, now)
    if reason == "unchanged_cooldown":
        return None, reason
    broad = _broad_group(idea, message_type)
    return (
        _DueItem(
            item_id=idea.idea_id,
            visible_family=family,
            message_type=message_type,
            material_digest=digest,
            material_snapshot=snapshot,
            due_reason=reason,
            broad_group=broad,
            idea=idea,
        ),
        reason,
    )


def _calendar_due(
    event: CalendarEvent,
    states: Mapping[str, Mapping[str, object]],
    now: datetime,
) -> tuple[_DueItem | None, str]:
    family = f"calendar:{event.event_id}"
    snapshot = {
        "event_id": event.event_id,
        "title": event.title,
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "importance": event.importance,
        "time_certainty": event.time_certainty,
        "affected_symbols": list(event.affected_symbols),
    }
    digest = _digest(snapshot)
    reason = _due_reason(states.get(family), snapshot, "risk_calendar", now)
    if reason == "unchanged_cooldown":
        return None, reason
    return (
        _DueItem(
            item_id=f"calendar-{event.event_id}",
            visible_family=family,
            message_type="risk_calendar",
            material_digest=digest,
            material_snapshot=snapshot,
            due_reason=reason,
            broad_group="scheduled_context",
            event=event,
        ),
        reason,
    )


def _due_reason(
    state: Mapping[str, object] | None,
    snapshot: Mapping[str, object],
    message_type: str,
    now: datetime,
) -> str:
    if state is None:
        return "first_seen"
    previous = state.get("material_snapshot")
    notified = state.get("last_notified_at")
    if not isinstance(previous, Mapping) or not isinstance(notified, str):
        raise LeanTelegramError("stored notification material is invalid")
    if _material_change(previous, snapshot):
        return "material_change"
    age = (now - _time(notified)).total_seconds()
    if age < 0:
        raise LeanTelegramError("stored notification time is in the future")
    if age >= COOLDOWN_MINUTES[message_type] * 60:
        return "cooldown_elapsed"
    return "unchanged_cooldown"


def _material_change(
    previous: Mapping[str, object],
    current: Mapping[str, object],
) -> bool:
    categorical = (
        "idea_type",
        "directional_bias",
        "telegram_route",
        "timing_state",
        "market_phase",
        "catalyst_status",
        "liquidity_status",
        "spread_status",
        "data_quality",
        "why_now",
        "main_risk",
        "what_confirms",
        "what_invalidates",
        "event_id",
        "title",
        "starts_at",
        "ends_at",
        "importance",
        "time_certainty",
        "affected_symbols",
    )
    if any(previous.get(key) != current.get(key) for key in categorical):
        return True
    for key in ("actionability", "confidence", "risk", "urgency"):
        old = previous.get(key)
        new = current.get(key)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if abs(float(new) - float(old)) >= MATERIAL_SCORE_DELTA:
                return True
        elif old != new:
            return True
    return False


def _messages(
    due: Sequence[_DueItem],
    *,
    dashboard_url: str,
    evaluated_at: datetime,
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    idea_items = [row for row in due if row.idea is not None]
    event_items = [row for row in due if row.event is not None]
    urgent = [row for row in idea_items if row.message_type == "urgent_review"]
    used: set[str] = set()
    for group_name in sorted({row.broad_group for row in urgent}):
        rows = [row for row in urgent if row.broad_group == group_name]
        if len(rows) < 3:
            continue
        for chunk in _chunks(rows, MAX_ITEMS_PER_MESSAGE):
            messages.append(
                _message(
                    chunk,
                    dashboard_url=dashboard_url,
                    evaluated_at=evaluated_at,
                    grouped=True,
                    market_wide=True,
                )
            )
            used.update(row.item_id for row in chunk)
    for row in urgent:
        if row.item_id not in used:
            messages.append(
                _message(
                    (row,),
                    dashboard_url=dashboard_url,
                    evaluated_at=evaluated_at,
                    grouped=False,
                    market_wide=False,
                )
            )
    for message_type in ("risk_calendar", "watchlist_update", "daily_digest"):
        rows = [row for row in idea_items if row.message_type == message_type]
        for chunk in _chunks(rows, MAX_ITEMS_PER_MESSAGE):
            messages.append(
                _message(
                    chunk,
                    dashboard_url=dashboard_url,
                    evaluated_at=evaluated_at,
                    grouped=len(chunk) > 1,
                    market_wide=False,
                )
            )
    for chunk in _chunks(event_items, MAX_ITEMS_PER_MESSAGE):
        messages.append(
            _message(
                chunk,
                dashboard_url=dashboard_url,
                evaluated_at=evaluated_at,
                grouped=len(chunk) > 1,
                market_wide=False,
            )
        )
    order = {value: index for index, value in enumerate(MESSAGE_TYPES)}
    messages.sort(
        key=lambda row: (
            order[str(row["message_type"])],
            str(row["message_id"]),
        )
    )
    return messages


def _message(
    rows: Sequence[_DueItem],
    *,
    dashboard_url: str,
    evaluated_at: datetime,
    grouped: bool,
    market_wide: bool,
) -> dict[str, object]:
    if not rows or len({row.message_type for row in rows}) != 1:
        raise LeanTelegramError("Telegram message group is invalid")
    message_type = rows[0].message_type
    body = _render_message(
        rows,
        dashboard_url=dashboard_url,
        evaluated_at=evaluated_at,
        grouped=grouped,
        market_wide=market_wide,
    )
    if len(body) > 4096:
        raise LeanTelegramError("Telegram message exceeds the platform limit")
    identity = {
        "message_type": message_type,
        "families": [row.visible_family for row in rows],
        "digests": [row.material_digest for row in rows],
    }
    message_id = "lean-telegram-" + _digest(identity)[:20]
    return {
        "message_id": message_id,
        "message_type": message_type,
        "grouped": grouped,
        "market_wide": market_wide,
        "item_count": len(rows),
        "item_ids": [row.item_id for row in rows],
        "visible_families": [row.visible_family for row in rows],
        "due_reasons": [row.due_reason for row in rows],
        "body": body,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "character_count": len(body),
        "state_updates": [
            {
                "visible_family": row.visible_family,
                "message_type": row.message_type,
                "material_digest": row.material_digest,
                "material_snapshot": dict(row.material_snapshot),
            }
            for row in rows
        ],
    }


def _render_message(
    rows: Sequence[_DueItem],
    *,
    dashboard_url: str,
    evaluated_at: datetime,
    grouped: bool,
    market_wide: bool,
) -> str:
    message_type = rows[0].message_type
    heading = {
        "urgent_review": "🚨 Urgent review",
        "watchlist_update": "👀 Watchlist update",
        "daily_digest": "📡 Daily radar digest",
        "risk_calendar": "⚠️ Risk & calendar",
    }[message_type]
    if market_wide:
        heading += f" · market-wide · {len(rows)} assets"
    elif grouped:
        heading += f" · {len(rows)} items"
    lines = [f"<b>{escape(heading)}</b>"]
    for row in rows:
        if row.idea is not None:
            idea = row.idea
            detail_url = f"{dashboard_url}/ideas/{quote(idea.idea_id, safe='')}"
            lines.extend(
                (
                    "",
                    (
                        f"<b>{escape(idea.symbol)} · "
                        f"{escape(_IDEA_LABELS[idea.idea_type])}</b>"
                    ),
                    (
                        f"{escape(_bias(idea.directional_bias))} · "
                        f"{escape(_human(idea.horizon))} · "
                        f"{escape(_human(idea.timing_state))}"
                    ),
                    (
                        f"Actionability <b>{idea.actionability_score:.0f}</b> · "
                        f"Confidence <b>{idea.confidence_score:.0f}</b> · "
                        f"Risk <b>{idea.risk_score:.0f}</b> · "
                        f"Urgency <b>{idea.urgency_score:.0f}</b>"
                    ),
                    (
                        f"Catalyst: {escape(_human(idea.catalyst_status))} · "
                        f"Phase: {escape(_human(idea.market_phase))}"
                    ),
                    f"Why now: {escape(_short(_first(idea.why_now, 'Market conditions changed')))}",
                    f"Main risk: {escape(_short(_first(idea.risks, 'Risk remains uncertain')))}",
                    f"Confirms: {escape(_short(_first(idea.what_confirms, 'Further confirmation required')))}",
                    f"Invalidates: {escape(_short(_first(idea.what_invalidates, 'Setup no longer holds')))}",
                    f'<a href="{escape(detail_url)}">Open dashboard detail</a>',
                )
            )
        elif row.event is not None:
            event = row.event
            affected = ", ".join(event.affected_symbols) or "All tracked markets"
            lines.extend(
                (
                    "",
                    f"<b>{escape(event.title)}</b>",
                    (
                        f"{escape(_relative_time(event.starts_at, evaluated_at))} · "
                        f"{escape(_human(event.importance))} importance · "
                        f"{escape(affected)}"
                    ),
                    "Context only · creates no market direction",
                    f'<a href="{escape(dashboard_url + "/calendar")}">Open calendar</a>',
                )
            )
    lines.extend(
        (
            "",
            "<i>Research only · human decision required · not a trade instruction</i>",
        )
    )
    return "\n".join(lines)


def _idea_material(idea: LeanIdea) -> dict[str, object]:
    return {
        "idea_type": idea.idea_type,
        "directional_bias": idea.directional_bias,
        "telegram_route": idea.telegram_route,
        "timing_state": idea.timing_state,
        "market_phase": idea.market_phase,
        "catalyst_status": idea.catalyst_status,
        "liquidity_status": idea.liquidity_status,
        "spread_status": idea.spread_status,
        "data_quality": idea.data_quality,
        "actionability": round(idea.actionability_score, 2),
        "confidence": round(idea.confidence_score, 2),
        "risk": round(idea.risk_score, 2),
        "urgency": round(idea.urgency_score, 2),
        "why_now": _first(idea.why_now, ""),
        "main_risk": _first(idea.risks, ""),
        "what_confirms": _first(idea.what_confirms, ""),
        "what_invalidates": _first(idea.what_invalidates, ""),
    }


def _broad_group(idea: LeanIdea, message_type: str) -> str:
    if message_type != "urgent_review":
        return message_type
    if idea.directional_bias == "long":
        return "market_upside"
    if idea.directional_bias in {"risk", "short_review"}:
        return "market_downside_or_exhaustion"
    return "market_anomaly"


def _idea(value: Mapping[str, object]) -> LeanIdea:
    payload = dict(value)
    for key in (
        "why_now",
        "supporting_facts",
        "risks",
        "missing_information",
        "what_confirms",
        "what_invalidates",
    ):
        payload[key] = tuple(payload.get(key, ()))
    try:
        return LeanIdea(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanTelegramError("stored Lean idea is invalid") from exc


def _send_one(
    sender: Callable[..., object],
    body: str,
    recipients: Sequence[str],
) -> dict[str, object]:
    try:
        result = sender(body, parse_mode="HTML", chat_ids=list(recipients))
    except Exception as exc:  # noqa: BLE001 - guarded send must fail soft
        return {
            "attempted": True,
            "success": False,
            "recipient_count": len(recipients),
            "delivered_count": 0,
            "failed_count": len(recipients),
            "error_class": type(exc).__name__[:80],
        }
    if isinstance(result, bool):
        success = result
        delivered = len(recipients) if success else 0
        failed = 0 if success else len(recipients)
        attempted = True
        error_class = None if success else "send_failed"
    else:
        attempted = bool(getattr(result, "attempted", True))
        delivered = _nonnegative_int(getattr(result, "delivered_count", 0))
        failed = _nonnegative_int(getattr(result, "failed_count", 0))
        success = bool(attempted and delivered > 0 and failed == 0)
        error = getattr(result, "error_class", None)
        error_class = str(error)[:80] if error else None
    return {
        "attempted": attempted,
        "success": success,
        "recipient_count": len(recipients),
        "delivered_count": delivered,
        "failed_count": failed,
        "error_class": error_class,
    }


def _default_sender() -> Callable[..., object]:
    from crypto_rsi_scanner.notifications import send_telegram_structured

    return send_telegram_structured


def _send_health(result: Mapping[str, object], *, checked_at: datetime) -> dict[str, object]:
    return {
        "schema_version": "lean_telegram_health_v1",
        "component": "telegram",
        "status": result.get("status", "unknown"),
        "checked_at": checked_at.isoformat(),
        "send_requested": bool(result.get("send_requested")),
        "send_attempted": bool(result.get("send_attempted")),
        "delivered_message_count": int(result.get("delivered_message_count", 0)),
        "failed_message_count": int(result.get("failed_message_count", 0)),
        "telegram_sends": int(result.get("delivered_message_count", 0)),
        "provider_call_attempted": False,
        "research_only": True,
        "trades_created": 0,
        "orders_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def _empty_plan(
    now: datetime,
    *,
    status: str,
    dashboard_url: str,
    reason: str,
) -> dict[str, object]:
    return {
        "schema_version": "lean_telegram_plan_v1",
        "status": status,
        "evaluated_at": now.isoformat(),
        "reason": reason,
        "source_mode": "unavailable",
        "active_idea_count": 0,
        "eligible_idea_count": 0,
        "upcoming_calendar_event_count": 0,
        "due_item_count": 0,
        "message_count": 0,
        "messages": [],
        "fixture_item_count": 0,
        "untrusted_source_item_count": 0,
        "suppressed_count": 0,
        "suppression_reasons": {},
        "hard_urgent_daily_cap": None,
        "dashboard_url": dashboard_url,
        "send_requested": False,
        "send_attempted": False,
        "telegram_send_attempted": False,
        "provider_call_attempted": False,
        "database_write_attempted": False,
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }


def _dashboard_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise LeanTelegramError("dashboard URL is invalid")
    clean = value.strip().rstrip("/")
    parsed = urlsplit(clean)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise LeanTelegramError("dashboard URL is unsafe")
    return clean


def _recipients(environ: Mapping[str, str]) -> tuple[str, ...]:
    raw = environ.get("TELEGRAM_CHAT_ID", "")
    return tuple(value.strip() for value in raw.split(",") if value.strip())


def _enabled(value: object) -> bool:
    return isinstance(value, str) and value.strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _chunks(values: Sequence[_DueItem], size: int) -> tuple[tuple[_DueItem, ...], ...]:
    return tuple(tuple(values[index : index + size]) for index in range(0, len(values), size))


def _aware_now(value: datetime | None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LeanTelegramError("Telegram evaluation time must be timezone-aware")
    return now.astimezone(timezone.utc)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanTelegramError("stored Telegram timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise LeanTelegramError("stored Telegram timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _relative_time(value: str, now: datetime) -> str:
    moment = _time(value)
    seconds = max(0, int((moment - now).total_seconds()))
    if seconds < 3600:
        relative = f"in {max(1, seconds // 60)}m"
    elif seconds < 86400:
        relative = f"in {seconds / 3600:.1f}h"
    else:
        relative = f"in {seconds / 86400:.1f}d"
    return f"{relative} · {moment.strftime('%d %b %H:%M UTC')}"


def _bias(value: str) -> str:
    return {
        "long": "Long-side review",
        "short_review": "Fade / exhaustion review",
        "risk": "Risk warning",
        "neutral": "Neutral review",
    }.get(value, _human(value))


def _human(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().capitalize()


def _first(values: Sequence[str], fallback: str) -> str:
    return values[0] if values else fallback


def _short(value: str, limit: int = 140) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _count(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = (
    "COOLDOWN_MINUTES",
    "DASHBOARD_URL_ENV",
    "DEFAULT_DASHBOARD_URL",
    "LeanTelegramError",
    "MATERIAL_SCORE_DELTA",
    "MESSAGE_TYPES",
    "SEND_GUARD_ENV",
    "build_telegram_plan",
    "render_telegram_preview",
    "render_telegram_readiness",
    "send_telegram_plan",
    "telegram_readiness",
)
