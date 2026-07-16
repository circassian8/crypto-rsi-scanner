from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_review import (
    CATEGORY_ORDER,
    LABEL_TAXONOMY,
    MAX_ITEMS_PER_CATEGORY,
    MAX_QUEUE_ITEMS,
    build_targeted_review_queue,
)


RUN_FINGERPRINT = "a" * 64
PROTOCOL_SHA256 = "b" * 64
PROTOCOL_VERSION = "decision_radar_empirical_validation_v1"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _idea(
    episode_id: str,
    *,
    actionability: float,
    catalyst: str = "unknown",
    liquidity: str = "high",
    chase: float = 30.0,
    **overrides: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": f"candidate:{episode_id}",
        "core_opportunity_id": f"core:{episode_id}",
        "canonical_asset_id": f"asset:{episode_id}",
        "symbol": episode_id.upper(),
        "observed_at": "2022-02-01T00:00:00+00:00",
        "partition": "development",
        "replay_partition": "development",
        "replay_mode": "medium",
        "data_mode": "replay",
        "replay_protocol_version": PROTOCOL_VERSION,
        "replay_protocol_sha256": PROTOCOL_SHA256,
        "radar_route": "actionable_watch",
        "primary_thesis_origin": "market_led",
        "directional_bias": "long",
        "catalyst_status": catalyst,
        "actionability_score": actionability,
        "evidence_confidence_score": 74.0,
        "risk_score": 40.0,
        "urgency_score": 50.0,
        "chase_risk_score": chase,
        "liquidity_tier": liquidity,
        "spread_status": "unavailable",
        "baseline_status": "warm",
        "baseline_warm": True,
        "point_in_time_universe_member": True,
        "operator_visible_idea": True,
        "data_quality_mode": "historical_ohlcv",
        "replay_data_quality_mode": "historical_ohlcv",
        "return_unit": "percent_points",
        "decision_projection": {
            "radar_route": "actionable_watch",
            "primary_thesis_origin": "market_led",
            "directional_bias": "long",
            "catalyst_status": catalyst,
            "actionability_score": actionability,
            "evidence_confidence_score": 74.0,
            "risk_score": 40.0,
            "urgency_score": 50.0,
            "chase_risk_score": chase,
            "research_only": True,
        },
        "research_only": True,
    }
    row.update(overrides)
    return row


def _episode(
    idea: dict[str, object],
    directional_return: float,
    *,
    status: str = "matured",
) -> dict[str, object]:
    episode_id = str(idea["candidate_id"]).split(":", 1)[1]
    representative = {
        key: idea[key]
        for key in (
            "candidate_id",
            "core_opportunity_id",
            "canonical_asset_id",
            "symbol",
            "observed_at",
            "partition",
            "radar_route",
            "primary_thesis_origin",
            "directional_bias",
            "catalyst_status",
            "actionability_score",
            "evidence_confidence_score",
            "risk_score",
            "urgency_score",
            "chase_risk_score",
            "liquidity_tier",
            "spread_status",
            "baseline_status",
            "baseline_warm",
            "point_in_time_universe_member",
            "operator_visible_idea",
            "data_quality_mode",
            "replay_data_quality_mode",
            "decision_projection",
        )
        if key in idea
    }
    outcome = {
        "episode_id": episode_id,
        "candidate_id": idea["candidate_id"],
        "status": status,
        "observed_at": idea["observed_at"],
        "primary_horizon": "3d",
        "primary_direction_adjusted_return": directional_return,
        "primary_relative_return_vs_btc": directional_return - 0.01,
        "primary_relative_return_vs_eth": directional_return - 0.02,
        "max_favorable_excursion": max(0.01, directional_return + 0.04),
        "max_adverse_excursion": min(-0.01, directional_return - 0.03),
        "time_to_mfe_hours": 48.0,
        "time_to_mae_hours": 24.0,
        "time_to_invalidation_hours": 24.0 if directional_return <= 0 else None,
        "return_unit": "fraction",
    }
    outcome["outcome_digest"] = _digest(outcome)
    body = {
        "episode_id": episode_id,
        "episode_digest": "",
        "representative": representative,
        "representative_outcome": outcome,
    }
    body["episode_digest"] = _digest(body)
    return body


def _analysis(
    false_late: list[dict[str, object]],
    *,
    violation: bool = True,
) -> dict[str, object]:
    row: dict[str, object] = {
        "schema_id": "decision_radar.empirical_replay_analysis",
        "partition": "development",
        "evidence_mode": "historical_replay",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "score_monotonicity": [
            {
                "score_field": "actionability_score",
                "expected_relationship": "nondecreasing_outcome_quality",
                "comparisons": [
                    {
                        "lower_bucket": "0_19",
                        "higher_bucket": "80_100",
                        "observed_delta_fraction": -0.30,
                        "violation": violation,
                    }
                ],
            }
        ],
        "false_positive_and_late_classifications": false_late,
    }
    row["analysis_digest"] = _digest(row)
    return row


def _controls(missed_rows: list[dict[str, object]], *, total: int | None = None):
    return {
        "schema_id": "decision_radar.empirical_replay_controls",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "contract_digest": "c" * 64,
        "evidence_mode": "historical_replay",
        "missed_move_evaluation": {
            "missed_opportunity_count": len(missed_rows) if total is None else total,
            "missed_opportunities": missed_rows,
            "missed_opportunities_truncated": (
                total is not None and total > len(missed_rows)
            ),
        },
    }


def _missed(index: int, return_fraction: float = 0.20) -> dict[str, object]:
    return {
        "missed_move_id": f"missed-move-v1:{index:064x}",
        "directional_bias": "long",
        "primary_endpoint_return_fraction": return_fraction,
        "endpoint_rule_crossed": True,
        "maximum_future_excursion_alone_sufficient": False,
        "operator_visible_idea": False,
        "trace_status": "no_idea",
        "failure_stage": "no_anomaly_generated",
        "qualification_failure_reasons": [],
        "qualifies_as_missed_opportunity": True,
        "observation": {
            "canonical_asset_id": f"missed:{index}",
            "symbol": f"M{index}",
            "observed_at": f"2022-03-{index + 1:02d}T00:00:00+00:00",
            "partition": "development",
            "data_quality_mode": "historical_ohlcv",
            "baseline_status": "warm",
            "liquidity_tier": "high",
            "observation_digest": f"{index + 1:064x}",
        },
        "outcome": {
            "status": "matured",
            "primary_horizon": "3d",
            "primary_direction_adjusted_return": return_fraction,
            "max_favorable_excursion": return_fraction + 0.05,
            "max_adverse_excursion": -0.03,
            "return_unit": "fraction",
        },
    }


def _build(
    ideas: list[dict[str, object]],
    episodes: list[dict[str, object]],
    analysis: dict[str, object] | None = None,
    controls: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_targeted_review_queue(
        ideas,
        {"episodes": episodes},
        {"partitions": {"development": analysis}} if analysis else {"partitions": {}},
        controls or {},
        run_fingerprint=RUN_FINGERPRINT,
    )


def test_empty_queue_closes_taxonomy_and_safety_contract() -> None:
    queue = _build([], [])

    assert queue["schema_id"] == "decision_radar.empirical_targeted_review_queue"
    assert queue["category_order"] == list(CATEGORY_ORDER)
    assert [row["category"] for row in queue["categories"]] == list(CATEGORY_ORDER)
    assert all(row["eligible_count"] == 0 for row in queue["categories"])
    assert all(row["selection_status"] == "zero_sample" for row in queue["categories"])
    assert queue["items"] == []
    assert queue["item_count"] == 0
    assert queue["human_feedback"]["labels"] == list(LABEL_TAXONOMY)
    assert queue["human_feedback"]["optional"] is True
    assert queue["human_feedback"]["ledger_implemented_by_this_module"] is False
    assert queue["selection_uses_outcomes"] is True
    assert queue["selection_changes_replay_results"] is False
    assert queue["policy_eligible"] is False
    assert queue["auto_apply"] is False
    assert set(queue["safety"].values()) == {0}
    assert len(queue["queue_digest"]) == 64


def test_queue_selects_all_requested_example_categories_and_binds_evidence() -> None:
    low = _idea("low", actionability=10.0)
    high = _idea("high", actionability=90.0, catalyst="confirmed")
    borderline = _idea("border", actionability=45.5)
    manipulation = _idea(
        "trap",
        actionability=70.0,
        liquidity="low",
        chase=85.0,
        risk_score_components={"manipulation_risk": 85.0},
    )
    inconsistent = _idea(
        "quality",
        actionability=50.0,
        replay_data_quality_mode="cross_sectional_proxy",
    )
    ideas = [low, high, borderline, manipulation, inconsistent]
    episodes = [
        _episode(low, 0.20),
        _episode(high, -0.20),
        _episode(borderline, 0.04),
        _episode(manipulation, -0.15),
        _episode(inconsistent, 0.02),
    ]
    false_late = [
        {
            "episode_id": "trap",
            "classification_status": "evaluated",
            "false_positive": True,
            "late_idea": True,
            "chase_risk_score": 85.0,
            "pre_signal_directional_move_7d_fraction": 0.40,
            "symptom_codes": ["failed_quickly", "high_chase_risk"],
            "issue_source_codes": ["timing_model", "data_quality"],
        }
    ]
    queue = _build(
        ideas,
        episodes,
        _analysis(false_late),
        _controls([_missed(1)]),
    )

    by_category = {row["category"]: row for row in queue["categories"]}
    assert all(by_category[name]["eligible_count"] >= 1 for name in CATEGORY_ORDER)
    assert all(by_category[name]["selected_count"] >= 1 for name in CATEGORY_ORDER)
    assert queue["item_count"] <= MAX_QUEUE_ITEMS
    assert queue["protocol_version"] == PROTOCOL_VERSION
    assert queue["protocol_sha256"] == PROTOCOL_SHA256
    assert len(queue["evidence_digest"]) == 64
    assert set(queue["source_evidence_digests"]) == {
        "ideas", "episodes", "analyses", "controls"
    }
    for item in queue["items"]:
        assert item["run_fingerprint"] == RUN_FINGERPRINT
        assert len(item["review_item_id"].split(":")[-1]) == 64
        assert len(item["evidence_digest"]) == 64
        assert item["review_status"] == "unlabeled"
        assert item["research_only"] is True
        assert item["auto_apply"] is False
        assert item["policy_eligible"] is False
    pair = next(
        item for item in queue["items"]
        if "monotonicity_violation" in item["categories"]
    )
    assert pair["target_kind"] == "episode_pair"
    assert set(pair["paired_episode_ids"]) == {"low", "high"}
    assert len(pair["pair_examples"]) == 2
    concern = next(
        item for item in queue["items"]
        if "manipulation_concern_candidate" in item["categories"]
    )
    reason = concern["selection_reasons"]["manipulation_concern_candidate"]
    assert reason["classification"] == "concern_candidate"
    assert reason["manipulation_confirmed"] is False
    assert concern["causal_claim"] is False


def test_selection_is_order_independent_and_queue_is_bounded() -> None:
    ideas = [
        _idea(
            f"episode-{index:03d}",
            actionability=44.0 if index % 2 else 70.0,
            catalyst="unknown",
        )
        for index in range(100)
    ]
    episodes = [
        _episode(idea, 0.01 + index / 1000.0)
        for index, idea in enumerate(ideas)
    ]
    missed = [_missed(index, 0.20 + index / 100.0) for index in range(12)]
    controls = _controls(missed, total=30)
    first = _build(ideas, episodes, _analysis([], violation=False), controls)
    second = _build(
        list(reversed(ideas)),
        list(reversed(episodes)),
        deepcopy(_analysis([], violation=False)),
        _controls(list(reversed(missed)), total=30),
    )

    assert first == second
    assert first["item_count"] <= MAX_QUEUE_ITEMS
    rows = {row["category"]: row for row in first["categories"]}
    assert all(row["selected_count"] <= MAX_ITEMS_PER_CATEGORY for row in rows.values())
    assert rows["unknown_catalyst_winner"]["eligible_count"] == 100
    assert rows["unknown_catalyst_winner"]["selected_count"] == 8
    assert rows["unknown_catalyst_winner"]["truncated_count"] == 92
    assert rows["missed_opportunity"]["eligible_count"] == 30
    assert rows["missed_opportunity"]["detail_rows_available"] == 12
    assert rows["missed_opportunity"]["selected_count"] == 8
    assert rows["missed_opportunity"]["truncated_count"] == 22
    assert rows["missed_opportunity"]["source_rows_truncated"] is True
    assert first["queue_truncated"] is True


def test_missing_data_is_not_mislabeled_as_inconsistent_data() -> None:
    idea = _idea("missing", actionability=50.0)
    idea.pop("replay_data_quality_mode")
    idea.pop("baseline_warm")
    idea["decision_projection"] = {}
    queue = _build([idea], [_episode(idea, 0.03)])
    row = next(
        item for item in queue["categories"]
        if item["category"] == "inconsistent_data_quality"
    )

    assert row["eligible_count"] == 0
    assert row["selection_status"] == "zero_sample"


def test_invalid_identity_and_protocol_drift_fail_closed() -> None:
    with pytest.raises(ValueError, match="run fingerprint invalid"):
        build_targeted_review_queue([], {"episodes": []}, {}, {}, run_fingerprint="bad")

    idea = _idea("drift", actionability=50.0)
    analysis = _analysis([])
    analysis["protocol_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="protocol identity drift"):
        _build([idea], [_episode(idea, 0.01)], analysis)

    invalid_episode = _episode(idea, 0.01)
    invalid_episode["episode_digest"] = "not-a-digest"
    with pytest.raises(ValueError, match="episode_digest invalid"):
        _build([idea], [invalid_episode])


def test_duplicate_episode_identity_drift_fails_closed() -> None:
    idea = _idea("duplicate", actionability=50.0)
    initial = _episode(idea, 0.01)
    changed = _episode(idea, -0.20)

    with pytest.raises(ValueError, match="duplicate episode drift"):
        _build([idea], [initial, changed])
