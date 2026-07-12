"""Focused regressions for authoritative Event Alpha outcome eligibility."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility as eligibility
from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes as outcomes
from crypto_rsi_scanner.event_alpha.radar import integrated_radar


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _observed_outcome(
    index: int = 0,
    *,
    evaluated_after: timedelta = timedelta(days=4),
    primary_horizon: str = "3d",
    label: str = "early_good",
) -> dict[str, object]:
    observed = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(seconds=index)
    evaluated = observed + evaluated_after
    identity = {
        "run_id": f"run-{index}",
        "profile": "fixture",
        "artifact_namespace": "outcome-firewall",
        "candidate_id": f"candidate-{index}",
        "core_opportunity_id": f"core-{index}",
        "observed_at": _iso(observed),
    }
    horizon_metadata: dict[str, dict[str, object]] = {}
    return_by_horizon: dict[str, float | None] = {}
    for horizon in eligibility.OUTCOME_HORIZONS:
        due = observed + timedelta(seconds=eligibility.OUTCOME_HORIZON_SECONDS[horizon])
        matured = due <= evaluated
        horizon_metadata[horizon] = {
            "due_at": _iso(due),
            "price_observed_at": _iso(due) if matured else None,
            "price_at_horizon": 10.4 if matured else None,
            "price_source": "binance_ohlcv" if matured else None,
            "price_observation_id": f"binance:{index}:{horizon}" if matured else None,
            "maturity_status": "matured" if matured else "pending",
            "provenance_status": "observed_market_prices" if matured else "missing",
        }
        return_by_horizon[horizon] = 0.04 if matured else None
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_outcome",
        **identity,
        **eligibility.build_outcome_identity_fields(identity),
        "outcome_eligibility_contract_version": (
            eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": "observed_market_prices",
        "outcome_evaluated_at": _iso(evaluated),
        "observation_price_provenance_status": "observed_market_prices",
        "price_at_observation": 10.0,
        "observation_price_source": "binance_ohlcv",
        "observation_price_id": f"binance:{index}:entry",
        "primary_horizon": primary_horizon,
        "primary_horizon_return": return_by_horizon[primary_horizon],
        "return_by_horizon": return_by_horizon,
        "horizons": dict(return_by_horizon),
        "horizon_metadata": horizon_metadata,
        "symbol": f"TEST{index}",
        "coin_id": f"test-{index}",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "provider": "candidate-provider",
        "source_origin": "official_exchange",
        "source_pack": "listing_pack",
        "outcome_status": horizon_metadata[primary_horizon]["maturity_status"],
        "outcome_label": label,
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    reasons = eligibility.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    return row


def _candidate(row: dict[str, object], **overrides: object) -> dict[str, object]:
    candidate = {
        field: row[field]
        for field in eligibility.OUTCOME_IDENTITY_FIELDS
    }
    candidate.update({
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "research_only": True,
        "symbol": row["symbol"],
        "coin_id": row["coin_id"],
        "opportunity_type": row["opportunity_type"],
        "provider": "candidate-provider",
        "source_origin": "official_exchange",
        "source_pack": "listing_pack",
    })
    candidate.update(overrides)
    return candidate


def _core(row: dict[str, object], **overrides: object) -> dict[str, object]:
    core = {
        field: row[field]
        for field in ("run_id", "profile", "artifact_namespace", "core_opportunity_id")
    }
    core.update({
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": row["observed_at"],
        "research_only": True,
        "symbol": row["symbol"],
        "coin_id": row["coin_id"],
        "opportunity_type": row["opportunity_type"],
        "provider": "core-provider",
    })
    core.update(overrides)
    return core


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_synthetic_fixture_rows_are_truthful_diagnostics_without_default_price():
    candidate = {
        "run_id": "run-synthetic",
        "profile": "fixture",
        "artifact_namespace": "outcome-firewall",
        "candidate_id": "candidate-synthetic",
        "core_opportunity_id": "core-synthetic",
        "observed_at": "2026-06-15T16:00:00+00:00",
        "symbol": "TESTLIST",
        "coin_id": "testlist",
        "opportunity_type": "EARLY_LONG_RESEARCH",
    }
    row = outcomes._outcome_row(candidate, now="2026-06-15T16:01:00+00:00")  # noqa: SLF001

    assert row["outcome_data_source"] == "synthetic_fixture"
    assert row["calibration_eligible"] is False
    assert row["calibration_ineligible_reasons"] == sorted(
        row["calibration_ineligible_reasons"]
    )
    assert "synthetic_fixture" in row["calibration_ineligible_reasons"]
    assert "horizon_return_contract_invalid" in row["calibration_ineligible_reasons"]
    assert row["primary_horizon"] == "3d"
    assert row["horizon_metadata"]["3d"]["maturity_status"] == "pending"
    assert row["outcome_status"] == "pending"
    assert row["outcome_label"] == "inconclusive"
    assert row["validation_label"] == "inconclusive"
    assert row["synthetic_diagnostic_label"] == "early_good"
    assert row["price_at_observation"] is None
    assert eligibility.validate_contract(row) == []
    assert eligibility.effective_calibration_eligible(row) is False
    assert all(
        row[field] is False
        for field in (
            "normal_rsi_signal_written",
            "triggered_fade_created",
            "paper_trade_created",
            "trade_created",
        )
    )

    late = outcomes._outcome_row(candidate, now="2026-06-20T16:00:00+00:00")  # noqa: SLF001
    assert late["horizon_metadata"]["3d"]["maturity_status"] == "missing_data"
    assert late["outcome_status"] == "missing_data"
    assert late["calibration_eligible"] is False


def test_primary_maturity_chronology_provenance_and_strict_numbers_gate_eligibility():
    valid = _observed_outcome()
    assert eligibility.validate_contract(valid) == []
    assert eligibility.effective_calibration_eligible(valid) is True

    partial = _observed_outcome(evaluated_after=timedelta(hours=1))
    assert partial["horizon_metadata"]["15m"]["maturity_status"] == "matured"
    assert partial["horizon_metadata"]["3d"]["maturity_status"] == "pending"
    assert eligibility.primary_horizon_maturation_state(partial) == "partially_matured"
    assert eligibility.effective_calibration_eligible(partial) is False

    before_due = deepcopy(valid)
    before_due["horizon_metadata"]["3d"]["price_observed_at"] = before_due["observed_at"]
    assert "primary_horizon_price_before_due" in eligibility.calibration_ineligibility_reasons(
        before_due
    )

    no_provenance = deepcopy(valid)
    no_provenance["horizon_metadata"]["3d"]["provenance_status"] = "missing"
    assert "primary_horizon_missing_provenance" in eligibility.calibration_ineligibility_reasons(
        no_provenance
    )

    for bad_value in (True, "0.04", float("nan"), float("inf"), float("-inf")):
        bad = deepcopy(valid)
        bad["return_by_horizon"]["15m"] = bad_value
        bad["horizons"]["15m"] = bad_value
        assert "horizon_return_contract_invalid" in eligibility.calibration_ineligibility_reasons(
            bad
        )
        assert eligibility.effective_calibration_eligible(bad) is False
    for bad_price in (True, "10", float("nan"), float("inf")):
        bad = deepcopy(valid)
        bad["price_at_observation"] = bad_price
        assert eligibility.effective_calibration_eligible(bad) is False
    assert eligibility.finite_number(True) is None
    assert eligibility.finite_number("1") is None
    assert eligibility.filled_horizon_count({"return_by_horizon": {"15m": True}}) == 0

    consumer_clock = datetime(2026, 6, 4, 12, tzinfo=timezone.utc)
    eligible, reasons = eligibility.effective_calibration_state(
        valid,
        evaluated_at=consumer_clock,
    )
    assert eligible is False
    assert "outcome_evaluated_in_future" in reasons


def test_observed_returns_require_exact_exit_price_lineage_and_recomputation():
    valid = _observed_outcome()
    assert eligibility.effective_calibration_eligible(valid) is True

    missing_price = deepcopy(valid)
    missing_price["horizon_metadata"]["3d"]["price_at_horizon"] = None
    reasons = eligibility.calibration_ineligibility_reasons(missing_price)
    assert "horizon_exit_price_missing" in reasons
    assert "horizon_return_contract_invalid" in reasons

    missing_source = deepcopy(valid)
    missing_source["horizon_metadata"]["3d"]["price_source"] = "\u200b"
    reasons = eligibility.calibration_ineligibility_reasons(missing_source)
    assert "horizon_price_source_missing" in reasons
    assert eligibility.effective_calibration_eligible(missing_source) is False

    missing_entry_lineage = deepcopy(valid)
    missing_entry_lineage["observation_price_source"] = ""
    missing_entry_lineage["observation_price_id"] = None
    reasons = eligibility.calibration_ineligibility_reasons(missing_entry_lineage)
    assert "missing_observation_price_source" in reasons
    assert "missing_observation_price_id" in reasons

    invented_return = deepcopy(valid)
    invented_return["return_by_horizon"]["3d"] = 0.40
    invented_return["horizons"]["3d"] = 0.40
    invented_return["primary_horizon_return"] = 0.40
    reasons = eligibility.calibration_ineligibility_reasons(invented_return)
    assert "horizon_return_recompute_mismatch" in reasons
    assert eligibility.effective_calibration_eligible(invented_return) is False

    duplicate_observation = deepcopy(valid)
    duplicate_observation["horizon_metadata"]["3d"]["price_observation_id"] = (
        duplicate_observation["horizon_metadata"]["24h"]["price_observation_id"]
    )
    assert "duplicate_horizon_price_observation_id" in (
        eligibility.calibration_ineligibility_reasons(duplicate_observation)
    )

    reused_entry_observation = deepcopy(valid)
    reused_entry_observation["observation_price_id"] = (
        reused_entry_observation["horizon_metadata"]["3d"]["price_observation_id"]
    )
    assert "duplicate_horizon_price_observation_id" in (
        eligibility.calibration_ineligibility_reasons(reused_entry_observation)
    )


def test_identity_clock_safety_and_lane_direction_are_fail_closed():
    valid = _observed_outcome()
    assert eligibility.deterministic_validation_status(valid) == "validated"

    invalid_lane = deepcopy(valid)
    invalid_lane["opportunity_type"] = "early_long_research"
    assert "invalid_outcome_lane" in eligibility.calibration_ineligibility_reasons(
        invalid_lane
    )
    assert eligibility.deterministic_validation_status(invalid_lane) == "inconclusive"

    for bad_identity in ("\u200b", "\x00", "e\u0301"):
        invalid_identity = deepcopy(valid)
        invalid_identity["candidate_id"] = bad_identity
        invalid_identity.update(eligibility.build_outcome_identity_fields(invalid_identity))
        invalid_identity["calibration_ineligible_reasons"] = list(
            eligibility.calibration_ineligibility_reasons(invalid_identity)
        )
        invalid_identity["calibration_eligible"] = not invalid_identity[
            "calibration_ineligible_reasons"
        ]
        assert eligibility.canonical_join_identity(invalid_identity) is None
        assert "invalid_exact_identity_text" in invalid_identity[
            "calibration_ineligible_reasons"
        ]

    future = _observed_outcome()
    future_observed = datetime.now(timezone.utc) + timedelta(days=30)
    future["observed_at"] = _iso(future_observed)
    future["outcome_evaluated_at"] = _iso(future_observed + timedelta(days=4))
    future.update(eligibility.build_outcome_identity_fields(future))
    for horizon in eligibility.OUTCOME_HORIZONS:
        due = future_observed + timedelta(
            seconds=eligibility.OUTCOME_HORIZON_SECONDS[horizon]
        )
        matured = due <= future_observed + timedelta(days=4)
        future["horizon_metadata"][horizon] = {
            "due_at": _iso(due),
            "price_observed_at": _iso(due) if matured else None,
            "price_at_horizon": 10.4 if matured else None,
            "price_source": "binance_ohlcv" if matured else None,
            "price_observation_id": f"binance:future:{horizon}" if matured else None,
            "maturity_status": "matured" if matured else "pending",
            "provenance_status": "observed_market_prices" if matured else "missing",
        }
    future["calibration_ineligible_reasons"] = list(
        eligibility.calibration_ineligibility_reasons(future)
    )
    future["calibration_eligible"] = not future["calibration_ineligible_reasons"]
    is_eligible, reasons = eligibility.effective_calibration_state(future)
    assert is_eligible is False
    assert "outcome_evaluated_in_future" in reasons
    partitioned, excluded, reason_counts = eligibility.partition_calibration_outcomes(
        [future]
    )
    assert partitioned == ()
    assert len(excluded) == 1
    assert reason_counts["outcome_evaluated_in_future"] == 1

    for field in (
        "execution_enabled",
        "notification_send_enabled",
        "created_alert",
        "send_requested",
    ):
        unsafe = deepcopy(valid)
        unsafe[field] = True
        assert "outcome_safety_contract_invalid" in eligibility.calibration_ineligibility_reasons(
            unsafe
        )
    unsafe_count = deepcopy(valid)
    unsafe_count["orders_created"] = True
    assert "outcome_safety_contract_invalid" in eligibility.calibration_ineligibility_reasons(
        unsafe_count
    )

    adverse_long = deepcopy(valid)
    for field in ("primary_horizon_return",):
        adverse_long[field] = -0.04
    adverse_long["return_by_horizon"]["3d"] = -0.04
    adverse_long["horizons"]["3d"] = -0.04
    adverse_long["horizon_metadata"]["3d"]["price_at_horizon"] = 9.6
    assert eligibility.deterministic_validation_status(adverse_long) == "invalidated/noise"
    assert "outcome_validation_claim_direction_mismatch" in (
        eligibility.calibration_ineligibility_reasons(adverse_long)
    )

    truthful_adverse = deepcopy(adverse_long)
    truthful_adverse["outcome_label"] = "junk"
    truthful_adverse["calibration_ineligible_reasons"] = list(
        eligibility.calibration_ineligibility_reasons(truthful_adverse)
    )
    truthful_adverse["calibration_eligible"] = not truthful_adverse[
        "calibration_ineligible_reasons"
    ]
    assert truthful_adverse["calibration_ineligible_reasons"] == []
    assert eligibility.effective_calibration_eligible(
        truthful_adverse,
        evaluated_at=truthful_adverse["outcome_evaluated_at"],
    ) is True


def test_performance_join_requires_exact_identity_unique_outcome_and_unique_core():
    valid = _observed_outcome()
    candidate = _candidate(valid)
    core = _core(valid)
    generated_at = valid["outcome_evaluated_at"]
    exact = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"),
        candidates=[candidate],
        core_rows=[core],
        outcome_rows=[valid],
        delivery_rows=[],
        generated_at=generated_at,
        stale_after_days=14,
    )
    assert len(exact) == 1
    assert exact[0]["calibration_eligible"] is True
    assert exact[0]["validation_label"] == "validated"

    cross_run = deepcopy(valid)
    cross_run["run_id"] = "different-run"
    cross_run.update(eligibility.build_outcome_identity_fields(cross_run))
    cross_run["calibration_ineligible_reasons"] = list(
        eligibility.calibration_ineligibility_reasons(cross_run)
    )
    cross_run["calibration_eligible"] = not cross_run["calibration_ineligible_reasons"]
    mismatch = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"),
        candidates=[candidate],
        core_rows=[core],
        outcome_rows=[cross_run],
        delivery_rows=[],
        generated_at=generated_at,
        stale_after_days=14,
    )
    assert len(mismatch) == 2
    assert all(row["calibration_eligible"] is False for row in mismatch)
    assert any(
        "identity_mismatch" in row["calibration_ineligible_reasons"]
        for row in mismatch
    )

    duplicate = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"),
        candidates=[candidate],
        core_rows=[core],
        outcome_rows=[valid, {**valid, "outcome_label": "remained_noise"}],
        delivery_rows=[],
        generated_at=generated_at,
        stale_after_days=14,
    )
    assert len(duplicate) == 2
    assert all(row["calibration_eligible"] is False for row in duplicate)
    assert all(
        "duplicate_outcome_identity" in row["calibration_ineligible_reasons"]
        for row in duplicate
    )

    no_core = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"), candidates=[candidate], core_rows=[], outcome_rows=[valid],
        delivery_rows=[], generated_at=generated_at, stale_after_days=14,
    )
    duplicate_core = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"), candidates=[candidate], core_rows=[core, dict(core)],
        outcome_rows=[valid], delivery_rows=[], generated_at=generated_at, stale_after_days=14,
    )
    assert all(row["calibration_eligible"] is False for row in no_core)
    assert all(row["calibration_eligible"] is False for row in duplicate_core)

    bare_candidate = {
        field: valid[field]
        for field in eligibility.OUTCOME_IDENTITY_FIELDS
    }
    bare_candidate_rows, bare_candidate_excluded, bare_candidate_reasons = (
        eligibility.partition_joined_calibration_outcomes(
            [valid],
            [bare_candidate],
            [core],
            evaluated_at=generated_at,
        )
    )
    assert bare_candidate_rows == ()
    assert len(bare_candidate_excluded) == 1
    assert bare_candidate_reasons["candidate_authority_contract_invalid"] == 1

    bare_core = {
        field: valid[field]
        for field in ("run_id", "profile", "artifact_namespace", "core_opportunity_id")
    }
    bare_core_rows, bare_core_excluded, bare_core_reasons = (
        eligibility.partition_joined_calibration_outcomes(
            [valid],
            [candidate],
            [bare_core],
            evaluated_at=generated_at,
        )
    )
    assert bare_core_rows == ()
    assert len(bare_core_excluded) == 1
    assert bare_core_reasons["core_authority_contract_invalid"] == 1

    idless = {"symbol": "IDLESS", "coin_id": "idless", "opportunity_type": "EARLY_LONG_RESEARCH"}
    no_fallback = outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"), candidates=[idless], core_rows=[], outcome_rows=[dict(idless)],
        delivery_rows=[], generated_at=generated_at, stale_after_days=14,
    )
    assert len(no_fallback) == 2
    assert all(row["calibration_eligible"] is False for row in no_fallback)


def test_joined_partition_rejects_duplicates_and_uses_only_authoritative_attribution():
    valid = _observed_outcome()
    candidate = _candidate(valid, provider="candidate-wins")
    core = _core(valid, provider="core-loses")
    forged = {**valid, "provider": "forged", "source_pack": "forged-pack"}
    eligible_rows, excluded, reasons = eligibility.partition_joined_calibration_outcomes(
        [forged], [candidate], [core], evaluated_at=valid["outcome_evaluated_at"]
    )
    assert not excluded
    assert not reasons
    assert eligible_rows[0]["provider"] == "candidate-wins"
    assert eligible_rows[0]["source_pack"] == "listing_pack"
    forged_priors = outcomes.build_integrated_radar_calibration_priors(
        [forged],
        evaluated_at=valid["outcome_evaluated_at"],
    )
    assert forged_priors["opportunity_type_priors"] == {}
    forged_report = outcomes.format_integrated_radar_outcome_report(
        [forged],
        evaluated_at=valid["outcome_evaluated_at"],
    )
    assert "Performance rows: 0" in forged_report

    absent_authority = _candidate(valid, provider=None, source_pack=None, source_origin=None)
    absent_core = _core(valid, provider=None, source_pack=None, source_origin=None)
    projected, excluded, _reasons = eligibility.partition_joined_calibration_outcomes(
        [forged], [absent_authority], [absent_core], evaluated_at=valid["outcome_evaluated_at"]
    )
    assert not excluded
    assert projected[0]["provider"] == "unknown"
    assert projected[0]["source_pack"] == "unknown"

    duplicates = [
        {**valid, "outcome_label": "early_good" if index % 2 else "remained_noise"}
        for index in range(100)
    ]
    eligible_rows, excluded, reasons = eligibility.partition_calibration_outcomes(duplicates)
    assert eligible_rows == ()
    assert len(excluded) == 100
    assert reasons["duplicate_outcome_identity"] == 100
    joined, joined_excluded, joined_reasons = eligibility.partition_joined_calibration_outcomes(
        duplicates, [candidate], [core], evaluated_at=valid["outcome_evaluated_at"]
    )
    assert joined == ()
    assert len(joined_excluded) == 100
    assert joined_reasons["duplicate_outcome_identity"] == 100


def test_pending_and_legacy_rows_never_satisfy_performance_sample_minimum(tmp_path: Path):
    namespace = tmp_path / "pending"
    pending_rows = [
        _observed_outcome(index, evaluated_after=timedelta(hours=1))
        for index in range(25)
    ]
    candidates = [_candidate(row) for row in pending_rows]
    cores = [_core(row) for row in pending_rows]
    legacy = {
        "row_type": "event_integrated_radar_outcome",
        "candidate_id": "legacy-candidate",
        "core_opportunity_id": "legacy-core",
        "symbol": "LEGACY",
        "coin_id": "legacy",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "outcome_status": "filled",
        "outcome_label": "early_good",
        "return_by_horizon": {horizon: 0.5 for horizon in eligibility.OUTCOME_HORIZONS},
    }
    _write_jsonl(namespace / integrated_radar.INTEGRATED_CANDIDATES_FILENAME, candidates)
    _write_jsonl(namespace / "event_core_opportunities.jsonl", cores)
    _write_jsonl(
        namespace / integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        [*pending_rows, legacy],
    )
    generated = "2026-06-01T01:00:24+00:00"
    payload = outcomes.build_radar_provider_performance(
        (namespace,), generated_at=generated, min_sample=25
    )

    assert payload["rows_evaluated"] == 0
    assert payload["calibration_ineligible_rows_excluded"] >= 25
    suggestion = payload["provider_prior_suggestions"]["candidate-provider"]
    assert suggestion["sample_size"] == 0
    assert suggestion["min_sample_warning"] is True
    assert suggestion["recommendation"] == "insufficient_sample_collect_more_outcomes"
    assert suggestion["validation_rate"] is None
    assert payload["main_aggregate"]["validation_rate"] is None
    assert payload["main_aggregate"]["validated_count"] == 0
    assert payload["main_aggregate"]["invalidated_noise_count"] == 0

    priors = outcomes.build_integrated_radar_calibration_priors([*pending_rows, legacy])
    assert priors["opportunity_type_priors"] == {}

    nonfinite_thesis = deepcopy(_observed_outcome(99))
    nonfinite_thesis["thesis_favorable_excursion"] = float("nan")
    prior = outcomes.build_integrated_radar_calibration_priors(
        [nonfinite_thesis],
        candidate_rows=[_candidate(nonfinite_thesis)],
        core_rows=[_core(nonfinite_thesis)],
        evaluated_at=nonfinite_thesis["outcome_evaluated_at"],
    )
    assert prior["opportunity_type_priors"]["EARLY_LONG_RESEARCH"][
        "median_thesis_favorable_move"
    ] is None
