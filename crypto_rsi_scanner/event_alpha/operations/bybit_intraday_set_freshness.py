"""Closed full-set freshness projection for sequential Bybit intraday bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence

from .bybit_execution_quality_capture_models import BybitCapturedJSONResponse
from .bybit_intraday import (
    MAX_PROVIDER_CLOCK_SKEW_SECONDS,
    MAX_PROVIDER_RESPONSE_AGE_SECONDS,
)


FRESHNESS_POLICY = "every_bar_fresh_at_capture_completion"
BAR_RECENCY_POLICY = "bar_age_strictly_less_than_interval_seconds"
MAXIMUM_PROVIDER_AGE_SECONDS = MAX_PROVIDER_RESPONSE_AGE_SECONDS


class _BybitIntradaySetFreshnessError(RuntimeError):
    """Raised when an intraday set cannot prove its completion-time state."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class BybitIntradaySetFreshness:
    """One conservative result for a completed sequential intraday set."""

    fresh_at_acquisition: bool
    fresh_at_completion: bool
    maximum_provider_age_at_completion_seconds: float
    minimum_bar_recency_remaining_at_completion_seconds: float


def _aware_utc(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _BybitIntradaySetFreshnessError(f"{field}_invalid") from exc
    else:
        raise _BybitIntradaySetFreshnessError(f"{field}_missing")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _BybitIntradaySetFreshnessError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def project_intraday_set_freshness(
    bars: Sequence[Mapping[str, object]],
    *,
    completed_at: datetime,
) -> BybitIntradaySetFreshness:
    """Re-evaluate every bar and provider clock at full-set completion."""

    completed = _aware_utc(completed_at, "capture_completed_at")
    if not bars:
        raise _BybitIntradaySetFreshnessError("intraday_bar_set_empty")
    provider_ages: list[float] = []
    bar_recency_remaining: list[float] = []
    for bar in bars:
        provider_at = _aware_utc(
            bar.get("provider_response_generated_at"),
            "provider_response_generated_at",
        )
        acquired_at = _aware_utc(
            bar.get("response_acquired_at"), "response_acquired_at"
        )
        bar_end_at = _aware_utc(bar.get("bar_end_at"), "bar_end_at")
        interval_seconds = bar.get("interval_seconds")
        if (
            type(interval_seconds) is not int
            or interval_seconds <= 0
            or acquired_at > completed
            or bar_end_at > acquired_at
        ):
            raise _BybitIntradaySetFreshnessError(
                "intraday_bar_completion_clock_invalid"
            )
        if provider_at > acquired_at:
            provider_skew = (provider_at - acquired_at).total_seconds()
            if provider_skew > MAX_PROVIDER_CLOCK_SKEW_SECONDS:
                raise _BybitIntradaySetFreshnessError(
                    "provider_response_generated_at_too_far_in_future"
                )
        provider_age = (completed - provider_at).total_seconds()
        if provider_age < -MAX_PROVIDER_CLOCK_SKEW_SECONDS:
            raise _BybitIntradaySetFreshnessError(
                "provider_response_generated_at_too_far_in_future"
            )
        provider_ages.append(max(0.0, provider_age))
        bar_age = (completed - bar_end_at).total_seconds()
        if bar_age < 0:
            raise _BybitIntradaySetFreshnessError(
                "intraday_bar_completion_clock_invalid"
            )
        bar_recency_remaining.append(float(interval_seconds) - bar_age)
    acquisition_fresh = all(
        bar.get("freshness_status") == "fresh" for bar in bars
    )
    completion_fresh = (
        acquisition_fresh
        and all(
            age <= MAXIMUM_PROVIDER_AGE_SECONDS for age in provider_ages
        )
        and all(remaining > 0 for remaining in bar_recency_remaining)
    )
    return BybitIntradaySetFreshness(
        fresh_at_acquisition=acquisition_fresh,
        fresh_at_completion=completion_fresh,
        maximum_provider_age_at_completion_seconds=round(
            max(provider_ages), 6
        ),
        minimum_bar_recency_remaining_at_completion_seconds=round(
            min(bar_recency_remaining), 6
        ),
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
            raise _BybitIntradaySetFreshnessError(
                "captured_response_outside_capture_window"
            )
        prior_received = response_received


def live_summary_freshness_values(
    value: BybitIntradaySetFreshness,
) -> dict[str, object]:
    return {
        "all_bars_fresh": value.fresh_at_completion,
        "all_bars_fresh_at_acquisition": value.fresh_at_acquisition,
        "all_bars_fresh_at_completion": value.fresh_at_completion,
        "intraday_set_freshness_policy": FRESHNESS_POLICY,
        "maximum_provider_response_age_at_completion_seconds": (
            value.maximum_provider_age_at_completion_seconds
        ),
        "maximum_provider_response_age_policy_seconds": (
            MAXIMUM_PROVIDER_AGE_SECONDS
        ),
        "minimum_bar_recency_remaining_at_completion_seconds": (
            value.minimum_bar_recency_remaining_at_completion_seconds
        ),
        "bar_recency_policy": BAR_RECENCY_POLICY,
    }


def common_freshness_values(
    prepared: Mapping[str, object],
) -> dict[str, object]:
    return {
        key: prepared[key]
        for key in (
            "all_bars_fresh",
            "all_bars_fresh_at_acquisition",
            "all_bars_fresh_at_completion",
            "intraday_set_freshness_policy",
            "maximum_provider_response_age_at_completion_seconds",
            "maximum_provider_response_age_policy_seconds",
            "minimum_bar_recency_remaining_at_completion_seconds",
            "bar_recency_policy",
            "protocol_v2_input_quality_eligible",
        )
    }


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
    summary: Mapping[str, object], value: BybitIntradaySetFreshness
) -> bool:
    return _exact_projection_matches(summary, live_summary_freshness_values(value))


def common_freshness_matches(
    artifact: Mapping[str, object], prepared: Mapping[str, object]
) -> bool:
    return _exact_projection_matches(artifact, common_freshness_values(prepared))


def freshness_contract_valid(value: Mapping[str, object]) -> bool:
    """Validate the closed aggregate relationship without raw response bytes."""

    acquisition = value.get("all_bars_fresh_at_acquisition")
    completion = value.get("all_bars_fresh_at_completion")
    maximum_age = value.get(
        "maximum_provider_response_age_at_completion_seconds"
    )
    minimum_remaining = value.get(
        "minimum_bar_recency_remaining_at_completion_seconds"
    )
    expected = {
        "all_bars_fresh": completion,
        "all_bars_fresh_at_acquisition": acquisition,
        "all_bars_fresh_at_completion": completion,
        "intraday_set_freshness_policy": FRESHNESS_POLICY,
        "maximum_provider_response_age_at_completion_seconds": maximum_age,
        "maximum_provider_response_age_policy_seconds": (
            MAXIMUM_PROVIDER_AGE_SECONDS
        ),
        "minimum_bar_recency_remaining_at_completion_seconds": (
            minimum_remaining
        ),
        "bar_recency_policy": BAR_RECENCY_POLICY,
        "protocol_v2_input_quality_eligible": completion,
    }
    return (
        type(acquisition) is bool
        and type(completion) is bool
        and type(maximum_age) is float
        and maximum_age >= 0
        and type(minimum_remaining) is float
        and (not completion or acquisition)
        and (
            not completion
            or (
                maximum_age <= MAXIMUM_PROVIDER_AGE_SECONDS
                and minimum_remaining > 0
            )
        )
        and _exact_projection_matches(value, expected)
    )


__all__ = (
    "BAR_RECENCY_POLICY",
    "FRESHNESS_POLICY",
    "MAXIMUM_PROVIDER_AGE_SECONDS",
    "_BybitIntradaySetFreshnessError",
    "common_freshness_matches",
    "common_freshness_values",
    "freshness_contract_valid",
    "live_summary_freshness_matches",
    "live_summary_freshness_values",
    "project_intraday_set_freshness",
    "require_exact_response_window",
)
