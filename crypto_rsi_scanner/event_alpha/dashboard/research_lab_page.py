"""Server-rendered Decision Radar Research Lab inside the existing dashboard."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .components import (
    HtmlFragment,
    badge,
    chips,
    data_table,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
)
from .models import DashboardSnapshot
from .presentation import humanize_enum
from .research_lab_hardening_panel import render_hardening_conclusion_panel
from .research_lab_loader import ORIGINS, REPORT_FILENAMES, ROUTES
from .system_page_support import display_count, render_metric_grid, render_page_intro, render_panel


def render_research_lab_page(snapshot: DashboardSnapshot) -> str:
    """Render descriptive evidence without implying a production policy change."""

    lab = _mapping(snapshot.research_lab)
    projections = _mapping(lab.get("projections"))
    validation = _mapping(projections.get("validation"))
    analyses = _mapping_rows(validation.get("analyses"))
    walk = _mapping(projections.get("walk_forward"))
    policy = _mapping(projections.get("policy"))
    live = _mapping(projections.get("live"))
    bundle = _mapping(lab.get("bundle"))
    intro = render_page_intro(
        "Decision Radar Research Lab",
        "Historical replay, live no-send observations, walk-forward checks, and shadow policy comparisons. Evidence here is descriptive and remains outside dashboard authority.",
        "Learning · read-only",
    )
    boundary = _boundary_banner(
        lab,
        analyses,
        live,
        bundle,
        generation_authoritative=snapshot.generation_authoritative,
    )
    inventory = _report_availability(lab)
    if lab.get("bundle_status") != "validated":
        return "".join((intro, boundary, inventory, _bundle_failure_panel(lab)))

    return "".join((
        intro,
        boundary,
        render_hardening_conclusion_panel(lab),
        _overview(lab, bundle, analyses, walk, policy, live),
        _bundle_identity_panel(bundle),
        _final_verdict_panel(validation, bundle),
        inventory,
        _closed_cohort_panel("Closed route evidence", "Eight routes, including explicit zero-sample cohorts.", analyses, "route_cohorts", ROUTES),
        _closed_cohort_panel("Closed origin evidence", "Seven primary thesis origins, including explicit zero-sample cohorts.", analyses, "primary_origin_cohorts", ORIGINS),
        _monotonicity_panel(analyses),
        _segmentation_panel(analyses),
        _market_catalyst_panel(analyses),
        _classification_panel(analyses),
        _path_and_cost_panel(analyses),
        _walk_forward_panel(walk),
        _policy_and_burden_panel(policy, analyses),
        _live_replay_panel(validation, analyses, live),
        _warnings_panel(lab, validation, analyses, policy, live),
    ))


def _boundary_banner(
    lab: Mapping[str, Any],
    analyses: list[Mapping[str, Any]],
    live: Mapping[str, Any],
    bundle: Mapping[str, Any],
    *,
    generation_authoritative: bool,
) -> str:
    replay_modes = sorted({str(row.get("evidence_mode") or "unknown") for row in analyses})
    badges = [
        badge("Shadow only", tone="neutral"),
        badge("No automatic application", tone="positive"),
        badge(lab.get("status") or "unavailable", tone=_status_tone(lab.get("status"))),
    ]
    if _production_contract_unchanged(bundle):
        badges.insert(0, badge("Production policy unchanged", tone="info", icon="shield"))
    elif lab.get("bundle_status") != "validated":
        badges.insert(0, badge("Evidence bundle unavailable", tone="warning", icon="warning"))
    if live.get("available") is True:
        badges.append(badge("Live no-send", tone="info", icon="data"))
    if not generation_authoritative:
        badges.append(badge("Historical research · current authority unavailable", tone="warning"))
    if any("fixture" in mode.casefold() for mode in replay_modes):
        badges.append(badge("Fixture evidence", tone="warning"))
    if any(_analysis_is_insufficient(row) for row in analyses) or live.get("evidence_strength") == "insufficient_sample":
        badges.append(badge("Insufficient sample", tone="warning", icon="warning"))
    return (
        '<section class="panel"><div class="section-heading"><div>'
        '<p class="eyebrow">Research boundary</p><h2>Evidence, not activation</h2>'
        '<p>Production routes and thresholds are not changed by this page. Any shadow recommendation still requires a sealed evaluation and explicit human approval.</p>'
        '</div></div><div class="badge-row">' + "".join(str(item) for item in badges) + "</div></section>"
    )


def _overview(
    lab: Mapping[str, Any],
    bundle: Mapping[str, Any],
    analyses: list[Mapping[str, Any]],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    live: Mapping[str, Any],
) -> str:
    by_partition = {str(row.get("partition") or ""): row for row in analyses}
    recommendation_rows = _mapping_rows(policy.get("recommendations"))
    candidate_count = sum(str(row.get("status") or "") == "candidate" for row in recommendation_rows)
    return render_metric_grid((
        ("Research reports", f"{sum(_report_ready(lab, name) for name in REPORT_FILENAMES)}/7", "info"),
        ("Development episodes", _episode_pair(by_partition.get("development")), "neutral"),
        ("Validation episodes", _episode_pair(by_partition.get("validation")), "neutral"),
        ("Final-test episodes", _episode_pair(by_partition.get("final_test")), "neutral"),
        ("Bundle", _short_digest(bundle.get("bundle_id")), "info"),
        ("Nonempty walk-forward folds", display_count(walk.get("nonempty_fold_count")), "neutral"),
        ("Shadow candidates", str(candidate_count), "warning" if candidate_count else "neutral"),
        ("Production changes", "0", "positive"),
    ))


def _report_availability(lab: Mapping[str, Any]) -> str:
    reports = _mapping(lab.get("reports"))
    rows = []
    for filename in REPORT_FILENAMES:
        record = _mapping(reports.get(filename))
        digest = str(record.get("sha256") or "")
        read_status = str(record.get("status") or "not configured")
        rows.append((
            _report_label(filename),
            badge(
                read_status,
                label="Readable" if read_status == "ready" else humanize_enum(read_status),
                tone="neutral" if read_status == "ready" else _status_tone(read_status),
            ),
            display_count(record.get("size_bytes")),
            digest[:12] + "…" if digest else "Not available",
            str(record.get("filename") or ""),
        ))
    body = data_table(
        ("Report", "Read state", "Bytes", "SHA-256", "Fixed source"),
        rows,
        caption="Fixed Research Lab report inventory",
        compact=True,
    )
    return render_panel("Research evidence inventory", str(body), eyebrow="Bounded fixed-path reads")


def _bundle_failure_panel(lab: Mapping[str, Any]) -> str:
    warnings = [str(item) for item in _list(lab.get("warnings")) if str(item)]
    body = str(empty_state(
        "Semantic evidence suppressed",
        "The exact seven-file bundle is incomplete or invalid. No missing value is interpreted as zero evidence, and no research metric is rendered until the whole bundle validates.",
    ))
    if warnings:
        body += str(chips(warnings, humanize=False))
    return render_panel("Bundle validation failed closed", body, eyebrow="No partial semantics")


def _bundle_identity_panel(bundle: Mapping[str, Any]) -> str:
    selection = _mapping(bundle.get("selection_run"))
    final = _mapping(bundle.get("final_test_run"))
    rows = (
        ("Bundle", str(bundle.get("bundle_id") or "Not available")),
        ("Protocol", f"{bundle.get('protocol_version') or 'Not available'} · {_short_digest(bundle.get('protocol_sha256'))}"),
        ("Selection run", str(selection.get("run_fingerprint") or "Not available")),
        ("Final-test run", str(final.get("run_fingerprint") or "Not available")),
        ("Recommendation seal", str(bundle.get("recommendation_seal_sha256") or "Not available")),
    )
    return render_panel(
        "Validated evidence identity",
        str(definition_list(rows)),
        eyebrow="Exact immutable bindings",
    )


def _final_verdict_panel(
    validation: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> str:
    conclusions = _mapping(validation.get("conclusions"))
    status = str(conclusions.get("final_confirmation_status") or "unavailable")
    route_gaps = [humanize_enum(item) for item in _list(conclusions.get("routes_with_no_empirical_evidence"))]
    origin_gaps = [humanize_enum(item) for item in _list(conclusions.get("origins_with_no_empirical_evidence"))]
    rows = (
        ("Confirmed candidates", display_count(conclusions.get("confirmed_candidate_count"))),
        ("Rejected candidates", display_count(conclusions.get("rejected_candidate_count"))),
        ("Insufficient candidates", display_count(conclusions.get("insufficient_sample_candidate_count"))),
        (
            "Policy mutation",
            "No production change" if _production_contract_unchanged(bundle) else "Unavailable",
        ),
    )
    if status == "no_candidate_recommendations":
        verdict_copy = (
            '<p><strong>No candidate recommendations</strong> means development and validation '
            'sealed no policy hypothesis for holdout confirmation; it is not a holdout pass.</p>'
        )
        verdict_eyebrow = "Negative result preserved"
    else:
        verdict_copy = (
            f'<p><strong>{escape_html(humanize_enum(status))}</strong> is the sealed final-test '
            'result for the preselected candidate set. It does not auto-apply or authorize a '
            'production change.</p>'
        )
        verdict_eyebrow = "Sealed evaluation result"
    body = (
        '<div class="badge-row">'
        + str(badge(status, label=humanize_enum(status), tone="neutral", icon="shield"))
        + str(badge("Human decision required for any future change", tone="info"))
        + "</div>"
        + verdict_copy
        + str(definition_list(rows))
        + '<p><strong>No empirical evidence — routes:</strong> '
        + str(chips(route_gaps, humanize=False))
        + '</p><p><strong>No empirical evidence — primary origins:</strong> '
        + str(chips(origin_gaps, humanize=False))
        + "</p>"
    )
    return render_panel("Final empirical verdict", body, eyebrow=verdict_eyebrow)


def _closed_cohort_panel(
    title: str,
    description: str,
    analyses: list[Mapping[str, Any]],
    field: str,
    expected: tuple[str, ...],
) -> str:
    rows: list[tuple[object, ...]] = []
    for analysis in analyses:
        partition = _partition_label(analysis)
        by_name = {
            str(row.get("cohort") or ""): row
            for row in _mapping_rows(analysis.get(field))
        }
        for name in expected:
            row = _mapping(by_name.get(name))
            rows.append(_cohort_table_row(partition, name, row))
    table = data_table(
        ("Evidence", "Cohort", "Episodes", "Matured", "Mean directional", "Hit rate", "MFE", "MAE (signed)", "Strength"),
        rows,
        caption=title,
        empty="The empirical validation report is absent or invalid. No zero counts are inferred from missing evidence.",
        compact=True,
    )
    body = f"<p>{escape_html(description)}</p>{table}"
    return render_panel(title, body, eyebrow="Descriptive cohorts")


def _cohort_table_row(partition: str, name: str, row: Mapping[str, Any]) -> tuple[object, ...]:
    sample_state = (
        badge("No evidence", tone="neutral")
        if _count(row.get("episode_count")) == 0
        else badge(
            row.get("sample_status") or "not reported",
            tone=_evidence_tone(row.get("sample_status")),
        )
    )
    return (
        partition,
        humanize_enum(name),
        display_count(row.get("episode_count")),
        display_count(row.get("matured_episode_count")),
        _percent(row.get("mean_directional_return_fraction")),
        _percent(row.get("hit_rate")),
        _percent(row.get("mean_mfe_fraction")),
        _percent(row.get("mean_mae_fraction")),
        sample_state,
    )


def _monotonicity_panel(analyses: list[Mapping[str, Any]]) -> str:
    rows = []
    details: list[str] = []
    for analysis in analyses:
        partition = _partition_label(analysis)
        for item in _mapping_rows(analysis.get("score_monotonicity")):
            evaluation_status = str(item.get("evaluation_status") or "not_evaluable")
            violation_count = _count(item.get("violation_count"))
            if evaluation_status == "not_evaluable":
                observed = badge("Not evaluable", tone="neutral")
            elif violation_count:
                observed = badge("Descriptive violation", tone="warning")
            else:
                observed = badge("No observed violation", tone="positive")
            rows.append((
                partition,
                humanize_enum(item.get("score_field")),
                humanize_enum(item.get("expected_relationship")),
                display_count(item.get("comparable_pair_count")),
                display_count(violation_count),
                observed,
                humanize_enum(item.get("not_evaluable_reason"))
                if evaluation_status == "not_evaluable" else "—",
            ))
            bucket_rows = [
                (
                    str(row.get("cohort") or ""),
                    display_count(row.get("sample_size")),
                    _percent(row.get("mean_directional_return_fraction")),
                    _percent(row.get("hit_rate")),
                    humanize_enum(row.get("sample_status")),
                )
                for row in _mapping_rows(item.get("buckets"))
            ]
            if bucket_rows:
                details.append(str(disclosure(
                    f"{partition} · {humanize_enum(item.get('score_field'))} buckets",
                    data_table(("Bucket", "Sample", "Mean directional", "Hit rate", "Evidence"), bucket_rows, compact=True),
                    summary="Unadjusted descriptive check",
                )))
    table = data_table(
        ("Evidence", "Score", "Frozen expectation", "Comparable pairs", "Violations", "Evaluation", "Reason"),
        rows,
        caption="Score monotonicity checks",
        empty="No score monotonicity report is available.",
        compact=True,
    )
    return render_panel(
        "Score monotonicity",
        str(table) + "".join(details),
        eyebrow="Actionability · confidence · risk · urgency · chase",
    )


def _segmentation_panel(analyses: list[Mapping[str, Any]]) -> str:
    rows: list[tuple[object, ...]] = []
    fields = (
        ("Market regime", "market_regime_cohorts"),
        ("Liquidity tier", "liquidity_tier_cohorts"),
        ("Data quality", "data_quality_cohorts"),
    )
    for analysis in analyses:
        partition = _partition_label(analysis)
        for dimension, field in fields:
            for row in _mapping_rows(analysis.get(field)):
                rows.append((
                    partition,
                    dimension,
                    humanize_enum(row.get("cohort")),
                    display_count(row.get("episode_count")),
                    display_count(row.get("matured_episode_count")),
                    display_count(row.get("sample_size")),
                    _percent(row.get("mean_directional_return_fraction")),
                    _percent(row.get("hit_rate")),
                    badge(row.get("sample_status") or "not reported", tone=_evidence_tone(row.get("sample_status"))),
                ))
    table = data_table(
        ("Evidence", "Dimension", "Cohort", "Episodes", "Matured", "Scoreable", "Mean directional", "Hit rate", "Strength"),
        rows,
        caption="Regime, liquidity, and data-quality cohorts",
        empty="No segmented cohort evidence is available.",
        compact=True,
    )
    return render_panel("Regimes, liquidity & data quality", str(table), eyebrow="Robustness slices")


def _market_catalyst_panel(analyses: list[Mapping[str, Any]]) -> str:
    rows = []
    for analysis in analyses:
        partition = _partition_label(analysis)
        for row in _mapping_rows(analysis.get("market_catalyst_cohorts")):
            rows.append(_cohort_table_row(partition, str(row.get("cohort") or "unknown"), row))
    table = data_table(
        ("Evidence", "Market / catalyst cohort", "Episodes", "Matured", "Mean directional", "Hit rate", "MFE", "MAE (signed)", "Strength"),
        rows,
        caption="Market-led and catalyst-context comparison",
        empty="No market-versus-catalyst cohort evidence is available.",
        compact=True,
    )
    return render_panel("Market vs catalyst", str(table), eyebrow="Context, not causal attribution")


def _classification_panel(analyses: list[Mapping[str, Any]]) -> str:
    rows = []
    symptoms: Counter[str] = Counter()
    missed_reasons: Counter[str] = Counter()
    for analysis in analyses:
        missed = _mapping(analysis.get("missed_opportunity_summary"))
        false_late = _mapping(analysis.get("false_positive_and_late_summary"))
        missed_counts = _mapping(missed.get("classification_counts"))
        symptom_counts = _mapping(false_late.get("symptom_counts"))
        missed_reasons.update({
            str(key): _count(value)
            for key, value in _mapping(missed.get("reason_counts")).items()
        })
        symptoms.update({
            str(key): _count(value)
            for key, value in symptom_counts.items()
        })
        rows.append((
            _partition_label(analysis),
            display_count(missed_counts.get("missed_opportunity")),
            display_count(symptom_counts.get("failed_quickly")),
            display_count(symptom_counts.get("late_pre_signal_move")),
            display_count(false_late.get("row_count")),
        ))
    summary = data_table(
        (
            "Evidence",
            "Missed",
            "Failed quickly symptom",
            "Late pre-signal symptom",
            "Rows summarized",
        ),
        rows,
        empty="No missed/false/late classifications are available.",
        compact=True,
    )
    reason_rows = [
        ("Missed reason", humanize_enum(name), str(count)) for name, count in missed_reasons.most_common(16)
    ] + [
        ("False/late symptom", humanize_enum(name), str(count)) for name, count in symptoms.most_common(16)
    ]
    detail = data_table(
        ("Type", "Frozen classification", "Episodes"),
        reason_rows,
        empty="No classified symptoms were observed in scoreable episodes.",
        compact=True,
    )
    return render_panel(
        "Missed moves & false/late symptoms",
        str(summary) + str(disclosure("Classification detail", detail, summary="Frozen descriptive rules")),
        eyebrow="Error analysis",
    )


def _path_and_cost_panel(analyses: list[Mapping[str, Any]]) -> str:
    path_rows = []
    cost_rows = []
    survivability_rows = []
    spread_observed = False
    for analysis in analyses:
        partition = _partition_label(analysis)
        for row in _mapping_rows(analysis.get("route_cohorts")):
            path_rows.append((
                partition,
                humanize_enum(row.get("cohort")),
                display_count(row.get("sample_size")),
                _percent(row.get("mean_mfe_fraction")),
                _percent(row.get("mean_mae_fraction")),
                _ratio(row.get("mfe_to_mae_ratio_of_means")),
                _percent(row.get("downside_5pct_fraction")),
            ))
        costs = _mapping(analysis.get("cost_sensitivity"))
        spread_observed = spread_observed or costs.get("historical_spread_observed") is True
        for row in _mapping_rows(costs.get("scenarios")):
            survives = row.get("mean_survives_assumed_cost")
            cost_rows.append((
                partition,
                display_count(row.get("round_trip_cost_bps")) + " bps",
                display_count(row.get("sample_size")),
                _percent(row.get("mean_net_directional_return_fraction")),
                _percent(row.get("net_hit_rate")),
                badge(
                    "Survives" if survives is True else "Does not survive" if survives is False else "Not estimable",
                    tone="positive" if survives is True else "warning" if survives is False else "muted",
                ),
            ))
        route_survivability = _mapping(
            _mapping(analysis.get("survivability")).get("route_cost_survivability")
        )
        for row in _mapping_rows(route_survivability.get("routes")):
            maximum = row.get("maximum_tolerable_round_trip_cost_bps")
            survivability_rows.append((
                partition,
                humanize_enum(row.get("route")),
                display_count(row.get("episode_count")),
                humanize_enum(row.get("evidence_status")),
                f"{float(maximum):.1f} bps"
                if isinstance(maximum, (int, float)) and not isinstance(maximum, bool)
                else "Not estimable",
                humanize_enum(route_survivability.get("historical_spread_observation_status")),
            ))
    paths = data_table(
        ("Evidence", "Route", "Sample", "Mean MFE", "Mean MAE (signed)", "MFE / MAE", "Downside 5%"),
        path_rows,
        caption="Path-dependent excursion evidence",
        empty="No MFE/MAE path evidence is available.",
        compact=True,
    )
    costs = data_table(
        ("Evidence", "Assumed round trip", "Sample", "Mean net", "Net hit rate", "Mean after cost"),
        cost_rows,
        caption="Frozen cost sensitivity",
        empty="No cost sensitivity evidence is available.",
        compact=True,
    )
    survivability = data_table(
        ("Evidence", "Route", "Episodes", "Evidence", "Mean break-even", "Observed spread"),
        survivability_rows,
        caption="Route cost survivability",
        empty="No route survivability evidence is available.",
        compact=True,
    )
    badges = '<div class="badge-row">' + str(badge(
        "Historical spread observed" if spread_observed else "Historical spread not observed",
        tone="positive" if spread_observed else "warning",
    )) + str(badge("Costs are assumed sensitivity, not execution evidence", tone="info")) + "</div>"
    return render_panel(
        "MFE, MAE & assumed costs",
        badges
        + '<p>MAE is a signed direction-adjusted adverse excursion; negative values are preserved.</p>'
        + str(paths)
        + str(disclosure("Assumed cost scenarios", costs, summary="Historical spread is unavailable"))
        + str(disclosure("Route survivability", survivability, summary="Descriptive, not an execution limit")),
        eyebrow="Path outcomes",
    )


def _walk_forward_panel(walk: Mapping[str, Any]) -> str:
    folds = _mapping_rows(walk.get("folds"))
    rows = []
    day_rows = []
    for row in folds:
        result = _mapping(row.get("test_result"))
        rows.append((
            display_count(row.get("fold")),
            _window(row.get("train_start"), row.get("train_end_exclusive")),
            _window(row.get("test_start"), row.get("test_end_exclusive")),
            display_count(row.get("train_episode_count")),
            display_count(row.get("test_episode_count")),
            humanize_enum(row.get("selected_scenario")),
            _percent(result.get("mean_directional_return_fraction")),
            _percent(result.get("hit_rate")),
            humanize_enum(result.get("evidence_strength")),
        ))
        selected_days = _count(row.get("test_selected_observation_day_count"))
        active_days = _count(row.get("test_idea_active_day_count"))
        day_rows.append((
            display_count(row.get("fold")),
            display_count(row.get("train_outcome_purged_count")),
            display_count(row.get("test_outcome_purged_count")),
            str(selected_days),
            str(active_days),
            str(max(0, selected_days - active_days)),
        ))
    table = data_table(
        ("Fold", "Train window", "Test window", "Train N", "Test N", "Selected shadow", "Test mean", "Test hit", "Strength"),
        rows,
        caption="Chronological rolling train/test folds",
        empty="Walk-forward evidence is absent or has no folds.",
        compact=True,
    )
    days = data_table(
        ("Fold", "Train outcomes purged", "Test outcomes purged", "Selected days", "Idea-active days", "Zero-idea days"),
        day_rows,
        caption="Point-in-time day denominators and outcome purges",
        empty="No fold denominator evidence is available.",
        compact=True,
    )
    status = badge(walk.get("status") or "unavailable", tone=_evidence_tone(walk.get("status")))
    guard = badge(
        "Final test untouched" if walk and walk.get("final_test_accessed") is not True else "Final-test firewall unavailable",
        tone="positive" if walk and walk.get("final_test_accessed") is not True else "warning",
        icon="shield",
    )
    selected = _count(walk.get("selected_observation_day_count"))
    active = _count(walk.get("idea_active_day_count"))
    header = f'<div class="badge-row">{status}{guard}</div>' if walk else ""
    summary = definition_list((
        ("Selected observation days", str(selected)),
        ("Idea-active days", str(active)),
        ("Zero-idea days", str(max(0, selected - active))),
        ("Outcome purge rule", humanize_enum(walk.get("outcome_purge_rule"))),
        ("Outcome-evaluable folds", display_count(walk.get("outcome_evaluable_fold_count"))),
    ))
    return render_panel(
        "Chronological walk-forward",
        header + str(summary) + str(table) + str(disclosure(
            "Fold purges and day denominators",
            days,
            summary="Outcome leakage controls",
        )),
        eyebrow="Out-of-window stability",
    )


def _policy_and_burden_panel(policy: Mapping[str, Any], analyses: list[Mapping[str, Any]]) -> str:
    scenario_rows = []
    for row in _mapping_rows(policy.get("scenarios")):
        scenario_rows.append((
            humanize_enum(row.get("scenario")),
            display_count(row.get("visible_episode_count")),
            display_count(row.get("matured_visible_episode_count")),
            display_count(row.get("route_change_count")),
            _decimal(row.get("ideas_per_active_day")),
            _percent(row.get("mean_directional_return_fraction")),
            _percent(row.get("quick_failure_rate")),
            humanize_enum(row.get("evidence_strength")),
        ))
    recommendation_rows = [
        (
            humanize_enum(row.get("scenario")),
            badge(row.get("status") or "not reported", tone=_evidence_tone(row.get("status"))),
            display_count(row.get("sample_size")),
            humanize_enum(row.get("evidence_strength")),
            humanize_enum(row.get("reason")),
            "Required" if row.get("human_approval_required") is True else "Not recorded",
        )
        for row in _mapping_rows(policy.get("recommendations"))
    ]
    burden_rows = []
    for analysis in analyses:
        burden = _mapping(analysis.get("operator_burden"))
        if burden:
            selected_days = _count(burden.get("observed_day_count"))
            active_days = _count(burden.get("idea_active_day_count"))
            burden_rows.append((
                _partition_label(analysis),
                display_count(burden.get("episode_count")),
                str(selected_days),
                str(active_days),
                str(max(0, selected_days - active_days)),
                display_count(burden.get("family_count")),
                _decimal(burden.get("mean_ideas_per_observed_day")),
                display_count(burden.get("urgent_visible_episode_count")),
                display_count(burden.get("visible_dependent_repeat_item_count")),
            ))
    scenarios = data_table(
        ("Shadow scenario", "Visible", "Matured", "Route changes", "Ideas / active day", "Mean directional", "Quick failures", "Strength"),
        scenario_rows,
        empty="No shadow-policy simulation is available.",
        compact=True,
    )
    recommendations = data_table(
        ("Scenario", "Shadow status", "Sample", "Strength", "Frozen reason", "Human approval"),
        recommendation_rows,
        empty="No shadow recommendation has been recorded.",
        compact=True,
    )
    burden = data_table(
        ("Evidence", "Ideas", "Selected days", "Idea-active days", "Zero-idea days", "Families", "Ideas / selected day", "Urgent", "Repeated family"),
        burden_rows,
        empty="No operator-burden summary is available.",
        compact=True,
    )
    decision_boundary = _mapping(policy.get("decision_boundary"))
    unchanged = (
        decision_boundary.get("production_policy_unchanged") is True
        and decision_boundary.get("automatic_policy_application") is False
    )
    body = (
        '<div class="badge-row">'
        + str(badge(
            "Production policy unchanged" if unchanged else "Production policy state unavailable",
            tone="info" if unchanged else "warning",
            icon="shield",
        ))
        + str(badge("shadow_only", label="Shadow recommendations do not auto-apply", tone="warning"))
        + "</div>"
        + str(scenarios)
        + str(disclosure("Shadow recommendations", recommendations, summary="Human approval required"))
        + str(disclosure("Operator burden", burden, summary="Visibility and review load"))
    )
    return render_panel("Shadow policy & operator burden", body, eyebrow="No automatic thresholds")


def _live_replay_panel(
    validation: Mapping[str, Any],
    analyses: list[Mapping[str, Any]],
    live: Mapping[str, Any],
) -> str:
    rows = []
    live_snapshot_note = ""
    for analysis in analyses:
        rows.append((
            "Historical replay",
            _partition_label(analysis),
            display_count(analysis.get("episode_count")),
            display_count(analysis.get("matured_episode_count")),
            humanize_enum(_analysis_strength(analysis)),
            "No",
            "Separated evidence mode",
        ))
    if live.get("available") is True:
        episodes = _mapping(live.get("episodes"))
        scorecard = _mapping(live.get("scorecard"))
        episode_count = _count(episodes.get("primary_episode_count"))
        repeat_count = _count(episodes.get("repeat_member_count"))
        source_generated_at = str(live.get("source_generated_at") or "unknown")
        live_snapshot_note = (
            '<p class="muted">The live row is the immutable campaign snapshot '
            "bound into this empirical bundle, not the current dashboard campaign. "
            f"Snapshot time: {escape_html(source_generated_at)}. Its "
            f"{episode_count} fixed-start {_plural(episode_count, 'episode')} and "
            f"{repeat_count} dependent {_plural(repeat_count, 'repeat')} are "
            "descriptive groups; statistical independence is not claimed.</p>"
        )
        rows.append((
            "Live no-send",
            humanize_enum(live.get("campaign_status")),
            display_count(episode_count),
            display_count(scorecard.get("matured_episode_count")),
            humanize_enum(live.get("evidence_strength")),
            "No",
            humanize_enum(scorecard.get("policy_conclusion")),
        ))
    table = data_table(
        ("Evidence mode", "Partition / state", "Episodes", "Matured", "Strength", "Policy eligible", "Interpretation"),
        rows,
        caption="Live and replay evidence remain separate",
        empty="No live or replay evidence is available. Missing evidence is not negative evidence.",
        compact=True,
    )
    campaign_evidence = ""
    if live.get("available") is True:
        shadow = _mapping(live.get("shadow_temporal_surprise"))
        human_review = _mapping(live.get("human_review"))
        control_context = _mapping(live.get("point_in_time_control_context"))
        episode_frontier = _mapping(live.get("episode_coverage_frontier"))
        campaign_evidence = (
            _live_episode_coverage_frontier(episode_frontier)
            + _live_point_in_time_control_context(control_context)
            + _live_shadow_coverage(shadow)
            + _live_human_review(human_review)
        )
    control_rows = []
    for label, controls in (
        ("Development + validation", _mapping(validation.get("selection_controls"))),
        ("Final test", _mapping(validation.get("final_test_controls"))),
    ):
        if controls:
            control_rows.append((
                label,
                display_count(controls.get("idea_count")),
                display_count(_mapping(controls.get("matched_non_signal_controls")).get("selected_control_count")),
                str(len(_mapping_rows(controls.get("benchmarks")))),
                "No" if controls.get("matched_control_causal_claim") is False else "Unavailable",
            ))
    controls_body = data_table(
        ("Evidence", "Ideas", "Matched controls", "Benchmarks", "Causal claim"),
        control_rows,
        empty="No matched-control or benchmark summary is available.",
        compact=True,
    )
    return render_panel(
        "Live no-send vs replay",
        '<p>Live no-send evidence is a separate observational lane and is never pooled into historical replay sample sizes.</p>'
        + live_snapshot_note
        + str(table)
        + campaign_evidence
        + str(disclosure("Controls & benchmarks", controls_body, summary="No causal claim")),
        eyebrow="Evidence separation",
    )


def _live_episode_coverage_frontier(value: Mapping[str, Any]) -> str:
    if not value:
        return ""
    if value.get("available") is not True:
        return str(disclosure(
            "Live episode coverage frontier",
            '<p class="muted">This immutable live campaign snapshot predates '
            "the closed all-route/all-origin frontier. Missing compatibility "
            "data is not zero episode coverage.</p>",
            summary="Not available in this historical live snapshot",
        ))
    contract = _mapping(value.get("contract"))
    routes = _mapping_rows(contract.get("route_coverage"))
    origins = _mapping_rows(contract.get("primary_origin_coverage"))
    if not routes or not origins:
        return ""
    route_table = data_table(
        (
            "Route",
            "Coverage",
            "Episodes",
            "Matured",
            "Not due",
            "Missing price",
            "Scoreable",
        ),
        [
            (
                humanize_enum(row.get("name")),
                "Observed"
                if row.get("coverage_status") == "observed"
                else "No episode",
                display_count(row.get("episode_count")),
                display_count(row.get("matured_episode_count")),
                display_count(row.get("not_due_episode_count")),
                display_count(row.get("due_missing_price_episode_count")),
                display_count(row.get("scoreable_directional_episode_count")),
            )
            for row in routes
        ],
        caption="Live no-send route episode coverage",
        compact=True,
    )
    origin_table = data_table(
        ("Primary origin", "Coverage", "Episodes", "Matured", "Scoreable"),
        [
            (
                humanize_enum(row.get("name")),
                "Observed"
                if row.get("coverage_status") == "observed"
                else "No episode",
                display_count(row.get("episode_count")),
                display_count(row.get("matured_episode_count")),
                display_count(row.get("scoreable_directional_episode_count")),
            )
            for row in origins
        ],
        caption="Live no-send primary-origin episode coverage",
        compact=True,
    )
    observed_routes = display_count(contract.get("observed_route_count"))
    route_total = display_count(contract.get("route_population_count"))
    observed_origins = display_count(
        contract.get("observed_primary_origin_count")
    )
    origin_total = display_count(contract.get("primary_origin_population_count"))
    body = (
        '<p class="muted">This is the exact live campaign snapshot sealed into '
        "the empirical bundle. Zero rows are missing evidence, not negative "
        "results. Minimum samples, independence, matched controls, and "
        "Protocol-v2 eligibility remain unsealed.</p>"
        + str(route_table)
        + str(disclosure(
            "Primary-origin coverage",
            origin_table,
            summary=f"{observed_origins}/{origin_total} origins observed",
        ))
    )
    return str(disclosure(
        "Live episode coverage frontier",
        body,
        summary=(
            f"{observed_routes}/{route_total} routes · "
            f"{observed_origins}/{origin_total} origins observed"
        ),
    ))


def _live_point_in_time_control_context(value: Mapping[str, Any]) -> str:
    if value.get("available") is not True:
        return str(disclosure(
            "Prospective matched-control context",
            '<p class="muted">This immutable campaign snapshot predates the closed point-in-time control-context projection. Missing compatibility data is not zero coverage, and no matched control is inferred.</p>',
            summary="Unavailable in this snapshot",
        ))
    coverage = _mapping(value.get("field_coverage_counts"))
    counted = _count(value.get("counted_observation_count"))
    rows = (
        (
            "Observation date",
            display_count(coverage.get("observation_date")),
            display_count(counted),
        ),
        (
            "Complete point-in-time universe context",
            display_count(value.get("point_in_time_universe_context_row_count")),
            display_count(counted),
        ),
        (
            "Control liquidity tier",
            display_count(coverage.get("control_liquidity_tier")),
            display_count(counted),
        ),
        (
            "Market regime",
            display_count(coverage.get("market_regime")),
            display_count(counted),
        ),
        (
            "Protocol-v2 partition",
            display_count(coverage.get("protocol_partition")),
            display_count(counted),
        ),
        (
            "Complete match context",
            display_count(value.get("complete_match_context_row_count")),
            display_count(counted),
        ),
    )
    body = HtmlFragment(
        str(data_table(
            ("Control-selection evidence", "Covered rows", "Assessed rows"),
            rows,
            empty="No point-in-time control context is available.",
            compact=True,
        ))
        + (
            '<p class="muted">Coverage is prospective and outcome-blind. Historical rows were not backfilled; '
            "no control was selected; and missing market-regime or sealed-partition context remains missing. "
            "This projection cannot change routes, scores, thresholds, publication authority, or Protocol-v2 evidence status.</p>"
        )
    )
    return str(disclosure(
        "Prospective matched-control context",
        body,
        summary=humanize_enum(value.get("status")),
    ))


def _live_shadow_coverage(shadow: Mapping[str, Any]) -> str:
    if shadow.get("available") is not True:
        return str(disclosure(
            "Causal feature coverage",
            '<p class="muted">This immutable campaign snapshot predates the closed causal temporal-surprise coverage projection. Missing compatibility data is not zero evidence.</p>',
            summary="Unavailable in this snapshot",
        ))
    coverage = _mapping(shadow.get("feature_coverage"))
    rows = []
    for feature, raw in sorted(coverage.items()):
        row = _mapping(raw)
        statuses = _mapping(row.get("status_counts"))
        rows.append((
            humanize_enum(feature),
            humanize_enum(row.get("family")),
            display_count(row.get("evaluated_observation_count")),
            display_count(row.get("ready_count")),
            display_count(statuses.get("insufficient_history")),
            display_count(statuses.get("current_unavailable")),
        ))
    counts = _mapping(shadow.get("projection_status_counts"))
    body = (
        '<p class="muted">Every projection uses only strictly earlier same-asset observations. '
        f"Evaluated: {escape_html(display_count(shadow.get('evaluated_observation_count')))}; "
        f"complete: {escape_html(display_count(counts.get('ready')))}; "
        f"partial: {escape_html(display_count(counts.get('partial')))}; "
        f"unavailable: {escape_html(display_count(counts.get('unavailable')))}. "
        "Coverage is descriptive; it does not alter routes, scores, thresholds, or authority.</p>"
        + str(data_table(
            ("Feature", "Family", "Evaluated", "Ready", "Warming", "Current unavailable"),
            rows,
            empty="No causal feature rows are available.",
            compact=True,
        ))
    )
    return str(disclosure(
        "Causal feature coverage",
        body,
        summary=(
            "All modeled features have some ready evidence"
            if shadow.get("all_features_have_ready_evidence") is True
            else "Feature coverage remains incomplete"
        ),
    ))


def _live_human_review(human_review: Mapping[str, Any]) -> str:
    if human_review.get("available") is not True:
        return str(disclosure(
            "Human review evidence",
            '<p class="muted">This immutable campaign snapshot predates the explicit human-review queue projection. Dashboard reads are never inferred as human actions.</p>',
            summary="Unavailable in this snapshot",
        ))
    rows = (
        ("Receipt-backed ideas", display_count(human_review.get("eligible_idea_count"))),
        ("Awaiting explicit action", display_count(human_review.get("action_required_count"))),
        ("First views recorded", display_count(human_review.get("first_view_record_count"))),
        ("Completed reviews", display_count(human_review.get("completed_review_record_count"))),
        ("Latency samples", display_count(human_review.get("completed_latency_sample_count"))),
    )
    body = str(data_table(
        ("Review evidence", "Count"),
        rows,
        empty="No human-review evidence is available.",
        compact=True,
    )) + (
        '<p class="muted">Only explicit confirmed operator actions count. '
        f"Latency status: {escape_html(humanize_enum(human_review.get('latency_evidence_status')))}. "
        "The queue is descriptive and is not Protocol-v2 evidence until separately frozen.</p>"
    )
    return str(disclosure(
        "Human review evidence",
        body,
        summary=humanize_enum(human_review.get("status")),
    ))


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else singular + "s"


def _warnings_panel(
    lab: Mapping[str, Any],
    validation: Mapping[str, Any],
    analyses: list[Mapping[str, Any]],
    policy: Mapping[str, Any],
    live: Mapping[str, Any],
) -> str:
    warnings = [str(value) for value in _list(lab.get("warnings")) if str(value)]
    supplement = _mapping(lab.get("hardening_supplement"))
    warnings.extend(
        str(value)
        for value in _list(supplement.get("warnings"))
        if str(value)
    )
    warnings.extend(
        str(row.get("multiple_comparison_warning"))
        for row in analyses
        if row.get("multiple_comparison_warning")
    )
    if policy.get("multiple_comparison_warning"):
        warnings.append(str(policy["multiple_comparison_warning"]))
    warning_rows = [(str(index + 1), warning) for index, warning in enumerate(dict.fromkeys(warnings))]
    warning_table = data_table(
        ("#", "Warning"),
        warning_rows,
        empty="No loader or multiple-comparison warnings were reported.",
        compact=True,
    )
    conclusion_values = _mapping(validation.get("conclusions"))
    limitations = _generic_summary(
        conclusion_values.get("what_is_not_validated"),
        "No validation limitations report is available.",
    )
    live_limitations = _generic_summary(
        live.get("limitations"),
        "No live-campaign limitations report is available.",
    )
    conclusions = _generic_summary(
        conclusion_values,
        "No bounded report conclusions are available.",
    )
    body = (
        str(warning_table)
        + str(disclosure("Validation limitations", limitations, summary="Read before interpreting cohorts", open=True))
        + str(disclosure("Live no-send limitations", live_limitations, summary="Separate operational evidence"))
        + str(disclosure("Bounded report conclusions", conclusions, summary="Descriptive only"))
    )
    return render_panel("Warnings & limitations", body, eyebrow="Interpretation guardrails")


def _generic_summary(value: Any, empty_message: str) -> HtmlFragment:
    if value in (None, {}, []):
        return empty_state("Not available", empty_message)
    pairs: list[tuple[object, object]] = []
    if isinstance(value, Mapping):
        for key, item in list(value.items())[:32]:
            pairs.append((humanize_enum(key), _generic_value(item)))
    elif isinstance(value, list):
        for index, item in enumerate(value[:32], 1):
            pairs.append((f"Item {index}", _generic_value(item)))
    else:
        pairs.append(("Value", _generic_value(value)))
    return definition_list(pairs)


def _generic_value(value: Any) -> HtmlFragment | str:
    if isinstance(value, Mapping):
        text = "; ".join(
            f"{humanize_enum(key)}: {_plain_value(item)}"
            for key, item in list(value.items())[:12]
        )
        return text or "Not available"
    if isinstance(value, list):
        return chips((_plain_value(item) for item in value[:16]), humanize=False)
    return _plain_value(value)


def _plain_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return "; ".join(
            f"{humanize_enum(key)}: {_plain_value(item)}"
            for key, item in list(value.items())[:8]
        )
    if isinstance(value, list):
        return ", ".join(_plain_value(item) for item in value[:8])
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value in (None, ""):
        return "Not available"
    return str(value)


def _report_ready(lab: Mapping[str, Any], key: str) -> int:
    return int(_mapping(_mapping(lab.get("reports")).get(key)).get("status") == "ready")


def _production_contract_unchanged(bundle: Mapping[str, Any]) -> bool:
    contract = _mapping(bundle.get("production_contract"))
    return bool(contract) and all(
        contract.get(field) is False
        for field in (
            "dashboard_authority_changed",
            "policy_applied",
            "routes_changed",
            "thresholds_changed",
        )
    ) and contract.get("human_approval_required") is True


def _episode_pair(value: Any) -> str:
    row = _mapping(value)
    if not row:
        return "Not available"
    return f"{_count(row.get('episode_count'))} / {_count(row.get('matured_episode_count'))}"


def _short_digest(value: Any) -> str:
    digest = str(value or "")
    return digest[:12] + "…" if digest else "Not available"


def _report_label(filename: str) -> str:
    labels = {
        REPORT_FILENAMES[0]: "Empirical validation · human",
        REPORT_FILENAMES[1]: "Empirical validation · machine",
        REPORT_FILENAMES[2]: "Walk-forward · human",
        REPORT_FILENAMES[3]: "Walk-forward · machine",
        REPORT_FILENAMES[4]: "Policy simulation · human",
        REPORT_FILENAMES[5]: "Policy simulation · machine",
        REPORT_FILENAMES[6]: "Research limitations",
    }
    return labels.get(filename, filename)


def _analysis_is_insufficient(value: Mapping[str, Any]) -> bool:
    return _count(value.get("directional_return_sample_size")) < 5


def _analysis_strength(value: Mapping[str, Any]) -> str:
    strengths = [str(row.get("sample_status") or "") for row in _mapping_rows(value.get("route_cohorts")) if _count(row.get("sample_size"))]
    if not strengths:
        return "no_evidence"
    if any(item == "insufficient_sample" for item in strengths):
        return "insufficient_sample"
    return strengths[0]


def _partition_label(value: Mapping[str, Any]) -> str:
    partition = humanize_enum(value.get("partition") or "unknown")
    mode = humanize_enum(value.get("evidence_mode") or "unknown")
    return f"{partition} · {mode}"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _percent(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Not available"
    return f"{float(value) * 100:.2f}%"


def _ratio(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Not available"
    return f"{float(value):.2f}×"


def _decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Not available"
    return f"{float(value):.2f}"


def _window(start: Any, end: Any) -> str:
    start_text = str(start or "Not available")[:10]
    end_text = str(end or "Not available")[:10]
    return f"{start_text} → {end_text}"


def _status_tone(value: Any) -> str:
    token = str(value or "").casefold()
    if token == "ready":
        return "positive"
    if token in {"partial", "missing", "not_configured"}:
        return "warning"
    return "danger" if token else "muted"


def _evidence_tone(value: Any) -> str:
    token = str(value or "").casefold()
    if token in {"ready", "complete", "candidate", "cohort_directional_sample", "shadow_recommendation_sample"}:
        return "positive"
    if "insufficient" in token or token in {"partial", "descriptive_sample", "not_supported"}:
        return "warning"
    return "neutral"


__all__ = ("render_research_lab_page",)
