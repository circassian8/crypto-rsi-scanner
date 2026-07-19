"""Static non-activating readiness for future Tokenomist v5 acquisition.

The current project closes only the synthetic response and immutable fixture
capture contracts.  This readiness surface reads only one dedicated boolean
authorization flag, never a credential value, file, provider, pointer, or
campaign state, and can never authorize or start a live request.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from typing import Mapping
from typing import Sequence

from ...event_providers.tokenomist_v5 import (
    ENDPOINT_HOST,
    ENDPOINT_PREFIX,
    MAX_PAGE_SIZE,
    MAX_RESPONSE_ROWS,
)
from .tokenomist_v5_capture import CONTRACT_VERSION as CAPTURE_CONTRACT_VERSION


CONTRACT_VERSION = "crypto_radar_tokenomist_v5_readiness_v1"
READINESS_COMMAND = "make radar-unlock-tokenomist-v5-readiness PYTHON=.venv/bin/python"
RESPONSE_SMOKE_COMMAND = "make radar-unlock-tokenomist-v5-smoke PYTHON=.venv/bin/python"
CAPTURE_SMOKE_COMMAND = (
    "make radar-unlock-tokenomist-v5-capture-smoke PYTHON=.venv/bin/python"
)
FUTURE_CAPTURE_COMMAND = (
    "unavailable_until_subscription_authorization_retention_and_live_transport_are_approved"
)
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_TOKENOMIST_V5_LIVE"
ROLLBACK_COMMAND = f"unset {LIVE_AUTH_ENV}"
BLOCKERS = (
    "live_transport_not_implemented",
    "provider_subscription_not_selected_or_authorized",
    "genuine_response_retention_and_redistribution_review_pending",
)
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("readiness_clock_timezone_missing")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _enabled(value: object) -> bool:
    return str(value or "").strip().casefold() in _TRUTHY


def build_tokenomist_v5_readiness(
    *,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Read one dedicated boolean authorization flag and remain fail-closed."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    blockers = list(BLOCKERS)
    if not authorized:
        blockers.insert(1, "runtime_provider_authorization_absent")
    return {
        "contract_version": CONTRACT_VERSION,
        "capture_contract_version": CAPTURE_CONTRACT_VERSION,
        "row_type": "decision_radar_tokenomist_v5_readiness",
        "status": "blocked",
        "ready": False,
        "checked_at": _iso(checked),
        "provider": "tokenomist",
        "provider_api_version": "v5",
        "legacy_provider_api_version": "v4",
        "legacy_v4_status": "deprecated",
        "legacy_v4_live_eligible": False,
        "source_class": "structured_unlock",
        "documented_endpoint_host": ENDPOINT_HOST,
        "documented_token_path_prefix": ENDPOINT_PREFIX,
        "response_page_size_bound": MAX_PAGE_SIZE,
        "response_row_bound_per_page": MAX_RESPONSE_ROWS,
        "response_contract_implemented": True,
        "fixture_capture_contract_implemented": True,
        "strict_fixture_capture_doctor_implemented": True,
        "offline_capture_smoke_available": True,
        "completion_evidence": {
            "v5_response_contract": "fixture_closed",
            "v5_immutable_capture_contract": "fixture_closed_strict_doctor",
            "live_transport": "not_implemented",
            "genuine_provider_capture": "absent",
        },
        "capture_mode_available": "offline_fixture_only",
        "live_transport_implemented": False,
        "live_capture_command_available": False,
        "provider_subscription_status": "not_selected_or_authorized",
        "subscription_terms_reviewed": False,
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_authorization_boundary_defined": True,
        "runtime_provider_authorized": authorized,
        "authorization_checked": True,
        "authorization_mutated": False,
        "retention_terms_reviewed": False,
        "redistribution_terms_reviewed": False,
        "genuine_provider_bytes_retention_allowed": False,
        "genuine_provider_bytes_standard_export_allowed": False,
        "request_plan_created": False,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "provider_request_count": 0,
        "environment_reads": 1,
        "environment_authorization_reads": 1,
        "environment_credential_reads": 0,
        "credential_presence_inspected": False,
        "credential_values_read": False,
        "writes_performed": False,
        "latest_pointer_available": False,
        "latest_pointer_published": False,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "source_authority_eligible": False,
        "directional_authority": False,
        "decision_policy_applied": False,
        "context_only": True,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "blockers": blockers,
        "next_safe_command": CAPTURE_SMOKE_COMMAND,
        "response_contract_smoke_command": RESPONSE_SMOKE_COMMAND,
        "capture_smoke_command": CAPTURE_SMOKE_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "future_capture_command": FUTURE_CAPTURE_COMMAND,
        "operator_action_required": (
            "select_and_approve_subscription_then_review_retention_and_redistribution_"
            "terms_then_implement_a_bounded_live_transport_before_using_the_dedicated_"
            "authorization_boundary"
        ),
        "authorization_boundary": (
            f"future_live_capture_requires_already_present_{LIVE_AUTH_ENV}=1_and_"
            "explicit_confirmation;readiness_never_creates_or_mutates_authorization"
        ),
        "expected_provider_activity": "none_readiness_only",
        "rollback_disable_command": ROLLBACK_COMMAND,
        "research_only": True,
        "no_send": True,
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
    print(json.dumps(build_tokenomist_v5_readiness(), indent=2, sort_keys=True))
    return 0


__all__ = (
    "BLOCKERS",
    "CAPTURE_SMOKE_COMMAND",
    "CONTRACT_VERSION",
    "FUTURE_CAPTURE_COMMAND",
    "LIVE_AUTH_ENV",
    "READINESS_COMMAND",
    "RESPONSE_SMOKE_COMMAND",
    "ROLLBACK_COMMAND",
    "build_tokenomist_v5_readiness",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
