"""Closed set freshness for sequential Bybit derivatives contexts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Mapping, Sequence

from .bybit_derivatives_context import (
    DEFAULT_FRESHNESS_SECONDS,
    MAX_PROVIDER_CLOCK_SKEW_SECONDS,
)
from .bybit_execution_quality_capture_models import BybitCapturedJSONResponse


SET_FRESHNESS_POLICY = "every_composite_context_fresh_at_capture_completion"
MAXIMUM_CONTEXT_AGE_SECONDS = DEFAULT_FRESHNESS_SECONDS
COMMON_FRESHNESS_FIELDS = (
    "all_context_fresh",
    "all_context_fresh_at_acquisition",
    "all_context_fresh_at_completion",
    "derivatives_set_freshness_policy",
    "maximum_context_age_at_completion_seconds",
    "maximum_context_age_policy_seconds",
    "protocol_v2_input_quality_eligible",
)


class _BybitDerivativesContextSetFreshnessError(RuntimeError):
    """Raised when a derivatives set cannot prove its completion-time state."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class BybitDerivativesContextSetFreshness:
    """One conservative result for a completed derivatives context set."""

    fresh_at_acquisition: bool
    fresh_at_completion: bool
    maximum_age_at_completion_seconds: float


def _aware_utc(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _BybitDerivativesContextSetFreshnessError(
                f"{field}_invalid"
            ) from exc
    else:
        raise _BybitDerivativesContextSetFreshnessError(f"{field}_missing")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _BybitDerivativesContextSetFreshnessError(
            f"{field}_timezone_missing"
        )
    return parsed.astimezone(timezone.utc)


def project_derivatives_context_set_freshness(
    contexts: Sequence[Mapping[str, object]],
    *,
    completed_at: datetime,
) -> BybitDerivativesContextSetFreshness:
    """Re-evaluate every oldest-component provider clock at completion."""

    completed = _aware_utc(completed_at, "capture_completed_at")
    if not contexts:
        raise _BybitDerivativesContextSetFreshnessError(
            "derivatives_context_set_empty"
        )
    ages: list[float] = []
    for context in contexts:
        observed = _aware_utc(
            context.get("provider_observed_at"), "provider_observed_at"
        )
        acquired = _aware_utc(context.get("acquired_at"), "acquired_at")
        if acquired > completed or observed > acquired:
            skew = (observed - acquired).total_seconds()
            if acquired > completed or skew > MAX_PROVIDER_CLOCK_SKEW_SECONDS:
                raise _BybitDerivativesContextSetFreshnessError(
                    "derivatives_context_completion_clock_invalid"
                )
        age = (completed - observed).total_seconds()
        if age < -MAX_PROVIDER_CLOCK_SKEW_SECONDS:
            raise _BybitDerivativesContextSetFreshnessError(
                "provider_observed_at_too_far_in_future"
            )
        ages.append(max(0.0, age))
    acquisition_fresh = all(
        context.get("freshness_status") == "fresh" for context in contexts
    )
    completion_fresh = acquisition_fresh and all(
        age <= MAXIMUM_CONTEXT_AGE_SECONDS for age in ages
    )
    return BybitDerivativesContextSetFreshness(
        fresh_at_acquisition=acquisition_fresh,
        fresh_at_completion=completion_fresh,
        maximum_age_at_completion_seconds=round(max(ages), 6),
    )


def require_exact_response_window(
    responses: Sequence[BybitCapturedJSONResponse],
    *,
    started_at: datetime,
    completed_at: datetime,
) -> None:
    """Require one ordered exact transport sequence inside the capture window."""

    started = _aware_utc(started_at, "capture_started_at")
    completed = _aware_utc(completed_at, "capture_completed_at")
    prior_received: datetime | None = None
    for response in responses:
        request_started = _aware_utc(
            response.request_started_at, "request_started_at"
        )
        response_received = _aware_utc(
            response.response_received_at, "response_received_at"
        )
        if (
            request_started < started
            or response_received < request_started
            or response_received > completed
            or (prior_received is not None and request_started < prior_received)
        ):
            raise _BybitDerivativesContextSetFreshnessError(
                "captured_response_outside_capture_window"
            )
        prior_received = response_received


def live_summary_freshness_values(
    value: BybitDerivativesContextSetFreshness,
) -> dict[str, object]:
    return {
        "all_context_fresh": value.fresh_at_completion,
        "all_context_fresh_at_acquisition": value.fresh_at_acquisition,
        "all_context_fresh_at_completion": value.fresh_at_completion,
        "derivatives_set_freshness_policy": SET_FRESHNESS_POLICY,
        "maximum_context_age_at_completion_seconds": (
            value.maximum_age_at_completion_seconds
        ),
        "maximum_context_age_policy_seconds": MAXIMUM_CONTEXT_AGE_SECONDS,
    }


def common_freshness_values(
    prepared: Mapping[str, object],
) -> dict[str, object]:
    return {key: prepared[key] for key in COMMON_FRESHNESS_FIELDS}


def _exact_projection_matches(
    actual: Mapping[str, object], expected: Mapping[str, object]
) -> bool:
    return all(
        key in actual
        and type(actual[key]) is type(expected_value)
        and actual[key] == expected_value
        for key, expected_value in expected.items()
    )


def live_summary_freshness_matches(
    summary: Mapping[str, object], value: BybitDerivativesContextSetFreshness
) -> bool:
    return _exact_projection_matches(summary, live_summary_freshness_values(value))


def common_freshness_matches(
    artifact: Mapping[str, object], prepared: Mapping[str, object]
) -> bool:
    return _exact_projection_matches(artifact, common_freshness_values(prepared))


def freshness_contract_valid(value: Mapping[str, object]) -> bool:
    acquisition = value.get("all_context_fresh_at_acquisition")
    completion = value.get("all_context_fresh_at_completion")
    maximum_age = value.get("maximum_context_age_at_completion_seconds")
    expected = {
        "all_context_fresh": completion,
        "all_context_fresh_at_acquisition": acquisition,
        "all_context_fresh_at_completion": completion,
        "derivatives_set_freshness_policy": SET_FRESHNESS_POLICY,
        "maximum_context_age_at_completion_seconds": maximum_age,
        "maximum_context_age_policy_seconds": MAXIMUM_CONTEXT_AGE_SECONDS,
        "protocol_v2_input_quality_eligible": completion,
    }
    return (
        type(acquisition) is bool
        and type(completion) is bool
        and type(maximum_age) is float
        and math.isfinite(maximum_age)
        and maximum_age >= 0
        and (not completion or acquisition)
        and (not completion or maximum_age <= MAXIMUM_CONTEXT_AGE_SECONDS)
        and _exact_projection_matches(value, expected)
    )


__all__ = (
    "COMMON_FRESHNESS_FIELDS",
    "MAXIMUM_CONTEXT_AGE_SECONDS",
    "SET_FRESHNESS_POLICY",
    "_BybitDerivativesContextSetFreshnessError",
    "common_freshness_matches",
    "common_freshness_values",
    "freshness_contract_valid",
    "live_summary_freshness_matches",
    "live_summary_freshness_values",
    "project_derivatives_context_set_freshness",
    "require_exact_response_window",
)
