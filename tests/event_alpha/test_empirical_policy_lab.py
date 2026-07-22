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


def _daily_clones(base, *, count: int, start: datetime, partition: str, value=0.10):
    ideas = []
    outcomes = []
    for index in range(count):
        idea = deepcopy(base)
        idea["candidate_id"] = f"clone-{partition}-{index:04d}"
        idea["episode_id"] = f"episode-{partition}-{index:04d}"
        observed = start + timedelta(days=index)
        original_observed = datetime.fromisoformat(
            str(base["observed_at"]).replace("Z", "+00:00")
        )
        original_expiry = datetime.fromisoformat(
            str(base["expires_at"]).replace("Z", "+00:00")
        )
        expires_at = observed + (original_expiry - original_observed)
        idea["observed_at"] = observed.isoformat()
        idea["decision_evaluated_at"] = observed.isoformat()
        idea["expires_at"] = expires_at.isoformat()
        idea["decision_projection"] = {
            **idea["decision_projection"],
            "decision_evaluated_at": observed.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        idea["replay_partition"] = partition
        ideas.append(idea)
        outcomes.append(_outcome(idea, value))
    return ideas, outcomes


def _selected_days_by_partition(ideas):
    result = {"development": set(), "validation": set(), "final_test": set()}
    for idea in ideas:
        partition = str(idea.get("replay_partition") or "")
        if partition in result:
            result[partition].add(str(idea["observed_at"])[:10])
    return result


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
    assert result["recommendation_seal_eligible"] is False
    assert result["recommendation_seal_ineligibility_reasons"] == [
        "exact_selected_observation_days_not_supplied"
    ]
    assert all(row["research_only"] and not row["auto_apply"] for row in result["scenarios"])


def test_active_day_fallback_cannot_be_frozen_as_recommendation_evidence() -> None:
    development = _idea("2022-06-01T00:00:00Z", partition="development")
    validation = _idea("2024-06-01T00:00:00Z", partition="validation")
    simulation = simulate_shadow_policies(
        [development, validation],
        [_outcome(development), _outcome(validation)],
        partitions=("development", "validation"),
    )

    assert simulation["observed_day_denominator_basis"] == (
        "fallback_episode_active_utc_days_only"
    )
    assert simulation["recommendation_seal_eligible"] is False
    with pytest.raises(
        ValueError, match="requires exact selected observation days"
    ):
        freeze_recommendation_set(
            simulation,
            selection_run_binding=_selection_binding(),
        )

    forged = deepcopy(simulation)
    forged["observed_day_denominator_basis"] = (
        "exact_selected_observation_utc_days"
    )
    forged["recommendation_seal_eligible"] = True
    forged["recommendation_seal_ineligibility_reasons"] = []
    forged["selected_observation_day_count"] = 2
    forged["selected_observation_days_sha256"] = "e" * 64
    with pytest.raises(
        ValueError, match="selected observation days inconsistent"
    ):
        freeze_recommendation_set(
            forged,
            selection_run_binding=_selection_binding(),
        )

    empty_exact = simulate_shadow_policies(
        [],
        [],
        partitions=("development", "validation"),
        selected_observation_days_by_partition={
            "development": set(),
            "validation": set(),
        },
    )
    assert empty_exact["recommendation_seal_eligible"] is False
    assert empty_exact["recommendation_seal_ineligibility_reasons"] == [
        "selected_observation_days_empty"
    ]
    with pytest.raises(
        ValueError, match="requires exact selected observation days"
    ):
        freeze_recommendation_set(
            empty_exact,
            selection_run_binding=_selection_binding(),
        )


def test_recommendation_seal_excludes_final_test_and_is_tamper_evident() -> None:
    development = _idea("2022-06-01T00:00:00Z", partition="development")
    validation = _idea("2024-06-01T00:00:00Z", partition="validation")
    simulation = simulate_shadow_policies(
        [development, validation],
        [_outcome(development), _outcome(validation)],
        partitions=("development", "validation"),
        selected_observation_days_by_partition=_selected_days_by_partition(
            [development, validation]
        ),
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
    with pytest.raises(
        ValueError, match="final confirmation requires exact selected observation days"
    ):
        evaluate_sealed_final_test(
            [final], [_outcome(final)], seal=seal
        )
    final_result = evaluate_sealed_final_test(
        [final],
        [_outcome(final)],
        seal=seal,
        selected_observation_days_by_partition=_selected_days_by_partition(
            [final]
        ),
    )
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
        selected_observation_days_by_partition=_selected_days_by_partition(
            [development, validation]
        ),
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
        if datetime(2023, 1, 1, tzinfo=timezone.utc) <= at < datetime(
            2023, 1, 15, tzinfo=timezone.utc
        ):
            continue
        partition = "development" if at < datetime(2023, 1, 1, tzinfo=timezone.utc) else "validation"
        idea = _idea(at.isoformat(), partition=partition, symbol=f"M{index}")
        ideas.append(idea)
        outcomes.append(_outcome(idea, 0.02 if index % 2 else -0.01))
    final = _idea("2025-06-01T00:00:00Z", partition="final_test", symbol="FINAL")
    ideas.append(final)
    outcomes.append(_outcome(final, 9.0))

    report = walk_forward_evaluation(
        ideas,
        outcomes,
        selected_observation_days_by_partition=_selected_days_by_partition(
            ideas
        ),
    )
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


def test_expiry_24h_caps_shadow_lifetime_and_uses_exact_expiry_outcome() -> None:
    idea = _idea("2024-06-01T00:00:00Z", partition="validation")
    observed = datetime(2024, 6, 1, tzinfo=timezone.utc)
    canonical_expiry = observed + timedelta(hours=72)
    idea["expires_at"] = canonical_expiry.isoformat()
    idea["decision_projection"] = {
        **idea["decision_projection"],
        "expires_at": canonical_expiry.isoformat(),
    }
    before = deepcopy(idea)
    outcome = {
        "candidate_id": idea["candidate_id"],
        "outcome_status": "matured",
        "primary_horizon": "3d",
        "primary_direction_adjusted_return": 0.12,
        "horizons": {
            "1d": {
                "due_at": (observed + timedelta(days=1)).isoformat(),
                "maturity_status": "matured",
                "direction_adjusted_return_fraction": -0.06,
            },
            "3d": {
                "due_at": (observed + timedelta(days=3)).isoformat(),
                "maturity_status": "matured",
                "direction_adjusted_return_fraction": 0.12,
            },
        },
    }

    result = simulate_shadow_policies(
        [idea],
        [outcome],
        partitions=("validation",),
        selected_observation_days_by_partition=_selected_days_by_partition(
            [idea]
        ),
    )
    production = next(
        row for row in result["scenarios"] if row["scenario"] == "production_policy"
    )
    expiry = next(
        row for row in result["scenarios"] if row["scenario"] == "expiry_24h"
    )

    assert idea == before
    assert production["mean_directional_return_fraction"] == pytest.approx(0.12)
    assert production["visible_operator_lifetime_hours"] == pytest.approx(72.0)
    assert expiry["route_change_count"] == 0
    assert expiry["expiry_capped_count"] == 1
    assert expiry["material_policy_change_count"] == 1
    assert expiry["visible_operator_lifetime_hours"] == pytest.approx(24.0)
    assert expiry["visible_operator_lifetime_reduction_hours"] == pytest.approx(48.0)
    assert expiry["mean_directional_return_fraction"] == pytest.approx(-0.06)
    assert expiry["return_basis_counts"] == {"shadow_expiry_exact_horizon": 1}
    assert expiry["false_positive_summary"]["quick_failure_count"] == 1
    assert expiry["missed_opportunity_proxy"][
        "expired_before_positive_primary_resolution_count"
    ] == 1
    comparison = expiry["comparison_to_production"]
    assert comparison["quick_failure_count_change"] == 1
    assert comparison["hidden_positive_episode_change"] == 1
    assert comparison["visible_operator_lifetime_hours_change"] == pytest.approx(
        -48.0
    )


def test_walk_forward_purges_boundary_outcomes_and_omits_partial_fold() -> None:
    start = datetime(2021, 6, 12, tzinfo=timezone.utc)
    ideas = []
    outcomes = []
    for index in range(70):
        at = start + timedelta(days=index * 18)
        if at >= datetime(2025, 1, 1, tzinfo=timezone.utc):
            break
        if datetime(2023, 1, 1, tzinfo=timezone.utc) <= at < datetime(
            2023, 1, 15, tzinfo=timezone.utc
        ):
            continue
        partition = (
            "development"
            if at < datetime(2023, 1, 1, tzinfo=timezone.utc)
            else "validation"
        )
        idea = _idea(at.isoformat(), partition=partition, symbol=f"P{index}")
        ideas.append(idea)
        outcome = _outcome(idea, 0.03)
        outcome["primary_horizon"] = "3d"
        outcome["horizons"] = {
            "3d": {"due_at": (at + timedelta(days=3)).isoformat()}
        }
        outcomes.append(outcome)
    crossing_at = datetime(2023, 6, 11, tzinfo=timezone.utc)
    crossing = _idea(
        crossing_at.isoformat(), partition="validation", symbol="BOUNDARY"
    )
    ideas.append(crossing)
    crossing_outcome = _outcome(crossing, 9.0)
    crossing_outcome["primary_horizon"] = "3d"
    crossing_outcome["horizons"] = {
        "3d": {"due_at": (crossing_at + timedelta(days=3)).isoformat()}
    }
    outcomes.append(crossing_outcome)

    report = walk_forward_evaluation(
        ideas,
        outcomes,
        selected_observation_days_by_partition=_selected_days_by_partition(
            ideas
        ),
    )

    assert report["outcome_purge_rule"] == "primary_horizon_due_at_lt_fold_boundary"
    assert report["omitted_partial_test_window"]["status"] == "omitted_partial_test_fold"
    assert report["fold_count"] >= report["minimum_fold_count"]
    assert any(
        fold["train_outcome_purged_count"] or fold["test_outcome_purged_count"]
        for fold in report["folds"]
    )
    assert all(
        fold["test_end_exclusive"]
        == (
            datetime.fromisoformat(fold["test_start"])
            + timedelta(days=180)
        ).isoformat()
        for fold in report["folds"]
    )


def test_walk_forward_counts_only_outcome_evaluable_test_folds() -> None:
    ideas = [
        _idea("2023-07-01T00:00:00Z", partition="validation", symbol="EMPTY1"),
        _idea("2024-01-01T00:00:00Z", partition="validation", symbol="EMPTY2"),
        _idea("2024-07-01T00:00:00Z", partition="validation", symbol="EMPTY3"),
    ]

    pending_outcomes = []
    for idea in ideas:
        observed = datetime.fromisoformat(
            str(idea["observed_at"]).replace("Z", "+00:00")
        )
        pending_outcomes.append({
            "candidate_id": idea["candidate_id"],
            "outcome_status": "pending",
            "primary_horizon": "3d",
            "horizons": {
                "3d": {
                    "due_at": (observed + timedelta(days=3)).isoformat()
                }
            },
        })

    report = walk_forward_evaluation(
        ideas,
        pending_outcomes,
        selected_observation_days_by_partition=_selected_days_by_partition(
            ideas
        ),
    )

    assert report["fold_count"] == 3
    assert all(row["test_episode_count"] == 1 for row in report["folds"])
    assert all(
        row["test_outcome_eligible_episode_count"] == 1
        for row in report["folds"]
    )
    assert all(
        row["test_outcome_evaluable_episode_count"] == 0
        for row in report["folds"]
    )
    assert report["nonempty_fold_count"] == 3
    assert report["outcome_evaluable_fold_count"] == 0
    assert report["status"] == "insufficient_walk_forward_folds"


def test_walk_forward_rejects_stored_due_at_drift_from_frozen_horizon() -> None:
    idea = _idea(
        "2023-07-01T00:00:00Z", partition="validation", symbol="DUE-DRIFT"
    )
    observed = datetime(2023, 7, 1, tzinfo=timezone.utc)
    outcome = _outcome(idea, 0.03)
    outcome["primary_horizon"] = "3d"
    outcome["horizons"] = {
        "3d": {"due_at": (observed + timedelta(days=2)).isoformat()}
    }

    with pytest.raises(
        ValueError, match="due_at does not match frozen horizon"
    ):
        walk_forward_evaluation(
            [idea],
            [outcome],
            selected_observation_days_by_partition=_selected_days_by_partition(
                [idea]
            ),
        )

    wrong_horizon = deepcopy(outcome)
    wrong_horizon["primary_horizon"] = "1d"
    wrong_horizon["horizons"] = {
        "1d": {"due_at": (observed + timedelta(days=1)).isoformat()}
    }
    with pytest.raises(
        ValueError, match="horizon does not match frozen protocol"
    ):
        walk_forward_evaluation(
            [idea],
            [wrong_horizon],
            selected_observation_days_by_partition=_selected_days_by_partition(
                [idea]
            ),
        )

    equivalent_offset = deepcopy(outcome)
    equivalent_offset["horizons"] = {
        "3d": {"due_at": "2023-07-04T03:00:00+03:00"}
    }
    report = walk_forward_evaluation(
        [idea],
        [equivalent_offset],
        selected_observation_days_by_partition=_selected_days_by_partition(
            [idea]
        ),
    )
    assert report["folds"][0]["test_outcome_eligible_episode_count"] == 1


def test_sealed_final_confirmation_uses_frozen_sample_and_noninferiority_rule() -> None:
    selection_base = _idea(
        "2024-01-01T00:00:00Z", partition="validation", symbol="SELECT"
    )
    selection_ideas, selection_outcomes = _daily_clones(
        selection_base,
        count=240,
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        partition="validation",
    )
    simulation = simulate_shadow_policies(
        selection_ideas,
        selection_outcomes,
        partitions=("development", "validation"),
        selected_observation_days_by_partition=_selected_days_by_partition(
            selection_ideas
        ),
    )
    recommendation = next(
        row
        for row in simulation["recommendations"]
        if row["scenario"] == "family_cooldown_48h"
    )
    assert recommendation["status"] == "candidate"
    seal = freeze_recommendation_set(
        simulation, selection_run_binding=_selection_binding()
    )

    final_base = _idea(
        "2025-02-01T00:00:00Z", partition="final_test", symbol="FINAL"
    )
    insufficient_ideas, insufficient_outcomes = _daily_clones(
        final_base,
        count=58,
        start=datetime(2025, 2, 1, tzinfo=timezone.utc),
        partition="final_test",
    )
    insufficient = evaluate_sealed_final_test(
        insufficient_ideas,
        insufficient_outcomes,
        seal=seal,
        selected_observation_days_by_partition=_selected_days_by_partition(
            insufficient_ideas
        ),
    )
    verdict = insufficient["confirmations"][0]
    assert verdict["sample_size"] == 29
    assert verdict["confirmation_status"] == "insufficient_sample"

    confirmed_ideas, confirmed_outcomes = _daily_clones(
        final_base,
        count=60,
        start=datetime(2025, 2, 1, tzinfo=timezone.utc),
        partition="final_test",
    )
    confirmed = evaluate_sealed_final_test(
        confirmed_ideas,
        confirmed_outcomes,
        seal=seal,
        selected_observation_days_by_partition=_selected_days_by_partition(
            confirmed_ideas
        ),
    )
    verdict = confirmed["confirmations"][0]
    assert verdict["sample_size"] == 30
    assert verdict["confirmation_status"] == "confirmed"
    assert verdict["eligible_for_human_policy_review"] is True
    assert confirmed["scenario_selection_performed"] is False
    assert confirmed["production_policy_mutations"] == 0
    assert [row["scenario"] for row in confirmed["evaluated_scenarios"]] == [
        "production_policy",
        "family_cooldown_48h",
    ]


def test_final_confirmation_rule_mutation_invalidates_seal() -> None:
    development = _idea("2022-06-01T00:00:00Z", partition="development")
    validation = _idea("2024-06-01T00:00:00Z", partition="validation")
    simulation = simulate_shadow_policies(
        [development, validation],
        [_outcome(development), _outcome(validation)],
        partitions=("development", "validation"),
        selected_observation_days_by_partition=_selected_days_by_partition(
            [development, validation]
        ),
    )
    seal = freeze_recommendation_set(
        simulation, selection_run_binding=_selection_binding()
    )
    changed = deepcopy(seal)
    changed["final_test_confirmation_rule"][
        "minimum_matured_visible_episodes"
    ] = 29

    assert "final_test_confirmation_rule_invalid" in validate_recommendation_seal(
        changed
    )


def test_shadow_burden_uses_same_selected_day_denominator_for_every_scenario() -> None:
    borderline = _idea(
        "2024-06-01T00:00:00Z",
        partition="validation",
        volume_zscore=2.5,
    )
    selected_days = {
        (datetime(2024, 6, 1, tzinfo=timezone.utc) + timedelta(days=index))
        .date()
        .isoformat()
        for index in range(100)
    }

    result = simulate_shadow_policies(
        [borderline],
        [_outcome(borderline)],
        partitions=("validation",),
        selected_observation_days_by_partition={"validation": selected_days},
    )

    production = next(
        row for row in result["scenarios"] if row["scenario"] == "production_policy"
    )
    hidden = next(
        row for row in result["scenarios"] if row["scenario"] == "dashboard_watch_50"
    )
    assert result["selected_observation_day_count"] == 100
    assert result["idea_active_day_count"] == 1
    assert result["observed_day_denominator_basis"] == (
        "exact_selected_observation_utc_days"
    )
    assert production["observed_day_count"] == 100
    assert production["zero_idea_observed_day_count"] == 99
    assert production["ideas_per_observed_day"] == pytest.approx(0.01)
    assert production["ideas_per_active_day"] == pytest.approx(1.0)
    assert hidden["ideas_per_observed_day"] == pytest.approx(0.0)
    assert hidden["selected_observation_days_sha256"] == production[
        "selected_observation_days_sha256"
    ]
    assert hidden["comparison_to_production"][
        "ideas_per_observed_day_change"
    ] == pytest.approx(-0.01)
    recommendation = next(
        row
        for row in result["recommendations"]
        if row["scenario"] == "dashboard_watch_50"
    )
    checks = recommendation["comparison_checks"]
    assert checks["operator_burden_metric"] == "ideas_per_observed_day"
    assert checks["operator_burden_denominator_match"] is True
