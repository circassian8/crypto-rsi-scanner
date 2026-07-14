"""Market Radar page over one exact Decision Radar generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from ..radar import market_units as event_market_units
from .charts import render_activity_chart, render_price_chart
from .components import escape_html
from .loader import candidate_identifier
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_currency,
    format_number,
    format_percent,
    humanize_enum,
    present_time,
    semantic_status,
)
from .view_data import dashboard_query, filter_sort_observations, finite_number


def render_market_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    filters = dashboard_query(query)
    observations = filter_sort_observations(snapshot.current_market_observations, filters)
    candidates = _candidate_by_asset(snapshot)
    spread_count = sum(1 for row in snapshot.current_market_observations if _spread_observed(row))
    baselines = Counter(_baseline_status(row) for row in snapshot.current_market_observations)
    metrics = (
        ("Assets evaluated", len(snapshot.current_market_observations), "Exact current scan"),
        ("Anomalies", len(snapshot.current_market_anomalies), "Scanner evidence"),
        ("Decision ideas", len(snapshot.current_candidates), "Canonical v2 rows"),
        ("Spread verified", f"{spread_count}/{len(snapshot.current_market_observations)}", "Execution quality"),
        ("Warm baselines", baselines.get("warm", 0), f"{baselines.get('warming', 0)} warming"),
    )
    hero = (
        '<section class="page-intro"><div><p class="eyebrow">Exact-generation market scan</p>'
        '<h2>See what the radar evaluated—even when no idea qualified</h2>'
        '<p>CoinGecko turnover and total volume are market proxies, not order-book depth. '
        'Unavailable spread remains unavailable and caps actionable routes.</p></div>'
        f'<div class="count-badge">{len(observations)}<small>shown</small></div></section>'
        + '<div class="metric-grid">' + "".join(_metric(*item) for item in metrics) + '</div>'
    )
    controls = _market_filters(filters)
    quality = _quality_banner(snapshot, spread_count=spread_count, baselines=baselines)
    accounting = _layer_accounting(snapshot)
    table = _market_table(observations, candidates)
    charts = _representative_charts(snapshot, observations)
    anomaly_evidence = _anomaly_cards(snapshot)
    return hero + quality + accounting + controls + table + charts + anomaly_evidence


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
        ("Core / operator ideas", str(len(snapshot.current_candidates)), "Consolidated operator rows"),
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
        '<p class="eyebrow">Layer accounting</p><h2>Where the rows went</h2>'
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
    sort = query.get("sort", "return_24h_desc")
    sort_options = "".join(
        f'<option value="{value}"{(" selected" if sort == value else "")}>{escape_html(label)}</option>'
        for value, label in (
            ("return_24h_desc", "24h return"), ("return_4h_desc", "4h return"),
            ("return_1h_desc", "1h return"), ("volume_desc", "Volume"),
            ("turnover_desc", "Turnover"), ("market_cap_desc", "Market cap"),
        )
    )
    return (
        '<form class="filter-panel market-filters" method="get" action="/market-radar"><div class="filter-grid">'
        f'<label class="filter-search"><span>Search asset</span><input type="search" name="search" value="{search}" placeholder="BTC, ETH, SOL…"></label>'
        + "".join(selects)
        + f'<label><span>Sort</span><select name="sort">{sort_options}</select></label></div>'
        '<div class="filter-actions"><button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/market-radar">Clear</a></div></form>'
    )


def _market_table(
    observations: tuple[Mapping[str, Any], ...],
    candidates: Mapping[tuple[str, str], Mapping[str, Any]],
) -> str:
    if not observations:
        return '<div class="empty-state"><h3>No market observations match this view</h3><p>Clear filters or inspect System Health for acquisition state.</p></div>'
    headers = (
        "Asset", "Price", "1h", "4h", "24h", "vs BTC 4h", "vs ETH 4h",
        "Volume", "Turnover", "Volume signal", "Baseline", "Liquidity basis",
        "Spread", "Freshness", "Decision route",
    )
    rows = []
    for row in observations:
        key = _asset_key(row)
        candidate = candidates.get(key, {})
        route = candidate.get("_dashboard_route") or candidate.get("radar_route")
        if candidate:
            identifier = candidate_identifier(candidate)
            route_html = (
                f'<a href="/ideas/{quote(identifier, safe="")}">{escape_html(humanize_enum(route))}</a>'
                f'<small>{escape_html(format_number(candidate.get("actionability_score"), decimals=1))} actionability</small>'
            )
        else:
            route_html = '<span class="muted">No Decision idea</span>'
        unit = str(row.get("return_unit") or "percent_points")
        quality = _quality(row)
        turnover = (
            row.get("volume_to_market_cap")
            if row.get("volume_to_market_cap") is not None
            else row.get("turnover_24h")
        )
        cells = (
            f'<strong>{escape_html(row.get("symbol") or row.get("coin_id") or UNAVAILABLE)}</strong><small>{escape_html(row.get("coin_id") or "")}</small>',
            escape_html(format_currency(row.get("price"), compact=False, decimals=_price_decimals(row.get("price")))),
            _return(row.get("return_1h"), _return_unit(row, "return_1h", unit)),
            _return(row.get("return_4h"), _return_unit(row, "return_4h", unit)),
            _return(row.get("return_24h"), _return_unit(row, "return_24h", unit)),
            _return(
                row.get("relative_return_vs_btc_4h"),
                _return_unit(row, "relative_return_vs_btc_4h", unit),
            ),
            _return(
                row.get("relative_return_vs_eth_4h"),
                _return_unit(row, "relative_return_vs_eth_4h", unit),
            ),
            escape_html(format_currency(row.get("volume_24h"))),
            escape_html(format_percent(turnover, unit="fraction", decimals=1)),
            f'{escape_html(format_number(row.get("volume_zscore_24h"), decimals=2))}<small>{escape_html(humanize_enum(row.get("volume_zscore_basis") or quality.get("volume_zscore_basis")))}</small>',
            _state_badge(_baseline_status(row)),
            escape_html(humanize_enum(row.get("liquidity_basis") or quality.get("liquidity_basis"))),
            _state_badge(row.get("spread_status") or quality.get("spread_basis")),
            _freshness(row),
            route_html,
        )
        rows.append(
            '<tr>' + "".join(
                f'<td data-label="{escape_html(label)}">{value}</td>'
                for label, value in zip(headers, cells, strict=True)
            ) + '</tr>'
        )
    head = "".join(f'<th scope="col">{escape_html(label)}</th>' for label in headers)
    return (
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Cross-sectional view</p>'
        '<h2>Market comparison</h2></div></div><div class="table-scroll" role="region" tabindex="0" '
        'aria-label="Scrollable market comparison"><table class="responsive-table market-table">'
        f'<caption class="sr-only">{len(observations)} exact market observations</caption>'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
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
        reasons.append("The temporal baseline is still cold or warming; proxy features remain visibly labeled.")
    if observations and not snapshot.current_candidates:
        reasons.append(
            f"The scan completed across {observations} assets and produced zero current ideas. "
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
    turnover_history = tuple(_turnover_percent_row(row) for row in history)
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
            turnover_history, activity="turnover", value_key="_turnover_percent", state=state,
            value_format="percent", proxy=True,
            state_detail=humanize_enum(quality.get("volume_zscore_basis")),
        )
        + '</div></section>'
    )


def _anomaly_cards(snapshot: DashboardSnapshot) -> str:
    if not snapshot.current_market_anomalies:
        return (
            '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Scanner evidence</p>'
            '<h2>Market anomalies</h2></div></div><div class="empty-inline">The exact scanner produced '
            'no anomaly evidence in this generation. Evaluated market observations remain visible above.</div></section>'
        )
    cards = []
    for row in snapshot.current_market_anomalies:
        cards.append(
            '<article class="anomaly-card"><div><p class="eyebrow">'
            f'{escape_html(humanize_enum(row.get("anomaly_type") or row.get("market_anomaly_type")))}</p>'
            f'<h3>{escape_html(row.get("symbol") or row.get("coin_id") or "Asset")}</h3></div>'
            f'<strong>{escape_html(format_number(row.get("anomaly_strength") or row.get("anomaly_score"), decimals=1))}</strong>'
            '<p>Scanner evidence only. A Decision idea appears separately only after canonical gates pass.</p></article>'
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


def _turnover_percent_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = finite_number(row.get("turnover_24h"))
    return {**dict(row), "_turnover_percent": value * 100.0 if value is not None else None}


def _freshness(row: Mapping[str, Any]) -> str:
    status = _state_badge(row.get("freshness_status"))
    observed = present_time(row.get("observed_at") or row.get("timestamp"))
    time = (
        f'<time datetime="{escape_html(observed.iso_utc)}" title="{escape_html(observed.utc_label)}">{escape_html(observed.relative_label)}</time>'
        if observed.available else '<span class="muted">Time unavailable</span>'
    )
    return status + f'<small>{time}</small>'


def _state_badge(value: object) -> str:
    status = semantic_status(value)
    return f'<span class="status-badge tone-{escape_html(status.tone)}"><i aria-hidden="true"></i>{escape_html(status.label)}</span>'


def _candidate_by_asset(snapshot: DashboardSnapshot) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {_asset_key(row): row for row in snapshot.current_candidates if any(_asset_key(row))}


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
