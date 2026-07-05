"""Heartbeat for the legacy notification pipeline."""

from __future__ import annotations

from .runtime import *

def legacy_meta_warnings(storage: Any, cfg: EventAlphaNotificationConfig) -> tuple[str, ...]:
    """Return migration warnings for old unscoped notification keys."""
    if _clean_scope(cfg.notification_scope) == NOTIFICATION_SCOPE_GLOBAL:
        return ()
    warnings: list[str] = []
    for lane, key in LAST_SENT_META_KEYS.items():
        if storage.get_meta(key):
            warnings.append(f"legacy unscoped key present for {lane}: {key}")
    return tuple(warnings)

def format_health_heartbeat(
    *,
    profile: str | None,
    result: Any | None = None,
    now: datetime | None = None,
    send_guard_status: str | None = None,
) -> str:
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings = tuple(str(item) for item in _value(result, "warnings") or () if str(item))
    partial = bool(_value(result, "partial_results", False) or _provider_failure_count(warnings) > 0)
    lane_due = _mapping_value(result, "send_lane_items_attempted")
    lane_sent = _mapping_value(result, "send_lane_items_delivered")
    lanes_due = sum(_safe_int(value) for value in lane_due.values())
    lanes_sent = sum(_safe_int(value) for value in lane_sent.values())
    lane_status = _delivery_lane_status(result, send_guard_status=send_guard_status)
    llm_calls = _num(result, "llm_calls_attempted")
    llm_skipped = _num(result, "llm_skipped_due_budget")
    lines = [
        "<b>Event Alpha Heartbeat</b>",
        "<i>Research-only / unvalidated. Not a trade signal.</i>",
        f"Profile: {_esc(profile or _value(result, 'profile') or 'default')}",
        f"Generated: {_esc(observed.isoformat())}",
        f"Status: {_esc('degraded' if partial else 'ok')}",
        f"Completed: {_yes_no(bool(_value(result, 'cycle_completed', result is not None)))}",
        f"Raw events: {_num(result, 'raw_events')} · Core opportunities: {_num(result, 'core_opportunities')}",
        f"Extraction rows: {_num(result, 'extraction_rows')}",
        (
            f"Alertable decisions: {_num(result, 'alertable')} · "
            f"Strict alerts: {_num(result, 'alerts')} · "
            f"Research candidates: {_num(result, 'candidates')} · "
            f"Raw source candidates: {_raw_source_candidate_count(result)}"
        ),
        (
            "Delivery lanes: "
            f"due={lanes_due} · sent={lanes_sent} · "
            f"would_send_but_guard_disabled={lane_status['would_send_but_guard_disabled']} · "
            f"blocked_by_quality={lane_status['blocked_by_quality']} · "
            f"blocked_by_cooldown={lane_status['blocked_by_cooldown']} · "
            f"not_due={lane_status['not_due']}"
        ),
        f"Heartbeat: due={_yes_no(bool(_value(result, 'send_heartbeat_due', False)))} · sent={_yes_no(bool(_value(result, 'send_heartbeat_sent', False)))}",
        f"Provider issues: {_provider_failure_count(warnings)}",
        f"LLM calls/skips: {llm_calls}/{llm_skipped}",
        f"LLM budget: {'exhausted' if _runtime_budget_exhausted(warnings) else 'ok'}",
        f"Artifact doctor: {_esc(_value(result, 'artifact_doctor_status', 'not_run') if result is not None else 'not_run')}",
    ]
    if send_guard_status:
        lines.append(f"Send guard: {_esc(send_guard_status)}")
    if warnings:
        lines.append("Top issues: " + _esc("; ".join(_truncate_text(item, 90) for item in warnings[:3])))
    else:
        lines.append("Top issues: none")
    lines.append("Next: make event-alpha-notify-preview PROFILE=" + _esc(profile or "notify_no_key"))
    return "\n".join(lines)

def _heartbeat_degraded(message: str) -> bool:
    text = str(message or "").casefold()
    return (
        "degraded=yes" in text
        or "partial_results=yes" in text
        or "runtime_budget_status=exhausted" in text
    )

__all__ = (
    'legacy_meta_warnings',
    'format_health_heartbeat',
    '_heartbeat_degraded',
)
