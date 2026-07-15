"""Pure market-row normalization and temporal-quality helpers.

This module keeps provider-derived values, transparent proxies, and rolling
history quality in one bounded place.  It performs no provider calls and only
reads candidate rows when producing aggregate quality counts.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ... import universe
from ..radar import market_enrichment
from .market_no_send_io import read_jsonl
from .market_provenance import DECISION_RADAR_MEASUREMENT_PROGRAM


def normalize_market_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    top_n: int,
    observed_at: datetime,
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
    request_ledger_artifact: str,
    candidate_source_mode: str | None,
    decision_radar_campaign_counted: bool,
    burn_in_counted: bool,
    safety_counters: Mapping[str, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a bounded liquid universe and add explicit feature bases."""

    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    clean, excluded, audit = universe.filter_markets_with_audit(
        materialized,
        limit=None,
        now=observed_at,
    )
    ranked = sorted(clean, key=_liquid_rank, reverse=True)[:top_n]
    proxy_zscores = _cross_sectional_turnover_zscores(ranked)
    source_mode = candidate_source_mode or (
        "live_no_send" if data_mode == "live" else "mocked_fixture"
    )
    normalized = [
        _normalize_market_row(
            row,
            observed_at=observed_at,
            provider=provider,
            data_mode=data_mode,
            source_mode=source_mode,
            request_cache_artifact=request_cache_artifact,
            request_ledger_artifact=request_ledger_artifact,
            decision_radar_campaign_counted=decision_radar_campaign_counted,
            burn_in_counted=burn_in_counted,
            proxy_zscore=proxy_zscores.get(index),
            safety_counters=safety_counters,
        )
        for index, row in enumerate(ranked)
    ]
    return normalized, _normalization_audit(
        audit,
        excluded=excluded,
        rows=normalized,
        top_n=top_n,
        provider=provider,
        data_mode=data_mode,
        source_mode=source_mode,
        observed_at=observed_at,
        decision_radar_campaign_counted=decision_radar_campaign_counted,
        burn_in_counted=burn_in_counted,
    )


def _normalize_market_row(
    row: Mapping[str, Any],
    *,
    observed_at: datetime,
    provider: str,
    data_mode: str,
    source_mode: str,
    request_cache_artifact: str,
    request_ledger_artifact: str,
    decision_radar_campaign_counted: bool,
    burn_in_counted: bool,
    proxy_zscore: float | None,
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    explicit_returns = _has_explicit_return_fields(row)
    snapshot = (
        _normalized_explicit_market_row(row)
        if explicit_returns
        else market_enrichment.market_snapshot_from_row(row, now=observed_at)
    )
    coin_id = str(snapshot.get("coin_id") or row.get("id") or row.get("coin_id") or "").strip()
    symbol = str(snapshot.get("symbol") or row.get("symbol") or "").upper().strip()
    market_cap = finite_float(row.get("market_cap"))
    total_volume = finite_float(row.get("total_volume") or row.get("volume_24h"))
    explicit_liquidity = finite_float(row.get("liquidity_usd"))
    liquidity = explicit_liquidity if explicit_liquidity is not None else total_volume
    volume_mcap = (
        total_volume / market_cap
        if total_volume is not None and market_cap is not None and market_cap > 0
        else None
    )
    volume_zscore = finite_float(row.get("volume_zscore_24h"))
    if volume_zscore is None:
        volume_zscore = proxy_zscore
    liquidity_basis = (
        "provider_observed" if explicit_liquidity is not None
        else "coingecko_total_volume_24h_proxy"
    )
    volume_zscore_basis = (
        "provider_observed" if row.get("volume_zscore_24h") is not None
        else "cross_sectional_log_turnover_proxy"
    )
    spread_available = row.get("spread_bps") is not None
    feature_basis = {
        "returns": "provider_observed_explicit" if explicit_returns else "provider_derived_sparkline",
        "relative_strength": "benchmark_derived_same_observation",
        "volume_turnover": "provider_observed",
        "volume_zscore": volume_zscore_basis,
        "liquidity": liquidity_basis,
        "spread": "provider_observed" if spread_available else "unavailable",
    }
    direct_features = sum(
        1
        for value in feature_basis.values()
        if "provider_observed" in value
        or "provider_derived" in value
        or "benchmark_derived" in value
    )
    proxy_features = sum(1 for value in feature_basis.values() if "proxy" in value)
    snapshot.update({
        "coin_id": coin_id,
        "symbol": symbol,
        "canonical_asset_id": str(row.get("canonical_asset_id") or coin_id or symbol),
        "name": str(row.get("name") or "") or None,
        "observed_at": observed_at.isoformat(),
        "timestamp": observed_at.isoformat(),
        "freshness_status": "fresh",
        "market_context_freshness_status": "fresh",
        "market_data_source": provider,
        "provider": provider,
        "source": provider,
        "source_class": "market_data",
        "source_pack": "market_anomaly_pack",
        "data_mode": data_mode,
        "data_acquisition_mode": "live_provider" if data_mode == "live" else "mocked_fixture",
        "candidate_source_mode": source_mode,
        "provider_request_succeeded": True,
        "provider_source_artifact": request_cache_artifact,
        "request_ledger_path": request_ledger_artifact,
        "provenance_contract_valid": True,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": bool(decision_radar_campaign_counted),
        "decision_radar_campaign_counted": bool(decision_radar_campaign_counted),
        "decision_radar_campaign_reason": (
            "counted_live_no_send_exact_lineage"
            if decision_radar_campaign_counted
            else f"not_counted_non_live_mode:{source_mode}"
        ),
        "burn_in_eligible": bool(burn_in_counted),
        "burn_in_counted": bool(burn_in_counted),
        "contract_counted_candidate": bool(
            decision_radar_campaign_counted or burn_in_counted
        ),
        "burn_in_reason": (
            _burn_in_reason(burn_in_counted)
            if burn_in_counted
            else "not_counted_separate_decision_radar_campaign"
        ),
        "contract_counted_status": (
            "counted"
            if decision_radar_campaign_counted or burn_in_counted
            else "not_counted"
        ),
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "market_cap": market_cap,
        "volume_24h": total_volume,
        "total_volume": total_volume,
        "volume_to_market_cap": volume_mcap,
        "feature_basis": {
            "volume_24h": "provider_observed",
            "market_cap": "provider_observed",
            "turnover_24h": (
                "derived_provider_ratio" if volume_mcap is not None else "unavailable"
            ),
        },
        "volume_zscore_24h": volume_zscore,
        "volume_zscore_basis": volume_zscore_basis,
        "liquidity_usd": liquidity,
        "liquidity_basis": liquidity_basis,
        "spread_bps": finite_float(row.get("spread_bps")),
        "spread_status": "verified" if spread_available else "unavailable",
        "market_feature_basis": feature_basis,
        "market_data_quality": _initial_market_quality(
            feature_basis,
            direct_features=direct_features,
            proxy_features=proxy_features,
            spread_available=spread_available,
            liquidity_basis=liquidity_basis,
            volume_zscore_basis=volume_zscore_basis,
        ),
        "direct_market_feature_count": direct_features,
        "proxy_market_feature_count": proxy_features,
        "is_tradable_asset": True,
        "venues": [provider],
        **dict(safety_counters),
    })
    return {key: value for key, value in snapshot.items() if value is not None}


def _initial_market_quality(
    feature_basis: Mapping[str, Any],
    *,
    direct_features: int,
    proxy_features: int,
    spread_available: bool,
    liquidity_basis: str,
    volume_zscore_basis: str,
) -> dict[str, Any]:
    return {
        "baseline_status": "not_evaluated",
        "direct_feature_count": direct_features,
        "proxy_feature_count": proxy_features,
        "spread_available": spread_available,
        "spread_basis": feature_basis["spread"],
        "liquidity_basis": liquidity_basis,
        "volume_zscore_basis": volume_zscore_basis,
    }


def _normalization_audit(
    audit: Mapping[str, Any],
    *,
    excluded: Mapping[str, int],
    rows: Sequence[Mapping[str, Any]],
    top_n: int,
    provider: str,
    data_mode: str,
    source_mode: str,
    observed_at: datetime,
    decision_radar_campaign_counted: bool,
    burn_in_counted: bool,
) -> dict[str, Any]:
    output = dict(audit)
    output.update({
        "requested_limit": top_n,
        "kept_count": len(rows),
        "excluded_count": int(sum(excluded.values())),
        "selection_order": "total_volume_desc",
        "provider": provider,
        "data_mode": data_mode,
        "observed_at": observed_at.isoformat(),
        "direct_feature_count": sum(int(row.get("direct_market_feature_count") or 0) for row in rows),
        "proxy_feature_count": sum(int(row.get("proxy_market_feature_count") or 0) for row in rows),
        "spread_available_count": sum(1 for row in rows if row.get("spread_bps") is not None),
        "candidate_source_mode": source_mode,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_counted": bool(decision_radar_campaign_counted),
        "burn_in_counted": bool(burn_in_counted),
    })
    return output


def market_quality_counts(path: str | Path) -> dict[str, Any]:
    return market_quality_counts_from_rows(read_jsonl(Path(path)))


def market_quality_counts_from_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    direct = 0
    proxy = 0
    warm = 0
    warming = 0
    statuses: Counter[str] = Counter()
    for row in rows:
        snapshot = row.get("market_state_snapshot")
        snapshot_quality = (
            snapshot.get("market_data_quality")
            if isinstance(snapshot, Mapping) else None
        )
        if not isinstance(snapshot, Mapping) or not isinstance(snapshot_quality, Mapping):
            fallback = row.get("market_snapshot")
            if isinstance(fallback, Mapping):
                snapshot = fallback
        snapshot = snapshot if isinstance(snapshot, Mapping) else {}
        quality = snapshot.get("market_data_quality")
        if not isinstance(quality, Mapping):
            quality = row.get("market_data_quality")
        quality = quality if isinstance(quality, Mapping) else {}
        direct += int(
            quality.get("direct_feature_count")
            or snapshot.get("direct_market_feature_count")
            or row.get("direct_market_feature_count")
            or 0
        )
        proxy += int(
            quality.get("proxy_feature_count")
            or snapshot.get("proxy_market_feature_count")
            or row.get("proxy_market_feature_count")
            or 0
        )
        status = str(quality.get("baseline_status") or "not_evaluated")
        statuses[status] += 1
        if status == "warm":
            warm += 1
        elif status in {"cold", "warming", "insufficient_history"}:
            warming += 1
    baseline_status = (
        "warm" if rows and warm == len(rows)
        else "warming" if warm or warming
        else "not_evaluated"
    )
    return {
        "baseline_status": baseline_status,
        "baseline_status_counts": dict(sorted(statuses.items())),
        "baseline_warm_assets": warm,
        "baseline_warming_assets": warming,
        "direct_feature_count": direct,
        "proxy_feature_count": proxy,
    }


def decision_route_counts(path: str | Path) -> Counter[str]:
    return Counter(
        str(
            row.get("radar_route")
            or row.get("decision_route")
            or row.get("actionability_route")
            or "diagnostic"
        )
        for row in read_jsonl(Path(path))
    )


def attach_history_quality(row: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    history = enriched.get("market_history")
    history = dict(history) if isinstance(history, Mapping) else {}
    status = str(history.get("status") or "not_evaluated")
    basis = enriched.get("market_feature_basis")
    basis = dict(basis) if isinstance(basis, Mapping) else {}
    if enriched.get("volume_zscore_basis"):
        basis["volume_zscore"] = enriched.get("volume_zscore_basis")
        basis["volume_zscore_24h"] = enriched.get("volume_zscore_basis")
    evidence = enriched.get("market_feature_evidence")
    if isinstance(evidence, Mapping) and evidence:
        basis["temporal_evidence"] = "explicit_feature_evidence_refs"
    basis_values = tuple(str(value or "").casefold() for value in basis.values())
    proxy_count = sum(1 for value in basis_values if "proxy" in value or "cross_sectional" in value)
    direct_count = sum(
        1
        for value in basis_values
        if value
        and "proxy" not in value
        and "cross_sectional" not in value
        and value != "unavailable"
    )
    quality = enriched.get("market_data_quality")
    quality = dict(quality) if isinstance(quality, Mapping) else {}
    market_snapshot_id = history.get("observation_id")
    quality.update({
        "baseline_status": status,
        "baseline_observation_count": int(history.get("prior_observation_count") or 0),
        "baseline_warm_feature_count": int(history.get("warm_feature_count") or 0),
        "baseline_feature_count": int(history.get("feature_count") or 0),
        "baseline_observation_id": history.get("observation_id"),
        "market_snapshot_id": market_snapshot_id,
        "direct_feature_count": direct_count,
        "proxy_feature_count": proxy_count,
        "feature_basis": basis,
        "liquidity_basis": enriched.get("liquidity_basis"),
        "volume_zscore_basis": enriched.get("volume_zscore_basis"),
        "spread_basis": basis.get("spread") or "unavailable",
        "spread_available": enriched.get("spread_bps") is not None,
        "research_only": True,
    })
    enriched.update({
        "market_feature_basis": basis,
        "feature_basis": basis,
        "market_data_quality": quality,
        "data_quality": quality,
        "temporal_baseline_status": status,
        "market_snapshot_id": market_snapshot_id,
        "market_history_observation_id": market_snapshot_id,
        "direct_market_feature_count": direct_count,
        "proxy_market_feature_count": proxy_count,
    })
    return enriched


def generation_feature_basis(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    observed: dict[str, set[str]] = {}
    for row in rows:
        basis = row.get("market_feature_basis")
        if not isinstance(basis, Mapping):
            continue
        for field, value in basis.items():
            text = str(value or "").strip()
            if text:
                observed.setdefault(str(field), set()).add(text)
    return {
        field: next(iter(values)) if len(values) == 1 else "mixed:" + ",".join(sorted(values))
        for field, values in sorted(observed.items())
    }


def generation_data_quality(
    rows: Iterable[Mapping[str, Any]],
    history_summary: Mapping[str, Any],
    *,
    history_filename: str,
) -> dict[str, Any]:
    materialized = [dict(row) for row in rows]
    statuses = Counter(str(row.get("temporal_baseline_status") or "not_evaluated") for row in materialized)
    return {
        "baseline_status_counts": dict(sorted(statuses.items())),
        "baseline_warm_assets": statuses.get("warm", 0),
        "baseline_warming_assets": statuses.get("warming", 0) + statuses.get("cold", 0),
        "direct_feature_count": sum(int(row.get("direct_market_feature_count") or 0) for row in materialized),
        "proxy_feature_count": sum(int(row.get("proxy_market_feature_count") or 0) for row in materialized),
        "spread_available_count": sum(1 for row in materialized if row.get("spread_bps") is not None),
        "history_schema_version": history_summary.get("schema_version"),
        "history_artifact": history_filename,
        "research_only": True,
    }


def finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _normalized_explicit_market_row(row: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        key: row.get(key)
        for key in (
            "price", "current_price", "return_1h", "return_4h", "return_24h",
            "return_72h", "return_7d", "relative_return_vs_btc_1h",
            "relative_return_vs_btc_4h", "relative_return_vs_btc_24h",
            "relative_return_vs_eth_1h", "relative_return_vs_eth_4h",
            "relative_return_vs_eth_24h", "return_unit",
        )
        if row.get(key) is not None
    }
    output["price"] = output.pop("current_price", output.get("price", None))
    output.setdefault("return_unit", "fraction")
    output["coin_id"] = str(row.get("coin_id") or row.get("id") or "")
    output["symbol"] = str(row.get("symbol") or "").upper()
    return output


def _cross_sectional_turnover_zscores(rows: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    values: dict[int, float] = {}
    for index, row in enumerate(rows):
        volume = finite_float(row.get("total_volume") or row.get("volume_24h"))
        market_cap = finite_float(row.get("market_cap"))
        if volume is None or market_cap is None or volume < 0 or market_cap <= 0:
            continue
        values[index] = math.log1p(volume / market_cap)
    if len(values) < 3:
        return {index: 0.0 for index in values}
    mean = sum(values.values()) / len(values)
    variance = sum((value - mean) ** 2 for value in values.values()) / len(values)
    stddev = math.sqrt(variance)
    if stddev <= 1e-12:
        return {index: 0.0 for index in values}
    return {index: round((value - mean) / stddev, 4) for index, value in values.items()}


def _liquid_rank(row: Mapping[str, Any]) -> tuple[float, float, float]:
    return (
        finite_float(row.get("total_volume") or row.get("volume_24h")) or 0.0,
        finite_float(row.get("liquidity_usd")) or 0.0,
        finite_float(row.get("market_cap")) or 0.0,
    )


def _has_explicit_return_fields(row: Mapping[str, Any]) -> bool:
    return any(row.get(key) is not None for key in ("return_1h", "return_4h", "return_24h"))


def smoke_rows() -> tuple[dict[str, Any], ...]:
    return (
        {"id": "bitcoin", "coin_id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "price": 65000, "return_unit": "fraction", "return_1h": 0.0005, "return_4h": 0.001, "return_24h": 0.002, "market_cap": 1_200_000_000_000, "total_volume": 30_000_000_000, "volume_zscore_24h": 0.0, "liquidity_usd": 5_000_000_000, "spread_bps": 2},
        {"id": "ethereum", "coin_id": "ethereum", "symbol": "ETH", "name": "Ethereum", "price": 3200, "return_unit": "fraction", "return_1h": 0.001, "return_4h": 0.002, "return_24h": 0.004, "market_cap": 400_000_000_000, "total_volume": 15_000_000_000, "volume_zscore_24h": 0.2, "liquidity_usd": 2_000_000_000, "spread_bps": 3},
        {"id": "market-flow", "coin_id": "market-flow", "symbol": "MKTFLOW", "name": "Market Flow", "price": 1.2, "return_unit": "fraction", "return_1h": 0.04, "return_4h": 0.10, "return_24h": 0.16, "market_cap": 90_000_000, "total_volume": 24_000_000, "volume_zscore_24h": 3.4, "liquidity_usd": 24_000_000, "spread_bps": 16},
        {"id": "market-flow-no-spread", "coin_id": "market-flow-no-spread", "symbol": "MKTNOSPREAD", "name": "Market Flow No Spread", "price": 2.2, "return_unit": "fraction", "return_1h": 0.035, "return_4h": 0.09, "return_24h": 0.15, "market_cap": 120_000_000, "total_volume": 20_000_000, "volume_zscore_24h": 3.1, "liquidity_usd": 18_000_000},
        {"id": "market-flow-low", "coin_id": "market-flow-low", "symbol": "MKTLOW", "name": "Market Flow Low", "price": 0.001, "return_unit": "fraction", "return_1h": 0.09, "return_4h": 0.25, "return_24h": 0.55, "market_cap": 12_000_000, "total_volume": 300_000, "volume_zscore_24h": 4.5, "liquidity_usd": 18_000, "spread_bps": 320},
    )


def _burn_in_reason(counted: bool) -> str:
    return (
        "counted_live_no_send_exact_lineage"
        if counted else "not_counted_non_live_mode:mocked_fixture"
    )
