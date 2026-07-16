"""Pure episode and path outcomes for Decision Radar empirical replay.

The producer is intentionally isolated from operational artifact code.  It
accepts already-materialized idea rows and daily OHLCV frames, performs no I/O,
and returns JSON-ready research values.  Outcome rules come from the frozen
empirical-validation protocol; callers cannot tune horizons, episode windows,
or invalidation thresholds at runtime.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_replay_episode_outcomes"
SCHEMA_VERSION = 1
METHOD = "frozen_daily_path_outcomes_with_fixed_start_episodes"
TIMING_RESOLUTION = {
    "basis": "daily_ohlcv",
    "minimum_increment_hours": 24,
    "intraday_timing_available": False,
    "same_idea_bar_extremes_included": False,
}

_PROTOCOL = empirical_validation_protocol.protocol_values()
_PRIMARY_DAYS = int(_PROTOCOL["outcomes"]["primary_horizon_days"])
_SENSITIVITY_DAYS = tuple(
    int(value) for value in _PROTOCOL["outcomes"]["sensitivity_horizons_days"]
)
_HORIZON_DAYS = tuple(sorted({_PRIMARY_DAYS, *_SENSITIVITY_DAYS}))
_PRIMARY_HORIZON = f"{_PRIMARY_DAYS}d"
_EPISODE_WINDOW_HOURS = int(_PROTOCOL["episodes"]["primary_window_hours"])
_INVALIDATION_RETURN = -abs(
    float(
        _PROTOCOL["false_positive_and_late_rules"][
            "quick_failure_return_fraction"
        ]
    )
)
_DIRECTION_SIGN = {
    "long": 1.0,
    "fade_short_review": -1.0,
    "risk": -1.0,
}
_PROGRESSION_FIELDS = (
    "radar_route",
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "chase_risk_score",
    "market_phase",
    "catalyst_status",
    "spread_status",
    "derivatives_status",
    "expires_at",
)
_SAFETY = {
    "research_only": True,
    "provider_calls": 0,
    "writes": 0,
    "notifications": 0,
    "trades": 0,
    "orders": 0,
    "paper_trades": 0,
    "normal_rsi_writes": 0,
    "triggered_fade_created": 0,
    "authorization_mutations": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
    "auto_apply": False,
}


def build_empirical_replay_outcomes(
    idea_rows: Iterable[Mapping[str, Any]],
    price_frames: Mapping[str, Any],
    *,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Build frozen representative outcomes and dependent episode progression.

    ``price_frames`` is keyed by symbol and must include daily ``close``,
    ``high``, and ``low`` values.  Timestamps may be a ``DatetimeIndex`` or a
    ``timestamp``, ``observed_at``, ``date``, or ``open_time`` column.  Idea
    timestamps require an exact matching entry bar.  ``BTC`` and ``ETH`` frames
    are optional, but missing benchmarks remain explicit in every horizon.
    """

    evaluated = _required_utc(evaluated_at, field_name="evaluated_at")
    frames, frame_diagnostics = _normalize_price_frames(price_frames)
    supplied = [dict(row) for row in idea_rows if isinstance(row, Mapping)]
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in supplied:
        snapshot, reasons = _idea_snapshot(row, evaluated_at=evaluated)
        if snapshot is None:
            excluded.append(
                {
                    "input_digest": _digest(_json_ready(row)),
                    "reasons": list(reasons),
                }
            )
        else:
            eligible.append(snapshot)

    episode_groups = _fixed_start_episode_groups(eligible)
    episodes = [
        _episode_value(group, frames=frames, evaluated_at=evaluated)
        for group in episode_groups
    ]
    excluded.sort(key=lambda row: (tuple(row["reasons"]), row["input_digest"]))
    result: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "protocol_version": _PROTOCOL["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(),
        "evaluated_at": evaluated.isoformat(),
        "primary_horizon": _PRIMARY_HORIZON,
        "primary_horizon_days": _PRIMARY_DAYS,
        "sensitivity_horizons": [f"{days}d" for days in _SENSITIVITY_DAYS],
        "horizon_days": {f"{days}d": days for days in _HORIZON_DAYS},
        "episode_window_hours": _EPISODE_WINDOW_HOURS,
        "episode_boundary_rule": (
            "member_observed_at_lt_episode_start_plus_window"
        ),
        "representative_rule": "first_eligible_observation_never_reselected",
        "timing_resolution": dict(TIMING_RESOLUTION),
        "status": (
            "empty" if not supplied else "partial" if excluded else "ready"
        ),
        "ideas_supplied": len(supplied),
        "ideas_eligible": len(eligible),
        "ideas_excluded": len(excluded),
        "excluded_ideas": excluded,
        "episode_count": len(episodes),
        "dependent_repeat_count": len(eligible) - len(episodes),
        "episodes": episodes,
        "price_frame_diagnostics": frame_diagnostics,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_SAFETY),
    }
    result["contract_digest"] = _digest(result)
    return result


def build_empirical_path_outcome(
    idea_row: Mapping[str, Any],
    price_frames: Mapping[str, Any],
    *,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Build one daily path outcome without episode grouping or side effects."""

    evaluated = _required_utc(evaluated_at, field_name="evaluated_at")
    snapshot, reasons = _idea_snapshot(dict(idea_row), evaluated_at=evaluated)
    if snapshot is None:
        raise ValueError("empirical idea invalid:" + ",".join(reasons))
    frames, _diagnostics = _normalize_price_frames(price_frames)
    return _path_outcome(snapshot, frames=frames, evaluated_at=evaluated)


def _episode_value(
    members: Sequence[dict[str, Any]],
    *,
    frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, Any]:
    representative = members[0]
    start = _required_utc(representative["observed_at"], field_name="observed_at")
    identity = {
        "canonical_asset_id": representative["canonical_asset_id"],
        "directional_bias": representative["directional_bias"],
        "anomaly_family": representative["anomaly_family"],
    }
    episode_id = "empirical-episode-v1:" + _digest(
        {
            "identity": identity,
            "episode_start_at": start.isoformat(),
            "representative_idea_id": representative["idea_id"],
        }
    )
    progression = [
        {**deepcopy(member), "episode_id": episode_id} for member in members
    ]
    representative_value = progression[0]
    representative_outcome = _path_outcome(
        representative,
        frames=frames,
        evaluated_at=evaluated_at,
    )
    representative_outcome["episode_id"] = episode_id
    representative_outcome["outcome_digest"] = _digest(
        {
            key: item
            for key, item in representative_outcome.items()
            if key != "outcome_digest"
        }
    )
    value: dict[str, Any] = {
        "episode_id": episode_id,
        "episode_identity": identity,
        "canonical_asset_id": representative["canonical_asset_id"],
        "directional_bias": representative["directional_bias"],
        "anomaly_family": representative["anomaly_family"],
        "episode_start_at": start.isoformat(),
        "window_end_exclusive_at": (
            start + timedelta(hours=_EPISODE_WINDOW_HOURS)
        ).isoformat(),
        "representative_rule": "first_eligible_observation_never_reselected",
        "representative_idea_id": representative["idea_id"],
        "representative": representative_value,
        "member_count": len(members),
        "dependent_repeat_count": len(members) - 1,
        "member_progression": progression,
        "progression_fields": list(_PROGRESSION_FIELDS),
        "representative_outcome": representative_outcome,
        "dependent_repeats_counted_as_independent": False,
        "representative_reselected": False,
        "research_only": True,
    }
    value["episode_digest"] = _digest(value)
    return value


def _path_outcome(
    idea: Mapping[str, Any],
    *,
    frames: Mapping[str, pd.DataFrame],
    evaluated_at: datetime,
) -> dict[str, Any]:
    observed = _required_utc(idea["observed_at"], field_name="observed_at")
    symbol = str(idea["symbol"])
    direction = str(idea["directional_bias"])
    sign = _DIRECTION_SIGN.get(direction)
    frame = frames.get(symbol.upper())
    entry_price = _exact_close(frame, observed)
    entry_missing_reason = (
        "asset_price_frame_missing"
        if frame is None
        else "entry_bar_missing_or_invalid"
        if entry_price is None
        else None
    )

    horizons: dict[str, dict[str, Any]] = {}
    for days in _HORIZON_DAYS:
        label = f"{days}d"
        horizons[label] = _horizon_value(
            observed_at=observed,
            evaluated_at=evaluated_at,
            days=days,
            entry_price=entry_price,
            entry_missing_reason=entry_missing_reason,
            frame=frame,
            benchmark_frames=frames,
            direction_sign=sign,
        )

    primary = horizons[_PRIMARY_HORIZON]
    pre_signal = _pre_signal_move(
        observed_at=observed,
        frame=frame,
        entry_price=entry_price,
        direction_sign=sign,
    )
    expiry = _expiry_assessment(
        idea,
        observed_at=observed,
        evaluated_at=evaluated_at,
        entry_price=entry_price,
        frame=frame,
        horizons=horizons,
        direction_sign=sign,
    )
    classifications = _classifications(
        direction=direction,
        primary=primary,
        expiry=expiry,
    )
    missing_reasons = list(primary["missing_reasons"])
    if sign is None:
        missing_reasons.append("directional_bias_not_scoreable")
    missing_reasons = list(dict.fromkeys(missing_reasons))
    value: dict[str, Any] = {
        "schema_id": "decision_radar.empirical_replay_path_outcome",
        "schema_version": SCHEMA_VERSION,
        "idea_id": idea["idea_id"],
        "canonical_asset_id": idea["canonical_asset_id"],
        "symbol": symbol,
        "observed_at": observed.isoformat(),
        "evaluated_at": evaluated_at.isoformat(),
        "directional_bias": direction,
        "direction_sign": sign,
        "direction_status": "scoreable" if sign is not None else "not_scoreable",
        "entry_price": entry_price,
        "entry_bar_at": observed.isoformat() if entry_price is not None else None,
        "primary_horizon": _PRIMARY_HORIZON,
        "primary_horizon_days": _PRIMARY_DAYS,
        "status": primary["maturity_status"],
        "missing_reasons": missing_reasons,
        "horizons": horizons,
        "primary_horizon_return": primary["raw_return_fraction"],
        "primary_direction_adjusted_return": primary[
            "direction_adjusted_return_fraction"
        ],
        "primary_relative_return_vs_btc": primary["relative_returns_fraction"][
            "BTC"
        ],
        "primary_relative_return_vs_eth": primary["relative_returns_fraction"][
            "ETH"
        ],
        "max_favorable_excursion": primary["max_favorable_excursion_fraction"],
        "max_adverse_excursion": primary["max_adverse_excursion_fraction"],
        "time_to_mfe_hours": primary["time_to_mfe_hours"],
        "time_to_mae_hours": primary["time_to_mae_hours"],
        "time_to_invalidation_hours": primary["time_to_invalidation_hours"],
        "pre_signal_move_7d": pre_signal,
        "classifications": classifications,
        "expiry": expiry,
        "timing_resolution": dict(TIMING_RESOLUTION),
        "same_idea_bar_excluded": True,
        "return_unit": "fraction",
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_SAFETY),
    }
    value["outcome_digest"] = _digest(value)
    return value


def _horizon_value(
    *,
    observed_at: datetime,
    evaluated_at: datetime,
    days: int,
    entry_price: float | None,
    entry_missing_reason: str | None,
    frame: pd.DataFrame | None,
    benchmark_frames: Mapping[str, pd.DataFrame],
    direction_sign: float | None,
) -> dict[str, Any]:
    due = observed_at + timedelta(days=days)
    missing: list[str] = []
    if entry_price is None:
        maturity = "missing_data"
        missing.append(entry_missing_reason or "entry_price_missing")
        exit_price = None
    elif evaluated_at < due:
        maturity = "pending"
        missing.append("horizon_not_due")
        exit_price = None
    else:
        exit_price = _exact_close(frame, due)
        if exit_price is None:
            maturity = "missing_data"
            missing.append("exit_bar_missing_or_invalid")
        else:
            maturity = "matured"

    raw_return = (
        exit_price / entry_price - 1.0
        if entry_price is not None and exit_price is not None
        else None
    )
    direction_return = (
        direction_sign * raw_return
        if direction_sign is not None and raw_return is not None
        else None
    )
    if direction_sign is None:
        missing.append("directional_bias_not_scoreable")

    benchmark_returns: dict[str, float | None] = {}
    benchmark_status: dict[str, str] = {}
    benchmark_missing: dict[str, list[str]] = {}
    relative: dict[str, float | None] = {}
    direction_relative: dict[str, float | None] = {}
    for benchmark in ("BTC", "ETH"):
        bench_frame = _benchmark_frame(benchmark_frames, benchmark)
        bench_entry = _exact_close(bench_frame, observed_at)
        bench_exit = _exact_close(bench_frame, due) if evaluated_at >= due else None
        reasons: list[str] = []
        if evaluated_at < due:
            status = "pending"
            reasons.append("horizon_not_due")
        elif bench_frame is None:
            status = "missing_data"
            reasons.append("benchmark_price_frame_missing")
        elif bench_entry is None:
            status = "missing_data"
            reasons.append("benchmark_entry_bar_missing_or_invalid")
        elif bench_exit is None:
            status = "missing_data"
            reasons.append("benchmark_exit_bar_missing_or_invalid")
        else:
            status = "matured"
        bench_return = (
            bench_exit / bench_entry - 1.0
            if bench_entry is not None and bench_exit is not None
            else None
        )
        relative_value = (
            raw_return - bench_return
            if raw_return is not None and bench_return is not None
            else None
        )
        benchmark_returns[benchmark] = bench_return
        benchmark_status[benchmark] = status
        benchmark_missing[benchmark] = reasons
        relative[benchmark] = relative_value
        direction_relative[benchmark] = (
            direction_sign * relative_value
            if direction_sign is not None and relative_value is not None
            else None
        )

    path = _path_metrics(
        frame,
        observed_at=observed_at,
        due_at=due,
        entry_price=entry_price,
        direction_sign=direction_sign,
        horizon_maturity=maturity,
        expected_days=days,
    )
    return {
        "horizon": f"{days}d",
        "horizon_days": days,
        "due_at": due.isoformat(),
        "maturity_status": maturity,
        "missing_reasons": list(dict.fromkeys(missing)),
        "exit_bar_at": due.isoformat() if exit_price is not None else None,
        "exit_price": exit_price,
        "raw_return_fraction": raw_return,
        "direction_adjusted_return_fraction": direction_return,
        "benchmark_returns_fraction": benchmark_returns,
        "benchmark_status": benchmark_status,
        "benchmark_missing_reasons": benchmark_missing,
        "relative_returns_fraction": relative,
        "direction_adjusted_relative_returns_fraction": direction_relative,
        **path,
        "return_unit": "fraction",
        "timing_resolution_hours": 24,
        "same_idea_bar_excluded": True,
    }


def _path_metrics(
    frame: pd.DataFrame | None,
    *,
    observed_at: datetime,
    due_at: datetime,
    entry_price: float | None,
    direction_sign: float | None,
    horizon_maturity: str,
    expected_days: int,
) -> dict[str, Any]:
    empty = {
        "path_status": (
            "pending" if horizon_maturity == "pending" else "missing_data"
        ),
        "path_missing_reasons": [],
        "path_bar_count": 0,
        "expected_path_bar_count": expected_days,
        "max_favorable_excursion_fraction": None,
        "max_adverse_excursion_fraction": None,
        "time_to_mfe_hours": None,
        "time_to_mae_hours": None,
        "time_to_invalidation_hours": None,
        "invalidation_threshold_fraction": _INVALIDATION_RETURN,
    }
    if horizon_maturity == "pending":
        empty["path_missing_reasons"] = ["horizon_not_due"]
        return empty
    if frame is None or entry_price is None:
        empty["path_missing_reasons"] = ["entry_or_frame_missing"]
        return empty
    if direction_sign is None:
        empty["path_missing_reasons"] = ["directional_bias_not_scoreable"]
        return empty

    start = pd.Timestamp(observed_at)
    end = pd.Timestamp(due_at)
    rows = frame.loc[(frame.index > start) & (frame.index <= end)]
    if len(rows) != expected_days:
        empty["path_bar_count"] = len(rows)
        empty["path_missing_reasons"] = ["daily_path_incomplete"]
        return empty
    if rows[["high", "low"]].isna().any().any():
        empty["path_bar_count"] = len(rows)
        empty["path_missing_reasons"] = ["daily_path_extreme_invalid"]
        return empty
    if bool((rows["high"] < rows["low"]).any()):
        empty["path_bar_count"] = len(rows)
        empty["path_missing_reasons"] = ["daily_high_below_low"]
        return empty

    favorable: list[tuple[float, pd.Timestamp]] = []
    adverse: list[tuple[float, pd.Timestamp]] = []
    invalidation_at: pd.Timestamp | None = None
    for timestamp, row in rows.iterrows():
        high_return = direction_sign * (float(row["high"]) / entry_price - 1.0)
        low_return = direction_sign * (float(row["low"]) / entry_price - 1.0)
        best = max(high_return, low_return)
        worst = min(high_return, low_return)
        favorable.append((best, timestamp))
        adverse.append((worst, timestamp))
        if invalidation_at is None and worst <= _INVALIDATION_RETURN:
            invalidation_at = timestamp

    best_value, best_at = max(favorable, key=lambda item: (item[0], -item[1].value))
    worst_value, worst_at = min(adverse, key=lambda item: (item[0], item[1].value))
    mfe = max(0.0, best_value)
    mae = min(0.0, worst_value)
    return {
        "path_status": "complete",
        "path_missing_reasons": [],
        "path_bar_count": len(rows),
        "expected_path_bar_count": expected_days,
        "max_favorable_excursion_fraction": mfe,
        "max_adverse_excursion_fraction": mae,
        "time_to_mfe_hours": (
            _hours(observed_at, best_at.to_pydatetime()) if mfe > 0 else None
        ),
        "time_to_mae_hours": (
            _hours(observed_at, worst_at.to_pydatetime()) if mae < 0 else None
        ),
        "time_to_invalidation_hours": (
            _hours(observed_at, invalidation_at.to_pydatetime())
            if invalidation_at is not None
            else None
        ),
        "invalidation_threshold_fraction": _INVALIDATION_RETURN,
    }


def _pre_signal_move(
    *,
    observed_at: datetime,
    frame: pd.DataFrame | None,
    entry_price: float | None,
    direction_sign: float | None,
) -> dict[str, Any]:
    start = observed_at - timedelta(days=7)
    prior = _exact_close(frame, start)
    raw = (
        entry_price / prior - 1.0
        if prior is not None and entry_price is not None
        else None
    )
    return {
        "status": "available" if raw is not None else "missing_data",
        "start_at": start.isoformat(),
        "end_at": observed_at.isoformat(),
        "raw_return_fraction": raw,
        "direction_adjusted_return_fraction": (
            direction_sign * raw
            if direction_sign is not None and raw is not None
            else None
        ),
        "return_unit": "fraction",
    }


def _expiry_assessment(
    idea: Mapping[str, Any],
    *,
    observed_at: datetime,
    evaluated_at: datetime,
    entry_price: float | None,
    frame: pd.DataFrame | None,
    horizons: Mapping[str, Mapping[str, Any]],
    direction_sign: float | None,
) -> dict[str, Any]:
    raw_expiry = idea.get("expires_at")
    if raw_expiry in (None, ""):
        return _empty_expiry("not_configured", expires_at=None)
    expiry = _optional_utc(raw_expiry)
    if expiry is None:
        return _empty_expiry("invalid_expiry", expires_at=str(raw_expiry))
    if expiry <= observed_at:
        return _empty_expiry("invalid_expiry", expires_at=expiry.isoformat())
    if evaluated_at < expiry:
        return _empty_expiry("not_expired", expires_at=expiry.isoformat())
    if frame is None or entry_price is None or direction_sign is None:
        return _empty_expiry("missing_data", expires_at=expiry.isoformat())

    expiry_row = frame.loc[
        (frame.index > pd.Timestamp(observed_at))
        & (frame.index >= pd.Timestamp(expiry))
        & (frame.index <= pd.Timestamp(evaluated_at))
    ]
    if expiry_row.empty:
        return _empty_expiry("missing_data", expires_at=expiry.isoformat())
    expiry_at = expiry_row.index[0]
    expiry_close = _finite_number(expiry_row.iloc[0]["close"])
    if expiry_close is None or expiry_close <= 0:
        return _empty_expiry("missing_data", expires_at=expiry.isoformat())
    at_expiry = direction_sign * (expiry_close / entry_price - 1.0)
    without_resolution = at_expiry <= 0.0

    assessment_horizon: str | None = None
    post_return: float | None = None
    for label in (f"{days}d" for days in _HORIZON_DAYS):
        horizon = horizons[label]
        exit_at = _optional_utc(horizon.get("exit_bar_at"))
        exit_price = _finite_number(horizon.get("exit_price"))
        if (
            horizon.get("maturity_status") == "matured"
            and exit_at is not None
            and exit_at > expiry_at.to_pydatetime()
            and exit_price is not None
        ):
            assessment_horizon = label
            post_return = direction_sign * (exit_price / expiry_close - 1.0)
            break
    post_behavior = (
        "not_observed"
        if post_return is None
        else "continuation"
        if post_return > 0
        else "reversal"
        if post_return < 0
        else "flat"
    )
    return {
        "status": (
            "expired_without_resolution"
            if without_resolution
            else "expired_with_directional_resolution"
        ),
        "expires_at": expiry.isoformat(),
        "expiry_price_observed_at": expiry_at.isoformat(),
        "expiry_price": expiry_close,
        "time_to_expiry_observation_hours": _hours(
            observed_at, expiry_at.to_pydatetime()
        ),
        "direction_adjusted_return_at_expiry_fraction": at_expiry,
        "expired_without_resolution": without_resolution,
        "post_expiry_behavior": post_behavior,
        "post_expiry_assessment_horizon": assessment_horizon,
        "post_expiry_direction_adjusted_return_fraction": post_return,
        "post_expiry_continuation": (
            post_return > 0 if post_return is not None else None
        ),
        "post_expiry_reversal": (
            post_return < 0 if post_return is not None else None
        ),
        "timing_resolution_hours": 24,
        "return_unit": "fraction",
    }


def _empty_expiry(status: str, *, expires_at: str | None) -> dict[str, Any]:
    return {
        "status": status,
        "expires_at": expires_at,
        "expiry_price_observed_at": None,
        "expiry_price": None,
        "time_to_expiry_observation_hours": None,
        "direction_adjusted_return_at_expiry_fraction": None,
        "expired_without_resolution": None,
        "post_expiry_behavior": "not_observed",
        "post_expiry_assessment_horizon": None,
        "post_expiry_direction_adjusted_return_fraction": None,
        "post_expiry_continuation": None,
        "post_expiry_reversal": None,
        "timing_resolution_hours": 24,
        "return_unit": "fraction",
    }


def _classifications(
    *,
    direction: str,
    primary: Mapping[str, Any],
    expiry: Mapping[str, Any],
) -> dict[str, Any]:
    direction_return = _finite_number(
        primary.get("direction_adjusted_return_fraction")
    )
    mfe = _finite_number(primary.get("max_favorable_excursion_fraction"))
    available = (
        primary.get("maturity_status") == "matured" and direction_return is not None
    )
    continuation = direction_return > 0 if available else None
    reversal = direction_return < 0 if available else None
    breakout_failure = None
    if available and direction == "long" and mfe is not None:
        breakout_failure = bool(mfe > 0 and direction_return <= 0)
    fade_success = (
        direction_return > 0
        if available and direction == "fade_short_review"
        else None
    )
    risk_validation = (
        direction_return > 0 if available and direction == "risk" else None
    )
    return {
        "status": "available" if available else "not_available",
        "continuation": continuation,
        "reversal": reversal,
        "breakout_failure": breakout_failure,
        "fade_success": fade_success,
        "risk_event_validation": risk_validation,
        "expired_without_resolution": expiry.get("expired_without_resolution"),
        "post_expiry_continuation": expiry.get("post_expiry_continuation"),
        "post_expiry_reversal": expiry.get("post_expiry_reversal"),
        "classification_basis": (
            "sign_of_direction_adjusted_primary_return_and_complete_daily_path"
        ),
        "descriptive_only": True,
    }


def _fixed_start_episode_groups(
    snapshots: Iterable[dict[str, Any]],
) -> list[tuple[dict[str, Any], ...]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        key = (
            str(snapshot["canonical_asset_id"]),
            str(snapshot["directional_bias"]),
            str(snapshot["anomaly_family"]),
        )
        grouped.setdefault(key, []).append(snapshot)

    episodes: list[tuple[dict[str, Any], ...]] = []
    for key in sorted(grouped):
        ordered = sorted(
            grouped[key],
            key=lambda row: (row["observed_at"], row["idea_id"]),
        )
        current: list[dict[str, Any]] = []
        window_end: datetime | None = None
        for snapshot in ordered:
            observed = _required_utc(snapshot["observed_at"], field_name="observed_at")
            if window_end is None or observed >= window_end:
                if current:
                    episodes.append(tuple(current))
                current = [snapshot]
                window_end = observed + timedelta(hours=_EPISODE_WINDOW_HOURS)
            else:
                current.append(snapshot)
        if current:
            episodes.append(tuple(current))
    return sorted(
        episodes,
        key=lambda group: (group[0]["observed_at"], group[0]["idea_id"]),
    )


def _idea_snapshot(
    row: Mapping[str, Any],
    *,
    evaluated_at: datetime,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    projection = row.get("decision_projection")
    projection = dict(projection) if isinstance(projection, Mapping) else {}
    reasons: list[str] = []

    def value(*keys: str) -> Any:
        for source in (row, projection):
            for key in keys:
                candidate = source.get(key)
                if candidate not in (None, ""):
                    return candidate
        return None

    canonical_asset_id = value("canonical_asset_id", "coin_id")
    symbol = value("symbol")
    observed = _optional_utc(value("observed_at", "decision_evaluated_at"))
    direction = str(value("directional_bias") or "").strip()
    if not isinstance(canonical_asset_id, str) or not canonical_asset_id.strip():
        reasons.append("canonical_asset_id_missing")
    if not isinstance(symbol, str) or not symbol.strip():
        reasons.append("symbol_missing")
    if observed is None:
        reasons.append("observed_at_invalid_or_naive")
    elif observed > evaluated_at:
        reasons.append("idea_observed_after_evaluation")
    if direction not in {*_DIRECTION_SIGN, "neutral"}:
        reasons.append("directional_bias_invalid")
    if reasons:
        return None, tuple(sorted(set(reasons)))

    anomaly_family = str(
        value("anomaly_family", "anomaly_type", "market_anomaly_type") or "unknown"
    )
    provisional = {
        "canonical_asset_id": canonical_asset_id.strip(),
        "symbol": symbol.strip().upper(),
        "observed_at": observed.isoformat(),
        "directional_bias": direction,
        "anomaly_family": anomaly_family,
    }
    idea_id = value("idea_id", "candidate_id", "observation_id")
    if not isinstance(idea_id, str) or not idea_id.strip():
        idea_id = "derived:" + _digest(provisional)
    snapshot: dict[str, Any] = {
        "idea_id": idea_id.strip(),
        **provisional,
        "candidate_id": _optional_text(value("candidate_id")),
        "core_opportunity_id": _optional_text(value("core_opportunity_id")),
        "radar_route": _optional_text(value("radar_route", "route")),
        "actionability_score": _finite_number(value("actionability_score")),
        "evidence_confidence_score": _finite_number(
            value("evidence_confidence_score")
        ),
        "risk_score": _finite_number(value("risk_score")),
        "urgency_score": _finite_number(value("urgency_score")),
        "chase_risk_score": _finite_number(value("chase_risk_score")),
        "market_phase": _optional_text(value("market_phase")),
        "catalyst_status": _optional_text(value("catalyst_status")),
        "spread_status": _optional_text(value("spread_status")),
        "derivatives_status": _optional_text(
            value("derivatives_status", "derivatives_data_status")
        ),
        "expires_at": _iso_or_original(value("expires_at")),
        # Bounded replay context required for partition, origin, regime,
        # liquidity, feature-quality, and missed-opportunity cohorts.  The
        # projection remains the canonical Decision surface; these values are
        # copied explicitly because several are replay-only rather than model
        # fields.
        "partition": _optional_text(value("partition", "replay_partition")),
        "replay_partition": _optional_text(
            value("replay_partition", "partition")
        ),
        "primary_thesis_origin": _optional_text(
            value("primary_thesis_origin", "thesis_origin")
        ),
        "thesis_origins": _text_list(value("thesis_origins", "source_origins")),
        "market_regime": _optional_text(value("market_regime")),
        "liquidity_tier": _optional_text(value("liquidity_tier")),
        "liquidity_usd": _finite_number(value("liquidity_usd")),
        "trailing_quote_volume_usd": _finite_number(
            value("trailing_quote_volume_usd", "trailing_quote_volume")
        ),
        "data_quality_mode": _optional_text(
            value("data_quality_mode", "replay_data_quality_mode")
        ),
        "replay_data_quality_mode": _optional_text(
            value("replay_data_quality_mode", "data_quality_mode")
        ),
        "replay_feature_quality": _json_ready(
            value("replay_feature_quality", "feature_basis") or {}
        ),
        "point_in_time_membership": _optional_bool(
            value("point_in_time_membership", "point_in_time_universe_member")
        ),
        "point_in_time_universe_member": _optional_bool(
            value("point_in_time_universe_member", "point_in_time_membership")
        ),
        "baseline_status": _optional_text(
            value("baseline_status", "baseline_maturity")
        ),
        "baseline_warm": _optional_bool(value("baseline_warm")),
        "operator_visible_idea": _optional_bool(
            value("operator_visible_idea", "operator_visible")
        ),
        "analysis_role": _optional_text(value("analysis_role")),
        "failure_reason_codes": _text_list(
            value("failure_reason_codes", "decision_hard_blockers")
        ),
        "catalyst_attribution_timing": _optional_text(
            value("catalyst_attribution_timing", "catalyst_evidence_timing")
        ),
        "catalyst_timing_vs_market_reaction": _optional_text(
            value("catalyst_timing_vs_market_reaction")
        ),
        "candidate_family_id": _optional_text(value("candidate_family_id")),
        "decision_projection": _json_ready(projection),
    }
    return snapshot, ()


def _normalize_price_frames(
    price_frames: Mapping[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    if not isinstance(price_frames, Mapping):
        raise TypeError("price_frames must be a mapping of symbol to DataFrame")
    normalized: dict[str, pd.DataFrame] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for raw_symbol, raw_frame in price_frames.items():
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        errors: list[str] = []
        frame: pd.DataFrame | None = None
        if symbol in normalized or symbol in diagnostics:
            errors.append("duplicate_symbol_key_after_normalization")
        elif isinstance(raw_frame, pd.DataFrame):
            frame, frame_errors = _normalize_frame(raw_frame)
            errors.extend(frame_errors)
        elif (
            isinstance(raw_frame, Sequence)
            and not isinstance(raw_frame, (str, bytes))
            and len(raw_frame) <= 4_096
            and all(isinstance(item, Mapping) for item in raw_frame)
        ):
            frame, frame_errors = _normalize_frame(pd.DataFrame(list(raw_frame)))
            errors.extend(frame_errors)
        else:
            errors.append("price_frame_not_dataframe_or_bounded_rows")
        if errors or frame is None:
            normalized.pop(symbol, None)
            diagnostics[symbol] = {
                "status": "invalid",
                "errors": sorted(set(errors or ["price_frame_invalid"])),
                "row_count": 0,
                "first_timestamp": None,
                "last_timestamp": None,
            }
            continue
        normalized[symbol] = frame
        diagnostics[symbol] = {
            "status": "available",
            "errors": [],
            "row_count": len(frame),
            "first_timestamp": frame.index[0].isoformat() if len(frame) else None,
            "last_timestamp": frame.index[-1].isoformat() if len(frame) else None,
        }
    return normalized, dict(sorted(diagnostics.items()))


def _normalize_frame(
    raw_frame: pd.DataFrame,
) -> tuple[pd.DataFrame | None, tuple[str, ...]]:
    frame = raw_frame.copy(deep=True)
    column_map = {str(column).casefold(): column for column in frame.columns}
    timestamp_column = next(
        (
            column_map[name]
            for name in ("timestamp", "observed_at", "date", "open_time")
            if name in column_map
        ),
        None,
    )
    raw_timestamps: Any = frame.index if timestamp_column is None else frame[timestamp_column]
    try:
        timestamps = _timestamp_index(raw_timestamps)
    except (TypeError, ValueError, OverflowError):
        return None, ("price_frame_timestamp_invalid",)
    if timestamps.isna().any():
        return None, ("price_frame_timestamp_invalid",)
    if timestamps.has_duplicates:
        return None, ("price_frame_timestamp_duplicate",)
    required = {}
    for name in ("close", "high", "low"):
        source = column_map.get(name)
        if source is None:
            return None, (f"price_frame_{name}_missing",)
        required[name] = pd.to_numeric(frame[source], errors="coerce").to_numpy()
    normalized = pd.DataFrame(required, index=timestamps)
    normalized.sort_index(inplace=True)
    for name in ("close", "high", "low"):
        normalized.loc[~normalized[name].map(_positive_finite), name] = float("nan")
    return normalized, ()


def _timestamp_index(values: Any) -> pd.DatetimeIndex:
    series = pd.Series(values)
    numeric = pd.to_numeric(series, errors="coerce")
    if len(series) and numeric.notna().all():
        maximum = float(numeric.abs().max())
        unit = "ns" if maximum >= 1e16 else "ms" if maximum >= 1e11 else "s"
        timestamps = pd.to_datetime(numeric, unit=unit, utc=True)
    else:
        timestamps = pd.to_datetime(series, utc=True)
    return pd.DatetimeIndex(timestamps)


def _exact_close(frame: pd.DataFrame | None, timestamp: datetime) -> float | None:
    if frame is None:
        return None
    key = pd.Timestamp(timestamp)
    if key not in frame.index:
        return None
    value = _finite_number(frame.loc[key, "close"])
    return value if value is not None and value > 0 else None


def _benchmark_frame(
    frames: Mapping[str, pd.DataFrame], benchmark: str
) -> pd.DataFrame | None:
    """Accept the protocol label and the Binance quote-pair spelling."""

    frame = frames.get(benchmark)
    return frame if frame is not None else frames.get(f"{benchmark}USDT")


def _required_utc(value: datetime | str, *, field_name: str) -> datetime:
    parsed = _optional_utc(value)
    if parsed is None:
        raise ValueError(f"{field_name} must be an aware timestamp")
    return parsed


def _optional_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = (
            value.to_pydatetime()
            if isinstance(value, pd.Timestamp)
            else value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso_or_original(value: Any) -> str | None:
    if value in (None, ""):
        return None
    parsed = _optional_utc(value)
    return parsed.isoformat() if parsed is not None else str(value)


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean or None


def _text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        clean = value.strip()
        return [clean] if clean else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return list(dict.fromkeys(
        clean
        for item in value
        if isinstance(item, str) and (clean := item.strip())
    ))


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive_finite(value: Any) -> bool:
    number = _finite_number(value)
    return number is not None and number > 0


def _hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_ready(item) for item in value)
    if isinstance(value, pd.Timestamp):
        parsed = _optional_utc(value)
        return parsed.isoformat() if parsed is not None else str(value)
    if isinstance(value, datetime):
        parsed = _optional_utc(value)
        return parsed.isoformat() if parsed is not None else str(value)
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA:
        return None
    return deepcopy(value)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _json_ready(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "METHOD",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "TIMING_RESOLUTION",
    "build_empirical_path_outcome",
    "build_empirical_replay_outcomes",
]
