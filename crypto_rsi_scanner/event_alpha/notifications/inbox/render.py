"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (render)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import research_cards as event_research_cards
from ...radar import core_opportunity_store as event_core_opportunity_store
from .. import delivery
from .. import pipeline as event_alpha_notifications
from .models import *  # noqa: F403

def format_notification_inbox(result: EventAlphaNotificationInboxResult, *, burn_in_review: bool = False) -> str:
    if burn_in_review:
        return _format_notification_inbox_burn_in_review(result)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION INBOX (research-only / review queue)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"notification_runs_path: {result.notification_runs_path}",
        f"alert_store_path: {result.alert_store_path}",
        f"feedback_path: {result.feedback_path}",
        f"research_cards_dir: {result.research_cards_dir}",
        f"outcomes_path: {result.outcomes_path or 'not loaded'}",
        (
            "rows: "
            f"notification_runs={result.notification_runs_read} "
            f"alerts={result.alert_rows_read} "
            f"feedback={result.feedback_rows_read} "
            f"cards={result.research_cards_read} "
            f"outcomes={result.outcome_rows_read}"
        ),
        (
            "review_items: "
            f"canonical={len(result.canonical_review_items)} "
            f"canonical_cards={result.canonical_review_items_with_cards} "
            f"canonical_feedback_targets={result.canonical_review_items_with_feedback_targets} "
            f"diagnostics_hidden={len(result.diagnostic_review_items_hidden)} "
            f"diagnostics_visible={len(result.diagnostic_review_items)}"
        ),
        (
            "feedback_authority: "
            f"supplied={result.feedback_rows_supplied} "
            f"eligible={result.feedback_rows_eligible} "
            f"excluded={result.feedback_rows_excluded}"
        ),
        "",
    ]
    _append_item_section(
        lines,
        "delivered core opportunities needing feedback",
        result.sent_without_feedback,
        profile=result.profile,
    )
    _append_item_section(
        lines,
        "partial-delivered core opportunities needing delivery review",
        result.partial_delivered_without_feedback,
        profile=result.profile,
    )
    _append_item_section(lines, "would-send core opportunities blocked by preview mode", result.would_send_without_feedback, profile=result.profile)
    _append_item_section(lines, "would-send core opportunities blocked by guard without feedback", result.would_send_blocked_without_feedback, profile=result.profile)
    _append_item_section(lines, "research-review candidates needing feedback", result.research_review_without_feedback, profile=result.profile)
    _append_item_section(lines, "near-misses for optional review", result.exploratory_without_feedback, profile=result.profile)
    _append_item_section(lines, "local-only learning rows for optional review", (*result.quality_gated_local_only, *result.weak_validated_local_only), profile=result.profile)
    _append_item_section(lines, "legacy quality conflicts for migration review", result.legacy_quality_conflicts, profile=result.profile)
    _append_item_section(lines, "high-priority/watchlist/digest core opportunities not reviewed", result.high_priority_unreviewed, profile=result.profile)
    _append_item_section(lines, "triggered-fade cards not reviewed", result.triggered_fade_unreviewed, profile=result.profile)
    if result.diagnostic_review_items:
        _append_item_section(lines, "diagnostic/support snapshots", result.diagnostic_review_items, profile=result.profile)
    elif result.diagnostic_review_items_hidden:
        lines.append(f"diagnostic/support snapshots hidden by default: {len(result.diagnostic_review_items_hidden)}")
        lines.append("- pass the diagnostics flag in local tooling to inspect source-noise/control snapshots")
        lines.append("")
    _append_run_section(lines, "heartbeat-only runs", result.heartbeat_only_runs)
    _append_run_section(lines, "duplicate/in-flight suppressed runs", result.duplicate_or_in_flight_runs)
    _append_run_section(lines, "provider-degraded notification runs", result.provider_degraded_runs)
    lines.append("Review queue is artifact-only; it does not send, trade, paper trade, or alter Event Alpha tiers.")
    return "\n".join(lines).rstrip()
def _append_review_queue_section(
    lines: list[str],
    title: str,
    items: Iterable[EventAlphaReviewQueueItem],
    *,
    profile: str,
    limit: int,
) -> None:
    rows = list(items)
    lines.append(f"{title}: {len(rows)}")
    if not rows:
        lines.append("- none")
        lines.append("")
        return
    for idx, item in enumerate(rows[: max(0, limit)], start=1):
        lines.append(
            f"{idx}. [{_human_queue_category(item.category)}] {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} "
            f"score={item.rank_score:g} tier={item.tier or 'unknown'} route={item.route or 'unknown'}"
        )
        lines.append(
            f"   why: {item.reason or 'selected for operator review'} · "
            f"card={item.card_basename or 'not_written'} · feedback={item.feedback_target or item.source_item.alert_id}"
        )
        lines.append(
            f"   command: make event-feedback-watch PROFILE={profile} FEEDBACK_TARGET='{item.feedback_target or item.source_item.alert_id}'"
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more in the full notification inbox")
    lines.append("")
def _card_label(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return Path(text).name or text
def _append_item_section(
    lines: list[str],
    title: str,
    items: Iterable[EventAlphaNotificationInboxItem],
    *,
    profile: str,
) -> None:
    rows = list(items)
    lines.append(f"{title}: {len(rows)}")
    if not rows:
        lines.append("- none")
        lines.append("")
        return
    for item in rows[:20]:
        item_id_label = "core_id" if item.core_opportunity_id and item.alert_id == item.core_opportunity_id else "alert_id"
        lines.append(
            f"- {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} {item_id_label}={item.alert_id} "
            f"tier={item.tier} playbook={item.playbook} "
            f"sent={_yes_no(item.sent)} would_send={_yes_no(item.would_send)} "
            f"delivery_state={item.delivery_state or 'none'}"
        )
        if item.alert_key and item.alert_key != item.alert_id:
            lines.append(f"  source_alert_id: {item.alert_key}")
        if item.core_opportunity_id and item.alert_id != item.core_opportunity_id:
            lines.append(f"  core_opportunity_id: {item.core_opportunity_id}")
        lines.append(f"  card: {item.card_path or 'not_written'}")
        lines.append(f"  run_id: {item.run_id or 'unknown'}")
        if item.quality_gate_block_reason:
            lines.append(
                f"  quality_gate: final={item.final_route_after_quality_gate or 'unknown'} "
                f"tier={item.final_tier_after_quality_gate or item.tier or 'unknown'} "
                f"block={item.quality_gate_block_reason}"
            )
        if item.snapshot_quality_classification:
            lines.append(f"  snapshot_classification: {item.snapshot_quality_classification}")
        if item.decision_model_version:
            lines.append(
                f"  radar_decision: route={item.radar_route or 'diagnostic'} "
                f"origin={item.primary_thesis_origin or item.thesis_origin or 'unknown'} "
                f"contributors={','.join(item.thesis_origins) or 'unknown'} "
                f"bias={item.directional_bias or 'neutral'} "
                f"catalyst={item.catalyst_status or 'unknown'} confidence={item.confidence_band or 'diagnostic'}"
            )
            lines.append(
                f"  radar_scores: actionability={_decision_score(item.actionability_score)} "
                f"evidence={_decision_score(item.evidence_confidence_score)} risk={_decision_score(item.risk_score)} "
                f"urgency={_decision_score(item.urgency_score)} chase_risk={_decision_score(item.chase_risk_score)}"
            )
            lines.append(
                f"  radar_timing: phase={item.market_phase or 'unknown'} timing={item.timing_state or 'unknown'} "
                f"horizon={item.preferred_horizon or 'unknown'} expires={item.expires_at or 'not set'} "
                f"tradability={item.tradability_status or 'unknown'} spread={item.spread_status or 'unavailable'}"
            )
            if item.why_still_worth_reviewing:
                lines.append("  why_review: " + "; ".join(item.why_still_worth_reviewing))
            if item.decision_missing_data:
                lines.append("  missing_data: " + "; ".join(item.decision_missing_data))
            if item.decision_warnings:
                lines.append("  decision_warnings: " + "; ".join(item.decision_warnings))
            if any("manip" in warning.casefold() or "illiquid" in warning.casefold() for warning in item.decision_warnings):
                lines.append("  manipulation_warning: verify liquidity, spread, and venue concentration manually")
        lines.append(f"  reason: {item.reason}")
        target = item.feedback_target or item.alert_id
        lines.append(f"  feedback_target: {target}")
        lines.append(f"  feedback_useful: make event-feedback-useful PROFILE={profile} FEEDBACK_TARGET='{target}'")
        lines.append(f"  feedback_late: make event-feedback-late PROFILE={profile} FEEDBACK_TARGET='{target}'")
        lines.append(
            f"  feedback_missing_confirmation: .venv/bin/python main.py --event-feedback-mark '{target}' "
            f"--event-feedback-label missing_confirmation --event-alpha-profile {profile}"
        )
        lines.append(
            f"  feedback_manipulation_risk: .venv/bin/python main.py --event-feedback-mark '{target}' "
            f"--event-feedback-label manipulation_risk --event-alpha-profile {profile}"
        )
        lines.append(f"  feedback_junk: make event-feedback-junk PROFILE={profile} FEEDBACK_TARGET='{target}'")
    lines.append("")

def _decision_score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}/100"
def _append_compact_item_section(
    lines: list[str],
    title: str,
    items: Iterable[EventAlphaNotificationInboxItem],
    *,
    profile: str,
    limit: int,
) -> None:
    rows = list(dict.fromkeys(items))
    lines.append(f"{title}: {len(rows)}")
    if not rows:
        lines.append("- none")
        lines.append("")
        return
    for idx, item in enumerate(rows[: max(0, limit)], start=1):
        target = item.feedback_target or item.alert_id
        lane_status = "sent" if item.sent else ("would-send" if item.would_send or item.blocked_by_guard else "review")
        lines.append(
            f"{idx}. {item.symbol or 'UNKNOWN'}/{item.coin_id or 'unknown'} "
            f"{lane_status} tier={item.tier or 'unknown'} playbook={item.playbook or 'unknown'}"
        )
        lines.append(
            f"   core_id: {item.core_opportunity_id or item.alert_id} · "
            f"state={item.final_state_after_quality_gate or item.delivery_state or 'unknown'} "
            f"route={item.final_route_after_quality_gate or 'unknown'}"
        )
        if item.card_path:
            lines.append(f"   card: {_card_label(item.card_path)}")
        lines.append(f"   feedback: make event-feedback-useful PROFILE={profile} FEEDBACK_TARGET='{target}'")
        if item.quality_gate_block_reason:
            lines.append(f"   gate: {item.quality_gate_block_reason}")
        lines.append(f"   why: {item.reason}")
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more in the full notification inbox")
    lines.append("")
def _append_run_section(lines: list[str], title: str, rows: Iterable[Mapping[str, Any]]) -> None:
    items = list(rows)
    lines.append(f"{title}: {len(items)}")
    if not items:
        lines.append("- none")
        lines.append("")
        return
    for row in items[:20]:
        lines.append(
            f"- run_id={row.get('run_id') or 'unknown'} "
            f"started_at={row.get('started_at') or 'unknown'} "
            f"profile={row.get('notification_profile') or row.get('profile') or 'default'} "
            f"scope={row.get('scope') or 'unknown'}:{row.get('scope_value') or 'unknown'}"
        )
        warnings = [str(item) for item in row.get("warnings") or [] if str(item)]
        if warnings:
            lines.append("  warnings: " + "; ".join(warnings[:5]))
        provider = row.get("provider_fail_fast_blocks") or []
        if provider:
            lines.append("  provider_fail_fast_blocks: " + "; ".join(str(item) for item in provider[:5]))
    lines.append("")
