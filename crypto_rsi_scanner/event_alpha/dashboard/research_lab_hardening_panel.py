"""Server-rendered operator panel for the empirical hardening supplement."""

from __future__ import annotations

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
from .presentation import humanize_enum
from .system_page_support import display_count, render_metric_grid, render_panel


def render_hardening_conclusion_panel(lab: Mapping[str, Any]) -> str:
    supplement = _mapping(lab.get("hardening_supplement"))
    summary = _mapping(supplement.get("projection"))
    if supplement.get("status") != "ready" or not summary:
        return _hardening_unavailable_panel(supplement)
    negative = (
        summary.get("negative_conclusion") is True
        and summary.get("production_policy_unchanged") is True
    )
    unsupported = _count(summary.get("unsupported_shadow_alternative_count"))
    alternatives = _count(summary.get("shadow_alternative_count"))
    monotonicity = _count(summary.get("score_monotonicity_violation_count"))
    maximum_urgent = _count(summary.get("maximum_urgent_items_on_one_day"))
    regime = str(summary.get("regime_dependence") or "not_evaluable")
    live = _mapping(summary.get("live_status"))
    aggregate = _mapping(summary.get("current_policy_aggregate"))
    routes = _mapping(summary.get("route_level_result"))
    headline = (
        "No supported production policy change"
        if negative
        else "Empirical result requires human review"
    )
    badges_html = (
        str(
            badge(
                "Production policy unchanged" if negative else "No automatic change",
                tone="info",
                icon="shield",
            )
        )
        + str(badge("Descriptive supplement", tone="neutral"))
        + str(
            badge(
                "sealed_v1_final_test_summary",
                label="Sealed v1 final-test summary only",
                tone="neutral",
            )
        )
    )
    if live.get("evidence_strength") == "insufficient_sample":
        badges_html += str(badge("Live evidence insufficient", tone="warning"))
    alternative_copy = (
        f"{unsupported} unsupported shadow alternatives"
        if alternatives and unsupported == alternatives
        else f"{unsupported} of {alternatives} shadow alternatives unsupported"
    )
    metrics = render_metric_grid((
        ("Shadow alternatives", alternative_copy, "neutral"),
        ("Monotonicity", f"{monotonicity} descriptive violations", "warning"),
        ("Peak urgent burden", f"{maximum_urgent} items in one day", "warning"),
        (
            "Matured visible episodes",
            display_count(aggregate.get("matured_visible_episode_count")),
            "neutral",
        ),
        (
            "Current policy mean",
            _percent(aggregate.get("mean_directional_return_fraction")),
            "neutral",
        ),
        (
            "Current policy hit rate",
            _percent(aggregate.get("hit_rate")),
            "neutral",
        ),
        (
            "Quick-failure rate",
            _percent(aggregate.get("quick_failure_rate")),
            "warning",
        ),
    ))
    (
        route_table,
        interpretation,
        route_gaps,
        origin_gaps,
        missing_data,
        route_conditioned,
        market_wide_risk,
        frozen_costs,
    ) = _operator_evidence_blocks(summary, routes, live, regime)
    body = (
        '<div class="badge-row">'
        + badges_html
        + "</div>"
        + f"<p><strong>{escape_html(headline)}.</strong> "
        + "The hardened readout preserves the negative result and does not authorize threshold, route, or execution changes.</p>"
        + "<p>The final-test column is copied from the already-sealed Protocol-v1 report summary for display only. The supplement did not access raw final-test data and did not use the holdout for scenario selection.</p>"
        + metrics
        + str(route_table)
        + str(interpretation)
        + "<p><strong>Routes with no empirical evidence</strong></p>"
        + str(chips(route_gaps, humanize=False))
        + "<p><strong>Origins with no empirical evidence</strong></p>"
        + str(chips(origin_gaps, humanize=False))
        + "<p><strong>Missing data most needed</strong></p>"
        + str(chips(missing_data, humanize=False))
        + str(disclosure(
            "Within-route score diagnostics",
            route_conditioned,
            summary="Development and validation only · closed 16-route matrix",
            open=True,
        ))
        + str(disclosure(
            "Outcome-blind market-wide risk grouping",
            market_wide_risk,
            summary="Development and validation only · no policy change",
        ))
        + str(disclosure(
            "Frozen cost sensitivity",
            frozen_costs,
            summary="0 / 20 / 50 / 100 / 200 bps · sealed final display-only",
        ))
    )
    return render_panel(
        "Operator conclusion",
        body,
        eyebrow="Negative conclusion · no production change",
    )


def _operator_evidence_blocks(
    summary: Mapping[str, Any],
    routes: Mapping[str, Any],
    live: Mapping[str, Any],
    regime: str,
) -> tuple[Any, ...]:
    route_rows = []
    for route in ("risk_watch", "dashboard_watch"):
        route_value = _mapping(routes.get(route))
        partitions = _mapping(route_value.get("partitions"))
        route_rows.append((
            humanize_enum(route),
            humanize_enum(route_value.get("evidence_status") or "unavailable"),
            display_count(route_value.get("matured_episode_count")),
            _route_partition_result(partitions, "development"),
            _route_partition_result(partitions, "validation"),
            _route_partition_result(partitions, "final_test"),
        ))
    route_table = data_table(
        ("Route", "Evidence", "Matured", "Development", "Validation", "Final test"),
        route_rows,
        caption="Route-level descriptive result",
        compact=True,
    )
    cost_copy = (
        "Historical spread not observed; costs are assumed sensitivity, not execution evidence"
        if summary.get("historical_spread_observed") is not True
        else "Historical spread evidence observed"
    )
    interpretation = definition_list((
        ("Regime dependence", humanize_enum(regime)),
        ("Cost evidence", cost_copy),
        (
            "Live lane",
            f"{humanize_enum(live.get('evidence_strength') or 'unavailable')} · "
            f"{humanize_enum(live.get('policy_conclusion') or 'unavailable')} · "
            "not pooled with replay"
            if live.get("evidence_pooled_with_replay") is not True
            else "pooled status requires review",
        ),
        (
            "Final confirmation",
            humanize_enum(summary.get("final_confirmation_status") or "unavailable"),
        ),
    ))
    route_gaps = [
        humanize_enum(item)
        for item in _list(summary.get("routes_with_no_empirical_evidence"))
    ]
    origin_gaps = [
        humanize_enum(item)
        for item in _list(summary.get("origins_with_no_empirical_evidence"))
    ]
    return (
        route_table,
        interpretation,
        route_gaps,
        origin_gaps,
        [str(item) for item in _list(summary.get("missing_data"))],
        _route_conditioned_diagnostics(
            _mapping(summary.get("route_conditioned_calibration"))
        ),
        _market_wide_risk_diagnostics(
            _mapping(summary.get("market_wide_risk_diagnostics"))
        ),
        _frozen_cost_sensitivity(
            _mapping(summary.get("frozen_cost_sensitivity"))
        ),
    )
def _hardening_unavailable_panel(supplement: Mapping[str, Any]) -> str:
    status = str(supplement.get("status") or "unavailable")
    warnings = [str(item) for item in _list(supplement.get("warnings")) if str(item)]
    record = _mapping(supplement.get("record"))
    body = (
        '<div class="badge-row">'
        + str(badge(status, tone=_status_tone(status), icon="warning"))
        + str(badge("Seven-file v1 evidence remains available", tone="info"))
        + "</div>"
        + str(empty_state(
            "Hardening supplement unavailable",
            "The optional bounded supplement is missing or invalid, so route-conditioned and market-wide diagnostics are suppressed. The validated seven-file Protocol-v1 bundle remains unchanged and is not interpreted as failed evidence.",
        ))
        + str(definition_list((
            ("Fixed source", str(record.get("filename") or "Not configured")),
            ("Read state", humanize_enum(status)),
        )))
    )
    if warnings:
        body += str(chips(warnings, humanize=False))
    return render_panel(
        "Empirical hardening supplement",
        body,
        eyebrow="Optional diagnostics unavailable · fail soft",
    )


def _route_conditioned_diagnostics(value: Mapping[str, Any]) -> HtmlFragment:
    rows = _mapping_rows(value.get("rows"))
    summary_rows = []
    score_rows = []
    for row in rows:
        score_counts = _mapping(row.get("score_counts"))
        summary_rows.append((
            humanize_enum(row.get("partition")),
            humanize_enum(row.get("route")),
            display_count(row.get("episode_count")),
            display_count(row.get("matured_episode_count")),
            display_count(row.get("evaluated_pair_count")),
            display_count(row.get("violation_count")),
        ))
        if row.get("route") in {"dashboard_watch", "risk_watch"}:
            for score_field, counts_value in score_counts.items():
                counts = _mapping(counts_value)
                score_rows.append((
                    humanize_enum(row.get("partition")),
                    humanize_enum(row.get("route")),
                    humanize_enum(score_field),
                    display_count(counts.get("evaluated_pair_count")),
                    display_count(counts.get("violation_count")),
                ))
    closed_table = data_table(
        (
            "Evidence",
            "Route",
            "Episodes",
            "Matured",
            "Evaluated adjacent pairs",
            "Violations",
        ),
        summary_rows,
        caption="Closed development / validation within-route diagnostics",
        empty="No route-conditioned diagnostic rows are available.",
        compact=True,
    )
    focus_table = data_table(
        ("Evidence", "Route", "Score", "Evaluated adjacent pairs", "Violations"),
        score_rows,
        caption="Dashboard-watch and risk-watch score detail",
        empty="No dashboard-watch or risk-watch score detail is available.",
        compact=True,
    )
    return HtmlFragment(
        '<p><strong>The older global mixed-route monotonicity result is confounded by route composition.</strong> '
        "These checks compare score buckets only within one route and remain descriptive; zero evaluated pairs means not evaluable, not no violation.</p>"
        + str(closed_table)
        + str(disclosure(
            "Dashboard-watch and risk-watch score fields",
            focus_table,
            summary="Five frozen score fields per partition",
        ))
    )


def _market_wide_risk_diagnostics(value: Mapping[str, Any]) -> HtmlFragment:
    peak = _mapping(value.get("peak_group"))
    top_assets = [str(item) for item in _list(peak.get("top_assets")) if str(item)]
    metrics = render_metric_grid((
        ("Risk items", _grouped_count(value.get("risk_item_count")), "neutral"),
        ("Partition-days", _grouped_count(value.get("partition_day_count")), "neutral"),
        ("Market-wide groups", _grouped_count(value.get("market_wide_group_count")), "warning"),
        ("Minimum distinct assets", _grouped_count(value.get("minimum_distinct_assets")), "neutral"),
    ))
    suppression = humanize_enum(
        value.get("correlated_family_suppression_status") or "not_evaluable"
    )
    body = (
        "<p>Groups are formed by exact UTC day from development and validation risk-watch items without reading outcomes. They are descriptive operator-load evidence, not causal or directional signals.</p>"
        + metrics
        + str(definition_list((
            ("Peak UTC day", str(peak.get("utc_day") or "Not available")),
            ("Peak risk items", display_count(peak.get("risk_item_count"))),
            ("Peak distinct assets", display_count(peak.get("distinct_asset_count"))),
            ("Peak partition", str(peak.get("partition") or "Not available")),
            ("Correlated-family suppression", suppression),
        )))
        + "<p><strong>Peak group · bounded top assets</strong></p>"
        + str(chips(top_assets, humanize=False))
    )
    if value.get("correlated_family_suppression_applied") is not True:
        body += (
            "<p>Correlated-family suppression is not evaluable because correlation and family-lineage evidence are missing; no suppression was applied.</p>"
        )
    return HtmlFragment(body)


def _frozen_cost_sensitivity(value: Mapping[str, Any]) -> HtmlFragment:
    rows = []
    for partition in _mapping_rows(value.get("partitions")):
        partition_label = humanize_enum(partition.get("partition"))
        if partition.get("sealed_final_display_only") is True:
            partition_label += " · sealed display only"
        for scenario in _mapping_rows(partition.get("scenarios")):
            rows.append((
                partition_label,
                display_count(scenario.get("round_trip_cost_bps")) + " bps",
                _percent(scenario.get("mean_net_directional_return_fraction")),
                _percent(scenario.get("net_hit_rate")),
            ))
    table = data_table(
        ("Evidence", "Assumed round trip", "Mean net", "Net hit rate"),
        rows,
        caption="Exact frozen Protocol-v1 cost sensitivity",
        empty="No frozen cost-sensitivity rows are available.",
        compact=True,
    )
    return HtmlFragment(
        '<div class="badge-row">'
        + str(badge("Assumed sensitivity", tone="info"))
        + str(badge("Not execution evidence", tone="warning"))
        + str(badge("Sealed final is display-only", tone="neutral"))
        + "</div>"
        + "<p>The final-test rows are copied from the already-validated sealed v1 report. They were not used to select scenarios or tune policy.</p>"
        + str(table)
    )


def _route_partition_result(
    partitions: Mapping[str, Any],
    partition: str,
) -> str:
    row = _mapping(partitions.get(partition))
    if not row:
        return "Not available"
    return (
        f"{humanize_enum(row.get('result_direction') or 'not_evaluable')} · "
        f"n={display_count(row.get('sample_size'))}"
    )

def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    return [
        row for row in value if isinstance(row, Mapping)
    ] if isinstance(value, list) else []


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _count(value: Any) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else 0
    )


def _grouped_count(value: Any) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return "Not available"
    return f"{value:,}"


def _percent(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Not available"
    return f"{float(value) * 100:.2f}%"


def _status_tone(value: Any) -> str:
    token = str(value or "").casefold()
    if token == "ready":
        return "positive"
    if token in {"partial", "missing", "not_configured"}:
        return "warning"
    return "danger" if token else "muted"


__all__ = ("render_hardening_conclusion_panel",)
