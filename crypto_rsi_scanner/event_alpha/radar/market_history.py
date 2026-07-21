"""Pure rolling market history and temporal baseline calculations. Callers own
persistence and provide prior observations plus normalized current rows;
derived returns use percentage points.
Provider fields and bases are preserved, and only fields explicitly marked as proxy are replaced.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from crypto_rsi_scanner.state_features import liquidity_bucket

from crypto_rsi_scanner.event_alpha.radar.market_history_models import (
    BASELINE_COUNTED,
    BASELINE_DUPLICATE,
    BASELINE_TOO_CLOSE,
    FEATURE_READINESS_GROUPS,
    MARKET_HISTORY_ENRICHMENT_SCHEMA,
    MARKET_HISTORY_OBSERVATION_SCHEMA,
    MARKET_HISTORY_SCHEMA_VERSION,
    MARKET_HISTORY_SUMMARY_SCHEMA,
    RETURN_UNIT_PERCENT_POINTS,
    TEMPORAL_BASELINE_BASIS,
    TEMPORAL_RELATIVE_STRENGTH_BASIS,
    MarketHistoryConfig,
    _MarketHistoryResult,
    _PreparedObservation,
    _RelativeReturnSample,
    _ReturnSample,
    _Telemetry,
    _config_values,
)
from crypto_rsi_scanner.event_alpha.radar.market_history_summary import (
    build_market_history_summary,
)


_WARM_FEATURE_STATUSES = {"ready", "constant_baseline", "warm"}

_LINEAGE_TEXT_FIELDS = (
    "provider", "source", "market_data_source", "data_mode", "provider_source_artifact",
    "data_acquisition_mode", "candidate_source_mode", "provider_generation_id",
    "provider_source_artifact_sha256", "request_ledger_path", "request_ledger_sha256",
    "measurement_program", "decision_radar_campaign_reason",
    "contract_counted_status", "no_send_status",
)
_LINEAGE_BOOL_FIELDS = (
    "provenance_contract_valid", "burn_in_eligible", "burn_in_counted",
    "decision_radar_campaign_eligible", "decision_radar_campaign_counted",
    "research_only",
)
_LINEAGE_FIELDS = (*_LINEAGE_TEXT_FIELDS, *_LINEAGE_BOOL_FIELDS)
_POINT_IN_TIME_CONTEXT_FIELDS = (
    "point_in_time_universe_member",
    "point_in_time_volume_rank",
    "point_in_time_universe_size",
    "point_in_time_universe_limit",
    "point_in_time_universe_policy",
    "control_liquidity_tier",
    "control_liquidity_tier_basis",
    "market_regime",
    "market_regime_basis",
    "market_regime_evidence",
    "protocol_partition",
    "protocol_partition_basis",
)
_CONTROL_LIQUIDITY_TIERS = {"high", "mid", "low", "unknown"}
_POINT_IN_TIME_UNIVERSE_POLICY = "bounded_top_liquid_by_total_volume"
_CONTROL_LIQUIDITY_TIER_BASIS = (
    "state_features_liquidity_bucket_v1:liquidity_usd_and_turnover_24h"
)
_POINT_IN_TIME_UNIVERSE_FIELDS = (
    "point_in_time_universe_member",
    "point_in_time_volume_rank",
    "point_in_time_universe_size",
    "point_in_time_universe_limit",
    "point_in_time_universe_policy",
    "control_liquidity_tier",
    "control_liquidity_tier_basis",
)
_CONTROL_MARKET_REGIMES = {"risk_on", "risk_off", "mixed"}
_CONTROL_MARKET_REGIME_EVIDENCE_KEYS = {
    "schema_id", "schema_version", "status", "reason", "regime", "basis",
    "observed_at", "horizon_hours", "return_unit", "btc_canonical_asset_id",
    "btc_observation_id", "btc_return_24h_percent_points",
    "universe_input_count", "universe_expected_count", "universe_limit",
    "universe_policy", "universe_median_return_24h_percent_points",
    "input_observation_ids", "input_observations_sha256",
    "all_inputs_current_cycle",
    "all_inputs_point_in_time_universe_members",
    "all_inputs_temporal_return_evidence_ready", "selection_uses_outcomes",
    "historical_context_backfilled", "routing_eligible",
    "decision_policy_eligible", "protocol_v2_evidence_eligible",
    "provider_calls", "research_only",
}
_PROXY_BASIS_MARKERS = ("proxy", "cross_sectional", "24h_volume")
_SCALAR_FEATURE_BASIS_FIELDS = (
    "price_basis",
    "volume_24h_basis",
    "market_cap_basis",
    "turnover_24h_basis",
    "turnover_basis",
    "volume_zscore_basis",
    "volume_zscore_24h_basis",
    "turnover_zscore_basis",
)
_UNSEALED_PROTOCOL_PARTITION_FIELDS = (
    "protocol_partition",
    "protocol_partition_basis",
)


def enrich_market_rows_with_history(
    current_rows: Iterable[Mapping[str, Any]],
    existing_history: Iterable[Mapping[str, Any]] = (),
    *,
    now: datetime | str,
    config: MarketHistoryConfig | None = None,
) -> _MarketHistoryResult:
    """Enrich current normalized rows from a bounded temporal history.

    The output row order matches ``current_rows``.  Valid current observations
    are evaluated against strictly earlier retained observations, so the
    current value never leaks into its own z-score baseline.  Existing-history
    conflicts are resolved by a stable completeness/canonical-JSON ordering;
    a conflicting current observation at an already-retained key fails closed.
    """
    cfg = config or MarketHistoryConfig()
    evaluated_at = _require_aware_utc(now, field_name="now")
    current = [copy.deepcopy(dict(row)) for row in current_rows if isinstance(row, Mapping)]
    historical = [copy.deepcopy(dict(row)) for row in existing_history if isinstance(row, Mapping)]
    telemetry = _Telemetry(example_limit=cfg.rejection_example_limit)
    prepared_history = _prepare_rows(
        historical,
        role="history",
        now=evaluated_at,
        max_age=cfg.max_history_age,
        telemetry=telemetry,
    )
    canonical_history = _deduplicate_history(prepared_history, telemetry)
    canonical_history, historical_cadence_counts = _classify_history_cadence(
        canonical_history,
        minimum_spacing=cfg.minimum_observation_spacing,
    )
    history_by_asset = _group_observations(canonical_history)
    counted_history_by_asset = _counted_observations(history_by_asset)
    prepared_current, current_rejections = _prepare_current_rows(
        current,
        now=evaluated_at,
        cfg=cfg,
        telemetry=telemetry,
    )
    accepted_current, current_statuses = _select_current_observations(
        prepared_current,
        history_by_asset=history_by_asset,
        telemetry=telemetry,
    )
    current_rejections.update(current_statuses)
    current_cadence_counts = _classify_current_cadence(
        accepted_current,
        history_by_asset=history_by_asset,
        minimum_spacing=cfg.minimum_observation_spacing,
    )
    combined_by_asset: dict[str, list[dict[str, Any]]] = {
        asset: [copy.deepcopy(item) for item in observations]
        for asset, observations in history_by_asset.items()
    }
    for prepared in accepted_current.values():
        observations = combined_by_asset.setdefault(prepared.asset_id, [])
        if not any(_observation_time(item) == prepared.observed_at for item in observations):
            observations.append(copy.deepcopy(prepared.observation))
    evaluation_by_asset: dict[str, list[dict[str, Any]]] = {
        asset: [copy.deepcopy(item) for item in observations]
        for asset, observations in counted_history_by_asset.items()
    }
    for prepared in accepted_current.values():
        observations = evaluation_by_asset.setdefault(prepared.asset_id, [])
        if not any(_observation_time(item) == prepared.observed_at for item in observations):
            observations.append(copy.deepcopy(prepared.observation))
    for observations in evaluation_by_asset.values():
        observations.sort(key=_observation_sort_key)
    pruned_by_limit = 0
    for asset_id, observations in combined_by_asset.items():
        observations.sort(key=_observation_sort_key)
        if len(observations) > cfg.max_observations_per_asset:
            pruned_by_limit += len(observations) - cfg.max_observations_per_asset
            combined_by_asset[asset_id] = observations[-cfg.max_observations_per_asset :]
    enriched: list[dict[str, Any]] = []
    warmup_status_counts: Counter[str] = Counter()
    warmup_feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
    warmup_group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    feature_basis_counts: Counter[str] = Counter()
    for index, source_row in enumerate(current):
        prepared = accepted_current.get(index)
        if prepared is None:
            reason = current_rejections.get(index, "invalid_observation")
            enriched.append(_rejected_current_row(source_row, reason))
            warmup_status_counts["rejected"] += 1
            continue
        row = _enrich_current_row(
            source_row,
            current=prepared,
            history_by_asset=evaluation_by_asset,
            cfg=cfg,
        )
        enriched.append(row)
        history_status = str(row.get("market_history", {}).get("status") or "unknown")
        warmup_status_counts[history_status] += 1
        warmup = row.get("market_history", {}).get("warmup")
        if isinstance(warmup, Mapping):
            for feature, details in warmup.items():
                if isinstance(details, Mapping):
                    warmup_feature_counts[str(feature)][str(details.get("status") or "unknown")] += 1
        groups = row.get("market_history", {}).get("feature_readiness")
        if isinstance(groups, Mapping):
            for group, details in groups.items():
                if isinstance(details, Mapping):
                    warmup_group_counts[str(group)][str(details.get("status") or "unknown")] += 1
        evidence = row.get("market_feature_evidence")
        if isinstance(evidence, Mapping):
            for details in evidence.values():
                if isinstance(details, Mapping) and details.get("basis"):
                    feature_basis_counts[str(details["basis"])] += 1
    retained = tuple(
        copy.deepcopy(observation)
        for asset_id in sorted(combined_by_asset)
        for observation in sorted(combined_by_asset[asset_id], key=_observation_sort_key)
    )
    summary = build_market_history_summary(
        schema_id=MARKET_HISTORY_SUMMARY_SCHEMA,
        schema_version=MARKET_HISTORY_SCHEMA_VERSION,
        evaluated_at=_iso(evaluated_at),
        config=_config_values(cfg),
        current_row_count=len(current),
        historical_row_count=len(historical),
        accepted_current_count=len(accepted_current),
        accepted_historical_count=len(canonical_history),
        current_cadence_counts=current_cadence_counts,
        historical_cadence_counts=historical_cadence_counts,
        minimum_observation_spacing_seconds=int(
            cfg.minimum_observation_spacing.total_seconds()
        ),
        rejection_counts=telemetry.counts,
        rejection_examples=telemetry.examples,
        retained=retained,
        retained_asset_count=len(combined_by_asset),
        pruned_by_age=int(telemetry.role_counts.get(("history", "stale"), 0)),
        pruned_by_limit=pruned_by_limit,
        warmup_status_counts=warmup_status_counts,
        warmup_feature_counts=warmup_feature_counts,
        warmup_group_counts=warmup_group_counts,
        feature_basis_counts=feature_basis_counts,
    )
    return _MarketHistoryResult(tuple(enriched), retained, summary)


def _prepare_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    role: str,
    now: datetime,
    max_age: timedelta,
    telemetry: _Telemetry,
) -> list[_PreparedObservation]:
    prepared: list[_PreparedObservation] = []
    for index, row in enumerate(rows):
        candidate, reason = _prepare_observation(row, role=role, index=index, now=now, max_age=max_age)
        if candidate is None:
            telemetry.record(reason, role=role, index=index)
            continue
        prepared.append(candidate)
    return prepared


def _prepare_current_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
    cfg: MarketHistoryConfig,
    telemetry: _Telemetry,
) -> tuple[list[_PreparedObservation], dict[int, str]]:
    prepared: list[_PreparedObservation] = []
    rejections: dict[int, str] = {}
    for index, row in enumerate(rows):
        candidate, reason = _prepare_observation(
            row,
            role="current",
            index=index,
            now=now,
            max_age=cfg.max_current_age,
            future_tolerance=cfg.future_tolerance,
        )
        if candidate is None:
            rejections[index] = reason
            telemetry.record(reason, role="current", index=index)
            continue
        prepared.append(candidate)
    return prepared, rejections


def _prepare_observation(
    row: Mapping[str, Any],
    *,
    role: str,
    index: int,
    now: datetime,
    max_age: timedelta,
    future_tolerance: timedelta = timedelta(0),
) -> tuple[_PreparedObservation | None, str]:
    asset_id, identity_error = _canonical_asset_identity(row)
    if not asset_id:
        return None, identity_error
    if _lineage_claims_invalid(row):
        return None, "invalid_lineage_claim"
    if _feature_basis_claims_invalid(row):
        return None, "invalid_feature_basis_claim"
    if _point_in_time_universe_claims_invalid(row):
        return None, "invalid_point_in_time_universe_claim"
    if any(
        field in row and row.get(field) not in (None, "")
        for field in _UNSEALED_PROTOCOL_PARTITION_FIELDS
    ):
        return None, "unsealed_protocol_partition_claim"
    raw_time = row.get("provider_observed_at") or row.get("observed_at") or row.get("timestamp")
    observed_at, time_error = _parse_aware_time(raw_time)
    if observed_at is None:
        return None, time_error
    if observed_at > now + future_tolerance:
        return None, "future"
    if observed_at < now - max_age:
        return None, "stale"
    observation = _observation_values(row, asset_id=asset_id, observed_at=observed_at)
    return _PreparedObservation(index, observation, asset_id, observed_at), ""


def _lineage_claims_invalid(row: Mapping[str, Any]) -> bool:
    """Reject explicit lineage that cannot remain typed through persistence."""

    for field in _LINEAGE_TEXT_FIELDS:
        if field not in row or row.get(field) in (None, ""):
            continue
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            return True
    return any(
        field in row
        and row.get(field) is not None
        and type(row.get(field)) is not bool
        for field in _LINEAGE_BOOL_FIELDS
    )


def _feature_basis_claims_invalid(row: Mapping[str, Any]) -> bool:
    """Reject explicit feature provenance that would otherwise be stringified."""

    for field in ("feature_basis", "market_feature_basis"):
        if field not in row or row.get(field) in (None, ""):
            continue
        value = row.get(field)
        if not isinstance(value, Mapping) or any(
            not _nonempty_basis_text(key) or not _nonempty_basis_text(item)
            for key, item in value.items()
        ):
            return True

    for field in _SCALAR_FEATURE_BASIS_FIELDS:
        if field in row and row.get(field) not in (None, ""):
            if not _nonempty_basis_text(row.get(field)):
                return True

    if "market_feature_evidence" not in row or row.get("market_feature_evidence") in (
        None,
        "",
    ):
        return False
    evidence = row.get("market_feature_evidence")
    if not isinstance(evidence, Mapping):
        return True
    for feature, details in evidence.items():
        if not _nonempty_basis_text(feature) or not isinstance(details, Mapping):
            return True
        if "basis" in details and not _nonempty_basis_text(details.get("basis")):
            return True
    return False


def _nonempty_basis_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _point_in_time_universe_claims_invalid(row: Mapping[str, Any]) -> bool:
    """Require one closed cross-field contract whenever current context is claimed."""

    if not any(
        field in row and row.get(field) not in (None, "")
        for field in _POINT_IN_TIME_UNIVERSE_FIELDS
    ):
        return False
    rank = row.get("point_in_time_volume_rank")
    size = row.get("point_in_time_universe_size")
    limit = row.get("point_in_time_universe_limit")
    liquidity_tier = row.get("control_liquidity_tier")
    liquidity_value = _first_number(
        row,
        "liquidity_usd",
        "volume_24h",
        "total_volume",
        "spot_volume_24h",
    )
    turnover_value = _first_number(
        row,
        "turnover_24h",
        "volume_to_market_cap",
        "volume_mcap",
    )
    if turnover_value is None:
        volume = _first_number(row, "volume_24h", "total_volume", "spot_volume_24h")
        market_cap = _first_number(row, "market_cap", "mcap")
        if volume is not None and market_cap is not None and market_cap > 0:
            turnover_value = volume / market_cap
    expected_liquidity_tier = (
        liquidity_bucket(liquidity_value, turnover_value)
        if liquidity_value is not None
        and liquidity_value >= 0
        and (turnover_value is None or turnover_value >= 0)
        else None
    )
    return not (
        row.get("point_in_time_universe_member") is True
        and type(rank) is int
        and rank > 0
        and type(size) is int
        and size > 0
        and type(limit) is int
        and limit > 0
        and rank <= size <= limit
        and row.get("point_in_time_universe_policy")
        == _POINT_IN_TIME_UNIVERSE_POLICY
        and isinstance(liquidity_tier, str)
        and liquidity_tier in _CONTROL_LIQUIDITY_TIERS
        and row.get("control_liquidity_tier_basis")
        == _CONTROL_LIQUIDITY_TIER_BASIS
        and liquidity_tier == expected_liquidity_tier
    )


def _deduplicate_history(
    rows: Sequence[_PreparedObservation],
    telemetry: _Telemetry,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, datetime], list[_PreparedObservation]] = defaultdict(list)
    for row in rows:
        groups[row.key].append(row)
    retained: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda value: (value[0], value[1])):
        candidates = groups[key]
        ordered = sorted(candidates, key=_prepared_preference_key)
        winner = ordered[0]
        retained.append(copy.deepcopy(winner.observation))
        winner_signature = _feature_signature(winner.observation)
        for duplicate in ordered[1:]:
            reason = (
                "duplicate"
                if _feature_signature(duplicate.observation) == winner_signature
                else "duplicate_conflict"
            )
            telemetry.record(
                reason,
                role="history",
                index=duplicate.index,
                asset_id=duplicate.asset_id,
                observed_at=duplicate.observed_at,
            )
    return retained


def _classify_history_cadence(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_spacing: timedelta,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Mark retained raw evidence without letting rapid rows warm baselines."""

    grouped = _group_observations(rows)
    classified: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for asset_id in sorted(grouped):
        last_counted_at: datetime | None = None
        for source in grouped[asset_id]:
            row = copy.deepcopy(source)
            observed_at = _observation_time(row)
            status = (
                BASELINE_COUNTED
                if last_counted_at is None or observed_at - last_counted_at >= minimum_spacing
                else BASELINE_TOO_CLOSE
            )
            row["baseline_counted"] = status == BASELINE_COUNTED
            row["baseline_counting_status"] = status
            if status == BASELINE_COUNTED:
                last_counted_at = observed_at
            counts[status] += 1
            classified.append(row)
    return classified, counts


def _counted_observations(
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        asset_id: [
            copy.deepcopy(dict(row))
            for row in rows
            if row.get("baseline_counted") is True
        ]
        for asset_id, rows in grouped.items()
    }


def _classify_current_cadence(
    accepted: Mapping[int, _PreparedObservation],
    *,
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    minimum_spacing: timedelta,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    status_by_key: dict[tuple[str, datetime], str] = {}
    for prepared in sorted(
        accepted.values(),
        key=lambda item: (item.asset_id, item.observed_at, item.index),
    ):
        status = status_by_key.get(prepared.key)
        if status is None:
            history = list(history_by_asset.get(prepared.asset_id, ()))
            existing_same_time = any(
                _observation_time(item) == prepared.observed_at for item in history
            )
            counted_times = [
                _observation_time(item)
                for item in history
                if item.get("baseline_counted") is True
                and _observation_time(item) < prepared.observed_at
            ]
            latest_counted = max(counted_times, default=None)
            if existing_same_time:
                status = BASELINE_DUPLICATE
            elif (
                latest_counted is not None
                and prepared.observed_at - latest_counted < minimum_spacing
            ):
                status = BASELINE_TOO_CLOSE
            else:
                status = BASELINE_COUNTED
            status_by_key[prepared.key] = status
            counts[status] += 1
        prepared.observation["baseline_counted"] = status == BASELINE_COUNTED
        prepared.observation["baseline_counting_status"] = status
    return counts


def _select_current_observations(
    rows: Sequence[_PreparedObservation],
    *,
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    telemetry: _Telemetry,
) -> tuple[dict[int, _PreparedObservation], dict[int, str]]:
    by_asset: dict[str, list[_PreparedObservation]] = defaultdict(list)
    for row in rows:
        by_asset[row.asset_id].append(row)
    accepted: dict[int, _PreparedObservation] = {}
    statuses: dict[int, str] = {}
    for asset_id in sorted(by_asset):
        candidates = by_asset[asset_id]
        newest_time = max(item.observed_at for item in candidates)
        newest = [item for item in candidates if item.observed_at == newest_time]
        older = [item for item in candidates if item.observed_at != newest_time]
        for item in older:
            statuses[item.index] = "out_of_order"
            telemetry.record(
                "out_of_order",
                role="current",
                index=item.index,
                asset_id=asset_id,
                observed_at=item.observed_at,
            )
        ordered = sorted(newest, key=_prepared_preference_key)
        winner = ordered[0]
        winner_signature = _feature_signature(winner.observation)
        identical_aliases: list[_PreparedObservation] = []
        for item in ordered[1:]:
            if _feature_signature(item.observation) == winner_signature:
                identical_aliases.append(item)
                telemetry.record(
                    "duplicate",
                    role="current",
                    index=item.index,
                    asset_id=asset_id,
                    observed_at=item.observed_at,
                )
            else:
                statuses[item.index] = "duplicate_conflict"
                telemetry.record(
                    "duplicate_conflict",
                    role="current",
                    index=item.index,
                    asset_id=asset_id,
                    observed_at=item.observed_at,
                )
        history = list(history_by_asset.get(asset_id, ()))
        latest_history_time = max((_observation_time(item) for item in history), default=None)
        existing_same_time = next(
            (item for item in history if _observation_time(item) == winner.observed_at),
            None,
        )
        if latest_history_time is not None and winner.observed_at < latest_history_time:
            rejected = [winner, *identical_aliases]
            for item in rejected:
                statuses[item.index] = "out_of_order"
                telemetry.record(
                    "out_of_order",
                    role="current",
                    index=item.index,
                    asset_id=asset_id,
                    observed_at=item.observed_at,
                )
            continue
        if existing_same_time is not None:
            if _feature_signature(existing_same_time) != winner_signature:
                rejected = [winner, *identical_aliases]
                for item in rejected:
                    statuses[item.index] = "duplicate_conflict"
                    telemetry.record(
                        "duplicate_conflict",
                        role="current",
                        index=item.index,
                        asset_id=asset_id,
                        observed_at=item.observed_at,
                    )
                continue
            telemetry.record(
                "duplicate",
                role="current",
                index=winner.index,
                asset_id=asset_id,
                observed_at=winner.observed_at,
            )
        accepted[winner.index] = winner
        for item in identical_aliases:
            accepted[item.index] = item
    return accepted, statuses


def _enrich_current_row(
    source_row: Mapping[str, Any],
    *,
    current: _PreparedObservation,
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    cfg: MarketHistoryConfig,
) -> dict[str, Any]:
    row = copy.deepcopy(dict(source_row))
    observations = list(history_by_asset.get(current.asset_id, ()))
    prior = [item for item in observations if _observation_time(item) < current.observed_at]
    evidence = _copy_evidence(row.get("market_feature_evidence"))
    warmup: dict[str, dict[str, Any]] = {}
    baseline_values: dict[str, Any] = {}
    scalar_specs = (
        ("volume_24h", "volume_zscore_24h", "temporal_volume_zscore_24h",
         ("volume_zscore_basis", "volume_zscore_24h_basis"), "volume_zscore_basis"),
        ("turnover_24h", "turnover_zscore", "temporal_turnover_zscore",
         ("turnover_zscore_basis", "turnover_basis"), "turnover_zscore_basis"),
    )
    for source_field, feature, temporal_field, basis_fields, basis_field in scalar_specs:
        baseline_rows = [item for item in prior if _number(item.get(source_field)) is not None]
        baseline = [_number(item.get(source_field)) for item in baseline_rows]
        baseline = [value for value in baseline if value is not None]
        value, stats = _zscore(
            _number(current.observation.get(source_field)),
            baseline,
            minimum=cfg.min_baseline_observations,
        )
        stats = _with_feature_coverage(
            stats,
            baseline_rows,
            required=_required_coverage(cfg, horizon_hours=0),
        )
        _record_baseline_feature(
            row, evidence, warmup, baseline_values,
            feature=feature, temporal_field=temporal_field, value=value, stats=stats,
            current=current, evidence_rows=baseline_rows,
        )
        if value is not None and _canonical_field_accepts_temporal(
            row, feature, basis_fields=basis_fields,
        ):
            _preserve_proxy_value(row, feature, basis_field)
            row[feature] = value
            row[basis_field] = TEMPORAL_BASELINE_BASIS
    current_returns, current_return_samples = _enrich_return_baselines(
        row,
        evidence,
        warmup,
        baseline_values,
        current=current,
        observations=observations,
        prior=prior,
        cfg=cfg,
    )
    _enrich_relative_baselines(
        row,
        evidence,
        warmup,
        baseline_values,
        current,
        prior,
        current_returns,
        current_return_samples,
        history_by_asset=history_by_asset, cfg=cfg,
    )
    return _finish_current_enrichment(
        row, current, observations, prior, warmup, baseline_values, evidence,
        cfg=cfg,
    )


def _enrich_return_baselines(
    row: dict[str, Any],
    evidence: dict[str, Any],
    warmup: dict[str, dict[str, Any]],
    baseline_values: dict[str, Any],
    *,
    current: _PreparedObservation,
    observations: Sequence[Mapping[str, Any]],
    prior: Sequence[Mapping[str, Any]],
    cfg: MarketHistoryConfig,
) -> tuple[dict[int, float | None], dict[int, _ReturnSample | None]]:
    current_returns: dict[int, float | None] = {}
    current_samples: dict[int, _ReturnSample | None] = {}
    for hours in sorted(cfg.return_horizons_hours):
        current_sample = _return_sample_for_endpoint(
            current.observation,
            observations,
            hours=hours,
            cfg=cfg,
        )
        historical_samples = _historical_return_samples(prior, hours=hours, cfg=cfg)
        current_return = current_sample.value if current_sample is not None else None
        historical_returns = [sample.value for sample in historical_samples]
        historical_evidence_rows = [
            evidence_row
            for sample in historical_samples
            for evidence_row in sample.evidence_rows
        ]
        current_returns[hours] = current_return
        current_samples[hours] = current_sample
        return_z, return_stats = _zscore(
            current_return,
            historical_returns,
            minimum=cfg.min_baseline_observations,
        )
        return_stats = _with_feature_coverage(
            return_stats,
            historical_evidence_rows,
            required=_required_coverage(cfg, horizon_hours=hours),
        )
        return_field = f"return_{hours}h"
        temporal_return_field = f"temporal_return_{hours}h"
        if current_return is not None:
            row[temporal_return_field] = current_return
            _declare_return_unit(row, temporal_return_field)
            if row.get(return_field) in (None, ""):
                row[return_field] = current_return
                _declare_return_unit(row, return_field)
            evidence[temporal_return_field] = _feature_evidence(
                current=current,
                sample_count=1,
                status="ready",
                calculation="price_horizon_return",
                evidence_rows=(current_sample.anchor,),
            )
        _record_baseline_feature(
            row,
            evidence,
            warmup,
            baseline_values,
            feature=f"return_zscore_{hours}h",
            temporal_field=f"temporal_return_zscore_{hours}h",
            value=return_z,
            stats=return_stats,
            current=current,
            evidence_rows=historical_evidence_rows,
        )
        volatility = (
            _rounded(statistics.pstdev(historical_returns))
            if len(historical_returns) >= 2
            else None
        )
        volatility_status = _baseline_status(
            current_return,
            len(historical_returns),
            cfg.min_baseline_observations,
            allow_constant=True,
        )
        volatility_stats = {
            "status": volatility_status,
            "sample_count": len(historical_returns),
            "required_sample_count": cfg.min_baseline_observations,
            "mean": (
                _rounded(statistics.fmean(historical_returns))
                if historical_returns
                else None
            ),
            "standard_deviation": volatility,
        }
        volatility_stats = _with_feature_coverage(
            volatility_stats,
            historical_evidence_rows,
            required=_required_coverage(cfg, horizon_hours=hours),
        )
        _record_baseline_feature(
            row,
            evidence,
            warmup,
            baseline_values,
            feature=f"return_volatility_{hours}h",
            temporal_field=f"temporal_return_volatility_{hours}h",
            value=volatility if volatility_status == "ready" else None,
            stats=volatility_stats,
            current=current,
            evidence_rows=historical_evidence_rows,
        )
        if volatility is not None and volatility_status == "ready":
            _declare_return_unit(row, f"temporal_return_volatility_{hours}h")
        absolute_returns = [abs(value) for value in historical_returns]
        volatility_z, volatility_z_stats = _zscore(
            abs(current_return) if current_return is not None else None,
            absolute_returns,
            minimum=cfg.min_baseline_observations,
        )
        volatility_z_stats = _with_feature_coverage(
            volatility_z_stats,
            historical_evidence_rows,
            required=_required_coverage(cfg, horizon_hours=hours),
        )
        _record_baseline_feature(
            row,
            evidence,
            warmup,
            baseline_values,
            feature=f"volatility_zscore_{hours}h",
            temporal_field=f"temporal_volatility_zscore_{hours}h",
            value=volatility_z,
            stats=volatility_z_stats,
            current=current,
            evidence_rows=historical_evidence_rows,
        )
    return current_returns, current_samples


def _enrich_relative_baselines(
    row: dict[str, Any],
    evidence: dict[str, Any],
    warmup: dict[str, dict[str, Any]],
    baseline_values: dict[str, Any],
    current: _PreparedObservation,
    prior: Sequence[Mapping[str, Any]],
    current_returns: Mapping[int, float | None],
    current_return_samples: Mapping[int, _ReturnSample | None],
    *,
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    cfg: MarketHistoryConfig,
) -> None:
    benchmarks = (
        ("btc", _find_benchmark_asset(history_by_asset, cfg.btc_asset_ids)),
        ("eth", _find_benchmark_asset(history_by_asset, cfg.eth_asset_ids)),
    )
    for name, asset_id in benchmarks:
        observations = list(history_by_asset.get(asset_id, ())) if asset_id else []
        if asset_id == current.asset_id:
            for hours in sorted(cfg.return_horizons_hours):
                feature = f"relative_return_vs_{name}_{hours}h_zscore"
                _record_baseline_feature(
                    row, evidence, warmup, baseline_values,
                    feature=feature, temporal_field=f"temporal_{feature}", value=None,
                    stats={"status": "not_applicable", "sample_count": 0, "required_sample_count": 0},
                    current=current,
                    benchmark_asset_id=asset_id,
                    evidence_rows=(),
                )
            continue
        endpoint = _aligned_observation(
            observations, current.observed_at, tolerance=cfg.benchmark_alignment_tolerance,
        )
        for hours in sorted(cfg.return_horizons_hours):
            feature = f"relative_return_vs_{name}_{hours}h"
            benchmark_sample = (
                _return_sample_for_endpoint(endpoint, observations, hours=hours, cfg=cfg)
                if endpoint is not None
                else None
            )
            asset_sample = current_return_samples.get(hours)
            benchmark_return = benchmark_sample.value if benchmark_sample is not None else None
            asset_return = current_returns.get(hours)
            relative = (
                _rounded(asset_return - benchmark_return)
                if asset_return is not None and benchmark_return is not None else None
            )
            historical_samples = _historical_relative_return_samples(
                prior,
                observations,
                hours=hours,
                cfg=cfg,
            )
            history = [sample.value for sample in historical_samples]
            historical_evidence_rows = [
                evidence_row
                for sample in historical_samples
                for evidence_row in sample.evidence_rows
            ]
            relative_z, stats = _zscore(
                relative, history, minimum=cfg.min_baseline_observations,
            )
            stats = _with_feature_coverage(
                stats,
                historical_evidence_rows,
                required=_required_coverage(cfg, horizon_hours=hours),
            )
            if relative is not None:
                temporal_field = f"temporal_{feature}"
                row[temporal_field] = relative
                _declare_return_unit(row, temporal_field)
                if row.get(feature) in (None, ""):
                    row[feature] = relative
                    _declare_return_unit(row, feature)
                    row[f"{feature}_basis"] = TEMPORAL_RELATIVE_STRENGTH_BASIS
                    _record_temporal_relative_strength_basis(row)
                evidence[temporal_field] = _feature_evidence(
                    current=current, sample_count=1, status="ready",
                    calculation=f"asset_return_minus_{name}_return", benchmark_asset_id=asset_id,
                    evidence_rows=(
                        asset_sample.anchor,
                        benchmark_sample.endpoint,
                        benchmark_sample.anchor,
                    ),
                )
            _record_baseline_feature(
                row, evidence, warmup, baseline_values,
                feature=f"{feature}_zscore", temporal_field=f"temporal_{feature}_zscore",
                value=relative_z, stats=stats, current=current,
                benchmark_asset_id=asset_id,
                evidence_rows=historical_evidence_rows,
            )


def _record_temporal_relative_strength_basis(row: dict[str, Any]) -> None:
    """Close the group-level basis when history supplies the canonical value.

    A stronger pre-existing basis remains authoritative.  This helper is only
    called when the temporal calculation filled the canonical relative-return
    field, so a parallel temporal diagnostic cannot relabel an independently
    supplied canonical value.
    """
    raw_basis = row.get("market_feature_basis")
    basis = dict(raw_basis) if isinstance(raw_basis, Mapping) else {}
    current_basis = str(basis.get("relative_strength") or "").strip().casefold()
    if current_basis in {"", "unavailable", "unknown", "not_evaluated"}:
        basis["relative_strength"] = TEMPORAL_RELATIVE_STRENGTH_BASIS
        row["market_feature_basis"] = basis


def _finish_current_enrichment(
    row: dict[str, Any],
    current: _PreparedObservation,
    observations: Sequence[Mapping[str, Any]],
    prior: Sequence[Mapping[str, Any]],
    warmup: Mapping[str, Mapping[str, Any]],
    baseline_values: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    cfg: MarketHistoryConfig,
) -> dict[str, Any]:
    statuses = [str(item.get("status") or "unknown") for item in warmup.values()]
    required_statuses = [status for status in statuses if status != "not_applicable"]
    warm_count = sum(status in _WARM_FEATURE_STATUSES for status in required_statuses)
    feature_readiness = _group_feature_readiness(warmup, cfg=cfg)
    required_groups = [
        details
        for group, details in feature_readiness.items()
        if group in cfg.required_feature_groups and details.get("required") is True
    ]
    if required_groups and all(details.get("status") == "warm" for details in required_groups):
        overall_status = "warm"
    elif prior:
        overall_status = "warming"
    else:
        overall_status = "cold"
    row["market_history"] = {
        "schema_id": MARKET_HISTORY_ENRICHMENT_SCHEMA,
        "schema_version": MARKET_HISTORY_SCHEMA_VERSION,
        "status": overall_status,
        "observation_id": current.observation["observation_id"],
        "canonical_asset_id": current.asset_id,
        "observation_count": len(observations),
        "prior_observation_count": len(prior),
        "oldest_observed_at": prior[0]["observed_at"] if prior else None,
        "newest_observed_at": observations[-1]["observed_at"] if observations else None,
        "warm_feature_count": warm_count,
        "feature_count": len(required_statuses),
        "not_applicable_feature_count": len(statuses) - len(required_statuses),
        "warmup": warmup,
        "feature_readiness": feature_readiness,
        "baseline_values": baseline_values,
        "baseline_counted": current.observation.get("baseline_counted") is True,
        "baseline_counting_status": current.observation.get("baseline_counting_status"),
        "return_unit": RETURN_UNIT_PERCENT_POINTS,
        "research_only": True,
    }
    row["market_history_status"] = overall_status
    row["market_history_observation_id"] = current.observation["observation_id"]
    row["market_history_baseline_counted"] = current.observation.get("baseline_counted") is True
    row["market_history_baseline_counting_status"] = current.observation.get(
        "baseline_counting_status"
    )
    row["market_feature_evidence"] = dict(evidence)
    return row


def _record_baseline_feature(
    row: dict[str, Any],
    evidence: dict[str, Any],
    warmup: dict[str, dict[str, Any]],
    baseline_values: dict[str, Any],
    *,
    feature: str,
    temporal_field: str,
    value: float | None,
    stats: Mapping[str, Any],
    current: _PreparedObservation,
    evidence_rows: Sequence[Mapping[str, Any]],
    benchmark_asset_id: str | None = None,
) -> None:
    status = str(stats.get("status") or "unknown")
    warmup[feature] = {
        "status": status,
        "sample_count": int(stats.get("sample_count") or 0),
        "required_sample_count": int(stats.get("required_sample_count") or 0),
        "coverage_seconds": int(stats.get("coverage_seconds") or 0),
        "required_coverage_seconds": int(stats.get("required_coverage_seconds") or 0),
        "oldest_sample_observed_at": stats.get("oldest_sample_observed_at"),
        "newest_sample_observed_at": stats.get("newest_sample_observed_at"),
        "basis": TEMPORAL_BASELINE_BASIS,
    }
    baseline_values[feature] = {
        "value": value,
        "mean": stats.get("mean"),
        "standard_deviation": stats.get("standard_deviation"),
        "sample_count": int(stats.get("sample_count") or 0),
        "coverage_seconds": int(stats.get("coverage_seconds") or 0),
        "required_coverage_seconds": int(stats.get("required_coverage_seconds") or 0),
        "status": status,
        "basis": TEMPORAL_BASELINE_BASIS,
    }
    if value is not None:
        row[temporal_field] = value
    evidence[temporal_field] = _feature_evidence(
        current=current,
        sample_count=int(stats.get("sample_count") or 0),
        status=status,
        calculation=feature,
        benchmark_asset_id=benchmark_asset_id,
        evidence_rows=evidence_rows,
    )


def _required_coverage(cfg: MarketHistoryConfig, *, horizon_hours: int) -> timedelta:
    cadence_span = cfg.minimum_observation_spacing * (cfg.min_baseline_observations - 1)
    return timedelta(hours=horizon_hours) + cadence_span


def _with_feature_coverage(
    stats: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    required: timedelta,
) -> dict[str, Any]:
    output = dict(stats)
    times = sorted(_observation_time(item) for item in observations)
    coverage = times[-1] - times[0] if len(times) >= 2 else timedelta(0)
    output.update({
        "coverage_seconds": max(0, int(coverage.total_seconds())),
        "required_coverage_seconds": int(required.total_seconds()),
        "oldest_sample_observed_at": _iso(times[0]) if times else None,
        "newest_sample_observed_at": _iso(times[-1]) if times else None,
    })
    if (
        str(output.get("status") or "") in _WARM_FEATURE_STATUSES
        and coverage < required
    ):
        output["status"] = "warming_time_coverage"
    return output


def _group_feature_readiness(
    warmup: Mapping[str, Mapping[str, Any]],
    *,
    cfg: MarketHistoryConfig,
) -> dict[str, dict[str, Any]]:
    horizons = tuple(sorted(cfg.return_horizons_hours))
    specs: dict[str, tuple[str, ...]] = {
        "volume": ("volume_zscore_24h",),
        "turnover": ("turnover_zscore",),
        "volatility": tuple(
            feature
            for hours in horizons
            for feature in (f"return_volatility_{hours}h", f"volatility_zscore_{hours}h")
        ),
        "returns_1h": ("return_zscore_1h",) if 1 in horizons else (),
        "returns_4h": ("return_zscore_4h",) if 4 in horizons else (),
        "returns_24h": ("return_zscore_24h",) if 24 in horizons else (),
        "btc_eth_relative": tuple(
            f"relative_return_vs_{benchmark}_{hours}h_zscore"
            for benchmark in ("btc", "eth")
            for hours in horizons
        ),
    }
    result: dict[str, dict[str, Any]] = {}
    for group in FEATURE_READINESS_GROUPS:
        features = specs[group]
        details = [dict(warmup[name]) for name in features if name in warmup]
        applicable = [item for item in details if item.get("status") != "not_applicable"]
        required = group in cfg.required_feature_groups and bool(features)
        if not features:
            status = "not_configured"
        elif applicable and all(str(item.get("status")) in _WARM_FEATURE_STATUSES for item in applicable):
            status = "warm"
        elif applicable and any(int(item.get("sample_count") or 0) > 0 for item in applicable):
            status = "warming"
        else:
            status = "cold"
        result[group] = {
            "status": status,
            "required": required,
            "features": list(features),
            "sample_count": min(
                (int(item.get("sample_count") or 0) for item in applicable),
                default=0,
            ),
            "required_sample_count": max(
                (int(item.get("required_sample_count") or 0) for item in applicable),
                default=0,
            ),
            "coverage_seconds": min(
                (int(item.get("coverage_seconds") or 0) for item in applicable),
                default=0,
            ),
            "required_coverage_seconds": max(
                (int(item.get("required_coverage_seconds") or 0) for item in applicable),
                default=0,
            ),
        }
    return result


def _feature_evidence(
    *,
    current: _PreparedObservation,
    evidence_rows: Sequence[Mapping[str, Any]],
    sample_count: int,
    status: str,
    calculation: str,
    benchmark_asset_id: str | None = None,
) -> dict[str, Any]:
    relevant = _canonical_evidence_rows(evidence_rows)
    observation_ids = [str(item["observation_id"]) for item in relevant]
    providers = sorted({str(item.get("provider") or "") for item in relevant if item.get("provider")})
    modes = sorted({str(item.get("data_mode") or "") for item in relevant if item.get("data_mode")})
    evidence = {
        "basis": TEMPORAL_BASELINE_BASIS,
        "status": status,
        "calculation": calculation,
        "sample_count": sample_count,
        "current_observation_id": current.observation["observation_id"],
        "baseline_first_observation_id": relevant[0].get("observation_id") if relevant else None,
        "baseline_last_observation_id": relevant[-1].get("observation_id") if relevant else None,
        "baseline_input_observation_count": len(relevant),
        "baseline_observation_ids_sha256": (
            hashlib.sha256(
                json.dumps(observation_ids, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if observation_ids
            else None
        ),
        "providers": providers,
        "data_modes": modes,
        "research_only": True,
    }
    if benchmark_asset_id:
        evidence["benchmark_asset_id"] = benchmark_asset_id
    return evidence


def _canonical_evidence_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Return exact input observations once, in deterministic temporal order."""

    by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        observation_id = str(row.get("observation_id") or "").strip()
        if not observation_id:
            raise ValueError("temporal feature evidence row is missing observation_id")
        existing = by_id.get(observation_id)
        if existing is not None and _canonical_json(existing) != _canonical_json(row):
            raise ValueError(
                f"temporal feature evidence observation conflict: {observation_id}"
            )
        by_id[observation_id] = row
    return sorted(by_id.values(), key=_observation_sort_key)


def _observation_values(
    row: Mapping[str, Any],
    *,
    asset_id: str,
    observed_at: datetime,
) -> dict[str, Any]:
    price = _first_number(row, "price", "current_price")
    if price is not None and price <= 0:
        price = None
    volume = _first_number(row, "volume_24h", "total_volume", "spot_volume_24h")
    if volume is not None and volume < 0:
        volume = None
    market_cap = _first_number(row, "market_cap", "mcap")
    if market_cap is not None and market_cap <= 0:
        market_cap = None
    supplied_turnover = _first_number(
        row,
        "turnover_24h",
        "volume_to_market_cap",
        "volume_mcap",
    )
    turnover = supplied_turnover
    if turnover is None and volume is not None and market_cap is not None:
        turnover = volume / market_cap
    if turnover is not None and turnover < 0:
        turnover = None
    timestamp = _iso(observed_at)
    observation: dict[str, Any] = {
        "schema_id": MARKET_HISTORY_OBSERVATION_SCHEMA,
        "schema_version": MARKET_HISTORY_SCHEMA_VERSION,
        "observation_id": _observation_id(asset_id, timestamp),
        "canonical_asset_id": asset_id,
        "coin_id": _first_identity_text(row, "coin_id", "id", max_length=160) or None,
        "symbol": (
            _first_identity_text(row, "symbol", "ticker", max_length=32).upper()
            or None
        ),
        "observed_at": timestamp,
        "price": price,
        "volume_24h": volume,
        "market_cap": market_cap,
        "turnover_24h": turnover,
        "return_unit": RETURN_UNIT_PERCENT_POINTS,
        "feature_basis": {
            "price": _input_feature_basis(
                row,
                "price",
                default="provider_observed" if price is not None else "unavailable",
            ),
            "volume_24h": _input_feature_basis(
                row,
                "volume_24h",
                default="provider_observed" if volume is not None else "unavailable",
            ),
            "market_cap": _input_feature_basis(
                row,
                "market_cap",
                default="provider_observed" if market_cap is not None else "unavailable",
            ),
            "turnover_24h": _input_feature_basis(
                row,
                "turnover_24h",
                default=(
                    "provider_observed"
                    if supplied_turnover is not None
                    else "derived_provider_ratio" if turnover is not None else "unavailable"
                ),
            ),
        },
        "research_only": True,
    }
    for key in _LINEAGE_FIELDS:
        if row.get(key) not in (None, ""):
            observation[key] = copy.deepcopy(row[key])
    for key in _POINT_IN_TIME_CONTEXT_FIELDS:
        value = _point_in_time_context_value(row, key)
        if value is not None:
            observation[key] = value
    return {key: value for key, value in observation.items() if value is not None}


def _point_in_time_context_value(row: Mapping[str, Any], key: str) -> Any:
    """Copy only closed point-in-time context; never infer it for old rows."""

    value = row.get(key)
    if key == "point_in_time_universe_member":
        return value if type(value) is bool else None
    if key in {
        "point_in_time_volume_rank",
        "point_in_time_universe_size",
        "point_in_time_universe_limit",
    }:
        return value if type(value) is int and value > 0 else None
    if key == "control_liquidity_tier":
        return value if type(value) is str and value in _CONTROL_LIQUIDITY_TIERS else None
    if key == "market_regime_evidence":
        return (
            copy.deepcopy(dict(value))
            if _closed_control_market_regime_evidence(value)
            and value.get("observed_at") == row.get("observed_at")
            and value.get("regime") == row.get("market_regime")
            and value.get("basis") == row.get("market_regime_basis")
            and value.get("universe_expected_count")
            == row.get("point_in_time_universe_size")
            and value.get("universe_limit")
            == row.get("point_in_time_universe_limit")
            and value.get("universe_policy")
            == row.get("point_in_time_universe_policy")
            else None
        )
    if key in _UNSEALED_PROTOCOL_PARTITION_FIELDS:
        return None
    if key in {
        "point_in_time_universe_policy",
        "control_liquidity_tier_basis",
        "market_regime",
        "market_regime_basis",
    }:
        return value if type(value) is str and 0 < len(value.strip()) <= 160 else None
    return None


def _closed_control_market_regime_evidence(value: object) -> bool:
    """Accept only closed, control-only observed evidence for persistence."""

    if not isinstance(value, Mapping) or set(value) != _CONTROL_MARKET_REGIME_EVIDENCE_KEYS:
        return False
    observed_at = value.get("observed_at")
    observed_time, _ = _parse_aware_time(observed_at)
    btc_return = _number(value.get("btc_return_24h_percent_points"))
    median_return = _number(
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
    expected_count = value.get("universe_expected_count")
    input_count = value.get("universe_input_count")
    universe_limit = value.get("universe_limit")
    observation_ids = value.get("input_observation_ids")
    btc_observation_id = value.get("btc_observation_id")
    digest = value.get("input_observations_sha256")
    if (
        value.get("schema_id") != "decision_radar.point_in_time_control_market_regime"
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
        or value.get("status") != "observed"
        or value.get("reason") is not None
        or value.get("regime") not in _CONTROL_MARKET_REGIMES
        or value.get("regime") != expected_regime
        or value.get("basis")
        != "coingecko_temporal_24h_btc_and_top_liquid_median_sign_v1"
        or not isinstance(observed_at, str)
        or observed_time is None
        or value.get("horizon_hours") != 24
        or value.get("return_unit") != "percent_points"
        or value.get("btc_canonical_asset_id") != "bitcoin"
        or not _bounded_observation_id(btc_observation_id)
        or btc_return is None
        or median_return is None
        or type(expected_count) is not int
        or expected_count <= 0
        or type(input_count) is not int
        or input_count != expected_count
        or type(universe_limit) is not int
        or universe_limit < expected_count
        or value.get("universe_policy") != "bounded_top_liquid_by_total_volume"
        or not isinstance(observation_ids, list)
        or len(observation_ids) != expected_count
        or not all(_bounded_observation_id(item) for item in observation_ids)
        or len(set(observation_ids)) != expected_count
        or btc_observation_id not in observation_ids
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or value.get("all_inputs_current_cycle") is not True
        or value.get("all_inputs_point_in_time_universe_members") is not True
        or value.get("all_inputs_temporal_return_evidence_ready") is not True
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
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return len(encoded) <= 8_192


def _bounded_observation_id(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 160


def _rejected_current_row(row: Mapping[str, Any], reason: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(row))
    result["market_history_status"] = "rejected"
    result["market_history"] = {
        "schema_id": MARKET_HISTORY_ENRICHMENT_SCHEMA,
        "schema_version": MARKET_HISTORY_SCHEMA_VERSION,
        "status": "rejected",
        "rejection_reason": reason,
        "warmup": {},
        "baseline_values": {},
        "research_only": True,
    }
    return result


def _historical_returns(
    observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> list[float]:
    return [sample.value for sample in _historical_return_samples(
        observations,
        hours=hours,
        cfg=cfg,
    )]


def _historical_return_samples(
    observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> list[_ReturnSample]:
    samples: list[_ReturnSample] = []
    ordered = sorted(observations, key=_observation_sort_key)
    for endpoint in ordered:
        sample = _return_sample_for_endpoint(endpoint, ordered, hours=hours, cfg=cfg)
        if sample is not None:
            samples.append(sample)
    return samples


def _historical_relative_returns(
    asset_observations: Sequence[Mapping[str, Any]],
    benchmark_observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> list[float]:
    return [sample.value for sample in _historical_relative_return_samples(
        asset_observations,
        benchmark_observations,
        hours=hours,
        cfg=cfg,
    )]


def _historical_relative_return_samples(
    asset_observations: Sequence[Mapping[str, Any]],
    benchmark_observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> list[_RelativeReturnSample]:
    samples: list[_RelativeReturnSample] = []
    asset_ordered = sorted(asset_observations, key=_observation_sort_key)
    benchmark_ordered = sorted(benchmark_observations, key=_observation_sort_key)
    for endpoint in asset_ordered:
        endpoint_time = _observation_time(endpoint)
        benchmark_endpoint = _aligned_observation(
            benchmark_ordered,
            endpoint_time,
            tolerance=cfg.benchmark_alignment_tolerance,
        )
        if benchmark_endpoint is None:
            continue
        asset_sample = _return_sample_for_endpoint(
            endpoint,
            asset_ordered,
            hours=hours,
            cfg=cfg,
        )
        benchmark_sample = _return_sample_for_endpoint(
            benchmark_endpoint,
            benchmark_ordered,
            hours=hours,
            cfg=cfg,
        )
        if asset_sample is not None and benchmark_sample is not None:
            samples.append(_RelativeReturnSample(
                value=_rounded(asset_sample.value - benchmark_sample.value),
                asset_endpoint=asset_sample.endpoint,
                asset_anchor=asset_sample.anchor,
                benchmark_endpoint=benchmark_sample.endpoint,
                benchmark_anchor=benchmark_sample.anchor,
            ))
    return samples


def _return_for_endpoint(
    endpoint: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> float | None:
    sample = _return_sample_for_endpoint(
        endpoint,
        observations,
        hours=hours,
        cfg=cfg,
    )
    return sample.value if sample is not None else None


def _return_sample_for_endpoint(
    endpoint: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> _ReturnSample | None:
    if endpoint is None:
        return None
    endpoint_time = _observation_time(endpoint)
    endpoint_price = _number(endpoint.get("price"))
    if endpoint_price is None or endpoint_price <= 0:
        return None
    target = endpoint_time - timedelta(hours=hours)
    tolerance = max(
        cfg.min_anchor_tolerance,
        timedelta(hours=hours * cfg.anchor_tolerance_ratio),
    )
    anchors = [
        item
        for item in observations
        if _observation_time(item) <= target
        and target - _observation_time(item) <= tolerance
        and _number(item.get("price")) is not None
    ]
    if not anchors:
        return None
    anchor = max(anchors, key=_observation_sort_key)
    anchor_price = _number(anchor.get("price"))
    if anchor_price is None or anchor_price <= 0:
        return None
    return _ReturnSample(
        value=_rounded((endpoint_price / anchor_price - 1.0) * 100.0),
        endpoint=endpoint,
        anchor=anchor,
    )


def _aligned_observation(
    observations: Sequence[Mapping[str, Any]],
    target: datetime,
    *,
    tolerance: timedelta,
) -> Mapping[str, Any] | None:
    """Return the latest causal observation within the backward tolerance."""

    candidates = [
        item
        for item in observations
        if _observation_time(item) <= target
        and target - _observation_time(item) <= tolerance
    ]
    if not candidates:
        return None
    return max(candidates, key=_observation_sort_key)


def _zscore(
    current: float | None,
    baseline: Sequence[float],
    *,
    minimum: int,
) -> tuple[float | None, dict[str, Any]]:
    sample = [value for value in baseline if math.isfinite(value)]
    mean = statistics.fmean(sample) if sample else None
    deviation = statistics.pstdev(sample) if len(sample) >= 2 else None
    status = _baseline_status(current, len(sample), minimum, allow_constant=False, deviation=deviation)
    value = None
    if status == "ready" and current is not None and mean is not None and deviation:
        value = _rounded((current - mean) / deviation)
    return value, {
        "status": status,
        "sample_count": len(sample),
        "required_sample_count": minimum,
        "mean": _rounded(mean),
        "standard_deviation": _rounded(deviation),
    }


def _baseline_status(
    current: float | None,
    sample_count: int,
    minimum: int,
    *,
    allow_constant: bool,
    deviation: float | None = None,
) -> str:
    if current is None:
        return "missing_current"
    if sample_count < minimum:
        return "warming"
    if not allow_constant and (deviation is None or deviation <= 1e-12):
        return "constant_baseline"
    return "ready"


def _canonical_field_accepts_temporal(
    row: Mapping[str, Any],
    field: str,
    *,
    basis_fields: Sequence[str],
) -> bool:
    if row.get(field) in (None, ""):
        return True
    basis_values = [
        value.strip().casefold()
        for name in basis_fields
        if isinstance((value := row.get(name)), str) and value.strip()
    ]
    evidence = row.get("market_feature_evidence")
    if isinstance(evidence, Mapping):
        details = evidence.get(field)
        if isinstance(details, Mapping):
            basis = details.get("basis")
            if isinstance(basis, str) and basis.strip():
                basis_values.append(basis.strip().casefold())
    return any(marker in basis for basis in basis_values for marker in _PROXY_BASIS_MARKERS)


def _preserve_proxy_value(row: dict[str, Any], field: str, basis_field: str) -> None:
    if row.get(field) not in (None, ""):
        row.setdefault(f"cross_sectional_{field}", row[field])
    if row.get(basis_field) not in (None, ""):
        row.setdefault(f"cross_sectional_{basis_field}", row[basis_field])


def _declare_return_unit(row: dict[str, Any], field: str) -> None:
    units = row.get("return_units")
    copied = copy.deepcopy(dict(units)) if isinstance(units, Mapping) else {}
    copied[field] = RETURN_UNIT_PERCENT_POINTS
    row["return_units"] = copied


def _copy_evidence(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): copy.deepcopy(item) for key, item in value.items()}


def _input_feature_basis(row: Mapping[str, Any], feature: str, *, default: str) -> str:
    feature_basis = row.get("feature_basis")
    if isinstance(feature_basis, Mapping):
        direct_basis = feature_basis.get(feature)
        if isinstance(direct_basis, str) and direct_basis.strip():
            return direct_basis.strip()
    evidence = row.get("market_feature_evidence")
    if isinstance(evidence, Mapping):
        details = evidence.get(feature)
        if isinstance(details, Mapping):
            evidence_basis = details.get("basis")
            if isinstance(evidence_basis, str) and evidence_basis.strip():
                return evidence_basis.strip()
    for key in (f"{feature}_basis", "turnover_basis" if feature == "turnover_24h" else ""):
        basis = row.get(key) if key else None
        if isinstance(basis, str) and basis.strip():
            return basis.strip()
    return default


def _group_observations(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        asset_id = _canonical_asset_id(row)
        if asset_id:
            grouped[asset_id].append(copy.deepcopy(dict(row)))
    for values in grouped.values():
        values.sort(key=_observation_sort_key)
    return dict(grouped)


def _find_benchmark_asset(
    history_by_asset: Mapping[str, Sequence[Mapping[str, Any]]],
    aliases: Sequence[str],
) -> str | None:
    available = set(history_by_asset)
    for alias in aliases:
        normalized = str(alias).strip().casefold()
        if normalized in available:
            return normalized
    for asset_id, observations in sorted(history_by_asset.items()):
        symbols = {str(item.get("symbol") or "").strip().casefold() for item in observations}
        coin_ids = {str(item.get("coin_id") or "").strip().casefold() for item in observations}
        if any(str(alias).strip().casefold() in symbols | coin_ids for alias in aliases):
            return asset_id
    return None


def _prepared_preference_key(item: _PreparedObservation) -> tuple[int, str]:
    return -_observation_quality(item.observation), _canonical_json(item.observation)


def _observation_quality(observation: Mapping[str, Any]) -> int:
    numeric = sum(
        observation.get(key) is not None
        for key in ("price", "volume_24h", "market_cap", "turnover_24h")
    )
    lineage = sum(observation.get(key) not in (None, "") for key in _LINEAGE_FIELDS)
    basis = observation.get("feature_basis")
    basis_count = len(basis) if isinstance(basis, Mapping) else 0
    context = sum(
        observation.get(key) not in (None, "")
        for key in _POINT_IN_TIME_CONTEXT_FIELDS
    )
    return int(numeric + lineage + basis_count + context)


def _feature_signature(observation: Mapping[str, Any]) -> str:
    values = {
        key: observation.get(key)
        for key in (
            "price",
            "volume_24h",
            "market_cap",
            "turnover_24h",
            "feature_basis",
            "provider",
            "source",
            "market_data_source",
            "data_mode",
            *_POINT_IN_TIME_CONTEXT_FIELDS,
        )
    }
    return _canonical_json(values)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _observation_sort_key(observation: Mapping[str, Any]) -> tuple[datetime, str]:
    return _observation_time(observation), str(observation.get("observation_id") or "")


def _observation_time(observation: Mapping[str, Any]) -> datetime:
    parsed, error = _parse_aware_time(observation.get("observed_at"))
    if parsed is None:
        raise ValueError(f"retained observation has invalid timestamp: {error}")
    return parsed


def _observation_id(asset_id: str, timestamp: str) -> str:
    digest = hashlib.sha256(f"{MARKET_HISTORY_OBSERVATION_SCHEMA}|{asset_id}|{timestamp}".encode()).hexdigest()
    return f"mhobs-{digest[:24]}"


def _canonical_asset_id(row: Mapping[str, Any]) -> str:
    return _canonical_asset_identity(row)[0]


def _canonical_asset_identity(row: Mapping[str, Any]) -> tuple[str, str]:
    raw = row.get("canonical_asset_id")
    if raw is None or raw == "":
        return "", "missing_canonical_asset_id"
    text = _identity_text(raw, max_length=160)
    if not text:
        return "", "invalid_canonical_asset_id"
    return text.casefold(), ""


def _identity_text(value: object, *, max_length: int) -> str:
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
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None or value == "":
            continue
        return _identity_text(value, max_length=max_length)
    return ""


def _first_number(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return _number(row.get(key))
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rounded(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    rounded = round(float(value), 8)
    return 0.0 if rounded == 0 else rounded


def _parse_aware_time(value: object) -> tuple[datetime | None, str]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None, "invalid_timestamp"
    else:
        return None, "missing_timestamp"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, "naive_timestamp"
    return parsed.astimezone(timezone.utc), ""


def _require_aware_utc(value: datetime | str, *, field_name: str) -> datetime:
    parsed, error = _parse_aware_time(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be an aware UTC timestamp: {error}")
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
