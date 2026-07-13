"""Pure rolling market history and temporal baseline calculations.
Callers own persistence and provide prior observations plus normalized current rows;
derived returns use percentage points.
Provider fields and bases are preserved, and only fields explicitly marked as proxy are replaced.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence


MARKET_HISTORY_OBSERVATION_SCHEMA = "event_alpha.market_history_observation"
MARKET_HISTORY_ENRICHMENT_SCHEMA = "event_alpha.market_history_enrichment"
MARKET_HISTORY_SUMMARY_SCHEMA = "event_alpha.market_history_summary"
MARKET_HISTORY_SCHEMA_VERSION = 1
TEMPORAL_BASELINE_BASIS = "temporal_baseline"
RETURN_UNIT_PERCENT_POINTS = "percent_points"

_LINEAGE_FIELDS = (
    "provider", "source", "market_data_source", "data_mode", "provider_source_artifact",
    "data_acquisition_mode", "candidate_source_mode", "provider_generation_id",
    "provider_source_artifact_sha256", "request_ledger_path", "request_ledger_sha256",
    "provenance_contract_valid", "burn_in_eligible", "burn_in_counted",
    "contract_counted_status", "no_send_status", "research_only",
)
_PROXY_BASIS_MARKERS = ("proxy", "cross_sectional", "24h_volume")


@dataclass(frozen=True)
class MarketHistoryConfig:
    """Deterministic retention and warm-up policy for market observations."""

    max_history_age: timedelta = timedelta(days=45)
    max_current_age: timedelta = timedelta(hours=6)
    future_tolerance: timedelta = timedelta(minutes=5)
    max_observations_per_asset: int = 256
    min_baseline_observations: int = 8
    return_horizons_hours: tuple[int, ...] = (1, 4, 24)
    anchor_tolerance_ratio: float = 0.25
    min_anchor_tolerance: timedelta = timedelta(minutes=5)
    benchmark_alignment_tolerance: timedelta = timedelta(minutes=5)
    btc_asset_ids: tuple[str, ...] = ("bitcoin", "btc")
    eth_asset_ids: tuple[str, ...] = ("ethereum", "eth")
    rejection_example_limit: int = 25

    def __post_init__(self) -> None:
        checks = (
            (self.max_history_age > timedelta(0), "max_history_age must be positive"),
            (self.max_current_age > timedelta(0), "max_current_age must be positive"),
            (self.future_tolerance >= timedelta(0), "future_tolerance cannot be negative"),
            (self.max_observations_per_asset >= 2, "max_observations_per_asset must be at least 2"),
            (self.min_baseline_observations >= 2, "min_baseline_observations must be at least 2"),
            (self.return_horizons_hours and all(value > 0 for value in self.return_horizons_hours),
             "return_horizons_hours must contain positive values"),
            (len(set(self.return_horizons_hours)) == len(self.return_horizons_hours),
             "return_horizons_hours must be unique"),
            (self.anchor_tolerance_ratio >= 0, "anchor_tolerance_ratio cannot be negative"),
            (self.min_anchor_tolerance >= timedelta(0), "min_anchor_tolerance cannot be negative"),
            (self.benchmark_alignment_tolerance >= timedelta(0),
             "benchmark_alignment_tolerance cannot be negative"),
            (self.rejection_example_limit >= 0, "rejection_example_limit cannot be negative"),
        )
        for valid, message in checks:
            if not valid:
                raise ValueError(message)
        if self.max_observations_per_asset <= self.min_baseline_observations:
            raise ValueError("max_observations_per_asset must leave room after min_baseline_observations")


@dataclass(frozen=True)
class _MarketHistoryResult:
    enriched_rows: tuple[dict[str, Any], ...]
    retained_history: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enriched_rows": copy.deepcopy(list(self.enriched_rows)),
            "retained_history": copy.deepcopy(list(self.retained_history)),
            "summary": copy.deepcopy(self.summary),
        }


@dataclass(frozen=True)
class _PreparedObservation:
    index: int
    observation: dict[str, Any]
    asset_id: str
    observed_at: datetime
    @property
    def key(self) -> tuple[str, datetime]:
        return self.asset_id, self.observed_at


@dataclass
class _Telemetry:
    counts: Counter[str] = field(default_factory=Counter)
    role_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    examples: list[dict[str, Any]] = field(default_factory=list)
    example_limit: int = 25
    def record(
        self,
        reason: str,
        *,
        role: str,
        index: int,
        asset_id: str = "",
        observed_at: datetime | None = None,
    ) -> None:
        self.counts[reason] += 1
        self.role_counts[(role, reason)] += 1
        if len(self.examples) >= self.example_limit:
            return
        item: dict[str, Any] = {
            "reason": reason,
            "role": role,
            "input_index": index,
        }
        if asset_id:
            item["canonical_asset_id"] = asset_id
        if observed_at is not None:
            item["observed_at"] = _iso(observed_at)
        self.examples.append(item)


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
    history_by_asset = _group_observations(canonical_history)
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
    combined_by_asset: dict[str, list[dict[str, Any]]] = {
        asset: [copy.deepcopy(item) for item in observations]
        for asset, observations in history_by_asset.items()
    }
    for prepared in accepted_current.values():
        observations = combined_by_asset.setdefault(prepared.asset_id, [])
        if not any(_observation_time(item) == prepared.observed_at for item in observations):
            observations.append(copy.deepcopy(prepared.observation))
    pruned_by_limit = 0
    for asset_id, observations in combined_by_asset.items():
        observations.sort(key=_observation_sort_key)
        if len(observations) > cfg.max_observations_per_asset:
            pruned_by_limit += len(observations) - cfg.max_observations_per_asset
            combined_by_asset[asset_id] = observations[-cfg.max_observations_per_asset :]
    enriched: list[dict[str, Any]] = []
    warmup_status_counts: Counter[str] = Counter()
    warmup_feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
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
            history_by_asset=combined_by_asset,
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
    summary = {
        "schema_id": MARKET_HISTORY_SUMMARY_SCHEMA,
        "schema_version": MARKET_HISTORY_SCHEMA_VERSION,
        "evaluated_at": _iso(evaluated_at),
        "config": _config_values(cfg),
        "input_counts": {
            "current_rows": len(current),
            "existing_history_rows": len(historical),
        },
        "accepted_counts": {
            "current_observations": len(accepted_current),
            "historical_observations": len(canonical_history),
        },
        "rejection_counts": dict(sorted(telemetry.counts.items())),
        "rejection_examples": sorted(
            telemetry.examples,
            key=lambda item: (
                str(item.get("role") or ""),
                int(item.get("input_index") or 0),
                str(item.get("reason") or ""),
            ),
        ),
        "retention": {
            "retained_observations": len(retained),
            "retained_assets": len(combined_by_asset),
            "pruned_by_age": int(telemetry.role_counts.get(("history", "stale"), 0)),
            "pruned_by_limit": pruned_by_limit,
            "oldest_observed_at": min((item["observed_at"] for item in retained), default=None),
            "newest_observed_at": max((item["observed_at"] for item in retained), default=None),
        },
        "warmup": {
            "row_status_counts": dict(sorted(warmup_status_counts.items())),
            "feature_status_counts": {
                feature: dict(sorted(counts.items()))
                for feature, counts in sorted(warmup_feature_counts.items())
            },
        },
        "feature_basis_counts": dict(sorted(feature_basis_counts.items())),
        "research_only": True,
    }
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
    asset_id = _canonical_asset_id(row)
    if not asset_id:
        return None, "missing_canonical_asset_id"
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
        baseline = [_number(item.get(source_field)) for item in prior]
        baseline = [value for value in baseline if value is not None]
        value, stats = _zscore(
            _number(current.observation.get(source_field)),
            baseline,
            minimum=cfg.min_baseline_observations,
        )
        _record_baseline_feature(
            row, evidence, warmup, baseline_values,
            feature=feature, temporal_field=temporal_field, value=value, stats=stats,
            current=current, prior=prior,
        )
        if value is not None and _canonical_field_accepts_temporal(
            row, feature, basis_fields=basis_fields,
        ):
            _preserve_proxy_value(row, feature, basis_field)
            row[feature] = value
            row[basis_field] = TEMPORAL_BASELINE_BASIS
    current_returns: dict[int, float | None] = {}
    for hours in sorted(cfg.return_horizons_hours):
        current_return = _return_for_endpoint(current.observation, observations, hours=hours, cfg=cfg)
        historical_returns = _historical_returns(prior, hours=hours, cfg=cfg)
        current_returns[hours] = current_return
        return_z, return_stats = _zscore(
            current_return,
            historical_returns,
            minimum=cfg.min_baseline_observations,
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
                prior=prior,
                sample_count=1,
                status="ready",
                calculation="price_horizon_return",
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
            prior=prior,
        )
        volatility = _rounded(statistics.pstdev(historical_returns)) if len(historical_returns) >= 2 else None
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
            "mean": _rounded(statistics.fmean(historical_returns)) if historical_returns else None,
            "standard_deviation": volatility,
        }
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
            prior=prior,
        )
        if volatility is not None and volatility_status == "ready":
            _declare_return_unit(row, f"temporal_return_volatility_{hours}h")
        absolute_returns = [abs(value) for value in historical_returns]
        volatility_z, volatility_z_stats = _zscore(
            abs(current_return) if current_return is not None else None,
            absolute_returns,
            minimum=cfg.min_baseline_observations,
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
            prior=prior,
        )
    _enrich_relative_baselines(
        row, evidence, warmup, baseline_values, current, prior, current_returns,
        history_by_asset=history_by_asset, cfg=cfg,
    )
    return _finish_current_enrichment(
        row, current, observations, prior, warmup, baseline_values, evidence,
    )


def _enrich_relative_baselines(
    row: dict[str, Any],
    evidence: dict[str, Any],
    warmup: dict[str, dict[str, Any]],
    baseline_values: dict[str, Any],
    current: _PreparedObservation,
    prior: Sequence[Mapping[str, Any]],
    current_returns: Mapping[int, float | None],
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
                    current=current, prior=prior, benchmark_asset_id=asset_id,
                )
            continue
        endpoint = _aligned_observation(
            observations, current.observed_at, tolerance=cfg.benchmark_alignment_tolerance,
        )
        for hours in sorted(cfg.return_horizons_hours):
            feature = f"relative_return_vs_{name}_{hours}h"
            benchmark_return = (
                _return_for_endpoint(endpoint, observations, hours=hours, cfg=cfg)
                if endpoint is not None else None
            )
            asset_return = current_returns.get(hours)
            relative = (
                _rounded(asset_return - benchmark_return)
                if asset_return is not None and benchmark_return is not None else None
            )
            history = _historical_relative_returns(prior, observations, hours=hours, cfg=cfg)
            relative_z, stats = _zscore(
                relative, history, minimum=cfg.min_baseline_observations,
            )
            if relative is not None:
                temporal_field = f"temporal_{feature}"
                row[temporal_field] = relative
                _declare_return_unit(row, temporal_field)
                if row.get(feature) in (None, ""):
                    row[feature] = relative
                    _declare_return_unit(row, feature)
                evidence[temporal_field] = _feature_evidence(
                    current=current, prior=prior, sample_count=1, status="ready",
                    calculation=f"asset_return_minus_{name}_return", benchmark_asset_id=asset_id,
                )
            _record_baseline_feature(
                row, evidence, warmup, baseline_values,
                feature=f"{feature}_zscore", temporal_field=f"temporal_{feature}_zscore",
                value=relative_z, stats=stats, current=current, prior=prior,
                benchmark_asset_id=asset_id,
            )


def _finish_current_enrichment(
    row: dict[str, Any],
    current: _PreparedObservation,
    observations: Sequence[Mapping[str, Any]],
    prior: Sequence[Mapping[str, Any]],
    warmup: Mapping[str, Mapping[str, Any]],
    baseline_values: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    statuses = [str(item.get("status") or "unknown") for item in warmup.values()]
    required_statuses = [status for status in statuses if status != "not_applicable"]
    warm_count = sum(status in {"ready", "constant_baseline"} for status in required_statuses)
    if required_statuses and warm_count == len(required_statuses):
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
        "baseline_values": baseline_values,
        "return_unit": RETURN_UNIT_PERCENT_POINTS,
        "research_only": True,
    }
    row["market_history_status"] = overall_status
    row["market_history_observation_id"] = current.observation["observation_id"]
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
    prior: Sequence[Mapping[str, Any]],
    benchmark_asset_id: str | None = None,
) -> None:
    status = str(stats.get("status") or "unknown")
    warmup[feature] = {
        "status": status,
        "sample_count": int(stats.get("sample_count") or 0),
        "required_sample_count": int(stats.get("required_sample_count") or 0),
        "basis": TEMPORAL_BASELINE_BASIS,
    }
    baseline_values[feature] = {
        "value": value,
        "mean": stats.get("mean"),
        "standard_deviation": stats.get("standard_deviation"),
        "sample_count": int(stats.get("sample_count") or 0),
        "status": status,
        "basis": TEMPORAL_BASELINE_BASIS,
    }
    if value is not None:
        row[temporal_field] = value
    evidence[temporal_field] = _feature_evidence(
        current=current,
        prior=prior,
        sample_count=int(stats.get("sample_count") or 0),
        status=status,
        calculation=feature,
        benchmark_asset_id=benchmark_asset_id,
    )


def _feature_evidence(
    *,
    current: _PreparedObservation,
    prior: Sequence[Mapping[str, Any]],
    sample_count: int,
    status: str,
    calculation: str,
    benchmark_asset_id: str | None = None,
) -> dict[str, Any]:
    relevant = list(prior[-sample_count:]) if sample_count > 0 else []
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
        "providers": providers,
        "data_modes": modes,
        "research_only": True,
    }
    if benchmark_asset_id:
        evidence["benchmark_asset_id"] = benchmark_asset_id
    return evidence


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
    turnover = _first_number(row, "turnover_24h", "volume_to_market_cap", "volume_mcap")
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
        "coin_id": str(row.get("coin_id") or row.get("id") or "").strip() or None,
        "symbol": str(row.get("symbol") or row.get("ticker") or "").strip().upper() or None,
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
                default="derived_provider_ratio" if turnover is not None else "unavailable",
            ),
        },
        "research_only": True,
    }
    for key in _LINEAGE_FIELDS:
        if row.get(key) not in (None, ""):
            observation[key] = copy.deepcopy(row[key])
    return {key: value for key, value in observation.items() if value is not None}


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
    values: list[float] = []
    ordered = sorted(observations, key=_observation_sort_key)
    for endpoint in ordered:
        value = _return_for_endpoint(endpoint, ordered, hours=hours, cfg=cfg)
        if value is not None:
            values.append(value)
    return values


def _historical_relative_returns(
    asset_observations: Sequence[Mapping[str, Any]],
    benchmark_observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> list[float]:
    values: list[float] = []
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
        asset_return = _return_for_endpoint(endpoint, asset_ordered, hours=hours, cfg=cfg)
        benchmark_return = _return_for_endpoint(
            benchmark_endpoint,
            benchmark_ordered,
            hours=hours,
            cfg=cfg,
        )
        if asset_return is not None and benchmark_return is not None:
            values.append(_rounded(asset_return - benchmark_return))
    return values


def _return_for_endpoint(
    endpoint: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    *,
    hours: int,
    cfg: MarketHistoryConfig,
) -> float | None:
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
    return _rounded((endpoint_price / anchor_price - 1.0) * 100.0)


def _aligned_observation(
    observations: Sequence[Mapping[str, Any]],
    target: datetime,
    *,
    tolerance: timedelta,
) -> Mapping[str, Any] | None:
    candidates = [
        item
        for item in observations
        if abs(_observation_time(item) - target) <= tolerance
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            abs((_observation_time(item) - target).total_seconds()),
            _observation_time(item),
            str(item.get("observation_id") or ""),
        ),
    )


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
    basis_values = [str(row.get(name) or "").casefold() for name in basis_fields]
    evidence = row.get("market_feature_evidence")
    if isinstance(evidence, Mapping):
        details = evidence.get(field)
        if isinstance(details, Mapping):
            basis_values.append(str(details.get("basis") or "").casefold())
        elif details:
            basis_values.append(str(details).casefold())
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
    if isinstance(feature_basis, Mapping) and feature_basis.get(feature) not in (None, ""):
        return str(feature_basis[feature])
    evidence = row.get("market_feature_evidence")
    if isinstance(evidence, Mapping):
        details = evidence.get(feature)
        if isinstance(details, Mapping) and details.get("basis"):
            return str(details["basis"])
        if isinstance(details, str) and details.strip():
            return details.strip()
    for key in (f"{feature}_basis", "turnover_basis" if feature == "turnover_24h" else ""):
        if key and row.get(key) not in (None, ""):
            return str(row[key])
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
    return int(numeric + lineage + basis_count)


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
    return str(row.get("canonical_asset_id") or "").strip().casefold()


def _first_number(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            value = _number(row.get(key))
            if value is not None:
                return value
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


def _config_values(cfg: MarketHistoryConfig) -> dict[str, Any]:
    return {
        "max_history_age_seconds": int(cfg.max_history_age.total_seconds()),
        "max_current_age_seconds": int(cfg.max_current_age.total_seconds()),
        "future_tolerance_seconds": int(cfg.future_tolerance.total_seconds()),
        "max_observations_per_asset": cfg.max_observations_per_asset,
        "min_baseline_observations": cfg.min_baseline_observations,
        "return_horizons_hours": list(sorted(cfg.return_horizons_hours)),
        "anchor_tolerance_ratio": cfg.anchor_tolerance_ratio,
        "min_anchor_tolerance_seconds": int(cfg.min_anchor_tolerance.total_seconds()),
        "benchmark_alignment_tolerance_seconds": int(cfg.benchmark_alignment_tolerance.total_seconds()),
        "btc_asset_ids": list(cfg.btc_asset_ids),
        "eth_asset_ids": list(cfg.eth_asset_ids),
    }
