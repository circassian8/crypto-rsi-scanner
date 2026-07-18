"""Static pre-registration readiness contract for empirical Protocol v2.

Protocol v1 cannot evaluate intraday timing, observed execution quality, or the
non-market evidence used by the current Decision Radar product.  This module
defines the evidence and freeze annex that a future Protocol v2 must seal
*before* its untouched holdout is identified or read.  It is not an executable
protocol: it exposes no replay or final-test target and reads no environment,
files, credentials, providers, or historical observations.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence


SCHEMA_ID = "decision_radar.empirical_validation_protocol_v2_readiness"
SCHEMA_VERSION = 1
CONTRACT_VERSION = "decision_radar_empirical_validation_v2_readiness_v1"
PROPOSED_PROTOCOL_VERSION = "decision_radar_empirical_validation_v2"


_CURRENT_DECISION_PROGRESS: dict[str, Any] = {
    "schema_id": "decision_radar.empirical_validation_protocol_v2_decision_progress",
    "schema_version": 1,
    "as_of": "2026-07-18",
    "status": "venue_selected_evidence_collection_blocked",
    "source": "accepted_human_decisions_after_frozen_readiness_contract",
    "frozen_readiness_contract_mutated": False,
    "confirmed_execution_decision": {
        "venue_id": "bybit",
        "instrument_mode": "usdt_linear_perpetual",
        "quote_currency": "USDT",
        "universe_rule": (
            "top_30_liquidity_ranked_radar_assets_intersect_exact_active_"
            "linearperpetual_trading_usdt_quoted_usdt_settled_nonprelisting_contracts"
        ),
        "exact_eligible_instrument_set_sealed": False,
        "data_boundary": "public_market_data_only",
        "credentials_or_private_account_data": False,
        "orders_or_execution_or_trading": False,
        "jurisdiction_and_account_eligibility": "owner_confirmed_2026-07-17",
    },
    "current_activation_blockers": [
        "exact_eligible_instrument_set_not_sealed",
        "bybit_public_reachability_unproven_after_recorded_403",
        "genuine_execution_quality_capture_absent",
        "data_sources_not_sealed",
        "partitions_and_untouched_holdout_not_sealed",
        "outcomes_and_costs_not_sealed",
        "universe_routes_episodes_and_minimum_samples_not_sealed",
        "human_protocol_v2_annex_approval_absent",
    ],
    "provider_authorization_created": False,
    "provider_calls": 0,
    "holdout_accessed": False,
    "research_only": True,
}


_REQUIRED_EVIDENCE: tuple[dict[str, Any], ...] = (
    {
        "role": "intraday_market_observations",
        "required_cadences": ["1h", "4h"],
        "required_fields": [
            "canonical_asset_id",
            "instrument_id",
            "venue_id",
            "interval_start",
            "interval_end",
            "open",
            "high",
            "low",
            "close",
            "base_volume",
            "quote_volume",
            "provider_observed_at",
            "acquired_at",
            "source_lineage_id",
        ],
    },
    {
        "role": "idea_timing_and_review_latency",
        "required_fields": [
            "idea_id",
            "idea_observed_at",
            "idea_available_at",
            "first_operator_viewed_at",
            "review_completed_at",
            "latency_seconds",
            "clock_source",
        ],
    },
    {
        "role": "execution_venue_spread_and_depth",
        "required_fields": [
            "venue_id",
            "instrument_mode",
            "instrument_id",
            "quote_asset",
            "provider_observed_at",
            "acquired_at",
            "best_bid",
            "best_ask",
            "spread_bps",
            "bid_depth_usd_by_band",
            "ask_depth_usd_by_band",
            "source_lineage_id",
        ],
    },
    {
        "role": "catalyst_timing",
        "required_fields": [
            "event_id",
            "canonical_asset_ids",
            "event_time",
            "first_public_at",
            "first_observed_at",
            "time_certainty",
            "provider",
            "source_url",
            "source_lineage_id",
        ],
    },
    {
        "role": "official_calendar_events",
        "required_fields": [
            "event_id",
            "category",
            "event_time_or_window",
            "time_certainty",
            "importance",
            "provider",
            "source_lineage_id",
        ],
    },
    {
        "role": "derivatives_context",
        "required_fields": [
            "instrument_id",
            "venue_id",
            "funding_rate",
            "open_interest",
            "liquidations",
            "provider_observed_at",
            "acquired_at",
            "source_lineage_id",
        ],
    },
    {
        "role": "onchain_context",
        "required_fields": [
            "chain_id",
            "canonical_asset_id",
            "metric_name",
            "metric_value",
            "block_number_or_time",
            "provider_observed_at",
            "acquired_at",
            "source_lineage_id",
        ],
    },
    {
        "role": "rsi_technical_context",
        "required_fields": [
            "canonical_asset_id",
            "instrument_id",
            "timeframe",
            "period",
            "wilder_rsi",
            "candle_close_time",
            "available_at",
            "source_lineage_id",
        ],
    },
)


_FREEZE_ANNEX_REQUIREMENTS: dict[str, list[str]] = {
    "execution_venue_and_instruments": [
        "intended_venue",
        "instrument_mode_spot_perpetual_or_dex",
        "quote_currency",
        "eligible_instrument_set",
        "jurisdiction_and_account_eligibility_confirmation",
        "expected_public_private_data_boundary",
    ],
    "data_sources": [
        "evidence_role",
        "provider_or_local_source",
        "dataset_or_endpoint_identity",
        "point_in_time_availability_rule",
        "freshness_rule",
        "timezone_rule",
        "immutable_lineage_and_content_digest",
        "authorization_boundary",
    ],
    "partitions_and_holdout": [
        "development_start_and_end",
        "validation_start_and_end",
        "untouched_holdout_start_and_end",
        "outcome_maturity_boundary",
        "embargo_or_purge_rule",
        "holdout_content_commitment",
        "holdout_access_ledger",
    ],
    "outcomes": [
        "primary_horizon",
        "sensitivity_horizons",
        "entry_and_exit_rules",
        "relative_benchmarks",
        "mfe_mae_and_invalidation_rules",
        "latency_outcomes",
        "missing_and_pending_rules",
    ],
    "costs": [
        "venue_fee_schedule",
        "observed_spread_rule",
        "depth_and_price_impact_rule",
        "slippage_rule",
        "latency_cost_rule",
        "unavailable_cost_fail_closed_rule",
    ],
    "universe": [
        "point_in_time_membership_method",
        "eligible_assets_and_instruments",
        "liquidity_thresholds",
        "listing_delisting_and_identity_rules",
    ],
    "routes": [
        "decision_model_version",
        "exact_route_definitions",
        "route_assignment_code_digest",
        "production_and_shadow_policy_digests",
    ],
    "episodes": [
        "episode_identity",
        "time_window",
        "representative_selection",
        "cross_asset_market_risk_grouping",
        "correlated_repeat_handling",
    ],
    "minimum_samples": [
        "aggregate_minimum",
        "route_minimum",
        "route_bias_regime_liquidity_quality_minimum",
        "insufficient_sample_rule",
        "multiple_comparison_policy",
    ],
}


_READINESS: dict[str, Any] = {
    "schema_id": SCHEMA_ID,
    "schema_version": SCHEMA_VERSION,
    "contract_version": CONTRACT_VERSION,
    "proposed_protocol_version": PROPOSED_PROTOCOL_VERSION,
    "status": "blocked_pending_exact_human_sealed_annex",
    "contract_validity": "static_readiness_contract_only",
    "required_evidence_contract_status": "frozen_static",
    "required_evidence_runtime_override_allowed": False,
    "protocol_freeze_status": "not_frozen",
    "protocol_activation_status": "blocked",
    "research_only": True,
    "required_evidence": list(_REQUIRED_EVIDENCE),
    "evidence_policy": {
        "missing_evidence": "unavailable",
        "invented_evidence": "forbidden",
        "proxy_for_required_evidence": "forbidden",
        "point_in_time_availability_required": True,
        "immutable_source_lineage_required": True,
    },
    "required_freeze_annex": _FREEZE_ANNEX_REQUIREMENTS,
    "freeze_annex_status": {
        "sealed": False,
        "sealed_at": None,
        "annex_sha256": None,
        "human_approved": False,
        "all_required_sections_complete": False,
    },
    "holdout": {
        "defined": False,
        "content_commitment_sealed": False,
        "access_authorized": False,
        "accessed": False,
        "access_count": 0,
        "protocol_v1_final_test_reuse_for_tuning": "forbidden",
        "protocol_v2_final_test_status": "not_run",
    },
    "activation_requirements": [
        "exact_execution_venue_and_instrument_annex_sealed",
        "exact_source_annex_sealed",
        "exact_partition_and_untouched_holdout_annex_sealed",
        "exact_outcome_annex_sealed",
        "exact_cost_annex_sealed",
        "exact_universe_and_route_annex_sealed",
        "exact_episode_annex_sealed",
        "exact_minimum_sample_annex_sealed",
        "human_protocol_v2_approval_recorded",
    ],
    "activation_blockers": [
        "execution_venue_not_selected",
        "instrument_mode_not_selected",
        "quote_currency_not_selected",
        "eligible_instrument_set_not_sealed",
        "jurisdiction_and_account_eligibility_not_confirmed",
        "public_private_data_boundary_not_declared",
        "data_sources_not_sealed",
        "partitions_and_untouched_holdout_not_sealed",
        "outcomes_and_costs_not_sealed",
        "universe_routes_episodes_and_minimum_samples_not_sealed",
        "human_protocol_v2_approval_absent",
    ],
    "exposed_targets": {
        "replay": [],
        "selection": [],
        "final_test": [],
    },
    "safety": {
        "provider_calls": 0,
        "credential_reads": 0,
        "file_reads": 0,
        "file_writes": 0,
        "environment_reads": 0,
        "dashboard_pointer_changes": 0,
        "notifications": 0,
        "trades": 0,
        "orders": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    },
}


def readiness_values() -> dict[str, Any]:
    """Return a defensive copy of the static, blocked readiness contract."""

    return deepcopy(_READINESS)


def current_decision_progress_values() -> dict[str, Any]:
    """Return current accepted decisions without mutating the frozen contract."""

    return deepcopy(_CURRENT_DECISION_PROGRESS)


def canonical_readiness_bytes(value: Mapping[str, Any] | None = None) -> bytes:
    payload = dict(value) if value is not None else readiness_values()
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def readiness_sha256(value: Mapping[str, Any] | None = None) -> str:
    return hashlib.sha256(canonical_readiness_bytes(value)).hexdigest()


def validate_readiness(value: Mapping[str, Any]) -> list[str]:
    """Fail closed on drift that could imply a usable or opened v2 protocol."""

    errors: list[str] = []
    if dict(value) != _READINESS:
        errors.append("protocol_v2_readiness_contract_drift")
    holdout = value.get("holdout")
    if not isinstance(holdout, Mapping):
        errors.append("holdout_contract_missing")
    else:
        if holdout.get("accessed") is not False or holdout.get("access_count") != 0:
            errors.append("holdout_must_remain_unopened")
        if holdout.get("protocol_v2_final_test_status") != "not_run":
            errors.append("protocol_v2_final_test_must_not_run")
        if holdout.get("protocol_v1_final_test_reuse_for_tuning") != "forbidden":
            errors.append("protocol_v1_final_test_tuning_firewall_missing")
    annex = value.get("freeze_annex_status")
    if not isinstance(annex, Mapping) or annex.get("sealed") is not False:
        errors.append("unsealed_annex_must_not_claim_frozen")
    if value.get("protocol_freeze_status") != "not_frozen":
        errors.append("protocol_must_not_claim_frozen")
    if value.get("protocol_activation_status") != "blocked":
        errors.append("protocol_activation_must_remain_blocked")
    exposed = value.get("exposed_targets")
    if not isinstance(exposed, Mapping) or any(exposed.get(name) for name in (
        "replay",
        "selection",
        "final_test",
    )):
        errors.append("protocol_v2_must_expose_no_evaluation_target")
    evidence = value.get("required_evidence")
    roles = {
        row.get("role")
        for row in evidence
        if isinstance(evidence, list) and isinstance(row, Mapping)
    } if isinstance(evidence, list) else set()
    expected_roles = {row["role"] for row in _REQUIRED_EVIDENCE}
    if roles != expected_roles:
        errors.append("required_evidence_roles_incomplete")
    safety = value.get("safety")
    if not isinstance(safety, Mapping) or set(safety.values()) != {0}:
        errors.append("static_readiness_safety_boundary_invalid")
    return list(dict.fromkeys(errors))


def format_readiness(value: Mapping[str, Any] | None = None) -> str:
    payload = dict(value) if value is not None else readiness_values()
    progress = current_decision_progress_values()
    decision = progress["confirmed_execution_decision"]
    lines = [
        "DECISION RADAR EMPIRICAL PROTOCOL V2 READINESS",
        f"status={payload['status']}",
        f"contract_version={payload['contract_version']}",
        f"proposed_protocol_version={payload['proposed_protocol_version']}",
        f"contract_sha256={readiness_sha256(payload)}",
        "required_evidence_contract=frozen_static runtime_override=false",
        "protocol_frozen=false activation=blocked holdout_accessed=false final_test=not_run",
        "targets_exposed=replay:0,selection:0,final_test:0",
        "provider_calls=0 credential_reads=0 file_reads=0 file_writes=0 environment_reads=0",
        "research_only=true no_orders=true no_trading_permission_requested=true",
        (
            "current_decision_progress="
            f"{progress['status']} frozen_contract_mutated=false"
        ),
        (
            "selected_execution_surface="
            f"{decision['venue_id']}:{decision['instrument_mode']}:"
            f"{decision['quote_currency']} data_boundary={decision['data_boundary']}"
        ),
        "",
        "Required point-in-time evidence (no invention or proxy):",
    ]
    for row in payload["required_evidence"]:
        cadence = ",".join(row.get("required_cadences", ()))
        suffix = f" cadences={cadence}" if cadence else ""
        lines.append(
            f"- {row['role']}:{suffix} fields={','.join(row['required_fields'])}"
        )
    lines.extend(("", "Required exact sealed annex sections:"))
    for section, fields in payload["required_freeze_annex"].items():
        lines.append(f"- {section}: {','.join(fields)}")
    lines.extend(("", "Current unresolved activation blockers:"))
    lines.extend(
        f"- {blocker}" for blocker in progress["current_activation_blockers"]
    )
    lines.extend(("", "Frozen-contract placeholders retained for audit/hash stability:"))
    lines.extend(f"- {blocker}" for blocker in payload["activation_blockers"])
    lines.extend(
        (
            "",
            "No Protocol-v2 replay or final test is available. The confirmed Bybit "
            "surface still requires a human-approved exact instrument set, source, "
            "partition/holdout, outcome, cost, universe, route, episode, and minimum-"
            "sample annex before activation.",
        )
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the blocked, static Protocol-v2 pre-registration contract."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = readiness_values()
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_readiness(payload))
    errors = validate_readiness(payload)
    if errors:
        print("protocol_v2_readiness_errors=" + ",".join(errors))
        return 2
    return 0


__all__ = (
    "CONTRACT_VERSION",
    "PROPOSED_PROTOCOL_VERSION",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "canonical_readiness_bytes",
    "current_decision_progress_values",
    "format_readiness",
    "main",
    "readiness_sha256",
    "readiness_values",
    "validate_readiness",
)


if __name__ == "__main__":
    raise SystemExit(main())
