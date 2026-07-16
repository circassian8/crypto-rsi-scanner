"""Closed Decision Radar cohort, horizon, timing, and expiry summaries.

The helper consumes already-materialized empirical episode representatives and
outcomes.  It is deliberately pure: there is no filesystem, environment,
provider, publication, notification, or policy mutation path.  Return values
remain decimal fractions, while timing values are explicitly measured in
hours.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from ..artifacts.schema.decision_model import (
    ALLOWED_CATALYST_STATUSES,
    ALLOWED_DIRECTIONAL_BIASES,
    ALLOWED_MARKET_PHASES,
    ALLOWED_PREFERRED_HORIZONS,
    ALLOWED_SPREAD_STATUSES,
    ALLOWED_TIMING_STATES,
    ALLOWED_TRADABILITY_STATUSES,
)
from .empirical_replay_statistics import (
    _bootstrap_mean_ci,
    _mean,
    _robust_summary,
)


SCHEMA_ID = "decision_radar.empirical_replay_dimension_analysis"
SCHEMA_VERSION = 1
METHOD = "closed_episode_cohorts_and_path_timing_sensitivity"

CONTRIBUTING_ORIGINS = (
    "market_led",
    "catalyst_led",
    "technical_led",
    "derivatives_led",
    "onchain_led",
    "fundamental_led",
    "macro_led",
)
CONTRIBUTING_ORIGIN_COHORTS = (*CONTRIBUTING_ORIGINS, "unknown")
DIRECTIONAL_BIASES = (*ALLOWED_DIRECTIONAL_BIASES, "unknown")
CATALYST_STATUSES = tuple(dict.fromkeys((*ALLOWED_CATALYST_STATUSES, "unknown")))
MARKET_PHASES = (*ALLOWED_MARKET_PHASES, "unknown")
TIMING_STATES = (*ALLOWED_TIMING_STATES, "unknown")
PREFERRED_HORIZONS = (*ALLOWED_PREFERRED_HORIZONS, "unknown")
TRADABILITY_STATUSES = (*ALLOWED_TRADABILITY_STATUSES, "unknown")
SPREAD_STATUSES = (*ALLOWED_SPREAD_STATUSES, "unknown")
BASELINE_MATURITIES = (
    "warm",
    "warming",
    "cold",
    "partial_bar",
    "complete",
    "insufficient_history",
    "unavailable",
    "stale",
    "not_evaluated",
    "missing",
    "unknown",
)
ASSET_TIERS = (
    "top_1_3",
    "rank_4_30",
    "rank_31_100",
    "outside_top_100",
    "unknown",
)
HORIZONS = ("1d", "3d", "7d", "14d")
OUTCOME_CLASSIFICATIONS = (
    "continuation",
    "reversal",
    "breakout_failure",
    "fade_success",
    "risk_event_validation",
)
EXPIRY_STATUSES = (
    "not_configured",
    "invalid_expiry",
    "not_expired",
    "missing_data",
    "expired_without_resolution",
    "expired_with_directional_resolution",
    "unknown",
)
POST_EXPIRY_STATUSES = ("not_observed", "continuation", "reversal", "flat", "unknown")
TIMING_METRICS = (
    "time_to_mfe_hours",
    "time_to_mae_hours",
    "time_to_invalidation_hours",
    "time_to_expiry_observation_hours",
)

_DIRECTION_SIGN = {"long": 1.0, "fade_short_review": -1.0, "risk": -1.0}
_FRACTION_UNITS = {"fraction", "decimal_fraction", "fraction_by_protocol"}
_PERCENT_POINT_UNITS = {"percent_points", "percentage_points", "pct_points"}


@dataclass(frozen=True)
class _Episode:
    episode_id: str
    representative: Mapping[str, Any]
    outcome: Mapping[str, Any]


def build_empirical_dimension_analysis(
    episodes: Iterable[Mapping[str, Any]],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    """Return closed empirical dimensions without changing production state."""

    rows = _episodes(episodes)
    cohorts = {
        "contributing_origin_cohorts": _multi_membership_cohorts(
            rows,
            cohort_type="contributing_thesis_origin",
            values=CONTRIBUTING_ORIGIN_COHORTS,
            getter=_contributing_origins,
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "directional_bias_cohorts": _closed_cohorts(
            rows, "directional_bias", DIRECTIONAL_BIASES, _field("directional_bias"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "catalyst_status_cohorts": _closed_cohorts(
            rows, "catalyst_status", CATALYST_STATUSES, _field("catalyst_status"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "market_phase_cohorts": _closed_cohorts(
            rows, "market_phase", MARKET_PHASES, _field("market_phase"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "timing_state_cohorts": _closed_cohorts(
            rows, "timing_state", TIMING_STATES, _field("timing_state"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "preferred_horizon_cohorts": _closed_cohorts(
            rows, "preferred_horizon", PREFERRED_HORIZONS, _field("preferred_horizon"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "tradability_status_cohorts": _closed_cohorts(
            rows, "tradability_status", TRADABILITY_STATUSES, _field("tradability_status"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "spread_status_cohorts": _closed_cohorts(
            rows, "spread_status", SPREAD_STATUSES, _field("spread_status"),
            partition, evidence_mode, bootstrap_resamples,
        ),
        "baseline_maturity_cohorts": _closed_cohorts(
            rows, "baseline_maturity", BASELINE_MATURITIES, _baseline_maturity,
            partition, evidence_mode, bootstrap_resamples,
        ),
        "asset_tier_cohorts": _closed_cohorts(
            rows, "point_in_time_asset_tier", ASSET_TIERS, _asset_tier,
            partition, evidence_mode, bootstrap_resamples,
        ),
    }
    provider_rows, provider_definitions = _provider_source_cohorts(
        rows,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
    )
    cohorts["provider_source_combination_cohorts"] = provider_rows
    value: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": len(rows),
        "cohorts": cohorts,
        "provider_source_combination_definitions": provider_definitions,
        "horizon_sensitivity": [
            _horizon_row(
                rows,
                horizon=horizon,
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for horizon in HORIZONS
        ],
        "timing_metrics": [
            _timing_row(
                rows,
                metric=metric,
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for metric in TIMING_METRICS
        ],
        "outcome_classification_summary": [
            _classification_row(
                rows,
                classification=name,
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for name in OUTCOME_CLASSIFICATIONS
        ],
        "expiry_status_cohorts": _closed_cohorts(
            rows, "expiry_status", EXPIRY_STATUSES, _expiry_status,
            partition, evidence_mode, bootstrap_resamples,
        ),
        "post_expiry_status_cohorts": [
            _post_expiry_row(
                status,
                [row for row in rows if _post_expiry_status(row) == status],
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
            )
            for status in POST_EXPIRY_STATUSES
        ],
        "return_unit": "fraction",
        "timing_unit": "hours",
        "episode_membership_counted_once_per_cohort": True,
        "contributing_origin_membership_is_multi_valued": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }
    return value


def _episodes(values: Iterable[Mapping[str, Any]]) -> list[_Episode]:
    result: list[_Episode] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, Mapping):
            raise ValueError("dimension_episode_not_mapping")
        episode_id = _text(raw.get("episode_id"))
        representative = raw.get("representative")
        outcome = raw.get("outcome")
        if not episode_id:
            raise ValueError("dimension_episode_id_required")
        if episode_id in seen:
            raise ValueError("duplicate_dimension_episode_id")
        if not isinstance(representative, Mapping) or not isinstance(outcome, Mapping):
            raise ValueError("dimension_episode_values_required")
        seen.add(episode_id)
        result.append(_Episode(episode_id, _flatten(representative), dict(outcome)))
    return sorted(result, key=lambda row: row.episode_id)


def _closed_cohorts(
    rows: Sequence[_Episode],
    cohort_type: str,
    values: Sequence[str],
    getter: Any,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> list[dict[str, Any]]:
    known = set(values)
    grouped: dict[str, list[_Episode]] = {value: [] for value in values}
    for row in rows:
        value = _text(getter(row))
        grouped[value if value in known else "unknown"].append(row)
    return [
        _cohort_row(
            cohort_type,
            value,
            grouped[value],
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        )
        for value in values
    ]


def _multi_membership_cohorts(
    rows: Sequence[_Episode],
    *,
    cohort_type: str,
    values: Sequence[str],
    getter: Any,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[_Episode]] = {value: [] for value in values}
    known = set(values) - {"unknown"}
    for row in rows:
        memberships = sorted(set(getter(row)) & known)
        if not memberships and "unknown" in grouped:
            memberships = ["unknown"]
        for value in memberships:
            grouped[value].append(row)
    result = []
    for value in values:
        cohort = _cohort_row(
            cohort_type,
            value,
            grouped[value],
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        )
        cohort["membership_is_multi_valued"] = True
        result.append(cohort)
    return result


def _provider_source_cohorts(
    rows: Sequence[_Episode],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[_Episode]] = defaultdict(list)
    definitions: dict[str, dict[str, Any]] = {}
    for row in rows:
        definition = _provider_source_definition(row)
        cohort = definition["cohort"]
        grouped[cohort].append(row)
        definitions[cohort] = definition
    grouped.setdefault("providers=unknown|sources=unknown", [])
    definitions.setdefault(
        "providers=unknown|sources=unknown",
        {
            "cohort": "providers=unknown|sources=unknown",
            "providers": [],
            "sources": [],
            "source_packs": [],
            "status": "unknown",
        },
    )
    result = [
        _cohort_row(
            "provider_source_combination",
            cohort,
            grouped[cohort],
            partition=partition,
            evidence_mode=evidence_mode,
            bootstrap_resamples=bootstrap_resamples,
        )
        for cohort in sorted(grouped)
    ]
    return result, [definitions[key] for key in sorted(definitions)]


def _cohort_row(
    cohort_type: str,
    cohort: str,
    rows: Sequence[_Episode],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    directional = [value for row in rows if (value := _primary_directional(row)) is not None]
    raw = [value for row in rows if (value := _primary_raw(row)) is not None]
    mfe = [value for row in rows if (value := _primary_mfe(row)) is not None]
    mae = [value for row in rows if (value := _primary_mae(row)) is not None]
    summary = _robust_summary(directional)
    sample_status, evidence_strength = _sample_evidence(len(directional))
    return {
        "cohort_type": cohort_type,
        "cohort": cohort,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": len(rows),
        "matured_episode_count": sum(_primary_matured(row) for row in rows),
        "sample_size": len(directional),
        "sample_status": sample_status,
        "evidence_strength": evidence_strength,
        "result_direction": _result_direction(summary["mean"]),
        "raw_return_sample_size": len(raw),
        "mean_raw_primary_return_fraction": _mean(raw),
        "mean_directional_return_fraction": summary["mean"],
        "median_directional_return_fraction": summary["median"],
        "trimmed_mean_10pct_directional_return_fraction": summary["trimmed_mean_10pct"],
        "hit_rate": sum(value > 0.0 for value in directional) / len(directional) if directional else None,
        "downside_5pct_fraction": summary["downside_5pct"],
        "worst_directional_return_fraction": min(directional) if directional else None,
        "mfe_sample_size": len(mfe),
        "mean_mfe_fraction": _mean(mfe),
        "mae_sample_size": len(mae),
        "mean_mae_fraction": _mean(mae),
        "mfe_to_mae_ratio_of_means": (
            _mean(mfe) / _mean(mae)
            if _mean(mfe) is not None and _mean(mae) not in (None, 0.0)
            else None
        ),
        "uncertainty": _bootstrap_mean_ci(
            directional,
            resamples=bootstrap_resamples,
            label=f"{partition}\0{evidence_mode}\0dimension\0{cohort_type}\0{cohort}",
        ),
        "return_basis": "direction_aligned_primary_horizon_return",
        "return_unit": "fraction",
        "multiple_comparison_adjusted": False,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _horizon_row(
    rows: Sequence[_Episode],
    *,
    horizon: str,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    horizon_rows = [(row, _horizon(row, horizon)) for row in rows]
    matured = [(row, value) for row, value in horizon_rows if _horizon_matured(value)]
    directional = [value for row, item in matured if (value := _horizon_directional(row, item)) is not None]
    raw = [value for _row, item in matured if (value := _fraction_field(item, "raw_return_fraction")) is not None]
    relative_btc = [value for row, item in matured if (value := _relative_directional(row, item, "BTC")) is not None]
    relative_eth = [value for row, item in matured if (value := _relative_directional(row, item, "ETH")) is not None]
    mfe = [value for _row, item in matured if (value := _horizon_mfe(item)) is not None]
    mae = [value for _row, item in matured if (value := _horizon_mae(item)) is not None]
    summary = _robust_summary(directional)
    sample_status, evidence_strength = _sample_evidence(len(directional))
    classes = [_horizon_classifications(row, item) for row, item in matured]
    maturity_counts: dict[str, int] = defaultdict(int)
    for _row, item in horizon_rows:
        maturity_counts[_text(item.get("maturity_status")) or "unknown"] += 1
    return {
        "horizon": horizon,
        "horizon_days": int(horizon[:-1]),
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": len(rows),
        "maturity_status_counts": dict(sorted(maturity_counts.items())),
        "matured_episode_count": len(matured),
        "sample_size": len(directional),
        "sample_status": sample_status,
        "evidence_strength": evidence_strength,
        "result_direction": _result_direction(summary["mean"]),
        "mean_raw_return_fraction": _mean(raw),
        "mean_directional_return_fraction": summary["mean"],
        "median_directional_return_fraction": summary["median"],
        "trimmed_mean_10pct_directional_return_fraction": summary["trimmed_mean_10pct"],
        "hit_rate": sum(value > 0.0 for value in directional) / len(directional) if directional else None,
        "downside_5pct_fraction": summary["downside_5pct"],
        "mean_directional_relative_return_vs_btc_fraction": _mean(relative_btc),
        "mean_directional_relative_return_vs_eth_fraction": _mean(relative_eth),
        "mean_mfe_fraction": _mean(mfe),
        "mean_mae_fraction": _mean(mae),
        "time_to_mfe": _horizon_timing_summary(
            matured, "time_to_mfe_hours", partition, evidence_mode, horizon, bootstrap_resamples
        ),
        "time_to_mae": _horizon_timing_summary(
            matured, "time_to_mae_hours", partition, evidence_mode, horizon, bootstrap_resamples
        ),
        "time_to_invalidation": _horizon_timing_summary(
            matured, "time_to_invalidation_hours", partition, evidence_mode, horizon, bootstrap_resamples
        ),
        "classification_counts": {
            name: sum(item.get(name) is True for item in classes)
            for name in OUTCOME_CLASSIFICATIONS
        },
        "classification_eligible_counts": {
            name: sum(item.get(name) is not None for item in classes)
            for name in OUTCOME_CLASSIFICATIONS
        },
        "classification_summary": [
            _classification_values_row(
                [item[name] for item in classes if isinstance(item.get(name), bool)],
                classification=name,
                episode_count=len(rows),
                partition=partition,
                evidence_mode=evidence_mode,
                bootstrap_resamples=bootstrap_resamples,
                label=f"horizon\0{horizon}\0{name}",
                horizon=horizon,
            )
            for name in OUTCOME_CLASSIFICATIONS
        ],
        "uncertainty": _bootstrap_mean_ci(
            directional,
            resamples=bootstrap_resamples,
            label=f"{partition}\0{evidence_mode}\0horizon\0{horizon}",
        ),
        "return_unit": "fraction",
        "timing_unit": "hours",
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _timing_row(
    rows: Sequence[_Episode],
    *,
    metric: str,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    values: list[float] = []
    complete_without_value = 0
    missing = 0
    for row in rows:
        if metric == "time_to_expiry_observation_hours":
            expiry = _expiry(row)
            value = _nonnegative(expiry.get(metric))
            complete = _expiry_status(row) in {
                "expired_without_resolution", "expired_with_directional_resolution"
            }
        else:
            primary = _primary_horizon(row)
            value = _nonnegative(
                row.outcome.get(metric)
                if row.outcome.get(metric) is not None
                else primary.get(metric)
            )
            complete = _text(primary.get("path_status")) == "complete"
        if value is not None:
            values.append(value)
        elif complete:
            complete_without_value += 1
        else:
            missing += 1
    return _timing_summary(
        metric,
        values,
        episode_count=len(rows),
        complete_without_value=complete_without_value,
        missing=missing,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
        label=f"timing\0{metric}",
    )


def _horizon_timing_summary(
    rows: Sequence[tuple[_Episode, Mapping[str, Any]]],
    metric: str,
    partition: str,
    evidence_mode: str,
    horizon: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    values = [value for _row, item in rows if (value := _nonnegative(item.get(metric))) is not None]
    complete_without_value = sum(
        _text(item.get("path_status")) == "complete" and _nonnegative(item.get(metric)) is None
        for _row, item in rows
    )
    missing = len(rows) - len(values) - complete_without_value
    return _timing_summary(
        metric,
        values,
        episode_count=len(rows),
        complete_without_value=complete_without_value,
        missing=missing,
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
        label=f"horizon\0{horizon}\0{metric}",
    )


def _timing_summary(
    metric: str,
    values: Sequence[float],
    *,
    episode_count: int,
    complete_without_value: int,
    missing: int,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
    label: str,
) -> dict[str, Any]:
    sample_status, evidence_strength = _sample_evidence(len(values))
    return {
        "metric": metric,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": episode_count,
        "sample_size": len(values),
        "sample_status": sample_status,
        "evidence_strength": evidence_strength,
        "observed_count": len(values),
        "complete_path_not_observed_count": complete_without_value,
        "missing_or_incomplete_count": missing,
        "mean_hours": _mean(values),
        "median_hours": statistics.median(values) if values else None,
        "minimum_hours": min(values) if values else None,
        "maximum_hours": max(values) if values else None,
        "uncertainty": _hours_uncertainty(
            values,
            resamples=bootstrap_resamples,
            label=f"{partition}\0{evidence_mode}\0{label}",
        ),
        "timing_unit": "hours",
        "timing_is_daily_resolution": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _classification_row(
    rows: Sequence[_Episode],
    *,
    classification: str,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    observed: list[bool] = []
    for row in rows:
        value = _primary_classifications(row).get(classification)
        if isinstance(value, bool):
            observed.append(value)
    return _classification_values_row(
        observed,
        classification=classification,
        episode_count=len(rows),
        partition=partition,
        evidence_mode=evidence_mode,
        bootstrap_resamples=bootstrap_resamples,
        label=f"classification\0{classification}",
    )


def _classification_values_row(
    observed: Sequence[bool],
    *,
    classification: str,
    episode_count: int,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
    label: str,
    horizon: str | None = None,
) -> dict[str, Any]:
    numeric = [1.0 if value else 0.0 for value in observed]
    sample_status, evidence_strength = _sample_evidence(len(numeric))
    result = {
        "classification": classification,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": episode_count,
        "eligible_sample_size": len(numeric),
        "sample_size": len(numeric),
        "sample_status": sample_status,
        "evidence_strength": evidence_strength,
        "true_count": sum(observed),
        "false_count": len(observed) - sum(observed),
        "rate_fraction": _mean(numeric),
        "uncertainty": _bootstrap_mean_ci(
            numeric,
            resamples=bootstrap_resamples,
            label=f"{partition}\0{evidence_mode}\0{label}",
        ),
        "rate_unit": "fraction",
        "classification_is_descriptive": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }
    if horizon is not None:
        result["horizon"] = horizon
    return result


def _post_expiry_row(
    status: str,
    rows: Sequence[_Episode],
    *,
    partition: str,
    evidence_mode: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    values = [value for row in rows if (value := _post_expiry_return(row)) is not None]
    summary = _robust_summary(values)
    sample_status, evidence_strength = _sample_evidence(len(values))
    return {
        "cohort_type": "post_expiry_status",
        "cohort": status,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "episode_count": len(rows),
        "sample_size": len(values),
        "sample_status": sample_status,
        "evidence_strength": evidence_strength,
        "result_direction": _result_direction(summary["mean"]),
        "mean_post_expiry_directional_return_fraction": summary["mean"],
        "median_post_expiry_directional_return_fraction": summary["median"],
        "trimmed_mean_10pct_post_expiry_directional_return_fraction": summary["trimmed_mean_10pct"],
        "uncertainty": _bootstrap_mean_ci(
            values,
            resamples=bootstrap_resamples,
            label=f"{partition}\0{evidence_mode}\0post_expiry\0{status}",
        ),
        "return_unit": "fraction",
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _flatten(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    projection = row.get("decision_projection")
    if isinstance(projection, Mapping):
        for key, value in projection.items():
            result.setdefault(str(key), value)
    quality = result.get("replay_feature_quality")
    if isinstance(quality, Mapping):
        result.setdefault("baseline_maturity", quality.get("baseline_maturity"))
    return result


def _field(name: str) -> Any:
    return lambda row: row.representative.get(name)


def _contributing_origins(row: _Episode) -> set[str]:
    raw = row.representative.get("thesis_origins")
    values = {_text(value) for value in raw} if isinstance(raw, (list, tuple, set)) else set()
    primary = _text(row.representative.get("primary_thesis_origin"))
    if primary:
        values.add(primary)
    return {value for value in values if value}


def _baseline_maturity(row: _Episode) -> str:
    quality = row.representative.get("replay_feature_quality")
    nested = quality.get("baseline_maturity") if isinstance(quality, Mapping) else None
    return _text(
        row.representative.get("baseline_maturity")
        or row.representative.get("baseline_status")
        or nested
    ) or "unknown"


def _asset_tier(row: _Episode) -> str:
    context = row.representative.get("point_in_time_context")
    nested_rank = context.get("point_in_time_volume_rank") if isinstance(context, Mapping) else None
    rank = _finite(
        row.representative.get("point_in_time_volume_rank")
        if row.representative.get("point_in_time_volume_rank") is not None
        else nested_rank
    )
    if rank is None or rank < 1 or not float(rank).is_integer():
        return "unknown"
    if rank <= 3:
        return "top_1_3"
    if rank <= 30:
        return "rank_4_30"
    if rank <= 100:
        return "rank_31_100"
    return "outside_top_100"


def _provider_source_definition(row: _Episode) -> dict[str, Any]:
    representative = row.representative
    projection = representative.get("decision_projection")
    lineage = projection.get("source_provider_lineage") if isinstance(projection, Mapping) else None
    lineage = lineage if isinstance(lineage, Mapping) else {}
    market_reference = projection.get("market_context_reference") if isinstance(projection, Mapping) else None
    market_reference = market_reference if isinstance(market_reference, Mapping) else {}
    providers = _tokens(
        representative.get("source_provider"),
        representative.get("provider"),
        representative.get("market_data_source"),
        lineage.get("providers"),
        market_reference.get("source"),
    )
    sources = _tokens(
        representative.get("source_origin"),
        representative.get("source_origins"),
        lineage.get("origins"),
    )
    source_packs = _tokens(
        representative.get("source_pack"),
        representative.get("source_packs"),
        lineage.get("source_packs"),
    )
    provider_label = "+".join(providers) or "unknown"
    source_label = "+".join(sources) or "unknown"
    return {
        "cohort": f"providers={provider_label}|sources={source_label}",
        "providers": providers,
        "sources": sources,
        "source_packs": source_packs,
        "status": "observed" if providers or sources else "unknown",
    }


def _primary_horizon(row: _Episode) -> Mapping[str, Any]:
    horizon = _text(row.outcome.get("primary_horizon")) or "3d"
    return _horizon(row, horizon)


def _horizon(row: _Episode, horizon: str) -> Mapping[str, Any]:
    values = row.outcome.get("horizons") or row.outcome.get("return_by_horizon")
    value = values.get(horizon) if isinstance(values, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def _horizon_matured(value: Mapping[str, Any]) -> bool:
    return _text(value.get("maturity_status") or value.get("status")) == "matured"


def _primary_matured(row: _Episode) -> bool:
    primary = _primary_horizon(row)
    if primary:
        return _horizon_matured(primary)
    return _text(row.outcome.get("status")) == "matured"


def _primary_directional(row: _Episode) -> float | None:
    if not _primary_matured(row):
        return None
    primary = _primary_horizon(row)
    value = _fraction_field(primary, "direction_adjusted_return_fraction")
    if value is None:
        value = _fraction_field(row.outcome, "primary_direction_adjusted_return")
    if value is not None:
        return value
    return _directional(row, _primary_raw(row))


def _primary_raw(row: _Episode) -> float | None:
    if not _primary_matured(row):
        return None
    primary = _primary_horizon(row)
    value = _fraction_field(primary, "raw_return_fraction")
    return value if value is not None else _fraction_field(row.outcome, "primary_horizon_return")


def _primary_mfe(row: _Episode) -> float | None:
    if not _primary_matured(row):
        return None
    value = _horizon_mfe(_primary_horizon(row))
    if value is None:
        value = _fraction_field(row.outcome, "max_favorable_excursion")
    return max(0.0, value) if value is not None else None


def _primary_mae(row: _Episode) -> float | None:
    if not _primary_matured(row):
        return None
    value = _horizon_mae(_primary_horizon(row))
    if value is None:
        value = _fraction_field(row.outcome, "max_adverse_excursion")
    return abs(value) if value is not None else None


def _horizon_directional(row: _Episode, value: Mapping[str, Any]) -> float | None:
    explicit = _fraction_field(value, "direction_adjusted_return_fraction")
    if explicit is not None:
        return explicit
    return _directional(row, _fraction_field(value, "raw_return_fraction"))


def _relative_directional(
    row: _Episode, value: Mapping[str, Any], benchmark: str
) -> float | None:
    adjusted = value.get("direction_adjusted_relative_returns_fraction")
    if isinstance(adjusted, Mapping):
        result = _fraction(adjusted.get(benchmark), "fraction")
        if result is not None:
            return result
    raw = value.get("relative_returns_fraction")
    if isinstance(raw, Mapping):
        return _directional(row, _fraction(raw.get(benchmark), "fraction"))
    return None


def _horizon_mfe(value: Mapping[str, Any]) -> float | None:
    result = _fraction_field(value, "max_favorable_excursion_fraction")
    return max(0.0, result) if result is not None else None


def _horizon_mae(value: Mapping[str, Any]) -> float | None:
    result = _fraction_field(value, "max_adverse_excursion_fraction")
    return abs(result) if result is not None else None


def _primary_classifications(row: _Episode) -> dict[str, bool | None]:
    explicit = row.outcome.get("classifications")
    explicit = explicit if isinstance(explicit, Mapping) else {}
    derived = _horizon_classifications(row, _primary_horizon(row))
    return {
        name: explicit.get(name) if isinstance(explicit.get(name), bool) else derived[name]
        for name in OUTCOME_CLASSIFICATIONS
    }


def _horizon_classifications(
    row: _Episode, value: Mapping[str, Any]
) -> dict[str, bool | None]:
    direction_return = _horizon_directional(row, value)
    if not _horizon_matured(value) or direction_return is None:
        return {name: None for name in OUTCOME_CLASSIFICATIONS}
    bias = _text(row.representative.get("directional_bias"))
    mfe = _horizon_mfe(value)
    return {
        "continuation": direction_return > 0.0,
        "reversal": direction_return < 0.0,
        "breakout_failure": (
            bool(mfe is not None and mfe > 0.0 and direction_return <= 0.0)
            if bias == "long" else None
        ),
        "fade_success": direction_return > 0.0 if bias == "fade_short_review" else None,
        "risk_event_validation": direction_return > 0.0 if bias == "risk" else None,
    }


def _expiry(row: _Episode) -> Mapping[str, Any]:
    value = row.outcome.get("expiry")
    return value if isinstance(value, Mapping) else {}


def _expiry_status(row: _Episode) -> str:
    return _text(_expiry(row).get("status")) or "unknown"


def _post_expiry_status(row: _Episode) -> str:
    value = _text(_expiry(row).get("post_expiry_behavior"))
    return value if value in POST_EXPIRY_STATUSES else "unknown"


def _post_expiry_return(row: _Episode) -> float | None:
    return _fraction_field(_expiry(row), "post_expiry_direction_adjusted_return_fraction")


def _fraction_field(source: Mapping[str, Any], field: str) -> float | None:
    raw = source.get(field)
    if raw is None:
        return None
    unit = (
        "fraction"
        if field.endswith("_fraction")
        else source.get(f"{field}_unit") or source.get("return_unit") or "fraction_by_protocol"
    )
    return _fraction(raw, unit)


def _fraction(raw: Any, unit: Any) -> float | None:
    value = _finite(raw)
    normalized = _text(unit)
    if value is None:
        return None
    if normalized in _FRACTION_UNITS:
        return value
    if normalized in _PERCENT_POINT_UNITS:
        return value / 100.0
    return None


def _directional(row: _Episode, value: float | None) -> float | None:
    sign = _DIRECTION_SIGN.get(_text(row.representative.get("directional_bias")))
    return sign * value if sign is not None and value is not None else None


def _tokens(*values: Any) -> list[str]:
    result: set[str] = set()
    for value in values:
        candidates = value if isinstance(value, (list, tuple, set)) else (value,)
        result.update(_text(candidate) for candidate in candidates if _text(candidate))
    return sorted(result)


def _sample_evidence(sample_size: int) -> tuple[str, str]:
    if sample_size == 0:
        return "no_sample", "no_evidence"
    if sample_size < 5:
        return "insufficient_sample", "insufficient"
    if sample_size < 30:
        return "descriptive_sample", "descriptive_only"
    if sample_size < 100:
        return "cohort_directional_sample", "exploratory"
    return "shadow_recommendation_sample", "stronger_exploratory"


def _result_direction(value: float | None) -> str:
    if value is None:
        return "no_result"
    if value > 0.0:
        return "positive_descriptive"
    if value < 0.0:
        return "negative_descriptive"
    return "flat_descriptive"


def _hours_uncertainty(
    values: Sequence[float], *, resamples: int, label: str
) -> dict[str, Any]:
    raw = _bootstrap_mean_ci(values, resamples=resamples, label=label)
    return {
        "status": raw["status"],
        "method": raw["method"],
        "confidence_level": raw["confidence_level"],
        "resamples": raw["resamples"],
        "sample_size": raw["sample_size"],
        "lower_hours": raw["lower_fraction"],
        "upper_hours": raw["upper_fraction"],
        "timing_unit": "hours",
    }


def _nonnegative(value: Any) -> float | None:
    result = _finite(value)
    return result if result is not None and result >= 0.0 else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


__all__ = [
    "ASSET_TIERS",
    "BASELINE_MATURITIES",
    "CATALYST_STATUSES",
    "CONTRIBUTING_ORIGIN_COHORTS",
    "CONTRIBUTING_ORIGINS",
    "DIRECTIONAL_BIASES",
    "EXPIRY_STATUSES",
    "HORIZONS",
    "MARKET_PHASES",
    "METHOD",
    "OUTCOME_CLASSIFICATIONS",
    "POST_EXPIRY_STATUSES",
    "PREFERRED_HORIZONS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SPREAD_STATUSES",
    "TIMING_METRICS",
    "TIMING_STATES",
    "TRADABILITY_STATUSES",
    "build_empirical_dimension_analysis",
]
