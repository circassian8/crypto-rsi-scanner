"""Decision Radar Today / command-center page."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from ..radar import market_units as event_market_units
from .components import escape_html
from .ideas_page import (
    render_idea_cards,
    render_idea_comparison,
    render_idea_filters,
)
from .layer_coverage import DashboardLayerCoverage, dashboard_layer_coverage
from .models import DashboardSnapshot
from .presentation import (
    format_percent,
    humanize_enum,
    humanize_reason,
    present_calendar_window,
    present_time,
    semantic_status,
)
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
    "catalyst": "/catalysts",
    "calendar": "/calendar",
    "derivatives": "/health",
    "rsi": "/health",
    "outcomes": "/outcomes",
    "request_ledger": "/health",
}


def render_today_page(
    snapshot: DashboardSnapshot,
    *,
    query: Mapping[str, str] | None = None,
    include_diagnostics: bool = False,
) -> str:
    source_rows = (
        snapshot.current_candidates
        if include_diagnostics
        else snapshot.visible_current_candidates
    )
    visible = tuple(filter_sort_candidates(source_rows, query))
    observations = snapshot.current_market_observations
    pending = sum(
        1 for row in snapshot.current_outcomes
        if str(row.get("outcome_status") or row.get("maturation_state") or "").casefold() == "pending"
    )
    metrics = (
        ("Attention now", len(visible), "Current visible ideas"),
        ("Assets evaluated", len(observations), "Exact market observations"),
        ("Anomaly evidence", len(snapshot.current_market_anomalies), "Scanner rows"),
        ("Upcoming events", len(snapshot.current_calendar_events), "Exact calendar rows"),
        ("Pending outcomes", pending, "Current learning loop"),
    )
    headline = (
        "No immediate Decision idea qualified"
        if not visible and observations
        else "No trusted current research is available"
        if not snapshot.generation_authoritative
        else "What deserves attention now"
    )
    intro_detail = (
        f"The scan evaluated {len(observations)} assets. A zero-idea result is valid and does not mean "
        "the provider or dashboard failed. Review the constraints and market table below."
        if not visible and observations
        else "Prioritized Decision v2 ideas, scheduled risk, and system constraints from one exact generation."
    )
    intro = (
        '<section class="command-hero"><div><p class="eyebrow">Today · command center</p>'
        f'<h2>{escape_html(headline)}</h2><p>{escape_html(intro_detail)}</p>'
        '<div class="hero-actions"><a class="button button-primary" href="/market-radar">Open Market Radar</a>'
        '<a class="button button-quiet" href="/health">Review system state</a></div></div>'
        f'<div class="hero-pulse"><span>{len(visible)}</span><small>ideas now</small></div></section>'
        + '<div class="metric-grid">' + "".join(_metric(*item) for item in metrics) + '</div>'
    )
    warnings = _operator_warnings(snapshot)
    attention = _attention_sections(visible)
    comparison = render_idea_comparison(visible)
    controls = (
        '<details class="disclosure filter-disclosure"'
        + (" open" if query else "")
        + '><summary>Filter and compare current ideas</summary><div class="disclosure__body">'
        + render_idea_filters(dict(query or {}), action="/")
        + comparison
        + '</div></details>'
    )
    expired = _expired_ideas(snapshot, query)
    market = _market_snapshot(snapshot)
    calendar = _calendar_snapshot(snapshot)
    campaign = _campaign_snapshot(snapshot)
    changes = _change_summary(snapshot)
    return (
        intro
        + warnings
        + controls
        + attention
        + expired
        + '<div class="two-column">'
        + market
        + calendar
        + campaign
        + changes
        + '</div>'
    )


def _expired_ideas(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    rows = tuple(filter_sort_candidates(snapshot.expired_current_candidates, query))
    if not rows:
        return ""
    return (
        '<section class="panel expired-ideas"><div class="section-heading"><div>'
        '<p class="eyebrow">Read-time safety</p>'
        '<h2>Expired ideas (not currently actionable)</h2></div>'
        f'<span class="lane-count">{len(rows)}</span></div>'
        '<p>Expired; current actionability suppressed. Canonical research history is preserved, '
        'but these rows cannot be presented as actionable at or after their recorded expiry.</p>'
        + render_idea_cards(rows)
        + '</section>'
    )


def _operator_warnings(snapshot: DashboardSnapshot) -> str:
    rows = snapshot.current_market_observations
    quality_rows = [_quality(row) for row in rows]
    spread = sum(1 for row, quality in zip(rows, quality_rows, strict=True) if (
        quality.get("spread_available") is True
        or str(row.get("spread_status") or "").casefold() in {"verified", "verified_good", "verified_acceptable"}
    ))
    warm = sum(1 for quality in quality_rows if str(quality.get("baseline_status") or "").casefold() == "warm")
    warnings: list[tuple[str, str, str]] = []
    coverage = dashboard_layer_coverage(snapshot)
    for layer in coverage:
        if not layer.action_required:
            continue
        warnings.append((
            _coverage_warning_title(layer),
            layer.detail,
            _COVERAGE_HREFS[layer.key],
        ))
    if rows and not spread:
        warnings.append((
            "Execution spread unavailable",
            f"Spread is unverified for all {len(rows)} assets. Liquid ideas can remain visible as watch items, but actionable routes stay capped.",
            "/market-radar?spread=unavailable",
        ))
    if rows and not warm:
        warnings.append((
            "Temporal baseline still warming",
            "No asset has a globally warm feature baseline yet. Direct observations and cross-sectional proxies are labeled separately.",
            "/campaign-history",
        ))
    if snapshot.doctor_status.casefold() != "ok":
        warnings.append((
            "Strict doctor requires attention",
            f"The exact doctor state is {humanize_enum(snapshot.doctor_status)}.",
            "/health",
        ))
    if not warnings:
        return '<section class="alert alert-positive"><div class="alert-icon" aria-hidden="true">✓</div><div><h2>No action-required system warnings</h2><p>Trust, doctor, and every expected exact-generation product layer are healthy or explicitly not applicable.</p></div></section>'
    return (
        '<section class="panel warning-stack"><div class="section-heading"><div><p class="eyebrow">Action required</p>'
        f'<h2>{len(warnings)} system constraint{"s" if len(warnings) != 1 else ""}</h2></div></div>'
        + "".join(
            f'<a class="warning-row" href="{escape_html(href)}"><span aria-hidden="true">!</span><div><strong>{escape_html(title)}</strong><p>{escape_html(detail)}</p></div><b aria-hidden="true">→</b></a>'
            for title, detail, href in warnings
        ) + '</section>'
    )


def _coverage_warning_title(layer: DashboardLayerCoverage) -> str:
    if layer.key == "calendar" and layer.status == "not_configured":
        return "Calendar acquisition not configured"
    if layer.key == "request_ledger":
        return f"Provider request ledger {humanize_enum(layer.status).casefold()}"
    return f"{layer.label} {humanize_enum(layer.status).casefold()}"


def _attention_sections(rows: tuple[Mapping[str, Any], ...]) -> str:
    sections = []
    for route, title, description in _ATTENTION_LANES:
        lane = tuple(row for row in rows if str(row.get("_dashboard_route") or row.get("radar_route")) == route)
        if not lane:
            continue
        sections.append(
            '<section class="attention-lane"><div class="section-heading"><div>'
            f'<p class="eyebrow">{escape_html(humanize_enum(route))}</p><h2>{escape_html(title)}</h2>'
            f'<p>{escape_html(description)}</p></div><span class="lane-count">{len(lane)}</span></div>'
            + render_idea_cards(lane, limit=4) + '</section>'
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
        snapshot.current_calendar_events,
        key=lambda row: str(row.get("scheduled_at") or row.get("window_start") or "~"),
    )[:4]
    if events:
        body = ''.join(_calendar_row(row) for row in events)
    else:
        status = _calendar_status(snapshot)
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


def _calendar_row(row: Mapping[str, Any]) -> str:
    timing = present_calendar_window(
        scheduled_at=row.get("scheduled_at"), window_start=row.get("window_start"),
        window_end=row.get("window_end"), time_certainty=row.get("time_certainty"),
    )
    status = semantic_status(row.get("importance"))
    return (
        '<article class="calendar-mini"><div><strong>'
        f'{escape_html(row.get("title") or "Scheduled event")}</strong>'
        f'<p>{escape_html(timing.label)} · {escape_html(timing.relative_label)}</p></div>'
        f'<span class="status-badge tone-{escape_html(status.tone)}">{escape_html(status.label)}</span></article>'
    )


def _campaign_snapshot(snapshot: DashboardSnapshot) -> str:
    generation = snapshot.market_generation
    counts = Counter(_baseline(row) for row in snapshot.current_market_observations)
    latest = snapshot.campaign_latest_attempt
    latest_time = present_time(latest.get("attempted_at") or latest.get("recorded_at") or latest.get("observed_at"))
    items = (
        ("Baseline", humanize_enum(generation.get("baseline_status") or _aggregate_baseline(counts))),
        ("Warm / warming / cold", f"{counts.get('warm', 0)} / {counts.get('warming', 0)} / {counts.get('cold', 0)}"),
        ("Spread coverage", f"{generation.get('spread_available_count') or 0}/{len(snapshot.current_market_observations)}"),
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
    attempts = snapshot.campaign_attempts
    if len(attempts) < 2:
        message = (
            "A trustworthy idea-level diff is not available yet. The current pointer history does not "
            "contain two validated candidate summaries, so no change is inferred."
        )
    else:
        current, previous = attempts[-1], attempts[-2]
        current_count = int(current.get("candidate_count") or 0)
        previous_count = int(previous.get("candidate_count") or 0)
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


def _metric(label: str, value: object, detail: str) -> str:
    return f'<article class="metric-card"><span>{escape_html(label)}</span><strong>{escape_html(value)}</strong><small>{escape_html(detail)}</small></article>'


def _definition(items: tuple[tuple[str, object], ...]) -> str:
    return '<dl class="definition-grid">' + ''.join(
        f'<dt>{escape_html(label)}</dt><dd>{escape_html(value)}</dd>' for label, value in items
    ) + '</dl>'


__all__ = ("render_today_page",)
