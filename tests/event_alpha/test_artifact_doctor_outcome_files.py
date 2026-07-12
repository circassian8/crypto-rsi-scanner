"""Canonical file-backed outcome authority checks for the artifact doctor."""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.artifacts import alert_store
from crypto_rsi_scanner.event_alpha.doctor import artifact_doctor
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility


_PROFILE = "no_key_live"
_NAMESPACE = "no_key_live"
_OBSERVED_AT = datetime(2026, 7, 1, tzinfo=timezone.utc)
_OUTCOME_EVALUATED_AT = datetime(2026, 7, 10, tzinfo=timezone.utc)
_EARLY_DOCTOR_CLOCK = datetime(2026, 7, 8, tzinfo=timezone.utc)
_LATE_DOCTOR_CLOCK = datetime(2026, 7, 11, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _outcome() -> dict[str, object]:
    horizon_metadata: dict[str, dict[str, object]] = {}
    returns: dict[str, float | None] = {}
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        due_at = _OBSERVED_AT + timedelta(
            seconds=outcome_eligibility.OUTCOME_HORIZON_SECONDS[horizon]
        )
        matured = due_at <= _OUTCOME_EVALUATED_AT
        return_value = 0.025 if horizon == "3d" else (0.01 if matured else None)
        returns[horizon] = return_value
        horizon_metadata[horizon] = {
            "due_at": _iso(due_at),
            "price_observed_at": _iso(due_at + timedelta(seconds=30)) if matured else None,
            "price_at_horizon": 100.0 * (1.0 + return_value) if return_value is not None else None,
            "price_source": "binance_ohlcv" if matured else None,
            "price_observation_id": f"binance:{horizon}:{due_at.timestamp()}" if matured else None,
            "maturity_status": "matured" if matured else "pending",
            "provenance_status": "observed_market_prices" if matured else "missing",
        }
    row: dict[str, object] = {
        "row_type": "event_alpha_outcome",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "run_id": "run-file-doctor",
        "profile": _PROFILE,
        "run_mode": "burn_in",
        "artifact_namespace": _NAMESPACE,
        "candidate_id": "candidate-file-doctor",
        "core_opportunity_id": "core-file-doctor",
        "observed_at": _iso(_OBSERVED_AT),
        "outcome_eligibility_contract_version": (
            outcome_eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": "observed_market_prices",
        "outcome_evaluated_at": _iso(_OUTCOME_EVALUATED_AT),
        "observation_price_provenance_status": "observed_market_prices",
        "price_at_observation": 100.0,
        "observation_price_source": "fixture_ohlcv",
        "observation_price_id": "fixture:entry:candidate-file-doctor",
        "observation_price_observed_at": _iso(_OBSERVED_AT),
        "primary_horizon": "3d",
        "primary_horizon_return": returns["3d"],
        "return_by_horizon": returns,
        "horizon_metadata": horizon_metadata,
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
    row.update(outcome_eligibility.build_outcome_identity_fields(row))
    return _seal(row)


def _seal(row: dict[str, object]) -> dict[str, object]:
    reasons = outcome_eligibility.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    return row


def _candidate(outcome: dict[str, object]) -> dict[str, object]:
    return {
        field: outcome[field]
        for field in outcome_eligibility.OUTCOME_IDENTITY_FIELDS
    } | {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "research_only": True,
        "symbol": outcome["symbol"],
        "opportunity_type": outcome["opportunity_type"],
        "run_mode": outcome["run_mode"],
    }


def _core(outcome: dict[str, object]) -> dict[str, object]:
    return {
        field: outcome[field]
        for field in (
            "core_opportunity_id",
            "run_id",
            "profile",
            "artifact_namespace",
        )
    } | {
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": outcome["observed_at"],
        "research_only": True,
        "symbol": outcome["symbol"],
        "opportunity_type": outcome["opportunity_type"],
        "run_mode": outcome["run_mode"],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _doctor(
    namespace_dir: Path,
    *,
    outcome_filename: str,
    outcome: dict[str, object],
    evaluated_at: datetime,
):
    canonical = _outcome()
    _write_jsonl(
        namespace_dir / "event_integrated_radar_candidates.jsonl",
        [_candidate(canonical)],
    )
    _write_jsonl(namespace_dir / "event_core_opportunities.jsonl", [_core(canonical)])
    _write_jsonl(namespace_dir / outcome_filename, [outcome])
    return artifact_doctor.diagnose_artifacts(
        profile=_PROFILE,
        artifact_namespace=_NAMESPACE,
        inspected_alert_store_path=namespace_dir / "event_alpha_alerts.jsonl",
        evaluated_at=evaluated_at,
    )


def test_doctor_semantically_loads_integrated_outcomes_with_fixed_clock(tmp_path):
    outcome = _outcome()
    early = _doctor(
        tmp_path / "early",
        outcome_filename="event_integrated_radar_outcomes.jsonl",
        outcome=outcome,
        evaluated_at=_EARLY_DOCTOR_CLOCK,
    )
    late = _doctor(
        tmp_path / "late",
        outcome_filename="event_integrated_radar_outcomes.jsonl",
        outcome=outcome,
        evaluated_at=_LATE_DOCTOR_CLOCK,
    )
    assert early.integrated_outcome_eligibility_contract_invalid == 1
    assert late.integrated_outcome_eligibility_contract_invalid == 0


def test_doctor_semantically_loads_alpha_outcome_provenance_defect(tmp_path):
    outcome = deepcopy(_outcome())
    outcome["horizon_metadata"]["3d"]["price_source"] = None
    result = _doctor(
        tmp_path,
        outcome_filename="event_alpha_outcomes.jsonl",
        outcome=outcome,
        evaluated_at=_LATE_DOCTOR_CLOCK,
    )
    assert result.integrated_outcome_eligible_provenance_missing == 1
    assert result.integrated_outcome_eligibility_contract_invalid == 1


def test_doctor_file_authority_rejects_exact_identity_mismatch(tmp_path):
    outcome = _outcome()
    outcome["candidate_id"] = "candidate-forged-context"
    outcome.update(outcome_eligibility.build_outcome_identity_fields(outcome))
    _seal(outcome)
    result = _doctor(
        tmp_path,
        outcome_filename="event_alpha_outcomes.jsonl",
        outcome=outcome,
        evaluated_at=_LATE_DOCTOR_CLOCK,
    )
    assert result.integrated_outcome_identity_mismatch == 1
    assert result.integrated_outcome_eligibility_contract_invalid == 1


def test_doctor_uses_independent_canonical_paths_not_alert_siblings(tmp_path):
    outcome = _outcome()
    candidate = _candidate(outcome)
    core = _core(outcome)
    namespace_dir = tmp_path / "namespace"
    alert_dir = tmp_path / "overridden-alert-store"
    candidate_path = tmp_path / "candidate-authority" / "candidates.jsonl"
    core_path = tmp_path / "core-authority" / "core.jsonl"
    feedback_path = tmp_path / "feedback-authority" / "feedback.jsonl"
    outcomes_path = tmp_path / "outcome-authority" / "outcomes.jsonl"
    integrated_outcomes_path = tmp_path / "integrated-outcome-authority" / "missing.jsonl"
    alert_path = alert_dir / "alerts.jsonl"

    decoy_outcome = deepcopy(outcome)
    decoy_outcome["candidate_id"] = "decoy-candidate"
    decoy_outcome.update(outcome_eligibility.build_outcome_identity_fields(decoy_outcome))
    _seal(decoy_outcome)
    for decoy_dir in (namespace_dir, alert_dir):
        _write_jsonl(
            decoy_dir / "event_integrated_radar_candidates.jsonl",
            [_candidate(decoy_outcome)],
        )
        _write_jsonl(decoy_dir / "event_core_opportunities.jsonl", [_core(decoy_outcome)])
        _write_jsonl(decoy_dir / "event_alpha_outcomes.jsonl", [decoy_outcome])
        _write_jsonl(
            decoy_dir / "event_alpha_feedback.jsonl",
            [
                {
                    "profile": _PROFILE,
                    "artifact_namespace": _NAMESPACE,
                    "run_mode": "burn_in",
                },
                {
                    "profile": _PROFILE,
                    "artifact_namespace": _NAMESPACE,
                    "run_mode": "burn_in",
                },
            ],
        )

    _write_jsonl(candidate_path, [candidate])
    _write_jsonl(core_path, [core])
    _write_jsonl(
        feedback_path,
        [
            {
                "profile": _PROFILE,
                "artifact_namespace": _NAMESPACE,
                "run_mode": "burn_in",
            }
        ],
    )
    _write_jsonl(outcomes_path, [outcome])
    result = artifact_doctor.diagnose_artifacts(
        profile=_PROFILE,
        artifact_namespace=_NAMESPACE,
        artifact_namespace_dir=namespace_dir,
        inspected_alert_store_path=alert_path,
        feedback_path=feedback_path,
        core_opportunity_store_path=core_path,
        outcomes_path=outcomes_path,
        integrated_candidate_path=candidate_path,
        integrated_outcomes_path=integrated_outcomes_path,
        evaluated_at=_LATE_DOCTOR_CLOCK,
    )
    assert result.feedback_rows == 1
    assert result.integrated_outcome_missing_for_candidate == 0
    assert result.integrated_outcome_identity_mismatch == 0
    assert result.integrated_outcome_eligibility_contract_invalid == 0


def test_doctor_missing_explicit_paths_fail_closed_over_supplied_rows(tmp_path):
    outcome = _outcome()
    candidate_path = tmp_path / "candidate-authority.jsonl"
    _write_jsonl(candidate_path, [_candidate(outcome)])
    result = artifact_doctor.diagnose_artifacts(
        feedback_rows=[{"profile": _PROFILE, "artifact_namespace": _NAMESPACE}],
        outcome_rows=[outcome],
        core_opportunity_rows=[_core(outcome)],
        profile=_PROFILE,
        artifact_namespace=_NAMESPACE,
        artifact_namespace_dir=tmp_path / "namespace",
        inspected_alert_store_path=tmp_path / "alerts" / "alerts.jsonl",
        feedback_path=tmp_path / "missing" / "feedback.jsonl",
        core_opportunity_store_path=tmp_path / "missing" / "core.jsonl",
        outcomes_path=tmp_path / "missing" / "outcomes.jsonl",
        integrated_candidate_path=candidate_path,
        integrated_outcomes_path=tmp_path / "missing" / "integrated-outcomes.jsonl",
        evaluated_at=_LATE_DOCTOR_CLOCK,
    )
    assert result.feedback_rows == 0
    assert result.integrated_candidate_core_missing == 1
    assert result.integrated_outcome_missing_for_candidate == 1


def test_doctor_requires_v2_diagnostic_placeholder_but_excludes_legacy_diagnostic():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    legacy = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "legacy-diagnostic",
        "opportunity_type": "DIAGNOSTIC",
    }
    explicit_v2 = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "v2-diagnostic",
        "opportunity_type": "DIAGNOSTIC",
        "decision_model_version": "crypto_radar_decision_model_v2",
        "decision_model_enabled": True,
        "radar_route": "diagnostic",
    }

    conflicts = event_alpha_artifact_doctor._integrated_outcome_conflicts(  # noqa: SLF001
        [legacy, explicit_v2],
        [],
    )

    assert conflicts["integrated_outcome_missing_for_candidate"] == 1


def test_doctor_accepts_diagnostic_placeholder_without_core_authority(monkeypatch):
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts import outcome_checks

    identity = {
        "run_id": "run-v2",
        "profile": "fixture",
        "artifact_namespace": "fixture",
        "candidate_id": "v2-diagnostic",
        "core_opportunity_id": "diagnostic-core-placeholder",
        "observed_at": "2026-06-15T16:00:00+00:00",
    }
    diagnostic = {
        **identity,
        "opportunity_type": "DIAGNOSTIC",
        "calibration_ineligible_reasons": ["unmatched_outcome_identity"],
    }
    monkeypatch.setattr(
        outcome_checks.outcome_eligibility_contract,
        "partition_joined_calibration_outcomes",
        lambda *_args, **_kwargs: ((), (diagnostic,), {"unmatched_outcome_identity": 1}),
    )

    invalid = outcome_checks._joined_authority_invalid_identities(  # noqa: SLF001
        [diagnostic],
        [diagnostic],
        [],
        evaluated_at="2026-06-15T16:00:00+00:00",
    )

    assert invalid == set()


def test_alert_loader_uses_explicit_core_authority_over_sibling(tmp_path):
    alert_path = tmp_path / "alert-override" / "alerts.jsonl"
    sibling_core_path = alert_path.parent / "event_core_opportunities.jsonl"
    explicit_core_path = tmp_path / "core-override" / "core.jsonl"
    snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-core-override",
        "profile": _PROFILE,
        "artifact_namespace": _NAMESPACE,
        "core_opportunity_id": "core-override",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "route": "RESEARCH_DIGEST",
    }
    sibling_core = {
        **snapshot,
        "row_type": "event_core_opportunity",
        "final_route_after_quality_gate": "STORE_ONLY",
        "route": "STORE_ONLY",
        "final_opportunity_score": 1,
    }
    explicit_core = {
        **sibling_core,
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "route": "HIGH_PRIORITY_RESEARCH",
        "final_opportunity_score": 99,
    }
    _write_jsonl(alert_path, [snapshot])
    _write_jsonl(sibling_core_path, [sibling_core])
    _write_jsonl(explicit_core_path, [explicit_core])

    default_row = alert_store.load_alert_snapshots(alert_path).rows[0]
    explicit_row = alert_store.load_alert_snapshots(
        alert_path,
        core_opportunity_store_path=explicit_core_path,
    ).rows[0]
    missing_row = alert_store.load_alert_snapshots(
        alert_path,
        core_opportunity_store_path=tmp_path / "missing-core.jsonl",
    ).rows[0]
    supplied_row = alert_store.load_alert_snapshots(
        alert_path,
        core_opportunity_rows=[explicit_core],
    ).rows[0]
    assert default_row["final_route_after_quality_gate"] == "STORE_ONLY"
    assert default_row["final_opportunity_score"] == 1
    assert explicit_row["final_opportunity_score"] == 99
    assert "final_opportunity_score" not in missing_row
    assert supplied_row["final_opportunity_score"] == 99


def test_all_cli_artifact_doctor_callers_supply_captured_clock():
    cli_root = Path(__file__).parents[2] / "crypto_rsi_scanner" / "cli"
    callsites: list[tuple[Path, int]] = []
    missing: list[tuple[Path, int]] = []
    required_paths = {
        "artifact_namespace_dir",
        "feedback_path",
        "core_opportunity_store_path",
        "outcomes_path",
        "integrated_candidate_path",
        "integrated_outcomes_path",
    }
    for path in cli_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "diagnose_artifacts"
            ):
                continue
            callsites.append((path, node.lineno))
            clock_keyword = next(
                (keyword for keyword in node.keywords if keyword.arg == "evaluated_at"),
                None,
            )
            if clock_keyword is None or not isinstance(clock_keyword.value, ast.Name):
                missing.append((path, node.lineno))
            if required_paths - {keyword.arg for keyword in node.keywords}:
                missing.append((path, node.lineno))
    assert callsites
    assert missing == []


def test_context_scoped_cli_alert_loaders_supply_core_authority():
    cli_root = Path(__file__).parents[2] / "crypto_rsi_scanner" / "cli"
    callsites: list[tuple[Path, int]] = []
    missing: list[tuple[Path, int]] = []
    for path in cli_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "load_alert_snapshots"
                and node.args
                and isinstance(node.args[0], ast.Attribute)
                and node.args[0].attr == "alert_store_path"
                and isinstance(node.args[0].value, ast.Name)
                and node.args[0].value.id == "context"
            ):
                continue
            callsites.append((path, node.lineno))
            keyword_names = {keyword.arg for keyword in node.keywords}
            if not {"core_opportunity_store_path", "core_opportunity_rows"} & keyword_names:
                missing.append((path, node.lineno))
    assert callsites
    assert missing == []
