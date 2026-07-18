"""Current Protocol-v2 decision progress beside the immutable readiness contract.

The 2026-07-16 readiness implementation is canonical empirical evidence and is
fingerprinted by the export policy.  This module projects later accepted human
decisions from the static execution-quality readiness contract without changing
that evidence, reading ambient state, or opening the holdout.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence

from crypto_rsi_scanner.event_alpha.operations.empirical_validation_protocol_v2 import (
    CONTRACT_VERSION as FROZEN_CONTRACT_VERSION,
    readiness_sha256,
)
from crypto_rsi_scanner.event_alpha.operations.execution_quality_readiness import (
    build_execution_quality_readiness,
)


SCHEMA_ID = "decision_radar.empirical_protocol_v2_current_progress"
SCHEMA_VERSION = 1
PROGRESS_VERSION = "decision_radar_empirical_protocol_v2_current_progress_v1"
FROZEN_READINESS_SHA256 = (
    "683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603"
)
_CURRENT_BLOCKERS = (
    "exact_eligible_instrument_set_not_sealed",
    "bybit_public_reachability_unproven_after_recorded_403",
    "genuine_execution_quality_capture_absent",
    "genuine_intraday_1h_4h_and_rsi_capture_absent",
    "data_sources_not_sealed",
    "partitions_and_untouched_holdout_not_sealed",
    "outcomes_and_costs_not_sealed",
    "universe_routes_episodes_and_minimum_samples_not_sealed",
    "human_protocol_v2_annex_approval_absent",
)
_SAFETY_ZERO_FIELDS = (
    "provider_calls",
    "credential_reads",
    "environment_reads",
    "file_reads",
    "file_writes",
    "holdout_reads",
    "sends",
    "trades",
    "orders",
    "paper_trades",
    "rsi_writes",
    "event_alpha_fade_triggers",
)


def current_progress_values() -> dict[str, Any]:
    """Return accepted progress derived only from deterministic static contracts."""

    execution = build_execution_quality_readiness()
    frozen_digest = readiness_sha256()
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "progress_version": PROGRESS_VERSION,
        "as_of": "2026-07-18",
        "status": "venue_selected_evidence_collection_blocked",
        "source": "accepted_human_decisions_after_frozen_readiness_contract",
        "frozen_readiness_contract": {
            "contract_version": FROZEN_CONTRACT_VERSION,
            "sha256": frozen_digest,
            "expected_sha256": FROZEN_READINESS_SHA256,
            "mutated": frozen_digest != FROZEN_READINESS_SHA256,
            "protocol_frozen": False,
            "holdout_accessed": False,
        },
        "confirmed_execution_decision": {
            "source_contract_version": execution.contract_version,
            "venue_id": execution.selected_venue,
            "instrument_mode": "usdt_linear_perpetual",
            "quote_currency": execution.quote_currency,
            "eligible_instrument_selection_rule": (
                execution.eligible_instrument_selection_rule
            ),
            "exact_eligible_instrument_ids": list(execution.eligible_instrument_set),
            "exact_eligible_instrument_set_sealed": (
                execution.eligible_instrument_set_frozen
            ),
            "data_boundary": "public_market_data_only",
            "jurisdiction_and_account_eligibility": (
                execution.jurisdiction_and_account_eligibility_confirmation
            ),
            "confirmed_at": execution.human_decision_confirmed_at,
            "credentials_or_private_account_data": False,
            "orders_or_execution_or_trading": False,
        },
        "current_activation_blockers": list(_CURRENT_BLOCKERS),
        "next_safe_commands": [
            "make radar-execution-quality-readiness PYTHON=.venv/bin/python",
            "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python",
            "make radar-intraday-bybit-readiness PYTHON=.venv/bin/python",
            "make radar-research-protocol-v2-progress-check PYTHON=.venv/bin/python",
        ],
        "safety": {field: 0 for field in _SAFETY_ZERO_FIELDS},
        "research_only": True,
    }


def validate_current_progress(value: Mapping[str, Any]) -> list[str]:
    """Validate the closed current-progress projection and its audit boundary."""

    errors: list[str] = []
    expected_top = {
        "schema_id",
        "schema_version",
        "progress_version",
        "as_of",
        "status",
        "source",
        "frozen_readiness_contract",
        "confirmed_execution_decision",
        "current_activation_blockers",
        "next_safe_commands",
        "safety",
        "research_only",
    }
    if set(value) != expected_top:
        errors.append("top_level_schema_mismatch")
        return errors
    if value.get("schema_id") != SCHEMA_ID or value.get("schema_version") != 1:
        errors.append("schema_identity_mismatch")
    if value.get("status") != "venue_selected_evidence_collection_blocked":
        errors.append("status_mismatch")

    frozen = value.get("frozen_readiness_contract")
    if not isinstance(frozen, Mapping):
        errors.append("frozen_readiness_contract_invalid")
    else:
        if frozen.get("sha256") != FROZEN_READINESS_SHA256:
            errors.append("frozen_readiness_contract_digest_mismatch")
        if frozen.get("expected_sha256") != FROZEN_READINESS_SHA256:
            errors.append("frozen_readiness_expected_digest_mismatch")
        if frozen.get("mutated") is not False:
            errors.append("frozen_readiness_contract_mutated")
        if frozen.get("protocol_frozen") is not False:
            errors.append("protocol_v2_must_remain_unfrozen")
        if frozen.get("holdout_accessed") is not False:
            errors.append("holdout_accessed")

    decision = value.get("confirmed_execution_decision")
    if not isinstance(decision, Mapping):
        errors.append("confirmed_execution_decision_invalid")
    else:
        expected = {
            "venue_id": "bybit",
            "instrument_mode": "usdt_linear_perpetual",
            "quote_currency": "USDT",
            "exact_eligible_instrument_set_sealed": False,
            "data_boundary": "public_market_data_only",
            "credentials_or_private_account_data": False,
            "orders_or_execution_or_trading": False,
        }
        for key, expected_value in expected.items():
            if decision.get(key) != expected_value:
                errors.append(f"confirmed_execution_decision_{key}_mismatch")
        if decision.get("exact_eligible_instrument_ids") != []:
            errors.append("exact_eligible_instrument_ids_must_remain_unsealed")

    blockers = value.get("current_activation_blockers")
    if blockers != list(_CURRENT_BLOCKERS):
        errors.append("current_activation_blockers_mismatch")
    elif "execution_venue_not_selected" in blockers:
        errors.append("superseded_venue_blocker_present")

    safety = value.get("safety")
    if not isinstance(safety, Mapping) or set(safety) != set(_SAFETY_ZERO_FIELDS):
        errors.append("safety_schema_mismatch")
    elif any(safety.get(field) != 0 for field in _SAFETY_ZERO_FIELDS):
        errors.append("safety_boundary_violated")
    if value.get("research_only") is not True:
        errors.append("research_only_required")
    return errors


def canonical_progress_bytes(value: Mapping[str, Any] | None = None) -> bytes:
    payload = dict(value) if value is not None else current_progress_values()
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def progress_sha256(value: Mapping[str, Any] | None = None) -> str:
    return hashlib.sha256(canonical_progress_bytes(value)).hexdigest()


def format_current_progress(value: Mapping[str, Any] | None = None) -> str:
    payload = deepcopy(dict(value) if value is not None else current_progress_values())
    frozen = payload["frozen_readiness_contract"]
    decision = payload["confirmed_execution_decision"]
    lines = [
        "DECISION RADAR EMPIRICAL PROTOCOL V2 CURRENT PROGRESS",
        f"status={payload['status']}",
        f"as_of={payload['as_of']} progress_sha256={progress_sha256(payload)}",
        (
            "frozen_readiness_contract="
            f"{frozen['contract_version']} sha256={frozen['sha256']} mutated=false"
        ),
        "protocol_frozen=false holdout_accessed=false",
        (
            "selected_execution_surface="
            f"{decision['venue_id']}:{decision['instrument_mode']}:"
            f"{decision['quote_currency']} data_boundary={decision['data_boundary']}"
        ),
        "eligible_instrument_set=not_yet_sealed",
        f"eligible_instrument_selection_rule={decision['eligible_instrument_selection_rule']}",
        (
            "provider_calls=0 credential_reads=0 environment_reads=0 file_reads=0 "
            "file_writes=0 holdout_reads=0"
        ),
        "research_only=true no_orders=true no_trading=true",
        "",
        "Current unresolved activation blockers:",
        *(f"- {blocker}" for blocker in payload["current_activation_blockers"]),
        "",
        "Next safe commands (all static/read-only):",
        *(f"- {command}" for command in payload["next_safe_commands"]),
        "",
        (
            "The immutable readiness contract still records its freeze-time placeholders. "
            "This separate projection is current operator truth and does not freeze or "
            "activate Protocol v2."
        ),
    ]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render current Protocol-v2 progress without changing frozen evidence."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    progress = current_progress_values()
    errors = validate_current_progress(progress)
    if args.check and errors:
        for error in errors:
            print(f"blocker={error}")
        return 1
    if args.as_json:
        print(json.dumps(progress, indent=2, sort_keys=True))
    else:
        print(format_current_progress(progress))
    return 0


__all__ = (
    "FROZEN_READINESS_SHA256",
    "PROGRESS_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "canonical_progress_bytes",
    "current_progress_values",
    "format_current_progress",
    "main",
    "progress_sha256",
    "validate_current_progress",
)


if __name__ == "__main__":
    raise SystemExit(main())
