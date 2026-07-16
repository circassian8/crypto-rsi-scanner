from __future__ import annotations

from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.operations import empirical_operator_burden
from crypto_rsi_scanner.event_alpha.operations import empirical_replay_analysis
from crypto_rsi_scanner.event_alpha.operations import empirical_validation_protocol


def _row(episode_id: str, **overrides):
    value = {
        "episode_id": episode_id,
        "observed_at": "2022-01-01T00:00:00Z",
        "expires_at": "2022-01-04T00:00:00Z",
        "operator_visible_idea": True,
        "radar_route": "rapid_market_anomaly",
        "anomaly_family": "volume",
        "dependent_repeat_count": 0,
    }
    value.update(overrides)
    return value


def _simulation_rows():
    return [
        _row(
            "a",
            dependent_repeat_count=2,
            episode_member_progression=[
                {"idea_id": "a0", "observed_at": "2022-01-01T00:00:00Z"},
                {
                    "idea_id": "a1",
                    "observed_at": "2022-01-01T02:00:00Z",
                    "material_change_reasons": ["route_changed"],
                },
                {
                    "idea_id": "a2",
                    "observed_at": "2022-01-01T04:00:00Z",
                    "material_change_reasons": [],
                },
            ],
            digest_eligible=True,
            review_required=True,
            system_warning=False,
            calendar_reminder=False,
        ),
        _row(
            "b",
            digest_eligible=False,
            review_required=False,
            system_warning=False,
            calendar_reminder=False,
        ),
        _row(
            "c",
            radar_route="calendar_risk",
            anomaly_family="calendar",
            digest_eligible=True,
            review_required=False,
            system_warning=False,
            calendar_reminder=True,
        ),
        _row(
            "d",
            observed_at="2022-01-01T06:00:00Z",
            digest_eligible=False,
            review_required=False,
            system_warning=True,
            calendar_reminder=False,
        ),
        _row(
            "e",
            observed_at="2022-01-01T12:00:00Z",
            digest_eligible=False,
            review_required=False,
            system_warning=False,
            calendar_reminder=False,
        ),
        _row(
            "f",
            observed_at="2022-01-02T00:00:00Z",
            digest_eligible=False,
            review_required=False,
            system_warning=False,
            calendar_reminder=False,
        ),
    ]


def test_frozen_budget_simulations_have_exact_outcome_blind_counts() -> None:
    result = empirical_operator_burden.build_operator_notification_burden(
        _simulation_rows(),
        partition="development",
        evidence_mode="historical_replay",
    )

    protocol = empirical_validation_protocol.protocol_values()
    assert result["frozen_budgets"] == protocol["operator_burden"]["budgets"]
    assert result["input_basis"] == "episode_representatives_only"
    assert result["episode_count"] == 6
    assert result["visible_episode_count"] == 6
    assert result["urgent_visible_episode_count"] == 5
    assert result["dependent_repeat_item_count"] == 2
    assert result["sample_status"]["status"] == "descriptive_sample"

    per_cycle = result["simulations"]["urgent_per_cycle"]
    assert [(row["parameters"]["limit"], row["retained_count"], row["suppressed_count"]) for row in per_cycle] == [
        (1, 4, 1),
        (3, 5, 0),
        (5, 5, 0),
    ]
    per_day = result["simulations"]["urgent_per_day"]
    assert [(row["parameters"]["limit"], row["retained_count"], row["suppressed_count"]) for row in per_day] == [
        (3, 4, 1),
        (5, 5, 0),
        (10, 5, 0),
    ]
    family = result["simulations"]["one_item_per_visible_family"]
    assert family["retained_count"] == 5
    assert family["suppressed_count"] == 1
    cooldowns = result["simulations"]["family_cooldown"]
    assert [row["parameters"]["cooldown_hours"] for row in cooldowns] == [6, 12, 24, 48]
    assert [(row["retained_count"], row["suppressed_count"]) for row in cooldowns] == [
        (5, 1),
        (4, 2),
        (3, 3),
        (2, 4),
    ]
    material = result["simulations"]["material_change_only"]
    assert material["status"] == "ready"
    assert material["eligible_count"] == 8
    assert material["retained_count"] == 7
    assert material["suppressed_count"] == 1
    assert material["selection_rule"] == "initial_representative_plus_explicit_material_changes_only"
    intervals = result["material_change_intervals"]
    assert intervals["status"] == "available"
    assert intervals["available_count"] == 1
    assert intervals["median_hours"] == pytest.approx(2.0)

    assert result["outcomes_used_for_selection"] == 0
    assert result["outcome_fields_read"] == []
    assert result["causal_claim"] is False
    assert result["policy_eligible"] is False
    assert result["auto_apply"] is False
    assert set(result["safety"].values()) == {0}


def test_simulation_is_order_independent_and_ignores_outcome_payloads() -> None:
    original = _simulation_rows()
    with_outcomes = deepcopy(original)
    for index, row in enumerate(with_outcomes):
        row["representative_outcome"] = {
            "primary_direction_adjusted_return": 1000.0 - index,
            "status": "matured",
        }
        row["primary_horizon_return"] = -1000.0 + index

    first = empirical_operator_burden.build_operator_notification_burden(
        original,
        partition="development",
        evidence_mode="historical_replay",
    )
    second = empirical_operator_burden.build_operator_notification_burden(
        list(reversed(with_outcomes)),
        partition="development",
        evidence_mode="historical_replay",
    )

    assert first == second


def test_optional_state_and_expiry_are_explicitly_available_partial_or_missing() -> None:
    rows = [
        _row(
            "available",
            radar_route="actionable_watch",
            digest_eligible=True,
            review_required=False,
            system_warning=False,
            calendar_reminder=True,
        ),
        _row(
            "missing",
            radar_route="actionable_watch",
            expires_at=None,
        ),
        _row(
            "invalid",
            radar_route="actionable_watch",
            observed_at="2022-01-03T00:00:00Z",
            expires_at="2022-01-02T00:00:00Z",
            digest_eligible=False,
        ),
    ]

    result = empirical_operator_burden.build_operator_notification_burden(
        rows,
        partition="validation",
        evidence_mode="historical_replay",
    )

    digest = result["optional_operator_state"]["digest"]
    assert digest == {
        "status": "partial",
        "sample_count": 3,
        "true_count": 1,
        "false_count": 1,
        "missing_count": 1,
        "inferred_count": 0,
    }
    review = result["optional_operator_state"]["review"]
    assert review["status"] == "partial"
    assert review["false_count"] == 1
    assert review["missing_count"] == 2
    lifetime = result["idea_lifetime_and_expiry"]
    assert lifetime["status"] == "partial"
    assert lifetime["available_count"] == 1
    assert lifetime["missing_count"] == 1
    assert lifetime["invalid_count"] == 1
    assert lifetime["median_hours"] == pytest.approx(72.0)


def test_material_change_simulation_fails_closed_without_complete_progression_evidence() -> None:
    rows = [
        _row("a", dependent_repeat_count=2),
        _row(
            "b",
            dependent_repeat_count=1,
            episode_member_progression=[
                {"idea_id": "b0"},
                {"idea_id": "b1"},
            ],
        ),
    ]

    result = empirical_operator_burden.build_operator_notification_burden(
        rows,
        partition="development",
        evidence_mode="historical_replay",
    )["simulations"]["material_change_only"]

    assert result["available"] is False
    assert result["status"] == "unavailable_progression_or_material_change_state_missing"
    assert result["progression_missing_count"] == 2
    assert result["material_change_state_missing_count"] == 1
    assert result["retained_count"] is None
    assert result["suppressed_count"] is None
    assert result["selection_rule"] == "explicit_material_change_state_only_never_infer"


def test_visibility_is_not_inferred_and_missing_family_or_time_never_suppresses() -> None:
    rows = [
        _row("visible", observed_at=None, anomaly_family=None),
        _row("hidden", operator_visible_idea=False),
        _row("unknown", operator_visible_idea=None),
    ]

    result = empirical_operator_burden.build_operator_notification_burden(
        rows,
        partition="development",
        evidence_mode="historical_replay",
    )

    assert result["visible_episode_count"] == 1
    assert result["hidden_episode_count"] == 1
    assert result["visibility_missing_count"] == 1
    one_family = result["simulations"]["one_item_per_visible_family"]
    assert one_family["retained_count"] == 1
    assert one_family["family_missing_count_retained_unsuppressed"] == 1
    for row in result["simulations"]["family_cooldown"]:
        assert row["retained_count"] == 1
        assert row["missing_family_or_time_count_retained_unsuppressed"] == 1


def test_analysis_surface_delegates_to_closed_simulator() -> None:
    rows = _simulation_rows()
    direct = empirical_operator_burden.build_operator_notification_burden(
        rows,
        partition="development",
        evidence_mode="historical_replay",
    )
    integrated = empirical_replay_analysis.operator_burden(
        rows,
        partition="development",
        evidence_mode="historical_replay",
    )

    assert integrated == direct
    assert integrated["schema_id"] == empirical_operator_burden.SCHEMA_ID


def test_empty_input_is_closed_and_all_scenarios_are_bounded() -> None:
    result = empirical_operator_burden.build_operator_notification_burden(
        [],
        partition="development",
        evidence_mode="historical_replay",
    )

    assert result["input_status"] == "no_input"
    assert result["sample_status"]["status"] == "no_sample"
    assert result["simulation_scenario_count"] == 12
    assert result["simulations"]["one_item_per_visible_family"]["status"] == "no_sample"
    assert result["simulations"]["material_change_only"]["available"] is False
