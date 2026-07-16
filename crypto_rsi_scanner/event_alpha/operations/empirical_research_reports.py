"""Closed, deterministic publication reports for empirical replay evidence.

The report bundle is a read-only projection of two already immutable replay
runs.  It does not evaluate ideas, select scenarios, mutate production policy,
or inspect provider authorization.  Large row-level replay artifacts remain in
their fingerprinted run namespaces; these reports retain bounded summaries and
the exact manifest/artifact digests needed to resolve that evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..radar import market_anomaly_receipt
from . import (
    empirical_live_campaign,
    empirical_policy_lab,
    empirical_replay_persistence,
    empirical_research_report_conclusions,
    empirical_research_report_validation,
    empirical_replay_store,
    empirical_validation_protocol,
)


SCHEMA_VERSION = 1
MAX_LIVE_REPORT_BYTES = empirical_live_campaign.MAX_REPORT_BYTES
MAX_REPORT_BYTES = 4 * 1024 * 1024
REPORT_FILENAMES = (
    "DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md",
    "DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json",
    "DECISION_RADAR_WALK_FORWARD_REPORT.md",
    "DECISION_RADAR_WALK_FORWARD_REPORT.json",
    "DECISION_RADAR_POLICY_SIMULATION_REPORT.md",
    "DECISION_RADAR_POLICY_SIMULATION_REPORT.json",
    "DECISION_RADAR_RESEARCH_LIMITATIONS.md",
)
_SELECTION_ARTIFACTS = (
    "execution_summary.json",
    "replay_analysis.json",
    "replay_controls.json",
    "targeted_review_queue.json",
    "shadow_policy_simulation.json",
    "recommendation_seal.json",
    "walk_forward.json",
    "replay_trace_summary.json",
    empirical_replay_persistence.IDEA_INDEX_FILENAME,
    empirical_replay_persistence.EPISODE_INDEX_FILENAME,
)
_FINAL_ARTIFACTS = (
    "execution_summary.json",
    "replay_analysis.json",
    "replay_controls.json",
    "targeted_review_queue.json",
    "recommendation_seal.json",
    "final_test_confirmation.json",
    "replay_trace_summary.json",
    empirical_replay_persistence.IDEA_INDEX_FILENAME,
    empirical_replay_persistence.EPISODE_INDEX_FILENAME,
)
_ROUTES = (
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
    "diagnostic",
)
_SAFETY = {
    "research_only": True,
    "auto_apply": False,
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}


@dataclass(frozen=True)
class ReportBundleResult:
    output_dir: Path
    bundle_id: str
    payloads: dict[str, bytes]
    checked: bool


@dataclass(frozen=True)
class _RunEvidence:
    manifest: dict[str, Any]
    payloads: dict[str, bytes]
    values: dict[str, dict[str, Any]]
    binding: dict[str, Any]


def build_report_bundle(
    *,
    selection_run: str | Path,
    final_test_run: str | Path,
    live_campaign_report: str | Path | None = None,
) -> tuple[str, dict[str, bytes]]:
    """Build all seven report bytes after closing cross-run evidence binding."""

    selection = _load_run(selection_run, required=_SELECTION_ARTIFACTS)
    final = _load_run(final_test_run, required=_FINAL_ARTIFACTS)
    _validate_run_modes(selection, final)
    seal = selection.values["recommendation_seal.json"]
    final_seal = final.values["recommendation_seal.json"]
    simulation = selection.values["shadow_policy_simulation.json"]
    confirmation = final.values["final_test_confirmation.json"]
    _validate_policy_chain(selection, final, simulation, seal, final_seal, confirmation)
    live_binding = _load_live_binding(live_campaign_report)
    validation_core = _validation_report(selection, final, live_binding=live_binding)
    walk_core = _walk_forward_report(selection, final)
    policy_core = _policy_report(selection, final)
    limitations_core = _limitations_core(validation_core)
    core_sha256 = _report_core_sha256(
        validation_core, walk_core, policy_core, limitations_core
    )
    envelope = _bundle_envelope(
        selection,
        final,
        seal,
        confirmation,
        live_binding,
        report_core_sha256=core_sha256,
    )
    validation = {**validation_core, "bundle": dict(envelope)}
    walk_forward = {**walk_core, "bundle": dict(envelope)}
    policy = {**policy_core, "bundle": dict(envelope)}
    payloads = _render_payloads(
        validation, walk_forward, policy, limitations_core, envelope
    )
    validate_report_bundle(payloads)
    return str(envelope["bundle_id"]), payloads


def write_report_bundle(
    *,
    selection_run: str | Path,
    final_test_run: str | Path,
    live_campaign_report: str | Path | None,
    output_dir: str | Path,
    check: bool = False,
) -> ReportBundleResult:
    """Atomically write, or byte-check, one complete deterministic bundle."""

    bundle_id, payloads = build_report_bundle(
        selection_run=selection_run,
        final_test_run=final_test_run,
        live_campaign_report=live_campaign_report,
    )
    output = _safe_output_path(output_dir, must_exist=check)
    if check:
        observed = _read_output_payloads(output)
        drift = [name for name in REPORT_FILENAMES if observed.get(name) != payloads[name]]
        if drift:
            raise RuntimeError("empirical_research_report_check_failed:" + ",".join(drift))
    else:
        market_anomaly_receipt.write_artifacts_atomic(
            output,
            payloads=payloads,
            expected_names=REPORT_FILENAMES,
        )
        if _read_output_payloads(output) != payloads:
            raise RuntimeError("empirical_research_report_post_write_drift")
    return ReportBundleResult(output, bundle_id, payloads, check)


def _load_run(path: str | Path, *, required: Sequence[str]) -> _RunEvidence:
    supplied = Path(path).expanduser()
    if supplied.is_symlink() or supplied.parent.is_symlink():
        raise RuntimeError("empirical_research_report_run_path_unsafe")
    _preflight_run_sizes(supplied)
    manifest, payloads = empirical_replay_store.load_verified_run(supplied)
    missing = sorted(set(required) - set(payloads))
    if missing:
        raise ValueError("empirical research run artifacts missing:" + ",".join(missing))
    values = {name: _canonical_mapping(payloads[name], name=name) for name in required}
    binding = {
        "run_fingerprint": manifest["run_fingerprint"],
        "protocol_version": manifest["protocol_version"],
        "protocol_sha256": manifest["protocol_sha256"],
        "input_sha256": manifest["input_sha256"],
        "code_sha256": manifest["code_sha256"],
        "configuration_sha256": _sha256(
            empirical_replay_store.canonical_json_bytes(manifest["configuration"])
        ),
        "manifest_sha256": _sha256(payloads[empirical_replay_store.MANIFEST_FILENAME]),
        "artifact_sha256": {
            name: manifest["artifacts"][name]["sha256"] for name in sorted(required)
        },
        "immutable": True,
        "research_only": True,
        "auto_apply": False,
    }
    return _RunEvidence(manifest, payloads, values, binding)


def _validate_run_modes(selection: _RunEvidence, final: _RunEvidence) -> None:
    selection_config = selection.manifest.get("configuration")
    final_config = final.manifest.get("configuration")
    if not isinstance(selection_config, Mapping) or (
        selection_config.get("mode") != "full"
        or selection_config.get("data_mode") != "full"
        or selection_config.get("partitions") != ["development", "validation"]
        or selection_config.get("universe_top_n") != 100
    ):
        raise ValueError("empirical research selection run must be full top100 development+validation")
    if not isinstance(final_config, Mapping) or (
        final_config.get("mode") != "final_test"
        or final_config.get("data_mode") != "full"
        or final_config.get("partitions") != ["final_test"]
        or final_config.get("universe_top_n") != 100
    ):
        raise ValueError("empirical research final run must be full top100 final_test")
    for run in (selection, final):
        if run.manifest.get("safety") != {key: value for key, value in _SAFETY.items() if key != "production_policy_mutations"}:
            raise ValueError("empirical research run safety contract invalid")
    if (
        selection.manifest["protocol_sha256"] != final.manifest["protocol_sha256"]
        or selection.manifest["protocol_version"] != final.manifest["protocol_version"]
    ):
        raise ValueError("empirical research protocol digest mismatch")
    if selection.manifest["input_sha256"] != final.manifest["input_sha256"]:
        raise ValueError("empirical research final input digest mismatch")
    if selection.manifest["code_sha256"] != final.manifest["code_sha256"]:
        raise ValueError("empirical research final code digest mismatch")
    empirical_research_report_validation.validate_run_semantics(
        manifest=selection.manifest,
        payloads=selection.payloads,
        values=selection.values,
        binding=selection.binding,
        expected_partitions=("development", "validation"),
    )
    empirical_research_report_validation.validate_run_semantics(
        manifest=final.manifest,
        payloads=final.payloads,
        values=final.values,
        binding=final.binding,
        expected_partitions=("final_test",),
    )


def _validate_policy_chain(
    selection: _RunEvidence,
    final: _RunEvidence,
    simulation: Mapping[str, Any],
    seal: Mapping[str, Any],
    final_seal: Mapping[str, Any],
    confirmation: Mapping[str, Any],
) -> None:
    errors = empirical_policy_lab.validate_recommendation_seal(seal)
    if errors:
        raise ValueError("empirical recommendation seal invalid:" + ";".join(errors))
    if selection.payloads["recommendation_seal.json"] != final.payloads["recommendation_seal.json"] or seal != final_seal:
        raise ValueError("empirical final recommendation seal substitution")
    if seal.get("protocol_version") != selection.manifest["protocol_version"]:
        raise ValueError("empirical recommendation seal protocol version mismatch")
    binding = seal.get("selection_run_binding")
    config = selection.manifest["configuration"]
    if not isinstance(binding, Mapping) or (
        binding.get("selection_run_fingerprint") != selection.manifest["run_fingerprint"]
        or binding.get("input_sha256") != selection.manifest["input_sha256"]
        or binding.get("code_sha256") != selection.manifest["code_sha256"]
        or binding.get("configuration_sha256") != _sha256(
            empirical_replay_store.canonical_json_bytes(config)
        )
        or binding.get("mode") != "full"
        or binding.get("simulation_artifact") != "shadow_policy_simulation.json"
        or seal.get("simulation_sha256") != _sha256(
            selection.payloads["shadow_policy_simulation.json"]
        )
    ):
        raise ValueError("empirical recommendation seal selection binding mismatch")
    expected_seal = empirical_policy_lab.freeze_recommendation_set(
        simulation,
        selection_run_binding=binding,
    )
    if seal != expected_seal:
        raise ValueError("empirical recommendation seal producer mismatch")
    final_config = final.manifest["configuration"]
    if final_config.get("recommendation_seal_sha256") != seal.get("seal_sha256"):
        raise ValueError("empirical final configuration seal digest mismatch")
    if simulation.get("partitions") != ["development", "validation"] or (
        simulation.get("protocol_sha256") != selection.manifest["protocol_sha256"]
        or simulation.get("research_only") is not True
        or simulation.get("auto_apply") is not False
    ):
        raise ValueError("empirical selection simulation invalid")
    _validate_selection_policy_artifacts(selection, simulation)
    _validate_confirmation(confirmation, seal, selection, final)


def _validate_selection_policy_artifacts(
    selection: _RunEvidence, simulation: Mapping[str, Any]
) -> None:
    walk = selection.values["walk_forward.json"]
    trace = selection.values["replay_trace_summary.json"]
    analyses = selection.values["replay_analysis.json"]
    protocol = empirical_validation_protocol.protocol_values()
    scenario_names = [
        str(row.get("scenario") or "")
        for row in simulation.get("scenarios", [])
        if isinstance(row, Mapping)
    ]
    frozen_names = [
        str(row.get("name") or "")
        for row in simulation.get("frozen_scenarios", [])
        if isinstance(row, Mapping)
    ]
    analysis_partitions = analyses.get("partitions")
    analysis_active_day_count = 0
    if not isinstance(analysis_partitions, Mapping):
        raise ValueError("empirical selection policy artifact mismatch")
    for partition in ("development", "validation"):
        analysis = analysis_partitions.get(partition)
        burden = analysis.get("operator_burden") if isinstance(analysis, Mapping) else None
        active_days = burden.get("idea_active_day_count") if isinstance(burden, Mapping) else None
        if not isinstance(active_days, int) or isinstance(active_days, bool) or active_days < 0:
            raise ValueError("empirical selection policy artifact mismatch")
        analysis_active_day_count += active_days
    simulation_active_days = simulation.get("idea_active_day_count")
    trace_active_days = trace.get("idea_observed_day_count")
    if (
        simulation.get("schema_id") != empirical_policy_lab.SCHEMA_ID
        or simulation.get("schema_version") != empirical_policy_lab.SCHEMA_VERSION
        or simulation.get("protocol_sha256") != selection.manifest["protocol_sha256"]
        or simulation.get("protocol_version") != selection.manifest["protocol_version"]
        or simulation.get("episode_representatives") != selection.manifest["metrics"]["episode_count"]
        or simulation.get("selected_observation_day_count")
        != trace.get("selected_partition_observed_day_count")
        or not isinstance(simulation_active_days, int)
        or isinstance(simulation_active_days, bool)
        or simulation_active_days != analysis_active_day_count
        or not isinstance(trace_active_days, int)
        or isinstance(trace_active_days, bool)
        or trace_active_days < simulation_active_days
        or trace_active_days > simulation.get("selected_observation_day_count", -1)
        or simulation.get("observed_day_denominator_basis")
        != trace.get("selected_partition_observed_day_basis")
        or scenario_names != frozen_names
        or len(scenario_names) != len(set(scenario_names))
        or simulation.get("multiple_comparison_warning")
        != protocol["statistics"]["multiple_comparison_policy"]
        or simulation.get("human_approval_required") is not True
        or simulation.get("production_policy_mutations") != 0
        or walk.get("schema_id") != empirical_policy_lab.WALK_FORWARD_SCHEMA_ID
        or walk.get("schema_version") != 1
        or walk.get("protocol_sha256") != selection.manifest["protocol_sha256"]
        or walk.get("protocol_version") != selection.manifest["protocol_version"]
        or walk.get("selection_partitions") != ["development", "validation"]
        or walk.get("selected_observation_day_count")
        != simulation.get("selected_observation_day_count")
        or walk.get("idea_active_day_count") != simulation.get("idea_active_day_count")
        or walk.get("observed_day_denominator_basis")
        != simulation.get("observed_day_denominator_basis")
        or walk.get("selected_observation_days_sha256")
        != simulation.get("selected_observation_days_sha256")
        or trace.get("selected_partition_observed_days_sha256")
        != simulation.get("selected_observation_days_sha256")
        or walk.get("final_test_accessed") is not False
        or walk.get("research_only") is not True
        or walk.get("auto_apply") is not False
    ):
        raise ValueError("empirical selection policy artifact mismatch")


def _validate_confirmation(
    value: Mapping[str, Any],
    seal: Mapping[str, Any],
    selection: _RunEvidence,
    final: _RunEvidence,
) -> None:
    confirmations = value.get("confirmations")
    if not isinstance(confirmations, list) or any(not isinstance(row, Mapping) for row in confirmations):
        raise ValueError("empirical final confirmation rows invalid")
    status_counts = Counter(str(row.get("confirmation_status") or "") for row in confirmations)
    candidate_names = sorted(
        str(row.get("scenario") or "")
        for row in seal.get("recommendations", [])
        if isinstance(row, Mapping) and row.get("status") == "candidate"
    )
    candidate_row_names = [str(row.get("scenario") or "") for row in confirmations]
    scenario_rows = value.get("evaluated_scenarios")
    if not isinstance(scenario_rows, list) or any(not isinstance(row, Mapping) for row in scenario_rows):
        raise ValueError("empirical final evaluated scenarios invalid")
    evaluated_names = [str(row.get("scenario") or "") for row in scenario_rows]
    expected_evaluated = ["production_policy", *candidate_names]
    trace = final.values["replay_trace_summary.json"]
    analyses = final.values["replay_analysis.json"]
    analysis_partitions = analyses.get("partitions")
    final_analysis = (
        analysis_partitions.get("final_test")
        if isinstance(analysis_partitions, Mapping)
        else None
    )
    final_burden = (
        final_analysis.get("operator_burden")
        if isinstance(final_analysis, Mapping)
        else None
    )
    analysis_active_days = (
        final_burden.get("idea_active_day_count")
        if isinstance(final_burden, Mapping)
        else None
    )
    confirmation_active_days = value.get("idea_active_day_count")
    trace_active_days = trace.get("idea_observed_day_count")
    protocol = empirical_validation_protocol.protocol_values()
    if (
        value.get("schema_id") != "decision_radar.empirical_final_test_confirmation"
        or value.get("schema_version") != 1
        or value.get("partition") != "final_test"
        or value.get("protocol_version") != final.manifest["protocol_version"]
        or value.get("protocol_sha256") != final.manifest["protocol_sha256"]
        or value.get("recommendation_seal_sha256") != seal.get("seal_sha256")
        or value.get("selection_run_binding") != seal.get("selection_run_binding")
        or value.get("candidate_scenarios") != candidate_names
        or candidate_row_names != candidate_names
        or len(candidate_row_names) != len(set(candidate_row_names))
        or evaluated_names != expected_evaluated
        or len(evaluated_names) != len(set(evaluated_names))
        or value.get("scenario_selection_performed") is not False
        or value.get("final_test_used_for_selection") is not False
        or value.get("research_only") is not True
        or value.get("auto_apply") is not False
        or value.get("production_policy_mutations") != 0
        or value.get("human_approval_required") is not True
        or value.get("scenario_set_sha256") != seal.get("scenario_set_sha256")
        or value.get("final_test_confirmation_rule")
        != seal.get("final_test_confirmation_rule")
        or value.get("final_test_confirmation_rule_sha256")
        != seal.get("final_test_confirmation_rule_sha256")
        or value.get("selected_observation_day_count")
        != trace.get("selected_partition_observed_day_count")
        or not isinstance(analysis_active_days, int)
        or isinstance(analysis_active_days, bool)
        or not isinstance(confirmation_active_days, int)
        or isinstance(confirmation_active_days, bool)
        or confirmation_active_days != analysis_active_days
        or not isinstance(trace_active_days, int)
        or isinstance(trace_active_days, bool)
        or trace_active_days < confirmation_active_days
        or trace_active_days > value.get("selected_observation_day_count", -1)
        or value.get("observed_day_denominator_basis")
        != trace.get("selected_partition_observed_day_basis")
        or value.get("selected_observation_days_sha256")
        != trace.get("selected_partition_observed_days_sha256")
        or value.get("confirmed_candidate_count") != status_counts["confirmed"]
        or value.get("rejected_candidate_count") != status_counts["rejected"]
        or value.get("insufficient_sample_candidate_count") != status_counts["insufficient_sample"]
        or selection.manifest["protocol_sha256"] != value.get("protocol_sha256")
    ):
        raise ValueError("empirical final confirmation binding invalid")
    if any(status not in {"confirmed", "rejected", "insufficient_sample"} for status in status_counts):
        raise ValueError("empirical final confirmation status invalid")
    expected_status = "complete" if candidate_names else "no_candidate_recommendations"
    if value.get("confirmation_status") != expected_status:
        raise ValueError("empirical final confirmation aggregate status invalid")
    minimum = int(protocol["final_test_confirmation_rule"]["minimum_matured_visible_episodes"])
    production = scenario_rows[0]
    for row, scenario in zip(confirmations, scenario_rows[1:], strict=True):
        _validate_confirmation_row(
            row,
            scenario=scenario,
            production=production,
            minimum=minimum,
            denominator=value,
        )


def _validate_confirmation_row(
    row: Mapping[str, Any],
    *,
    scenario: Mapping[str, Any],
    production: Mapping[str, Any],
    minimum: int,
    denominator: Mapping[str, Any],
) -> None:
    status = str(row.get("confirmation_status") or "")
    expected_metrics = {
        "mean_directional_return_fraction": scenario.get("mean_directional_return_fraction"),
        "quick_failure_rate": scenario.get("quick_failure_rate"),
        "ideas_per_observed_day": scenario.get("ideas_per_observed_day"),
        "ideas_per_active_day_descriptive": scenario.get("ideas_per_active_day"),
        "observed_day_count": scenario.get("observed_day_count"),
        "observed_day_denominator_basis": scenario.get("observed_day_denominator_basis"),
        "selected_observation_days_sha256": scenario.get("selected_observation_days_sha256"),
        "matured_visible_episode_count": scenario.get("matured_visible_episode_count"),
    }
    production_metrics = {
        **expected_metrics,
        "mean_directional_return_fraction": production.get("mean_directional_return_fraction"),
        "quick_failure_rate": production.get("quick_failure_rate"),
        "ideas_per_observed_day": production.get("ideas_per_observed_day"),
        "ideas_per_active_day_descriptive": production.get("ideas_per_active_day"),
        "observed_day_count": production.get("observed_day_count"),
        "observed_day_denominator_basis": production.get("observed_day_denominator_basis"),
        "selected_observation_days_sha256": production.get("selected_observation_days_sha256"),
        "matured_visible_episode_count": production.get("matured_visible_episode_count"),
    }
    denominator_match = all(
        scenario.get(field) == production.get(field) == denominator.get(top)
        for field, top in (
            ("observed_day_count", "selected_observation_day_count"),
            ("observed_day_denominator_basis", "observed_day_denominator_basis"),
            ("selected_observation_days_sha256", "selected_observation_days_sha256"),
        )
    )
    if (
        row.get("scenario") != scenario.get("scenario")
        or row.get("selection_status") != "candidate"
        or row.get("sample_size") != scenario.get("matured_visible_episode_count")
        or row.get("minimum_sample_size") != minimum
        or row.get("material_policy_change_count") != scenario.get("material_policy_change_count")
        or row.get("candidate_metrics") != expected_metrics
        or row.get("production_metrics") != production_metrics
        or not isinstance(row.get("checks"), Mapping)
        or row["checks"].get("operator_burden_denominator_match") is not denominator_match
        or row.get("eligible_for_human_policy_review") is not (status == "confirmed")
        or row.get("scenario_selection_performed") is not False
        or row.get("human_approval_required") is not True
        or row.get("production_policy_mutations") != 0
        or row.get("research_only") is not True
        or row.get("auto_apply") is not False
        or row
        != empirical_policy_lab._final_confirmation(
            scenario,
            production,
            rule=empirical_validation_protocol.protocol_values()[
                "final_test_confirmation_rule"
            ],
        )
    ):
        raise ValueError("empirical final confirmation row invalid")


def _bundle_envelope(
    selection: _RunEvidence,
    final: _RunEvidence,
    seal: Mapping[str, Any],
    confirmation: Mapping[str, Any],
    live_binding: Mapping[str, Any],
    *,
    report_core_sha256: Mapping[str, str],
) -> dict[str, Any]:
    body = {
        "schema_id": "decision_radar.empirical_research_report_bundle",
        "schema_version": SCHEMA_VERSION,
        "protocol_version": selection.manifest["protocol_version"],
        "protocol_sha256": selection.manifest["protocol_sha256"],
        "selection_run": selection.binding,
        "final_test_run": final.binding,
        "recommendation_seal_sha256": seal["seal_sha256"],
        "final_confirmation_sha256": _sha256(final.payloads["final_test_confirmation.json"]),
        "live_campaign_report": dict(live_binding),
        "report_artifacts": list(REPORT_FILENAMES),
        "report_core_sha256": dict(report_core_sha256),
        "evidence_lanes": {
            "historical_replay": "selection_and_final_test_kept_distinct",
            "live_no_send": "separate_digest_only_not_pooled_with_replay",
            "fixture": "not_used",
        },
        "safety": dict(_SAFETY),
        "production_contract": {
            "thresholds_changed": False,
            "routes_changed": False,
            "policy_applied": False,
            "dashboard_authority_changed": False,
            "human_approval_required": True,
        },
    }
    return {**body, "bundle_id": _sha256(empirical_replay_store.canonical_json_bytes(body))}


def _validation_report(
    selection: _RunEvidence,
    final: _RunEvidence,
    *,
    live_binding: Mapping[str, Any],
) -> dict[str, Any]:
    selection_analysis = _analysis_summary(selection.values["replay_analysis.json"])
    final_analysis = _analysis_summary(final.values["replay_analysis.json"])
    selection_controls = _controls_summary(selection.values["replay_controls.json"])
    final_controls = _controls_summary(final.values["replay_controls.json"])
    conclusions = _conclusions(
        selection_analysis,
        final_analysis,
        confirmation=final.values["final_test_confirmation.json"],
        walk=selection.values["walk_forward.json"],
        simulation=selection.values["shadow_policy_simulation.json"],
        selection_controls=selection_controls,
        final_controls=final_controls,
        live_binding=live_binding,
    )
    return {
        "schema_id": "decision_radar.empirical_validation_report",
        "schema_version": SCHEMA_VERSION,
        "report_status": "closed_immutable_evidence_projection",
        "selection_execution": selection.values["execution_summary.json"],
        "final_test_execution": final.values["execution_summary.json"],
        "selection_analysis": selection_analysis,
        "final_test_analysis": final_analysis,
        "selection_controls": selection_controls,
        "final_test_controls": final_controls,
        "review_evidence": {
            "selection": _review_summary(selection.values["targeted_review_queue.json"]),
            "final_test": _review_summary(final.values["targeted_review_queue.json"]),
        },
        "final_confirmation": final.values["final_test_confirmation.json"],
        "conclusions": conclusions,
        "safety": dict(_SAFETY),
    }


def _walk_forward_report(
    selection: _RunEvidence,
    final: _RunEvidence,
) -> dict[str, Any]:
    walk = selection.values["walk_forward.json"]
    return {
        "schema_id": "decision_radar.empirical_walk_forward_report",
        "schema_version": SCHEMA_VERSION,
        "walk_forward": walk,
        "final_confirmation": final.values["final_test_confirmation.json"],
        "conclusion": {
            "sample_size": walk.get("outcome_evaluable_fold_count", 0),
            "sample_unit": "outcome_evaluable_chronological_walk_forward_folds",
            "nonempty_fold_count": walk.get("nonempty_fold_count", 0),
            "partition": "development_and_validation",
            "evidence_strength": "exploratory_walk_forward",
            "uncertainty": "fold_results_are_not_independent_causal_estimates",
            "evidence_lane": "historical_replay",
            "policy_eligible": False,
            "human_approval_required": True,
            "status": walk.get("status", "unknown"),
        },
        "safety": dict(_SAFETY),
    }


def _policy_report(
    selection: _RunEvidence,
    final: _RunEvidence,
) -> dict[str, Any]:
    return {
        "schema_id": "decision_radar.empirical_policy_simulation_report",
        "schema_version": SCHEMA_VERSION,
        "selection_simulation": selection.values["shadow_policy_simulation.json"],
        "frozen_recommendation_seal": selection.values["recommendation_seal.json"],
        "final_test_confirmation": final.values["final_test_confirmation.json"],
        "decision_boundary": {
            "selection_uses_final_test": False,
            "final_test_can_nominate_new_scenarios": False,
            "automatic_policy_application": False,
            "human_approval_required": True,
            "production_policy_unchanged": True,
        },
        "safety": dict(_SAFETY),
    }


def _analysis_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    partitions = value.get("partitions")
    if value.get("research_only") is not True or value.get("auto_apply") is not False or not isinstance(partitions, Mapping):
        raise ValueError("empirical replay analysis invalid")
    return {
        "schema_id": value.get("schema_id"),
        "schema_version": value.get("schema_version"),
        "partitions": {
            str(name): _partition_analysis_summary(row)
            for name, row in sorted(partitions.items())
            if isinstance(row, Mapping)
        },
        "research_only": True,
        "auto_apply": False,
    }


def _partition_analysis_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    cohort_names = (
        "route_cohorts",
        "primary_origin_cohorts",
        "market_regime_cohorts",
        "liquidity_tier_cohorts",
        "market_catalyst_cohorts",
        "data_quality_cohorts",
    )
    dimensions = value.get("dimension_analysis")
    compact_dimensions: dict[str, Any] = {}
    if isinstance(dimensions, Mapping):
        compact_dimensions = {
            "cohorts": {
                str(name): _cohort_rows(rows)
                for name, rows in sorted((dimensions.get("cohorts") or {}).items())
                if isinstance(rows, list)
            },
            "expiry_status_cohorts": _cohort_rows(dimensions.get("expiry_status_cohorts")),
            "post_expiry_status_cohorts": _cohort_rows(dimensions.get("post_expiry_status_cohorts")),
            "horizon_sensitivity": _cohort_rows(dimensions.get("horizon_sensitivity")),
            "timing_metrics": _cohort_rows(dimensions.get("timing_metrics")),
            "provider_source_combination_definitions": dimensions.get("provider_source_combination_definitions", []),
            "return_unit": dimensions.get("return_unit"),
            "timing_unit": dimensions.get("timing_unit"),
        }
    false_rows = value.get("false_positive_and_late_classifications")
    missed_rows = value.get("missed_opportunity_classifications")
    return {
        key: value.get(key)
        for key in (
            "schema_id",
            "schema_version",
            "method",
            "protocol_version",
            "protocol_sha256",
            "partition",
            "evidence_mode",
            "episode_count",
            "matured_episode_count",
            "directional_return_sample_size",
            "return_unit",
            "analysis_digest",
            "invalid_declared_return_unit_count",
            "unclassified_primary_origin_count",
            "unclassified_route_count",
            "recommendation",
            "policy_eligible",
            "causal_claim",
            "research_only",
            "auto_apply",
            "multiple_comparison_warning",
            "safety",
        )
    } | {
        **{name: _cohort_rows(value.get(name)) for name in cohort_names},
        "dimension_analysis": compact_dimensions,
        "score_monotonicity": _bounded_json(value.get("score_monotonicity", []), limit=256),
        "cost_sensitivity": _bounded_json(value.get("cost_sensitivity", {}), limit=128),
        "survivability": _bounded_json(value.get("survivability", {}), limit=512),
        "operator_burden": _operator_burden_summary(value.get("operator_burden")),
        "false_positive_and_late_summary": _classification_summary(false_rows),
        "missed_opportunity_summary": _classification_summary(missed_rows),
    }


def _cohort_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    allowed = {
        "cohort", "cohort_type", "partition", "episode_count", "matured_episode_count",
        "sample_size", "sample_status", "evidence_strength", "evidence_mode", "result_direction",
        "return_basis", "return_unit", "hit_rate", "mean_directional_return_fraction",
        "median_directional_return_fraction", "trimmed_mean_10pct_directional_return_fraction",
        "mean_raw_primary_return_fraction", "mean_mfe_fraction", "median_mfe_fraction",
        "mean_mae_fraction", "median_mae_fraction", "mfe_to_mae_ratio_of_means",
        "downside_5pct_fraction", "worst_directional_return_fraction", "uncertainty",
        "policy_eligible", "causal_claim", "research_only", "auto_apply", "horizon",
        "horizon_days", "status", "metric", "unit", "value", "available_count",
    }
    return [
        {key: row[key] for key in row if key in allowed}
        for row in value[:256]
        if isinstance(row, Mapping)
    ]


def _operator_burden_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"status": "unavailable"}
    scalars = {
        key: item for key, item in value.items()
        if not isinstance(item, (Mapping, list))
    }
    return {
        **scalars,
        "selected_observation_day_count": value.get("selected_observation_day_count", value.get("observed_day_count")),
        "idea_active_day_count": value.get("idea_active_day_count"),
        "ideas_per_selected_observation_day": value.get(
            "ideas_per_selected_observation_day", value.get("mean_ideas_per_observed_day")
        ),
        "frozen_budgets": _bounded_json(value.get("frozen_budgets", {}), limit=64),
        "simulations": _bounded_json(value.get("simulations", {}), limit=256),
        "idea_lifetime_and_expiry": _bounded_json(value.get("idea_lifetime_and_expiry", {}), limit=64),
        "material_change_intervals": _bounded_json(value.get("material_change_intervals", {}), limit=64),
        "sample_status": _bounded_json(value.get("sample_status", {}), limit=32),
    }


def _classification_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, list):
        return {"row_count": 0, "status": "unavailable"}
    symptoms: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    classifications: Counter[str] = Counter()
    for row in value:
        if not isinstance(row, Mapping):
            continue
        symptoms.update(str(item) for item in row.get("symptom_codes", []) if item)
        reasons.update(str(item) for item in row.get("reason_codes", []) if item)
        if row.get("classification"):
            classifications[str(row["classification"])] += 1
    return {
        "row_count": sum(isinstance(row, Mapping) for row in value),
        "symptom_counts": dict(sorted(symptoms.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "classification_counts": dict(sorted(classifications.items())),
        "row_level_examples_remain_in_immutable_run": True,
    }


def _controls_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        raise ValueError("empirical replay controls invalid")
    benchmarks = value.get("benchmark_rows")
    compact_benchmarks = []
    if isinstance(benchmarks, list):
        for row in benchmarks:
            if not isinstance(row, Mapping):
                continue
            compact_benchmarks.append({
                key: item for key, item in row.items()
                if key not in {"selections", "primary_outcome_metrics"}
                and not isinstance(item, (Mapping, list))
            } | {
                "cost_sensitivity": _bounded_json(row.get("cost_sensitivity", {}), limit=128),
                "holding_period_sensitivity": _bounded_json(row.get("holding_period_sensitivity", {}), limit=128),
                "unavailable_reason_counts": _bounded_json(row.get("unavailable_reason_counts", {}), limit=64),
            })
    return {
        "schema_id": value.get("schema_id"),
        "schema_version": value.get("schema_version"),
        "method": value.get("method"),
        "protocol_version": value.get("protocol_version"),
        "protocol_sha256": value.get("protocol_sha256"),
        "contract_digest": value.get("contract_digest"),
        "evidence_mode": value.get("evidence_mode"),
        "observation_count": value.get("observation_count"),
        "idea_count": value.get("idea_count"),
        "benchmark_policy_order": value.get("benchmark_policy_order", []),
        "benchmarks": compact_benchmarks,
        "matched_non_signal_controls": _mapping_without_rows(value.get("matched_non_signal_controls")),
        "missed_move_evaluation": _mapping_without_rows(value.get("missed_move_evaluation")),
        "matched_control_causal_claim": value.get("matched_control_causal_claim"),
        "selection_uses_outcomes": value.get("selection_uses_outcomes"),
        "final_test_used_for_tuning": value.get("final_test_used_for_tuning"),
        "policy_eligible": value.get("policy_eligible"),
        "research_only": True,
        "auto_apply": False,
        "safety": value.get("safety"),
    }


def _mapping_without_rows(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"status": "unavailable"}
    return {
        key: _bounded_json(item, limit=128)
        for key, item in value.items()
        if key not in {"rows", "selections", "endpoint_candidates", "missed_opportunities"}
    }


def _review_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.get(key)
        for key in (
            "schema_id", "schema_version", "method", "run_fingerprint",
            "protocol_version", "protocol_sha256", "item_count",
            "maximum_item_count", "queue_truncated", "closed_category_taxonomy", "category_order",
            "categories", "queue_digest", "evidence_digest", "policy_eligible",
            "selection_uses_outcomes", "selection_changes_replay_results",
            "final_test_used_for_policy_selection", "causal_claim", "research_only",
            "auto_apply", "safety",
        )
    } | {"row_level_items_remain_in_immutable_run": True}


def _conclusions(
    selection: Mapping[str, Any],
    final: Mapping[str, Any],
    *,
    confirmation: Mapping[str, Any],
    walk: Mapping[str, Any],
    simulation: Mapping[str, Any],
    selection_controls: Mapping[str, Any],
    final_controls: Mapping[str, Any],
    live_binding: Mapping[str, Any],
) -> dict[str, Any]:
    return empirical_research_report_conclusions.build_conclusions(
        selection,
        final,
        confirmation=confirmation,
        walk=walk,
        simulation=simulation,
        selection_controls=selection_controls,
        final_controls=final_controls,
        live_binding=live_binding,
    )


def _limitations_core(validation: Mapping[str, Any]) -> dict[str, Any]:
    selection = validation["selection_execution"]
    conclusion = validation["conclusions"]
    return {
        "schema_id": "decision_radar.empirical_research_limitations",
        "schema_version": SCHEMA_VERSION,
        "limitations": [
            "historical replay is descriptive and cannot establish causal alpha",
            "daily historical OHLCV cannot validate intraday execution, exact alert latency, order-book spread, slippage, or adverse selection",
            "cost results are assumptions unless separately marked observed",
            "proxy and direct evidence remain separate cohorts",
            "matched controls are not a randomized experiment",
            "walk-forward folds overlap in training history and are not independent trials",
            "multiple cohort and scenario comparisons increase false-discovery risk",
            "live no-send evidence is not pooled into historical replay sample sizes",
            "human labels are optional preference data and cannot auto-tune the model",
            "final-test results cannot nominate a new policy scenario",
        ],
        "historical_spread_observed": selection.get("historical_spread_observed", False),
        "residual_survivorship_present": selection.get("residual_survivorship_present", "unknown"),
        "routes_with_no_empirical_evidence": conclusion.get(
            "routes_with_no_empirical_evidence", []
        ),
        "no_evidence_is_not_validation": True,
        "next_human_boundary": "review sealed confirmation with sample size, regime coverage, data quality, cost survivability, and operator burden before any explicit policy decision",
        "production_policy_unchanged": True,
        "research_only": True,
        "auto_apply": False,
    }


def _report_core_sha256(
    validation: Mapping[str, Any],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    limitations: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "empirical_validation": _sha256(
            empirical_replay_store.canonical_json_bytes(validation)
        ),
        "walk_forward": _sha256(empirical_replay_store.canonical_json_bytes(walk)),
        "policy_simulation": _sha256(
            empirical_replay_store.canonical_json_bytes(policy)
        ),
        "research_limitations": _sha256(
            empirical_replay_store.canonical_json_bytes(limitations)
        ),
    }


def _render_payloads(
    validation: Mapping[str, Any],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    limitations: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> dict[str, bytes]:
    return {
        REPORT_FILENAMES[0]: _validation_markdown(validation).encode("utf-8"),
        REPORT_FILENAMES[1]: empirical_replay_store.canonical_json_bytes(validation),
        REPORT_FILENAMES[2]: _walk_forward_markdown(walk).encode("utf-8"),
        REPORT_FILENAMES[3]: empirical_replay_store.canonical_json_bytes(walk),
        REPORT_FILENAMES[4]: _policy_markdown(policy).encode("utf-8"),
        REPORT_FILENAMES[5]: empirical_replay_store.canonical_json_bytes(policy),
        REPORT_FILENAMES[6]: _limitations_markdown(limitations, envelope).encode(
            "utf-8"
        ),
    }


def validate_report_bundle(payloads: Mapping[str, bytes]) -> dict[str, Any]:
    """Recompute core digests, envelope ID, and every deterministic output byte."""

    if tuple(payloads) != REPORT_FILENAMES:
        raise RuntimeError("empirical_research_report_bundle_invalid")
    validation = _canonical_mapping(payloads[REPORT_FILENAMES[1]], name=REPORT_FILENAMES[1])
    walk = _canonical_mapping(payloads[REPORT_FILENAMES[3]], name=REPORT_FILENAMES[3])
    policy = _canonical_mapping(payloads[REPORT_FILENAMES[5]], name=REPORT_FILENAMES[5])
    envelopes = [row.get("bundle") for row in (validation, walk, policy)]
    if not all(isinstance(row, Mapping) and row == envelopes[0] for row in envelopes):
        raise RuntimeError("empirical_research_report_envelope_splice")
    envelope = dict(envelopes[0])
    bundle_id = str(envelope.pop("bundle_id", ""))
    if bundle_id != _sha256(empirical_replay_store.canonical_json_bytes(envelope)):
        raise RuntimeError("empirical_research_report_bundle_id_invalid")
    empirical_research_report_validation.validate_published_bundle(
        validation=validation,
        walk=walk,
        policy=policy,
        envelope=envelope,
        expected_report_filenames=REPORT_FILENAMES,
        expected_safety=_SAFETY,
    )
    validation_core = {key: value for key, value in validation.items() if key != "bundle"}
    walk_core = {key: value for key, value in walk.items() if key != "bundle"}
    policy_core = {key: value for key, value in policy.items() if key != "bundle"}
    limitations_core = _limitations_core(validation_core)
    observed_core_sha256 = _report_core_sha256(
        validation_core, walk_core, policy_core, limitations_core
    )
    if envelope.get("report_core_sha256") != observed_core_sha256:
        raise RuntimeError("empirical_research_report_core_digest_invalid")
    closed_envelope = {**envelope, "bundle_id": bundle_id}
    expected = _render_payloads(
        validation, walk, policy, limitations_core, closed_envelope
    )
    if expected != dict(payloads):
        raise RuntimeError("empirical_research_report_render_drift")
    _validate_payloads(payloads, expected_bundle_id=bundle_id)
    return closed_envelope


def _load_live_binding(path: str | Path | None) -> dict[str, Any]:
    if path is None or not str(path).strip():
        return {
            "status": "not_provided",
            "sha256": None,
            "size_bytes": 0,
            "evidence_pooled_with_replay": False,
        }
    supplied = Path(path).expanduser()
    payload = _read_parent_anchored_file(supplied, maximum=MAX_LIVE_REPORT_BYTES)
    value = _json_mapping(payload, name="live_campaign_report")
    try:
        projection = empirical_live_campaign.project_live_campaign(value)
    except ValueError as exc:
        raise ValueError("empirical live campaign report invalid") from exc
    projection_payload = empirical_replay_store.canonical_json_bytes(projection)
    return {
        "status": "provided_separate_observational_lane",
        "filename": supplied.name,
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
        "schema_id": value.get("schema_id"),
        "canonical_projection_sha256": _sha256(projection_payload),
        "canonical_projection": projection,
        "evidence_pooled_with_replay": False,
    }


def _canonical_mapping(payload: bytes, *, name: str) -> dict[str, Any]:
    value = _json_mapping(payload, name=name)
    if payload != empirical_replay_store.canonical_json_bytes(value):
        raise ValueError(f"empirical research artifact noncanonical:{name}")
    return value


def _json_mapping(payload: bytes, *, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"empirical research artifact invalid:{name}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"empirical research artifact invalid:{name}")
    return dict(value)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_parent_anchored_file(path: Path, *, maximum: int) -> bytes:
    absolute = Path(os.path.abspath(path))
    if absolute.is_symlink() or absolute.parent.is_symlink():
        raise RuntimeError("empirical_research_report_input_path_unsafe")
    parent_fd = _open_directory_fd(absolute.parent)
    file_fd = -1
    try:
        parent_status = os.fstat(parent_fd)
        file_fd = os.open(
            absolute.name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > maximum:
            raise RuntimeError("empirical_research_report_input_too_large")
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(file_fd, min(1024 * 1024, maximum + 1 - total)):
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise RuntimeError("empirical_research_report_input_too_large")
        after = os.fstat(file_fd)
        current_parent = absolute.parent.stat(follow_symlinks=False)
        if (
            (
                opened.st_dev, opened.st_ino, opened.st_size,
                opened.st_mtime_ns, opened.st_ctime_ns,
            )
            != (
                after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns, after.st_ctime_ns,
            )
            or (parent_status.st_dev, parent_status.st_ino)
            != (current_parent.st_dev, current_parent.st_ino)
        ):
            raise RuntimeError("empirical_research_report_input_identity_drift")
        return b"".join(chunks)
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError("empirical_research_report_input_unavailable") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def _open_directory_fd(path: Path) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("empirical_research_report_directory_unsafe") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RuntimeError("empirical_research_report_directory_unsafe")
    return descriptor


def _preflight_run_sizes(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    directory_fd = _open_directory_fd(absolute)
    try:
        total = 0
        for name in os.listdir(directory_fd):
            status = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if not stat.S_ISREG(status.st_mode):
                raise RuntimeError("empirical_research_report_run_leaf_unsafe")
            maximum = (
                2 * 1024 * 1024
                if name == empirical_replay_store.MANIFEST_FILENAME
                else empirical_replay_store.MAX_ARTIFACT_BYTES
            )
            if status.st_size > maximum:
                raise RuntimeError("empirical_research_report_run_artifact_too_large")
            total += status.st_size
        if total > empirical_replay_store.MAX_BUNDLE_BYTES + 2 * 1024 * 1024:
            raise RuntimeError("empirical_research_report_run_bundle_too_large")
    finally:
        os.close(directory_fd)


def _safe_output_path(path: str | Path, *, must_exist: bool) -> Path:
    supplied = Path(path).expanduser()
    if supplied.is_symlink() or supplied.parent.is_symlink():
        raise RuntimeError("empirical_research_report_output_path_unsafe")
    absolute = Path(os.path.abspath(supplied))
    if must_exist and (not absolute.exists() or not absolute.is_dir()):
        raise RuntimeError("empirical_research_report_output_unavailable")
    if not absolute.exists() and not absolute.parent.is_dir():
        raise RuntimeError("empirical_research_report_output_parent_unavailable")
    return absolute


def _read_output_payloads(output: Path) -> dict[str, bytes]:
    if output.is_symlink() or not output.is_dir():
        raise RuntimeError("empirical_research_report_output_path_unsafe")
    return {
        name: _read_parent_anchored_file(output / name, maximum=MAX_REPORT_BYTES)
        for name in REPORT_FILENAMES
    }


def _bounded_json(value: Any, *, limit: int) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _bounded_json(item, limit=limit)
            for key, item in list(sorted(value.items(), key=lambda row: str(row[0])))[:limit]
        }
    if isinstance(value, list):
        return [_bounded_json(item, limit=limit) for item in value[:limit]]
    return value


def _validate_payloads(payloads: Mapping[str, bytes], *, expected_bundle_id: str) -> None:
    if tuple(payloads) != REPORT_FILENAMES:
        raise RuntimeError("empirical_research_report_bundle_invalid")
    for name, payload in payloads.items():
        if not payload or len(payload) > MAX_REPORT_BYTES:
            raise RuntimeError(f"empirical_research_report_size_invalid:{name}")
        if expected_bundle_id.encode("ascii") not in payload:
            raise RuntimeError(f"empirical_research_report_bundle_id_missing:{name}")


def _validation_markdown(report: Mapping[str, Any]) -> str:
    envelope = report["bundle"]
    conclusion = report["conclusions"]
    selection = report["selection_execution"]
    final = report["final_test_execution"]
    lines = _markdown_header("Decision Radar Empirical Validation Report", envelope)
    lines += [
        "## Verdict",
        "",
        "This is a research-only, descriptive replay result. It does not establish causal alpha, recommend a trade, or change production policy.",
        "",
        f"- Selection ideas / episodes: {selection.get('idea_count', 0)} / {selection.get('episode_count', 0)}",
        f"- Final-test ideas / episodes: {final.get('idea_count', 0)} / {final.get('episode_count', 0)}",
        f"- Final confirmation: `{conclusion.get('final_confirmation_status')}`",
        f"- Confirmed / rejected / insufficient: {conclusion.get('confirmed_candidate_count', 0)} / {conclusion.get('rejected_candidate_count', 0)} / {conclusion.get('insufficient_sample_candidate_count', 0)}",
        "",
        "## Route evidence",
        "",
        "| Route | Development | Validation | Final test |",
        "|---|---:|---:|---:|",
    ]
    for route in _ROUTES:
        samples = conclusion["route_matured_episode_samples"].get(route, {})
        lines.append(
            f"| `{route}` | {samples.get('development', 0)} | {samples.get('validation', 0)} | {samples.get('final_test', 0)} |"
        )
    walk = conclusion.get("walk_forward_stability", {})
    monotonicity = conclusion.get("score_monotonicity", {})
    live = conclusion.get("live_campaign_integration", {})
    lines += [
        "",
        "Zero samples are reported as no evidence, never as validation.",
        "",
        "## Cross-checks",
        "",
        f"- Walk-forward: `{walk.get('status')}`; outcome-evaluable folds {walk.get('outcome_evaluable_fold_count', 0)} / {walk.get('minimum_fold_count', 0)} required.",
        "- Score monotonicity: " + ", ".join(
            f"{partition}=`{row.get('status')}`"
            for partition, row in sorted(monotonicity.items())
            if isinstance(row, Mapping)
        ),
        f"- Live no-send lane: `{live.get('status')}`; evidence pooled with replay: `{live.get('evidence_pooled_with_replay')}`.",
        f"- Confirmation verification: {conclusion.get('confirmation_verification_scope')}",
        "",
        "## Additional evidence most needed",
        "",
        *[f"- {item}" for item in conclusion.get("additional_data_most_needed", [])],
        "",
        "## Evidence boundaries",
        "",
        "- Historical replay and live no-send evidence remain separate.",
        "- Missing historical spread is not treated as observed execution quality.",
        "- Matched controls are descriptive and do not support causal inference.",
        "- Every policy recommendation still requires an explicit human decision.",
        "",
    ]
    return "\n".join(lines)


def _walk_forward_markdown(report: Mapping[str, Any]) -> str:
    envelope = report["bundle"]
    walk = report["walk_forward"]
    lines = _markdown_header("Decision Radar Walk-Forward Report", envelope)
    lines += [
        "## Result",
        "",
        f"- Status: `{walk.get('status', 'unknown')}`",
        f"- Folds / non-empty / outcome-evaluable / required: {walk.get('fold_count', 0)} / {walk.get('nonempty_fold_count', 0)} / {walk.get('outcome_evaluable_fold_count', 0)} / {walk.get('minimum_fold_count', 0)}",
        f"- Outcome purge rule: `{walk.get('outcome_purge_rule', 'unavailable')}`",
        f"- Final test accessed for selection: `{walk.get('final_test_accessed', False)}`",
        "",
        "| Fold | Train end | Test end | Selected scenario | Test episodes |",
        "|---:|---|---|---|---:|",
    ]
    for fold in walk.get("folds", []):
        if isinstance(fold, Mapping):
            lines.append(
                f"| {fold.get('fold')} | {fold.get('train_end_exclusive')} | {fold.get('test_end_exclusive')} | `{fold.get('selected_scenario')}` | {fold.get('test_episode_count', 0)} |"
            )
    lines += [
        "",
        "Fold estimates are exploratory, not independent causal estimates. No scenario is applied automatically.",
        "",
    ]
    return "\n".join(lines)


def _policy_markdown(report: Mapping[str, Any]) -> str:
    envelope = report["bundle"]
    simulation = report["selection_simulation"]
    confirmation = report["final_test_confirmation"]
    lines = _markdown_header("Decision Radar Policy Simulation Report", envelope)
    lines += [
        "## Frozen recommendations",
        "",
        "| Scenario | Selection status | Evidence | Reason |",
        "|---|---|---|---|",
    ]
    for row in simulation.get("recommendations", []):
        if isinstance(row, Mapping):
            lines.append(
                f"| `{row.get('scenario')}` | `{row.get('status')}` | `{row.get('evidence_strength')}` | {row.get('reason')} |"
            )
    lines += [
        "",
        "## Sealed final-test confirmation",
        "",
        f"- Status: `{confirmation.get('confirmation_status')}`",
        f"- Confirmed / rejected / insufficient: {confirmation.get('confirmed_candidate_count', 0)} / {confirmation.get('rejected_candidate_count', 0)} / {confirmation.get('insufficient_sample_candidate_count', 0)}",
        "- Final-test data could confirm or reject only pre-sealed candidates; it could not nominate a new scenario.",
        "- Production thresholds and routes remain unchanged. Human approval is required for any future policy change.",
        "",
    ]
    return "\n".join(lines)


def _limitations_markdown(
    limitations: Mapping[str, Any], envelope: Mapping[str, Any]
) -> str:
    lines = _markdown_header("Decision Radar Research Limitations", envelope)
    lines += [
        "## Current limitations",
        "",
        "1. Historical replay is descriptive and cannot establish causal alpha.",
        "2. Daily historical OHLCV cannot validate intraday execution, exact alert latency, order-book spread, slippage, or adverse selection.",
        f"3. Historical spread observed: `{limitations.get('historical_spread_observed', False)}`. Cost results are assumptions unless separately marked observed.",
        f"4. Residual survivorship present: `{limitations.get('residual_survivorship_present', 'unknown')}`.",
        "5. Proxy and direct evidence remain separate cohorts; a proxy-only result must not be generalized to direct live evidence.",
        "6. Matched controls are selected without outcomes but are not a randomized experiment.",
        "7. Walk-forward folds overlap in training history and are not independent trials.",
        "8. Multiple cohort and scenario comparisons increase false-discovery risk.",
        "9. Live no-send evidence is fingerprinted separately and is never pooled into historical replay sample sizes.",
        "10. Human review labels are optional preference data and cannot auto-tune the model.",
        "11. No final-test result can nominate a new policy scenario.",
        "12. No thresholds, routes, sends, trades, execution, paper trades, RSI writes, or dashboard authority changed.",
        "",
        "## Explicit no-evidence routes",
        "",
    ]
    zero_routes = limitations.get("routes_with_no_empirical_evidence", [])
    lines.append(", ".join(f"`{route}`" for route in zero_routes) if zero_routes else "None in the closed route taxonomy.")
    lines += [
        "",
        "A zero-sample route is unvalidated; it is not evidence of safety, weakness, or strength.",
        "",
        "## Next human boundary",
        "",
        "Review any sealed confirmation alongside sample size, regime coverage, data-quality basis, cost survivability, and operator burden. A separate explicit human decision is required before changing production policy.",
        "",
    ]
    return "\n".join(lines)


def _markdown_header(title: str, envelope: Mapping[str, Any]) -> list[str]:
    live = envelope["live_campaign_report"]
    return [
        f"# {title}",
        "",
        f"- Report bundle: `{envelope['bundle_id']}`",
        f"- Protocol: `{envelope['protocol_version']}` (`{envelope['protocol_sha256']}`)",
        f"- Selection run: `{envelope['selection_run']['run_fingerprint']}`",
        f"- Final-test run: `{envelope['final_test_run']['run_fingerprint']}`",
        f"- Recommendation seal: `{envelope['recommendation_seal_sha256']}`",
        f"- Live no-send report: `{live['status']}`",
        "- Safety: research only; no automatic policy application; no sends, trades, orders, paper trades, RSI writes, provider calls, or authority mutations.",
        "",
    ]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish closed Decision Radar empirical reports.")
    parser.add_argument("--selection-run", required=True)
    parser.add_argument("--final-test-run", required=True)
    parser.add_argument("--live-campaign-report", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = write_report_bundle(
        selection_run=args.selection_run,
        final_test_run=args.final_test_run,
        live_campaign_report=args.live_campaign_report,
        output_dir=args.output_dir,
        check=args.check,
    )
    action = "checked" if result.checked else "written"
    print(f"empirical research report bundle {action}: {result.bundle_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_FILENAMES",
    "ReportBundleResult",
    "build_report_bundle",
    "main",
    "validate_report_bundle",
    "write_report_bundle",
]
