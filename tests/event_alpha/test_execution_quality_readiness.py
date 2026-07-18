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
    COMMON_METRICS,
    CONTRACT_VERSION,
    EXECUTION_MODES,
    MULTI_VENUE_RESEARCH_OPTION,
    REQUIRED_SNAPSHOT_FIELDS,
    ExecutionQualityReader,
    ExecutionQualitySnapshot,
    build_execution_quality_readiness,
    format_execution_quality_readiness,
    main,
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
    assert CONTRACT_VERSION == "crypto_radar_execution_quality_readiness_v6"
    assert result.status == "execution_surface_selected_capture_contract_ready_inactive"
    assert result.selected_venue == "bybit"
    assert result.selected_execution_mode == "perpetual"
    assert result.intended_venue == "bybit"
    assert result.intended_instrument_mode == "perpetual"
    assert result.quote_currency == "USDT"
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
    assert result.required_human_decision_fields == (
        "exact_frozen_eligible_instrument_set",
    )
    assert result.supported_offline_adapters == (
        "bybit_usdt_linear_perpetual_fixture_normalizer_v2",
    )
    assert result.supported_live_adapters == (
        "bybit_usdt_linear_perpetual_public_REST_capture_v2",
    )
    assert result.supported_evidence_stores == (
        "immutable_raw_response_manifest_receipt_pointer_v2",
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
        "USDT_to_USD_cost_unit_policy_not_sealed",
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
    assert "top_30_liquid_decision_radar_assets" in rendered
    assert "eligible_instrument_set_frozen=false" in rendered
    assert "jurisdiction_and_account_eligibility_confirmed=true" in rendered
    assert "expected_public_private_data_boundary=public_market_data_only" in rendered
    assert "supported_offline_adapters=bybit_usdt_linear_perpetual" in rendered
    assert (
        "supported_live_adapters="
        "bybit_usdt_linear_perpetual_public_REST_capture_v2"
    ) in rendered
    assert (
        "supported_evidence_stores="
        "immutable_raw_response_manifest_receipt_pointer_v2"
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
    assert "future_generic_USD_projection=unavailable" in rendered
    assert "generic_target_after_conversion=bid_depth_usd_by_band" in rendered
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
    for venue in by_id.values():
        assert venue["jurisdiction_constraints"]
        assert venue["network_constraints"]
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
        "bybit_usdt_linear_perpetual_fixture_normalizer_v2"
    ]
    assert payload["supported_live_adapters"] == [
        "bybit_usdt_linear_perpetual_public_REST_capture_v2"
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
