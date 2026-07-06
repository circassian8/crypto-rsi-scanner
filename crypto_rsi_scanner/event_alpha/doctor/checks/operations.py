"""Event Alpha burn-in operation artifact checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import check_registry
from ._utils import Messages, ctx_mapping, ctx_value


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    daily_run = ctx_mapping(ctx, "daily_burn_in_run")
    scorecard = ctx_mapping(ctx, "burn_in_scorecard")
    source_yield = ctx_mapping(ctx, "source_yield_report")
    review_inbox = ctx_mapping(ctx, "daily_review_inbox")
    archive_manifest = ctx_mapping(ctx, "burn_in_archive_manifest")
    _check_daily_run(ctx, daily_run, blockers, warnings)
    _check_scorecard(scorecard, blockers)
    _check_source_yield(source_yield, blockers)
    _check_review_inbox(review_inbox, blockers, warnings)
    _check_archive_manifest(archive_manifest, blockers)


def _check_daily_run(ctx: object, daily_run: Mapping[str, Any], blockers: Messages, warnings: Messages) -> None:
    if not daily_run and _is_burn_in_namespace(ctx):
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_missing",
                "daily_burn_in_run_missing",
            )
        )
        return
    if not daily_run:
        return
    steps = [row for row in daily_run.get("steps") or [] if isinstance(row, Mapping)]
    missing_status = sum(1 for row in steps if not str(row.get("status") or "").strip())
    if missing_status:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_status",
                f"daily_burn_in_run_step_missing_status={missing_status}",
            )
        )
    missing_timeout = sum(1 for row in steps if row.get("timeout_seconds") in (None, ""))
    if missing_timeout:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_timeout",
                f"daily_burn_in_run_step_missing_timeout={missing_timeout}",
            )
        )
    side_effects = sum(1 for key in _FORBIDDEN_SIDE_EFFECT_FIELDS if _int(daily_run.get(key)) != 0)
    if side_effects:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_side_effects",
                f"daily_burn_in_run_forbidden_side_effect_claim={side_effects}",
            )
        )
    integrated_conflicts = ctx_mapping(ctx, "integrated_conflicts")
    if _int(integrated_conflicts.get("integrated_preview_lane_mismatch")):
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_integrated_preview",
                "daily_burn_in_integrated_preview_mismatch",
            )
        )


def _check_scorecard(scorecard: Mapping[str, Any], blockers: Messages) -> None:
    if not scorecard:
        return
    contract_counted = _int(scorecard.get("contract_counted_candidate_count"))
    real_candidates = _int(scorecard.get("real_burn_in_candidate_count"))
    if contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_contract_count",
                "burn_in_scorecard_contract_count_exceeds_real_candidates",
            )
        )
    if scorecard.get("evidence_scope") == "real_burn_in_evidence" and contract_counted == 0:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_real_scope",
                "burn_in_scorecard_real_scope_without_contract_candidates",
            )
        )
    support_rows = (
        _int(scorecard.get("fixture_candidates"))
        + _int(scorecard.get("fixture_candidate_count"))
        + _int(scorecard.get("preflight_diagnostic_rows"))
        + _int(scorecard.get("readiness_rows"))
        + _int(scorecard.get("source_coverage_rows"))
    )
    if support_rows and contract_counted and contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_contract_count",
                "burn_in_scorecard_counts_support_rows_as_real_candidates",
            )
        )
    if _int(scorecard.get("fixture_candidate_count")) and contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_scorecard_fixture_real",
                "daily_burn_in_scorecard_counts_fixture_as_real_candidate",
            )
        )


def _check_source_yield(source_yield: Mapping[str, Any], blockers: Messages) -> None:
    if not source_yield:
        return
    if "real_candidate_rows" not in source_yield:
        return
    real_rows = _int(source_yield.get("real_candidate_rows"))
    provider_candidate_rows = sum(
        _int(row.get("candidate_count"))
        for row in (source_yield.get("providers") or {}).values()
        if isinstance(row, Mapping)
    )
    if provider_candidate_rows > real_rows:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.source_yield_real_candidate_rows",
                "source_yield_counts_non_real_rows_as_candidate_yield",
            )
        )
    if (_int(source_yield.get("provider_readiness_rows")) or _int(source_yield.get("preflight_diagnostic_rows"))) and real_rows == 0 and provider_candidate_rows:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.source_yield_preflight_candidate_yield",
                "source_yield_counts_readiness_or_preflight_as_candidate_yield",
            )
        )


def _check_review_inbox(review_inbox: Mapping[str, Any], blockers: Messages, warnings: Messages) -> None:
    if not review_inbox:
        return
    items = [row for row in review_inbox.get("items") or [] if isinstance(row, Mapping)]
    missing_provenance = sum(1 for row in items if not row.get("candidate_provenance") or not row.get("source_artifact"))
    if missing_provenance:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_selected_provenance",
                f"review_inbox_selected_items_missing_provenance={missing_provenance}",
            )
        )
    hidden_selected = sum(1 for row in items if row.get("diagnostic_only") is True or row.get("preflight_only") is True)
    if hidden_selected:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_hidden_default",
                f"review_inbox_selected_diagnostic_or_preflight_only={hidden_selected}",
            )
        )
    if items and "generic_context_source_downranked" in (items[0].get("downrank_reason_codes") or []):
        accepted_below = any(
            "accepted_evidence_no_market_confirmation" in (row.get("review_value_reason_codes") or [])
            or "accepted_evidence_found" in (row.get("review_value_reason_codes") or [])
            for row in items[1:]
        )
        if accepted_below:
            warnings.append(
                check_registry.format_check_message(
                    "outcomes.review_inbox_generic_context_priority",
                    "review_inbox_generic_context_outranks_accepted_evidence",
                )
            )


def _check_archive_manifest(archive_manifest: Mapping[str, Any], blockers: Messages) -> None:
    if not archive_manifest:
        return
    if str(archive_manifest.get("archive_scope") or "") != "active_burn_in_namespaces":
        return
    non_burn_in = (
        _int(archive_manifest.get("included_without_burn_in_run_count"))
        + _int(archive_manifest.get("notification_rehearsal_included_count"))
        + _int(archive_manifest.get("no_key_included_count"))
        + _int(archive_manifest.get("provider_rehearsal_included_count"))
        + _int(archive_manifest.get("fixture_included_count"))
    )
    if non_burn_in:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_archive_scope",
                "daily_burn_in_archive_includes_non_burn_in_by_default",
            )
        )


def _is_burn_in_namespace(ctx: object) -> bool:
    namespace = str(ctx_value(ctx, "artifact_namespace", "") or "")
    profile = str(ctx_value(ctx, "profile", "") or "")
    status_obj = ctx_value(ctx, "namespace_status", None)
    status = str(getattr(status_obj, "status", "") or "")
    safe_for_burn = bool(getattr(status_obj, "safe_for_burn_in_measurement", False))
    return (
        namespace.startswith("live_burn_in_")
        or profile.startswith("live_burn_in")
        or safe_for_burn
        or status in {"active_live_rehearsal", "active"}
    )


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


_FORBIDDEN_SIDE_EFFECT_FIELDS = (
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)
