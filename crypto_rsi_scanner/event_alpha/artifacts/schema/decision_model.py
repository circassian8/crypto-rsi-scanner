"""Schema fields and semantic checks for Crypto Radar Decision Model v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import math
from typing import Any

import crypto_rsi_scanner.event_alpha.operations.market_provenance as event_market_provenance
import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as event_catalyst_attribution
import crypto_rsi_scanner.event_alpha.radar.source_independence as event_source_independence
import crypto_rsi_scanner.event_alpha.radar.source_independence_store as event_source_independence_store


DECISION_MODEL_VERSION = "crypto_radar_decision_model_v2"
LEGACY_DECISION_PROJECTION_SCHEMA_VERSION = "crypto_radar_decision_projection_v1"
DECISION_PROJECTION_SCHEMA_VERSION = "crypto_radar_decision_projection_v2"
SUPPORTED_DECISION_PROJECTION_SCHEMA_VERSIONS = (
    LEGACY_DECISION_PROJECTION_SCHEMA_VERSION,
    DECISION_PROJECTION_SCHEMA_VERSION,
)
ALLOWED_THESIS_ORIGINS = (
    "market_led", "catalyst_led", "technical_led", "derivatives_led", "onchain_led",
    "fundamental_led", "macro_led", "mixed",
)
ALLOWED_DIRECTIONAL_BIASES = ("long", "fade_short_review", "risk", "neutral")
ALLOWED_CATALYST_STATUSES = ("confirmed", "plausible", "unknown", "not_required", "disproven")
ALLOWED_CONFIDENCE_BANDS = ("diagnostic", "exploratory", "actionable", "high_confidence")
ALLOWED_TIMING_STATES = ("early", "active", "extended", "exhausted", "scheduled", "stale")
ALLOWED_TRADABILITY_STATUSES = ("good", "acceptable", "poor", "blocked")
ALLOWED_SPREAD_STATUSES = (
    "verified_good", "verified_acceptable", "verified_wide", "unavailable", "stale",
)
ALLOWED_MARKET_PHASES = (
    "emerging", "breakout", "acceleration", "active", "extended", "exhaustion", "reversal",
)
ALLOWED_PREFERRED_HORIZONS = ("intraday", "1d_3d", "3d_7d", "scheduled_window")
ALLOWED_RADAR_ROUTES = (
    "dashboard_watch", "actionable_watch", "high_confidence_watch", "rapid_market_anomaly",
    "fade_exhaustion_review", "risk_watch", "calendar_risk", "diagnostic",
)
_MODEL_TEXT_COLLECTION_FIELDS = (
    "thesis_origins", "decision_hard_blockers", "decision_soft_penalties",
    "decision_missing_data", "decision_warnings", "why_still_worth_reviewing",
    "radar_what_confirms", "radar_what_invalidates",
)
_PROJECTION_TEXT_COLLECTION_FIELDS = (
    "hard_blockers", "soft_penalties", "warnings", "supporting_facts",
    "missing_information", "main_risks", "what_confirms", "what_invalidates",
    "source_independence_errors",
)
_RSI_REFERENCE_FIELDS = {
    "context_version", "symbol", "coin_id", "setup_type", "rsi_timeframe",
    "observed_at", "freshness_status", "valid",
}
_RSI_REFERENCE_TEXT_FIELDS = (
    "context_version", "symbol", "coin_id", "setup_type", "rsi_timeframe",
    "observed_at", "freshness_status",
)

FIELDS = (
    "decision_model_version", "decision_model_enabled", "thesis_origin",
    "primary_thesis_origin", "thesis_origins",
    "directional_bias", "catalyst_status", "confidence_band", "timing_state",
    "tradability_status", "spread_status", "radar_route", "radar_route_reason", "radar_actionable",
    "actionability_score", "evidence_confidence_score", "risk_score",
    "urgency_score", "market_phase", "preferred_horizon", "expires_at", "chase_risk_score",
    "actionability_score_components", "evidence_confidence_score_components",
    "risk_score_components", "actionability_penalty_components", "decision_hard_blockers",
    "decision_soft_penalties", "decision_warnings", "decision_missing_data",
    "why_still_worth_reviewing", "radar_what_confirms", "radar_what_invalidates",
    "actionability_score_cohort", "anomaly_type",
    "decision_source_side_effect_safety_failed", "decision_source_secret_safety_failed",
    "decision_source_path_safety_failed",
    "decision_projection_schema_version", "hard_blockers", "soft_penalties", "warnings",
    "why_now", "supporting_facts", "missing_information", "main_risks",
    "what_confirms", "what_invalidates", "calendar_evidence", "calendar_evidence_ids",
    "rsi_context", "rsi_context_references", "observation_ids", "source_provider_lineage",
    "catalyst_attributions",
    "source_independence", "independent_source_count",
    "independent_corroboration_count", "source_content_cluster_count",
    "source_independence_status", "source_independence_errors",
    "market_provenance",
    "market_context_reference", "market_observation_identity_bound",
    "market_provenance_schema_version", "market_provenance_contract_version",
    "data_acquisition_mode", "candidate_source_mode",
    "provider", "provider_call_attempted", "provider_call_succeeded",
    "provider_request_succeeded", "live_provider_authorized", "request_ledger_path",
    "request_ledger_sha256", "provider_source_artifact", "provider_source_artifact_sha256",
    "provider_generation_id", "cache_status", "provenance_contract_valid",
    "burn_in_eligible", "burn_in_counted", "burn_in_reason", "feature_basis",
    "data_quality", "contract_counted_candidate",
    "decision_evaluated_at", "decision_safety_invariants", "decision_projection",
)
TYPES = {
    "decision_model_version": "str", "decision_model_enabled": "bool",
    "thesis_origin": "str", "primary_thesis_origin": "str", "thesis_origins": "list",
    "directional_bias": "str", "catalyst_status": "str",
    "confidence_band": "str", "timing_state": "str", "tradability_status": "str",
    "spread_status": "str", "radar_route": "str", "radar_route_reason": "str",
    "radar_actionable": "bool", "actionability_score": "float",
    "evidence_confidence_score": "float", "risk_score": "float",
    "urgency_score": "float", "market_phase": "str", "preferred_horizon": "str",
    "expires_at": "str", "chase_risk_score": "float",
    "actionability_score_components": "dict", "evidence_confidence_score_components": "dict",
    "risk_score_components": "dict", "actionability_penalty_components": "dict",
    "decision_hard_blockers": "list", "decision_soft_penalties": "list",
    "decision_warnings": "list", "decision_missing_data": "list",
    "why_still_worth_reviewing": "list", "radar_what_confirms": "list",
    "radar_what_invalidates": "list",
    "actionability_score_cohort": "str", "anomaly_type": "str",
    "decision_source_side_effect_safety_failed": "bool",
    "decision_source_secret_safety_failed": "bool",
    "decision_source_path_safety_failed": "bool",
    "decision_projection_schema_version": "str",
    "hard_blockers": "list", "soft_penalties": "list", "warnings": "list",
    "why_now": "str", "supporting_facts": "list", "missing_information": "list",
    "main_risks": "list", "what_confirms": "list", "what_invalidates": "list",
    "calendar_evidence": "list", "calendar_evidence_ids": "list", "rsi_context": "dict",
    "rsi_context_references": "list", "observation_ids": "list",
    "source_provider_lineage": "dict", "market_provenance": "dict",
    "catalyst_attributions": "list",
    "source_independence": "dict", "independent_source_count": "int",
    "independent_corroboration_count": "int", "source_content_cluster_count": "int",
    "source_independence_status": "str", "source_independence_errors": "list",
    "market_context_reference": "dict", "market_observation_identity_bound": "bool",
    "market_provenance_schema_version": "str", "market_provenance_contract_version": "int",
    "data_acquisition_mode": "str",
    "candidate_source_mode": "str", "provider": "str",
    "provider_call_attempted": "bool", "provider_call_succeeded": "bool",
    "provider_request_succeeded": "bool", "live_provider_authorized": "bool",
    "request_ledger_path": "str", "request_ledger_sha256": "str",
    "provider_source_artifact": "str", "provider_source_artifact_sha256": "str",
    "provider_generation_id": "str", "cache_status": "str",
    "provenance_contract_valid": "bool", "burn_in_eligible": "bool",
    "burn_in_counted": "bool", "burn_in_reason": "str", "feature_basis": "dict",
    "data_quality": "dict", "contract_counted_candidate": "bool",
    "decision_evaluated_at": "str",
    "decision_safety_invariants": "dict",
    "decision_projection": "dict",
}
ENUMS = {
    "thesis_origin": ALLOWED_THESIS_ORIGINS,
    "primary_thesis_origin": ALLOWED_THESIS_ORIGINS,
    "directional_bias": ALLOWED_DIRECTIONAL_BIASES,
    "catalyst_status": ALLOWED_CATALYST_STATUSES,
    "confidence_band": ALLOWED_CONFIDENCE_BANDS,
    "timing_state": ALLOWED_TIMING_STATES,
    "tradability_status": ALLOWED_TRADABILITY_STATUSES,
    "spread_status": ALLOWED_SPREAD_STATUSES,
    "market_phase": ALLOWED_MARKET_PHASES,
    "preferred_horizon": ALLOWED_PREFERRED_HORIZONS,
    "radar_route": ALLOWED_RADAR_ROUTES,
}


def validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Fail closed on malformed explicit v2 rows without touching legacy rows."""

    return _validate_contract(row)


def _validate_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate one explicit contract behind the stable public entrypoint."""

    if str(row.get("decision_model_version") or "") != DECISION_MODEL_VERSION:
        return ["unsupported_decision_model_version"]
    required = (
        "decision_model_enabled", "thesis_origin", "directional_bias", "catalyst_status",
        "confidence_band", "timing_state", "tradability_status", "radar_route",
        "radar_route_reason", "radar_actionable", "actionability_score",
        "evidence_confidence_score", "risk_score", "actionability_score_components",
        "evidence_confidence_score_components", "risk_score_components",
        "actionability_penalty_components", "decision_hard_blockers",
        "decision_soft_penalties", "decision_missing_data", "decision_warnings",
        "why_still_worth_reviewing", "radar_what_confirms", "radar_what_invalidates",
        "actionability_score_cohort",
    )
    errors = [
        f"decision_model_missing_field:{field}"
        for field in required
        if field not in row or row.get(field) is None or isinstance(row.get(field), str) and not str(row.get(field)).strip()
    ]
    extended_fields = (
        "primary_thesis_origin", "thesis_origins", "spread_status", "urgency_score",
        "market_phase", "preferred_horizon", "expires_at", "chase_risk_score",
    )
    extended_contract = any(field in row for field in extended_fields)
    if extended_contract:
        errors.extend(
            f"decision_model_missing_field:{field}"
            for field in extended_fields
            if field not in row or field != "expires_at" and row.get(field) is None
        )
    if not isinstance(row.get("decision_model_enabled"), bool):
        errors.append("decision_model_invalid_type:decision_model_enabled")
    if not isinstance(row.get("radar_actionable"), bool):
        errors.append("decision_model_invalid_type:radar_actionable")
    for field, allowed in ENUMS.items():
        if field in extended_fields and not extended_contract:
            continue
        if str(row.get(field) or "") not in allowed:
            errors.append(f"decision_model_invalid_enum:{field}")
    for field in (
        "actionability_score_components", "evidence_confidence_score_components",
        "risk_score_components", "actionability_penalty_components",
    ):
        if not isinstance(row.get(field), Mapping):
            errors.append(f"decision_model_invalid_type:{field}")
    if extended_contract:
        origins = _items(row.get("thesis_origins"))
        if not origins:
            errors.append("decision_model_empty_transparency_field:thesis_origins")
        elif any(origin not in ALLOWED_THESIS_ORIGINS for origin in origins) or (
            row.get("decision_model_enabled") is True and "mixed" in origins
        ):
            errors.append("decision_model_invalid_thesis_origins")
        elif len(origins) != len(set(origins)):
            errors.append("decision_model_duplicate_thesis_origins")
        elif origins[0] != str(row.get("primary_thesis_origin") or ""):
            errors.append("decision_model_primary_thesis_origin_order_mismatch")
    for field in _MODEL_TEXT_COLLECTION_FIELDS:
        if field == "thesis_origins" and not extended_contract:
            continue
        if not _is_sequence(row.get(field)):
            errors.append(f"decision_model_invalid_type:{field}")
        elif any(
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            for value in row.get(field, ())
        ):
            errors.append(f"decision_model_invalid_collection_value:{field}")
    source_safety_blockers = {
        "decision_source_side_effect_safety_failed": "research_safety_invariant_failed",
        "decision_source_secret_safety_failed": "secret_safety_failed",
        "decision_source_path_safety_failed": "operator_path_safety_failed",
    }
    hard_blockers = set(_items(row.get("decision_hard_blockers")))
    for field, blocker in source_safety_blockers.items():
        if field in row and not isinstance(row.get(field), bool):
            errors.append(f"decision_model_invalid_type:{field}")
        if row.get(field) is True and blocker not in hard_blockers:
            errors.append(f"decision_model_source_safety_attestation_without_blocker:{field}")
    if row.get("decision_model_enabled") is True:
        if row.get("research_only") is not True:
            errors.append("decision_model_research_only_required")
        for field in (
            "actionability_score_components", "evidence_confidence_score_components",
            "risk_score_components",
        ):
            if isinstance(row.get(field), Mapping) and not row.get(field):
                errors.append(f"decision_model_empty_transparency_field:{field}")
        for field in (
            "decision_warnings", "why_still_worth_reviewing", "radar_what_confirms",
            "radar_what_invalidates",
        ):
            if _is_sequence(row.get(field)) and not tuple(row.get(field) or ()):
                errors.append(f"decision_model_empty_transparency_field:{field}")
    errors.extend(_validate_scores_and_expiry(row, extended_contract=extended_contract))
    if row.get("radar_actionable") is True:
        if row.get("decision_hard_blockers"):
            errors.append("decision_model_actionable_with_hard_blocker")
        if str(row.get("tradability_status") or "") not in {"good", "acceptable"}:
            errors.append("decision_model_actionable_not_tradable")
        if extended_contract and str(row.get("spread_status") or "") not in {"verified_good", "verified_acceptable"}:
            errors.append("decision_model_actionable_spread_unverified")
        if str(row.get("confidence_band") or "") not in {"actionable", "high_confidence"}:
            errors.append("decision_model_actionable_band_mismatch")
    elif str(row.get("confidence_band") or "") in {"actionable", "high_confidence"}:
        errors.append("decision_model_non_actionable_band_mismatch")
    route = str(row.get("radar_route") or "")
    if route in {"actionable_watch", "high_confidence_watch", "rapid_market_anomaly"} and row.get("radar_actionable") is not True:
        errors.append("decision_model_watch_route_not_actionable")
    if route in {"dashboard_watch", "risk_watch", "calendar_risk"} and row.get("radar_actionable") is not False:
        errors.append("decision_model_observational_route_marked_actionable")
    if route == "high_confidence_watch" and str(row.get("confidence_band") or "") != "high_confidence":
        errors.append("decision_model_high_confidence_route_band_mismatch")
    if row.get("decision_hard_blockers") and route != "diagnostic":
        errors.append("decision_model_hard_blocker_non_diagnostic_route")
    if extended_contract:
        has_calendar = _has_calendar_evidence(row)
        if route == "calendar_risk" and not has_calendar:
            errors.append("decision_model_calendar_risk_without_calendar_evidence")
        if route == "risk_watch" and has_calendar:
            errors.append("decision_model_risk_watch_with_calendar_evidence")
    if row.get("thesis_origin") == "market_led" and row.get("catalyst_status") == "unknown":
        warnings = {
            item
            for field in ("decision_warnings", "decision_soft_penalties")
            for item in _items(row.get(field))
        }
        if not any("catalyst" in item.casefold() and "unknown" in item.casefold() for item in warnings):
            errors.append("decision_model_unknown_catalyst_warning_missing")
    if extended_contract:
        errors.extend(_validate_market_return_units(row))
    if "decision_projection_schema_version" in row:
        errors.extend(_validate_closed_projection(row))
    nested_projection = row.get("decision_projection")
    if nested_projection is not None:
        if not isinstance(nested_projection, Mapping):
            errors.append("decision_projection_invalid_type")
        else:
            errors.extend(
                f"decision_projection_nested:{error}"
                for error in _validate_contract(nested_projection)
            )
    return errors


def _validate_closed_projection(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    projection_version = row.get("decision_projection_schema_version")
    if projection_version not in SUPPORTED_DECISION_PROJECTION_SCHEMA_VERSIONS:
        errors.append("decision_projection_schema_version_unsupported")
    required = (
        "hard_blockers", "soft_penalties", "warnings", "why_now", "supporting_facts",
        "missing_information", "main_risks", "what_confirms", "what_invalidates",
        "calendar_evidence", "calendar_evidence_ids", "rsi_context", "rsi_context_references",
        "observation_ids", "source_provider_lineage", "decision_evaluated_at",
        "decision_safety_invariants",
    )
    errors.extend(
        f"decision_projection_missing_field:{field}"
        for field in required
        if field not in row or row.get(field) is None
    )
    for field in (
        "hard_blockers", "soft_penalties", "warnings", "supporting_facts",
        "missing_information", "main_risks", "what_confirms", "what_invalidates",
        "calendar_evidence", "calendar_evidence_ids", "rsi_context_references", "observation_ids",
        "catalyst_attributions",
    ):
        if field in row and not _is_sequence(row.get(field)):
            errors.append(f"decision_projection_invalid_type:{field}")
    for field in _PROJECTION_TEXT_COLLECTION_FIELDS:
        if field in row and _is_sequence(row.get(field)) and any(
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            for value in row.get(field, ())
        ):
            errors.append(f"decision_projection_invalid_collection_value:{field}")
    for field in (
        "rsi_context", "source_provider_lineage", "decision_safety_invariants",
        "source_independence",
    ):
        if field in row and not isinstance(row.get(field), Mapping):
            errors.append(f"decision_projection_invalid_type:{field}")
    if not isinstance(row.get("why_now"), str) or not str(row.get("why_now") or "").strip():
        errors.append("decision_projection_why_now_missing")
    if _aware_timestamp(row.get("decision_evaluated_at")) is None:
        errors.append("decision_projection_evaluation_timestamp_invalid")
    observation_ids = row.get("observation_ids")
    if _is_sequence(observation_ids):
        observation_id_values = tuple(observation_ids)
        if not observation_id_values:
            errors.append("decision_projection_observation_ids_empty")
        elif any(
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            for value in observation_id_values
        ):
            errors.append("decision_projection_observation_ids_invalid")

    aliases = {
        "hard_blockers": "decision_hard_blockers",
        "soft_penalties": "decision_soft_penalties",
        "warnings": "decision_warnings",
        "missing_information": "decision_missing_data",
        "what_confirms": "radar_what_confirms",
        "what_invalidates": "radar_what_invalidates",
    }
    for alias, canonical in aliases.items():
        if _items(row.get(alias)) != _items(row.get(canonical)):
            errors.append(f"decision_projection_alias_mismatch:{alias}")

    errors.extend(_validate_projection_calendar_and_rsi(row))
    errors.extend(_validate_projection_catalyst_attributions(row))
    errors.extend(_validate_projection_source_independence(row))

    lineage = row.get("source_provider_lineage")
    if isinstance(lineage, Mapping):
        for field in ("providers", "origins", "source_packs"):
            if not _is_sequence(lineage.get(field)):
                errors.append(f"decision_projection_lineage_invalid:{field}")
            elif any(
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
                for value in lineage.get(field, ())
            ):
                errors.append(
                    f"decision_projection_lineage_value_invalid:{field}"
                )
        data_mode = lineage.get("data_mode")
        if (
            not isinstance(data_mode, str)
            or not data_mode.strip()
            or data_mode != data_mode.strip()
        ):
            errors.append("decision_projection_lineage_value_invalid:data_mode")
        for field in (
            "provider_generation_id", "run_id", "profile", "artifact_namespace",
            "candidate_source_mode", "measurement_program",
        ):
            value = lineage.get(field)
            if value is not None and (
                not isinstance(value, str) or value != value.strip()
            ):
                errors.append(
                    f"decision_projection_lineage_value_invalid:{field}"
                )

    provenance = row.get("market_provenance")
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            errors.append("decision_projection_market_provenance_invalid_type")
        else:
            normalized_provenance = event_market_provenance.normalize_market_provenance(provenance)
            if dict(provenance) != normalized_provenance:
                errors.append("decision_projection_market_provenance_not_canonical")
            if isinstance(lineage, Mapping) and lineage.get("market_provenance") != normalized_provenance:
                errors.append("decision_projection_market_provenance_lineage_mismatch")
            flat_provenance = event_market_provenance.market_provenance_flat_fields(
                normalized_provenance
            )
            for field, expected in flat_provenance.items():
                if row.get(field) != expected:
                    errors.append(f"decision_projection_market_provenance_alias_mismatch:{field}")

    market_reference = row.get("market_context_reference")
    if market_reference is not None:
        if not isinstance(market_reference, Mapping):
            errors.append("decision_projection_market_context_reference_invalid_type")
        elif market_reference:
            allowed_reference_fields = {
                "source", "observed_at", "freshness_status", "market_snapshot_id",
            }
            if set(market_reference) != allowed_reference_fields:
                errors.append("decision_projection_market_context_reference_fields_invalid")
            for field in allowed_reference_fields:
                value = market_reference.get(field)
                if value is not None and (
                    not isinstance(value, str) or not value or value != value.strip()
                ):
                    errors.append(
                        f"decision_projection_market_context_reference_value_invalid:{field}"
                    )
            observed_at = market_reference.get("observed_at")
            if observed_at is not None and _aware_timestamp(observed_at) is None:
                errors.append("decision_projection_market_context_reference_timestamp_invalid")
    errors.extend(
        _validate_projection_market_observation_binding(row, market_reference)
    )
    campaign_provenance = (
        provenance
        if isinstance(provenance, Mapping)
        and provenance.get("measurement_program")
        == event_market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM
        else None
    )
    if campaign_provenance is not None:
        required_reference_fields = {
            "source", "observed_at", "freshness_status", "market_snapshot_id",
        }
        if not isinstance(market_reference, Mapping) or set(market_reference) != required_reference_fields:
            errors.append("decision_projection_campaign_market_context_reference_missing")
        else:
            for field in required_reference_fields:
                value = market_reference.get(field)
                if not isinstance(value, str) or not value or value != value.strip():
                    errors.append(
                        f"decision_projection_campaign_market_context_reference_missing:{field}"
                    )
            if _aware_timestamp(market_reference.get("observed_at")) is None:
                errors.append("decision_projection_campaign_market_context_reference_timestamp_invalid")

    safety = row.get("decision_safety_invariants")
    required_safety = (
        "research_only", "no_live_trading", "no_event_alpha_paper_trading",
        "no_normal_rsi_writes", "no_triggered_fade_creation", "no_notification_send",
    )
    if isinstance(safety, Mapping):
        for field in required_safety:
            if safety.get(field) is not True:
                errors.append(f"decision_projection_safety_invariant_failed:{field}")
        source_safety = {
            "source_side_effect_safety_passed": "decision_source_side_effect_safety_failed",
            "source_secret_safety_passed": "decision_source_secret_safety_failed",
            "source_path_safety_passed": "decision_source_path_safety_failed",
        }
        for field, attestation in source_safety.items():
            if not isinstance(safety.get(field), bool):
                errors.append(f"decision_projection_safety_invariant_invalid:{field}")
            elif safety.get(field) is not (row.get(attestation) is not True):
                errors.append(f"decision_projection_safety_attestation_mismatch:{field}")
    return list(dict.fromkeys(errors))


def _validate_projection_market_observation_binding(
    row: Mapping[str, Any],
    market_reference: object,
) -> list[str]:
    if "market_observation_identity_bound" not in row:
        return []
    identity_bound = row.get("market_observation_identity_bound")
    if not isinstance(identity_bound, bool):
        return ["decision_projection_market_observation_identity_bound_invalid"]
    if identity_bound is not True:
        return []
    reference = market_reference if isinstance(market_reference, Mapping) else {}
    raw_snapshot_id = reference.get("market_snapshot_id")
    snapshot_id = (
        raw_snapshot_id.strip() if isinstance(raw_snapshot_id, str) else ""
    )
    if not snapshot_id:
        return ["decision_projection_bound_market_snapshot_missing"]
    if snapshot_id not in _items(row.get("observation_ids")):
        return ["decision_projection_market_snapshot_observation_id_missing"]
    return []


def _validate_projection_source_independence(
    row: Mapping[str, Any],
) -> list[str]:
    """Validate the closed independence value and its projection aliases."""

    contract = row.get("source_independence")
    count_fields = {
        "independent_source_count": "independent_evidence_count",
        "independent_corroboration_count": "independent_corroboration_count",
        "source_content_cluster_count": "content_cluster_count",
    }
    extension_fields = {
        "source_independence",
        "source_independence_status",
        "source_independence_errors",
        *count_fields,
    }
    present = extension_fields.intersection(row)
    if not present:
        # Shipped projection-v1 artifacts predate this additive, fail-closed
        # extension. They remain readable without inventing source evidence.
        return []
    if present != extension_fields:
        return ["decision_projection_source_independence_extension_incomplete"]
    errors: list[str] = []
    status = row.get("source_independence_status")
    if status not in {"assessed", "unassessed", "rejected"}:
        errors.append("decision_projection_source_independence_status_invalid")
    raw_errors = row.get("source_independence_errors")
    if not _is_sequence(raw_errors) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 160
        for item in raw_errors
    ):
        errors.append("decision_projection_source_independence_errors_invalid")
    for field in count_fields:
        value = row.get(field)
        if type(value) is not int or value < 0:
            errors.append(
                f"decision_projection_source_independence_count_invalid:{field}"
            )

    if not isinstance(contract, Mapping):
        return [
            *errors,
            "decision_projection_source_independence_invalid_type",
        ]
    if not contract:
        if status == "assessed":
            errors.append("decision_projection_source_independence_assessed_without_contract")
        if status == "rejected" and not _items(raw_errors):
            errors.append("decision_projection_source_independence_rejected_without_error")
        for field in count_fields:
            if row.get(field) != 0:
                errors.append(
                    f"decision_projection_source_independence_alias_mismatch:{field}"
                )
        return errors

    if status != "assessed" or _items(raw_errors):
        errors.append("decision_projection_source_independence_contract_status_mismatch")

    if contract.get("schema_id") == event_source_independence_store.REFERENCE_SCHEMA_ID:
        if (
            row.get("decision_projection_schema_version")
            != DECISION_PROJECTION_SCHEMA_VERSION
        ):
            errors.append(
                "decision_projection_source_independence_reference_requires_v2"
            )
        errors.extend(
            f"decision_projection_source_independence_reference:{error}"
            for error in event_source_independence_store.validate_reference(contract)
        )
        for field, contract_field in count_fields.items():
            if row.get(field) != contract.get(contract_field):
                errors.append(
                    f"decision_projection_source_independence_alias_mismatch:{field}"
                )
        return errors

    errors.extend(
        f"decision_projection_source_independence:{error}"
        for error in event_source_independence.validate_source_independence_contract(
            contract
        )
    )
    for field, contract_field in count_fields.items():
        if row.get(field) != contract.get(contract_field):
            errors.append(
                f"decision_projection_source_independence_alias_mismatch:{field}"
            )
    return errors


def _validate_projection_catalyst_attributions(
    row: Mapping[str, Any],
) -> list[str]:
    if "catalyst_attributions" not in row:
        return []
    values = row.get("catalyst_attributions")
    if not _is_sequence(values):
        return ["decision_projection_catalyst_attributions_invalid_type"]
    errors: list[str] = []
    digests: list[str] = []
    raw_anomaly_id = row.get("market_anomaly_id")
    explicit_anomaly_id = (
        raw_anomaly_id.strip() if isinstance(raw_anomaly_id, str) else ""
    )
    observation_ids = (
        row.get("observation_ids", ())
        if _is_sequence(row.get("observation_ids"))
        else ()
    )
    candidate_ids = (
        {explicit_anomaly_id}
        if explicit_anomaly_id
        else {
            value.strip()
            for value in observation_ids
            if isinstance(value, str) and value.strip()
        }
    )
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            errors.append(
                f"decision_projection_catalyst_attribution_{index}:not_mapping"
            )
            continue
        contract_errors = event_catalyst_attribution.validate_contract(value)
        errors.extend(
            f"decision_projection_catalyst_attribution_{index}:{error}"
            for error in contract_errors
        )
        anomaly_id = value.get("anomaly_id")
        if (
            not candidate_ids
            or not isinstance(anomaly_id, str)
            or anomaly_id not in candidate_ids
        ):
            errors.append(
                f"decision_projection_catalyst_attribution_{index}:anomaly_binding_mismatch"
            )
        digest = str(
            value.get("attribution_digest") or value.get("digest") or ""
        )
        if digest:
            digests.append(digest)
    if len(digests) != len(set(digests)):
        errors.append("decision_projection_catalyst_attributions_duplicate")
    return errors


def _validate_projection_calendar_and_rsi(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    evidence = row.get("calendar_evidence")
    evidence_ids: list[str] = []
    if _is_sequence(evidence):
        for item in evidence:
            if not isinstance(item, Mapping):
                errors.append("decision_projection_calendar_evidence_invalid")
                continue
            raw_event_id = item.get("calendar_event_id")
            raw_reference = item.get("evidence_reference")
            event_id = raw_event_id.strip() if isinstance(raw_event_id, str) else ""
            reference = raw_reference.strip() if isinstance(raw_reference, str) else ""
            if raw_event_id not in (None, "") and not event_id:
                errors.append("decision_projection_calendar_event_id_invalid")
            if raw_reference not in (None, "") and not reference:
                errors.append("decision_projection_calendar_reference_invalid")
            if not event_id and not reference:
                errors.append("decision_projection_calendar_evidence_unresolvable")
            if event_id:
                evidence_ids.append(event_id)
            category = item.get("category")
            event_kind = item.get("event_kind")
            if category not in (None, "") and not (
                isinstance(category, str) and category.strip()
            ):
                errors.append("decision_projection_calendar_category_invalid")
            if event_kind not in (None, "") and not (
                isinstance(event_kind, str) and event_kind.strip()
            ):
                errors.append("decision_projection_calendar_event_kind_invalid")
            if not any(
                isinstance(value, str) and value.strip()
                for value in (category, event_kind)
            ):
                errors.append("decision_projection_calendar_category_missing")
            if not isinstance(item.get("time_certainty"), str) or item.get(
                "time_certainty"
            ) not in {
                "exact", "window", "estimated", "unknown",
            }:
                errors.append("decision_projection_calendar_time_certainty_invalid")
            if not isinstance(item.get("importance"), str) or item.get(
                "importance"
            ) not in {
                "low", "medium", "high", "critical", "unknown",
            }:
                errors.append("decision_projection_calendar_importance_invalid")
            for field in ("source", "source_url"):
                value = item.get(field)
                if value not in (None, "") and not (
                    isinstance(value, str) and value.strip()
                ):
                    errors.append(
                        f"decision_projection_calendar_{field}_invalid"
                    )
            timestamps = (
                item.get("scheduled_at"), item.get("window_start"), item.get("window_end"),
            )
            if not any(value not in (None, "") for value in timestamps):
                errors.append("decision_projection_calendar_time_missing")
            elif any(
                value not in (None, "")
                and (
                    not isinstance(value, str)
                    or _aware_timestamp(value) is None
                )
                for value in timestamps
            ):
                errors.append("decision_projection_calendar_time_invalid")
    raw_evidence_ids = row.get("calendar_evidence_ids")
    raw_evidence_id_values = (
        tuple(raw_evidence_ids) if _is_sequence(raw_evidence_ids) else ()
    )
    typed_evidence_ids = (
        tuple(
            value.strip()
            for value in raw_evidence_id_values
            if isinstance(value, str) and value.strip()
        )
        if raw_evidence_id_values
        else ()
    )
    if len(typed_evidence_ids) != len(raw_evidence_id_values):
        errors.append("decision_projection_calendar_ids_invalid")
    if typed_evidence_ids != tuple(evidence_ids):
        errors.append("decision_projection_calendar_ids_mismatch")
    if str(row.get("radar_route") or "") == "calendar_risk" and not (
        _is_sequence(evidence) and any(isinstance(item, Mapping) for item in evidence)
    ):
        errors.append("decision_projection_calendar_risk_without_evidence")

    rsi_context = row.get("rsi_context")
    rsi_references = row.get("rsi_context_references")
    context = rsi_context if isinstance(rsi_context, Mapping) else {}
    if context:
        if not _canonical_text(context.get("context_version")):
            errors.append("decision_projection_rsi_context_version_invalid")
        if not isinstance(context.get("valid"), bool):
            errors.append("decision_projection_rsi_context_valid_invalid")
        if not _canonical_text(context.get("freshness_status")):
            errors.append("decision_projection_rsi_context_freshness_invalid")
        for field in _RSI_REFERENCE_TEXT_FIELDS:
            value = context.get(field)
            if value is not None and not _canonical_text(value):
                errors.append(
                    f"decision_projection_rsi_context_value_invalid:{field}"
                )
        observed_at = context.get("observed_at")
        if observed_at is not None and _aware_timestamp(observed_at) is None:
            errors.append("decision_projection_rsi_context_timestamp_invalid")

    reference_rows: list[Mapping[str, Any]] = []
    if _is_sequence(rsi_references):
        for item in rsi_references:
            if not isinstance(item, Mapping):
                errors.append("decision_projection_rsi_reference_invalid")
                continue
            reference_rows.append(item)
            if set(item) != _RSI_REFERENCE_FIELDS:
                errors.append("decision_projection_rsi_reference_fields_invalid")
                continue
            if not _canonical_text(item.get("context_version")):
                errors.append("decision_projection_rsi_reference_version_invalid")
            if not isinstance(item.get("valid"), bool):
                errors.append("decision_projection_rsi_reference_valid_invalid")
            if not _canonical_text(item.get("freshness_status")):
                errors.append("decision_projection_rsi_reference_freshness_invalid")
            for field in _RSI_REFERENCE_TEXT_FIELDS:
                value = item.get(field)
                if value is not None and not _canonical_text(value):
                    errors.append(
                        f"decision_projection_rsi_reference_value_invalid:{field}"
                    )
            observed_at = item.get("observed_at")
            if observed_at is not None and _aware_timestamp(observed_at) is None:
                errors.append("decision_projection_rsi_reference_timestamp_invalid")
    if context and not reference_rows:
        errors.append("decision_projection_rsi_context_unreferenced")
    elif context:
        expected = {field: context.get(field) for field in _RSI_REFERENCE_FIELDS}
        if not any(dict(reference) == expected for reference in reference_rows):
            errors.append("decision_projection_rsi_reference_context_mismatch")
    return errors


def _validate_scores_and_expiry(
    row: Mapping[str, Any],
    *,
    extended_contract: bool,
) -> list[str]:
    errors: list[str] = []
    score_fields = ["actionability_score", "evidence_confidence_score", "risk_score"]
    if extended_contract:
        score_fields.extend(("urgency_score", "chase_risk_score"))
    for field in score_fields:
        score = _finite_number(row.get(field))
        if score is None:
            errors.append(f"decision_model_invalid_score:{field}")
            continue
        if not 0.0 <= score <= 100.0:
            errors.append(f"decision_model_score_out_of_range:{field}")
    expires_at = row.get("expires_at")
    expiry = _aware_timestamp(expires_at) if expires_at not in (None, "") else None
    if expires_at not in (None, "") and expiry is None:
        errors.append("decision_model_invalid_timestamp:expires_at")
    evaluated_at = next(
        (
            _aware_timestamp(row.get(field))
            for field in ("decision_evaluated_at", "evaluated_at", "generated_at", "observed_at")
            if row.get(field) not in (None, "")
        ),
        None,
    )
    if expiry is not None and evaluated_at is not None and expiry <= evaluated_at and row.get("radar_actionable") is True:
        errors.append("decision_model_expired_idea_actionable")
    return errors


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping))


def _canonical_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _items(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.replace(";", ",").split(",") if item.strip())
    if isinstance(value, Mapping):
        return tuple(str(item) for item in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


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
    return parsed


def _has_calendar_evidence(row: Mapping[str, Any]) -> bool:
    canonical = row.get("calendar_evidence")
    if _is_sequence(canonical) and any(isinstance(item, Mapping) and bool(item) for item in canonical):
        return True
    for field in (
        "unified_calendar_event", "calendar_event", "scheduled_catalyst_event", "unlock_event",
    ):
        if isinstance(row.get(field), Mapping) and bool(row.get(field)):
            return True
    nearby = row.get("nearby_calendar_events") or row.get("calendar_events")
    if _is_sequence(nearby) and any(isinstance(item, Mapping) and bool(item) for item in nearby):
        return True
    return _aware_timestamp(row.get("scheduled_at")) is not None


def _validate_market_return_units(row: Mapping[str, Any]) -> list[str]:
    return_fields = (
        "return_5m", "return_15m", "return_1h", "return_4h", "return_24h", "return_72h",
        "return_7d", "relative_return_vs_btc", "relative_return_vs_eth",
        "relative_return_vs_sector", "relative_return_vs_btc_1h",
        "relative_return_vs_btc_4h", "relative_return_vs_btc_24h",
        "relative_return_vs_eth_1h", "relative_return_vs_eth_4h",
        "relative_return_vs_eth_24h", "open_interest_delta", "open_interest_delta_1h",
        "open_interest_delta_4h", "open_interest_delta_24h", "dex_volume_change",
        "dex_liquidity_change",
    )
    errors: list[str] = []
    for snapshot_field in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        snapshot = row.get(snapshot_field)
        if not isinstance(snapshot, Mapping):
            continue
        values = tuple(field for field in return_fields if snapshot.get(field) not in (None, ""))
        if not values:
            continue
        common_unit = _return_unit(snapshot.get("return_unit"))
        raw_overrides = next(
            (
                snapshot.get(field)
                for field in ("return_units", "return_unit_by_field", "field_return_units")
                if field in snapshot
            ),
            None,
        )
        if raw_overrides is not None and not isinstance(raw_overrides, Mapping):
            errors.append(f"decision_model_invalid_return_unit_metadata:{snapshot_field}")
            overrides: Mapping[str, Any] = {}
        else:
            overrides = raw_overrides or {}
        for field in overrides:
            if str(field) not in return_fields:
                errors.append(f"decision_model_unknown_return_unit_field:{snapshot_field}:{field}")
        for field in values:
            unit = _return_unit(overrides.get(field)) if field in overrides else common_unit
            if unit is None:
                errors.append(f"decision_model_return_unit_missing:{snapshot_field}:{field}")
                continue
            value = _finite_number(snapshot.get(field))
            if value is None:
                errors.append(f"decision_model_invalid_return_value:{snapshot_field}:{field}")
                continue
            if unit == "fraction" and abs(value) > 3.0:
                errors.append(f"decision_model_implausible_fraction_return:{snapshot_field}:{field}")
            if unit == "percent_points" and abs(value) > 300.0:
                errors.append(f"decision_model_implausible_percent_return:{snapshot_field}:{field}")
    return list(dict.fromkeys(errors))


def _return_unit(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if text in {"fraction", "fractions", "decimal", "raw_fraction"}:
        return "fraction"
    if text in {"percent", "percentage", "percent_points", "percentage_points", "pct", "pct_points"}:
        return "percent_points"
    return None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


__all__ = (
    "ALLOWED_CATALYST_STATUSES", "ALLOWED_CONFIDENCE_BANDS", "ALLOWED_DIRECTIONAL_BIASES",
    "ALLOWED_MARKET_PHASES", "ALLOWED_PREFERRED_HORIZONS", "ALLOWED_RADAR_ROUTES",
    "ALLOWED_SPREAD_STATUSES", "ALLOWED_THESIS_ORIGINS", "ALLOWED_TIMING_STATES",
    "ALLOWED_TRADABILITY_STATUSES", "DECISION_MODEL_VERSION",
    "DECISION_PROJECTION_SCHEMA_VERSION", "LEGACY_DECISION_PROJECTION_SCHEMA_VERSION",
    "SUPPORTED_DECISION_PROJECTION_SCHEMA_VERSIONS", "ENUMS", "FIELDS",
    "TYPES", "validate_contract",
)
