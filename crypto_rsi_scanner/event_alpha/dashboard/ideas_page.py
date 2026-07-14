"""Trader-first idea list and detail pages for Decision Radar."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote, urlencode

from .charts import (
    render_activity_chart,
    render_price_chart,
    render_relative_chart,
)
from .components import escape_html, safe_external_href
from .loader import candidate_identifier
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_score,
    humanize_enum,
    humanize_reason,
    present_calendar_window,
    present_time,
    score_band,
    semantic_status,
)
from .view_data import (
    candidate_data_quality,
    candidate_provenance,
    dashboard_query,
    filter_sort_candidates,
    finite_number,
    origin_tokens,
)


def render_ideas_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
    *,
    include_diagnostics: bool = False,
) -> str:
    filters = dashboard_query(query)
    rows: Iterable[Mapping[str, Any]] = snapshot.current_candidates
    if not include_diagnostics:
        rows = tuple(
            row for row in rows
            if row.get("_decision_model_status") == "v2"
            and row.get("_dashboard_route") != "diagnostic"
        )
    selected = filter_sort_candidates(rows, filters)
    return (
        '<section class="page-intro"><div><p class="eyebrow">Canonical Decision v2 ideas</p>'
        '<h2>Research opportunities, ranked for human review</h2>'
        '<p>Actionability describes usefulness now; evidence confidence describes how well the '
        'explanation is supported. Neither is a win probability.</p></div>'
        f'<div class="count-badge" aria-label="{len(selected)} matching ideas">{len(selected)}<small>matching</small></div></section>'
        + render_idea_filters(filters, action="/ideas")
        + _active_filters(filters)
        + render_idea_cards(selected)
        + render_idea_comparison(selected)
        + (
            '<p class="diagnostic-link"><a href="/ideas?include_diagnostics=1">Show diagnostic controls</a></p>'
            if not include_diagnostics and snapshot.diagnostic_candidates else ""
        )
    )


def render_idea_cards(rows: Iterable[Mapping[str, Any]], *, limit: int | None = None) -> str:
    materialized = tuple(rows)
    if limit is not None:
        materialized = materialized[: max(0, int(limit))]
    if not materialized:
        return (
            '<div class="empty-state"><span aria-hidden="true">○</span><div>'
            '<h3>No ideas match this view</h3><p>This can be a valid outcome. Market observations '
            'and coverage state remain available in Market Radar and System Health.</p></div></div>'
        )
    return '<div class="idea-grid">' + "".join(_idea_card(row) for row in materialized) + "</div>"


def render_idea_comparison(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = tuple(rows)
    if not materialized:
        return ""
    headers = (
        "Idea", "Route", "Bias", "Actionability", "Evidence", "Risk", "Urgency",
        "Chase risk", "Phase", "Catalyst", "Tradability", "Spread", "Horizon", "Expires",
    )
    body = []
    for row in materialized:
        identifier = candidate_identifier(row)
        href = f"/ideas/{quote(identifier, safe='')}"
        cells = (
            f'<a href="{href}"><strong>{escape_html(row.get("symbol") or identifier)}</strong></a>',
            escape_html(humanize_enum(row.get("_dashboard_route") or row.get("radar_route"))),
            escape_html(humanize_enum(row.get("directional_bias"))),
            escape_html(format_score(row.get("actionability_score"))),
            escape_html(format_score(row.get("evidence_confidence_score"))),
            escape_html(format_score(row.get("risk_score"))),
            escape_html(format_score(row.get("urgency_score"))),
            escape_html(format_score(row.get("chase_risk_score"))),
            escape_html(humanize_enum(row.get("market_phase") or row.get("timing_state"))),
            escape_html(humanize_enum(row.get("catalyst_status"))),
            escape_html(humanize_enum(row.get("tradability_status"))),
            escape_html(humanize_enum(row.get("spread_status"))),
            escape_html(humanize_enum(row.get("preferred_horizon"))),
            _time_markup(row.get("expires_at"), expiry=True),
        )
        body.append(
            "<tr>" + "".join(
                f'<td data-label="{escape_html(label)}">{value}</td>'
                for label, value in zip(headers, cells, strict=True)
            ) + "</tr>"
        )
    head = "".join(f'<th scope="col">{escape_html(value)}</th>' for value in headers)
    return (
        '<section class="panel comparison-panel"><div class="section-heading"><div><p class="eyebrow">Comparison</p>'
        '<h2>Idea matrix</h2></div></div><div class="table-scroll" role="region" tabindex="0" '
        'aria-label="Scrollable idea comparison"><table class="responsive-table"><caption class="sr-only">'
        f'{len(materialized)} current Decision Radar ideas</caption><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div></section>'
    )


def render_idea_filters(query: Mapping[str, str], *, action: str) -> str:
    options = (
        ("route", "Route", ("dashboard_watch", "actionable_watch", "high_confidence_watch", "rapid_market_anomaly", "fade_exhaustion_review", "risk_watch", "calendar_risk", "diagnostic")),
        ("origin", "Origin", ("market_led", "catalyst_led", "technical_led", "derivatives_led", "onchain_led", "fundamental_led", "macro_led")),
        ("bias", "Bias", ("long_watch", "fade_short_review", "risk", "neutral")),
        ("actionability", "Actionability", ("very_high", "high", "medium", "low")),
        ("evidence", "Evidence", ("very_high", "high", "medium", "low")),
        ("risk", "Risk", ("low", "medium", "high")),
        ("urgency", "Urgency", ("very_high", "high", "medium", "low")),
        ("market_phase", "Phase", ("emerging", "breakout", "acceleration", "active", "extended", "exhaustion", "reversal")),
        ("catalyst", "Catalyst", ("confirmed", "plausible", "unknown", "not_required", "disproven")),
        ("tradability", "Tradability", ("verified", "provisional", "poor", "blocked")),
        ("spread", "Spread", ("verified_good", "verified_acceptable", "verified_wide", "unavailable", "stale")),
        ("freshness", "Freshness", ("fresh", "warming", "stale", "unknown")),
        ("horizon", "Horizon", ("intraday", "1h", "4h", "24h", "multi_day")),
    )
    fields = [
        '<label class="filter-search"><span>Search symbol or thesis</span>'
        f'<input type="search" name="search" value="{escape_html(query.get("search", ""))}" placeholder="BTC, breakout, listing…"></label>'
    ]
    for name, label, values in options:
        selected = query.get(name, "")
        option_html = '<option value="">All</option>' + "".join(
            f'<option value="{escape_html(value)}"{(" selected" if value == selected else "")}>{escape_html(humanize_enum(value))}</option>'
            for value in values
        )
        fields.append(f'<label><span>{escape_html(label)}</span><select name="{name}">{option_html}</select></label>')
    sort_selected = query.get("sort", "attention")
    sort_values = (
        ("attention", "Operator attention"), ("actionability_desc", "Actionability · high first"),
        ("evidence_desc", "Evidence · high first"), ("urgency_desc", "Urgency · high first"),
        ("risk_asc", "Risk · low first"), ("risk_desc", "Risk · high first"),
        ("expiry_asc", "Expiry · soonest first"),
    )
    fields.append(
        '<label><span>Sort</span><select name="sort">' + "".join(
            f'<option value="{value}"{(" selected" if value == sort_selected else "")}>{escape_html(label)}</option>'
            for value, label in sort_values
        ) + '</select></label>'
    )
    return (
        f'<form class="filter-panel" method="get" action="{escape_html(action)}"><div class="filter-grid">'
        + "".join(fields)
        + '</div><div class="filter-actions"><button class="button button-primary" type="submit">Apply filters</button>'
        f'<a class="button button-quiet" href="{escape_html(action)}">Clear all</a></div></form>'
    )


def render_idea_detail(
    snapshot: DashboardSnapshot,
    identifier: str,
    *,
    include_diagnostics: bool = False,
) -> tuple[int, str, str]:
    row = next((item for item in snapshot.current_candidates if candidate_identifier(item) == identifier), None)
    if row is None or (
        not include_diagnostics
        and row.get("_decision_expired_at_read_time") is not True
        and (row.get("_decision_model_status") != "v2" or row.get("_dashboard_route") == "diagnostic")
    ):
        return 404, "Idea not found", (
            '<div class="empty-state"><h2>Idea not found</h2>'
            '<p>No visible candidate in this exact generation has that identity.</p></div>'
        )
    if not snapshot.generation_authoritative:
        return 409, "Idea unavailable", '<div class="alert alert-danger">The exact generation is not trusted.</div>'
    title = f"{row.get('symbol') or 'Idea'} decision brief"
    provenance = candidate_provenance(row)
    quality = candidate_data_quality(row)
    score_cards = "".join(
        _score_card(label, row.get(field), dimension=dimension, explanation=explanation)
        for label, field, dimension, explanation in (
            ("Actionability", "actionability_score", "quality", "Usefulness and timing now — not win probability."),
            ("Evidence", "evidence_confidence_score", "quality", "Confidence in the explanation — not expected return."),
            ("Risk", "risk_score", "risk", "Higher is more risk; the scale is not reversed."),
            ("Urgency", "urgency_score", "urgency", "How quickly the research window may change."),
            ("Chase risk", "chase_risk_score", "risk", "Risk that the move is already extended."),
        )
    )
    history = _idea_history(snapshot, row)
    baseline_state = str(quality.get("baseline_status") or "missing")
    chart_state = baseline_state if baseline_state in {"warming", "cold"} else ("ready" if history else "missing")
    charts = (
        '<div class="chart-grid">'
        + render_price_chart(history, state=chart_state, state_detail="Exact-generation bounded history")
        + render_activity_chart(history, activity="volume", value_key="volume_24h", state=chart_state, proxy=False)
        + render_activity_chart(history, activity="turnover", value_key="turnover_24h", state=chart_state, proxy=True)
        + render_relative_chart(history, benchmark="BTC", state=chart_state, state_detail="Relative history may be unavailable until baseline warms")
        + '</div>'
    )
    context = _decision_context(row, provenance, quality)
    source = _source_block(row)
    calendar = _nearby_calendar(snapshot, row)
    outcome = _outcome_block(snapshot, row)
    feedback_command = (
        f".venv/bin/python main.py --event-feedback-mark {identifier} useful --confirm"
    )
    body = (
        '<p class="back-link"><a href="/ideas">← All ideas</a></p>'
        '<section class="idea-hero panel"><div><p class="eyebrow">Crypto Decision Radar</p>'
        f'<h2>{escape_html(row.get("symbol") or identifier)} <span>{escape_html(row.get("coin_id") or "")}</span></h2>'
        f'<div class="chip-row">{_status_badge(row.get("_dashboard_route"))}{_status_badge(row.get("directional_bias"))}'
        f'{_status_badge(row.get("catalyst_status"))}{_status_badge(row.get("market_phase"))}</div></div>'
        f'<div class="idea-expiry"><span>Research window</span>{_time_markup(row.get("expires_at"), expiry=True)}</div></section>'
        f'<section class="score-grid" aria-label="Decision score summary">{score_cards}</section>'
        + context
        + source
        + _narrative_grid(row)
        + _decision_evidence(row)
        + '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Measured context</p><h2>Market history</h2></div>'
        f'{_status_badge(baseline_state)}</div>{charts}</section>'
        + calendar
        + _technical_context(row)
        + _catalyst_context(row)
        + outcome
        + '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Optional preference signal</p>'
        '<h2>Usefulness feedback</h2></div></div><p>Feedback is optional and never controls visibility or thresholds. '
        'The dashboard remains GET/HEAD-only; use the explicit confirmed CLI pathway.</p>'
        f'<pre class="copy-value"><code>{escape_html(feedback_command)}</code></pre></section>'
        + _technical_details(row, provenance, quality)
    )
    return 200, title, body


def _idea_card(row: Mapping[str, Any]) -> str:
    identifier = candidate_identifier(row)
    route = row.get("_dashboard_route") or row.get("radar_route")
    warning_values = _values(row, "decision_warnings", "main_risks")
    why = _values(row, "why_now", "why_still_worth_reviewing", "supporting_facts")
    expiry = _time_markup(row.get("expires_at"), expiry=True)
    scores = "".join(
        _mini_score(label, row.get(field), dimension)
        for label, field, dimension in (
            ("Act", "actionability_score", "quality"),
            ("Evidence", "evidence_confidence_score", "quality"),
            ("Risk", "risk_score", "risk"),
            ("Urgency", "urgency_score", "urgency"),
        )
    )
    return (
        f'<article class="idea-card route-{escape_html(str(route or "unknown"))}">'
        '<div class="idea-card-head"><div>'
        f'<p class="eyebrow">{escape_html(humanize_enum(route))}</p><h3><a href="/ideas/{quote(identifier, safe="")}">'
        f'{escape_html(row.get("symbol") or identifier)}</a></h3>'
        f'<p class="muted">{escape_html(" + ".join(humanize_enum(value) for value in origin_tokens(row)))}</p></div>'
        f'{_status_badge(row.get("directional_bias"))}</div>'
        f'<div class="mini-score-grid">{scores}</div>'
        f'<p class="idea-why">{escape_html(why[0] if why else "No concise thesis recorded.")}</p>'
        + _card_sparkline(row)
        + '<div class="idea-meta">'
        f'<span>{escape_html(humanize_enum(row.get("market_phase") or row.get("timing_state")))}</span>'
        f'<span>{escape_html(humanize_enum(row.get("preferred_horizon")))}</span><span>{expiry}</span></div>'
        f'<div class="chip-row">{_status_badge(row.get("catalyst_status"))}{_status_badge(row.get("spread_status"))}'
        f'{_status_badge(row.get("tradability_status"))}</div>'
        + (f'<p class="card-warning">{escape_html(humanize_reason(warning_values[0]))}</p>' if warning_values else "")
        + f'<a class="card-action" href="/ideas/{quote(identifier, safe="")}">Open decision brief <span aria-hidden="true">→</span></a></article>'
    )


def _decision_context(
    row: Mapping[str, Any],
    provenance: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> str:
    items = (
        ("Primary thesis origin", humanize_enum(row.get("primary_thesis_origin") or row.get("thesis_origin"))),
        ("Thesis origins", " · ".join(humanize_enum(value) for value in origin_tokens(row))),
        (
            "Current actionability",
            "suppressed: expired at dashboard read time"
            if row.get("_decision_expired_at_read_time") is True
            else str(bool(row.get("radar_actionable"))).casefold(),
        ),
        ("Read-time safety reason", row.get("_decision_read_time_reason") or UNAVAILABLE),
        ("Timing", humanize_enum(row.get("timing_state"))),
        ("Market phase", humanize_enum(row.get("market_phase"))),
        ("Preferred horizon", humanize_enum(row.get("preferred_horizon"))),
        ("Expires at", present_time(row.get("expires_at")).utc_label),
        ("Tradability", humanize_enum(row.get("tradability_status"))),
        ("Spread", humanize_enum(row.get("spread_status"))),
        ("Market freshness", humanize_enum(row.get("market_data_freshness") or row.get("market_context_freshness_status"))),
        ("Data mode", humanize_enum(provenance.get("candidate_source_mode") or provenance.get("data_mode"))),
        ("Market provider", humanize_enum(provenance.get("provider"))),
        ("Baseline", humanize_enum(quality.get("baseline_status"))),
        ("Liquidity basis", humanize_enum(quality.get("liquidity_basis"))),
        ("Volume basis", humanize_enum(quality.get("volume_zscore_basis"))),
        ("Execution quality", humanize_enum(quality.get("spread_basis") or row.get("spread_status"))),
    )
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Decision context</p><h2>How to read this idea</h2></div></div>' + _definition_grid(items) + '</section>'


def _narrative_grid(row: Mapping[str, Any]) -> str:
    blocks = (
        ("Why now", _values(row, "why_now", "why_still_worth_reviewing"), "info"),
        ("What confirms", _values(row, "radar_what_confirms", "what_confirms"), "positive"),
        ("What invalidates", _values(row, "radar_what_invalidates", "what_invalidates"), "danger"),
        ("Main risks", _values(row, "main_risks", "decision_warnings"), "warning"),
        ("Missing information", _values(row, "missing_information", "decision_missing_data"), "neutral"),
        ("Supporting facts", _values(row, "supporting_facts"), "neutral"),
    )
    cards = []
    for title, values, tone in blocks:
        content = "".join(f"<li>{escape_html(_narrative_text(value))}</li>" for value in values)
        cards.append(
            f'<section class="narrative-card tone-{tone}"><h2>{escape_html(title)}</h2>'
            + (f"<ul>{content}</ul>" if content else '<p class="muted">No item recorded.</p>')
            + "</section>"
        )
    return '<div class="narrative-grid">' + "".join(cards) + "</div>"


def _decision_evidence(row: Mapping[str, Any]) -> str:
    sections = (
        _value_section("Hard blockers", _values(row, "decision_hard_blockers")),
        _value_section("Soft penalties", _values(row, "decision_soft_penalties")),
        _value_section("Decision warnings", _values(row, "decision_warnings")),
        _component_table("Actionability score components", row.get("actionability_score_components")),
        _component_table("Actionability penalty components", row.get("actionability_penalty_components")),
        _component_table(
            "Evidence-confidence score components",
            row.get("evidence_confidence_score_components"),
        ),
        _component_table("Risk score components", row.get("risk_score_components")),
    )
    return (
        '<details class="technical-details panel"><summary>Decision evidence and score components</summary>'
        '<div class="disclosure__body">'
        + "".join(sections)
        + "</div></details>"
    )


def _value_section(title: str, values: tuple[str, ...]) -> str:
    body = (
        "<ul>" + "".join(f"<li>{escape_html(value)}</li>" for value in values) + "</ul>"
        if values
        else '<p class="muted">None recorded.</p>'
    )
    return f"<h3>{escape_html(title)}</h3>{body}"


def _component_table(title: str, value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return f'<h3>{escape_html(title)}</h3><p class="muted">No component detail recorded.</p>'
    rows = "".join(
        '<tr><th scope="row"><code>'
        + escape_html(key)
        + "</code></th><td>"
        + escape_html(component)
        + "</td></tr>"
        for key, component in sorted(value.items())
        if not isinstance(component, (Mapping, list, tuple, set))
    )
    return (
        f"<h3>{escape_html(title)}</h3>"
        '<div class="table-scroll"><table class="responsive-table compact-table">'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _source_block(row: Mapping[str, Any]) -> str:
    raw = str(
        row.get("source_url")
        or row.get("latest_source_url")
        or row.get("url")
        or ""
    ).strip()
    label = str(row.get("source") or row.get("latest_source") or "Source")
    if not raw:
        source = '<span class="muted">Source URL unavailable</span>'
    else:
        safe_url = safe_external_href(raw)
        if safe_url is None:
            source = '<span class="muted">unsafe or unavailable source URL</span>'
        else:
            source = (
                f'<a href="{escape_html(safe_url)}" rel="noreferrer" target="_blank">'
                f'{escape_html(label)}</a>'
            )
    return (
        '<section class="panel source-panel"><div class="section-heading"><div>'
        '<p class="eyebrow">Evidence source</p><h2>Latest recorded source</h2>'
        f'</div></div><p>{source}</p></section>'
    )


def _narrative_text(value: str) -> str:
    text = str(value).strip()
    if not text:
        return UNAVAILABLE
    if "_" in text and not any(character.isspace() for character in text):
        return humanize_reason(text)
    return text


def _card_sparkline(row: Mapping[str, Any]) -> str:
    values: tuple[float, ...] = ()
    for container_name in ("market_state_snapshot", "market_snapshot"):
        container = row.get(container_name)
        if not isinstance(container, Mapping):
            continue
        for field in ("price_series", "close_series", "return_series", "sparkline_values"):
            raw = container.get(field)
            if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
                continue
            parsed = tuple(
                number
                for item in raw
                if (number := finite_number(item)) is not None
            )
            if len(parsed) >= 2:
                values = parsed
                break
        if values:
            break
    if len(values) < 2:
        return ""
    width, height, padding = 108.0, 30.0, 2.0
    low, high = min(values), max(values)
    span = high - low
    points = []
    for index, value in enumerate(values):
        x = padding + (width - 2 * padding) * index / (len(values) - 1)
        y = height / 2 if span == 0 else padding + (height - 2 * padding) * (high - value) / span
        points.append(f"{x:.1f},{y:.1f}")
    return (
        '<svg class="sparkline" viewBox="0 0 108 30" role="img" '
        'aria-label="Existing market snapshot trend">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="currentColor" '
        'stroke-width="2" vector-effect="non-scaling-stroke"></polyline></svg>'
    )


def _nearby_calendar(snapshot: DashboardSnapshot, row: Mapping[str, Any]) -> str:
    evidence_ids = set(_values(row, "calendar_evidence_ids"))
    evidence = row.get("calendar_evidence")
    if isinstance(evidence, Iterable) and not isinstance(evidence, (str, bytes, Mapping)):
        for item in evidence:
            if isinstance(item, Mapping):
                value = item.get("calendar_event_id") or item.get("event_id")
                if value:
                    evidence_ids.add(str(value))
    symbol = str(row.get("symbol") or "").upper()
    nearby = []
    for event in snapshot.current_calendar_events:
        event_id = str(event.get("calendar_event_id") or "")
        assets = {str(item).upper() for item in event.get("affected_assets") or ()}
        if event_id in evidence_ids or symbol and symbol in assets:
            nearby.append(event)
    if not nearby:
        return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scheduled risk</p><h2>Nearby calendar events</h2></div></div><div class="empty-inline">No exact-generation calendar event is attached to this idea.</div></section>'
    cards = []
    for event in nearby:
        timing = present_calendar_window(
            scheduled_at=event.get("scheduled_at"), window_start=event.get("window_start"),
            window_end=event.get("window_end"), time_certainty=event.get("time_certainty"),
        )
        cards.append(
            '<article class="calendar-mini"><div>'
            f'<strong>{escape_html(event.get("title") or "Scheduled event")}</strong>'
            f'<p>{escape_html(timing.label)} · {escape_html(timing.relative_label)}</p></div>'
            f'{_status_badge(event.get("importance"))}</article>'
        )
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scheduled risk</p><h2>Nearby calendar events</h2></div></div>' + "".join(cards) + '</section>'


def _technical_context(row: Mapping[str, Any]) -> str:
    context = row.get("rsi_context")
    refs = _values(row, "rsi_context_references")
    if not isinstance(context, Mapping) and not refs:
        return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Technical context</p><h2>RSI and setup evidence</h2></div></div><div class="empty-inline">No exact RSI context is attached. No RSI scan, alert, or write is performed by this page.</div></section>'
    values = []
    if isinstance(context, Mapping):
        for key in ("setup", "timeframe", "rsi", "regime", "trend", "edge_status"):
            if context.get(key) not in (None, ""):
                values.append((humanize_enum(key), humanize_enum(context.get(key))))
    if refs:
        values.append(("Evidence references", ", ".join(refs)))
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Technical context</p><h2>RSI and setup evidence</h2></div></div>' + _definition_grid(values) + '<p class="muted">Read-only context; no RSI writes, alerts, paper trades, or execution.</p></section>'


def _catalyst_context(row: Mapping[str, Any]) -> str:
    blockers = _values(row, "opportunity_type_why_not_alertable", "why_not_alertable")
    return (
        '<section class="panel catalyst-panel"><div class="section-heading"><div><p class="eyebrow">Catalyst Radar classification</p>'
        '<h2>Secondary catalyst view</h2></div>' + _status_badge(row.get("catalyst_status")) + '</div>'
        + _definition_grid((
            ("Legacy classification", humanize_enum(row.get("opportunity_type"))),
            ("Strict catalyst route", humanize_enum(row.get("final_route_after_quality_gate") or row.get("route"))),
            ("Source strength", humanize_enum(row.get("source_strength"))),
        ))
        + '<h3>Why not eligible for strict catalyst alert</h3>'
        + ("<ul>" + "".join(f"<li>{escape_html(humanize_reason(value))}</li>" for value in blockers) + "</ul>" if blockers else '<p class="muted">No strict catalyst blocker recorded.</p>')
        + '</section>'
    )


def _outcome_block(snapshot: DashboardSnapshot, row: Mapping[str, Any]) -> str:
    identifier = candidate_identifier(row)
    outcome = next((item for item in snapshot.current_outcomes if str(item.get("core_opportunity_id") or item.get("candidate_id")) == identifier), None)
    if outcome is None:
        return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Learning loop</p><h2>Outcome</h2></div></div><div class="empty-inline">No exact-generation outcome row is attached.</div></section>'
    items = (
        ("State", humanize_enum(outcome.get("outcome_status") or outcome.get("maturation_state"))),
        ("Route cohort", humanize_enum(outcome.get("radar_route") or outcome.get("route"))),
        ("Actionability cohort", humanize_enum(outcome.get("actionability_score_cohort"))),
        ("Evidence cohort", humanize_enum(outcome.get("evidence_confidence_score_cohort"))),
        ("Risk cohort", humanize_enum(outcome.get("risk_score_cohort"))),
    )
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Learning loop</p><h2>Outcome</h2></div></div>' + _definition_grid(items) + '<p class="sample-warning">One idea cannot establish statistical edge. Outcomes remain descriptive until a meaningful sample matures.</p></section>'


def _technical_details(
    row: Mapping[str, Any],
    provenance: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> str:
    values = (
        ("Candidate ID", candidate_identifier(row)),
        ("Canonical route code", row.get("radar_route")),
        ("Model version", row.get("decision_model_version")),
        ("Evaluation time", present_time(row.get("decision_evaluated_at")).utc_label),
        ("Market snapshot ID", row.get("market_snapshot_id")),
        ("Observation IDs", ", ".join(_values(row, "observation_ids")) or UNAVAILABLE),
        ("Provider source artifact", provenance.get("provider_source_artifact")),
        ("Request ledger", provenance.get("request_ledger_path")),
        ("Cache status", provenance.get("cache_status")),
        ("Measurement program", provenance.get("measurement_program")),
        ("Campaign counted", provenance.get("decision_radar_campaign_counted")),
        ("Direct feature count", quality.get("direct_feature_count")),
        ("Proxy feature count", quality.get("proxy_feature_count")),
    )
    return '<details class="technical-details panel"><summary>Technical lineage and raw identifiers</summary>' + _definition_grid(values, raw=True) + '</details>'


def _idea_history(snapshot: DashboardSnapshot, row: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    symbol = str(row.get("symbol") or "").upper()
    coin_id = str(row.get("coin_id") or row.get("canonical_asset_id") or "").casefold()
    return tuple(
        item for item in snapshot.exact_market_history
        if (symbol and str(item.get("symbol") or "").upper() == symbol)
        or (coin_id and str(item.get("coin_id") or item.get("canonical_asset_id") or "").casefold() == coin_id)
    )


def _score_card(label: str, value: object, *, dimension: str, explanation: str) -> str:
    band = score_band(value, dimension=dimension)
    number = finite_number(value)
    formatted = format_score(value)
    meter = ""
    if number is not None and 0 <= number <= 100:
        meter = (
            f'<div class="score-meter" role="meter" aria-label="{escape_html(label)}" '
            'aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{escape_html(formatted)}"><span style="width:{number:.1f}%"></span></div>'
        )
    return (
        f'<article class="score-card tone-{escape_html(band.tone)}"><div><span>{escape_html(label)}</span>'
        f'<strong>{escape_html(formatted)}<small>/100</small></strong></div>'
        f'<p><b>{escape_html(band.label)}</b> · {escape_html(explanation)}</p>'
        f'{meter}</article>'
    )


def _mini_score(label: str, value: object, dimension: str) -> str:
    band = score_band(value, dimension=dimension)
    return f'<div class="mini-score tone-{escape_html(band.tone)}"><span>{escape_html(label)}</span><strong>{escape_html(format_score(value))}</strong><small>{escape_html(band.label)}</small></div>'


def _status_badge(value: object) -> str:
    status = semantic_status(value)
    return f'<span class="status-badge tone-{escape_html(status.tone)}"><i aria-hidden="true"></i>{escape_html(status.label)}</span>'


def _time_markup(value: object, *, expiry: bool = False) -> str:
    presented = present_time(value)
    if not presented.available:
        return '<span class="muted">Unavailable</span>'
    prefix = "Expired " if expiry and presented.relative_label.endswith("ago") else ""
    primary = prefix + presented.relative_label
    return f'<time datetime="{escape_html(presented.iso_utc)}" title="{escape_html(presented.utc_label)}">{escape_html(primary)}</time>'


def _active_filters(query: Mapping[str, str]) -> str:
    active = [(name, value) for name, value in query.items() if name != "sort"]
    if not active:
        return ""
    chips = "".join(
        f'<span class="filter-chip"><b>{escape_html(humanize_enum(name))}:</b> {escape_html(humanize_enum(value))}</span>'
        for name, value in active
    )
    return f'<div class="active-filters" aria-label="Selected filters">{chips}<a href="/ideas">Clear all</a></div>'


def _definition_grid(items: Iterable[tuple[str, object]], *, raw: bool = False) -> str:
    values = []
    for label, value in items:
        display = UNAVAILABLE if value in (None, "", [], {}) else str(value)
        rendered = f'<code>{escape_html(display)}</code>' if raw else escape_html(display)
        values.append(f'<dt>{escape_html(label)}</dt><dd>{rendered}</dd>')
    return '<dl class="definition-grid">' + "".join(values) + '</dl>'


def _values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    out = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            if value.strip():
                out.append(value.strip())
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            out.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(out))


__all__ = (
    "render_idea_cards", "render_idea_comparison", "render_idea_detail",
    "render_idea_filters", "render_ideas_page",
)
