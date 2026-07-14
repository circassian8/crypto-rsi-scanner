"""Operator-facing exact-generation calendar page.

This module is presentation-only.  It renders the calendar rows already bound
to :class:`DashboardSnapshot`; it never discovers a file, calls a provider, or
changes calendar/provider configuration.
"""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import quote

from .components import (
    HtmlFragment,
    badge,
    chips,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
    link,
    safe_external_href,
    time_element,
)
from .loader import candidate_identifier
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_duration,
    format_exact_utc,
    format_number,
    humanize_enum,
    humanize_reason,
    present_calendar_window,
    present_time,
)


_NEXT_SAFE_ACTION = (
    "Configure RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH with a fresh non-fixture "
    "operator-verified snapshot, then run make radar-market-no-send-readiness"
)
_FILTER_FIELDS = ("search", "importance", "category", "scope")
_GLOBAL_ASSETS = {"ALL", "CRYPTO", "CRYPTO_MARKET", "GLOBAL", "MARKET", "MARKET_WIDE"}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr|d|day|w|week)s?\s*$", re.I)
_UTC = timezone.utc


@dataclass(frozen=True)
class _CalendarState:
    key: str
    label: str
    tone: str
    title: str
    message: str
    needs_snapshot_action: bool
    metadata: Mapping[str, Any]


def render_calendar_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    """Render the responsive calendar workspace for one exact generation."""

    if not snapshot.generation_authoritative:
        return str(
            _calendar_state_panel(
                _CalendarState(
                    key="untrusted",
                    label="Current calendar suppressed",
                    tone="danger",
                    title="This generation is not trusted",
                    message=(
                        "Exact-generation authority checks did not pass, so calendar rows are "
                        "not shown as current. Review System Health before using this schedule."
                    ),
                    needs_snapshot_action=False,
                    metadata={
                        "authority_status": snapshot.generation_authority_status,
                        "authority_reasons": snapshot.generation_authority_reasons,
                    },
                ),
                row_count=0,
                snapshot=snapshot,
            )
        )

    rows = tuple(snapshot.current_calendar_events)
    state = _calendar_state(snapshot, has_rows=bool(rows))
    status = _calendar_state_panel(state, row_count=len(rows), snapshot=snapshot)
    if not rows:
        return str(status)

    filters = _calendar_query(query)
    selected = tuple(row for row in rows if _matches_filters(row, filters))
    controls = _filter_controls(rows, filters, selected_count=len(selected))
    if not selected:
        no_results = empty_state(
            "No calendar events match these filters",
            "The exact generation still contains calendar rows. Clear or adjust the filters to see them.",
            action_label="Clear calendar filters",
            action_href="/calendar",
        )
        return str(HtmlFragment(str(status) + str(controls) + str(no_results)))

    grouped = _group_events(selected, clock=snapshot.generation_authority_checked_at)
    rendered_groups: list[str] = []
    event_index = 0
    for group_index, (heading, group_rows) in enumerate(grouped, start=1):
        cards: list[str] = []
        for row in group_rows:
            event_index += 1
            cards.append(
                str(
                    _event_card(
                        snapshot,
                        row,
                        index=event_index,
                        clock=snapshot.generation_authority_checked_at,
                    )
                )
            )
        rendered_groups.append(
            f'<section class="calendar-day" aria-labelledby="calendar-day-{group_index}">'
            f'<header class="section-heading cluster"><h2 id="calendar-day-{group_index}">'
            f'{escape_html(heading)}</h2><span class="count-label">'
            f'{len(group_rows)} event{"s" if len(group_rows) != 1 else ""}</span></header>'
            f'<div class="card-grid calendar-grid">{"".join(cards)}</div></section>'
        )
    return str(HtmlFragment(str(status) + str(controls) + "".join(rendered_groups)))


def _calendar_state(snapshot: DashboardSnapshot, *, has_rows: bool) -> _CalendarState:
    raw = snapshot.market_generation.get("calendar_snapshot")
    metadata = raw if isinstance(raw, Mapping) else {}
    if has_rows:
        return _CalendarState(
            "observed",
            "Observed for this exact generation",
            "positive",
            "Calendar coverage is current",
            "Only fingerprint-bound rows from the current operator generation are shown.",
            False,
            metadata,
        )

    status = _token(metadata.get("status"))
    error = _token(metadata.get("error_class") or metadata.get("error"))
    configured = metadata.get("configured")
    rejected_count = _finite_number(metadata.get("normalization_rejected_count")) or 0.0
    combined = f"{status} {error}"
    if rejected_count > 0 or any(word in combined for word in ("reject", "invalid", "fixture_provenance")):
        rejection_message = (
            "Retained calendar rows failed unified-calendar normalization. This empty dashboard "
            "layer is a normalization failure, not evidence that no scheduled events exist."
            if rejected_count > 0
            else (
                "Fixture, test, mock, or replay calendar provenance was rejected for this live "
                "generation. Zero rows is not evidence that no scheduled events exist."
                if "fixture" in combined
                else (
                    "The configured calendar provenance was rejected by admission checks. Zero "
                    "rows is not evidence that no scheduled events exist."
                )
            )
        )
        return _CalendarState(
            "rejected",
            "Snapshot rejected",
            "danger",
            "Calendar input did not pass admission",
            rejection_message,
            True,
            metadata,
        )
    if "stale" in combined or "too_old" in combined:
        return _CalendarState(
            "stale",
            "Snapshot stale",
            "danger",
            "Calendar input is out of date",
            (
                "The configured calendar snapshot was stale and was not admitted into this exact "
                "generation. Zero rows is not evidence that no scheduled events exist."
            ),
            True,
            metadata,
        )
    if configured is False or status in {
        "missing_config",
        "not_configured",
        "skipped_missing_config",
    }:
        return _CalendarState(
            "not_configured",
            "Not configured",
            "muted",
            "No calendar snapshot was configured",
            (
                "Calendar acquisition was not configured for this generation. This layer was "
                "unavailable, and zero rows is not evidence that no scheduled events exist."
            ),
            True,
            metadata,
        )
    if status in {
        "complete",
        "healthy_empty",
        "observed",
        "observed_no_results",
        "usable",
    } and rejected_count == 0:
        return _CalendarState(
            "healthy_empty",
            "Observed · no scheduled events",
            "positive",
            "The observed calendar is empty",
            (
                "The calendar snapshot was observed for this exact generation and produced zero "
                "retained events. This is a healthy empty result, not missing coverage."
            ),
            False,
            metadata,
        )

    if status in {"degraded", "failed", "unavailable"} or error:
        return _CalendarState(
            "unavailable",
            "Coverage unavailable",
            "warning",
            "Calendar acquisition is unavailable",
            (
                "Calendar acquisition failed or was unavailable. This layer is unavailable, and "
                "zero rows is not evidence that no scheduled events exist."
            ),
            True,
            metadata,
        )

    fallback = _source_pack_calendar_state(snapshot)
    if fallback is not None:
        return fallback
    return _CalendarState(
        "unavailable",
        "Coverage unavailable",
        "warning",
        "Calendar coverage was not fully observed",
        (
            "No accepted exact-generation calendar rows or complete acquisition receipt is "
            "available. Treat the schedule as unknown, not quiet."
        ),
        True,
        metadata,
    )


def _source_pack_calendar_state(snapshot: DashboardSnapshot) -> _CalendarState | None:
    packs = snapshot.source_coverage.get("packs")
    if not isinstance(packs, Iterable) or isinstance(packs, (str, bytes, Mapping)):
        return None
    statuses = {
        _token(row.get("provider_coverage_status") or row.get("source_pack_coverage_status"))
        for row in packs
        if isinstance(row, Mapping)
        and _token(row.get("source_pack")) in {"unified_calendar_pack", "unlock_supply_pack"}
    }
    statuses.discard("")
    metadata = {"legacy_source_pack_statuses": sorted(statuses)}
    if statuses and statuses <= {"not_configured", "missing_config"}:
        return _CalendarState(
            "not_configured",
            "Not configured",
            "muted",
            "No calendar source pack was configured",
            (
                "Relevant source packs were not configured for this generation. This layer was "
                "unavailable, and zero rows is not evidence that no relevant events exist."
            ),
            True,
            metadata,
        )
    if statuses & {"complete", "observed_healthy", "observed_no_results"}:
        return _CalendarState(
            "healthy_empty",
            "Observed · no scheduled events",
            "positive",
            "The observed calendar is empty",
            "Configured calendar coverage was observed and retained zero exact-generation events.",
            False,
            metadata,
        )
    if statuses:
        return _CalendarState(
            "unavailable",
            "Coverage incomplete",
            "warning",
            "Calendar coverage is incomplete",
            "At least one relevant source pack was skipped, degraded, or unavailable.",
            True,
            metadata,
        )
    return None


def _calendar_state_panel(
    state: _CalendarState,
    *,
    row_count: int,
    snapshot: DashboardSnapshot,
) -> HtmlFragment:
    count = (
        f"{row_count} exact-generation event{'s' if row_count != 1 else ''}."
        if row_count
        else "No exact-generation events."
    )
    action = ""
    if state.needs_snapshot_action:
        action = f'<p class="next-action"><strong>Next safe action:</strong> {escape_html(_NEXT_SAFE_ACTION)}.</p>'
    elif state.key == "healthy_empty":
        action = (
            '<p class="next-action"><strong>Next safe action:</strong> No corrective action is required. '
            f'For a newer operator snapshot, {escape_html(_NEXT_SAFE_ACTION)}.</p>'
        )
    metadata = _calendar_metadata_disclosure(state.metadata, snapshot=snapshot)
    return HtmlFragment(
        '<section class="panel calendar-coverage" aria-labelledby="calendar-coverage-title">'
        '<div class="section-heading cluster"><div><p class="eyebrow">Exact-generation coverage</p>'
        f'<h2 id="calendar-coverage-title">{escape_html(state.title)}</h2></div>'
        f'{badge(state.key, tone=state.tone, label=state.label)}</div>'
        f'<p>{escape_html(state.message)} <span class="muted">{escape_html(count)}</span></p>'
        f'{action}{metadata}</section>'
    )


def _calendar_metadata_disclosure(
    metadata: Mapping[str, Any],
    *,
    snapshot: DashboardSnapshot,
) -> HtmlFragment:
    counts = metadata.get("counts")
    count_text = ""
    if isinstance(counts, Mapping):
        count_text = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    elif metadata.get("retained_row_count") is not None:
        count_text = str(metadata.get("retained_row_count"))
    items = (
        ("Recorded status", metadata.get("status") or UNAVAILABLE),
        ("Coverage receipt", _calendar_receipt_label(metadata)),
        ("Configured", metadata.get("configured") if metadata.get("configured") is not None else UNAVAILABLE),
        ("Read error class", metadata.get("error_class") or metadata.get("error") or "None recorded"),
        ("Retained / reported counts", count_text or "Not recorded"),
        ("Normalization rejected", metadata.get("normalization_rejected_count") or 0),
        ("Legacy source-pack statuses", ", ".join(metadata.get("legacy_source_pack_statuses") or ()) or "Not applicable"),
        (
            "Current generation",
            f"Current generation: {snapshot.artifact_namespace}; namespace-local core store rows {snapshot.cumulative_store_count}",
        ),
    )
    return disclosure("Exact calendar coverage metadata", definition_list(items))


def _calendar_receipt_label(metadata: Mapping[str, Any]) -> str:
    parts = [f"status={metadata.get('status') or 'unknown'}"]
    configured = metadata.get("configured")
    if configured is not None:
        parts.append(f"configured={str(configured).lower() if isinstance(configured, bool) else configured}")
    counts = metadata.get("counts")
    if isinstance(counts, Mapping):
        parts.extend(f"{key}={value}" for key, value in sorted(counts.items()))
    for field in (
        "scheduled_row_count",
        "unlock_row_count",
        "calendar_row_count",
        "event_count",
        "retained_row_count",
        "unified_calendar_count",
        "normalization_rejected_count",
        "normalization_status",
    ):
        if metadata.get(field) is not None:
            parts.append(f"{field}={metadata.get(field)}")
    return "; ".join(parts)


def _filter_controls(
    rows: tuple[Mapping[str, Any], ...],
    filters: Mapping[str, str],
    *,
    selected_count: int,
) -> HtmlFragment:
    importance = sorted({_importance(row) for row in rows}, key=_importance_sort)
    categories = sorted({value for row in rows for value in _category_tokens(row)})
    scopes = sorted({_scope(row) for row in rows})
    search = escape_html(filters.get("search", ""))
    fields = (
        '<label class="filter-search" for="calendar-search"><span>Search</span>'
        f'<input id="calendar-search" name="search" type="search" maxlength="120" value="{search}" '
        'placeholder="Event, asset, or source"></label>'
        + _select("importance", "Importance", importance, filters.get("importance"))
        + _select("category", "Category", categories, filters.get("category"))
        + _select("scope", "Scope", scopes, filters.get("scope"))
    )
    summary = (
        f'<p class="result-summary" role="status">Showing <strong>{selected_count}</strong> of '
        f'<strong>{len(rows)}</strong> exact-generation events, ordered chronologically.</p>'
    )
    return HtmlFragment(
        '<form class="filter-panel calendar-filters" action="/calendar" method="get" '
        'aria-label="Filter calendar events"><div class="section-heading"><div>'
        '<p class="eyebrow">Calendar controls</p><h2>Find scheduled risk</h2></div></div>'
        f'<div class="filter-grid">{fields}</div><div class="filter-actions cluster">'
        '<button class="button button-primary" type="submit">Apply filters</button>'
        '<a class="button button-quiet" href="/calendar">Clear</a></div>'
        f'{summary}</form>'
    )


def _select(name: str, label: str, values: Iterable[str], selected: str | None) -> str:
    options = ['<option value="">All</option>']
    for value in values:
        selected_attr = " selected" if value == selected else ""
        options.append(
            f'<option value="{escape_html(value)}"{selected_attr}>{escape_html(_filter_label(name, value))}</option>'
        )
    return (
        f'<label for="calendar-{escape_html(name)}"><span>{escape_html(label)}</span>'
        f'<select id="calendar-{escape_html(name)}" name="{escape_html(name)}">'
        f'{"".join(options)}</select></label>'
    )


def _filter_label(name: str, value: str) -> str:
    if name == "importance":
        return f"{humanize_enum(value)} impact"
    if name == "scope":
        return "Market-wide" if value == "market_wide" else "Asset-specific"
    return humanize_enum(value)


def _event_card(
    snapshot: DashboardSnapshot,
    row: Mapping[str, Any],
    *,
    index: int,
    clock: str | None,
) -> HtmlFragment:
    importance = _importance(row)
    category = next(iter(_category_tokens(row)), "unclassified")
    scope = _scope(row)
    certainty = _token(row.get("time_certainty")) or "unknown"
    exact_time = _event_is_exact(row)
    title = str(row.get("title") or "Untitled scheduled event")
    timing = _event_time(row, clock=clock)
    assets = _assets(row)
    ideas = _nearby_ideas(snapshot, row)
    metrics = _economic_metrics(row)
    impact = _impact_window(row)
    reminders = _reminder_labels(row.get("reminder_windows"))
    source = _source(row)
    source_html = (
        link(
            f"View {source[0]}",
            source[1],
            aria_label=f"Open source for {title}",
            css_class="source-link",
        )
        if source[1]
        else HtmlFragment(f'<span class="unavailable">{escape_html(source[0])} · source link unavailable</span>')
    )
    high_impact = importance in {"critical", "high"}
    classes = "calendar-event-card card" + (" calendar-event-card--high-impact" if high_impact else "")
    heading_id = f"calendar-event-{index}"
    context_parts = []
    if metrics:
        context_parts.append(str(metrics))
    context_parts.append(
        '<div class="calendar-context grid"><div><h4>Affected scope</h4>'
        + str(chips(assets or ("market_wide",), aria_label="Affected assets"))
        + '</div><div><h4>Impact window</h4><p>'
        + escape_html(impact)
        + "</p></div><div><h4>Display reminders</h4>"
        + str(chips(reminders, aria_label="Display reminder windows", empty="None recorded"))
        + "</div></div>"
    )
    ideas_html = _ideas_block(ideas)
    metadata = disclosure("Exact event metadata", _event_metadata(row))
    return HtmlFragment(
        f'<article class="{classes}" aria-labelledby="{heading_id}">'
        '<header class="calendar-event-card__header"><div class="badge-row cluster">'
        f'{badge(importance, tone=_importance_tone(importance), label=f"{humanize_enum(importance)} impact")}'
        f'{badge(category, tone="info", label=humanize_enum(category))}'
        f'{badge(scope, tone="neutral", label=_filter_label("scope", scope))}'
        f'{badge(certainty, tone="positive" if exact_time else "warning", label=_certainty_label(certainty, has_window=not exact_time and _has_window(row)))}'
        f'</div><h3 id="{heading_id}">{escape_html(title)}</h3>{timing}</header>'
        f'<div class="calendar-event-card__body">{"".join(context_parts)}{ideas_html}'
        f'<footer class="calendar-event-card__footer">{source_html}</footer>{metadata}</div></article>'
    )


def _event_time(row: Mapping[str, Any], *, clock: str | None) -> HtmlFragment:
    scheduled = row.get("scheduled_at")
    if _event_is_exact(row):
        presented = present_time(scheduled, now=clock)
        return HtmlFragment(
            '<p class="calendar-event-time"><span class="sr-only">Scheduled </span>'
            f'{time_element(presented)}<span class="time-note">Local operator time</span></p>'
        )
    window = present_calendar_window(
        scheduled_at=scheduled,
        window_start=row.get("window_start"),
        window_end=row.get("window_end"),
        time_certainty=row.get("time_certainty"),
        now=clock,
    )
    label = window.label.replace("Window: Window: ", "Window: ", 1)
    relative = (
        f'<span class="countdown">{escape_html(window.relative_label)} until window opens</span>'
        if window.relative_label not in {"", UNAVAILABLE}
        and window.relative_label.startswith("in ")
        else (
            f'<span class="countdown">Window opened {escape_html(window.relative_label)}</span>'
            if window.relative_label not in {"", UNAVAILABLE}
            else ""
        )
    )
    return HtmlFragment(
        '<p class="calendar-event-time calendar-event-time--uncertain">'
        f'<span>{escape_html(label)}</span>{relative}'
        '<span class="time-note">Timing is not an exact appointment</span></p>'
    )


def _economic_metrics(row: Mapping[str, Any]) -> HtmlFragment:
    values = (
        ("Previous", row.get("previous_value"), False),
        ("Forecast", row.get("forecast_value"), False),
        ("Actual", row.get("actual_value"), False),
        ("Surprise", row.get("surprise_value"), True),
    )
    if all(value is None for _, value, _ in values):
        return HtmlFragment("")
    items = [
        (label, _metric_value(value, signed=signed))
        for label, value, signed in values
    ]
    sequence = " / ".join(
        _metric_value(value, signed=signed) for _, value, signed in values
    )
    return HtmlFragment(
        '<div class="calendar-release-data" aria-label="Release data"><h4>Release data</h4>'
        f'{definition_list(items, css_class="metric-grid")}'
        '<p class="release-sequence"><strong>Previous / forecast / actual / surprise:</strong> '
        f'{escape_html(sequence)}</p></div>'
    )


def _metric_value(value: object, *, signed: bool) -> str:
    if value is None:
        return "Awaiting release"
    formatted = format_number(value, decimals=2, signed=signed)
    if formatted != UNAVAILABLE:
        return formatted
    text = str(value).strip()
    return text[:80] if text else UNAVAILABLE


def _ideas_block(ideas: tuple[tuple[Mapping[str, Any], str], ...]) -> str:
    if not ideas:
        return '<div class="nearby-ideas"><h4>Nearby active ideas</h4><p class="muted">No active exact-generation idea is linked by calendar evidence or affected asset.</p></div>'
    items = []
    for row, match in ideas:
        identifier = candidate_identifier(row)
        symbol = row.get("symbol") or row.get("coin_id") or "Unknown asset"
        route = row.get("_dashboard_route") or row.get("radar_route") or "diagnostic"
        match_label = "Calendar evidence" if match == "evidence" else "Affected asset"
        items.append(
            '<li><div>'
            + str(link(f"{symbol} · {humanize_enum(route)}", f"/ideas/{quote(identifier, safe='')}"))
            + f'<span class="muted">{escape_html(_operator_text(row.get("why_now"), reason=True, fallback="Open the idea for decision context."))}</span>'
            + f'</div>{badge(match, tone="info", label=match_label)}</li>'
        )
    return '<div class="nearby-ideas"><h4>Nearby active ideas</h4><ul class="idea-link-list">' + "".join(items) + "</ul></div>"


def _nearby_ideas(
    snapshot: DashboardSnapshot,
    event: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], str], ...]:
    event_id = str(event.get("calendar_event_id") or "").strip()
    event_assets = _asset_tokens(event)
    matches: list[tuple[Mapping[str, Any], str]] = []
    for row in snapshot.visible_current_candidates:
        if row.get("_decision_expired_at_read_time") is True:
            continue
        evidence_ids = _candidate_calendar_ids(row)
        direct = bool(event_id and event_id in evidence_ids)
        asset_match = bool(event_assets & _candidate_asset_tokens(row))
        if direct or asset_match:
            matches.append((row, "evidence" if direct else "asset"))
    matches.sort(
        key=lambda pair: (
            pair[1] != "evidence",
            -(_finite_number(pair[0].get("urgency_score")) or 0.0),
            str(pair[0].get("symbol") or pair[0].get("coin_id") or ""),
        )
    )
    return tuple(matches)


def _candidate_calendar_ids(row: Mapping[str, Any]) -> set[str]:
    ids = {str(value).strip() for value in _iter_values(row.get("calendar_evidence_ids")) if str(value).strip()}
    for field in ("calendar_evidence", "unified_calendar_context"):
        for value in _iter_values(row.get(field)):
            if isinstance(value, Mapping):
                event_id = str(value.get("calendar_event_id") or "").strip()
                if event_id:
                    ids.add(event_id)
    single = row.get("unified_calendar_event")
    if isinstance(single, Mapping) and single.get("calendar_event_id"):
        ids.add(str(single.get("calendar_event_id")).strip())
    return ids


def _candidate_asset_tokens(row: Mapping[str, Any]) -> set[str]:
    values: list[object] = [
        row.get("symbol"),
        row.get("validated_symbol"),
        row.get("coin_id"),
        row.get("validated_coin_id"),
    ]
    values.extend(_iter_values(row.get("affected_assets")))
    return {_asset_token(value) for value in values if _asset_token(value)}


def _event_metadata(row: Mapping[str, Any]) -> HtmlFragment:
    exact_time = format_exact_utc(row.get("scheduled_at")) if _event_is_exact(row) else "Not exact"
    certainty = _token(row.get("time_certainty")) or "unknown"
    items = (
        ("Calendar event ID", row.get("calendar_event_id") or UNAVAILABLE),
        ("Recorded timing certainty", row.get("time_certainty") or UNAVAILABLE),
        ("Recorded timing type", f"({certainty})"),
        ("Exact scheduled UTC", exact_time),
        ("Window start UTC", format_exact_utc(row.get("window_start"))),
        ("Window end UTC", format_exact_utc(row.get("window_end"))),
        ("Recorded scheduled value", row.get("scheduled_at") or "Not recorded"),
        ("Recorded window start", row.get("window_start") or "Not recorded"),
        ("Recorded window end", row.get("window_end") or "Not recorded"),
        ("Recorded impact window", _raw_impact_window(row)),
        ("Recorded source timezone", row.get("timezone") or UNAVAILABLE),
        ("Observed UTC", format_exact_utc(row.get("observed_at"))),
        ("Tracking status", row.get("post_event_tracking_status") or UNAVAILABLE),
        ("Source class", row.get("source_class") or row.get("event_kind") or UNAVAILABLE),
    )
    return definition_list(items, css_class="technical-grid")


def _raw_impact_window(row: Mapping[str, Any]) -> str:
    before = str(row.get("impact_window_before") or "").strip()
    after = str(row.get("impact_window_after") or "").strip()
    if before and after:
        return f"-{before} / +{after}"
    if before:
        return f"-{before}"
    if after:
        return f"+{after}"
    return "Not recorded"


def _calendar_query(query: Mapping[str, str] | None) -> dict[str, str]:
    if not isinstance(query, Mapping):
        return {}
    values: dict[str, str] = {}
    for field in _FILTER_FIELDS:
        raw = query.get(field)
        text = str(raw).strip().casefold() if isinstance(raw, str) else ""
        if text and len(text) <= 120:
            values[field] = text
    return values


def _matches_filters(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    if filters.get("importance") and filters["importance"] != _importance(row):
        return False
    if filters.get("category") and filters["category"] not in _category_tokens(row):
        return False
    if filters.get("scope") and filters["scope"] != _scope(row):
        return False
    search = filters.get("search")
    if search:
        text = " ".join(
            str(value or "")
            for value in (
                row.get("title"),
                row.get("source"),
                row.get("provider"),
                row.get("description"),
                " ".join(_assets(row)),
                " ".join(_category_tokens(row)),
            )
        ).casefold()
        if search not in text:
            return False
    return True


def _group_events(
    rows: tuple[Mapping[str, Any], ...],
    *,
    clock: str | None,
) -> tuple[tuple[str, tuple[Mapping[str, Any], ...]], ...]:
    ordered = sorted(rows, key=_event_sort_key)
    groups: OrderedDict[date | None, list[Mapping[str, Any]]] = OrderedDict()
    for row in ordered:
        instant = _event_instant(row)
        local_day = instant.astimezone().date() if instant is not None else None
        groups.setdefault(local_day, []).append(row)
    current = _parse_instant(clock)
    current_day = current.astimezone().date() if current is not None else datetime.now().astimezone().date()
    return tuple(
        (
            _day_heading(day, current_day),
            tuple(group_rows),
        )
        for day, group_rows in groups.items()
    )


def _event_sort_key(row: Mapping[str, Any]) -> tuple[datetime, str]:
    instant = _event_instant(row) or datetime.max.replace(tzinfo=_UTC)
    return instant, str(row.get("title") or "").casefold()


def _event_instant(row: Mapping[str, Any]) -> datetime | None:
    for field in ("window_start", "scheduled_at", "window_end"):
        parsed = _parse_instant(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_instant(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=_UTC)
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(normalized)
            except ValueError:
                return None
            parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=_UTC)
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_UTC)
    return parsed.astimezone(_UTC)


def _day_heading(day: date | None, current: date) -> str:
    if day is None:
        return "Date to be confirmed"
    relative = ""
    if day == current:
        relative = "Today · "
    elif (day - current).days == 1:
        relative = "Tomorrow · "
    year = f", {day.year}" if day.year != current.year else ""
    return f"{relative}{day:%A, %B} {day.day}{year}"


def _importance(row: Mapping[str, Any]) -> str:
    return _token(row.get("importance") or row.get("impact")) or "unknown"


def _importance_sort(value: str) -> tuple[int, str]:
    return ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(value, 9), value)


def _importance_tone(value: str) -> str:
    return {"critical": "danger", "high": "warning", "medium": "info", "low": "neutral"}.get(value, "muted")


def _certainty_label(value: str, *, has_window: bool = False) -> str:
    if has_window:
        return "Scheduled window"
    labels = {
        "confirmed": "Confirmed time",
        "exact": "Confirmed time",
        "scheduled": "Scheduled time",
        "window": "Scheduled window",
        "range": "Scheduled window",
        "approximate": "Approximate time",
        "estimated": "Approximate time",
        "date_only": "Date known · time unconfirmed",
        "unknown": "Timing unconfirmed",
        "unconfirmed": "Timing unconfirmed",
    }
    return labels.get(value, "Timing certainty not recorded")


def _event_is_exact(row: Mapping[str, Any]) -> bool:
    certainty = _token(row.get("time_certainty"))
    return (
        certainty in {"confirmed", "exact", "scheduled"}
        and row.get("scheduled_at") not in (None, "")
        and not _has_window(row)
    )


def _has_window(row: Mapping[str, Any]) -> bool:
    return row.get("window_start") not in (None, "") or row.get("window_end") not in (None, "")


def _category_tokens(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[object] = [row.get("category"), row.get("event_category"), row.get("event_kind")]
    values.extend(_iter_values(row.get("categories")))
    return tuple(dict.fromkeys(value for item in values if (value := _token(item))))


def _scope(row: Mapping[str, Any]) -> str:
    explicit = _token(row.get("scope") or row.get("market_scope"))
    if explicit in {"global", "market", "market_wide"}:
        return "market_wide"
    if explicit in {"asset", "asset_specific", "token_specific"}:
        return "asset_specific"
    assets = _asset_tokens(row)
    return "market_wide" if not assets or assets & _GLOBAL_ASSETS else "asset_specific"


def _assets(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in _iter_values(row.get("affected_assets")) if str(value).strip())


def _asset_tokens(row: Mapping[str, Any]) -> set[str]:
    return {_asset_token(value) for value in _assets(row) if _asset_token(value)}


def _asset_token(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _impact_window(row: Mapping[str, Any]) -> str:
    before = _duration_value(row.get("impact_window_before"))
    after = _duration_value(row.get("impact_window_after"))
    if before != UNAVAILABLE and after != UNAVAILABLE:
        return f"From {before} before through {after} after"
    if before != UNAVAILABLE:
        return f"Begins {before} before the event"
    if after != UNAVAILABLE:
        return f"Continues {after} after the event"
    return "Not recorded"


def _reminder_labels(value: object) -> tuple[str, ...]:
    labels = []
    for item in _iter_values(value):
        raw = item.get("offset") if isinstance(item, Mapping) else item
        label = _duration_value(raw)
        if label != UNAVAILABLE:
            labels.append(f"{label} before")
    return tuple(labels)


def _duration_value(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format_duration(value)
    match = _DURATION.fullmatch(str(value or ""))
    if not match:
        return UNAVAILABLE
    magnitude = float(match.group(1))
    unit = match.group(2).casefold()
    multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
        "d": 86400,
        "day": 86400,
        "w": 604800,
        "week": 604800,
    }[unit]
    return format_duration(magnitude * multiplier)


def _source(row: Mapping[str, Any]) -> tuple[str, str]:
    label = _operator_text(
        row.get("source") or row.get("provider"),
        fallback="Recorded source",
    )
    raw = str(row.get("source_url") or "").strip()
    if not raw:
        return label, ""
    safe_url = safe_external_href(raw)
    if safe_url is None:
        return label, ""
    return label, safe_url


def _operator_text(value: object, *, reason: bool = False, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if "_" in text and not any(character.isspace() for character in text):
        return humanize_reason(text) if reason else humanize_enum(text)
    return text


def _iter_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def _token(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


__all__ = ("render_calendar_page",)
