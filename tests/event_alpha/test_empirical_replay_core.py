from __future__ import annotations

from copy import deepcopy

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_replay_core import (
    canonical_idea_bytes,
    partition_for_timestamp,
    run_replay_kernel,
)
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import decision_model_values


def _observation(**overrides):
    row = {
        "symbol": "MOVE",
        "canonical_asset_id": "move",
        "observed_at": "2024-06-01T00:00:00+00:00",
        "close": 12.0,
        "quote_volume": 20_000_000.0,
        "return_24h": 30.0,
        "return_72h": 35.0,
        "return_7d": 45.0,
        "relative_return_vs_btc_24h": 28.0,
        "relative_return_vs_eth_24h": 25.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 20_000_000.0,
        "liquidity_tier": "large",
        "market_regime": "bull",
        "point_in_time_universe_member": True,
        "point_in_time_volume_rank": 4,
        "baseline_status": "warm",
        "data_quality_mode": "historical_ohlcv",
        "market_data_source": "binance_historical_ohlcv",
        "source_mode": "historical_replay",
        "market_data_basis": "historical_ohlcv",
        "volume_anomaly_basis": "historical_ohlcv_prior_90d",
        "liquidity_basis": "historical_ohlcv_trailing_quote_volume",
        "spread_basis": "unavailable",
        "catalyst_evidence_timing": "missing",
        "calendar_evidence_timing": "missing",
        "rsi_context_timing": "temporal_direct",
        "direct_proxy_class": "temporal_direct",
        "direct_feature_count": 8,
        "proxy_feature_count": 0,
        "feature_basis": {
            "returns": "historical_ohlcv",
            "volume": "historical_ohlcv_prior_90d",
            "spread": "unavailable",
        },
        "missing_features": ["return_4h", "spread_bps", "derivatives", "calendar", "catalyst"],
    }
    row.update(overrides)
    return row


def test_replay_uses_canonical_production_projection_and_explicit_missing_spread() -> None:
    result = run_replay_kernel(
        [_observation()],
        mode="medium",
        artifact_namespace="empirical-test",
        allowed_partitions=("validation",),
    )

    assert len(result.ideas) == 1
    idea = result.ideas[0]
    projection = idea["decision_projection"]
    assert decision_model_values(idea) == projection
    assert decision_model_values(projection) == projection
    assert projection["spread_status"] == "unavailable"
    assert projection["radar_actionable"] is False
    assert projection["radar_route"] in {"dashboard_watch", "fade_exhaustion_review", "diagnostic"}
    assert idea["replay_feature_quality"]["spread_basis"] == "unavailable"
    assert idea["replay_feature_quality"]["catalyst_evidence_timing"] == "missing"
    assert idea["baseline_status"] == "warm"
    assert idea["liquidity_usd"] == 20_000_000.0
    assert idea["data_quality_mode"] == "historical_ohlcv"
    assert idea["return_unit"] == "percent_points"
    assert idea["anomaly_generated"] is True
    assert result.trace_summary["provider_calls"] == 0
    assert result.trace_summary["dashboard_authority_mutations"] == 0


def test_daily_rsi_observation_survives_projection_without_decision_authority() -> None:
    reference = {
        "context_type": "daily_rsi_observation",
        "context_version": "empirical_daily_rsi_observation_v1",
        "rsi_value": 68.0,
        "rsi_timeframe": "1d",
        "observed_at": "2024-06-01T00:00:00+00:00",
        "data_basis": "historical_ohlcv",
        "timing_basis": "point_in_time_completed_daily_bar",
        "read_only": True,
        "authoritative": False,
        "technical_thesis_origin_allowed": False,
        "score_adjustment_allowed": False,
        "policy_adjustment_allowed": False,
        "actionability_adjustment": 0.0,
        "risk_adjustment": 0.0,
        "research_only": True,
    }
    without_context = run_replay_kernel(
        [_observation()],
        mode="medium",
        artifact_namespace="rsi-context-control",
        allowed_partitions=("validation",),
    )
    with_context = run_replay_kernel(
        [
            _observation(
                rsi=68.0,
                rsi_context_timing="point_in_time_completed_daily_bar",
                rsi_context_basis="historical_ohlcv",
                rsi_context_references=[reference],
            )
        ],
        mode="medium",
        artifact_namespace="rsi-context-control",
        allowed_partitions=("validation",),
    )

    plain = without_context.ideas[0]
    contextual = with_context.ideas[0]
    plain_projection = plain["decision_projection"]
    projection = contextual["decision_projection"]
    assert contextual["rsi_context_references"] == [reference]
    assert projection["rsi_context_references"] == [reference]
    assert projection["rsi_context"] == {}
    for field in (
        "primary_thesis_origin",
        "thesis_origins",
        "radar_route",
        "radar_actionable",
        "actionability_score",
        "evidence_confidence_score",
        "risk_score",
        "urgency_score",
        "chase_risk_score",
        "hard_blockers",
        "soft_penalties",
    ):
        assert projection[field] == plain_projection[field]
    assert projection["primary_thesis_origin"] == "market_led"
    assert "technical_led" not in projection["thesis_origins"]
    assert "rsi_context_version" not in contextual
    assert with_context.trace_summary["provider_calls"] == 0
    assert with_context.trace_summary["normal_rsi_writes"] == 0
    assert with_context.trace_summary["event_alpha_paper_trades"] == 0
    assert with_context.trace_summary["event_alpha_triggered_fade"] == 0


def test_replay_ignores_future_and_outcome_fields() -> None:
    base = _observation()
    leaked = {**base, "future_return_3d": 900.0, "outcome": {"return": 900.0}}

    first = run_replay_kernel(
        [base], mode="medium", artifact_namespace="same", allowed_partitions=("validation",)
    ).ideas[0]
    second = run_replay_kernel(
        [leaked], mode="medium", artifact_namespace="same", allowed_partitions=("validation",)
    ).ideas[0]

    assert canonical_idea_bytes(first) == canonical_idea_bytes(second)


def test_replay_trace_preserves_no_idea_and_gate_failures() -> None:
    rows = [
        _observation(symbol="FLAT", canonical_asset_id="flat", return_24h=1.0),
        _observation(symbol="COLD", canonical_asset_id="cold", baseline_status="insufficient_history"),
        _observation(symbol="OUT", canonical_asset_id="out", point_in_time_universe_member=False),
    ]
    result = run_replay_kernel(
        rows, mode="medium", artifact_namespace="trace", allowed_partitions=("validation",)
    )

    assert result.ideas == ()
    assert result.trace_summary["failure_stage_counts"] == {
        "insufficient_history": 1,
        "no_anomaly_generated": 1,
        "universe_exclusion": 1,
    }


def test_replay_partition_selection_is_chronological_and_final_test_is_guarded() -> None:
    assert partition_for_timestamp("2022-01-01T00:00:00Z") == "development"
    assert partition_for_timestamp("2024-01-01T00:00:00Z") == "validation"
    assert partition_for_timestamp("2025-01-01T00:00:00Z") == "final_test"
    assert partition_for_timestamp("2026-06-01T00:00:00Z") == "outside_protocol_window"

    with pytest.raises(ValueError, match="sealed final_test"):
        run_replay_kernel(
            [_observation(observed_at="2025-06-01T00:00:00Z")],
            mode="medium",
            artifact_namespace="forbidden",
            allowed_partitions=("final_test",),
        )


def test_fixture_mode_is_mechanics_only_and_separate() -> None:
    result = run_replay_kernel(
        [_observation(observed_at="2026-06-05T00:00:00Z")],
        mode="fixture",
        artifact_namespace="fixture",
        allowed_partitions=("fixture",),
    )

    assert result.ideas[0]["replay_mode"] == "fixture"
    assert result.ideas[0]["replay_partition"] == "fixture"
    assert result.ideas[0]["data_mode"] == "fixture"
    assert result.trace_summary["mode"] == "fixture"


def test_invalid_protocol_or_naive_time_fails_closed() -> None:
    bad_protocol = deepcopy(__import__(
        "crypto_rsi_scanner.event_alpha.operations.empirical_validation_protocol",
        fromlist=["protocol_values"],
    ).protocol_values())
    bad_protocol["outcomes"]["primary_horizon_days"] = 7
    with pytest.raises(ValueError, match="protocol invalid"):
        run_replay_kernel(
            [_observation()],
            mode="medium",
            artifact_namespace="bad",
            allowed_partitions=("validation",),
            protocol=bad_protocol,
        )
    with pytest.raises(ValueError, match="timezone"):
        run_replay_kernel(
            [_observation(observed_at="2024-01-01T00:00:00")],
            mode="medium",
            artifact_namespace="bad-time",
            allowed_partitions=("validation",),
        )
