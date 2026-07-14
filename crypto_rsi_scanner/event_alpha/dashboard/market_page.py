"""Market Radar page over one exact Decision Radar generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from ..radar import market_units as event_market_units
from .charts import render_activity_chart, render_price_chart
from .components import HtmlFragment, disclosure, escape_html
from .loader import candidate_identifier
from .layer_coverage import dashboard_layer_coverage_by_key
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_currency,
    format_number,
    format_percent,
    humanize_enum,
    present_turnover_series,
    present_time,
    semantic_status,
)
from .view_data import dashboard_query, filter_sort_observations, finite_number


def render_market_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    filters = dashboard_query(query)
    candidates = _candidate_by_asset(snapshot)
    observations = filter_sort_observations(snapshot.current_market_observations, filters)
    if not snapshot.current_market_observations:
        market_layer = dashboard_layer_coverage_by_key(snapshot)["market"]
        verified_empty = market_layer.status == "healthy_empty"
        next_step = "" if verified_empty else (
            '<section class="panel market-next-step"><p class="eyebrow">Next step</p>'
            '<h2>Verify acquisition coverage</h2>'
            '<p>Confirm the exact market-layer receipt and generation authority before relying '
            'on this page for current market context.</p>'
            '<p><a class="button button-primary" href="/health#product-layer-coverage">'
            'Review market-layer health</a></p></section>'
        )
        return (
            _market_hero(snapshot, ())
            + next_step
            + _market_explanation(
                snapshot,
                spread_count=0,
                baselines=Counter(),
            )
            + _anomaly_cards(snapshot)
        )
    if filters.get("sort") in (None, "", "decision_first"):
        observations = tuple(sorted(
            observations,
            key=lambda row: 0 if _asset_key(row) in candidates else 1,
        ))
    spread_count = sum(1 for row in snapshot.current_market_observations if _spread_observed(row))
    baselines = Counter(_baseline_status(row) for row in snapshot.current_market_observations)
    metrics = (
        ("Assets evaluated", len(snapshot.current_market_observations), "Exact current scan"),
        ("Anomalies", len(snapshot.current_market_anomalies), "Scanner evidence"),
        ("Decision ideas", len(snapshot.visible_current_candidates), "Current operator-visible rows"),
        ("Spread verified", f"{spread_count}/{len(snapshot.current_market_observations)}", "Execution quality"),
        ("Warm baselines", baselines.get("warm", 0), f"{baselines.get('warming', 0)} warming"),
    )
    hero = _market_hero(snapshot, observations) + (
        '<div class="metric-grid market-metrics">' + "".join(_metric(*item) for item in metrics) + '</div>'
    )
    controls = _market_filters(filters)
    table = _market_table(
        observations,
        candidates,
        now=snapshot.generation_authority_checked_at,
    )
    mobile_list = _market_mobile_list(
        observations,
        candidates,
        now=snapshot.generation_authority_checked_at,
    )
    explanation = _market_explanation(
        snapshot,
        spread_count=spread_count,
        baselines=baselines,
    )
    charts = _representative_charts(snapshot, observations)
    anomaly_evidence = _anomaly_cards(snapshot)
    lead_evidence = (
        (anomaly_evidence if snapshot.current_market_anomalies else "")
        + charts
    )
    trailing_evidence = "" if snapshot.current_market_anomalies else anomaly_evidence
    return (
        hero
        + controls
        + lead_evidence
        + table
        + mobile_list
        + explanation
        + trailing_evidence
    )


def _market_hero(
    snapshot: DashboardSnapshot,
    observations: tuple[Mapping[str, Any], ...],
) -> str:
    total = len(snapshot.current_market_observations)
    market_layer = dashboard_layer_coverage_by_key(snapshot)["market"]
    ideas = len(snapshot.visible_current_candidates)
    shown = len(observations)
    if total and ideas:
        heading = f"{total} {_plural(total, 'asset')} evaluated · {ideas} Decision {_plural(ideas, 'idea')}"
        context = (
            "Exact-generation layer counts; ideas may originate from other evidence layers. "
        )
    elif total:
        heading = f"{total} {_plural(total, 'asset')} evaluated · no Decision idea qualified"
        context = "The completed scan is healthy evidence even when canonical gates retain zero ideas. "
    elif ideas:
        heading = f"{ideas} Decision {_plural(ideas, 'idea')} · market scan unavailable"
        context = (
            "The ideas may originate from other canonical evidence layers, so this page does not "
            "invent market context. "
        )
    elif market_layer.status == "healthy_empty":
        heading = "Market scan complete · no in-scope observations retained"
        context = (
            "The exact acquisition receipt is complete and verified empty. "
        )
    else:
        heading = "No exact market evidence is attached to this generation"
        context = "Inspect System Health for acquisition and generation authority before relying on market context. "
    if total and shown != total:
        visibility = f"Showing {shown} of {total} exact observations after filters. "
    elif total:
        visibility = f"All {total} exact observations shown. "
    else:
        visibility = ""
    methodology = (
        "CoinGecko volume and turnover are liquidity proxies; unavailable spread caps actionable routes."
        if total
        else "No proxy market values, spread claims, or market history are inferred."
    )
    return (
        '<section class="page-intro"><div><p class="eyebrow">Exact-generation market scan</p>'
        f'<h2>{escape_html(heading)}</h2><p>{escape_html(visibility + context)}'
        f'{escape_html(methodology)}</p></div></section>'
    )


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else singular + "s"


def _market_explanation(
    snapshot: DashboardSnapshot,
    *,
    spread_count: int,
    baselines: Counter[str],
) -> str:
    return (
        '<details class="disclosure market-explanation"><summary>'
        '<span>How this market scan was qualified</span>'
        '<span class="disclosure__summary">Data quality and row accounting</span>'
        '</summary><div class="disclosure__body">'
        + _quality_banner(snapshot, spread_count=spread_count, baselines=baselines)
        + _layer_accounting(snapshot)
        + '</div></details>'
    )


def _layer_accounting(snapshot: DashboardSnapshot) -> str:
    generation = snapshot.market_generation
    ledger = snapshot.current_request_ledger
    raw = _first_finite(
        generation.get("raw_market_row_count"),
        ledger.get("raw_market_row_count"),
        ledger.get("result_count"),
    )
    selected = _first_finite(
        generation.get("selected_market_row_count"),
        ledger.get("selected_market_row_count"),
    )
    integrated = finite_number(generation.get("candidate_count"))
    market_funnel_receipt = (
        generation.get("row_type") == "event_market_no_send_generation"
        or raw is not None
        or selected is not None
    )
    stages = (
        ("Provider rows", _count_label(raw), "Bounded response"),
        ("Selected universe", _count_label(selected), "Top-liquid selection"),
        ("Exact observations", str(len(snapshot.current_market_observations)), "Fingerprint-bound"),
        ("Anomaly evidence", str(len(snapshot.current_market_anomalies)), "Scanner qualification"),
        ("Integrated candidates", _count_label(integrated), "All canonical candidate rows"),
        ("Canonical candidates", str(len(snapshot.current_candidates)), "All routes, including diagnostics"),
    )
    selected_count = int(selected) if selected is not None and selected >= 0 else None
    if not market_funnel_receipt:
        interpretation = (
            "This integrated generation has no market-only funnel receipt. Operator ideas may originate "
            "from catalyst, technical, derivatives, on-chain, fundamental, or macro evidence, so the "
            "dashboard shows these as independent layer counts and does not infer a causal chain."
        )
    elif selected_count == len(snapshot.current_market_observations):
        interpretation = (
            f"All {selected_count} selected assets survive into the exact observation layer. "
            "Later reductions are scanner qualification and canonical consolidation—not a dashboard "
            "data-loss gap."
        )
    elif selected_count is None:
        interpretation = (
            "The selected-universe receipt is unavailable. Exact observation counts remain visible, "
            "but the dashboard does not infer the missing stage."
        )
    else:
        interpretation = (
            f"The selected receipt records {selected_count} rows while the exact observation layer has "
            f"{len(snapshot.current_market_observations)}. Review System Health before treating the funnel as complete."
        )
    items = []
    for index, (label, value, detail) in enumerate(stages):
        if index and market_funnel_receipt:
            items.append('<span class="funnel-arrow" aria-hidden="true">→</span>')
        items.append(
            '<article class="funnel-step">'
            f'<span>{escape_html(label)}</span><strong>{escape_html(value)}</strong>'
            f'<small>{escape_html(detail)}</small></article>'
        )
    return (
        '<section class="panel"><div class="section-heading"><div>'
        '<p class="eyebrow">Layer accounting</p><h2>'
        + ("Where the rows went" if market_funnel_receipt else "Independent layer counts")
        + '</h2>'
        '</div></div><div class="layer-funnel" aria-label="'
        + ("Market-to-decision row funnel" if market_funnel_receipt else "Independent integrated layer counts")
        + '">'
        + "".join(items)
        + f'</div><p class="funnel-interpretation">{escape_html(interpretation)}</p></section>'
    )


def _count_label(value: float | None) -> str:
    return str(max(0, int(value))) if value is not None and value.is_integer() else format_number(value)


def _first_finite(*values: object) -> float | None:
    for value in values:
        number = finite_number(value)
        if number is not None:
            return number
    return None


def _market_filters(query: Mapping[str, str]) -> str:
    search = escape_html(query.get("search", ""))
    selects = []
    for name, label, values in (
        ("freshness", "Freshness", ("fresh", "warming", "stale", "unknown")),
        ("spread", "Spread", ("verified_good", "verified_acceptable", "verified_wide", "unavailable", "stale")),
        ("data_mode", "Data mode", ("live", "live_no_send", "fixture", "artifact_replay", "cached")),
    ):
        selected = query.get(name, "")
        options = '<option value="">All</option>' + "".join(
            f'<option value="{value}"{(" selected" if selected == value else "")}>{escape_html(humanize_enum(value))}</option>'
            for value in values
        )
        selects.append(f'<label><span>{label}</span><select name="{name}">{options}</select></label>')
    sort = query.get("sort", "decision_first")
    sort_options = "".join(
        f'<option value="{value}"{(" selected" if sort == value else "")}>{escape_html(label)}</option>'
        for value, label in (
            ("decision_first", "Decision ideas first"),
            ("return_24h_desc", "24h return"), ("return_4h_desc", "4h return"),
            ("return_1h_desc", "1h return"), ("volume_desc", "Volume"),
            ("turnover_desc", "Turnover"), ("market_cap_desc", "Market cap"),
        )
    )
    active_advanced = sum(
        1 for name in ("freshness", "spread", "data_mode") if query.get(name)
    )
    advanced_open = " open" if active_advanced else ""
    form = (
        '<form class="filter-panel embedded-filter-panel market-filters" method="get" action="/market-radar"><div class="filter-grid">'
        f'<label class="filter-search"><span>Search asset</span><input type="search" name="search" value="{search}" placeholder="BTC, ETH, SOL…"></label>'
        + f'<label><span>Sort</span><select name="sort">{sort_options}</select></label></div>'
        '<details class="disclosure filter-advanced"'
        + advanced_open
        + '><summary><span>Market filters</span>'
        + f'<span class="filter-chip">{active_advanced} active</span></summary>'
        + '<div class="disclosure__body"><div class="filter-grid">'
        + "".join(selects)
        + '</div></div></details><div class="filter-actions">'
        '<button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/market-radar">Clear</a></div></form>'
    )
    active_count = active_advanced + int(bool(query.get("search"))) + int(
        sort != "decision_first"
    )
    return str(disclosure(
        "Search, sort, and filter assets",
        HtmlFragment(form),
        summary=f"{active_count} active",
        open=bool(active_count),
        css_class="filter-disclosure market-filter-disclosure",
    ))


def _market_table(
    observations: tuple[Mapping[str, Any], ...],
    candidates: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    now: object = None,
) -> str:
    if not observations:
        return (
            '<div class="empty-state"><h3>No market observations match this view</h3>'
            '<p>Clear the selected filters, or review exact acquisition evidence in System Health.</p>'
            '<p class="empty-state__action"><a href="/health#product-layer-coverage">Review market-layer health</a></p></div>'
        )
    headers = (
        "Asset", "Decision route", "Price", "4h", "24h", "Volume",
        "Turnover", "Baseline", "Spread", "Freshness",
    )
    rows = []
    for row in observations:
        key = _asset_key(row)
        candidate = candidates.get(key, {})
        route_html = _decision_route(candidate)
        unit = str(row.get("return_unit") or "percent_points")
        quality = _quality(row)
        turnover = (
            row.get("volume_to_market_cap")
            if row.get("volume_to_market_cap") is not None
            else row.get("turnover_24h")
        )
        symbol = row.get("symbol") or row.get("coin_id") or UNAVAILABLE
        evidence_items = (
            ("Coin ID", escape_html(row.get("coin_id") or UNAVAILABLE)),
            ("1h move", _return(row.get("return_1h"), _return_unit(row, "return_1h", unit))),
            ("vs BTC 4h", _return(row.get("relative_return_vs_btc_4h"), _return_unit(row, "relative_return_vs_btc_4h", unit))),
            ("vs ETH 4h", _return(row.get("relative_return_vs_eth_4h"), _return_unit(row, "relative_return_vs_eth_4h", unit))),
            (
                "Volume signal",
                f'{escape_html(format_number(row.get("volume_zscore_24h"), decimals=2))}'
                f'<small>{escape_html(humanize_enum(row.get("volume_zscore_basis") or quality.get("volume_zscore_basis")))}</small>',
            ),
            ("Liquidity basis", escape_html(humanize_enum(row.get("liquidity_basis") or quality.get("liquidity_basis")))),
        )
        evidence = "".join(
            f'<dt>{escape_html(label)}</dt><dd>{value}</dd>'
            for label, value in evidence_items
        )
        cells = (
            '<div class="market-asset-heading">'
            f'<strong>{escape_html(symbol)}</strong>'
            '<details class="market-row-details"><summary '
            f'aria-label="View {escape_html(symbol)} asset context">Context</summary>'
            f'<dl>{evidence}</dl></details></div>',
            route_html,
            escape_html(format_currency(row.get("price"), compact=False, decimals=_price_decimals(row.get("price")))),
            _return(row.get("return_4h"), _return_unit(row, "return_4h", unit)),
            _return(row.get("return_24h"), _return_unit(row, "return_24h", unit)),
            escape_html(format_currency(row.get("volume_24h"))),
            escape_html(format_percent(turnover, unit="fraction", decimals=1)),
            _state_badge(_baseline_status(row)),
            _state_badge(row.get("spread_status") or quality.get("spread_basis")),
            _freshness(row, now=now),
        )
        rows.append(
            '<tr><th scope="row" data-label="Asset">'
            + cells[0]
            + '</th>'
            + "".join(
                f'<td data-label="{escape_html(label)}">{value}</td>'
                for label, value in zip(headers[1:], cells[1:], strict=True)
            ) + '</tr>'
        )
    head = "".join(f'<th scope="col">{escape_html(label)}</th>' for label in headers)
    return (
        '<section class="panel market-desktop-table"><div class="section-heading"><div><p class="eyebrow">Cross-sectional view</p>'
        '<h2>Market comparison</h2></div></div><div class="table-scroll" role="region" tabindex="0" '
        'aria-label="Scrollable market comparison"><table class="responsive-table market-table">'
        f'<caption class="sr-only">{len(observations)} exact market observations</caption>'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )


def _market_mobile_list(
    observations: tuple[Mapping[str, Any], ...],
    candidates: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    now: object = None,
) -> str:
    if not observations:
        return ""
    items = []
    for row in observations:
        candidate = candidates.get(_asset_key(row), {})
        unit = str(row.get("return_unit") or "percent_points")
        quality = _quality(row)
        turnover = (
            row.get("volume_to_market_cap")
            if row.get("volume_to_market_cap") is not None
            else row.get("turnover_24h")
        )
        symbol = row.get("symbol") or row.get("coin_id") or UNAVAILABLE
        coin_id = row.get("coin_id") or "Canonical coin id unavailable"
        details = (
            ("Coin ID", escape_html(coin_id)),
            ("1h move", _return(row.get("return_1h"), _return_unit(row, "return_1h", unit))),
            ("4h move", _return(row.get("return_4h"), _return_unit(row, "return_4h", unit))),
            (
                "vs BTC 4h",
                _return(
                    row.get("relative_return_vs_btc_4h"),
                    _return_unit(row, "relative_return_vs_btc_4h", unit),
                ),
            ),
            (
                "vs ETH 4h",
                _return(
                    row.get("relative_return_vs_eth_4h"),
                    _return_unit(row, "relative_return_vs_eth_4h", unit),
                ),
            ),
            ("24h volume", escape_html(format_currency(row.get("volume_24h")))),
            ("Turnover", escape_html(format_percent(turnover, unit="fraction", decimals=1))),
            (
                "Volume signal",
                f'{escape_html(format_number(row.get("volume_zscore_24h"), decimals=2))}'
                f'<small>{escape_html(humanize_enum(row.get("volume_zscore_basis") or quality.get("volume_zscore_basis")))}</small>',
            ),
            (
                "Liquidity basis",
                escape_html(humanize_enum(row.get("liquidity_basis") or quality.get("liquidity_basis"))),
            ),
            ("Spread", _state_badge(row.get("spread_status") or quality.get("spread_basis"))),
            ("Freshness", _freshness(row, now=now)),
        )
        detail_list = "".join(
            f'<dt>{escape_html(label)}</dt><dd>{value}</dd>' for label, value in details
        )
        items.append(
            '<article class="market-mobile-card">'
            '<header class="market-mobile-head"><div>'
            f'<p class="eyebrow">Exact market observation</p><h3>{escape_html(symbol)}</h3></div>'
            f'{_state_badge(row.get("freshness_status"))}</header>'
            '<div class="market-mobile-returns"><span><small>Price</small><strong>'
            f'{escape_html(format_currency(row.get("price"), compact=False, decimals=_price_decimals(row.get("price"))))}'
            '</strong></span><span><small>24h move</small>'
            f'{_return(row.get("return_24h"), _return_unit(row, "return_24h", unit))}</span></div>'
            '<div class="market-mobile-summary"><p><small>Baseline</small>'
            f'{_state_badge(_baseline_status(row))}</p><p><small>Decision route</small>'
            f'{_decision_route(candidate)}</p></div>'
            '<details class="disclosure market-mobile-details"><summary><span>More market evidence</span>'
            '<span class="disclosure__summary">Returns, liquidity, spread, freshness</span></summary>'
            f'<div class="disclosure__body"><dl class="definition-grid">{detail_list}</dl></div></details>'
            '</article>'
        )
    visible_limit = 6
    visible_items = "".join(items[:visible_limit])
    remaining_items = items[visible_limit:]
    overflow = ""
    if remaining_items:
        count = len(remaining_items)
        overflow = (
            '<details class="disclosure market-mobile-overflow"><summary>'
            f'<span>Show {count} more asset{"s" if count != 1 else ""}</span>'
            '<span class="disclosure__summary">Full evaluated universe</span></summary>'
            '<div class="disclosure__body market-mobile-items">'
            + "".join(remaining_items)
            + "</div></details>"
        )
    return (
        '<section class="panel market-mobile-list"><div class="section-heading"><div>'
        '<p class="eyebrow">Compact market view</p><h2>Market observations</h2></div></div>'
        '<div class="market-mobile-items">'
        + visible_items
        + "</div>"
        + overflow
        + '</section>'
    )


def _decision_route(candidate: Mapping[str, Any]) -> str:
    if not candidate:
        return '<span class="muted">No Decision idea</span>'
    route = candidate.get("_dashboard_route") or candidate.get("radar_route")
    identifier = candidate_identifier(candidate)
    actionability = format_number(candidate.get("actionability_score"), decimals=1)
    actionability_label = (
        "Actionability not recorded"
        if actionability == UNAVAILABLE
        else f"Actionability {actionability}/100"
    )
    return (
        f'<a href="/ideas/{quote(identifier, safe="")}">{escape_html(humanize_enum(route))}</a>'
        f'<small>{escape_html(actionability_label)}</small>'
    )


def _quality_banner(
    snapshot: DashboardSnapshot,
    *,
    spread_count: int,
    baselines: Counter[str],
) -> str:
    observations = len(snapshot.current_market_observations)
    reasons = []
    if not observations:
        reasons.append("No fingerprint-bound market observations are attached.")
    if observations and not spread_count:
        reasons.append("Spread is unavailable for every asset; this prevents actionable execution-quality claims.")
    if observations and not baselines.get("warm"):
        if baselines.get("warming") or baselines.get("cold"):
            reasons.append("The temporal baseline is still cold or warming; proxy features remain visibly labeled.")
        else:
            reasons.append("Temporal baseline status is unavailable or unknown; no maturity claim is made.")
    if observations and not snapshot.visible_current_candidates:
        reasons.append(
            f"The scan completed across {observations} assets and produced zero operator-visible current ideas. "
            "This is a qualification result, not an empty provider response."
        )
    if not reasons:
        reasons.append("The exact market scan completed with current observations and explicit quality evidence.")
    tone = "warning" if spread_count < observations or not baselines.get("warm") else "positive"
    return '<section class="alert alert-' + tone + '"><div class="alert-icon" aria-hidden="true">i</div><div><h2>Data-quality read</h2><ul>' + "".join(f'<li>{escape_html(value)}</li>' for value in reasons) + '</ul></div></section>'


def _representative_charts(
    snapshot: DashboardSnapshot,
    observations: tuple[Mapping[str, Any], ...],
) -> str:
    if not observations:
        return ""
    lead = observations[0]
    key = _asset_key(lead)
    history = tuple(row for row in snapshot.exact_market_history if _asset_key(row) == key)
    quality = _quality(lead)
    baseline = _baseline_status(lead)
    state = baseline if baseline in {"cold", "warming"} else ("ready" if history else "missing")
    turnover = present_turnover_series(
        history,
        metric_basis=(
            quality.get("volume_zscore_basis")
            or lead.get("volume_zscore_basis")
        ),
    )
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Bounded history</p>'
        f'<h2>{escape_html(lead.get("symbol") or "Lead asset")} context</h2></div>{_state_badge(baseline)}</div>'
        '<div class="chart-grid">'
        + render_price_chart(history, state=state, state_detail="Exact fingerprinted history")
        + render_activity_chart(
            history, activity="volume", value_key="volume_24h", state=state,
            proxy=False,
        )
        + render_activity_chart(
            turnover.rows,
            activity="turnover",
            title=turnover.title,
            summary=turnover.summary,
            value_key=turnover.value_key,
            state=state,
            value_format="percent",
            proxy=turnover.proxy,
            state_detail=turnover.state_detail,
        )
        + '</div></section>'
    )


def _anomaly_cards(snapshot: DashboardSnapshot) -> str:
    if not snapshot.current_market_anomalies:
        observation_context = (
            "Evaluated market observations remain visible above."
            if snapshot.current_market_observations
            else "No exact market observations were admitted for this generation."
        )
        return (
            '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scanner evidence</p>'
            '<h2>Market anomalies</h2></div></div><div class="empty-inline">The exact scanner produced '
            f'no anomaly evidence in this generation. {escape_html(observation_context)}</div></section>'
        )
    cards = []
    candidates = _candidate_by_asset(snapshot)
    observations = {
        _asset_key(row): row
        for row in snapshot.current_market_observations
        if any(_asset_key(row))
    }
    for row in snapshot.current_market_anomalies:
        strength = (
            row.get("anomaly_strength")
            if row.get("anomaly_strength") is not None
            else row.get("anomaly_score")
        )
        strength_label = format_number(strength, decimals=1)
        asset_key = _asset_key(row)
        candidate = candidates.get(asset_key, {})
        observation = observations.get(asset_key, {})
        observation_unit = str(observation.get("return_unit") or "percent_points")
        move = _return(
            observation.get("return_24h"),
            _return_unit(observation, "return_24h", observation_unit),
        )
        explanation = (
            "Scanner evidence is not itself a Decision route. The linked canonical Decision passed separately through model gates."
            if candidate
            else "Scanner evidence is not itself a Decision route. No canonical Decision idea qualified for this asset."
        )
        cards.append(
            '<article class="anomaly-card"><div class="anomaly-card__header"><div><p class="eyebrow">'
            f'{escape_html(humanize_enum(row.get("anomaly_type") or row.get("market_anomaly_type")))}</p>'
            f'<h3>{escape_html(row.get("symbol") or row.get("coin_id") or "Asset")}</h3></div>'
            '<div class="anomaly-card__metrics">'
            '<div class="anomaly-card__metric"><span>24h move</span>'
            f'<strong>{move}</strong></div>'
            '<div class="anomaly-card__metric anomaly-card__metric--secondary"><span>Scanner strength</span>'
            f'<strong>{escape_html(strength_label)}</strong></div></div></div>'
            '<div class="anomaly-card__decision"><span>Canonical Decision</span>'
            f'{_decision_route(candidate)}</div>'
            f'<p>{escape_html(explanation)}</p></article>'
        )
    return '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scanner evidence</p><h2>Market anomalies</h2></div></div><div class="card-grid">' + "".join(cards) + '</div></section>'


def _metric(label: str, value: object, detail: str) -> str:
    return f'<article class="metric-card"><span>{escape_html(label)}</span><strong>{escape_html(value)}</strong><small>{escape_html(detail)}</small></article>'


def _return(value: object, unit: str) -> str:
    try:
        label = format_percent(value, unit=unit, decimals=2, signed=True)
    except ValueError:
        label = UNAVAILABLE
    number = finite_number(value)
    tone = "positive" if number is not None and number > 0 else "danger" if number is not None and number < 0 else "muted"
    return f'<span class="number tone-{tone}">{escape_html(label)}</span>'


def _return_unit(row: Mapping[str, Any], field: str, default: str) -> str:
    return event_market_units.return_unit_for_field(row, field, default=default)


def _freshness(row: Mapping[str, Any], *, now: object = None) -> str:
    status = _state_badge(row.get("freshness_status"))
    observed = present_time(
        row.get("observed_at") or row.get("timestamp"),
        now=now,
    )
    time = (
        f'<time datetime="{escape_html(observed.iso_utc)}" title="{escape_html(observed.utc_label)}">{escape_html(observed.relative_label)}</time>'
        if observed.available else '<span class="muted">Time unavailable</span>'
    )
    return status + f'<small>{time}</small>'


def _state_badge(value: object) -> str:
    status = semantic_status(value)
    return f'<span class="status-badge tone-{escape_html(status.tone)}"><i aria-hidden="true"></i>{escape_html(status.label)}</span>'


def _candidate_by_asset(snapshot: DashboardSnapshot) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        _asset_key(row): row
        for row in snapshot.visible_current_candidates
        if any(_asset_key(row))
    }


def _asset_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("symbol") or row.get("validated_symbol") or "").upper(),
        str(row.get("coin_id") or row.get("validated_coin_id") or row.get("canonical_asset_id") or "").casefold(),
    )


def _quality(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("market_data_quality") or row.get("data_quality")
    return value if isinstance(value, Mapping) else {}


def _baseline_status(row: Mapping[str, Any]) -> str:
    quality = _quality(row)
    return str(row.get("temporal_baseline_status") or quality.get("baseline_status") or "unknown")


def _spread_observed(row: Mapping[str, Any]) -> bool:
    quality = _quality(row)
    return quality.get("spread_available") is True or str(row.get("spread_status") or "").casefold() in {
        "verified", "verified_good", "verified_acceptable", "available", "provider_observed",
    }


def _price_decimals(value: object) -> int:
    number = finite_number(value)
    if number is None:
        return 2
    if abs(number) < 0.01:
        return 6
    if abs(number) < 1:
        return 4
    return 2


__all__ = ("render_market_page",)
