"""Observational readiness for a future KuCoin announcement capture.

This module reads only the already-present authorization value supplied by the
caller or process environment. It builds the exact bounded request contract but
has no HTTP client, persistence, capture command, or policy integration.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Mapping, Sequence

from .kucoin_announcements import (
    MAX_RESPONSE_PAGES,
    PROVIDER_ID,
    build_kucoin_announcement_request_plan,
)


CONTRACT_VERSION = "crypto_radar_kucoin_announcements_readiness_v1"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_KUCOIN_ANNOUNCEMENTS_LIVE"
READINESS_COMMAND = (
    "make radar-announcements-kucoin-readiness PYTHON=.venv/bin/python"
)
SMOKE_COMMAND = "make radar-announcements-kucoin-smoke PYTHON=.venv/bin/python"
CAPTURE_SMOKE_COMMAND = (
    "make radar-announcements-kucoin-capture-smoke PYTHON=.venv/bin/python"
)
FUTURE_CAPTURE_COMMAND = (
    "unavailable_until_live_transport_and_authorized_capture_command_are_implemented"
)
AUTHORIZATION_ACTION = (
    "none_until_live_transport_and_authorized_capture_command_are_implemented"
)
ROLLBACK_COMMAND = f"unset {LIVE_AUTH_ENV}"
DEFAULT_WINDOW_HOURS = 24
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _enabled(value: object) -> bool:
    return str(value or "").strip().casefold() in _TRUTHY


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("readiness_clock_timezone_missing")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def build_kucoin_announcement_readiness(
    *,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return bounded current readiness without network or filesystem I/O."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    window_start = checked - timedelta(hours=DEFAULT_WINDOW_HOURS)
    plan = build_kucoin_announcement_request_plan(
        start_time=window_start,
        end_time=checked,
    )
    reasons = []
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    reasons.append("live_capture_transport_not_implemented")
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_kucoin_announcements_readiness",
        "status": "blocked",
        "ready": False,
        "checked_at": _iso(checked),
        "provider": PROVIDER_ID,
        "source_class": "official_exchange",
        "provider_contract_configured": True,
        "live_capture_configured": False,
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "authorization_mutated": False,
        "request_window_hours": DEFAULT_WINDOW_HOURS,
        "request_window_start": _iso(window_start),
        "request_window_end": _iso(checked),
        "request_plan": plan,
        "maximum_provider_request_count": MAX_RESPONSE_PAGES,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "provider_request_count": 0,
        "redirects_allowed": False,
        "retries_allowed": False,
        "alternate_hosts_allowed": False,
        "proxy_or_vpn_bypass_allowed": False,
        "exact_response_input_contract_implemented": True,
        "immutable_capture_boundary_implemented": True,
        "capture_command_available": False,
        "strict_capture_doctor_implemented": True,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": reasons,
        "next_safe_command": CAPTURE_SMOKE_COMMAND,
        "response_contract_smoke_command": SMOKE_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "future_capture_command": FUTURE_CAPTURE_COMMAND,
        "operator_action_required": (
            AUTHORIZATION_ACTION
            if not authorized
            else "wait_for_live_capture_transport_implementation"
        ),
        "authorization_boundary": (
            f"future_capture_requires_already_present_{LIVE_AUTH_ENV}=1_and_"
            "explicit_confirmation;readiness_never_creates_or_mutates_authorization"
        ),
        "expected_provider_activity": "none_readiness_only",
        "expected_provider_activity_if_future_authorized_capture_is_implemented": (
            f"between_1_and_{MAX_RESPONSE_PAGES}_public_GETs_no_redirects_or_retries"
        ),
        "rollback_disable_command": ROLLBACK_COMMAND,
        "research_only": True,
        "no_send": True,
        "credentials_read": False,
        "private_data_read": False,
        "writes_performed": False,
        "orders_available": False,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "telegram_sends": 0,
    }


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    print(
        json.dumps(
            build_kucoin_announcement_readiness(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


__all__ = (
    "AUTHORIZATION_ACTION",
    "CAPTURE_SMOKE_COMMAND",
    "CONTRACT_VERSION",
    "FUTURE_CAPTURE_COMMAND",
    "LIVE_AUTH_ENV",
    "READINESS_COMMAND",
    "ROLLBACK_COMMAND",
    "SMOKE_COMMAND",
    "build_kucoin_announcement_readiness",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
