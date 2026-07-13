"""Canonical cadence- and feature-aware readiness over retained market history."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

from . import market_history


MARKET_HISTORY_READINESS_SCHEMA = "event_alpha.market_history_readiness"


def assess_market_history_readiness(
    existing_history: Iterable[Mapping[str, Any]],
    *,
    now: datetime | str,
    config: market_history.MarketHistoryConfig | None = None,
) -> dict[str, Any]:
    """Assess one cache with the same cadence and feature policy as enrichment."""

    cfg = config or market_history.MarketHistoryConfig()
    evaluated_at = market_history._require_aware_utc(now, field_name="now")
    historical = [dict(row) for row in existing_history if isinstance(row, Mapping)]
    telemetry = market_history._Telemetry(example_limit=cfg.rejection_example_limit)
    prepared = market_history._prepare_rows(
        historical,
        role="history",
        now=evaluated_at,
        max_age=cfg.max_history_age,
        telemetry=telemetry,
    )
    canonical = market_history._deduplicate_history(prepared, telemetry)
    canonical, cadence_counts = market_history._classify_history_cadence(
        canonical,
        minimum_spacing=cfg.minimum_observation_spacing,
    )
    raw_by_asset = market_history._group_observations(canonical)
    counted_by_asset = market_history._counted_observations(raw_by_asset)
    asset_readiness: dict[str, dict[str, Any]] = {}
    group_counts = {
        group: Counter() for group in market_history.FEATURE_READINESS_GROUPS
    }
    for asset_id in sorted(raw_by_asset):
        groups = _history_feature_groups(asset_id, counted_by_asset, cfg=cfg)
        required = [
            groups[group]
            for group in cfg.required_feature_groups
            if groups[group].get("required") is True
        ]
        status = (
            "warm"
            if required and all(item["status"] == "warm" for item in required)
            else "warming"
        )
        counted = counted_by_asset.get(asset_id, [])
        raw = raw_by_asset[asset_id]
        asset_readiness[asset_id] = {
            "status": status,
            "raw_observation_count": len(raw),
            "baseline_counted_observation_count": len(counted),
            "too_close_observation_count": sum(
                item.get("baseline_counting_status") == market_history.BASELINE_TOO_CLOSE
                for item in raw
            ),
            "oldest_counted_observed_at": counted[0]["observed_at"] if counted else None,
            "newest_counted_observed_at": counted[-1]["observed_at"] if counted else None,
            "feature_readiness": groups,
        }
        for group, details in groups.items():
            group_counts[group][str(details.get("status") or "unknown")] += 1
    observed_times = [market_history._observation_time(row) for row in canonical]
    counted_times = [
        market_history._observation_time(row)
        for rows in counted_by_asset.values()
        for row in rows
    ]
    newest = max(observed_times, default=None)
    newest_counted = max(counted_times, default=None)
    next_eligible = newest + cfg.minimum_observation_spacing if newest else None
    warm_assets = sum(item["status"] == "warm" for item in asset_readiness.values())
    if not canonical:
        valid_input_times = [
            parsed
            for row in historical
            if (
                parsed := market_history._parse_aware_time(
                    row.get("provider_observed_at")
                    or row.get("observed_at")
                    or row.get("timestamp")
                )[0]
            ) is not None
            and parsed <= evaluated_at
        ]
        status = "stale" if valid_input_times else "cold"
    elif warm_assets == len(asset_readiness):
        status = "warm"
    else:
        status = "warming"
    feature_readiness = {
        group: {
            "status_counts": dict(sorted(counts.items())),
            "warm_asset_count": int(counts.get("warm", 0)),
            "warming_asset_count": int(sum(counts.values()) - counts.get("warm", 0)),
            "asset_count": int(sum(counts.values())),
        }
        for group, counts in group_counts.items()
    }
    return {
        "schema_id": MARKET_HISTORY_READINESS_SCHEMA,
        "schema_version": market_history.MARKET_HISTORY_SCHEMA_VERSION,
        "evaluated_at": market_history._iso(evaluated_at),
        "baseline_status": status,
        "baseline_observation_count": len(canonical),
        "baseline_counted_observation_count": int(
            cadence_counts.get(market_history.BASELINE_COUNTED, 0)
        ),
        "baseline_too_close_observation_count": int(
            cadence_counts.get(market_history.BASELINE_TOO_CLOSE, 0)
        ),
        "baseline_asset_count": len(asset_readiness),
        "baseline_warm_asset_count": warm_assets,
        "baseline_min_observations": cfg.min_baseline_observations,
        "minimum_observation_spacing_seconds": int(
            cfg.minimum_observation_spacing.total_seconds()
        ),
        "baseline_newest_observed_at": market_history._iso(newest) if newest else None,
        "baseline_newest_counted_observed_at": (
            market_history._iso(newest_counted) if newest_counted else None
        ),
        "next_eligible_observation_at": (
            market_history._iso(next_eligible) if next_eligible else None
        ),
        "cadence_status": (
            "eligible" if next_eligible is None or evaluated_at >= next_eligible else "waiting"
        ),
        "baseline_feature_readiness": feature_readiness,
        "baseline_asset_readiness": asset_readiness,
        "rejection_counts": dict(sorted(telemetry.counts.items())),
        "research_only": True,
    }


def _history_feature_groups(
    asset_id: str,
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    cfg: market_history.MarketHistoryConfig,
) -> dict[str, dict[str, Any]]:
    observations = list(history_by_asset.get(asset_id, ()))
    warmup: dict[str, dict[str, Any]] = {}
    for source_field, feature in (
        ("volume_24h", "volume_zscore_24h"),
        ("turnover_24h", "turnover_zscore"),
    ):
        sample = [
            item
            for item in observations
            if market_history._number(item.get(source_field)) is not None
        ]
        warmup[feature] = _feature_details(
            sample,
            cfg=cfg,
            required=market_history._required_coverage(cfg, horizon_hours=0),
        )
    for hours in sorted(cfg.return_horizons_hours):
        values = market_history._historical_returns(observations, hours=hours, cfg=cfg)
        details = _feature_details(
            observations,
            cfg=cfg,
            required=market_history._required_coverage(cfg, horizon_hours=hours),
            sample_count=len(values),
        )
        for feature in (
            f"return_zscore_{hours}h",
            f"return_volatility_{hours}h",
            f"volatility_zscore_{hours}h",
        ):
            warmup[feature] = dict(details)
    benchmarks = (
        ("btc", market_history._find_benchmark_asset(history_by_asset, cfg.btc_asset_ids)),
        ("eth", market_history._find_benchmark_asset(history_by_asset, cfg.eth_asset_ids)),
    )
    for name, benchmark_asset_id in benchmarks:
        benchmark = list(history_by_asset.get(benchmark_asset_id, ())) if benchmark_asset_id else []
        for hours in sorted(cfg.return_horizons_hours):
            feature = f"relative_return_vs_{name}_{hours}h_zscore"
            if benchmark_asset_id == asset_id:
                warmup[feature] = {
                    "status": "not_applicable",
                    "sample_count": 0,
                    "required_sample_count": 0,
                    "coverage_seconds": 0,
                    "required_coverage_seconds": 0,
                }
                continue
            values = market_history._historical_relative_returns(
                observations,
                benchmark,
                hours=hours,
                cfg=cfg,
            )
            warmup[feature] = _feature_details(
                observations,
                cfg=cfg,
                required=market_history._required_coverage(cfg, horizon_hours=hours),
                sample_count=len(values),
            )
    return market_history._group_feature_readiness(warmup, cfg=cfg)


def _feature_details(
    observations: Sequence[Mapping[str, Any]],
    *,
    cfg: market_history.MarketHistoryConfig,
    required: timedelta,
    sample_count: int | None = None,
) -> dict[str, Any]:
    count = len(observations) if sample_count is None else sample_count
    times = sorted(market_history._observation_time(item) for item in observations)
    coverage = times[-1] - times[0] if len(times) >= 2 else timedelta(0)
    status = (
        "warming"
        if count < cfg.min_baseline_observations
        else "warming_time_coverage"
        if coverage < required
        else "warm"
    )
    return {
        "status": status,
        "sample_count": count,
        "required_sample_count": cfg.min_baseline_observations,
        "coverage_seconds": max(0, int(coverage.total_seconds())),
        "required_coverage_seconds": int(required.total_seconds()),
    }


__all__ = ("MARKET_HISTORY_READINESS_SCHEMA", "assess_market_history_readiness")
