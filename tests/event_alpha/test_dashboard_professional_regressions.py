from __future__ import annotations

import re
from dataclasses import replace

from crypto_rsi_scanner.event_alpha.dashboard.campaign_page import (
    render_campaign_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.health_render import render_health
from crypto_rsi_scanner.event_alpha.dashboard.ideas_page import (
    render_idea_detail,
    render_ideas_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.market_page import render_market_page
from crypto_rsi_scanner.event_alpha.dashboard.shell import render_shell
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import (
    render_health_page,
    render_outcomes_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot


def test_fixture_campaign_metrics_fail_closed_when_generation_is_untrusted() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        generation_authority_status="failed",
        generation_authority_reasons=("operator_state_sha256_mismatch",),
        operator_state={**source.operator_state, "run_mode": "fixture"},
    )

    page = render_campaign_page(snapshot, {})
    metrics = page.split('<div class="metric-grid">', 1)[1].split("</div>", 1)[0]

    assert "Current campaign authority suppressed" in page
    assert '<span>Fixture observations</span><strong>Suppressed</strong>' in metrics
    assert '<span>Fixture ideas</span><strong>Suppressed</strong>' in metrics
    assert '<span>Fixture observations</span><strong>2</strong>' not in metrics
    assert '<span>Fixture ideas</span><strong>1</strong>' not in metrics


def test_default_market_outcome_and_run_filters_open_only_when_active() -> None:
    snapshot = _snapshot()
    surfaces = (
        (
            render_market_page(snapshot, {}),
            render_market_page(snapshot, {"search": "btc"}),
            "market-filter-disclosure",
        ),
        (
            render_outcomes_page(snapshot, {}),
            render_outcomes_page(snapshot, {"scope": "current"}),
            "outcome-filter-disclosure",
        ),
        (
            render_campaign_page(snapshot, {}),
            render_campaign_page(snapshot, {"status": "failed"}),
            "campaign-filter-disclosure",
        ),
    )

    for default_page, active_page, css_class in surfaces:
        closed = f'<details class="disclosure filter-disclosure {css_class}">'
        opened = f'<details class="disclosure filter-disclosure {css_class}" open>'
        assert closed in default_page
        assert opened not in default_page
        assert opened in active_page


def test_today_keeps_expired_ideas_in_a_closed_disclosure() -> None:
    source = _snapshot()
    expired = {
        **source.current_candidates[0],
        "radar_route": "dashboard_watch",
        "_dashboard_route": "diagnostic",
        "_decision_expired_at_read_time": True,
        "_decision_read_time_reason": "canonical_expiry_at_or_before_dashboard_read_time",
    }

    page = render_today_page(replace(source, current_candidates=(expired,)))

    opening = '<details class="disclosure panel expired-ideas">'
    assert opening in page
    assert '<details class="disclosure panel expired-ideas" open>' not in page
    assert "Expired ideas (not currently actionable)" in page
    assert "Expired; current actionability suppressed." in page


def test_outcome_learning_sections_are_collapsed_by_default() -> None:
    page = render_outcomes_page(_snapshot(), {})

    assert '<details class="disclosure panel outcome-history-disclosure">' in page
    assert '<details class="disclosure panel outcome-history-disclosure" open>' not in page
    assert page.count(
        '<details class="disclosure panel outcome-secondary-disclosure">'
    ) == 2
    assert (
        '<details class="disclosure panel outcome-secondary-disclosure" open>'
        not in page
    )
    assert "Historical campaign outcomes" in page
    assert "Matured route cohorts" in page
    assert "Optional human feedback" in page


def test_health_compatibility_tables_expose_accessible_scroll_regions() -> None:
    page = render_health(_snapshot())
    captions = (
        "Artifact manifest compatibility diagnostics",
        "Exact-generation source-pack compatibility diagnostics",
        "Exact-generation provider readiness compatibility diagnostics",
        "Cumulative provider health compatibility diagnostics",
    )

    tables = re.findall(
        r'<table class="responsive-table compact-table">.*?</table>',
        page,
    )
    assert len(tables) == len(captions)
    for caption, table in zip(captions, tables, strict=True):
        assert (
            '<div class="table-scroll" role="region" tabindex="0" '
            f'aria-label="{caption}">'
        ) in page
        assert f'<caption class="sr-only">{caption}</caption>' in table
        assert '<th scope="col">' in table
        body = table.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = re.findall(r"<tr>(.*?)</tr>", body)
        assert rows
        assert all(row.startswith('<th scope="row">') for row in rows)


def test_unavailable_current_outcome_layer_is_not_described_as_a_zero_row_sample() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        current_outcomes=(),
        current_outcomes_metadata={},
    )

    page = render_outcomes_page(snapshot, {})

    assert "No fingerprint-verified exact outcome artifact is available" in page
    assert "Only 0 matured rows in the exact current generation" not in page
    assert '<span>Current outcome coverage</span><strong>Unavailable</strong>' in page
    assert "Current outcome rows</span>" not in page
    assert "Current pending</span>" not in page


def test_empty_market_anomaly_section_does_not_claim_missing_observations_are_visible() -> None:
    source = _snapshot()
    page = render_market_page(
        replace(
            source,
            current_market_observations=(),
            current_market_anomalies=(),
        ),
        {},
    )

    assert "No exact market observations were admitted for this generation" in page
    assert "Evaluated market observations remain visible above" not in page


def test_market_anomaly_labels_missing_strength_and_links_its_canonical_decision() -> None:
    source = _snapshot()
    observations = (
        dict(
            source.current_market_observations[0],
            return_24h=-14.22,
            return_unit="percent_points",
        ),
        *source.current_market_observations[1:],
    )
    page = render_market_page(
        replace(source, current_market_observations=observations),
        {},
    )

    assert "24h move" in page
    assert "-14.22%" in page
    assert "Scanner strength" in page
    assert "Canonical Decision" in page
    assert '<a href="/ideas/candidate%3Abtc">Dashboard watch</a>' in page
    assert "Actionability not recorded" in page
    assert "Unavailable actionability" not in page
    assert "Unavailable</strong>" in page


def test_market_anomaly_decision_uses_score_first_actionability_copy() -> None:
    source = _snapshot()
    candidate = {**source.current_candidates[0], "actionability_score": 35}
    page = render_market_page(replace(source, current_candidates=(candidate,)), {})

    assert "Actionability 35/100" in page
    assert "35 actionability" not in page


def test_desktop_market_comparison_keeps_coin_identity_inside_compact_context() -> None:
    source = _snapshot()
    observations = (
        dict(source.current_market_observations[0], coin_id="bitcoin"),
        *source.current_market_observations[1:],
    )
    page = render_market_page(
        replace(source, current_market_observations=observations),
        {},
    )
    desktop = page.split('<section class="panel market-desktop-table">', 1)[1].split(
        '<section class="panel market-mobile-list">', 1
    )[0]

    assert 'class="market-asset-heading"' in desktop
    assert '>Context</summary>' in desktop
    assert '<dt>Coin ID</dt><dd>bitcoin</dd>' in desktop
    assert 'class="market-asset-meta"' not in desktop


def test_mobile_market_card_keeps_provider_slug_in_secondary_evidence() -> None:
    source = _snapshot()
    observations = (
        dict(source.current_market_observations[0], coin_id="polygon-ecosystem-token"),
        *source.current_market_observations[1:],
    )
    page = render_market_page(
        replace(source, current_market_observations=observations),
        {},
    )
    mobile = page.split('<section class="panel market-mobile-list">', 1)[1]
    header = mobile.split('</header>', 1)[0]

    assert "Exact market observation" in header
    assert "polygon-ecosystem-token" not in header
    assert '<dt>Coin ID</dt><dd>polygon-ecosystem-token</dd>' in mobile


def test_today_labels_an_active_calendar_window_by_its_remaining_risk_window() -> None:
    source = _snapshot()
    event = {
        "event_id": "calendar:active",
        "title": "Active unlock window",
        "window_start": "2026-07-13T10:00:00+00:00",
        "window_end": "2026-07-20T10:00:00+00:00",
        "time_certainty": "window",
        "importance": "high",
    }

    page = render_today_page(
        replace(
            source,
            current_candidates=(),
            current_calendar_events=(event,),
        )
    )

    assert "Active · ends in" in page
    assert "Active unlock window" in page
    assert "Active scheduled risk" in page
    assert "Scheduled risk" in page
    assert "Active + upcoming exact rows" in page
    assert "No current idea needs review" not in page
    assert 'href="/calendar?time=active">Review 1 active event</a>' in page
    assert '<div class="hero-pulse"><span>1</span><small>active risk</small>' in page


def test_today_names_a_single_risk_watch_without_overstating_it_as_an_idea() -> None:
    source = _snapshot()
    risk_watch = {
        **source.current_candidates[0],
        "_dashboard_route": "risk_watch",
        "radar_route": "risk_watch",
    }

    page = render_today_page(replace(source, current_candidates=(risk_watch,)))

    assert '>Review 1 risk watch</a>' in page
    assert '<div class="hero-pulse"><span>1</span><small>risk watch</small>' in page
    assert ">Review 1 idea</a>" not in page


def test_relative_idea_and_calendar_times_use_the_exact_dashboard_read_clock() -> None:
    source = _snapshot()
    clock = "2031-05-10T12:00:00+00:00"
    candidate = {
        **source.current_candidates[0],
        "expires_at": "2031-05-11T12:00:00+00:00",
        "calendar_evidence_ids": ["calendar:future"],
    }
    event = {
        "calendar_event_id": "calendar:future",
        "title": "Exact-clock protocol review",
        "scheduled_at": "2031-05-11T12:00:00+00:00",
        "time_certainty": "exact",
        "importance": "high",
        "affected_assets": ["BTC"],
    }
    snapshot = replace(
        source,
        generation_authority_checked_at=clock,
        current_candidates=(candidate,),
        current_calendar_events=(event,),
    )

    ideas = render_ideas_page(snapshot, {})
    today = render_today_page(snapshot)
    status, _title, detail = render_idea_detail(snapshot, "candidate:btc")

    assert status == 200
    assert "in 1 day" in ideas
    assert "in 1 day" in today
    assert "in 1 day" in detail
    assert "in 4 years" not in ideas + today + detail
    decision_context = detail.split("<h2>How to read this idea</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert "<dt>Expires</dt>" in decision_context
    assert "in 1 day" in decision_context
    assert "Expires at" not in decision_context


def test_all_operator_relative_times_share_the_exact_dashboard_read_clock() -> None:
    source = _snapshot()
    clock = "2031-05-10T12:00:00+00:00"
    observation = {
        **source.current_market_observations[0],
        "observed_at": "2031-05-10T11:55:00+00:00",
    }
    latest = {
        **source.campaign_latest_attempt,
        "recorded_at": "2031-05-10T11:50:00+00:00",
        "observed_at": "2031-05-10T11:49:00+00:00",
    }
    snapshot = replace(
        source,
        generation_authority_checked_at=clock,
        operator_state={
            **source.operator_state,
            "generated_at": "2031-05-10T11:45:00+00:00",
        },
        current_market_observations=(observation,),
        current_outcomes=(
            {
                **source.current_outcomes[0],
                "observed_at": "2031-05-10T11:57:00+00:00",
            },
            {
                **source.current_outcomes[1],
                "outcome_evaluated_at": "2031-05-10T11:40:00+00:00",
            },
        ),
        current_request_ledger={
            **source.current_request_ledger,
            "observed_at": "2031-05-10T11:55:00+00:00",
            "request_started_at": "2031-05-10T11:58:00+00:00",
            "request_ended_at": "2031-05-10T11:59:00+00:00",
        },
        market_generation={
            **source.market_generation,
            "observed_at": "2031-05-10T11:55:00+00:00",
            "next_eligible_observation_at": "2031-05-10T13:00:00+00:00",
        },
        campaign_attempts=(latest,),
        campaign_latest_attempt=latest,
        campaign_reservation={
            **source.campaign_reservation,
            "acquired_at": "2031-05-10T11:58:00+00:00",
            "provider_call_reserved_at": "2031-05-10T11:58:00+00:00",
            "released_at": "2031-05-10T11:59:00+00:00",
            "expires_at": "2031-05-10T12:15:00+00:00",
            "next_provider_call_at": "2031-05-10T12:55:00+00:00",
        },
        provider_readiness={
            "providers": [
                {
                    "provider": "coingecko",
                    "status": "healthy",
                    "last_success_at": "2031-05-10T11:30:00+00:00",
                }
            ]
        },
        provider_health_read_at="2031-05-10T11:59:00+00:00",
    )

    market = render_market_page(snapshot, {})
    today = render_today_page(snapshot)
    campaign = render_campaign_page(snapshot, {})
    health = render_health_page(snapshot)
    outcomes = render_outcomes_page(snapshot, {"scope": "current"})
    shell = render_shell(snapshot, title="Today", path="/", body="")

    assert "5 min ago" in market
    assert "10 min ago" in today
    assert "10 min ago" in campaign
    assert "Next eligible in 55 min" in campaign
    assert "15 min ago" in health
    assert "30 min ago" in health
    assert "2 min ago" in health
    assert "in 1 hr" in health
    assert "3 min ago" in outcomes
    assert "20 min ago" in outcomes
    assert "just now" in shell
    assert "4 years" not in market + today + campaign + health + outcomes + shell


def test_diagnostic_opt_in_never_resurrects_expired_rows_as_current() -> None:
    source = _snapshot()
    expired = {
        **source.current_candidates[0],
        "candidate_id": "candidate:expired",
        "symbol": "EXPIRED",
        "_dashboard_route": "diagnostic",
        "radar_route": "dashboard_watch",
        "_decision_expired_at_read_time": True,
    }
    diagnostic = {
        **source.current_candidates[0],
        "candidate_id": "candidate:diagnostic",
        "symbol": "DIAGNOSTIC",
        "_dashboard_route": "diagnostic",
        "radar_route": "diagnostic",
        "_decision_expired_at_read_time": False,
    }
    snapshot = replace(source, current_candidates=(expired, diagnostic))

    ideas = render_ideas_page(snapshot, {}, include_diagnostics=True)
    today = render_today_page(snapshot, include_diagnostics=True)
    current_today, expired_today = today.split(
        '<details class="disclosure panel expired-ideas">',
        1,
    )

    assert "DIAGNOSTIC" in ideas
    assert "EXPIRED" not in ideas
    assert "DIAGNOSTIC" in current_today
    assert "EXPIRED" not in current_today
    assert "EXPIRED" in expired_today
    assert 'class="attention-card route-diagnostic"' not in current_today
    assert '<span>Decision ideas</span><strong>0</strong>' in current_today


def test_idea_detail_groups_repeated_risks_and_keeps_raw_reason_in_lineage() -> None:
    source = _snapshot()
    candidate = {
        **source.current_candidates[0],
        "main_risks": [
            "Catalyst unknown: evidence confidence is lower.",
            "Spread is unavailable; execution quality is not verified.",
            "The temporal market baseline is not warm.",
        ],
        "decision_warnings": [
            "Catalyst unknown soft penalty.",
            "Spread unavailable dashboard only.",
            "Temporal market baseline not warm.",
            "Market turnover weak.",
        ],
        "_decision_expired_at_read_time": True,
        "_decision_read_time_reason": (
            "canonical_expiry_at_or_before_dashboard_read_time"
        ),
    }

    status, _title, page = render_idea_detail(
        replace(source, current_candidates=(candidate,)),
        "candidate:btc",
    )

    assert status == 200
    main_risks = page.split("<h2>Main risks</h2>", 1)[1].split("</section>", 1)[0]
    assert main_risks.count("Catalyst unknown") == 1
    assert main_risks.count("Spread") == 1
    assert main_risks.count("baseline") == 1
    assert "Market turnover weak." in main_risks
    assert "Recorded risk detail" in page
    assert "How to record optional feedback" in page
    context = page.split("<h2>How to read this idea</h2>", 1)[1].split("</section>", 1)[0]
    assert "The recorded research window had expired by dashboard read time." in context
    assert "canonical_expiry_at_or_before_dashboard_read_time" not in context
    assert "Read-time safety reason code" in page
    assert "canonical_expiry_at_or_before_dashboard_read_time" in page


def test_health_gap_disclosure_and_run_summary_use_exact_scopes_and_grammar() -> None:
    health = render_health_page(_snapshot())
    history = render_campaign_page(_snapshot(), {})

    assert "Show all 5 product-layer gaps" in health
    assert "more coverage gaps" not in health
    assert "2 observations · 1 anomaly · 1 canonical candidate row · 1 current idea" in history


def test_health_action_summary_links_to_stable_evidence_sections() -> None:
    page = render_health_page(_snapshot())

    assert 'id="operator-action-summary"' in page
    assert 'id="exact-generation"' in page
    assert 'id="market-quality"' in page
    assert 'class="health-action" href="#provider-readiness"' in page
    assert 'class="health-action" href="#market-quality"' in page
    assert 'class="health-action" href="#product-layer-coverage"' in page
    assert "Provider failures" in page
    action_summary = page.split('id="operator-action-summary"', 1)[1].split(
        'id="exact-generation"', 1
    )[0]
    assert 'class="health-action__copy"' in action_summary
    assert 'class="status-badge' not in action_summary
