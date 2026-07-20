"""Current Protocol-v2 progress must stay separate from frozen audit evidence."""

from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_validation_protocol_v2_progress as progress,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_DOCUMENT_SHA256 = (
    "897b29a85ff38fb19f5c0eda7e8077bf4b3cbc18aa92270e03d3ffe413c8ae4e"
)
FROZEN_IMPLEMENTATION_SHA256 = (
    "78867805252783d887c4a8ee475e34edb289e9bc86aa8582723ba93bcc975e97"
)


def test_current_progress_records_confirmed_venue_and_real_blockers() -> None:
    values = progress.current_progress_values()
    decision = values["confirmed_execution_decision"]

    assert progress.validate_current_progress(values) == []
    assert values["progress_version"].endswith("_v19")
    assert values["as_of"] == "2026-07-20"
    assert values["status"] == "venue_selected_evidence_collection_blocked"
    assert decision["venue_id"] == "bybit"
    assert decision["instrument_mode"] == "usdt_linear_perpetual"
    assert decision["quote_currency"] == "USDT"
    assert decision["primary_cost_currency"] == "USDT"
    assert decision["primary_cost_currency_policy"] == (
        "native_USDT_only_no_USD_conversion_or_equivalence"
    )
    assert decision["primary_cost_currency_policy_sealed"] is True
    assert decision["usd_equivalence_assumed"] is False
    assert decision["protocol_v2_cost_model_sealed"] is False
    assert decision["remaining_protocol_v2_cost_fields"] == [
        "fee_rate_source_and_assumption",
        "entry_exit_order_style",
        "notional_tiers_usdt",
        "base_quantity_selection_and_rounding_policy",
        "spread_and_visible_book_impact_application",
        "slippage_beyond_visible_book_policy",
        "funding_holding_period_and_sign_treatment",
        "latency_cost_policy",
        "unavailable_cost_policy",
    ]
    assert "not_account_authoritative" in decision["fee_rate_authority_status"]
    assert decision["account_specific_fee_rate_access_authorized"] is False
    assert decision["official_fee_sources_reviewed_at"] == "2026-07-20"
    assert "bid_depth_usdt_by_band" in decision["selected_native_snapshot_fields"]
    assert not any(
        "_usd_" in field for field in decision["selected_native_snapshot_fields"]
    )
    assert decision["generic_cross_venue_projection_available"] is False
    assert decision["selected_impact_reference"] == "mid_price"
    assert decision["selected_side_impact_includes_crossing_half_spread"] is True
    assert (
        decision["standalone_spread_addition_to_selected_side_impact_permitted"]
        is False
    )
    assert decision["round_trip_impact_requires_entry_and_exit_snapshots"] is True
    assert decision["impact_cost_application_policy_sealed"] is False
    assert decision["buy_impact_size_basis"] == "exact_usdt_spend"
    assert decision["sell_impact_size_basis"] == "exact_usdt_proceeds"
    assert decision["same_numeric_usdt_notional_proves_same_base_quantity"] is False
    assert decision["round_trip_base_quantity_reconciliation_implemented"] is True
    assert decision["round_trip_base_quantity_policy_sealed"] is False
    assert decision["round_trip_size_basis"] == (
        "same_exact_base_quantity_across_distinct_books"
    )
    assert decision["round_trip_visible_book_schema_version"] == (
        "crypto_radar.bybit_visible_book_round_trip.v3"
    )
    assert decision["round_trip_visible_book_order_style"] == (
        "immediately_marketable_book_walk"
    )
    assert decision["round_trip_visible_book_cost_basis"] == (
        "entry_mid_notional_usdt"
    )
    assert decision["round_trip_visible_book_realized_execution"] is False
    assert decision["round_trip_quantity_unit"] == "base_asset"
    assert decision["round_trip_quantity_semantics"] == (
        "bybit_USDT_linear_contract_quantity_in_underlying_token"
    )
    assert decision["instrument_order_constraints_implemented"] is True
    assert decision["instrument_constraint_fields"] == [
        "quantity_step",
        "minimum_order_quantity",
        "maximum_limit_order_quantity",
        "maximum_market_order_quantity",
        "minimum_notional_value_usdt",
    ]
    assert decision["instrument_maximums_dynamic"] is True
    assert decision["instrument_maximums_revalidated_each_catalog_capture"] is True
    assert decision["instrument_constraints_causality_required"] is True
    assert decision["instrument_constraints_freshness_policy_sealed"] is False
    assert decision["entry_exit_order_style_policy_sealed"] is False
    assert decision["dynamic_constraints_revalidated_per_leg"] is True
    assert decision["separate_entry_exit_constraint_lineages_required"] is True
    assert decision["exit_constraint_snapshot_required_after_entry"] is True
    assert decision["constraint_values_may_change_between_legs"] is True
    assert decision["per_leg_order_style_eligibility_reported"] is True
    assert decision["round_trip_same_style_intersection_reported"] is True
    assert decision["same_order_style_required_by_primitive"] is False
    assert decision["target_notional_sizing_implemented"] is True
    assert decision["target_notional_sizing_schema_version"] == (
        "crypto_radar.bybit_target_entry_mid_notional_sizing.v1"
    )
    assert decision["target_notional_round_trip_schema_version"] == (
        "crypto_radar.bybit_target_notional_visible_book_round_trip.v2"
    )
    assert decision["target_notional_input_unit"] == "USDT"
    assert decision["target_notional_reference"] == "entry_mid_price"
    assert decision["target_notional_rounding_mode"] == "floor_to_quantity_step"
    assert decision["target_notional_does_not_exceed_reference"] is True
    assert decision["target_notional_is_quote_budget"] is False
    assert (
        decision["marketable_quote_value_may_exceed_target_due_spread_and_impact"]
        is True
    )
    assert decision["target_notional_round_trip_identity_reconciled"] is True
    assert decision["capture_pair_round_trip_implemented"] is True
    assert decision["capture_pair_round_trip_schema_version"] == (
        "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1"
    )
    assert decision["capture_pair_exact_namespaces_required"] is True
    assert decision["capture_pair_latest_pointer_used"] is False
    assert decision["capture_pair_both_strict_clean_required"] is True
    assert decision["capture_pair_both_completion_fresh_required"] is True
    assert decision["capture_pair_windows_ordered_non_overlapping"] is True
    assert decision[
        "capture_pair_base_and_namespaces_descriptor_held_together"
    ] is True
    assert decision["capture_pair_provider_calls"] == 0
    assert decision["capture_pair_writes_performed"] is False
    assert decision["capture_pair_protocol_v2_annex_bound"] is False
    assert decision["capture_pair_protocol_v2_evidence_eligible"] is False
    assert decision["immediately_marketable_liquidity_role"] == "taker"
    assert (
        decision["marketable_limit_immediate_fill_liquidity_role"] == "taker"
    )
    assert decision["maker_liquidity_scenario_modeled"] is False
    assert decision["taker_fee_application_implemented"] is True
    assert decision["taker_fee_scenario_schema_version"] == (
        "crypto_radar.bybit_visible_book_taker_fee_scenario.v1"
    )
    assert decision["taker_fee_rate_unit"] == "fraction"
    assert decision["taker_fee_applied_to_each_executed_leg_quote_value"] is True
    assert decision["taker_fee_effective_window_must_cover_both_legs"] is True
    assert decision["taker_fee_source_reference_required"] is True
    assert decision["taker_fee_source_sealed"] is False
    assert decision["taker_fee_protocol_v2_annex_bound"] is False
    assert decision["taker_fee_provider_calls"] == 0
    assert decision["taker_fee_writes_performed"] is False
    assert decision["funding_settlement_application_implemented"] is True
    assert decision["funding_settlement_scenario_schema_version"] == (
        "crypto_radar.bybit_funding_settlement_scenario.v1"
    )
    assert decision["funding_rate_unit"] == "fraction"
    assert decision["funding_position_value_formula"] == (
        "base_quantity_times_settlement_mark_price"
    )
    assert decision["funding_position_cashflow_sign_convention"] == (
        "positive_received_negative_paid"
    )
    assert decision["positive_funding_long_pays_short"] is True
    assert decision["negative_funding_short_pays_long"] is True
    assert decision["settlement_mark_price_required"] is True
    assert decision["single_funding_event_arithmetic_implemented"] is True
    assert decision["funding_interval_aggregation_implemented"] is True
    assert decision["funding_interval_scenario_schema_version"] == (
        "crypto_radar.bybit_funding_interval_scenario.v1"
    )
    assert decision["expected_funding_settlement_set_reconciled"] is True
    assert decision["funding_settlement_order_strict"] is True
    assert (
        decision["operator_supplied_schedule_coverage_complete_possible"] is True
    )
    assert decision["funding_interval_coverage_scope"] == (
        "operator_supplied_unsealed_expected_settlement_schedule"
    )
    assert decision["holding_interval_funding_coverage_complete"] is False
    assert decision["funding_schedule_source_sealed"] is False
    assert decision["funding_rate_source_sealed"] is False
    assert decision["settlement_mark_source_sealed"] is False
    assert decision["funding_settlement_protocol_v2_annex_bound"] is False
    assert decision["funding_settlement_provider_calls"] == 0
    assert decision["funding_settlement_writes_performed"] is False
    assert decision["composite_execution_cost_implemented"] is True
    assert decision["composite_execution_cost_schema_version"] == (
        "crypto_radar.bybit_composite_execution_cost_scenario.v1"
    )
    assert decision["composite_component_identity_reconciled"] is True
    assert decision["composite_component_values_fully_rederived"] is True
    assert decision["composite_modeled_component_scope"] == (
        "visible_book_plus_unsealed_taker_fee_plus_operator_supplied_funding_schedule"
    )
    assert decision["composite_complete_protocol_v2_cost_model"] is False
    assert decision["composite_funding_interval_coverage_complete"] is False
    assert decision["composite_latency_cost_included"] is False
    assert decision["composite_beyond_visible_book_slippage_included"] is False
    assert decision["composite_unavailable_cost_policy_sealed"] is False
    assert decision["composite_provider_calls"] == 0
    assert decision["composite_writes_performed"] is False
    assert decision["target_notional_tier_set_sealed"] is False
    assert decision["base_quantity_selection_policy_sealed"] is False
    assert decision["data_boundary"] == "public_market_data_only"
    assert decision["exact_eligible_instrument_ids"] == []
    assert decision["exact_eligible_instrument_set_sealed"] is False
    assert decision["credentials_or_private_account_data"] is False
    assert decision["orders_or_execution_or_trading"] is False
    assert "exact_eligible_instrument_set_not_sealed" in values[
        "current_activation_blockers"
    ]
    assert "live_market_temporal_baseline_not_yet_warm" in values[
        "current_activation_blockers"
    ]
    assert (
        "genuine_bybit_rest_funding_open_interest_positioning_capture_absent"
        in values["current_activation_blockers"]
    )
    assert "genuine_bybit_liquidation_stream_capture_absent" in values[
        "current_activation_blockers"
    ]
    liquidation = values["native_liquidation_contract"]
    assert liquidation["transport"] == "public_websocket"
    assert liquidation["topic_template"] == "allLiquidation.{instrument_id}"
    assert liquidation["offline_exact_message_normalizer_implemented"] is True
    assert liquidation["operator_transcript_immutable_import_implemented"] is True
    assert liquidation["operator_import_scope"] == "selected_application_payloads"
    assert liquidation["operator_import_coverage_status"] == "observed_messages_only"
    assert liquidation["operator_import_coverage_complete"] is False
    assert liquidation["project_websocket_listener_implemented"] is False
    assert liquidation["project_transport_capture_implemented"] is False
    assert liquidation["genuine_capture_present"] is False
    assert liquidation["provider_connection_attempted"] is False
    assert liquidation["protocol_v2_evidence_eligible"] is False
    unlock = values["structured_unlock_contract"]
    assert unlock["provider"] == "tokenomist"
    assert unlock["provider_api_version"] == "v5"
    assert unlock["legacy_provider_api_version"] == "v4"
    assert unlock["legacy_v4_status"] == "deprecated"
    assert unlock["legacy_v4_live_eligible"] is False
    assert unlock["offline_response_normalizer_implemented"] is True
    assert unlock["strict_fixture_capture_doctor_implemented"] is True
    assert unlock["fixture_capture_retained"] is False
    assert unlock["full_multipage_capture_contract_implemented"] is False
    assert unlock["live_transport_implemented"] is False
    assert unlock["genuine_capture_present"] is False
    assert unlock["subscription_terms_approved"] is False
    assert unlock["protocol_v2_evidence_eligible"] is False
    assert "historical_outcome_recovery_incomplete" in values[
        "current_activation_blockers"
    ]
    assert (
        "explicit_human_review_timing_and_source_independence_labels_incomplete"
        in values["current_activation_blockers"]
    )
    assert "execution_venue_not_selected" not in values[
        "current_activation_blockers"
    ]
    assert set(values["safety"].values()) == {0}
    assert values["research_only"] is True


def test_frozen_readiness_files_remain_at_policy_fingerprints() -> None:
    document = REPO_ROOT / "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md"
    implementation = (
        REPO_ROOT
        / "crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2.py"
    )

    assert hashlib.sha256(document.read_bytes()).hexdigest() == FROZEN_DOCUMENT_SHA256
    assert (
        hashlib.sha256(implementation.read_bytes()).hexdigest()
        == FROZEN_IMPLEMENTATION_SHA256
    )
    frozen = progress.current_progress_values()["frozen_readiness_contract"]
    assert frozen["sha256"] == progress.FROZEN_READINESS_SHA256
    assert frozen["mutated"] is False


def test_progress_values_are_defensive_and_digest_is_deterministic() -> None:
    first = progress.current_progress_values()
    second = progress.current_progress_values()
    expected = progress.progress_sha256(second)
    first["current_activation_blockers"].append("invented")

    assert first != second
    assert deepcopy(second) == second
    assert progress.progress_sha256() == expected
    assert progress.canonical_progress_bytes().endswith(b"\n")


def test_progress_validation_fails_closed_on_audit_or_safety_drift() -> None:
    digest_drift = progress.current_progress_values()
    digest_drift["frozen_readiness_contract"]["sha256"] = "0" * 64
    safety_drift = progress.current_progress_values()
    safety_drift["safety"]["provider_calls"] = 1
    venue_drift = progress.current_progress_values()
    venue_drift["confirmed_execution_decision"]["venue_id"] = "other"
    blocker_drift = progress.current_progress_values()
    blocker_drift["current_activation_blockers"] = ["execution_venue_not_selected"]
    command_drift = progress.current_progress_values()
    command_drift["next_safe_commands"] = ["make unsafe-live-call"]
    version_drift = progress.current_progress_values()
    version_drift["progress_version"] = "decision_radar_progress_unknown"
    liquidation_drift = progress.current_progress_values()
    liquidation_drift["native_liquidation_contract"][
        "project_websocket_listener_implemented"
    ] = True
    unlock_drift = progress.current_progress_values()
    unlock_drift["structured_unlock_contract"]["genuine_capture_present"] = True
    cost_unit_drift = progress.current_progress_values()
    cost_unit_drift["confirmed_execution_decision"]["usd_equivalence_assumed"] = True
    cost_model_drift = progress.current_progress_values()
    cost_model_drift["confirmed_execution_decision"][
        "protocol_v2_cost_model_sealed"
    ] = True
    native_field_drift = progress.current_progress_values()
    native_field_drift["confirmed_execution_decision"][
        "selected_native_snapshot_fields"
    ] = ["bid_depth_usd_by_band"]
    impact_drift = progress.current_progress_values()
    impact_drift["confirmed_execution_decision"][
        "standalone_spread_addition_to_selected_side_impact_permitted"
    ] = True
    quantity_drift = progress.current_progress_values()
    quantity_drift["confirmed_execution_decision"][
        "round_trip_base_quantity_reconciliation_implemented"
    ] = False

    for mutation in (
        digest_drift,
        safety_drift,
        venue_drift,
        blocker_drift,
        command_drift,
        version_drift,
        liquidation_drift,
        unlock_drift,
        cost_unit_drift,
        cost_model_drift,
        native_field_drift,
        impact_drift,
        quantity_drift,
    ):
        assert progress.validate_current_progress(mutation)


def test_progress_cli_reads_no_ambient_state_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("current progress must not perform external I/O")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setenv("RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE", "secret")
    monkeypatch.setenv(
        "RSI_DECISION_RADAR_TOKENOMIST_V5_LIVE",
        "tokenomist-secret-must-not-be-read",
    )

    before = tuple(tmp_path.iterdir())
    assert progress.main(["--json", "--check"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert tuple(tmp_path.iterdir()) == before == ()
    assert output.err == ""
    assert payload["confirmed_execution_decision"]["venue_id"] == "bybit"
    assert payload["safety"]["provider_calls"] == 0
    assert "secret" not in output.out
    assert "tokenomist-secret-must-not-be-read" not in output.out


def test_progress_human_output_and_make_targets_are_explicit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert progress.main([]) == 0
    output = capsys.readouterr()
    assert "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS" in output.out
    assert "selected_execution_surface=bybit:usdt_linear_perpetual:USDT" in output.out
    assert "primary_cost_currency=USDT" in output.out
    assert "USD_equivalence_assumed=false" in output.out
    assert "protocol_v2_cost_model_sealed=false" in output.out
    assert "fee_rate_authority_status=unsealed_public_reference" in output.out
    assert "selected_native_snapshot_fields=best_bid,best_ask,mid_price" in output.out
    assert "generic_cross_venue_projection_available=false" in output.out
    assert "selected_side_impact_reference=mid_price" in output.out
    assert "standalone_spread_addition_permitted=false" in output.out
    assert "buy_impact_size_basis=exact_usdt_spend" in output.out
    assert "round_trip_base_quantity_reconciliation_implemented=true" in output.out
    assert "round_trip_base_quantity_policy_sealed=false" in output.out
    assert "same_exact_base_quantity_across_distinct_books" in output.out
    assert "crypto_radar.bybit_visible_book_round_trip.v3" in output.out
    assert "instrument_order_constraints_implemented=true" in output.out
    assert "instrument_maximums_dynamic=true" in output.out
    assert "instrument_constraints_freshness_policy_sealed=false" in output.out
    assert "dynamic_constraints_revalidated_per_leg=true" in output.out
    assert "separate_entry_exit_constraint_lineages_required=true" in output.out
    assert "exit_constraint_snapshot_required_after_entry=true" in output.out
    assert "constraint_values_may_change_between_legs=true" in output.out
    assert "per_leg_order_style_eligibility_reported=true" in output.out
    assert "round_trip_same_style_intersection_reported=true" in output.out
    assert "same_order_style_required_by_primitive=false" in output.out
    assert "target_notional_sizing_implemented=true" in output.out
    assert "target_notional_input_unit=USDT reference=entry_mid_price" in output.out
    assert "rounding=floor_to_quantity_step" in output.out
    assert "target_notional_is_quote_budget=false" in output.out
    assert "immediately_marketable_liquidity_role=taker" in output.out
    assert "marketable_limit_immediate_fill_liquidity_role=taker" in output.out
    assert "maker_liquidity_scenario_modeled=false" in output.out
    assert "taker_fee_application_implemented=true" in output.out
    assert "crypto_radar.bybit_visible_book_taker_fee_scenario.v1" in output.out
    assert "taker_fee_applied_to_each_executed_leg_quote_value=true" in output.out
    assert "effective_window_must_cover_both_legs=true" in output.out
    assert "taker_fee_source_sealed=false" in output.out
    assert "funding_settlement_application_implemented=true" in output.out
    assert "crypto_radar.bybit_funding_settlement_scenario.v1" in output.out
    assert "base_quantity_times_settlement_mark_price" in output.out
    assert "cashflow_sign=positive_received_negative_paid" in output.out
    assert "positive_funding_long_pays_short=true" in output.out
    assert "negative_funding_short_pays_long=true" in output.out
    assert "settlement_mark_price_required=true" in output.out
    assert "single_funding_event_arithmetic_implemented=true" in output.out
    assert "funding_interval_aggregation_implemented=true" in output.out
    assert "crypto_radar.bybit_funding_interval_scenario.v1" in output.out
    assert "expected_funding_settlement_set_reconciled=true" in output.out
    assert "funding_settlement_order_strict=true" in output.out
    assert (
        "operator_supplied_schedule_coverage_complete_possible=true" in output.out
    )
    assert (
        "funding_interval_coverage_scope="
        "operator_supplied_unsealed_expected_settlement_schedule" in output.out
    )
    assert "holding_interval_funding_coverage_complete=false" in output.out
    assert "funding_schedule_source_sealed=false" in output.out
    assert "funding_rate_source_sealed=false" in output.out
    assert "settlement_mark_source_sealed=false" in output.out
    assert "composite_execution_cost_implemented=true" in output.out
    assert "crypto_radar.bybit_composite_execution_cost_scenario.v1" in output.out
    assert "composite_component_identity_reconciled=true" in output.out
    assert "component_values_fully_rederived=true" in output.out
    assert "composite_complete_protocol_v2_cost_model=false" in output.out
    assert "composite_provider_calls=0 writes_performed=false" in output.out
    assert "capture_pair_round_trip_implemented=true" in output.out
    assert "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1" in output.out
    assert "capture_pair_exact_namespaces_required=true" in output.out
    assert "latest_pointer_used=false" in output.out
    assert "both_strict_clean_required=true" in output.out
    assert "both_completion_fresh_required=true" in output.out
    assert "capture_pair_windows_ordered_non_overlapping=true" in output.out
    assert "base_and_namespaces_descriptor_held_together=true" in output.out
    assert "capture_pair_protocol_v2_annex_bound=false" in output.out
    assert "target_notional_tier_set_sealed=false" in output.out
    assert "base_quantity_selection_policy_sealed=false" in output.out
    assert "eligible_instrument_set=not_yet_sealed" in output.out
    assert "Current unresolved activation blockers:" in output.out
    assert "- exact_eligible_instrument_set_not_sealed" in output.out
    assert (
        "- genuine_bybit_rest_funding_open_interest_positioning_capture_absent"
        in output.out
    )
    assert "- genuine_bybit_liquidation_stream_capture_absent" in output.out
    assert "native_liquidation_surface=public_websocket:" in output.out
    assert "offline_normalizer=true detached_import=true" in output.out
    assert "project_listener=false project_transport_capture=false" in output.out
    assert "genuine_capture=false coverage=observed_messages_only" in output.out
    assert "structured_unlock_surface=tokenomist:v5" in output.out
    assert "fixture_capture_doctor=true" in output.out
    assert "full_multipage=false live_transport=false genuine_capture=false" in output.out
    assert "offline/readiness/queue only; no provider calls" in output.out
    assert "radar-derivatives-bybit-liquidation-smoke" in output.out
    assert "radar-derivatives-bybit-liquidation-capture-smoke" in output.out
    assert "radar-unlock-tokenomist-v5-readiness" in output.out
    assert "radar-unlock-tokenomist-v5-capture-smoke" in output.out
    assert "radar-outcome-price-recovery-readiness" in output.out
    assert "event-alpha-source-independence-oos-readiness" in output.out
    assert "provider_calls=0" in output.out

    rendered = []
    for target in (
        "radar-research-protocol-v2-progress",
        "radar-research-protocol-v2-progress-check",
    ):
        completed = subprocess.run(
            ["make", "-n", target, "PYTHON=python3"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rendered.append(completed.stdout)
    assert all("empirical_validation_protocol_v2_progress" in row for row in rendered)
    assert "--check" not in rendered[0]
    assert rendered[1].count("--check") == 1
    assert "provider" not in "\n".join(rendered).casefold()


def test_checked_in_progress_note_matches_structured_unlock_frontier() -> None:
    note = (
        REPO_ROOT / "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_CURRENT_PROGRESS.md"
    ).read_text(encoding="utf-8")

    assert "Tokenomist v5 cliff-unlock response normalization" in note
    assert "primary cost currency: native USDT" in note
    assert "fee schedule" in note
    assert "pure funding arithmetic" in note
    assert "operator-supplied expected schedule" in note
    assert "authoritative schedule/rate/mark coverage" in note
    assert "pure composite cost arithmetic" in note
    assert "side-specific executed-value fees" in note
    assert "synthetic-fixture capture/doctor" in note
    assert "retains\n  nothing" in note
    assert "v4 remains deprecated and live-ineligible" in note
    assert "make radar-unlock-tokenomist-v5-readiness" in note
    assert "make radar-unlock-tokenomist-v5-capture-smoke" in note


def test_primary_readiness_target_leads_with_current_progress() -> None:
    completed = subprocess.run(
        ["make", "radar-research-protocol-v2-readiness", "PYTHON=python3"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    current_at = completed.stdout.index(
        "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS"
    )
    frozen_at = completed.stdout.index("DECISION RADAR EMPIRICAL PROTOCOL V2 READINESS")

    assert current_at < frozen_at
    assert "selected_execution_surface=bybit:usdt_linear_perpetual:USDT" in (
        completed.stdout
    )
    assert "execution_venue_not_selected" in completed.stdout[frozen_at:]
    assert "provider_calls=0" in completed.stdout
