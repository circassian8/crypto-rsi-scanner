"""Protocol-v2 pre-registration must remain static, blocked, and unopened."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_validation_protocol_v2 as protocol_v2,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_EVIDENCE_ROLES = {
    "intraday_market_observations",
    "idea_timing_and_review_latency",
    "execution_venue_spread_and_depth",
    "catalyst_timing",
    "official_calendar_events",
    "derivatives_context",
    "onchain_context",
    "rsi_technical_context",
}
def test_readiness_contract_is_valid_but_protocol_activation_is_blocked() -> None:
    values = protocol_v2.readiness_values()

    assert protocol_v2.validate_readiness(values) == []
    assert values["status"] == "blocked_pending_exact_human_sealed_annex"
    assert values["contract_validity"] == "static_readiness_contract_only"
    assert values["required_evidence_contract_status"] == "frozen_static"
    assert values["required_evidence_runtime_override_allowed"] is False
    assert values["protocol_freeze_status"] == "not_frozen"
    assert values["protocol_activation_status"] == "blocked"
    assert values["freeze_annex_status"] == {
        "sealed": False,
        "sealed_at": None,
        "annex_sha256": None,
        "human_approved": False,
        "all_required_sections_complete": False,
    }
    assert values["research_only"] is True


def test_required_evidence_is_explicit_point_in_time_and_never_proxied() -> None:
    values = protocol_v2.readiness_values()
    by_role = {row["role"]: row for row in values["required_evidence"]}

    assert set(by_role) == REQUIRED_EVIDENCE_ROLES
    assert by_role["intraday_market_observations"]["required_cadences"] == [
        "1h",
        "4h",
    ]
    assert {
        "idea_observed_at",
        "idea_available_at",
        "first_operator_viewed_at",
        "review_completed_at",
        "latency_seconds",
    } <= set(by_role["idea_timing_and_review_latency"]["required_fields"])
    assert {
        "venue_id",
        "instrument_mode",
        "quote_asset",
        "spread_bps",
        "bid_depth_usd_by_band",
        "ask_depth_usd_by_band",
    } <= set(by_role["execution_venue_spread_and_depth"]["required_fields"])
    for role in (
        "catalyst_timing",
        "official_calendar_events",
        "derivatives_context",
        "onchain_context",
        "rsi_technical_context",
    ):
        assert "source_lineage_id" in by_role[role]["required_fields"]
    assert values["evidence_policy"] == {
        "missing_evidence": "unavailable",
        "invented_evidence": "forbidden",
        "proxy_for_required_evidence": "forbidden",
        "point_in_time_availability_required": True,
        "immutable_source_lineage_required": True,
    }


def test_exact_freeze_annex_precedes_any_holdout_access() -> None:
    values = protocol_v2.readiness_values()
    annex = values["required_freeze_annex"]

    assert set(annex) == {
        "execution_venue_and_instruments",
        "data_sources",
        "partitions_and_holdout",
        "outcomes",
        "costs",
        "universe",
        "routes",
        "episodes",
        "minimum_samples",
    }
    assert {
        "intended_venue",
        "instrument_mode_spot_perpetual_or_dex",
        "quote_currency",
        "eligible_instrument_set",
        "jurisdiction_and_account_eligibility_confirmation",
        "expected_public_private_data_boundary",
    } == set(annex["execution_venue_and_instruments"])
    assert "untouched_holdout_start_and_end" in annex["partitions_and_holdout"]
    assert "holdout_content_commitment" in annex["partitions_and_holdout"]
    assert "observed_spread_rule" in annex["costs"]
    assert "exact_route_definitions" in annex["routes"]
    assert "route_bias_regime_liquidity_quality_minimum" in annex["minimum_samples"]


def test_holdout_and_all_evaluation_targets_remain_closed() -> None:
    values = protocol_v2.readiness_values()

    assert values["holdout"] == {
        "defined": False,
        "content_commitment_sealed": False,
        "access_authorized": False,
        "accessed": False,
        "access_count": 0,
        "protocol_v1_final_test_reuse_for_tuning": "forbidden",
        "protocol_v2_final_test_status": "not_run",
    }
    assert values["exposed_targets"] == {
        "replay": [],
        "selection": [],
        "final_test": [],
    }
    assert set(values["safety"].values()) == {0}


def test_safety_or_holdout_mutations_fail_closed() -> None:
    mutations = []
    accessed = protocol_v2.readiness_values()
    accessed["holdout"]["accessed"] = True
    accessed["holdout"]["access_count"] = 1
    mutations.append(accessed)
    target = protocol_v2.readiness_values()
    target["exposed_targets"]["final_test"] = ["do-not-run"]
    mutations.append(target)
    proxy = protocol_v2.readiness_values()
    proxy["evidence_policy"]["proxy_for_required_evidence"] = "allowed"
    mutations.append(proxy)
    activation = protocol_v2.readiness_values()
    activation["protocol_activation_status"] = "ready"
    mutations.append(activation)
    network = protocol_v2.readiness_values()
    network["safety"]["provider_calls"] = 1
    mutations.append(network)

    for mutation in mutations:
        assert protocol_v2.validate_readiness(mutation)


def test_values_are_defensive_and_digest_is_deterministic() -> None:
    first = protocol_v2.readiness_values()
    second = protocol_v2.readiness_values()
    expected = protocol_v2.readiness_sha256(second)
    first["required_evidence"][0]["required_fields"].append("invented")

    assert second == protocol_v2.readiness_values()
    assert first != second
    assert deepcopy(second) == second
    assert protocol_v2.readiness_sha256() == expected
    assert protocol_v2.canonical_readiness_bytes().endswith(b"\n")


def test_build_and_cli_read_no_ambient_state_and_write_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Protocol-v2 readiness must not open a network connection")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setenv("EXCHANGE_API_SECRET", "must-not-print")

    before = tuple(tmp_path.iterdir())
    assert protocol_v2.main(["--json", "--check"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert tuple(tmp_path.iterdir()) == before == ()
    assert output.err == ""
    assert payload["holdout"]["accessed"] is False
    assert payload["protocol_activation_status"] == "blocked"
    assert payload["exposed_targets"]["final_test"] == []
    assert "must-not-print" not in output.out


def test_human_output_leads_with_blocked_unopened_truth(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert protocol_v2.main([]) == 0
    output = capsys.readouterr()

    assert output.err == ""
    assert "DECISION RADAR EMPIRICAL PROTOCOL V2 READINESS" in output.out
    assert "required_evidence_contract=frozen_static runtime_override=false" in output.out
    assert "protocol_frozen=false activation=blocked holdout_accessed=false" in output.out
    assert "targets_exposed=replay:0,selection:0,final_test:0" in output.out
    assert "Required point-in-time evidence (no invention or proxy)" in output.out
    assert "No Protocol-v2 replay or final test is available" in output.out


def test_make_targets_validate_current_progress_then_frozen_contract() -> None:
    outputs = []
    for target in (
        "radar-research-protocol-v2-readiness",
        "radar-research-protocol-v2-check",
    ):
        completed = subprocess.run(
            ["make", "-n", target, "PYTHON=python3"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    for row in outputs:
        progress_token = "operations.empirical_validation_protocol_v2_progress"
        frozen_token = "operations.empirical_validation_protocol_v2"
        progress_at = row.index(progress_token)
        frozen_at = row.index(frozen_token, progress_at + len(progress_token))
        assert progress_at < frozen_at
    assert "--check" not in outputs[0]
    assert outputs[1].count("--check") == 2
    rendered = "\n".join(outputs).casefold()
    assert "replay_run" not in rendered
    assert "final-test" not in rendered
    assert "provider" not in rendered
