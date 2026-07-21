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
    regime_generation_audit = _mapping(
        report.get("control_market_regime_generation_audit")
    )
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
            regime_generation_audit=regime_generation_audit,
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
        *_shadow_surprise_audit_section(report),
        *_episode_shadow_lines_from_report(report),
        *_decision_episode_scorecard_section(report),
        *_episode_coverage_frontier_section(report),
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


def _shadow_surprise_audit_section(report: Mapping[str, Any]) -> list[str]:
    audit = _mapping(report.get("shadow_temporal_surprise_campaign_audit"))
    source = _mapping(audit.get("source_history"))
    features = _mapping(audit.get("feature_coverage"))
    lines = [
        "### Causal temporal-surprise replay",
        "",
        (
            "This is a read-only replay of the shadow model over retained, "
            "cadence-counted observations. Each projection uses only strictly "
            "earlier same-asset history; it does not rewrite historical rows or "
            "change routes, scores, thresholds, or authority."
        ),
        f"- Audit status: `{_text(audit.get('status'))}`",
        f"- Shadow schema: `{_text(audit.get('shadow_schema_id'))}` v`{_int(audit.get('shadow_schema_version'))}`",
        f"- Exact history rows: `{_int(source.get('row_count'))}`",
        f"- Baseline-counted rows replayed: `{_int(audit.get('evaluated_observation_count'))}`",
        f"- Non-counted rows excluded: `{_int(audit.get('excluded_not_baseline_counted_count'))}`",
        f"- Input rejections: `{_int(audit.get('input_rejected_count'))}`",
        f"- Evaluation errors: `{_int(audit.get('evaluation_error_count'))}`",
        f"- Assets replayed: `{_int(audit.get('asset_count'))}`",
        f"- Source-bound projection digest: `{_text(audit.get('source_bound_projection_digest'))}`",
        f"- Causal-value projection digest: `{_text(audit.get('causal_projection_digest'))}`",
        (
            "- An audit status of `ready` means every modeled feature has some "
            "ready evidence; it does not mean every projection is ready. The "
            "counts below remain authoritative."
        ),
        "- Statistical independence claimed: `false`",
        "- Protocol-v2 evidence eligible: `false`",
        (
            "- Robust-z quantiles and empirical tail ranks describe only ready "
            "historical projections. Tail ranks are not p-values, and "
            "overlapping horizon samples are not independent."
        ),
        "",
        (
            "| Feature | Family | Ready / evaluated | Status counts | Sample "
            "range | Robust z p05 / median / p95 | Tail kind | Tail rank min / "
            "median / p95 | Minimum-tail observation |"
        ),
        "|---|---|---:|---|---:|---:|---|---:|---|",
    ]
    for feature in sorted(features):
        coverage = _mapping(features.get(feature))
        minimum = coverage.get("minimum_eligible_sample_count")
        maximum = coverage.get("maximum_eligible_sample_count")
        sample_range = (
            f"{minimum}–{maximum}"
            if type(minimum) is int and type(maximum) is int
            else "n/a"
        )
        robust_distribution = " / ".join(
            _number(coverage.get(field))
            for field in ("robust_z_p05", "robust_z_median", "robust_z_p95")
        )
        tail_distribution = " / ".join(
            _number(coverage.get(field))
            for field in (
                "descriptive_tail_rank_minimum",
                "descriptive_tail_rank_median",
                "descriptive_tail_rank_p95",
            )
        )
        minimum_tail = _mapping(
            coverage.get("minimum_descriptive_tail_rank_observation")
        )
        minimum_tail_observation = (
            f"{_text(minimum_tail.get('canonical_asset_id'))} @ "
            f"{_text(minimum_tail.get('observed_at'))}"
            if minimum_tail
            else "n/a"
        )
        lines.append(
            f"| {_md(feature)} | {_md(coverage.get('family'))} | "
            f"{_int(coverage.get('ready_count'))} / "
            f"{_int(coverage.get('evaluated_observation_count'))} | "
            f"{_counts(_mapping(coverage.get('status_counts'))) or 'none'} | "
            f"{sample_range} | {robust_distribution} | "
            f"{_md(coverage.get('descriptive_tail_rank_kind'))} | "
            f"{tail_distribution} | {_md(minimum_tail_observation)} |"
        )
    if any(
        isinstance(value, Mapping)
        and "variation_observation_count" in value
        for value in features.values()
    ):
        lines.extend([
            "",
            (
                "Reference-set variation below is calculated only for projections "
                "meeting the model's existing nominal sample minimum. It is not an "
                "effective-sample-size estimate and applies no distinctness threshold."
            ),
            "",
            (
                "| Feature | Variation rows / evaluated | Distinct count min / "
                "median / max | Distinct ratio min / median / p95 | Largest-tie "
                "ratio median / p95 / max | Least-diverse reference set |"
            ),
            "|---|---:|---:|---:|---:|---|",
        ])
        for feature in sorted(features):
            coverage = _mapping(features.get(feature))
            distinct_counts = " / ".join(
                _number(coverage.get(field))
                for field in (
                    "distinct_baseline_value_count_minimum",
                    "distinct_baseline_value_count_median",
                    "distinct_baseline_value_count_maximum",
                )
            )
            distinct_ratios = " / ".join(
                _number(coverage.get(field))
                for field in (
                    "distinct_baseline_value_ratio_minimum",
                    "distinct_baseline_value_ratio_median",
                    "distinct_baseline_value_ratio_p95",
                )
            )
            tie_ratios = " / ".join(
                _number(coverage.get(field))
                for field in (
                    "maximum_baseline_value_tie_ratio_median",
                    "maximum_baseline_value_tie_ratio_p95",
                    "maximum_baseline_value_tie_ratio_maximum",
                )
            )
            minimum_distinct = _mapping(
                coverage.get(
                    "minimum_distinct_baseline_value_ratio_observation"
                )
            )
            least_diverse = (
                f"{_text(minimum_distinct.get('canonical_asset_id'))} @ "
                f"{_text(minimum_distinct.get('observed_at'))}; "
                f"{_int(minimum_distinct.get('distinct_baseline_value_count'))}/"
                f"{_int(minimum_distinct.get('sample_count'))} distinct; largest "
                f"tie {_int(minimum_distinct.get('maximum_baseline_value_tie_count'))}/"
                f"{_int(minimum_distinct.get('sample_count'))}"
                if minimum_distinct
                else "n/a"
            )
            lines.append(
                f"| {_md(feature)} | "
                f"{_int(coverage.get('variation_observation_count'))} / "
                f"{_int(coverage.get('evaluated_observation_count'))} | "
                f"{distinct_counts} | {distinct_ratios} | {tie_ratios} | "
                f"{_md(least_diverse)} |"
            )
    lines.extend(["", "### Decision episodes", ""])
    return lines


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
        f"- Recorded-action status: `{_text(value.get('status'))}`",
        f"- Receipt-backed ideas eligible for review timing: `{_int(queue.get('eligible_idea_count'))}`",
        f"- Awaiting explicit human action: `{_int(queue.get('action_required_count'))}`",
        f"- Not yet viewed: `{_int(queue.get('not_viewed_count'))}`",
        f"- In review: `{_int(queue.get('in_review_count'))}`",
        f"- Review queue command: `{_md(queue.get('operator_queue_command')) or 'unavailable'}`",
        f"- Ledger events: `{_int(value.get('ledger_event_count'))}`",
        f"- Ideas with recorded human action: `{_int(value.get('idea_record_count'))}`",
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
    regime_generation_audit: Mapping[str, Any],
) -> list[str]:
    current = _mapping(baseline.get("current_universe_maturity"))
    control_context = _mapping(
        baseline.get("point_in_time_control_context_readiness")
    )
    current_quality = _mapping(current_generation.get("data_quality"))
    current_regime_input = _mapping(
        current_generation.get("current_authority_control_market_regime_input")
    )
    latest_row_statuses = _mapping(current_quality.get("baseline_status_counts"))
    observed_asset_count = _int(current.get("observed_asset_count"))
    future_same_asset_eligibility = (
        f"{_int(current.get('next_cycle_point_in_time_eligible_asset_count'))}"
        f"/{observed_asset_count}"
        if observed_asset_count
        else "unavailable (no assessed current assets)"
    )
    lines = [
        "",
        "## Baseline maturity",
        "",
        "### Current authoritative universe",
        "",
        f"- Status: `{_text(current.get('status'))}`",
        f"- Latest exact-generation row readiness: `{_counts(latest_row_statuses) if latest_row_statuses else 'unavailable'}`",
        f"- Exact authority assets: `{_int(current.get('expected_asset_count'))}`",
        f"- Assets found in retained history: `{observed_asset_count}`",
        f"- Missing current assets: `{_int(current.get('missing_asset_count'))}`",
        f"- Fully warm retained-history baselines: `{_int(current.get('baseline_warm_asset_count'))}`",
        f"- Current-universe retained observations: `{_int(current.get('baseline_observation_count'))}`",
        f"- Current-universe baseline-counted observations: `{_int(current.get('baseline_counted_observation_count'))}`",
        f"- Missing/unassessed asset IDs: `{_joined(current.get('missing_asset_ids')) or 'none'}`",
        f"- Observed non-warm asset IDs: `{_joined(current.get('non_warm_asset_ids')) or 'none'}`",
        (
            "- Retained history eligible for a future same-asset point-in-time "
            f"evaluation: `{future_same_asset_eligibility}`"
        ),
        (
            "- Existing history cadence boundary: "
            f"`{_text(current.get('next_cycle_point_in_time_eligible_at')) or 'unavailable'}`"
        ),
        (
            "- Eligibility basis: "
            f"`{_text(current.get('next_cycle_point_in_time_basis')) or 'unavailable'}`"
        ),
        "- Provider-call eligibility: `not inferred`; Daily Operations readiness remains authoritative.",
        "",
        "### Exact current control-regime input replay",
        "",
        *_current_control_regime_input_lines(current_regime_input),
        "",
        "### Exact-generation control-regime history",
        "",
        *_control_regime_generation_audit_lines(regime_generation_audit),
        "",
        (
            "Retained-history maturity and latest point-in-time feature availability are "
            "separate. Future-observation eligibility is conditional on the same canonical "
            "asset remaining in the next universe and does not claim unknown future membership "
            "or feature values are already observed. The table below measures only retained "
            "sample depth and elapsed coverage for the exact current asset set."
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
        "",
        "### Prospective matched-control context",
        "",
        *_point_in_time_control_context_lines(control_context),
    ]
    return lines


def _control_regime_generation_audit_lines(
    value: Mapping[str, Any],
) -> list[str]:
    if not value:
        return [
            "- Status: `unavailable`",
            "- This compatibility report has no immutable-generation input audit.",
        ]
    latest = _mapping(value.get("latest_complete_generation"))
    expected = _int(latest.get("universe_expected_count"))
    eligible = _int(latest.get("eligible_input_count"))
    missing = _joined(latest.get("missing_asset_ids")) or "none"
    recent = _joined(latest.get("recent_entry_missing_asset_ids")) or "none"
    lines = [
        f"- Status: `{_md(value.get('status')) or 'unavailable'}`",
        (
            "- Verified immutable generation sources: "
            f"`{_int(value.get('verified_source_generation_count'))}/"
            f"{_int(value.get('input_generation_count'))}`"
        ),
        (
            "- Complete point-in-time universes audited: "
            f"`{_int(value.get('complete_universe_generation_count'))}`"
        ),
        (
            "- Causal 24-hour input results: "
            f"`{_int(value.get('ready_generation_count'))} ready / "
            f"{_int(value.get('incomplete_generation_count'))} incomplete / "
            f"{_int(value.get('complete_but_unavailable_generation_count'))} "
            "complete-but-unavailable`"
        ),
        (
            "- Comparable universe transitions: "
            f"`{_int(value.get('transition_count'))}`; membership changed in "
            f"`{_int(value.get('universe_change_transition_count'))}`"
        ),
        (
            "- Incomplete cycles overlapping an observed entry within 24 hours: "
            f"`{_int(value.get('incomplete_with_recent_entry_count'))}`; "
            "incomplete cycles without that overlap: "
            f"`{_int(value.get('incomplete_without_recent_entry_count'))}`"
        ),
        (
            "- Latest exact cycle: "
            f"`{_md(latest.get('observed_at')) or 'unavailable'}` — "
            f"`{eligible}/{expected}` eligible inputs; missing: `{_md(missing)}`"
        ),
        f"- Latest missing assets with a recent observed entry: `{_md(recent)}`",
        (
            "- Interpretation: membership overlap is descriptive, not causal "
            "attribution. Older anchor gaps and recent entries remain distinct; "
            "no universe, cadence, threshold, route, or regime policy changed."
        ),
        "- Historical backfill/retained-history mutation/provider calls: `false / false / 0`.",
        "- Routing/policy/Protocol-v2 evidence eligibility: `false`.",
    ]
    return lines


def _current_control_regime_input_lines(value: Mapping[str, Any]) -> list[str]:
    if not value:
        return [
            "- Status: `unavailable`",
            "- This compatibility report has no exact-authority regime-input replay.",
        ]
    diagnostic = _mapping(value.get("diagnostic"))
    replayed = _mapping(diagnostic.get("replayed_control_market_regime"))
    expected = _int(diagnostic.get("universe_expected_count"))
    eligible = _int(diagnostic.get("eligible_input_count"))
    missing = [
        _mapping(row)
        for row in diagnostic.get("missing_inputs") or ()
        if isinstance(row, Mapping)
    ]
    lines = [
        f"- Status: `{_md(value.get('status')) or 'unavailable'}`",
        (
            "- Exact source binding: "
            f"`{str(value.get('source_snapshot_verified') is True).lower()}` "
            f"(`{_md(value.get('source_artifact'))}`, SHA-256 "
            f"`{_md(value.get('source_artifact_sha256')) or 'none'}`)"
        ),
        f"- Eligible causal 24-hour inputs: `{eligible}/{expected}`",
        f"- Missing current inputs: `{_int(diagnostic.get('missing_input_count'))}`",
        (
            "- Read-only replay result: "
            f"`{_md(replayed.get('status')) or 'unavailable'}`"
            + (
                f" (`{_md(replayed.get('reason'))}`)"
                if replayed.get("reason")
                else f" (`{_md(replayed.get('regime'))}`)"
            )
        ),
    ]
    for row in missing:
        identity = _md(row.get("canonical_asset_id")) or "unknown"
        symbol = _md(row.get("symbol"))
        rank = row.get("point_in_time_volume_rank")
        label = identity + (f" ({symbol})" if symbol else "")
        if type(rank) is int:
            label += f", rank {rank}"
        reasons = ", ".join(
            _control_regime_input_reason(reason)
            for reason in row.get("reasons") or ()
        )
        lines.append(f"  - `{label}`: {reasons or 'input contract invalid'}")
    lines.extend([
        "- Retained history mutated by report: `false`; historical backfill: `false`.",
        "- Routing/policy/Protocol-v2 evidence eligibility: `false`; provider calls: `0`.",
    ])
    return lines


def _control_regime_input_reason(value: Any) -> str:
    labels = {
        "market_history_not_counted": "row is not baseline-counted",
        "observation_identity_missing": "observation identity is missing",
        "canonical_asset_identity_missing": "canonical asset identity is missing",
        "temporal_return_value_missing_or_invalid": "causal 24-hour return is unavailable",
        "temporal_return_unit_invalid": "causal 24-hour return unit is unavailable",
        "temporal_return_evidence_invalid": "causal 24-hour evidence reference is unavailable",
    }
    return labels.get(_text(value), _md(value))


def _point_in_time_control_context_lines(value: Mapping[str, Any]) -> list[str]:
    if not value:
        return [
            "- Status: `unavailable`",
            "- This older report has no point-in-time control-context coverage projection.",
        ]
    coverage = _mapping(value.get("field_coverage_counts"))
    counted = _int(value.get("counted_observation_count"))
    return [
        f"- Status: `{_text(value.get('status')) or 'unavailable'}`",
        f"- Baseline-counted rows assessed: `{counted}`",
        (
            "- Complete point-in-time universe rows: "
            f"`{_int(value.get('point_in_time_universe_context_row_count'))}/{counted}`"
        ),
        (
            "- Complete matched-control context rows: "
            f"`{_int(value.get('complete_match_context_row_count'))}/{counted}`"
        ),
        (
            "- Control-liquidity coverage: "
            f"`{_int(coverage.get('control_liquidity_tier'))}/{counted}`"
        ),
        (
            "- Market-regime coverage: "
            f"`{_int(coverage.get('market_regime'))}/{counted}`"
        ),
        (
            "- Protocol-partition coverage: "
            f"`{_int(coverage.get('protocol_partition'))}/{counted}`"
        ),
        "- Selection performed: `false`; outcomes are not read by this projection.",
        "- Historical context backfilled: `false`; Protocol-v2 evidence eligible: `false`.",
    ]


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


def _episode_coverage_frontier_section(
    report: Mapping[str, Any],
) -> list[str]:
    value = _mapping(report.get("protocol_v2_episode_coverage_frontier"))
    route_rows = [
        dict(row)
        for row in value.get("route_coverage") or ()
        if isinstance(row, Mapping)
    ]
    origin_rows = [
        dict(row)
        for row in value.get("primary_origin_coverage") or ()
        if isinstance(row, Mapping)
    ]
    lines = [
        "## Protocol-v2 episode coverage frontier",
        "",
        (
            "This expands the frozen-episode scorecard across every canonical "
            "Decision route and primary origin, including categories with zero "
            "episodes. It is a descriptive coverage audit, not a sample-size "
            "decision or an independence claim."
        ),
        f"- Status: `{_text(value.get('status'))}`",
        f"- Frozen primary episodes: `{_int(value.get('episode_count'))}`",
        f"- Matured episode outcomes: `{_int(value.get('matured_episode_count'))}`",
        f"- Observed routes: `{_int(value.get('observed_route_count'))}`/"
        f"`{_int(value.get('route_population_count'))}`",
        f"- Zero-episode routes: `{_int(value.get('zero_episode_route_count'))}` "
        f"(`{_joined(value.get('unobserved_route_names')) or 'none'}`)",
        f"- Observed primary origins: "
        f"`{_int(value.get('observed_primary_origin_count'))}`/"
        f"`{_int(value.get('primary_origin_population_count'))}`",
        f"- Zero-episode primary origins: "
        f"`{_int(value.get('zero_episode_primary_origin_count'))}` "
        f"(`{_joined(value.get('unobserved_primary_origin_names')) or 'none'}`)",
        "- Minimum-sample policy sealed: `false`; sample sufficiency is not yet evaluable.",
        "- Statistical and cross-asset independence claimed: `false`.",
        "- Protocol-v2 evidence eligible: `false`.",
        "",
        "### Route coverage",
        "",
        "| Route | Coverage | Episodes | Matured | Due missing price | Not due | Excluded | Scoreable | Aligned |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(_episode_coverage_rows(route_rows))
    lines.extend([
        "",
        "### Primary-origin coverage",
        "",
        "| Primary origin | Coverage | Episodes | Matured | Due missing price | Not due | Excluded | Scoreable | Aligned |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    lines.extend(_episode_coverage_rows(origin_rows))
    lines.append("")
    return lines


def _episode_coverage_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [
        f"| {_md(row.get('name'))} | {_md(row.get('coverage_status'))} | "
        f"{_int(row.get('episode_count'))} | "
        f"{_int(row.get('matured_episode_count'))} | "
        f"{_int(row.get('due_missing_price_episode_count'))} | "
        f"{_int(row.get('not_due_episode_count'))} | "
        f"{_int(row.get('contract_excluded_episode_count'))} | "
        f"{_int(row.get('scoreable_directional_episode_count'))} | "
        f"{_int(row.get('aligned_episode_count'))} |"
        for row in rows
    ]


def _feature_maturity_lines(value: Any) -> list[str]:
    feature_readiness = _mapping(value)
    if not feature_readiness:
        return ["- Feature-level maturity is not yet available for this scope."]
    has_next_cycle_projection = any(
        isinstance(raw, Mapping)
        and "next_cycle_point_in_time_eligible_asset_count" in raw
        for raw in feature_readiness.values()
    )
    lines = (
        [
            "| Feature group | Warm | Warming | Cold | Other | Future same-asset eligible | Samples min-max / required | Elapsed min-max / required | Deficit assets | Status counts |",
            "|---|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
        if has_next_cycle_projection
        else [
            "| Feature group | Warm | Warming | Cold | Other | Samples min-max / required | Elapsed min-max / required | Status counts |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for name, raw in sorted(feature_readiness.items()):
        feature = _mapping(raw)
        counts = ", ".join(
            f"{key}={_int(count)}"
            for key, count in sorted(_mapping(feature.get("status_counts")).items())
        ) or "none"
        prefix = (
            f"| {_md(name)} | {_int(feature.get('warm_asset_count'))} | "
            f"{_int(feature.get('warming_asset_count'))} | "
            f"{_int(feature.get('cold_asset_count'))} | "
            f"{_int(feature.get('other_asset_count'))} | "
        )
        if has_next_cycle_projection:
            lines.append(
                prefix
                + f"{_int(feature.get('next_cycle_point_in_time_eligible_asset_count'))} | "
                f"{_md(_sample_progress(feature))} | "
                f"{_md(_coverage_progress(feature))} | "
                f"{_md(_deficit_asset_summary(feature.get('deficit_assets')))} | "
                f"{_md(counts)} |"
            )
        else:
            lines.append(
                prefix
                + f"{_md(_sample_progress(feature))} | "
                f"{_md(_coverage_progress(feature))} | {_md(counts)} |"
            )
    return lines


def _deficit_asset_summary(value: Any) -> str:
    rows = [dict(row) for row in value or () if isinstance(row, Mapping)]
    if not rows:
        return "none"
    rendered = []
    for row in rows:
        rendered.append(
            f"{_text(row.get('canonical_asset_id'))} "
            f"[{_text(row.get('status'))}; "
            f"samples {_int(row.get('sample_count'))}/{_int(row.get('required_sample_count'))} "
            f"(gap {_int(row.get('sample_deficit'))}); "
            f"coverage {_hours(row.get('coverage_seconds'))}/{_hours(row.get('required_coverage_seconds'))}h "
            f"(gap {_hours(row.get('coverage_deficit_seconds'))}h)]"
        )
    return "; ".join(rendered)


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
