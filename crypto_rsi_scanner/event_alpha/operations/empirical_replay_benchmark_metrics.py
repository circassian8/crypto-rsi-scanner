"""Pure descriptive metrics for outcome-joined empirical benchmarks.

Benchmark selection happens elsewhere and remains strictly point-in-time and
outcome-blind.  This module receives already-selected rows after their frozen
path outcomes have been joined.  It summarizes those outcomes without I/O,
policy mutation, causal claims, or unit conversion.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_benchmark_metrics"
SCHEMA_VERSION = 1

_PROTOCOL = empirical_validation_protocol.protocol_values()
_COST_BPS = tuple(
    int(value) for value in _PROTOCOL["cost_scenarios"]["round_trip_cost_bps"]
)
_COST_LABEL = str(_PROTOCOL["cost_scenarios"]["unobserved_cost_label"])
_PRIMARY_DAYS = int(_PROTOCOL["outcomes"]["primary_horizon_days"])
_HORIZON_DAYS = tuple(
    sorted(
        {
            _PRIMARY_DAYS,
            *(
                int(value)
                for value in _PROTOCOL["outcomes"][
                    "sensitivity_horizons_days"
                ]
            ),
        }
    )
)


def build_benchmark_row(
    policy: str,
    selections: Sequence[Mapping[str, Any]],
    unavailable: Mapping[str, int],
    *,
    eligible_group_count: int,
    detail_row_limit: int,
) -> dict[str, Any]:
    """Return one closed baseline row with robust and sensitivity metrics."""

    normalized = [dict(row) for row in selections if isinstance(row, Mapping)]
    matured = [
        row for row in normalized if _primary_status(row.get("outcome")) == "matured"
    ]
    pending = [
        row for row in normalized if _primary_status(row.get("outcome")) == "pending"
    ]
    missing = [
        row
        for row in normalized
        if _primary_status(row.get("outcome")) not in {"matured", "pending"}
    ]
    status = (
        "empty"
        if not normalized and eligible_group_count == 0
        else "unavailable"
        if not normalized
        else "available"
        if len(matured) == len(normalized)
        else "pending"
        if pending and not missing
        else "partial"
    )
    detail_rows = sorted(normalized, key=_selection_order)
    primary = _horizon_summary(normalized, days=_PRIMARY_DAYS)
    holding_rows = [
        _horizon_summary(normalized, days=days) for days in _HORIZON_DAYS
    ]
    directional = _ordered_directional_returns(
        normalized, horizon_label=f"{_PRIMARY_DAYS}d"
    )
    cost_sensitivity = _cost_sensitivity(directional)
    return {
        "policy": policy,
        "status": status,
        "eligible_group_count": eligible_group_count,
        "selection_count": len(normalized),
        "selection_detail_limit": detail_row_limit,
        "selections_truncated": len(normalized) > detail_row_limit,
        "selection_detail_policy": "earliest_chronological_no_outcome_rank",
        "matured_outcome_count": len(matured),
        "pending_outcome_count": len(pending),
        "missing_outcome_count": len(missing),
        "unavailable_reason_counts": dict(sorted(unavailable.items())),
        "metric_schema_id": SCHEMA_ID,
        "metric_schema_version": SCHEMA_VERSION,
        "metric_status": primary["status"],
        "sample_size": primary["sample_size"],
        "mean_primary_raw_return_fraction": primary[
            "mean_raw_return_fraction"
        ],
        "mean_primary_direction_adjusted_return_fraction": primary[
            "mean_direction_adjusted_return_fraction"
        ],
        "median_primary_direction_adjusted_return_fraction": primary[
            "median_direction_adjusted_return_fraction"
        ],
        "trimmed_mean_10pct_primary_direction_adjusted_return_fraction": primary[
            "trimmed_mean_10pct_direction_adjusted_return_fraction"
        ],
        "hit_rate": primary["hit_rate"],
        "mean_primary_mfe_fraction": primary["mean_mfe_fraction"],
        "mean_primary_mae_fraction": primary["mean_mae_fraction"],
        "downside_5pct_primary_direction_adjusted_return_fraction": primary[
            "downside_5pct_direction_adjusted_return_fraction"
        ],
        "worst_primary_direction_adjusted_return_fraction": primary[
            "worst_direction_adjusted_return_fraction"
        ],
        "chronological_drawdown_proxy_fraction": primary[
            "chronological_drawdown_proxy_fraction"
        ],
        "drawdown_proxy_basis": primary["drawdown_proxy_basis"],
        "break_even_mean_round_trip_cost_bps": cost_sensitivity[
            "break_even_mean_round_trip_cost_bps"
        ],
        "primary_outcome_metrics": primary,
        "cost_sensitivity": cost_sensitivity,
        "holding_period_sensitivity": {
            "status": (
                "available"
                if any(row["sample_size"] for row in holding_rows)
                else "unavailable"
            ),
            "horizons": holding_rows,
            "horizon_order": [f"{days}d" for days in _HORIZON_DAYS],
            "selection_uses_outcomes": False,
            "outcomes_joined_after_selection": True,
            "return_unit": "fraction",
            "causal_claim": False,
            "policy_eligible": False,
            "research_only": True,
            "auto_apply": False,
        },
        "return_unit": "fraction",
        "cost_unit": "basis_points",
        "selection_uses_outcomes": False,
        "outcomes_joined_after_selection": True,
        "selections": detail_rows[:detail_row_limit],
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def compact_joined_path_outcome(outcome: Mapping[str, Any]) -> dict[str, Any]:
    """Keep every frozen horizon needed for later baseline comparisons."""

    primary_label = str(outcome.get("primary_horizon") or f"{_PRIMARY_DAYS}d")
    raw_horizons = outcome.get("horizons")
    raw_horizons = raw_horizons if isinstance(raw_horizons, Mapping) else {}
    horizon_fields = (
        "horizon",
        "horizon_days",
        "maturity_status",
        "due_at",
        "raw_return_fraction",
        "direction_adjusted_return_fraction",
        "max_favorable_excursion_fraction",
        "max_adverse_excursion_fraction",
        "time_to_mfe_hours",
        "time_to_mae_hours",
        "time_to_invalidation_hours",
        "path_status",
        "path_missing_reasons",
        "missing_reasons",
        "return_unit",
    )
    compact_horizons: dict[str, dict[str, Any]] = {}
    for label in sorted(raw_horizons, key=_horizon_sort_key):
        raw = raw_horizons.get(label)
        if not isinstance(raw, Mapping):
            continue
        compact_horizons[str(label)] = {
            field: _json_ready(raw.get(field)) for field in horizon_fields
        }
    fields = (
        "idea_id",
        "candidate_id",
        "canonical_asset_id",
        "symbol",
        "observed_at",
        "directional_bias",
        "status",
        "primary_horizon",
        "primary_horizon_return",
        "primary_direction_adjusted_return",
        "primary_relative_return_vs_btc",
        "primary_relative_return_vs_eth",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "time_to_mfe_hours",
        "time_to_mae_hours",
        "time_to_invalidation_hours",
        "pre_signal_move_7d",
        "classifications",
        "expiry",
        "return_unit",
        "research_only",
        "auto_apply",
    )
    return {
        **{field: _json_ready(outcome.get(field)) for field in fields},
        "horizons": compact_horizons,
        "preserved_horizon_order": [
            label for label in (f"{days}d" for days in _HORIZON_DAYS)
            if label in compact_horizons
        ],
        "primary_horizon_preserved": primary_label in compact_horizons,
    }


def _horizon_summary(
    selections: Sequence[Mapping[str, Any]], *, days: int
) -> dict[str, Any]:
    label = f"{days}d"
    statuses: Counter[str] = Counter()
    unavailable: Counter[str] = Counter()
    raw_returns: list[float] = []
    directional_rows: list[tuple[str, str, float]] = []
    mfe_values: list[float] = []
    mae_values: list[float] = []
    for selection in selections:
        horizon = _horizon(selection.get("outcome"), label=label)
        if horizon is None:
            statuses["missing_data"] += 1
            unavailable["horizon_not_preserved"] += 1
            continue
        status = str(horizon.get("maturity_status") or "missing_data")
        statuses[status] += 1
        if status != "matured":
            reasons = horizon.get("missing_reasons")
            if isinstance(reasons, Sequence) and not isinstance(
                reasons, (str, bytes, bytearray)
            ):
                for reason in reasons:
                    unavailable[str(reason or "unspecified_missing_reason")] += 1
            else:
                unavailable[f"horizon_{status}"] += 1
            continue
        unit = str(horizon.get("return_unit") or "")
        if unit != "fraction":
            unavailable["return_unit_not_fraction"] += 1
            continue
        raw = _finite(horizon.get("raw_return_fraction"))
        directional = _finite(horizon.get("direction_adjusted_return_fraction"))
        if raw is not None:
            raw_returns.append(raw)
        if directional is None:
            unavailable["direction_adjusted_return_unavailable"] += 1
            continue
        directional_rows.append(
            (
                _selection_observed_at(selection),
                str(selection.get("selection_id") or ""),
                directional,
            )
        )
        mfe = _finite(horizon.get("max_favorable_excursion_fraction"))
        mae = _finite(horizon.get("max_adverse_excursion_fraction"))
        if mfe is not None:
            mfe_values.append(mfe)
        else:
            unavailable["mfe_unavailable"] += 1
        if mae is not None:
            mae_values.append(mae)
        else:
            unavailable["mae_unavailable"] += 1

    directional = [item[2] for item in sorted(directional_rows)]
    summary = _robust_summary(directional)
    mfe_summary = _robust_summary(mfe_values)
    mae_summary = _robust_summary(mae_values)
    return {
        "horizon": label,
        "horizon_days": days,
        "status": "available" if directional else "unavailable",
        "selection_count": len(selections),
        "maturity_status_counts": dict(sorted(statuses.items())),
        "matured_outcome_count": statuses.get("matured", 0),
        "pending_outcome_count": statuses.get("pending", 0),
        "missing_outcome_count": (
            len(selections) - statuses.get("matured", 0) - statuses.get("pending", 0)
        ),
        "unavailable_reason_counts": dict(sorted(unavailable.items())),
        "raw_return_sample_size": len(raw_returns),
        "sample_size": len(directional),
        "mean_raw_return_fraction": _mean(raw_returns),
        "mean_direction_adjusted_return_fraction": summary["mean"],
        "median_direction_adjusted_return_fraction": summary["median"],
        "trimmed_mean_10pct_direction_adjusted_return_fraction": summary[
            "trimmed_mean_10pct"
        ],
        "hit_rate": (
            sum(value > 0.0 for value in directional) / len(directional)
            if directional
            else None
        ),
        "downside_5pct_direction_adjusted_return_fraction": summary[
            "downside_5pct"
        ],
        "worst_direction_adjusted_return_fraction": (
            min(directional) if directional else None
        ),
        "mfe_sample_size": len(mfe_values),
        "mean_mfe_fraction": mfe_summary["mean"],
        "median_mfe_fraction": mfe_summary["median"],
        "mae_sample_size": len(mae_values),
        "mean_mae_fraction": mae_summary["mean"],
        "median_mae_fraction": mae_summary["median"],
        "chronological_drawdown_proxy_fraction": _drawdown_proxy(directional),
        "drawdown_proxy_basis": (
            "additive_direction_adjusted_returns_ordered_by_observation_time;"
            "overlap_not_netting_or_portfolio_simulation"
        ),
        "return_unit": "fraction",
        "selection_uses_outcomes": False,
        "outcomes_joined_after_selection": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _cost_sensitivity(
    ordered_directional: Sequence[float],
) -> dict[str, Any]:
    gross_mean = _mean(ordered_directional)
    scenarios: list[dict[str, Any]] = []
    for bps in _COST_BPS:
        cost_fraction = bps / 10_000.0
        net = [value - cost_fraction for value in ordered_directional]
        summary = _robust_summary(net)
        scenarios.append(
            {
                "round_trip_cost_bps": bps,
                "round_trip_cost_fraction": cost_fraction,
                "cost_basis": _COST_LABEL,
                "historical_spread_observed": False,
                "sample_size": len(net),
                "mean_net_direction_adjusted_return_fraction": summary["mean"],
                "median_net_direction_adjusted_return_fraction": summary[
                    "median"
                ],
                "trimmed_mean_10pct_net_direction_adjusted_return_fraction": summary[
                    "trimmed_mean_10pct"
                ],
                "net_hit_rate": (
                    sum(value > 0.0 for value in net) / len(net)
                    if net
                    else None
                ),
                "downside_5pct_net_direction_adjusted_return_fraction": summary[
                    "downside_5pct"
                ],
                "mean_survives_assumed_cost": (
                    summary["mean"] > 0.0 if summary["mean"] is not None else None
                ),
                "return_unit": "fraction",
                "cost_unit": "basis_points",
                "causal_claim": False,
                "policy_eligible": False,
                "research_only": True,
                "auto_apply": False,
            }
        )
    return {
        "status": "available" if ordered_directional else "unavailable",
        "gross_sample_size": len(ordered_directional),
        "gross_mean_direction_adjusted_return_fraction": gross_mean,
        "break_even_mean_round_trip_cost_bps": (
            max(0.0, gross_mean * 10_000.0)
            if gross_mean is not None
            else None
        ),
        "break_even_basis": "mean_directional_return_assumed_round_trip_cost",
        "historical_spread_observed": False,
        "cost_basis": _COST_LABEL,
        "scenarios": scenarios,
        "return_unit": "fraction",
        "cost_unit": "basis_points",
        "selection_uses_outcomes": False,
        "outcomes_joined_after_selection": True,
        "causal_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _ordered_directional_returns(
    selections: Sequence[Mapping[str, Any]], *, horizon_label: str
) -> list[float]:
    rows: list[tuple[str, str, float]] = []
    for selection in selections:
        horizon = _horizon(selection.get("outcome"), label=horizon_label)
        if (
            horizon is None
            or horizon.get("maturity_status") != "matured"
            or horizon.get("return_unit") != "fraction"
        ):
            continue
        value = _finite(horizon.get("direction_adjusted_return_fraction"))
        if value is not None:
            rows.append(
                (
                    _selection_observed_at(selection),
                    str(selection.get("selection_id") or ""),
                    value,
                )
            )
    return [row[2] for row in sorted(rows)]


def _horizon(outcome: Any, *, label: str) -> Mapping[str, Any] | None:
    if not isinstance(outcome, Mapping):
        return None
    horizons = outcome.get("horizons")
    if not isinstance(horizons, Mapping):
        return None
    value = horizons.get(label)
    return value if isinstance(value, Mapping) else None


def _primary_status(outcome: Any) -> str:
    if not isinstance(outcome, Mapping):
        return "missing_data"
    return str(outcome.get("status") or "missing_data")


def _selection_order(row: Mapping[str, Any]) -> tuple[str, str]:
    return _selection_observed_at(row), str(row.get("selection_id") or "")


def _selection_observed_at(row: Mapping[str, Any]) -> str:
    observation = row.get("observation")
    return str(
        observation.get("observed_at")
        if isinstance(observation, Mapping)
        else ""
    )


def _robust_summary(values: Sequence[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    trim = math.floor(len(ordered) * 0.10)
    retained = ordered[trim : len(ordered) - trim] if trim else ordered
    return {
        "mean": _mean(ordered),
        "median": statistics.median(ordered) if ordered else None,
        "trimmed_mean_10pct": _mean(retained),
        "downside_5pct": _quantile(ordered, 0.05),
    }


def _drawdown_proxy(ordered_returns: Sequence[float]) -> float | None:
    if not ordered_returns:
        return None
    cumulative = 0.0
    peak = 0.0
    worst = 0.0
    for value in ordered_returns:
        cumulative += value
        peak = max(peak, cumulative)
        worst = min(worst, cumulative - peak)
    return worst


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower] * (1.0 - weight) + values[upper] * weight)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _horizon_sort_key(value: Any) -> tuple[int, str]:
    label = str(value)
    try:
        days = int(label.removesuffix("d"))
    except ValueError:
        days = 10**9
    return days, label


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_ready(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return deepcopy(value)


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_benchmark_row",
    "compact_joined_path_outcome",
]
