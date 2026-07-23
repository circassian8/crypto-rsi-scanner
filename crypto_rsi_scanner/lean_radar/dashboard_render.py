"""Human-first HTML rendering for the six-page Lean Radar dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import math
from typing import Iterable, Mapping, Sequence
from urllib.parse import quote

from .dashboard_data import _LeanDashboardState, _LeanIdeaDetail
from .models import CalendarEvent, LeanIdea, LeanOutcome, MarketSnapshot


NAVIGATION = (
    ("/", "Today"),
    ("/ideas", "Ideas"),
    ("/market", "Market"),
    ("/calendar", "Calendar"),
    ("/outcomes", "Outcomes"),
    ("/health", "System Health"),
)

ROUTE_LABELS = {
    "urgent_review": "Urgent review",
    "watchlist": "Watchlist",
    "daily_digest": "Daily digest",
    "dashboard_only": "Dashboard only",
    "risk_calendar": "Risk & calendar",
    "diagnostic_hidden": "Diagnostics",
}
IDEA_LABELS = {
    "market_breakout_long": "Market breakout",
    "relative_strength_long": "Relative strength",
    "pullback_or_mean_reversion": "Pullback / mean reversion",
    "rapid_market_anomaly": "Rapid market anomaly",
    "exhaustion_or_fade_review": "Exhaustion / fade review",
    "selloff_or_risk_warning": "Selloff / risk warning",
    "calendar_risk": "Scheduled risk",
    "dashboard_watch": "Developing watch",
    "diagnostic": "Data diagnostic",
}
RESULT_LABELS = {
    "pending": "Pending",
    "unresolved": "Unresolved",
    "inconclusive": "Inconclusive",
    "continued": "Continued",
    "reversed": "Reversed",
    "failed_quickly": "Failed quickly",
    "risk_warning_validated": "Risk warning validated",
}
ROUTE_SLUGS = {value.replace("_", "-"): value for value in ROUTE_LABELS}
IDEA_SLUGS = {value.replace("_", "-"): value for value in IDEA_LABELS}


@dataclass(frozen=True)
class RenderedDashboardPage:
    status_code: int
    title: str
    body: str


def render_dashboard_page(
    state: _LeanDashboardState,
    path: str,
    *,
    query: Mapping[str, str] | None = None,
    detail: _LeanIdeaDetail | None = None,
) -> RenderedDashboardPage:
    values = query or {}
    if path == "/":
        title, active, content = "Today", "/", _today(state)
    elif path == "/ideas":
        title, active, content = "Ideas", "/ideas", _ideas(state, values)
    elif path == "/market":
        title, active, content = "Market", "/market", _market(state)
    elif path == "/calendar":
        title, active, content = "Calendar", "/calendar", _calendar_page(state)
    elif path == "/outcomes":
        title, active, content = "Outcomes", "/outcomes", _outcomes(state, values)
    elif path == "/health":
        title, active, content = "System Health", "/health", _health(state)
    elif path.startswith("/ideas/") and detail is not None:
        title = f"{detail.idea.symbol} idea"
        active, content = "/ideas", _idea_detail(state, detail)
    else:
        return RenderedDashboardPage(
            404,
            "Not found",
            _shell(
                state,
                title="Not found",
                active="",
                content=_empty(
                    "This view does not exist",
                    "Return to Today to continue reviewing the current market state.",
                    action=("Back to Today", "/"),
                ),
            ),
        )
    return RenderedDashboardPage(
        200,
        title,
        _shell(state, title=title, active=active, content=content),
    )


def render_unavailable(reason: str) -> RenderedDashboardPage:
    safe_reason = escape(reason)
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crypto Radar unavailable</title><style>{DASHBOARD_CSS}</style></head>
<body><main class="standalone"><section class="empty-state critical">
<div class="empty-icon">!</div><p class="eyebrow">Dashboard unavailable</p>
<h1>Runtime state is not ready</h1><p>{safe_reason}</p>
<code>make lean-radar-health</code><p class="fine-print">Research only · no send · no trading</p>
</section></main></body></html>"""
    return RenderedDashboardPage(503, "Unavailable", body)


def _shell(
    state: _LeanDashboardState,
    *,
    title: str,
    active: str,
    content: str,
) -> str:
    health = state.health_status or {}
    scan = state.scan_status or {}
    freshness = str(health.get("data_freshness", "unavailable"))
    health_status = str(health.get("status", "not_run"))
    source_mode = str(scan.get("source_mode", "unavailable"))
    source_label = {
        "live_no_send": "Live no-send",
        "imported_snapshot": "Imported snapshot",
        "fixture": "Fixture data",
    }.get(source_mode, "Source unavailable")
    nav = "".join(
        f'<a class="nav-link{" active" if href == active else ""}" href="{href}">'
        f'<span class="nav-dot"></span>{escape(label)}</a>'
        for href, label in NAVIGATION
    )
    warning = ""
    if state.truncated_sections:
        warning = (
            '<div class="banner warn"><strong>Bounded view:</strong> '
            + escape(", ".join(_human(value) for value in state.truncated_sections))
            + " history is truncated. Current operator rows remain visible.</div>"
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>{escape(title)} · Crypto Radar</title>
<style>{DASHBOARD_CSS}</style></head><body>
<div class="app-shell"><aside class="sidebar"><a class="brand" href="/">
<span class="brand-mark">CR</span><span><strong>Crypto Radar</strong>
<small>Bybit perpetuals</small></span></a><nav>{nav}</nav>
<div class="sidebar-foot"><span class="status-light {_tone(health_status)}"></span>
<span>{escape(_human(health_status))}</span><small>Research only · no send</small></div></aside>
<main class="main"><header class="topbar"><div><p class="eyebrow">Operator workspace</p>
<h1>{escape(title)}</h1></div><div class="top-pills">
{_badge(source_label, _tone(source_mode))}{_badge(_human(freshness), _tone(freshness))}{_badge("Research only", "quiet")}</div></header>
{warning}<div class="content">{content}</div><footer>Human decision required · No automatic trading</footer>
</main></div></body></html>"""


def _today(state: _LeanDashboardState) -> str:
    visible = tuple(
        idea for idea in state.active_ideas if idea.dashboard_route != "diagnostic_hidden"
    )
    urgent = tuple(idea for idea in visible if idea.dashboard_route == "urgent_review")
    watch = tuple(idea for idea in visible if idea.dashboard_route == "watchlist")
    risk = tuple(idea for idea in visible if idea.dashboard_route == "risk_calendar")
    developing = tuple(
        idea
        for idea in visible
        if idea.dashboard_route in {"daily_digest", "dashboard_only"}
    )
    rapid_count = sum(idea.idea_type == "rapid_market_anomaly" for idea in visible)
    fade_count = sum(idea.idea_type == "exhaustion_or_fade_review" for idea in visible)
    health = state.health_status or {}
    scan = state.scan_status or {}
    errors = health.get("errors") if isinstance(health.get("errors"), list) else []
    next_scan = health.get("next_scan_at") or scan.get("next_scan_at")
    metrics = _metrics(
        (
            ("Active ideas", str(len(visible)), "Current scan"),
            ("Look now", str(len(urgent)), f"{rapid_count} rapid anomalies"),
            ("Fade reviews", str(fade_count), "Review only"),
            ("Markets", str(len(state.latest_snapshots)), "Venue-confirmed set"),
        )
    )
    warning_panel = ""
    if errors:
        warning_panel = _panel(
            "System attention",
            '<ul class="clean-list">'
            + "".join(f"<li>{escape(str(value))}</li>" for value in errors[:6])
            + "</ul>",
            eyebrow="Before the next live scan",
            tone="warn",
        )
    elif not state.health_status:
        warning_panel = _panel(
            "Refresh system health",
            "<p>The bounded operator-health snapshot has not been created yet.</p>"
            "<code>make lean-radar-health</code>",
            eyebrow="One safe local action",
            tone="warn",
        )
    scan_strip = _panel(
        "Current scan",
        '<div class="inline-facts">'
        + _fact("Status", _human(str(scan.get("status", "not run"))))
        + _fact("Observed", _when(scan.get("observed_at"), state.loaded_at))
        + _fact("Next eligible", _when(next_scan, state.loaded_at))
        + _fact("Freshness", _human(str(health.get("data_freshness", "unavailable"))))
        + "</div>",
        eyebrow="Point-in-time state",
    )
    scheduled = tuple(
        row
        for row in state.calendar_events
        if state.loaded_at <= _time(row.starts_at) <= state.loaded_at + timedelta(hours=24)
    )
    calendar_strip = ""
    if scheduled:
        calendar_strip = _panel(
            "Scheduled risk in the next 24 hours",
            '<div class="inline-facts">'
            + "".join(
                _fact(
                    row.title,
                    f"{_when(row.starts_at, state.loaded_at)} · {_human(row.importance)}",
                )
                for row in scheduled[:3]
            )
            + '</div><a class="text-link" href="/calendar">Open calendar →</a>',
            eyebrow="Context only · creates no direction",
            tone="warn",
        )
    sections = "".join(
        (
            _idea_section("Look now", "Time-sensitive review items", urgent),
            _idea_section("Watchlist", "Qualified ideas worth monitoring", watch),
            _idea_section("Risk & calendar", "Downside and scheduled-risk context", risk),
            _idea_section("Developing", "Useful context that is not urgent", developing),
        )
    )
    if not visible:
        sections = _empty(
            "No current review items",
            "The latest trusted scan found no setup that cleared the Lean Radar screens. "
            "Market observations remain available below.",
            action=("Review market", "/market"),
        )
    return metrics + warning_panel + scan_strip + calendar_strip + sections


def _ideas(state: _LeanDashboardState, query: Mapping[str, str]) -> str:
    route = ROUTE_SLUGS.get(query.get("route", ""))
    idea_type = IDEA_SLUGS.get(query.get("type", ""))
    horizon = query.get("horizon", "")
    search = query.get("q", "").strip().upper()[:24]
    sort = query.get("sort", "actionability")
    rows = list(state.active_ideas)
    if route is None and not query.get("route"):
        rows = [row for row in rows if row.dashboard_route != "diagnostic_hidden"]
    elif route:
        rows = [row for row in rows if row.dashboard_route == route]
    if idea_type:
        rows = [row for row in rows if row.idea_type == idea_type]
    if horizon:
        rows = [row for row in rows if row.horizon.replace("_", "-") == horizon]
    if search:
        rows = [row for row in rows if search in row.symbol.upper()]
    key = {
        "urgency": lambda row: row.urgency_score,
        "risk": lambda row: row.risk_score,
        "time": lambda row: _time(row.created_at).timestamp(),
        "symbol": lambda row: row.symbol,
    }.get(sort, lambda row: row.actionability_score)
    rows.sort(key=key, reverse=sort != "symbol")
    controls = f"""<form class="filters" method="get" action="/ideas">
<label>Search<input name="q" value="{escape(search)}" placeholder="BTC"></label>
<label>Route<select name="route">{_select_options(query.get('route', ''), ROUTE_SLUGS, ROUTE_LABELS, 'All visible routes')}</select></label>
<label>Idea type<select name="type">{_select_options(query.get('type', ''), IDEA_SLUGS, IDEA_LABELS, 'All idea types')}</select></label>
<label>Horizon<select name="horizon">{_plain_options(query.get('horizon', ''), ('1h','1h-to-4h','4h','4h-to-24h','24h','3d'), 'All horizons')}</select></label>
<label>Sort<select name="sort">{_plain_options(sort, ('actionability','urgency','risk','time','symbol'), None)}</select></label>
<button type="submit">Apply</button><a class="reset" href="/ideas">Reset</a></form>"""
    summary = f'<p class="result-count">{len(rows)} current idea{"s" if len(rows) != 1 else ""}</p>'
    cards = (
        '<div class="idea-grid">' + "".join(_idea_card(row) for row in rows) + "</div>"
        if rows
        else _empty(
            "No ideas match these filters",
            "Clear a filter or wait for the next eligible scan.",
            action=("Clear filters", "/ideas"),
        )
    )
    return _intro(
        "Current operator ideas",
        "One setup per asset, ordered for human review. Unknown catalyst remains visible; missing execution quality stays explicit.",
    ) + controls + summary + cards


def _market(state: _LeanDashboardState) -> str:
    rows = sorted(state.latest_snapshots, key=lambda row: row.volume_usd_24h, reverse=True)
    scan = state.scan_status or {}
    source_label = {
        "live_no_send": "Live no-send",
        "imported_snapshot": "Imported snapshot",
        "fixture": "Fixture data",
    }.get(str(scan.get("source_mode", "")), "Unavailable")
    header = _intro(
        "Latest venue-constrained market",
        "CoinGecko detection rows intersected with confirmed Bybit USDT perpetuals. Prices are research context, not executable quotes.",
    )
    metrics = _metrics(
        (
            ("Observed assets", str(len(rows)), "Latest point per asset"),
            ("Bybit instruments", str(state.catalog_count), "Confirmed catalog"),
            ("Data source", source_label, "No provider call on page load"),
            ("Observed", _when(scan.get("observed_at"), state.loaded_at), "UTC"),
        )
    )
    if not rows:
        return header + metrics + _empty(
            "No market observations yet",
            "Run readiness, then one authorized or genuine imported scan.",
        )
    body = "".join(
        f"""<tr><td><strong>{escape(row.symbol)}</strong><small>{escape(row.bybit_instrument)}</small></td>
<td>{_money(row.price_usd)}</td><td>{_signed(row.return_1h_pp)}</td>
<td>{_signed(row.return_24h_pp)}</td><td>{_signed(row.return_7d_pp)}</td>
<td>{_money(row.volume_usd_24h, compact=True)}</td><td>{_rsi(row.rsi_14)}</td>
<td>{_sparkline(row.sparkline_prices, label=f'{row.symbol} seven-day price')}</td>
<td>{_badge(_human(row.data_quality), _tone(row.data_quality))}<small>{_when(row.observed_at, state.loaded_at)}</small></td></tr>"""
        for row in rows
    )
    return header + metrics + _table(
        ("Asset", "Price", "1h", "24h", "7d", "24h volume", "RSI", "7d path", "Data"),
        body,
        "market-table",
    )


def _calendar_page(state: _LeanDashboardState) -> str:
    now = state.loaded_at
    upcoming = tuple(row for row in state.calendar_events if _time(row.starts_at) >= now)
    recent = tuple(
        row
        for row in state.calendar_events
        if now - timedelta(hours=24) <= _time(row.starts_at) < now
    )
    calendar_health = (state.health_status or {}).get("calendar")
    status = (
        str(calendar_health.get("status", "unavailable"))
        if isinstance(calendar_health, Mapping)
        else "unavailable"
    )
    intro = _intro(
        "Scheduled context, never direction",
        "Macro events apply as broad risk context. Crypto events attach only to exact symbols. A calendar date cannot create a trade idea.",
    )
    metrics = _metrics(
        (
            ("Upcoming", str(len(upcoming)), "Stored events"),
            ("Recent", str(len(recent)), "Past 24 hours"),
            ("Coverage", _human(status), "Local snapshot"),
            (
                "Next event",
                _when(upcoming[0].starts_at, now) if upcoming else "None scheduled",
                "UTC",
            ),
        )
    )
    if not upcoming and not recent:
        message = (
            "The calendar is loaded and has no current events."
            if status in {"ready", "no_upcoming"}
            else "No validated calendar snapshot is available. Market-led ideas remain usable with this limitation shown."
        )
        return intro + metrics + _empty("Calendar is clear", message)
    return (
        intro
        + metrics
        + _event_section("Upcoming", upcoming, now)
        + _event_section("Recent context", recent, now)
    )


def _outcomes(state: _LeanDashboardState, query: Mapping[str, str]) -> str:
    status_filter = query.get("status", "")
    horizon_filter = query.get("horizon", "")
    rows = list(state.outcomes)
    if status_filter in {"pending", "matured", "unresolved"}:
        rows = [row for row in rows if row.status == status_filter]
    if horizon_filter in {"1h", "4h", "24h", "3d"}:
        rows = [row for row in rows if row.horizon == horizon_filter]
    rows.sort(key=lambda row: _time(row.target_at), reverse=True)
    all_rows = state.outcomes
    metrics = _metrics(
        (
            ("Matured", str(sum(row.status == "matured" for row in all_rows)), "Observed endpoints"),
            ("Pending", str(sum(row.status == "pending" for row in all_rows)), "Waiting for horizon"),
            ("Unresolved", str(sum(row.status == "unresolved" for row in all_rows)), "Missing bounded endpoint"),
            ("Ideas tracked", str(len({row.idea_id for row in all_rows})), "Four horizons each"),
        )
    )
    controls = f"""<form class="filters compact" method="get" action="/outcomes">
<label>Status<select name="status">{_plain_options(status_filter, ('pending','matured','unresolved'), 'All states')}</select></label>
<label>Horizon<select name="horizon">{_plain_options(horizon_filter, ('1h','4h','24h','3d'), 'All horizons')}</select></label>
<button type="submit">Apply</button><a class="reset" href="/outcomes">Reset</a></form>"""
    if not rows:
        table = _empty(
            "No outcomes match",
            "Outcomes appear automatically after ideas and retained future observations exist.",
        )
    else:
        body = "".join(_outcome_row(row) for row in rows[:500])
        table = _table(
            ("Idea", "Horizon", "Result", "Return", "vs BTC", "vs ETH", "MFE / MAE", "Endpoint"),
            body,
            "outcomes-table",
        )
    return _intro(
        "Observed outcomes",
        "Point-in-time descriptive results only. Missing cadence evidence stays unresolved and never tunes the detector automatically.",
    ) + metrics + controls + table


def _health(state: _LeanDashboardState) -> str:
    health = state.health_status or {}
    scan = state.scan_status or {}
    outcomes = state.outcome_status or {}
    errors = health.get("errors") if isinstance(health.get("errors"), list) else []
    status = str(health.get("status", "not_run"))
    provider_current = _human(str(health.get("current_authorization_status", "not checked")))
    source_label = {
        "live_no_send": "Live no-send",
        "imported_snapshot": "Imported snapshot",
        "fixture": "Fixture data",
    }.get(str(scan.get("source_mode", "")), "Source unavailable")
    provider_last = (
        "Succeeded"
        if health.get("last_provider_call_succeeded") is True
        else "Failed"
        if health.get("last_provider_call_attempted") is True
        else "Not attempted"
    )
    hero = f"""<section class="health-hero {_tone(status)}"><div>
<p class="eyebrow">Current operator state</p><h2>{escape(_human(status))}</h2>
<p>{'Core local state is ready.' if status == 'ready' else 'Review the items below before the next provider-backed scan.'}</p></div>
{_badge('No send', 'good')}</section>"""
    cards = '<div class="health-grid">' + "".join(
        (
            _health_card(
                "Market data",
                _human(str(health.get("data_freshness", "unavailable"))),
                f"{source_label} · last scan {_when(health.get('last_scan_at') or scan.get('observed_at'), state.loaded_at)}",
            ),
            _health_card(
                "Current authorization",
                provider_current,
                _human(str(health.get("current_provider_call_eligibility", "not checked"))),
            ),
            _health_card(
                "Last provider result",
                provider_last,
                _when(health.get("last_provider_attempted_at"), state.loaded_at),
            ),
            _health_card(
                "Bybit universe",
                f"{state.catalog_count} instruments",
                f"Catalog {_when(state.catalog_observed_at, state.loaded_at)}",
            ),
            _health_card(
                "Calendar",
                _human(str(_nested(health, "calendar", "status", default="unavailable"))),
                f"{len(state.calendar_events)} retained events",
            ),
            _health_card(
                "Outcomes",
                _human(str(outcomes.get("status", "not run"))),
                f"{outcomes.get('matured_count', 0)} matured · {outcomes.get('unresolved_count', 0)} unresolved",
            ),
        )
    ) + "</div>"
    action = health.get("next_safe_command")
    action_panel = _panel(
        "Next safe action",
        f"<code>{escape(str(action or 'make lean-radar-readiness'))}</code>"
        '<p class="fine-print">This dashboard never runs the command for you.</p>',
        eyebrow="Operator controlled",
        tone="accent",
    )
    error_panel = _panel(
        "Attention items" if errors else "No recorded blockers",
        (
            '<ul class="clean-list">'
            + "".join(f"<li>{escape(str(value))}</li>" for value in errors[:8])
            + "</ul>"
            if errors
            else "<p>The latest persisted health projection has no recorded errors.</p>"
        ),
        eyebrow="Bounded summary",
        tone="warn" if errors else "good",
    )
    safety = _panel(
        "Safety boundary",
        '<div class="safety-grid">'
        + "".join(
            f'<span><b>0</b>{escape(label)}</span>'
            for label in (
                "Telegram sends",
                "Trades",
                "Orders",
                "Paper trades",
                "RSI writes",
                "Triggered fades",
            )
        )
        + "</div>",
        eyebrow="This product path",
    )
    return _intro(
        "System truth without hidden activity",
        "Current permission, historical provider result, freshness, and local readiness are separate facts. Page loads make no provider call or write.",
    ) + hero + cards + action_panel + error_panel + safety


def _idea_detail(state: _LeanDashboardState, detail: _LeanIdeaDetail) -> str:
    idea = detail.idea
    history = detail.market_history
    prices = tuple(row.price_usd for row in history)
    volumes = tuple(row.volume_usd_24h for row in history)
    if len(prices) < 2 and history:
        prices = history[-1].sparkline_prices
    back = '<a class="back-link" href="/ideas">← Back to ideas</a>'
    title = f"""<section class="detail-head"><div>{back}<div class="idea-heading">
<span class="symbol-orb">{escape(idea.symbol[:5])}</span><div><p class="eyebrow">{escape(IDEA_LABELS.get(idea.idea_type, _human(idea.idea_type)))}</p>
<h2>{escape(idea.symbol)} <small>{escape(idea.bybit_instrument)}</small></h2>
<div class="badge-row">{_badge(ROUTE_LABELS.get(idea.dashboard_route, _human(idea.dashboard_route)), _tone(idea.dashboard_route))}
{_badge(_human(idea.directional_bias), _tone(idea.directional_bias))}{_badge(_human(idea.catalyst_status), _tone(idea.catalyst_status))}</div></div></div></div>
<div class="detail-clock"><span>Created {_when(idea.created_at, state.loaded_at)}</span><span>Expires {_when(idea.expires_at, state.loaded_at)}</span></div></section>"""
    scores = '<div class="score-grid">' + "".join(
        _score(label, value, risk=label == "Risk")
        for label, value in (
            ("Actionability", idea.actionability_score),
            ("Confidence", idea.confidence_score),
            ("Risk", idea.risk_score),
            ("Urgency", idea.urgency_score),
        )
    ) + "</div>"
    charts = f"""<section class="panel chart-panel"><div class="panel-head"><div><p class="eyebrow">Retained market path</p><h3>Price and activity</h3></div><span>{len(history)} observations</span></div>
<div class="chart-grid"><div><label>Price</label>{_chart(prices, 'Price path')}</div><div><label>24h volume</label>{_chart(volumes, 'Volume path', tone='amber')}</div></div>
<p class="fine-print">Point-in-time snapshots; lines are context, not executable quotes.</p></section>"""
    narrative = '<div class="detail-grid">' + "".join(
        (
            _list_panel("Why now", idea.why_now, "Operator thesis"),
            _list_panel("Supporting facts", idea.supporting_facts, "Observed evidence"),
            _list_panel("Main risks", idea.risks, "What can go wrong", tone="warn"),
            _list_panel("Missing information", idea.missing_information, "Known limitations"),
            _list_panel("What confirms", idea.what_confirms, "Evidence to look for", tone="good"),
            _list_panel("What invalidates", idea.what_invalidates, "Stop believing the thesis", tone="danger"),
        )
    ) + "</div>"
    context = _detail_context(idea, now=state.loaded_at)
    outcomes = _detail_outcomes(detail.outcomes)
    return title + scores + charts + narrative + context + outcomes


def _detail_context(idea: LeanIdea, *, now: datetime) -> str:
    technical = idea.technical_context
    calendar = idea.calendar_context
    events = calendar.get("events") if isinstance(calendar.get("events"), list) else []
    calendar_rows = "".join(
        f'<li><strong>{escape(str(row.get("title", "Scheduled event")))}</strong>'
        f'<span>{_when(row.get("starts_at"), now)} · '
        f'{escape(_human(str(row.get("importance", "unknown"))))}</span></li>'
        for row in events[:5]
        if isinstance(row, Mapping)
    )
    return f"""<section class="context-grid">
{_panel('Technical context', '<div class="inline-facts">' + _fact('RSI', _number(technical.get('rsi_14'))) + _fact('vs BTC 1h', _signed_value(technical.get('relative_btc_1h_pp'))) + _fact('vs ETH 1h', _signed_value(technical.get('relative_eth_1h_pp'))) + _fact('Chase risk', _number(technical.get('chase_risk_score'))) + '</div>', eyebrow='Current scan')}
{_panel('Calendar context', '<ul class="event-mini">' + calendar_rows + '</ul>' if calendar_rows else '<p>No exact scheduled context is attached to this idea.</p>', eyebrow='Context only')}
{_panel('Catalyst context', '<p>' + escape(_human(idea.catalyst_status)) + '</p><p class="fine-print">Unknown catalyst lowers confidence and raises risk; it does not hide a liquid market-led idea.</p>', eyebrow='Optional explanation')}
</section>"""


def _detail_outcomes(rows: Sequence[LeanOutcome]) -> str:
    if not rows:
        return _panel(
            "Outcome history",
            "<p>No outcome placeholders are stored for this idea.</p>",
            eyebrow="Point-in-time review",
        )
    body = "".join(_outcome_row(row) for row in rows)
    return '<section><div class="section-head"><div><p class="eyebrow">Point-in-time review</p><h2>Outcome history</h2></div></div>' + _table(
        ("Idea", "Horizon", "Result", "Return", "vs BTC", "vs ETH", "MFE / MAE", "Endpoint"),
        body,
        "outcomes-table",
    ) + "</section>"


def _idea_section(title: str, subtitle: str, rows: Sequence[LeanIdea]) -> str:
    if not rows:
        return ""
    return f'<section><div class="section-head"><div><p class="eyebrow">{escape(subtitle)}</p><h2>{escape(title)}</h2></div><span>{len(rows)}</span></div><div class="idea-grid">' + "".join(
        _idea_card(row) for row in rows
    ) + "</div></section>"


def _idea_card(idea: LeanIdea) -> str:
    why = idea.why_now[0] if idea.why_now else "Review the current evidence."
    return f"""<article class="idea-card {_tone(idea.dashboard_route)}">
<div class="idea-card-top"><div><span class="symbol">{escape(idea.symbol)}</span>
<span class="instrument">{escape(idea.bybit_instrument)}</span></div>
{_badge(ROUTE_LABELS.get(idea.dashboard_route, _human(idea.dashboard_route)), _tone(idea.dashboard_route))}</div>
<h3>{escape(IDEA_LABELS.get(idea.idea_type, _human(idea.idea_type)))}</h3><p>{escape(why)}</p>
<div class="mini-scores"><span><b>{idea.actionability_score:.0f}</b>Action</span>
<span><b>{idea.confidence_score:.0f}</b>Confidence</span><span><b>{idea.risk_score:.0f}</b>Risk</span>
<span><b>{idea.urgency_score:.0f}</b>Urgency</span></div>
<div class="card-meta"><span>{escape(_human(idea.catalyst_status))} catalyst</span><span>{escape(_human(idea.horizon))}</span><span>{escape(_human(idea.outcome_status))} outcome</span></div>
<a class="card-link" href="/ideas/{quote(idea.idea_id, safe='')}">Review idea <span>→</span></a></article>"""


def _event_section(
    title: str,
    rows: Sequence[CalendarEvent],
    now: datetime,
) -> str:
    if not rows:
        return ""
    cards = "".join(
        f"""<article class="event-card"><div class="event-date"><b>{_time(row.starts_at).strftime('%d')}</b><span>{_time(row.starts_at).strftime('%b')}</span></div>
<div><div class="badge-row">{_badge(_human(row.category), 'accent')}{_badge(_human(row.importance), _tone(row.importance))}</div>
<h3>{escape(row.title)}</h3><p>{_when(row.starts_at, now)} · {escape(_human(row.time_certainty))}</p>
<small>{escape(', '.join(row.affected_symbols) if row.affected_symbols else 'All tracked markets')} · {escape(row.source_name)}</small></div></article>"""
        for row in rows
    )
    return f'<section><div class="section-head"><div><p class="eyebrow">Context only</p><h2>{escape(title)}</h2></div><span>{len(rows)}</span></div><div class="event-list">{cards}</div></section>'


def _outcome_row(row: LeanOutcome) -> str:
    endpoint = (
        _when(row.end_observed_at, _time(row.evaluated_at))
        if row.end_observed_at
        else _human(row.status)
    )
    return f"""<tr><td><a href="/ideas/{quote(row.idea_id, safe='')}"><strong>{escape(row.symbol)}</strong></a><small>{escape(IDEA_LABELS.get(row.idea_type, _human(row.idea_type)))}</small></td>
<td>{escape(row.horizon)}{' ' + _badge('Expired', 'warn') if row.expired else ''}</td>
<td>{_badge(RESULT_LABELS.get(row.result, _human(row.result)), _tone(row.result))}</td>
<td>{_signed(row.return_pp)}</td><td>{_signed(row.relative_btc_pp)}</td><td>{_signed(row.relative_eth_pp)}</td>
<td>{_signed(row.mfe_pp)} / {_signed(row.mae_pp)}</td><td>{escape(endpoint)}<small>{row.path_snapshot_count} points</small></td></tr>"""


def _metrics(rows: Sequence[tuple[str, str, str]]) -> str:
    return '<section class="metrics">' + "".join(
        f'<article><span>{escape(label)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></article>'
        for label, value, note in rows
    ) + "</section>"


def _intro(title: str, text: str) -> str:
    return f'<section class="page-intro"><p class="eyebrow">Lean Crypto Radar</p><h2>{escape(title)}</h2><p>{escape(text)}</p></section>'


def _panel(
    title: str,
    body: str,
    *,
    eyebrow: str,
    tone: str = "",
) -> str:
    return f'<section class="panel {escape(tone)}"><div class="panel-head"><div><p class="eyebrow">{escape(eyebrow)}</p><h3>{escape(title)}</h3></div></div>{body}</section>'


def _list_panel(
    title: str,
    values: Sequence[str],
    eyebrow: str,
    *,
    tone: str = "",
) -> str:
    body = (
        '<ul class="clean-list">'
        + "".join(f"<li>{escape(value)}</li>" for value in values)
        + "</ul>"
        if values
        else "<p>Nothing recorded.</p>"
    )
    return _panel(title, body, eyebrow=eyebrow, tone=tone)


def _health_card(title: str, value: str, note: str) -> str:
    return f'<article><span>{escape(title)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></article>'


def _score(label: str, value: float, *, risk: bool = False) -> str:
    tone = "risk" if risk else "score"
    return f'<article><div><span>{escape(label)}</span><strong>{value:.0f}</strong></div><div class="score-track"><i class="{tone}" style="width:{max(0, min(100, value)):.0f}%"></i></div></article>'


def _fact(label: str, value: str) -> str:
    return f'<span><small>{escape(label)}</small><b>{escape(value)}</b></span>'


def _table(headers: Sequence[str], body: str, css_class: str) -> str:
    return f'<div class="table-wrap {escape(css_class)}"><table><thead><tr>' + "".join(
        f"<th>{escape(value)}</th>" for value in headers
    ) + f"</tr></thead><tbody>{body}</tbody></table></div>"


def _empty(
    title: str,
    text: str,
    *,
    action: tuple[str, str] | None = None,
) -> str:
    button = (
        f'<a class="button" href="{escape(action[1])}">{escape(action[0])}</a>'
        if action
        else ""
    )
    return f'<section class="empty-state"><div class="empty-icon">○</div><h2>{escape(title)}</h2><p>{escape(text)}</p>{button}</section>'


def _badge(label: str, tone: str) -> str:
    return f'<span class="badge {escape(tone)}">{escape(label)}</span>'


def _sparkline(values: Sequence[float], *, label: str) -> str:
    return _line_svg(values, width=108, height=32, label=label, css="sparkline")


def _chart(
    values: Sequence[float],
    label: str,
    *,
    tone: str = "cyan",
) -> str:
    return _line_svg(values, width=360, height=100, label=label, css=f"chart {tone}")


def _line_svg(
    values: Sequence[float],
    *,
    width: int,
    height: int,
    label: str,
    css: str,
) -> str:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if len(clean) < 2:
        return '<span class="muted">Not enough history</span>'
    low, high = min(clean), max(clean)
    span = high - low or 1.0
    points = " ".join(
        f"{index * width / (len(clean) - 1):.1f},{height - ((value - low) / span) * (height - 8) - 4:.1f}"
        for index, value in enumerate(clean)
    )
    return f'<svg class="{escape(css)}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}"><polyline points="{points}"/></svg>'


def _select_options(
    selected: str,
    slugs: Mapping[str, str],
    labels: Mapping[str, str],
    all_label: str,
) -> str:
    options = [f'<option value="">{escape(all_label)}</option>']
    for slug, raw in slugs.items():
        options.append(
            f'<option value="{escape(slug)}"{" selected" if selected == slug else ""}>{escape(labels[raw])}</option>'
        )
    return "".join(options)


def _plain_options(
    selected: str,
    values: Sequence[str],
    all_label: str | None,
) -> str:
    options = [f'<option value="">{escape(all_label)}</option>'] if all_label else []
    for value in values:
        options.append(
            f'<option value="{escape(value)}"{" selected" if selected == value else ""}>{escape(_human(value))}</option>'
        )
    return "".join(options)


def _money(value: float, *, compact: bool = False) -> str:
    if compact:
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        if value >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"${value / 1_000:.1f}K"
    if value >= 1_000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.6f}".rstrip("0").rstrip(".")


def _signed(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _signed_value(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Unavailable"
    return f"{float(value):+.2f}%"


def _number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Unavailable"
    return f"{float(value):.1f}"


def _rsi(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def _when(value: object, now: datetime) -> str:
    if not isinstance(value, str):
        return "Not available"
    try:
        parsed = _time(value)
    except ValueError:
        return "Invalid time"
    delta = parsed - now.astimezone(timezone.utc)
    seconds = delta.total_seconds()
    if abs(seconds) < 60:
        relative = "now"
    elif seconds > 0 and seconds < 3600:
        relative = f"in {math.ceil(seconds / 60)}m"
    elif seconds < 0 and seconds > -3600:
        relative = f"{math.ceil(abs(seconds) / 60)}m ago"
    elif seconds > 0 and seconds < 86_400:
        relative = f"in {seconds / 3600:.1f}h"
    elif seconds < 0 and seconds > -86_400:
        relative = f"{abs(seconds) / 3600:.1f}h ago"
    else:
        relative = parsed.strftime("%d %b")
    return f"{relative} · {parsed.strftime('%H:%M')} UTC"


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp is not aware")
    return parsed.astimezone(timezone.utc)


def _human(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().capitalize()


def _tone(value: str) -> str:
    lowered = value.casefold()
    if any(token in lowered for token in ("ready", "complete", "fresh", "known", "confirmed", "continued", "validated", "adequate", "observed", "high")):
        return "good"
    if any(token in lowered for token in ("urgent", "rapid", "active", "look", "long")):
        return "accent"
    if any(token in lowered for token in ("risk", "warn", "late", "unresolved", "unknown", "partial", "medium", "attention", "fade", "fixture")):
        return "warn"
    if any(token in lowered for token in ("failed", "blocked", "stale", "invalid", "insufficient", "extreme")):
        return "danger"
    return "quiet"


def _nested(
    values: Mapping[str, object],
    outer: str,
    inner: str,
    *,
    default: object,
) -> object:
    child = values.get(outer)
    return child.get(inner, default) if isinstance(child, Mapping) else default


DASHBOARD_CSS = r"""
:root{--bg:#071019;--bg2:#0b1622;--panel:#101d2a;--panel2:#142333;--line:#22364a;--ink:#f2f7fb;--muted:#8fa5b8;--cyan:#49d7e8;--cyan2:#99f2f4;--green:#69dda8;--amber:#f2bf68;--red:#ff7f84;--shadow:0 18px 50px rgba(0,0,0,.24);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 88% 0,rgba(73,215,232,.08),transparent 32rem),var(--bg);color:var(--ink);font-size:15px;line-height:1.5}a{color:inherit;text-decoration:none}h1,h2,h3,p{margin-top:0}h1{font-size:clamp(1.55rem,3vw,2.25rem);letter-spacing:-.035em;margin-bottom:0}h2{font-size:1.35rem;letter-spacing:-.02em;margin-bottom:.45rem}h3{font-size:1rem;margin-bottom:.45rem}small,.muted,.fine-print{color:var(--muted)}code{display:block;max-width:100%;overflow:auto;padding:.8rem 1rem;border:1px solid var(--line);border-radius:10px;background:#09131d;color:var(--cyan2);font:600 .78rem ui-monospace,SFMono-Regular,Menlo,monospace}.text-link{display:inline-block;margin-top:14px;color:var(--cyan2);font-size:.76rem;font-weight:800}.app-shell{min-height:100vh}.sidebar{position:fixed;inset:0 auto 0 0;width:225px;padding:24px 16px;display:flex;flex-direction:column;background:rgba(7,16,25,.96);border-right:1px solid var(--line);z-index:3}.brand{display:flex;gap:12px;align-items:center;padding:0 9px 28px}.brand-mark{display:grid;place-items:center;width:39px;height:39px;border:1px solid rgba(73,215,232,.55);border-radius:12px;background:linear-gradient(145deg,rgba(73,215,232,.22),rgba(73,215,232,.04));color:var(--cyan2);font-weight:800;font-size:.78rem;letter-spacing:.06em}.brand strong,.brand small{display:block}.brand strong{font-size:.98rem}.brand small{font-size:.7rem;margin-top:1px}.sidebar nav{display:grid;gap:4px}.nav-link{position:relative;display:flex;gap:11px;align-items:center;padding:10px 12px;border-radius:9px;color:#a9bac8;font-size:.88rem;font-weight:600}.nav-link:hover{background:rgba(255,255,255,.035);color:var(--ink)}.nav-link.active{background:rgba(73,215,232,.1);color:var(--cyan2)}.nav-dot{width:6px;height:6px;border:1px solid currentColor;border-radius:50%}.nav-link.active .nav-dot{background:var(--cyan);box-shadow:0 0 12px var(--cyan)}.sidebar-foot{margin-top:auto;padding:14px 10px;border-top:1px solid var(--line);display:grid;grid-template-columns:9px 1fr;gap:3px 8px;align-items:center;font-size:.78rem}.sidebar-foot small{grid-column:2}.status-light{width:7px;height:7px;border-radius:50%;background:var(--muted)}.status-light.good{background:var(--green);box-shadow:0 0 10px var(--green)}.status-light.warn{background:var(--amber)}.status-light.danger{background:var(--red)}.main{margin-left:225px;min-height:100vh}.topbar{min-height:106px;padding:25px clamp(22px,4vw,58px);display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid rgba(34,54,74,.7);background:rgba(7,16,25,.68);backdrop-filter:blur(16px)}.top-pills,.badge-row{display:flex;gap:7px;flex-wrap:wrap}.content{max-width:1420px;padding:32px clamp(22px,4vw,58px) 70px}.eyebrow{margin-bottom:5px;text-transform:uppercase;letter-spacing:.13em;color:var(--muted);font-size:.65rem;font-weight:800}.page-intro{max-width:810px;margin-bottom:23px}.page-intro>p:last-child{color:#adbfcc;margin-bottom:0}.badge{display:inline-flex;align-items:center;white-space:nowrap;padding:4px 8px;border:1px solid var(--line);border-radius:999px;color:#b7c7d3;background:rgba(255,255,255,.025);font-size:.67rem;font-weight:800;letter-spacing:.02em}.badge.good{border-color:rgba(105,221,168,.26);background:rgba(105,221,168,.1);color:#9aefc4}.badge.accent{border-color:rgba(73,215,232,.27);background:rgba(73,215,232,.1);color:var(--cyan2)}.badge.warn{border-color:rgba(242,191,104,.3);background:rgba(242,191,104,.11);color:#ffd58e}.badge.danger{border-color:rgba(255,127,132,.3);background:rgba(255,127,132,.11);color:#ffafb2}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:26px}.metrics article,.health-grid article{padding:16px 17px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,rgba(20,35,51,.95),rgba(13,26,38,.95))}.metrics span,.health-grid span{display:block;color:var(--muted);font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}.metrics strong,.health-grid strong{display:block;margin:.25rem 0;font-size:1.35rem;letter-spacing:-.03em}.metrics small,.health-grid small{display:block}.panel{padding:20px;border:1px solid var(--line);border-radius:14px;background:var(--panel);box-shadow:var(--shadow);margin-bottom:20px}.panel.warn{border-color:rgba(242,191,104,.24)}.panel.danger{border-color:rgba(255,127,132,.25)}.panel.good{border-color:rgba(105,221,168,.22)}.panel.accent{border-color:rgba(73,215,232,.24)}.panel-head,.section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.panel-head>span,.section-head>span{display:grid;place-items:center;min-width:28px;height:28px;border-radius:999px;background:var(--panel2);color:var(--muted);font-size:.76rem}.inline-facts{display:flex;gap:30px;flex-wrap:wrap}.inline-facts>span{display:grid;gap:2px}.inline-facts small{text-transform:uppercase;letter-spacing:.06em;font-size:.62rem}.inline-facts b{font-size:.86rem}.section-head{margin:30px 0 13px}.section-head h2{margin:0}.idea-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.idea-card{position:relative;overflow:hidden;padding:18px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,var(--panel2),#0d1925);box-shadow:0 12px 28px rgba(0,0,0,.17)}.idea-card:before{content:"";position:absolute;inset:0 auto 0 0;width:2px;background:var(--muted)}.idea-card.accent:before{background:var(--cyan)}.idea-card.warn:before{background:var(--amber)}.idea-card.danger:before{background:var(--red)}.idea-card-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.symbol{font-size:1.12rem;font-weight:850;letter-spacing:-.02em}.instrument{display:block;color:var(--muted);font-size:.65rem}.idea-card h3{margin:15px 0 7px}.idea-card>p{min-height:44px;color:#b5c4d0;font-size:.83rem}.mini-scores{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin:15px 0}.mini-scores span{text-align:center;color:var(--muted);font-size:.56rem;text-transform:uppercase}.mini-scores b{display:block;color:var(--ink);font-size:.93rem}.card-meta{display:flex;gap:6px;flex-wrap:wrap;color:var(--muted);font-size:.67rem}.card-meta span:not(:last-child):after{content:"·";margin-left:6px}.card-link{display:flex;justify-content:space-between;margin:15px -18px -18px;padding:12px 18px;border-top:1px solid var(--line);color:var(--cyan2);font-size:.76rem;font-weight:800}.filters{display:grid;grid-template-columns:1.1fr repeat(4,minmax(115px,.8fr)) auto auto;gap:9px;align-items:end;margin:18px 0}.filters.compact{grid-template-columns:repeat(2,minmax(150px,220px)) auto auto;justify-content:start}.filters label{color:var(--muted);font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.filters input,.filters select{display:block;width:100%;margin-top:5px;padding:10px 11px;border:1px solid var(--line);border-radius:9px;background:#0c1823;color:var(--ink);font:inherit;font-size:.8rem}.filters button,.button{padding:10px 15px;border:1px solid rgba(73,215,232,.34);border-radius:9px;background:rgba(73,215,232,.12);color:var(--cyan2);font-weight:800;cursor:pointer}.reset{padding:10px;color:var(--muted);font-size:.78rem}.result-count{color:var(--muted);font-size:.75rem}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:13px;background:var(--panel)}table{width:100%;border-collapse:collapse;min-width:850px}th,td{padding:13px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}th{position:sticky;top:0;background:#101d2a;color:var(--muted);font-size:.62rem;text-transform:uppercase;letter-spacing:.07em}td{font-size:.77rem}td small{display:block;margin-top:2px;font-size:.62rem}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:rgba(255,255,255,.018)}.sparkline{width:108px;height:32px;color:var(--cyan)}svg polyline{fill:none;stroke:currentColor;stroke-width:2;vector-effect:non-scaling-stroke}.event-list{display:grid;gap:9px}.event-card{display:grid;grid-template-columns:54px 1fr;gap:15px;align-items:center;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}.event-date{display:grid;place-items:center;width:48px;height:48px;border-radius:11px;background:#0b1722;color:var(--cyan2)}.event-date b{font-size:1.05rem}.event-date span{font-size:.6rem;text-transform:uppercase}.event-card h3{margin:5px 0 2px}.event-card p,.event-card small{margin:0;color:var(--muted);font-size:.72rem}.health-hero{display:flex;justify-content:space-between;align-items:center;padding:22px;margin-bottom:14px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(120deg,rgba(73,215,232,.1),var(--panel))}.health-hero.warn{background:linear-gradient(120deg,rgba(242,191,104,.1),var(--panel))}.health-hero h2{font-size:1.8rem}.health-hero p:last-child{margin:0;color:var(--muted)}.health-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:20px}.safety-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.safety-grid span{padding:10px;border-radius:9px;background:#0b1722;text-align:center;color:var(--muted);font-size:.65rem}.safety-grid b{display:block;color:var(--green);font-size:1.05rem}.clean-list{padding:0;margin:0;list-style:none}.clean-list li{position:relative;padding:7px 0 7px 17px;border-bottom:1px solid rgba(34,54,74,.55);color:#bdcbd5;font-size:.82rem}.clean-list li:last-child{border-bottom:0}.clean-list li:before{content:"";position:absolute;left:0;top:14px;width:5px;height:5px;border-radius:50%;background:var(--cyan)}.detail-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:19px}.back-link{display:inline-block;margin-bottom:15px;color:var(--muted);font-size:.75rem}.idea-heading{display:flex;gap:14px;align-items:center}.symbol-orb{display:grid;place-items:center;width:57px;height:57px;border-radius:16px;background:linear-gradient(145deg,rgba(73,215,232,.22),rgba(73,215,232,.06));border:1px solid rgba(73,215,232,.3);font-weight:900;color:var(--cyan2)}.idea-heading h2{font-size:1.65rem;margin:0}.idea-heading h2 small{font-size:.65rem;font-weight:500}.detail-clock{display:grid;gap:3px;text-align:right;color:var(--muted);font-size:.7rem}.score-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px}.score-grid article{padding:14px;border:1px solid var(--line);border-radius:11px;background:var(--panel)}.score-grid article>div:first-child{display:flex;justify-content:space-between}.score-grid span{color:var(--muted);font-size:.7rem}.score-track{height:4px;margin-top:9px;border-radius:5px;background:#07111a;overflow:hidden}.score-track i{display:block;height:100%;background:linear-gradient(90deg,#268fa0,var(--cyan))}.score-track i.risk{background:linear-gradient(90deg,#b47632,var(--amber))}.chart-grid{display:grid;grid-template-columns:2fr 1fr;gap:20px}.chart-grid label{display:block;margin-bottom:7px;color:var(--muted);font-size:.68rem;text-transform:uppercase}.chart{display:block;width:100%;height:100px;color:var(--cyan);border-bottom:1px solid var(--line)}.chart.amber{color:var(--amber)}.detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}.detail-grid .panel{margin:0}.context-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;margin:20px 0}.context-grid .panel{margin:0}.event-mini{padding:0;list-style:none;margin:0}.event-mini li{display:grid;padding:7px 0;border-bottom:1px solid var(--line)}.event-mini span{color:var(--muted);font-size:.7rem}.empty-state{display:grid;justify-items:center;text-align:center;padding:55px 22px;border:1px dashed #2c4357;border-radius:15px;background:rgba(16,29,42,.48)}.empty-state p{max-width:620px;color:var(--muted)}.empty-icon{display:grid;place-items:center;width:42px;height:42px;margin-bottom:12px;border:1px solid var(--line);border-radius:50%;color:var(--cyan)}.standalone{min-height:100vh;display:grid;place-items:center;padding:24px}.standalone .empty-state{width:min(650px,100%)}.banner{margin:16px clamp(22px,4vw,58px) 0;padding:11px 14px;border-radius:9px;font-size:.75rem}.banner.warn{border:1px solid rgba(242,191,104,.25);background:rgba(242,191,104,.08);color:#f4d7a4}footer{padding:18px clamp(22px,4vw,58px);border-top:1px solid var(--line);color:var(--muted);font-size:.68rem}
@media(max-width:1050px){.idea-grid{grid-template-columns:repeat(2,1fr)}.filters{grid-template-columns:repeat(3,1fr)}.detail-grid,.context-grid{grid-template-columns:repeat(2,1fr)}.safety-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){body{padding-bottom:64px}.sidebar{position:fixed;inset:auto 0 0 0;width:auto;height:62px;padding:6px 8px;border:0;border-top:1px solid var(--line);display:block}.brand,.sidebar-foot{display:none}.sidebar nav{height:100%;display:grid;grid-template-columns:repeat(6,1fr)}.nav-link{justify-content:center;display:grid;gap:2px;padding:5px 2px;text-align:center;font-size:.56rem}.nav-dot{margin:auto}.main{margin-left:0}.topbar{min-height:88px;padding:18px}.content{padding:22px 16px 45px}.top-pills .badge.quiet{display:none}.metrics{grid-template-columns:repeat(2,1fr)}.idea-grid,.health-grid,.detail-grid,.context-grid,.chart-grid{grid-template-columns:1fr}.filters,.filters.compact{grid-template-columns:repeat(2,1fr)}.filters button,.filters .reset{align-self:end}.detail-head{display:block}.detail-clock{text-align:left;margin-top:15px}.score-grid{grid-template-columns:repeat(2,1fr)}.inline-facts{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.safety-grid{grid-template-columns:repeat(2,1fr)}.market-table{margin-left:-16px;margin-right:-16px;border-radius:0}.event-card{grid-template-columns:46px 1fr}}
@media(max-width:430px){.metrics{grid-template-columns:1fr 1fr}.idea-grid{grid-template-columns:1fr}.filters,.filters.compact{grid-template-columns:1fr}.topbar{align-items:flex-start}.top-pills{justify-content:flex-end}.mini-scores{grid-template-columns:repeat(4,1fr)}}
"""


__all__ = (
    "DASHBOARD_CSS",
    "NAVIGATION",
    "RenderedDashboardPage",
    "render_dashboard_page",
    "render_unavailable",
)
