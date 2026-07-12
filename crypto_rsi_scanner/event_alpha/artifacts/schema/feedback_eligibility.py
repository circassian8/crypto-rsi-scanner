"""Schema adapter for the exact Event Alpha feedback eligibility firewall."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from . import decision_model as decision_model_specs
from ...outcomes.feedback_eligibility import (
    FEEDBACK_ELIGIBILITY_CONTRACT_VERSION,
    FEEDBACK_ELIGIBILITY_MARKERS,
    FEEDBACK_ELIGIBILITY_REQUIRED_FIELDS,
    FEEDBACK_IDENTITY_FIELDS,
    FEEDBACK_INELIGIBLE_REASONS,
    FEEDBACK_TARGET_TYPE,
    VALID_FEEDBACK_LABELS,
    build_feedback_eligibility_fields,
    canonical_feedback_identity,
    canonical_feedback_identity_key,
    canonical_feedback_join_identity,
    effective_feedback_eligible,
    effective_feedback_state,
    feedback_notes_are_safe,
    feedback_ineligibility_reasons,
    has_feedback_eligibility_marker,
    partition_joined_calibration_feedback,
    validate_contract,
)

FEEDBACK_EVIDENCE_TELEMETRY_FIELDS = (
    "feedback_rows_supplied",
    "feedback_rows_eligible",
    "feedback_rows_excluded",
    "feedback_exclusion_reason_counts",
)
FEEDBACK_EVIDENCE_TELEMETRY_TYPES = {
    "feedback_rows_supplied": "int",
    "feedback_rows_eligible": "int",
    "feedback_rows_excluded": "int",
    "feedback_exclusion_reason_counts": "dict",
}
FEEDBACK_ROW_FIELD_TYPES = {
    "schema_version": "str",
    "row_type": "str",
    "feedback_id": "str",
    "target": "str",
    "key": "str",
    "event_id": "str",
    "incident_id": "str",
    "coin_id": "str",
    "symbol": "str",
    "relationship_type": "str",
    "external_asset": "str",
    "event_time": "str",
    "label": "str",
    "marked_at": "str",
    "marked_by": "str",
    "notes": "str",
    "source": "str",
    "state": "str",
    "route": "str",
    "playbook_type": "str",
    "latest_score": "int",
    "watchlist_last_seen_at": "str",
    "source_class": "str",
    "source_domain": "str",
    "evidence_specificity": "str",
    "impact_path_type": "str",
    "candidate_role": "str",
    "opportunity_level": "str",
    "market_confirmation_level": "str",
    "source_pack": "str",
    "source_provider": "str",
    "accepted_evidence_reason_codes": "list",
    "feedback_target": "str",
    "feedback_target_type": "str",
    "core_opportunity_id": "str",
    "card_path": "str",
    "run_id": "str",
    "run_mode": "str",
    "profile": "str",
    "artifact_namespace": "str",
    "hypothesis_id": "str",
    "watchlist_key": "str",
    "final_route_after_quality_gate": "str",
    "lane": "str",
    "market_context_freshness_status": "str",
    "catalyst_frame_status": "str",
    "main_frame_type": "str",
    "source_provider_domain": "str",
    "provider_coverage_status": "str",
    "source_metadata": "dict",
    "schema_id": "str",
    "feedback_eligibility_contract_version": "int",
    "feedback_identity": "dict",
    "feedback_identity_key": "str",
    "calibration_eligible": "bool",
    "calibration_ineligible_reasons": "list",
    "research_only": "bool",
    **decision_model_specs.TYPES,
}
_PRIOR_GROUP_NAMES = (
    "playbook_priors",
    "provider_priors",
    "llm_role_priors",
    "tier_priors",
    "source_pack_priors",
    "source_domain_priors",
    "market_confirmation_priors",
    "catalyst_frame_priors",
)


def schema_specs(
    schema_factory: Callable[..., Any],
    *,
    common_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    """Return a legacy-readable feedback schema with optional v1 firewall fields."""

    required = ("row_type", "target", "label", "marked_at")
    declared = tuple(
        dict.fromkeys(
            (
                *FEEDBACK_ROW_FIELD_TYPES,
                *common_safety,
                *common_lineage,
            )
        )
    )
    return {
        "feedback_row_v1": schema_factory(
            "feedback_row_v1",
            required=required,
            optional=tuple(field for field in declared if field not in required),
            types=FEEDBACK_ROW_FIELD_TYPES,
            enums={
                "label": tuple(sorted(VALID_FEEDBACK_LABELS)),
                **decision_model_specs.ENUMS,
            },
            paths=("card_path",),
            safety=common_safety,
            timestamps=("marked_at", "event_time", "watchlist_last_seen_at"),
            lineage=common_lineage,
        )
    }


def validate_prior_contract(row: Mapping[str, Any]) -> list[str]:
    """Validate recommendation-only feedback priors without enabling them."""

    errors: list[str] = []
    if row.get("schema_version") != "event_alpha_calibration_priors_v2":
        errors.append("feedback_prior_schema_version_invalid")
    if row.get("row_type") != "event_alpha_calibration_priors":
        errors.append("feedback_prior_row_type_invalid")
    if row.get("feedback_firewall_applied") is not True:
        errors.append("feedback_prior_firewall_not_applied")
    if row.get("feedback_eligibility_contract_version") != FEEDBACK_ELIGIBILITY_CONTRACT_VERSION:
        errors.append("feedback_prior_contract_version_invalid")
    if row.get("research_only") is not True or row.get("recommendation_only") is not True:
        errors.append("feedback_prior_not_recommendation_only")
    if row.get("auto_apply") is not False:
        errors.append("feedback_prior_auto_apply_not_false")

    supplied = _nonnegative_int(row.get("feedback_rows_supplied"))
    eligible = _nonnegative_int(row.get("feedback_rows_eligible"))
    excluded = _nonnegative_int(row.get("feedback_rows_excluded"))
    if None in (supplied, eligible, excluded) or supplied != eligible + excluded:
        errors.append("feedback_prior_denominator_mismatch")
    min_sample = _positive_int(row.get("min_sample"))
    if min_sample is None or type(row.get("min_sample_warning")) is not bool:
        errors.append("feedback_prior_min_sample_invalid")
    elif eligible is not None and row.get("min_sample_warning") is not (eligible < min_sample):
        errors.append("feedback_prior_min_sample_warning_mismatch")

    generated = _aware_time(row.get("generated_at"))
    evaluated = _aware_time(row.get("feedback_firewall_evaluated_at"))
    if generated is None or evaluated is None or generated < evaluated:
        errors.append("feedback_prior_clock_invalid")
    if not _reason_counts_valid(row.get("feedback_exclusion_reason_counts"), excluded):
        errors.append("feedback_prior_exclusion_counts_invalid")
    if min_sample is not None and eligible is not None:
        for group_name in _PRIOR_GROUP_NAMES:
            if not _prior_group_valid(row.get(group_name), min_sample, eligible):
                errors.append(f"feedback_prior_group_invalid:{group_name}")
    # Keep schema/doctor acceptance exactly aligned with the runtime loader.
    # The lazy import avoids a module-import cycle through the schema registry.
    from ...outcomes import priors as feedback_priors

    if not feedback_priors.prior_payload_is_valid(row):
        errors.append("feedback_prior_payload_invalid")
    return errors


def _prior_group_valid(value: Any, min_sample: int, eligible: int) -> bool:
    if not isinstance(value, Mapping):
        return False
    samples_seen = 0
    for key, item in value.items():
        if type(key) is not str or not key or not isinstance(item, Mapping):
            return False
        counts = tuple(_nonnegative_int(item.get(name)) for name in ("samples", "useful", "junk", "watch"))
        if any(count is None for count in counts):
            return False
        samples, useful, junk, watch = counts
        if useful + junk + watch > samples:
            return False
        if item.get("min_sample_warning") is not (samples < min_sample):
            return False
        adjustment = item.get("score_adjustment")
        if type(adjustment) is not int or (samples < min_sample and adjustment != 0):
            return False
        samples_seen += samples
    return samples_seen == eligible


def _reason_counts_valid(value: Any, excluded: int | None) -> bool:
    if excluded is None or not isinstance(value, Mapping):
        return False
    total = 0
    for reason, count in value.items():
        if (
            type(reason) is not str
            or reason not in FEEDBACK_INELIGIBLE_REASONS
            or _positive_int(count) is None
        ):
            return False
        total += count
    return (not value) if excluded == 0 else total >= excluded


def _aware_time(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _nonnegative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _positive_int(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


__all__ = (
    "FEEDBACK_ELIGIBILITY_CONTRACT_VERSION",
    "FEEDBACK_ELIGIBILITY_MARKERS",
    "FEEDBACK_ELIGIBILITY_REQUIRED_FIELDS",
    "FEEDBACK_EVIDENCE_TELEMETRY_FIELDS",
    "FEEDBACK_EVIDENCE_TELEMETRY_TYPES",
    "FEEDBACK_IDENTITY_FIELDS",
    "FEEDBACK_INELIGIBLE_REASONS",
    "FEEDBACK_ROW_FIELD_TYPES",
    "FEEDBACK_TARGET_TYPE",
    "VALID_FEEDBACK_LABELS",
    "build_feedback_eligibility_fields",
    "canonical_feedback_identity",
    "canonical_feedback_identity_key",
    "canonical_feedback_join_identity",
    "effective_feedback_eligible",
    "effective_feedback_state",
    "feedback_notes_are_safe",
    "feedback_ineligibility_reasons",
    "has_feedback_eligibility_marker",
    "partition_joined_calibration_feedback",
    "schema_specs",
    "validate_contract",
    "validate_prior_contract",
)
