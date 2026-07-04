"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (helpers)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
from .... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_router,
    event_core_opportunities,
    event_watchlist,
)
from ...artifacts import research_cards as event_research_cards
from ...radar import core_opportunity_store as event_core_opportunity_store
from .. import delivery
from .. import pipeline as event_alpha_notifications
from .models import *  # noqa: F403

def _format_notification_inbox_burn_in_review(result: EventAlphaNotificationInboxResult) -> str:
    sent_or_partial = (*result.sent_without_feedback, *result.partial_delivered_without_feedback)
    would_send = (*result.would_send_without_feedback, *result.would_send_blocked_without_feedback)
    active = (*sent_or_partial, *would_send, *result.high_priority_unreviewed, *result.triggered_fade_unreviewed)
    local_count = len(result.quality_gated_local_only) + len(result.weak_validated_local_only)
    queue = build_ranked_review_queue(result, limit=12)
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN REVIEW INBOX (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        (
            "summary: "
            f"sent_or_partial={len(sent_or_partial)} "
            f"would_send={len(would_send)} "
            f"active_unreviewed={len(active)} "
            f"research_review={len(result.research_review_without_feedback)} "
            f"near_miss={len(result.exploratory_without_feedback)} "
            f"local_or_quality_capped={local_count} "
            f"provider_degraded_runs={len(result.provider_degraded_runs)} "
            f"diagnostics_hidden={len(result.diagnostic_review_items_hidden)}"
        ),
        "",
    ]
    _append_review_queue_section(lines, "Ranked review queue", queue, profile=result.profile, limit=12)
    _append_compact_item_section(lines, "Would-send / sent core opportunities", active, profile=result.profile, limit=12)
    _append_compact_item_section(lines, "Research-review candidates", result.research_review_without_feedback, profile=result.profile, limit=8)
    _append_compact_item_section(lines, "Near-miss candidates", result.exploratory_without_feedback, profile=result.profile, limit=8)
    if local_count:
        lines.append(f"Local-only / quality-capped rows: {local_count}")
        lines.append("- collapsed in burn-in review; use the full inbox or quality review for row-level diagnostics")
        lines.append("")
    else:
        lines.append("Local-only / quality-capped rows: 0")
        lines.append("- none")
        lines.append("")
    _append_run_section(lines, "provider-degraded notification runs", result.provider_degraded_runs)
    if result.diagnostic_review_items_hidden:
        lines.append(f"Diagnostic/support rows hidden: {len(result.diagnostic_review_items_hidden)}")
        lines.append("- rerun with diagnostics enabled for source-noise/control row details")
        lines.append("")
    lines.append("Burn-in review is artifact-only; it does not send, trade, paper trade, or alter Event Alpha tiers.")
    return "\n".join(lines).rstrip()
def alert_snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    """Return true for support/control snapshots that should be hidden by default."""
    return (
        bool(row.get("is_diagnostic_snapshot"))
        or str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("core_opportunity_id_status") or "") == "diagnostic_support"
        or event_core_opportunities.row_is_diagnostic(row)
    )
def _is_triggered_fade(item: EventAlphaNotificationInboxItem) -> bool:
    return item.tier == "TRIGGERED_FADE" or item.playbook == "proxy_fade" or "TRIGGERED_FADE" in item.reason.upper()
def _is_weak_validated_local_only(
    item: EventAlphaNotificationInboxItem,
    alerts: Iterable[Mapping[str, Any]],
) -> bool:
    for alert in alerts:
        alert_key = str(alert.get("alert_key") or "")
        alert_id = str(alert.get("alert_id") or (f"ea:{alert_key}" if alert_key else ""))
        if item.alert_id not in {alert_id, f"ea:{alert_key}"} and item.alert_key != alert_key:
            continue
        if str(alert.get("relationship_type") or "") != "impact_hypothesis":
            return False
        if bool(alert.get("route_alertable")):
            return False
        components = alert.get("score_components") if isinstance(alert.get("score_components"), Mapping) else {}
        stage = str(alert.get("validation_stage") or components.get("validation_stage") or "")
        impact_path_strength = str(alert.get("impact_path_strength") or components.get("impact_path_strength") or "")
        impact_path_type = str(alert.get("impact_path_type") or components.get("impact_path_type") or "")
        opportunity_level = str(alert.get("opportunity_level") or components.get("opportunity_level") or "")
        why_digest_ineligible = str(alert.get("why_digest_ineligible") or components.get("why_digest_ineligible") or "")
        reason_text = " ".join(str(value or "") for value in (
            alert.get("route_reason"),
            alert.get("reason"),
            *((alert.get("quality_warnings") or []) if isinstance(alert.get("quality_warnings"), list) else []),
        )).casefold()
        return (
            stage == "catalyst_link_validated"
            or impact_path_strength in {"weak", "none"}
            or impact_path_type == "generic_cooccurrence_only"
            or opportunity_level in {"local_only", "exploratory"}
            or bool(why_digest_ineligible)
            or "impact_path_not_validated" in reason_text
            or "weak_validated" in reason_text
            or "generic_cooccurrence" in reason_text
        )
    return False
def _heartbeat_only(row: Mapping[str, Any]) -> bool:
    due = row.get("lane_counts_due") or {}
    sent = row.get("lane_counts_sent") or {}
    non_heartbeat_due = sum(_int(value) for key, value in dict(due).items() if key != "health_heartbeat")
    non_heartbeat_sent = sum(_int(value) for key, value in dict(sent).items() if key != "health_heartbeat")
    return bool(row.get("heartbeat_due") or row.get("heartbeat_sent")) and non_heartbeat_due == 0 and non_heartbeat_sent == 0
def _provider_degraded(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("partial_results")
        or _int(row.get("provider_failure_count")) > 0
        or row.get("provider_fail_fast_blocks")
        or row.get("runtime_budget_exhausted")
        or _degraded_warning(row.get("warnings") or ())
    )
def _degraded_warning(warnings: Iterable[Any]) -> bool:
    tokens = ("failed", "failure", "timeout", "dns", "429", "backoff", "runtime_budget")
    return any(any(token in str(warning).casefold() for token in tokens) for warning in warnings)
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
