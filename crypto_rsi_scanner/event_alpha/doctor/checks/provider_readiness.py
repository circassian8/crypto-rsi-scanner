"""Provider readiness and provider-specific preflight consistency checks."""

from __future__ import annotations

from ._utils import Messages, ctx_mapping, ctx_value, emit


def apply_structured_artifact_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    official_exchange_conflicts = ctx_mapping(ctx, "official_exchange_conflicts")
    official_exchange_activation_conflicts = ctx_mapping(ctx, "official_exchange_activation_conflicts")
    instrument_resolution_conflicts = ctx_mapping(ctx, "instrument_resolution_conflicts")
    scheduled_conflicts = ctx_mapping(ctx, "scheduled_conflicts")
    derivatives_conflicts = ctx_mapping(ctx, "derivatives_conflicts")

    for key in (
        "official_exchange_candidate_missing_source_fields",
        "official_exchange_listing_without_official_source",
        "official_exchange_secret_leak",
        "official_exchange_delisting_long_research",
        "official_exchange_quote_asset_misclassified",
        "official_exchange_major_pair_noise_promoted_early_long",
        "official_exchange_created_alert_rows",
    ):
        count = official_exchange_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "official_exchange_activation_missing_shared_schema",
        "official_exchange_activation_live_without_ledger",
        "official_exchange_activation_signed_listener_secret_leak",
        "official_exchange_activation_forbidden_side_effect_claim",
    ):
        count = official_exchange_activation_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "instrument_resolution_missing_canonical_id_when_fixture_has_it",
        "instrument_resolution_quote_asset_misclassified",
        "instrument_resolution_sector_visible_as_tradable",
    ):
        count = instrument_resolution_conflicts.get(key, 0)
        if count:
            blocker = strict or key in {
                "instrument_resolution_quote_asset_misclassified",
                "instrument_resolution_sector_visible_as_tradable",
            }
            emit(blockers, warnings, f"{key}={count}", blocker=blocker)
    if instrument_resolution_conflicts.get("instrument_resolution_coinalyze_symbol_unlinked", 0):
        warnings.append(
            "instrument_resolution_coinalyze_symbol_unlinked="
            f"{instrument_resolution_conflicts['instrument_resolution_coinalyze_symbol_unlinked']}"
        )
    for key in (
        "unlock_without_structured_evidence",
        "unlock_missing_event_time",
        "unlock_promoted_without_size_metrics",
        "media_unlock_promoted_structured",
        "stale_completed_catalyst_upcoming",
        "cryptopanic_unlock_proof",
        "scheduled_catalyst_created_alert_rows",
    ):
        count = scheduled_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    if scheduled_conflicts.get("calendar_event_missing_source_url", 0):
        message = f"calendar_event_missing_source_url={scheduled_conflicts['calendar_event_missing_source_url']}"
        emit(blockers, warnings, message, blocker=strict)
    for key in (
        "fade_review_without_completed_move",
        "fade_review_without_crowding_exhaustion",
        "fade_review_created_triggered_fade",
        "fade_review_created_normal_rsi_signal",
        "fade_review_notification_missing_disclaimer",
        "derivatives_artifact_secret_leak",
        "derivatives_metric_claim_implemented_missing",
        "stale_derivatives_snapshot_promoted_fade_review",
    ):
        count = derivatives_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "derivatives_state_missing_freshness_status",
        "derivatives_unit_metadata_missing",
        "confirmed_long_crowded_without_warning",
    ):
        count = derivatives_conflicts.get(key, 0)
        if count:
            warnings.append(f"{key}={count}")


def apply_preflight_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    strict = bool(ctx_value(ctx, "strict", False))
    live_provider_readiness_conflicts = ctx_mapping(ctx, "live_provider_readiness_conflicts")
    coinalyze_preflight_conflicts = ctx_mapping(ctx, "coinalyze_preflight_conflicts")
    bybit_announcements_conflicts = ctx_mapping(ctx, "bybit_announcements_conflicts")
    unlock_calendar_conflicts = ctx_mapping(ctx, "unlock_calendar_conflicts")
    dex_onchain_conflicts = ctx_mapping(ctx, "dex_onchain_conflicts")

    if live_provider_readiness_conflicts.get("live_provider_readiness_missing", 0):
        warnings.append(
            "live_provider_readiness_missing="
            f"{live_provider_readiness_conflicts['live_provider_readiness_missing']}"
        )
    for key in (
        "live_provider_readiness_secret_leak",
        "live_provider_readiness_live_calls_allowed_in_smoke",
        "live_provider_readiness_configured_missing_env",
    ):
        count = live_provider_readiness_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "coinalyze_preflight_secret_leak",
        "coinalyze_preflight_live_call_allowed_in_smoke",
        "coinalyze_preflight_configured_missing_env",
        "coinalyze_preflight_ready_without_request_ledger",
        "coinalyze_preflight_missing_fixture_parser_status",
        "coinalyze_preflight_forbidden_side_effect_claim",
        "coinalyze_rehearsal_secret_leak",
        "coinalyze_rehearsal_live_without_ledger",
        "coinalyze_rehearsal_live_call_allowed_in_smoke",
        "coinalyze_rehearsal_live_without_explicit_allow",
        "coinalyze_rehearsal_request_budget_exceeded",
        "coinalyze_rehearsal_success_without_derivatives_state",
        "coinalyze_rehearsal_success_without_crowding_candidates",
        "coinalyze_provider_health_healthy_without_successful_ledger",
        "coinalyze_rehearsal_forbidden_side_effect_claim",
        "coinalyze_supported_metric_implemented_missing_state",
    ):
        count = coinalyze_preflight_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "bybit_announcements_preflight_secret_leak",
        "bybit_announcements_preflight_live_call_allowed_in_smoke",
        "bybit_announcements_preflight_missing_fixture_parser_status",
        "bybit_announcements_rehearsal_secret_leak",
        "bybit_announcements_rehearsal_live_without_ledger",
        "bybit_announcements_rehearsal_live_without_explicit_allow",
        "bybit_announcements_rehearsal_unsupported_params",
        "bybit_announcements_rehearsal_forbidden_side_effect_claim",
    ):
        count = bybit_announcements_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "unlock_calendar_preflight_secret_leak",
        "unlock_calendar_preflight_live_without_ledger",
        "unlock_calendar_preflight_live_call_allowed_in_smoke",
        "unlock_calendar_preflight_missing_fixture_parser_status",
        "unlock_calendar_preflight_forbidden_side_effect_claim",
    ):
        count = unlock_calendar_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
    for key in (
        "dex_onchain_readiness_secret_leak",
        "dex_onchain_live_without_ledger",
        "dex_onchain_live_call_allowed_in_smoke",
        "dex_onchain_missing_fixture_parser_status",
        "dex_onchain_forbidden_side_effect_claim",
        "dex_low_liquidity_promoted_confirmed",
        "protocol_metric_missing_source_time",
    ):
        count = dex_onchain_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
