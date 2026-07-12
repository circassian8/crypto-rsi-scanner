"""Schema adapter for the canonical outcome eligibility firewall."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ...outcomes.outcome_eligibility import (
    OUTCOME_DATA_SOURCES,
    OUTCOME_ELIGIBILITY_CONTRACT_VERSION,
    OUTCOME_ELIGIBILITY_MARKERS,
    OUTCOME_ELIGIBILITY_REQUIRED_FIELDS,
    OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS,
    OUTCOME_HORIZONS,
    OUTCOME_HORIZON_METADATA_FIELDS,
    OUTCOME_HORIZON_SECONDS,
    OUTCOME_IDENTITY_FIELDS,
    OUTCOME_INELIGIBLE_REASONS,
    OUTCOME_MATURITY_STATUSES,
    OUTCOME_PROVENANCE_STATUSES,
    calibration_ineligibility_reasons,
    canonical_outcome_identity,
    canonical_outcome_identity_key,
    effective_calibration_eligible,
    has_outcome_eligibility_marker,
    primary_horizon_for_lane,
    validate_contract,
)

OUTCOME_EVIDENCE_TELEMETRY_FIELDS = (
    "outcome_rows_supplied",
    "outcome_rows_eligible",
    "outcome_rows_excluded",
    "outcome_exclusion_reason_counts",
)
OUTCOME_EVIDENCE_TELEMETRY_TYPES = {
    "outcome_rows_supplied": "int",
    "outcome_rows_eligible": "int",
    "outcome_rows_excluded": "int",
    "outcome_exclusion_reason_counts": "dict",
}


def schema_specs(
    schema_factory: Callable[..., Any],
    *,
    decision_model_fields: tuple[str, ...],
    decision_model_types: Mapping[str, str],
    decision_model_enums: Mapping[str, tuple[str, ...]],
    allowed_opportunity_types: tuple[str, ...],
    common_safety: tuple[str, ...],
    common_lineage: tuple[str, ...],
) -> dict[str, Any]:
    """Return the legacy-readable outcome schema with optional firewall fields."""

    return {
        "outcome_row_v1": schema_factory(
            "outcome_row_v1",
            required=("row_type", "symbol", "opportunity_type"),
            optional=(
                "schema_id", "schema_version", "candidate_id", "core_opportunity_id",
                "outcome_status", "outcome_label", "maturation_state",
                "return_by_horizon", "max_favorable_excursion",
                "max_adverse_excursion", "price_data_status", "market_state_class",
                "crowding_class", "outcome_eligibility_contract_version",
                "outcome_data_source", "outcome_identity", "outcome_identity_key",
                "calibration_eligible", "calibration_ineligible_reasons",
                "primary_horizon", "horizon_metadata", "observation_price_provenance_status",
                "outcome_evaluated_at", "price_at_observation", "primary_horizon_return",
                "observation_price_source", "observation_price_id",
                "observation_price_observed_at",
                *decision_model_fields, *common_safety,
            ),
            types={
                **decision_model_types,
                "outcome_eligibility_contract_version": "int",
                "outcome_data_source": "str",
                "outcome_identity": "dict",
                "outcome_identity_key": "str",
                "calibration_eligible": "bool",
                "calibration_ineligible_reasons": "list",
                "primary_horizon": "str",
                "horizon_metadata": "dict",
                "observation_price_provenance_status": "str",
                "outcome_evaluated_at": "str",
                "price_at_observation": "float",
                "observation_price_source": "str",
                "observation_price_id": "str",
                "observation_price_observed_at": "str",
                "primary_horizon_return": "float",
            },
            enums={
                "opportunity_type": allowed_opportunity_types,
                "outcome_data_source": tuple(sorted(OUTCOME_DATA_SOURCES)),
                "primary_horizon": OUTCOME_HORIZONS,
                "observation_price_provenance_status": tuple(sorted(OUTCOME_PROVENANCE_STATUSES)),
                **decision_model_enums,
            },
            safety=common_safety,
            timestamps=(
                "observed_at", "matured_at", "outcome_evaluated_at",
                "observation_price_observed_at",
            ),
            lineage=common_lineage,
        )
    }


__all__ = (
    "OUTCOME_DATA_SOURCES",
    "OUTCOME_ELIGIBILITY_CONTRACT_VERSION",
    "OUTCOME_ELIGIBILITY_MARKERS",
    "OUTCOME_ELIGIBILITY_REQUIRED_FIELDS",
    "OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS",
    "OUTCOME_EVIDENCE_TELEMETRY_FIELDS",
    "OUTCOME_EVIDENCE_TELEMETRY_TYPES",
    "OUTCOME_HORIZONS",
    "OUTCOME_HORIZON_METADATA_FIELDS",
    "OUTCOME_HORIZON_SECONDS",
    "OUTCOME_IDENTITY_FIELDS",
    "OUTCOME_INELIGIBLE_REASONS",
    "OUTCOME_MATURITY_STATUSES",
    "OUTCOME_PROVENANCE_STATUSES",
    "calibration_ineligibility_reasons",
    "canonical_outcome_identity",
    "canonical_outcome_identity_key",
    "effective_calibration_eligible",
    "has_outcome_eligibility_marker",
    "primary_horizon_for_lane",
    "schema_specs",
    "validate_contract",
)
