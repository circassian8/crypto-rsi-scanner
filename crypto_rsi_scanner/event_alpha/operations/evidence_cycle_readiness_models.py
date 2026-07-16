"""Closed value models for the read-only evidence-cycle readiness report."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class _EvidencePlannerCatalogRow:
    source_pack: str
    logical_query_count: int
    provider_hint_counts: Mapping[str, int]
    ordered_provider_hints: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _EvidenceProviderReadiness:
    provider_hint: str
    runtime_mapping: str
    mapping_kind: str
    logical_provider_fanout: int
    acquisition_mode: str
    evidence_query_eligible: bool
    live_evidence_eligible: bool
    profile_live_capability: bool
    current_explicit_authorization: bool
    current_authorization_status: str
    current_provider_call_eligibility: bool
    http_request_fanout_max_per_logical_query: int
    credential_requirement: str
    credential_present: bool | None
    configured_local_source_status: str
    persisted_health_status: str
    persisted_health_disabled_until: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _PersistedEvidencePlanReadiness:
    status: str
    scope: str
    source_file: str
    latest_run_id: str | None
    plan_count: int | None
    logical_query_count: int | None
    budgeted_logical_query_count_upper_bound: int | None
    provider_hint_counts: Mapping[str, int] | None
    budgeted_http_request_upper_bound: int | None
    input_truncated: bool
    applies_to_next_cycle: str
    note: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _EvidenceCycleReadiness:
    contract_version: str
    checked_at: str
    status: str
    profile: str
    profile_run_mode: str
    profile_send_lane_policy: str
    profile_requests_send: bool
    artifact_namespace: str
    acquisition_enabled: bool
    fixture_only: bool
    max_candidates: int
    max_logical_queries: int
    max_results_per_query: int
    timeout_seconds: float
    deterministic_catalog: tuple[_EvidencePlannerCatalogRow, ...]
    deterministic_catalog_provider_hint_counts: Mapping[str, int]
    deterministic_catalog_logical_query_count: int
    deterministic_catalog_max_queries_per_candidate: int
    persisted_current_plan: _PersistedEvidencePlanReadiness
    selected_provider_hints_status: str
    selected_provider_hints: tuple[str, ...] | None
    provider_mapping: tuple[_EvidenceProviderReadiness, ...]
    source_configuration_summary: Mapping[str, tuple[str, ...]]
    mapping_missing_hints: tuple[str, ...]
    mapping_fixture_fallback_hints: tuple[str, ...]
    gdelt_runtime_mapping_status: str
    gdelt_runtime_mapping_defect_fixed: bool
    evidence_acquisition_http_request_upper_bound: int
    logical_queries_are_http_requests: bool
    blockers: tuple[str, ...]
    candidate_dependent_provider_gaps: tuple[str, ...]
    warnings: tuple[str, ...]
    fresh_validation_cycle_status: str
    fresh_validation_cycle_permitted: bool
    provider_cadence_status: str
    next_safe_command: str
    expected_provider_activity_for_next_command: str
    authorization_boundary: str
    llm_profile_capability_enabled: bool
    llm_current_explicit_authorization: bool
    llm_provider: str
    llm_credential_present: bool | None
    llm_availability_status: str
    llm_stage_readiness: Mapping[str, Mapping[str, object]]
    llm_max_calls_per_run: int
    llm_max_calls_per_day: int
    llm_max_parallel_calls: int
    llm_required_for_readiness: bool
    llm_required_for_evidence_execution: bool
    no_send_state: str
    send_requested_by_readiness: bool
    telegram_configuration_inspected: bool
    readiness_contract_artifacts_produced: bool
    source_independence_contract_production: str
    source_independence_artifact_production: str
    catalyst_attribution_contract_production: str
    catalyst_attribution_artifact_production: str
    credential_values_read: bool
    credential_presence_inspected: bool
    provider_call_planned_by_readiness: bool
    provider_call_attempted_by_readiness: bool
    authorization_created_or_mutated: bool
    telegram_send_attempted: bool
    network_called: bool
    writes_performed: bool
    research_only: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


EvidencePlannerCatalogRow = _EvidencePlannerCatalogRow
EvidenceProviderReadiness = _EvidenceProviderReadiness
PersistedEvidencePlanReadiness = _PersistedEvidencePlanReadiness
EvidenceCycleReadiness = _EvidenceCycleReadiness

__all__ = (
    "EvidenceCycleReadiness",
    "EvidencePlannerCatalogRow",
    "EvidenceProviderReadiness",
    "PersistedEvidencePlanReadiness",
)
