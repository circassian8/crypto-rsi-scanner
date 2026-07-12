"""Focused outcome identity, provenance, maturity, doctor, and burn-in regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import subprocess
import sys
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.artifacts.schema import outcome_eligibility as schema_contract
from crypto_rsi_scanner.event_alpha.doctor import check_registry
from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.outcome_checks import (
    _integrated_outcome_conflicts,
)
from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.provider_readiness_checks import (
    _integrated_radar_artifact_conflicts,
)
from crypto_rsi_scanner.event_alpha.doctor.checks.integrated_radar import (
    apply_integrated_artifact_checks,
)
from crypto_rsi_scanner.event_alpha.outcomes import burn_in
from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility as contract


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _observed_metadata(
    observed_at: datetime,
    evaluated_at: datetime,
) -> dict[str, dict[str, object]]:
    metadata: dict[str, dict[str, object]] = {}
    for horizon in contract.OUTCOME_HORIZONS:
        due = observed_at + timedelta(seconds=contract.OUTCOME_HORIZON_SECONDS[horizon])
        if due <= evaluated_at:
            metadata[horizon] = {
                "due_at": _iso(due),
                "price_observed_at": _iso(due + timedelta(seconds=30)),
                "price_at_horizon": None,
                "price_source": "binance_ohlcv",
                "price_observation_id": f"binance:{horizon}:{due.timestamp()}",
                "maturity_status": "matured",
                "provenance_status": "observed_market_prices",
            }
        else:
            metadata[horizon] = {
                "due_at": _iso(due),
                "price_observed_at": None,
                "price_at_horizon": None,
                "price_source": None,
                "price_observation_id": None,
                "maturity_status": "pending",
                "provenance_status": "missing",
            }
    return metadata


def _seal(row: dict[str, object]) -> dict[str, object]:
    reasons = contract.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    return row


def _outcome(
    *,
    run_id: str = "run-observed",
    candidate_id: str = "candidate-observed",
    core_opportunity_id: str = "core-observed",
    observed_at: datetime | None = None,
    evaluated_at: datetime | None = None,
    primary_horizon: str = "3d",
) -> dict[str, object]:
    observed = observed_at or datetime(2026, 6, 1, tzinfo=timezone.utc)
    evaluated = evaluated_at or observed + timedelta(days=8, hours=1)
    metadata = _observed_metadata(observed, evaluated)
    returns = {
        horizon: (
            (0.025 if horizon == primary_horizon else 0.01)
            if metadata[horizon]["maturity_status"] == "matured"
            else None
        )
        for horizon in contract.OUTCOME_HORIZONS
    }
    for horizon, return_value in returns.items():
        if return_value is not None:
            metadata[horizon]["price_at_horizon"] = 100.0 * (1.0 + return_value)
    row: dict[str, object] = {
        "row_type": "event_alpha_outcome",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "run_id": run_id,
        "profile": "no_key_live",
        "run_mode": "burn_in",
        "artifact_namespace": "no_key_live",
        "candidate_id": candidate_id,
        "core_opportunity_id": core_opportunity_id,
        "observed_at": _iso(observed),
        "outcome_eligibility_contract_version": contract.OUTCOME_ELIGIBILITY_CONTRACT_VERSION,
        "outcome_data_source": "observed_market_prices",
        "outcome_evaluated_at": _iso(evaluated),
        "observation_price_provenance_status": "observed_market_prices",
        "price_at_observation": 100.0,
        "observation_price_source": "fixture_ohlcv",
        "observation_price_id": f"fixture:entry:{candidate_id}:{_iso(observed)}",
        "observation_price_observed_at": _iso(observed),
        "primary_horizon": primary_horizon,
        "primary_horizon_return": returns[primary_horizon],
        "return_by_horizon": returns,
        "horizon_metadata": metadata,
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
        "no_trade_created": True,
        "no_paper_trade_created": True,
    }
    row.update(contract.build_outcome_identity_fields(row))
    return _seal(row)


def _synthetic_outcome() -> dict[str, object]:
    observed = datetime(2026, 6, 1, tzinfo=timezone.utc)
    evaluated = observed + timedelta(hours=2)
    row = _outcome(
        run_id="run-synthetic",
        candidate_id="candidate-synthetic",
        core_opportunity_id="core-synthetic",
        observed_at=observed,
        evaluated_at=evaluated,
    )
    row.update({
        "outcome_data_source": "synthetic_fixture",
        "observation_price_provenance_status": "synthetic_fixture",
        "horizon_metadata": contract.build_synthetic_horizon_metadata(
            observed_at=row["observed_at"],
            evaluated_at=row["outcome_evaluated_at"],
        ),
    })
    return _seal(row)


def _candidate(row: dict[str, object]) -> dict[str, object]:
    return {
        field: row[field]
        for field in contract.OUTCOME_IDENTITY_FIELDS
    } | {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "research_only": True,
        "symbol": row["symbol"],
        "opportunity_type": row["opportunity_type"],
        "run_mode": row["run_mode"],
    }


def _core(row: dict[str, object]) -> dict[str, object]:
    return {
        field: row[field]
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    } | {
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": row["observed_at"],
        "research_only": True,
        "symbol": row["symbol"],
        "opportunity_type": row["opportunity_type"],
        "run_mode": row["run_mode"],
    }


def test_outcome_schema_is_legacy_readable_and_uses_one_canonical_contract():
    legacy = {
        "row_type": "event_alpha_outcome",
        "symbol": "BTC",
        "opportunity_type": "EARLY_LONG_RESEARCH",
    }
    assert schema_v1.validate_row_against_schema(legacy, "outcome_row_v1") == []

    row = _outcome()
    assert schema_v1.validate_row_against_schema(row, "outcome_row_v1") == []
    assert schema_contract.validate_contract is contract.validate_contract
    assert schema_contract.OUTCOME_INELIGIBLE_REASONS is contract.OUTCOME_INELIGIBLE_REASONS
    assert schema_contract.OUTCOME_HORIZON_SECONDS is contract.OUTCOME_HORIZON_SECONDS
    assert contract.primary_horizon_for_lane(row["opportunity_type"]) == row["primary_horizon"]

    partial = {**legacy, "calibration_eligible": False}
    errors = schema_v1.validate_row_against_schema(partial, "outcome_row_v1")
    assert "outcome_eligibility_missing_field:outcome_identity" in errors
    assert "outcome_eligibility_reasons_mismatch" in errors


def test_outcome_evidence_telemetry_is_typed_on_all_burn_in_schemas():
    rows = {
        "event_alpha_burn_in_scorecard_v1": {
            "row_type": "event_alpha_burn_in_scorecard",
            "profile": "no_key_live",
            "artifact_namespace": "no_key_live",
            "research_only": True,
            "no_send_rehearsal": True,
        },
        "event_alpha_burn_in_measurement_dashboard_v1": {
            "row_type": "event_alpha_burn_in_measurement_dashboard",
            "profile": "no_key_live",
            "artifact_namespace": "no_key_live",
            "evidence_scope": "operational",
            "auto_apply_thresholds": False,
            "research_only": True,
            "no_send_rehearsal": True,
        },
        "event_alpha_source_yield_report_v1": {
            "row_type": "event_alpha_source_yield_report",
            "profile": "no_key_live",
            "artifact_namespace": "no_key_live",
            "evidence_scope": "operational",
            "auto_apply": False,
            "research_only": True,
            "no_send_rehearsal": True,
        },
    }
    telemetry = {
        "outcome_rows_supplied": 5,
        "outcome_rows_eligible": 2,
        "outcome_rows_excluded": 3,
        "outcome_exclusion_reason_counts": {"synthetic_fixture": 3},
    }
    for schema_id, base in rows.items():
        schema = schema_v1.get_schema(schema_id)
        assert set(schema_contract.OUTCOME_EVIDENCE_TELEMETRY_FIELDS) <= schema.declared_fields
        assert all(
            schema.field_types[field] == expected
            for field, expected in schema_contract.OUTCOME_EVIDENCE_TELEMETRY_TYPES.items()
        )
        assert schema_v1.validate_row_against_schema({**base, **telemetry}, schema) == []
        invalid = {**base, **telemetry, "outcome_rows_supplied": True}
        assert "invalid_type:outcome_rows_supplied:int" in schema_v1.validate_row_against_schema(
            invalid,
            schema,
        )


def test_outcome_contract_rejects_concealed_reasons_and_adversarial_time_evidence():
    synthetic = _synthetic_outcome()
    assert contract.validate_contract(synthetic) == []
    concealed = deepcopy(synthetic)
    concealed["calibration_ineligible_reasons"] = ["synthetic_fixture"]
    assert "outcome_eligibility_reasons_mismatch" in contract.validate_contract(concealed)

    wrong_lane_horizon = _outcome(primary_horizon="24h")
    assert "primary_horizon_lane_mismatch" in (
        contract.calibration_ineligibility_reasons(wrong_lane_horizon)
    )
    assert contract.effective_calibration_eligible(wrong_lane_horizon) is False

    due_mismatch = _outcome(primary_horizon="15m")
    due_mismatch["horizon_metadata"]["15m"]["due_at"] = _iso(
        datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(minutes=16)
    )
    reasons = contract.calibration_ineligibility_reasons(due_mismatch)
    assert "horizon_metadata_contract_invalid" in reasons
    assert "primary_horizon_due_mismatch" in reasons
    assert contract.effective_calibration_eligible(due_mismatch) is False

    naive = _outcome()
    naive["outcome_evaluated_at"] = "2026-06-09T01:00:00"
    assert contract.parse_aware_time(naive["outcome_evaluated_at"]) is None
    assert "missing_outcome_evaluated_at" in contract.calibration_ineligibility_reasons(naive)
    assert contract.effective_calibration_eligible(naive) is False

    pending_after_due = _outcome(primary_horizon="1h")
    pending_after_due["horizon_metadata"]["1h"].update({
        "price_observed_at": None,
        "maturity_status": "pending",
        "provenance_status": "missing",
    })
    assert "horizon_metadata_contract_invalid" in contract.calibration_ineligibility_reasons(
        pending_after_due
    )

    before_due = _outcome(primary_horizon="1h")
    before_due["horizon_metadata"]["1h"]["price_observed_at"] = before_due["observed_at"]
    assert "primary_horizon_price_before_due" in contract.calibration_ineligibility_reasons(before_due)

    excessive_lag = _outcome(primary_horizon="15m")
    due = contract.parse_aware_time(excessive_lag["horizon_metadata"]["15m"]["due_at"])
    assert due is not None
    excessive_lag["horizon_metadata"]["15m"]["price_observed_at"] = _iso(
        due + timedelta(minutes=16)
    )
    assert "primary_horizon_price_lag_exceeded" in contract.calibration_ineligibility_reasons(
        excessive_lag
    )

    recompute_mismatch = _outcome(primary_horizon="1h")
    recompute_mismatch["horizon_metadata"]["1h"]["price_at_horizon"] = 150.0
    assert "horizon_return_recompute_mismatch" in contract.calibration_ineligibility_reasons(
        recompute_mismatch
    )

    nonfinite = _outcome()
    nonfinite["primary_horizon_return"] = float("nan")
    assert "primary_horizon_return_invalid" in contract.calibration_ineligibility_reasons(nonfinite)
    assert contract.effective_calibration_eligible(nonfinite) is False

    string_return = _outcome()
    string_return["primary_horizon_return"] = "0.025"
    assert "primary_horizon_return_invalid" in contract.calibration_ineligibility_reasons(
        string_return
    )

    return_mismatch = _outcome()
    return_mismatch["return_by_horizon"]["3d"] = 0.5
    assert "primary_horizon_return_mismatch" in contract.calibration_ineligibility_reasons(
        return_mismatch
    )

    unsafe = _outcome()
    unsafe["trade_created"] = True
    assert "outcome_safety_contract_invalid" in contract.calibration_ineligibility_reasons(unsafe)


def test_doctor_blocks_synthetic_immature_provenance_and_identity_failures():
    valid = _outcome()
    candidate = _candidate(valid)
    clean = _integrated_outcome_conflicts([candidate], [valid])
    for key in (
        "integrated_outcome_eligibility_contract_invalid",
        "integrated_outcome_synthetic_evidence_leak",
        "integrated_outcome_immature_validation_claim",
        "integrated_outcome_duplicate_exact_identity",
        "integrated_outcome_ambiguous_exact_identity",
        "integrated_outcome_eligible_provenance_missing",
        "integrated_outcome_identity_mismatch",
    ):
        assert clean[key] == 0

    canonical_without_positive_aliases = deepcopy(valid)
    canonical_without_positive_aliases.pop("no_trade_created")
    canonical_without_positive_aliases.pop("no_paper_trade_created")
    alias_free_conflicts = _integrated_outcome_conflicts(
        [candidate],
        [canonical_without_positive_aliases],
    )
    assert alias_free_conflicts["integrated_outcome_schema_missing"] == 0

    synthetic = _synthetic_outcome()
    synthetic["outcome_label"] = "useful"
    synthetic_conflicts = _integrated_outcome_conflicts([_candidate(synthetic)], [synthetic])
    assert synthetic_conflicts["integrated_outcome_synthetic_evidence_leak"] == 1
    assert synthetic_conflicts["integrated_outcome_returns_without_price"] == 0

    observed = datetime(2026, 6, 1, tzinfo=timezone.utc)
    pending = _outcome(
        run_id="run-pending",
        candidate_id="candidate-pending",
        core_opportunity_id="core-pending",
        observed_at=observed,
        evaluated_at=observed + timedelta(minutes=30),
        primary_horizon="1h",
    )
    pending["primary_horizon_return"] = None
    pending["outcome_label"] = "useful"
    _seal(pending)
    assert contract.validate_contract(pending) == []
    pending_conflicts = _integrated_outcome_conflicts([_candidate(pending)], [pending])
    assert pending_conflicts["integrated_outcome_immature_validation_claim"] == 1

    provenance = _outcome(
        run_id="run-provenance",
        candidate_id="candidate-provenance",
        core_opportunity_id="core-provenance",
    )
    provenance["observation_price_provenance_status"] = "missing"
    provenance_conflicts = _integrated_outcome_conflicts([_candidate(provenance)], [provenance])
    assert provenance_conflicts["integrated_outcome_eligibility_contract_invalid"] == 1
    assert provenance_conflicts["integrated_outcome_eligible_provenance_missing"] == 1

    duplicate_conflicts = _integrated_outcome_conflicts([candidate], [valid, deepcopy(valid)])
    assert duplicate_conflicts["integrated_outcome_duplicate_exact_identity"] == 1

    duplicate_candidates = _integrated_outcome_conflicts([candidate, deepcopy(candidate)], [valid])
    assert duplicate_candidates["integrated_outcome_ambiguous_exact_identity"] == 1

    malformed = deepcopy(valid)
    malformed.pop("outcome_identity")
    malformed_conflicts = _integrated_outcome_conflicts([candidate], [malformed])
    assert malformed_conflicts["integrated_outcome_ambiguous_exact_identity"] == 1

    assert _integrated_outcome_conflicts([], [valid])["integrated_outcome_identity_mismatch"] == 1
    incomplete_candidate = deepcopy(candidate)
    incomplete_candidate.pop("profile")
    assert _integrated_outcome_conflicts(
        [incomplete_candidate], [valid]
    )["integrated_outcome_identity_mismatch"] == 1
    wrong_context = deepcopy(candidate)
    wrong_context["run_id"] = "other-run"
    assert _integrated_outcome_conflicts(
        [wrong_context], [valid]
    )["integrated_outcome_identity_mismatch"] == 1

    earlier_doctor_clock = contract.parse_aware_time(valid["outcome_evaluated_at"])
    assert earlier_doctor_clock is not None
    earlier_doctor_clock -= timedelta(seconds=1)
    future_conflicts = _integrated_outcome_conflicts(
        [candidate],
        [valid],
        evaluated_at=earlier_doctor_clock,
    )
    assert future_conflicts["integrated_outcome_eligibility_contract_invalid"] == 1


def test_outcome_doctor_is_import_order_independent():
    script = """
from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.outcome_checks import (
    _integrated_outcome_conflicts,
)

row = {
    "candidate_id": "candidate-isolated",
    "symbol": "BTC",
    "coin_id": "bitcoin",
    "opportunity_type": "EARLY_LONG_RESEARCH",
    "no_trade_created": True,
    "no_paper_trade_created": True,
}
conflicts = _integrated_outcome_conflicts([], [row])
assert conflicts["integrated_outcome_missing_for_candidate"] == 0

from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.provider_readiness_checks import (
    _integrated_radar_artifact_conflicts,
)
assert _integrated_radar_artifact_conflicts([], core_rows=[])[
    "integrated_candidate_core_missing"
] == 0
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_doctor_core_authority_join_is_exact_duplicate_safe_and_order_invariant():
    outcome = _outcome()
    candidate = _candidate(outcome)
    exact = _core(outcome)
    other_run = {**exact, "run_id": "other-run", "opportunity_type": "CONFIRMED_LONG_RESEARCH"}

    for core_rows in ([exact, other_run], [other_run, exact]):
        conflicts = _integrated_radar_artifact_conflicts(
            [candidate],
            core_rows=core_rows,
        )
        assert conflicts["integrated_candidate_core_missing"] == 0
        assert conflicts["integrated_candidate_core_opportunity_type_mismatch"] == 0
        assert conflicts["integrated_core_silent_upgrade"] == 0

    duplicate = _integrated_radar_artifact_conflicts(
        [candidate],
        core_rows=[exact, deepcopy(exact)],
    )
    assert duplicate["integrated_candidate_core_missing"] == 1

    wrong_context = _integrated_radar_artifact_conflicts(
        [candidate],
        core_rows=[other_run],
    )
    assert wrong_context["integrated_candidate_core_missing"] == 1


def test_exact_identity_distinguishes_runs_and_registered_doctor_counter_blocks_strict():
    first = _outcome(run_id="run-a", candidate_id="shared-candidate", core_opportunity_id="core-a")
    second = _outcome(run_id="run-b", candidate_id="shared-candidate", core_opportunity_id="core-b")
    conflicts = _integrated_outcome_conflicts([_candidate(first), _candidate(second)], [first, second])
    assert conflicts["integrated_outcome_ambiguous_exact_identity"] == 0
    assert conflicts["integrated_outcome_identity_mismatch"] == 0

    check = check_registry.CHECK_BY_ID["outcomes.eligibility_firewall"]
    assert check.severity == "blocker"
    blockers: list[str] = []
    warnings: list[str] = []
    apply_integrated_artifact_checks(
        SimpleNamespace(
            strict=True,
            integrated_conflicts={"integrated_outcome_synthetic_evidence_leak": 1},
        ),
        blockers,
        warnings,
    )
    assert warnings == []
    assert blockers == [
        "outcomes.eligibility_firewall: integrated_outcome_synthetic_evidence_leak=1"
    ]


def test_missing_outcomes_are_visible_but_do_not_block_fresh_strict_radar_smoke():
    blockers: list[str] = []
    warnings: list[str] = []
    apply_integrated_artifact_checks(
        SimpleNamespace(
            strict=True,
            integrated_conflicts={"integrated_outcome_missing_for_candidate": 9},
        ),
        blockers,
        warnings,
    )
    assert blockers == []
    assert warnings == ["integrated_outcome_missing_for_candidate=9"]


def test_calibration_priors_attribute_lane_from_exact_candidate_core_authority():
    outcome = _outcome()
    candidate = _candidate(outcome)
    core = _core(outcome)
    outcome["opportunity_type"] = "RISK_ONLY"

    payload = integrated_radar_outcomes.build_integrated_radar_calibration_priors(
        [outcome],
        candidate_rows=[candidate],
        core_rows=[core],
        evaluated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )

    assert set(payload["opportunity_type_priors"]) == {"EARLY_LONG_RESEARCH"}
    assert payload["opportunity_type_priors"]["EARLY_LONG_RESEARCH"][
        "calibration_eligible_rows"
    ] == 1


def test_burn_in_counts_only_unique_mature_exact_provenance_outcomes():
    valid = _outcome(run_id="run-valid", candidate_id="candidate-valid", core_opportunity_id="core-valid")
    duplicate = _outcome(
        run_id="run-duplicate",
        candidate_id="candidate-duplicate",
        core_opportunity_id="core-duplicate",
    )
    synthetic = _synthetic_outcome()
    scorecard = burn_in.build_burn_in_scorecard(
        days=30,
        now=datetime(2026, 6, 10, tzinfo=timezone.utc),
        outcome_rows=[valid, duplicate, deepcopy(duplicate), synthetic],
        candidate_rows=[_candidate(valid), _candidate(duplicate), _candidate(synthetic)],
        core_rows=[_core(valid), _core(duplicate), _core(synthetic)],
        profile="no_key_live",
        artifact_namespace="no_key_live",
    )
    assert scorecard.outcome_rows_supplied == 4
    assert scorecard.outcome_row_count == 1
    assert scorecard.outcome_rows_excluded == 3
    assert [row["candidate_id"] for row in scorecard.outcome_rows] == ["candidate-valid"]
    assert scorecard.outcome_rows[0]["calibration_eligible"] is True
    assert scorecard.outcome_exclusion_reason_counts["duplicate_outcome_identity"] == 2
    assert scorecard.outcome_exclusion_reason_counts["synthetic_fixture"] == 1
    rendered = burn_in.format_burn_in_scorecard(scorecard)
    assert "outcomes_supplied=4" in rendered
    assert "outcomes_excluded=3" in rendered
    assert "duplicate_outcome_identity=2" in rendered

    first = _outcome(run_id="run-a", candidate_id="shared-candidate", core_opportunity_id="core-a")
    second = _outcome(run_id="run-b", candidate_id="shared-candidate", core_opportunity_id="core-b")
    distinct_runs = burn_in.build_burn_in_scorecard(
        days=30,
        now=datetime(2026, 6, 10, tzinfo=timezone.utc),
        outcome_rows=[first, second],
        candidate_rows=[_candidate(first), _candidate(second)],
        core_rows=[_core(first), _core(second)],
        profile="no_key_live",
        artifact_namespace="no_key_live",
    )
    assert distinct_runs.outcome_row_count == 2
    assert "ambiguous_outcome_identity" not in distinct_runs.outcome_exclusion_reason_counts

    invented = burn_in.build_burn_in_scorecard(
        days=30,
        now=datetime(2026, 6, 10, tzinfo=timezone.utc),
        outcome_rows=[valid],
        profile="no_key_live",
        artifact_namespace="no_key_live",
    )
    assert invented.outcome_row_count == 0
    assert invented.outcome_rows_excluded == 1
    assert invented.outcome_exclusion_reason_counts["unmatched_outcome_identity"] == 1
