"""Closed diagnostics for campaign outcomes missing primary-horizon prices."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Mapping

from ..outcomes import outcome_eligibility


OutcomeState = Callable[[Mapping[str, Any]], str]


def build_outcome_metrics(
    outcomes: Iterable[Mapping[str, Any]],
    *,
    history_snapshot: Mapping[str, Any] | None,
    outcome_state: OutcomeState,
) -> dict[str, Any]:
    """Summarize canonical outcome state and optionally attach exact price gaps."""

    materialized = list(outcomes)
    counts: Counter[str] = Counter(outcome_state(row) for row in materialized)
    refresh_errors: Counter[str] = Counter()
    for row in materialized:
        errors = row.get("campaign_outcome_refresh_errors")
        if isinstance(errors, (list, tuple)):
            refresh_errors.update(_text(value) for value in errors if _text(value))
    has_ledger = any(row.get("campaign_outcome_ledger") is True for row in materialized)
    has_candidate_base = any(
        row.get("campaign_outcome_source") == "canonical_candidate_pending_base"
        for row in materialized
    )
    source = (
        "canonical_candidate_pending_base_plus_campaign_ledger"
        if has_ledger and has_candidate_base
        else "campaign_outcome_ledger"
        if has_ledger
        else "canonical_candidate_pending_base"
    )
    metrics = {
        "total": len(materialized),
        "pending": counts["not_due"],
        "matured": counts["matured"],
        "missing_data": counts["due_missing_price"],
        "not_due": counts["not_due"],
        "due_missing_price": counts["due_missing_price"],
        "other": counts["other"],
        "status_counts": dict(sorted(counts.items())),
        "source": source,
        "refresh_build_error_count": sum(refresh_errors.values()),
        "refresh_build_error_counts": dict(sorted(refresh_errors.items())),
        "human_feedback_optional": True,
        "automatic_threshold_changes": False,
    }
    if history_snapshot is None:
        return metrics
    price_gap_details = build_due_missing_price_details(
        materialized,
        history_snapshot=history_snapshot,
        outcome_state=outcome_state,
    )
    history = _mapping(history_snapshot)
    metrics.update({
        "due_missing_price_detail_count": len(price_gap_details),
        "due_missing_price_details": price_gap_details,
        "price_history_snapshot": {
            "status": _text(history.get("status")) or "not_supplied",
            "artifact": history.get("artifact"),
            "sha256": history.get("sha256"),
            "row_count": _int(history.get("row_count")),
            "binding_source": history.get("binding_source"),
        },
    })
    return metrics


def build_due_missing_price_details(
    outcomes: Iterable[Mapping[str, Any]],
    *,
    history_snapshot: Mapping[str, Any] | None,
    outcome_state: OutcomeState,
) -> list[dict[str, Any]]:
    """Explain each due primary outcome without manufacturing a price."""

    snapshot = _mapping(history_snapshot)
    history_status = _text(snapshot.get("status")) or "not_supplied"
    supplied_rows = snapshot.get("rows")
    history_rows = (
        tuple(row for row in supplied_rows if isinstance(row, Mapping))
        if isinstance(supplied_rows, (list, tuple))
        else ()
    )
    details: list[dict[str, Any]] = []
    for source in outcomes:
        if outcome_state(source) != "due_missing_price":
            continue
        row = dict(source)
        primary = row.get("primary_horizon")
        metadata = row.get("horizon_metadata")
        primary_metadata = (
            metadata.get(primary)
            if isinstance(metadata, Mapping) and type(primary) is str
            else None
        )
        due = (
            outcome_eligibility.parse_aware_time(primary_metadata.get("due_at"))
            if isinstance(primary_metadata, Mapping)
            else None
        )
        lag_seconds = (
            min(outcome_eligibility.OUTCOME_HORIZON_SECONDS[primary], 24 * 60 * 60)
            if type(primary) is str
            and primary in outcome_eligibility.OUTCOME_HORIZON_SECONDS
            else None
        )
        allowed_latest = (
            due + timedelta(seconds=lag_seconds)
            if due is not None and lag_seconds is not None
            else None
        )
        observations = _asset_price_observations(row, history_rows)
        used_ids = _used_outcome_price_ids(row)
        before_due = (
            [value for value in observations if due is not None and value[0] < due]
            if due is not None
            else []
        )
        after_due = (
            [value for value in observations if due is not None and value[0] >= due]
            if due is not None
            else []
        )
        qualifying = (
            [
                value
                for value in after_due
                if allowed_latest is not None
                and value[0] <= allowed_latest
                and value[1] not in used_ids
            ]
            if allowed_latest is not None
            else []
        )
        last_before = before_due[-1] if before_due else None
        first_after = after_due[0] if after_due else None
        resolution_status = _resolution_status(
            history_status=history_status,
            due=due,
            allowed_latest=allowed_latest,
            qualifying=qualifying,
            first_after=first_after,
        )
        first_after_lag = (
            (first_after[0] - due).total_seconds()
            if first_after is not None and due is not None
            else None
        )
        beyond_window = (
            max(0.0, (first_after[0] - allowed_latest).total_seconds())
            if first_after is not None and allowed_latest is not None
            else None
        )
        details.append({
            "outcome_identity_key": row.get("outcome_identity_key"),
            "source_artifact_namespace": row.get("source_artifact_namespace"),
            "candidate_id": row.get("candidate_id"),
            "core_opportunity_id": row.get("core_opportunity_id"),
            "symbol": row.get("symbol"),
            "coin_id": row.get("coin_id"),
            "observed_at": row.get("observed_at"),
            "primary_horizon": primary,
            "due_at": outcome_eligibility.iso_utc(due) if due is not None else None,
            "allowed_lag_seconds": lag_seconds,
            "allowed_latest_price_at": (
                outcome_eligibility.iso_utc(allowed_latest)
                if allowed_latest is not None
                else None
            ),
            "outcome_evaluated_at": row.get("outcome_evaluated_at"),
            "qualifying_price_observation_count": len(qualifying),
            "last_retained_price_before_due": _price_gap_observation(
                last_before,
                relative_to=due,
            ),
            "first_retained_price_after_due": _price_gap_observation(
                first_after,
                relative_to=due,
            ),
            "first_post_due_lag_seconds": first_after_lag,
            "seconds_beyond_allowed_window": beyond_window,
            "resolution_status": resolution_status,
            "ledger_refresh_can_resolve_from_retained_history": bool(qualifying),
            "historical_point_in_time_evidence_required": not bool(qualifying),
            "interpolation_permitted": False,
            "automatic_threshold_change_permitted": False,
            "research_only": True,
        })
    return sorted(
        details,
        key=lambda row: (
            _text(row.get("due_at")),
            _text(row.get("source_artifact_namespace")),
            _text(row.get("candidate_id")),
        ),
    )


def _resolution_status(
    *,
    history_status: str,
    due: datetime | None,
    allowed_latest: datetime | None,
    qualifying: list[tuple[datetime, str, str]],
    first_after: tuple[datetime, str, str] | None,
) -> str:
    if history_status not in {"observed", "observed_empty"}:
        return "price_history_unavailable"
    if due is None or allowed_latest is None:
        return "outcome_contract_invalid"
    if qualifying:
        return "qualifying_price_available_ledger_refresh_required"
    if first_after is None:
        return "no_post_due_price_retained"
    if first_after[0] > allowed_latest:
        return "first_post_due_price_outside_allowed_window"
    return "post_due_prices_already_allocated_to_other_horizons"


def _asset_price_observations(
    outcome: Mapping[str, Any],
    history_rows: Iterable[Mapping[str, Any]],
) -> list[tuple[datetime, str, str]]:
    coin_id = _text(outcome.get("coin_id"))
    symbol = _text(outcome.get("symbol"))
    if not coin_id or not symbol:
        return []
    observations: list[tuple[datetime, str, str]] = []
    for row in history_rows:
        if (
            _text(row.get("coin_id") or row.get("canonical_asset_id")) != coin_id
            or _text(row.get("symbol")) != symbol
        ):
            continue
        observed_at = outcome_eligibility.parse_aware_time(row.get("observed_at"))
        price = outcome_eligibility.finite_number(row.get("price"))
        observation_id = _text(row.get("observation_id"))
        source = _text(row.get("source") or row.get("provider"))
        if (
            observed_at is None
            or price is None
            or price <= 0
            or not observation_id
            or not source
        ):
            continue
        observations.append((observed_at, observation_id, source))
    return sorted(observations, key=lambda value: (value[0], value[2], value[1]))


def _used_outcome_price_ids(row: Mapping[str, Any]) -> set[str]:
    used = {_text(row.get("observation_price_id"))}
    metadata = row.get("horizon_metadata")
    if isinstance(metadata, Mapping):
        for value in metadata.values():
            if isinstance(value, Mapping):
                used.add(_text(value.get("price_observation_id")))
    used.discard("")
    return used


def _price_gap_observation(
    value: tuple[datetime, str, str] | None,
    *,
    relative_to: datetime | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    observed_at, observation_id, source = value
    return {
        "observed_at": outcome_eligibility.iso_utc(observed_at),
        "observation_id": observation_id,
        "source": source,
        "seconds_from_due": (
            (observed_at - relative_to).total_seconds()
            if relative_to is not None
            else None
        ),
    }


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = ("build_due_missing_price_details", "build_outcome_metrics")
