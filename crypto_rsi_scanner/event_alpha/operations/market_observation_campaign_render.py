"""Deterministic Markdown rendering for Decision Radar campaign reports."""

from __future__ import annotations

import math
from typing import Any, Mapping

from . import market_observation_campaign_contract


_int = market_observation_campaign_contract.nonnegative_int


EXECUTION_SURFACE_NOTICE = (
    "Bybit USDT-linear perpetuals are the selected execution surface; no spread or depth "
    "evidence is treated as available until a separately authorized immutable capture "
    "succeeds."
)


def format_campaign_report(report: Mapping[str, Any]) -> str:
    """Render the canonical report as deterministic operator-facing Markdown."""
    metrics = _mapping(report.get("campaign_metrics"))
    outcomes = _mapping(report.get("outcomes"))
    review_timing = _mapping(report.get("human_review_timing"))
    review_queue = _mapping(report.get("human_review_queue"))
    baseline = _mapping(report.get("baseline_maturity"))
    pointer = _mapping(report.get("pointer"))
    next_observation = _mapping(report.get("next_observation"))
    limitations = list(report.get("data_quality_limitations") or ())
    conclusion = _mapping(report.get("campaign_v2_conclusion"))
    authority_proven = _authority_proven(pointer)
    lines = [
        "# Decision Radar live observation campaign v2",
        "",
        f"Generated at `{_text(report.get('generated_at'))}` from local artifacts only.",
        "Research and decision support only. This report contains no trade recommendation.",
        "",
        "## Campaign measurement",
        "",
        f"- Status: `{_text(report.get('campaign_status'))}`",
        f"- Counted real/no-send cycles: `{_int(metrics.get('real_cycles'))}`",
        f"- Real market observations: `{_int(metrics.get('real_observations'))}`",
        f"- Baseline-counting observations: `{_int(metrics.get('baseline_counted_observation_count'))}`",
        f"- Too-close observations: `{_int(metrics.get('too_close_observation_count'))}`",
        f"- Real Decision candidates: `{_int(metrics.get('real_candidates'))}`",
        f"- Current ideas: `{_int(metrics.get('current_ideas'))}`",
        f"- Historical ideas: `{_int(metrics.get('historical_ideas'))}`",
        f"- Direct feature evidence: `{_int(metrics.get('direct_feature_count'))}`",
        f"- Proxy feature evidence: `{_int(metrics.get('proxy_feature_count'))}`",
        f"- Pending outcomes: `{_int(metrics.get('pending_outcomes'))}`",
        f"- Matured outcomes: `{_int(metrics.get('matured_outcomes'))}`",
        f"- Explicit first-view records: `{_int(metrics.get('review_timing_first_views'))}`",
        f"- Completed human reviews: `{_int(metrics.get('review_timing_completed_reviews'))}`",
        f"- Ideas awaiting explicit review action: `{_int(metrics.get('review_timing_action_required'))}`",
        f"- Provider failures: `{_int(metrics.get('provider_failed_attempts'))}`",
        f"- Preflight/blocked attempts: `{_int(metrics.get('blocked_attempts'))}`",
        "- Event Alpha catalyst burn-in: `separate_not_aggregated`",
        "- Historical market-provenance v2 fields: `read_only_adapter`",
        "",
        "### Decision routes",
        "",
    ]
    route_counts = _mapping(metrics.get("route_counts"))
    lines.extend(_route_lines(route_counts))
    lines.extend([
        "",
        "## Authority and pointer",
        "",
        f"- Pointer status: `{_text(pointer.get('status'))}`",
        f"- Current authority namespace: `{_text(pointer.get('artifact_namespace')) if authority_proven else 'none'}`",
        f"- Pointer target namespace: `{_text(pointer.get('artifact_namespace')) or 'none'}`",
        f"- Exact run: `{_text(pointer.get('run_id')) or 'none'}`",
        f"- Revision: `{_text(pointer.get('revision')) or 'none'}`",
        f"- Exact operator binding: `{str(pointer.get('exact_operator_binding') is True).lower()}`",
        "",
        "### Authoritative generations",
        "",
    ])
    lines.extend(_generation_table(report.get("authoritative_generations")))
    lines.extend([
        "",
        "### Complete but non-authoritative generations",
        "",
    ])
    lines.extend(_generation_table(report.get("non_authoritative_complete_generations")))
    lines.extend(
        _baseline_maturity_section(
            baseline,
            current_generation=_current_authoritative_generation(report),
        )
    )
    lines.extend([
        "",
        "## Outcomes",
        "",
        f"- Total canonical outcomes: `{_int(outcomes.get('total'))}`",
        f"- Pending: `{_int(outcomes.get('pending'))}`",
        f"- Matured: `{_int(outcomes.get('matured'))}`",
        f"- Missing data: `{_int(outcomes.get('missing_data'))}`",
        f"- Source: `{_text(outcomes.get('source'))}`",
        f"- Refresh/build errors: `{_int(outcomes.get('refresh_build_error_count'))}`",
        *_due_missing_price_lines(outcomes),
        "- Human labels remain optional preference feedback; no thresholds or routes change automatically.",
        "",
        "## Human review timing",
        "",
        *_review_timing_lines(review_timing, review_queue),
        "",
        "## Anomaly episodes (shadow)",
        "",
        *_episode_shadow_lines_from_report(report),
        *_decision_episode_scorecard_section(report),
        "## Failed and blocked attempts",
        "",
    ])
    lines.extend(_attempt_table(report.get("provider_failed_attempts"), empty="No provider failures recorded."))
    lines.append("")
    lines.extend(_attempt_table(report.get("blocked_or_preflight_attempts"), empty="No blocked/preflight attempts recorded."))
    lines.extend([
        "",
        "## Excluded invalid generations",
        "",
    ])
    excluded = [
        dict(row)
        for row in report.get("excluded_invalid_generations") or ()
        if isinstance(row, Mapping)
    ]
    if excluded:
        for row in excluded:
            reasons = ", ".join(str(value) for value in row.get("validation_errors") or ())
            lines.append(
                f"- `{_md(row.get('artifact_namespace'))}`: `{_md(reasons or 'invalid_generation')}`"
            )
    else:
        lines.append("- None.")
    lines.extend([
        "",
        "## Data-quality limitations",
        "",
    ])
    if limitations:
        for item in limitations:
            value = _mapping(item)
            lines.append(
                f"- **{_md(value.get('category'))}:** {_md(value.get('detail'))}"
            )
    else:
        lines.append("- No campaign-level limitation was derived from current artifacts.")
    lines.extend([
        "",
        "## Next observation",
        "",
        f"- Next eligible time: `{_text(next_observation.get('next_eligible_observation_at')) or 'now'}`",
        f"- Eligible at report time: `{str(next_observation.get('eligible_now') is True).lower()}`",
        f"- Exact next safe operator command: `{_text(next_observation.get('next_safe_operator_command'))}`",
        "- Authorization is rechecked at the provider boundary; this report never creates or changes it.",
        "",
        "## Campaign-v2 conclusion",
        "",
        _text(conclusion.get("summary")),
        "",
        EXECUTION_SURFACE_NOTICE,
        "No trade is recommended. No automatic threshold or route change is authorized.",
        "",
    ])
    return "\n".join(lines)


def _authority_proven(pointer: Mapping[str, Any]) -> bool:
    return bool(
        pointer.get("status") == "authoritative"
        and pointer.get("exact_operator_binding") is True
    )


def _review_timing_lines(
    value: Mapping[str, Any], queue: Mapping[str, Any]
) -> list[str]:
    lines = [
        "Human review is counted only through explicit confirmed actions; dashboard GET/HEAD and health probes never create timing evidence.",
        f"- Status: `{_text(value.get('status'))}`",
        f"- Receipt-backed ideas eligible for review timing: `{_int(queue.get('eligible_idea_count'))}`",
        f"- Awaiting explicit human action: `{_int(queue.get('action_required_count'))}`",
        f"- Not yet viewed: `{_int(queue.get('not_viewed_count'))}`",
        f"- In review: `{_int(queue.get('in_review_count'))}`",
        f"- Review queue command: `{_md(queue.get('operator_queue_command')) or 'unavailable'}`",
        f"- Ledger events: `{_int(value.get('ledger_event_count'))}`",
        f"- Idea records: `{_int(value.get('idea_record_count'))}`",
        f"- First views: `{_int(value.get('first_view_record_count'))}`",
        f"- Completed reviews: `{_int(value.get('completed_review_record_count'))}`",
        f"- Incomplete reviews: `{_int(value.get('incomplete_review_record_count'))}`",
        f"- Events after report time: `{_int(value.get('events_after_evaluated_at_count'))}`",
        f"- Availability definition: {_md(value.get('idea_available_at_definition'))}",
        f"- Latency definition: `{_md(value.get('latency_seconds_definition'))}`",
        "- Protocol-v2 evidence eligible: `false` until the sealed annex binds the exact clock and missing-data rules.",
    ]
    records = [
        dict(row)
        for row in value.get("records") or ()
        if isinstance(row, Mapping)
    ]
    if not records:
        return [
            *lines,
            "- No explicit human review timing has been recorded; eligible queue rows remain unmeasured until the operator confirms a real action.",
        ]
    lines.extend(
        [
            "",
            "| Namespace | Idea | Route | Status | Pipeline s | First-view s | Review s | Available-to-complete s |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in records:
        lines.append(
            f"| {_md(row.get('artifact_namespace'))} | {_md(row.get('idea_id'))} | "
            f"{_md(row.get('radar_route'))} | {_md(row.get('review_status'))} | "
            f"{_number(row.get('pipeline_latency_seconds'))} | "
            f"{_number(row.get('time_to_first_view_seconds'))} | "
            f"{_number(row.get('review_duration_seconds'))} | "
            f"{_number(row.get('latency_seconds'))} |"
        )
    return lines


def _baseline_maturity_section(
    baseline: Mapping[str, Any],
    *,
    current_generation: Mapping[str, Any],
) -> list[str]:
    current = _mapping(baseline.get("current_universe_maturity"))
    current_quality = _mapping(current_generation.get("data_quality"))
    latest_row_statuses = _mapping(current_quality.get("baseline_status_counts"))
    lines = [
        "",
        "## Baseline maturity",
        "",
        "### Current authoritative universe",
        "",
        f"- Status: `{_text(current.get('status'))}`",
        f"- Exact authority assets: `{_int(current.get('expected_asset_count'))}`",
        f"- Assets found in retained history: `{_int(current.get('observed_asset_count'))}`",
        f"- Missing current assets: `{_int(current.get('missing_asset_count'))}`",
        f"- Fully warm retained-history baselines: `{_int(current.get('baseline_warm_asset_count'))}`",
        f"- Current-universe retained observations: `{_int(current.get('baseline_observation_count'))}`",
        f"- Current-universe baseline-counted observations: `{_int(current.get('baseline_counted_observation_count'))}`",
        f"- Missing asset IDs: `{_joined(current.get('missing_asset_ids')) or 'none'}`",
        f"- Latest exact-generation row readiness: `{_counts(latest_row_statuses) if latest_row_statuses else 'unavailable'}`",
        "",
        (
            "Retained-history maturity and latest point-in-time feature availability are "
            "separate. The table below measures sample depth and elapsed coverage for the "
            "exact current asset set; it does not claim that every latest-row feature exists."
        ),
        "",
        "#### Retained-history feature maturity for current-universe assets",
        "",
        *_feature_maturity_lines(current.get("baseline_feature_readiness")),
        "",
        "### Retained campaign history",
        "",
        f"- Status: `{_text(baseline.get('baseline_status'))}`",
        f"- Retained observations: `{_int(baseline.get('baseline_observation_count'))}`",
        f"- Baseline-counted observations: `{_int(baseline.get('baseline_counted_observation_count'))}`",
        f"- Too-close observations: `{_int(baseline.get('baseline_too_close_observation_count'))}`",
        f"- Duplicate observations: `{_int(baseline.get('baseline_duplicate_observation_count'))}`",
        f"- Conflicting duplicate observations: `{_int(baseline.get('baseline_duplicate_conflict_count'))}`",
        f"- Assets: `{_int(baseline.get('baseline_asset_count'))}`",
        f"- Warm assets: `{_int(baseline.get('baseline_warm_asset_count'))}`",
        f"- Minimum spacing seconds: `{_int(baseline.get('minimum_observation_spacing_seconds'))}`",
        "",
        "#### Retained-history feature maturity",
        "",
        *_feature_maturity_lines(baseline.get("baseline_feature_readiness")),
    ]
    return lines


def _current_authoritative_generation(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    for raw in report.get("authoritative_generations") or ():
        row = _mapping(raw)
        publication = _mapping(row.get("publication"))
        if publication.get("currently_authoritative") is True:
            return row
    return {}


def _route_lines(route_counts: Mapping[str, Any]) -> list[str]:
    lines = [
        f"- `{route}`: `{_int(count)}`"
        for route, count in sorted(route_counts.items())
    ]
    return lines or ["- No real Decision candidates yet."]


def _episode_shadow_lines_from_report(report: Mapping[str, Any]) -> list[str]:
    return _episode_shadow_lines(
        _mapping(report.get("shadow_anomaly_episodes")),
        _mapping(report.get("shadow_anomaly_episode_input_audit")),
    )


def _episode_shadow_lines(
    value: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> list[str]:
    sensitivity = _mapping(value.get("sensitivity_counts"))
    outcome_counts = _mapping(audit.get("outcome_evidence_status_counts"))
    candidate_rejections = _mapping(
        audit.get("candidate_row_rejection_reason_counts")
    )
    generation_rejections = _mapping(
        audit.get("generation_rejection_reason_counts")
    )
    lines = [
        "Repeated observations are grouped into fixed-start descriptive episodes; "
        "they are not claimed to be statistically independent.",
        f"- Input status: `{_text(audit.get('status'))}`",
        f"- Candidate input status: `{_text(audit.get('candidate_input_status'))}`",
        f"- Outcome input status: `{_text(audit.get('outcome_input_status'))}`",
        f"- Structural membership status: `{_text(value.get('status'))}`",
        f"- Outcome ledger status: `{_text(audit.get('outcome_ledger_status'))}`",
        f"- Candidate snapshots: `{_int(audit.get('candidate_snapshot_generation_count'))}`/"
        f"`{_int(audit.get('counted_generation_count'))}` generations",
        f"- Eligible anomaly observations: `{_int(value.get('records_eligible'))}`",
        f"- Excluded observations: `{_int(value.get('records_excluded'))}`",
        f"- Primary 24h episodes: `{_int(value.get('primary_episode_count'))}`",
        f"- Primary repeats: `{_int(value.get('primary_repeat_member_count'))}`",
        f"- Candidate rows outside market-anomaly scope: "
        f"`{_int(audit.get('out_of_scope_candidate_count'))}`",
        f"- Missing outcome joins: `{_int(audit.get('missing_outcome_join_count'))}`",
        f"- Ambiguous outcome joins: `{_int(audit.get('ambiguous_outcome_join_count'))}`",
        f"- Invalid outcome rows: `{_int(audit.get('invalid_outcome_row_count'))}`",
        f"- Duplicate outcome identities: "
        f"groups=`{_int(audit.get('duplicate_outcome_identity_group_count'))}`, "
        f"rows=`{_int(audit.get('duplicate_outcome_row_count'))}`",
        f"- Cross-candidate outcome collisions: "
        f"groups=`{_int(audit.get('cross_candidate_outcome_collision_group_count'))}`, "
        f"candidates=`{_int(audit.get('cross_candidate_outcome_collision_candidate_count'))}`, "
        f"rows=`{_int(audit.get('cross_candidate_outcome_collision_row_count'))}`",
        f"- Orphan outcome rows: `{_int(audit.get('orphan_outcome_row_count'))}`",
        f"- Outcome evidence statuses: `{_counts(outcome_counts)}`",
        f"- Generation rejections: `{_int(audit.get('generation_rejection_count'))}` "
        f"(`{_counts(generation_rejections)}`)",
        f"- Candidate-row rejections: `{_int(audit.get('candidate_row_rejection_count'))}` "
        f"(`{_counts(candidate_rejections)}`)",
    ]
    for label in ("12h", "24h", "48h"):
        row = _mapping(sensitivity.get(label))
        lines.append(
            f"- `{label}` sensitivity: episodes=`{_int(row.get('episode_count'))}`, "
            f"repeats=`{_int(row.get('repeat_member_count'))}`"
        )
    lines.extend([
        "- The first observation is frozen as representative before outcome maturity is inspected.",
        "- Shadow only: no route, score, threshold, provider, publication, or authority change.",
    ])
    return lines


def _decision_episode_scorecard_lines(value: Mapping[str, Any]) -> list[str]:
    states = _mapping(value.get("outcome_state_counts"))
    alignments = _mapping(value.get("direction_alignment_counts"))
    persistence = _mapping(
        value.get("outcome_cohort_persistence_status_counts")
    )
    lines = [
        "Only the frozen first member of each primary episode is evaluated; "
        "outcome maturity never reselects a representative.",
        f"- Status: `{_text(value.get('status'))}`",
        f"- Episode representatives: `{_int(value.get('representative_count'))}`",
        f"- Matured primary outcomes: `{_int(value.get('matured_episode_count'))}`",
        f"- Scoreable directional outcomes: "
        f"`{_int(value.get('scoreable_directional_episode_count'))}`",
        f"- Primary outcome states: `{_counts(states)}`",
        f"- Direction alignment: `{_counts(alignments)}`",
        f"- Cohort persistence: `{_counts(persistence)}`",
        f"- Exact source artifact bindings: "
        f"`{_int(value.get('source_artifact_binding_count'))}`",
        f"- Exact outcome validation bindings: "
        f"`{_int(value.get('outcome_validation_binding_count'))}`",
        f"- Policy conclusion: `{_text(value.get('policy_conclusion'))}`",
        "- Direction comes from canonical Decision-v2 bias, not a legacy "
        "Event Alpha lane; only the declared primary horizon may mature.",
    ]
    representatives = [
        dict(row)
        for row in value.get("representatives") or ()
        if isinstance(row, Mapping)
    ]
    if not representatives:
        return [*lines, "- No primary episode representative is available."]
    lines.extend([
        "",
        "| Asset | Route | Bias | State | Alignment | Primary return (fraction) | Score cohorts A/E/R |",
        "|---|---|---|---|---|---:|---|",
    ])
    for row in representatives:
        primary_return = row.get("primary_horizon_return")
        rendered_return = (
            f"{float(primary_return):.8f}"
            if type(primary_return) in (int, float)
            else "n/a"
        )
        cohorts = "/".join(
            _text(row.get(field)) or "unknown"
            for field in (
                "actionability_score_cohort",
                "evidence_confidence_score_cohort",
                "risk_score_cohort",
            )
        )
        lines.append(
            f"| {_md(row.get('canonical_asset_id'))} | "
            f"{_md(row.get('radar_route'))} | {_md(row.get('directional_bias'))} | "
            f"{_md(row.get('outcome_state'))} | "
            f"{_md(row.get('direction_alignment'))} | {rendered_return} | "
            f"{_md(cohorts)} |"
        )
    lines.append(
        "- Descriptive only: no route, score, calibration, threshold, or "
        "authority change is eligible."
    )
    return lines


def _decision_episode_scorecard_section(report: Mapping[str, Any]) -> list[str]:
    return [
        "",
        "## Decision-v2 episode outcomes (shadow)",
        "",
        *_decision_episode_scorecard_lines(
            _mapping(report.get("decision_v2_episode_outcome_scorecard"))
        ),
        "",
    ]


def _feature_maturity_lines(value: Any) -> list[str]:
    feature_readiness = _mapping(value)
    if not feature_readiness:
        return ["- Feature-level maturity is not yet available for this scope."]
    lines = [
        "| Feature group | Warm | Warming | Cold | Other | Samples min-max / required | Elapsed min-max / required | Status counts |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for name, raw in sorted(feature_readiness.items()):
        feature = _mapping(raw)
        counts = ", ".join(
            f"{key}={_int(count)}"
            for key, count in sorted(_mapping(feature.get("status_counts")).items())
        ) or "none"
        lines.append(
            f"| {_md(name)} | {_int(feature.get('warm_asset_count'))} | "
            f"{_int(feature.get('warming_asset_count'))} | "
            f"{_int(feature.get('cold_asset_count'))} | "
            f"{_int(feature.get('other_asset_count'))} | "
            f"{_md(_sample_progress(feature))} | "
            f"{_md(_coverage_progress(feature))} | {_md(counts)} |"
        )
    return lines


def _sample_progress(feature: Mapping[str, Any]) -> str:
    minimum = _int(feature.get("minimum_sample_count"))
    maximum = _int(feature.get("maximum_sample_count"))
    required = _int(feature.get("required_sample_count"))
    deficit = _int(feature.get("sample_count_deficit_asset_count"))
    value_range = str(minimum) if minimum == maximum else f"{minimum}-{maximum}"
    return f"{value_range} / {required} ({deficit} below)"


def _coverage_progress(feature: Mapping[str, Any]) -> str:
    minimum = _hours(feature.get("minimum_coverage_seconds"))
    maximum = _hours(feature.get("maximum_coverage_seconds"))
    required = _hours(feature.get("required_coverage_seconds"))
    deficit = _int(feature.get("coverage_deficit_asset_count"))
    value_range = minimum if minimum == maximum else f"{minimum}-{maximum}"
    return f"{value_range} / {required} h ({deficit} below)"


def _hours(value: Any) -> str:
    seconds = _int(value)
    hours = seconds / 3_600
    return f"{hours:.2f}".rstrip("0").rstrip(".")


def _generation_table(value: Any) -> list[str]:
    rows = [dict(row) for row in value or () if isinstance(row, Mapping)]
    if not rows:
        return ["- None."]
    lines = [
        "| Namespace | Observed at | Candidates | Routes | Attempt audit | Publication | Operations | Current |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        publication = _mapping(row.get("publication"))
        routes = ", ".join(
            f"{name}={_int(count)}"
            for name, count in sorted(_mapping(row.get("route_counts")).items())
        ) or "none"
        lines.append(
            f"| {_md(row.get('artifact_namespace'))} | {_md(row.get('observed_at'))} | "
            f"{_int(row.get('candidate_count'))} | {_md(routes)} | "
            f"{_md(publication.get('attempt_audit_status'))} | "
            f"{_md(publication.get('publication_status'))} | "
            f"{_md(publication.get('operations_status'))} | "
            f"{str(publication.get('currently_authoritative') is True).lower()} |"
        )
    return lines


def _attempt_table(value: Any, *, empty: str) -> list[str]:
    rows = [dict(row) for row in value or () if isinstance(row, Mapping)]
    if not rows:
        return [f"- {empty}"]
    lines = [
        "| Namespace | Observed at | Status | Provider attempted | Failure class |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {_md(row.get('artifact_namespace'))} | {_md(row.get('observed_at'))} | "
            f"{_md(row.get('attempt_status'))} | "
            f"{str(row.get('provider_call_attempted') is True).lower()} | "
            f"{_md(row.get('failure_class') or 'none')} |"
        )
    return lines


def _due_missing_price_lines(outcomes: Mapping[str, Any]) -> list[str]:
    rows = [
        dict(row)
        for row in outcomes.get("due_missing_price_details") or ()
        if isinstance(row, Mapping)
    ]
    if not rows:
        return []
    history = _mapping(outcomes.get("price_history_snapshot"))
    lines = [
        "",
        "### Due outcomes without a qualifying price",
        "",
        (
            "These rows remain unresolved because the exact retained price history does not "
            "currently prove a price inside the closed outcome window. No interpolation or "
            "automatic threshold change is permitted."
        ),
        "",
        f"- Price-history snapshot status: `{_md(history.get('status'))}`",
        f"- Price-history rows: `{_int(history.get('row_count'))}`",
        f"- Price-history SHA-256: `{_md(history.get('sha256') or 'none')}`",
        "",
        "| Asset | Candidate observed | Outcome due | Price allowed through | First retained after due | Outside window | Evidence status |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        first_after = _mapping(row.get("first_retained_price_after_due"))
        beyond = row.get("seconds_beyond_allowed_window")
        outside = (
            f"{float(beyond) / 3600:.2f} h"
            if type(beyond) in (int, float) and float(beyond) > 0
            else "0.00 h"
            if type(beyond) in (int, float)
            else "unknown"
        )
        asset = _text(row.get("symbol")) or _text(row.get("coin_id")) or "unknown"
        lines.append(
            f"| {_md(asset)} | {_md(row.get('observed_at'))} | {_md(row.get('due_at'))} | "
            f"{_md(row.get('allowed_latest_price_at'))} | "
            f"{_md(first_after.get('observed_at') or 'none')} | {_md(outside)} | "
            f"{_md(row.get('resolution_status'))} |"
        )
    lines.append("")
    return lines


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _number(value: Any) -> str:
    if type(value) not in (int, float):
        return "—"
    try:
        rendered = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(rendered):
        return "—"
    return f"{rendered:.6f}".rstrip("0").rstrip(".")


def _counts(value: Mapping[str, Any]) -> str:
    return ", ".join(
        f"{key}={_int(count)}" for key, count in sorted(value.items())
    ) or "none"


def _joined(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    return ", ".join(_md(item) for item in value if _text(item))


def _md(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("`", "'").replace("\n", " ")


__all__ = ("format_campaign_report",)
