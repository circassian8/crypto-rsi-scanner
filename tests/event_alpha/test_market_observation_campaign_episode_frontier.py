"""Canonical all-route/all-origin coverage over frozen Decision episodes."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign_episode_frontier as frontier_module,
)
from crypto_rsi_scanner.project_health import radar_north_star
from tests.event_alpha.test_decision_episode_scorecard import (
    _START,
    _candidate,
    _core,
    _episode,
    _outcome,
    _score,
)


def _scorecard(*, empty: bool = False):
    evaluated = _START + timedelta(days=2)
    if empty:
        return _score(
            _episode([], evaluated_at=evaluated),
            [],
            [],
            [],
            evaluated_at=evaluated,
        )
    candidate = _candidate("frontier", _START)
    core = _core(candidate)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    scorecard = _score(
        _episode([candidate], evaluated_at=evaluated),
        [candidate],
        [core],
        [outcome],
        evaluated_at=evaluated,
    )
    return scorecard


def test_frontier_names_every_zero_route_and_primary_origin() -> None:
    scorecard = _scorecard()
    frontier = frontier_module.build_protocol_v2_episode_coverage_frontier(
        scorecard
    )
    representative = scorecard["representatives"][0]
    observed_route = representative["radar_route"]
    observed_origin = representative["primary_thesis_origin"]

    assert frontier["status"] == "descriptive_incomplete"
    assert frontier["episode_count"] == 1
    assert frontier["matured_episode_count"] == 1
    assert frontier["observed_route_count"] == 1
    assert frontier["zero_episode_route_count"] == 7
    assert frontier["observed_primary_origin_count"] == 1
    assert frontier["zero_episode_primary_origin_count"] == 6
    assert len(frontier["route_coverage"]) == 8
    assert len(frontier["primary_origin_coverage"]) == 7
    assert sum(row["episode_count"] for row in frontier["route_coverage"]) == 1
    assert sum(
        row["episode_count"] for row in frontier["primary_origin_coverage"]
    ) == 1
    assert observed_route not in frontier["unobserved_route_names"]
    assert observed_origin not in frontier["unobserved_primary_origin_names"]
    assert frontier["minimum_sample_policy_sealed"] is False
    assert frontier["minimum_sample_count"] is None
    assert frontier["sample_sufficiency_evaluable"] is False
    assert frontier["statistical_independence_claim"] is False
    assert frontier["cross_asset_independence_claim"] is False
    assert frontier["protocol_v2_evidence_eligible"] is False
    assert frontier["provider_calls"] == frontier["writes"] == 0
    assert (
        frontier_module.validate_protocol_v2_episode_coverage_frontier(
            frontier,
            scorecard=scorecard,
        )
        == []
    )


def test_empty_frontier_preserves_every_canonical_zero() -> None:
    scorecard = _scorecard(empty=True)
    frontier = frontier_module.build_protocol_v2_episode_coverage_frontier(
        scorecard
    )

    assert frontier["status"] == "empty"
    assert frontier["episode_count"] == 0
    assert frontier["unobserved_route_names"] == list(
        frontier_module.CANONICAL_ROUTES
    )
    assert frontier["unobserved_primary_origin_names"] == list(
        frontier_module.CANONICAL_PRIMARY_ORIGINS
    )
    assert all(row["coverage_status"] == "unobserved" for row in frontier["route_coverage"])
    assert all(
        row["episode_count"] == 0
        for row in frontier["primary_origin_coverage"]
    )


def test_frontier_fails_closed_on_count_or_source_drift() -> None:
    scorecard = _scorecard()
    frontier = frontier_module.build_protocol_v2_episode_coverage_frontier(
        scorecard
    )

    count_drift = deepcopy(frontier)
    count_drift["route_coverage"][0]["episode_count"] += 1
    errors = frontier_module.validate_protocol_v2_episode_coverage_frontier(
        count_drift,
        scorecard=scorecard,
    )
    assert "invalid_contract_digest" in errors
    assert "source_scorecard_projection_mismatch" in errors

    forged_source_schema = deepcopy(frontier)
    forged_source_schema["source_scorecard_schema_id"] = "invented_scorecard"
    forged_values = dict(forged_source_schema)
    forged_values.pop("contract_digest")
    forged_source_schema["contract_digest"] = frontier_module._digest(  # noqa: SLF001
        forged_values
    )
    errors = frontier_module.validate_protocol_v2_episode_coverage_frontier(
        forged_source_schema
    )
    assert "invalid_source_scorecard_schema_id" in errors

    forged_source_clock = deepcopy(frontier)
    forged_source_clock["source_scorecard_evaluated_at"] = "2026-07-15T17:00:00"
    forged_values = dict(forged_source_clock)
    forged_values.pop("contract_digest")
    forged_source_clock["contract_digest"] = frontier_module._digest(  # noqa: SLF001
        forged_values
    )
    errors = frontier_module.validate_protocol_v2_episode_coverage_frontier(
        forged_source_clock
    )
    assert "invalid_source_scorecard_evaluated_at" in errors

    source_drift = deepcopy(frontier)
    source_drift["source_scorecard_contract_digest"] = "0" * 64
    errors = frontier_module.validate_protocol_v2_episode_coverage_frontier(
        source_drift,
        scorecard=scorecard,
    )
    assert "invalid_contract_digest" in errors
    assert "source_scorecard_projection_mismatch" in errors


def test_frontier_rejects_a_noncanonical_source_taxonomy() -> None:
    scorecard = _scorecard()
    scorecard["exclusive_cohorts"]["radar_route"][0]["name"] = "invented_route"

    try:
        frontier_module.build_protocol_v2_episode_coverage_frontier(scorecard)
    except ValueError as exc:
        assert "episode_coverage_source_scorecard_invalid" in str(exc)
    else:  # pragma: no cover - regression assertion
        raise AssertionError("tampered scorecard was accepted")


def test_north_star_keeps_episode_frontier_descriptive_and_complete() -> None:
    payload = radar_north_star.build_north_star()
    policy = payload["protocol_v2_episode_coverage_frontier_policy"]

    assert policy["schema_id"] == frontier_module.SCHEMA_ID
    assert policy["canonical_routes"] == list(frontier_module.CANONICAL_ROUTES)
    assert policy["canonical_primary_origins"] == list(
        frontier_module.CANONICAL_PRIMARY_ORIGINS
    )
    assert policy["zero_episode_categories_explicit"] is True
    assert policy["minimum_sample_policy_sealed"] is False
    assert policy["statistical_independence_claim"] is False
    assert policy["protocol_v2_evidence_eligible"] is False
    assert policy["provider_calls"] == policy["writes"] == 0
    assert "## Protocol-v2 Episode Coverage Frontier" in (
        radar_north_star.format_north_star(payload)
    )
