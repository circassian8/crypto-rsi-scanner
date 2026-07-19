"""Decision Radar Today / command-center page."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from ..radar import market_units as event_market_units
from .calendar_page import calendar_temporal_state
from .components import escape_html
from .ideas_page import (
    render_attention_cards,
    render_idea_cards,
    render_idea_comparison,
    render_idea_filters,
)
from .layer_coverage import (
    DashboardLayerCoverage,
    dashboard_layer_coverage,
    dashboard_layer_coverage_by_key,
)
from .maintenance_guidance import maintenance_expiry_guidance
from .models import DashboardSnapshot
from .operator_work_queue import operator_work_actions, render_operator_work_queue
from .presentation import (
    UNAVAILABLE,
    format_duration,
    format_percent,
    humanize_enum,
    humanize_reason,
    operator_route_label,
    present_calendar_window,
    present_time,
    semantic_status,
)
from .presentation_models.outcome_state import project_outcome_state
from .view_data import filter_sort_candidates, filter_sort_observations


_ATTENTION_LANES = (
    ("high_confidence_watch", "High-confidence ideas", "Highest combined actionability and explanatory support."),
    ("actionable_watch", "Actionable research", "Timely, tradable research for a human decision."),
    ("rapid_market_anomaly", "Rapid market anomalies", "Urgent market-led dislocations; cause may still be unknown."),
    ("dashboard_watch", "Dashboard watch", "Useful context that has not met the actionable route contract."),
    ("fade_exhaustion_review", "Fade / exhaustion review", "Manual review only; never creates triggered-fade state."),
    ("risk_watch", "Risk watches", "Elevated risk or suspicious conditions that deserve attention."),
    ("calendar_risk", "Calendar / scheduled risk", "Ideas constrained by a nearby scheduled event."),
)

_COVERAGE_HREFS = {
    "market": "/market-radar",
    "catalyst": "/health#source-pack-coverage",
    "calendar": "/calendar",
    "derivatives": "/health#provider-readiness",
    "rsi": "/health#product-layer-coverage",
    "outcomes": "/outcomes",
    "request_ledger": "/health#provider-request",
}

_OPTIONAL_CONTEXT_LAYERS = frozenset({"catalyst", "calendar", "derivatives", "rsi"})
_Constraint = tuple[str, str, str, str]


def render_today_page(
    snapshot: DashboardSnapshot,
    *,
    query: Mapping[str, str] | None = None,
    include_diagnostics: bool = False,
) -> str:
    source_rows = (
        (*snapshot.visible_current_candidates, *snapshot.diagnostic_candidates)
        if include_diagnostics
        else snapshot.visible_current_candidates
    )
    visible = tuple(filter_sort_candidates(source_rows, query))
    review_rows = tuple(
        row for row in visible
        if str(row.get("_dashboard_route") or row.get("radar_route")) != "diagnostic"
    )
    intro, metric_summary, active_calendar_events = _today_summary(
        snapshot,
        review_rows,
    )
    warnings = _operator_warnings(snapshot)
    maintenance_action = _maintenance_expiry_action(snapshot)
    attention = _attention_sections(
        review_rows,
        active_calendar_events=active_calendar_events,
        clock=snapshot.generation_authority_checked_at,
    )
    comparison = render_idea_comparison(
        visible,
        now=snapshot.generation_authority_checked_at,
    )
    controls = (
        '<details class="disclosure filter-disclosure"'
        + (" open" if query else "")
        + '><summary>Filter and compare current ideas</summary><div class="disclosure__body">'
        + render_idea_filters(dict(query or {}), action="/")
        + comparison
        + '</div></details>'
    )
    diagnostics = (
        _diagnostic_review(
            visible,
            now=snapshot.generation_authority_checked_at,
        )
        if include_diagnostics
        else ""
    )
    expired = _expired_ideas(
        snapshot,
        query,
        include_diagnostics=include_diagnostics,
    )
    return (
        intro
        + attention
        + metric_summary
        + render_operator_work_queue(snapshot)
        + maintenance_action
        + warnings
        + controls
        + diagnostics
        + expired
        + '<div class="two-column">'
        + _market_snapshot(snapshot)
        + _calendar_snapshot(snapshot)
        + _campaign_snapshot(snapshot)
        + _change_summary(snapshot)
        + '</div>'
    )


def _today_summary(
    snapshot: DashboardSnapshot,
    review_rows: tuple[Mapping[str, Any], ...],
) -> tuple[str, str, tuple[Mapping[str, Any], ...]]:
    observations = snapshot.current_market_observations
    coverage_by_key = dashboard_layer_coverage_by_key(snapshot)
    market_metric = _layer_metric(
        snapshot,
        coverage_by_key["market"],
        count=len(observations),
        healthy_detail="Exact market observations",
    )
    calendar_metric = _layer_metric(
        snapshot,
        coverage_by_key["calendar"],
        count=len(_current_calendar_events(snapshot)),
        healthy_detail="Active + upcoming exact rows",
    )
    current_calendar_events = _current_calendar_events(snapshot)
    active_calendar_events = tuple(
        row
        for row in current_calendar_events
        if calendar_temporal_state(
            row,
            clock=snapshot.generation_authority_checked_at,
        ) == "active"
    )
    pending = sum(
        1 for row in snapshot.current_outcomes
        if project_outcome_state(row)[1] == "pending"
    )
    outcome_metric = _outcome_metric(
        snapshot,
        coverage_by_key["outcomes"],
        pending=pending,
    )
    trusted_value: object = len(review_rows) if snapshot.generation_authoritative else "Suppressed"
    anomaly_value: object = (
        len(snapshot.current_market_anomalies)
        if snapshot.generation_authoritative
        else "Suppressed"
    )
    metrics = (
        ("Decision ideas", trusted_value, "Current idea queue"),
        ("Assets evaluated", *market_metric),
        ("Anomaly evidence", anomaly_value, "Exact scanner rows"),
        ("Scheduled risk", *calendar_metric),
        ("Pending outcomes", *outcome_metric),
    )
    headline = (
        "No immediate Decision idea qualified"
        if not review_rows and observations
        else "No trusted current research is available"
        if not snapshot.generation_authoritative
        else "What deserves attention now"
    )
    intro_detail = (
        f"The scan evaluated {len(observations)} assets. A zero-idea result is valid and does not mean "
        "the provider or dashboard failed. Review the constraints and market table below."
        if not review_rows and observations
        else "Prioritized Decision v2 research, scheduled risk, and system constraints from one exact generation."
    )
    attention_noun = _attention_noun(review_rows)
    hero_actions = _hero_actions(
        visible_count=len(review_rows),
        visible_noun=attention_noun,
        active_event_count=len(active_calendar_events),
        generation_authoritative=snapshot.generation_authoritative,
    )
    if review_rows:
        pulse_value = len(review_rows)
        pulse_label = attention_noun
    elif active_calendar_events:
        pulse_value = len(active_calendar_events)
        pulse_label = f"active {'risk' if pulse_value == 1 else 'risks'}"
    else:
        pulse_value = 0
        pulse_label = "ideas now"
    intro = (
        '<section class="command-hero"><div><p class="eyebrow">Today · command center</p>'
        f'<h2>{escape_html(headline)}</h2><p>{escape_html(intro_detail)}</p>'
        f'{hero_actions}</div>'
        f'<div class="hero-pulse"><span>{pulse_value}</span><small>{escape_html(pulse_label)}</small></div></section>'
    )
    metric_summary = (
        '<div class="today-metrics" role="region" aria-label="Current generation summary">'
        '<div class="metric-grid">' + "".join(_metric(*item) for item in metrics) + '</div></div>'
    )
    return intro, metric_summary, active_calendar_events


def _maintenance_expiry_action(snapshot: DashboardSnapshot) -> str:
    guidance = maintenance_expiry_guidance(snapshot)
    if guidance.get("active") is not True:
        return ""
    remaining = format_duration(guidance.get("time_until_expiry_seconds"))
    readiness = str(guidance.get("safe_manual_readiness_command") or "")
    install = str(guidance.get("installation_command") or "")
    return (
        '<section class="alert alert-warning maintenance-expiry-action">'
        '<div class="alert-icon" aria-hidden="true">!</div><div>'
        '<h2>Freshness check due soon</h2>'
        f'<p>Current authority expires in approximately {escape_html(remaining)}. '
        'Daily maintenance is disabled, so review readiness manually; this command '
        'does not call a provider.</p>'
        f'<p><code>{escape_html(readiness)}</code></p>'
        '<details class="disclosure"><summary>Optional scheduler installation</summary>'
        '<div class="disclosure__body"><p>Installation changes recurring local state '
        'and requires explicit confirmation. It does not authorize a provider.</p>'
        f'<p><code>{escape_html(install)}</code></p></div></details>'
        '</div></section>'
    )


def _diagnostic_review(
    rows: tuple[Mapping[str, Any], ...],
    *,
    now: object = None,
) -> str:
    diagnostics = tuple(
        row
        for row in rows
        if str(row.get("_dashboard_route") or row.get("radar_route")) == "diagnostic"
    )
    if not diagnostics:
        return ""
    return (
        '<details class="disclosure panel diagnostic-review"><summary><span>'
        'Diagnostic controls</span>'
        f'<span class="filter-chip">{len(diagnostics)} retained</span></summary>'
        '<div class="disclosure__body"><p>Diagnostic rows are retained for model review and '
        'never enter the current attention queue.</p>'
        + render_idea_cards(
            diagnostics,
            now=now,
        )
        + '</div></details>'
    )


def _hero_actions(
    *,
    visible_count: int,
    visible_noun: str,
    active_event_count: int,
    generation_authoritative: bool,
) -> str:
    if generation_authoritative and visible_count:
        primary = (f"Review {visible_count} {visible_noun}", "/ideas")
        secondary = ("Open Market Radar", "/market-radar")
    elif generation_authoritative and active_event_count:
        event_word = "event" if active_event_count == 1 else "events"
        primary = (
            f"Review {active_event_count} active {event_word}",
            "/calendar?time=active",
        )
        secondary = ("Open Market Radar", "/market-radar")
    elif generation_authoritative:
        primary = ("Open Market Radar", "/market-radar")
        secondary = ("Review system state", "/health")
    else:
        primary = ("Review system state", "/health")
        secondary = None
    actions = (
        '<div class="hero-actions">'
        f'<a class="button button-primary" href="{escape_html(primary[1])}">'
        f'{escape_html(primary[0])}</a>'
    )
    if secondary is not None:
        actions += (
            f'<a class="button button-quiet" href="{escape_html(secondary[1])}">'
            f'{escape_html(secondary[0])}</a>'
        )
    return actions + "</div>"


def _attention_noun(rows: tuple[Mapping[str, Any], ...]) -> str:
    """Name a single specialist route without overstating it as a generic idea."""

    if len(rows) != 1:
        return "ideas"
    route = str(rows[0].get("_dashboard_route") or rows[0].get("radar_route") or "")
    return operator_route_label(route, fallback="idea").casefold()


def _expired_ideas(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
    *,
    include_diagnostics: bool,
) -> str:
    source_rows = (
        (
            *snapshot.expired_visible_current_candidates,
            *snapshot.expired_diagnostic_candidates,
        )
        if include_diagnostics
        else snapshot.expired_visible_current_candidates
    )
    rows = tuple(filter_sort_candidates(source_rows, query))
    if not rows:
        return ""
    return (
        '<details class="disclosure panel expired-ideas"><summary><span>'
        'Expired ideas (not currently actionable)</span>'
        f'<span class="filter-chip">{len(rows)} retained</span></summary>'
        '<div class="disclosure__body"><p><strong>Expired; current actionability suppressed.</strong> '
        'Canonical research history is preserved, but these rows cannot be presented as actionable '
        'at or after their recorded expiry.</p>'
        + render_idea_cards(
            rows,
            now=snapshot.generation_authority_checked_at,
        )
        + '</div></details>'
    )


def _operator_warnings(snapshot: DashboardSnapshot) -> str:
    rows = snapshot.current_market_observations
    quality_rows = [_quality(row) for row in rows]
    spread = sum(1 for row, quality in zip(rows, quality_rows, strict=True) if (
        quality.get("spread_available") is True
        or str(row.get("spread_status") or "").casefold() in {"verified", "verified_good", "verified_acceptable"}
    ))
    warm = sum(1 for quality in quality_rows if str(quality.get("baseline_status") or "").casefold() == "warm")
    system_failures: list[_Constraint] = []
    decision_blockers: list[_Constraint] = []
    required_coverage_gaps: list[_Constraint] = []
    optional_coverage_gaps: list[_Constraint] = []
    coverage = dashboard_layer_coverage(snapshot)
    has_campaign_execution_action = any(
        title.startswith("Bybit USDT-perpetual spread evidence")
        for _category, title, _detail, _command, _link_label, _href in operator_work_actions(
            snapshot
        )
    )
    for layer in coverage:
        if not layer.action_required:
            continue
        item = (
            f"coverage:{layer.key}",
            _coverage_warning_title(layer),
            layer.detail,
            _COVERAGE_HREFS[layer.key],
        )
        target = (
            optional_coverage_gaps
            if layer.key in _OPTIONAL_CONTEXT_LAYERS
            else required_coverage_gaps
        )
        target.append(item)
    if rows and not spread and not has_campaign_execution_action:
        decision_blockers.append((
            "decision:spread",
            "Execution spread unavailable",
            f"Spread is unverified for all {len(rows)} assets. Liquid ideas can remain visible as watch items, but actionable routes stay capped.",
            "/market-radar?spread=unavailable",
        ))
    if rows and not warm:
        decision_blockers.append((
            "decision:baseline",
            "Temporal baseline still warming",
            _temporal_baseline_constraint_detail(snapshot),
            "/campaign-history",
        ))
    if snapshot.doctor_status.casefold() != "ok":
        system_failures.insert(0, (
            "system:doctor",
            "Integrity checks require attention",
            f"The exact run-integrity state is {humanize_enum(snapshot.doctor_status)}.",
            "/health#operator-action-summary",
        ))
    seen: set[str] = set()
    system_failures = _dedupe_constraints(system_failures, seen=seen)
    required_coverage_gaps = _dedupe_constraints(required_coverage_gaps, seen=seen)
    decision_blockers = _dedupe_constraints(decision_blockers, seen=seen)
    optional_coverage_gaps = _dedupe_constraints(optional_coverage_gaps, seen=seen)
    if not system_failures and not required_coverage_gaps and not decision_blockers and not optional_coverage_gaps:
        return '<section class="alert alert-positive"><div class="alert-icon" aria-hidden="true">✓</div><div><h2>No action-required system warnings</h2><p>Trust, run integrity, and every expected exact-generation product layer are healthy or explicitly not applicable.</p></div></section>'
    sections: list[str] = []
    if system_failures:
        sections.append(_constraint_panel(
            eyebrow="System integrity",
            title=_counted_label(len(system_failures), "system failure"),
            detail="These conditions affect exact-generation trust, acquisition, or required product evidence.",
            rows=system_failures,
        ))
    if required_coverage_gaps:
        sections.append(_constraint_panel(
            eyebrow="Required evidence coverage",
            title=_counted_label(len(required_coverage_gaps), "required coverage gap"),
            detail=(
                "These exact-generation product layers are expected but incomplete. "
                "They are coverage gaps, not automatically provider or system failures."
            ),
            rows=required_coverage_gaps,
        ))
    if decision_blockers:
        sections.append(_constraint_panel(
            eyebrow="Decision constraints",
            title=_counted_label(len(decision_blockers), "actionability constraint"),
            detail="These constraints cap current actionability without hiding the underlying research evidence.",
            rows=decision_blockers,
        ))
    if optional_coverage_gaps:
        if not system_failures and not required_coverage_gaps and not decision_blockers:
            sections.append(
                '<section class="alert alert-positive"><div class="alert-icon" aria-hidden="true">✓</div><div>'
                '<h2>No current system failure or actionability constraint</h2><p>Optional context remains incomplete; '
                'review it below without interpreting missing coverage as confirmed absence.</p></div></section>'
            )
        sections.append(_coverage_gap_disclosure(optional_coverage_gaps))
    return "".join(sections)


def _temporal_baseline_constraint_detail(snapshot: DashboardSnapshot) -> str:
    fallback = (
        "No asset has a globally warm feature baseline yet. Direct observations "
        "and cross-sectional proxies are labeled separately."
    )
    state = snapshot.campaign_operator_actions
    baseline = state.get("temporal_baseline")
    if state.get("status") != "ready" or not isinstance(baseline, Mapping):
        return fallback
    groups = baseline.get("feature_groups")
    if not isinstance(groups, Mapping):
        return fallback
    observed = _non_negative_int(baseline.get("observed_asset_count"))
    fully_warm = _non_negative_int(baseline.get("fully_warm_asset_count"))
    if observed is None or observed <= 0 or fully_warm is None:
        return fallback
    labels = (
        ("turnover", "turnover"),
        ("volume", "volume"),
        ("returns_1h", "1h returns"),
        ("returns_4h", "4h returns"),
        ("returns_24h", "24h returns"),
        ("btc_eth_relative", "BTC/ETH-relative"),
        ("volatility", "volatility"),
    )
    summaries: list[str] = []
    for key, label in labels:
        details = groups.get(key)
        if not isinstance(details, Mapping):
            return fallback
        warm = _non_negative_int(details.get("warm_asset_count"))
        asset_count = _non_negative_int(details.get("asset_count"))
        minimum_sample = _non_negative_int(details.get("minimum_sample_count"))
        maximum_sample = _non_negative_int(details.get("maximum_sample_count"))
        required_sample = _non_negative_int(details.get("required_sample_count"))
        coverage_deficit = _non_negative_int(
            details.get("coverage_deficit_asset_count")
        )
        if (
            warm is None
            or asset_count != observed
            or minimum_sample is None
            or maximum_sample is None
            or minimum_sample > maximum_sample
            or required_sample is None
            or required_sample <= 0
            or coverage_deficit is None
            or coverage_deficit > observed
        ):
            return fallback
        sample_range = (
            str(minimum_sample)
            if minimum_sample == maximum_sample
            else f"{minimum_sample}-{maximum_sample}"
        )
        summaries.append(
            f"{label} {warm}/{asset_count} ({sample_range}/{required_sample} samples"
            + (
                f"; {coverage_deficit} below elapsed coverage"
                if coverage_deficit
                else ""
            )
            + ")"
        )
    return (
        f"{fully_warm}/{observed} assets have fully warm retained-history baselines. "
        "Historical maturity by feature family: "
        + " · ".join(summaries)
        + ". These counts measure retained sample depth and elapsed coverage, not whether "
        "the latest cycle produced every point-in-time feature; current rows keep their "
        "own readiness state."
    )


def _dedupe_constraints(
    rows: list[_Constraint],
    *,
    seen: set[str],
) -> list[_Constraint]:
    deduped: list[_Constraint] = []
    for row in rows:
        key = row[0]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _constraint_panel(
    *,
    eyebrow: str,
    title: str,
    detail: str,
    rows: list[_Constraint],
) -> str:
    return (
        '<section class="panel warning-stack"><div class="section-heading"><div>'
        f'<p class="eyebrow">{escape_html(eyebrow)}</p><h2>{escape_html(title)}</h2>'
        f'<p>{escape_html(detail)}</p></div></div>{_constraint_rows(rows)}</section>'
    )


def _coverage_gap_disclosure(rows: list[_Constraint]) -> str:
    return (
        '<details class="disclosure coverage-gap-disclosure"><summary><span>Optional coverage gaps</span>'
        f'<span class="disclosure__summary">{escape_html(_counted_label(len(rows), "layer"))}</span>'
        '</summary><div class="disclosure__body"><p>These context layers can improve explanation or risk '
        'assessment, but their absence is not itself a provider failure or a universal visibility gate.</p>'
        f'{_constraint_rows(rows)}</div></details>'
    )


def _constraint_rows(rows: list[_Constraint]) -> str:
    return "".join(
        f'<a class="warning-row" href="{escape_html(href)}"><span aria-hidden="true">!</span>'
        f'<div><strong>{escape_html(title)}</strong><p>{escape_html(detail)}</p></div>'
        '<b aria-hidden="true">→</b></a>'
        for _key, title, detail, href in rows
    )


def _counted_label(count: int, singular: str) -> str:
    return f"{count} {singular if count == 1 else singular + 's'}"


def _coverage_warning_title(layer: DashboardLayerCoverage) -> str:
    if layer.key == "calendar" and layer.status == "not_configured":
        return "Calendar acquisition not configured"
    if layer.key == "request_ledger":
        return f"Provider request ledger {humanize_enum(layer.status).casefold()}"
    return f"{layer.label} {humanize_enum(layer.status).casefold()}"


def _attention_sections(
    rows: tuple[Mapping[str, Any], ...],
    *,
    active_calendar_events: tuple[Mapping[str, Any], ...],
    clock: str | None,
) -> str:
    sections = []
    for route, title, description in _ATTENTION_LANES:
        lane = tuple(row for row in rows if str(row.get("_dashboard_route") or row.get("radar_route")) == route)
        if not lane:
            continue
        sections.append(
            '<section class="attention-lane"><div class="section-heading"><div>'
            f'<p class="eyebrow">{escape_html(operator_route_label(route))}</p><h2>{escape_html(title)}</h2>'
            f'<p>{escape_html(description)}</p></div><span class="lane-count">{len(lane)}</span></div>'
            + render_attention_cards(lane, limit=4, now=clock)
            + (
                f'<p class="lane-overflow-link"><a href="/ideas?route={escape_html(route)}">View all {len(lane)} ideas in this lane</a></p>'
                if len(lane) > 4
                else ""
            )
            + '</section>'
        )
    if active_calendar_events:
        calendar_rows = "".join(
            _calendar_row(row, clock=clock)
            for row in active_calendar_events[:3]
        )
        sections.append(
            '<section class="attention-lane attention-lane--calendar"><div class="section-heading"><div>'
            '<p class="eyebrow">Calendar / scheduled risk</p><h2>Active scheduled risk</h2>'
            '<p>An exact-generation impact window is open now. Review timing and affected assets before relying on a current idea.</p>'
            f'</div><span class="lane-count">{len(active_calendar_events)}</span></div>'
            f'<div class="calendar-mini-list">{calendar_rows}</div></section>'
        )
    if not sections:
        return (
            '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Attention queue</p>'
            '<h2>No current idea needs review</h2></div></div><div class="empty-inline">The canonical '
            'Decision route count is zero. Market observations, coverage gaps, and campaign progress are still shown.</div></section>'
        )
    return ''.join(sections)


def _market_snapshot(snapshot: DashboardSnapshot) -> str:
    rows = filter_sort_observations(snapshot.current_market_observations, {"sort": "return_24h_desc"})[:5]
    if not rows:
        body = '<div class="empty-inline">No exact-generation market observations are attached.</div>'
    else:
        body = '<div class="mover-list">' + "".join(_mover_row(row) for row in rows) + '</div>'
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Market pulse</p>'
        '<h2>Largest 24h movers</h2></div><a href="/market-radar">All assets</a></div>'
        + body + '</section>'
    )


def _mover_row(row: Mapping[str, Any]) -> str:
    unit = event_market_units.return_unit_for_field(
        row,
        "return_24h",
        default=str(row.get("return_unit") or "percent_points"),
    )
    try:
        change = format_percent(row.get("return_24h"), unit=unit, decimals=2, signed=True)
    except ValueError:
        change = "Unavailable"
    number = row.get("return_24h")
    try:
        tone = "positive" if float(number) > 0 else "danger" if float(number) < 0 else "muted"
    except (TypeError, ValueError):
        tone = "muted"
    return (
        '<div class="mover-row"><div><strong>'
        f'{escape_html(row.get("symbol") or row.get("coin_id") or "Asset")}</strong>'
        f'<small>{escape_html(humanize_enum(_quality(row).get("baseline_status")))}</small></div>'
        f'<span class="tone-{tone}">{escape_html(change)}</span></div>'
    )


def _calendar_snapshot(snapshot: DashboardSnapshot) -> str:
    events = sorted(
        _current_calendar_events(snapshot),
        key=lambda row: str(row.get("scheduled_at") or row.get("window_start") or "~"),
    )[:4]
    if events:
        body = ''.join(
            _calendar_row(row, clock=snapshot.generation_authority_checked_at)
            for row in events
        )
    else:
        status = _calendar_status(snapshot)
        if snapshot.current_calendar_events:
            past_count = len(snapshot.current_calendar_events)
            body = (
                '<div class="empty-inline">No active or upcoming risk remains in this snapshot. '
                f'<a href="/calendar?time=past">Review {past_count} past '
                f'event{"s" if past_count != 1 else ""}</a>.</div>'
            )
        else:
            message = {
                "not_configured": "Calendar acquisition was not configured for this generation; zero rows does not mean no events exist.",
                "healthy_empty": "The configured calendar snapshot was observed and contained no retained events in scope.",
                "stale": "The configured calendar snapshot was stale and was not admitted.",
                "fixture_rejected_live": "Fixture or replay calendar data was correctly rejected from the live generation.",
            }.get(status, "No exact-generation calendar rows are available; inspect the calendar acquisition state.")
            body = f'<div class="empty-inline">{escape_html(message)}</div>'
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scheduled risk</p>'
        '<h2>Upcoming calendar</h2></div><a href="/calendar">Open calendar</a></div>'
        + body + '</section>'
    )


def _current_calendar_events(
    snapshot: DashboardSnapshot,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        row
        for row in snapshot.current_calendar_events
        if calendar_temporal_state(
            row,
            clock=snapshot.generation_authority_checked_at,
        ) in {"active", "upcoming"}
    )


def _calendar_row(row: Mapping[str, Any], *, clock: str | None) -> str:
    timing = present_calendar_window(
        scheduled_at=row.get("scheduled_at"), window_start=row.get("window_start"),
        window_end=row.get("window_end"), time_certainty=row.get("time_certainty"),
        now=clock,
    )
    status = semantic_status(row.get("importance"))
    temporal_state = calendar_temporal_state(row, clock=clock)
    if temporal_state == "active":
        end = present_time(row.get("window_end"), now=clock)
        timing_summary = (
            f"Active · ends {end.relative_label}"
            if end.available
            else f"Active risk window · opened {timing.relative_label}"
        )
    else:
        timing_summary = f"{timing.label} · {timing.relative_label}"
    return (
        '<article class="calendar-mini"><div><strong>'
        f'{escape_html(row.get("title") or "Scheduled event")}</strong>'
        f'<p>{escape_html(timing_summary)}</p></div>'
        f'<span class="status-badge tone-{escape_html(status.tone)}">{escape_html(status.label)}</span></article>'
    )


def _campaign_snapshot(snapshot: DashboardSnapshot) -> str:
    generation = snapshot.market_generation
    observations = snapshot.current_market_observations
    counts = Counter(_baseline(row) for row in observations)
    latest = snapshot.campaign_latest_attempt
    latest_time = present_time(
        latest.get("attempted_at")
        or latest.get("recorded_at")
        or latest.get("observed_at"),
        now=snapshot.generation_authority_checked_at,
    )
    baseline = (
        humanize_enum(
            generation.get("baseline_status") or _aggregate_baseline(counts)
        )
        if observations
        else UNAVAILABLE
    )
    maturity_counts = (
        f"{counts.get('warm', 0)} / {counts.get('warming', 0)} / {counts.get('cold', 0)}"
        if observations
        else UNAVAILABLE
    )
    spread_count = sum(
        1
        for row in observations
        if _quality(row).get("spread_available") is True
        or str(row.get("spread_status") or "").casefold()
        in {"verified", "verified_good", "verified_acceptable"}
    )
    spread_coverage = (
        f"{spread_count}/{len(observations)}" if observations else UNAVAILABLE
    )
    exact_items = (
        ("Current-row baseline", baseline),
        ("Current rows · warm / warming / cold", maturity_counts),
        ("Spread coverage", spread_coverage),
    )
    if str(snapshot.operator_state.get("run_mode") or "").casefold() == "fixture":
        items = exact_items + ((
            "Live campaign history",
            "Separate context · not this fixture",
        ),)
    else:
        items = exact_items + (
            ("Latest attempt", latest_time.primary_label if latest_time.available else "Unavailable"),
            ("Latest result", humanize_enum(latest.get("status") or latest.get("result_status"))),
        )
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Observation campaign</p>'
        '<h2>Baseline maturity</h2></div><a href="/campaign-history">History</a></div>'
        + _definition(items)
        + '<p class="muted">A warm sample requires both enough observations and enough elapsed feature-specific coverage.</p></section>'
    )


def _change_summary(snapshot: DashboardSnapshot) -> str:
    comparison = _candidate_count_comparison(snapshot)
    if comparison is None:
        message = (
            "A trustworthy idea-level diff is not available yet. The current pointer history does not "
            "contain two validated candidate summaries, so no change is inferred."
        )
    else:
        previous_count, current_count = comparison
        delta = current_count - previous_count
        message = (
            f"Candidate count changed from {previous_count} to {current_count} "
            f"({delta:+d}). Attempt rows are historical campaign evidence, not current authority."
        )
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Since previous authority</p>'
        '<h2>Material change</h2></div></div>'
        f'<p>{escape_html(message)}</p><p class="muted">Only exact validated summaries are compared; missing data is never guessed.</p></section>'
    )


def _candidate_count_comparison(snapshot: DashboardSnapshot) -> tuple[int, int] | None:
    attempts = snapshot.campaign_attempts
    if len(attempts) < 2:
        return None
    previous, current = attempts[-2], attempts[-1]
    if (
        current.get("artifact_namespace") != snapshot.artifact_namespace
        or current.get("run_id") != snapshot.run_id
    ):
        return None
    for row in (previous, current):
        if (
            str(row.get("status") or "").casefold() != "complete"
            or row.get("decision_radar_campaign_counted") is not True
        ):
            return None
    previous_count = _non_negative_int(previous.get("candidate_count"))
    current_count = _non_negative_int(current.get("candidate_count"))
    if previous_count is None or current_count is None:
        return None
    return previous_count, current_count


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _calendar_status(snapshot: DashboardSnapshot) -> str:
    calendar = snapshot.market_generation.get("calendar_snapshot")
    if isinstance(calendar, Mapping):
        status = str(calendar.get("normalization_status") or calendar.get("status") or "unknown").casefold()
        return status
    packs = snapshot.source_coverage.get("packs")
    if isinstance(packs, (list, tuple)):
        statuses = {
            str(row.get("provider_coverage_status") or row.get("source_pack_coverage_status") or "").casefold()
            for row in packs if isinstance(row, Mapping) and str(row.get("source_pack") or "") == "unlock_supply_pack"
        }
        if statuses == {"not_configured"}:
            return "not_configured"
    return "unknown"


def _quality(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("market_data_quality") or row.get("data_quality")
    return value if isinstance(value, Mapping) else {}


def _baseline(row: Mapping[str, Any]) -> str:
    return str(_quality(row).get("baseline_status") or "unknown").casefold()


def _aggregate_baseline(counts: Counter[str]) -> str:
    if counts.get("warm"):
        return "warm"
    if counts.get("warming"):
        return "warming"
    if counts.get("cold"):
        return "cold"
    return "unknown"


def _layer_metric(
    snapshot: DashboardSnapshot,
    layer: DashboardLayerCoverage,
    *,
    count: int,
    healthy_detail: str,
) -> tuple[object, str]:
    if not snapshot.generation_authoritative:
        return "Suppressed", "Untrusted exact generation"
    if layer.status in {"healthy_nonempty", "healthy_empty"}:
        return count, healthy_detail
    if layer.status == "degraded" and count:
        return f"{count} admitted", "Incomplete exact coverage"
    if layer.status == "not_configured":
        return "Not configured", "No exact layer configured"
    if layer.status == "not_applicable":
        return "Not applicable", "Layer not required"
    return "Unavailable", f"{humanize_enum(layer.status)} layer"


def _outcome_metric(
    snapshot: DashboardSnapshot,
    layer: DashboardLayerCoverage,
    *,
    pending: int,
) -> tuple[object, str]:
    authority = str(snapshot.current_outcomes_metadata.get("authority") or "")
    fingerprint_verified = (
        authority == "current_generation_fingerprint_verified"
        and bool(snapshot.current_outcomes_metadata.get("sha256"))
    )
    admitted = (
        snapshot.generation_authoritative
        and (
            layer.status in {"healthy_nonempty", "healthy_empty"}
            or (layer.status == "degraded" and fingerprint_verified)
        )
    )
    if admitted:
        return (
            f"{pending} admitted" if layer.status == "degraded" else pending,
            "Incomplete outcome coverage"
            if layer.status == "degraded"
            else "Current learning loop",
        )
    return _layer_metric(
        snapshot,
        layer,
        count=pending,
        healthy_detail="Current learning loop",
    )


def _metric(label: str, value: object, detail: str) -> str:
    text_value = str(value)
    text_class = " metric-card--text" if not any(character.isdigit() for character in text_value) else ""
    return f'<article class="metric-card{text_class}"><span>{escape_html(label)}</span><strong>{escape_html(value)}</strong><small>{escape_html(detail)}</small></article>'


def _definition(items: tuple[tuple[str, object], ...]) -> str:
    return '<dl class="definition-grid">' + ''.join(
        f'<dt>{escape_html(label)}</dt><dd>{escape_html(value)}</dd>' for label, value in items
    ) + '</dl>'


__all__ = ("render_today_page",)
