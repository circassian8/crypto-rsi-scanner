"""Deterministic Markdown rendering for Decision Radar campaign reports."""

from __future__ import annotations

from typing import Any, Mapping


def format_campaign_report(report: Mapping[str, Any]) -> str:
    """Render the canonical report as deterministic operator-facing Markdown."""

    metrics = _mapping(report.get("campaign_metrics"))
    outcomes = _mapping(report.get("outcomes"))
    baseline = _mapping(report.get("baseline_maturity"))
    pointer = _mapping(report.get("pointer"))
    next_observation = _mapping(report.get("next_observation"))
    limitations = list(report.get("data_quality_limitations") or ())
    conclusion = _mapping(report.get("campaign_v2_conclusion"))
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
        f"- Provider failures: `{_int(metrics.get('provider_failed_attempts'))}`",
        f"- Preflight/blocked attempts: `{_int(metrics.get('blocked_attempts'))}`",
        "- Event Alpha catalyst burn-in: `separate_not_aggregated`",
        "- Historical market-provenance v2 fields: `read_only_adapter`",
        "",
        "### Decision routes",
        "",
    ]
    route_counts = _mapping(metrics.get("route_counts"))
    lines.extend(
        [f"- `{route}`: `{_int(count)}`" for route, count in sorted(route_counts.items())]
        or ["- No real Decision candidates yet."]
    )
    lines.extend([
        "",
        "## Authority and pointer",
        "",
        f"- Pointer status: `{_text(pointer.get('status'))}`",
        f"- Current namespace: `{_text(pointer.get('artifact_namespace')) or 'none'}`",
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
    lines.extend([
        "",
        "## Baseline maturity",
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
        "### Feature maturity",
        "",
    ])
    lines.extend(_feature_maturity_lines(baseline.get("baseline_feature_readiness")))
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
        "- Human labels remain optional preference feedback; no thresholds or routes change automatically.",
        "",
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
        "Spread-provider selection remains deferred until the operator identifies the intended execution venue.",
        "No trade is recommended. No automatic threshold or route change is authorized.",
        "",
    ])
    return "\n".join(lines)


def _feature_maturity_lines(value: Any) -> list[str]:
    feature_readiness = _mapping(value)
    if not feature_readiness:
        return ["- Feature-level maturity is not yet available in retained evidence."]
    lines = [
        "| Feature group | Warm assets | Warming assets | Status counts |",
        "|---|---:|---:|---|",
    ]
    for name, raw in sorted(feature_readiness.items()):
        feature = _mapping(raw)
        counts = ", ".join(
            f"{key}={_int(count)}"
            for key, count in sorted(_mapping(feature.get("status_counts")).items())
        ) or "none"
        lines.append(
            f"| {_md(name)} | {_int(feature.get('warm_asset_count'))} | "
            f"{_int(feature.get('warming_asset_count'))} | {_md(counts)} |"
        )
    return lines


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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _md(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("`", "'").replace("\n", " ")


__all__ = ("format_campaign_report",)
