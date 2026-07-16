from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_policy_lab import (
    evaluate_sealed_final_test,
    freeze_recommendation_set,
    simulate_shadow_policies,
    validate_recommendation_seal,
    walk_forward_evaluation,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_core import run_replay_kernel


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _selection_binding(*, mode: str = "full") -> dict[str, str]:
    return {
        "selection_run_fingerprint": _A,
        "input_sha256": _B,
        "code_sha256": _C,
        "configuration_sha256": _D,
        "mode": mode,
        "simulation_artifact": "shadow_policy_simulation.json",
    }


def _idea(
    at: str,
    *,
    partition: str,
    symbol: str = "MOVE",
    episode_id: str | None = None,
    volume_zscore: float = 3.0,
):
    observation = {
        "symbol": symbol,
        "canonical_asset_id": symbol.casefold(),
        "observed_at": at,
        "close": 12.0,
        "quote_volume": 20_000_000.0,
        "return_24h": 30.0,
        "return_72h": 35.0,
        "return_7d": 45.0,
        "relative_return_vs_btc_24h": 28.0,
        "relative_return_vs_eth_24h": 25.0,
        "volume_zscore_24h": volume_zscore,
        "liquidity_usd": 20_000_000.0,
        "liquidity_tier": "large",
        "market_regime": "bull",
        "point_in_time_universe_member": True,
        "point_in_time_volume_rank": 4,
        "baseline_status": "warm",
        "data_quality_mode": "historical_ohlcv",
        "market_data_source": "binance_historical_ohlcv",
    }
    mode = "final_test" if partition == "final_test" else "medium"
    idea = dict(run_replay_kernel(
        [observation], mode=mode, artifact_namespace="policy-test", allowed_partitions=(partition,)
    ).ideas[0])
    if episode_id:
        idea["episode_id"] = episode_id
    return idea


def _outcome(idea, value=0.10):
    return {
        "candidate_id": idea["candidate_id"],
        "outcome_status": "matured",
        "primary_return_fraction": value,
    }


def test_shadow_policy_uses_episode_representatives_and_never_auto_applies() -> None:
    first = _idea("2024-06-01T00:00:00Z", partition="validation", episode_id="episode-1")
    repeat = deepcopy(first)
    repeat["candidate_id"] = "repeat"
    result = simulate_shadow_policies(
        [first, repeat], [_outcome(first)], partitions=("validation",)
    )

    assert result["episode_representatives"] == 1
    assert len(result["scenarios"]) == 10
    assert result["auto_apply"] is False
    assert result["production_policy_mutations"] == 0
    assert all(row["research_only"] and not row["auto_apply"] for row in result["scenarios"])


def test_recommendation_seal_excludes_final_test_and_is_tamper_evident() -> None:
    development = _idea("2022-06-01T00:00:00Z", partition="development")
    validation = _idea("2024-06-01T00:00:00Z", partition="validation")
    simulation = simulate_shadow_policies(
        [development, validation],
        [_outcome(development), _outcome(validation)],
        partitions=("development", "validation"),
    )
    seal = freeze_recommendation_set(
        simulation,
        selection_run_binding=_selection_binding(),
    )
    assert validate_recommendation_seal(seal) == []
    assert seal["final_test_used_for_selection"] is False

    changed = deepcopy(seal)
    changed["recommendations"][0]["status"] = "candidate"
    assert "seal_digest_invalid" in validate_recommendation_seal(changed)

    changed_scenario = deepcopy(seal)
    changed_scenario["frozen_scenarios"][0]["changes"] = {"invented": True}
    changed_scenario_body = {
        key: value for key, value in changed_scenario.items() if key != "seal_sha256"
    }
    # Re-hashing the outer document cannot make a changed scenario definition
    # match the frozen protocol or its independently closed scenario-set digest.
    import hashlib
    import json

    changed_scenario["seal_sha256"] = hashlib.sha256(
        (
            json.dumps(
                changed_scenario_body,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    ).hexdigest()
    assert "scenario_definitions_invalid" in validate_recommendation_seal(
        changed_scenario
    )

    final = _idea("2025-06-01T00:00:00Z", partition="final_test")
    final_result = evaluate_sealed_final_test([final], [_outcome(final)], seal=seal)
    assert final_result["scenario_selection_performed"] is False
    assert final_result["partition"] == "final_test"

    final_simulation = simulate_shadow_policies([final], [_outcome(final)], partitions=("final_test",))
    with pytest.raises(ValueError, match="development and validation only"):
        freeze_recommendation_set(
            final_simulation,
            selection_run_binding=_selection_binding(),
        )


def test_recommendation_seal_requires_closed_selection_run_binding() -> None:
    development = _idea("2022-06-01T00:00:00Z", partition="development")
    validation = _idea("2024-06-01T00:00:00Z", partition="validation")
    simulation = simulate_shadow_policies(
        [development, validation],
        [_outcome(development), _outcome(validation)],
        partitions=("development", "validation"),
    )

    with pytest.raises(ValueError, match="selection run binding invalid"):
        freeze_recommendation_set(
            simulation,
            selection_run_binding={"mode": "full"},
        )

    seal = freeze_recommendation_set(
        simulation,
        selection_run_binding=_selection_binding(mode="medium"),
    )
    assert validate_recommendation_seal(seal) == []
    assert seal["selection_run_binding"]["mode"] == "medium"


def test_walk_forward_is_chronological_and_never_accesses_final_test() -> None:
    start = datetime(2021, 6, 12, tzinfo=timezone.utc)
    ideas = []
    outcomes = []
    for index in range(60):
        at = start + timedelta(days=index * 21)
        if at >= datetime(2025, 1, 1, tzinfo=timezone.utc):
            break
        partition = "development" if at < datetime(2023, 1, 1, tzinfo=timezone.utc) else "validation"
        idea = _idea(at.isoformat(), partition=partition, symbol=f"M{index}")
        ideas.append(idea)
        outcomes.append(_outcome(idea, 0.02 if index % 2 else -0.01))
    final = _idea("2025-06-01T00:00:00Z", partition="final_test", symbol="FINAL")
    ideas.append(final)
    outcomes.append(_outcome(final, 9.0))

    report = walk_forward_evaluation(ideas, outcomes)
    assert report["final_test_accessed"] is False
    assert report["fold_count"] >= 3
    assert all(row["selection_used_final_test"] is False for row in report["folds"])
    assert all(row["test_start"] == row["train_end_exclusive"] for row in report["folds"])


def test_shadow_policy_rejects_invalid_partition() -> None:
    with pytest.raises(ValueError, match="partitions invalid"):
        simulate_shadow_policies([], [], partitions=("fixture",))


def test_shadow_threshold_can_change_route_without_projection_drift() -> None:
    borderline = _idea(
        "2024-06-01T00:00:00Z",
        partition="validation",
        volume_zscore=2.5,
    )
    assert borderline["radar_route"] == "dashboard_watch"
    assert 45.0 <= borderline["actionability_score"] < 50.0

    result = simulate_shadow_policies(
        [borderline],
        [_outcome(borderline)],
        partitions=("validation",),
    )

    dashboard_50 = next(
        row for row in result["scenarios"] if row["scenario"] == "dashboard_watch_50"
    )
    assert dashboard_50["route_change_count"] == 1
    assert dashboard_50["material_policy_change_count"] == 1
    assert dashboard_50["visible_episode_count"] == 0


def test_behaviorally_identical_shadow_scenario_is_not_recommended() -> None:
    idea = _idea("2024-06-01T00:00:00Z", partition="validation")
    result = simulate_shadow_policies(
        [idea],
        [_outcome(idea)],
        partitions=("validation",),
    )
    recommendation = next(
        row
        for row in result["recommendations"]
        if row["scenario"] == "actionable_evidence_60"
    )

    assert recommendation["status"] == "not_supported"
    assert recommendation["reason"] == "scenario_produced_no_observable_policy_change"
    assert recommendation["material_policy_change_count"] == 0
