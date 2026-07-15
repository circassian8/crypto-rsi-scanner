"""Closed Decision-v2 scorecard regressions over frozen anomaly episodes."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from crypto_rsi_scanner.event_alpha.outcomes import anomaly_episode_shadow
from crypto_rsi_scanner.event_alpha.outcomes import decision_episode_scorecard
from crypto_rsi_scanner.event_alpha.outcomes import decision_episode_scorecard_contract
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility
from crypto_rsi_scanner.event_alpha.outcomes.observed_outcome_builder import (
    build_observed_outcome,
)
from crypto_rsi_scanner.event_alpha.operations import market_observation_outcomes
from crypto_rsi_scanner.event_alpha.radar import decision_model
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)
from crypto_rsi_scanner.event_alpha.radar.decision_models import (
    decision_score_cohort_values,
)


_START = datetime(2026, 7, 13, 15, tzinfo=timezone.utc)


def _candidate(
    suffix: str,
    observed: datetime,
    *,
    risk: bool = False,
    legacy_lane: str = "CONFIRMED_LONG_RESEARCH",
) -> dict[str, object]:
    observed_at = observed.isoformat()
    state = "risk_off_sell_pressure" if risk else "confirmed_breakout"
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": f"run-{suffix}",
        "profile": "no_key_live",
        "artifact_namespace": f"namespace-{suffix}",
        "candidate_id": f"candidate-{suffix}",
        "core_opportunity_id": f"core-{suffix}",
        "observed_at": observed_at,
        "symbol": "SCORE",
        "coin_id": "score-token",
        "canonical_asset_id": "score-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        # Deliberately independent of the canonical Decision-v2 direction.
        "opportunity_type": legacy_lane,
        "market_state_class": state,
        "anomaly_type": state,
        "market_anomaly_id": f"market-anomaly-{suffix}",
        "market_anomaly_bucket": "selloff_risk" if risk else "high_liquidity_breakout",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_snapshot": {
            "market_data_source": "coingecko",
            "observed_at": observed_at,
            "freshness_status": "fresh",
            "market_snapshot_id": f"snapshot-{suffix}",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": -8.0 if risk else 12.0,
            "return_24h": -15.0 if risk else 20.0,
            "relative_return_vs_btc_4h": -6.0 if risk else 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.30,
            "liquidity_usd": 12_000_000.0,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
        },
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(decision_model.evaluate_radar_decision(row).to_dict())
    row["decision_projection"] = decision_model_values(row)
    assert outcome_eligibility.valid_candidate_authority(row)
    return row


def _core(candidate: dict[str, object]) -> dict[str, object]:
    row = deepcopy(candidate)
    row.update({
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": candidate["observed_at"],
        "integrated_candidate_id": candidate["candidate_id"],
    })
    assert outcome_eligibility.valid_core_authority(row)
    assert decision_model_values(row) == decision_model_values(candidate)
    return row


def _close(candidate: dict[str, object], when: datetime, price: float, suffix: str):
    return {
        "symbol": candidate["symbol"],
        "coin_id": candidate["coin_id"],
        "close_observed_at": when.isoformat(),
        "close": price,
        "source": "coingecko",
        "observation_id": f"coingecko:{suffix}",
    }


def _outcome(
    candidate: dict[str, object],
    core: dict[str, object],
    *,
    persisted_evaluated_at: datetime,
    primary_price: float | None = None,
    secondary_price: float | None = None,
    cohort_mode: str = "versioned",
) -> dict[str, object]:
    observed = outcome_eligibility.parse_aware_time(candidate["observed_at"])
    assert observed is not None
    closes = [_close(candidate, observed, 100.0, f"entry:{candidate['candidate_id']}")]
    if secondary_price is not None:
        closes.append(_close(
            candidate,
            observed + timedelta(minutes=15),
            secondary_price,
            f"15m:{candidate['candidate_id']}",
        ))
    if primary_price is not None:
        closes.append(_close(
            candidate,
            observed + timedelta(hours=24),
            primary_price,
            f"24h:{candidate['candidate_id']}",
        ))
    result = build_observed_outcome(
        [candidate],
        [core],
        closes,
        evaluated_at=persisted_evaluated_at,
        price_data_kind="observed_market_prices",
    )
    assert result.outcome is not None, result.build_errors
    row = dict(result.outcome)
    projection = decision_model_values(candidate)
    row["decision_projection"] = deepcopy(projection)
    row.update(deepcopy(projection))
    cohorts = decision_score_cohort_values(projection)
    assert cohorts is not None
    if cohort_mode == "versioned":
        row.update(cohorts)
        row["decision_score_cohort_contract_version"] = 1
    elif cohort_mode == "legacy_null":
        row["actionability_score_cohort"] = cohorts["actionability_score_cohort"]
        row["evidence_confidence_score_cohort"] = None
        row["risk_score_cohort"] = None
    elif cohort_mode == "legacy_exact":
        row.update(cohorts)
    else:
        raise AssertionError(cohort_mode)
    row.update({
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "source_artifact_namespace": candidate["artifact_namespace"],
        "campaign_outcome_ledger": True,
        "campaign_outcome_authority": "candidate_core_join",
        "campaign_core_opportunity_present": True,
        "campaign_calibration_scope": "candidate_core_joined",
    })
    assert decision_model_values(row) == projection
    assert outcome_eligibility.validate_contract(row) == []
    return row


def _episode(candidates: list[dict[str, object]], *, evaluated_at: datetime):
    records = []
    for candidate in candidates:
        identity = outcome_eligibility.build_outcome_identity_fields(candidate)
        projection = decision_model_values(candidate)
        records.append({
            "artifact_namespace": candidate["artifact_namespace"],
            "run_id": candidate["run_id"],
            "candidate_id": candidate["candidate_id"],
            "outcome_identity_key": identity["outcome_identity_key"],
            "market_anomaly_id": candidate["market_anomaly_id"],
            "canonical_asset_id": candidate["canonical_asset_id"],
            "observed_at": candidate["observed_at"],
            "outcome_evidence_status": "unavailable",
            "outcome_evidence_reasons": ["outcome_not_joined_for_partition"],
            "primary_horizon_return": None,
            "radar_route": projection["radar_route"],
            "anomaly_type": candidate["anomaly_type"],
            "directional_bias": projection["directional_bias"],
        })
    return anomaly_episode_shadow.build_shadow_anomaly_episodes(
        records,
        evaluated_at=evaluated_at,
    )


def _score(
    episode: dict[str, object],
    candidates: list[dict[str, object]],
    cores: list[dict[str, object]],
    outcomes: list[dict[str, object]],
    *,
    evaluated_at: datetime,
):
    rows_by_role = {
        "candidate": candidates,
        "core": cores,
        "outcome": outcomes,
    }
    artifacts = []
    for role, rows in rows_by_role.items():
        encoded_rows = sorted(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            for row in rows
        )
        raw = b"".join(row + b"\n" for row in encoded_rows)
        artifacts.append({
            "source_role": role,
            "artifact_namespace": (
                "radar_market_history_cache"
                if role == "outcome"
                else f"scorecard-{role}-snapshot"
            ),
            "run_id": (
                "campaign-ledger-read-once"
                if role == "outcome"
                else f"scorecard-{role}-read-once"
            ),
            "artifact_name": f"{role}-rows.jsonl",
            "artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "artifact_size_bytes": len(raw),
            "row_count": len(rows),
            "binding_source": "unit_test_read_once_bytes",
        })
    candidate_by_identity = {
        (candidate["artifact_namespace"], candidate["candidate_id"]): candidate
        for candidate in candidates
    }
    validations = []
    for outcome in outcomes:
        candidate = candidate_by_identity[
            (outcome["artifact_namespace"], outcome["candidate_id"])
        ]
        result = market_observation_outcomes.campaign_ledger_outcome_validation(
            outcome,
            candidate,
            namespace=str(candidate["artifact_namespace"]),
        )
        validations.append({
            "schema_id": (
                "event_alpha.campaign_ledger_outcome_validation_binding"
            ),
            "schema_version": 1,
            "artifact_namespace": outcome["artifact_namespace"],
            "candidate_id": outcome["candidate_id"],
            "outcome_identity_key": outcome["outcome_identity_key"],
            "outcome_row_digest": hashlib.sha256(json.dumps(
                outcome,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()).hexdigest(),
            "valid": result.valid,
            "reasons": list(result.reasons),
            "score_cohort_status": result.score_cohort_status,
            "score_cohort_reason": result.score_cohort_reason,
            "canonical_score_cohorts": dict(result.canonical_score_cohorts),
        })
    return decision_episode_scorecard.build_decision_episode_scorecard(
        episode,
        candidates,
        cores,
        outcomes,
        evaluated_at=evaluated_at,
        source_artifact_bindings=artifacts,
        outcome_validation_bindings=validations,
    )


def test_legacy_long_lane_cannot_override_canonical_risk_direction():
    candidate = _candidate("risk", _START, risk=True)
    core = _core(candidate)
    evaluated = _START + timedelta(days=2)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=90.0,
        cohort_mode="legacy_null",
    )
    episode = _episode([candidate], evaluated_at=evaluated)

    scorecard = _score(
        episode,
        [candidate],
        [core],
        [outcome],
        evaluated_at=evaluated,
    )
    representative = scorecard["representatives"][0]

    assert candidate["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert representative["directional_bias"] == "risk"
    assert representative["direction_alignment"] == "aligned"
    assert representative["outcome_state"] == "matured"
    assert representative["outcome_cohort_persistence_status"] == (
        "legacy_null_derived_from_canonical_scores"
    )
    assert representative["declared_outcome_cohorts"] == {
        "decision_score_cohort_contract_version": None,
        "actionability_score_cohort": representative["actionability_score_cohort"],
        "evidence_confidence_score_cohort": None,
        "risk_score_cohort": None,
    }
    assert representative["canonical_score_cohorts"] == {
        "actionability_score_cohort": representative["actionability_score_cohort"],
        "evidence_confidence_score_cohort": representative[
            "evidence_confidence_score_cohort"
        ],
        "risk_score_cohort": representative["risk_score_cohort"],
    }
    assert scorecard["policy_conclusion"] == "insufficient_for_policy_change"
    assert scorecard["research_only"] is True
    assert scorecard["routing_changes"] == scorecard["threshold_changes"] == 0
    assert decision_episode_scorecard.validate_contract(
        scorecard,
        episode_value=episode,
    ) == []


def test_secondary_maturity_never_promotes_primary_horizon_to_matured():
    candidate = _candidate("secondary", _START)
    core = _core(candidate)
    persisted = _START + timedelta(hours=1)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=persisted,
        secondary_price=105.0,
    )
    episode = _episode([candidate], evaluated_at=persisted)

    scorecard = _score(
        episode,
        [candidate],
        [core],
        [outcome],
        evaluated_at=persisted,
    )

    assert outcome["return_by_horizon"]["15m"] == pytest.approx(0.05)
    assert scorecard["outcome_state_counts"]["not_due"] == 1
    assert scorecard["matured_episode_count"] == 0
    assert scorecard["representatives"][0]["primary_horizon_return"] is None


def test_due_primary_without_price_is_explicitly_due_missing():
    candidate = _candidate("missing", _START)
    core = _core(candidate)
    persisted = _START + timedelta(hours=1)
    external = _START + timedelta(days=2)
    outcome = _outcome(candidate, core, persisted_evaluated_at=persisted)
    episode = _episode([candidate], evaluated_at=external)

    scorecard = _score(
        episode,
        [candidate],
        [core],
        [outcome],
        evaluated_at=external,
    )

    assert scorecard["outcome_state_counts"]["due_missing_price"] == 1
    assert scorecard["representatives"][0]["direction_alignment"] == (
        "not_evaluated"
    )


def test_repeat_with_mature_outcome_cannot_replace_fixed_representative():
    first = _candidate("first", _START)
    repeat = _candidate("repeat", _START + timedelta(hours=6))
    first_core, repeat_core = _core(first), _core(repeat)
    external = _START + timedelta(days=2)
    first_outcome = _outcome(
        first,
        first_core,
        persisted_evaluated_at=_START + timedelta(hours=1),
    )
    repeat_outcome = _outcome(
        repeat,
        repeat_core,
        persisted_evaluated_at=external,
        primary_price=110.0,
    )
    episode = _episode([repeat, first], evaluated_at=external)

    scorecard = _score(
        episode,
        [repeat, first],
        [repeat_core, first_core],
        [repeat_outcome, first_outcome],
        evaluated_at=external,
    )

    assert episode["primary_episode_count"] == 1
    assert episode["primary_repeat_member_count"] == 1
    assert scorecard["representative_count"] == 1
    assert scorecard["representatives"][0]["candidate_id"] == first["candidate_id"]
    assert scorecard["representatives"][0]["outcome_state"] == "due_missing_price"


def test_duplicate_outcome_authority_fails_closed_even_when_bytes_match():
    candidate = _candidate("duplicate", _START)
    core = _core(candidate)
    evaluated = _START + timedelta(days=2)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    episode = _episode([candidate], evaluated_at=evaluated)

    scorecard = _score(
        episode,
        [candidate],
        [core],
        [outcome, deepcopy(outcome)],
        evaluated_at=evaluated,
    )

    representative = scorecard["representatives"][0]
    assert representative["outcome_state"] == "contract_excluded"
    assert representative["contract_exclusion_reasons"] == [
        "outcome_authority_ambiguous"
    ]


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("core_projection", "core_decision_projection_mismatch"),
        ("core_identity", "core_integrated_candidate_id_mismatch"),
        ("outcome_projection", "outcome_decision_projection_mismatch"),
        ("versioned_cohort", "versioned_decision_score_cohort_mismatch"),
    ),
)
def test_authority_and_cohort_drift_fail_closed(mutation: str, expected_reason: str):
    candidate = _candidate(f"drift-{mutation}", _START)
    core = _core(candidate)
    evaluated = _START + timedelta(days=2)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    if mutation == "core_projection":
        core["actionability_score"] = float(core["actionability_score"]) - 1.0
    elif mutation == "core_identity":
        core["integrated_candidate_id"] = "different-candidate"
    elif mutation == "outcome_projection":
        outcome["risk_score"] = float(outcome["risk_score"]) + 1.0
    else:
        outcome["risk_score_cohort"] = "80_100"
    episode = _episode([candidate], evaluated_at=evaluated)

    scorecard = _score(
        episode,
        [candidate],
        [core],
        [outcome],
        evaluated_at=evaluated,
    )

    representative = scorecard["representatives"][0]
    assert representative["outcome_state"] == "contract_excluded"
    assert expected_reason in representative["contract_exclusion_reasons"]


def test_input_order_is_digest_stable_and_contract_tampering_is_detected():
    first = _candidate("stable-a", _START)
    second = _candidate("stable-b", _START + timedelta(days=2))
    cores = [_core(first), _core(second)]
    evaluated = _START + timedelta(days=4)
    outcomes = [
        _outcome(
            first,
            cores[0],
            persisted_evaluated_at=evaluated,
            primary_price=105.0,
            cohort_mode="legacy_exact",
        ),
        _outcome(
            second,
            cores[1],
            persisted_evaluated_at=evaluated,
            primary_price=95.0,
        ),
    ]
    episode = _episode([second, first], evaluated_at=evaluated)

    left = _score(
        episode,
        [first, second],
        cores,
        outcomes,
        evaluated_at=evaluated,
    )
    right = _score(
        episode,
        [second, first],
        list(reversed(cores)),
        list(reversed(outcomes)),
        evaluated_at=evaluated,
    )

    assert left == right
    tampered = deepcopy(left)
    tampered["matured_episode_count"] += 1
    errors = decision_episode_scorecard.validate_contract(
        tampered,
        episode_value=episode,
    )
    assert "matured_episode_count_mismatch" in errors
    assert "invalid_contract_digest" in errors


def test_invalid_episode_contract_is_rejected_before_joining_rows():
    episode = _episode([], evaluated_at=_START)
    episode["primary_episode_count"] = 1

    with pytest.raises(ValueError, match="invalid_episode_contract"):
        _score(episode, [], [], [], evaluated_at=_START)


def test_rehashed_semantic_forgery_is_rejected_against_candidate_authority():
    candidate = _candidate("forged", _START)
    core = _core(candidate)
    evaluated = _START + timedelta(days=2)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    episode = _episode([candidate], evaluated_at=evaluated)
    forged = deepcopy(_score(
        episode,
        [candidate],
        [core],
        [outcome],
        evaluated_at=evaluated,
    ))
    representative = forged["representatives"][0]
    representative["risk_score"] = 90.0
    representative["risk_score_cohort"] = "80_100"
    representative["canonical_score_cohorts"]["risk_score_cohort"] = "80_100"
    representative["direction_alignment"] = "opposed"
    representative["representative_digest"] = decision_episode_scorecard._digest({
        key: value
        for key, value in representative.items()
        if key != "representative_digest"
    })
    forged["direction_alignment_counts"] = decision_episode_scorecard._closed_counts(
        (row["direction_alignment"] for row in forged["representatives"]),
        decision_episode_scorecard.DIRECTION_ALIGNMENTS,
    )
    forged["exclusive_cohorts"] = decision_episode_scorecard._exclusive_cohorts(
        forged["representatives"]
    )
    forged["nonexclusive_thesis_origin_cohorts"] = (
        decision_episode_scorecard._origin_cohorts(forged["representatives"])
    )
    forged["contract_digest"] = decision_episode_scorecard._digest({
        key: value for key, value in forged.items() if key != "contract_digest"
    })

    errors = decision_episode_scorecard.validate_contract(
        forged,
        episode_value=episode,
        candidate_rows=[candidate],
    )

    assert "representative_0:direction_alignment_mismatch" in errors
    assert "representative_0:candidate_decision_values_mismatch" in errors


def test_source_binding_identity_allows_equal_empty_artifacts_across_runs():
    empty_digest = hashlib.sha256(b"").hexdigest()
    rows = [
        {
            "source_role": role,
            "artifact_namespace": namespace,
            "run_id": run_id,
            "artifact_name": f"{role}.jsonl",
            "artifact_sha256": empty_digest,
            "artifact_size_bytes": 0,
            "row_count": 0,
            "binding_source": "read_once_test_binding",
        }
        for role, namespace, run_id in (
            ("candidate", "generation-a", "run-a"),
            ("candidate", "generation-b", "run-b"),
            ("core", "generation-a", "run-a"),
            ("outcome", "history-cache", "campaign-ledger-snapshot"),
        )
    ]
    rows = decision_episode_scorecard_contract.materialize_source_artifact_bindings(
        rows
    )

    assert decision_episode_scorecard_contract.source_artifact_binding_errors(
        rows,
        row_counts={"candidate": 0, "core": 0, "outcome": 0},
    ) == []
    malformed = deepcopy(rows)
    malformed[0].pop("run_id")
    assert any(
        "run_id" in error
        for error in decision_episode_scorecard_contract.source_artifact_binding_errors(
            malformed,
            row_counts={"candidate": 0, "core": 0, "outcome": 0},
        )
    )


def test_zero_row_role_never_requires_a_synthetic_source_binding():
    assert decision_episode_scorecard_contract.source_artifact_binding_errors(
        [],
        row_counts={"candidate": 0, "core": 0, "outcome": 0},
    ) == []


def test_invalid_ledger_binding_preserves_missing_identity_without_invention():
    row_digest = hashlib.sha256(b"malformed-ledger-row").hexdigest()
    binding = {
        "schema_id": "event_alpha.campaign_ledger_outcome_validation_binding",
        "schema_version": 1,
        "artifact_namespace": None,
        "candidate_id": None,
        "outcome_identity_key": None,
        "outcome_row_digest": row_digest,
        "valid": False,
        "reasons": ["campaign_outcome_candidate_binding_missing"],
        "score_cohort_status": "invalid",
        "score_cohort_reason": "canonical_candidate_missing",
        "canonical_score_cohorts": {
            "actionability_score_cohort": "unknown",
            "evidence_confidence_score_cohort": "unknown",
            "risk_score_cohort": "unknown",
        },
    }

    assert decision_episode_scorecard_contract.outcome_validation_binding_errors(
        [binding]
    ) == []
