"""Outcomes & Learning page for the local Decision Radar dashboard."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from .components import (
    HtmlFragment,
    badge,
    data_table,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
    time_element,
)
from .layer_coverage import DashboardLayerCoverage, dashboard_layer_coverage_by_key
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    humanize_enum,
    operator_route_label,
    present_time,
)
from .presentation_models.outcome_state import project_outcome_state
from .system_page_support import (
    as_number as _number,
    render_metric_grid as _metric_grid,
    render_page_intro as _page_intro,
    render_panel as _panel,
)


_OUTCOME_ROUTE_VALUES = (
    "dashboard_watch",
    "actionable_watch",
    "high_confidence_watch",
    "rapid_market_anomaly",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
    "diagnostic",
)
_OUTCOME_ROUTE_OPTIONS = tuple(
    (route, operator_route_label(route)) for route in _OUTCOME_ROUTE_VALUES
)
_OUTCOME_STATE_FIELD = "_dashboard_outcome_state"
_OUTCOME_BUCKET_FIELD = "_dashboard_outcome_bucket"
_OUTCOME_ROUTE_FIELD = "_dashboard_outcome_route"
_OUTCOME_SOURCE_FIELD = "_dashboard_outcome_source"
_OUTCOME_GENERATION_FIELD = "_dashboard_outcome_generation"


@dataclass(frozen=True)
class _OutcomePageState:
    filters: Mapping[str, str]
    current: tuple[Mapping[str, Any], ...]
    historical: tuple[tuple[Mapping[str, Any], str], ...]
    filtered_current: tuple[Mapping[str, Any], ...]
    filtered_history: tuple[Mapping[str, Any], ...]
    current_counts: Counter[str]
    current_matured: int
    history_matured: int
    outcome_layer: DashboardLayerCoverage
    outcome_authority: str
    outcome_authority_label: str
    current_layer_admitted: bool
    metrics: tuple[tuple[str, str, str], ...]
    read_clock: object


def render_outcomes_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    """Render exact outcome placeholders separately from historical learning."""

    state = _build_outcome_page_state(snapshot, query)
    sections: list[str] = [
        _page_intro(
            "What the radar is learning",
            "Pending, matured, and unavailable observations with score cohorts. Evidence confidence is not win probability.",
            "Research-only learning loop",
        ),
        _outcome_filter_form(state.filters),
    ]
    if not snapshot.generation_authoritative:
        sections.append(
            _panel(
                "Current outcome rows suppressed",
                (
                    "Current outcome rows are unavailable because generation authority "
                    "did not pass. Historical campaign rows remain separately labeled context."
                ),
                eyebrow="Fail-closed authority",
            )
        )
    if snapshot.generation_authoritative and state.filters["scope"] in {"all", "current"}:
        sections.append(_current_outcome_section(snapshot, state))
    sections.append(
        '<div class="outcome-metrics">' + _metric_grid(state.metrics) + '</div>'
    )
    if state.filters["scope"] in {"all", "historical"}:
        sections.append(_historical_outcome_section(state))
    sections.extend((
        _cohort_summary(
            state.current if state.current_layer_admitted else (),
            state.historical,
        ),
        _feedback_summary(snapshot),
    ))
    return "".join(sections)


def _build_outcome_page_state(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> _OutcomePageState:
    filters = _outcome_filters(query)
    current = tuple(
        _project_outcome(
            row,
            source="Exact generation",
            fallback_generation=snapshot.artifact_namespace,
        )
        for row in snapshot.current_outcomes
    )
    historical = _historical_outcomes(snapshot)
    current_counts = _outcome_counts(current)
    historical_counts = _outcome_counts(tuple(row for row, _source in historical))
    outcome_layer = dashboard_layer_coverage_by_key(snapshot)["outcomes"]
    outcome_authority = str(
        snapshot.current_outcomes_metadata.get("authority") or ""
    ).strip()
    outcome_fingerprint_verified = (
        outcome_authority == "current_generation_fingerprint_verified"
        and bool(snapshot.current_outcomes_metadata.get("sha256"))
    )
    current_layer_admitted = (
        snapshot.generation_authoritative
        and (
            outcome_layer.status in {"healthy_nonempty", "healthy_empty"}
            or (outcome_layer.status == "degraded" and outcome_fingerprint_verified)
        )
    )
    state = _OutcomePageState(
        filters=filters,
        current=current,
        historical=historical,
        filtered_current=_filter_outcomes(current, filters),
        filtered_history=_filter_outcomes(
            tuple(row for row, _source in historical),
            filters,
        ),
        current_counts=current_counts,
        current_matured=current_counts["matured"],
        history_matured=historical_counts["matured"],
        outcome_layer=outcome_layer,
        outcome_authority=outcome_authority,
        outcome_authority_label=(
            humanize_enum(outcome_authority)
            if outcome_authority
            else humanize_enum(outcome_layer.status)
        ),
        current_layer_admitted=current_layer_admitted,
        metrics=(),
        read_clock=snapshot.generation_authority_checked_at,
    )
    return replace(state, metrics=_outcome_metrics(snapshot, state))


def _outcome_metrics(
    snapshot: DashboardSnapshot,
    state: _OutcomePageState,
) -> tuple[tuple[str, str, str], ...]:
    current_layer_incomplete = (
        state.current_layer_admitted and state.outcome_layer.status == "degraded"
    )
    unavailable_current_value = (
        "Unavailable" if snapshot.generation_authoritative else "Suppressed"
    )
    current_value = (
        f"{len(state.current)} admitted"
        if current_layer_incomplete
        else str(len(state.current))
        if state.current_layer_admitted
        else unavailable_current_value
    )
    coverage_metric = (
        "Current outcome coverage",
        _operator_coverage_label(state.outcome_layer.status),
        _coverage_tone(state.outcome_layer.status),
    )
    history_metric = (
        "Historical sample",
        f"{len(state.historical)} rows · {state.history_matured} matured",
        "positive" if state.history_matured else "muted",
    )
    if not state.current_layer_admitted:
        return (coverage_metric, history_metric)
    return (
        (
            "Current outcome rows",
            current_value,
            "warning" if current_layer_incomplete else "info",
        ),
        coverage_metric,
        (
            "Current pending",
            str(state.current_counts["pending"]),
            "warning" if state.current_counts["pending"] else "muted",
        ),
        (
            "Current matured",
            str(state.current_matured),
            "positive" if state.current_matured else "muted",
        ),
        (
            "Current unavailable",
            str(state.current_counts["unavailable"]),
            "warning" if state.current_counts["unavailable"] else "muted",
        ),
        history_metric,
    )


def _current_outcome_section(
    snapshot: DashboardSnapshot,
    state: _OutcomePageState,
) -> str:
    return _outcome_section(
        "Exact current-generation outcomes",
        (
            "Fingerprint-verified placeholders and outcomes for this run only; the coverage badge still reports count or contract gaps."
            if state.outcome_authority == "current_generation_fingerprint_verified"
            and snapshot.current_outcomes_metadata.get("sha256")
            else "Exact current-generation outcome coverage; unavailable or rejected data is never presented as verified."
        ),
        state.filtered_current if state.current_layer_admitted else (),
        empty_title=(
            "Current outcomes unavailable"
            if not state.current_layer_admitted
            else "No current outcome rows"
            if not state.current
            else "No current outcomes match these filters"
        ),
        empty_message=_current_outcome_empty_message(
            current=state.current if state.current_layer_admitted else (),
            filtered_current=(
                state.filtered_current if state.current_layer_admitted else ()
            ),
            layer=state.outcome_layer,
        ),
        authority=state.outcome_authority_label,
        now=state.read_clock,
        tail_html=(
            _sample_warning(
                state.current_matured,
                scope="exact current generation",
            )
            if state.current_layer_admitted
            else ""
        ),
    )


def _historical_outcome_section(state: _OutcomePageState) -> str:
    return _outcome_section(
        "Historical campaign outcomes",
        (
            "Historical / non-authoritative for the current generation. These rows "
            "support learning but never alter current visibility or thresholds."
        ),
        state.filtered_history,
        empty_title="No historical outcomes match these filters",
        empty_message="No historical outcome rows match these filters.",
        authority="Historical / non-authoritative",
        now=state.read_clock,
        collapsed=True,
        lead_html=_sample_warning(
            state.history_matured,
            scope="historical campaign",
        ),
    )


def _operator_coverage_label(value: object) -> str:
    token = str(value or "").strip().casefold()
    return {
        "healthy_nonempty": "Complete",
        "healthy_empty": "Complete · empty",
        "degraded": "Incomplete",
        "not_configured": "Not configured",
        "not_applicable": "Not applicable",
    }.get(token, humanize_enum(value))


def _coverage_tone(status: str) -> str:
    if status in {"healthy_nonempty", "healthy_empty"}:
        return "positive"
    if status == "not_applicable":
        return "muted"
    if status in {"rejected", "stale"}:
        return "danger"
    return "warning"


def _outcome_section(
    title: str,
    description: str,
    rows: tuple[Mapping[str, Any], ...],
    *,
    empty_title: str,
    empty_message: str,
    authority: str,
    now: object = None,
    collapsed: bool = False,
    lead_html: str = "",
    tail_html: str = "",
) -> str:
    table_rows = []
    mobile_rows: list[str] = []
    for row in rows:
        state = _outcome_state(row)
        source = row.get(_OUTCOME_SOURCE_FIELD) or UNAVAILABLE
        generation = row.get(_OUTCOME_GENERATION_FIELD) or UNAVAILABLE
        idea = row.get("symbol") or row.get("coin_id") or row.get("candidate_id") or "Idea"
        route = operator_route_label(_outcome_route(row))
        horizon = humanize_enum(row.get("primary_horizon") or row.get("preferred_horizon"))
        actionability = _cohort_label(
            row.get("actionability_score_cohort"),
            row.get("actionability_score"),
            actionability=True,
        )
        evidence = _cohort_label(
            row.get("evidence_confidence_score_cohort"),
            row.get("evidence_confidence_score"),
        )
        risk = _cohort_label(row.get("risk_score_cohort"), row.get("risk_score"))
        cohorts = _outcome_cohort_cell(
            actionability=actionability,
            evidence=evidence,
            risk=risk,
        )
        result = (
            humanize_enum(row.get("outcome_label") or row.get("validation_label"))
            if _outcome_bucket(row) == "matured"
            else UNAVAILABLE
        )
        generation_label = _outcome_generation_cell(generation, source)
        table_rows.append((
            idea,
            _outcome_state_result_cell(state, result),
            route,
            cohorts,
            _outcome_time(row, now=now),
            horizon,
            generation_label,
        ))
        mobile_rows.append(
            '<article class="outcome-record">'
            '<header class="outcome-record__header"><div>'
            f'<p class="eyebrow">{escape_html(route)}</p>'
            f'<h3>{escape_html(idea)}</h3></div>{badge(state)}</header>'
            '<div class="outcome-record__scores" aria-label="Decision score cohorts">'
            f'<span><small><span aria-hidden="true">Action</span><span class="sr-only">Actionability</span></small><strong>{escape_html(actionability)}</strong></span>'
            f'<span><small>Evidence</small><strong>{escape_html(evidence)}</strong></span>'
            f'<span><small>Risk</small><strong>{escape_html(risk)}</strong></span>'
            '</div>'
            '<p class="outcome-record__timing">'
            f'{_outcome_time(row, now=now)} <span aria-hidden="true">·</span> '
            f'{escape_html(horizon)} horizon</p>'
            + (
                f'<p class="outcome-record__result"><strong>Result</strong> {escape_html(result)}</p>'
                if result != UNAVAILABLE
                else ""
            )
            + str(disclosure(
                "Generation and provenance",
                definition_list((
                    ("Generation", generation),
                    ("Scope", source),
                    ("Observed / evaluated", _outcome_time(row, now=now)),
                    ("Preferred horizon", horizon),
                ), css_class="definition-grid"),
                summary="Exact identity and evidence scope",
                css_class="outcome-record__details",
            ))
            + '</article>'
        )
    table = (
        data_table(
            (
                "Idea", "State / result", "Route", "Score cohorts",
                "Observed / evaluated", "Horizon", "Generation",
            ),
            table_rows,
            caption=title,
            compact=True,
        )
        if table_rows
        else empty_state(empty_title, empty_message)
    )
    content = (
        lead_html
        + f'<p>{escape_html(description)}</p>'
        + str(badge(authority, tone="info" if "historical" in authority.casefold() else None))
        + '<div class="outcome-desktop-table">' + str(table) + '</div>'
        + '<div class="outcome-mobile-list">' + "".join(mobile_rows) + '</div>'
        + tail_html
    )
    if collapsed:
        return str(disclosure(
            title,
            HtmlFragment(content),
            summary=f"{len(rows)} historical row{'s' if len(rows) != 1 else ''}",
            css_class="panel outcome-history-disclosure",
        ))
    return _panel(
        title,
        content,
        eyebrow="Pending and matured",
    )


def _current_outcome_empty_message(
    *,
    current: tuple[Mapping[str, Any], ...],
    filtered_current: tuple[Mapping[str, Any], ...],
    layer: DashboardLayerCoverage,
) -> str:
    if current and not filtered_current:
        return (
            "Exact current outcome rows exist, but none match the selected filters. "
            "Clear or adjust the filters to see them."
        )
    if layer.status == "healthy_empty":
        return (
            "The fingerprint-verified outcome artifact is empty for this zero-idea generation. "
            "That is a verified empty result, not a missing artifact."
        )
    if layer.status == "not_applicable":
        return (
            "This generation has no canonical current ideas, so no outcome placeholder is required. "
            "No fingerprint-verification claim is made for an absent artifact."
        )
    if layer.status == "rejected":
        return (
            "The exact outcome artifact was rejected and no current rows were admitted. "
            "Zero rows is not a verified empty result."
        )
    if layer.status == "stale":
        return (
            "The exact outcome artifact is stale and cannot be presented as current. "
            "Zero rows is not a verified empty result."
        )
    return (
        "No fingerprint-verified exact outcome artifact is available for the current ideas. "
        "Zero rows is not a verified empty result."
    )


def _cohort_summary(
    current: tuple[Mapping[str, Any], ...],
    historical: tuple[tuple[Mapping[str, Any], str], ...],
) -> str:
    matured = [
        row
        for row in (*current, *(row for row, _source in historical))
        if _outcome_bucket(row) == "matured"
    ]
    route_counts = Counter(
        operator_route_label(_outcome_route(row))
        for row in matured
    )
    rows = [
        (route, count, "Descriptive only · no automatic threshold")
        for route, count in route_counts.most_common()
    ]
    body = (
        str(data_table(
            ("Route cohort", "Matured rows", "Use"),
            rows,
            caption="Matured sample by Decision route",
            empty="No matured outcome cohort is available yet.",
        ))
        + '<p class="muted">Cohort summaries need adequate sample size and diversity before supporting any human policy review.</p>'
    )
    return str(disclosure(
        "Matured route cohorts",
        HtmlFragment(body),
        summary=(
            f"{len(matured)} matured row{'s' if len(matured) != 1 else ''}"
            if rows
            else "No matured cohort yet"
        ),
        css_class="panel outcome-secondary-disclosure",
    ))


def _feedback_summary(snapshot: DashboardSnapshot) -> str:
    counts = Counter(
        humanize_enum(
            row.get("feedback_label")
            or row.get("label")
            or row.get("human_label")
            or "unclassified"
        )
        for row in snapshot.cumulative_feedback
    )
    rows = [(label, count) for label, count in counts.most_common()]
    body = (
        str(data_table(
            ("Preference label", "Rows"),
            rows,
            caption="Cumulative optional feedback",
            empty="No optional human preference feedback has been recorded.",
        ))
        + '<p class="muted">Feedback is preference data only. It does not automatically change scores, routes, gates, or visibility.</p>'
    )
    return str(disclosure(
        "Optional human feedback",
        HtmlFragment(body),
        summary=f"{sum(counts.values())} preference row{'s' if sum(counts.values()) != 1 else ''}",
        css_class="panel outcome-secondary-disclosure",
    ))


def _outcome_filters(query: Mapping[str, str] | None) -> dict[str, str]:
    raw = query or {}
    scope = str(raw.get("scope") or "all").casefold()
    status = str(raw.get("status") or "all").casefold()
    route = _normalize_outcome_route(raw.get("route"))
    allowed_routes = {value for value, _label in _OUTCOME_ROUTE_OPTIONS}
    return {
        "scope": scope if scope in {"all", "current", "historical"} else "all",
        "status": status if status in {"all", "pending", "matured", "unavailable"} else "all",
        "route": route if route in allowed_routes else "",
        "search": str(raw.get("search") or "").strip().casefold(),
    }


def _filter_outcomes(
    rows: tuple[Mapping[str, Any], ...],
    filters: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    selected = []
    for row in rows:
        if filters["status"] != "all" and _outcome_bucket(row) != filters["status"]:
            continue
        route = _outcome_route(row)
        if filters["route"] and route != filters["route"]:
            continue
        search_text = " ".join(
            str(row.get(field) or "")
            for field in ("symbol", "coin_id", "candidate_id", "core_opportunity_id")
        ).casefold()
        if filters["search"] and filters["search"] not in search_text:
            continue
        selected.append(row)
    return tuple(selected)


def _historical_outcomes(
    snapshot: DashboardSnapshot,
) -> tuple[tuple[Mapping[str, Any], str], ...]:
    rows: list[tuple[Mapping[str, Any], str]] = []
    seen: set[tuple[str, ...]] = set()
    for values, source in (
        (snapshot.campaign_outcomes, "Decision campaign"),
        (snapshot.cumulative_outcomes, "Namespace history"),
    ):
        for row in values:
            key = _outcome_key(row)
            if key in seen:
                continue
            seen.add(key)
            rows.append((_project_outcome(row, source=source), source))
    return tuple(rows)


def _outcome_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("artifact_namespace") or ""),
        str(row.get("candidate_id") or row.get("core_opportunity_id") or ""),
        str(row.get("observed_at") or row.get("decision_evaluated_at") or ""),
    )


def _outcome_state(row: Mapping[str, Any]) -> str:
    projected = str(row.get(_OUTCOME_STATE_FIELD) or "").strip().casefold()
    return projected or project_outcome_state(row)[0]


def _outcome_bucket(row: Mapping[str, Any]) -> str:
    projected = str(row.get(_OUTCOME_BUCKET_FIELD) or "").strip().casefold()
    return (
        projected
        if projected in {"pending", "matured", "unavailable"}
        else project_outcome_state(row)[1]
    )


def _project_outcome(
    row: Mapping[str, Any],
    *,
    source: str,
    fallback_generation: str = "",
) -> Mapping[str, Any]:
    """Copy an artifact row into the canonical, presentation-only outcome projection."""

    state, bucket = project_outcome_state(row)
    projected = dict(row)
    projected[_OUTCOME_STATE_FIELD] = state
    projected[_OUTCOME_BUCKET_FIELD] = bucket
    projected[_OUTCOME_ROUTE_FIELD] = _normalize_outcome_route(
        row.get("radar_route") or row.get("route")
    )
    projected[_OUTCOME_SOURCE_FIELD] = source
    projected[_OUTCOME_GENERATION_FIELD] = _outcome_generation_identity(
        row,
        source=source,
        fallback=fallback_generation,
    )
    return projected


def _outcome_route(row: Mapping[str, Any]) -> str:
    projected = str(row.get(_OUTCOME_ROUTE_FIELD) or "").strip().casefold()
    return projected or _normalize_outcome_route(row.get("radar_route") or row.get("route"))


def _normalize_outcome_route(value: object) -> str:
    token = "".join(
        character if character.isalnum() else "_"
        for character in str(value or "").strip().casefold()
    )
    while "__" in token:
        token = token.replace("__", "_")
    token = token.strip("_")
    return {
        "calendar_scheduled_risk": "calendar_risk",
        "fade_exhaustion": "fade_exhaustion_review",
        "high_confidence": "high_confidence_watch",
    }.get(token, token)


def _outcome_generation_identity(
    row: Mapping[str, Any],
    *,
    source: str,
    fallback: str,
) -> str:
    namespace = str(
        row.get("artifact_namespace")
        or row.get("origin_artifact_namespace")
        or row.get("source_artifact_namespace")
        or fallback
        or ""
    ).strip()
    run_id = str(row.get("run_id") or row.get("origin_run_id") or "").strip()
    if namespace and run_id:
        return f"{namespace} · {run_id}"
    if namespace:
        return namespace
    if run_id:
        return run_id
    observed = str(row.get("observed_at") or row.get("decision_evaluated_at") or "").strip()
    return f"{source} · {observed}" if observed else source


def _outcome_counts(rows: tuple[Mapping[str, Any], ...]) -> Counter[str]:
    return Counter(_outcome_bucket(row) for row in rows)


def _outcome_time(
    row: Mapping[str, Any],
    *,
    now: object = None,
) -> HtmlFragment:
    value = (
        row.get("outcome_evaluated_at")
        if _outcome_bucket(row) == "matured"
        else row.get("observed_at") or row.get("decision_evaluated_at")
    )
    if value in (None, ""):
        value = row.get("outcome_evaluated_at")
    return time_element(present_time(value, now=now))


def _cohort_label(
    value: object,
    score: object,
    *,
    actionability: bool = False,
) -> str:
    text = str(value or "").strip()
    if text:
        parts = text.split("_")
        if len(parts) == 2 and all(part.replace(".", "", 1).isdigit() for part in parts):
            return f"{parts[0]}–{parts[1]}"
        return humanize_enum(text)
    number = _number(score)
    if number is None:
        return UNAVAILABLE
    if actionability:
        if number >= 85:
            return "85–100"
        if number >= 70:
            return "70–84"
        if number >= 50:
            return "50–69"
        if number >= 25:
            return "25–49"
        return "0–24"
    if number < 25:
        return "0–24"
    if number < 45:
        return "25–44"
    if number < 65:
        return "45–64"
    if number < 80:
        return "65–79"
    return "80–100"


def _compact_generation_identity(value: object) -> HtmlFragment:
    exact = str(value or UNAVAILABLE)
    if len(exact) <= 38:
        return HtmlFragment(escape_html(exact))
    namespace, separator, run_id = exact.partition(" · ")
    namespace_label = namespace if len(namespace) <= 25 else namespace[:24] + "…"
    run_label = run_id if len(run_id) <= 10 else run_id[:9] + "…"
    visible = f"{namespace_label}{separator}{run_label}" if separator else namespace_label
    return HtmlFragment(
        f'<span class="compact-identity" title="{escape_html(exact)}">'
        f'{escape_html(visible)}</span>'
    )


def _outcome_cohort_cell(
    *,
    actionability: str,
    evidence: str,
    risk: str,
) -> HtmlFragment:
    accessible = (
        f"Actionability {actionability}; evidence {evidence}; risk {risk}."
    )
    return HtmlFragment(
        f'<span class="table-cohort-cell" aria-label="{escape_html(accessible)}">'
        '<span><small>Actionability</small>'
        f'<strong>{escape_html(actionability)}</strong></span>'
        '<span><small>Evidence</small>'
        f'<strong>{escape_html(evidence)}</strong></span>'
        '<span><small>Risk</small>'
        f'<strong>{escape_html(risk)}</strong></span>'
        '</span>'
    )


def _outcome_state_result_cell(state: str, result: str) -> HtmlFragment:
    result_detail = (
        f'<small>{escape_html(result)}</small>'
        if result != UNAVAILABLE
        else ""
    )
    return HtmlFragment(
        '<span class="table-stack-cell outcome-state-cell">'
        f'{badge(state)}{result_detail}</span>'
    )


def _outcome_generation_cell(generation: object, source: object) -> HtmlFragment:
    exact_generation = str(generation or UNAVAILABLE)
    exact_source = str(source or UNAVAILABLE)
    accessible = (
        f"Exact generation identity: {exact_generation}. "
        f"Provenance scope: {exact_source}."
    )
    visible_identity = (
        HtmlFragment('<span class="compact-identity">Current run</span>')
        if exact_source == "Exact generation"
        else _compact_generation_identity(exact_generation)
    )
    return HtmlFragment(
        f'<span class="table-identity-cell" title="{escape_html(accessible)}">'
        f'{visible_identity}'
        f'<small>{escape_html(exact_source)}</small>'
        f'<span class="sr-only">{escape_html(accessible)}</span>'
        '</span>'
    )


def _sample_warning(matured: int, *, scope: str) -> str:
    if matured == 0:
        return (
            '<p class="sample-note"><strong>Observation stage.</strong> '
            f'The {escape_html(scope)} has no matured outcome rows yet. '
            'This is an observation-stage state, not evidence of zero edge. '
            'Do not infer edge or change thresholds.</p>'
        )
    if matured >= 30:
        return (
            '<div class="alert alert-positive"><div><strong>Sample-size checkpoint</strong>'
            f'<p>{matured} matured rows in the {escape_html(scope)}. Cohort diversity still matters.</p></div></div>'
        )
    return (
        '<div class="alert alert-warning"><div><strong>Small-sample warning</strong>'
        f'<p>Only {matured} matured row{"s" if matured != 1 else ""} in the {escape_html(scope)}. '
        'Do not infer edge or change thresholds from this sample.</p></div></div>'
    )


def _outcome_filter_form(filters: Mapping[str, str]) -> str:
    advanced_active = filters["status"] != "all" or bool(filters["route"])
    active_count = sum((
        filters["scope"] != "all",
        filters["status"] != "all",
        bool(filters["route"]),
        bool(filters["search"]),
    ))
    form = (
        '<form class="filter-panel embedded-filter-panel" method="get" action="/outcomes">'
        '<div class="filter-grid-primary">'
        f'<label class="filter-search"><span>Search idea</span><input type="search" name="search" value="{escape_html(filters["search"])}" placeholder="BTC, DEXE…"></label>'
        f'<label><span>Scope</span><select name="scope">{_options(filters["scope"], (("all", "Current + historical"), ("current", "Exact current"), ("historical", "Historical")))}</select></label>'
        '</div><details class="disclosure filter-advanced"'
        + (' open' if advanced_active else '')
        + '><summary>State and route <span class="disclosure__summary">Optional filters</span></summary>'
        '<div class="filter-grid-advanced">'
        f'<label><span>State</span><select name="status">{_options(filters["status"], (("all", "Pending + matured + unavailable"), ("pending", "Pending"), ("matured", "Matured"), ("unavailable", "Unavailable / incomplete")))}</select></label>'
        f'<label><span>Route</span><select name="route">{_options(filters["route"], (("", "All routes"), *_OUTCOME_ROUTE_OPTIONS))}</select></label>'
        '</div></details><div class="filter-actions"><button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/outcomes">Clear</a></div></form>'
    )
    return str(disclosure(
        "Filter outcomes",
        HtmlFragment(form),
        summary=f"{active_count} active",
        open=bool(active_count),
        css_class="filter-disclosure outcome-filter-disclosure",
    ))


def _options(selected: str, values: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'<option value="{escape_html(value)}"{" selected" if selected == value else ""}>{escape_html(label)}</option>'
        for value, label in values
    )


__all__ = ("render_outcomes_page",)
