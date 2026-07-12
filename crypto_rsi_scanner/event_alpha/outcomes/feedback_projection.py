"""Bounded Decision-v2 and calendar projections for feedback artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def decision_fields(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable Decision-v2 subset persisted with feedback."""

    if not values:
        return {}
    fields = {
        "decision_model_version": _optional_str(values.get("decision_model_version")),
        "decision_model_enabled": bool(values.get("decision_model_enabled", True)),
        "thesis_origin": _optional_str(values.get("thesis_origin")),
        "primary_thesis_origin": _optional_str(values.get("primary_thesis_origin")),
        "thesis_origins": _text_tuple(values.get("thesis_origins")),
        "directional_bias": _optional_str(values.get("directional_bias")),
        "catalyst_status": _optional_str(values.get("catalyst_status")),
        "confidence_band": _optional_str(values.get("confidence_band")),
        "timing_state": _optional_str(values.get("timing_state")),
        "tradability_status": _optional_str(values.get("tradability_status")),
        "spread_status": _optional_str(values.get("spread_status")),
        "radar_route": _optional_str(values.get("radar_route")),
        "radar_route_reason": _optional_str(values.get("radar_route_reason")),
        "radar_actionable": bool(values.get("radar_actionable")),
        "actionability_score": _optional_float(values.get("actionability_score")),
        "evidence_confidence_score": _optional_float(
            values.get("evidence_confidence_score")
        ),
        "risk_score": _optional_float(values.get("risk_score")),
        "urgency_score": _optional_float(values.get("urgency_score")),
        "market_phase": _optional_str(values.get("market_phase")),
        "preferred_horizon": _optional_str(values.get("preferred_horizon")),
        "expires_at": _optional_str(values.get("expires_at")),
        "chase_risk_score": _optional_float(values.get("chase_risk_score")),
        "actionability_score_cohort": _optional_str(
            values.get("actionability_score_cohort")
        ),
        "anomaly_type": _optional_str(values.get("anomaly_type")),
        "actionability_score_components": _optional_mapping(
            values.get("actionability_score_components")
        ),
        "actionability_penalty_components": _optional_mapping(
            values.get("actionability_penalty_components")
        ),
        "evidence_confidence_score_components": _optional_mapping(
            values.get("evidence_confidence_score_components")
            or values.get("evidence_confidence_components")
        ),
        "risk_score_components": _optional_mapping(values.get("risk_score_components")),
        "decision_hard_blockers": _text_tuple(values.get("decision_hard_blockers")),
        "decision_soft_penalties": _text_tuple(values.get("decision_soft_penalties")),
        "decision_missing_data": _text_tuple(values.get("decision_missing_data")),
        "decision_warnings": _text_tuple(values.get("decision_warnings")),
        "why_still_worth_reviewing": _text_tuple(
            values.get("why_still_worth_reviewing")
        ),
        "radar_what_confirms": _text_tuple(values.get("radar_what_confirms")),
        "radar_what_invalidates": _text_tuple(values.get("radar_what_invalidates")),
    }
    for field in (
        "decision_source_side_effect_safety_failed",
        "decision_source_secret_safety_failed",
        "decision_source_path_safety_failed",
    ):
        value = _optional_bool(values.get(field))
        if value is not None:
            fields[field] = value
    return fields


_MINIMAL_CALENDAR_EVENT_FIELDS = (
    "calendar_event_id",
    "event_id",
    "event_kind",
    "importance",
    "scheduled_at",
    "window_start",
    "window_end",
)


def calendar_evidence_fields(*authorities: Mapping[str, Any]) -> dict[str, Any]:
    """Project bounded, independently auditable calendar proof.

    The first authority with stable identity/type/time evidence wins. Titles,
    URLs, and complete provider payloads are deliberately excluded.
    """

    for authority in authorities:
        if not isinstance(authority, Mapping):
            continue
        scheduled_at = _aware_calendar_timestamp(authority.get("scheduled_at"))
        event_rows: list[Mapping[str, Any]] = []
        for field in (
            "nearby_calendar_events",
            "calendar_events",
            "unified_calendar_context",
        ):
            value = authority.get(field)
            if isinstance(value, Iterable) and not isinstance(
                value, (str, bytes, Mapping)
            ):
                event_rows.extend(item for item in value if isinstance(item, Mapping))
        for field in (
            "unified_calendar_event",
            "calendar_event",
            "scheduled_catalyst_event",
            "unlock_event",
        ):
            value = authority.get(field)
            if isinstance(value, Mapping) and value:
                event_rows.append(value)

        minimal_rows = tuple(
            event
            for event in (_minimal_calendar_event(row) for row in event_rows)
            if event
        )
        if scheduled_at is None:
            scheduled_at = next(
                (
                    value
                    for event in minimal_rows
                    if (
                        value := _aware_calendar_timestamp(event.get("scheduled_at"))
                    )
                    is not None
                ),
                None,
            )
        if scheduled_at is not None or minimal_rows:
            return {
                "scheduled_at": scheduled_at,
                "nearby_calendar_events": minimal_rows,
            }
    return {}


def _minimal_calendar_event(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in _MINIMAL_CALENDAR_EVENT_FIELDS:
        value = row.get(field)
        if value in (None, ""):
            continue
        if field in {"scheduled_at", "window_start", "window_end"}:
            timestamp = _aware_calendar_timestamp(value)
            if timestamp is not None:
                out[field] = timestamp
            continue
        if type(value) in (str, int, float, bool):
            out[field] = value
    return out


def _aware_calendar_timestamp(value: Any) -> str | None:
    if type(value) is not str or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (OverflowError, TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_mapping(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, (str, bytes)):
        text = str(value).strip()
        return (text,) if text else ()
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return tuple(
            dict.fromkeys(str(item).strip() for item in value if str(item).strip())
        )
    text = str(value).strip()
    return (text,) if text else ()
