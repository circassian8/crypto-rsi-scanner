"""Read-only cadence synthesis for Decision Radar campaign reports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from . import market_no_send_campaign_guard
from . import market_no_send_campaign_provider
from ..radar import market_history


def next_observation(
    artifact_base_dir: Path,
    baseline: Mapping[str, Any],
    *,
    evaluated: datetime,
) -> dict[str, Any]:
    """Combine history cadence, durable reservations, and provider backoff."""

    reservation = market_no_send_campaign_guard.assess_campaign_reservation(
        artifact_base_dir,
        checked_at=evaluated,
    )
    provider_backoff = market_no_send_campaign_provider.assess_shared_provider_state(
        artifact_base_dir,
        checked_at=evaluated,
    )
    return synthesize_next_observation(
        baseline,
        reservation,
        provider_backoff,
        evaluated=evaluated,
    )


def synthesize_next_observation(
    baseline: Mapping[str, Any],
    reservation: Mapping[str, Any],
    provider_backoff: Mapping[str, Any],
    *,
    evaluated: datetime,
) -> dict[str, Any]:
    """Combine already-read cadence states without a second state read."""

    history_next = _time(baseline.get("next_eligible_observation_at"))
    reservation_next = _time(reservation.get("next_provider_call_at"))
    provider_next = _time(provider_backoff.get("disabled_until"))
    clocks = tuple(
        value for value in (history_next, reservation_next, provider_next)
        if value is not None
    )
    next_eligible = max(clocks) if clocks else None
    blocking_reasons = [
        reason
        for reason in (
            _text(reservation.get("reason")),
            _text(provider_backoff.get("reason")),
        )
        if reason
    ]
    eligible = (
        reservation.get("allowed") is True
        and provider_backoff.get("allowed") is True
        and (next_eligible is None or evaluated >= next_eligible)
    )
    return {
        "next_eligible_observation_at": _iso(next_eligible),
        "history_next_eligible_observation_at": _iso(history_next),
        "provider_call_reservation_next_at": _iso(reservation_next),
        "provider_backoff_disabled_until": _iso(provider_next),
        "eligible_now": eligible,
        "cadence_status": (
            "eligible"
            if eligible
            else "blocked"
            if blocking_reasons and next_eligible is None
            else "waiting"
        ),
        "blocking_reasons": blocking_reasons,
        "next_safe_operator_command": (
            "make radar-daily-ops-cycle PYTHON=.venv/bin/python"
            if eligible
            else "make radar-daily-ops-readiness PYTHON=.venv/bin/python"
        ),
        "eligible_run_command": "make radar-daily-ops-cycle PYTHON=.venv/bin/python",
        "authorization_rechecked_by_command": True,
        "rapid_cycles_do_not_advance_warmup": True,
    }


def legacy_next_eligible(readiness: Mapping[str, Any]) -> str | None:
    """Preserve the pre-v2 history-only cadence fallback without provider state."""

    newest = _time(
        readiness.get("baseline_newest_counted_observed_at")
        or readiness.get("baseline_newest_observed_at")
    )
    if newest is None:
        return None
    seconds = int(readiness.get("minimum_observation_spacing_seconds") or 0) or int(
        market_history.MarketHistoryConfig().minimum_observation_spacing.total_seconds()
    )
    return (newest + timedelta(seconds=seconds)).isoformat()


def _time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


__all__ = (
    "legacy_next_eligible",
    "next_observation",
    "synthesize_next_observation",
)
