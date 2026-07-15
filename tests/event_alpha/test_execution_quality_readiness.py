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


def test_static_readiness_selects_and_activates_nothing() -> None:
    result = build_execution_quality_readiness()

    assert result.contract_version == CONTRACT_VERSION
    assert result.status == "operator_venue_required"
    assert result.selected_venue is None
    assert result.selected_execution_mode is None
    assert result.supported_live_adapters == ()
    assert result.provider_call_planned is False
    assert result.provider_call_attempted is False
    assert result.live_adapter_activated is False
    assert result.credentials_read is False
    assert result.network_called is False
    assert result.writes_performed is False
    assert result.research_only is True
    assert result.operator_decision == "select_execution_venue_and_instrument_mode"
    assert result.next_safe_command == (
        "make radar-execution-quality-readiness PYTHON=.venv/bin/python"
    )
    assert result.expected_provider_activity == "none_static_readiness_only"
    assert result.rollback_disable_command == "none_required_no_adapter_or_provider_is_active"
    assert result.spread_provider_status == "not_selected"
    assert set(result.selection_blockers) == {
        "intended_execution_venue_not_selected",
        "intended_execution_mode_not_selected",
        "no_live_execution_quality_adapter_implemented",
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
        assert row.jurisdiction_constraints
        assert "operator_must_confirm_current_venue_and_account_eligibility" in (
            row.jurisdiction_constraints
        )
        assert row.network_constraints
        assert row.request_limits
        assert set(COMMON_METRICS) <= set(row.expected_metrics)
        assert row.official_sources_reviewed_at == "2026-07-15"


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

    assert "current_egress_restricted" in bybit.implementation_status
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


def test_human_report_is_explicitly_nonselecting_and_no_call() -> None:
    rendered = format_execution_quality_readiness(build_execution_quality_readiness())

    assert "status=operator_venue_required" in rendered
    assert "selected_venue=none selected_execution_mode=none" in rendered
    assert "supported_live_adapters=none" in rendered
    assert "provider_call_planned=false provider_call_attempted=false" in rendered
    assert "credentials_read=false network_called=false writes_performed=false" in rendered
    assert "next_safe_command=make radar-execution-quality-readiness" in rendered
    assert "expected_provider_activity=none_static_readiness_only" in rendered
    assert "spread_provider_status=not_selected" in rendered
    assert "No venue is selected" in rendered
    for venue_id in EXPECTED_VENUES:
        assert f"- {venue_id}:" in rendered


def test_cli_json_is_structured_static_and_secret_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EXCHANGE_API_SECRET", "must-not-print")

    assert main(["--json"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert output.err == ""
    assert payload["status"] == "operator_venue_required"
    assert payload["selected_venue"] is None
    assert payload["supported_live_adapters"] == []
    assert payload["provider_call_planned"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["network_called"] is False
    assert payload["credentials_read"] is False
    assert payload["spread_provider_status"] == "not_selected"
    assert payload["rollback_disable_command"] == (
        "none_required_no_adapter_or_provider_is_active"
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
