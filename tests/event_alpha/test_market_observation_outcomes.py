"""Durable, candidate-authoritative Decision Radar campaign outcomes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
)
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign
from crypto_rsi_scanner.event_alpha.operations import market_observation_outcomes
from crypto_rsi_scanner.event_alpha.operations.market_no_send_history_cache import (
    LIVE_HISTORY_CACHE_NAMESPACE,
)
from crypto_rsi_scanner.event_alpha.radar import decision_model
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)
from tests.event_alpha.campaign_test_support import write_countable_generation


_OBSERVED = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
_NAMESPACE = "campaign_outcome_candidate_only"


def _candidate() -> dict[str, object]:
    observed = _OBSERVED.isoformat()
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": "campaign-outcome-run",
        "profile": "no_key_live",
        "artifact_namespace": _NAMESPACE,
        "candidate_id": "candidate-campaign-outcome",
        "core_opportunity_id": "core-campaign-outcome-filtered",
        "observed_at": observed,
        "symbol": "CAMPAIGN",
        "coin_id": "campaign-token",
        "canonical_asset_id": "campaign-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "opportunity_type": "DIAGNOSTIC",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_snapshot": {
            "market_data_source": "coingecko",
            "observed_at": observed,
            "freshness_status": "fresh",
            "market_snapshot_id": "market-campaign-outcome-1",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
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
    return row


def _history_rows(*, include_primary_close: bool) -> list[dict[str, object]]:
    entry = {
        "schema_id": "event_alpha.market_history_observation",
        "schema_version": 1,
        "canonical_asset_id": "campaign-token",
        "coin_id": "campaign-token",
        "symbol": "CAMPAIGN",
        "observed_at": _OBSERVED.isoformat(),
        "observation_id": "campaign-entry",
        "price": 100.0,
        "source": "coingecko",
        "provider": "coingecko",
        "research_only": True,
    }
    rows = [entry]
    if include_primary_close:
        rows.append({
            **entry,
            "observed_at": (_OBSERVED + timedelta(hours=24)).isoformat(),
            "observation_id": "campaign-primary-24h",
            "price": 110.0,
        })
    return rows


def _write_campaign_fixture(
    base: Path,
    *,
    include_primary_close: bool = True,
    candidate: dict[str, object] | None = None,
    core_rows: tuple[dict[str, object], ...] = (),
) -> tuple[Path, Path, Path]:
    namespace_dir = base / _NAMESPACE
    history_dir = base / LIVE_HISTORY_CACHE_NAMESPACE
    namespace_dir.mkdir(parents=True)
    history_dir.mkdir(parents=True)
    manifest_path, _manifest, _rows = write_countable_generation(
        base,
        _NAMESPACE,
        _OBSERVED.isoformat(),
        candidates=[candidate or _candidate()],
        core_rows=core_rows,
    )
    candidate_path = namespace_dir / "event_integrated_radar_candidates.jsonl"
    market_no_send_io.write_jsonl(
        history_dir / "event_market_history.jsonl",
        _history_rows(include_primary_close=include_primary_close),
    )
    pointer = base / CURRENT_NAMESPACE_POINTER
    pointer.write_bytes(b'{"artifact_namespace":"unchanged-authority"}\n')
    return manifest_path, candidate_path, pointer


def test_candidate_only_canonical_projection_matures_without_core_and_no_side_effects(
    tmp_path: Path,
):
    manifest_path, candidate_path, pointer = _write_campaign_fixture(tmp_path)
    source_bytes = {
        manifest_path: manifest_path.read_bytes(),
        candidate_path: candidate_path.read_bytes(),
        candidate_path.with_name("event_core_opportunities.jsonl"): (
            candidate_path.with_name("event_core_opportunities.jsonl").read_bytes()
        ),
        pointer: pointer.read_bytes(),
    }

    pending_result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(hours=1),
    )
    pending = market_observation_outcomes.load_campaign_outcomes(tmp_path)[0]
    assert pending_result["maturation_counts"] == {"pending": 1}
    assert pending["maturation_state"] == "pending"

    result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )

    rows = market_observation_outcomes.load_campaign_outcomes(tmp_path)
    assert result["provider_calls"] == 0
    assert result["maturation_counts"] == {"matured": 1}
    assert result["build_error_counts"] == {}
    assert result["monotonic_preserved_count"] == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["maturation_state"] == "matured"
    assert row["primary_horizon"] == "24h"
    assert row["primary_horizon_return"] == pytest.approx(0.1)
    assert row["campaign_outcome_authority"] == "canonical_decision_candidate"
    assert row["campaign_core_opportunity_present"] is False
    assert row["campaign_calibration_scope"] == "candidate_only_not_core_joined"
    assert row["calibration_eligible"] is False
    assert row["include_in_performance"] is False
    assert "diagnostic_lane" in row["calibration_ineligible_reasons"]
    assert "unmatched_outcome_identity" in row["calibration_ineligible_reasons"]
    assert row["decision_projection"] == decision_model_values(_candidate())
    assert row["research_only"] is True
    assert row["no_send_rehearsal"] is True
    assert all(
        row[field] is False
        for field in (
            "sent",
            "trade_created",
            "paper_trade_created",
            "normal_rsi_signal_written",
            "triggered_fade_created",
        )
    )
    for path, before in source_bytes.items():
        assert path.read_bytes() == before


def test_mature_campaign_outcome_is_monotonic_after_bounded_history_pruning(
    tmp_path: Path,
):
    manifest_path, candidate_path, pointer = _write_campaign_fixture(tmp_path)
    immutable_before = {
        manifest_path: manifest_path.read_bytes(),
        candidate_path: candidate_path.read_bytes(),
        pointer: pointer.read_bytes(),
    }
    market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )
    mature = market_observation_outcomes.load_campaign_outcomes(tmp_path)[0]

    history_path = (
        tmp_path / LIVE_HISTORY_CACHE_NAMESPACE / "event_market_history.jsonl"
    )
    market_no_send_io.write_jsonl(
        history_path,
        _history_rows(include_primary_close=False),
    )
    result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=3),
    )
    preserved = market_observation_outcomes.load_campaign_outcomes(tmp_path)[0]

    assert result["provider_calls"] == 0
    assert result["monotonic_preserved_count"] == 1
    assert result["maturation_counts"] == {"matured": 1}
    assert preserved["maturation_state"] == "matured"
    assert preserved["primary_horizon_return"] == mature["primary_horizon_return"]
    assert preserved["horizon_metadata"]["24h"] == mature["horizon_metadata"]["24h"]
    assert preserved["observation_price_id"] == mature["observation_price_id"]
    for path, before in immutable_before.items():
        assert path.read_bytes() == before


def test_candidate_only_adapter_fails_closed_on_decision_projection_drift(
    tmp_path: Path,
):
    candidate = _candidate()
    projection = dict(candidate["decision_projection"])
    projection["radar_route"] = "diagnostic"
    candidate["decision_projection"] = projection
    _manifest, _candidate_path, pointer = _write_campaign_fixture(
        tmp_path,
        candidate=candidate,
    )
    pointer_before = pointer.read_bytes()

    result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )
    row = market_observation_outcomes.load_campaign_outcomes(tmp_path)[0]

    assert result["provider_calls"] == 0
    assert result["build_error_counts"] == {
        "candidate_decision_projection_invalid": 1,
    }
    assert row.get("maturation_state") != "matured"
    assert row["campaign_outcome_authority"] == "invalid_candidate_projection"
    assert row["campaign_core_opportunity_present"] is False
    assert pointer.read_bytes() == pointer_before


def test_core_join_requires_exact_candidate_decision_projection(tmp_path: Path):
    candidate = _candidate()
    projection = decision_model_values(candidate)
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=projection,
    )
    assert core is not None
    core["run_id"] = f"{_OBSERVED.isoformat()}|no_key_live"
    drifted_projection = dict(projection)
    drifted_projection["radar_route"] = "dashboard_watch"
    core["decision_projection"] = drifted_projection
    _write_campaign_fixture(tmp_path, candidate=candidate, core_rows=(core,))

    result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )
    row = market_observation_outcomes.load_campaign_outcomes(tmp_path)[0]

    assert result["build_error_counts"] == {"core_decision_projection_mismatch": 1}
    assert row["campaign_outcome_authority"] == "canonical_decision_candidate"
    assert row["campaign_core_opportunity_present"] is False
    assert row["campaign_calibration_scope"] == "candidate_only_not_core_joined"
    assert row["calibration_eligible"] is False
    assert "core_decision_projection_mismatch" in row["campaign_outcome_refresh_errors"]


def test_campaign_report_rejects_mutable_ledger_projection_drift(tmp_path: Path):
    _write_campaign_fixture(tmp_path)
    market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )
    campaign_path = (
        tmp_path
        / LIVE_HISTORY_CACHE_NAMESPACE
        / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    rows = market_no_send_io.read_jsonl(campaign_path)
    assert rows[0]["maturation_state"] == "matured"
    projection = dict(rows[0]["decision_projection"])
    projection["risk_score"] = float(projection["risk_score"]) + 1.0
    rows[0]["decision_projection"] = projection
    market_no_send_io.write_jsonl(campaign_path, rows)
    generations, _attempts, excluded = market_observation_campaign._load_generations(  # noqa: SLF001
        tmp_path,
        current_authority={},
    )

    campaign_rows = market_observation_campaign._campaign_outcomes(  # noqa: SLF001
        tmp_path,
        generations,
    )
    metrics = market_observation_campaign._outcome_metrics(campaign_rows)  # noqa: SLF001

    assert excluded == []
    assert metrics["total"] == 1
    assert metrics["matured"] == 0
    assert metrics["pending"] == 1
    assert metrics["source"] == "canonical_candidate_pending_base"


def test_invalid_generation_is_excluded_and_stale_mature_row_is_not_preserved(
    tmp_path: Path,
):
    manifest_path, _candidate_path, _pointer = _write_campaign_fixture(tmp_path)
    manifest = market_no_send_io.read_json_object(manifest_path)
    manifest["candidate_count"] = 7
    market_no_send_io.write_json_atomic(manifest_path, manifest)
    campaign_path = (
        tmp_path
        / LIVE_HISTORY_CACHE_NAMESPACE
        / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    market_no_send_io.write_jsonl(campaign_path, [{
        "source_artifact_namespace": _NAMESPACE,
        "candidate_id": "candidate-campaign-outcome",
        "maturation_state": "matured",
        "campaign_outcome_ledger": True,
    }])

    result = market_observation_outcomes.refresh_campaign_outcomes(
        tmp_path,
        evaluated_at=_OBSERVED + timedelta(days=2),
    )

    assert result["validated_generation_count"] == 0
    assert result["excluded_generation_count"] == 1
    assert result["outcome_count"] == 0
    assert result["provider_calls"] == 0
    assert any(
        "candidate_count" in reason
        for reason in result["excluded_generations"][0]["validation_errors"]
    )
    assert market_observation_outcomes.load_campaign_outcomes(tmp_path) == []
