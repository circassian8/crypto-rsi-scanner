"""Non-finite numeric evidence must remain unavailable across Radar layers."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest


def test_nonfinite_values_cannot_create_market_confirmation():
    from crypto_rsi_scanner.event_alpha.radar import market_confirmation

    now = "2026-06-15T16:00:00Z"
    result = market_confirmation.evaluate_market_confirmation(
        {
            "market": {
                "return_24h": float("inf"),
                "volume_zscore_24h": float("inf"),
                "volume_to_market_cap": float("inf"),
            },
            "derivatives": {
                "derivatives_crowding": float("inf"),
                "open_interest_24h_change_pct": float("inf"),
                "funding_rate_8h": float("inf"),
            },
            "playbook_type": "listing_liquidity_event",
            "now": now,
            "market_context_observed_at": now,
            "market_context_max_age_hours": float("inf"),
        }
    )

    assert result.level == "none"
    assert result.market_confirmation_score == 0.0
    assert result.data_quality == 0.0
    assert result.score_components == {}
    assert "insufficient_data" in result.reasons
    json.dumps(asdict(result), allow_nan=False)


def test_nonfinite_values_cannot_create_reaction_or_derivatives_crowding():
    from crypto_rsi_scanner.event_alpha.radar import derivatives_crowding
    from crypto_rsi_scanner.event_alpha.radar import market_reaction

    now = "2026-06-15T16:00:00Z"
    reaction = market_reaction.evaluate_market_reaction(
        {
            "source_class": "broad_news",
            "source_pack": "market_anomaly_pack",
            "impact_path_type": "market_dislocation_unknown",
            "market_snapshot": {
                "return_24h": float("inf"),
                "return_4h": float("inf"),
                "relative_return_vs_btc": float("inf"),
                "volume_zscore_24h": float("inf"),
                "liquidity_usd": float("inf"),
            },
        }
    )
    reaction_snapshot = reaction.market_state_snapshot.to_dict()

    assert reaction.market_state == "no_reaction"
    assert "volume_turnover_zscore" not in reaction_snapshot
    assert "liquidity_usd" not in reaction_snapshot
    assert reaction_snapshot["observed_fields"] == 0

    state = derivatives_crowding.normalize_derivatives_state(
        {
            "symbol": "INFUSDT_PERP",
            "coin_id": "inf",
            "observed_at": now,
            "freshness_status": "fresh",
            "open_interest": float("inf"),
            "open_interest_delta_24h": float("inf"),
            "funding_rate": float("inf"),
            "funding_zscore": float("inf"),
            "liquidation_imbalance": float("inf"),
            "perp_spot_volume_ratio": float("inf"),
        },
        observed_at=now,
    )

    for field in (
        "open_interest",
        "open_interest_delta_24h",
        "funding_rate",
        "funding_zscore",
        "liquidation_imbalance",
        "perp_spot_volume_ratio",
    ):
        assert state[field] is None
    assert derivatives_crowding._crowding_evidence(state) == ()
    assert state["raw_payload_redacted"]["open_interest"] == "<non_finite>"
    json.dumps(state, allow_nan=False)


def test_boolean_numerics_cannot_become_market_or_catalyst_evidence(tmp_path):
    from crypto_rsi_scanner.event_alpha.radar import asset_registry
    from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution
    from crypto_rsi_scanner.event_alpha.radar import derivatives_crowding
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_enrichment
    from crypto_rsi_scanner.event_alpha.radar import market_reaction
    from crypto_rsi_scanner.event_alpha.radar import market_state
    from crypto_rsi_scanner.event_alpha.radar import price_history

    now = "2026-07-20T12:00:00Z"
    raw_market = {
        "id": "boolean-market",
        "coin_id": "boolean-market",
        "symbol": "BOOL",
        "observed_at": now,
        "return_unit": "fraction",
        "price": True,
        "current_price": True,
        "return_1h": True,
        "return_4h": True,
        "return_24h": True,
        "relative_return_vs_btc_4h": True,
        "market_cap": True,
        "total_volume": True,
        "volume_24h": True,
        "volume_zscore_24h": True,
        "liquidity_usd": True,
        "spread_bps": True,
        "open_interest_delta": True,
        "funding_level": True,
        "funding_zscore": True,
        "liquidation_imbalance": True,
        "price_change_percentage_24h_in_currency": True,
        "sparkline_in_7d": {"price": [True] * 30},
    }

    snapshot = market_state.snapshot_from_market_row(raw_market, observed_at=now)
    for field in (
        "price",
        "return_1h",
        "return_4h",
        "return_24h",
        "relative_return_vs_btc_4h",
        "volume_24h",
        "volume_zscore_24h",
        "volume_to_market_cap",
        "liquidity_usd",
        "spread_bps",
        "open_interest_delta",
        "funding_level",
        "funding_zscore",
        "liquidation_imbalance",
    ):
        assert getattr(snapshot, field) is None
    assert snapshot.observed_fields == ()

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        [raw_market],
        observed_at=now,
    )
    assert anomalies == []
    assert snapshots[0]["observed_fields"] == []

    reaction = market_reaction.evaluate_market_reaction({
        "market_snapshot": raw_market,
        "derivatives_snapshot": raw_market,
    })
    assert reaction.market_state == "no_reaction"
    assert reaction.market_state_snapshot.observed_fields == 0

    derivatives = derivatives_crowding.normalize_derivatives_state(
        raw_market,
        observed_at=now,
    )
    for field in (
        "open_interest",
        "open_interest_delta_1h",
        "open_interest_delta_4h",
        "open_interest_delta_24h",
        "funding_rate",
        "funding_zscore",
        "liquidation_imbalance",
        "perp_spot_volume_ratio",
    ):
        assert derivatives[field] is None
    assert derivatives_crowding._crowding_evidence(derivatives) == ()

    enrichment = market_enrichment.market_snapshot_from_row(raw_market)
    for field in (
        "price",
        "market_cap",
        "volume_24h",
        "return_1h",
        "return_4h",
        "return_24h",
        "return_7d",
        "volume_zscore_24h",
    ):
        assert field not in enrichment

    universe = tmp_path / "boolean-universe.json"
    universe.write_text(json.dumps({
        "rows": [{
            "id": "boolean-market",
            "symbol": "BOOL",
            "market_cap_rank": True,
            "total_volume": True,
        }]
    }), encoding="utf-8")
    assets = asset_registry.assets_from_coingecko_universe(universe)
    assert len(assets) == 1
    assert assets[0].liquidity_tier is None

    assert price_history._float(True) is None
    assert catalyst_attribution._finite_number(True) is None


def test_nonfinite_or_shadowed_zero_universe_values_cannot_derive_liquidity(tmp_path):
    from crypto_rsi_scanner.event_alpha.radar import asset_registry

    path = tmp_path / "universe.json"
    path.write_text(
        """{"rows":[
            {"id":"infinite","symbol":"INF","total_volume":1e309},
            {"id":"zero","symbol":"ZERO","market_cap_rank":0,"rank":1,
             "total_volume":0,"volume_usd":100000000}
        ]}""",
        encoding="utf-8",
    )

    assets = {asset.coin_id: asset for asset in asset_registry.assets_from_coingecko_universe(path)}

    assert assets["infinite"].liquidity_tier is None
    assert assets["zero"].liquidity_tier is None


def test_derivatives_zero_age_and_funding_zscore_remain_observed():
    from crypto_rsi_scanner.event_alpha.radar import derivatives_crowding

    assert derivatives_crowding._completed_move(
        {"return_24h": 0.15, "event_age_hours": 0.0},
        "no_reaction",
    ) is True

    report = derivatives_crowding.format_derivatives_crowding_report(
        state_rows=[
            {
                "symbol": "ZERO",
                "coin_id": "zero",
                "provider": "fixture",
                "freshness_status": "fresh",
                "funding_zscore": 0.0,
            }
        ],
        candidate_rows=[],
    )

    assert "funding_z=0 " in report
    assert "funding_z=n/a" not in report


def test_market_no_send_normalization_closes_invalid_numeric_basis_claims():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    observed_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    rows, audit = market_no_send_features.normalize_market_rows(
        [
            {
                "id": "invalid-evidence",
                "coin_id": "invalid-evidence",
                "symbol": "BAD",
                "name": "Invalid Evidence",
                "price": 10,
                "return_unit": "fraction",
                "return_1h": 0.01,
                "return_4h": 0.02,
                "return_24h": 0.03,
                "market_cap": 100_000_000,
                "total_volume": 1_000_000,
                "volume_zscore_24h": float("inf"),
                "liquidity_usd": -1,
                "spread_bps": float("inf"),
            },
            {
                "id": "nonfinite-universe-audit",
                "symbol": "INFAUDIT",
                "name": "Nonfinite Universe Audit",
                "market_cap_rank": float("inf"),
                "market_cap": float("inf"),
                "total_volume": 1_000_000,
            },
        ],
        top_n=1,
        observed_at=observed_at,
        provider="coingecko",
        data_mode="live",
        request_cache_artifact="market.json",
        request_ledger_artifact="ledger.json",
        candidate_source_mode="live_no_send",
        decision_radar_campaign_counted=True,
        burn_in_counted=False,
        safety_counters={},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["volume_zscore_24h"] == 0.0
    assert row["volume_zscore_basis"] == "cross_sectional_log_turnover_proxy"
    assert row["liquidity_usd"] == 1_000_000
    assert row["liquidity_basis"] == "coingecko_total_volume_24h_proxy"
    assert row["spread_status"] == "unavailable"
    assert row["market_feature_basis"]["spread"] == "unavailable"
    assert "spread_bps" not in row
    assert audit["spread_available_count"] == 0
    json.dumps({"rows": rows, "audit": audit}, allow_nan=False)


def test_market_no_send_normalization_excludes_structured_market_identities():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    observed_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    base = {
        "name": "Malformed Identity",
        "current_price": 10,
        "market_cap": 100_000_000,
        "total_volume": 1_000_000,
    }
    rows, audit = market_no_send_features.normalize_market_rows(
        [
            {**base, "id": {"borrowed": "bitcoin"}, "symbol": "BTC"},
            {**base, "id": "bitcoin", "symbol": ["BTC"]},
            {
                **base,
                "id": "bitcoin",
                "symbol": "BTC",
                "canonical_asset_id": {"borrowed": "bitcoin"},
            },
        ],
        top_n=3,
        observed_at=observed_at,
        provider="coingecko",
        data_mode="live",
        request_cache_artifact="market.json",
        request_ledger_artifact="ledger.json",
        candidate_source_mode="live_no_send",
        decision_radar_campaign_counted=True,
        burn_in_counted=False,
        safety_counters={},
    )

    assert rows == []
    assert audit["excluded_by_reason"] == {
        "invalid_canonical_identity": 1,
        "missing_identity": 2,
    }


def test_market_no_send_rejects_malformed_return_unit_metadata():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    observed_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    base = {
        "id": "unit-contract",
        "coin_id": "unit-contract",
        "symbol": "UNIT",
        "name": "Unit Contract",
        "current_price": 10,
        "return_1h": 0.05,
        "return_4h": 0.10,
        "return_24h": 0.16,
        "relative_return_vs_btc_4h": 0.10,
        "market_cap": 100_000_000,
        "total_volume": 10_000_000,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 10_000_000,
        "spread_bps": 5.0,
    }
    invalid_metadata = (
        {"return_unit": {"borrowed": "fraction"}},
        {"return_unit": True},
        {"return_unit": "basis_points"},
        {"return_unit": "fraction", "source_return_unit": "percent_points"},
        {"return_units": ["fraction"]},
        {"return_units": {"return_4h": {"unit": "fraction"}}},
        {
            "return_units": {"return_4h": "fraction"},
            "field_return_units": {"return_4h": "percent_points"},
        },
    )

    for metadata in invalid_metadata:
        with pytest.raises(
            ValueError,
            match="^market_row_return_unit_metadata_invalid$",
        ):
            market_no_send_features.normalize_market_rows(
                [{**base, **metadata}],
                top_n=1,
                observed_at=observed_at,
                provider="fixture",
                data_mode="mock",
                request_cache_artifact="market.json",
                request_ledger_artifact="ledger.json",
                candidate_source_mode="mocked_fixture",
                decision_radar_campaign_counted=False,
                burn_in_counted=False,
                safety_counters={},
            )


def test_market_state_rejects_malformed_unit_metadata_without_anomaly():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_state

    observed_at = "2026-07-20T17:00:00Z"
    row = {
        "id": "malformed-units",
        "coin_id": "malformed-units",
        "symbol": "BADUNIT",
        "return_unit": {"borrowed": "fraction"},
        "return_4h": 0.10,
        "return_24h": 0.16,
        "relative_return_vs_btc_4h": 0.10,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 100_000_000.0,
        "spread_bps": 5.0,
        "freshness_status": "fresh",
    }

    snapshot = market_state.snapshot_from_market_row(row, observed_at=observed_at)
    assert snapshot.source_return_unit == "unknown"
    assert snapshot.return_4h is None
    assert snapshot.return_24h is None
    assert snapshot.relative_return_vs_btc_4h is None
    assert "invalid_source_return_unit_metadata" in snapshot.unit_warnings

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        [row],
        observed_at=observed_at,
    )
    assert anomalies == []
    assert "invalid_source_return_unit_metadata" in snapshots[0]["unit_warnings"]


def test_market_no_send_preserves_valid_mixed_return_units():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
    from crypto_rsi_scanner.event_alpha.radar import market_state

    observed_at = datetime(2026, 7, 20, 17, tzinfo=timezone.utc)
    rows, _audit = market_no_send_features.normalize_market_rows(
        [{
            "id": "mixed-units",
            "coin_id": "mixed-units",
            "symbol": "MIXED",
            "name": "Mixed Units",
            "current_price": 10,
            "return_unit": "fractions",
            "return_4h": 0.10,
            "return_24h": 0.16,
            "relative_return_vs_btc_4h": 10.0,
            "return_units": {
                "relative_return_vs_btc_4h": "percentage",
            },
            "market_cap": 100_000_000,
            "total_volume": 10_000_000,
            "volume_zscore_24h": 3.0,
            "liquidity_usd": 100_000_000.0,
            "spread_bps": 5.0,
        }],
        top_n=1,
        observed_at=observed_at,
        provider="fixture",
        data_mode="mock",
        request_cache_artifact="market.json",
        request_ledger_artifact="ledger.json",
        candidate_source_mode="mocked_fixture",
        decision_radar_campaign_counted=False,
        burn_in_counted=False,
        safety_counters={},
    )

    assert rows[0]["return_unit"] == "fraction"
    assert rows[0]["return_units"] == {
        "relative_return_vs_btc_4h": "percent_points",
    }
    snapshot = market_state.snapshot_from_market_row(
        rows[0],
        observed_at=observed_at,
    )
    assert snapshot.return_4h == 10.0
    assert snapshot.return_24h == 16.0
    assert snapshot.relative_return_vs_btc_4h == 10.0
    assert snapshot.unit_warnings == ()

    _snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        rows,
        observed_at=observed_at,
    )
    assert [row["anomaly_type"] for row in anomalies] == ["confirmed_breakout"]


def test_malformed_benchmark_units_cannot_create_relative_breakout():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    rows = [
        {
            "id": "bitcoin",
            "coin_id": "bitcoin",
            "symbol": "BTC",
            "return_unit": {"borrowed": "fraction"},
            "return_4h": 0.10,
            "return_24h": 0.10,
            "freshness_status": "fresh",
        },
        {
            "id": "benchmark-victim",
            "coin_id": "benchmark-victim",
            "symbol": "VICTIM",
            "return_unit": "fraction",
            "return_4h": 0.20,
            "return_24h": 0.20,
            "volume_zscore_24h": 3.0,
            "liquidity_usd": 100_000_000.0,
            "spread_bps": 5.0,
            "freshness_status": "fresh",
        },
    ]

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        rows,
        observed_at="2026-07-21T10:45:00Z",
    )
    by_symbol = {row["symbol"]: row for row in snapshots}

    assert by_symbol["VICTIM"]["return_4h"] == 20.0
    assert by_symbol["VICTIM"]["relative_return_vs_btc_4h"] is None
    assert "invalid_btc_benchmark_return_unit_metadata" in by_symbol["VICTIM"][
        "unit_warnings"
    ]
    assert anomalies == []


def test_unit_warnings_block_market_anomaly_classification():
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner

    row = {
        "id": "bad-scale",
        "coin_id": "bad-scale",
        "symbol": "SCALE",
        "return_unit": "fraction",
        "return_4h": 10.0,
        "return_24h": 10.0,
        "relative_return_vs_btc_4h": 10.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 100_000_000.0,
        "spread_bps": 5.0,
        "freshness_status": "fresh",
    }

    snapshots, anomalies = market_anomaly_scanner.scan_market_rows(
        [row],
        observed_at="2026-07-21T10:57:00Z",
    )

    assert snapshots[0]["return_4h"] == 1000.0
    assert "implausible_fraction_return:return_4h" in snapshots[0]["unit_warnings"]
    assert anomalies == []
    assert market_anomaly_scanner.classify_market_state(
        {
            "return_4h": 12.0,
            "return_24h": 18.0,
            "relative_return_vs_btc_4h": 10.0,
            "volume_zscore_24h": 3.0,
            "unit_warnings": ["invalid_source_return_unit_metadata"],
        }
    ) == market_anomaly_scanner.NO_REACTION
    assert market_anomaly_scanner.classify_market_state(
        {
            "return_4h": 12.0,
            "return_24h": 18.0,
            "relative_return_vs_btc_4h": 10.0,
            "volume_zscore_24h": 3.0,
            "unit_warnings": "malformed-warning-container",
        }
    ) == market_anomaly_scanner.NO_REACTION


def test_market_no_send_normalization_preserves_canonical_numeric_zeroes():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    observed_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    row = market_no_send_features._normalize_market_row(
        {
            "id": "zero-evidence",
            "coin_id": "zero-evidence",
            "symbol": "ZERO",
            "price": 10,
            "return_unit": "fraction",
            "return_1h": 0.0,
            "return_4h": 0.0,
            "return_24h": 0.0,
            "market_cap": 100,
            "total_volume": 0,
            "volume_24h": 999,
            "volume_zscore_24h": 0,
            "liquidity_usd": 0,
            "spread_bps": 0,
        },
        observed_at=observed_at,
        provider="fixture",
        data_mode="mock",
        source_mode="mocked_fixture",
        request_cache_artifact="market.json",
        request_ledger_artifact="ledger.json",
        decision_radar_campaign_counted=False,
        burn_in_counted=False,
        proxy_zscore=9.0,
        safety_counters={},
    )

    assert row["total_volume"] == 0
    assert row["volume_24h"] == 0
    assert row["volume_to_market_cap"] == 0
    assert row["volume_zscore_24h"] == 0
    assert row["volume_zscore_basis"] == "provider_observed"
    assert row["liquidity_usd"] == 0
    assert row["liquidity_basis"] == "provider_observed"
    assert row["spread_bps"] == 0
    assert row["spread_status"] == "verified"
    assert market_no_send_features.finite_float(True) is None


def test_market_quality_counts_preserve_zero_and_close_invalid_counts():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    rows = [
        {
            "market_state_snapshot": {
                "market_data_quality": {
                    "direct_feature_count": 0,
                    "proxy_feature_count": 0,
                },
                "direct_market_feature_count": 7,
                "proxy_market_feature_count": 8,
            },
            "direct_market_feature_count": 9,
            "proxy_market_feature_count": 10,
        },
        {
            "market_state_snapshot": {
                "market_data_quality": {
                    "direct_feature_count": float("inf"),
                    "proxy_feature_count": True,
                },
                "direct_market_feature_count": 11,
                "proxy_market_feature_count": 12,
            },
            "direct_market_feature_count": 13,
            "proxy_market_feature_count": 14,
        },
        {
            "market_state_snapshot": {
                "market_data_quality": {
                    "direct_feature_count": -1,
                    "proxy_feature_count": 1.5,
                },
                "direct_market_feature_count": 15,
                "proxy_market_feature_count": 16,
            },
        },
    ]

    counts = market_no_send_features.market_quality_counts_from_rows(rows)

    assert counts["direct_feature_count"] == 0
    assert counts["proxy_feature_count"] == 0


def test_market_quality_counts_fall_back_only_when_canonical_count_is_blank():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_features

    counts = market_no_send_features.market_quality_counts_from_rows([
        {
            "market_state_snapshot": {
                "market_data_quality": {
                    "direct_feature_count": None,
                    "proxy_feature_count": " ",
                },
                "direct_market_feature_count": "4",
                "proxy_market_feature_count": 2.0,
            },
            "direct_market_feature_count": 9,
            "proxy_market_feature_count": 10,
        },
    ])

    assert counts["direct_feature_count"] == 4
    assert counts["proxy_feature_count"] == 2


def test_request_telemetry_preserves_zero_and_closes_malformed_numbers():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send

    telemetry = market_no_send._safe_request_telemetry(
        {
            "duration_ms": float("inf"),
            "http_status": float("nan"),
            "result_count": 0,
            "retry_count": True,
        },
        fallback_result_count=30,
        succeeded=True,
    )

    assert telemetry["duration_ms"] == 0
    assert telemetry["http_status"] is None
    assert telemetry["result_count"] == 0
    assert telemetry["retry_count"] == 0
    json.dumps(telemetry, allow_nan=False)


def test_request_telemetry_uses_fallback_only_for_missing_or_blank_counts():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send

    missing = market_no_send._safe_request_telemetry(
        {},
        fallback_result_count=30,
        succeeded=True,
    )
    blank = market_no_send._safe_request_telemetry(
        {"result_count": " ", "http_status": " "},
        fallback_result_count=30,
        succeeded=True,
    )
    unavailable = market_no_send._safe_request_telemetry(
        {"http_status": None},
        fallback_result_count=30,
        succeeded=True,
    )

    assert missing["result_count"] == 30
    assert missing["http_status"] == 200
    assert blank["result_count"] == 30
    assert blank["http_status"] == 200
    assert unavailable["http_status"] is None


def test_shared_failure_telemetry_reuses_strict_numeric_projection():
    from crypto_rsi_scanner.event_alpha.operations import (
        market_no_send_campaign_provider,
    )

    attempted_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    telemetry = market_no_send_campaign_provider._sanitized_telemetry(
        {
            "duration_ms": float("inf"),
            "http_status": float("nan"),
            "result_count": 0,
            "retry_count": True,
            "cache_behavior": "credential_cache",
            "headers": {"authorization": "must-not-survive"},
        },
        attempted_at=attempted_at,
        error_class="TimeoutError",
    )

    assert telemetry["duration_ms"] == 0
    assert telemetry["http_status"] is None
    assert telemetry["result_count"] == 0
    assert telemetry["retry_count"] == 0
    assert telemetry["cache_behavior"] == "network"
    assert telemetry["request_started_at"] == attempted_at.isoformat()
    assert telemetry["request_ended_at"] == attempted_at.isoformat()
    assert "headers" not in telemetry
    json.dumps(telemetry, allow_nan=False)


def test_provider_health_telemetry_is_strict_before_it_is_persisted():
    from crypto_rsi_scanner.event_alpha.operations import market_no_send_provider

    started_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    telemetry = market_no_send_provider._request_telemetry(
        {
            "duration_ms": float("inf"),
            "http_status": float("nan"),
            "retry_count": True,
        },
        started_at=started_at,
        started_monotonic=0,
        result_count=0,
        error_class="TimeoutError",
    )

    assert telemetry["duration_ms"] == 0
    assert telemetry["http_status"] is None
    assert telemetry["result_count"] == 0
    assert telemetry["retry_count"] == 0
    assert telemetry["error_class"] == "TimeoutError"
    json.dumps(telemetry, allow_nan=False)


def test_campaign_count_projection_is_strict_and_shared_across_surfaces():
    from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign
    from crypto_rsi_scanner.event_alpha.operations import (
        market_observation_campaign_baseline,
        market_observation_campaign_contract,
        market_observation_campaign_outcome_gaps,
        market_observation_campaign_render,
    )

    surfaces = (
        market_observation_campaign._int,
        market_observation_campaign_baseline._int,
        market_observation_campaign_contract.nonnegative_int,
        market_observation_campaign_outcome_gaps._int,
        market_observation_campaign_render._int,
    )
    for project in surfaces:
        assert project(3) == 3
        for invalid in (True, -1, 1.5, float("inf"), float("nan"), "3"):
            assert project(invalid) == 0

    assert market_observation_campaign_render._number(float("inf")) == "—"
    assert market_observation_campaign_render._number(float("nan")) == "—"


def test_campaign_legacy_cadence_rejects_nonintegral_spacing():
    from crypto_rsi_scanner.event_alpha.operations import (
        market_observation_campaign_cadence,
    )
    from crypto_rsi_scanner.event_alpha.radar import market_history

    observed_at = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    default_spacing = market_history.MarketHistoryConfig().minimum_observation_spacing
    for invalid in (True, -1, 1.5, float("inf"), float("nan"), "60"):
        next_at = market_observation_campaign_cadence.legacy_next_eligible({
            "baseline_newest_counted_observed_at": observed_at.isoformat(),
            "minimum_observation_spacing_seconds": invalid,
        })

        assert next_at is not None
        assert datetime.fromisoformat(next_at) - observed_at == default_spacing

    assert market_observation_campaign_cadence.legacy_next_eligible({
        "baseline_newest_counted_observed_at": observed_at.isoformat(),
        "minimum_observation_spacing_seconds": 60,
    }) == (observed_at + timedelta(seconds=60)).isoformat()


def test_validation_prices_reject_nonfinite_and_shadowed_invalid_values():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    observed_at = "2026-07-19T06:00:00Z"

    assert event_validation._num(float("inf")) is None
    assert event_validation._num(float("nan")) is None
    assert event_validation._num(True) is None
    assert event_validation._parse_price_candle({
        "timestamp": observed_at,
        "close": 0,
        "price": 10,
    }) is None
    assert event_validation._parse_price_candle({
        "timestamp": "not-a-timestamp",
        "time": observed_at,
        "close": 10,
    }) is None

    candle = event_validation._parse_price_candle({
        "timestamp": observed_at,
        "close": 10,
        "high": float("inf"),
        "low": True,
    })
    assert candle is not None
    assert candle.high is None
    assert candle.low is None


def test_validation_outcome_does_not_replace_invalid_supplied_entry_price():
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    decision_time = datetime(2026, 7, 19, 6, tzinfo=timezone.utc)
    candles = [
        event_validation.ValidationOutcomeCandle(
            decision_time,
            close=10,
            high=10,
            low=10,
        ),
        event_validation.ValidationOutcomeCandle(
            decision_time.replace(day=20),
            close=9,
            high=9,
            low=9,
        ),
        event_validation.ValidationOutcomeCandle(
            decision_time.replace(day=22),
            close=8,
            high=8,
            low=8,
        ),
        event_validation.ValidationOutcomeCandle(
            decision_time.replace(day=26),
            close=7,
            high=7,
            low=7,
        ),
    ]

    for invalid_entry in (0, float("inf"), True, "not-a-price"):
        result = event_validation.fill_validation_outcomes(
            [{
                "signal_type": "SHORT_TRIGGERED",
                "asset_coin_id": "invalid-entry",
                "trigger_observed_at": decision_time.isoformat(),
                "entry_reference_price": invalid_entry,
            }],
            {"invalid-entry": candles},
        )

        assert result.filled_rows == 0
        assert result.insufficient_history_rows == 1
        assert "post_event_return_72h" not in result.rows[0]


def test_integrated_liquidity_checks_preserve_zero_and_reject_invalid_values():
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import merge_policy

    assert merge_policy._float_value(float("inf")) is None
    assert merge_policy._float_value(True) is None
    assert merge_policy._dex_liquidity_sane({
        "dex_liquidity_snapshot": {
            "pool_liquidity_usd": 0,
            "liquidity_usd": 2_000_000,
        },
        "pool_liquidity_usd": 3_000_000,
    }) is False
    assert merge_policy._dex_liquidity_sane({
        "dex_liquidity_snapshot": {"pool_liquidity_usd": float("inf")},
    }) is False
    assert merge_policy._family_liquidity_sane([{
        "market_snapshot": {
            "liquidity_usd": 0,
            "order_book_depth_2pct": 2_000_000,
            "spread_bps": 0,
        },
    }]) is False
    assert merge_policy._family_liquidity_sane([{
        "market_snapshot": {
            "liquidity_usd": 2_000_000,
            "spread_bps": 0,
            "bid_ask_spread_bps": 300,
        },
    }]) is True
    assert merge_policy._family_liquidity_sane([{
        "market_snapshot": {
            "liquidity_usd": float("inf"),
            "spread_bps": 0,
        },
    }]) is False


def test_integrated_representatives_rank_canonical_zero_not_legacy_alias():
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import merge_policy

    dex_zero = {
        "candidate_id": "dex-zero",
        "row_type": "event_dex_pool_state",
        "pool_liquidity_usd": 0,
        "liquidity_usd": 10_000_000,
        "dex_volume_24h": 0,
        "volume_24h": 10_000_000,
    }
    dex_observed = {
        "candidate_id": "dex-observed",
        "row_type": "event_dex_pool_state",
        "pool_liquidity_usd": 1_000,
        "dex_volume_24h": 1_000,
    }
    protocol_zero = {
        "candidate_id": "protocol-zero",
        "row_type": "event_protocol_fundamentals",
        "tvl_usd": 0,
        "tvl": 10_000_000,
    }
    protocol_observed = {
        "candidate_id": "protocol-observed",
        "row_type": "event_protocol_fundamentals",
        "tvl_usd": 1_000,
    }

    assert merge_policy._best_dex_row([dex_zero, dex_observed])["candidate_id"] == "dex-observed"
    assert (
        merge_policy._best_protocol_row([protocol_zero, protocol_observed])["candidate_id"]
        == "protocol-observed"
    )


def test_outcome_metrics_preserve_zero_and_fail_closed_on_invalid_aliases():
    from crypto_rsi_scanner.event_alpha.outcomes import outcome_artifacts

    row = {
        "observed_at": "2026-07-19T06:00:00Z",
        "entry_reference_price": 10,
        "primary_horizon_return": 0.5,
        "max_favorable_excursion": 0.8,
        "max_adverse_excursion": 0.4,
        "btc_primary_horizon_return": 0,
        "btc_return_primary": 0.2,
        "alt_basket_primary_horizon_return": 0,
        "alt_basket_return_primary": 0.3,
    }
    metrics = outcome_artifacts.compute_playbook_outcome_metrics(
        row,
        returns={
            "primary_horizon_return": 0,
            "max_favorable_excursion": 0,
            "max_adverse_excursion": 0.1,
        },
    )

    assert metrics["underperformance_vs_btc"] == 0
    assert metrics["underperformance_vs_alt_basket"] == 0
    assert metrics["mfe_mae_ratio"] == 0

    invalid = outcome_artifacts.compute_playbook_outcome_metrics(
        row,
        returns={
            "primary_horizon_return": float("inf"),
            "max_favorable_excursion": float("inf"),
            "max_adverse_excursion": 0.1,
        },
    )
    assert invalid["underperformance_vs_btc"] is None
    assert invalid["underperformance_vs_alt_basket"] is None
    assert invalid["mfe_mae_ratio"] is None
    assert outcome_artifacts._num(True) is None

    invalid_entry = outcome_artifacts.compute_playbook_outcome_metrics(
        {**row, "entry_reference_price": 0},
        price_rows=[{
            "timestamp": "2026-07-19T07:00:00Z",
            "close": 20,
        }],
        returns={"primary_horizon_return": 0},
    )
    assert invalid_entry["underperformance_vs_btc"] is None
    assert invalid_entry["underperformance_vs_alt_basket"] is None


def test_outcome_price_extremes_do_not_fallback_from_invalid_canonical_price():
    from crypto_rsi_scanner.event_alpha.outcomes import outcome_artifacts

    rows = [{
        "timestamp": "2026-07-19T07:00:00Z",
        "high": 0,
        "low": float("inf"),
        "close": 20,
    }]

    assert outcome_artifacts._up_leg_from_prices(10, rows) is None
    assert outcome_artifacts._extreme(rows, key="high", fallback="close", mode="max") is None
    assert outcome_artifacts._extreme(rows, key="low", fallback="close", mode="min") is None
