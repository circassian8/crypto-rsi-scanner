"""Static execution-quality feasibility and interface contract regressions."""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit

import pytest

from crypto_rsi_scanner.event_alpha.operations.execution_quality_readiness import (
    BYBIT_NATIVE_METRICS,
    COMMON_METRICS,
    CONTRACT_VERSION,
    EXECUTION_MODES,
    MULTI_VENUE_RESEARCH_OPTION,
    OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL,
    OFFICIAL_PUBLIC_FEE_REFERENCE_URL,
    REMAINING_PROTOCOL_V2_COST_FIELDS,
    REMAINING_PROTOCOL_V2_SEALING_FIELDS,
    REQUIRED_SNAPSHOT_FIELDS,
    ExecutionQualityReader,
    ExecutionQualitySnapshot,
    build_execution_quality_readiness,
    format_execution_quality_readiness,
    main,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_fee import (
    OFFICIAL_MAKER_TAKER_URL,
    SCHEMA_VERSION as TAKER_FEE_SCENARIO_SCHEMA_VERSION,
)


EXPECTED_VENUES = {
    "binance",
    "bybit",
    "coinbase_exchange",
    "kraken",
    "dex_operator_selected",
}
REPO_ROOT = Path(__file__).resolve().parents[2]
DECISION_PACKAGE = (
    REPO_ROOT / "research/DECISION_RADAR_EXECUTION_VENUE_DECISION_PACKAGE.md"
)
NORTH_STAR_JSON = REPO_ROOT / "research/CRYPTO_DECISION_RADAR_NORTH_STAR.json"


def test_static_readiness_records_confirmed_surface_without_live_activation() -> None:
    result = build_execution_quality_readiness()

    assert result.contract_version == CONTRACT_VERSION
    assert CONTRACT_VERSION == "crypto_radar_execution_quality_readiness_v17"
    assert result.status == "execution_surface_selected_capture_contract_ready_inactive"
    assert result.selected_venue == "bybit"
    assert result.selected_execution_mode == "perpetual"
    assert result.intended_venue == "bybit"
    assert result.intended_instrument_mode == "perpetual"
    assert result.quote_currency == "USDT"
    assert result.primary_cost_currency == "USDT"
    assert result.primary_cost_currency_policy == (
        "native_USDT_only_no_USD_conversion_or_equivalence"
    )
    assert result.primary_cost_currency_policy_sealed is True
    assert result.usd_equivalence_assumed is False
    assert result.protocol_v2_cost_model_sealed is False
    assert result.remaining_protocol_v2_cost_fields == REMAINING_PROTOCOL_V2_COST_FIELDS
    assert result.fee_rate_authority_status == (
        "unsealed_public_reference_not_account_authoritative_authenticated_"
        "account_endpoint_outside_public_only_scope"
    )
    assert result.public_fee_reference_url == OFFICIAL_PUBLIC_FEE_REFERENCE_URL
    assert (
        result.account_fee_rate_endpoint_doc_url
        == OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL
    )
    assert result.account_fee_endpoint_requires_credentials is True
    assert result.account_specific_fee_rate_access_authorized is False
    assert result.official_fee_sources_reviewed_at == "2026-07-20"
    assert result.required_snapshot_fields_scope == (
        "inactive_generic_cross_venue_interface_not_selected_bybit_native_contract"
    )
    assert result.selected_native_snapshot_fields == BYBIT_NATIVE_METRICS
    assert result.generic_cross_venue_projection_available is False
    impact = result.impact_cost_semantics
    assert impact["selected_impact_reference"] == "mid_price"
    assert impact["selected_side_impact_includes_crossing_half_spread"] is True
    assert impact["standalone_spread_addition_to_selected_side_impact_permitted"] is False
    assert impact["round_trip_impact_requires_entry_and_exit_snapshots"] is True
    assert impact["impact_cost_application_policy_sealed"] is False
    assert impact["buy_impact_size_basis"] == "exact_usdt_spend"
    assert impact["sell_impact_size_basis"] == "exact_usdt_proceeds"
    assert impact["same_numeric_usdt_notional_proves_same_base_quantity"] is False
    assert impact["round_trip_base_quantity_reconciliation_implemented"] is True
    assert impact["round_trip_base_quantity_policy_sealed"] is False
    assert impact["round_trip_size_basis"] == (
        "same_exact_base_quantity_across_distinct_books"
    )
    assert impact["round_trip_visible_book_schema_version"] == (
        "crypto_radar.bybit_visible_book_round_trip.v3"
    )
    assert impact["round_trip_visible_book_order_style"] == (
        "immediately_marketable_book_walk"
    )
    assert impact["round_trip_visible_book_cost_basis"] == (
        "entry_mid_notional_usdt"
    )
    assert impact["round_trip_visible_book_realized_execution"] is False
    assert impact["round_trip_quantity_unit"] == "base_asset"
    assert impact["round_trip_quantity_semantics"] == (
        "bybit_USDT_linear_contract_quantity_in_underlying_token"
    )
    assert impact["instrument_order_constraints_implemented"] is True
    assert impact["instrument_constraint_fields"] == (
        "quantity_step",
        "minimum_order_quantity",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
    )
    assert impact["instrument_maximums_dynamic"] is True
    assert impact["instrument_maximums_revalidated_each_catalog_capture"] is True
    assert impact["instrument_constraints_causality_required"] is True
    assert impact["instrument_constraints_freshness_policy_sealed"] is False
    assert impact["minimum_order_quantity_enforced"] is True
    assert (
        impact["minimum_notional_enforced_on_entry_and_exit_visible_quote_value"]
        is True
    )
    assert impact["order_style_quantity_eligibility_reported"] is True
    assert impact["entry_exit_order_style_policy_sealed"] is False
    assert impact["dynamic_constraints_revalidated_per_leg"] is True
    assert impact["separate_entry_exit_constraint_lineages_required"] is True
    assert impact["exit_constraint_snapshot_required_after_entry"] is True
    assert impact["constraint_values_may_change_between_legs"] is True
    assert impact["per_leg_order_style_eligibility_reported"] is True
    assert impact["round_trip_same_style_intersection_reported"] is True
    assert impact["same_order_style_required_by_primitive"] is False
    assert impact["target_notional_sizing_implemented"] is True
    assert impact["target_notional_sizing_schema_version"] == (
        "crypto_radar.bybit_target_entry_mid_notional_sizing.v1"
    )
    assert impact["target_notional_round_trip_schema_version"] == (
        "crypto_radar.bybit_target_notional_visible_book_round_trip.v2"
    )
    assert impact["target_notional_input_unit"] == "USDT"
    assert impact["target_notional_reference"] == "entry_mid_price"
    assert impact["target_notional_rounding_mode"] == "floor_to_quantity_step"
    assert impact["target_notional_does_not_exceed_reference"] is True
    assert impact["target_notional_is_quote_budget"] is False
    assert (
        impact["marketable_quote_value_may_exceed_target_due_spread_and_impact"]
        is True
    )
    assert impact["target_notional_round_trip_identity_reconciled"] is True
    assert impact["capture_pair_round_trip_implemented"] is True
    assert impact["capture_pair_round_trip_schema_version"] == (
        "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1"
    )
    assert impact["capture_pair_exact_namespaces_required"] is True
    assert impact["capture_pair_latest_pointer_used"] is False
    assert impact["capture_pair_both_strict_clean_required"] is True
    assert impact["capture_pair_both_completion_fresh_required"] is True
    assert impact["capture_pair_windows_ordered_non_overlapping"] is True
    assert impact["capture_pair_base_and_namespaces_descriptor_held_together"] is True
    assert impact["capture_pair_provider_calls"] == 0
    assert impact["capture_pair_writes_performed"] is False
    assert impact["capture_pair_protocol_v2_annex_bound"] is False
    assert impact["capture_pair_protocol_v2_evidence_eligible"] is False
    assert impact["immediately_marketable_liquidity_role"] == "taker"
    assert impact["marketable_limit_immediate_fill_liquidity_role"] == "taker"
    assert impact["maker_liquidity_scenario_modeled"] is False
    assert impact["taker_fee_application_implemented"] is True
    assert (
        impact["taker_fee_scenario_schema_version"]
        == TAKER_FEE_SCENARIO_SCHEMA_VERSION
    )
    assert impact["taker_fee_rate_unit"] == "fraction"
    assert impact["taker_fee_applied_to_each_executed_leg_quote_value"] is True
    assert impact["taker_fee_effective_window_must_cover_both_legs"] is True
    assert impact["taker_fee_source_reference_required"] is True
    assert impact["taker_fee_source_sealed"] is False
    assert impact["taker_fee_protocol_v2_annex_bound"] is False
    assert impact["taker_fee_provider_calls"] == 0
    assert impact["taker_fee_writes_performed"] is False
    assert impact["official_maker_taker_url"] == OFFICIAL_MAKER_TAKER_URL
    assert impact["target_notional_tier_set_sealed"] is False
    assert impact["base_quantity_selection_policy_sealed"] is False
    assert result.eligible_instrument_set == ()
    assert "top_30_liquid_decision_radar_assets" in (
        result.eligible_instrument_selection_rule or ""
    )
    assert result.eligible_instrument_set_frozen is False
    assert result.jurisdiction_and_account_eligibility_confirmation == (
        "owner_confirmed_2026-07-17_for_bybit_USDT_linear_perpetual_research_scope"
    )
    assert result.jurisdiction_and_account_eligibility_confirmed is True
    assert result.expected_public_private_data_boundary == (
        "public_market_data_only_no_credentials_no_private_data"
    )
    assert result.human_decision_confirmed_at == "2026-07-17"
    assert result.required_human_decision_fields == REMAINING_PROTOCOL_V2_SEALING_FIELDS
    assert result.supported_offline_adapters == (
        "bybit_usdt_linear_perpetual_fixture_normalizer_v5",
        "bybit_usdt_linear_quantity_reconciled_visible_book_round_trip_v3",
        "bybit_usdt_linear_target_mid_notional_sizing_and_round_trip_v2",
        "bybit_two_exact_immutable_capture_round_trip_v1",
        "bybit_visible_book_taker_fee_scenario_v1",
    )
    assert result.supported_live_adapters == (
        "bybit_usdt_linear_perpetual_public_REST_capture_v5",
    )
    assert result.supported_evidence_stores == (
        "immutable_raw_response_manifest_receipt_pointer_v5",
    )
    assert result.immutable_capture_contract_implemented is True
    assert result.protocol_v2_annex_bound is False
    assert result.protocol_v2_evidence_eligible is False
    assert result.provider_call_planned is False
    assert result.provider_call_attempted is False
    assert result.live_adapter_activated is False
    assert result.credentials_read is False
    assert result.network_called is False
    assert result.writes_performed is False
    assert result.research_only is True
    assert result.operator_decision == (
        "confirmed_bybit_USDT_linear_perpetual_public_market_data_only"
    )
    assert result.next_safe_command == (
        "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
    )
    assert result.expected_provider_activity == "none_static_readiness_only"
    assert result.rollback_disable_command == (
        "unset_RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE_if_later_enabled"
    )
    assert result.spread_provider_status == (
        "bybit_immutable_capture_ready_inactive_live_spread_unavailable"
    )
    assert result.public_market_data_scope_confirmed is True
    assert result.public_market_data_permission_requested is False
    assert result.private_market_data_permission_requested is False
    assert result.order_permission_requested is False
    assert result.trading_permission_requested is False
    assert result.multiple_venue_research_option == MULTI_VENUE_RESEARCH_OPTION
    assert set(result.selection_blockers) == {
        "eligible_instrument_set_not_frozen",
        "bybit_public_endpoint_reachability_unverified_after_recorded_403",
        "runtime_provider_authorization_not_created_by_operator_selection",
        "protocol_v2_cost_model_not_sealed",
        "protocol_v2_annex_not_sealed",
    }


def test_build_is_static_without_network_files_or_ambient_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("static readiness must not open a network connection")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setenv("API_KEY", "must-not-be-read-or-rendered")
    monkeypatch.setenv("BYBIT_API_SECRET", "must-not-be-read-or-rendered")

    before = tuple(tmp_path.iterdir())
    payload = build_execution_quality_readiness().to_dict()
    rendered = json.dumps(payload, sort_keys=True)

    assert tuple(tmp_path.iterdir()) == before == ()
    assert "must-not-be-read-or-rendered" not in rendered
    assert payload["credentials_read"] is False
    assert payload["network_called"] is False
    assert payload["writes_performed"] is False


def test_capability_catalog_reports_complete_feasibility_without_preference() -> None:
    result = build_execution_quality_readiness()
    by_id = {row.venue_id: row for row in result.feasible_venues}

    assert set(by_id) == EXPECTED_VENUES
    assert result.supported_interface_modes == EXECUTION_MODES
    assert {
        mode for row in result.feasible_venues for mode in row.execution_modes
    } == set(EXECUTION_MODES)
    assert not any(row.implementation_status == "implemented" for row in result.feasible_venues)
    assert tuple(row.venue_id for row in result.feasible_venues) == (
        "binance",
        "bybit",
        "coinbase_exchange",
        "kraken",
        "dex_operator_selected",
    )


def test_every_capability_reports_access_limits_metrics_and_constraints() -> None:
    result = build_execution_quality_readiness()

    for row in result.feasible_venues:
        assert row.execution_modes
        assert set(row.execution_modes) <= set(EXECUTION_MODES)
        assert row.market_data_access
        assert row.required_operator_inputs
        assert "intended_execution_venue" in row.required_operator_inputs
        assert "intended_execution_mode" in row.required_operator_inputs
        assert "quote_currency" in row.required_operator_inputs
        assert "eligible_instrument_set" in row.required_operator_inputs
        assert "jurisdiction_and_account_eligibility_confirmation" in (
            row.required_operator_inputs
        )
        assert "expected_public_private_data_boundary" in row.required_operator_inputs
        assert row.jurisdiction_constraints
        assert "operator_must_confirm_current_venue_and_account_eligibility" in (
            row.jurisdiction_constraints
        )
        assert row.network_constraints
        assert row.request_limits
        if row.venue_id == "bybit":
            assert row.expected_metrics == BYBIT_NATIVE_METRICS
            assert not any("_usd_" in field for field in row.expected_metrics)
            assert any("_usdt_" in field for field in row.expected_metrics)
        else:
            assert set(COMMON_METRICS) <= set(row.expected_metrics)
        expected_review_date = "2026-07-17" if row.venue_id == "bybit" else "2026-07-15"
        assert row.official_sources_reviewed_at == expected_review_date


def test_cex_candidates_expect_public_books_without_credentials() -> None:
    rows = {
        row.venue_id: row for row in build_execution_quality_readiness().feasible_venues
    }

    for venue_id in ("binance", "bybit", "coinbase_exchange", "kraken"):
        row = rows[venue_id]
        assert row.public_endpoint_expected is True
        assert row.credentials_required == ()
        assert row.market_data_access == "public_market_data_no_credentials_expected"

    dex = rows["dex_operator_selected"]
    assert dex.public_endpoint_expected is None
    assert dex.credentials_required == ("provider_specific_if_required",)
    assert "chain_id" in dex.required_operator_inputs
    assert "pool_or_router_identity" in dex.required_operator_inputs


def test_official_source_metadata_is_https_and_provider_tbd_invents_none() -> None:
    rows = build_execution_quality_readiness().feasible_venues

    for row in rows:
        if row.venue_id == "dex_operator_selected":
            assert row.official_source_urls == ()
            continue
        assert row.official_source_urls
        for source in row.official_source_urls:
            parsed = urlsplit(source)
            assert parsed.scheme == "https"
            assert parsed.hostname
            assert parsed.username is None
            assert parsed.password is None
            assert parsed.query == ""
            assert parsed.fragment == ""


def test_catalog_preserves_known_bybit_restriction_without_bypass() -> None:
    bybit = next(
        row
        for row in build_execution_quality_readiness().feasible_venues
        if row.venue_id == "bybit"
    )

    assert "selected_public_REST_adapter_ready_inactive" in bybit.implementation_status
    assert "live_egress_reachability_unverified" in bybit.implementation_status
    assert "current_project_egress_has_recorded_a_region_restricted_403" in (
        bybit.network_constraints
    )
    assert "no_proxy_VPN_or_region_bypass_is_authorized" in bybit.network_constraints


def test_closed_snapshot_contract_contains_required_lineage_and_quality_fields() -> None:
    snapshot_fields = {field.name for field in fields(ExecutionQualitySnapshot)}

    assert set(REQUIRED_SNAPSHOT_FIELDS) <= snapshot_fields
    assert {
        "provider_observed_at",
        "acquired_at",
        "freshness_status",
        "source_url",
        "request_lineage_id",
        "research_only",
    } <= set(REQUIRED_SNAPSHOT_FIELDS)
    assert {
        "chain_id",
        "block_number",
        "pool_or_router_id",
        "gas_estimate_native",
        "route_identity",
    } <= snapshot_fields
    assert ExecutionQualitySnapshot.__dataclass_fields__["research_only"].default is True


def test_reader_protocol_exposes_only_one_read_operation() -> None:
    operations = {
        name
        for name, value in vars(ExecutionQualityReader).items()
        if callable(value) and not name.startswith("_")
    }

    assert operations == {"read_execution_quality"}
    assert all(
        prohibited not in " ".join(vars(ExecutionQualityReader)).casefold()
        for prohibited in ("place_order", "submit_order", "cancel_order", "execute_order")
    )


def test_human_report_is_explicitly_selected_but_no_call() -> None:
    rendered = format_execution_quality_readiness(build_execution_quality_readiness())

    assert (
        "status=execution_surface_selected_capture_contract_ready_inactive"
        in rendered
    )
    assert "selected_venue=bybit selected_execution_mode=perpetual" in rendered
    assert "intended_venue=bybit intended_instrument_mode=perpetual" in rendered
    assert "quote_currency=USDT eligible_instrument_set=not_yet_frozen" in rendered
    assert "primary_cost_currency=USDT primary_cost_currency_policy_sealed=true" in rendered
    assert "usd_equivalence_assumed=false" in rendered
    assert "protocol_v2_cost_model_sealed=false" in rendered
    assert "remaining_protocol_v2_cost_fields=fee_rate_source_and_assumption" in rendered
    assert "public_reference_not_account_authoritative" in rendered
    assert OFFICIAL_PUBLIC_FEE_REFERENCE_URL in rendered
    assert OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL in rendered
    assert "account_fee_endpoint_requires_credentials=true" in rendered
    assert "account_specific_fee_rate_access_authorized=false" in rendered
    assert "required_snapshot_fields_scope=inactive_generic_cross_venue" in rendered
    assert "selected_native_snapshot_fields=best_bid,best_ask,mid_price" in rendered
    assert "bid_depth_usdt_by_band" in rendered
    assert "generic_cross_venue_projection_available=false" in rendered
    assert "selected_impact_reference=mid_price" in rendered
    assert "selected_side_impact_includes_crossing_half_spread=true" in rendered
    assert "standalone_spread_addition_to_selected_side_impact_permitted=false" in rendered
    assert "round_trip_impact_requires_entry_and_exit_snapshots=true" in rendered
    assert "impact_cost_application_policy_sealed=false" in rendered
    assert "buy_impact_size_basis=exact_usdt_spend" in rendered
    assert "sell_impact_size_basis=exact_usdt_proceeds" in rendered
    assert "same_numeric_usdt_notional_proves_same_base_quantity=false" in rendered
    assert "round_trip_base_quantity_reconciliation_implemented=true" in rendered
    assert "round_trip_base_quantity_policy_sealed=false" in rendered
    assert "round_trip_size_basis=same_exact_base_quantity_across_distinct_books" in rendered
    assert "crypto_radar.bybit_visible_book_round_trip.v3" in rendered
    assert "instrument_order_constraints_implemented=true" in rendered
    assert "minimum_order_quantity,maximum_limit_order_quantity" in rendered
    assert "instrument_maximums_dynamic=true" in rendered
    assert "revalidated_each_catalog_capture=true" in rendered
    assert "instrument_constraints_freshness_policy_sealed=false" in rendered
    assert "entry_exit_order_style_policy_sealed=false" in rendered
    assert "dynamic_constraints_revalidated_per_leg=true" in rendered
    assert "separate_entry_exit_constraint_lineages_required=true" in rendered
    assert "exit_constraint_snapshot_required_after_entry=true" in rendered
    assert "constraint_values_may_change_between_legs=true" in rendered
    assert "per_leg_order_style_eligibility_reported=true" in rendered
    assert "round_trip_same_style_intersection_reported=true" in rendered
    assert "same_order_style_required_by_primitive=false" in rendered
    assert "minimum_notional_enforced_on_entry_and_exit_visible_quote_value=true" in rendered
    assert "target_notional_sizing_implemented=true" in rendered
    assert "crypto_radar.bybit_target_entry_mid_notional_sizing.v1" in rendered
    assert "crypto_radar.bybit_target_notional_visible_book_round_trip.v2" in rendered
    assert "target_notional_input_unit=USDT reference=entry_mid_price" in rendered
    assert "rounding=floor_to_quantity_step" in rendered
    assert "target_notional_does_not_exceed_reference=true" in rendered
    assert "target_notional_is_quote_budget=false" in rendered
    assert "immediately_marketable_liquidity_role=taker" in rendered
    assert "marketable_limit_immediate_fill_liquidity_role=taker" in rendered
    assert "maker_liquidity_scenario_modeled=false" in rendered
    assert "taker_fee_application_implemented=true" in rendered
    assert TAKER_FEE_SCENARIO_SCHEMA_VERSION in rendered
    assert "taker_fee_applied_to_each_executed_leg_quote_value=true" in rendered
    assert "effective_window_must_cover_both_legs=true" in rendered
    assert "taker_fee_source_sealed=false" in rendered
    assert "capture_pair_round_trip_implemented=true" in rendered
    assert "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1" in rendered
    assert "capture_pair_exact_namespaces_required=true" in rendered
    assert "latest_pointer_used=false" in rendered
    assert "both_strict_clean_required=true" in rendered
    assert "both_completion_fresh_required=true" in rendered
    assert "capture_pair_windows_ordered_non_overlapping=true" in rendered
    assert "base_and_namespaces_descriptor_held_together=true" in rendered
    assert "capture_pair_protocol_v2_annex_bound=false" in rendered
    assert "target_notional_tier_set_sealed=false" in rendered
    assert "base_quantity_selection_policy_sealed=false" in rendered
    assert "round_trip_quantity_unit=base_asset" in rendered
    assert "realized_execution=false" in rendered
    assert "top_30_liquid_decision_radar_assets" in rendered
    assert "eligible_instrument_set_frozen=false" in rendered
    assert "jurisdiction_and_account_eligibility_confirmed=true" in rendered
    assert "expected_public_private_data_boundary=public_market_data_only" in rendered
    assert "supported_offline_adapters=bybit_usdt_linear_perpetual" in rendered
    assert (
        "supported_live_adapters="
        "bybit_usdt_linear_perpetual_public_REST_capture_v5"
    ) in rendered
    assert (
        "supported_evidence_stores="
        "immutable_raw_response_manifest_receipt_pointer_v5"
    ) in rendered
    assert "immutable_capture_contract_implemented=true" in rendered
    assert "protocol_v2_annex_bound=false" in rendered
    assert "protocol_v2_evidence_eligible=false" in rendered
    assert (
        "read_only=true provider_calls=0 provider_call_planned=false "
        "provider_call_attempted=false"
    ) in rendered
    assert "credentials_read=false network_called=false writes_performed=false" in rendered
    assert "next_safe_command=make radar-execution-quality-bybit-readiness" in rendered
    assert "expected_provider_activity=none_static_readiness_only" in rendered
    assert "spread_provider_status=bybit_immutable_capture_ready_inactive" in rendered
    assert "set_freshness=every_book_fresh_at_capture_completion" in rendered
    assert "public_market_data_scope_confirmed=true" in rendered
    assert "public_market_data_permission_requested=false" in rendered
    assert "private_market_data_permission_requested=false" in rendered
    assert "order_permission_requested=false trading_permission_requested=false" in rendered
    assert "CONFIRMED EXECUTION-QUALITY DECISION" in rendered
    assert "intended_venue=bybit" in rendered
    assert "instrument_mode=perpetual" in rendered
    assert "quote_currency=USDT" in rendered
    assert "eligible_instrument_set=pending_exact_annex_freeze" in rendered
    assert (
        "jurisdiction_and_account_eligibility_confirmation="
        "confirmed_2026-07-17_by_owner_for_research_scope"
    ) in rendered
    assert (
        "expected_public_private_data_boundary="
        "public_market_data_only_no_credentials_no_private_data"
    ) in rendered
    assert "Bybit USDT-linear perpetuals are selected" in rendered
    assert "Feasibility catalog (Bybit perpetual is selected" in rendered
    assert "- spot: venues=binance,bybit,coinbase_exchange,kraken" in rendered
    assert "- perpetual: venues=binance,bybit" in rendered
    assert "- dex: venues=dex_operator_selected" in rendered
    assert "route_identity" in rendered
    assert "operator_must_confirm_derivatives_jurisdiction" in rendered
    assert "RPC_or_quote_access_and_credentials_unknown" in rendered
    assert "Execution-quality unit boundary" in rendered
    assert "selected_bybit_offline=best_bid,best_ask,mid_price,spread_bps" in rendered
    assert "bid_depth_usdt_by_band" in rendered
    assert "primary_protocol_v2_cost_unit=USDT" in rendered
    assert "future_generic_USD_projection=outside_primary_protocol_v2_cost_surface" in rendered
    assert "generic_cross_venue_fields_if_later_converted=bid_depth_usd_by_band" in rendered
    assert (
        "buy_price_impact_bps_by_notional,"
        "sell_price_impact_bps_by_notional"
    ) in rendered
    assert "dex_additions=chain_id,block_number,pool_or_router_id" in rendered
    assert "Multiple-venue research alternative (not an execution venue)" in rendered
    assert "mode_id=multiple_venue_research" in rendered
    assert "cannot_close_the_primary_cost_model" in rendered
    assert "no_credentials_orders_wallets_or_trading_permission" in rendered
    for venue_id in EXPECTED_VENUES:
        assert f"- {venue_id}:" in rendered


def test_structured_report_keeps_mode_access_auth_and_quality_distinctions() -> None:
    payload = build_execution_quality_readiness().to_dict()
    by_id = {row["venue_id"]: row for row in payload["feasible_venues"]}

    assert by_id["binance"]["execution_modes"] == ("spot", "perpetual")
    assert by_id["coinbase_exchange"]["execution_modes"] == ("spot",)
    assert by_id["dex_operator_selected"]["execution_modes"] == ("dex",)
    assert by_id["binance"]["public_endpoint_expected"] is True
    assert by_id["binance"]["credentials_required"] == ()
    assert by_id["dex_operator_selected"]["public_endpoint_expected"] is None
    assert by_id["dex_operator_selected"]["credentials_required"] == (
        "provider_specific_if_required",
    )
    for venue_id, venue in by_id.items():
        assert venue["jurisdiction_constraints"]
        assert venue["network_constraints"]
        if venue_id == "bybit":
            assert tuple(venue["expected_metrics"]) == BYBIT_NATIVE_METRICS
            assert not any("_usd_" in field for field in venue["expected_metrics"])
        else:
            assert set(COMMON_METRICS) <= set(venue["expected_metrics"])
    assert {
        "spread_bps",
        "bid_depth_usd_by_band",
        "ask_depth_usd_by_band",
        "buy_price_impact_bps_by_notional",
        "sell_price_impact_bps_by_notional",
    } <= set(payload["required_snapshot_fields"])


def test_cli_json_is_structured_static_and_secret_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EXCHANGE_API_SECRET", "must-not-print")

    assert main(["--json"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert output.err == ""
    assert payload["status"] == (
        "execution_surface_selected_capture_contract_ready_inactive"
    )
    assert payload["selected_venue"] == "bybit"
    assert payload["selected_execution_mode"] == "perpetual"
    assert payload["intended_venue"] == "bybit"
    assert payload["intended_instrument_mode"] == "perpetual"
    assert payload["quote_currency"] == "USDT"
    assert payload["primary_cost_currency"] == "USDT"
    assert payload["primary_cost_currency_policy"] == (
        "native_USDT_only_no_USD_conversion_or_equivalence"
    )
    assert payload["primary_cost_currency_policy_sealed"] is True
    assert payload["usd_equivalence_assumed"] is False
    assert payload["protocol_v2_cost_model_sealed"] is False
    assert payload["remaining_protocol_v2_cost_fields"] == list(
        REMAINING_PROTOCOL_V2_COST_FIELDS
    )
    assert "not_account_authoritative" in payload["fee_rate_authority_status"]
    assert payload["public_fee_reference_url"] == OFFICIAL_PUBLIC_FEE_REFERENCE_URL
    assert (
        payload["account_fee_rate_endpoint_doc_url"]
        == OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL
    )
    assert payload["account_fee_endpoint_requires_credentials"] is True
    assert payload["account_specific_fee_rate_access_authorized"] is False
    assert payload["official_fee_sources_reviewed_at"] == "2026-07-20"
    assert payload["required_snapshot_fields_scope"].startswith(
        "inactive_generic_cross_venue_interface"
    )
    assert payload["selected_native_snapshot_fields"] == list(BYBIT_NATIVE_METRICS)
    assert payload["generic_cross_venue_projection_available"] is False
    assert payload["selected_impact_reference"] == "mid_price"
    assert payload["selected_side_impact_includes_crossing_half_spread"] is True
    assert (
        payload["standalone_spread_addition_to_selected_side_impact_permitted"]
        is False
    )
    assert payload["round_trip_impact_requires_entry_and_exit_snapshots"] is True
    assert payload["impact_cost_application_policy_sealed"] is False
    assert payload["buy_impact_size_basis"] == "exact_usdt_spend"
    assert payload["sell_impact_size_basis"] == "exact_usdt_proceeds"
    assert payload["same_numeric_usdt_notional_proves_same_base_quantity"] is False
    assert payload["round_trip_base_quantity_reconciliation_implemented"] is True
    assert payload["round_trip_base_quantity_policy_sealed"] is False
    assert payload["round_trip_size_basis"] == (
        "same_exact_base_quantity_across_distinct_books"
    )
    assert payload["round_trip_visible_book_schema_version"] == (
        "crypto_radar.bybit_visible_book_round_trip.v3"
    )
    assert payload["dynamic_constraints_revalidated_per_leg"] is True
    assert payload["separate_entry_exit_constraint_lineages_required"] is True
    assert payload["exit_constraint_snapshot_required_after_entry"] is True
    assert payload["constraint_values_may_change_between_legs"] is True
    assert payload["per_leg_order_style_eligibility_reported"] is True
    assert payload["round_trip_same_style_intersection_reported"] is True
    assert payload["same_order_style_required_by_primitive"] is False
    assert payload["required_human_decision_fields"] == list(
        REMAINING_PROTOCOL_V2_SEALING_FIELDS
    )
    assert payload["eligible_instrument_set"] == []
    assert "top_30_liquid_decision_radar_assets" in payload[
        "eligible_instrument_selection_rule"
    ]
    assert payload["eligible_instrument_set_frozen"] is False
    assert payload["jurisdiction_and_account_eligibility_confirmed"] is True
    assert payload["expected_public_private_data_boundary"] == (
        "public_market_data_only_no_credentials_no_private_data"
    )
    assert payload["human_decision_confirmed_at"] == "2026-07-17"
    assert payload["supported_offline_adapters"] == [
        "bybit_usdt_linear_perpetual_fixture_normalizer_v5",
        "bybit_usdt_linear_quantity_reconciled_visible_book_round_trip_v3",
        "bybit_usdt_linear_target_mid_notional_sizing_and_round_trip_v2",
        "bybit_two_exact_immutable_capture_round_trip_v1",
        "bybit_visible_book_taker_fee_scenario_v1",
    ]
    assert payload["supported_live_adapters"] == [
        "bybit_usdt_linear_perpetual_public_REST_capture_v5"
    ]
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["network_called"] is False
    assert payload["credentials_read"] is False
    assert payload["spread_provider_status"] == (
        "bybit_immutable_capture_ready_inactive_live_spread_unavailable"
    )
    assert payload["public_market_data_scope_confirmed"] is True
    assert payload["public_market_data_permission_requested"] is False
    assert payload["private_market_data_permission_requested"] is False
    assert payload["order_permission_requested"] is False
    assert payload["trading_permission_requested"] is False
    assert payload["multiple_venue_research_option"] == MULTI_VENUE_RESEARCH_OPTION
    assert payload["human_decision_template"] == {
        "eligible_instrument_set": (
            "pending_exact_annex_freeze_from_confirmed_selection_rule"
        ),
        "expected_public_private_data_boundary": (
            "public_market_data_only_no_credentials_no_private_data"
        ),
        "instrument_mode": "perpetual",
        "intended_venue": "bybit",
        "jurisdiction_and_account_eligibility_confirmation": (
            "confirmed_2026-07-17_by_owner_for_research_scope"
        ),
        "quote_currency": "USDT",
    }
    assert payload["rollback_disable_command"] == (
        "unset_RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE_if_later_enabled"
    )
    assert "must-not-print" not in output.out


def test_cli_human_output_succeeds_without_activation(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr()

    assert output.err == ""
    assert "CRYPTO DECISION RADAR EXECUTION-QUALITY READINESS" in output.out
    assert "live_adapter_activated" not in output.out
    assert "trade, order, or execution action is authorized" in output.out


def test_make_targets_are_static_readiness_only() -> None:
    def dry_run(target: str) -> str:
        completed = subprocess.run(
            ["make", "-n", target, "PYTHON=python3"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    human = dry_run("radar-execution-quality-readiness")
    structured = dry_run("radar-execution-quality-readiness-json")

    assert "operations.execution_quality_readiness" in human
    assert "--json" not in human
    assert structured.count("--json") == 1
    rendered = f"{human}\n{structured}".casefold()
    assert "place-order" not in rendered
    assert "execute-order" not in rendered


def test_checked_operator_decision_package_records_selection_and_boundaries() -> None:
    rendered = DECISION_PACKAGE.read_text(encoding="utf-8")

    assert "operator decision confirmed" in rendered
    assert "Bybit" in rendered
    assert "USDT-linear perpetual" in rendered
    assert "public market data only" in rendered
    assert "immutable exact-response\ncapture contract are implemented but inactive" in rendered
    assert "protocol_v2_input_quality_eligible" in rendered
    assert "protocol_v2_evidence_eligible=false" in rendered
    assert "Never\n  rewrite a historical capture to promote it" in rendered
    assert "no credential, private-data access" in rendered
    for option in (
        "Binance",
        "Bybit",
        "Coinbase Exchange",
        "Kraken",
        "Operator-selected DEX",
        "Multiple-venue research",
    ):
        assert f"| {option} |" in rendered
    for field, _value in build_execution_quality_readiness().human_decision_template:
        assert field in rendered
    assert "cannot close the primary cost model" in rendered
    assert "primary Protocol-v2 cost currency is now explicitly sealed as native USDT" in rendered
    assert "No field is relabeled as USD" in rendered
    assert "public reference table is not account- or\nsymbol-authoritative" in rendered
    assert "/v5/account/fee-rate" in rendered
    assert "requires credentials and private account" in rendered
    assert "No Protocol-v2 holdout is defined, opened, or evaluated" in rendered
    assert (
        "No production threshold, route, score, notification, or authority changes"
        in rendered
    )


def test_north_star_records_selected_inactive_adapter_not_stale_no_selection() -> None:
    payload = json.loads(NORTH_STAR_JSON.read_text(encoding="utf-8"))
    readiness = payload["execution_quality_readiness"]
    decision = payload["operator_decisions"]["execution_venue_and_spread_provider"]

    assert readiness["contract_version"] == CONTRACT_VERSION
    assert readiness["primary_cost_currency"] == "USDT"
    assert readiness["primary_cost_currency_policy_sealed"] is True
    assert readiness["usd_equivalence_assumed"] is False
    assert readiness["protocol_v2_cost_model_sealed"] is False
    assert readiness["remaining_protocol_v2_cost_fields"] == list(
        REMAINING_PROTOCOL_V2_COST_FIELDS
    )
    assert readiness["account_specific_fee_rate_access_authorized"] is False
    assert readiness["selected_native_snapshot_fields"] == list(BYBIT_NATIVE_METRICS)
    assert readiness["generic_cross_venue_projection_available"] is False
    assert readiness["selected_side_impact_includes_crossing_half_spread"] is True
    assert (
        readiness["standalone_spread_addition_to_selected_side_impact_permitted"]
        is False
    )
    assert readiness["same_numeric_usdt_notional_proves_same_base_quantity"] is False
    assert readiness["round_trip_base_quantity_reconciliation_implemented"] is True
    assert readiness["round_trip_base_quantity_policy_sealed"] is False
    assert readiness["round_trip_size_basis"] == (
        "same_exact_base_quantity_across_distinct_books"
    )
    assert readiness["round_trip_visible_book_schema_version"] == (
        "crypto_radar.bybit_visible_book_round_trip.v3"
    )
    assert readiness["dynamic_constraints_revalidated_per_leg"] is True
    assert readiness["separate_entry_exit_constraint_lineages_required"] is True
    assert readiness["exit_constraint_snapshot_required_after_entry"] is True
    assert readiness["constraint_values_may_change_between_legs"] is True
    assert readiness["per_leg_order_style_eligibility_reported"] is True
    assert readiness["round_trip_same_style_intersection_reported"] is True
    assert readiness["same_order_style_required_by_primitive"] is False
    assert readiness["target_notional_sizing_implemented"] is True
    assert readiness["target_notional_round_trip_schema_version"] == (
        "crypto_radar.bybit_target_notional_visible_book_round_trip.v2"
    )
    assert readiness["target_notional_rounding_mode"] == (
        "floor_to_quantity_step"
    )
    assert readiness["target_notional_does_not_exceed_reference"] is True
    assert readiness["target_notional_is_quote_budget"] is False
    assert readiness["capture_pair_round_trip_implemented"] is True
    assert readiness["capture_pair_round_trip_schema_version"] == (
        "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1"
    )
    assert readiness["capture_pair_exact_namespaces_required"] is True
    assert readiness["capture_pair_latest_pointer_used"] is False
    assert readiness["capture_pair_both_strict_clean_required"] is True
    assert readiness["capture_pair_both_completion_fresh_required"] is True
    assert readiness["capture_pair_windows_ordered_non_overlapping"] is True
    assert readiness[
        "capture_pair_base_and_namespaces_descriptor_held_together"
    ] is True
    assert readiness["capture_pair_protocol_v2_evidence_eligible"] is False
    assert readiness["immediately_marketable_liquidity_role"] == "taker"
    assert readiness["marketable_limit_immediate_fill_liquidity_role"] == "taker"
    assert readiness["maker_liquidity_scenario_modeled"] is False
    assert readiness["taker_fee_application_implemented"] is True
    assert (
        readiness["taker_fee_scenario_schema_version"]
        == TAKER_FEE_SCENARIO_SCHEMA_VERSION
    )
    assert readiness["taker_fee_source_sealed"] is False
    assert readiness["taker_fee_protocol_v2_annex_bound"] is False
    assert readiness["target_notional_tier_set_sealed"] is False
    assert readiness["base_quantity_selection_policy_sealed"] is False
    assert readiness["final_live_adapter_implemented"] is False
    assert readiness["public_rest_adapter_implemented"] is True
    assert readiness["immutable_capture_contract_implemented"] is True
    assert readiness["live_adapter_active"] is False
    assert readiness["protocol_v2_annex_bound"] is False
    assert readiness["protocol_v2_evidence_eligible"] is False
    assert readiness["capture_status_command"].startswith(
        "make radar-execution-quality-bybit-status"
    )
    assert readiness["next_safe_command"].startswith(
        "make radar-execution-quality-bybit-readiness"
    )
    assert decision["current_status"] == (
        "bybit_USDT_linear_perpetual_selected_immutable_capture_ready_inactive"
    )
    assert "not_selected" not in json.dumps(decision, sort_keys=True)
    assert "RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE" in decision[
        "authorization_boundary"
    ]
