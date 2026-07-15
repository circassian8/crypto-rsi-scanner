"""Pure rolling market-history and temporal-baseline regressions."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

import crypto_rsi_scanner.event_alpha.radar.market_history as event_market_history
import crypto_rsi_scanner.event_alpha.radar.market_history_readiness as market_history_readiness


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _row(
    asset_id: str,
    observed_at: datetime | str,
    *,
    price: float,
    volume: float,
    market_cap: float = 10_000.0,
    symbol: str | None = None,
    **extra,
) -> dict:
    return {
        "canonical_asset_id": asset_id,
        "coin_id": asset_id,
        "symbol": symbol or asset_id.upper(),
        "observed_at": observed_at.isoformat() if isinstance(observed_at, datetime) else observed_at,
        "price": price,
        "volume_24h": volume,
        "market_cap": market_cap,
        "provider": "coingecko",
        "source": "coingecko",
        "market_data_source": "coingecko",
        "data_mode": "live",
        "no_send_status": "enforced",
        "research_only": True,
        **extra,
    }


def _config(**overrides) -> event_market_history.MarketHistoryConfig:
    values = {
        "max_history_age": timedelta(days=2),
        "max_current_age": timedelta(hours=2),
        "future_tolerance": timedelta(minutes=2),
        "max_observations_per_asset": 64,
        "min_baseline_observations": 3,
        "return_horizons_hours": (1, 4),
        "anchor_tolerance_ratio": 0.05,
        "min_anchor_tolerance": timedelta(seconds=1),
        "benchmark_alignment_tolerance": timedelta(seconds=1),
    }
    values.update(overrides)
    return event_market_history.MarketHistoryConfig(**values)


def _three_asset_history(hours: int = 10) -> list[dict]:
    rows: list[dict] = []
    for offset in range(hours, 0, -1):
        step = hours - offset
        timestamp = NOW - timedelta(hours=offset)
        rows.extend((
            _row("move-token", timestamp, price=100 + step * 2, volume=1_000 + step * 100),
            _row("bitcoin", timestamp, price=200 + step, volume=5_000 + step * 120, symbol="BTC"),
            _row(
                "ethereum",
                timestamp,
                price=1_000 + step * 5,
                volume=4_000 + step * 90,
                symbol="ETH",
            ),
        ))
    return rows


def test_market_history_enriches_temporal_features_and_preserves_lineage_and_basis():
    current = _row(
        "MOVE-TOKEN",
        NOW,
        price=120,
        volume=2_200,
        data_acquisition_mode="live_provider",
        candidate_source_mode="live_no_send",
        provider_generation_id="pilot-run-1",
        provider_source_artifact_sha256="a" * 64,
        request_ledger_path="event_market_no_send_request_ledger.json",
        request_ledger_sha256="b" * 64,
        provenance_contract_valid=True,
        burn_in_eligible=True,
        burn_in_counted=True,
        volume_zscore_24h=9.9,
        volume_zscore_basis="cross_sectional_log_turnover_proxy",
        market_feature_evidence={
            "liquidity_usd": {"basis": "provider_observed", "provider": "coingecko"},
        },
    )
    benchmarks = [
        _row("bitcoin", NOW, price=210, volume=6_300, symbol="BTC"),
        _row("ethereum", NOW, price=1_050, volume=5_000, symbol="ETH"),
    ]

    result = event_market_history.enrich_market_rows_with_history(
        [current, *benchmarks],
        _three_asset_history(),
        now=NOW,
        config=_config(),
    )

    enriched = result.enriched_rows[0]
    assert enriched["canonical_asset_id"] == "MOVE-TOKEN"
    assert enriched["provider"] == "coingecko"
    assert enriched["source"] == "coingecko"
    assert enriched["data_mode"] == "live"
    assert enriched["no_send_status"] == "enforced"
    assert enriched["research_only"] is True
    assert enriched["market_history"]["canonical_asset_id"] == "move-token"
    assert enriched["market_history"]["status"] == "warm"
    assert enriched["temporal_return_1h"] == pytest.approx((120 / 118 - 1) * 100)
    assert enriched["temporal_return_4h"] == pytest.approx((120 / 112 - 1) * 100)
    assert enriched["temporal_return_zscore_1h"] is not None
    assert enriched["temporal_return_volatility_1h"] > 0
    assert enriched["temporal_volatility_zscore_1h"] is not None
    assert enriched["temporal_relative_return_vs_btc_1h"] == pytest.approx(
        (120 / 118 - 1) * 100 - (210 / 209 - 1) * 100,
    )
    assert enriched["temporal_relative_return_vs_eth_4h"] == pytest.approx(
        (120 / 112 - 1) * 100 - (1_050 / 1_030 - 1) * 100,
    )
    assert enriched["temporal_relative_return_vs_btc_1h_zscore"] is not None
    assert enriched["volume_zscore_24h"] == enriched["temporal_volume_zscore_24h"]
    assert enriched["volume_zscore_basis"] == event_market_history.TEMPORAL_BASELINE_BASIS
    assert enriched["cross_sectional_volume_zscore_24h"] == 9.9
    assert enriched["cross_sectional_volume_zscore_basis"] == "cross_sectional_log_turnover_proxy"
    assert enriched["turnover_zscore"] == enriched["temporal_turnover_zscore"]
    assert enriched["turnover_zscore_basis"] == event_market_history.TEMPORAL_BASELINE_BASIS
    assert enriched["market_feature_evidence"]["liquidity_usd"]["basis"] == "provider_observed"
    assert (
        enriched["market_feature_evidence"]["temporal_volume_zscore_24h"]["basis"]
        == event_market_history.TEMPORAL_BASELINE_BASIS
    )
    assert enriched["return_units"]["return_1h"] == "percent_points"
    assert result.retained_history[0]["canonical_asset_id"] == "bitcoin"
    assert all(row["observed_at"].endswith("+00:00") for row in result.retained_history)
    retained_current = next(
        row
        for row in result.retained_history
        if row["canonical_asset_id"] == "move-token" and row["observed_at"] == NOW.isoformat()
    )
    assert retained_current["candidate_source_mode"] == "live_no_send"
    assert retained_current["data_acquisition_mode"] == "live_provider"
    assert retained_current["provider_generation_id"] == "pilot-run-1"
    assert retained_current["provider_source_artifact_sha256"] == "a" * 64
    assert retained_current["request_ledger_sha256"] == "b" * 64
    assert retained_current["burn_in_counted"] is True
    assert result.summary["warmup"]["row_status_counts"] == {"warm": 3}
    assert json.loads(json.dumps(result.to_dict()))["summary"]["research_only"] is True


def test_turnover_basis_distinguishes_provider_value_from_derived_ratio():
    result = event_market_history.enrich_market_rows_with_history(
        [
            _row(
                "provider-turnover",
                NOW,
                price=10,
                volume=100,
                market_cap=1_000,
                turnover_24h=0.9,
            ),
            _row(
                "derived-turnover",
                NOW,
                price=10,
                volume=100,
                market_cap=1_000,
            ),
        ],
        now=NOW,
        config=_config(),
    )

    retained = {
        row["canonical_asset_id"]: row
        for row in result.retained_history
    }
    assert retained["provider-turnover"]["turnover_24h"] == 0.9
    assert (
        retained["provider-turnover"]["feature_basis"]["turnover_24h"]
        == "provider_observed"
    )
    assert retained["derived-turnover"]["turnover_24h"] == pytest.approx(0.1)
    assert (
        retained["derived-turnover"]["feature_basis"]["turnover_24h"]
        == "derived_provider_ratio"
    )


def test_provider_observed_zscore_is_not_replaced_by_temporal_baseline():
    current = _row(
        "move-token",
        NOW,
        price=120,
        volume=2_200,
        volume_zscore_24h=7.0,
        volume_zscore_basis="provider_observed",
        market_feature_evidence={
            "volume_zscore_24h": {"basis": "provider_observed", "provider": "vendor"},
        },
    )

    result = event_market_history.enrich_market_rows_with_history(
        [current],
        [row for row in _three_asset_history() if row["canonical_asset_id"] == "move-token"],
        now=NOW,
        config=_config(),
    )
    enriched = result.enriched_rows[0]

    assert enriched["volume_zscore_24h"] == 7.0
    assert enriched["volume_zscore_basis"] == "provider_observed"
    assert enriched["temporal_volume_zscore_24h"] is not None
    assert enriched["market_feature_evidence"]["volume_zscore_24h"]["provider"] == "vendor"


def test_warmup_is_explicit_and_does_not_replace_proxy_before_ready():
    history = [
        _row("move-token", NOW - timedelta(hours=2), price=100, volume=1_000),
        _row("move-token", NOW - timedelta(hours=1), price=102, volume=1_100),
    ]
    current = _row(
        "move-token",
        NOW,
        price=104,
        volume=1_250,
        volume_zscore_24h=1.7,
        volume_zscore_basis="cross_sectional_log_turnover_proxy",
    )

    result = event_market_history.enrich_market_rows_with_history(
        [current],
        history,
        now=NOW,
        config=_config(min_baseline_observations=4),
    )
    enriched = result.enriched_rows[0]

    assert enriched["market_history_status"] == "warming"
    volume_warmup = enriched["market_history"]["warmup"]["volume_zscore_24h"]
    assert {
        key: volume_warmup[key]
        for key in ("status", "sample_count", "required_sample_count", "basis")
    } == {
        "status": "warming",
        "sample_count": 2,
        "required_sample_count": 4,
        "basis": "temporal_baseline",
    }
    assert volume_warmup["coverage_seconds"] == 3600
    assert volume_warmup["required_coverage_seconds"] == 10800
    assert enriched["market_history"]["warmup"]["return_zscore_1h"]["status"] == "warming"
    assert enriched["temporal_return_1h"] == pytest.approx((104 / 102 - 1) * 100)
    assert "temporal_volume_zscore_24h" not in enriched
    assert enriched["volume_zscore_24h"] == 1.7
    assert enriched["volume_zscore_basis"] == "cross_sectional_log_turnover_proxy"
    assert enriched["market_history"]["warmup"]["relative_return_vs_btc_1h_zscore"]["status"] == "missing_current"


def test_rejection_telemetry_covers_naive_future_stale_and_out_of_order_rows():
    valid_history = _row("move-token", NOW - timedelta(hours=1), price=101, volume=1_100)
    history = [
        valid_history,
        _row("naive-history", "2026-07-13T11:00:00", price=1, volume=10),
        _row("future-history", NOW + timedelta(minutes=1), price=1, volume=10),
        _row("stale-history", NOW - timedelta(hours=5), price=1, volume=10),
    ]
    current = [
        _row("move-token", NOW - timedelta(hours=2), price=100, volume=1_000),
        _row("naive-current", "2026-07-13T12:00:00", price=1, volume=10),
        _row("future-current", NOW + timedelta(minutes=3), price=1, volume=10),
        _row("stale-current", NOW - timedelta(hours=5), price=1, volume=10),
        {
            "canonical_asset_id": "",
            "observed_at": NOW.isoformat(),
            "price": 1,
            "volume_24h": 10,
        },
    ]

    result = event_market_history.enrich_market_rows_with_history(
        current,
        history,
        now=NOW,
        config=_config(max_history_age=timedelta(hours=3)),
    )

    assert result.summary["rejection_counts"] == {
        "future": 2,
        "missing_canonical_asset_id": 1,
        "naive_timestamp": 2,
        "out_of_order": 1,
        "stale": 2,
    }
    assert [row["market_history"]["rejection_reason"] for row in result.enriched_rows] == [
        "out_of_order",
        "naive_timestamp",
        "future",
        "stale",
        "missing_canonical_asset_id",
    ]
    assert len(result.retained_history) == 1
    assert result.retained_history[0]["canonical_asset_id"] == "move-token"
    assert result.summary["retention"]["pruned_by_age"] == 1


def test_retention_is_bounded_by_age_and_per_asset_limit():
    history = [
        _row("move-token", NOW - timedelta(hours=11), price=89, volume=890),
        *[
            _row(
                "move-token",
                NOW - timedelta(hours=offset),
                price=100 - offset,
                volume=1_000 - offset * 10,
            )
            for offset in range(5, 0, -1)
        ],
    ]
    current = _row("move-token", NOW, price=100, volume=1_000)

    result = event_market_history.enrich_market_rows_with_history(
        [current],
        history,
        now=NOW,
        config=_config(
            max_history_age=timedelta(hours=10),
            max_observations_per_asset=3,
            min_baseline_observations=2,
        ),
    )

    assert [row["observed_at"] for row in result.retained_history] == [
        (NOW - timedelta(hours=2)).isoformat(),
        (NOW - timedelta(hours=1)).isoformat(),
        NOW.isoformat(),
    ]
    assert result.summary["retention"]["pruned_by_age"] == 1
    assert result.summary["retention"]["pruned_by_limit"] == 3
    assert result.summary["retention"]["retained_observations"] == 3


def test_duplicate_and_conflict_resolution_is_deterministic_for_history_input_order():
    timestamp = NOW - timedelta(hours=2)
    identical = _row("move-token", timestamp, price=100, volume=1_000)
    duplicate = copy.deepcopy(identical)
    conflict = _row("move-token", timestamp, price=101, volume=1_000)
    previous = _row("move-token", NOW - timedelta(hours=3), price=98, volume=900)
    current = _row("move-token", NOW, price=104, volume=1_200)

    first = event_market_history.enrich_market_rows_with_history(
        [current],
        [identical, conflict, previous, duplicate],
        now=NOW,
        config=_config(),
    )
    second = event_market_history.enrich_market_rows_with_history(
        [current],
        [duplicate, previous, conflict, identical],
        now=NOW,
        config=_config(),
    )

    assert first.retained_history == second.retained_history
    assert first.enriched_rows == second.enriched_rows
    assert first.summary["rejection_counts"] == second.summary["rejection_counts"]
    assert first.summary["rejection_counts"]["duplicate"] == 1
    assert first.summary["rejection_counts"]["duplicate_conflict"] == 1


def test_conflicting_current_observation_at_existing_key_fails_closed():
    existing = _row("move-token", NOW, price=100, volume=1_000)
    current = _row("move-token", NOW, price=999, volume=1_000)

    result = event_market_history.enrich_market_rows_with_history(
        [current],
        [existing],
        now=NOW,
        config=_config(),
    )

    assert result.enriched_rows[0]["market_history_status"] == "rejected"
    assert result.enriched_rows[0]["market_history"]["rejection_reason"] == "duplicate_conflict"
    assert result.retained_history[0]["price"] == 100
    assert result.summary["rejection_counts"]["duplicate_conflict"] == 1


def test_same_asset_current_rows_accept_only_newest_and_report_older_as_out_of_order():
    older = _row("move-token", NOW - timedelta(minutes=30), price=100, volume=1_000)
    newest = _row("move-token", NOW, price=101, volume=1_100)

    result = event_market_history.enrich_market_rows_with_history(
        [older, newest],
        [],
        now=NOW,
        config=_config(),
    )

    assert result.enriched_rows[0]["market_history"]["rejection_reason"] == "out_of_order"
    assert result.enriched_rows[1]["market_history_status"] == "cold"
    assert result.summary["rejection_counts"]["out_of_order"] == 1
    assert len(result.retained_history) == 1


def test_inputs_are_not_mutated_and_retained_history_can_be_rebuilt_deterministically():
    history = [row for row in _three_asset_history(6) if row["canonical_asset_id"] == "move-token"]
    history[0]["price_basis"] = "dex_pool_observed"
    current = [_row("move-token", NOW, price=112, volume=1_700)]
    original_history = copy.deepcopy(history)
    original_current = copy.deepcopy(current)

    first = event_market_history.enrich_market_rows_with_history(
        current,
        history,
        now=NOW,
        config=_config(),
    )
    rebuilt = event_market_history.enrich_market_rows_with_history(
        [],
        reversed(first.retained_history),
        now=NOW,
        config=_config(),
    )

    assert history == original_history
    assert current == original_current
    assert rebuilt.retained_history == first.retained_history
    assert rebuilt.retained_history[0]["feature_basis"]["price"] == "dex_pool_observed"
    assert json.dumps(rebuilt.summary, sort_keys=True)


def test_market_history_requires_aware_clock_and_valid_bounded_config():
    with pytest.raises(ValueError, match="aware UTC"):
        event_market_history.enrich_market_rows_with_history([], [], now=datetime(2026, 7, 13, 12, 0))
    with pytest.raises(ValueError, match="max_observations_per_asset"):
        event_market_history.MarketHistoryConfig(max_observations_per_asset=1)
    with pytest.raises(ValueError, match="min_baseline_observations"):
        event_market_history.MarketHistoryConfig(min_baseline_observations=1)
    with pytest.raises(ValueError, match="minimum_observation_spacing"):
        event_market_history.MarketHistoryConfig(
            minimum_observation_spacing=timedelta(0),
        )


def test_too_close_observation_is_preserved_but_never_advances_baseline():
    first_at = NOW - timedelta(minutes=10)
    first = _row("move-token", first_at, price=100, volume=1_000)
    rapid = _row("move-token", NOW, price=101, volume=1_100)

    result = event_market_history.enrich_market_rows_with_history(
        [rapid],
        [first],
        now=NOW,
        config=_config(),
    )

    enriched = result.enriched_rows[0]
    assert enriched["market_history"]["baseline_counted"] is False
    assert enriched["market_history"]["baseline_counting_status"] == "too_close"
    assert enriched["market_history"]["prior_observation_count"] == 1
    assert result.summary["baseline_counting"]["current"] == {"too_close": 1}
    assert len(result.retained_history) == 2
    assert [row["baseline_counting_status"] for row in result.retained_history] == [
        "counted",
        "too_close",
    ]

    eligible_at = NOW + timedelta(hours=1)
    rebuilt = event_market_history.enrich_market_rows_with_history(
        [_row("move-token", eligible_at, price=102, volume=1_200)],
        result.retained_history,
        now=eligible_at,
        config=_config(),
    )
    assert rebuilt.enriched_rows[0]["market_history"]["baseline_counted"] is True
    assert [row["baseline_counting_status"] for row in rebuilt.retained_history] == [
        "counted",
        "too_close",
        "counted",
    ]


def test_readiness_rejects_rapid_count_warmth_and_reports_every_feature_group():
    start = NOW - timedelta(minutes=70)
    rapid = [
        _row(
            "move-token",
            start + timedelta(minutes=10 * index),
            price=100 + index,
            volume=1_000 + index * 10,
        )
        for index in range(8)
    ]

    readiness = market_history_readiness.assess_market_history_readiness(
        rapid,
        now=NOW,
    )

    assert readiness["baseline_status"] == "warming"
    assert readiness["baseline_observation_count"] == 8
    assert readiness["baseline_counted_observation_count"] == 2
    assert readiness["baseline_too_close_observation_count"] == 6
    assert readiness["cadence_status"] == "waiting"
    assert readiness["next_eligible_observation_at"] == (NOW + timedelta(hours=1)).isoformat()
    assert set(readiness["baseline_feature_readiness"]) == set(
        event_market_history.FEATURE_READINESS_GROUPS
    )
    assert readiness["baseline_asset_readiness"]["move-token"]["status"] == "warming"


def test_long_horizon_history_is_globally_warm_only_when_all_groups_are_warm():
    history: list[dict] = []
    for index in range(27):
        observed_at = NOW - timedelta(hours=26 - index)
        history.extend((
            _row("move-token", observed_at, price=100 + index * 2, volume=1_000 + index * 13),
            _row("bitcoin", observed_at, price=200 + index, volume=5_000 + index * 17, symbol="BTC"),
            _row("ethereum", observed_at, price=1_000 + index * 3, volume=4_000 + index * 19, symbol="ETH"),
        ))
    cfg = event_market_history.MarketHistoryConfig(
        max_history_age=timedelta(days=2),
        max_observations_per_asset=64,
        min_baseline_observations=2,
    )

    readiness = market_history_readiness.assess_market_history_readiness(
        history,
        now=NOW,
        config=cfg,
    )

    assert readiness["baseline_status"] == "warm"
    assert readiness["baseline_warm_asset_count"] == 3
    for group in event_market_history.FEATURE_READINESS_GROUPS:
        assert readiness["baseline_feature_readiness"][group]["warm_asset_count"] == 3

    without_eth = [row for row in history if row["canonical_asset_id"] != "ethereum"]
    missing_benchmark = market_history_readiness.assess_market_history_readiness(
        without_eth,
        now=NOW,
        config=cfg,
    )
    assert missing_benchmark["baseline_status"] == "warming"
    assert (
        missing_benchmark["baseline_feature_readiness"]["btc_eth_relative"]["warm_asset_count"]
        == 0
    )
