from __future__ import annotations

import socket
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations.empirical_replay_analysis import (
    ROUTES,
    build_empirical_replay_analysis_from_episodes,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_core import (
    run_replay_kernel,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_data import (
    build_replay_catalog,
    iter_point_in_time_observations,
    load_fixture_dataset,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_outcomes import (
    build_empirical_replay_outcomes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_fixture_replay_closes_data_decision_episode_outcome_and_analysis(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("empirical fixture replay attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    authority_sentinel = tmp_path / "production-pointer.json"
    authority_sentinel.write_bytes(b'{"revision":99}\n')
    authority_before = authority_sentinel.read_bytes()

    dataset = load_fixture_dataset(PROJECT_ROOT / "fixtures" / "backtest_smoke" / "klines")
    catalog = build_replay_catalog(dataset)
    observations = list(iter_point_in_time_observations(dataset))
    replay = run_replay_kernel(
        observations,
        mode="fixture",
        artifact_namespace="empirical-fixture-integration",
        allowed_partitions=("fixture",),
    )
    outcomes = build_empirical_replay_outcomes(
        replay.ideas,
        dataset.frames(),
        evaluated_at="2026-06-20T00:00:00Z",
    )
    analysis = build_empirical_replay_analysis_from_episodes(
        outcomes,
        partition="fixture",
        evidence_mode="fixture_mechanics_only",
        bootstrap_resamples=10,
    )

    assert catalog["source_kind"] == "checked_daily_smoke_fixture"
    assert catalog["provider_calls"] == 0
    assert replay.ideas
    assert outcomes["episode_count"] > 0
    assert outcomes["episode_count"] <= len(replay.ideas)
    assert analysis["episode_count"] == outcomes["episode_count"]
    assert [row["cohort"] for row in analysis["route_cohorts"]] == list(ROUTES)
    assert any(row["sample_size"] > 0 for row in analysis["route_cohorts"])
    assert analysis["policy_eligible"] is False
    assert analysis["auto_apply"] is False
    assert replay.trace_summary["provider_calls"] == 0
    assert replay.trace_summary["dashboard_authority_mutations"] == 0
    assert outcomes["safety"]["writes"] == 0
    assert authority_sentinel.read_bytes() == authority_before
