"""Operator-facing exact-generation calendar page.

This module is presentation-only.  It renders the calendar rows already bound
to :class:`DashboardSnapshot`; it never discovers a file, calls a provider, or
changes calendar/provider configuration.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    time_element,
)
from .calendar_values import (
    _asset_token,
    _asset_tokens,
    _assets,
    _category_tokens,
    _certainty_label,
    _day_heading,
    _duration_seconds,
    _duration_value,
    _event_instant,
    _event_is_exact,
    _event_sort_key,
    _finite_number,
    _has_window,
    _impact_window,
    _importance,
    _importance_sort,
    _importance_tone,
    _iter_values,
    _matches_filters,
    _operator_text,
    _parse_instant,
    _raw_impact_window,
    _reminder_labels,
    _scope,
    _source,
    _temporal_label,
    _temporal_tone,
    _token,
)
from .loader import candidate_identifier
from .layer_coverage import dashboard_layer_coverage_by_key
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_exact_utc,
    format_number,
    humanize_enum,
    present_calendar_window,
    present_time,
)


_NEXT_SAFE_ACTION = (
    "Configure RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH with a fresh non-fixture "
    "operator-verified snapshot, then run make radar-market-no-send-readiness"
)
_FILTER_FIELDS = ("search", "importance", "category", "scope", "time")
_TIME_FILTER_OPTIONS = (
    ("current", "Active + upcoming"),
    ("active", "Active risk window"),
    ("upcoming", "Upcoming"),
    ("past", "Past"),
    ("all", "All event history"),
)
_TEMPORAL_STATE_FIELD = "_dashboard_calendar_temporal_state"


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

    canonical_rows = tuple(snapshot.current_calendar_events)
    state = _calendar_state(snapshot, has_rows=bool(canonical_rows))
    status = _calendar_state_panel(state, row_count=len(canonical_rows), snapshot=snapshot)
    if not canonical_rows:
        return str(status)

    filters = _calendar_query(query)
    rows = tuple(
        _calendar_event_projection(
            row,
            clock=snapshot.generation_authority_checked_at,
        )
        for row in canonical_rows
    )
    past_count = sum(
        1 for row in rows if row.get(_TEMPORAL_STATE_FIELD) == "past"
    )
    selected = tuple(row for row in rows if _matches_filters(row, filters))
    controls = _filter_controls(rows, filters, selected_count=len(selected))
    if not selected:
        if filters["time"] == "current" and past_count:
            no_results = empty_state(
                "No active or upcoming calendar risk",
                (
                    f"This verified snapshot contains {past_count} past "
                    f"event{'s' if past_count != 1 else ''}, kept outside the default current view."
                ),
                action_label="Review past events",
                action_href="/calendar?time=past",
            )
        else:
            no_results = empty_state(
                "No calendar events match this view",
                "The exact generation still contains calendar rows. Clear or adjust the filters to see them.",
                action_label="Clear calendar filters",
                action_href="/calendar",
            )
        return str(HtmlFragment(str(status) + str(controls) + str(no_results)))

    grouped = _group_events(
        selected,
        clock=snapshot.generation_authority_checked_at,
        reverse=filters["time"] == "past",
    )
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
    past_summary = (
        _past_event_summary(past_count)
        if filters["time"] == "current" and past_count
        else ""
    )
    return str(
        HtmlFragment(
            str(status) + str(controls) + "".join(rendered_groups) + str(past_summary)
        )
    )


def _calendar_state(snapshot: DashboardSnapshot, *, has_rows: bool) -> _CalendarState:
    raw = snapshot.market_generation.get("calendar_snapshot")
    raw_metadata = raw if isinstance(raw, Mapping) else {}
    coverage = dashboard_layer_coverage_by_key(snapshot)["calendar"]
    metadata = {
        **raw_metadata,
        "canonical_coverage_status": coverage.status,
        "canonical_coverage_detail": coverage.detail,
    }
    raw_status = _token(
        raw_metadata.get("normalization_status") or raw_metadata.get("status")
    )
    raw_error = _token(raw_metadata.get("error_class") or raw_metadata.get("error"))
    raw_combined = f"{raw_status} {raw_error}"
    rejected_count = _finite_number(
        raw_metadata.get("normalization_rejected_count")
    )
    coverage_state = _calendar_coverage_state(
        snapshot,
        coverage=coverage,
        metadata=metadata,
        raw_metadata=raw_metadata,
        raw_combined=raw_combined,
        rejected_count=rejected_count,
        has_rows=has_rows,
    )
    if coverage_state is not None:
        return coverage_state
    return _calendar_receipt_state(snapshot, metadata=metadata)


def _calendar_coverage_state(
    snapshot: DashboardSnapshot,
    *,
    coverage: Any,
    metadata: Mapping[str, Any],
    raw_metadata: Mapping[str, Any],
    raw_combined: str,
    rejected_count: float | None,
    has_rows: bool,
) -> _CalendarState | None:
    if has_rows:
        if coverage.status == "degraded":
            return _CalendarState(
                "degraded",
                "Incomplete snapshot",
                "warning",
                "Calendar rows have coverage gaps",
                (
                    f"{coverage.detail} Admitted rows remain visible, but this is not a fully "
                    "verified-empty or complete-coverage claim."
                ),
                True,
                metadata,
            )
        return _CalendarState(
            "observed",
            "Verified snapshot",
            "positive",
            "Calendar snapshot verified",
            (
                "Fingerprint-bound rows from the exact operator generation are available. "
                "Active, upcoming, and past status is derived at dashboard read time."
            ),
            False,
            metadata,
        )

    if coverage.status == "healthy_empty":
        return _CalendarState(
            "healthy_empty",
            "Observed · no scheduled events",
            "positive",
            "The observed calendar is empty",
            coverage.detail,
            False,
            metadata,
        )
    if coverage.status == "not_configured":
        if not raw_metadata:
            legacy = _source_pack_calendar_state(snapshot)
            if legacy is not None:
                return legacy
        return _CalendarState(
            "not_configured",
            "Not configured",
            "muted",
            "No calendar snapshot was configured",
            (
                "Calendar acquisition was not configured for this generation; zero rows is "
                "not evidence that no scheduled events exist."
            ),
            True,
            metadata,
        )
    if coverage.status in {"rejected", "stale"}:
        if coverage.status == "stale":
            message = (
                "The configured calendar snapshot was stale and was not admitted. Zero rows "
                "is not evidence that no scheduled events exist."
            )
        elif rejected_count is not None and rejected_count > 0:
            message = (
                "Retained calendar rows failed unified-calendar normalization. Zero rows is "
                "not evidence that no scheduled events exist."
            )
        elif "fixture" in raw_combined:
            message = (
                "Fixture, test, mock, or replay calendar provenance was rejected for this live "
                "generation. Zero rows is not evidence that no scheduled events exist."
            )
        else:
            message = coverage.detail
        return _CalendarState(
            coverage.status,
            "Snapshot rejected" if coverage.status == "rejected" else "Snapshot stale",
            "danger",
            "Calendar input did not pass admission" if coverage.status == "rejected" else "Calendar input is out of date",
            message,
            True,
            metadata,
        )
    if coverage.status in {"degraded", "unavailable"}:
        return _CalendarState(
            "unavailable",
            "Coverage incomplete" if coverage.status == "degraded" else "Coverage unavailable",
            "warning",
            "Calendar coverage is incomplete" if coverage.status == "degraded" else "Calendar acquisition is unavailable",
            coverage.detail,
            True,
            metadata,
        )
    return None


def _calendar_receipt_state(
    snapshot: DashboardSnapshot,
    *,
    metadata: Mapping[str, Any],
) -> _CalendarState:
    status = _token(metadata.get("status"))
    error = _token(metadata.get("error_class") or metadata.get("error"))
    configured = metadata.get("configured")
    rejected_count = (
        _finite_number(metadata.get("normalization_rejected_count")) or 0.0
    )
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
        f"{row_count} exact-generation event{'s' if row_count != 1 else ''}"
        if row_count
        else "No exact-generation events"
    )
    action = _calendar_operator_action(state)
    metadata = _calendar_metadata_disclosure(state.metadata, snapshot=snapshot)
    if state.key == "observed":
        return HtmlFragment(
            '<section class="panel calendar-coverage calendar-coverage--verified" '
            'aria-labelledby="calendar-coverage-title">'
            '<div class="calendar-coverage__heading"><div>'
            '<p class="eyebrow">Exact-generation calendar</p>'
            f'<h2 id="calendar-coverage-title">{escape_html(state.title)}</h2></div>'
            f'{badge(state.key, tone=state.tone, label=state.label)}</div>'
            '<p class="calendar-coverage__receipt">'
            f'<strong>{escape_html(count)}</strong> · fingerprint-bound to this operator generation; '
            'timing is evaluated at dashboard read time.</p>'
            f'{metadata}</section>'
        )
    return HtmlFragment(
        '<section class="panel calendar-coverage" aria-labelledby="calendar-coverage-title">'
        '<div class="section-heading cluster"><div><p class="eyebrow">Exact-generation coverage</p>'
        f'<h2 id="calendar-coverage-title">{escape_html(state.title)}</h2></div>'
        f'{badge(state.key, tone=state.tone, label=state.label)}</div>'
        f'<p>{escape_html(state.message)} <span class="muted">{escape_html(count)}.</span></p>'
        f'{action}{metadata}</section>'
    )


def _past_event_summary(count: int) -> HtmlFragment:
    return HtmlFragment(
        '<section class="panel calendar-past-summary" aria-labelledby="calendar-past-title">'
        '<div class="section-heading cluster"><div><p class="eyebrow">Historical schedule</p>'
        '<h2 id="calendar-past-title">Past events</h2></div>'
        f'<span class="count-label">{count}</span></div>'
        f'<p>{count} event{"s" if count != 1 else ""} from this verified snapshot '
        'are preserved as historical context and excluded from the default current-risk view.</p>'
        + str(
            link(
                f'Review {count} past event{"s" if count != 1 else ""}',
                "/calendar?time=past",
                css_class="button button-quiet",
            )
        )
        + '</section>'
    )


def _calendar_operator_action(state: _CalendarState) -> str:
    if state.needs_snapshot_action:
        explanation = (
            "Calendar coverage is not available for this generation. Review System Health "
            "to see whether the snapshot is missing, stale, rejected, or unavailable before "
            "starting another no-send readiness check."
        )
        setup = _calendar_setup_disclosure(optional=False)
    elif state.key == "healthy_empty":
        explanation = (
            "No corrective action is required. Review System Health for the accepted coverage "
            "receipt, or open the optional setup instructions before requesting a newer snapshot."
        )
        setup = _calendar_setup_disclosure(optional=True)
    elif state.key == "untrusted":
        explanation = (
            "Current calendar content is suppressed. Review System Health before relying on "
            "this generation."
        )
        setup = ""
    else:
        return ""
    health_link = link(
        "Review System Health",
        "/health",
        aria_label="Review calendar coverage in System Health",
        css_class="button button-primary",
    )
    return (
        '<div class="calendar-operator-action"><p><strong>Operator next step:</strong> '
        f'{escape_html(explanation)}</p>{health_link}</div>{setup}'
    )


def _calendar_setup_disclosure(*, optional: bool) -> str:
    prefix = (
        "Optional refresh: "
        if optional
        else "Use only a fresh, non-fixture, operator-verified local snapshot. "
    )
    body = HtmlFragment(
        f'<p>{escape_html(prefix)}The Calendar page never enables a provider or performs a request.</p>'
        '<p class="next-action"><strong>Exact local readiness sequence:</strong> '
        f'{escape_html(_NEXT_SAFE_ACTION)}.</p>'
    )
    return str(disclosure("Calendar readiness and setup instructions", body))


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
    canonical_coverage = _calendar_coverage_label(
        metadata.get("canonical_coverage_status")
    )
    items = (
        ("Recorded status", metadata.get("status") or "Not recorded"),
        ("Coverage receipt", _calendar_receipt_label(metadata)),
        ("Source provider", metadata.get("source_provider") or "Not recorded"),
        (
            "Source / acquisition mode",
            f"{metadata.get('upstream_source_mode') or metadata.get('source_mode') or 'Not recorded'} / "
            f"{metadata.get('upstream_acquisition_mode') or 'Not recorded'}",
        ),
        (
            "Snapshot observed",
            time_element(
                present_time(
                    metadata.get("snapshot_observed_at"),
                    now=snapshot.generation_authority_checked_at,
                )
            ),
        ),
        ("Freshness basis", metadata.get("freshness_basis") or "Not recorded"),
        (
            "Source fingerprint",
            metadata.get("source_sha256")
            or metadata.get("canonical_rows_sha256")
            or "Not recorded",
        ),
        ("Configured", metadata.get("configured") if metadata.get("configured") is not None else "Not recorded"),
        ("Read error class", metadata.get("error_class") or metadata.get("error") or "Not recorded"),
        ("Retained / reported counts", count_text or "Not recorded"),
        (
            "Normalization rejected",
            metadata.get("normalization_rejected_count")
            if metadata.get("normalization_rejected_count") is not None
            else "Not recorded",
        ),
        ("Legacy source-pack statuses", ", ".join(metadata.get("legacy_source_pack_statuses") or ()) or "Not applicable"),
        (
            "Current generation",
            f"Current generation: {snapshot.artifact_namespace}; namespace-local core store rows {snapshot.cumulative_store_count}",
        ),
    )
    body = HtmlFragment(
        '<p class="calendar-coverage__authority"><strong>Canonical coverage:</strong> '
        f'{escape_html(canonical_coverage)}</p>{definition_list(items)}'
    )
    return disclosure("Producer receipt metadata", body)


def _calendar_coverage_label(value: object) -> str:
    status = _token(value)
    return {
        "healthy_nonempty": "Complete",
        "healthy_empty": "Complete · no scheduled events",
        "degraded": "Incomplete",
        "not_configured": "Not configured",
        "rejected": "Rejected",
        "stale": "Stale",
        "unavailable": "Unavailable",
    }.get(status, humanize_enum(status) if status else "Not recorded")


def _calendar_receipt_label(metadata: Mapping[str, Any]) -> str:
    parts = []
    if metadata.get("status") is not None:
        parts.append(f"status={metadata.get('status')}")
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
    return "; ".join(parts) or "Not recorded"


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
    primary_fields = (
        '<label class="filter-search" for="calendar-search"><span>Search</span>'
        f'<input id="calendar-search" name="search" type="search" maxlength="120" value="{search}" '
        'placeholder="Event, asset, or source"></label>'
        + _select("importance", "Importance", importance, filters.get("importance"))
        + _time_select(filters["time"])
    )
    advanced_fields = (
        _select("category", "Category", categories, filters.get("category"))
        + _select("scope", "Scope", scopes, filters.get("scope"))
    )
    advanced_count = sum(1 for name in ("category", "scope") if filters.get(name))
    advanced_open = " open" if advanced_count else ""
    result_summary = (
        f'<p class="result-summary" role="status">Showing <strong>{selected_count}</strong> of '
        f'<strong>{len(rows)}</strong> exact-generation events for the '
        f'{escape_html(_time_filter_label(filters["time"]).casefold())} view.</p>'
    )
    form = (
        '<form class="filter-panel embedded-filter-panel calendar-filters" action="/calendar" '
        'method="get" aria-label="Filter calendar events"><div class="section-heading"><div>'
        '<p class="eyebrow">Calendar controls</p><h2>Find scheduled risk</h2></div></div>'
        f'<div class="filter-grid">{primary_fields}</div>'
        '<details class="disclosure filter-advanced"'
        + advanced_open
        + '><summary><span>More calendar filters</span>'
        + f'<span class="filter-chip">{advanced_count} active</span></summary>'
        + f'<div class="disclosure__body"><div class="filter-grid">{advanced_fields}</div></div></details>'
        '<div class="filter-actions cluster">'
        '<button class="button button-primary" type="submit">Apply filters</button>'
        '<a class="button button-quiet" href="/calendar">Clear</a></div>'
        f'{result_summary}</form>'
    )
    active_count = sum(
        1 for name in ("search", "importance", "category", "scope") if filters.get(name)
    ) + (1 if filters.get("time", "current") != "current" else 0)
    open_attr = " open" if active_count else ""
    disclosure_summary = (
        f"{active_count} active · {selected_count} shown"
        if active_count
        else f"{selected_count} current"
    )
    return HtmlFragment(
        '<details class="disclosure filter-disclosure calendar-filter-disclosure"'
        + open_attr
        + '><summary><span>Filter calendar events</span>'
        f'<span class="disclosure__summary">{escape_html(disclosure_summary)}</span></summary>'
        f'<div class="disclosure__body">{form}</div></details>'
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


def _time_select(selected: str) -> str:
    options = "".join(
        f'<option value="{escape_html(value)}"'
        f'{" selected" if value == selected else ""}>{escape_html(label)}</option>'
        for value, label in _TIME_FILTER_OPTIONS
    )
    return (
        '<label for="calendar-time"><span>Time</span>'
        f'<select id="calendar-time" name="time">{options}</select></label>'
    )


def _time_filter_label(value: str) -> str:
    return dict(_TIME_FILTER_OPTIONS).get(value, "Active + upcoming")


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
    temporal_state = str(row.get(_TEMPORAL_STATE_FIELD) or "upcoming")
    classes = "calendar-event-card card" + (" calendar-event-card--high-impact" if high_impact else "")
    heading_id = f"calendar-event-{index}"
    visible_context = (
        '<div class="calendar-context grid"><div><h4>Affected assets</h4>'
        + str(chips(
            assets or ("Market-wide",),
            aria_label="Affected assets",
            humanize=False,
        ))
        + '</div><div><h4>Impact window</h4><p>'
        + escape_html(impact)
        + "</p></div></div>"
    )
    detail_sections = []
    if metrics:
        detail_sections.append(
            '<section class="calendar-detail-section"><h4>Release data</h4>'
            + str(metrics)
            + '</section>'
        )
    detail_sections.append(
        '<section class="calendar-detail-section"><h4>Display reminders</h4>'
        + str(chips(reminders, aria_label="Display reminder windows", empty="None recorded"))
        + '</section>'
    )
    detail_sections.append(
        '<section class="calendar-detail-section"><h4>Related ideas</h4>'
        + _ideas_block(ideas)
        + '</section>'
    )
    provenance = HtmlFragment(
        f'<footer class="calendar-event-card__footer">{source_html}</footer>'
        + str(_event_metadata(row))
    )
    detail_sections.append(
        '<section class="calendar-detail-section"><h4>Source and provenance</h4>'
        + str(provenance)
        + '</section>'
    )
    details = str(
        disclosure(
            "Event details",
            HtmlFragment("".join(detail_sections)),
            summary=(
                f'{len(reminders)} reminder{"s" if len(reminders) != 1 else ""} · '
                f'{len(ideas)} linked idea{"s" if len(ideas) != 1 else ""}'
            ),
            css_class="calendar-event-details",
        )
    )
    return HtmlFragment(
        f'<article class="{classes}" aria-labelledby="{heading_id}">'
        '<header class="calendar-event-card__header"><div class="badge-row cluster">'
        f'{badge(importance, tone=_importance_tone(importance), label=f"{humanize_enum(importance)} impact")}'
        f'{badge(category, tone="info", label=humanize_enum(category))}'
        f'{badge(temporal_state, tone=_temporal_tone(temporal_state), label=_temporal_label(temporal_state))}'
        f'</div><p class="calendar-event-meta">{escape_html(_filter_label("scope", scope))} · '
        f'{escape_html(_certainty_label(certainty, has_window=not exact_time and _has_window(row)))}</p>'
        f'<h3 id="{heading_id}">{escape_html(title)}</h3>{timing}</header>'
        f'<div class="calendar-event-card__body">{visible_context}{details}'
        '</div></article>'
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
        '<div class="calendar-release-data" aria-label="Release data">'
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
        return '<div class="nearby-ideas"><p class="muted">No active exact-generation idea is linked by calendar evidence or affected asset.</p></div>'
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
    return '<div class="nearby-ideas"><ul class="idea-link-list">' + "".join(items) + "</ul></div>"


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


def _calendar_event_projection(
    row: Mapping[str, Any],
    *,
    clock: str | None,
) -> Mapping[str, Any]:
    """Return a presentation-only temporal projection without changing the artifact row."""

    projected = dict(row)
    projected[_TEMPORAL_STATE_FIELD] = _calendar_temporal_state(row, clock=clock)
    return projected


def _calendar_temporal_state(
    row: Mapping[str, Any],
    *,
    clock: str | None,
) -> str:
    checked_at = _parse_instant(clock)
    if checked_at is None:
        return "upcoming"
    start, end = _calendar_event_bounds(row)
    if start is None or end is None:
        return "upcoming"
    before = _duration_seconds(row.get("impact_window_before")) or 0.0
    after = _duration_seconds(row.get("impact_window_after")) or 0.0
    active_start = start - timedelta(seconds=before)
    active_end = end + timedelta(seconds=after)
    if checked_at < active_start:
        return "upcoming"
    if checked_at <= active_end:
        return "active"
    return "past"


def calendar_temporal_state(
    row: Mapping[str, Any],
    *,
    clock: str | None,
) -> str:
    """Expose the read-time calendar state for other dashboard summaries."""

    return _calendar_temporal_state(row, clock=clock)


def _calendar_event_bounds(
    row: Mapping[str, Any],
) -> tuple[datetime | None, datetime | None]:
    if _has_window(row):
        start = _parse_instant(row.get("window_start"))
        end = _parse_instant(row.get("window_end"))
        start = start or end
        end = end or start
    else:
        scheduled = _parse_instant(row.get("scheduled_at"))
        if scheduled is not None and _token(row.get("time_certainty")) in {
            "date_known",
            "date_only",
            "day_only",
        }:
            start = scheduled.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        else:
            start = scheduled
            end = scheduled
    if start is not None and end is not None and end < start:
        return end, start
    return start, end


def _calendar_query(query: Mapping[str, str] | None) -> dict[str, str]:
    values: dict[str, str] = {"time": "current"}
    if not isinstance(query, Mapping):
        return values
    for field in _FILTER_FIELDS:
        raw = query.get(field)
        text = str(raw).strip().casefold() if isinstance(raw, str) else ""
        if text and len(text) <= 120:
            values[field] = text
    allowed_time = {value for value, _label in _TIME_FILTER_OPTIONS}
    if values["time"] not in allowed_time:
        values["time"] = "current"
    return values


def _group_events(
    rows: tuple[Mapping[str, Any], ...],
    *,
    clock: str | None,
    reverse: bool = False,
) -> tuple[tuple[str, tuple[Mapping[str, Any], ...]], ...]:
    ordered = sorted(rows, key=_event_sort_key, reverse=reverse)
    active = tuple(
        row for row in ordered
        if calendar_temporal_state(row, clock=clock) == "active"
    )
    active_ids = {id(row) for row in active}
    groups: OrderedDict[date | None, list[Mapping[str, Any]]] = OrderedDict()
    for row in ordered:
        if id(row) in active_ids:
            continue
        instant = _event_instant(row)
        local_day = instant.astimezone().date() if instant is not None else None
        groups.setdefault(local_day, []).append(row)
    current = _parse_instant(clock)
    current_day = current.astimezone().date() if current is not None else datetime.now().astimezone().date()
    dated = tuple(
        (
            _day_heading(day, current_day),
            tuple(group_rows),
        )
        for day, group_rows in groups.items()
    )
    return (("Active now", active), *dated) if active else dated


__all__ = ("calendar_temporal_state", "render_calendar_page")
