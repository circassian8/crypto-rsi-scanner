"""Semantic reconciliation for closed empirical research report inputs."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    empirical_live_campaign,
    empirical_policy_lab,
    empirical_replay_analysis,
    empirical_replay_controls,
    empirical_replay_persistence,
    empirical_replay_run,
    empirical_review,
    empirical_validation_protocol,
)


_TRACE_ZERO_FIELDS = (
    "provider_calls",
    "authorization_mutations",
    "telegram_sends",
    "trades",
    "orders",
    "event_alpha_paper_trades",
    "normal_rsi_writes",
    "event_alpha_triggered_fade",
    "dashboard_authority_mutations",
)


def validate_run_semantics(
    *,
    manifest: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    values: Mapping[str, Mapping[str, Any]],
    binding: dict[str, Any],
    expected_partitions: tuple[str, ...],
) -> None:
    summary = values["execution_summary.json"]
    trace = values["replay_trace_summary.json"]
    analyses = values["replay_analysis.json"]
    controls = values["replay_controls.json"]
    review = values["targeted_review_queue.json"]
    mode = str(manifest["configuration"]["mode"])
    protocol_sha = str(manifest["protocol_sha256"])
    protocol_version = str(manifest["protocol_version"])
    if (
        summary.get("schema_id") != empirical_replay_run.RUN_SCHEMA_ID
        or summary.get("schema_version") != empirical_replay_run.RUN_SCHEMA_VERSION
        or summary.get("mode") != mode
        or summary.get("run_fingerprint") != manifest["run_fingerprint"]
        or summary.get("research_only") is not True
        or summary.get("auto_apply") is not False
        or summary.get("policy_mutations") != 0
        or summary.get("provider_calls") != 0
        or summary.get("dashboard_authority_mutations") != 0
    ):
        raise ValueError("empirical execution summary contract invalid")
    if (
        trace.get("schema_id") != "decision_radar.empirical_replay_trace_summary"
        or trace.get("schema_version") != 1
        or trace.get("mode") != mode
        or trace.get("protocol_sha256") != protocol_sha
        or trace.get("protocol_version") != protocol_version
        or trace.get("research_only") is not True
        or trace.get("auto_apply") is not False
        or any(trace.get(field) != 0 for field in _TRACE_ZERO_FIELDS)
    ):
        raise ValueError("empirical trace summary contract invalid")
    _validate_execution_trace_counts(summary, trace, expected_partitions)
    idea_rows, episode_rows = _validated_archive_rows(payloads)
    _validate_archive_counts(
        manifest, binding, summary, trace, idea_rows, episode_rows
    )
    _validate_analyses(
        analyses,
        expected_partitions=expected_partitions,
        protocol_sha=protocol_sha,
        protocol_version=protocol_version,
        summary=summary,
    )
    _validate_controls_and_review(
        controls,
        review,
        protocol_sha=protocol_sha,
        protocol_version=protocol_version,
        run_fingerprint=str(manifest["run_fingerprint"]),
        summary=summary,
        partition_count=len(expected_partitions),
    )


def validate_published_bundle(
    *,
    validation: Mapping[str, Any],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    envelope: Mapping[str, Any],
    expected_report_filenames: tuple[str, ...],
    expected_safety: Mapping[str, Any],
) -> None:
    """Validate the closed publication semantics without reopening source runs."""

    expected_contract = {
        "thresholds_changed": False,
        "routes_changed": False,
        "policy_applied": False,
        "dashboard_authority_changed": False,
        "human_approval_required": True,
    }
    expected_lanes = {
        "historical_replay": "selection_and_final_test_kept_distinct",
        "live_no_send": "separate_digest_only_not_pooled_with_replay",
        "fixture": "not_used",
    }
    if (
        validation.get("schema_id") != "decision_radar.empirical_validation_report"
        or validation.get("schema_version") != 1
        or validation.get("report_status") != "closed_immutable_evidence_projection"
        or walk.get("schema_id") != "decision_radar.empirical_walk_forward_report"
        or walk.get("schema_version") != 1
        or policy.get("schema_id") != "decision_radar.empirical_policy_simulation_report"
        or policy.get("schema_version") != 1
        or any(row.get("safety") != expected_safety for row in (validation, walk, policy))
        or envelope.get("schema_id") != "decision_radar.empirical_research_report_bundle"
        or envelope.get("schema_version") != 1
        or envelope.get("safety") != expected_safety
        or envelope.get("production_contract") != expected_contract
        or envelope.get("evidence_lanes") != expected_lanes
        or envelope.get("report_artifacts") != list(expected_report_filenames)
    ):
        raise RuntimeError("empirical_research_report_publication_contract_invalid")
    _validate_published_sources(validation, walk, policy, envelope)
    _validate_published_policy(validation, walk, policy, envelope)
    _validate_published_live(envelope.get("live_campaign_report"))
    _validate_published_conclusions(validation.get("conclusions"), envelope)


def _validate_published_sources(
    validation: Mapping[str, Any],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> None:
    selection = envelope.get("selection_run")
    final = envelope.get("final_test_run")
    walk_value = walk.get("walk_forward")
    simulation = policy.get("selection_simulation")
    conclusion = walk.get("conclusion")
    selection_execution = validation.get("selection_execution")
    final_execution = validation.get("final_test_execution")
    selection_analysis = validation.get("selection_analysis")
    final_analysis = validation.get("final_test_analysis")
    selection_controls = validation.get("selection_controls")
    final_controls = validation.get("final_test_controls")
    review = validation.get("review_evidence")
    if (
        not isinstance(selection, Mapping)
        or not isinstance(final, Mapping)
        or any(
            row.get("immutable") is not True
            or row.get("research_only") is not True
            or row.get("auto_apply") is not False
            or row.get("protocol_version") != envelope.get("protocol_version")
            or row.get("protocol_sha256") != envelope.get("protocol_sha256")
            or not isinstance(row.get("archive_counts"), Mapping)
            for row in (selection, final)
        )
        or not isinstance(walk_value, Mapping)
        or not isinstance(simulation, Mapping)
        or not isinstance(conclusion, Mapping)
        or not isinstance(selection_execution, Mapping)
        or not isinstance(final_execution, Mapping)
        or not isinstance(selection_analysis, Mapping)
        or not isinstance(final_analysis, Mapping)
        or not isinstance(selection_controls, Mapping)
        or not isinstance(final_controls, Mapping)
        or not isinstance(review, Mapping)
        or walk_value.get("protocol_sha256") != envelope.get("protocol_sha256")
        or simulation.get("protocol_sha256") != envelope.get("protocol_sha256")
        or conclusion.get("sample_size")
        != walk_value.get("outcome_evaluable_fold_count")
        or conclusion.get("sample_unit")
        != "outcome_evaluable_chronological_walk_forward_folds"
        or selection_execution.get("run_fingerprint") != selection.get("run_fingerprint")
        or final_execution.get("run_fingerprint") != final.get("run_fingerprint")
    ):
        raise RuntimeError("empirical_research_report_source_contract_invalid")
    _validate_published_execution(
        selection_execution, selection, expected_mode="full"
    )
    _validate_published_execution(
        final_execution, final, expected_mode="final_test"
    )
    if (
        selection_analysis.get("schema_id")
        != "decision_radar.empirical_partition_analyses"
        or selection_analysis.get("schema_version") != 1
        or not isinstance(selection_analysis.get("partitions"), Mapping)
        or set(selection_analysis.get("partitions", {}))
        != {"development", "validation"}
        or final_analysis.get("schema_id")
        != "decision_radar.empirical_partition_analyses"
        or final_analysis.get("schema_version") != 1
        or not isinstance(final_analysis.get("partitions"), Mapping)
        or set(final_analysis.get("partitions", {})) != {"final_test"}
        or selection_controls.get("schema_id") != empirical_replay_controls.SCHEMA_ID
        or selection_controls.get("schema_version") != empirical_replay_controls.SCHEMA_VERSION
        or final_controls.get("schema_id") != empirical_replay_controls.SCHEMA_ID
        or final_controls.get("schema_version") != empirical_replay_controls.SCHEMA_VERSION
        or set(review) != {"selection", "final_test"}
    ):
        raise RuntimeError("empirical_research_report_source_contract_invalid")
    _validate_published_analysis_partitions(
        selection_analysis["partitions"], envelope
    )
    _validate_published_analysis_partitions(final_analysis["partitions"], envelope)
    for controls, execution in (
        (selection_controls, selection_execution),
        (final_controls, final_execution),
    ):
        if (
            controls.get("protocol_sha256") != envelope.get("protocol_sha256")
            or controls.get("idea_count") != execution.get("idea_count")
            or controls.get("observation_count") != execution.get("observation_count")
            or controls.get("safety") != empirical_replay_controls._SAFETY
            or controls.get("research_only") is not True
            or controls.get("auto_apply") is not False
        ):
            raise RuntimeError("empirical_research_report_source_contract_invalid")
    for name, row in review.items():
        expected = selection if name == "selection" else final
        if (
            not isinstance(row, Mapping)
            or row.get("schema_id") != empirical_review.SCHEMA_ID
            or row.get("schema_version") != empirical_review.SCHEMA_VERSION
            or row.get("run_fingerprint") != expected.get("run_fingerprint")
            or row.get("protocol_sha256") != envelope.get("protocol_sha256")
            or row.get("safety") != empirical_review._ZERO_SAFETY
        ):
            raise RuntimeError("empirical_research_report_source_contract_invalid")


def _validate_published_execution(
    execution: Mapping[str, Any],
    binding: Mapping[str, Any],
    *,
    expected_mode: str,
) -> None:
    counts = binding["archive_counts"]
    routes = execution.get("route_counts")
    if (
        execution.get("schema_id") != empirical_replay_run.RUN_SCHEMA_ID
        or execution.get("schema_version") != empirical_replay_run.RUN_SCHEMA_VERSION
        or execution.get("mode") != expected_mode
        or execution.get("idea_count") != counts.get("idea_count")
        or execution.get("episode_count") != counts.get("episode_count")
        or not isinstance(routes, Mapping)
        or sum(_count(value) for value in routes.values()) != execution.get("idea_count")
        or execution.get("provider_calls") != 0
        or execution.get("policy_mutations") != 0
        or execution.get("dashboard_authority_mutations") != 0
        or execution.get("research_only") is not True
        or execution.get("auto_apply") is not False
    ):
        raise RuntimeError("empirical_research_report_source_contract_invalid")


def _validate_published_analysis_partitions(
    partitions: Mapping[str, Any], envelope: Mapping[str, Any]
) -> None:
    for name, row in partitions.items():
        if (
            not isinstance(row, Mapping)
            or row.get("schema_id") != empirical_replay_analysis.SCHEMA_ID
            or row.get("schema_version") != empirical_replay_analysis.SCHEMA_VERSION
            or row.get("partition") != name
            or row.get("protocol_sha256") != envelope.get("protocol_sha256")
            or row.get("safety") != empirical_replay_analysis._ZERO_SAFETY
            or row.get("research_only") is not True
            or row.get("auto_apply") is not False
        ):
            raise RuntimeError("empirical_research_report_source_contract_invalid")


def _validate_published_policy(
    validation: Mapping[str, Any],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> None:
    seal = policy.get("frozen_recommendation_seal")
    confirmation = policy.get("final_test_confirmation")
    boundary = policy.get("decision_boundary")
    if not isinstance(seal, Mapping) or empirical_policy_lab.validate_recommendation_seal(seal):
        raise RuntimeError("empirical_research_report_seal_invalid")
    simulation = policy.get("selection_simulation")
    if not isinstance(simulation, Mapping):
        raise RuntimeError("empirical_research_report_seal_invalid")
    try:
        expected_seal = empirical_policy_lab.freeze_recommendation_set(
            simulation,
            selection_run_binding=seal.get("selection_run_binding", {}),
        )
    except ValueError as exc:
        raise RuntimeError("empirical_research_report_seal_invalid") from exc
    if seal != expected_seal:
        raise RuntimeError("empirical_research_report_seal_invalid")
    if (
        confirmation != validation.get("final_confirmation")
        or confirmation != walk.get("final_confirmation")
        or envelope.get("recommendation_seal_sha256") != seal.get("seal_sha256")
        or envelope.get("final_confirmation_sha256")
        != _sha256_bytes(_canonical_bytes(confirmation))
        or boundary != {
            "selection_uses_final_test": False,
            "final_test_can_nominate_new_scenarios": False,
            "automatic_policy_application": False,
            "human_approval_required": True,
            "production_policy_unchanged": True,
        }
    ):
        raise RuntimeError("empirical_research_report_policy_binding_invalid")
    _validate_published_confirmation(confirmation, seal)


def _validate_published_confirmation(
    value: Any, seal: Mapping[str, Any]
) -> None:
    if not isinstance(value, Mapping):
        raise RuntimeError("empirical_research_report_confirmation_invalid")
    rows = value.get("confirmations")
    evaluated = value.get("evaluated_scenarios")
    candidates = sorted(
        str(row.get("scenario") or "")
        for row in seal.get("recommendations", [])
        if isinstance(row, Mapping) and row.get("status") == "candidate"
    )
    if not isinstance(rows, list) or not isinstance(evaluated, list):
        raise RuntimeError("empirical_research_report_confirmation_invalid")
    row_names = [str(row.get("scenario") or "") for row in rows if isinstance(row, Mapping)]
    evaluated_names = [
        str(row.get("scenario") or "") for row in evaluated
        if isinstance(row, Mapping)
    ]
    statuses = Counter(str(row.get("confirmation_status") or "") for row in rows if isinstance(row, Mapping))
    expected_status = "complete" if candidates else "no_candidate_recommendations"
    if (
        len(row_names) != len(rows)
        or len(evaluated_names) != len(evaluated)
        or value.get("schema_id") != "decision_radar.empirical_final_test_confirmation"
        or value.get("schema_version") != 1
        or value.get("partition") != "final_test"
        or value.get("protocol_version") != seal.get("protocol_version")
        or value.get("protocol_sha256") != seal.get("protocol_sha256")
        or value.get("recommendation_seal_sha256") != seal.get("seal_sha256")
        or value.get("selection_run_binding") != seal.get("selection_run_binding")
        or value.get("scenario_set_sha256") != seal.get("scenario_set_sha256")
        or value.get("final_test_confirmation_rule")
        != seal.get("final_test_confirmation_rule")
        or value.get("final_test_confirmation_rule_sha256")
        != seal.get("final_test_confirmation_rule_sha256")
        or value.get("candidate_scenarios") != candidates
        or row_names != candidates
        or len(row_names) != len(set(row_names))
        or evaluated_names != ["production_policy", *candidates]
        or len(evaluated_names) != len(set(evaluated_names))
        or any(status not in {"confirmed", "rejected", "insufficient_sample"} for status in statuses)
        or value.get("confirmed_candidate_count") != statuses["confirmed"]
        or value.get("rejected_candidate_count") != statuses["rejected"]
        or value.get("insufficient_sample_candidate_count") != statuses["insufficient_sample"]
        or value.get("confirmation_status") != expected_status
        or value.get("scenario_selection_performed") is not False
        or value.get("final_test_used_for_selection") is not False
        or value.get("human_approval_required") is not True
        or value.get("production_policy_mutations") != 0
        or value.get("research_only") is not True
        or value.get("auto_apply") is not False
    ):
        raise RuntimeError("empirical_research_report_confirmation_invalid")
    production = evaluated[0]
    if any(
        production.get(field) != value.get(top)
        for field, top in (
            ("observed_day_count", "selected_observation_day_count"),
            ("observed_day_denominator_basis", "observed_day_denominator_basis"),
            ("selected_observation_days_sha256", "selected_observation_days_sha256"),
        )
    ):
        raise RuntimeError("empirical_research_report_confirmation_invalid")
    for row, scenario in zip(rows, evaluated[1:], strict=True):
        if (
            any(
                not (
                    scenario.get(field)
                    == production.get(field)
                    == value.get(top)
                )
                for field, top in (
                    ("observed_day_count", "selected_observation_day_count"),
                    ("observed_day_denominator_basis", "observed_day_denominator_basis"),
                    ("selected_observation_days_sha256", "selected_observation_days_sha256"),
                )
            )
            or row != empirical_policy_lab._final_confirmation(
                scenario,
                production,
                rule=seal["final_test_confirmation_rule"],
            )
        ):
            raise RuntimeError("empirical_research_report_confirmation_invalid")


def _validate_published_live(value: Any) -> None:
    if not isinstance(value, Mapping) or value.get("evidence_pooled_with_replay") is not False:
        raise RuntimeError("empirical_research_report_live_binding_invalid")
    if value.get("status") == "not_provided":
        if value != {
            "status": "not_provided", "sha256": None, "size_bytes": 0,
            "evidence_pooled_with_replay": False,
        }:
            raise RuntimeError("empirical_research_report_live_binding_invalid")
        return
    projection = value.get("canonical_projection")
    if (
        value.get("status") != "provided_separate_observational_lane"
        or not isinstance(projection, Mapping)
        or projection.get("schema_id") != empirical_live_campaign.SCHEMA_ID
        or projection.get("schema_version")
        not in empirical_live_campaign.SUPPORTED_SCHEMA_VERSIONS
        or projection.get("research_only") is not True
        or projection.get("auto_apply") is not False
        or any(projection.get(field) != 0 for field in (
            "provider_calls", "writes", "authorization_mutations",
            "dashboard_authority_mutations",
        ))
        or value.get("canonical_projection_sha256")
        != _sha256_bytes(_canonical_bytes(projection))
    ):
        raise RuntimeError("empirical_research_report_live_binding_invalid")
    if projection.get("schema_version") == empirical_live_campaign.SCHEMA_VERSION:
        episodes = projection.get("episodes")
        if (
            not isinstance(episodes, Mapping)
            or episodes.get("statistical_independence_claim") is not False
            or episodes.get("cross_asset_independence_claim") is not False
        ):
            raise RuntimeError("empirical_research_report_live_binding_invalid")


def _validate_published_conclusions(
    value: Any, envelope: Mapping[str, Any]
) -> None:
    if not isinstance(value, Mapping):
        raise RuntimeError("empirical_research_report_conclusions_invalid")
    unchanged = value.get("what_remains_unchanged")
    live = value.get("live_campaign_integration")
    warnings = value.get("multiple_comparison_warnings")
    expected_warning = empirical_validation_protocol.protocol_values()["statistics"][
        "multiple_comparison_policy"
    ]
    route_findings = value.get("route_findings")
    origin_findings = value.get("origin_findings")
    expected_no_evidence_routes = [
        name
        for name in empirical_replay_analysis.ROUTES
        if isinstance(route_findings, Mapping)
        and isinstance(route_findings.get(name), Mapping)
        and route_findings[name].get("evidence_status") == "no_empirical_evidence"
    ]
    expected_no_evidence_origins = [
        name
        for name in empirical_replay_analysis.PRIMARY_ORIGINS
        if isinstance(origin_findings, Mapping)
        and isinstance(origin_findings.get(name), Mapping)
        and origin_findings[name].get("evidence_status") == "no_empirical_evidence"
    ]
    if (
        value.get("causal_claim") is not False
        or value.get("probabilistic_calibration_claim") is not False
        or value.get("trade_recommendation") is not False
        or value.get("production_policy_unchanged") is not True
        or value.get("automatic_policy_application") is not False
        or value.get("no_evidence_is_not_validation") is not True
        or not isinstance(route_findings, Mapping)
        or set(route_findings) != set(empirical_replay_analysis.ROUTES)
        or not isinstance(origin_findings, Mapping)
        or set(origin_findings) != set(empirical_replay_analysis.PRIMARY_ORIGINS)
        or value.get("routes_with_no_empirical_evidence")
        != expected_no_evidence_routes
        or value.get("origins_with_no_empirical_evidence")
        != expected_no_evidence_origins
        or unchanged != {
            "thresholds": True,
            "routes": True,
            "production_policy": True,
            "dashboard_authority": True,
            "provider_authorization": True,
            "notifications_and_execution": True,
        }
        or not isinstance(live, Mapping)
        or live.get("evidence_pooled_with_replay") is not False
        or live.get("separate_observational_lane") is not True
        or live.get("status")
        != envelope.get("live_campaign_report", {}).get("status")
        or not isinstance(warnings, Mapping)
        or any(
            warnings.get(name) != expected_warning
            for name in ("development", "validation", "final_test", "policy_simulation")
        )
    ):
        raise RuntimeError("empirical_research_report_conclusions_invalid")


def _validate_execution_trace_counts(
    summary: Mapping[str, Any],
    trace: Mapping[str, Any],
    expected_partitions: tuple[str, ...],
) -> None:
    exact_fields = (
        "observation_count",
        "selected_partition_observation_count",
        "selected_partition_observed_day_count",
        "selected_partition_observed_day_count_by_partition",
        "selected_partition_observed_day_basis",
        "selected_partition_observation_start_at",
        "selected_partition_observation_end_at",
        "idea_count",
        "idea_observed_day_count",
        "idea_count_per_selected_observed_day",
        "route_counts",
    )
    if any(summary.get(field) != trace.get(field) for field in exact_fields):
        raise ValueError("empirical execution and trace count mismatch")
    route_counts = trace.get("route_counts")
    partition_counts = trace.get("partition_counts")
    day_counts = trace.get("selected_partition_observed_day_count_by_partition")
    day_digests = trace.get("selected_partition_observed_days_sha256_by_partition")
    if (
        trace.get("observation_counting_unit") != "input_observation_rows"
        or trace.get("idea_counting_unit") != "canonical_idea_rows"
        or trace.get("route_counting_unit") != "canonical_idea_rows"
        or not isinstance(route_counts, Mapping)
        or set(route_counts) - set(empirical_replay_analysis.ROUTES)
        or sum(_count(value) for value in route_counts.values()) != trace.get("idea_count")
        or not isinstance(partition_counts, Mapping)
        or not set(partition_counts) <= set(expected_partitions)
        or sum(_count(value) for value in partition_counts.values()) != trace.get("idea_count")
        or not isinstance(day_counts, Mapping)
        or set(day_counts) != set(expected_partitions)
        or trace.get("selected_partition_observed_day_count")
        != sum(_count(value) for value in day_counts.values())
        or trace.get("selected_partition_observed_day_basis")
        != "exact_selected_observation_utc_days"
        or not isinstance(day_digests, Mapping)
        or set(day_digests) != set(expected_partitions)
        or any(not _is_sha256(value) for value in day_digests.values())
        or not _is_sha256(trace.get("selected_partition_observed_days_sha256"))
    ):
        raise ValueError("empirical trace taxonomy or denominator invalid")


def _validated_archive_rows(
    payloads: Mapping[str, bytes],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    try:
        ideas = empirical_replay_persistence.decode_archive_rows(
            empirical_replay_persistence.IDEA_INDEX_FILENAME, payloads
        )
        episodes = empirical_replay_persistence.decode_archive_rows(
            empirical_replay_persistence.EPISODE_INDEX_FILENAME, payloads
        )
    except ValueError as exc:
        raise ValueError("empirical replay persistence archive invalid") from exc
    return ideas, episodes


def _validate_archive_counts(
    manifest: Mapping[str, Any],
    binding: dict[str, Any],
    summary: Mapping[str, Any],
    trace: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
    episodes: Sequence[Mapping[str, Any]],
) -> None:
    idea_count = len(ideas)
    episode_count = len(episodes)
    metrics = manifest["metrics"]
    route_counts = Counter(
        str(row.get("decision_projection", {}).get("radar_route") or "diagnostic")
        for row in ideas
    )
    partition_counts = Counter(
        str(row.get("replay", {}).get("replay_partition") or "") for row in ideas
    )
    representative_ids = {
        str(row.get("representative_idea_id") or "") for row in episodes
    }
    idea_ids = {str(row.get("identity", {}).get("candidate_id") or "") for row in ideas}
    if (
        idea_count != summary.get("idea_count")
        or idea_count != metrics.get("idea_count")
        or episode_count != summary.get("episode_count")
        or episode_count != metrics.get("episode_count")
        or dict(sorted(route_counts.items())) != trace.get("route_counts")
        or dict(sorted(partition_counts.items())) != trace.get("partition_counts")
        or not representative_ids <= idea_ids
        or len(representative_ids) != episode_count
    ):
        raise ValueError("empirical replay archive count or identity mismatch")
    binding["archive_counts"] = {
        "idea_count": idea_count,
        "episode_count": episode_count,
    }


def _validate_analyses(
    value: Mapping[str, Any],
    *,
    expected_partitions: tuple[str, ...],
    protocol_sha: str,
    protocol_version: str,
    summary: Mapping[str, Any],
) -> None:
    partitions = value.get("partitions")
    if (
        value.get("schema_id") != "decision_radar.empirical_partition_analyses"
        or value.get("schema_version") != 1
        or value.get("research_only") is not True
        or value.get("auto_apply") is not False
        or not isinstance(partitions, Mapping)
        or set(partitions) != set(expected_partitions)
    ):
        raise ValueError("empirical partition analysis wrapper invalid")
    episode_total = matured_total = 0
    for name, row in partitions.items():
        if not isinstance(row, Mapping):
            raise ValueError("empirical partition analysis invalid")
        body = {key: item for key, item in row.items() if key != "analysis_digest"}
        routes = _closed_cohort_names(row.get("route_cohorts"))
        origins = _closed_cohort_names(row.get("primary_origin_cohorts"))
        episode_count = _count(row.get("episode_count"))
        matured = _count(row.get("matured_episode_count"))
        if (
            row.get("schema_id") != empirical_replay_analysis.SCHEMA_ID
            or row.get("schema_version") != empirical_replay_analysis.SCHEMA_VERSION
            or row.get("partition") != name
            or row.get("protocol_sha256") != protocol_sha
            or row.get("protocol_version") != protocol_version
            or row.get("research_only") is not True
            or row.get("auto_apply") is not False
            or row.get("policy_eligible") is not False
            or row.get("causal_claim") is not False
            or row.get("safety") != empirical_replay_analysis._ZERO_SAFETY
            or routes != set(empirical_replay_analysis.ROUTES)
            or origins != set(empirical_replay_analysis.PRIMARY_ORIGINS)
            or sum(_count(item.get("episode_count")) for item in row["route_cohorts"])
            != episode_count
            or sum(_count(item.get("episode_count")) for item in row["primary_origin_cohorts"])
            != episode_count
            or matured > episode_count
            or _count(row.get("directional_return_sample_size")) > matured
            or row.get("analysis_digest") != _value_sha256(body)
            or row.get("multiple_comparison_warning")
            != empirical_validation_protocol.protocol_values()["statistics"]["multiple_comparison_policy"]
        ):
            raise ValueError("empirical partition analysis semantic mismatch")
        episode_total += episode_count
        matured_total += matured
    if (
        episode_total != summary.get("episode_count")
        or matured_total != sum(summary.get("matured_episode_count_by_partition", {}).values())
    ):
        raise ValueError("empirical analysis execution count mismatch")


def _validate_controls_and_review(
    controls: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    protocol_sha: str,
    protocol_version: str,
    run_fingerprint: str,
    summary: Mapping[str, Any],
    partition_count: int,
) -> None:
    controls_body = {key: value for key, value in controls.items() if key != "contract_digest"}
    review_body = {key: value for key, value in review.items() if key != "queue_digest"}
    inputs = review.get("input_counts")
    if (
        controls.get("schema_id") != empirical_replay_controls.SCHEMA_ID
        or controls.get("schema_version") != empirical_replay_controls.SCHEMA_VERSION
        or controls.get("method") != empirical_replay_controls.METHOD
        or controls.get("protocol_sha256") != protocol_sha
        or controls.get("protocol_version") != protocol_version
        or controls.get("idea_count") != summary.get("idea_count")
        or controls.get("observation_count") != summary.get("observation_count")
        or controls.get("benchmark_policy_order")
        != empirical_validation_protocol.protocol_values()["benchmark_policies"]
        or controls.get("safety") != empirical_replay_controls._SAFETY
        or controls.get("research_only") is not True
        or controls.get("auto_apply") is not False
        or controls.get("selection_uses_outcomes") is not False
        or controls.get("matched_control_causal_claim") is not False
        or controls.get("final_test_used_for_tuning") is not False
        or controls.get("policy_eligible") is not False
        or controls.get("contract_digest") != _value_sha256(controls_body)
        or review.get("schema_id") != empirical_review.SCHEMA_ID
        or review.get("schema_version") != empirical_review.SCHEMA_VERSION
        or review.get("method") != "deterministic_outcome_aware_targeted_review_v1"
        or review.get("run_fingerprint") != run_fingerprint
        or review.get("protocol_sha256") != protocol_sha
        or review.get("protocol_version") != protocol_version
        or review.get("research_only") is not True
        or review.get("auto_apply") is not False
        or review.get("closed_category_taxonomy") is not True
        or review.get("category_order") != list(empirical_review.CATEGORY_ORDER)
        or review.get("selection_uses_outcomes") is not True
        or review.get("selection_changes_replay_results") is not False
        or review.get("final_test_used_for_policy_selection") is not False
        or review.get("causal_claim") is not False
        or review.get("policy_eligible") is not False
        or review.get("safety") != empirical_review._ZERO_SAFETY
        or review.get("item_count") != len(review.get("items", []))
        or review.get("queue_digest") != _value_sha256(review_body)
        or not isinstance(inputs, Mapping)
        or inputs.get("idea_count") != summary.get("idea_count")
        or inputs.get("episode_count") != summary.get("episode_count")
        or inputs.get("analysis_partition_count") != partition_count
    ):
        raise ValueError("empirical controls or review semantic mismatch")


def _closed_cohort_names(value: Any) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        return set()
    names = [str(row.get("cohort") or "") for row in value]
    return set(names) if len(names) == len(set(names)) else set()


def _count(value: Any) -> int:
    return value if type(value) is int and value >= 0 else -1


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = ["validate_published_bundle", "validate_run_semantics"]
