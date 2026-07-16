from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution
from crypto_rsi_scanner.event_alpha.radar import source_independence
from crypto_rsi_scanner.event_alpha.dashboard.ideas_page import (
    render_idea_comparison,
    render_idea_detail,
    render_idea_filters,
    render_ideas_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.market_page import render_market_page
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page


_NOW = datetime(2026, 7, 12, 7, 0, tzinfo=timezone.utc)


def _sparse_snapshot():
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    observations = (
        {
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "return_24h": 2.0,
            "return_unit": "percent_points",
            "spread_status": "unavailable",
            "freshness_status": "fresh",
            "market_data_quality": {"baseline_status": "warming"},
        },
        {
            "symbol": "ETH",
            "coin_id": "ethereum",
            "return_24h": -1.0,
            "return_unit": "percent_points",
            "spread_status": "unavailable",
            "freshness_status": "fresh",
            "market_data_quality": {"baseline_status": "warming"},
        },
    )
    return replace(
        snapshot,
        current_candidates=(),
        current_market_observations=observations,
        current_market_anomalies=(),
        current_calendar_events=(),
        current_outcomes=(),
        market_generation={
            "raw_market_row_count": 80,
            "selected_market_row_count": 2,
        },
        current_request_ledger={
            "raw_market_row_count": 80,
            "selected_market_row_count": 2,
        },
        source_coverage={
            "packs": [
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "not_configured",
                }
            ]
        },
    )


def test_today_distinguishes_zero_ideas_from_zero_market_data() -> None:
    page = render_dashboard_page(_sparse_snapshot(), "/")

    assert page.status_code == 200
    assert "No immediate Decision idea qualified" in page.body
    assert "The scan evaluated 2 assets" in page.body
    assert "does not mean the provider or dashboard failed" in page.body
    assert "Calendar acquisition not configured" in page.body
    assert "Execution spread unavailable" in page.body


def test_ideas_zero_state_distinguishes_valid_generation_from_filter_miss() -> None:
    snapshot = _sparse_snapshot()

    unfiltered = render_ideas_page(snapshot, None)
    filtered = render_ideas_page(snapshot, {"search": "does-not-exist"})

    assert "No current ideas qualified" in unfiltered
    assert "No ideas match this view" not in unfiltered
    assert "No ideas match this view" in filtered


def test_idea_cards_and_filters_use_canonical_operator_route_labels() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    page = render_ideas_page(snapshot, None)

    assert ">Actionable idea</p>" in page
    assert ">High-confidence idea</p>" in page
    assert '<option value="actionable_watch">Actionable idea</option>' in page
    assert (
        '<option value="high_confidence_watch">High-confidence idea</option>'
        in page
    )


def test_today_prioritizes_visible_ideas_and_uses_ideas_primary_action() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    body = render_today_page(snapshot)
    visible_count = len(snapshot.visible_current_candidates)

    assert visible_count > 0
    assert (
        f'<a class="button button-primary" href="/ideas">Review {visible_count} ideas</a>'
        in body
    )
    one_idea = render_today_page(
        replace(snapshot, current_candidates=(snapshot.visible_current_candidates[0],))
    )
    assert (
        '<a class="button button-primary" href="/ideas">Review 1 actionable idea</a>'
        in one_idea
    )
    attention_index = body.index('<section class="attention-lane"')
    assert attention_index < body.index('<section class="panel warning-stack"')
    assert attention_index < body.index('class="disclosure filter-disclosure"')


def test_today_never_infers_zero_change_from_attempts_without_candidate_counts() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    attempts = (
        {
            "artifact_namespace": "previous",
            "run_id": "previous-run",
            "status": "complete",
            "decision_radar_campaign_counted": True,
        },
        {
            "artifact_namespace": snapshot.artifact_namespace,
            "run_id": snapshot.run_id,
            "status": "complete",
            "decision_radar_campaign_counted": True,
        },
    )

    body = render_today_page(replace(snapshot, campaign_attempts=attempts))

    assert "Candidate count changed from 0 to 0" not in body
    assert "A trustworthy idea-level diff is not available yet" in body
    assert "no change is inferred" in body


def test_market_radar_accounts_for_every_layer_without_inventing_rows() -> None:
    page = render_dashboard_page(_sparse_snapshot(), "/market-radar")

    assert page.status_code == 200
    assert "Where the rows went" in page.body
    assert "Provider rows" in page.body
    assert "Selected universe" in page.body
    assert "Exact observations" in page.body
    assert "Anomaly evidence" in page.body
    assert "Integrated candidates" in page.body
    assert "Canonical candidates" in page.body
    assert "All 2 selected assets survive into the exact observation layer" in page.body
    assert "scanner qualification and canonical consolidation" in page.body
    assert "not a dashboard data-loss gap" in page.body


def test_market_radar_intro_describes_the_exact_available_layers() -> None:
    sparse = render_market_page(_sparse_snapshot(), {})

    assert "2 assets evaluated · no Decision idea qualified" in sparse
    assert "All 2 exact observations shown" in sparse
    assert "See what the radar evaluated—even when no idea qualified" not in sparse

    candidates_only = render_market_page(
        load_dashboard_snapshot(
            "fixtures/event_alpha/radar_dashboard",
            "current",
            now=_NOW,
        ),
        {},
    )

    assert "3 Decision ideas · market scan unavailable" in candidates_only
    assert "The ideas may originate from other canonical evidence layers" in candidates_only
    assert "See what the radar evaluated—even when no idea qualified" not in candidates_only
    assert candidates_only.count("3 Decision ideas · market scan unavailable") == 1
    assert "Verify acquisition coverage" in candidates_only
    assert "No exact market observations to compare" not in candidates_only


def test_verified_empty_market_scan_does_not_repeat_the_hero_state() -> None:
    source = _sparse_snapshot()
    snapshot = replace(
        source,
        current_market_observations=(),
        market_generation={"status": "complete", "selected_market_row_count": 0},
        current_request_ledger={
            "provider_request_succeeded": True,
            "selected_market_row_count": 0,
        },
    )

    page = render_market_page(snapshot, {})

    assert page.count("Market scan complete · no in-scope observations retained") == 1
    assert "Verified empty market scan" not in page
    assert "No in-scope observations were retained" not in page
    assert "Verify acquisition coverage" not in page
    assert "How this market scan was qualified" in page


def test_market_radar_orders_controls_and_compact_data_before_scan_explanation() -> None:
    body = render_market_page(_sparse_snapshot(), {})

    summary = body.index('class="metric-grid market-metrics"')
    filters = body.index('class="filter-panel embedded-filter-panel market-filters"')
    desktop = body.index('class="panel market-desktop-table"')
    mobile = body.index('class="panel market-mobile-list"')
    explanation = body.index('class="disclosure market-explanation"')

    assert summary < filters < desktop < mobile < explanation
    assert '<details class="disclosure filter-disclosure market-filter-disclosure">' in body
    assert '<details class="disclosure market-explanation">' in body
    assert '<details class="disclosure market-explanation" open>' not in body
    assert body.index("Data-quality read") > explanation
    assert body.index("Where the rows went") > explanation


def test_market_radar_keeps_desktop_comparison_and_adds_mobile_row_details() -> None:
    body = render_market_page(_sparse_snapshot(), {"search": "BTC"})

    assert '<table class="responsive-table market-table">' in body
    assert '<th scope="col">Decision route</th>' in body
    assert body.count('class="market-mobile-card"') == 1
    assert "Showing 1 of 2 exact observations after filters" in body
    assert '<h3>BTC</h3>' in body
    assert '<small>Price</small>' in body
    assert '<small>24h move</small>' in body
    assert '<small>Baseline</small>' in body
    assert '<small>Decision route</small>' in body
    assert '<details class="disclosure market-mobile-details">' in body
    assert "More market evidence" in body
    assert "Returns, liquidity, spread, freshness" in body
    assert '<h3>ETH</h3>' not in body


def test_integrated_generation_does_not_imply_every_idea_descended_from_market_anomalies() -> None:
    source = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    snapshot = replace(
        source,
        current_market_observations=(),
        current_market_anomalies=(),
        market_generation={},
        current_request_ledger={},
    )

    page = render_dashboard_page(snapshot, "/market-radar")

    assert 'aria-label="Independent integrated layer counts"' in page.body
    assert "Independent layer counts" in page.body
    assert "Where the rows went" not in page.body
    assert "no market-only funnel receipt" in page.body
    assert "does not infer a causal chain" in page.body
    assert '<span class="funnel-arrow"' not in page.body


def test_market_quality_zero_idea_copy_uses_operator_visible_candidates() -> None:
    source = _sparse_snapshot()
    diagnostic = {
        "candidate_id": "candidate:diagnostic",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "_decision_model_status": "v2",
        "_dashboard_route": "diagnostic",
        "radar_route": "diagnostic",
    }

    page = render_market_page(replace(source, current_candidates=(diagnostic,)), {})

    assert "produced zero operator-visible current ideas" in page
    assert "not an empty provider response" in page


def test_exact_generation_summary_separates_candidate_rows_from_visible_ideas() -> None:
    page = render_dashboard_page(
        load_dashboard_snapshot(
            "fixtures/event_alpha/radar_dashboard",
            "current",
            now=_NOW,
        ),
        "/ideas",
    )

    assert "4 candidate rows" in page.body
    assert "3 operator-visible" in page.body


def test_ideas_filters_keep_search_route_and_sort_primary() -> None:
    rendered = render_idea_filters({}, action="/ideas")
    advanced_at = rendered.index('<details class="disclosure filter-advanced"')
    primary = rendered[:advanced_at]
    advanced = rendered[advanced_at:]

    assert 'name="search"' in primary
    assert 'name="route"' in primary
    assert 'name="sort"' in primary
    assert 'name="origin"' not in primary
    assert 'name="risk"' not in primary
    assert '<details class="disclosure filter-advanced">' in rendered
    assert 'aria-label="0 advanced filters active">0 active</span>' in rendered
    assert 'name="origin"' in advanced
    assert 'name="risk"' in advanced
    assert 'name="horizon"' in advanced
    assert '<details class="disclosure filter-disclosure idea-filter-disclosure">' in rendered
    assert '<details class="disclosure filter-disclosure idea-filter-disclosure" open>' not in rendered
    assert '<summary><span>Filter &amp; sort ideas</span>' in rendered
    assert '<span class="disclosure__summary">All current ideas</span>' in rendered
    assert 'aria-label="Filter and sort ideas"' in rendered


def test_ideas_filters_open_advanced_section_and_count_only_advanced_queries() -> None:
    rendered = render_idea_filters(
        {
            "route": "risk_watch",
            "origin": "market_led",
            "risk": "high",
            "sort": "evidence_desc",
        },
        action="/ideas",
    )

    assert '<details class="disclosure filter-advanced" open>' in rendered
    assert 'aria-label="2 advanced filters active">2 active</span>' in rendered
    assert '<option value="risk_watch" selected>Risk watch</option>' in rendered
    assert '<option value="market_led" selected>Market-led</option>' in rendered
    assert '<option value="high" selected>High</option>' in rendered
    assert '<option value="evidence_desc" selected>Evidence · high first</option>' in rendered
    assert '<details class="disclosure filter-disclosure idea-filter-disclosure" open>' in rendered
    assert '<span class="disclosure__summary">4 active</span>' in rendered


def test_ideas_intro_uses_compact_operator_copy_and_count() -> None:
    page = render_dashboard_page(
        load_dashboard_snapshot(
            "fixtures/event_alpha/radar_dashboard",
            "current",
            now=_NOW,
        ),
        "/ideas",
    )

    assert '<section class="page-intro ideas-intro">' in page.body
    assert "Current research ideas" in page.body
    assert "Ranked by usefulness, evidence, and risk for human review" in page.body
    assert '<small>ideas</small>' in page.body


def test_idea_comparison_is_collapsed_and_uses_accessible_row_headers() -> None:
    rendered = render_idea_comparison(
        (
            {
                "core_opportunity_id": "core:alpha",
                "symbol": "ALPHA",
                "radar_route": "risk_watch",
            },
            {
                "core_opportunity_id": "core:beta",
                "symbol": "BETA",
                "radar_route": "dashboard_watch",
            },
        )
    )

    assert '<details class="disclosure panel comparison-panel">' in rendered
    assert '<details class="disclosure panel comparison-panel" open>' not in rendered
    assert '<summary><span>Compare ideas in matrix</span>' in rendered
    assert '<span class="filter-chip">2 ideas</span>' in rendered
    assert '<table class="responsive-table mobile-cards">' in rendered
    assert '<th scope="row" data-label="Idea"><a href="/ideas/core%3Aalpha">' in rendered
    assert '<td data-label="Route">Risk watch</td>' in rendered


def test_single_idea_does_not_offer_a_meaningless_comparison_matrix() -> None:
    rendered = render_idea_comparison(({
        "core_opportunity_id": "core:alpha",
        "symbol": "ALPHA",
        "radar_route": "risk_watch",
    },))

    assert rendered == ""


def test_idea_detail_prioritizes_thesis_and_collapses_supporting_context() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    status, _title, body = render_idea_detail(snapshot, "core:alpha")

    assert status == 200
    assert "Catalyst unknown" in body
    assert "Phase breakout" in body
    score_at = body.index('aria-label="Decision scores"')
    for heading in ("Why now", "What confirms", "What invalidates", "Main risks"):
        assert body.index(heading) < score_at
    assert body.index("Decision thesis") < score_at < body.index("How to read this idea")
    assert '<details class="disclosure decision-checklist">' in body
    assert '<details class="disclosure decision-checklist" open>' not in body
    assert "Confirmation and invalidation checklist" in body
    assert '<details class="disclosure thesis-notes">' in body
    assert '<details class="disclosure thesis-notes" open>' not in body
    assert "Missing information" in body
    assert "Supporting facts" in body

    assert '<details class="disclosure data-provenance">' in body
    assert '<details class="disclosure data-provenance" open>' not in body
    for label in (
        "Data mode",
        "Market provider",
        "Baseline",
        "Liquidity basis",
        "Volume basis",
        "Execution quality",
    ):
        assert label in body

    coverage_at = body.index('<details class="disclosure panel context-coverage">')
    assert '<details class="disclosure panel context-coverage" open>' not in body
    assert '<span>Context coverage</span>' in body
    assert '<section class="panel source-panel">' not in body
    assert '<section class="panel catalyst-panel">' not in body
    for heading in (
        "Latest recorded source",
        "Nearby calendar events",
        "RSI and setup evidence",
        "Secondary catalyst view",
    ):
        assert body.index(heading) > coverage_at
    assert "No exact-generation calendar event is attached to this idea." in body
    assert "No exact RSI context is attached." in body


def test_idea_detail_shows_concise_evidence_verdict_and_hides_contract_payloads() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    original_body = (
        "PumpX token holders can trade synthetic exposure to SpaceX before the "
        "initial public offering opens for qualified crypto market participants"
    )
    independent_body = (
        "Independent analysts confirm PumpX settlement contracts reference SpaceX "
        "private market exposure with separate custody documentation for participants"
    )
    contract = source_independence.assess_source_independence(
        [
            {
                "source_id": "original",
                "source_url": "https://one.example/story",
                "title": "Initial catalyst evidence",
                "body": original_body,
                "published_at": "2026-07-12T05:00:00Z",
            },
            {
                "source_id": "syndicated",
                "source_url": "https://two.example/story",
                "title": "Initial catalyst evidence",
                "body": original_body,
                "published_at": "2026-07-12T05:01:00Z",
            },
            {
                "source_id": "independent",
                "source_url": "https://three.example/story",
                "title": "Independent catalyst analysis",
                "body": independent_body,
                "published_at": "2026-07-12T05:02:00Z",
            },
        ]
    )
    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "anomaly-dashboard-verdict",
            "observed_at": "2026-07-12T06:00:00Z",
        },
        {
            "raw_id": "official-dashboard-source",
            "provider": "official_exchange",
            "source_url": "https://exchange.example/notices/dashboard-verdict",
            "content_hash": "b" * 64,
            "published_at": "2026-07-12T05:30:00Z",
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "main_frame_role": "main_catalyst",
            "candidate_role": "direct_subject",
            "impact_path_strength": "direct",
        },
    )
    candidates = tuple(
        {
            **row,
            "source_independence": contract,
            "source_independence_status": "assessed",
            "source_independence_errors": [],
            "independent_source_count": 2,
            "independent_corroboration_count": 1,
            "source_content_cluster_count": 2,
            "source_update_count": 3,
            "evidence_acquisition_accepted_count": 3,
            "catalyst_attribution": attribution,
        }
        if row.get("core_opportunity_id") == "core:alpha"
        else row
        for row in snapshot.current_candidates
    )
    snapshot = replace(snapshot, current_candidates=candidates)

    status, _title, body = render_idea_detail(snapshot, "core:alpha")

    assert status == 200
    assert "Evidence verdict" in body
    assert "Accepted evidence is a validation count, not independent corroboration." in body
    for label, value in (
        ("Raw sources", "3"),
        ("Accepted evidence rows (not corroboration)", "3"),
        ("Content clusters", "2"),
        ("Independent evidence units", "2"),
        ("Additional independent corroborations", "1"),
        ("Syndicated copies collapsed", "1"),
        ("Catalyst timing", "Antecedent"),
        ("Causal eligibility", "Eligible"),
        ("Source authority", "Official"),
    ):
        assert f"<dt>{label}</dt><dd>{value}</dd>" in body
    verdict = body[
        body.index('<section class="panel evidence-verdict">') : body.index(
            "</section>", body.index('<section class="panel evidence-verdict">')
        )
    ]
    assert contract["contract_digest"] not in verdict
    assert attribution["attribution_digest"] not in verdict
    assert contract["contract_digest"] in body
    assert attribution["attribution_digest"] in body
    assert body.index(contract["contract_digest"]) > body.index(
        "Technical lineage, contract digests, and raw identifiers"
    )
    assert "normalized_body" not in body


def test_idea_detail_distinguishes_unassessed_accepted_evidence_from_measured_zero() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    without_measurement = tuple(
        {
            key: value
            for key, value in row.items()
            if key
            not in {
                "accepted_evidence_count",
                "evidence_acquisition_accepted_count",
            }
        }
        if row.get("core_opportunity_id") == "core:alpha"
        else row
        for row in snapshot.current_candidates
    )
    unassessed = replace(snapshot, current_candidates=without_measurement)
    status, _title, body = render_idea_detail(unassessed, "core:alpha")

    assert status == 200
    assert (
        "<dt>Accepted evidence rows (not corroboration)</dt>"
        "<dd>Not assessed</dd>"
    ) in body

    measured_zero = replace(
        snapshot,
        current_candidates=tuple(
            {
                **row,
                "evidence_acquisition_accepted_count": 0,
            }
            if row.get("core_opportunity_id") == "core:alpha"
            else row
            for row in without_measurement
        ),
    )
    status, _title, body = render_idea_detail(measured_zero, "core:alpha")

    assert status == 200
    assert (
        "<dt>Accepted evidence rows (not corroboration)</dt><dd>0</dd>"
    ) in body


def test_idea_detail_suppresses_duplicate_coin_id_but_preserves_lineage() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    status, _title, body = render_idea_detail(snapshot, "core:alpha")

    assert status == 200
    hero = body[body.index('<section class="idea-hero panel">'):body.index(
        "</section>", body.index('<section class="idea-hero panel">')
    )]
    assert "<h2>ALPHA</h2>" in hero
    assert "<span>alpha</span>" not in hero
    assert "Coin ID" in body
    assert "<code>alpha</code>" in body

    distinct_candidate = {**snapshot.current_candidates[0], "coin_id": "alpha-token"}
    distinct_snapshot = replace(snapshot, current_candidates=(distinct_candidate,))
    status, _title, distinct_body = render_idea_detail(distinct_snapshot, "core:alpha")

    assert status == 200
    distinct_hero = distinct_body[
        distinct_body.index('<section class="idea-hero panel">'):
        distinct_body.index(
            "</section>",
            distinct_body.index('<section class="idea-hero panel">'),
        )
    ]
    assert "<h2>ALPHA <span>alpha-token</span></h2>" in distinct_hero


def test_idea_detail_keeps_absent_source_explicit_inside_context_coverage() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    candidate = {
        **snapshot.current_candidates[0],
        "source_url": None,
        "latest_source_url": None,
        "url": None,
    }

    status, _title, body = render_idea_detail(
        replace(snapshot, current_candidates=(candidate,)),
        "core:alpha",
    )

    assert status == 200
    coverage_at = body.index('<details class="disclosure panel context-coverage">')
    assert body.index("Source URL unavailable") > coverage_at
    assert '<section class="panel source-panel">' not in body


def test_idea_detail_consolidates_fully_unavailable_market_history() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )

    status, _title, body = render_idea_detail(snapshot, "core:alpha")

    assert status == 200
    history_at = body.index("<h2>Market history</h2>")
    history_end = body.index(
        '<details class="disclosure panel context-coverage">',
        history_at,
    )
    history = body[history_at:history_end]
    assert 'role="status" aria-label="4 market history series unavailable"' in history
    assert history.count("History unavailable") == 1
    assert '<svg class="radar-inline-chart"' not in history
    assert 'aria-label="Unavailable market history series"' in history
    for label in (
        "Price history",
        "Volume history",
        "Turnover history · proxy evidence",
        "Relative performance vs BTC",
    ):
        assert label in history
    assert "no values are inferred" in history


def test_idea_detail_renders_measured_history_and_compacts_only_missing_series() -> None:
    snapshot = load_dashboard_snapshot(
        "fixtures/event_alpha/radar_dashboard",
        "current",
        now=_NOW,
    )
    history_row = {
        "symbol": "ALPHA",
        "coin_id": "alpha",
        "observed_at": "2026-07-12T06:00:00+00:00",
        "price": 1.25,
    }

    status, _title, body = render_idea_detail(
        replace(snapshot, exact_market_history=(history_row,)),
        "core:alpha",
    )

    assert status == 200
    history_at = body.index("<h2>Market history</h2>")
    history_end = body.index(
        '<details class="disclosure panel context-coverage">',
        history_at,
    )
    history = body[history_at:history_end]
    assert history.count('<svg class="radar-inline-chart"') == 1
    assert "<title>Price history</title>" in history
    assert 'aria-label="3 market history series unavailable"' in history
    assert "Volume history" in history
    assert "Turnover history · proxy evidence" in history
    assert "Relative performance vs BTC" in history
