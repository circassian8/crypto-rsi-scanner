"""Small point-in-time feature builder for Lean Crypto Radar."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import statistics
from typing import Mapping, Sequence

from .models import MarketFeatures, MarketSnapshot


MIN_BASELINE_SAMPLES = 8
STALE_AFTER_SECONDS = 45 * 60
FUTURE_TOLERANCE_SECONDS = 5 * 60
MIN_VOLUME_USD_24H = 10_000_000.0
MIN_MARKET_CAP_USD = 50_000_000.0


def build_features(
    snapshots: Sequence[MarketSnapshot],
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    evaluated_at: datetime,
) -> tuple[MarketFeatures, ...]:
    if evaluated_at.tzinfo is None:
        raise ValueError("feature evaluation time must be timezone-aware")
    benchmark_by_symbol = {row.symbol: row for row in snapshots}
    btc = benchmark_by_symbol.get("BTC")
    eth = benchmark_by_symbol.get("ETH")
    turnover_z = _cross_section_zscores(
        [row.turnover_ratio_24h for row in snapshots]
    )
    out: list[MarketFeatures] = []
    for index, snapshot in enumerate(snapshots):
        history = histories.get(snapshot.canonical_asset_id, ())
        prior_volumes = [
            value
            for row in history
            if (value := _positive(row.get("volume_usd_24h"))) is not None
        ]
        warm = len(prior_volumes) >= MIN_BASELINE_SAMPLES
        volume_zscore = _robust_z(prior_volumes, snapshot.volume_usd_24h) if warm else None
        baseline_status = "warm" if warm else "warming" if prior_volumes else "cold"
        observed = datetime.fromisoformat(snapshot.observed_at.replace("Z", "+00:00"))
        age_seconds = (
            evaluated_at.astimezone(timezone.utc)
            - observed.astimezone(timezone.utc)
        ).total_seconds()
        if age_seconds < -FUTURE_TOLERANCE_SECONDS:
            freshness = "future_invalid"
        elif age_seconds > STALE_AFTER_SECONDS:
            freshness = "stale"
        else:
            freshness = "fresh"
        liquidity = (
            "adequate"
            if snapshot.volume_usd_24h >= MIN_VOLUME_USD_24H
            and snapshot.market_cap_usd >= MIN_MARKET_CAP_USD
            else "insufficient"
        )
        rel_btc = _relative_family(snapshot, btc)
        rel_eth = _relative_family(snapshot, eth)
        benchmark_status = (
            "ready"
            if btc is not None and eth is not None
            else "partial"
            if btc is not None or eth is not None
            else "unavailable"
        )
        out.append(
            MarketFeatures(
                snapshot=snapshot,
                baseline_status=baseline_status,
                baseline_sample_count=len(prior_volumes),
                volume_zscore=volume_zscore,
                volume_signal_basis=(
                    "rolling_log_volume_robust_zscore"
                    if warm
                    else "cold_cross_section_turnover_proxy"
                ),
                turnover_cross_section_zscore=turnover_z[index],
                relative_btc_1h_pp=rel_btc[0],
                relative_btc_24h_pp=rel_btc[1],
                relative_eth_1h_pp=rel_eth[0],
                relative_eth_24h_pp=rel_eth[1],
                benchmark_status=benchmark_status,
                age_seconds=age_seconds,
                freshness_status=freshness,
                liquidity_status=liquidity,
                chase_risk_score=_chase_risk(snapshot),
            )
        )
    return tuple(out)


def _relative_family(
    asset: MarketSnapshot,
    benchmark: MarketSnapshot | None,
) -> tuple[float | None, float | None]:
    if benchmark is None:
        return (None, None)
    return (
        _difference(asset.return_1h_pp, benchmark.return_1h_pp),
        _difference(asset.return_24h_pp, benchmark.return_24h_pp),
    )


def _difference(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else left - right


def _robust_z(history: Sequence[float], current: float) -> float:
    logs = [math.log(value) for value in history if value > 0]
    if len(logs) < MIN_BASELINE_SAMPLES:
        return 0.0
    current_log = math.log(current)
    median = statistics.median(logs)
    mad = statistics.median(abs(value - median) for value in logs)
    scale = mad * 1.4826
    if scale <= 1e-12:
        scale = statistics.pstdev(logs)
    return 0.0 if scale <= 1e-12 else (current_log - median) / scale


def _cross_section_zscores(values: Sequence[float]) -> tuple[float | None, ...]:
    if len(values) < 2:
        return tuple(None for _ in values)
    logs = [math.log(max(value, 1e-12)) for value in values]
    mean = statistics.fmean(logs)
    scale = statistics.pstdev(logs)
    if scale <= 1e-12:
        return tuple(0.0 for _ in values)
    return tuple((value - mean) / scale for value in logs)


def _positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def _chase_risk(snapshot: MarketSnapshot) -> float:
    move = abs(snapshot.return_24h_pp or 0.0) * 2.2
    rsi_extension = max(0.0, (snapshot.rsi_14 or 50.0) - 65.0) * 1.8
    return min(100.0, round(move + rsi_extension, 2))


__all__ = (
    "FUTURE_TOLERANCE_SECONDS",
    "MIN_BASELINE_SAMPLES",
    "MIN_MARKET_CAP_USD",
    "MIN_VOLUME_USD_24H",
    "STALE_AFTER_SECONDS",
    "build_features",
)
