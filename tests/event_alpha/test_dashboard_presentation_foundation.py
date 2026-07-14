from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.components import (
    HtmlFragment,
    badge,
    chips,
    data_table,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
    link,
    score,
    section,
    time_element,
)
from crypto_rsi_scanner.event_alpha.dashboard.presentation import (
    UNAVAILABLE,
    format_calendar_window,
    format_compact_number,
    format_currency,
    format_duration,
    format_exact_utc,
    format_local_time,
    format_number,
    format_percent,
    format_relative_time,
    format_score,
    humanize_enum,
    humanize_identifier,
    humanize_reason,
    humanize_reasons,
    present_calendar_window,
    present_time,
    score_band,
    semantic_status,
    status_tone,
)
from crypto_rsi_scanner.event_alpha.dashboard.styles import (
    DASHBOARD_CSS,
    dashboard_css,
)


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def test_time_presentation_keeps_local_relative_and_exact_utc_views() -> None:
    value = present_time(
        "2026-07-14T11:55:00Z",
        now=NOW,
        tz="Europe/Moscow",
    )

    assert value.available is True
    assert value.local_label == "Today, 14:55 MSK"
    assert value.relative_label == "5 min ago"
    assert value.utc_label == "2026-07-14 11:55:00 UTC"
    assert value.iso_utc == "2026-07-14T11:55:00Z"
    assert value.timezone_label == "MSK"
    assert value.primary_label == "5 min ago · Today, 14:55 MSK"
    assert format_local_time(
        "2026-07-14T11:55:00Z", now=NOW, tz="Europe/Moscow"
    ) == value.local_label
    assert format_relative_time("2026-07-14T14:00:00Z", now=NOW) == "in 2 hr"
    assert format_exact_utc("2026-07-14T14:00:00+02:00") == "2026-07-14 12:00:00 UTC"


def test_time_presentation_uses_one_unavailable_contract() -> None:
    value = present_time("not-a-time", now=NOW, tz="UTC")

    assert value.available is False
    assert value.local_label == UNAVAILABLE
    assert value.relative_label == UNAVAILABLE
    assert value.utc_label == UNAVAILABLE
    assert value.iso_utc == ""
    assert format_local_time(None, now=NOW, tz="UTC") == UNAVAILABLE
    assert format_relative_time(float("nan"), now=NOW) == UNAVAILABLE
    assert format_exact_utc("") == UNAVAILABLE


def test_time_presentation_handles_day_boundaries_in_operator_timezone() -> None:
    assert (
        present_time(
            "2026-07-14T22:00:00Z",
            now=NOW,
            tz="Europe/Moscow",
        ).local_label
        == "Tomorrow, 01:00 MSK"
    )
    assert (
        present_time(
            "2025-07-14T12:00:00Z",
            now=NOW,
            tz="Europe/Moscow",
        ).local_label
        == "Jul 14, 2025, 15:00 MSK"
    )


def test_calendar_window_presentation_preserves_range_and_certainty() -> None:
    value = present_calendar_window(
        window_start="2026-07-14T15:00:00Z",
        window_end="2026-07-14T17:00:00Z",
        time_certainty="window",
        now=NOW,
        tz="Europe/Moscow",
    )

    assert value.available is True
    assert value.label == "Window: Jul 14, 18:00–20:00 MSK"
    assert value.certainty_label == "Scheduled window"
    assert value.relative_label == "in 3 hr"
    assert value.utc_label == (
        "2026-07-14 15:00:00 UTC – 2026-07-14 17:00:00 UTC"
    )
    assert (
        format_calendar_window(
            window_start="2026-07-14T15:00:00Z",
            window_end="2026-07-14T17:00:00Z",
            time_certainty="window",
            now=NOW,
            tz="Europe/Moscow",
        )
        == value.label
    )


def test_calendar_window_does_not_invent_date_only_or_approximate_precision() -> None:
    date_only = present_calendar_window(
        scheduled_at="2026-07-15",
        time_certainty="date_only",
        now=NOW,
        tz="Europe/Moscow",
    )
    approximate = present_calendar_window(
        scheduled_at="2026-07-14T15:00:00Z",
        time_certainty="estimated",
        now=NOW,
        tz="Europe/Moscow",
    )
    unconfirmed = present_calendar_window(
        scheduled_at="2026-07-14T15:00:00Z",
        time_certainty="unknown",
        now=NOW,
        tz="Europe/Moscow",
    )

    assert date_only.label == "Jul 15 · time unconfirmed"
    assert date_only.relative_label == UNAVAILABLE
    assert date_only.utc_label == UNAVAILABLE
    assert approximate.label == "Around Today, 18:00 MSK · approximate"
    assert approximate.certainty_label == "Approximate time"
    assert unconfirmed.label == "Today, 18:00 MSK · time unconfirmed"
    assert unconfirmed.certainty_label == "Timing unconfirmed"


def test_calendar_window_reports_missing_and_unrecorded_certainty_honestly() -> None:
    missing = present_calendar_window(now=NOW, tz="UTC")
    unrecorded = present_calendar_window(
        scheduled_at="2026-07-14T15:00:00Z",
        now=NOW,
        tz="Europe/Moscow",
    )

    assert missing.available is False
    assert missing.label == UNAVAILABLE
    assert missing.certainty_label == "Timing certainty not recorded"
    assert unrecorded.label.endswith("· certainty not recorded")


def test_identifier_and_reason_humanization_is_operator_facing() -> None:
    assert humanize_enum("rapid_market_anomaly") == "Rapid market anomaly"
    assert humanize_identifier("api_http_status") == "API HTTP status"
    assert humanize_identifier("onchain_led") == "On-chain-led"
    assert humanize_identifier(None) == UNAVAILABLE
    assert humanize_reason("needs_market_confirmation") == (
        "Needs clearer price and volume confirmation."
    )
    assert humanize_reason("custom_reason_code") == "Custom reason code."
    assert humanize_reasons(
        ["market_context_missing", "market_context_missing", "source_noise"],
        limit=1,
    ) == "Market context is missing. +1 more"
    assert humanize_reasons([]) == UNAVAILABLE


def test_numeric_formatters_are_compact_and_unit_explicit() -> None:
    assert format_number(12345.67, decimals=1) == "12,345.7"
    assert format_number(4.2, decimals=1, signed=True) == "+4.2"
    assert format_compact_number(1_260_000) == "1.3M"
    assert format_compact_number(-12_500) == "-12.5K"
    assert format_currency(1_260_000) == "$1.3M"
    assert format_currency(-12_500, currency="USD") == "-USD 12.5K"
    assert format_percent(0.10, unit="fraction") == "10%"
    assert format_percent(10.0, unit="percent_points") == "10%"
    assert format_percent(2.5, signed=True) == "+2.5%"
    assert format_number(float("inf")) == UNAVAILABLE
    assert format_currency(True) == UNAVAILABLE
    with pytest.raises(ValueError, match="unsupported percent unit"):
        format_percent(10, unit="ambiguous")


def test_duration_and_score_helpers_reject_unknown_or_implausible_values() -> None:
    assert format_duration(42) == "42 sec"
    assert format_duration(90) == "1 min"
    assert format_duration(90061) == "1 day 1 hr"
    assert format_duration(-1) == UNAVAILABLE
    assert format_score(72.25) == "72.2"
    assert format_score(101) == UNAVAILABLE
    assert score_band(72).label == "High"
    assert score_band(72).tone == "positive"
    assert score_band(72, dimension="risk").tone == "danger"
    assert score_band(50, dimension="urgency").tone == "info"
    assert score_band(None).label == UNAVAILABLE


@pytest.mark.parametrize(
    ("value", "label", "tone"),
    (
        ("healthy_empty", "Healthy · no matching rows", "positive"),
        ("not_configured", "Not configured", "muted"),
        ("provider_degraded", "Provider degraded", "warning"),
        ("stale", "Stale", "danger"),
        ("live_no_send", "Live / real data · no-send", "info"),
        ("bespoke_state", "Bespoke state", "neutral"),
    ),
)
def test_semantic_status_has_closed_tones(
    value: str,
    label: str,
    tone: str,
) -> None:
    status = semantic_status(value)
    assert status.label == label
    assert status.tone == tone
    assert status_tone(value) == tone


def test_html_primitives_escape_raw_values_and_unsafe_links() -> None:
    assert escape_html('<script x="1">') == "&lt;script x=&quot;1&quot;&gt;"
    assert "<script" not in badge("<script>").casefold()
    assert "&lt;script&gt;" in badge("<script>")
    unsafe_link = link("<Open>", 'javascript:alert("x")')
    assert unsafe_link == '<a href="#">&lt;Open&gt;</a>'
    safe_link = link("Open", "/candidate/a?x=1&y=2", aria_label='Open "A"')
    assert 'href="/candidate/a?x=1&amp;y=2"' in safe_link
    assert 'aria-label="Open &quot;A&quot;"' in safe_link


def test_badges_chips_scores_and_times_have_accessible_semantics() -> None:
    rendered_badge = badge("fresh", title='Observed "now"')
    rendered_chips = chips(["market_led", "<unsafe>"], aria_label="Origins")
    rendered_score = score(82, label="Actionability")
    rendered_time = time_element(
        present_time(
            "2026-07-14T11:55:00Z",
            now=NOW,
            tz="Europe/Moscow",
        )
    )

    assert 'status-badge--positive' in rendered_badge
    assert 'title="Observed &quot;now&quot;"' in rendered_badge
    assert '<ul class="chip-list" aria-label="Origins">' in rendered_chips
    assert "Market-led" in rendered_chips
    assert "&lt;unsafe&gt;" in rendered_chips
    assert 'role="img"' in rendered_score
    assert 'aria-label="Actionability: 82 out of 100, High"' in rendered_score
    assert 'datetime="2026-07-14T11:55:00Z"' in rendered_time
    assert 'title="2026-07-14 11:55:00 UTC"' in rendered_time


def test_data_table_is_contained_mobile_ready_and_escapes_cells() -> None:
    rendered = data_table(
        ("Asset", "Status"),
        [
            ("<BTC>", badge("fresh")),
            ("ETH", "<b>unsafe</b>"),
        ],
        caption='Ideas "now"',
    )

    assert isinstance(rendered, HtmlFragment)
    assert 'class="table-scroll"' in rendered
    assert 'role="region"' in rendered
    assert 'tabindex="0"' in rendered
    assert '<table class="data-table mobile-cards">' in rendered
    assert '<caption>Ideas &quot;now&quot;</caption>' in rendered
    assert '<th scope="col">Asset</th>' in rendered
    assert '<th scope="row" data-label="Asset">&lt;BTC&gt;</th>' in rendered
    assert '<td data-label="Status"><span class="status-badge' in rendered
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in rendered
    assert "<b>unsafe</b>" not in rendered


def test_data_table_empty_state_and_width_mismatch_are_explicit() -> None:
    rendered = data_table(("Asset",), [], empty="<none>")

    assert 'class="empty-state"' in rendered
    assert "&lt;none&gt;" in rendered
    assert "<none>" not in rendered
    with pytest.raises(ValueError, match="row width"):
        data_table(("A", "B"), [("only one",)])


def test_empty_disclosure_definition_and_section_components_escape_by_default() -> None:
    empty = empty_state("<Empty>", "<No rows>", action_label="<Try>", action_href="/")
    closed = disclosure("<Details>", "<raw>")
    composed = disclosure("Safe component", badge("fresh"), open=True)
    definitions = definition_list([("<Key>", "<Value>"), ("Status", badge("fresh"))])
    panel = section("<Title>", "<Body>", eyebrow="<Eyebrow>")

    assert "&lt;Empty&gt;" in empty and "&lt;No rows&gt;" in empty
    assert "&lt;Try&gt;" in empty
    assert "<summary><span>&lt;Details&gt;</span></summary>" in closed
    assert "&lt;raw&gt;" in closed and "<raw>" not in closed
    assert "<details class=\"disclosure\" open>" in composed
    assert '<span class="status-badge' in composed
    assert "<dt>&lt;Key&gt;</dt><dd>&lt;Value&gt;</dd>" in definitions
    assert "<h2>&lt;Title&gt;</h2>&lt;Body&gt;" in panel
    assert '<p class="eyebrow">&lt;Eyebrow&gt;</p>' in panel


def test_css_contains_accessibility_responsiveness_and_overflow_contracts() -> None:
    assert dashboard_css() == DASHBOARD_CSS
    assert "--color-canvas:" in DASHBOARD_CSS
    assert "--touch-target: 2.75rem" in DASHBOARD_CSS
    assert ".skip-link" in DASHBOARD_CSS
    assert ":focus-visible" in DASHBOARD_CSS
    assert "@media (prefers-reduced-motion: reduce)" in DASHBOARD_CSS
    assert ".table-scroll" in DASHBOARD_CSS
    assert "overflow-x: auto" in DASHBOARD_CSS
    assert ".mobile-cards td::before" in DASHBOARD_CSS
    assert "content: attr(data-label)" in DASHBOARD_CSS
    assert "grid-template-columns: minmax(6.5rem, 38%) minmax(0, 1fr)" in DASHBOARD_CSS
    assert "overflow-wrap: anywhere" in DASHBOARD_CSS
    assert "@media (pointer: coarse)" in DASHBOARD_CSS
