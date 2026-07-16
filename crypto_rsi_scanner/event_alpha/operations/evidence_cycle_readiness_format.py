"""Text rendering for the read-only evidence-cycle readiness contract."""

from __future__ import annotations

from .evidence_cycle_readiness_models import EvidenceCycleReadiness


def format_evidence_cycle_readiness(report: EvidenceCycleReadiness) -> str:
    """Render the closed readiness projection without inspecting runtime state."""

    lines = [
        "=" * 76,
        "EVENT ALPHA EVIDENCE-CYCLE READINESS (read-only / research-only)",
        "=" * 76,
        f"status={report.status}",
        (
            f"profile={report.profile} run_mode={report.profile_run_mode} "
            f"namespace={report.artifact_namespace}"
        ),
        (
            f"acquisition_enabled={str(report.acquisition_enabled).lower()} "
            f"fixture_only={str(report.fixture_only).lower()} "
            f"max_candidates={report.max_candidates} "
            f"max_logical_queries={report.max_logical_queries}"
        ),
        "",
        "deterministic pre-cycle catalog (not a materialized cycle plan):",
        (
            f"- source_packs={len(report.deterministic_catalog)} "
            f"catalog_logical_queries={report.deterministic_catalog_logical_query_count} "
            f"max_queries_per_candidate={report.deterministic_catalog_max_queries_per_candidate}"
        ),
        f"- provider_hint_counts={dict(report.deterministic_catalog_provider_hint_counts)}",
        (
            "- bounded evidence-acquisition HTTP-request upper bound="
            f"{report.evidence_acquisition_http_request_upper_bound}; "
            "logical queries are not HTTP requests; this excludes discovery, "
            "market, enrichment, and LLM stages"
        ),
        "",
        "exact persisted current-plan snapshot:",
        f"- status={report.persisted_current_plan.status}",
        f"- latest_run_id={report.persisted_current_plan.latest_run_id or 'none'}",
        (
            f"- plan_count={_display(report.persisted_current_plan.plan_count)} "
            f"logical_query_count={_display(report.persisted_current_plan.logical_query_count)} "
            f"provider_hint_counts={_display(report.persisted_current_plan.provider_hint_counts)}"
        ),
        (
            f"- selected_provider_hints_status={report.selected_provider_hints_status} "
            f"selected_provider_hints={_display(report.selected_provider_hints)}"
        ),
        f"- note={report.persisted_current_plan.note}",
        "",
        "source configuration summary:",
        *(
            f"- {key}={list(value)}"
            for key, value in report.source_configuration_summary.items()
        ),
        "",
        "actual runtime provider mapping / HTTP fan-out:",
    ]
    for row in report.provider_mapping:
        lines.append(
            f"- {row.provider_hint}: mapping={row.runtime_mapping} kind={row.mapping_kind} "
            f"mode={row.acquisition_mode} logical_fanout={row.logical_provider_fanout} "
            f"http_fanout_max={row.http_request_fanout_max_per_logical_query} "
            f"call_eligible={str(row.current_provider_call_eligibility).lower()} "
            f"profile_capability={str(row.profile_live_capability).lower()} "
            f"current_explicit_authorization={str(row.current_explicit_authorization).lower()} "
            f"authorization={row.current_authorization_status} "
            f"health={row.persisted_health_status}"
        )
    lines.extend(["", "blockers:"])
    if report.blockers:
        lines.extend(f"- {item}" for item in report.blockers)
    else:
        lines.append("- none")
    lines.append("candidate-dependent provider gaps:")
    if report.candidate_dependent_provider_gaps:
        lines.extend(f"- {item}" for item in report.candidate_dependent_provider_gaps)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            (
                f"gdelt_runtime_mapping_status={report.gdelt_runtime_mapping_status} "
                f"defect_fixed={str(report.gdelt_runtime_mapping_defect_fixed).lower()}"
            ),
            (
                f"fresh_validation_cycle_status={report.fresh_validation_cycle_status} "
                f"permitted={str(report.fresh_validation_cycle_permitted).lower()} "
                f"provider_cadence={report.provider_cadence_status}"
            ),
            (
                f"llm_availability={report.llm_availability_status} "
                f"provider={report.llm_provider} "
                f"profile_capability={str(report.llm_profile_capability_enabled).lower()} "
                f"current_explicit_authorization="
                f"{str(report.llm_current_explicit_authorization).lower()} "
                f"credential_present={_display(report.llm_credential_present)} "
                f"max_calls_per_run={report.llm_max_calls_per_run} "
                f"max_calls_per_day={report.llm_max_calls_per_day} "
                f"max_parallel_calls={report.llm_max_parallel_calls} "
                f"llm_required_for_readiness={str(report.llm_required_for_readiness).lower()} "
                f"llm_required_for_evidence_execution="
                f"{str(report.llm_required_for_evidence_execution).lower()}"
            ),
            "llm_stage_readiness:",
            *(
                f"- {stage}: provider={row['provider']} "
                f"profile_capability={str(bool(row['profile_capability'])).lower()} "
                f"current_explicit_authorization="
                f"{str(bool(row['current_explicit_authorization'])).lower()} "
                f"status={row['status']}"
                for stage, row in report.llm_stage_readiness.items()
            ),
            (
                f"no_send_state={report.no_send_state} "
                f"send_requested={str(report.send_requested_by_readiness).lower()} "
                f"telegram_configuration_inspected="
                f"{str(report.telegram_configuration_inspected).lower()}"
            ),
            "contract/artifact production:",
            f"- readiness_artifacts_produced={str(report.readiness_contract_artifacts_produced).lower()}",
            f"- source_independence_contract={report.source_independence_contract_production}",
            f"- source_independence_artifact={report.source_independence_artifact_production}",
            f"- catalyst_attribution_contract={report.catalyst_attribution_contract_production}",
            f"- catalyst_attribution_artifact={report.catalyst_attribution_artifact_production}",
            (
                f"credential_values_read={str(report.credential_values_read).lower()} "
                f"credential_presence_inspected="
                f"{str(report.credential_presence_inspected).lower()}"
            ),
            "",
            f"next_safe_command={report.next_safe_command}",
            f"expected_provider_activity={report.expected_provider_activity_for_next_command}",
            (
                "readiness_side_effects: provider_call_planned=false "
                "provider_call_attempted=false network_called=false "
                "writes_performed=false authorization_mutated=false "
                "telegram_send_attempted=false"
            ),
        ]
    )
    return "\n".join(lines).rstrip()


def _display(value: object) -> str:
    return "unknown_not_materialized" if value is None else str(value)


__all__ = ("format_evidence_cycle_readiness",)
