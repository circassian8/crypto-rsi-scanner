"""Pure read-only RSI technical-context adapter regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

from crypto_rsi_scanner.event_alpha.radar.rsi_technical_context import (
    RSI_TECHNICAL_CONTEXT_VERSION,
    apply_rsi_technical_context,
    normalize_rsi_signal_artifact,
    rsi_context_adjustment,
)


_NOW = "2026-07-12T12:00:00+00:00"


def _rsi_artifact(**overrides):
    row = {
        "symbol": "RSICTX",
        "coin_id": "rsi-context",
        "setup_type": "dip_buy",
        "rsi_daily": 22.0,
        "severity": "ALERT",
        "market_regime": "BULL",
        "conviction": 74,
        "expected_dir": "up",
        "observed_at": "2026-07-12T10:00:00+00:00",
        "freshness_status": "fresh",
    }
    row.update(overrides)
    return row


def _candidate(**overrides):
    row = {
        "symbol": "RSICTX",
        "coin_id": "rsi-context",
        "directional_bias": "long",
        "actionability_score": 60.0,
        "risk_score": 40.0,
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(overrides)
    return row


def _integrated_market_row():
    return {
        "row_type": "event_market_anomaly",
        "symbol": "RSICTX",
        "coin_id": "rsi-context",
        "canonical_asset_id": "rsi-context",
        "source_class": "market_data",
        "source_pack": "market_anomaly_pack",
        "impact_path_type": "market_anomaly_unknown",
        "market_state": "confirmed_breakout",
        "market_state_class": "confirmed_breakout",
        "anomaly_type": "high_liquidity_breakout",
        "anomaly_bucket": "high_liquidity_breakout",
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "market_snapshot": {
            "return_unit": "fraction",
            "return_1h": 0.035,
            "return_4h": 0.10,
            "return_24h": 0.16,
            "relative_return_vs_btc_4h": 0.10,
            "volume_zscore_24h": 3.4,
            "volume_to_market_cap": 0.28,
            "volume_24h": 50_000_000,
            "liquidity_usd": 24_000_000,
            "spread_bps": 16,
            "observed_at": _NOW,
            "market_context_freshness_status": "fresh",
        },
        "observed_at": _NOW,
    }


def _build_integrated(sidecars):
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    return integrated_radar.build_integrated_candidates(
        sidecar_rows=sidecars,
        profile="fixture",
        artifact_namespace="rsi_context_test",
        run_mode="fixture",
        run_id="rsi-context-run",
        observed_at=_NOW,
    )


def test_normalizes_registry_grounded_rsi_context_without_mutating_input():
    artifact = _rsi_artifact()
    original = deepcopy(artifact)

    context = normalize_rsi_signal_artifact(artifact, evaluated_at=_NOW)

    assert artifact == original
    assert context.context_version == RSI_TECHNICAL_CONTEXT_VERSION
    assert context.valid is True
    assert context.symbol == "RSICTX"
    assert context.coin_id == "rsi-context"
    assert context.setup_type == "dip_buy"
    assert context.rsi_severity == "alert"
    assert context.rsi_value == 22.0
    assert context.rsi_timeframe == "1d"
    assert context.market_regime == "UPTREND"
    assert context.market_alignment == "favorable"
    assert context.conviction == 74.0
    assert context.effective_conviction == 74.0
    assert context.setup_edge_prior == 64.0
    assert context.setup_has_edge is True
    assert context.expected_direction == "up"
    assert context.freshness_status == "fresh"
    assert context.age_hours == 2.0
    assert context.warnings == ()


def test_flag_and_regime_can_derive_canonical_setup_and_direction():
    artifact = _rsi_artifact()
    artifact.pop("setup_type")
    artifact.pop("expected_dir")
    artifact.update({"flag": "OS", "regime": "UPTREND"})
    artifact.pop("market_regime")

    context = normalize_rsi_signal_artifact(artifact, evaluated_at=_NOW)

    assert context.valid is True
    assert context.setup_type == "dip_buy"
    assert context.expected_direction == "up"
    assert context.market_regime == "UPTREND"


def test_compatible_and_incompatible_context_adjust_scores_transparently():
    artifact = _rsi_artifact()
    long_candidate = _candidate()
    risk_candidate = _candidate(directional_bias="risk")
    original_candidate = deepcopy(long_candidate)
    original_artifact = deepcopy(artifact)

    compatible = apply_rsi_technical_context(
        long_candidate,
        artifact,
        evaluated_at=_NOW,
    )
    incompatible = apply_rsi_technical_context(
        risk_candidate,
        artifact,
        evaluated_at=_NOW,
    )

    assert long_candidate == original_candidate
    assert artifact == original_artifact
    assert compatible["rsi_context_compatibility"] == "compatible"
    assert compatible["rsi_actionability_adjustment"] > 0
    assert compatible["rsi_risk_adjustment"] < 0
    assert compatible["rsi_adjusted_actionability_score"] > 60.0
    assert compatible["rsi_adjusted_risk_score"] < 40.0
    assert "rsi_direction_supports_radar_thesis" in compatible["rsi_adjustment_reason_codes"]
    assert incompatible["rsi_context_compatibility"] == "incompatible"
    assert incompatible["rsi_actionability_adjustment"] < 0
    assert incompatible["rsi_risk_adjustment"] > 0
    assert incompatible["rsi_adjusted_actionability_score"] < 60.0
    assert incompatible["rsi_adjusted_risk_score"] > 40.0
    assert "rsi_direction_conflicts_with_radar_thesis" in incompatible["rsi_adjustment_reason_codes"]


def test_no_edge_setup_caps_conviction_and_cannot_raise_actionability():
    artifact = _rsi_artifact(
        setup_type="breakdown_risk",
        rsi_daily=12.0,
        severity="EXTREME",
        market_regime="DOWNTREND",
        conviction=96,
        expected_dir="down",
    )

    applied = apply_rsi_technical_context(
        _candidate(directional_bias="risk"),
        artifact,
        evaluated_at=_NOW,
    )
    context = applied["rsi_context"]

    assert context["setup_has_edge"] is False
    assert context["setup_edge_prior"] == 16.0
    assert context["conviction"] == 96.0
    assert context["effective_conviction"] == 16.0
    assert context["conviction_cap"] == 16.0
    assert "rsi_no_edge_conviction_capped" in context["warnings"]
    assert applied["rsi_context_compatibility"] == "no_edge"
    assert applied["rsi_actionability_adjustment"] < 0
    assert applied["rsi_adjusted_actionability_score"] < 60.0
    assert applied["rsi_risk_adjustment"] > 0
    assert "rsi_setup_without_measured_edge" in applied["rsi_adjustment_reason_codes"]


def test_stale_and_unknown_freshness_are_diagnostic_only_and_fail_soft():
    stale = normalize_rsi_signal_artifact(
        _rsi_artifact(observed_at="2026-07-09T00:00:00+00:00"),
        evaluated_at=_NOW,
    )
    unknown = normalize_rsi_signal_artifact(
        {
            key: value
            for key, value in _rsi_artifact().items()
            if key not in {"observed_at", "freshness_status"}
        },
        evaluated_at=_NOW,
    )
    self_asserted_fresh = normalize_rsi_signal_artifact(
        {
            key: value
            for key, value in _rsi_artifact().items()
            if key != "observed_at"
        },
        evaluated_at=_NOW,
    )

    stale_adjustment = rsi_context_adjustment(stale, directional_bias="long")
    unknown_adjustment = rsi_context_adjustment(unknown, directional_bias="long")

    assert stale.valid is True
    assert stale.freshness_status == "stale"
    assert stale_adjustment.actionability_adjustment == 0
    assert stale_adjustment.risk_adjustment == 0
    assert unknown.valid is True
    assert unknown.freshness_status == "unknown"
    assert unknown_adjustment.actionability_adjustment == 0
    assert unknown_adjustment.risk_adjustment == 0
    assert self_asserted_fresh.freshness_status == "unknown"
    assert rsi_context_adjustment(
        self_asserted_fresh,
        directional_bias="long",
    ).actionability_adjustment == 0


def test_invalid_or_future_context_does_not_borrow_aliases_or_adjust_scores():
    invalid_value = _rsi_artifact(rsi_value="not-a-number", rsi_daily=18.0)
    future = _rsi_artifact(observed_at="2026-07-12T14:00:00+00:00")
    invalid_status = _rsi_artifact(freshness_status="invalid")

    invalid_applied = apply_rsi_technical_context(
        _candidate(),
        invalid_value,
        evaluated_at=_NOW,
    )
    future_applied = apply_rsi_technical_context(
        _candidate(),
        future,
        evaluated_at=_NOW,
    )
    invalid_status_applied = apply_rsi_technical_context(
        _candidate(),
        invalid_status,
        evaluated_at=_NOW,
    )

    assert invalid_applied["rsi_context_valid"] is False
    assert invalid_applied["rsi_value"] is None
    assert invalid_applied["rsi_context"]["rsi_timeframe"] == "unspecified"
    assert invalid_applied["rsi_actionability_adjustment"] == 0
    assert invalid_applied["rsi_adjusted_actionability_score"] == 60.0
    assert future_applied["rsi_context_valid"] is False
    assert future_applied["rsi_freshness_status"] == "invalid"
    assert "rsi_timestamp_in_future" in future_applied["rsi_context"]["warnings"]
    assert future_applied["rsi_actionability_adjustment"] == 0
    assert future_applied["rsi_adjusted_risk_score"] == 40.0
    assert invalid_status_applied["rsi_context_valid"] is False
    assert invalid_status_applied["rsi_freshness_status"] == "invalid"
    assert invalid_status_applied["rsi_actionability_adjustment"] == 0


def test_adapter_outputs_are_read_only_research_metadata_with_zero_side_effects():
    applied = apply_rsi_technical_context(
        _candidate(),
        _rsi_artifact(),
        evaluated_at=_NOW,
    )

    assert applied["research_only"] is True
    assert applied["normal_rsi_signal_written"] is False
    assert applied["triggered_fade_created"] is False
    assert applied["paper_trade_created"] is False
    assert applied["trade_created"] is False
    assert applied["rsi_context_safety"] == {
        "read_only": True,
        "provider_calls": 0,
        "alerts_created": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }
    assert applied["rsi_context_version"] == RSI_TECHNICAL_CONTEXT_VERSION
    assert applied["rsi_context"]["context_version"] == RSI_TECHNICAL_CONTEXT_VERSION


def test_adapter_rejects_cross_asset_context_before_score_fusion():
    applied = apply_rsi_technical_context(
        _candidate(symbol="OTHER", coin_id="other"),
        _rsi_artifact(symbol="BTC", coin_id="bitcoin"),
        evaluated_at=_NOW,
    )

    assert applied["rsi_context_valid"] is False
    assert applied["rsi_actionability_adjustment"] == 0
    assert applied["rsi_risk_adjustment"] == 0
    assert applied["rsi_adjusted_actionability_score"] == 60.0
    assert "rsi_asset_identity_mismatch" in applied["rsi_context"]["warnings"]


def test_integrated_builder_applies_unique_exact_rsi_context_before_canonical_reevaluation():
    baseline = _build_integrated({"market_anomaly": [_integrated_market_row()]})
    enriched = _build_integrated({
        "market_anomaly": [_integrated_market_row()],
        "rsi_signal_context": [_rsi_artifact()],
    })

    assert len(baseline) == len(enriched) == 1
    base_row = baseline[0]
    row = enriched[0]
    assert row["candidate_id"] == base_row["candidate_id"]
    assert row["rsi_context_valid"] is True
    assert row["rsi_context"]["symbol"] == "RSICTX"
    assert row["rsi_context"]["coin_id"] == "rsi-context"
    assert row["rsi_context_compatibility"] == "compatible"
    assert row["rsi_actionability_adjustment"] > 0
    assert row["rsi_risk_adjustment"] < 0
    assert row["actionability_score"] != base_row["actionability_score"]
    assert row["risk_score"] < base_row["risk_score"]
    assert row["actionability_score_components"][
        "rsi_technical_context_bonus_points"
    ] == row["rsi_actionability_adjustment"]
    assert row["risk_score_components"][
        "rsi_technical_context_adjustment"
    ] == row["rsi_risk_adjustment"]
    assert row["research_only"] is True
    assert row["created_alert"] is False
    assert row["normal_rsi_signal_written"] is False
    assert row["paper_trade_created"] is False
    assert row["triggered_fade_created"] is False


def test_integrated_builder_never_creates_rsi_only_candidates_and_fails_closed_on_ambiguity():
    rsi = _rsi_artifact()
    assert _build_integrated({"rsi_signal_context": [rsi]}) == ()

    baseline = _build_integrated({"market_anomaly": [_integrated_market_row()]})[0]
    ambiguous = _build_integrated({
        "market_anomaly": [_integrated_market_row()],
        "rsi_signal_context": [rsi, dict(rsi)],
    })[0]
    mismatched = _build_integrated({
        "market_anomaly": [_integrated_market_row()],
        "rsi_signal_context": [_rsi_artifact(coin_id="different-asset")],
    })[0]
    ticker_only = _rsi_artifact()
    ticker_only.pop("coin_id")
    incomplete = _build_integrated({
        "market_anomaly": [_integrated_market_row()],
        "rsi_signal_context": [ticker_only],
    })[0]

    for row in (ambiguous, mismatched, incomplete):
        assert row["candidate_id"] == baseline["candidate_id"]
        assert "rsi_context_version" not in row
        assert row["actionability_score"] == baseline["actionability_score"]
        assert row["risk_score"] == baseline["risk_score"]


def test_configured_local_rsi_sidecar_loads_read_only_and_reaches_builder(
    tmp_path,
    monkeypatch,
):
    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    path = tmp_path / "rsi-signals.json"
    original = json.dumps({"signals": [_rsi_artifact()]}, sort_keys=True) + "\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(config, "EVENT_ALPHA_RSI_SIGNAL_CONTEXT_PATH", path)

    sidecars, manifest = integrated_radar._run_or_load_sidecars(
        namespace_dir=tmp_path / "cycle",
        fixture=False,
        observed_at=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        profile="fixture",
        artifact_namespace="rsi_context_test",
        run_mode="fixture",
        run_id="rsi-context-run",
        input_mode=integrated_radar.INPUT_MODE_RUN_SIDECARS,
        coinalyze_namespace=None,
    )
    sidecars["market_anomaly"] = (_integrated_market_row(),)
    rows = _build_integrated(sidecars)
    rsi_manifest = next(
        item for item in manifest if item["sidecar_name"] == "rsi_signal_context"
    )

    assert len(rows) == 1
    assert rows[0]["rsi_context_valid"] is True
    assert rows[0]["rsi_context_safety"]["read_only"] is True
    assert rsi_manifest["mode"] == "loaded_local_read_only"
    assert rsi_manifest["configured"] is True
    assert rsi_manifest["row_counts"] == {"rows": 1}
    assert path.read_text(encoding="utf-8") == original
