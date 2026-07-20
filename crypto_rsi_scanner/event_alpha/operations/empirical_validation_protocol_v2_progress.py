"""Current Protocol-v2 evidence progress beside the immutable readiness contract.

The 2026-07-16 readiness implementation is canonical empirical evidence and is
fingerprinted by the export policy.  This module projects later accepted human
decisions plus a dated, manually reconciled operator evidence frontier without
changing that evidence, reading ambient state, or opening the holdout.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence

from crypto_rsi_scanner.event_alpha.operations.bybit_liquidation_stream import (
    OFFICIAL_ALL_LIQUIDATION_DOC,
    PUBLIC_WEBSOCKET_URL,
    PUSH_FREQUENCY_MILLISECONDS,
    TOPIC_PREFIX,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_fee import (
    OFFICIAL_MAKER_TAKER_URL,
    SCHEMA_VERSION as TAKER_FEE_SCENARIO_SCHEMA_VERSION,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_cost import (
    SCHEMA_VERSION as COMPOSITE_EXECUTION_COST_SCHEMA_VERSION,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_funding import (
    INTERVAL_SCHEMA_VERSION as FUNDING_INTERVAL_SCENARIO_SCHEMA_VERSION,
    OFFICIAL_FUNDING_FEE_URL,
    OFFICIAL_FUNDING_HISTORY_URL,
    OFFICIAL_INSTRUMENT_INFO_URL,
    OFFICIAL_MARK_PRICE_KLINE_URL,
    SCHEMA_VERSION as FUNDING_SETTLEMENT_SCENARIO_SCHEMA_VERSION,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_validation_protocol_v2 import (
    CONTRACT_VERSION as FROZEN_CONTRACT_VERSION,
    readiness_sha256,
)
from crypto_rsi_scanner.event_alpha.operations.execution_quality_readiness import (
    BYBIT_NATIVE_METRICS,
    REMAINING_PROTOCOL_V2_COST_FIELDS,
    build_execution_quality_readiness,
)
from crypto_rsi_scanner.event_alpha.operations.tokenomist_v5_capture import (
    CONTRACT_VERSION as TOKENOMIST_CAPTURE_CONTRACT_VERSION,
)
from crypto_rsi_scanner.event_alpha.operations.tokenomist_v5_readiness import (
    LIVE_AUTH_ENV as TOKENOMIST_LIVE_AUTH_ENV,
)
from crypto_rsi_scanner.event_providers.tokenomist_v5 import (
    CAPTURE_CONTRACT as TOKENOMIST_RESPONSE_CONTRACT,
)


SCHEMA_ID = "decision_radar.empirical_protocol_v2_current_progress"
SCHEMA_VERSION = 1
PROGRESS_VERSION = "decision_radar_empirical_protocol_v2_current_progress_v19"
PROGRESS_SOURCE = (
    "accepted_decisions_and_verified_operator_state_as_of_2026_07_20_"
    "with_unsealed_identity_rederived_composite_execution_cost_"
    "and_unsealed_exact_expected_settlement_funding_interval_aggregation_"
    "and_exact_leg_taker_fee_"
    "application_two_exact_immutable_"
    "capture_round_trip_target_mid_notional_floor_"
    "sizing_separate_entry_exit_catalog_bound_"
    "dynamic_instrument_constraints_quantity_reconciled_round_trip_"
    "primitive_mid_reference_impact_semantics_native_"
    "Bybit_snapshot_fields_truthful_pending_cost_model_native_USDT_cost_unit_"
    "detached_native_liquidation_import_and_tokenomist_v5_fixture_capture_contract"
)
FROZEN_READINESS_SHA256 = (
    "683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603"
)
_CURRENT_BLOCKERS = (
    "live_market_temporal_baseline_not_yet_warm",
    "exact_eligible_instrument_set_not_sealed",
    "bybit_public_reachability_unproven_after_recorded_403",
    "genuine_execution_quality_capture_absent",
    "genuine_intraday_1h_4h_and_rsi_capture_absent",
    "genuine_bybit_rest_funding_open_interest_positioning_capture_absent",
    "genuine_bybit_liquidation_stream_capture_absent",
    "authoritative_catalyst_unlock_onchain_fundamental_and_official_macro_sources_not_sealed",
    "historical_outcome_recovery_incomplete",
    "explicit_human_review_timing_and_source_independence_labels_incomplete",
    "partitions_and_untouched_holdout_not_sealed",
    "cost_model_not_sealed",
    "universe_routes_independent_episodes_and_minimum_samples_not_sealed",
    "human_protocol_v2_annex_approval_absent",
)
_NEXT_SAFE_COMMANDS = (
    "make radar-market-no-send-readiness PYTHON=.venv/bin/python",
    "make radar-execution-quality-readiness PYTHON=.venv/bin/python",
    "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python",
    "make radar-execution-quality-bybit-round-trip "
    "BYBIT_ENTRY_EXECUTION_CAPTURE_NAMESPACE=<entry> "
    "BYBIT_EXIT_EXECUTION_CAPTURE_NAMESPACE=<exit> "
    "BYBIT_EXECUTION_INSTRUMENT_ID=<instrument> "
    "BYBIT_EXECUTION_POSITION_SIDE=<long_or_short> "
    "BYBIT_EXECUTION_TARGET_NOTIONAL_USDT=<usdt> PYTHON=.venv/bin/python",
    "make radar-intraday-bybit-readiness PYTHON=.venv/bin/python",
    "make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python",
    "make radar-derivatives-bybit-liquidation-smoke PYTHON=.venv/bin/python",
    "make radar-derivatives-bybit-liquidation-capture-smoke PYTHON=.venv/bin/python",
    "make radar-calendar-official-readiness PYTHON=.venv/bin/python",
    "make radar-unlock-tokenomist-v5-readiness PYTHON=.venv/bin/python",
    "make radar-unlock-tokenomist-v5-capture-smoke PYTHON=.venv/bin/python",
    "make radar-outcome-price-recovery-readiness PYTHON=.venv/bin/python",
    "make radar-review-timing-queue PYTHON=.venv/bin/python",
    "make event-alpha-source-independence-oos-readiness PYTHON=.venv/bin/python",
    "make radar-research-protocol-v2-progress-check PYTHON=.venv/bin/python",
)
_SAFETY_ZERO_FIELDS = (
    "provider_calls",
    "websocket_connections",
    "credential_reads",
    "environment_reads",
    "file_reads",
    "file_writes",
    "holdout_reads",
    "sends",
    "trades",
    "orders",
    "paper_trades",
    "rsi_writes",
    "event_alpha_fade_triggers",
)
_EXPECTED_EXECUTION_DECISION = {
    "venue_id": "bybit",
    "instrument_mode": "usdt_linear_perpetual",
    "quote_currency": "USDT",
    "primary_cost_currency": "USDT",
    "primary_cost_currency_policy": (
        "native_USDT_only_no_USD_conversion_or_equivalence"
    ),
    "primary_cost_currency_policy_sealed": True,
    "usd_equivalence_assumed": False,
    "protocol_v2_cost_model_sealed": False,
    "remaining_protocol_v2_cost_fields": list(REMAINING_PROTOCOL_V2_COST_FIELDS),
    "fee_rate_authority_status": (
        "unsealed_public_reference_not_account_authoritative_authenticated_"
        "account_endpoint_outside_public_only_scope"
    ),
    "account_specific_fee_rate_access_authorized": False,
    "official_fee_sources_reviewed_at": "2026-07-20",
    "selected_native_snapshot_fields": list(BYBIT_NATIVE_METRICS),
    "generic_cross_venue_projection_available": False,
    "selected_impact_reference": "mid_price",
    "selected_side_impact_includes_crossing_half_spread": True,
    "standalone_spread_addition_to_selected_side_impact_permitted": False,
    "round_trip_impact_requires_entry_and_exit_snapshots": True,
    "impact_cost_application_policy_sealed": False,
    "buy_impact_size_basis": "exact_usdt_spend",
    "sell_impact_size_basis": "exact_usdt_proceeds",
    "same_numeric_usdt_notional_proves_same_base_quantity": False,
    "round_trip_base_quantity_reconciliation_implemented": True,
    "round_trip_base_quantity_policy_sealed": False,
    "round_trip_size_basis": "same_exact_base_quantity_across_distinct_books",
    "round_trip_visible_book_schema_version": (
        "crypto_radar.bybit_visible_book_round_trip.v3"
    ),
    "round_trip_visible_book_order_style": "immediately_marketable_book_walk",
    "round_trip_visible_book_cost_basis": "entry_mid_notional_usdt",
    "round_trip_visible_book_realized_execution": False,
    "round_trip_quantity_unit": "base_asset",
    "round_trip_quantity_semantics": (
        "bybit_USDT_linear_contract_quantity_in_underlying_token"
    ),
    "round_trip_quantity_source_url": (
        "https://www.bybit.com/en/help-center/article/Order-Cost-USDT-Contract"
    ),
    "instrument_order_constraints_implemented": True,
    "instrument_constraint_fields": [
        "quantity_step",
        "minimum_order_quantity",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
    ],
    "instrument_constraint_source_url": (
        "https://bybit-exchange.github.io/docs/v5/market/instrument"
    ),
    "instrument_maximums_dynamic": True,
    "instrument_maximums_revalidated_each_catalog_capture": True,
    "instrument_constraints_causality_required": True,
    "instrument_constraints_freshness_policy_sealed": False,
    "minimum_order_quantity_enforced": True,
    "minimum_notional_enforced_on_entry_and_exit_visible_quote_value": True,
    "order_style_quantity_eligibility_reported": True,
    "entry_exit_order_style_policy_sealed": False,
    "dynamic_constraints_revalidated_per_leg": True,
    "separate_entry_exit_constraint_lineages_required": True,
    "exit_constraint_snapshot_required_after_entry": True,
    "constraint_values_may_change_between_legs": True,
    "per_leg_order_style_eligibility_reported": True,
    "round_trip_same_style_intersection_reported": True,
    "same_order_style_required_by_primitive": False,
    "target_notional_sizing_implemented": True,
    "target_notional_sizing_schema_version": (
        "crypto_radar.bybit_target_entry_mid_notional_sizing.v1"
    ),
    "target_notional_round_trip_schema_version": (
        "crypto_radar.bybit_target_notional_visible_book_round_trip.v2"
    ),
    "target_notional_input_unit": "USDT",
    "target_notional_reference": "entry_mid_price",
    "target_notional_rounding_mode": "floor_to_quantity_step",
    "target_notional_does_not_exceed_reference": True,
    "target_notional_shortfall_bound": (
        "strictly_less_than_one_quantity_step_at_entry_mid"
    ),
    "target_notional_is_quote_budget": False,
    "marketable_quote_value_may_exceed_target_due_spread_and_impact": True,
    "target_notional_round_trip_identity_reconciled": True,
    "capture_pair_round_trip_implemented": True,
    "capture_pair_round_trip_schema_version": (
        "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1"
    ),
    "capture_pair_exact_namespaces_required": True,
    "capture_pair_latest_pointer_used": False,
    "capture_pair_both_strict_clean_required": True,
    "capture_pair_both_completion_fresh_required": True,
    "capture_pair_windows_ordered_non_overlapping": True,
    "capture_pair_base_and_namespaces_descriptor_held_together": True,
    "capture_pair_provider_calls": 0,
    "capture_pair_writes_performed": False,
    "capture_pair_protocol_v2_annex_bound": False,
    "capture_pair_protocol_v2_evidence_eligible": False,
    "immediately_marketable_liquidity_role": "taker",
    "marketable_limit_immediate_fill_liquidity_role": "taker",
    "maker_liquidity_scenario_modeled": False,
    "taker_fee_application_implemented": True,
    "taker_fee_scenario_schema_version": TAKER_FEE_SCENARIO_SCHEMA_VERSION,
    "taker_fee_rate_unit": "fraction",
    "taker_fee_applied_to_each_executed_leg_quote_value": True,
    "taker_fee_effective_window_must_cover_both_legs": True,
    "taker_fee_source_reference_required": True,
    "taker_fee_source_sealed": False,
    "taker_fee_protocol_v2_annex_bound": False,
    "taker_fee_provider_calls": 0,
    "taker_fee_writes_performed": False,
    "official_maker_taker_url": OFFICIAL_MAKER_TAKER_URL,
    "funding_settlement_application_implemented": True,
    "funding_settlement_scenario_schema_version": (
        FUNDING_SETTLEMENT_SCENARIO_SCHEMA_VERSION
    ),
    "funding_rate_unit": "fraction",
    "funding_position_value_formula": (
        "base_quantity_times_settlement_mark_price"
    ),
    "funding_position_cashflow_sign_convention": (
        "positive_received_negative_paid"
    ),
    "positive_funding_long_pays_short": True,
    "negative_funding_short_pays_long": True,
    "settlement_mark_price_required": True,
    "single_funding_event_arithmetic_implemented": True,
    "funding_interval_aggregation_implemented": True,
    "funding_interval_scenario_schema_version": (
        FUNDING_INTERVAL_SCENARIO_SCHEMA_VERSION
    ),
    "expected_funding_settlement_set_reconciled": True,
    "funding_settlement_order_strict": True,
    "operator_supplied_schedule_coverage_complete_possible": True,
    "funding_interval_coverage_scope": (
        "operator_supplied_unsealed_expected_settlement_schedule"
    ),
    "holding_interval_funding_coverage_complete": False,
    "funding_schedule_source_sealed": False,
    "funding_rate_source_sealed": False,
    "settlement_mark_source_sealed": False,
    "funding_settlement_protocol_v2_annex_bound": False,
    "funding_settlement_provider_calls": 0,
    "funding_settlement_writes_performed": False,
    "official_funding_fee_url": OFFICIAL_FUNDING_FEE_URL,
    "official_funding_history_url": OFFICIAL_FUNDING_HISTORY_URL,
    "official_instrument_info_url": OFFICIAL_INSTRUMENT_INFO_URL,
    "official_mark_price_kline_url": OFFICIAL_MARK_PRICE_KLINE_URL,
    "composite_execution_cost_implemented": True,
    "composite_execution_cost_schema_version": (
        COMPOSITE_EXECUTION_COST_SCHEMA_VERSION
    ),
    "composite_component_identity_reconciled": True,
    "composite_component_values_fully_rederived": True,
    "composite_modeled_component_scope": (
        "visible_book_plus_unsealed_taker_fee_plus_operator_supplied_"
        "funding_schedule"
    ),
    "composite_complete_protocol_v2_cost_model": False,
    "composite_funding_interval_coverage_complete": False,
    "composite_latency_cost_included": False,
    "composite_beyond_visible_book_slippage_included": False,
    "composite_unavailable_cost_policy_sealed": False,
    "composite_provider_calls": 0,
    "composite_writes_performed": False,
    "target_notional_tier_set_sealed": False,
    "base_quantity_selection_policy_sealed": False,
    "exact_eligible_instrument_set_sealed": False,
    "data_boundary": "public_market_data_only",
    "credentials_or_private_account_data": False,
    "orders_or_execution_or_trading": False,
}


def current_progress_values() -> dict[str, Any]:
    """Return accepted progress derived only from deterministic static contracts."""

    execution = build_execution_quality_readiness()
    impact = dict(execution.impact_cost_semantics)
    impact["instrument_constraint_fields"] = list(
        impact["instrument_constraint_fields"]
    )
    frozen_digest = readiness_sha256()
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "progress_version": PROGRESS_VERSION,
        "as_of": "2026-07-20",
        "status": "venue_selected_evidence_collection_blocked",
        "source": PROGRESS_SOURCE,
        "frozen_readiness_contract": {
            "contract_version": FROZEN_CONTRACT_VERSION,
            "sha256": frozen_digest,
            "expected_sha256": FROZEN_READINESS_SHA256,
            "mutated": frozen_digest != FROZEN_READINESS_SHA256,
            "protocol_frozen": False,
            "holdout_accessed": False,
        },
        "confirmed_execution_decision": {
            "source_contract_version": execution.contract_version,
            "venue_id": execution.selected_venue,
            "instrument_mode": "usdt_linear_perpetual",
            "quote_currency": execution.quote_currency,
            "primary_cost_currency": execution.primary_cost_currency,
            "primary_cost_currency_policy": execution.primary_cost_currency_policy,
            "primary_cost_currency_policy_sealed": (
                execution.primary_cost_currency_policy_sealed
            ),
            "usd_equivalence_assumed": execution.usd_equivalence_assumed,
            "protocol_v2_cost_model_sealed": execution.protocol_v2_cost_model_sealed,
            "remaining_protocol_v2_cost_fields": list(
                execution.remaining_protocol_v2_cost_fields
            ),
            "fee_rate_authority_status": execution.fee_rate_authority_status,
            "account_specific_fee_rate_access_authorized": (
                execution.account_specific_fee_rate_access_authorized
            ),
            "official_fee_sources_reviewed_at": (
                execution.official_fee_sources_reviewed_at
            ),
            "selected_native_snapshot_fields": list(
                execution.selected_native_snapshot_fields
            ),
            "generic_cross_venue_projection_available": (
                execution.generic_cross_venue_projection_available
            ),
            **impact,
            "eligible_instrument_selection_rule": (
                execution.eligible_instrument_selection_rule
            ),
            "exact_eligible_instrument_ids": list(execution.eligible_instrument_set),
            "exact_eligible_instrument_set_sealed": (
                execution.eligible_instrument_set_frozen
            ),
            "data_boundary": "public_market_data_only",
            "jurisdiction_and_account_eligibility": (
                execution.jurisdiction_and_account_eligibility_confirmation
            ),
            "confirmed_at": execution.human_decision_confirmed_at,
            "credentials_or_private_account_data": False,
            "orders_or_execution_or_trading": False,
        },
        "native_liquidation_contract": {
            "venue_id": "bybit",
            "transport": "public_websocket",
            "websocket_url": PUBLIC_WEBSOCKET_URL,
            "topic_template": f"{TOPIC_PREFIX}{{instrument_id}}",
            "push_frequency_milliseconds": PUSH_FREQUENCY_MILLISECONDS,
            "source_contract_url": OFFICIAL_ALL_LIQUIDATION_DOC,
            "required_provider_fields": ["T", "s", "S", "v", "p"],
            "provider_side_semantics": {
                "Buy": "long_position_liquidated",
                "Sell": "short_position_liquidated",
            },
            "offline_exact_message_normalizer_implemented": True,
            "operator_transcript_immutable_import_implemented": True,
            "operator_import_scope": "selected_application_payloads",
            "operator_import_coverage_status": "observed_messages_only",
            "operator_import_coverage_complete": False,
            "project_websocket_listener_implemented": False,
            "project_transport_capture_implemented": False,
            "genuine_capture_present": False,
            "runtime_authorization_created": False,
            "provider_connection_attempted": False,
            "protocol_v2_annex_bound": False,
            "protocol_v2_evidence_eligible": False,
            "research_only": True,
        },
        "structured_unlock_contract": {
            "provider": "tokenomist",
            "provider_api_version": "v5",
            "legacy_provider_api_version": "v4",
            "legacy_v4_status": "deprecated",
            "legacy_v4_live_eligible": False,
            "source_role": "cliff_unlock_context",
            "response_fixture_contract": TOKENOMIST_RESPONSE_CONTRACT,
            "offline_response_normalizer_implemented": True,
            "immutable_fixture_capture_contract_version": (
                TOKENOMIST_CAPTURE_CONTRACT_VERSION
            ),
            "strict_fixture_capture_doctor_implemented": True,
            "fixture_capture_retained": False,
            "fixture_capture_authority_eligible": False,
            "full_multipage_capture_contract_implemented": False,
            "live_transport_implemented": False,
            "genuine_capture_present": False,
            "runtime_authorization_env": TOKENOMIST_LIVE_AUTH_ENV,
            "runtime_authorization_created": False,
            "subscription_terms_approved": False,
            "genuine_bytes_retention_approved": False,
            "genuine_bytes_standard_export_approved": False,
            "provider_call_attempted": False,
            "protocol_v2_annex_bound": False,
            "protocol_v2_evidence_eligible": False,
            "research_only": True,
        },
        "current_activation_blockers": list(_CURRENT_BLOCKERS),
        "next_safe_commands": list(_NEXT_SAFE_COMMANDS),
        "safety": {field: 0 for field in _SAFETY_ZERO_FIELDS},
        "research_only": True,
    }


def validate_current_progress(value: Mapping[str, Any]) -> list[str]:
    """Validate the closed current-progress projection and its audit boundary."""

    errors: list[str] = []
    expected_top = {
        "schema_id",
        "schema_version",
        "progress_version",
        "as_of",
        "status",
        "source",
        "frozen_readiness_contract",
        "confirmed_execution_decision",
        "native_liquidation_contract",
        "structured_unlock_contract",
        "current_activation_blockers",
        "next_safe_commands",
        "safety",
        "research_only",
    }
    if set(value) != expected_top:
        errors.append("top_level_schema_mismatch")
        return errors
    if value.get("schema_id") != SCHEMA_ID or value.get("schema_version") != 1:
        errors.append("schema_identity_mismatch")
    if value.get("progress_version") != PROGRESS_VERSION:
        errors.append("progress_version_mismatch")
    if value.get("as_of") != "2026-07-20":
        errors.append("as_of_mismatch")
    if value.get("source") != PROGRESS_SOURCE:
        errors.append("source_mismatch")
    if value.get("status") != "venue_selected_evidence_collection_blocked":
        errors.append("status_mismatch")

    frozen = value.get("frozen_readiness_contract")
    if not isinstance(frozen, Mapping):
        errors.append("frozen_readiness_contract_invalid")
    else:
        if frozen.get("sha256") != FROZEN_READINESS_SHA256:
            errors.append("frozen_readiness_contract_digest_mismatch")
        if frozen.get("expected_sha256") != FROZEN_READINESS_SHA256:
            errors.append("frozen_readiness_expected_digest_mismatch")
        if frozen.get("mutated") is not False:
            errors.append("frozen_readiness_contract_mutated")
        if frozen.get("protocol_frozen") is not False:
            errors.append("protocol_v2_must_remain_unfrozen")
        if frozen.get("holdout_accessed") is not False:
            errors.append("holdout_accessed")

    decision = value.get("confirmed_execution_decision")
    if not isinstance(decision, Mapping):
        errors.append("confirmed_execution_decision_invalid")
    else:
        for key, expected_value in _EXPECTED_EXECUTION_DECISION.items():
            if decision.get(key) != expected_value:
                errors.append(f"confirmed_execution_decision_{key}_mismatch")
        if decision.get("exact_eligible_instrument_ids") != []:
            errors.append("exact_eligible_instrument_ids_must_remain_unsealed")

    liquidation = value.get("native_liquidation_contract")
    expected_liquidation = {
        "venue_id": "bybit",
        "transport": "public_websocket",
        "websocket_url": PUBLIC_WEBSOCKET_URL,
        "topic_template": f"{TOPIC_PREFIX}{{instrument_id}}",
        "push_frequency_milliseconds": PUSH_FREQUENCY_MILLISECONDS,
        "source_contract_url": OFFICIAL_ALL_LIQUIDATION_DOC,
        "required_provider_fields": ["T", "s", "S", "v", "p"],
        "provider_side_semantics": {
            "Buy": "long_position_liquidated",
            "Sell": "short_position_liquidated",
        },
        "offline_exact_message_normalizer_implemented": True,
        "operator_transcript_immutable_import_implemented": True,
        "operator_import_scope": "selected_application_payloads",
        "operator_import_coverage_status": "observed_messages_only",
        "operator_import_coverage_complete": False,
        "project_websocket_listener_implemented": False,
        "project_transport_capture_implemented": False,
        "genuine_capture_present": False,
        "runtime_authorization_created": False,
        "provider_connection_attempted": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }
    if liquidation != expected_liquidation:
        errors.append("native_liquidation_contract_mismatch")

    unlock = value.get("structured_unlock_contract")
    expected_unlock = {
        "provider": "tokenomist",
        "provider_api_version": "v5",
        "legacy_provider_api_version": "v4",
        "legacy_v4_status": "deprecated",
        "legacy_v4_live_eligible": False,
        "source_role": "cliff_unlock_context",
        "response_fixture_contract": TOKENOMIST_RESPONSE_CONTRACT,
        "offline_response_normalizer_implemented": True,
        "immutable_fixture_capture_contract_version": (
            TOKENOMIST_CAPTURE_CONTRACT_VERSION
        ),
        "strict_fixture_capture_doctor_implemented": True,
        "fixture_capture_retained": False,
        "fixture_capture_authority_eligible": False,
        "full_multipage_capture_contract_implemented": False,
        "live_transport_implemented": False,
        "genuine_capture_present": False,
        "runtime_authorization_env": TOKENOMIST_LIVE_AUTH_ENV,
        "runtime_authorization_created": False,
        "subscription_terms_approved": False,
        "genuine_bytes_retention_approved": False,
        "genuine_bytes_standard_export_approved": False,
        "provider_call_attempted": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }
    if unlock != expected_unlock:
        errors.append("structured_unlock_contract_mismatch")

    blockers = value.get("current_activation_blockers")
    if blockers != list(_CURRENT_BLOCKERS):
        errors.append("current_activation_blockers_mismatch")
    elif "execution_venue_not_selected" in blockers:
        errors.append("superseded_venue_blocker_present")
    if value.get("next_safe_commands") != list(_NEXT_SAFE_COMMANDS):
        errors.append("next_safe_commands_mismatch")

    safety = value.get("safety")
    if not isinstance(safety, Mapping) or set(safety) != set(_SAFETY_ZERO_FIELDS):
        errors.append("safety_schema_mismatch")
    elif any(safety.get(field) != 0 for field in _SAFETY_ZERO_FIELDS):
        errors.append("safety_boundary_violated")
    if value.get("research_only") is not True:
        errors.append("research_only_required")
    return errors


def canonical_progress_bytes(value: Mapping[str, Any] | None = None) -> bytes:
    payload = dict(value) if value is not None else current_progress_values()
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def progress_sha256(value: Mapping[str, Any] | None = None) -> str:
    return hashlib.sha256(canonical_progress_bytes(value)).hexdigest()


def format_current_progress(value: Mapping[str, Any] | None = None) -> str:
    payload = deepcopy(dict(value) if value is not None else current_progress_values())
    frozen = payload["frozen_readiness_contract"]
    decision = payload["confirmed_execution_decision"]
    liquidation = payload["native_liquidation_contract"]
    unlock = payload["structured_unlock_contract"]
    lines = [
        "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS",
        f"status={payload['status']}",
        f"as_of={payload['as_of']} progress_sha256={progress_sha256(payload)}",
        (
            "frozen_readiness_contract="
            f"{frozen['contract_version']} sha256={frozen['sha256']} mutated=false"
        ),
        "protocol_frozen=false holdout_accessed=false",
        (
            "selected_execution_surface="
            f"{decision['venue_id']}:{decision['instrument_mode']}:"
            f"{decision['quote_currency']} data_boundary={decision['data_boundary']}"
        ),
        (
            "primary_cost_currency="
            f"{decision['primary_cost_currency']} policy="
            f"{decision['primary_cost_currency_policy']} sealed=true "
            "USD_equivalence_assumed=false"
        ),
        "protocol_v2_cost_model_sealed=false remaining_cost_fields="
        + ",".join(decision["remaining_protocol_v2_cost_fields"]),
        f"fee_rate_authority_status={decision['fee_rate_authority_status']}",
        "selected_native_snapshot_fields="
        + ",".join(decision["selected_native_snapshot_fields"]),
        "generic_cross_venue_projection_available=false",
        "selected_side_impact_reference=mid_price includes_crossing_half_spread=true",
        "standalone_spread_addition_permitted=false "
        "round_trip_requires_entry_and_exit_snapshots=true "
        "impact_cost_application_policy_sealed=false",
        "buy_impact_size_basis=exact_usdt_spend "
        "sell_impact_size_basis=exact_usdt_proceeds",
        "same_numeric_usdt_notional_proves_same_base_quantity=false "
        "round_trip_base_quantity_reconciliation_implemented=true",
        "round_trip_base_quantity_policy_sealed=false "
        "round_trip_size_basis=same_exact_base_quantity_across_distinct_books",
        (
            "round_trip_visible_book_model="
            f"{decision['round_trip_visible_book_schema_version']} "
            f"order_style={decision['round_trip_visible_book_order_style']} "
            f"cost_basis={decision['round_trip_visible_book_cost_basis']} "
            "realized_execution=false"
        ),
        (
            "round_trip_quantity_unit="
            f"{decision['round_trip_quantity_unit']} semantics="
            f"{decision['round_trip_quantity_semantics']}"
        ),
        (
            "instrument_order_constraints_implemented=true fields="
            + ",".join(decision["instrument_constraint_fields"])
        ),
        (
            "instrument_maximums_dynamic=true "
            "revalidated_each_catalog_capture=true causality_required=true"
        ),
        (
            "instrument_constraints_freshness_policy_sealed=false "
            "entry_exit_order_style_policy_sealed=false"
        ),
        (
            "dynamic_constraints_revalidated_per_leg=true "
            "separate_entry_exit_constraint_lineages_required=true "
            "exit_constraint_snapshot_required_after_entry=true"
        ),
        (
            "constraint_values_may_change_between_legs=true "
            "per_leg_order_style_eligibility_reported=true "
            "round_trip_same_style_intersection_reported=true "
            "same_order_style_required_by_primitive=false"
        ),
        (
            "minimum_order_quantity_enforced=true "
            "minimum_notional_enforced_on_entry_and_exit_visible_quote_value=true "
            "order_style_quantity_eligibility_reported=true"
        ),
        (
            "target_notional_sizing_implemented=true sizing_schema="
            f"{decision['target_notional_sizing_schema_version']} "
            "round_trip_schema="
            f"{decision['target_notional_round_trip_schema_version']}"
        ),
        (
            "target_notional_input_unit=USDT reference=entry_mid_price "
            "rounding=floor_to_quantity_step does_not_exceed_reference=true"
        ),
        (
            "target_notional_shortfall_bound="
            f"{decision['target_notional_shortfall_bound']} "
            "round_trip_identity_reconciled=true"
        ),
        (
            "target_notional_is_quote_budget=false "
            "marketable_quote_value_may_exceed_target_due_spread_and_impact=true"
        ),
        (
            "immediately_marketable_liquidity_role=taker "
            "marketable_limit_immediate_fill_liquidity_role=taker "
            "maker_liquidity_scenario_modeled=false"
        ),
        (
            "taker_fee_application_implemented=true schema="
            f"{decision['taker_fee_scenario_schema_version']} "
            "rate_unit=fraction"
        ),
        (
            "taker_fee_applied_to_each_executed_leg_quote_value=true "
            "effective_window_must_cover_both_legs=true "
            "source_reference_required=true"
        ),
        (
            "taker_fee_source_sealed=false protocol_v2_annex_bound=false "
            "provider_calls=0 writes_performed=false"
        ),
        (
            "funding_settlement_application_implemented=true schema="
            f"{decision['funding_settlement_scenario_schema_version']} "
            "rate_unit=fraction"
        ),
        (
            "funding_position_value_formula="
            f"{decision['funding_position_value_formula']} "
            "cashflow_sign=positive_received_negative_paid"
        ),
        (
            "positive_funding_long_pays_short=true "
            "negative_funding_short_pays_long=true "
            "settlement_mark_price_required=true"
        ),
        (
            "single_funding_event_arithmetic_implemented=true "
            "funding_interval_aggregation_implemented=true schema="
            f"{decision['funding_interval_scenario_schema_version']} "
            "holding_interval_funding_coverage_complete=false"
        ),
        (
            "expected_funding_settlement_set_reconciled=true "
            "funding_settlement_order_strict=true "
            "operator_supplied_schedule_coverage_complete_possible=true"
        ),
        (
            "funding_interval_coverage_scope="
            f"{decision['funding_interval_coverage_scope']}"
        ),
        (
            "funding_schedule_source_sealed=false "
            "funding_rate_source_sealed=false "
            "settlement_mark_source_sealed=false "
            "protocol_v2_annex_bound=false provider_calls=0 "
            "writes_performed=false"
        ),
        (
            "composite_execution_cost_implemented=true schema="
            f"{decision['composite_execution_cost_schema_version']}"
        ),
        (
            "composite_component_identity_reconciled=true "
            "component_values_fully_rederived=true scope="
            f"{decision['composite_modeled_component_scope']}"
        ),
        (
            "composite_complete_protocol_v2_cost_model=false "
            "funding_interval_coverage_complete=false "
            "latency_cost_included=false "
            "beyond_visible_book_slippage_included=false "
            "unavailable_cost_policy_sealed=false"
        ),
        "composite_provider_calls=0 writes_performed=false",
        (
            "capture_pair_round_trip_implemented=true schema="
            f"{decision['capture_pair_round_trip_schema_version']}"
        ),
        (
            "capture_pair_exact_namespaces_required=true latest_pointer_used=false "
            "both_strict_clean_required=true both_completion_fresh_required=true"
        ),
        (
            "capture_pair_windows_ordered_non_overlapping=true "
            "base_and_namespaces_descriptor_held_together=true "
            "provider_calls=0 writes_performed=false"
        ),
        (
            "capture_pair_protocol_v2_annex_bound=false "
            "protocol_v2_evidence_eligible=false"
        ),
        (
            "target_notional_tier_set_sealed=false "
            "base_quantity_selection_policy_sealed=false"
        ),
        "eligible_instrument_set=not_yet_sealed",
        f"eligible_instrument_selection_rule={decision['eligible_instrument_selection_rule']}",
        (
            "native_liquidation_surface="
            f"{liquidation['transport']}:{liquidation['topic_template']} "
            "offline_normalizer=true detached_import=true "
            "project_listener=false project_transport_capture=false "
            "genuine_capture=false coverage=observed_messages_only"
        ),
        (
            "structured_unlock_surface="
            f"{unlock['provider']}:{unlock['provider_api_version']} "
            "offline_normalizer=true fixture_capture_doctor=true "
            "full_multipage=false live_transport=false genuine_capture=false "
            "protocol_v2_evidence=false"
        ),
        (
            "provider_calls=0 credential_reads=0 environment_reads=0 file_reads=0 "
            "file_writes=0 holdout_reads=0"
        ),
        "research_only=true no_orders=true no_trading=true",
        "",
        "Current unresolved activation blockers:",
        *(f"- {blocker}" for blocker in payload["current_activation_blockers"]),
        "",
        "Next safe commands (offline/readiness/queue only; no provider calls):",
        *(f"- {command}" for command in payload["next_safe_commands"]),
        "",
        (
            "The immutable readiness contract still records its freeze-time placeholders. "
            "This separate projection is current operator truth and does not freeze or "
            "activate Protocol v2."
        ),
    ]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render current Protocol-v2 progress without changing frozen evidence."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    progress = current_progress_values()
    errors = validate_current_progress(progress)
    if args.check and errors:
        for error in errors:
            print(f"blocker={error}")
        return 1
    if args.as_json:
        print(json.dumps(progress, indent=2, sort_keys=True))
    else:
        print(format_current_progress(progress))
    return 0


__all__ = (
    "FROZEN_READINESS_SHA256",
    "PROGRESS_SOURCE",
    "PROGRESS_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "canonical_progress_bytes",
    "current_progress_values",
    "format_current_progress",
    "main",
    "progress_sha256",
    "validate_current_progress",
)


if __name__ == "__main__":
    raise SystemExit(main())
