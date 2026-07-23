"""Point-in-time outcome maturation for Lean Crypto Radar ideas.

The outcome lane reads only retained market snapshots.  It does not call a
provider, require a human label, or feed any result back into setup thresholds.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math
from typing import Mapping, Sequence

from .models import LeanIdea, LeanOutcome, MarketSnapshot, OUTCOME_HORIZONS
from .safety import SAFETY_COUNTERS
from .store import LeanRadarStore, LeanRadarStoreError


HORIZON_DELTAS = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
}
MAX_ENDPOINT_LAG = timedelta(minutes=45)
DESCRIPTIVE_MOVE_BAND_PP = 2.0
FAILED_QUICKLY_BAND_PP = 3.0


class _LeanOutcomeError(ValueError):
    """Raised when retained outcome evidence cannot be interpreted safely."""


LeanOutcomeError = _LeanOutcomeError


def pending_outcomes_for_scan(
    ideas: Sequence[LeanIdea],
    snapshots: Sequence[MarketSnapshot],
    *,
    evaluated_at: datetime,
) -> tuple[LeanOutcome, ...]:
    """Create complete pending placeholders for the current atomic scan write."""

    evaluated = _aware_utc(evaluated_at, "outcome evaluation time")
    by_asset_and_time = {
        (row.canonical_asset_id, _time(row.observed_at)): row for row in snapshots
    }
    outcomes: list[LeanOutcome] = []
    for idea in ideas:
        start = _time(idea.created_at)
        snapshot = by_asset_and_time.get((idea.canonical_asset_id, start))
        if snapshot is None:
            raise LeanOutcomeError("current idea has no exact start snapshot")
        for horizon in OUTCOME_HORIZONS:
            outcomes.append(
                _pending_outcome(
                    idea,
                    horizon=horizon,
                    start_price_usd=snapshot.price_usd,
                    evaluated_at=evaluated,
                )
            )
    return tuple(outcomes)


def refresh_outcomes(
    store: LeanRadarStore,
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, object]:
    """Mature every due horizon from retained snapshots and persist one truth."""

    evaluated = _aware_utc(
        evaluated_at or datetime.now(timezone.utc), "outcome evaluation time"
    )
    if not store.path.exists():
        return {
            "status": "setup_required",
            "component": "outcomes",
            "checked_at": evaluated.isoformat(),
            "idea_count": 0,
            "outcome_count": 0,
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "automatic_threshold_changes": 0,
            "human_labels_required": False,
            "research_only": True,
            **SAFETY_COUNTERS,
        }

    ideas = tuple(_idea_from_mapping(row) for row in store.list_ideas())
    existing = {
        (row.idea_id, row.horizon): row
        for row in (_outcome_from_mapping(value) for value in store.list_outcomes())
    }
    refreshed: list[LeanOutcome] = []
    for idea in ideas:
        for horizon in OUTCOME_HORIZONS:
            outcome = existing.get((idea.idea_id, horizon))
            if outcome is None:
                start_snapshot = _snapshot_at(
                    store,
                    idea.canonical_asset_id,
                    _time(idea.created_at),
                )
                outcome = _pending_outcome(
                    idea,
                    horizon=horizon,
                    start_price_usd=(
                        start_snapshot.price_usd if start_snapshot is not None else None
                    ),
                    evaluated_at=evaluated,
                    missing_information=(
                        ()
                        if start_snapshot is not None
                        else ("Exact start snapshot is unavailable",)
                    ),
                )
            refreshed.append(_evaluate_outcome(store, idea, outcome, evaluated))

    idea_statuses = _idea_outcome_statuses(ideas, refreshed)
    counts = {state: 0 for state in ("pending", "matured", "unresolved")}
    result_counts = {
        result: 0
        for result in (
            "inconclusive",
            "continued",
            "reversed",
            "failed_quickly",
            "risk_warning_validated",
        )
    }
    for row in refreshed:
        counts[row.status] += 1
        if row.result in result_counts:
            result_counts[row.result] += 1
    health = {
        "status": "ready" if ideas else "waiting_for_ideas",
        "component": "outcomes",
        "checked_at": evaluated.isoformat(),
        "idea_count": len(ideas),
        "outcome_count": len(refreshed),
        "pending_count": counts["pending"],
        "matured_count": counts["matured"],
        "unresolved_count": counts["unresolved"],
        "expired_idea_count": sum(
            evaluated >= _time(idea.expires_at) for idea in ideas
        ),
        "result_counts": result_counts,
        "horizons": list(OUTCOME_HORIZONS),
        "endpoint_policy": "first observation at/after target within 45 minutes",
        "classification_policy": {
            "descriptive_move_band_pp": DESCRIPTIVE_MOVE_BAND_PP,
            "failed_quickly_1h_band_pp": FAILED_QUICKLY_BAND_PP,
        },
        "provider_call_attempted": False,
        "telegram_send_attempted": False,
        "automatic_threshold_changes": 0,
        "human_labels_required": False,
        "research_only": True,
        **SAFETY_COUNTERS,
    }
    store.write_outcomes(refreshed, idea_statuses=idea_statuses, health=health)
    return health


def _evaluate_outcome(
    store: LeanRadarStore,
    idea: LeanIdea,
    outcome: LeanOutcome,
    evaluated_at: datetime,
) -> LeanOutcome:
    expired = evaluated_at >= _time(idea.expires_at)
    if outcome.status == "matured":
        return replace(outcome, evaluated_at=evaluated_at.isoformat(), expired=expired)

    target = _time(outcome.target_at)
    deadline = target + MAX_ENDPOINT_LAG
    start_snapshot = _snapshot_at(
        store, idea.canonical_asset_id, _time(outcome.start_observed_at)
    )
    start_price = outcome.start_price_usd
    if start_snapshot is not None:
        if start_price is not None and not math.isclose(
            start_price, start_snapshot.price_usd, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise LeanOutcomeError("stored outcome start price drifted from its snapshot")
        start_price = start_snapshot.price_usd

    query_end = min(deadline, evaluated_at)
    endpoint: MarketSnapshot | None = None
    if query_end >= target:
        candidates = _snapshot_window(
            store,
            idea.canonical_asset_id,
            start=_time(outcome.start_observed_at),
            end=query_end,
        )
        endpoint = next((row for row in candidates if _time(row.observed_at) >= target), None)
    if start_price is None or endpoint is None:
        missing = []
        if start_price is None:
            missing.append("Exact start snapshot is unavailable")
        if endpoint is None:
            missing.append(
                "Waiting for the target observation window"
                if evaluated_at <= deadline
                else "No endpoint snapshot exists within the 45-minute target window"
            )
        state = "pending" if evaluated_at <= deadline else "unresolved"
        return LeanOutcome(
            idea_id=idea.idea_id,
            symbol=idea.symbol,
            canonical_asset_id=idea.canonical_asset_id,
            idea_type=idea.idea_type,
            directional_bias=idea.directional_bias,
            horizon=outcome.horizon,
            target_at=outcome.target_at,
            status=state,
            result=state,
            evaluated_at=evaluated_at.isoformat(),
            start_observed_at=outcome.start_observed_at,
            start_price_usd=start_price,
            expired=expired,
            missing_information=tuple(missing),
        )

    endpoint_time = _time(endpoint.observed_at)
    path = _snapshot_window(
        store,
        idea.canonical_asset_id,
        start=_time(outcome.start_observed_at),
        end=endpoint_time,
    )
    raw_path_returns = [_return_pp(start_price, row.price_usd) for row in path]
    if not raw_path_returns or not math.isclose(
        raw_path_returns[0], 0.0, rel_tol=0.0, abs_tol=1e-12
    ):
        raise LeanOutcomeError("outcome path is missing its exact start snapshot")
    asset_return = _return_pp(start_price, endpoint.price_usd)
    multiplier = _direction_multiplier(idea.directional_bias)
    missing: list[str] = []
    if idea.directional_bias == "neutral":
        mfe = None
        mae = None
        missing.append("Directional MFE and MAE are unavailable for a neutral idea")
    else:
        oriented_path = [value * multiplier for value in raw_path_returns]
        mfe = max(0.0, max(oriented_path))
        mae = min(0.0, min(oriented_path))
    relative_btc = _relative_return(
        store,
        asset_return=asset_return,
        benchmark_id="bitcoin",
        start=_time(outcome.start_observed_at),
        end=endpoint_time,
    )
    if relative_btc is None:
        missing.append("Exact BTC benchmark path is unavailable")
    relative_eth = _relative_return(
        store,
        asset_return=asset_return,
        benchmark_id="ethereum",
        start=_time(outcome.start_observed_at),
        end=endpoint_time,
    )
    if relative_eth is None:
        missing.append("Exact ETH benchmark path is unavailable")
    return LeanOutcome(
        idea_id=idea.idea_id,
        symbol=idea.symbol,
        canonical_asset_id=idea.canonical_asset_id,
        idea_type=idea.idea_type,
        directional_bias=idea.directional_bias,
        horizon=outcome.horizon,
        target_at=outcome.target_at,
        status="matured",
        result=_classify_result(
            idea,
            horizon=outcome.horizon,
            raw_return_pp=asset_return,
            oriented_return_pp=asset_return * multiplier,
        ),
        evaluated_at=evaluated_at.isoformat(),
        start_observed_at=outcome.start_observed_at,
        start_price_usd=start_price,
        end_observed_at=endpoint_time.isoformat(),
        end_price_usd=endpoint.price_usd,
        endpoint_lag_seconds=(endpoint_time - target).total_seconds(),
        return_pp=asset_return,
        relative_btc_pp=relative_btc,
        relative_eth_pp=relative_eth,
        mfe_pp=mfe,
        mae_pp=mae,
        path_snapshot_count=len(path),
        expired=expired,
        missing_information=tuple(missing),
    )


def _pending_outcome(
    idea: LeanIdea,
    *,
    horizon: str,
    start_price_usd: float | None,
    evaluated_at: datetime,
    missing_information: tuple[str, ...] = (),
) -> LeanOutcome:
    start = _time(idea.created_at)
    return LeanOutcome(
        idea_id=idea.idea_id,
        symbol=idea.symbol,
        canonical_asset_id=idea.canonical_asset_id,
        idea_type=idea.idea_type,
        directional_bias=idea.directional_bias,
        horizon=horizon,
        target_at=(start + HORIZON_DELTAS[horizon]).isoformat(),
        status="pending",
        result="pending",
        evaluated_at=evaluated_at.isoformat(),
        start_observed_at=start.isoformat(),
        start_price_usd=start_price_usd,
        expired=evaluated_at >= _time(idea.expires_at),
        missing_information=missing_information,
    )


def _idea_outcome_statuses(
    ideas: Sequence[LeanIdea],
    outcomes: Sequence[LeanOutcome],
) -> dict[str, str]:
    grouped: dict[str, list[str]] = {idea.idea_id: [] for idea in ideas}
    for row in outcomes:
        grouped.setdefault(row.idea_id, []).append(row.status)
    result: dict[str, str] = {}
    for idea_id, states in grouped.items():
        if states and all(state == "matured" for state in states):
            result[idea_id] = "matured"
        elif states and all(state == "unresolved" for state in states):
            result[idea_id] = "unresolved"
        elif any(state != "pending" for state in states):
            result[idea_id] = "partial"
        else:
            result[idea_id] = "pending"
    return result


def _classify_result(
    idea: LeanIdea,
    *,
    horizon: str,
    raw_return_pp: float,
    oriented_return_pp: float,
) -> str:
    if idea.directional_bias == "neutral":
        return "inconclusive"
    if idea.directional_bias == "risk" and raw_return_pp <= -DESCRIPTIVE_MOVE_BAND_PP:
        return "risk_warning_validated"
    if horizon == "1h" and oriented_return_pp <= -FAILED_QUICKLY_BAND_PP:
        return "failed_quickly"
    if oriented_return_pp >= DESCRIPTIVE_MOVE_BAND_PP:
        return "continued"
    if oriented_return_pp <= -DESCRIPTIVE_MOVE_BAND_PP:
        return "reversed"
    return "inconclusive"


def _relative_return(
    store: LeanRadarStore,
    *,
    asset_return: float,
    benchmark_id: str,
    start: datetime,
    end: datetime,
) -> float | None:
    benchmark_start = _snapshot_at(store, benchmark_id, start)
    benchmark_end = _snapshot_at(store, benchmark_id, end)
    if benchmark_start is None or benchmark_end is None:
        return None
    return asset_return - _return_pp(
        benchmark_start.price_usd, benchmark_end.price_usd
    )


def _snapshot_at(
    store: LeanRadarStore,
    canonical_asset_id: str,
    observed_at: datetime,
) -> MarketSnapshot | None:
    rows = _snapshot_window(
        store,
        canonical_asset_id,
        start=observed_at,
        end=observed_at,
    )
    return rows[0] if rows else None


def _snapshot_window(
    store: LeanRadarStore,
    canonical_asset_id: str,
    *,
    start: datetime,
    end: datetime,
) -> tuple[MarketSnapshot, ...]:
    return tuple(
        _snapshot_from_mapping(row)
        for row in store.snapshot_window(
            canonical_asset_id,
            start=start.astimezone(timezone.utc).isoformat(),
            end=end.astimezone(timezone.utc).isoformat(),
        )
    )


def _return_pp(start_price: float, end_price: float) -> float:
    return ((end_price / start_price) - 1.0) * 100.0


def _direction_multiplier(directional_bias: str) -> float:
    return -1.0 if directional_bias in {"short_review", "risk"} else 1.0


def _idea_from_mapping(value: Mapping[str, object]) -> LeanIdea:
    payload = dict(value)
    for key in (
        "why_now",
        "supporting_facts",
        "risks",
        "missing_information",
        "what_confirms",
        "what_invalidates",
    ):
        payload[key] = tuple(payload.get(key, ()))
    try:
        return LeanIdea(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanRadarStoreError("stored idea is invalid") from exc


def _outcome_from_mapping(value: Mapping[str, object]) -> LeanOutcome:
    payload = dict(value)
    payload["missing_information"] = tuple(payload.get("missing_information", ()))
    try:
        return LeanOutcome(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanRadarStoreError("stored outcome is invalid") from exc


def _snapshot_from_mapping(value: Mapping[str, object]) -> MarketSnapshot:
    payload = dict(value)
    payload["sparkline_prices"] = tuple(payload.get("sparkline_prices", ()))
    try:
        return MarketSnapshot(**payload)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LeanRadarStoreError("stored market snapshot is invalid") from exc


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanOutcomeError("outcome timestamp is invalid") from exc
    return _aware_utc(parsed, "outcome timestamp")


def _aware_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        raise LeanOutcomeError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = (
    "DESCRIPTIVE_MOVE_BAND_PP",
    "FAILED_QUICKLY_BAND_PP",
    "HORIZON_DELTAS",
    "MAX_ENDPOINT_LAG",
    "LeanOutcomeError",
    "pending_outcomes_for_scan",
    "refresh_outcomes",
)
