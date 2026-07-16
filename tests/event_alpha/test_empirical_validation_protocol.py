from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import empirical_validation_protocol as protocol


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frozen_protocol_is_exact_valid_and_tracked() -> None:
    values = protocol.protocol_values()

    assert protocol.validate_protocol(values) == []
    assert protocol.check_tracked_protocol_files(PROJECT_ROOT) == []
    assert protocol.protocol_sha256(values) == protocol.protocol_sha256()
    assert values["status"] == "frozen_before_final_test_evaluation"
    assert values["research_only"] is True
    assert values["auto_apply"] is False


def test_frozen_protocol_has_closed_chronological_final_test_firewall() -> None:
    values = protocol.protocol_values()

    assert [row["name"] for row in values["partitions"]] == [
        "development",
        "validation",
        "final_test",
    ]
    assert values["partitions"][0]["outcome_end_exclusive"] == values["partitions"][1]["start_inclusive"]
    assert values["partitions"][1]["outcome_end_exclusive"] == values["partitions"][2]["start_inclusive"]
    assert values["partition_embargoes"] == [
        {
            "after_partition": "development",
            "before_partition": "validation",
            "start_inclusive": "2023-01-01T00:00:00Z",
            "end_exclusive": "2023-01-15T00:00:00Z",
            "idea_evaluation_allowed": False,
            "purpose": "outcome_only_maximum_sensitivity_horizon_purge",
        },
        {
            "after_partition": "validation",
            "before_partition": "final_test",
            "start_inclusive": "2025-01-01T00:00:00Z",
            "end_exclusive": "2025-01-15T00:00:00Z",
            "idea_evaluation_allowed": False,
            "purpose": "outcome_only_maximum_sensitivity_horizon_purge",
        },
    ]
    assert values["partitions"][2]["policy_selection_allowed"] is False
    assert values["walk_forward"]["selection_partitions"] == ["development", "validation"]
    assert values["walk_forward"]["confirmation_partition"] == "final_test"
    assert values["walk_forward"]["final_test_used_for_tuning"] is False
    assert values["walk_forward"]["recommendation_set_must_be_hashed_before_final_test"] is True


def test_frozen_protocol_closes_primary_outcome_controls_and_missed_move_rule() -> None:
    values = protocol.protocol_values()

    assert values["outcomes"]["primary_horizon_days"] == 3
    assert values["observation"]["same_bar_high_low_for_outcome_forbidden"] is True
    assert values["feature_warmup"]["volume_zscore_lookback_days"] == 90
    assert values["feature_warmup"]["volume_zscore_min_observations"] == 20
    assert values["episodes"]["representative"] == "first_eligible_observation"
    assert values["episodes"]["representative_reselection"] == "forbidden"
    assert values["episodes"]["window_end_inclusive"] is True
    assert values["episodes"]["boundary_rule"] == (
        "member_observed_at_lte_episode_start_plus_window"
    )
    assert values["matched_controls"]["selection_uses_outcomes"] is False
    assert values["missed_opportunity_rule"]["maximum_future_excursion_alone_is_sufficient"] is False
    assert values["missed_opportunity_rule"]["classification_occurs_only_after_maturity"] is True


def test_frozen_protocol_declares_missing_data_and_safety_without_proxies() -> None:
    values = protocol.protocol_values()

    assert values["missing_data_policy"]["spread_without_order_book"] == "unavailable"
    assert values["missing_data_policy"]["proxy_must_be_labeled"] is True
    assert values["missing_data_policy"]["direct_and_proxy_results_reported_separately"] is True
    assert values["cost_scenarios"]["historical_spread_observation_status"] == "unavailable"
    assert set(values["safety"].values()) == {0}
    assert values["policy_change_rules"]["production_mutation_allowed"] is False
    assert values["policy_change_rules"]["threshold_lowering_to_create_ideas"] is False
    for rule_name in (
        "shadow_recommendation_rule",
        "final_test_confirmation_rule",
    ):
        rule = values[rule_name]
        assert rule["rule_id"] == (
            "noninferior_return_failure_selected_day_burden_v1"
        )
        assert rule["ideas_per_selected_observation_day_check"] == (
            "candidate_lte_1_2x_production"
        )
        assert "ideas_per_active_day_check" not in rule


def test_protocol_mutations_fail_closed() -> None:
    mutation_cases = []
    final_tuning = protocol.protocol_values()
    final_tuning["walk_forward"]["final_test_used_for_tuning"] = True
    mutation_cases.append(final_tuning)
    horizon = protocol.protocol_values()
    horizon["outcomes"]["primary_horizon_days"] = 7
    mutation_cases.append(horizon)
    boundary = protocol.protocol_values()
    boundary["partitions"][1]["start_inclusive"] = "2023-02-01T00:00:00Z"
    mutation_cases.append(boundary)
    safety = protocol.protocol_values()
    safety["safety"]["provider_calls"] = 1
    mutation_cases.append(safety)
    warmup = protocol.protocol_values()
    warmup["feature_warmup"]["volume_zscore_min_observations"] = 19
    mutation_cases.append(warmup)
    episode = protocol.protocol_values()
    episode["episodes"]["window_end_inclusive"] = False
    mutation_cases.append(episode)

    for values in mutation_cases:
        assert protocol.validate_protocol(values)


def test_protocol_values_are_defensive_copies() -> None:
    first = protocol.protocol_values()
    second = protocol.protocol_values()
    first["partitions"][0]["end_exclusive"] = "2099-01-01T00:00:00Z"

    assert second == protocol.protocol_values()
    assert first != second
    assert deepcopy(second) == second


def test_selected_observation_day_digest_is_order_and_duplicate_independent() -> None:
    expected = protocol.selected_observation_days_sha256(
        ["2025-01-15", "2025-01-16"]
    )

    assert protocol.selected_observation_days_sha256(
        ["2025-01-16", "2025-01-15", "2025-01-16"]
    ) == expected
    assert protocol.selected_observation_days_sha256([]) == (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )
