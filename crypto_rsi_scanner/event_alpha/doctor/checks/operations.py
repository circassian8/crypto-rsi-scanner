"""Event Alpha burn-in operation artifact checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import check_registry
from ._utils import Messages, ctx_mapping


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    scorecard = ctx_mapping(ctx, "burn_in_scorecard")
    source_yield = ctx_mapping(ctx, "source_yield_report")
    review_inbox = ctx_mapping(ctx, "daily_review_inbox")
    _check_scorecard(scorecard, blockers)
    _check_source_yield(source_yield, blockers)
    _check_review_inbox(review_inbox, blockers, warnings)


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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
