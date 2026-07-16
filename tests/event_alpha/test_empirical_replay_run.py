from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_policy_lab,
    empirical_replay_persistence,
    empirical_replay_run,
    empirical_replay_store,
    empirical_validation_protocol,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_run import execute_empirical_replay
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_store import (
    MAX_ARTIFACT_BYTES,
    MAX_BUNDLE_BYTES,
    load_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "fixtures" / "backtest_smoke" / "klines"


def _zero_safety() -> dict[str, object]:
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


def _write_bound_selection_run(tmp_path: Path, *, mode: str = "full") -> Path:
    protocol = empirical_validation_protocol.protocol_values()
    protocol_sha256 = empirical_validation_protocol.protocol_sha256(protocol)
    input_sha256 = "b" * 64
    code_sha256 = empirical_replay_store.code_fingerprint(
        empirical_replay_run._code_paths()
    )
    configuration = {
        "mode": mode,
        "partitions": ["development", "validation"],
        "universe_top_n": 100,
        "research_only": True,
        "auto_apply": False,
    }
    run_fingerprint = empirical_replay_store.run_fingerprint(
        protocol_sha256=protocol_sha256,
        input_sha256=input_sha256,
        code_sha256=code_sha256,
        configuration=configuration,
    )
    simulation = empirical_policy_lab.simulate_shadow_policies(
        (),
        (),
        partitions=("development", "validation"),
        protocol=protocol,
        selected_observation_days_by_partition={
            "development": {"2022-06-01"},
            "validation": {"2024-06-01"},
        },
    )
    seal = empirical_policy_lab.freeze_recommendation_set(
        simulation,
        selection_run_binding={
            "selection_run_fingerprint": run_fingerprint,
            "input_sha256": input_sha256,
            "code_sha256": code_sha256,
            "configuration_sha256": hashlib.sha256(
                empirical_replay_store.canonical_json_bytes(configuration)
            ).hexdigest(),
            "mode": mode,
            "simulation_artifact": "shadow_policy_simulation.json",
        },
    )
    stored = empirical_replay_store.write_immutable_run(
        tmp_path / "selection",
        protocol_version=protocol["protocol_version"],
        protocol_sha256=protocol_sha256,
        input_sha256=input_sha256,
        code_sha256=code_sha256,
        configuration=configuration,
        artifacts={
            "shadow_policy_simulation.json": empirical_replay_store.canonical_json_bytes(
                simulation
            ),
            "recommendation_seal.json": empirical_replay_store.canonical_json_bytes(
                seal
            ),
        },
        metrics={"idea_count": 0},
        safety=_zero_safety(),
    )
    return stored.run_dir / "recommendation_seal.json"


def test_fixture_execution_is_immutable_resumable_bounded_and_authority_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("empirical replay runner attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    pointer = tmp_path / "radar_current_namespace.json"
    pointer.write_bytes(b'{"revision":123}\n')
    before = pointer.read_bytes()
    output = tmp_path / "research-lab"

    first = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=output,
    )
    second = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=output,
    )

    assert first.resumed is False
    assert second.resumed is True
    assert first.run_fingerprint == second.run_fingerprint
    assert first.run_dir == second.run_dir
    assert first.summary["idea_count"] > 0
    assert first.summary["episode_count"] > 0
    assert first.summary["input_data_window_semantics"] == "completed_daily_bar_cache_window_inclusive"
    assert first.summary["observation_counting_unit"] == "input_observation_rows"
    assert first.summary["selected_partition_observation_count"] == first.summary["observation_count"]
    assert first.summary["selected_partition_observed_day_count"] > 0
    assert first.summary["selected_partition_observation_start_at"]
    assert first.summary["selected_partition_observation_end_at"]
    assert first.summary["candidate_pool_symbol_count"] == first.summary[
        "selected_symbol_count"
    ]
    assert first.summary["selected_symbol_count_semantics"] == (
        "legacy_alias_candidate_pool_symbol_count"
    )
    assert first.summary["point_in_time_universe_top_n"] == 3
    assert first.summary["idea_counting_unit"] == "canonical_idea_rows"
    assert first.summary["route_counting_unit"] == "canonical_idea_rows"
    assert first.summary["idea_observed_day_count"] > 0
    assert first.summary["idea_count_per_selected_observed_day"] > 0
    assert first.summary["matched_control_count"] >= 0
    assert first.summary["missed_endpoint_candidate_count"] >= 0
    assert sum(first.summary["benchmark_status_counts"].values()) == 8
    assert first.summary["evidence_strength_by_partition"]["fixture"] == "descriptive_only"
    assert first.summary["provider_calls"] == 0
    assert first.summary["dashboard_authority_mutations"] == 0
    assert pointer.read_bytes() == before
    assert not (output / "latest.json").exists()
    assert not (output / "radar_current_namespace.json").exists()
    manifest = load_manifest(first.run_dir)
    assert manifest["safety"]["provider_calls"] == 0
    assert manifest["safety"]["dashboard_authority_mutations"] == 0
    assert manifest["metrics"]["idea_count"] == first.summary["idea_count"]
    assert "replay_controls.json" in manifest["artifacts"]
    assert "targeted_review_queue.json" in manifest["artifacts"]
    assert manifest["artifacts"]["replay_trace_examples.jsonl"]["size_bytes"] > 0
    assert empirical_replay_persistence.IDEA_INDEX_FILENAME in manifest["artifacts"]
    assert empirical_replay_persistence.EPISODE_INDEX_FILENAME in manifest["artifacts"]
    assert "replay_ideas.jsonl" not in manifest["artifacts"]
    assert "replay_episode_outcomes.json" not in manifest["artifacts"]
    assert manifest["configuration"]["persistence_schema_version"] == 1
    assert manifest["configuration"]["artifact_shard_target_bytes"] == 8 * 1024 * 1024
    assert "empirical_replay_persistence.py" in empirical_replay_run._code_paths()
    assert "empirical_review.py" in empirical_replay_run._code_paths()
    review_queue = json.loads(
        (first.run_dir / "targeted_review_queue.json").read_text(encoding="utf-8")
    )
    assert review_queue["research_only"] is True
    assert review_queue["auto_apply"] is False
    assert manifest["metrics"]["targeted_review_item_count"] == review_queue["item_count"]
    payloads = {
        name: (first.run_dir / name).read_bytes()
        for name in manifest["artifacts"]
    }
    ideas = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.IDEA_INDEX_FILENAME,
        payloads,
    )
    episodes = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.EPISODE_INDEX_FILENAME,
        payloads,
    )
    assert len(ideas) == manifest["metrics"]["idea_count"]
    assert len(episodes) == manifest["metrics"]["episode_count"]
    assert all(row["decision_projection"]["research_only"] is True for row in ideas)
    assert max(row["size_bytes"] for row in manifest["artifacts"].values()) <= MAX_ARTIFACT_BYTES
    assert sum(row["size_bytes"] for row in manifest["artifacts"].values()) <= MAX_BUNDLE_BYTES
    analysis = json.loads(
        (first.run_dir / "replay_analysis.json").read_text(encoding="utf-8")
    )
    trace_summary = json.loads(
        (first.run_dir / "replay_trace_summary.json").read_text(encoding="utf-8")
    )
    burden = analysis["partitions"]["fixture"]["operator_burden"]
    assert burden["observed_day_count"] == first.summary[
        "selected_partition_observed_day_count"
    ]
    assert burden["observed_day_denominator"]["basis"] == (
        "exact_selected_observation_utc_days"
    )
    assert trace_summary["selected_partition_observed_days_sha256"] == (
        burden["observed_day_denominator"]["days_sha256"]
    )
    markdown = (first.run_dir / "execution_summary.md").read_text(
        encoding="utf-8"
    )
    assert "Candidate-pool inputs:" in markdown
    assert "Point-in-time universe: top 3 assets per observation" in markdown


def test_execution_summary_separates_candidate_pool_from_point_in_time_top_n() -> None:
    summary = empirical_replay_run._execution_summary(
        run_mode="medium",
        fingerprint="f" * 64,
        catalog={
            "data_start_at": "2021-01-01T00:00:00Z",
            "data_end_at": "2025-01-01T00:00:00Z",
            "selected_symbol_count": 419,
            "row_count": 10_000,
            "partial_bar_count": 0,
            "residual_survivorship_present": True,
        },
        configuration={"universe_top_n": 100},
        trace_summary={
            "observation_count": 1_000,
            "observation_counting_unit": "input_observation_rows",
            "selected_partition_observation_count": 1_000,
            "selected_partition_observed_day_count": 100,
            "selected_partition_observed_day_count_by_partition": {
                "development": 100
            },
            "selected_partition_observed_day_basis": (
                "exact_selected_observation_utc_days"
            ),
            "selected_partition_observation_start_at": "2021-01-01T00:00:00Z",
            "selected_partition_observation_end_at": "2021-04-10T00:00:00Z",
            "idea_count": 4,
            "idea_counting_unit": "canonical_idea_rows",
            "idea_observed_day_count": 3,
            "idea_count_per_selected_observed_day": 0.04,
            "route_counts": {"dashboard_watch": 4},
            "route_counting_unit": "canonical_idea_rows",
        },
        outcomes={"episode_count": 4, "dependent_repeat_count": 0},
        analyses={
            "development": {"matured_episode_count": 4, "route_cohorts": []}
        },
        controls={
            "matched_non_signal_controls": {
                "selected_control_count": 0,
                "unavailable_control_count": 0,
            },
            "missed_move_evaluation": {
                "missed_opportunity_count": 0,
                "endpoint_candidate_count": 0,
            },
            "benchmark_rows": [],
        },
        runtime={"total_seconds": 1.0, "bottleneck_stage": "decision_replay"},
    )

    assert summary["candidate_pool_symbol_count"] == 419
    assert summary["point_in_time_universe_top_n"] == 100
    assert summary["selected_symbol_count"] == 419
    assert summary["selected_symbol_count_semantics"] == (
        "legacy_alias_candidate_pool_symbol_count"
    )
    markdown = empirical_replay_run._summary_markdown(summary)
    assert "Candidate-pool inputs: 419 cached symbols" in markdown
    assert "Point-in-time universe: top 100 assets per observation" in markdown


def test_existing_run_artifact_drift_fails_closed(tmp_path: Path) -> None:
    first = execute_empirical_replay(
        mode="fixture-smoke",
        input_dir=FIXTURES,
        output_root=tmp_path / "lab",
    )
    manifest = load_manifest(first.run_dir)
    idea_part = next(
        name
        for name in manifest["artifacts"]
        if name.startswith(empirical_replay_persistence.IDEA_PART_PREFIX)
    )
    (first.run_dir / idea_part).write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="manifest_invalid"):
        execute_empirical_replay(
            mode="fixture-smoke",
            input_dir=FIXTURES,
            output_root=tmp_path / "lab",
        )


def test_final_test_requires_valid_preexisting_seal_before_input_access(tmp_path: Path) -> None:
    missing_input = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="requires a recommendation seal"):
        execute_empirical_replay(
            mode="final-test",
            input_dir=missing_input,
            output_root=tmp_path / "lab",
        )

    fake_seal = tmp_path / "recommendation_seal.json"
    fake_seal.write_text("{}\n")
    with pytest.raises(ValueError, match="recommendation seal unreadable"):
        execute_empirical_replay(
            mode="final-test",
            input_dir=missing_input,
            output_root=tmp_path / "lab",
            recommendation_seal_path=fake_seal,
        )


def test_final_test_accepts_only_exact_full_selection_bundle(tmp_path: Path) -> None:
    seal_path = _write_bound_selection_run(tmp_path)
    loaded = empirical_replay_run._load_recommendation_seal(seal_path)
    assert loaded["selection_run_binding"]["mode"] == "full"

    selection_manifest = load_manifest(seal_path.parent)
    simulation_path = seal_path.parent / "shadow_policy_simulation.json"
    original = simulation_path.read_bytes()
    simulation_path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="recommendation seal unreadable"):
        empirical_replay_run._load_recommendation_seal(seal_path)
    simulation_path.write_bytes(original)
    assert load_manifest(seal_path.parent) == selection_manifest

    medium_seal_path = _write_bound_selection_run(tmp_path / "medium", mode="medium")
    with pytest.raises(ValueError, match="selection run binding invalid"):
        empirical_replay_run._load_recommendation_seal(medium_seal_path)


def test_replay_fingerprint_covers_behavior_bearing_dependency_closure() -> None:
    paths = empirical_replay_run._code_paths()
    expected = {
        "empirical_replay_observations.py",
        "empirical_replay_data_bar.py",
        "empirical_replay_data_dataset.py",
        "empirical_replay_data_mode.py",
        "empirical_replay_statistics.py",
        "empirical_replay_dimensions.py",
        "empirical_operator_burden.py",
        "empirical_replay_persistence.py",
        "empirical_replay_benchmark_metrics.py",
        "empirical_missed_attribution.py",
        "empirical_review.py",
        "decision_policy.py",
        "decision_projection_schema.py",
        "market_units.py",
        "rsi_technical_context.py",
        "config.py",
        "state_features.py",
        "indicators.py",
        "signal_registry.py",
    }
    assert expected <= set(paths)
    assert all(path.is_file() and not path.is_symlink() for path in paths.values())


def test_non_final_mode_rejects_seal_before_input_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="only for final_test"):
        execute_empirical_replay(
            mode="medium",
            input_dir=tmp_path / "does-not-exist",
            output_root=tmp_path / "lab",
            recommendation_seal_path=tmp_path / "unused.json",
        )
