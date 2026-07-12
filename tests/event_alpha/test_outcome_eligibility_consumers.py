"""Operator-report regressions for exact joined outcome evidence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.operations import measurement, scorecard, source_yield
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _observed_outcome(
    *,
    observed_at: datetime,
    evaluated_at: datetime,
    candidate_id: str,
    core_opportunity_id: str,
) -> dict[str, object]:
    identity = {
        "run_id": "run-authority",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "authority",
        "candidate_id": candidate_id,
        "core_opportunity_id": core_opportunity_id,
        "observed_at": observed_at.isoformat(),
    }
    metadata: dict[str, dict[str, object]] = {}
    returns: dict[str, float] = {}
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        due_at = observed_at + timedelta(
            seconds=outcome_eligibility.OUTCOME_HORIZON_SECONDS[horizon]
        )
        metadata[horizon] = {
            "due_at": due_at.isoformat(),
            "price_observed_at": (due_at + timedelta(minutes=1)).isoformat(),
            "price_at_horizon": 101.0,
            "price_source": "fixture_ohlcv",
            "price_observation_id": f"fixture:{candidate_id}:{horizon}",
            "maturity_status": "matured",
            "provenance_status": "observed_market_prices",
        }
        returns[horizon] = 0.01
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_outcome",
        "symbol": "FORGED",
        "coin_id": "forged",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        **identity,
        "outcome_identity": dict(identity),
        "outcome_identity_key": outcome_eligibility.canonical_outcome_identity_key(identity),
        "outcome_eligibility_contract_version": (
            outcome_eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": "observed_market_prices",
        "outcome_evaluated_at": evaluated_at.isoformat(),
        "observation_price_provenance_status": "observed_market_prices",
        "price_at_observation": 100.0,
        "observation_price_source": "fixture_ohlcv",
        "observation_price_id": f"fixture:{candidate_id}:entry",
        "observation_price_observed_at": observed_at.isoformat(),
        "primary_horizon": "3d",
        "primary_horizon_return": returns["3d"],
        "return_by_horizon": returns,
        "horizons": dict(returns),
        "horizon_metadata": metadata,
        "outcome_status": "filled",
        "validation_status": "validated",
        "provider": "forged-provider",
        "source_provider": "forged-provider-alias",
        "source_pack": "forged-pack",
        "source_pack_id": "forged-pack-alias",
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    reasons = outcome_eligibility.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    assert reasons == ()
    return row


def test_operational_reports_use_only_exact_joined_outcome_evidence(tmp_path: Path):
    evaluated_at = datetime.now(timezone.utc).replace(microsecond=0)
    observed_at = evaluated_at - timedelta(days=8)
    valid = _observed_outcome(
        observed_at=observed_at,
        evaluated_at=evaluated_at,
        candidate_id="candidate-valid",
        core_opportunity_id="core-valid",
    )
    forged = _observed_outcome(
        observed_at=observed_at,
        evaluated_at=evaluated_at,
        candidate_id="candidate-invented",
        core_opportunity_id="core-invented",
    )
    legacy = [
        {
            "row_type": "event_integrated_radar_outcome",
            "symbol": "LEGACY",
            "opportunity_type": "EARLY_LONG_RESEARCH",
            "candidate_id": f"legacy-{index}",
            "core_opportunity_id": f"legacy-core-{index}",
            "observed_at": evaluated_at.isoformat(),
            "outcome_status": "filled",
            "validation_status": "validated",
            "primary_horizon_return": 0.50,
        }
        for index in range(100)
    ]
    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "research_only": True,
        **{field: valid[field] for field in outcome_eligibility.OUTCOME_IDENTITY_FIELDS},
        "symbol": "AUTH",
        "coin_id": "authority",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "provider": "candidate-provider",
        "source_pack": "candidate-pack",
    }
    core = {
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": valid["observed_at"],
        "research_only": True,
        **{
            field: valid[field]
            for field in ("run_id", "profile", "artifact_namespace", "core_opportunity_id")
        },
        "symbol": "AUTH",
        "coin_id": "authority",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "provider": "core-provider",
        "source_pack": "core-pack",
    }
    namespace_dir = tmp_path / "authority"
    _write_jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl", [candidate])
    _write_jsonl(namespace_dir / "event_core_opportunities.jsonl", [core])
    _write_jsonl(
        namespace_dir / "event_integrated_radar_outcomes.jsonl",
        [valid, forged, *legacy],
    )

    eligible, excluded, reasons = outcome_eligibility.partition_joined_calibration_outcomes(
        [valid, forged, *legacy],
        [candidate],
        [core],
    )
    assert len(eligible) == 1
    assert len(excluded) == 101
    assert eligible[0]["provider"] == "candidate-provider"
    assert eligible[0]["source_pack"] == "candidate-pack"
    assert eligible[0].get("source_provider") != "forged-provider-alias"
    assert eligible[0].get("source_pack_id") != "forged-pack-alias"
    assert reasons["unmatched_outcome_identity"] >= 1
    assert reasons["legacy_outcome_contract"] == 100

    score = scorecard.build_scorecard(
        profile="live_burn_in_no_send",
        artifact_namespace="authority",
        base_dir=tmp_path,
        count_explicit_namespace_for_burn_in=True,
    )
    weekly = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="authority",
        base_dir=tmp_path,
    )
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        artifact_namespace="authority",
        base_dir=tmp_path,
    )
    for payload in (score, weekly, yield_report):
        assert payload["outcome_rows_supplied"] == 102
        assert payload["outcome_rows_eligible"] == 1
        assert payload["outcome_rows_excluded"] == 101
        assert payload["outcome_exclusion_reason_counts"]["legacy_outcome_contract"] == 100
    assert schema_v1.validate_row_against_schema(
        {**score, "namespace_dir": "event_fade_cache/authority"},
        "event_alpha_burn_in_scorecard_v1",
    ) == []
    assert schema_v1.validate_row_against_schema(
        {**weekly, "namespace_dir": "event_fade_cache/authority"},
        "event_alpha_burn_in_measurement_dashboard_v1",
    ) == []
    assert schema_v1.validate_row_against_schema(
        {**yield_report, "namespace_dir": "event_fade_cache/authority"},
        "event_alpha_source_yield_report_v1",
    ) == []
    assert score["outcome_rows"] == 1
    assert any(reason.startswith("min_outcome_rows:1/") for reason in score["enough_data_reasons"])
    assert weekly["low_sample_warning"] is True
    assert any(reason == "min_outcome_rows:1/100" for reason in weekly["enough_data_reasons"])
    assert yield_report["outcome_count"] == 1
    assert any(
        reason == "min_outcome_rows:1/100"
        for reason in yield_report["enough_data_reasons"]
    )
