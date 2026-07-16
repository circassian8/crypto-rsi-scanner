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
from .research_lab_loader import ORIGINS, ROUTES
from .system_page_support import display_count, render_metric_grid, render_page_intro, render_panel


def render_research_lab_page(snapshot: DashboardSnapshot) -> str:
    """Render descriptive evidence without implying a production policy change."""

    lab = _mapping(snapshot.research_lab)
    validation = _projection(lab, "validation")
    analyses = _mapping_rows(validation.get("analyses"))
    walk = _projection(lab, "walk_forward")
    policy = _projection(lab, "policy")
    live = _projection(lab, "live_campaign")

    return "".join((
        render_page_intro(
            "Decision Radar Research Lab",
            "Historical replay, live no-send observations, walk-forward checks, and shadow policy comparisons. Evidence here is descriptive and remains outside dashboard authority.",
            "Learning · read-only",
        ),
        _boundary_banner(lab, analyses, live),
        _overview(lab, analyses, walk, policy, live),
        _report_availability(lab),
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
) -> str:
    replay_modes = sorted({str(row.get("evidence_mode") or "unknown") for row in analyses})
    badges = [
        badge("Production policy unchanged", tone="info", icon="shield"),
        badge("Shadow only", tone="neutral"),
        badge("No automatic application", tone="positive"),
        badge(lab.get("status") or "unavailable", tone=_status_tone(lab.get("status"))),
    ]
    if live:
        badges.append(badge("Live no-send", tone="info", icon="data"))
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
    analyses: list[Mapping[str, Any]],
    walk: Mapping[str, Any],
    policy: Mapping[str, Any],
    live: Mapping[str, Any],
) -> str:
    replay_episodes = sum(_count(row.get("episode_count")) for row in analyses)
    replay_matured = sum(_count(row.get("matured_episode_count")) for row in analyses)
    live_episodes = _count(_mapping(live.get("episodes")).get("primary_episode_count"))
    live_matured = _count(_mapping(live.get("scorecard")).get("matured_episode_count"))
    recommendation_rows = _mapping_rows(policy.get("recommendations"))
    candidate_count = sum(str(row.get("status") or "") == "candidate" for row in recommendation_rows)
    return render_metric_grid((
        ("Research reports", str(sum(_report_ready(lab, key) for key in ("validation", "walk_forward", "policy", "live_campaign"))) + "/4", "info"),
        ("Replay episodes", str(replay_episodes), "neutral"),
        ("Replay matured", str(replay_matured), "neutral"),
        ("Live no-send episodes", str(live_episodes), "neutral"),
        ("Live matured", str(live_matured), "neutral"),
        ("Nonempty walk-forward folds", display_count(walk.get("nonempty_fold_count")), "neutral"),
        ("Shadow candidates", str(candidate_count), "warning" if candidate_count else "neutral"),
        ("Production changes", "0", "positive"),
    ))


def _report_availability(lab: Mapping[str, Any]) -> str:
    reports = _mapping(lab.get("reports"))
    rows = []
    labels = {
        "validation": "Empirical validation",
        "walk_forward": "Walk-forward",
        "policy": "Shadow policy",
        "live_campaign": "Live campaign",
    }
    for key, label in labels.items():
        record = _mapping(reports.get(key))
        digest = str(record.get("sha256") or "")
        rows.append((
            label,
            badge(record.get("status") or "not configured", tone=_status_tone(record.get("status"))),
            display_count(record.get("size_bytes")),
            digest[:12] + "…" if digest else "Not available",
            str(record.get("filename") or ""),
        ))
    body = data_table(
        ("Report", "State", "Bytes", "SHA-256", "Fixed source"),
        rows,
        caption="Fixed Research Lab report inventory",
        compact=True,
    )
    return render_panel("Research evidence inventory", str(body), eyebrow="Bounded fixed-path reads")


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
        ("Evidence", "Cohort", "Episodes", "Matured", "Mean directional", "Hit rate", "MFE", "MAE", "Strength"),
        rows,
        caption=title,
        empty="The empirical validation report is absent or invalid. No zero counts are inferred from missing evidence.",
        compact=True,
    )
    body = f"<p>{escape_html(description)}</p>{table}"
    return render_panel(title, body, eyebrow="Descriptive cohorts")


def _cohort_table_row(partition: str, name: str, row: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        partition,
        humanize_enum(name),
        display_count(row.get("episode_count")),
        display_count(row.get("matured_episode_count")),
        _percent(row.get("mean_directional_return_fraction")),
        _percent(row.get("hit_rate")),
        _percent(row.get("mean_mfe_fraction")),
        _percent(row.get("mean_mae_fraction")),
        badge(row.get("sample_status") or "not reported", tone=_evidence_tone(row.get("sample_status"))),
    )


def _monotonicity_panel(analyses: list[Mapping[str, Any]]) -> str:
    rows = []
    details: list[str] = []
    for analysis in analyses:
        partition = _partition_label(analysis)
        for item in _mapping_rows(analysis.get("score_monotonicity")):
            rows.append((
                partition,
                humanize_enum(item.get("score_field")),
                humanize_enum(item.get("expected_relationship")),
                display_count(item.get("comparable_pair_count")),
                display_count(item.get("violation_count")),
                badge(
                    "No observed violation" if _count(item.get("violation_count")) == 0 else "Descriptive violation",
                    tone="positive" if _count(item.get("violation_count")) == 0 else "warning",
                ),
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
        ("Evidence", "Score", "Frozen expectation", "Comparable pairs", "Violations", "Observed state"),
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
                    display_count(row.get("sample_size")),
                    _percent(row.get("mean_directional_return_fraction")),
                    _percent(row.get("hit_rate")),
                    badge(row.get("sample_status") or "not reported", tone=_evidence_tone(row.get("sample_status"))),
                ))
    table = data_table(
        ("Evidence", "Dimension", "Cohort", "Episodes", "Scoreable", "Mean directional", "Hit rate", "Strength"),
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
        ("Evidence", "Market / catalyst cohort", "Episodes", "Matured", "Mean directional", "Hit rate", "MFE", "MAE", "Strength"),
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
        missed = _mapping_rows(analysis.get("missed_opportunity_classifications"))
        false_late = _mapping_rows(analysis.get("false_positive_and_late_classifications"))
        for row in missed:
            if row.get("qualifies") is True:
                missed_reasons.update(str(value) for value in _list(row.get("reason_codes")))
        for row in false_late:
            symptoms.update(str(value) for value in _list(row.get("symptom_codes")))
        rows.append((
            _partition_label(analysis),
            str(sum(row.get("qualifies") is True for row in missed)),
            str(sum(row.get("false_positive") is True for row in false_late)),
            str(sum(row.get("late_idea") is True for row in false_late)),
            str(sum(str(row.get("classification_status")) == "evaluated" for row in false_late)),
        ))
    summary = data_table(
        ("Evidence", "Missed", "False positive", "Late", "Evaluated"),
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
        "Missed, false-positive & late ideas",
        str(summary) + str(disclosure("Classification detail", detail, summary="Frozen descriptive rules")),
        eyebrow="Error analysis",
    )


def _path_and_cost_panel(analyses: list[Mapping[str, Any]]) -> str:
    path_rows = []
    cost_rows = []
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
    paths = data_table(
        ("Evidence", "Route", "Sample", "Mean MFE", "Mean MAE", "MFE / MAE", "Downside 5%"),
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
    return render_panel(
        "MFE, MAE & assumed costs",
        str(paths) + str(disclosure("Cost scenarios", costs, summary="Historical spread not inferred")),
        eyebrow="Path outcomes",
    )


def _walk_forward_panel(walk: Mapping[str, Any]) -> str:
    folds = _mapping_rows(walk.get("folds"))
    rows = []
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
    table = data_table(
        ("Fold", "Train window", "Test window", "Train N", "Test N", "Selected shadow", "Test mean", "Test hit", "Strength"),
        rows,
        caption="Chronological rolling train/test folds",
        empty="Walk-forward evidence is absent or has no folds.",
        compact=True,
    )
    status = badge(walk.get("status") or "unavailable", tone=_evidence_tone(walk.get("status")))
    guard = badge(
        "Final test untouched" if walk and walk.get("final_test_accessed") is not True else "Final-test firewall unavailable",
        tone="positive" if walk and walk.get("final_test_accessed") is not True else "warning",
        icon="shield",
    )
    header = f'<div class="badge-row">{status}{guard}</div>' if walk else ""
    return render_panel("Chronological walk-forward", header + str(table), eyebrow="Out-of-window stability")


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
            burden_rows.append((
                _partition_label(analysis),
                display_count(burden.get("episode_count")),
                display_count(burden.get("observed_day_count")),
                display_count(burden.get("family_count")),
                _decimal(burden.get("mean_ideas_per_observed_day")),
                str(sum(_count(row.get("urgent_item_count")) for row in _mapping_rows(burden.get("daily")))),
                str(sum(_count(row.get("repeated_family_item_count")) for row in _mapping_rows(burden.get("daily")))),
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
        ("Evidence", "Ideas", "Observed days", "Families", "Ideas / day", "Urgent", "Repeated family"),
        burden_rows,
        empty="No operator-burden summary is available.",
        compact=True,
    )
    body = (
        '<div class="badge-row">'
        + str(badge("Production policy unchanged", tone="info", icon="shield"))
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
    for analysis in analyses:
        rows.append((
            "Replay / fixture",
            _partition_label(analysis),
            display_count(analysis.get("episode_count")),
            display_count(analysis.get("matured_episode_count")),
            humanize_enum(_analysis_strength(analysis)),
            "No",
            "Separated evidence mode",
        ))
    if live:
        episodes = _mapping(live.get("episodes"))
        scorecard = _mapping(live.get("scorecard"))
        rows.append((
            "Live no-send",
            humanize_enum(live.get("campaign_status")),
            display_count(episodes.get("primary_episode_count")),
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
    controls = _mapping(validation.get("controls_and_benchmarks"))
    controls_body = _generic_summary(controls, "No matched-control or benchmark summary is available.")
    return render_panel(
        "Live no-send vs replay",
        str(table) + str(disclosure("Controls & benchmarks", controls_body, summary="No causal claim")),
        eyebrow="Evidence separation",
    )


def _warnings_panel(
    lab: Mapping[str, Any],
    validation: Mapping[str, Any],
    analyses: list[Mapping[str, Any]],
    policy: Mapping[str, Any],
    live: Mapping[str, Any],
) -> str:
    warnings = [str(value) for value in _list(lab.get("warnings")) if str(value)]
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
    limitations = _generic_summary(
        validation.get("limitations"),
        "No validation limitations report is available.",
    )
    live_limitations = _generic_summary(
        live.get("limitations"),
        "No live-campaign limitations report is available.",
    )
    conclusions = _generic_summary(
        validation.get("conclusions"),
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


def _projection(lab: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    record = _mapping(_mapping(lab.get("reports")).get(key))
    if record.get("status") != "ready":
        return {}
    return _mapping(record.get("projection"))


def _report_ready(lab: Mapping[str, Any], key: str) -> int:
    return int(_mapping(_mapping(lab.get("reports")).get(key)).get("status") == "ready")


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
