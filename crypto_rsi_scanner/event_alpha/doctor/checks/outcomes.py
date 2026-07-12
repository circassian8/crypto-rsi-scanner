"""Outcome, quality, watchlist, and incident consistency checks."""

from __future__ import annotations

from typing import Any, Mapping

from .. import check_registry
from ._utils import Messages, ctx_mapping, ctx_value, emit


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    strict_api = bool(ctx_value(ctx, "strict_api", False))
    core_store_available = bool(ctx_value(ctx, "core_store_available", False))
    quality = ctx_mapping(ctx, "quality")
    snapshot_core_conflicts = ctx_mapping(ctx, "snapshot_core_conflicts")
    watchlist_conflicts = ctx_mapping(ctx, "watchlist_conflicts")
    incident_linkage = ctx_mapping(ctx, "incident_linkage")
    feedback_integrity = ctx_mapping(ctx, "feedback_integrity")

    _apply_feedback_eligibility_checks(
        feedback_integrity,
        blockers=blockers,
        warnings=warnings,
        strict=strict,
    )

    if quality.get("quality_fields_missing_count", 0):
        message = (
            "quality fields missing: "
            f"total={quality['quality_fields_missing_count']} "
            f"hypotheses_missing_verdict={quality['hypothesis_rows_missing_opportunity_verdict']} "
            f"watchlist_missing={quality['watchlist_rows_missing_quality_fields']} "
            f"alerts_missing={quality['alert_rows_missing_quality_fields']}"
            f" fresh_hypotheses_missing_top_level={quality['fresh_hypothesis_rows_missing_top_level_quality']} "
            f"fresh_watchlist_missing_top_level={quality['fresh_watchlist_rows_missing_top_level_quality']} "
            f"fresh_alerts_missing_top_level={quality['fresh_alert_rows_missing_top_level_quality']} "
            f"legacy_quality_missing={quality['legacy_quality_missing_rows']}"
        )
        if ctx_value(ctx, "fresh_missing", 0):
            emit(blockers, warnings, message, blocker=strict)
        else:
            warnings.append(message)
    if ctx_value(ctx, "route_conflicts", 0):
        warnings.append(f"alertable_route_conflicts_with_opportunity_level={ctx_value(ctx, 'route_conflicts')}")
    for key, message_key in (
        ("route_mismatch", "alert_snapshot_route_mismatch_core_store"),
        ("level_mismatch", "alert_snapshot_level_mismatch_core_store"),
        ("live_confirmation_stale", "alert_snapshot_live_confirmation_stale"),
        ("core_resolution_missing", "alert_snapshot_core_resolution_missing"),
    ):
        count = snapshot_core_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{message_key}={count}", blocker=strict and core_store_available)
    if snapshot_core_conflicts.get("pre_reconciliation_alertable", 0):
        warnings.append(
            "alert_snapshot_pre_reconciliation_alertable="
            f"{snapshot_core_conflicts['pre_reconciliation_alertable']}"
        )
    for key, message_key in (
        ("diagnostic_support_alertable", "diagnostic_support_snapshot_alertable"),
        ("diagnostic_support_inherits_core_route", "diagnostic_support_snapshot_inherits_core_route"),
        ("duplicate_alertable_snapshot_for_core", "duplicate_alertable_snapshot_for_core"),
    ):
        count = snapshot_core_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{message_key}={count}", blocker=strict)
    if snapshot_core_conflicts.get("canonical_snapshot_missing_for_visible_core", 0):
        warnings.append(
            "canonical_snapshot_missing_for_visible_core="
            f"{snapshot_core_conflicts['canonical_snapshot_missing_for_visible_core']}"
        )
    if ctx_value(ctx, "fresh_route_conflicts", 0) and strict:
        blockers.append(f"fresh_quality_route_conflict_rows={ctx_value(ctx, 'fresh_route_conflicts')}")
    if ctx_value(ctx, "legacy_route_conflicts", 0):
        message = f"legacy_quality_conflict_rows={ctx_value(ctx, 'legacy_route_conflicts')}"
        emit(blockers, warnings, message, blocker=strict and strict_api)
    if ctx_value(ctx, "fresh_missing_final_route", 0) and strict:
        blockers.append(f"fresh_alert_rows_missing_final_route={ctx_value(ctx, 'fresh_missing_final_route')}")

    if watchlist_conflicts.get("quality_capped_watchlist_rows", 0):
        warnings.append(f"quality-capped rows present: {watchlist_conflicts['quality_capped_watchlist_rows']}")
    for key in (
        "non_hypothesis_watchlist_quality_conflicts",
        "hypothesis_watchlist_quality_conflicts",
        "watchlist_state_conflicts_with_quality",
    ):
        count = watchlist_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")
    if watchlist_conflicts.get("fresh_uncapped", 0):
        emit(blockers, warnings, f"fresh_watchlist_state_conflict_rows={watchlist_conflicts['fresh_uncapped']}", blocker=strict)
    if watchlist_conflicts.get("legacy", 0):
        message = f"legacy_watchlist_conflicts={watchlist_conflicts['legacy']}"
        emit(blockers, warnings, message, blocker=strict and strict_api)

    if incident_linkage.get("hypothesis_rows_missing_incident_id", 0):
        message = f"hypothesis_rows_missing_incident_id={incident_linkage['hypothesis_rows_missing_incident_id']}"
        emit(blockers, warnings, message, blocker=strict and bool(incident_linkage.get("fresh_missing_hypotheses", 0)))
    if incident_linkage.get("watchlist_hypothesis_rows_missing_incident_id", 0):
        message = (
            "watchlist_hypothesis_rows_missing_incident_id="
            f"{incident_linkage['watchlist_hypothesis_rows_missing_incident_id']}"
        )
        emit(blockers, warnings, message, blocker=strict and bool(incident_linkage.get("fresh_missing_watchlist", 0)))
    if incident_linkage.get("alert_hypothesis_rows_missing_incident_id", 0):
        message = f"alert_hypothesis_rows_missing_incident_id={incident_linkage['alert_hypothesis_rows_missing_incident_id']}"
        emit(blockers, warnings, message, blocker=strict and bool(incident_linkage.get("fresh_missing_alerts", 0)))
    for key in (
        "incident_rows_without_linked_hypotheses",
        "incident_rows_without_linked_watchlist",
        "diagnostic_incident_rows",
        "raw_observation_incident_rows",
        "external_context_incident_rows",
        "rejected_incident_rows",
        "canonical_unlinked_incidents",
    ):
        count = incident_linkage.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")
    for key in (
        "active_incident_without_qualified_link",
        "quality_blocked_links_promoting_incident",
        "incident_relevance_missing",
    ):
        count = incident_linkage.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "linked_incident_without_qualified_link",
        "weak_unqualified_incident_links",
        "quality_blocked_links_present",
        "garbage_primary_subject_incidents",
    ):
        count = incident_linkage.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")


def _apply_feedback_eligibility_checks(
    summary: Mapping[str, Any],
    *,
    blockers: Messages,
    warnings: Messages,
    strict: bool,
) -> None:
    if not summary:
        return

    def message(detail: str) -> str:
        return check_registry.format_check_message(
            "outcomes.feedback_eligibility_firewall",
            detail,
        )

    severe_fields = (
        "feedback_eligibility_contract_invalid",
        "feedback_persisted_eligible_invalid",
        "feedback_duplicate_rows",
        "feedback_future_rows",
        "feedback_unsafe_rows",
        "feedback_missing_core_rows",
        "feedback_ambiguous_core_rows",
        "feedback_duplicate_json_keys",
        "feedback_invalid_jsonl",
        "feedback_jsonl_read_errors",
    )
    for field in severe_fields:
        count = int(summary.get(field) or 0)
        if count:
            emit(blockers, warnings, message(f"{field}={count}"), blocker=strict)

    legacy = int(summary.get("feedback_legacy_rows") or 0)
    if legacy:
        warnings.append(message(f"feedback_legacy_rows_readable_but_ineligible={legacy}"))
    superseded = int(summary.get("feedback_superseded_rows") or 0)
    if superseded:
        warnings.append(message(f"feedback_superseded_rows={superseded}"))
    excluded = int(summary.get("feedback_rows_excluded") or 0)
    reasons = summary.get("feedback_exclusion_reason_counts")
    if excluded and isinstance(reasons, Mapping):
        reason_text = ",".join(
            f"{key}:{int(value)}"
            for key, value in sorted(reasons.items())
            if int(value)
        )
        warnings.append(
            message(
                f"feedback_rows_excluded={excluded}"
                + (f" reasons={reason_text}" if reason_text else "")
            )
        )
