"""Offline observed-price producer tests for Event Alpha outcomes."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.artifacts import paths as event_artifact_paths
from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.outcomes import observed_outcome_builder as builder
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_discovery"
    / "observed_outcome_dense_ohlcv.json"
)
OBSERVED_AT = datetime(2026, 6, 1, 12, 7, tzinfo=timezone.utc)
FULL_EVALUATION = datetime(2026, 6, 8, 12, 20, tzinfo=timezone.utc)


def _fixture_rows() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "event_alpha_observed_ohlcv_fixture_v1"
    assert payload["candidate_observed_at"] == "2026-06-01T12:07:00Z"
    return [dict(row) for row in payload["rows"]]


def _observed_rows() -> list[dict[str, object]]:
    rows = _fixture_rows()
    for row in rows:
        row["source"] = "binance_ohlcv"
        row["observation_id"] = str(row["observation_id"]).replace(
            "fixture:testobs:", "binance:testobs:"
        )
    return rows


def _candidate(*, lane: str = "EARLY_LONG_RESEARCH") -> dict[str, object]:
    return {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": "observed-builder-run",
        "profile": "fixture",
        "artifact_namespace": "observed-outcome-builder",
        "candidate_id": "candidate-testobs",
        "core_opportunity_id": "core-testobs",
        "observed_at": OBSERVED_AT.isoformat(),
        "symbol": "TESTOBS",
        "coin_id": "test-observed",
        "opportunity_type": lane,
        "provider": "fixture-provider",
        "source_origin": "official_exchange",
        "source_pack": "listing_pack",
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }


def _core(*, lane: str = "EARLY_LONG_RESEARCH") -> dict[str, object]:
    return {
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "observed-builder-run",
        "profile": "fixture",
        "artifact_namespace": "observed-outcome-builder",
        "core_opportunity_id": "core-testobs",
        "generated_at": (OBSERVED_AT + timedelta(minutes=1)).isoformat(),
        "symbol": "TESTOBS",
        "coin_id": "test-observed",
        "opportunity_type": lane,
        "provider": "fixture-core-provider",
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }


def test_dense_fixture_is_deterministic_but_never_calibration_truth():
    prices = _fixture_rows()
    result = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    reversed_result = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        reversed(prices),
        evaluated_at=FULL_EVALUATION,
    )

    assert result.build_errors == ()
    assert result.produced is True
    assert result.outcome == reversed_result.outcome
    assert result.observations_supplied == result.observations_accepted == len(prices)
    row = result.outcome
    assert row is not None
    assert row["outcome_data_source"] == "synthetic_fixture"
    assert row["observation_price_provenance_status"] == "synthetic_fixture"
    assert row["calibration_eligible"] is False
    assert "synthetic_fixture" in row["calibration_ineligible_reasons"]
    assert row["include_in_performance"] is False
    assert row["validation_status"] == "inconclusive"
    assert schema_v1.validate_row_against_schema(row, "outcome_row_v1") == []


def test_explicit_observed_lineage_builds_exact_provenance_complete_outcome():
    prices = _observed_rows()
    result = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=FULL_EVALUATION,
        price_data_kind="observed_market_prices",
    )
    row = result.outcome
    assert row is not None
    assert row["calibration_eligible"] is True
    assert row["calibration_ineligible_reasons"] == []
    assert row["include_in_performance"] is True
    assert row["primary_horizon"] == "3d"
    assert row["validation_status"] == "validated"
    assert row["observation_price_observed_at"] == "2026-06-01T12:00:00+00:00"
    assert row["observation_price_id"] == "binance:testobs:20260601T120000Z"
    assert row["price_at_observation"] == 104.8
    expected_times = {
        "15m": "2026-06-01T12:30:00+00:00",
        "1h": "2026-06-01T13:15:00+00:00",
        "4h": "2026-06-01T16:15:00+00:00",
        "24h": "2026-06-02T12:15:00+00:00",
        "3d": "2026-06-04T12:15:00+00:00",
        "7d": "2026-06-08T12:15:00+00:00",
    }
    observed_ids = {row["observation_price_id"]}
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        metadata = row["horizon_metadata"][horizon]
        assert metadata["price_observed_at"] == expected_times[horizon]
        assert metadata["price_source"] == "binance_ohlcv"
        assert metadata["price_observation_id"] not in observed_ids
        observed_ids.add(metadata["price_observation_id"])
        recomputed = metadata["price_at_horizon"] / row["price_at_observation"] - 1.0
        assert row["return_by_horizon"][horizon] == recomputed
    assert outcome_eligibility.validate_contract(row) == []
    assert schema_v1.validate_row_against_schema(row, "outcome_row_v1") == []
    assert row["research_only"] is True
    assert row["no_send_rehearsal"] is True
    assert all(
        row[field] is False
        for field in (
            "sent",
            "normal_rsi_signal_written",
            "triggered_fade_created",
            "paper_trade_created",
            "trade_created",
        )
    )


def test_observed_claim_rejects_fixture_lineage_and_projects_away_core_debug_fields():
    rejected = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        _fixture_rows(),
        evaluated_at=FULL_EVALUATION,
        price_data_kind="observed_market_prices",
    )
    assert rejected.outcome is None
    assert rejected.build_errors == ("synthetic_lineage_claimed_observed",)

    core = _core()
    core["card_path_abs_debug"] = "/private/tmp/secret-machine-path/card.md"
    result = builder.build_observed_outcome(
        [_candidate()],
        [core],
        _fixture_rows(),
        evaluated_at=FULL_EVALUATION,
    )
    assert result.outcome is not None
    assert not any(
        key.startswith("core_") and key != "core_opportunity_id"
        for key in result.outcome
    )
    assert not any(key.endswith("_abs_debug") for key in result.outcome)
    assert event_artifact_paths.has_operator_absolute_path(result.outcome) is False


def test_primary_horizon_mapping_is_public_literal_and_fail_closed():
    assert outcome_eligibility.primary_horizon_for_lane("EARLY_LONG_RESEARCH") == "3d"
    for lane in (
        "CONFIRMED_LONG_RESEARCH",
        "FADE_SHORT_REVIEW",
        "RISK_ONLY",
        "UNCONFIRMED_RESEARCH",
        "DIAGNOSTIC",
    ):
        assert outcome_eligibility.primary_horizon_for_lane(lane) == "24h"
    assert outcome_eligibility.primary_horizon_for_lane("early_long_research") is None
    assert outcome_eligibility.primary_horizon_for_lane(1) is None


def test_evaluation_clock_is_required_aware_and_caps_future_closes():
    prices = _fixture_rows()
    naive = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=datetime(2026, 6, 8, 12, 20),
    )
    assert naive.outcome is None
    assert naive.build_errors == ("invalid_evaluated_at",)

    before_first_exit = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=datetime(2026, 6, 1, 12, 25, tzinfo=timezone.utc),
    )
    assert before_first_exit.build_errors == ()
    assert before_first_exit.outcome is not None
    assert before_first_exit.outcome["horizon_metadata"]["15m"]["maturity_status"] == "missing_data"
    assert before_first_exit.outcome["horizon_metadata"]["15m"]["price_observed_at"] is None
    assert before_first_exit.outcome["horizon_metadata"]["1h"]["maturity_status"] == "pending"
    assert before_first_exit.outcome["outcome_status"] == "pending"
    assert before_first_exit.outcome["calibration_eligible"] is False


def test_primary_horizon_distinguishes_pending_from_mature_missing_data():
    prices = _fixture_rows()
    pending = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=OBSERVED_AT + timedelta(hours=2),
    )
    assert pending.outcome is not None
    assert pending.outcome["outcome_status"] == "pending"
    assert "primary_horizon_pending" in pending.outcome["calibration_ineligible_reasons"]

    due = OBSERVED_AT + timedelta(days=3)
    ceiling = due + timedelta(days=1)
    without_primary_window = [
        row
        for row in prices
        if not (
            due
            <= outcome_eligibility.parse_aware_time(row["close_observed_at"])
            <= ceiling
        )
    ]
    missing = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        without_primary_window,
        evaluated_at=ceiling + timedelta(minutes=1),
    )
    assert missing.build_errors == ()
    assert missing.outcome is not None
    assert missing.outcome["outcome_status"] == "missing_data"
    assert missing.outcome["horizon_metadata"]["3d"]["maturity_status"] == "missing_data"
    assert missing.outcome["horizon_metadata"]["3d"]["price_at_horizon"] is None
    assert missing.outcome["calibration_eligible"] is False
    assert "primary_horizon_not_mature" in missing.outcome["calibration_ineligible_reasons"]


def test_entry_is_last_completed_close_and_staleness_is_bounded():
    prices = _fixture_rows()
    result = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert result.outcome is not None
    assert result.outcome["observation_price_observed_at"] == "2026-06-01T12:00:00+00:00"
    assert result.outcome["observation_price_id"] != "fixture:testobs:20260601T121500Z"

    stale_prices = [
        row
        for row in prices
        if outcome_eligibility.parse_aware_time(row["close_observed_at"])
        <= datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    ]
    stale = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        stale_prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert stale.outcome is None
    assert stale.build_errors == ("entry_price_stale",)


def test_exact_candidate_core_authority_is_unique_and_context_bound():
    prices = _fixture_rows()
    duplicate_candidate = builder.build_observed_outcome(
        [_candidate(), _candidate()],
        [_core()],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert duplicate_candidate.outcome is None
    assert duplicate_candidate.build_errors == ("candidate_authority_count_invalid",)

    duplicate_core = builder.build_observed_outcome(
        [_candidate()],
        [_core(), _core()],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert duplicate_core.outcome is None
    assert duplicate_core.build_errors == ("core_authority_count_invalid",)

    wrong_context = _core()
    wrong_context["run_id"] = "other-run"
    unmatched = builder.build_observed_outcome(
        [_candidate()],
        [wrong_context],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert unmatched.outcome is None
    assert unmatched.build_errors == ("core_authority_count_invalid",)

    mismatched_lane = builder.build_observed_outcome(
        [_candidate()],
        [_core(lane="RISK_ONLY")],
        prices,
        evaluated_at=FULL_EVALUATION,
    )
    assert mismatched_lane.outcome is None
    assert mismatched_lane.build_errors == ("candidate_core_attribution_mismatch",)


def test_malformed_or_ambiguous_close_lineage_fails_closed():
    prices = _fixture_rows()
    duplicate = deepcopy(prices[0])
    duplicate["close_observed_at"] = prices[1]["close_observed_at"]
    poisoned = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        [*prices, duplicate],
        evaluated_at=FULL_EVALUATION,
    )
    assert poisoned.outcome is None
    assert set(poisoned.build_errors) == {
        "ambiguous_close_timestamp",
        "duplicate_close_observation_id",
    }

    invalid = deepcopy(prices)
    invalid[96]["close"] = True
    malformed = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        invalid,
        evaluated_at=FULL_EVALUATION,
    )
    assert malformed.outcome is None
    assert malformed.build_errors == ("invalid_close_observation",)


def test_entry_price_observed_at_is_a_canonical_contract_guard():
    result = builder.build_observed_outcome(
        [_candidate()],
        [_core()],
        _observed_rows(),
        evaluated_at=FULL_EVALUATION,
        price_data_kind="observed_market_prices",
    )
    assert result.outcome is not None
    missing = deepcopy(result.outcome)
    missing.pop("observation_price_observed_at")
    reasons = outcome_eligibility.calibration_ineligibility_reasons(missing)
    assert "missing_observation_price_observed_at" in reasons

    after_candidate = deepcopy(result.outcome)
    after_candidate["observation_price_observed_at"] = (
        OBSERVED_AT + timedelta(seconds=1)
    ).isoformat()
    assert "observation_price_after_candidate" in (
        outcome_eligibility.calibration_ineligibility_reasons(after_candidate)
    )

    after_evaluation = deepcopy(result.outcome)
    after_evaluation["outcome_evaluated_at"] = (
        OBSERVED_AT - timedelta(minutes=10)
    ).isoformat()
    assert "observation_price_after_evaluation" in (
        outcome_eligibility.calibration_ineligibility_reasons(after_evaluation)
    )

    stale = deepcopy(result.outcome)
    stale["observation_price_observed_at"] = (
        OBSERVED_AT
        - timedelta(seconds=outcome_eligibility.OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS + 1)
    ).isoformat()
    assert "observation_price_stale" in (
        outcome_eligibility.calibration_ineligibility_reasons(stale)
    )
