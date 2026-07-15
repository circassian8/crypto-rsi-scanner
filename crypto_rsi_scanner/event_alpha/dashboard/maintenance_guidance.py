"""Pure dashboard guidance for an expiring, manually maintained authority."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Mapping

from ... import config
from ..operations import daily_operations_current_status


APPROACHING_EXPIRY_SECONDS = 90 * 60


def maintenance_expiry_guidance(snapshot: Any) -> dict[str, object]:
    """Return one non-mutating manual action only when all trigger facts hold."""

    service = _mapping(getattr(snapshot, "maintenance_service", {}))
    state = _mapping(getattr(snapshot, "maintenance_state", {}))
    current = _mapping(getattr(snapshot, "maintenance_current_status", {}))
    now = _aware_timestamp(
        getattr(snapshot, "generation_authority_checked_at", None)
    )
    expiry = _authority_expiry(_mapping(getattr(snapshot, "operator_state", {})))
    next_eligible = _aware_timestamp(
        current.get("next_eligible_observation_at")
        or state.get("next_eligible_observation_at")
    )
    scheduler_enabled = current.get("scheduler_enabled")
    if not isinstance(scheduler_enabled, bool):
        scheduler_enabled = state.get("scheduler_enabled")
    if not isinstance(scheduler_enabled, bool):
        scheduler_enabled = service.get("enabled")
    if (
        now is None
        or expiry is None
        or next_eligible is None
        or scheduler_enabled is not False
        or next_eligible > now
    ):
        return {"active": False}
    seconds = int((expiry - now).total_seconds())
    if not 0 < seconds <= APPROACHING_EXPIRY_SECONDS:
        return {"active": False}
    return {
        "active": True,
        "authority_expires_at": expiry.isoformat(),
        "time_until_expiry_seconds": seconds,
        "maintenance_disabled": True,
        "safe_manual_readiness_command": daily_operations_current_status.READINESS_COMMAND,
        "installation_command": daily_operations_current_status.INSTALL_COMMAND,
        "rollback_disable_command": daily_operations_current_status.DISABLE_COMMAND,
        "installation_requires_confirmation": True,
        "provider_activity": (
            "Readiness performs no provider call. A separately invoked eligible cycle may "
            "attempt at most one already-authorized bounded CoinGecko request."
        ),
    }


def _authority_expiry(operator_state: Mapping[str, Any]) -> datetime | None:
    started = _aware_timestamp(
        operator_state.get("run_started_at") or operator_state.get("generated_at")
    )
    if started is None:
        return None
    try:
        hours = float(config.EVENT_ALPHA_MAX_RUN_AGE_HOURS)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(hours) or hours <= 0:
        return None
    return started + timedelta(hours=hours)


def _aware_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = (
    "APPROACHING_EXPIRY_SECONDS",
    "maintenance_expiry_guidance",
)
