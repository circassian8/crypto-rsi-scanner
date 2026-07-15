"""Pure contract tests for fixed-window shadow anomaly episodes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.outcomes import anomaly_episode_shadow


_START = datetime(2026, 7, 15, 0, tzinfo=timezone.utc)
_EVALUATED = _START + timedelta(days=7)
_FALSE_FLAGS = (
    "routing_eligible",
    "priority_eligible",
    "decision_score_eligible",
    "score_adjustment_eligible",
    "calibration_eligible",
    "threshold_change_eligible",
    "auto_apply",
)


def _record(
    hour: float,
    *,
    suffix: str,
    asset: str = "asset-alpha",
    route: str = "dashboard_watch",
    anomaly_type: str = "confirmed_breakout",
    direction: str = "bullish",
    outcome_status: str | None = "unavailable",
    primary_return: float | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "artifact_namespace": f"namespace-{suffix}",
        "run_id": f"run-{suffix}",
        "candidate_id": f"candidate-{suffix}",
        "outcome_identity_key": hashlib.sha256(
            f"outcome-{suffix}".encode("utf-8")
        ).hexdigest(),
        "market_anomaly_id": f"anomaly-{suffix}",
        "canonical_asset_id": asset,
        "observed_at": (_START + timedelta(hours=hour)).isoformat(),
        "radar_route": route,
        "anomaly_type": anomaly_type,
        "directional_bias": direction,
    }
    if outcome_status is not None:
        row["outcome_evidence_status"] = outcome_status
    if primary_return is not None:
        row["primary_horizon_return"] = primary_return
    return row


def _build(records):
    return anomaly_episode_shadow.build_shadow_anomaly_episodes(
        records,
        evaluated_at=_EVALUATED,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _identity(ref: dict[str, object]) -> dict[str, object]:
    return {
        key: ref[key]
        for key in (
            "artifact_namespace",
            "run_id",
            "candidate_id",
            "outcome_identity_key",
            "market_anomaly_id",
            "canonical_asset_id",
            "observed_at",
        )
    }


def _rehash(result: dict[str, object]) -> None:
    result["contract_digest"] = _digest({
        key: value for key, value in result.items() if key != "contract_digest"
    })


def _rehash_episode(episode: dict[str, object]) -> None:
    episode["episode_digest"] = _digest(
        anomaly_episode_shadow._episode_digest_values(episode)  # noqa: SLF001
    )


def test_fixed_start_half_open_windows_and_sensitivity_counts():
    rows = [
        _record(0, suffix="00", route="dashboard_watch"),
        _record(11, suffix="11", route="rapid_market_anomaly"),
        _record(23, suffix="23", anomaly_type="late_momentum"),
        _record(24, suffix="24", direction="bearish"),
        _record(35, suffix="35", route="risk_watch"),
        _record(48, suffix="48", anomaly_type="post_event_fade_setup"),
    ]

    result = _build(rows)

    assert result["method"] == "fixed_start_window_declustering"
    assert result["boundary_rule"] == (
        "member_observed_at_lt_episode_start_plus_window"
    )
    assert result["primary_episode_count"] == 3
    assert result["status"] == "ready"
    assert result["evaluated_at"] == _EVALUATED.isoformat()
    assert result["sensitivity_counts"] == {
        "12h": {"episode_count": 4, "repeat_member_count": 2},
        "24h": {"episode_count": 3, "repeat_member_count": 3},
        "48h": {"episode_count": 2, "repeat_member_count": 4},
    }
    assert result["primary_repeat_member_count"] == 3
    assert [row["member_count"] for row in result["episodes"]] == [3, 2, 1]
    assert result["episodes"][0]["representative"]["candidate_id"] == (
        "candidate-00"
    )
    assert result["episodes"][0]["representative"]["radar_route"] == (
        "dashboard_watch"
    )
    assert result["episodes"][1]["episode_start_at"] == rows[3]["observed_at"]
    assert result["episodes"][0]["last_member_observed_at"] == rows[2]["observed_at"]
    assert result["episodes"][0]["window_end_exclusive_at"] == rows[3]["observed_at"]


def test_fixed_start_anchor_prevents_previous_member_chaining():
    result = _build([
        _record(0, suffix="start"),
        _record(23, suffix="inside"),
        _record(46, suffix="outside"),
    ])

    assert result["primary_episode_count"] == 2
    assert [episode["member_count"] for episode in result["episodes"]] == [2, 1]
    assert result["episodes"][1]["representative"]["candidate_id"] == (
        "candidate-outside"
    )


def test_half_open_boundary_keeps_microsecond_before_and_splits_exact_boundary():
    before_boundary = _record(24, suffix="before-boundary")
    before_boundary["observed_at"] = (
        _START + timedelta(hours=24) - timedelta(microseconds=1)
    ).isoformat()

    result = _build([
        _record(0, suffix="anchor"),
        before_boundary,
        _record(24, suffix="exact-boundary"),
    ])

    assert result["primary_episode_count"] == 2
    assert [episode["member_count"] for episode in result["episodes"]] == [2, 1]
    assert result["episodes"][1]["episode_start_at"] == (
        _START + timedelta(hours=24)
    ).isoformat()


def test_exact_canonical_asset_identity_is_not_case_folded_or_aliased():
    result = _build([
        _record(0, suffix="lower", asset="asset-alpha"),
        _record(1, suffix="upper", asset="Asset-Alpha"),
    ])

    assert result["primary_episode_count"] == 2
    assert {episode["canonical_asset_id"] for episode in result["episodes"]} == {
        "asset-alpha",
        "Asset-Alpha",
    }


def test_input_order_and_mutation_do_not_change_deterministic_contract():
    rows = [
        _record(23, suffix="late"),
        _record(0, suffix="first"),
        _record(4, suffix="middle", outcome_status="available", primary_return=0.1),
    ]
    before = deepcopy(rows)

    forward = _build(rows)
    reverse = _build(reversed(rows))

    assert rows == before
    assert forward == reverse
    assert len(forward["contract_digest"]) == 64
    episode = forward["episodes"][0]
    assert episode["episode_id"] == (
        "shadow-anomaly-episode-v1:" + episode["member_binding_digest"]
    )
    assert len(episode["episode_digest"]) == 64


def test_malformed_and_ambiguous_structural_bindings_are_explicitly_excluded():
    duplicate_a = _record(0, suffix="duplicate-a")
    duplicate_b = _record(1, suffix="duplicate-b")
    duplicate_b["artifact_namespace"] = duplicate_a["artifact_namespace"]
    duplicate_b["run_id"] = duplicate_a["run_id"]
    duplicate_b["candidate_id"] = duplicate_a["candidate_id"]
    malformed = _record(2, suffix="malformed")
    malformed["observed_at"] = "2026-07-15T02:00:00"
    missing = _record(3, suffix="missing")
    missing.pop("outcome_identity_key")
    malformed_outcome_identity = _record(4, suffix="bad-outcome-key")
    malformed_outcome_identity["outcome_identity_key"] = "opaque-outcome-id"

    result = _build([
        _record(5, suffix="valid"),
        duplicate_a,
        duplicate_b,
        malformed,
        missing,
        malformed_outcome_identity,
        None,  # type: ignore[list-item]
    ])

    assert result["records_supplied"] == 7
    assert result["records_eligible"] == 1
    assert result["records_excluded"] == 6
    assert result["status"] == "partial"
    assert result["exclusion_reason_counts"] == {
        "ambiguous_candidate_binding": 2,
        "invalid_observed_at": 1,
        "invalid_outcome_identity_key": 2,
        "record_not_mapping": 1,
    }
    assert result["exclusion_refs"]
    assert all(len(row["record_digest"]) == 64 for row in result["exclusion_refs"])


def test_outcome_and_anomaly_identity_collisions_are_structural_exclusions():
    outcome_a = _record(0, suffix="outcome-a")
    outcome_b = _record(1, suffix="outcome-b")
    outcome_b["artifact_namespace"] = outcome_a["artifact_namespace"]
    outcome_b["run_id"] = outcome_a["run_id"]
    outcome_b["outcome_identity_key"] = outcome_a["outcome_identity_key"]
    outcome_result = _build([
        outcome_a,
        outcome_b,
    ])

    anomaly_a = _record(0, suffix="anomaly-a")
    anomaly_b = _record(1, suffix="anomaly-b")
    anomaly_b["artifact_namespace"] = anomaly_a["artifact_namespace"]
    anomaly_b["run_id"] = anomaly_a["run_id"]
    anomaly_b["market_anomaly_id"] = anomaly_a["market_anomaly_id"]
    anomaly_result = _build([
        anomaly_a,
        anomaly_b,
    ])

    assert outcome_result["records_eligible"] == 0
    assert outcome_result["exclusion_reason_counts"] == {
        "ambiguous_outcome_binding": 2
    }
    assert anomaly_result["records_eligible"] == 0
    assert anomaly_result["exclusion_reason_counts"] == {
        "ambiguous_anomaly_binding": 2
    }


def test_outcome_identity_key_requires_canonical_lowercase_sha256_everywhere():
    malformed = _record(0, suffix="malformed-outcome-key")
    malformed["outcome_identity_key"] = "A" * 64

    result = _build([malformed])

    assert result["records_eligible"] == 0
    assert result["exclusion_reason_counts"] == {
        "invalid_outcome_identity_key": 1
    }

    valid = _build([_record(0, suffix="valid-outcome-key")])
    forged = deepcopy(valid)
    forged["episodes"][0]["member_refs"][0]["outcome_identity_key"] = "a" * 63
    forged["episodes"][0]["representative"] = forged["episodes"][0][
        "member_refs"
    ][0]

    errors = anomaly_episode_shadow.validate_contract(forged)
    assert "episode_0:member_ref_0:invalid_outcome_identity_key" in errors


def test_outcome_evidence_status_is_fail_closed_but_never_changes_membership():
    first = _record(
        0,
        suffix="first-ambiguous",
        outcome_status="ambiguous",
        primary_return=float("nan"),
    )
    second = _record(
        6,
        suffix="later-matured",
        outcome_status="available",
        primary_return=0.25,
    )

    result = _build([second, first])

    assert result["records_eligible"] == 2
    assert result["primary_episode_count"] == 1
    episode = result["episodes"][0]
    assert episode["representative"]["candidate_id"] == "candidate-first-ambiguous"
    assert episode["representative"]["outcome_evidence_status"] == "ambiguous"
    assert episode["representative"]["primary_horizon_return"] is None
    assert episode["outcome_evidence_status_counts"] == {
        "ambiguous": 1,
        "available": 1,
    }
    json.dumps(result, allow_nan=False)


def test_optional_context_and_outcome_mutations_do_not_change_episode_identity():
    baseline = [
        _record(0, suffix="stable-first"),
        _record(5, suffix="stable-second"),
    ]
    mutated = deepcopy(baseline)
    mutated[0].update({
        "radar_route": "rapid_market_anomaly",
        "anomaly_type": "post_event_fade_setup",
        "directional_bias": "bearish",
        "outcome_evidence_status": "ambiguous",
        "outcome_evidence_reasons": ["duplicate_outcome_identity"],
        "primary_horizon_return": 99.0,
    })
    mutated[1].update({
        "radar_route": "risk_watch",
        "outcome_evidence_status": "available",
        "outcome_evidence_reasons": ["outcome_contract_invalid"],
        "primary_horizon_return": -0.5,
    })

    original_result = _build(baseline)
    mutated_result = _build(mutated)
    original_episode = original_result["episodes"][0]
    mutated_episode = mutated_result["episodes"][0]

    assert original_result["input_binding_digest"] == mutated_result[
        "input_binding_digest"
    ]
    assert original_episode["episode_id"] == mutated_episode["episode_id"]
    assert original_episode["member_binding_digest"] == mutated_episode[
        "member_binding_digest"
    ]
    assert original_episode["episode_digest"] == mutated_episode["episode_digest"]
    assert [row["candidate_id"] for row in original_episode["member_refs"]] == [
        row["candidate_id"] for row in mutated_episode["member_refs"]
    ]
    assert mutated_episode["representative"]["outcome_evidence_reasons"] == [
        "duplicate_outcome_identity",
        "nonavailable_outcome_value_ignored",
    ]


def test_available_outcome_without_finite_value_downgrades_without_exclusion():
    result = _build([
        _record(
            0,
            suffix="invalid-outcome",
            outcome_status="available",
            primary_return=float("inf"),
        )
    ])

    representative = result["episodes"][0]["representative"]
    assert result["records_eligible"] == 1
    assert representative["outcome_evidence_status"] == "unavailable"
    assert representative["primary_horizon_return"] is None
    assert representative["outcome_evidence_reasons"] == [
        "available_outcome_missing_finite_primary_return"
    ]


def test_member_references_are_complete_within_hard_bound():
    rows = [
        _record(
            index * (23.0 / (anomaly_episode_shadow.MAX_MEMBER_REFS - 1)),
            suffix=f"bounded-{index:03d}",
        )
        for index in range(anomaly_episode_shadow.MAX_MEMBER_REFS)
    ]
    result = _build(rows)
    episode = result["episodes"][0]

    assert episode["member_count"] == len(rows)
    assert episode["member_ref_count"] == len(rows)
    assert len(episode["member_refs"]) == len(rows)
    assert episode["member_refs_truncated"] is False
    assert len(episode["member_binding_digest"]) == 64
    assert result["validation_coverage"] == {
        "member_refs": "complete_with_hard_bound",
        "max_member_refs": anomaly_episode_shadow.MAX_MEMBER_REFS,
        "exclusion_refs": "complete_with_hard_bound",
        "max_exclusion_refs": anomaly_episode_shadow.MAX_EXCLUSION_REFS,
        "full_membership_bound_by_digest": True,
        "validator_full_member_recomputation": "always",
        "validator_full_exclusion_recomputation": "always",
        "sensitivity_count_validation": "full_partition_recomputation",
        "bound_exceeded_policy": "fail_closed_without_contract",
    }

    too_many = [
        _record(
            index * (23.0 / anomaly_episode_shadow.MAX_MEMBER_REFS),
            suffix=f"overflow-{index:03d}",
        )
        for index in range(anomaly_episode_shadow.MAX_MEMBER_REFS + 1)
    ]
    with pytest.raises(ValueError, match="member bound exceeded"):
        _build(too_many)


def test_closed_shadow_policy_is_explicit_on_contract_and_episodes():
    result = _build([
        _record(0, suffix="policy")
    ])
    episode = result["episodes"][0]

    assert result["schema_id"] == "event_alpha.shadow_anomaly_episodes"
    assert result["schema_version"] == 1
    assert result["research_only"] is True
    assert result["statistical_independence_claim"] is False
    assert result["cross_asset_independence_claim"] is False
    assert episode["research_only"] is True
    assert episode["statistical_independence_claim"] is False
    assert episode["cross_asset_independence_claim"] is False
    assert all(result[field] is False for field in _FALSE_FLAGS)
    assert all(episode[field] is False for field in _FALSE_FLAGS)


def test_evaluation_clock_is_required_utc_and_future_members_are_excluded():
    with pytest.raises(ValueError, match="aware UTC"):
        anomaly_episode_shadow.build_shadow_anomaly_episodes(
            [_record(0, suffix="naive-clock")],
            evaluated_at=datetime(2026, 7, 15),
        )
    with pytest.raises(ValueError, match="aware UTC"):
        anomaly_episode_shadow.build_shadow_anomaly_episodes(
            [_record(0, suffix="offset-clock")],
            evaluated_at="2026-07-15T03:00:00+03:00",
        )

    result = anomaly_episode_shadow.build_shadow_anomaly_episodes(
        [_record(2, suffix="future")],
        evaluated_at=_START,
    )

    assert result["status"] == "partial"
    assert result["records_eligible"] == 0
    assert result["primary_episode_count"] == 0
    assert result["primary_repeat_member_count"] == 0
    assert result["sensitivity_counts"] == {
        "12h": {"episode_count": 0, "repeat_member_count": 0},
        "24h": {"episode_count": 0, "repeat_member_count": 0},
        "48h": {"episode_count": 0, "repeat_member_count": 0},
    }
    assert result["exclusion_reason_counts"] == {"future_observation": 1}


def test_extreme_time_fails_closed_without_overflow_crash():
    row = _record(0, suffix="extreme")
    row["observed_at"] = "9999-12-31T00:00:00+00:00"

    result = anomaly_episode_shadow.build_shadow_anomaly_episodes(
        [row],
        evaluated_at="9999-12-31T00:00:00+00:00",
    )

    assert result["status"] == "partial"
    assert result["records_eligible"] == 0
    assert result["exclusion_reason_counts"] == {
        "observation_window_overflow": 1
    }


def test_closed_validator_rejects_unknown_keys_counts_digests_and_boundaries():
    result = _build([
        _record(0, suffix="validate-first"),
        _record(4, suffix="validate-second"),
    ])
    assert anomaly_episode_shadow.validate_contract(result) == []

    unknown = deepcopy(result)
    unknown["invented"] = True
    assert "contract:unknown_key:invented" in (
        anomaly_episode_shadow.validate_contract(unknown)
    )

    count_drift = deepcopy(result)
    count_drift["primary_repeat_member_count"] = 0
    count_errors = anomaly_episode_shadow.validate_contract(count_drift)
    assert "primary_count_not_closed" in count_errors
    assert "invalid_contract_digest" in count_errors

    boundary_drift = deepcopy(result)
    boundary_drift["episodes"][0]["window_end_exclusive_at"] = (
        _START + timedelta(hours=23)
    ).isoformat()
    boundary_errors = anomaly_episode_shadow.validate_contract(boundary_drift)
    assert "episode_0:invalid_episode_boundary" in boundary_errors
    assert "episode_0:invalid_episode_digest" in boundary_errors

    sensitivity_drift = deepcopy(result)
    sensitivity_drift["sensitivity_counts"]["12h"] = {
        "episode_count": 0,
        "repeat_member_count": 2,
    }
    sensitivity_errors = anomaly_episode_shadow.validate_contract(sensitivity_drift)
    assert "sensitivity_episode_counts_not_monotonic" in sensitivity_errors


def test_closed_validator_rejects_builder_impossible_identity_collision():
    result = _build([
        _record(0, suffix="collision-first"),
        _record(4, suffix="collision-second"),
    ])
    episode = result["episodes"][0]
    first, second = episode["member_refs"]
    for field in ("artifact_namespace", "run_id", "candidate_id"):
        second[field] = first[field]
    second["record_digest"] = _digest(_identity(second))
    identities = [_identity(ref) for ref in episode["member_refs"]]
    episode["member_binding_digest"] = _digest(identities)
    episode["episode_id"] = (
        "shadow-anomaly-episode-v1:" + episode["member_binding_digest"]
    )
    result["input_binding_digest"] = _digest(identities)
    _rehash_episode(episode)
    _rehash(result)

    errors = anomaly_episode_shadow.validate_contract(result)

    assert "ambiguous_candidate_binding" in errors


def test_closed_validator_recomputes_outcome_and_sensitivity_summaries():
    result = _build([
        _record(0, suffix="summary-first"),
        _record(4, suffix="summary-second"),
    ])
    episode = result["episodes"][0]
    episode["outcome_evidence_status_counts"] = {"available": 2}
    result["sensitivity_counts"]["12h"] = {
        "episode_count": 2,
        "repeat_member_count": 0,
    }
    _rehash(result)

    errors = anomaly_episode_shadow.validate_contract(result)

    assert "episode_0:outcome_evidence_status_counts_not_recomputed" in errors
    assert "sensitivity_partition_mismatch" in errors


def test_closed_validator_rejects_integer_return_and_extreme_window():
    numeric = _build([
        _record(
            0,
            suffix="numeric",
            outcome_status="available",
            primary_return=1.0,
        )
    ])
    numeric_episode = numeric["episodes"][0]
    numeric_episode["representative"]["primary_horizon_return"] = 1
    numeric_episode["member_refs"][0]["primary_horizon_return"] = 1
    _rehash(numeric)
    assert "episode_0:member_ref_0:invalid_primary_horizon_return" in (
        anomaly_episode_shadow.validate_contract(numeric)
    )

    extreme = _build([_record(0, suffix="persisted-extreme")])
    extreme["evaluated_at"] = "9999-12-31T00:00:00+00:00"
    extreme_episode = extreme["episodes"][0]
    extreme_time = "9999-12-31T00:00:00+00:00"
    for ref in (
        extreme_episode["representative"],
        extreme_episode["member_refs"][0],
    ):
        ref["observed_at"] = extreme_time
        ref["record_digest"] = _digest(_identity(ref))
    identity = _identity(extreme_episode["member_refs"][0])
    extreme_episode["episode_start_at"] = extreme_time
    extreme_episode["last_member_observed_at"] = extreme_time
    extreme_episode["window_end_exclusive_at"] = extreme_time
    extreme_episode["member_binding_digest"] = _digest([identity])
    extreme_episode["episode_id"] = (
        "shadow-anomaly-episode-v1:" + extreme_episode["member_binding_digest"]
    )
    extreme["input_binding_digest"] = _digest([identity])
    _rehash_episode(extreme_episode)
    _rehash(extreme)

    extreme_errors = anomaly_episode_shadow.validate_contract(extreme)

    assert "episode_0:episode_window_overflow" in extreme_errors


def test_closed_validator_rejects_noncanonical_utc_timestamp_spellings():
    member_offset = _build([_record(0, suffix="offset-member")])
    member_episode = member_offset["episodes"][0]
    offset_observed = "2026-07-15T03:00:00+03:00"
    member_episode["representative"]["observed_at"] = offset_observed
    member_episode["member_refs"][0]["observed_at"] = offset_observed
    _rehash(member_offset)

    member_errors = anomaly_episode_shadow.validate_contract(member_offset)

    assert "episode_0:member_ref_0:observed_at_not_canonical_utc" in member_errors

    boundary_z = _build([_record(0, suffix="z-boundaries")])
    boundary_episode = boundary_z["episodes"][0]
    boundary_episode["episode_start_at"] = "2026-07-15T00:00:00Z"
    boundary_episode["last_member_observed_at"] = "2026-07-15T00:00:00Z"
    boundary_episode["window_end_exclusive_at"] = "2026-07-16T00:00:00Z"
    _rehash_episode(boundary_episode)
    _rehash(boundary_z)

    boundary_errors = anomaly_episode_shadow.validate_contract(boundary_z)

    assert "episode_0:episode_start_at_not_canonical_utc" in boundary_errors
    assert "episode_0:last_member_observed_at_not_canonical_utc" in boundary_errors
    assert "episode_0:window_end_exclusive_at_not_canonical_utc" in boundary_errors
