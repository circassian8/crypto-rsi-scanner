"""Pure market-row normalization and temporal-quality helpers.

This module keeps provider-derived values, transparent proxies, and rolling
history quality in one bounded place.  It performs no provider calls and only
reads candidate rows when producing aggregate quality counts.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ... import universe
from ...state_features import liquidity_bucket
from ..radar import market_enrichment
from ..radar import market_units as event_market_units
from .market_no_send_io import read_jsonl
from .market_provenance import DECISION_RADAR_MEASUREMENT_PROGRAM

MARKET_SNAPSHOT_UNIT_VALIDATION_CONTRACT_VERSION = 1
POINT_IN_TIME_UNIVERSE_POLICY = "bounded_top_liquid_by_total_volume"
CONTROL_LIQUIDITY_TIER_BASIS = (
    "state_features_liquidity_bucket_v1:liquidity_usd_and_turnover_24h"
)
CONTROL_MARKET_REGIME_SCHEMA_ID = (
    "decision_radar.point_in_time_control_market_regime"
)
CONTROL_MARKET_REGIME_SCHEMA_VERSION = 1
CONTROL_MARKET_REGIME_BASIS = (
    "coingecko_temporal_24h_btc_and_top_liquid_median_sign_v1"
)
CONTROL_MARKET_REGIMES = frozenset(("risk_on", "risk_off", "mixed"))
CONTROL_MARKET_REGIME_REASONS = frozenset((
    "current_rows_empty",
    "current_cycle_context_invalid",
    "temporal_return_24h_incomplete",
    "btc_context_missing",
))
CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_ID = (
    "decision_radar.point_in_time_control_market_regime_input_diagnostic"
)
CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION = 1
CONTROL_MARKET_REGIME_INPUT_REASON_CODES = frozenset((
    "market_history_not_counted",
    "observation_identity_missing",
    "canonical_asset_identity_missing",
    "temporal_return_value_missing_or_invalid",
    "temporal_return_unit_invalid",
    "temporal_return_evidence_invalid",
))
_CONTROL_MARKET_REGIME_KEYS = frozenset((
    "schema_id",
    "schema_version",
    "status",
    "reason",
    "regime",
    "basis",
    "observed_at",
    "horizon_hours",
    "return_unit",
    "btc_canonical_asset_id",
    "btc_observation_id",
    "btc_return_24h_percent_points",
    "universe_input_count",
    "universe_expected_count",
    "universe_limit",
    "universe_policy",
    "universe_median_return_24h_percent_points",
    "input_observation_ids",
    "input_observations_sha256",
    "all_inputs_current_cycle",
    "all_inputs_point_in_time_universe_members",
    "all_inputs_temporal_return_evidence_ready",
    "selection_uses_outcomes",
    "historical_context_backfilled",
    "routing_eligible",
    "decision_policy_eligible",
    "protocol_v2_evidence_eligible",
    "provider_calls",
    "research_only",
))
_CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_KEYS = frozenset((
    "schema_id",
    "schema_version",
    "status",
    "reason",
    "basis",
    "observed_at",
    "universe_row_count",
    "universe_expected_count",
    "universe_limit",
    "eligible_input_count",
    "missing_input_count",
    "missing_inputs",
    "missing_input_reason_counts",
    "bitcoin_input_ready",
    "all_inputs_ready",
    "replayed_control_market_regime",
    "selection_uses_outcomes",
    "historical_context_backfilled",
    "retained_history_mutated",
    "routing_eligible",
    "decision_policy_eligible",
    "protocol_v2_evidence_eligible",
    "provider_calls",
    "research_only",
))
_TEMPORAL_RETURN_EVIDENCE_KEYS = frozenset((
    "basis",
    "status",
    "calculation",
    "sample_count",
    "current_observation_id",
    "baseline_first_observation_id",
    "baseline_last_observation_id",
    "baseline_input_observation_count",
    "baseline_observation_ids_sha256",
    "providers",
    "data_modes",
    "research_only",
))
_RETURN_UNIT_ALIASES = {
    "fraction": "fraction",
    "fractions": "fraction",
    "decimal": "fraction",
    "raw_fraction": "fraction",
    "percent": "percent_points",
    "percentage": "percent_points",
    "percent_points": "percent_points",
    "percentage_points": "percent_points",
    "pct": "percent_points",
    "pct_points": "percent_points",
}
_RETURN_UNIT_FIELDS = (
    "return_unit",
    "source_return_unit",
    "market_return_unit",
    "unit",
)


@dataclass(frozen=True)
class _MarketQualityInputs:
    market_cap: float | None
    total_volume: float | None
    volume_mcap: float | None
    volume_zscore: float | None
    volume_zscore_basis: str
    liquidity: float | None
    liquidity_basis: str
    spread_bps: float | None
    feature_basis: Mapping[str, str]
    direct_features: int
    proxy_features: int


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
    normalized = []
    for index, row in enumerate(ranked):
        normalized_row = _normalize_market_row(
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
        normalized.append(
            _attach_point_in_time_universe_context(
                normalized_row,
                rank=index + 1,
                selected_count=len(ranked),
                requested_limit=top_n,
            )
        )
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


def _attach_point_in_time_universe_context(
    row: Mapping[str, Any],
    *,
    rank: int,
    selected_count: int,
    requested_limit: int,
) -> dict[str, Any]:
    """Retain outcome-blind universe context without changing Radar policy.

    ``control_liquidity_tier`` deliberately has its own name.  It is the
    existing empirical-control bucket and must not replace the operator-facing
    ``liquidity_tier`` consumed by Decision routing.
    """

    output = dict(row)
    output.update({
        "point_in_time_universe_member": True,
        "point_in_time_volume_rank": rank,
        "point_in_time_universe_size": selected_count,
        "point_in_time_universe_limit": requested_limit,
        "point_in_time_universe_policy": POINT_IN_TIME_UNIVERSE_POLICY,
        "control_liquidity_tier": liquidity_bucket(
            output.get("liquidity_usd"),
            output.get("volume_to_market_cap"),
        ),
        "control_liquidity_tier_basis": CONTROL_LIQUIDITY_TIER_BASIS,
    })
    return output


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
    return_unit_contract = (
        _explicit_return_unit_contract(row) if explicit_returns else None
    )
    if explicit_returns and return_unit_contract is None:
        raise ValueError("market_row_return_unit_metadata_invalid")
    snapshot = (
        _normalized_explicit_market_row(
            row,
            return_unit_contract=return_unit_contract,
        )
        if explicit_returns
        else market_enrichment.market_snapshot_from_row(row, now=observed_at)
    )
    coin_id = _first_identity_text(row, "coin_id", "id", max_length=160)
    symbol = _first_identity_text(row, "symbol", max_length=32).upper()
    canonical_asset_id = _canonical_asset_identity(
        row,
        fallback=coin_id or symbol,
    )
    quality = _market_quality_inputs(
        row,
        snapshot,
        explicit_returns=explicit_returns,
        proxy_zscore=proxy_zscore,
    )
    snapshot.update({
        "coin_id": coin_id,
        "symbol": symbol,
        "canonical_asset_id": canonical_asset_id,
        "name": _first_identity_text(row, "name", max_length=160) or None,
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
        "market_cap": quality.market_cap,
        "volume_24h": quality.total_volume,
        "total_volume": quality.total_volume,
        "volume_to_market_cap": quality.volume_mcap,
        "feature_basis": {
            "volume_24h": (
                "provider_observed" if quality.total_volume is not None else "unavailable"
            ),
            "market_cap": (
                "provider_observed" if quality.market_cap is not None else "unavailable"
            ),
            "turnover_24h": (
                "derived_provider_ratio" if quality.volume_mcap is not None else "unavailable"
            ),
        },
        "volume_zscore_24h": quality.volume_zscore,
        "volume_zscore_basis": quality.volume_zscore_basis,
        "liquidity_usd": quality.liquidity,
        "liquidity_basis": quality.liquidity_basis,
        "spread_bps": quality.spread_bps,
        "spread_status": "verified" if quality.spread_bps is not None else "unavailable",
        "market_feature_basis": quality.feature_basis,
        "market_data_quality": _initial_market_quality(
            quality.feature_basis,
            direct_features=quality.direct_features,
            proxy_features=quality.proxy_features,
            spread_available=quality.spread_bps is not None,
            liquidity_basis=quality.liquidity_basis,
            volume_zscore_basis=quality.volume_zscore_basis,
        ),
        "direct_market_feature_count": quality.direct_features,
        "proxy_market_feature_count": quality.proxy_features,
        "is_tradable_asset": True,
        "venues": [provider],
        **dict(safety_counters),
    })
    return {key: value for key, value in snapshot.items() if value is not None}


def _market_quality_inputs(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    explicit_returns: bool,
    proxy_zscore: float | None,
) -> _MarketQualityInputs:
    market_cap = _finite_alias_value(row, "market_cap", minimum=0.0, exclusive=True)
    total_volume = _finite_alias_value(
        row, "total_volume", "volume_24h", minimum=0.0,
    )
    explicit_liquidity = _finite_alias_value(row, "liquidity_usd", minimum=0.0)
    liquidity = explicit_liquidity if explicit_liquidity is not None else total_volume
    volume_mcap = (
        total_volume / market_cap
        if total_volume is not None and market_cap is not None else None
    )
    provider_volume_zscore = finite_float(row.get("volume_zscore_24h"))
    proxy_volume_zscore = finite_float(proxy_zscore)
    volume_zscore = (
        provider_volume_zscore
        if provider_volume_zscore is not None else proxy_volume_zscore
    )
    liquidity_basis = (
        "provider_observed" if explicit_liquidity is not None
        else "coingecko_total_volume_24h_proxy" if total_volume is not None
        else "unavailable"
    )
    volume_zscore_basis = (
        "provider_observed" if provider_volume_zscore is not None
        else "cross_sectional_log_turnover_proxy" if proxy_volume_zscore is not None
        else "unavailable"
    )
    spread_bps = _finite_alias_value(row, "spread_bps", minimum=0.0)
    returns_available = _any_finite(
        snapshot, "return_1h", "return_4h", "return_24h", "return_72h", "return_7d",
    )
    relative_strength_available = _any_finite(
        snapshot,
        "relative_return_vs_btc_1h", "relative_return_vs_btc_4h",
        "relative_return_vs_btc_24h", "relative_return_vs_eth_1h",
        "relative_return_vs_eth_4h", "relative_return_vs_eth_24h",
    )
    feature_basis = {
        "returns": (
            "provider_observed_explicit" if explicit_returns
            else "provider_derived_sparkline" if returns_available
            else "unavailable"
        ),
        "relative_strength": (
            "benchmark_derived_same_observation"
            if relative_strength_available else "unavailable"
        ),
        "volume_turnover": (
            "derived_provider_ratio" if volume_mcap is not None else "unavailable"
        ),
        "volume_zscore": volume_zscore_basis,
        "liquidity": liquidity_basis,
        "spread": "provider_observed" if spread_bps is not None else "unavailable",
    }
    return _MarketQualityInputs(
        market_cap=market_cap,
        total_volume=total_volume,
        volume_mcap=volume_mcap,
        volume_zscore=volume_zscore,
        volume_zscore_basis=volume_zscore_basis,
        liquidity=liquidity,
        liquidity_basis=liquidity_basis,
        spread_bps=spread_bps,
        feature_basis=feature_basis,
        direct_features=sum(
            1 for value in feature_basis.values()
            if any(token in value for token in (
                "provider_observed", "provider_derived", "benchmark_derived",
            ))
        ),
        proxy_features=sum(1 for value in feature_basis.values() if "proxy" in value),
    )


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
        "point_in_time_universe_policy": POINT_IN_TIME_UNIVERSE_POLICY,
        "point_in_time_universe_context_count": sum(
            row.get("point_in_time_universe_member") is True for row in rows
        ),
        "control_liquidity_tier_basis": CONTROL_LIQUIDITY_TIER_BASIS,
        "provider": provider,
        "data_mode": data_mode,
        "observed_at": observed_at.isoformat(),
        "direct_feature_count": sum(
            _first_nonnegative_count((row, "direct_market_feature_count"))
            for row in rows
        ),
        "proxy_feature_count": sum(
            _first_nonnegative_count((row, "proxy_market_feature_count"))
            for row in rows
        ),
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
    unit_warning_rows = 0
    unit_warnings: Counter[str] = Counter()
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
        row_unit_warnings = _snapshot_unit_warnings(snapshot)
        if row_unit_warnings:
            unit_warning_rows += 1
            unit_warnings.update(row_unit_warnings)
        direct += _first_nonnegative_count(
            (quality, "direct_feature_count"),
            (snapshot, "direct_market_feature_count"),
            (row, "direct_market_feature_count"),
        )
        proxy += _first_nonnegative_count(
            (quality, "proxy_feature_count"),
            (snapshot, "proxy_market_feature_count"),
            (row, "proxy_market_feature_count"),
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
        "market_snapshot_unit_validation_contract_version": (
            MARKET_SNAPSHOT_UNIT_VALIDATION_CONTRACT_VERSION
        ),
        "market_snapshot_unit_validation_status": (
            "clean" if rows and not unit_warning_rows
            else "blocked" if unit_warning_rows
            else "not_evaluated"
        ),
        "market_snapshot_unit_warning_row_count": unit_warning_rows,
        "market_snapshot_unit_warning_count": sum(unit_warnings.values()),
        "market_snapshot_unit_warning_counts": dict(sorted(unit_warnings.items())),
        "baseline_status": baseline_status,
        "baseline_status_counts": dict(sorted(statuses.items())),
        "baseline_warm_assets": warm,
        "baseline_warming_assets": warming,
        "direct_feature_count": direct,
        "proxy_feature_count": proxy,
    }


def _snapshot_unit_warnings(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    value = snapshot.get("unit_warnings")
    if value in (None, "", [], ()):
        return ()
    if not isinstance(value, (list, tuple)):
        return ("unit_warnings_contract_invalid",)
    warnings = tuple(
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    )
    if len(warnings) != len(value):
        return (*warnings, "unit_warnings_contract_invalid")
    return warnings


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


def point_in_time_control_market_regime(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one closed control-only regime from exact current-cycle returns.

    The context deliberately uses the separately derived temporal 24-hour
    return, never the provider sparkline alias consumed by the Decision model.
    It is attached only to retained research history by the persistence caller.
    No outcome, route, score, or threshold is read here.
    """

    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not materialized:
        return _unavailable_control_market_regime("current_rows_empty")
    expected_values = [row.get("point_in_time_universe_size") for row in materialized]
    limit_values = [row.get("point_in_time_universe_limit") for row in materialized]
    policy_values = [row.get("point_in_time_universe_policy") for row in materialized]
    observed_values = {str(row.get("observed_at") or "") for row in materialized}
    rank_values = [row.get("point_in_time_volume_rank") for row in materialized]
    expected = (
        expected_values[0]
        if all(item == expected_values[0] for item in expected_values)
        else None
    )
    limit = (
        limit_values[0]
        if all(item == limit_values[0] for item in limit_values)
        else None
    )
    policy = (
        policy_values[0]
        if all(item == policy_values[0] for item in policy_values)
        else None
    )
    observed_at = next(iter(observed_values)) if len(observed_values) == 1 else ""
    if (
        type(expected) is not int
        or expected < 1
        or len(materialized) != expected
        or type(limit) is not int
        or limit < expected
        or policy != POINT_IN_TIME_UNIVERSE_POLICY
        or not all(type(rank) is int for rank in rank_values)
        or sorted(rank_values) != list(range(1, expected + 1))
        or any(row.get("point_in_time_universe_member") is not True for row in materialized)
        or not _aware_iso8601(observed_at)
    ):
        return _unavailable_control_market_regime(
            "current_cycle_context_invalid",
            observed_at=observed_at or None,
            universe_expected_count=expected if type(expected) is int else 0,
            universe_limit=limit if type(limit) is int else 0,
            universe_policy=str(policy or ""),
        )

    inputs: list[dict[str, Any]] = []
    for row in sorted(
        materialized,
        key=lambda item: int(item["point_in_time_volume_rank"]),
    ):
        history = row.get("market_history")
        evidence = row.get("market_feature_evidence")
        return_units = row.get("return_units")
        temporal_evidence = (
            evidence.get("temporal_return_24h")
            if isinstance(evidence, Mapping) else None
        )
        observation_id = (
            history.get("observation_id") if isinstance(history, Mapping) else None
        )
        value = finite_float(row.get("temporal_return_24h"))
        asset_id = _identity_text(row.get("canonical_asset_id"), max_length=160)
        if not asset_id:
            return _unavailable_control_market_regime(
                "current_cycle_context_invalid",
                observed_at=observed_at,
                universe_expected_count=expected,
                universe_limit=limit,
                universe_policy=policy,
            )
        if (
            not isinstance(history, Mapping)
            or history.get("baseline_counted") is not True
            or not isinstance(observation_id, str)
            or not observation_id
            or value is None
            or not isinstance(return_units, Mapping)
            or return_units.get("temporal_return_24h") != "percent_points"
            or not _temporal_return_evidence_ready(
                temporal_evidence,
                observation_id=observation_id,
            )
        ):
            return _unavailable_control_market_regime(
                "temporal_return_24h_incomplete",
                observed_at=observed_at,
                universe_expected_count=expected,
                universe_limit=limit,
                universe_policy=policy,
            )
        inputs.append({
            "canonical_asset_id": asset_id,
            "observation_id": observation_id,
            "observed_at": observed_at,
            "point_in_time_volume_rank": row["point_in_time_volume_rank"],
            "temporal_return_24h_percent_points": round(value, 12),
            "temporal_return_evidence_sha256": _sha256_json(temporal_evidence),
        })
    if len({item["canonical_asset_id"] for item in inputs}) != expected:
        return _unavailable_control_market_regime(
            "current_cycle_context_invalid",
            observed_at=observed_at,
            universe_expected_count=expected,
            universe_limit=limit,
            universe_policy=policy,
        )
    btc = [item for item in inputs if item["canonical_asset_id"] == "bitcoin"]
    if len(btc) != 1:
        return _unavailable_control_market_regime(
            "btc_context_missing",
            observed_at=observed_at,
            universe_expected_count=expected,
            universe_limit=limit,
            universe_policy=policy,
        )
    btc_return = float(btc[0]["temporal_return_24h_percent_points"])
    median_return = round(statistics.median(
        float(item["temporal_return_24h_percent_points"]) for item in inputs
    ), 12)
    regime = (
        "risk_on"
        if btc_return > 0.0 and median_return > 0.0
        else "risk_off"
        if btc_return < 0.0 and median_return < 0.0
        else "mixed"
    )
    value = {
        "schema_id": CONTROL_MARKET_REGIME_SCHEMA_ID,
        "schema_version": CONTROL_MARKET_REGIME_SCHEMA_VERSION,
        "status": "observed",
        "reason": None,
        "regime": regime,
        "basis": CONTROL_MARKET_REGIME_BASIS,
        "observed_at": observed_at,
        "horizon_hours": 24,
        "return_unit": "percent_points",
        "btc_canonical_asset_id": "bitcoin",
        "btc_observation_id": btc[0]["observation_id"],
        "btc_return_24h_percent_points": round(btc_return, 12),
        "universe_input_count": len(inputs),
        "universe_expected_count": expected,
        "universe_limit": limit,
        "universe_policy": policy,
        "universe_median_return_24h_percent_points": median_return,
        "input_observation_ids": [item["observation_id"] for item in inputs],
        "input_observations_sha256": _sha256_json(inputs),
        "all_inputs_current_cycle": True,
        "all_inputs_point_in_time_universe_members": True,
        "all_inputs_temporal_return_evidence_ready": True,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "research_only": True,
    }
    if not control_market_regime_evidence_valid(value):  # pragma: no cover
        raise AssertionError("control market regime evidence invalid")
    return value


def control_market_regime_evidence_valid(value: object) -> bool:
    """Validate the closed compact regime evidence copied into history rows."""

    if not isinstance(value, Mapping) or set(value) != _CONTROL_MARKET_REGIME_KEYS:
        return False
    if (
        value.get("schema_id") != CONTROL_MARKET_REGIME_SCHEMA_ID
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != CONTROL_MARKET_REGIME_SCHEMA_VERSION
        or value.get("status") not in {"observed", "unavailable"}
        or value.get("basis") != CONTROL_MARKET_REGIME_BASIS
        or value.get("horizon_hours") != 24
        or value.get("return_unit") != "percent_points"
        or value.get("selection_uses_outcomes") is not False
        or value.get("historical_context_backfilled") is not False
        or value.get("routing_eligible") is not False
        or value.get("decision_policy_eligible") is not False
        or value.get("protocol_v2_evidence_eligible") is not False
        or type(value.get("provider_calls")) is not int
        or value.get("provider_calls") != 0
        or value.get("research_only") is not True
    ):
        return False
    if value.get("status") == "unavailable":
        expected = value.get("universe_expected_count")
        limit = value.get("universe_limit")
        return (
            value.get("reason") in CONTROL_MARKET_REGIME_REASONS
            and value.get("regime") is None
            and value.get("btc_canonical_asset_id") is None
            and value.get("btc_observation_id") is None
            and value.get("btc_return_24h_percent_points") is None
            and value.get("universe_median_return_24h_percent_points") is None
            and value.get("input_observation_ids") == []
            and value.get("input_observations_sha256") is None
            and value.get("all_inputs_current_cycle") is False
            and value.get("all_inputs_point_in_time_universe_members") is False
            and value.get("all_inputs_temporal_return_evidence_ready") is False
            and _nonnegative_integer(value.get("universe_input_count"))
            and _nonnegative_integer(expected)
            and _nonnegative_integer(limit)
            and value.get("universe_policy") in {"", POINT_IN_TIME_UNIVERSE_POLICY}
            and (
                value.get("observed_at") is None
                or _aware_iso8601(value.get("observed_at"))
            )
        )
    btc_return = finite_float(value.get("btc_return_24h_percent_points"))
    median_return = finite_float(
        value.get("universe_median_return_24h_percent_points")
    )
    expected_regime = (
        "risk_on"
        if btc_return is not None and median_return is not None
        and btc_return > 0.0 and median_return > 0.0
        else "risk_off"
        if btc_return is not None and median_return is not None
        and btc_return < 0.0 and median_return < 0.0
        else "mixed"
    )
    expected = value.get("universe_expected_count")
    limit = value.get("universe_limit")
    observation_ids = value.get("input_observation_ids")
    return bool(
        value.get("reason") is None
        and value.get("regime") in CONTROL_MARKET_REGIMES
        and value.get("regime") == expected_regime
        and _aware_iso8601(value.get("observed_at"))
        and value.get("btc_canonical_asset_id") == "bitcoin"
        and isinstance(value.get("btc_observation_id"), str)
        and value.get("btc_observation_id")
        and btc_return is not None
        and median_return is not None
        and type(expected) is int
        and expected > 0
        and type(value.get("universe_input_count")) is int
        and value.get("universe_input_count") == expected
        and type(limit) is int
        and limit >= expected
        and value.get("universe_policy") == POINT_IN_TIME_UNIVERSE_POLICY
        and isinstance(observation_ids, list)
        and len(observation_ids) == expected
        and all(
            isinstance(item, str) and 0 < len(item) <= 160
            for item in observation_ids
        )
        and len(set(observation_ids)) == expected
        and value.get("btc_observation_id") in observation_ids
        and isinstance(value.get("input_observations_sha256"), str)
        and len(value["input_observations_sha256"]) == 64
        and all(character in "0123456789abcdef" for character in value["input_observations_sha256"])
        and value.get("all_inputs_current_cycle") is True
        and value.get("all_inputs_point_in_time_universe_members") is True
        and value.get("all_inputs_temporal_return_evidence_ready") is True
    )


def point_in_time_control_market_regime_input_diagnostic(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Explain exact current-cycle regime input readiness without mutation.

    This is a read-only replay diagnostic.  It does not make an unavailable
    regime usable, write evidence to retained history, or expose the result to
    routing.  Its purpose is to name the precise current rows and field-level
    reasons that keep the closed regime projection from becoming observed.
    """

    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    replayed = point_in_time_control_market_regime(materialized)
    missing_inputs: list[dict[str, Any]] = []
    eligible_asset_ids: list[str] = []
    for index, row in enumerate(materialized, start=1):
        reasons: list[str] = []
        history = row.get("market_history")
        evidence = row.get("market_feature_evidence")
        units = row.get("return_units")
        observation_id = (
            history.get("observation_id") if isinstance(history, Mapping) else None
        )
        raw_asset_id = row.get("canonical_asset_id")
        asset_id = (
            raw_asset_id.strip()
            if isinstance(raw_asset_id, str)
            and 0 < len(raw_asset_id.strip()) <= 160
            else f"unidentified-row-{index}"
        )
        raw_symbol = row.get("symbol")
        symbol = (
            raw_symbol.strip()
            if isinstance(raw_symbol, str) and len(raw_symbol.strip()) <= 32
            else ""
        )
        rank = row.get("point_in_time_volume_rank")
        if not isinstance(history, Mapping) or history.get("baseline_counted") is not True:
            reasons.append("market_history_not_counted")
        if not isinstance(observation_id, str) or not observation_id:
            reasons.append("observation_identity_missing")
        if asset_id.startswith("unidentified-row-"):
            reasons.append("canonical_asset_identity_missing")
        if finite_float(row.get("temporal_return_24h")) is None:
            reasons.append("temporal_return_value_missing_or_invalid")
        if (
            not isinstance(units, Mapping)
            or units.get("temporal_return_24h") != "percent_points"
        ):
            reasons.append("temporal_return_unit_invalid")
        temporal_evidence = (
            evidence.get("temporal_return_24h")
            if isinstance(evidence, Mapping)
            else None
        )
        if not isinstance(observation_id, str) or not _temporal_return_evidence_ready(
            temporal_evidence,
            observation_id=observation_id or "",
        ):
            reasons.append("temporal_return_evidence_invalid")
        if reasons:
            missing_inputs.append({
                "canonical_asset_id": asset_id,
                "symbol": symbol,
                "point_in_time_volume_rank": (
                    rank if type(rank) is int and rank > 0 else None
                ),
                "reasons": sorted(set(reasons)),
            })
        else:
            eligible_asset_ids.append(asset_id)
    missing_inputs.sort(key=lambda item: (
        item["point_in_time_volume_rank"] is None,
        item["point_in_time_volume_rank"] or 0,
        item["canonical_asset_id"],
    ))
    reason_counts = Counter(
        reason
        for item in missing_inputs
        for reason in item["reasons"]
    )
    expected = replayed.get("universe_expected_count")
    limit = replayed.get("universe_limit")
    status = (
        "ready"
        if replayed.get("status") == "observed"
        else "incomplete"
        if (
            replayed.get("reason") == "temporal_return_24h_incomplete"
            and type(expected) is int
            and expected == len(materialized)
            and 0 < len(eligible_asset_ids) < len(materialized)
        )
        else "unavailable"
    )
    value = {
        "schema_id": CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_ID,
        "schema_version": CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION,
        "status": status,
        "reason": replayed.get("reason"),
        "basis": CONTROL_MARKET_REGIME_BASIS,
        "observed_at": replayed.get("observed_at"),
        "universe_row_count": len(materialized),
        "universe_expected_count": expected if type(expected) is int else 0,
        "universe_limit": limit if type(limit) is int else 0,
        "eligible_input_count": len(eligible_asset_ids),
        "missing_input_count": len(missing_inputs),
        "missing_inputs": missing_inputs,
        "missing_input_reason_counts": dict(sorted(reason_counts.items())),
        "bitcoin_input_ready": "bitcoin" in eligible_asset_ids,
        "all_inputs_ready": replayed.get("status") == "observed",
        "replayed_control_market_regime": replayed,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "retained_history_mutated": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "research_only": True,
    }
    if not control_market_regime_input_diagnostic_valid(value):  # pragma: no cover
        raise AssertionError("control market regime input diagnostic invalid")
    return value


def control_market_regime_input_diagnostic_valid(value: object) -> bool:
    """Validate the closed read-only current-input diagnostic."""

    if (
        not isinstance(value, Mapping)
        or set(value) != _CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_KEYS
        or value.get("schema_id")
        != CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_ID
        or value.get("schema_version")
        != CONTROL_MARKET_REGIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION
        or value.get("status") not in {"ready", "incomplete", "unavailable"}
        or value.get("basis") != CONTROL_MARKET_REGIME_BASIS
        or value.get("selection_uses_outcomes") is not False
        or value.get("historical_context_backfilled") is not False
        or value.get("retained_history_mutated") is not False
        or type(value.get("bitcoin_input_ready")) is not bool
        or type(value.get("all_inputs_ready")) is not bool
        or value.get("routing_eligible") is not False
        or value.get("decision_policy_eligible") is not False
        or value.get("protocol_v2_evidence_eligible") is not False
        or value.get("provider_calls") != 0
        or value.get("research_only") is not True
    ):
        return False
    replayed = value.get("replayed_control_market_regime")
    if not control_market_regime_evidence_valid(replayed):
        return False
    row_count = value.get("universe_row_count")
    expected = value.get("universe_expected_count")
    limit = value.get("universe_limit")
    eligible = value.get("eligible_input_count")
    missing_count = value.get("missing_input_count")
    missing_inputs = value.get("missing_inputs")
    if not (
        _nonnegative_integer(row_count)
        and _nonnegative_integer(expected)
        and _nonnegative_integer(limit)
        and _nonnegative_integer(eligible)
        and _nonnegative_integer(missing_count)
        and eligible + missing_count == row_count
        and isinstance(missing_inputs, list)
        and len(missing_inputs) == missing_count
        and len(missing_inputs) <= 256
        and value.get("reason") == replayed.get("reason")
        and value.get("observed_at") == replayed.get("observed_at")
    ):
        return False
    expected_reason_counts: Counter[str] = Counter()
    missing_asset_ids: set[str] = set()
    for item in missing_inputs:
        if not isinstance(item, Mapping) or set(item) != {
            "canonical_asset_id",
            "symbol",
            "point_in_time_volume_rank",
            "reasons",
        }:
            return False
        asset_id = item.get("canonical_asset_id")
        symbol = item.get("symbol")
        rank = item.get("point_in_time_volume_rank")
        reasons = item.get("reasons")
        if not (
            isinstance(asset_id, str)
            and 0 < len(asset_id) <= 160
            and asset_id not in missing_asset_ids
            and isinstance(symbol, str)
            and len(symbol) <= 32
            and (rank is None or (type(rank) is int and rank > 0))
            and isinstance(reasons, list)
            and reasons
            and reasons == sorted(set(reasons))
            and all(reason in CONTROL_MARKET_REGIME_INPUT_REASON_CODES for reason in reasons)
        ):
            return False
        missing_asset_ids.add(asset_id)
        expected_reason_counts.update(reasons)
    if value.get("missing_input_reason_counts") != dict(
        sorted(expected_reason_counts.items())
    ):
        return False
    if value.get("status") == "ready":
        return bool(
            replayed.get("status") == "observed"
            and value.get("reason") is None
            and row_count == expected == eligible
            and missing_count == 0
            and value.get("bitcoin_input_ready") is True
            and value.get("all_inputs_ready") is True
        )
    if value.get("status") == "incomplete":
        return bool(
            replayed.get("status") == "unavailable"
            and value.get("reason") == "temporal_return_24h_incomplete"
            and row_count == expected
            and 0 < eligible < row_count
            and missing_count > 0
            and value.get("all_inputs_ready") is False
        )
    return bool(
        replayed.get("status") == "unavailable"
        and value.get("all_inputs_ready") is False
    )


def _unavailable_control_market_regime(
    reason: str,
    *,
    observed_at: str | None = None,
    universe_expected_count: int = 0,
    universe_limit: int = 0,
    universe_policy: str = "",
) -> dict[str, Any]:
    value = {
        "schema_id": CONTROL_MARKET_REGIME_SCHEMA_ID,
        "schema_version": CONTROL_MARKET_REGIME_SCHEMA_VERSION,
        "status": "unavailable",
        "reason": reason,
        "regime": None,
        "basis": CONTROL_MARKET_REGIME_BASIS,
        "observed_at": observed_at if _aware_iso8601(observed_at) else None,
        "horizon_hours": 24,
        "return_unit": "percent_points",
        "btc_canonical_asset_id": None,
        "btc_observation_id": None,
        "btc_return_24h_percent_points": None,
        "universe_input_count": 0,
        "universe_expected_count": max(0, universe_expected_count),
        "universe_limit": max(0, universe_limit),
        "universe_policy": (
            universe_policy
            if universe_policy == POINT_IN_TIME_UNIVERSE_POLICY
            else ""
        ),
        "universe_median_return_24h_percent_points": None,
        "input_observation_ids": [],
        "input_observations_sha256": None,
        "all_inputs_current_cycle": False,
        "all_inputs_point_in_time_universe_members": False,
        "all_inputs_temporal_return_evidence_ready": False,
        "selection_uses_outcomes": False,
        "historical_context_backfilled": False,
        "routing_eligible": False,
        "decision_policy_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "provider_calls": 0,
        "research_only": True,
    }
    if not control_market_regime_evidence_valid(value):  # pragma: no cover
        raise AssertionError("unavailable control market regime evidence invalid")
    return value


def _temporal_return_evidence_ready(
    value: object,
    *,
    observation_id: str,
) -> bool:
    if not isinstance(value, Mapping) or set(value) != _TEMPORAL_RETURN_EVIDENCE_KEYS:
        return False
    anchor_id = value.get("baseline_first_observation_id")
    return bool(
        value.get("status") == "ready"
        and value.get("basis") == "temporal_baseline"
        and value.get("calculation") == "price_horizon_return"
        and value.get("current_observation_id") == observation_id
        and value.get("sample_count") == 1
        and value.get("baseline_input_observation_count") == 1
        and isinstance(anchor_id, str)
        and anchor_id
        and value.get("baseline_last_observation_id") == anchor_id
        and value.get("baseline_observation_ids_sha256")
        == _sha256_json([anchor_id])
        and value.get("providers") == ["coingecko"]
        and value.get("data_modes") == ["live"]
        and value.get("research_only") is True
    )


def _sha256_json(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _aware_iso8601(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


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
        "direct_feature_count": sum(
            _first_nonnegative_count((row, "direct_market_feature_count"))
            for row in materialized
        ),
        "proxy_feature_count": sum(
            _first_nonnegative_count((row, "proxy_market_feature_count"))
            for row in materialized
        ),
        "spread_available_count": sum(1 for row in materialized if row.get("spread_bps") is not None),
        "history_schema_version": history_summary.get("schema_version"),
        "history_artifact": history_filename,
        "research_only": True,
    }


def finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _first_nonnegative_count(
    *sources: tuple[Mapping[str, Any], str],
) -> int:
    """Return the first supplied count without letting invalid evidence fall through."""

    for source, field in sources:
        if field not in source:
            continue
        value = source.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        parsed = finite_float(value)
        if parsed is None or parsed < 0 or not parsed.is_integer():
            return 0
        return int(parsed)
    return 0


def _any_finite(row: Mapping[str, Any], *fields: str) -> bool:
    return any(finite_float(row.get(field)) is not None for field in fields)


def _normalized_explicit_market_row(
    row: Mapping[str, Any],
    *,
    return_unit_contract: tuple[str, dict[str, str]],
) -> dict[str, Any]:
    output = {
        key: value
        for key in (
            "return_1h", "return_4h", "return_24h", "return_72h", "return_7d",
            "relative_return_vs_btc_1h", "relative_return_vs_btc_4h",
            "relative_return_vs_btc_24h", "relative_return_vs_eth_1h",
            "relative_return_vs_eth_4h", "relative_return_vs_eth_24h",
        )
        if (value := finite_float(row.get(key))) is not None
    }
    price = _finite_alias_value(row, "current_price", "price", minimum=0.0, exclusive=True)
    if price is not None:
        output["price"] = price
    return_unit, return_units = return_unit_contract
    output["return_unit"] = return_unit
    if return_units:
        output["return_units"] = return_units
    output["coin_id"] = _first_identity_text(
        row,
        "coin_id",
        "id",
        max_length=160,
    )
    output["symbol"] = _first_identity_text(
        row,
        "symbol",
        max_length=32,
    ).upper()
    return output


def _cross_sectional_turnover_zscores(rows: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    values: dict[int, float] = {}
    for index, row in enumerate(rows):
        volume = _finite_alias_value(
            row,
            "total_volume",
            "volume_24h",
            minimum=0.0,
        )
        market_cap = _finite_alias_value(
            row,
            "market_cap",
            minimum=0.0,
            exclusive=True,
        )
        if volume is None or market_cap is None:
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
        _finite_alias_value(
            row,
            "total_volume",
            "volume_24h",
            minimum=0.0,
        ) or 0.0,
        _finite_alias_value(row, "liquidity_usd", minimum=0.0) or 0.0,
        _finite_alias_value(
            row,
            "market_cap",
            minimum=0.0,
            exclusive=True,
        ) or 0.0,
    )


def _has_explicit_return_fields(row: Mapping[str, Any]) -> bool:
    return any(
        finite_float(row.get(key)) is not None
        for key in ("return_1h", "return_4h", "return_24h")
    )


def _explicit_return_unit_contract(
    row: Mapping[str, Any],
) -> tuple[str, dict[str, str]] | None:
    """Close common and field-level units before copying explicit returns."""

    declared_common_units: list[str] = []
    for field in _RETURN_UNIT_FIELDS:
        if field not in row:
            continue
        value = row.get(field)
        if value is None or value == "":
            continue
        canonical = _canonical_return_unit(value)
        if canonical is None:
            return None
        declared_common_units.append(canonical)
    if len(set(declared_common_units)) > 1:
        return None
    common_unit = declared_common_units[0] if declared_common_units else "fraction"

    projections: list[dict[str, str]] = []
    for metadata_field in event_market_units.RETURN_UNIT_METADATA_KEYS:
        if metadata_field not in row:
            continue
        raw = row.get(metadata_field)
        if not isinstance(raw, Mapping):
            return None
        projection: dict[str, str] = {}
        for field, unit in raw.items():
            if not isinstance(field, str) or field not in event_market_units.RETURN_KEYS:
                return None
            canonical = _canonical_return_unit(unit)
            if canonical is None:
                return None
            projection[field] = canonical
        projections.append(dict(sorted(projection.items())))
    if projections and any(value != projections[0] for value in projections[1:]):
        return None
    return common_unit, (projections[0] if projections else {})


def _canonical_return_unit(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return _RETURN_UNIT_ALIASES.get(value.strip().casefold())


def _finite_alias_value(
    row: Mapping[str, Any],
    *keys: str,
    minimum: float | None = None,
    exclusive: bool = False,
) -> float | None:
    """Return the first supplied alias without shadowing canonical zeroes.

    A supplied but invalid higher-priority value fails closed instead of being
    silently replaced by a lower-priority alias. Missing and blank values may
    fall through to the next documented alias.
    """

    for key in keys:
        if key not in row:
            continue
        raw = row.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        value = finite_float(raw)
        if value is None:
            return None
        if minimum is not None and (
            value < minimum or (exclusive and value == minimum)
        ):
            return None
        return value
    return None


def _identity_text(value: object, *, max_length: int) -> str:
    """Return bounded identity text without coercing structured evidence."""

    if not isinstance(value, str):
        return ""
    text = value.strip()
    if (
        not text
        or len(text) > max_length
        or any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in text
        )
    ):
        return ""
    return text


def _first_identity_text(
    row: Mapping[str, Any],
    *keys: str,
    max_length: int,
) -> str:
    """Resolve identity aliases while preserving invalid explicit precedence."""

    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None or value == "":
            continue
        return _identity_text(value, max_length=max_length)
    return ""


def _canonical_asset_identity(row: Mapping[str, Any], *, fallback: str) -> str:
    if "canonical_asset_id" not in row or row.get("canonical_asset_id") in (None, ""):
        return fallback
    return _identity_text(row.get("canonical_asset_id"), max_length=160)


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
