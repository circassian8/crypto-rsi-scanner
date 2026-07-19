"""Observational readiness for a future KuCoin UTA announcement capture.

This module reads only the already-present authorization value supplied by the
caller or process environment.  The implemented v1 fixture contract targets a
legacy endpoint that KuCoin now documents as replaced; this surface therefore
blocks that endpoint from live use and never turns its plan into provider work.
It has no HTTP client, persistence, capture command, or policy integration.
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


CONTRACT_VERSION = "crypto_radar_kucoin_announcements_readiness_v2"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_KUCOIN_ANNOUNCEMENTS_LIVE"
CURRENT_ANNOUNCEMENTS_PATH = "/api/ua/v1/market/announcement"
CURRENT_OFFICIAL_API_DOC = (
    "https://www.kucoin.com/docs-new/rest/ua/get-announcements"
)
OFFICIAL_MIGRATION_SOURCE = (
    "https://www.kucoin.com/docs-new/change-log"
)
READINESS_COMMAND = (
    "make radar-announcements-kucoin-readiness PYTHON=.venv/bin/python"
)
SMOKE_COMMAND = "make radar-announcements-kucoin-smoke PYTHON=.venv/bin/python"
CAPTURE_SMOKE_COMMAND = (
    "make radar-announcements-kucoin-capture-smoke PYTHON=.venv/bin/python"
)
FUTURE_CAPTURE_COMMAND = (
    "unavailable_until_current_UTA_contract_live_transport_and_authorized_capture_command_are_implemented"
)
AUTHORIZATION_ACTION = (
    "none_current_UTA_contract_implementation_and_review_required_before_authorization_action"
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
    legacy_plan = build_kucoin_announcement_request_plan(
        start_time=window_start,
        end_time=checked,
    )
    reasons = []
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    reasons.extend(
        (
            "legacy_endpoint_superseded_for_live_use",
            "current_uta_response_contract_not_implemented",
            "live_capture_transport_not_implemented",
        )
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_kucoin_announcements_readiness",
        "status": "blocked",
        "ready": False,
        "checked_at": _iso(checked),
        "provider": PROVIDER_ID,
        "source_class": "official_exchange",
        "provider_contract_configured": False,
        "current_contract": {
            "status": "not_implemented",
            "path": CURRENT_ANNOUNCEMENTS_PATH,
            "official_api_doc": CURRENT_OFFICIAL_API_DOC,
            "request_plan": None,
        },
        "legacy_contract": {
            "status": "fixture_verified_historical_not_live_eligible",
            "path": legacy_plan["path"],
            "contract_version": legacy_plan["contract_version"],
            "request_plan": legacy_plan,
            "official_migration_source": OFFICIAL_MIGRATION_SOURCE,
        },
        "live_capture_configured": False,
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "authorization_mutated": False,
        "request_window_hours": DEFAULT_WINDOW_HOURS,
        "request_window_start": _iso(window_start),
        "request_window_end": _iso(checked),
        "request_plan": None,
        "maximum_provider_request_count": 0,
        "legacy_maximum_provider_request_count": MAX_RESPONSE_PAGES,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "provider_request_count": 0,
        "redirects_allowed": False,
        "retries_allowed": False,
        "alternate_hosts_allowed": False,
        "proxy_or_vpn_bypass_allowed": False,
        "exact_response_input_contract_implemented": False,
        "legacy_exact_response_input_contract_implemented": True,
        "immutable_capture_boundary_implemented": False,
        "legacy_immutable_capture_boundary_implemented": True,
        "capture_command_available": False,
        "strict_capture_doctor_implemented": False,
        "legacy_strict_capture_doctor_implemented": True,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": reasons,
        "next_safe_command": READINESS_COMMAND,
        "legacy_capture_smoke_command": CAPTURE_SMOKE_COMMAND,
        "legacy_response_contract_smoke_command": SMOKE_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "future_capture_command": FUTURE_CAPTURE_COMMAND,
        "operator_action_required": (
            AUTHORIZATION_ACTION
            if not authorized
            else "unset_unreviewed_authorization_and_wait_for_current_UTA_contract_implementation"
        ),
        "authorization_boundary": (
            "the_legacy_v1_endpoint_is_not_live_eligible;future_current_UTA_capture_"
            f"requires_already_present_{LIVE_AUTH_ENV}=1_and_explicit_confirmation;"
            "readiness_never_creates_or_mutates_authorization"
        ),
        "expected_provider_activity": "none_readiness_only",
        "expected_provider_activity_if_future_authorized_capture_is_implemented": (
            "unknown_until_the_current_UTA_request_and_pagination_contract_is_closed"
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
    "CURRENT_ANNOUNCEMENTS_PATH",
    "CURRENT_OFFICIAL_API_DOC",
    "FUTURE_CAPTURE_COMMAND",
    "LIVE_AUTH_ENV",
    "OFFICIAL_MIGRATION_SOURCE",
    "READINESS_COMMAND",
    "ROLLBACK_COMMAND",
    "SMOKE_COMMAND",
    "build_kucoin_announcement_readiness",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
