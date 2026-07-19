"""Closed full-set freshness projection for sequential Bybit order books."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence

from .bybit_execution_quality import DEFAULT_FRESHNESS_SECONDS
from .bybit_execution_quality_capture_models import BybitCapturedJSONResponse


FRESHNESS_POLICY = "every_book_fresh_at_capture_completion"
MAXIMUM_AGE_SECONDS = DEFAULT_FRESHNESS_SECONDS


class _BybitExecutionQualitySetFreshnessError(RuntimeError):
    """Raised when an execution-quality set cannot prove its provider clocks."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class BybitExecutionQualitySetFreshness:
    """One conservative freshness result for a completed sequential book set."""

    fresh_at_acquisition: bool
    fresh_at_completion: bool
    maximum_age_at_completion_seconds: float


def _aware_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _BybitExecutionQualitySetFreshnessError(
                "provider_observed_at_invalid"
            ) from exc
    else:
        raise _BybitExecutionQualitySetFreshnessError(
            "provider_observed_at_missing"
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _BybitExecutionQualitySetFreshnessError(
            "provider_observed_at_timezone_missing"
        )
    return parsed.astimezone(timezone.utc)


def project_execution_quality_set_freshness(
    snapshots: Sequence[Mapping[str, object]],
    *,
    completed_at: datetime,
) -> BybitExecutionQualitySetFreshness:
    """Evaluate every provider clock again at full-set completion."""

    completed = _aware_utc(completed_at)
    if not snapshots:
        raise _BybitExecutionQualitySetFreshnessError(
            "execution_quality_snapshot_set_empty"
        )
    ages: list[float] = []
    for snapshot in snapshots:
        observed = _aware_utc(snapshot.get("provider_observed_at"))
        age = (completed - observed).total_seconds()
        if age < -5:
            raise _BybitExecutionQualitySetFreshnessError(
                "provider_observed_at_too_far_in_future"
            )
        ages.append(max(0.0, age))
    acquisition_fresh = all(
        snapshot.get("freshness_status") == "fresh" for snapshot in snapshots
    )
    completion_fresh = acquisition_fresh and all(
        age <= MAXIMUM_AGE_SECONDS for age in ages
    )
    return BybitExecutionQualitySetFreshness(
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

    started = _aware_utc(started_at)
    completed = _aware_utc(completed_at)
    prior_received: datetime | None = None
    for response in responses:
        request_started = _aware_utc(response.request_started_at)
        response_received = _aware_utc(response.response_received_at)
        if (
            request_started < started
            or response_received > completed
            or (prior_received is not None and request_started < prior_received)
        ):
            raise _BybitExecutionQualitySetFreshnessError(
                "captured_response_outside_capture_window"
            )
        prior_received = response_received


def exact_response_acquisition_matches(
    snapshot: Mapping[str, object], response: BybitCapturedJSONResponse
) -> bool:
    """Tie a normalized book to the exact local response-read completion."""

    return _aware_utc(snapshot.get("acquired_at")) == _aware_utc(
        response.response_received_at
    )


def live_summary_freshness_values(
    value: BybitExecutionQualitySetFreshness,
) -> dict[str, object]:
    return {
        "execution_quality_set_freshness_policy": FRESHNESS_POLICY,
        "all_execution_quality_fresh": value.fresh_at_completion,
        "all_execution_quality_fresh_at_acquisition": value.fresh_at_acquisition,
        "all_execution_quality_fresh_at_completion": value.fresh_at_completion,
        "maximum_execution_quality_age_at_completion_seconds": (
            value.maximum_age_at_completion_seconds
        ),
        "maximum_execution_quality_age_policy_seconds": MAXIMUM_AGE_SECONDS,
    }


def prepared_freshness_values(
    value: BybitExecutionQualitySetFreshness,
) -> dict[str, object]:
    result = live_summary_freshness_values(value)
    result.pop("all_execution_quality_fresh")
    result["protocol_v2_input_quality_eligible"] = value.fresh_at_completion
    return result


def observation_freshness_values(
    prepared: Mapping[str, object],
) -> dict[str, object]:
    return {
        "all_fresh": prepared["protocol_v2_input_quality_eligible"],
        "all_fresh_at_acquisition": prepared[
            "all_execution_quality_fresh_at_acquisition"
        ],
        "all_fresh_at_completion": prepared[
            "all_execution_quality_fresh_at_completion"
        ],
        "freshness_policy": prepared["execution_quality_set_freshness_policy"],
        "maximum_age_at_completion_seconds": prepared[
            "maximum_execution_quality_age_at_completion_seconds"
        ],
        "maximum_age_policy_seconds": prepared[
            "maximum_execution_quality_age_policy_seconds"
        ],
    }


def common_freshness_values(prepared: Mapping[str, object]) -> dict[str, object]:
    return {
        key: prepared[key]
        for key in (
            "protocol_v2_input_quality_eligible",
            "all_execution_quality_fresh_at_acquisition",
            "all_execution_quality_fresh_at_completion",
            "execution_quality_set_freshness_policy",
            "maximum_execution_quality_age_at_completion_seconds",
            "maximum_execution_quality_age_policy_seconds",
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
    summary: Mapping[str, object],
    value: BybitExecutionQualitySetFreshness,
) -> bool:
    return _exact_projection_matches(summary, live_summary_freshness_values(value))


def prepared_summary_freshness_matches(
    summary: Mapping[str, object], prepared: Mapping[str, object]
) -> bool:
    expected = common_freshness_values(prepared)
    expected["all_execution_quality_fresh"] = prepared[
        "all_execution_quality_fresh_at_completion"
    ]
    return _exact_projection_matches(summary, expected)


def observation_freshness_matches(
    observation: Mapping[str, object], prepared: Mapping[str, object]
) -> bool:
    return _exact_projection_matches(
        observation, observation_freshness_values(prepared)
    )


def common_freshness_matches(
    artifact: Mapping[str, object], prepared: Mapping[str, object]
) -> bool:
    return _exact_projection_matches(artifact, common_freshness_values(prepared))


def observation_freshness_contract_valid(value: Mapping[str, object]) -> bool:
    expected = {
        "all_fresh": value.get("all_fresh_at_completion"),
        "all_fresh_at_acquisition": value.get("all_fresh_at_acquisition"),
        "all_fresh_at_completion": value.get("all_fresh_at_completion"),
        "freshness_policy": FRESHNESS_POLICY,
        "maximum_age_at_completion_seconds": value.get(
            "maximum_age_at_completion_seconds"
        ),
        "maximum_age_policy_seconds": MAXIMUM_AGE_SECONDS,
    }
    return (
        type(value.get("all_fresh_at_acquisition")) is bool
        and type(value.get("all_fresh_at_completion")) is bool
        and type(value.get("maximum_age_at_completion_seconds")) in {int, float}
        and value["maximum_age_at_completion_seconds"] >= 0
        and _exact_projection_matches(value, expected)
    )


__all__ = (
    "FRESHNESS_POLICY",
    "MAXIMUM_AGE_SECONDS",
    "_BybitExecutionQualitySetFreshnessError",
    "common_freshness_matches",
    "common_freshness_values",
    "exact_response_acquisition_matches",
    "live_summary_freshness_matches",
    "live_summary_freshness_values",
    "observation_freshness_contract_valid",
    "observation_freshness_matches",
    "observation_freshness_values",
    "prepared_freshness_values",
    "prepared_summary_freshness_matches",
    "project_execution_quality_set_freshness",
    "require_exact_response_window",
)
