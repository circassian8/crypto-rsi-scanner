"""Trader-first idea list and detail pages for Decision Radar."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote, urlencode

from ..radar import catalyst_attribution as event_catalyst_attribution
from ..radar import source_independence as event_source_independence
from .components import escape_html, safe_external_href
from .idea_history import render_market_history_charts as _market_history_charts
from .loader import candidate_identifier
from .layer_coverage import dashboard_layer_coverage_by_key
from .models import DashboardSnapshot, is_canonical_diagnostic_candidate
from .presentation import (
    UNAVAILABLE,
    candidate_operator_route,
    candidate_operator_route_label,
    format_score,
    humanize_enum,
    humanize_reason,
    operator_route_label,
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
    rows = (
        (*snapshot.visible_current_candidates, *snapshot.diagnostic_candidates)
        if include_diagnostics
        else snapshot.visible_current_candidates
    )
    selected = filter_sort_candidates(rows, filters)
    expired_diagnostics = (
        filter_sort_candidates(snapshot.expired_diagnostic_candidates, filters)
        if include_diagnostics
        else ()
    )
    valid_unfiltered_zero = not filters and not rows
    match_label = "matching idea" if len(selected) == 1 else "matching ideas"
    count_label = "idea" if len(selected) == 1 else "ideas"
    return (
        '<section class="page-intro ideas-intro"><div><p class="eyebrow">Canonical Decision v2 ideas</p>'
        '<h2>Current research ideas</h2>'
        '<p>Ranked by usefulness, evidence, and risk for human review—not by win probability.</p></div>'
        f'<div class="count-badge" aria-label="{len(selected)} {match_label}">{len(selected)}<small>{count_label}</small></div></section>'
        + render_idea_filters(filters, action="/ideas")
        + _active_filters(filters)
        + render_idea_cards(
            selected,
            now=snapshot.generation_authority_checked_at,
            empty_title=(
                "No current ideas qualified"
                if valid_unfiltered_zero
                else "No ideas match this view"
            ),
            empty_detail=(
                "This exact generation produced no operator-visible Decision idea. "
                "Market observations and coverage state remain available in Market Radar and System Health."
                if valid_unfiltered_zero
                else None
            ),
        )
        + render_idea_comparison(
            selected,
            now=snapshot.generation_authority_checked_at,
        )
        + _expired_diagnostic_history(
            expired_diagnostics,
            now=snapshot.generation_authority_checked_at,
        )
        + (
            '<p class="diagnostic-link"><a href="/ideas?include_diagnostics=1">Show diagnostic controls</a></p>'
            if not include_diagnostics
            and (snapshot.diagnostic_candidates or snapshot.expired_diagnostic_candidates)
            else ""
        )
    )


def _expired_diagnostic_history(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: object = None,
) -> str:
    materialized = tuple(rows)
    if not materialized:
        return ""
    return (
        '<details class="disclosure panel expired-ideas"><summary><span>'
        'Expired diagnostic controls</span>'
        f'<span class="filter-chip">{len(materialized)} retained</span></summary>'
        '<div class="disclosure__body"><p>These diagnostic rows are retained as '
        'historical model evidence and remain outside the current idea queue.</p>'
        + render_idea_cards(materialized, now=now)
        + '</div></details>'
    )


def render_idea_cards(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = None,
    now: object = None,
    empty_title: str = "No ideas match this view",
    empty_detail: str | None = None,
) -> str:
    materialized = tuple(rows)
    if limit is not None:
        materialized = materialized[: max(0, int(limit))]
    if not materialized:
        detail = empty_detail or (
            "This can be a valid outcome. Market observations and coverage state "
            "remain available in Market Radar and System Health."
        )
        return (
            '<div class="empty-state"><span aria-hidden="true">○</span><div>'
            f'<h3>{escape_html(empty_title)}</h3><p>{escape_html(detail)}</p></div></div>'
        )
    return (
        '<div class="idea-grid">'
        + "".join(_idea_card(row, now=now) for row in materialized)
        + "</div>"
    )


def render_attention_cards(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 4,
    now: object = None,
) -> str:
    """Render a deliberately compact command-center review queue."""

    materialized = tuple(rows)[: max(0, int(limit))]
    return (
        '<div class="attention-card-grid">'
        + "".join(_attention_card(row, now=now) for row in materialized)
        + "</div>"
    )


def render_idea_comparison(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: object = None,
) -> str:
    materialized = tuple(rows)
    if len(materialized) < 2:
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
            escape_html(operator_route_label(candidate_operator_route(row))),
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
            _time_markup(row.get("expires_at"), expiry=True, now=now),
        )
        body.append(
            '<tr><th scope="row" data-label="Idea">'
            + cells[0]
            + "</th>"
            + "".join(
                f'<td data-label="{escape_html(label)}">{value}</td>'
                for label, value in zip(headers[1:], cells[1:], strict=True)
            )
            + "</tr>"
        )
    head = "".join(f'<th scope="col">{escape_html(value)}</th>' for value in headers)
    idea_label = "idea" if len(materialized) == 1 else "ideas"
    return (
        '<details class="disclosure panel comparison-panel"><summary><span>Compare ideas in matrix</span>'
        f'<span class="filter-chip">{len(materialized)} {idea_label}</span></summary>'
        '<div class="disclosure__body"><div class="table-scroll" role="region" tabindex="0" '
        'aria-label="Scrollable idea comparison"><table class="responsive-table mobile-cards"><caption class="sr-only">'
        f'{len(materialized)} current Decision Radar ideas</caption><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div></div></details>'
    )


def render_idea_filters(query: Mapping[str, str], *, action: str) -> str:
    route_values = (
        "dashboard_watch", "actionable_watch", "high_confidence_watch",
        "rapid_market_anomaly", "fade_exhaustion_review", "risk_watch",
        "calendar_risk", "diagnostic",
    )
    advanced_options = (
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
    primary_fields = [
        '<label class="filter-search"><span>Search symbol or thesis</span>'
        f'<input type="search" name="search" value="{escape_html(query.get("search", ""))}" placeholder="BTC, breakout, listing…"></label>'
    ]
    primary_fields.append(_filter_select("route", "Route", route_values, query))
    sort_selected = query.get("sort", "attention")
    sort_values = (
        ("attention", "Operator attention"), ("actionability_desc", "Actionability · high first"),
        ("evidence_desc", "Evidence · high first"), ("urgency_desc", "Urgency · high first"),
        ("risk_asc", "Risk · low first"), ("risk_desc", "Risk · high first"),
        ("expiry_asc", "Expiry · soonest first"),
    )
    primary_fields.append(
        '<label><span>Sort</span><select name="sort">' + "".join(
            f'<option value="{value}"{(" selected" if value == sort_selected else "")}>{escape_html(label)}</option>'
            for value, label in sort_values
        ) + '</select></label>'
    )
    advanced_fields = [
        _filter_select(name, label, values, query)
        for name, label, values in advanced_options
    ]
    advanced_count = sum(
        1 for name, _label, _values in advanced_options if query.get(name)
    )
    advanced_open = " open" if advanced_count else ""
    active_filter_label = "filter" if advanced_count == 1 else "filters"
    form = (
        f'<form class="filter-panel{(" embedded-filter-panel idea-filters" if action == "/ideas" else "")}" '
        f'method="get" action="{escape_html(action)}" aria-label="Filter and sort ideas"><div class="filter-grid">'
        + "".join(primary_fields)
        + '</div><details class="disclosure filter-advanced"'
        + advanced_open
        + '><summary><span>Advanced filters</span>'
        + f'<span class="filter-chip" aria-label="{advanced_count} advanced {active_filter_label} active">{advanced_count} active</span>'
        + '</summary><div class="disclosure__body"><div class="filter-grid">'
        + "".join(advanced_fields)
        + '</div></div></details><div class="filter-actions"><button class="button button-primary" type="submit">Apply filters</button>'
        f'<a class="button button-quiet" href="{escape_html(action)}">Clear all</a></div></form>'
    )
    if action != "/ideas":
        return form

    active_count = sum(
        1
        for name in ("search", "route", *(item[0] for item in advanced_options))
        if query.get(name)
    ) + (1 if query.get("sort", "attention") != "attention" else 0)
    open_attr = " open" if active_count else ""
    active_label = (
        f"{active_count} active"
        if active_count
        else "All current ideas"
    )
    return (
        '<details class="disclosure filter-disclosure idea-filter-disclosure"'
        + open_attr
        + '><summary><span>Filter &amp; sort ideas</span>'
        f'<span class="disclosure__summary">{escape_html(active_label)}</span></summary>'
        f'<div class="disclosure__body">{form}</div></details>'
    )


def _filter_select(
    name: str,
    label: str,
    values: Iterable[str],
    query: Mapping[str, str],
) -> str:
    selected = query.get(name, "")
    option_html = '<option value="">All</option>' + "".join(
        f'<option value="{escape_html(value)}"{(" selected" if value == selected else "")}>{escape_html(operator_route_label(value) if name == "route" else humanize_enum(value))}</option>'
        for value in values
    )
    return (
        f'<label><span>{escape_html(label)}</span>'
        f'<select name="{escape_html(name)}">{option_html}</select></label>'
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
        and is_canonical_diagnostic_candidate(row)
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
    expired_at_read_time = row.get("_decision_expired_at_read_time") is True
    score_cards = "".join(
        _score_card(label, row.get(field), dimension=dimension, explanation=explanation)
        for label, field, dimension, explanation in (
            (
                "Actionability at evaluation" if expired_at_read_time else "Actionability",
                "actionability_score", "quality",
                "Recorded usefulness at evaluation; this idea is expired." if expired_at_read_time else "Usefulness and timing now — not win probability.",
            ),
            ("Evidence at evaluation" if expired_at_read_time else "Evidence", "evidence_confidence_score", "quality", "Confidence in the recorded explanation — not expected return."),
            ("Risk at evaluation" if expired_at_read_time else "Risk", "risk_score", "risk", "Higher is more risk; the scale is not reversed."),
            ("Urgency at evaluation" if expired_at_read_time else "Urgency", "urgency_score", "urgency", "How quickly the recorded research window could change."),
            ("Chase risk at evaluation" if expired_at_read_time else "Chase risk", "chase_risk_score", "risk", "Risk that the recorded move was already extended."),
        )
    )
    history = _idea_history(snapshot, row)
    baseline_state = str(quality.get("baseline_status") or "missing")
    chart_state = baseline_state if baseline_state in {"warming", "cold"} else ("ready" if history else "missing")
    charts = _market_history_charts(
        history,
        chart_state=chart_state,
        baseline_state=baseline_state,
        turnover_basis=(
            quality.get("volume_zscore_basis")
            or row.get("volume_zscore_basis")
        ),
    )
    context = _decision_context(
        row,
        provenance,
        quality,
        now=snapshot.generation_authority_checked_at,
    )
    context_coverage = _context_coverage(snapshot, row)
    outcome = _outcome_block(snapshot, row)
    feedback_command = (
        f".venv/bin/python main.py --event-feedback-mark {identifier} useful --confirm"
    )
    body = (
        '<p class="back-link"><a href="/ideas">← All ideas</a></p>'
        '<section class="idea-hero panel"><div><p class="eyebrow">Crypto Decision Radar</p>'
        f'<h2>{_idea_hero_label(row, identifier)}</h2>'
        f'<div class="chip-row">{_detail_route_badges(row)}{_status_badge(row.get("directional_bias"), label=_bias_label(row.get("directional_bias")))}'
        f'{_qualified_status_badge("Catalyst", row.get("catalyst_status"))}'
        f'{_qualified_status_badge("Phase", row.get("market_phase"))}</div></div>'
        f'<div class="idea-expiry"><span>Research window</span>{_time_markup(row.get("expires_at"), expiry=True, now=snapshot.generation_authority_checked_at)}</div></section>'
        + (
            '<div class="alert alert-warning"><strong>Historical evaluation snapshot.</strong> '
            'Every score and market/context label below describes evaluation time, not current usefulness.</div>'
            if expired_at_read_time else ""
        )
        + _narrative_grid(row)
        + _primary_calendar_callout(snapshot, row)
        + f'<section class="score-grid" aria-label="Decision scores{" at evaluation" if expired_at_read_time else ""}">{score_cards}</section>'
        + context
        + _evidence_verdict(row)
        + _decision_evidence(row)
        + '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Measured context</p><h2>Market history</h2></div>'
        f'{_status_badge(baseline_state)}</div>{charts}</section>'
        + context_coverage
        + outcome
        + '<details class="technical-details panel"><summary>How to record optional feedback</summary>'
        '<div class="disclosure__body"><p>Feedback is optional and never controls visibility or thresholds. '
        'The dashboard remains GET/HEAD-only; use the explicit confirmed CLI pathway.</p>'
        f'<pre class="copy-value"><code>{escape_html(feedback_command)}</code></pre></div></details>'
        + _technical_details(row, provenance, quality)
    )
    return 200, title, body


def _attention_card(row: Mapping[str, Any], *, now: object = None) -> str:
    identifier = candidate_identifier(row)
    route = candidate_operator_route(row)
    why = _values(row, "why_now", "why_still_worth_reviewing", "supporting_facts")
    scores = "".join(
        _mini_score(label, row.get(field), dimension)
        for label, field, dimension in (
            ("Action", "actionability_score", "quality"),
            ("Evidence", "evidence_confidence_score", "quality"),
            ("Risk", "risk_score", "risk"),
        )
    )
    href = f'/ideas/{quote(identifier, safe="")}'
    return (
        f'<article class="attention-card route-{escape_html(str(route or "unknown"))}">'
        '<header class="attention-card__head"><div>'
        f'<p class="eyebrow">{escape_html(candidate_operator_route_label(row))}</p>'
        f'<h3><a href="{href}">{escape_html(row.get("symbol") or identifier)}</a></h3>'
        f'</div>{_status_badge(row.get("directional_bias"), label=_bias_label(row.get("directional_bias")))}</header>'
        f'<div class="mini-score-grid attention-card__scores">{scores}</div>'
        f'<p class="attention-card__thesis">{escape_html(why[0] if why else "No concise thesis recorded.")}</p>'
        '<footer class="attention-card__footer"><span><small>Research window</small>'
        f'{_time_markup(row.get("expires_at"), expiry=True, now=now)}</span>'
        f'<a class="card-action" href="{href}">Review brief <span aria-hidden="true">→</span></a>'
        '</footer></article>'
    )


def _idea_card(row: Mapping[str, Any], *, now: object = None) -> str:
    identifier = candidate_identifier(row)
    route = candidate_operator_route(row)
    warning_values = _values(row, "decision_warnings", "main_risks")
    card_warning = next((value for value in warning_values if not _generic_safety_note(value)), "")
    why = _values(row, "why_now", "why_still_worth_reviewing", "supporting_facts")
    expiry = _time_markup(row.get("expires_at"), expiry=True, now=now)
    scores = "".join(
        _mini_score(label, row.get(field), dimension)
        for label, field, dimension in (
            ("Actionability", "actionability_score", "quality"),
            ("Evidence", "evidence_confidence_score", "quality"),
            ("Risk", "risk_score", "risk"),
            ("Urgency", "urgency_score", "urgency"),
        )
    )
    return (
        f'<article class="idea-card route-{escape_html(str(route or "unknown"))}">'
        '<div class="idea-card-head"><div>'
        f'<p class="eyebrow">{escape_html(candidate_operator_route_label(row))}</p><h3><a href="/ideas/{quote(identifier, safe="")}">'
        f'{escape_html(row.get("symbol") or identifier)}</a></h3>'
        f'<p class="muted">{escape_html(" + ".join(humanize_enum(value) for value in origin_tokens(row)))}</p></div>'
        f'{_status_badge(row.get("directional_bias"), label=_bias_label(row.get("directional_bias")))}</div>'
        f'<div class="mini-score-grid">{scores}</div>'
        f'<p class="idea-why">{escape_html(why[0] if why else "No concise thesis recorded.")}</p>'
        + _card_sparkline(row)
        + '<div class="idea-meta">'
        f'<span><small>Phase</small>{escape_html(humanize_enum(row.get("market_phase") or row.get("timing_state")))}</span>'
        f'<span><small>Horizon</small>{escape_html(humanize_enum(row.get("preferred_horizon")))}</span>'
        f'<span><small>Expiry</small>{expiry}</span></div>'
        f'<div class="chip-row">{_qualified_status_badge("Catalyst", row.get("catalyst_status"))}'
        f'{_qualified_status_badge("Spread", row.get("spread_status"))}'
        f'{_qualified_status_badge("Tradability", row.get("tradability_status"))}</div>'
        + (f'<p class="card-warning">{escape_html(humanize_reason(card_warning))}</p>' if card_warning else "")
        + f'<a class="card-action" href="/ideas/{quote(identifier, safe="")}">Open decision brief <span aria-hidden="true">→</span></a></article>'
    )


def _idea_hero_label(row: Mapping[str, Any], identifier: str) -> str:
    symbol = str(row.get("symbol") or identifier)
    coin_id = str(row.get("coin_id") or "").strip()
    if not coin_id or coin_id.casefold() == symbol.casefold():
        return escape_html(symbol)
    return f'{escape_html(symbol)} <span>{escape_html(coin_id)}</span>'


def _decision_context(
    row: Mapping[str, Any],
    provenance: Mapping[str, Any],
    quality: Mapping[str, Any],
    *,
    now: object = None,
) -> str:
    route = str(row.get("_dashboard_route") or row.get("radar_route") or "diagnostic")
    if row.get("_decision_expired_at_read_time") is True:
        actionability = "Expired · read-time visibility suppressed"
    elif row.get("radar_actionable") is True:
        actionability = "Operator-actionable research"
    else:
        actionability = {
            "dashboard_watch": "Dashboard-only research",
            "fade_exhaustion_review": "Manual fade / exhaustion review",
            "risk_watch": "Downside-risk review only",
            "calendar_risk": "Scheduled-risk review",
            "diagnostic": "Diagnostic only",
        }.get(route, "Research review only")
    evaluation_suffix = (
        " at evaluation"
        if row.get("_decision_expired_at_read_time") is True
        else ""
    )
    decision_items = [
        ("Primary thesis origin", humanize_enum(row.get("primary_thesis_origin") or row.get("thesis_origin"))),
        ("Thesis origins", " · ".join(humanize_enum(value) for value in origin_tokens(row))),
        ("Operator status", actionability),
        ("Timing" + evaluation_suffix, humanize_enum(row.get("timing_state"))),
        ("Market phase" + evaluation_suffix, humanize_enum(row.get("market_phase"))),
        ("Preferred horizon", humanize_enum(row.get("preferred_horizon"))),
        ("Expires", _friendly_expiry(row.get("expires_at"), now=now)),
        ("Tradability" + evaluation_suffix, humanize_enum(row.get("tradability_status"))),
        ("Spread" + evaluation_suffix, humanize_enum(row.get("spread_status"))),
        ("Market freshness" + evaluation_suffix, humanize_enum(row.get("market_data_freshness") or row.get("market_context_freshness_status"))),
    ]
    if row.get("_decision_read_time_reason") not in (None, "", UNAVAILABLE):
        decision_items.append((
            "Read-time safety reason",
            humanize_reason(row.get("_decision_read_time_reason")),
        ))
    provenance_items = (
        ("Data mode", humanize_enum(provenance.get("candidate_source_mode") or provenance.get("data_mode"))),
        ("Market provider", humanize_enum(provenance.get("provider"))),
        ("Baseline", humanize_enum(quality.get("baseline_status"))),
        ("Liquidity basis", humanize_enum(quality.get("liquidity_basis"))),
        ("Volume basis", humanize_enum(quality.get("volume_zscore_basis"))),
        ("Execution quality", humanize_enum(quality.get("spread_basis") or row.get("spread_status"))),
    )
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Decision context</p>'
        '<h2>How to read this idea</h2></div></div>'
        + _definition_grid(tuple(decision_items))
        + '<details class="disclosure data-provenance"><summary>Data provenance and measurement quality</summary>'
        '<div class="disclosure__body">'
        + _definition_grid(provenance_items)
        + '</div></details></section>'
    )


def _friendly_expiry(value: object, *, now: object = None) -> str:
    presented = present_time(value, now=now)
    if not presented.available:
        return UNAVAILABLE
    return f"{presented.local_label} · {presented.relative_label}"


def _narrative_grid(row: Mapping[str, Any]) -> str:
    recorded_risks = tuple(
        value for value in _values(row, "main_risks", "decision_warnings")
        if not _generic_safety_note(value)
    )
    primary_blocks = (
        ("Why now", _values(row, "why_now", "why_still_worth_reviewing"), "info"),
        (
            "Main risks",
            _dedupe_risk_values(recorded_risks),
            "warning",
        ),
    )
    checklist_blocks = (
        ("What confirms", _values(row, "radar_what_confirms", "what_confirms"), "positive"),
        ("What invalidates", _values(row, "radar_what_invalidates", "what_invalidates"), "danger"),
    )
    research_blocks = (
        ("Missing information", _values(row, "missing_information", "decision_missing_data"), "neutral"),
        ("Supporting facts", _values(row, "supporting_facts"), "neutral"),
        ("Recorded risk detail", recorded_risks, "neutral"),
    )
    return (
        '<section class="panel decision-thesis"><div class="section-heading"><div>'
        '<p class="eyebrow">Decision thesis</p><h2>What matters before the scores</h2></div></div>'
        '<div class="narrative-grid">'
        + "".join(_narrative_card(*block) for block in primary_blocks)
        + '</div><details class="disclosure decision-checklist"><summary><span>Confirmation and invalidation checklist</span>'
        '<span class="disclosure__summary">Review before acting</span></summary>'
        '<div class="disclosure__body"><div class="narrative-grid">'
        + "".join(_narrative_card(*block) for block in checklist_blocks)
        + '</div></div></details><details class="disclosure thesis-notes"><summary>Supporting research notes</summary>'
        '<div class="disclosure__body"><div class="narrative-grid">'
        + "".join(_narrative_card(*block) for block in research_blocks)
        + '</div></div></details></section>'
    )


def _narrative_card(title: str, values: tuple[str, ...], tone: str) -> str:
    content = "".join(
        f"<li>{escape_html(_narrative_text(value))}</li>" for value in values
    )
    return (
        f'<section class="narrative-card tone-{tone}"><h2>{escape_html(title)}</h2>'
        + (f"<ul>{content}</ul>" if content else '<p class="muted">No item recorded.</p>')
        + "</section>"
    )


def _generic_safety_note(value: str) -> bool:
    token = str(value).casefold()
    return (
        "not a trade instruction" in token
        or "research only" in token
        or "human decision" in token
    )


def _dedupe_risk_values(values: tuple[str, ...]) -> tuple[str, ...]:
    """Keep one operator-facing explanation per repeated risk concept."""

    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = " ".join(str(value).casefold().split())
        concept = _risk_concept(token)
        key = concept or token.rstrip(".")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return tuple(deduped)


def _risk_concept(token: str) -> str | None:
    if "catalyst" in token and ("unknown" in token or "source" in token):
        return "catalyst_support"
    if "spread" in token or "execution-quality" in token or "execution quality" in token:
        return "execution_quality"
    if "baseline" in token and ("warm" in token or "temporal" in token):
        return "temporal_baseline"
    if "turnover" in token:
        return "market_turnover"
    if "confirmation gate" in token:
        return "market_confirmation"
    return None


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


def _context_coverage(snapshot: DashboardSnapshot, row: Mapping[str, Any]) -> str:
    source_url = str(
        row.get("source_url")
        or row.get("latest_source_url")
        or row.get("url")
        or ""
    ).strip()
    calendar_rows = _nearby_calendar_rows(snapshot, row)
    rsi_context = row.get("rsi_context")
    rsi_references = _values(row, "rsi_context_references")
    catalyst_status = str(row.get("catalyst_status") or "").strip().casefold()
    catalyst_present = catalyst_status not in {
        "",
        "unknown",
        "unavailable",
        "not_recorded",
    } and any(
        row.get(field) not in (None, "", [], {})
        for field in (
            "opportunity_type",
            "final_route_after_quality_gate",
            "route",
            "source_strength",
        )
    )
    source_attached = bool(source_url and safe_external_href(source_url) is not None)
    attached_count = sum(
        (
            source_attached,
            bool(calendar_rows),
            isinstance(rsi_context, Mapping) or bool(rsi_references),
            catalyst_present,
        )
    )
    return (
        '<details class="disclosure panel context-coverage"><summary><span>Context coverage</span>'
        f'<span class="filter-chip">{attached_count} of 4 layers attached</span></summary>'
        '<div class="disclosure__body"><p class="muted">Supporting source, calendar, technical, and catalyst layers. '
        'Unavailable layers remain explicit and do not imply evidence.</p>'
        '<div class="context-coverage__grid">'
        + _source_block(row)
        + _nearby_calendar(snapshot, row, nearby=calendar_rows)
        + _technical_context(row)
        + _catalyst_context(row)
        + '</div></div></details>'
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
        '<section class="context-coverage__section source-context"><div class="section-heading"><div>'
        '<p class="eyebrow">Evidence source detail</p><h2>Latest recorded source</h2>'
        f'</div></div><p>{source}</p></section>'
    )


def _evidence_verdict(row: Mapping[str, Any]) -> str:
    independence = event_source_independence.validated_source_independence_container(
        row
    )
    attribution = _validated_catalyst_attribution(row)
    raw_count = _count_value(independence.get("raw_document_count"))
    if raw_count is None:
        raw_count = _first_count(row, "source_update_count", "source_count")
    accepted_count = _first_count(
        row,
        "evidence_acquisition_accepted_count",
        "accepted_evidence_count",
    )
    assessed = bool(independence)
    metrics = (
        ("Raw sources", _count_label(raw_count, unavailable="Unavailable")),
        (
            "Accepted evidence rows (not corroboration)",
            _count_label(accepted_count, unavailable="0"),
        ),
        (
            "Content clusters",
            _count_label(
                _count_value(independence.get("content_cluster_count"))
                if assessed
                else None
            ),
        ),
        (
            "Independent evidence units",
            _count_label(
                _count_value(independence.get("independent_evidence_count"))
                if assessed
                else None
            ),
        ),
        (
            "Additional independent corroborations",
            _count_label(
                _count_value(independence.get("independent_corroboration_count"))
                if assessed
                else None
            ),
        ),
        (
            "Syndicated copies collapsed",
            _count_label(_collapsed_copy_count(independence) if assessed else None),
        ),
        ("Catalyst timing", _catalyst_timing_label(attribution)),
        ("Causal eligibility", _causal_eligibility_label(attribution)),
        ("Source authority", _source_authority_label(attribution)),
        (
            "Evidence errors",
            _bounded_evidence_errors(
                row,
                source_independence=independence,
                attribution=attribution,
            ),
        ),
    )
    return (
        '<section class="panel evidence-verdict"><div class="section-heading"><div>'
        '<p class="eyebrow">Evidence reality</p><h2>Evidence verdict</h2></div>'
        f'{_status_badge("assessed" if assessed else "unassessed")}</div>'
        '<p>Accepted evidence is a validation count, not independent corroboration. '
        'Only validated content-and-origin units raise the corroboration count.</p>'
        + _definition_grid(metrics)
        + '</section>'
    )


def _validated_catalyst_attribution(row: Mapping[str, Any]) -> dict[str, Any]:
    if (
        row.get("catalyst_attribution_rejected") is True
        or _values(row, "catalyst_attribution_rejection_reasons")
    ):
        return {}
    supplied: list[Mapping[str, Any]] = []
    single = row.get("catalyst_attribution")
    if single not in (None, "", {}, []):
        if not isinstance(single, Mapping):
            return {}
        supplied.append(single)
    multiple = row.get("catalyst_attributions")
    if multiple not in (None, "", {}, []):
        if not isinstance(multiple, Iterable) or isinstance(
            multiple, (str, bytes, Mapping)
        ):
            return {}
        for value in multiple:
            if not isinstance(value, Mapping):
                return {}
            supplied.append(value)
    if not supplied or any(
        event_catalyst_attribution.validate_contract(value) for value in supplied
    ):
        return {}
    return dict(supplied[0])


def _collapsed_copy_count(contract: Mapping[str, Any]) -> int:
    documents = contract.get("documents")
    if not isinstance(documents, list):
        return 0
    return sum(
        1
        for document in documents
        if isinstance(document, Mapping)
        and document.get("match_kind") in {"exact", "near_duplicate"}
    )


def _catalyst_timing_label(attribution: Mapping[str, Any]) -> str:
    return humanize_enum(attribution.get("temporal_relation") or "not_assessed")


def _causal_eligibility_label(attribution: Mapping[str, Any]) -> str:
    if not attribution:
        return "Not assessed"
    if attribution.get("causal_eligible") is True:
        return "Eligible"
    if attribution.get("evidence_use") == "disproof":
        return "Disproof"
    return "Context only"


def _source_authority_label(attribution: Mapping[str, Any]) -> str:
    if not attribution:
        return "Unassessed"
    source_class = str(attribution.get("source_class") or "").casefold()
    if attribution.get("source_authority_verified") is True:
        if source_class.startswith("official_"):
            return "Official"
        if source_class.startswith("structured_"):
            return "Structured"
    return "Context"


def _bounded_evidence_errors(
    row: Mapping[str, Any],
    *,
    source_independence: Mapping[str, Any],
    attribution: Mapping[str, Any],
) -> str:
    values = [
        *_values(row, "source_independence_errors"),
        *_values(row, "catalyst_attribution_rejection_reasons"),
    ]
    if (
        not source_independence
        and row.get("source_independence") not in (None, "", {}, [])
        and not _values(row, "source_independence_errors")
        and "source_independence_invalid" not in values
    ):
        values.append("source_independence_invalid")
    if (
        not attribution
        and (
            row.get("catalyst_attribution") not in (None, "", {}, [])
            or row.get("catalyst_attributions") not in (None, "", {}, [])
        )
        and "catalyst_attribution_invalid" not in values
    ):
        values.append("catalyst_attribution_invalid")
    clean = [humanize_reason(" ".join(value.split())[:160]) for value in values]
    if not clean:
        return "No errors recorded"
    visible = clean[:4]
    hidden = len(clean) - len(visible)
    return "; ".join(visible) + (f"; +{hidden} more" if hidden else "")


def _count_value(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _first_count(row: Mapping[str, Any], *fields: str) -> int | None:
    for field in fields:
        value = _count_value(row.get(field))
        if value is not None:
            return value
    return None


def _count_label(value: int | None, *, unavailable: str = "Not assessed") -> str:
    return str(value) if value is not None else unavailable


def _narrative_text(value: str) -> str:
    text = str(value).strip()
    if not text:
        return UNAVAILABLE
    if text.casefold().startswith("nearby calendar risk:"):
        raw_items = text.split(":", 1)[1].split(",")
        seen: set[str] = set()
        items: list[str] = []
        for item in raw_items:
            token = item.strip().casefold()
            if not token or token in seen:
                continue
            seen.add(token)
            items.append(humanize_enum(item.strip()))
        return "Nearby calendar risk: " + (", ".join(items) or UNAVAILABLE)
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


def _nearby_calendar_rows(
    snapshot: DashboardSnapshot,
    row: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
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
    return tuple(nearby)


def _nearby_calendar(
    snapshot: DashboardSnapshot,
    row: Mapping[str, Any],
    *,
    nearby: tuple[Mapping[str, Any], ...] | None = None,
) -> str:
    if nearby is None:
        nearby = _nearby_calendar_rows(snapshot, row)
    if not nearby:
        return '<section class="context-coverage__section calendar-context"><div class="section-heading"><div><p class="eyebrow">Scheduled risk</p><h2>Nearby calendar events</h2></div></div><div class="empty-inline">No exact-generation calendar event is attached to this idea.</div></section>'
    cards = []
    for event in nearby:
        timing = present_calendar_window(
            scheduled_at=event.get("scheduled_at"), window_start=event.get("window_start"),
            window_end=event.get("window_end"), time_certainty=event.get("time_certainty"),
            now=snapshot.generation_authority_checked_at,
        )
        cards.append(
            '<article class="calendar-mini"><div>'
            f'<strong>{escape_html(event.get("title") or "Scheduled event")}</strong>'
            f'<p>{escape_html(timing.label)} · {escape_html(timing.relative_label)}</p></div>'
            f'{_status_badge(event.get("importance"))}</article>'
        )
    return '<section class="context-coverage__section calendar-context"><div class="section-heading"><div><p class="eyebrow">Scheduled risk</p><h2>Nearby calendar events</h2></div></div>' + "".join(cards) + '</section>'


def _primary_calendar_callout(
    snapshot: DashboardSnapshot,
    row: Mapping[str, Any],
) -> str:
    route = str(row.get("_dashboard_route") or row.get("radar_route") or "")
    if route != "calendar_risk":
        return ""
    nearby = _nearby_calendar_rows(snapshot, row)
    if not nearby:
        return (
            '<section class="panel primary-calendar-callout"><p class="eyebrow">Scheduled risk</p>'
            '<h2>Calendar evidence is missing</h2><p>The route references scheduled risk, but no '
            'exact-generation event row is attached. Treat this as an evidence gap.</p></section>'
        )
    cards = []
    for event in nearby[:3]:
        timing = present_calendar_window(
            scheduled_at=event.get("scheduled_at"),
            window_start=event.get("window_start"),
            window_end=event.get("window_end"),
            time_certainty=event.get("time_certainty"),
            now=snapshot.generation_authority_checked_at,
        )
        cards.append(
            '<article class="calendar-mini"><div>'
            f'<strong>{escape_html(event.get("title") or "Scheduled event")}</strong>'
            f'<p>{escape_html(timing.label)} · {escape_html(timing.relative_label)}</p></div>'
            f'{_status_badge(event.get("importance"))}</article>'
        )
    return (
        '<section class="panel primary-calendar-callout"><div class="section-heading"><div>'
        '<p class="eyebrow">Scheduled risk tied to this decision</p>'
        '<h2>Calendar context before the scores</h2></div>'
        '<a href="/calendar">Open calendar</a></div>'
        + "".join(cards)
        + '</section>'
    )


def _technical_context(row: Mapping[str, Any]) -> str:
    context = row.get("rsi_context")
    refs = _values(row, "rsi_context_references")
    if not isinstance(context, Mapping) and not refs:
        return '<section class="context-coverage__section rsi-context"><div class="section-heading"><div><p class="eyebrow">Technical context</p><h2>RSI and setup evidence</h2></div></div><div class="empty-inline">No exact RSI context is attached. No RSI scan, alert, or write is performed by this page.</div></section>'
    values = []
    if isinstance(context, Mapping):
        for key in ("setup", "timeframe", "rsi", "regime", "trend", "edge_status"):
            if context.get(key) not in (None, ""):
                values.append((humanize_enum(key), humanize_enum(context.get(key))))
    if refs:
        values.append(("Evidence references", ", ".join(refs)))
    return '<section class="context-coverage__section rsi-context"><div class="section-heading"><div><p class="eyebrow">Technical context</p><h2>RSI and setup evidence</h2></div></div>' + _definition_grid(values) + '<p class="muted">Read-only context; no RSI writes, alerts, paper trades, or execution.</p></section>'


def _catalyst_context(row: Mapping[str, Any]) -> str:
    blockers = _values(row, "opportunity_type_why_not_alertable", "why_not_alertable")
    return (
        '<section class="context-coverage__section catalyst-context"><div class="section-heading"><div><p class="eyebrow">Catalyst Radar classification</p>'
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
        layer = dashboard_layer_coverage_by_key(snapshot)["outcomes"]
        authority = str(snapshot.current_outcomes_metadata.get("authority") or "")
        fingerprint_verified = (
            authority == "current_generation_fingerprint_verified"
            and bool(snapshot.current_outcomes_metadata.get("sha256"))
        )
        admitted = layer.status in {"healthy_nonempty", "healthy_empty"} or (
            layer.status == "degraded" and fingerprint_verified
        )
        message = (
            "A required outcome placeholder is missing from the verified exact-generation outcome artifact."
            if admitted
            else "The outcome layer is unavailable for this generation; no pending or matured state is inferred."
        )
        return (
            '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Learning loop</p>'
            '<h2>Outcome</h2></div></div><div class="empty-inline">'
            f'{escape_html(message)}</div></section>'
        )
    items = (
        ("State", humanize_enum(outcome.get("outcome_status") or outcome.get("maturation_state"))),
        ("Route cohort", operator_route_label(outcome.get("radar_route") or outcome.get("route"))),
        ("Actionability cohort", _score_cohort_label(outcome.get("actionability_score_cohort"))),
        ("Evidence cohort", _score_cohort_label(outcome.get("evidence_confidence_score_cohort"))),
        ("Risk cohort", _score_cohort_label(outcome.get("risk_score_cohort"))),
    )
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Learning loop</p><h2>Outcome</h2></div></div>' + _definition_grid(items) + '<p class="sample-warning">One idea cannot establish statistical edge. Outcomes remain descriptive until a meaningful sample matures.</p></section>'


def _technical_details(
    row: Mapping[str, Any],
    provenance: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> str:
    source_independence = (
        event_source_independence.validated_source_independence_container(row)
    )
    catalyst_attribution = _validated_catalyst_attribution(row)
    values = (
        ("Candidate ID", candidate_identifier(row)),
        ("Symbol", row.get("symbol")),
        ("Coin ID", row.get("coin_id")),
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
        ("Read-time safety reason code", row.get("_decision_read_time_reason")),
        ("Direct feature count", quality.get("direct_feature_count")),
        ("Proxy feature count", quality.get("proxy_feature_count")),
        (
            "Source-independence contract digest",
            source_independence.get("contract_digest"),
        ),
        (
            "Catalyst-attribution digest",
            catalyst_attribution.get("attribution_digest"),
        ),
    )
    return (
        '<details class="technical-details panel"><summary>Technical lineage, contract digests, and raw identifiers</summary>'
        '<p class="muted">Full evidence contracts remain in exact-generation artifacts and are not expanded in the operator view.</p>'
        + _definition_grid(values, raw=True)
        + '</details>'
    )


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


def _status_badge(value: object, *, label: str | None = None) -> str:
    status = semantic_status(value)
    return f'<span class="status-badge tone-{escape_html(status.tone)}"><i aria-hidden="true"></i>{escape_html(label or status.label)}</span>'


def _bias_label(value: object) -> str:
    return {
        "long": "Long bias",
        "short": "Short bias",
        "risk": "Downside risk",
        "neutral": "Neutral bias",
    }.get(str(value or "").strip().casefold(), humanize_enum(value))


def _detail_route_badges(row: Mapping[str, Any]) -> str:
    if row.get("_decision_expired_at_read_time") is True:
        canonical_route = candidate_operator_route(row)
        return (
            _status_badge("expired", label="Expired")
            + _status_badge(
                canonical_route,
                label=f"{operator_route_label(canonical_route)} at evaluation",
            )
        )
    route = candidate_operator_route(row)
    return _status_badge(route, label=operator_route_label(route))


def _qualified_status_badge(name: str, value: object) -> str:
    label = humanize_enum(value)
    return _status_badge(value, label=f"{name} {label.casefold()}")


def _score_cohort_label(value: object) -> str:
    text = str(value or "").strip()
    parts = text.split("_")
    if len(parts) == 2 and all(part.replace(".", "", 1).isdigit() for part in parts):
        return f"{parts[0]}–{parts[1]}"
    return humanize_enum(value)


def _time_markup(
    value: object,
    *,
    expiry: bool = False,
    now: object = None,
) -> str:
    presented = present_time(value, now=now)
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
