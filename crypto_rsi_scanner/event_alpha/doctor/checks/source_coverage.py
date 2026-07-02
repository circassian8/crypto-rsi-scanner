"""Source coverage and source-pack consistency checks."""

from __future__ import annotations

from ._utils import Messages, ctx_mapping, ctx_value, emit


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    core_store_available = bool(ctx_value(ctx, "core_store_available", False))
    source_coverage_report_conflicts = ctx_mapping(ctx, "source_coverage_report_conflicts")
    source_coverage_conflicts = ctx_mapping(ctx, "source_coverage_conflicts")
    cryptopanic_conflicts = ctx_mapping(ctx, "cryptopanic_conflicts")

    if source_coverage_report_conflicts.get("source_coverage_report_missing", 0):
        warnings.append(
            "source_coverage_report_missing="
            f"{source_coverage_report_conflicts['source_coverage_report_missing']}"
        )
    if source_coverage_report_conflicts.get("source_coverage_provider_status_unknown", 0):
        warnings.append(
            "source_coverage_provider_status_unknown="
            f"{source_coverage_report_conflicts['source_coverage_provider_status_unknown']}"
        )
    for key in (
        "source_coverage_provider_marked_healthy_without_observation",
        "source_coverage_context_provider_ranked_above_lane_critical",
        "source_coverage_coinalyze_missing_linked_artifact",
        "source_coverage_bybit_announcements_missing_linked_artifact",
        "source_coverage_unlock_calendar_missing_linked_artifact",
        "source_coverage_dex_onchain_missing_linked_artifact",
    ):
        count = source_coverage_report_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "source_coverage_category_priority_missing",
        "source_coverage_readiness_link_missing",
    ):
        count = source_coverage_report_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")

    if source_coverage_conflicts.get("source_pack_provider_status_missing", 0):
        warnings.append(
            "source_pack_provider_status_missing="
            f"{source_coverage_conflicts['source_pack_provider_status_missing']}"
        )
    if source_coverage_conflicts.get("missing_provider_recommendations_missing", 0):
        warnings.append(
            "missing_provider_recommendations_missing="
            f"{source_coverage_conflicts['missing_provider_recommendations_missing']}"
        )
    if source_coverage_conflicts.get("degraded_provider_absence_marked_meaningful", 0):
        message = (
            "degraded_provider_absence_marked_meaningful="
            f"{source_coverage_conflicts['degraded_provider_absence_marked_meaningful']}"
        )
        emit(blockers, warnings, message, blocker=strict)

    if cryptopanic_conflicts.get("cryptopanic_configured_but_not_observed", 0):
        warnings.append(
            "cryptopanic_configured_but_not_observed="
            f"{cryptopanic_conflicts['cryptopanic_configured_but_not_observed']}"
        )
    if cryptopanic_conflicts.get("cryptopanic_used_but_no_source_coverage_entry", 0):
        message = (
            "cryptopanic_used_but_no_source_coverage_entry="
            f"{cryptopanic_conflicts['cryptopanic_used_but_no_source_coverage_entry']}"
        )
        emit(blockers, warnings, message, blocker=strict)
    if cryptopanic_conflicts.get("cryptopanic_accepted_evidence_missing_from_card", 0):
        message = (
            "cryptopanic_accepted_evidence_missing_from_card="
            f"{cryptopanic_conflicts['cryptopanic_accepted_evidence_missing_from_card']}"
        )
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if cryptopanic_conflicts.get("cryptopanic_rejected_only_promoted", 0):
        message = (
            "cryptopanic_rejected_only_promoted="
            f"{cryptopanic_conflicts['cryptopanic_rejected_only_promoted']}"
        )
        emit(blockers, warnings, message, blocker=strict and core_store_available)
    if cryptopanic_conflicts.get("cryptopanic_token_printed_or_unredacted", 0):
        message = (
            "cryptopanic_token_printed_or_unredacted="
            f"{cryptopanic_conflicts['cryptopanic_token_printed_or_unredacted']}"
        )
        emit(blockers, warnings, message, blocker=strict)
    if cryptopanic_conflicts.get("cryptopanic_growth_unsupported_param_used", 0):
        message = (
            "cryptopanic_growth_unsupported_param_used="
            f"{cryptopanic_conflicts['cryptopanic_growth_unsupported_param_used']}"
        )
        emit(blockers, warnings, message, blocker=strict)
    for key in (
        "cryptopanic_duplicate_request_key",
        "cryptopanic_invalid_currency_code",
        "cryptopanic_empty_currency_request",
        "cryptopanic_coin_id_sent_as_currency",
        "cryptopanic_status_code_missing_on_http_failure",
        "cryptopanic_body_excerpt_unredacted_token",
    ):
        count = cryptopanic_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "cryptopanic_all_requests_failed",
        "cryptopanic_json_parse_errors",
        "cryptopanic_configured_but_unusable",
    ):
        count = cryptopanic_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")
    if cryptopanic_conflicts.get("cryptopanic_quota_exceeded", 0):
        message = f"cryptopanic_quota_exceeded={cryptopanic_conflicts['cryptopanic_quota_exceeded']}"
        emit(blockers, warnings, message, blocker=strict)
    if cryptopanic_conflicts.get("cryptopanic_request_ledger_missing_when_used", 0):
        message = (
            "cryptopanic_request_ledger_missing_when_used="
            f"{cryptopanic_conflicts['cryptopanic_request_ledger_missing_when_used']}"
        )
        emit(blockers, warnings, message, blocker=strict)
    for key in (
        "cryptopanic_success_with_backoff_status",
        "cryptopanic_restore_token_recommendation_when_configured",
    ):
        count = cryptopanic_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
