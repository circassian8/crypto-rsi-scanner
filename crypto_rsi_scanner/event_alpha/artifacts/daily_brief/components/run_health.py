"""Canonical run and notification health formatting for the daily brief."""

from __future__ import annotations

from .runtime import *


def _latest_run_health_lines(latest: Mapping[str, Any], alertable_text: str) -> list[str]:
    counters = event_alpha_run_counters.canonical_run_counters(latest)
    send_state = event_alpha_run_counters.canonical_send_state(latest)
    lines = [
        f"- Run: {latest.get('run_id') or 'unknown'}",
        f"- Profile: {latest.get('profile') or 'default'}",
        f"- Success: {str(bool(latest.get('success'))).lower()}",
        (
            f"- Event funnel: raw_events={counters['raw_events']}, "
            f"candidate_events={counters['candidate_events']}, "
            f"research_candidates={counters['research_candidates']}"
        ),
        (
            f"- Core/store scopes: source_alert_snapshots={counters['source_alert_snapshots']}, "
            f"current_generation_core_rows={counters['current_generation_core_rows']}, "
            f"current_generation_visible_core_rows={counters['current_generation_visible_core_rows']}, "
            f"cumulative_store_rows={counters['cumulative_store_rows']}"
        ),
        (
            f"- Decision/preview output: routed={int(latest.get('routed') or 0)}, "
            f"alertable_decisions={counters['alertable_decisions']} "
            f"(visible_core_gate_count={alertable_text}), strict_alerts={counters['strict_alerts']}, "
            f"preview_rendered_items={counters['preview_rendered_items']}"
        ),
        (
            f"- Notification facts: burn_in_mode={send_state['burn_in_mode']}, "
            f"send_guard_status={send_state['send_guard_status']}, "
            f"send_requested={str(send_state['send_requested']).lower()}, "
            f"send_attempted={str(send_state['send_attempted']).lower()}, "
            f"no_send_rehearsal={str(send_state['no_send_rehearsal']).lower()}, "
            f"delivered={send_state['send_items_delivered']}"
        ),
        "- Catalyst frames analyzed/validated/disagreements/unresolved: "
        f"{int(latest.get('catalyst_frames_analyzed') or latest.get('catalyst_frame_rows') or 0)} / "
        f"{int(latest.get('catalyst_frame_validations') or latest.get('catalyst_frame_validations_applied') or 0)} / "
        f"{int(latest.get('catalyst_frame_disagreements') or 0)} / "
        f"{int(latest.get('catalyst_frame_unresolved') or 0)}",
        f"- Catalyst frame rows skipped/missing: {int(latest.get('catalyst_frame_rows_skipped') or 0)}",
    ]
    catalyst_frame_skip = latest.get("catalyst_frame_skip_reasons") or {}
    if isinstance(catalyst_frame_skip, Mapping) and catalyst_frame_skip:
        lines.append(
            "- Catalyst frame skip reasons: "
            + ", ".join(f"{key}={int(value or 0)}" for key, value in sorted(catalyst_frame_skip.items()))
        )
    warnings = [str(w) for w in latest.get("warnings") or [] if str(w)]
    if warnings:
        lines.append("- Warnings: " + "; ".join(warnings[:6]))
    return lines

def _latest_notification_health_lines(latest_notification: Mapping[str, Any]) -> list[str]:
    lines = [
        "- Notify lock/deliveries: "
        f"lock_acquired={str(bool(latest_notification.get('lock_acquired'))).lower()} "
        f"skipped_active_lock={str(bool(latest_notification.get('skipped_due_to_active_lock'))).lower()} "
        f"deliveries={int(latest_notification.get('deliveries_delivered') or 0)}d/"
        f"{int(latest_notification.get('deliveries_partial_delivered') or 0)}partial/"
        f"{int(latest_notification.get('deliveries_failed') or 0)}f/"
        f"{int(latest_notification.get('deliveries_skipped_duplicate') or 0)}dup/"
        f"{int(latest_notification.get('deliveries_skipped_in_flight') or 0)}flight/"
        f"{int(latest_notification.get('deliveries_blocked') or 0)}blocked"
    ]
    if event_alpha_notification_runs.row_has_delivery_failures(latest_notification):
        lines.append(
            f"- Notify delivery failures: {int(latest_notification.get('deliveries_failed') or 0)} "
            "failed delivery row(s) — run --event-alpha-notification-deliveries-report"
        )
    return lines
