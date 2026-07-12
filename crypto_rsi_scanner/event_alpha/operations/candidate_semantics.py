"""Explicit candidate review-state semantics for operating reports."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any

from ..radar import near_miss as event_near_miss
from . import common


CandidatePredicate = Callable[[Mapping[str, Any]], bool]

_NEAR_MISS_VALUES = frozenset(
    {
        "near_miss",
        "near-miss",
        "near_miss_core",
        "research_review_near_miss",
        "near-miss cards",
    }
)
_QUALITY_CAP_VALUES = frozenset(
    {
        "quality_capped",
        "quality-capped",
        "local-only / quality-capped cards",
    }
)
_EXPLICIT_STATE_FIELDS = (
    "review_state",
    "review_bucket",
    "item_type",
    "state_quality_classification",
    "card_group",
    "review_group",
)


def opportunity_identity(row: Mapping[str, Any]) -> str:
    """Return a stable identity without guessing equivalence across representations."""

    core_identity = core_observation_identity(row)
    if core_identity:
        return core_identity
    row_type = _text(row.get("row_type")) or "untyped"
    for field in (
        "core_opportunity_id",
        "canonical_core_opportunity_id",
        "feedback_target",
        "candidate_id",
        "alert_key",
        "alert_id",
        "snapshot_id",
        "near_miss_id",
        "feedback_id",
        "id",
    ):
        value = _text(row.get(field))
        if value:
            return f"row:{row_type}:{field}:{value}"
    return ""


def core_observation_identity(row: Mapping[str, Any]) -> str:
    """Identify one Core observation without collapsing the same Core across runs."""

    core_id = _first_exact_identity(
        row,
        "core_opportunity_id",
        "canonical_core_opportunity_id",
    )
    if not core_id and _text(row.get("feedback_target_type")).casefold() == "core_opportunity_id":
        core_id = _exact_identity_part(row.get("feedback_target"))
    authority = (
        _exact_identity_part(row.get("run_id")),
        _exact_identity_part(row.get("profile")),
        _exact_identity_part(row.get("artifact_namespace")),
        core_id,
    )
    if not all(authority):
        return ""
    return "core_observation:" + json.dumps(
        authority,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def latest_authoritative_core_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Select the latest row for each exact run/profile/namespace/Core authority."""

    selected: dict[str, tuple[datetime, dict[str, Any] | None]] = {}
    for raw in rows:
        row = dict(raw)
        if _text(row.get("row_type")) != "event_core_opportunity":
            continue
        identity = core_observation_identity(row)
        observed_at = common.parse_aware_utc(row.get("generated_at"))
        if not identity or observed_at is None:
            continue
        prior = selected.get(identity)
        if prior is None or observed_at > prior[0]:
            selected[identity] = (observed_at, row)
        elif observed_at == prior[0] and prior[1] is not None and row != prior[1]:
            selected[identity] = (observed_at, None)
    return [item[1] for item in selected.values() if item[1] is not None]


def matching_opportunity_identities(
    rows: Iterable[Mapping[str, Any]],
    predicate: CandidatePredicate,
) -> set[str]:
    """Return deduplicated identities for rows matching an explicit predicate."""

    return {
        identity
        for row in rows
        if predicate(row) and (identity := opportunity_identity(row))
    }


def review_cohort_counts(
    core_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, int]:
    """Count exact Core near-miss/quality cohorts and joined near-miss labels."""

    cores = latest_authoritative_core_rows(core_rows)
    near_misses = matching_opportunity_identities(
        cores,
        lambda row: is_deterministic_core_near_miss(row, evaluated_at=evaluated_at),
    )
    quality_capped = matching_opportunity_identities(
        cores,
        is_authoritative_core_quality_cap,
    )
    labeled = {
        identity
        for row in feedback_rows
        if (identity := opportunity_identity(row)) and identity in near_misses
    }
    return {
        "core_opportunities": len(cores),
        "labeled_near_misses": len(labeled),
        "near_misses": len(near_misses),
        "quality_capped": len(quality_capped),
    }


def is_explicit_near_miss(row: Mapping[str, Any]) -> bool:
    """Recognize only explicit near-miss fields, never arbitrary row text."""

    if row.get("is_near_miss") is True or _text(row.get("near_miss_id")):
        return True
    return any(
        _text(row.get(field)).casefold() in _NEAR_MISS_VALUES
        for field in _EXPLICIT_STATE_FIELDS
    )


def is_deterministic_core_near_miss(
    row: Mapping[str, Any],
    *,
    evaluated_at: datetime | None = None,
) -> bool:
    """Apply the canonical deterministic near-miss classifier to Core authority."""

    if _text(row.get("row_type")) != "event_core_opportunity":
        return False
    if not core_observation_identity(row):
        return False
    try:
        return event_near_miss.near_miss_metadata_for_row(
            row,
            now=evaluated_at,
        ) is not None
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
        return False


def is_explicit_quality_cap(row: Mapping[str, Any]) -> bool:
    """Recognize authoritative quality-cap state, never requested state or prose."""

    if row.get("state_quality_capped") is True or row.get("quality_capped") is True:
        return True
    if _text(row.get("quality_state_block_reason")):
        return True
    if _text(row.get("final_state_after_quality_gate")).upper() == "QUALITY_BLOCKED":
        return True
    return any(
        _text(row.get(field)).casefold() in _QUALITY_CAP_VALUES
        for field in _EXPLICIT_STATE_FIELDS
    )


def is_authoritative_core_quality_cap(row: Mapping[str, Any]) -> bool:
    """Return whether an exact Core observation carries an authoritative quality cap."""

    return bool(
        _text(row.get("row_type")) == "event_core_opportunity"
        and core_observation_identity(row)
        and (
            row.get("state_quality_capped") is True
            or _text(row.get("final_state_after_quality_gate")).upper()
            == "QUALITY_BLOCKED"
        )
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _exact_identity_part(value: Any) -> str:
    """Accept only canonical non-empty strings; never coerce or normalize ids."""

    if type(value) is not str or not value or value != value.strip():
        return ""
    return value


def _first_exact_identity(row: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = row.get(field)
        if value in (None, ""):
            continue
        return _exact_identity_part(value)
    return ""


__all__ = (
    "core_observation_identity",
    "is_authoritative_core_quality_cap",
    "is_deterministic_core_near_miss",
    "is_explicit_near_miss",
    "is_explicit_quality_cap",
    "latest_authoritative_core_rows",
    "matching_opportunity_identities",
    "opportunity_identity",
    "review_cohort_counts",
)
