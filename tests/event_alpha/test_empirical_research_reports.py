from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_live_campaign,
    empirical_policy_lab,
    empirical_replay_analysis,
    empirical_replay_controls,
    empirical_replay_persistence,
    empirical_replay_store,
    empirical_research_report_validation,
    empirical_research_reports,
    empirical_review,
    empirical_validation_protocol,
)


_INPUT = "b" * 64
_CODE = "c" * 64
_SELECTION_DAYS = {
    "development": ("2022-06-01",),
    "validation": ("2024-06-01",),
}
_FINAL_DAYS = {"final_test": ("2025-06-01",)}


def _safety() -> dict[str, object]:
    return {
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
    }


def _value_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _days_digest(days: tuple[str, ...]) -> str:
    return empirical_validation_protocol.selected_observation_days_sha256(days)


def _analysis(days: dict[str, tuple[str, ...]]) -> dict[str, object]:
    return {
        "schema_id": "decision_radar.empirical_partition_analyses",
        "schema_version": 1,
        "partitions": {
            partition: empirical_replay_analysis.build_empirical_replay_analysis_from_episodes(
                {"episodes": []},
                partition=partition,
                evidence_mode="historical_replay",
                bootstrap_resamples=10,
                selected_observation_days=partition_days,
            )
            for partition, partition_days in days.items()
        },
        "research_only": True,
        "auto_apply": False,
    }


def _controls(*, observation_count: int) -> dict[str, object]:
    protocol = empirical_validation_protocol.protocol_values()
    body: dict[str, object] = {
        "schema_id": empirical_replay_controls.SCHEMA_ID,
        "schema_version": empirical_replay_controls.SCHEMA_VERSION,
        "method": empirical_replay_controls.METHOD,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "evidence_mode": "historical_replay",
        "observation_count": observation_count,
        "idea_count": 0,
        "benchmark_policy_order": protocol["benchmark_policies"],
        "benchmark_rows": [],
        "matched_non_signal_controls": {
            "selected_control_count": 0,
            "rows": [],
            "selection_uses_outcomes": False,
        },
        "missed_move_evaluation": {
            "endpoint_candidate_count": 0,
            "missed_opportunity_count": 0,
            "missed_opportunities": [],
        },
        "matched_control_causal_claim": False,
        "selection_uses_outcomes": False,
        "final_test_used_for_tuning": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(empirical_replay_controls._SAFETY),
    }
    return {**body, "contract_digest": _value_digest(body)}


def _summary(
    mode: str,
    *,
    run_fingerprint: str,
    days: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    flattened = sorted({day for rows in days.values() for day in rows})
    counts = {partition: len(rows) for partition, rows in days.items()}
    return {
        "schema_id": "decision_radar.empirical_replay_execution",
        "schema_version": 1,
        "mode": mode,
        "run_fingerprint": run_fingerprint,
        "observation_count": len(flattened),
        "selected_partition_observation_count": len(flattened),
        "selected_partition_observed_day_count": len(flattened),
        "selected_partition_observed_day_count_by_partition": counts,
        "selected_partition_observed_day_basis": "exact_selected_observation_utc_days",
        "selected_partition_observation_start_at": flattened[0],
        "selected_partition_observation_end_at": flattened[-1],
        "idea_count": 0,
        "idea_observed_day_count": 0,
        "idea_count_per_selected_observed_day": 0.0,
        "route_counts": {},
        "episode_count": 0,
        "matured_episode_count_by_partition": {
            partition: 0 for partition in days
        },
        "historical_spread_observed": False,
        "intraday_validation_available": False,
        "residual_survivorship_present": True,
        "provider_calls": 0,
        "policy_mutations": 0,
        "dashboard_authority_mutations": 0,
        "research_only": True,
        "auto_apply": False,
    }


def _trace(
    mode: str,
    *,
    days: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    protocol = empirical_validation_protocol.protocol_values()
    flattened = sorted({day for rows in days.values() for day in rows})
    counts = {partition: len(rows) for partition, rows in days.items()}
    return {
        "schema_id": "decision_radar.empirical_replay_trace_summary",
        "schema_version": 1,
        "mode": mode,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "observation_count": len(flattened),
        "selected_partition_observation_count": len(flattened),
        "selected_partition_observed_day_count": len(flattened),
        "selected_partition_observed_day_count_by_partition": counts,
        "selected_partition_observed_days_sha256_by_partition": {
            partition: _days_digest(rows)
            for partition, rows in days.items()
        },
        "selected_partition_observed_days_sha256": _days_digest(
            tuple(flattened)
        ),
        "selected_partition_observed_day_basis": "exact_selected_observation_utc_days",
        "selected_partition_observation_start_at": flattened[0],
        "selected_partition_observation_end_at": flattened[-1],
        "idea_count": 0,
        "idea_observed_day_count": 0,
        "idea_count_per_selected_observed_day": 0.0,
        "route_counts": {},
        "partition_counts": {},
        "observation_counting_unit": "input_observation_rows",
        "idea_counting_unit": "canonical_idea_rows",
        "route_counting_unit": "canonical_idea_rows",
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
    }


def _review(
    *,
    run_fingerprint: str,
    observation_count: int,
    partition_count: int,
) -> dict[str, object]:
    protocol = empirical_validation_protocol.protocol_values()
    body: dict[str, object] = {
        "schema_id": empirical_review.SCHEMA_ID,
        "schema_version": empirical_review.SCHEMA_VERSION,
        "method": "deterministic_outcome_aware_targeted_review_v1",
        "run_fingerprint": run_fingerprint,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "item_count": 0,
        "maximum_item_count": empirical_review.MAX_QUEUE_ITEMS,
        "queue_truncated": False,
        "closed_category_taxonomy": True,
        "category_order": list(empirical_review.CATEGORY_ORDER),
        "categories": [],
        "items": [],
        "input_counts": {
            "observation_count": observation_count,
            "idea_count": 0,
            "episode_count": 0,
            "analysis_partition_count": partition_count,
        },
        "policy_eligible": False,
        "selection_uses_outcomes": True,
        "selection_changes_replay_results": False,
        "final_test_used_for_policy_selection": False,
        "causal_claim": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(empirical_review._ZERO_SAFETY),
    }
    return {**body, "queue_digest": _value_digest(body)}


def _archives() -> dict[str, bytes]:
    return empirical_replay_persistence.build_replay_persistence_archives(
        (),
        {"episodes": [], "episode_count": 0, "contract_digest": "d" * 64},
    ).artifacts


def _live_report() -> dict[str, object]:
    return {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "generated_at": "2026-07-16T00:00:00Z",
        "campaign_status": "observational",
        "campaign_metrics": {},
        "shadow_anomaly_episodes": {
            "statistical_independence_claim": False,
            "cross_asset_independence_claim": False,
        },
        "decision_v2_episode_outcome_scorecard": {},
        "outcomes": {},
        "data_quality_limitations": [],
        "safety": {
            "research_only": True,
            "normal_rsi_signal_rows_written": 0,
            "paper_trades_created": 0,
            "provider_calls_made_by_report": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "triggered_fade_created": 0,
            "provider_authorization_modified": False,
        },
    }


def _write_runs(
    tmp_path: Path,
    *,
    selection_mode: str = "full",
    final_input: str = _INPUT,
    final_code: str = _CODE,
    substitute_final_seal: bool = False,
    rewrite_both_seals: bool = False,
    selection_mutator: Callable[[dict[str, bytes]], None] | None = None,
    final_mutator: Callable[[dict[str, bytes]], None] | None = None,
) -> tuple[Path, Path]:
    protocol = empirical_validation_protocol.protocol_values()
    protocol_sha = empirical_validation_protocol.protocol_sha256(protocol)
    selection_config = {
        "mode": selection_mode,
        "data_mode": "full",
        "partitions": ["development", "validation"],
        "universe_top_n": 100,
        "research_only": True,
        "auto_apply": False,
    }
    selection_fingerprint = empirical_replay_store.run_fingerprint(
        protocol_sha256=protocol_sha,
        input_sha256=_INPUT,
        code_sha256=_CODE,
        configuration=selection_config,
    )
    simulation = empirical_policy_lab.simulate_shadow_policies(
        (), (),
        partitions=("development", "validation"),
        protocol=protocol,
        selected_observation_days_by_partition=_SELECTION_DAYS,
    )
    seal = empirical_policy_lab.freeze_recommendation_set(
        simulation,
        selection_run_binding={
            "selection_run_fingerprint": selection_fingerprint,
            "input_sha256": _INPUT,
            "code_sha256": _CODE,
            "configuration_sha256": hashlib.sha256(
                empirical_replay_store.canonical_json_bytes(selection_config)
            ).hexdigest(),
            "mode": selection_mode,
            "simulation_artifact": "shadow_policy_simulation.json",
        },
    )
    if rewrite_both_seals:
        seal = deepcopy(seal)
        seal["human_approval_required"] = False
        body = {key: value for key, value in seal.items() if key != "seal_sha256"}
        seal["seal_sha256"] = hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(body)
        ).hexdigest()
    walk = empirical_policy_lab.walk_forward_evaluation(
        (), (),
        protocol=protocol,
        selected_observation_days_by_partition=_SELECTION_DAYS,
    )
    selection_artifacts = {
        "execution_summary.json": empirical_replay_store.canonical_json_bytes(
            _summary(selection_mode, run_fingerprint=selection_fingerprint, days=_SELECTION_DAYS)
        ),
        "replay_analysis.json": empirical_replay_store.canonical_json_bytes(
            _analysis(_SELECTION_DAYS)
        ),
        "replay_controls.json": empirical_replay_store.canonical_json_bytes(
            _controls(observation_count=2)
        ),
        "targeted_review_queue.json": empirical_replay_store.canonical_json_bytes(
            _review(run_fingerprint=selection_fingerprint, observation_count=2, partition_count=2)
        ),
        "shadow_policy_simulation.json": empirical_replay_store.canonical_json_bytes(simulation),
        "recommendation_seal.json": empirical_replay_store.canonical_json_bytes(seal),
        "walk_forward.json": empirical_replay_store.canonical_json_bytes(walk),
        "replay_trace_summary.json": empirical_replay_store.canonical_json_bytes(
            _trace(selection_mode, days=_SELECTION_DAYS)
        ),
        **_archives(),
    }
    if selection_mutator is not None:
        selection_mutator(selection_artifacts)
    selection = empirical_replay_store.write_immutable_run(
        tmp_path / "selection-store",
        protocol_version=protocol["protocol_version"],
        protocol_sha256=protocol_sha,
        input_sha256=_INPUT,
        code_sha256=_CODE,
        configuration=selection_config,
        artifacts=selection_artifacts,
        metrics={"idea_count": 0, "episode_count": 0},
        safety=_safety(),
    )
    final_seal = seal
    if substitute_final_seal:
        final_seal = deepcopy(seal)
        final_seal["human_approval_required"] = not bool(
            final_seal["human_approval_required"]
        )
        body = {key: value for key, value in final_seal.items() if key != "seal_sha256"}
        final_seal["seal_sha256"] = hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(body)
        ).hexdigest()
    confirmation = empirical_policy_lab.evaluate_sealed_final_test(
        (), (),
        seal=final_seal,
        protocol=protocol,
        selected_observation_days_by_partition=_FINAL_DAYS,
    )
    final_config = {
        "mode": "final_test",
        "data_mode": "full",
        "partitions": ["final_test"],
        "universe_top_n": 100,
        "recommendation_seal_sha256": final_seal["seal_sha256"],
        "research_only": True,
        "auto_apply": False,
    }
    final_fingerprint = empirical_replay_store.run_fingerprint(
        protocol_sha256=protocol_sha,
        input_sha256=final_input,
        code_sha256=final_code,
        configuration=final_config,
    )
    final_artifacts = {
        "execution_summary.json": empirical_replay_store.canonical_json_bytes(
            _summary("final_test", run_fingerprint=final_fingerprint, days=_FINAL_DAYS)
        ),
        "replay_analysis.json": empirical_replay_store.canonical_json_bytes(
            _analysis(_FINAL_DAYS)
        ),
        "replay_controls.json": empirical_replay_store.canonical_json_bytes(
            _controls(observation_count=1)
        ),
        "targeted_review_queue.json": empirical_replay_store.canonical_json_bytes(
            _review(run_fingerprint=final_fingerprint, observation_count=1, partition_count=1)
        ),
        "recommendation_seal.json": empirical_replay_store.canonical_json_bytes(final_seal),
        "final_test_confirmation.json": empirical_replay_store.canonical_json_bytes(confirmation),
        "replay_trace_summary.json": empirical_replay_store.canonical_json_bytes(
            _trace("final_test", days=_FINAL_DAYS)
        ),
        **_archives(),
    }
    if final_mutator is not None:
        final_mutator(final_artifacts)
    final = empirical_replay_store.write_immutable_run(
        tmp_path / "final-store",
        protocol_version=protocol["protocol_version"],
        protocol_sha256=protocol_sha,
        input_sha256=final_input,
        code_sha256=final_code,
        configuration=final_config,
        artifacts=final_artifacts,
        metrics={"idea_count": 0, "episode_count": 0},
        safety=_safety(),
    )
    return selection.run_dir, final.run_dir


def test_builds_exact_closed_deterministic_seven_file_bundle(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    bundle_id, first = empirical_research_reports.build_report_bundle(
        selection_run=selection,
        final_test_run=final,
    )
    second_id, second = empirical_research_reports.build_report_bundle(
        selection_run=selection,
        final_test_run=final,
    )

    assert tuple(first) == empirical_research_reports.REPORT_FILENAMES
    assert first == second
    assert bundle_id == second_id
    validation = json.loads(first["DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json"])
    policy = json.loads(first["DECISION_RADAR_POLICY_SIMULATION_REPORT.json"])
    assert validation["bundle"]["bundle_id"] == bundle_id
    assert validation["bundle"]["selection_run"]["configuration_sha256"]
    assert validation["bundle"]["final_test_run"]["manifest_sha256"]
    assert set(validation["bundle"]["report_core_sha256"]) == {
        "empirical_validation",
        "walk_forward",
        "policy_simulation",
        "research_limitations",
    }
    assert validation["bundle"]["live_campaign_report"]["status"] == "not_provided"
    assert validation["conclusions"]["production_policy_unchanged"] is True
    assert set(validation["conclusions"]["route_findings"]) == set(
        empirical_research_reports._ROUTES
    )
    assert set(validation["conclusions"]["origin_findings"]) == {
        "market_led", "catalyst_led", "technical_led", "derivatives_led",
        "onchain_led", "fundamental_led", "macro_led",
    }
    assert validation["conclusions"]["origins_with_no_empirical_evidence"] == [
        origin
        for origin in empirical_research_reports._ORIGINS
        if validation["conclusions"]["origin_findings"][origin]["evidence_status"]
        == "no_empirical_evidence"
    ]
    validation_markdown = first["DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md"]
    limitations_markdown = first["DECISION_RADAR_RESEARCH_LIMITATIONS.md"]
    assert b"## Origin evidence" in validation_markdown
    assert b"Primary thesis origins:" in limitations_markdown
    assert b"`macro_led`" in limitations_markdown
    assert validation["conclusions"]["walk_forward_stability"][
        "outcome_evaluable_fold_count"
    ] == 0
    assert validation["conclusions"]["multiple_comparison_warnings"][
        "policy_simulation"
    ] == empirical_validation_protocol.protocol_values()["statistics"][
        "multiple_comparison_policy"
    ]
    assert policy["frozen_recommendation_seal"] == json.loads(
        (selection / "recommendation_seal.json").read_bytes()
    )
    assert policy["final_test_confirmation"] == json.loads(
        (final / "final_test_confirmation.json").read_bytes()
    )
    assert str(tmp_path).encode() not in b"".join(first.values())
    assert empirical_research_reports.validate_report_bundle(first)["bundle_id"] == bundle_id


def test_policy_chain_distinguishes_raw_idea_days_from_episode_active_days(
    tmp_path: Path,
) -> None:
    selection_path, _ = _write_runs(tmp_path)
    loaded = empirical_research_reports._load_run(
        selection_path,
        required=empirical_research_reports._SELECTION_ARTIFACTS,
    )
    values = deepcopy(loaded.values)
    values["replay_trace_summary.json"]["idea_observed_day_count"] = 1
    evidence = empirical_research_reports._RunEvidence(
        loaded.manifest,
        loaded.payloads,
        values,
        loaded.binding,
    )

    empirical_research_reports._validate_selection_policy_artifacts(
        evidence,
        values["shadow_policy_simulation.json"],
    )

    values["shadow_policy_simulation.json"]["idea_active_day_count"] = 1
    values["walk_forward.json"]["idea_active_day_count"] = 1
    with pytest.raises(ValueError, match="selection policy artifact mismatch"):
        empirical_research_reports._validate_selection_policy_artifacts(
            evidence,
            values["shadow_policy_simulation.json"],
        )


def test_confirmation_distinguishes_raw_idea_days_from_episode_active_days(
    tmp_path: Path,
) -> None:
    selection_path, final_path = _write_runs(tmp_path)
    selection = empirical_research_reports._load_run(
        selection_path,
        required=empirical_research_reports._SELECTION_ARTIFACTS,
    )
    final = empirical_research_reports._load_run(
        final_path,
        required=empirical_research_reports._FINAL_ARTIFACTS,
    )
    values = deepcopy(final.values)
    values["replay_trace_summary.json"]["idea_observed_day_count"] = 1
    evidence = empirical_research_reports._RunEvidence(
        final.manifest,
        final.payloads,
        values,
        final.binding,
    )
    seal = selection.values["recommendation_seal.json"]

    empirical_research_reports._validate_confirmation(
        values["final_test_confirmation.json"],
        seal,
        selection,
        evidence,
    )

    values["final_test_confirmation.json"]["idea_active_day_count"] = 1
    with pytest.raises(ValueError, match="final confirmation binding invalid"):
        empirical_research_reports._validate_confirmation(
            values["final_test_confirmation.json"],
            seal,
            selection,
            evidence,
        )


def test_validator_rejects_core_tamper_envelope_splice_and_markdown_drift(
    tmp_path: Path,
) -> None:
    selection, final = _write_runs(tmp_path)
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection,
        final_test_run=final,
    )

    changed = dict(payloads)
    validation = json.loads(changed[empirical_research_reports.REPORT_FILENAMES[1]])
    validation["conclusions"]["production_policy_unchanged"] = False
    changed[empirical_research_reports.REPORT_FILENAMES[1]] = (
        empirical_replay_store.canonical_json_bytes(validation)
    )
    with pytest.raises(RuntimeError, match="conclusions_invalid|core_digest_invalid"):
        empirical_research_reports.validate_report_bundle(changed)

    live = tmp_path / "live.json"
    live.write_text(json.dumps(_live_report(), indent=2) + "\n", encoding="utf-8")
    _other_id, other = empirical_research_reports.build_report_bundle(
        selection_run=selection,
        final_test_run=final,
        live_campaign_report=live,
    )
    spliced = dict(payloads)
    policy = json.loads(spliced[empirical_research_reports.REPORT_FILENAMES[5]])
    policy["bundle"] = json.loads(other[empirical_research_reports.REPORT_FILENAMES[5]])["bundle"]
    spliced[empirical_research_reports.REPORT_FILENAMES[5]] = (
        empirical_replay_store.canonical_json_bytes(policy)
    )
    with pytest.raises(RuntimeError, match="envelope_splice"):
        empirical_research_reports.validate_report_bundle(spliced)

    markdown_drift = dict(payloads)
    markdown_drift[empirical_research_reports.REPORT_FILENAMES[6]] += b"tampered\n"
    with pytest.raises(RuntimeError, match="render_drift"):
        empirical_research_reports.validate_report_bundle(markdown_drift)


def test_atomic_write_and_check_mode_byte_compare(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    output = tmp_path / "research"
    written = empirical_research_reports.write_report_bundle(
        selection_run=selection,
        final_test_run=final,
        live_campaign_report=None,
        output_dir=output,
    )
    checked = empirical_research_reports.write_report_bundle(
        selection_run=selection,
        final_test_run=final,
        live_campaign_report=None,
        output_dir=output,
        check=True,
    )
    assert written.bundle_id == checked.bundle_id
    assert checked.checked is True

    changed = output / empirical_research_reports.REPORT_FILENAMES[0]
    changed.write_bytes(changed.read_bytes() + b"drift\n")
    with pytest.raises(RuntimeError, match="check_failed"):
        empirical_research_reports.write_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=None,
            output_dir=output,
            check=True,
        )


def test_atomic_failure_preserves_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, final = _write_runs(tmp_path)
    output = tmp_path / "research"
    empirical_research_reports.write_report_bundle(
        selection_run=selection,
        final_test_run=final,
        live_campaign_report=None,
        output_dir=output,
    )
    before = {name: (output / name).read_bytes() for name in empirical_research_reports.REPORT_FILENAMES}
    live = tmp_path / "live.json"
    live.write_bytes(empirical_replay_store.canonical_json_bytes(_live_report()))

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected atomic failure")

    monkeypatch.setattr(
        empirical_research_reports.market_anomaly_receipt,
        "write_artifacts_atomic",
        fail,
    )
    with pytest.raises(RuntimeError, match="injected"):
        empirical_research_reports.write_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=live,
            output_dir=output,
        )
    assert before == {name: (output / name).read_bytes() for name in empirical_research_reports.REPORT_FILENAMES}


def test_rejects_medium_selection_before_reporting(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path, selection_mode="medium")
    with pytest.raises(ValueError, match="must be full top100"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"final_input": "a" * 64}, "input digest mismatch"),
        ({"final_code": "a" * 64}, "code digest mismatch"),
        ({"substitute_final_seal": True}, "seal substitution"),
    ],
)
def test_rejects_final_binding_or_seal_substitution(
    tmp_path: Path, kwargs: dict[str, object], match: str
) -> None:
    selection, final = _write_runs(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=match):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
        )


def test_rejects_immutable_digest_drift(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    artifact = selection / "execution_summary.json"
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(RuntimeError, match="manifest_invalid"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
        )


def test_rejects_symlinked_run_live_and_output_paths(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    selection_link = tmp_path / "selection-link"
    selection_link.symlink_to(selection, target_is_directory=True)
    with pytest.raises(RuntimeError, match="path_unsafe"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection_link,
            final_test_run=final,
        )

    live = tmp_path / "live.json"
    live.write_bytes(empirical_replay_store.canonical_json_bytes(_live_report()))
    live_link = tmp_path / "live-link.json"
    live_link.symlink_to(live)
    with pytest.raises(RuntimeError, match="path_unsafe"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=live_link,
        )

    real_output = tmp_path / "real-output"
    real_output.mkdir()
    output_link = tmp_path / "output-link"
    output_link.symlink_to(real_output, target_is_directory=True)
    with pytest.raises(RuntimeError, match="output_path_unsafe"):
        empirical_research_reports.write_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=None,
            output_dir=output_link,
        )


def test_live_report_parent_replacement_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, final = _write_runs(tmp_path)
    live_dir = tmp_path / "live-parent"
    live_dir.mkdir()
    live = live_dir / "campaign.json"
    live.write_text(json.dumps(_live_report(), indent=2) + "\n", encoding="utf-8")
    replacement = tmp_path / "replacement-parent"
    replacement.mkdir()
    (replacement / "campaign.json").write_text(
        json.dumps(_live_report(), indent=2) + "\n", encoding="utf-8"
    )
    original = empirical_research_reports._open_directory_fd
    replaced = False

    def replace_after_open(directory: Path):
        nonlocal replaced
        descriptor = original(directory)
        if Path(directory) == live_dir and not replaced:
            replaced = True
            live_dir.rename(tmp_path / "old-live-parent")
            replacement.rename(live_dir)
        return descriptor

    monkeypatch.setattr(
        empirical_research_reports,
        "_open_directory_fd",
        replace_after_open,
    )
    with pytest.raises(RuntimeError, match="identity_drift"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=live,
        )


@pytest.mark.parametrize("duplicate_count", [1, 2])
def test_rejects_extra_or_duplicate_final_confirmation_rows(
    tmp_path: Path, duplicate_count: int
) -> None:
    def forge(artifacts: dict[str, bytes]) -> None:
        value = json.loads(artifacts["final_test_confirmation.json"])
        value["confirmations"] = [
            {"scenario": "forged", "confirmation_status": "confirmed"}
            for _ in range(duplicate_count)
        ]
        artifacts["final_test_confirmation.json"] = (
            empirical_replay_store.canonical_json_bytes(value)
        )

    selection, final = _write_runs(tmp_path, final_mutator=forge)
    with pytest.raises(ValueError, match="confirmation"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_validly_rehashed_but_nonproducer_seal(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path, rewrite_both_seals=True)
    with pytest.raises(ValueError, match="seal producer mismatch"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_cross_artifact_safety_contradiction(tmp_path: Path) -> None:
    def contradict(artifacts: dict[str, bytes]) -> None:
        value = json.loads(artifacts["replay_controls.json"])
        value["safety"]["trades"] = 1
        body = {key: item for key, item in value.items() if key != "contract_digest"}
        value["contract_digest"] = _value_digest(body)
        artifacts["replay_controls.json"] = empirical_replay_store.canonical_json_bytes(value)

    selection, final = _write_runs(tmp_path, selection_mutator=contradict)
    with pytest.raises(ValueError, match="controls or review semantic mismatch"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_partition_count_contradiction(tmp_path: Path) -> None:
    def contradict(artifacts: dict[str, bytes]) -> None:
        value = json.loads(artifacts["replay_trace_summary.json"])
        value["partition_counts"] = {"development": 1}
        artifacts["replay_trace_summary.json"] = empirical_replay_store.canonical_json_bytes(value)

    selection, final = _write_runs(tmp_path, selection_mutator=contradict)
    with pytest.raises(ValueError, match="trace taxonomy or denominator"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_selected_observation_day_digest_contradiction(
    tmp_path: Path,
) -> None:
    def contradict(artifacts: dict[str, bytes]) -> None:
        value = json.loads(artifacts["replay_trace_summary.json"])
        value["selected_partition_observed_days_sha256"] = "a" * 64
        artifacts["replay_trace_summary.json"] = empirical_replay_store.canonical_json_bytes(value)

    selection, final = _write_runs(tmp_path, selection_mutator=contradict)
    with pytest.raises(ValueError, match="selection policy artifact mismatch"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_oversized_run_leaf_before_manifest_load(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    with (selection / "unmanifested.bin").open("wb") as handle:
        handle.truncate(empirical_replay_store.MAX_ARTIFACT_BYTES + 1)
    with pytest.raises(RuntimeError, match="run_artifact_too_large"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection, final_test_run=final
        )


def test_rejects_invalid_live_campaign_schema(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    live = _live_report()
    live["schema_id"] = "forged.live.campaign"
    path = tmp_path / "live.json"
    path.write_bytes(empirical_replay_store.canonical_json_bytes(live))
    with pytest.raises(ValueError, match="live campaign report invalid"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=path,
        )


def test_rejects_oversized_live_campaign_before_read(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    path = tmp_path / "live.json"
    with path.open("wb") as handle:
        handle.truncate(empirical_research_reports.MAX_LIVE_REPORT_BYTES + 1)
    with pytest.raises(RuntimeError, match="input_too_large"):
        empirical_research_reports.build_report_bundle(
            selection_run=selection,
            final_test_run=final,
            live_campaign_report=path,
        )


def test_binds_valid_live_campaign_as_separate_canonical_projection(
    tmp_path: Path,
) -> None:
    selection, final = _write_runs(tmp_path)
    path = tmp_path / "live.json"
    path.write_text(json.dumps(_live_report(), indent=2) + "\n", encoding="utf-8")
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection,
        final_test_run=final,
        live_campaign_report=path,
    )
    validation = json.loads(payloads[empirical_research_reports.REPORT_FILENAMES[1]])
    binding = validation["bundle"]["live_campaign_report"]
    assert binding["status"] == "provided_separate_observational_lane"
    assert binding["canonical_projection"]["schema_id"] == (
        "decision_radar.empirical_live_campaign_projection"
    )
    assert binding["evidence_pooled_with_replay"] is False


def test_rejects_boolean_live_projection_schema_version() -> None:
    projection = empirical_live_campaign.project_live_campaign(_live_report())
    projection["schema_version"] = True
    binding = {
        "status": "provided_separate_observational_lane",
        "canonical_projection": projection,
        "canonical_projection_sha256": hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(projection)
        ).hexdigest(),
        "evidence_pooled_with_replay": False,
    }

    with pytest.raises(
        RuntimeError, match="empirical_research_report_live_binding_invalid"
    ):
        empirical_research_report_validation._validate_published_live(binding)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        (
            "shadow_temporal_surprise",
            "statistical_independence_claimed",
            True,
        ),
        (
            "human_review",
            "dashboard_reads_recorded_as_human_actions",
            True,
        ),
    ),
)
def test_rejects_resigned_live_campaign_v3_evidence_drift(
    section: str, field: str, value: object
) -> None:
    projection = empirical_live_campaign.project_live_campaign(_live_report())
    projection[section][field] = value
    binding = {
        "status": "provided_separate_observational_lane",
        "canonical_projection": projection,
        "canonical_projection_sha256": hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(projection)
        ).hexdigest(),
        "evidence_pooled_with_replay": False,
    }

    with pytest.raises(
        RuntimeError, match="empirical_research_report_live_binding_invalid"
    ):
        empirical_research_report_validation._validate_published_live(binding)


def _resign_publication_bundle(
    payloads: dict[str, bytes],
    mutate: Callable[
        [dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], None
    ],
) -> dict[str, bytes]:
    validation = json.loads(payloads[empirical_research_reports.REPORT_FILENAMES[1]])
    walk = json.loads(payloads[empirical_research_reports.REPORT_FILENAMES[3]])
    policy = json.loads(payloads[empirical_research_reports.REPORT_FILENAMES[5]])
    envelope = dict(validation.pop("bundle"))
    walk.pop("bundle")
    policy.pop("bundle")
    envelope.pop("bundle_id")
    mutate(validation, walk, policy, envelope)
    limitations = empirical_research_reports._limitations_core(validation)
    envelope["report_core_sha256"] = empirical_research_reports._report_core_sha256(
        validation, walk, policy, limitations
    )
    envelope["bundle_id"] = hashlib.sha256(
        empirical_replay_store.canonical_json_bytes(envelope)
    ).hexdigest()
    validation["bundle"] = dict(envelope)
    walk["bundle"] = dict(envelope)
    policy["bundle"] = dict(envelope)
    return empirical_research_reports._render_payloads(
        validation, walk, policy, limitations, envelope
    )


def test_validator_rejects_resigned_production_contract_contradiction(
    tmp_path: Path,
) -> None:
    selection, final = _write_runs(tmp_path)
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection, final_test_run=final
    )

    def forge(_validation, _walk, _policy, envelope):
        envelope["production_contract"]["routes_changed"] = True

    forged = _resign_publication_bundle(payloads, forge)
    with pytest.raises(RuntimeError, match="publication_contract_invalid"):
        empirical_research_reports.validate_report_bundle(forged)


def test_validator_rejects_resigned_no_evidence_origin_drift(
    tmp_path: Path,
) -> None:
    selection, final = _write_runs(tmp_path)
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection, final_test_run=final
    )

    def forge(validation, _walk, _policy, _envelope):
        validation["conclusions"]["origins_with_no_empirical_evidence"] = []

    forged = _resign_publication_bundle(payloads, forge)
    with pytest.raises(RuntimeError, match="conclusions_invalid"):
        empirical_research_reports.validate_report_bundle(forged)


def test_validator_rejects_resigned_nonproducer_seal(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection, final_test_run=final
    )

    def forge(_validation, _walk, policy, envelope):
        seal = policy["frozen_recommendation_seal"]
        seal["human_approval_required"] = False
        body = {key: item for key, item in seal.items() if key != "seal_sha256"}
        seal["seal_sha256"] = hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(body)
        ).hexdigest()
        envelope["recommendation_seal_sha256"] = seal["seal_sha256"]

    forged = _resign_publication_bundle(payloads, forge)
    with pytest.raises(RuntimeError, match="seal_invalid"):
        empirical_research_reports.validate_report_bundle(forged)


def test_validator_rejects_resigned_duplicate_confirmation(tmp_path: Path) -> None:
    selection, final = _write_runs(tmp_path)
    _bundle_id, payloads = empirical_research_reports.build_report_bundle(
        selection_run=selection, final_test_run=final
    )

    def forge(validation, walk, policy, envelope):
        confirmation = policy["final_test_confirmation"]
        confirmation["confirmations"] = [
            {"scenario": "forged", "confirmation_status": "confirmed"},
            {"scenario": "forged", "confirmation_status": "confirmed"},
        ]
        validation["final_confirmation"] = deepcopy(confirmation)
        walk["final_confirmation"] = deepcopy(confirmation)
        envelope["final_confirmation_sha256"] = hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(confirmation)
        ).hexdigest()

    forged = _resign_publication_bundle(payloads, forge)
    with pytest.raises(RuntimeError, match="confirmation_invalid"):
        empirical_research_reports.validate_report_bundle(forged)
