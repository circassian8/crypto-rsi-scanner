"""Persist one bounded, credential-free Daily Operations readiness snapshot.

The dashboard reads this receipt instead of inspecting process environment
variables.  Producing it performs no provider call and never creates or changes
authorization.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .market_no_send_io import write_json_atomic


CONTRACT_VERSION = 1
CURRENT_STATUS_FILENAME = "event_radar_daily_operations_current_status.json"
CURRENT_STATUS_TTL_SECONDS = 15 * 60
READINESS_COMMAND = "make radar-daily-ops-readiness PYTHON=.venv/bin/python"
INSTALL_COMMAND = (
    "CONFIRM=1 make radar-daily-ops-install PYTHON=.venv/bin/python"
)
DISABLE_COMMAND = (
    "CONFIRM=1 make radar-daily-ops-uninstall PYTHON=.venv/bin/python"
)


def current_status_values(readiness: Any) -> dict[str, object]:
    """Project an existing readiness result into a closed persisted receipt."""

    checked_at = _aware_timestamp(getattr(readiness, "checked_at", None))
    if checked_at is None:
        raise ValueError("daily operations readiness timestamp is invalid")
    market = getattr(readiness, "market", None)
    dashboard = getattr(readiness, "dashboard", None)
    scheduler = getattr(readiness, "scheduler", None)
    authorized = getattr(market, "live_provider_authorized", None)
    if not isinstance(authorized, bool):
        raise ValueError("daily operations authorization state is invalid")
    call_eligibility = _provider_call_eligibility(readiness)
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_daily_operations_current_status",
        "updated_at": checked_at.isoformat(),
        "current_authorization_status": (
            "authorized" if authorized else "not_authorized"
        ),
        "current_authorization_checked_at": checked_at.isoformat(),
        "current_status_valid_until": (
            checked_at + timedelta(seconds=CURRENT_STATUS_TTL_SECONDS)
        ).isoformat(),
        "current_provider_call_eligibility": call_eligibility,
        "next_eligible_observation_at": getattr(
            market, "next_eligible_observation_at", None
        ),
        "scheduler_enabled": getattr(scheduler, "enabled", None),
        "scheduler_loaded": getattr(scheduler, "loaded", None),
        "scheduler_healthy": getattr(scheduler, "healthy", None),
        "dashboard_owned": getattr(dashboard, "owned", None),
        "readiness_status": _safe_token(getattr(readiness, "status", None)),
        "readiness_reason": _safe_token(getattr(readiness, "reason", None)),
        "safe_manual_readiness_command": READINESS_COMMAND,
        "installation_command": INSTALL_COMMAND,
        "rollback_disable_command": DISABLE_COMMAND,
        "installation_requires_confirmation": True,
        "authorization_boundary": "existing_live_authorization_only",
        "implications": _eligibility_implications(call_eligibility),
        "expected_provider_activity": (
            "readiness_none_cycle_at_most_one_bounded_coingecko_request"
        ),
        "provider_call_attempted": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "no_send": True,
        "research_only": True,
    }


def persist_current_status(
    artifact_base_dir: str | Path,
    readiness: Any,
) -> Path:
    """Write the closed readiness receipt under the already-selected base."""

    base = Path(artifact_base_dir).expanduser().resolve()
    if not base.is_dir():
        raise ValueError("daily operations artifact base is not a directory")
    path = base / CURRENT_STATUS_FILENAME
    write_json_atomic(path, current_status_values(readiness))
    return path


def provider_attempt_state_values(
    *,
    rows: Sequence[Mapping[str, Any]],
    previous: Mapping[str, Any],
) -> dict[str, object]:
    """Project the newest provider-backed terminal cycle into bounded state."""

    latest = next(
        (
            row
            for row in reversed(rows)
            if row.get("status") in {"succeeded", "failed"}
            and row.get("provider_call_attempted") is True
        ),
        {},
    )
    attempted_at = latest.get("provider_attempted_at")
    if attempted_at is None and latest:
        attempted_at = previous.get("last_attempted_observation")
    return {
        "last_provider_attempt_cycle_id": latest.get("cycle_id"),
        "last_provider_attempt_status": latest.get("status"),
        "last_provider_attempt_reason": latest.get("reason"),
        "last_provider_attempt_namespace": latest.get("artifact_namespace"),
        "last_provider_attempted_at": attempted_at,
        "last_provider_attempt_terminal_at": latest.get("recorded_at"),
        "last_provider_request_succeeded": latest.get(
            "provider_request_succeeded"
        ),
    }


def _provider_call_eligibility(readiness: Any) -> str:
    market = getattr(readiness, "market", None)
    dashboard = getattr(readiness, "dashboard", None)
    if getattr(market, "live_provider_authorized", None) is not True:
        return "blocked_authorization"
    cadence = _safe_token(getattr(market, "cadence_status", None))
    if cadence == "waiting":
        return "waiting_cadence"
    if getattr(dashboard, "owned", None) is not True:
        return "blocked_dashboard_ownership"
    if getattr(readiness, "status", None) == "ready":
        return "eligible"
    reason = _safe_token(getattr(readiness, "reason", None))
    return f"blocked_{reason}" if reason else "blocked_unknown"


def _eligibility_implications(eligibility: str) -> str:
    if eligibility == "eligible":
        return "an_explicit_cycle_may_attempt_one_already_authorized_bounded_request"
    if eligibility == "waiting_cadence":
        return "cadence_blocks_a_provider_request_until_the_persisted_eligible_time"
    if eligibility == "blocked_authorization":
        return "current_authorization_is_absent_and_the_provider_boundary_is_closed"
    if eligibility == "blocked_dashboard_ownership":
        return "dashboard_ownership_must_be_exact_before_a_cycle_can_publish"
    return "the_reported_readiness_blocker_keeps_the_provider_boundary_closed"


def _safe_token(value: object) -> str:
    text = str(value or "").strip().casefold()
    return "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in text
    ).strip("_")[:80]


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


__all__ = (
    "CONTRACT_VERSION",
    "CURRENT_STATUS_FILENAME",
    "CURRENT_STATUS_TTL_SECONDS",
    "DISABLE_COMMAND",
    "INSTALL_COMMAND",
    "READINESS_COMMAND",
    "current_status_values",
    "persist_current_status",
    "provider_attempt_state_values",
)
