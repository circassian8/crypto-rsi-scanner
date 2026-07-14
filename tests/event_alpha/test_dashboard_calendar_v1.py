"""Operator Experience V1 calendar presentation regressions."""

from __future__ import annotations

import copy
import re
from dataclasses import replace
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.calendar_page import (
    calendar_temporal_state,
    render_calendar_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardSnapshot


_CLOCK = "2026-07-14T09:00:00+00:00"
_NEXT_SAFE_ACTION = (
    "Configure RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH with a fresh non-fixture "
    "operator-verified snapshot, then run make radar-market-no-send-readiness"
)


def _event(
    event_id: str,
    title: str,
    scheduled_at: str,
    *,
    event_kind: str,
    importance: str,
    assets: list[str],
    source_url: str = "https://calendar.example/events/current",
    time_certainty: str = "exact",
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, object]:
    return {
        "calendar_event_id": event_id,
        "title": title,
        "scheduled_at": scheduled_at,
        "window_start": window_start,
        "window_end": window_end,
        "time_certainty": time_certainty,
        "event_kind": event_kind,
        "importance": importance,
        "affected_assets": assets,
        "previous_value": 2.8 if event_kind == "inflation" else None,
        "forecast_value": 2.7 if event_kind == "inflation" else None,
        "actual_value": None,
        "surprise_value": None,
        "impact_window_before": "24h",
        "impact_window_after": "4h",
        "reminder_windows": ["24h", "1h"],
        "source": "Operator calendar",
        "source_url": source_url,
        "observed_at": "2026-07-14T08:58:00+00:00",
        "timezone": "UTC",
        "post_event_tracking_status": "upcoming",
    }


def _candidate(
    candidate_id: str,
    symbol: str,
    *,
    calendar_ids: list[str] | None = None,
    route: str = "calendar_risk",
    expired: bool = False,
) -> dict[str, object]:
    return {
        "core_opportunity_id": candidate_id,
        "symbol": symbol,
        "coin_id": symbol.casefold(),
        "_decision_model_status": "v2",
        "_dashboard_route": route,
        "radar_route": route,
        "radar_actionable": route in {"actionable_watch", "high_confidence_watch"},
        "calendar_evidence_ids": calendar_ids or [],
        "urgency_score": 61,
        "why_now": "Scheduled context is close enough to review.",
        "_decision_expired_at_read_time": expired,
    }


def _snapshot(
    *,
    events: tuple[dict[str, object], ...] = (),
    candidates: tuple[dict[str, object], ...] = (),
    calendar_snapshot: dict[str, object] | None = None,
) -> DashboardSnapshot:
    return DashboardSnapshot(
        namespace_dir=Path("/tmp/exact-calendar-generation"),
        run_id="2026-07-14T08:59:00+00:00|no_key_live",
        profile="no_key_live",
        artifact_namespace="radar_market_no_send_exact",
        revision=7,
        manifest_status="complete",
        doctor_status="ok",
        doctor_verified_revision=7,
        generation_authority_status="authoritative",
        generation_authority_reasons=(),
        generation_authority_checked_at=_CLOCK,
        operator_state_sha256="a" * 64,
        operator_state={"research_only": True, "send_attempted": False},
        current_candidates=candidates,
        current_calendar_events=events,
        market_generation=(
            {"calendar_snapshot": calendar_snapshot}
            if calendar_snapshot is not None
            else {}
        ),
    )


def _rich_snapshot() -> DashboardSnapshot:
    inflation = _event(
        "cal-inflation",
        "United States inflation release",
        "2026-07-14T10:00:00+00:00",
        event_kind="inflation",
        importance="critical",
        assets=["BTC", "ETH", "CRYPTO_MARKET"],
    )
    unlock = _event(
        "cal-unlock",
        "TEST scheduled token unlock",
        "2026-07-15T08:00:00+00:00",
        event_kind="crypto_unlock",
        importance="high",
        assets=["TEST"],
        source_url="javascript:alert(document.cookie)",
    )
    window = _event(
        "cal-window",
        "Expected regulatory decision window",
        "2026-07-16T12:00:00+00:00",
        event_kind="regulatory_decision",
        importance="medium",
        assets=["RISK"],
        time_certainty="window",
        window_start="2026-07-20T00:00:00+00:00",
        window_end="2026-07-21T23:59:59+00:00",
    )
    candidates = (
        _candidate("core:inflation", "BTC", calendar_ids=["cal-inflation"]),
        _candidate("core:unlock", "TEST", route="dashboard_watch"),
        _candidate("core:diagnostic", "BTC", route="diagnostic"),
        _candidate("core:expired", "RISK", route="actionable_watch", expired=True),
    )
    return _snapshot(
        events=(window, unlock, inflation),
        candidates=candidates,
        calendar_snapshot={
            "status": "healthy_nonempty",
            "configured": True,
            "retained_row_count": 3,
            "normalization_rejected_count": 0,
        },
    )


def test_calendar_groups_chronologically_and_renders_human_times_and_release_context():
    page = render_calendar_page(_rich_snapshot(), {})

    assert page.index("Active now") < page.index("Monday, July 20")
    assert page.count('class="calendar-day"') == 2
    active_group = page.split("Active now", 1)[1].split("Monday, July 20", 1)[0]
    assert "United States inflation release" in active_group
    assert "TEST scheduled token unlock" in active_group
    assert "in 1 hr" in page
    assert "Local operator time" in page
    assert "Previous" in page and "2.8" in page
    assert "Forecast" in page and "2.7" in page
    assert "Awaiting release" in page
    assert "From 1 day before through 4 hr after" in page
    assert "1 day before" in page and "1 hr before" in page
    assert "Critical impact" in page
    assert "Urgent" not in page


def test_calendar_default_view_derives_active_upcoming_and_past_without_mutating_rows():
    past = _event(
        "cal-past",
        "Past inflation release",
        "2026-07-13T08:00:00+00:00",
        event_kind="inflation",
        importance="high",
        assets=["BTC"],
    )
    active = _event(
        "cal-active",
        "Active inflation risk window",
        "2026-07-14T10:00:00+00:00",
        event_kind="inflation",
        importance="critical",
        assets=["BTC", "ETH"],
    )
    upcoming = _event(
        "cal-upcoming",
        "Upcoming protocol upgrade",
        "2026-07-16T12:00:00+00:00",
        event_kind="protocol",
        importance="medium",
        assets=["TEST"],
    )
    snapshot = _snapshot(
        events=(past, upcoming, active),
        calendar_snapshot={
            "status": "healthy_nonempty",
            "configured": True,
            "retained_row_count": 3,
            "normalization_rejected_count": 0,
        },
    )
    before = copy.deepcopy(snapshot.current_calendar_events)

    page = render_calendar_page(snapshot, {})

    assert "Calendar snapshot verified" in page
    assert "Verified snapshot" in page
    assert 'class="panel calendar-coverage calendar-coverage--verified"' in page
    assert "3 exact-generation events" in page
    assert "fingerprint-bound to this operator generation" in page
    assert "Calendar coverage is current" not in page
    assert "Active inflation risk window" in page
    assert "Upcoming protocol upgrade" in page
    assert "Past inflation release" not in page
    assert "Active risk window" in page
    assert "Upcoming" in page
    assert "Showing <strong>2</strong> of <strong>3</strong>" in page
    assert "Past events" in page
    assert "Review 1 past event" in page
    assert 'href="/calendar?time=past"' in page
    assert snapshot.current_calendar_events == before
    assert all(
        "_dashboard_calendar_temporal_state" not in row
        for row in snapshot.current_calendar_events
    )


@pytest.mark.parametrize("time_certainty", ("date_only", "day_only", "date_known"))
def test_date_only_calendar_event_remains_current_through_its_known_day(
    time_certainty: str,
):
    event = _event(
        f"cal-{time_certainty}",
        "Known-day protocol event",
        "2026-07-14",
        event_kind="protocol",
        importance="high",
        assets=["TEST"],
        time_certainty=time_certainty,
    )
    event["impact_window_before"] = None
    event["impact_window_after"] = None
    snapshot = _snapshot(events=(event,))
    noon_snapshot = replace(
        snapshot,
        generation_authority_checked_at="2026-07-14T12:00:00+00:00",
    )
    next_day_snapshot = replace(
        snapshot,
        generation_authority_checked_at="2026-07-15T12:00:00+00:00",
    )

    assert calendar_temporal_state(
        event,
        clock=noon_snapshot.generation_authority_checked_at,
    ) == "active"
    assert calendar_temporal_state(
        event,
        clock=next_day_snapshot.generation_authority_checked_at,
    ) == "past"
    assert "Known-day protocol event" in render_calendar_page(noon_snapshot, {})
    assert "Known-day protocol event" not in render_calendar_page(next_day_snapshot, {})
    assert "Known-day protocol event" in render_calendar_page(
        next_day_snapshot,
        {"time": "past"},
    )


def test_exact_time_calendar_event_keeps_point_in_time_semantics():
    event = _event(
        "cal-exact",
        "Exact protocol event",
        "2026-07-14T10:00:00+00:00",
        event_kind="protocol",
        importance="high",
        assets=["TEST"],
        time_certainty="exact",
    )
    event["impact_window_before"] = None
    event["impact_window_after"] = None

    assert calendar_temporal_state(event, clock="2026-07-14T09:59:59+00:00") == "upcoming"
    assert calendar_temporal_state(event, clock="2026-07-14T10:00:00+00:00") == "active"
    assert calendar_temporal_state(event, clock="2026-07-14T10:00:01+00:00") == "past"


def test_calendar_past_view_is_explicit_and_does_not_mix_current_risk():
    events = (
        _event(
            "cal-past",
            "Past employment release",
            "2026-07-13T08:00:00+00:00",
            event_kind="employment",
            importance="high",
            assets=["BTC"],
        ),
        _event(
            "cal-active",
            "Current inflation risk window",
            "2026-07-14T10:00:00+00:00",
            event_kind="inflation",
            importance="critical",
            assets=["BTC"],
        ),
        _event(
            "cal-future",
            "Future protocol upgrade",
            "2026-07-16T12:00:00+00:00",
            event_kind="protocol",
            importance="medium",
            assets=["TEST"],
        ),
    )
    snapshot = _snapshot(events=events)

    page = render_calendar_page(snapshot, {"time": "past"})

    assert "Past employment release" in page
    assert "Current inflation risk window" not in page
    assert "Future protocol upgrade" not in page
    assert '<option value="past" selected>Past</option>' in page
    assert "Passed" in page
    assert "Showing <strong>1</strong> of <strong>3</strong>" in page


def test_uncertain_window_never_uses_decoy_exact_time_and_raw_codes_are_not_primary_labels():
    page = render_calendar_page(_rich_snapshot(), {})
    card = page.split("Expected regulatory decision window", 1)[1].split("</article>", 1)[0]
    primary = re.sub(r"<details\b.*?</details>", "", page, flags=re.DOTALL)

    assert "Window:" in card
    assert "Timing is not an exact appointment" in card
    assert "Scheduled window" in page
    assert "<time " not in card
    assert "2026-07-16T12:00:00+00:00" not in primary
    assert "2026-07-20T00:00:00+00:00" in page
    assert "2026-07-21T23:59:59+00:00" in page
    assert ">crypto_unlock<" not in primary
    assert ">regulatory_decision<" not in primary
    assert "Crypto unlock" in page
    assert "Regulatory decision" in page


def test_calendar_filters_importance_category_scope_and_search_without_mutating_source_rows():
    snapshot = _rich_snapshot()
    original_titles = tuple(row["title"] for row in snapshot.current_calendar_events)
    page = render_calendar_page(
        snapshot,
        {
            "importance": "high",
            "category": "crypto_unlock",
            "scope": "asset_specific",
            "search": "token unlock",
        },
    )

    assert "Showing <strong>1</strong> of <strong>3</strong>" in page
    assert "TEST scheduled token unlock" in page
    assert "United States inflation release" not in page
    assert "Expected regulatory decision window" not in page
    assert 'value="high" selected' in page
    assert 'value="crypto_unlock" selected' in page
    assert 'value="asset_specific" selected' in page
    assert tuple(row["title"] for row in snapshot.current_calendar_events) == original_titles


def test_calendar_joins_only_active_exact_generation_ideas_by_evidence_or_asset():
    page = render_calendar_page(_rich_snapshot(), {})

    assert "/ideas/core%3Ainflation" in page
    assert "Calendar evidence" in page
    assert "/ideas/core%3Aunlock" in page
    assert "Affected asset" in page
    assert "/ideas/core%3Adiagnostic" not in page
    assert "/ideas/core%3Aexpired" not in page


def test_calendar_allows_only_http_source_links():
    page = render_calendar_page(_rich_snapshot(), {})

    assert 'href="https://calendar.example/events/current"' in page
    assert "javascript:" not in page
    unlock_card = page.split("TEST scheduled token unlock", 1)[1].split("</article>", 1)[0]
    assert "source link unavailable" in unlock_card


@pytest.mark.parametrize(
    ("metadata", "expected_title", "expected_label"),
    (
        (
            {"status": "not_configured", "configured": False},
            "No calendar snapshot was configured",
            "Not configured",
        ),
        (
            {"status": "stale", "configured": True, "error_class": "snapshot_too_old"},
            "Calendar input is out of date",
            "Snapshot stale",
        ),
        (
            {
                "status": "healthy_nonempty",
                "configured": True,
                "normalization_rejected_count": 2,
            },
            "Calendar input did not pass admission",
            "Snapshot rejected",
        ),
        (
            {
                "status": "healthy_empty",
                "configured": True,
                "retained_row_count": 0,
                "normalization_rejected_count": 0,
            },
            "The observed calendar is empty",
            "Observed · no scheduled events",
        ),
    ),
)
def test_calendar_empty_states_are_honest_and_offer_the_exact_safe_local_action(
    metadata,
    expected_title,
    expected_label,
):
    page = render_calendar_page(_snapshot(calendar_snapshot=metadata), {})

    assert expected_title in page
    assert expected_label in page
    assert _NEXT_SAFE_ACTION in page
    assert "No exact-generation events" in page
    assert "provider call" not in page.casefold()
    compatibility_phrase = {
        "Not configured": "Calendar acquisition was not configured",
        "Snapshot stale": "calendar snapshot was stale",
        "Snapshot rejected": "failed unified-calendar normalization",
        "Observed · no scheduled events": "calendar snapshot was observed",
    }[expected_label]
    assert compatibility_phrase in page


def test_calendar_preserves_exact_receipt_and_release_values_inside_polished_surface():
    event = dict(_rich_snapshot().current_calendar_events[0])
    event.update(
        {
            "previous_value": 3.1,
            "forecast_value": 3.0,
            "actual_value": 2.8,
            "surprise_value": -0.2,
            "impact_window_before": "24h",
            "impact_window_after": "4h",
        }
    )
    snapshot = _snapshot(
        events=(event,),
        calendar_snapshot={
            "status": "healthy_nonempty",
            "configured": True,
            "counts": {"scheduled": 1, "unlocks": 0},
            "normalization_rejected_count": 0,
        },
    )

    page = render_calendar_page(snapshot, {})

    assert "3.1 / 3 / 2.8 / -0.2" in page
    assert "-24h / +4h" in page
    assert "status=healthy_nonempty" in page
    assert "scheduled=1" in page
    assert "Current generation:" in page


def test_calendar_receipt_shows_official_pack_source_freshness_and_fingerprint():
    event = dict(_rich_snapshot().current_calendar_events[0])
    page = render_calendar_page(
        _snapshot(
            events=(event,),
            calendar_snapshot={
                "status": "healthy_nonempty",
                "configured": True,
                "source_provider": "official_us_macro",
                "upstream_source_mode": "operator_verified_calendar_snapshot",
                "upstream_acquisition_mode": "operator_verified_export",
                "snapshot_observed_at": "2026-07-14T15:00:00+00:00",
                "freshness_basis": "snapshot_observed_at",
                "source_sha256": "a" * 64,
                "retained_row_count": 1,
            },
        ),
        {},
    )

    assert "Official us macro" in page or "official_us_macro" in page
    assert "operator_verified_calendar_snapshot / operator_verified_export" in page
    assert "Snapshot observed" in page
    assert "Freshness basis" in page
    assert "a" * 64 in page


def test_verified_calendar_leads_with_canonical_authority_when_producer_receipt_is_absent():
    event = dict(_rich_snapshot().current_calendar_events[0])
    page = render_calendar_page(_snapshot(events=(event,)), {})

    disclosure = page.split("Producer receipt metadata", 1)[1]
    assert "Canonical coverage:</strong> Complete" in disclosure
    assert disclosure.index("Canonical coverage:") < disclosure.index("Recorded status")
    assert "<dt>Recorded status</dt><dd>Not recorded</dd>" in disclosure
    assert "<dt>Coverage receipt</dt><dd>Not recorded</dd>" in disclosure
    assert "<dt>Configured</dt><dd>Not recorded</dd>" in disclosure
    assert "<dt>Read error class</dt><dd>Not recorded</dd>" in disclosure
    assert "status=unknown" not in disclosure
    assert "<dd>Unavailable</dd>" not in disclosure


def test_calendar_distinguishes_unavailable_and_legacy_not_configured_coverage():
    unavailable = _snapshot(
        calendar_snapshot={
            "status": "unavailable",
            "configured": True,
            "error_class": "snapshot_unreadable",
        }
    )
    legacy = replace(
        _snapshot(),
        source_coverage={
            "packs": [
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "not_configured",
                }
            ]
        },
    )

    unavailable_page = render_calendar_page(unavailable, {})
    legacy_page = render_calendar_page(legacy, {})

    assert "failed or was unavailable" in unavailable_page
    assert "snapshot_unreadable" in unavailable_page
    assert "Relevant source packs were not configured" in legacy_page
    assert "not evidence that no relevant events exist" in legacy_page


def test_untrusted_generation_suppresses_calendar_rows_even_if_the_snapshot_object_contains_them():
    trusted = _rich_snapshot()
    snapshot = replace(
        trusted,
        generation_authority_status="untrusted",
        generation_authority_reasons=("doctor:stale",),
    )

    page = render_calendar_page(snapshot, {})

    assert "This generation is not trusted" in page
    assert "United States inflation release" not in page
    assert "TEST scheduled token unlock" not in page
    assert 'class="calendar-day"' not in page


def test_calendar_cards_are_semantic_responsive_surfaces_with_accessible_controls():
    page = render_calendar_page(_rich_snapshot(), {"search": '<script>alert("x")</script>'})

    assert '<form class="filter-panel embedded-filter-panel calendar-filters"' in page
    assert 'aria-label="Filter calendar events"' in page
    assert '<details class="disclosure filter-disclosure calendar-filter-disclosure" open>' in page
    assert '<summary><span>Filter calendar events</span>' in page
    assert '<label class="filter-search" for="calendar-search"><span>Search</span>' in page
    assert '<label for="calendar-importance"><span>Importance</span>' in page
    assert '<label for="calendar-time"><span>Time</span>' in page
    assert '<label for="calendar-category"><span>Category</span>' in page
    assert '<label for="calendar-scope"><span>Scope</span>' in page
    assert 'class="calendar-grid"' in page or "No calendar events match this view" in page
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_calendar_filters_are_collapsed_by_default_and_open_for_active_queries():
    default_page = render_calendar_page(_rich_snapshot(), {})
    past_page = render_calendar_page(_rich_snapshot(), {"time": "past"})

    closed = '<details class="disclosure filter-disclosure calendar-filter-disclosure">'
    opened = '<details class="disclosure filter-disclosure calendar-filter-disclosure" open>'
    assert closed in default_page
    assert opened not in default_page
    assert '<span class="disclosure__summary">3 current</span>' in default_page
    assert opened in past_page
    assert '<span class="disclosure__summary">1 active · 0 shown</span>' in past_page


def test_calendar_cards_keep_decision_context_visible_and_collapse_supporting_detail():
    page = render_calendar_page(_rich_snapshot(), {})
    card = page.split('<article class="calendar-event-card card calendar-event-card--high-impact"', 1)[1].split("</article>", 1)[0]
    primary = re.sub(r"<details\b.*?</details>", "", card, flags=re.DOTALL)

    assert "United States inflation release" in primary
    assert "in 1 hr" in primary
    assert "Critical impact" in primary
    assert "Market-wide" in primary
    assert "Affected assets" in primary
    assert "BTC" in primary and "ETH" in primary
    assert "Impact window" in primary
    assert "From 1 day before through 4 hr after" in primary
    assert "Previous" not in primary
    assert "1 hr before" not in primary
    assert "/ideas/core%3Ainflation" not in primary
    assert "https://calendar.example/events/current" not in primary
    assert '<summary><span>Event details</span>' in card
    assert "<h4>Release data</h4>" in card
    assert "<h4>Display reminders</h4>" in card
    assert "<h4>Related ideas</h4>" in card
    assert "<h4>Source and provenance</h4>" in card
    assert card.count("<details") == 1
    assert "<details" in card and "<details class=\"disclosure\" open>" not in card


def test_calendar_missing_setup_leads_with_health_action_and_hides_commands_in_disclosure():
    page = render_calendar_page(
        _snapshot(calendar_snapshot={"status": "not_configured", "configured": False}),
        {},
    )
    primary = re.sub(r"<details\b.*?</details>", "", page, flags=re.DOTALL)

    assert "Calendar coverage is not available for this generation" in primary
    assert 'href="/health"' in primary
    assert "Review System Health" in primary
    assert "RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH" not in primary
    assert "make radar-market-no-send-readiness" not in primary
    assert '<summary><span>Calendar readiness and setup instructions</span>' in page
    assert _NEXT_SAFE_ACTION in page
