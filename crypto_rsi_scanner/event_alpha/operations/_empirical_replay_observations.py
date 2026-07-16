"""Private point-in-time observation assembly for empirical replay data."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from ...state_features import liquidity_bucket
from .empirical_replay_data_bar import ReplayBar
from .empirical_replay_data_dataset import ReplayDataset
from .empirical_replay_data_series import ReplaySeries


def _iter_point_in_time_observations(
    dataset: ReplayDataset,
    *,
    partitions: Mapping[str, Sequence[datetime | str]] | None,
    top_n: int | None,
    membership_window: int | None,
) -> Iterator[dict[str, Any]]:
    from .empirical_replay_data import (
        _benchmark_return_maps,
        _btc_market_regime,
        _partition_ranges,
        _point_in_time_membership_index,
        _series_analytics,
    )

    ranges = _partition_ranges(partitions)
    membership_by_key, _limit, _window = _point_in_time_membership_index(
        dataset,
        top_n=top_n,
        window_days=membership_window,
    )
    benchmark_returns = _benchmark_return_maps(dataset)
    market_regime = _btc_market_regime(dataset)
    for item in dataset.series:
        yield from _iter_series_observations(
            dataset=dataset,
            item=item,
            per_open=_series_analytics(item, dataset.mode),
            ranges=ranges,
            membership_by_key=membership_by_key,
            benchmark_returns=benchmark_returns,
            market_regime=market_regime,
        )


def _iter_series_observations(
    *,
    dataset: ReplayDataset,
    item: ReplaySeries,
    per_open: Mapping[datetime, Mapping[str, Any]],
    ranges: Sequence[tuple[str, datetime, datetime]],
    membership_by_key: Mapping[
        tuple[str, datetime], tuple[int | None, bool, float | None, str]
    ],
    benchmark_returns: Mapping[str, Mapping[datetime, float | None]],
    market_regime: Mapping[datetime, str | None],
) -> Iterator[dict[str, Any]]:
    from .empirical_replay_data import (
        _combined_baseline_status,
        _partition_for,
        _relative_return,
    )

    for bar in item.bars:
        partition = _partition_for(bar.observed_at, ranges)
        if ranges and partition is None:
            continue
        values = per_open[bar.bar_open_at]
        rank, in_universe, trailing_volume, membership_status = membership_by_key[
            (item.symbol, bar.observed_at)
        ]
        return_24h = values["return_24h"]
        relative_btc = _relative_return(
            return_24h,
            benchmark_returns["BTC"].get(bar.bar_open_at),
        )
        relative_eth = _relative_return(
            return_24h,
            benchmark_returns["ETH"].get(bar.bar_open_at),
        )
        regime = market_regime.get(bar.bar_open_at)
        baseline_status = _combined_baseline_status(
            volume_status=str(values["volume_baseline_status"]),
            membership_status=membership_status,
        )
        feature_basis = _feature_basis(
            bar=bar,
            item=item,
            values=values,
            relative_btc=relative_btc,
            relative_eth=relative_eth,
            regime=regime,
        )
        yield _observation_payload(
            dataset=dataset,
            item=item,
            bar=bar,
            values=values,
            partition=partition,
            rank=rank,
            in_universe=in_universe,
            trailing_volume=trailing_volume,
            membership_status=membership_status,
            baseline_status=baseline_status,
            relative_btc=relative_btc,
            relative_eth=relative_eth,
            regime=regime,
            feature_basis=feature_basis,
        )


def _feature_basis(
    *,
    bar: ReplayBar,
    item: ReplaySeries,
    values: Mapping[str, Any],
    relative_btc: float | None,
    relative_eth: float | None,
    regime: str | None,
) -> dict[str, str]:
    historical_or_missing = lambda value: (
        "historical_ohlcv" if value is not None else "missing"
    )
    return {
        "open": historical_or_missing(bar.open),
        "high": historical_or_missing(bar.high),
        "low": historical_or_missing(bar.low),
        "close": "historical_ohlcv",
        "quote_volume": item.quote_volume_basis,
        "liquidity_usd": item.quote_volume_basis,
        "volume_membership": "point_in_time_volume_universe",
        "volume_zscore_24h": (
            (
                "cross_sectional_proxy"
                if item.quote_volume_basis == "cross_sectional_proxy"
                else "temporal_direct"
            )
            if values["volume_zscore_24h"] is not None
            else "missing"
        ),
        "return_24h": historical_or_missing(values["return_24h"]),
        "return_72h": historical_or_missing(values["return_72h"]),
        "return_7d": historical_or_missing(values["return_7d"]),
        "relative_return_vs_btc_24h": historical_or_missing(relative_btc),
        "relative_return_vs_eth_24h": historical_or_missing(relative_eth),
        "rsi": historical_or_missing(values["rsi"]),
        "market_regime": historical_or_missing(regime),
        "intraday_returns": "missing",
        "spread_bps": "unavailable",
        "order_book_depth": "unavailable",
        "catalyst_evidence_timing": "unavailable",
        "calendar_evidence_timing": "unavailable",
    }


def _missing_features(
    *,
    bar: ReplayBar,
    values: Mapping[str, Any],
    relative_btc: float | None,
    relative_eth: float | None,
    regime: str | None,
) -> list[str]:
    missing = [
        "return_15m",
        "return_1h",
        "return_4h",
        "relative_return_vs_btc_4h",
        "relative_return_vs_eth_4h",
        "spread_bps",
        "order_book_depth",
        "funding",
        "open_interest",
        "catalyst_evidence_timing",
        "calendar_evidence_timing",
    ]
    optional_values = {
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "return_24h": values["return_24h"],
        "return_72h": values["return_72h"],
        "return_7d": values["return_7d"],
        "relative_return_vs_btc_24h": relative_btc,
        "relative_return_vs_eth_24h": relative_eth,
        "volume_zscore_24h": values["volume_zscore_24h"],
        "rsi": values["rsi"],
        "market_regime": regime,
    }
    missing.extend(key for key, value in optional_values.items() if value is None)
    if not bar.full_daily_bar:
        missing.append("daily_bar_complete")
    return sorted(set(missing))


def _observation_payload(
    *,
    dataset: ReplayDataset,
    item: ReplaySeries,
    bar: ReplayBar,
    values: Mapping[str, Any],
    partition: str | None,
    rank: int | None,
    in_universe: bool,
    trailing_volume: float | None,
    membership_status: str,
    baseline_status: str,
    relative_btc: float | None,
    relative_eth: float | None,
    regime: str | None,
    feature_basis: Mapping[str, str],
) -> dict[str, Any]:
    from .empirical_replay_data import (
        OBSERVATION_SCHEMA_ID,
        OBSERVATION_SCHEMA_VERSION,
        _iso,
    )

    direct_feature_count = sum(
        basis
        in {
            "historical_ohlcv",
            "point_in_time_volume_universe",
            "provider_observed",
            "temporal_direct",
        }
        for basis in feature_basis.values()
    )
    proxy_feature_count = sum(
        basis == "cross_sectional_proxy" for basis in feature_basis.values()
    )
    return_24h = values["return_24h"]
    return {
        "schema_id": OBSERVATION_SCHEMA_ID,
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "source_mode": "artifact_replay",
        "source_kind": dataset.source_kind,
        "market_data_source": (
            "binance_historical_ohlcv"
            if dataset.source_kind == "binance_daily_klines_cache"
            else "checked_fixture_historical_ohlcv"
        ),
        "data_quality_mode": (
            "cross_sectional_proxy"
            if item.quote_volume_basis == "cross_sectional_proxy"
            else "historical_ohlcv"
        ),
        "market_data_basis": "historical_ohlcv",
        "volume_anomaly_basis": feature_basis["volume_zscore_24h"],
        "liquidity_basis": item.quote_volume_basis,
        "spread_basis": "unavailable",
        "intraday_basis": "missing",
        "baseline_maturity": baseline_status,
        "data_quality_status": "partial" if bar.full_daily_bar else "partial_bar",
        "catalyst_evidence_timing": "unavailable",
        "calendar_evidence_timing": "unavailable",
        "rsi_context_timing": "temporal_direct" if values["rsi"] is not None else "missing",
        "direct_proxy_class": "mixed_proxy" if proxy_feature_count else "temporal_direct",
        "direct_feature_count": direct_feature_count,
        "proxy_feature_count": proxy_feature_count,
        "volume_zscore_basis": feature_basis["volume_zscore_24h"],
        "mode": dataset.mode.name,
        "partition": partition or "unassigned",
        "symbol": item.symbol,
        "canonical_asset_id": item.canonical_asset_id,
        "canonical_asset_id_basis": "historical_exchange_symbol",
        "bar_open_at": _iso(bar.bar_open_at),
        "observed_at": _iso(bar.observed_at),
        "bar_duration_seconds": bar.bar_duration_seconds,
        "bar_duration_status": "full_daily" if bar.full_daily_bar else "partial_daily",
        "full_daily_bar": bar.full_daily_bar,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "base_volume": bar.base_volume,
        "quote_volume": bar.quote_volume,
        "liquidity_usd": bar.quote_volume,
        "liquidity_tier": liquidity_bucket(bar.quote_volume, None),
        "in_universe": in_universe,
        "volume_rank": rank,
        "point_in_time_universe_member": in_universe,
        "point_in_time_volume_rank": rank,
        "trailing_quote_volume": trailing_volume,
        "membership_status": membership_status,
        "baseline_status": baseline_status,
        "volume_baseline_status": values["volume_baseline_status"],
        "volume_baseline_count": values["volume_baseline_count"],
        "return_24h": return_24h,
        "return_72h": values["return_72h"],
        "return_7d": values["return_7d"],
        "relative_return_vs_btc_24h": relative_btc,
        "relative_return_vs_eth_24h": relative_eth,
        "volume_zscore_24h": values["volume_zscore_24h"],
        "rsi": values["rsi"],
        "market_regime": regime,
        "spread_bps": None,
        "spread_status": "unavailable",
        "intraday_status": "missing",
        "return_unit": "percent_points",
        "feature_basis": dict(feature_basis),
        "feature_quality_modes": sorted(set(feature_basis.values())),
        "missing_features": _missing_features(
            bar=bar,
            values=values,
            relative_btc=relative_btc,
            relative_eth=relative_eth,
            regime=regime,
        ),
        "source_file": item.relative_path,
        "source_file_sha256": item.content_sha256,
        "residual_survivorship_present": dataset.residual_survivorship_present,
        "research_only": True,
        "provider_calls": 0,
        "network_access": False,
        "final_test_evaluated": False,
    }


__all__: tuple[str, ...] = ()
