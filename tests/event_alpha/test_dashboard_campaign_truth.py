"""Run-history presentation regressions for missing and exact values."""

from __future__ import annotations

from dataclasses import replace

from crypto_rsi_scanner.event_alpha.dashboard.campaign_page import (
    render_campaign_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.shell import render_shell
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import render_health_page
from crypto_rsi_scanner.event_alpha.dashboard.system_page_support import (
    display_count,
    first_recorded,
)
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot


def test_count_presentation_preserves_zero_and_does_not_invent_missing_zero() -> None:
    assert first_recorded(0, 80) == 0
    assert first_recorded(None, 80) == 80
    assert display_count(0) == "0"
    assert display_count(None) == "Unavailable"


def test_current_run_contract_preserves_exact_zero_before_fallback_counts() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        current_request_ledger={
            **source.current_request_ledger,
            "raw_market_row_count": 0,
            "selected_market_row_count": 0,
        },
        market_generation={
            **source.market_generation,
            "raw_market_row_count": 80,
            "selected_market_row_count": 30,
            "direct_feature_count": 12,
            "proxy_feature_count": 5,
            "market_provenance": {
                "data_quality": {
                    "direct_feature_count": 0,
                    "proxy_feature_count": 0,
                }
            },
        },
    )

    page = render_campaign_page(snapshot, {})

    assert "<dt>Raw / selected rows</dt><dd>0 / 0</dd>" in page
    assert "<dt>Direct / proxy features</dt><dd>0 / 0</dd>" in page
    assert "<dt>Raw / selected rows</dt><dd>80 / 30</dd>" not in page
    assert "<dt>Direct / proxy features</dt><dd>12 / 5</dd>" not in page


def test_fixture_run_marks_unadmitted_market_layer_unavailable_not_zero() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        operator_state={**source.operator_state, "run_mode": "fixture"},
        current_market_observations=(),
        current_market_anomalies=(),
        current_request_ledger={},
        market_generation={},
    )

    page = render_campaign_page(snapshot, {})
    metrics = page.split('<div class="metric-grid">', 1)[1].split("</div>", 1)[0]

    assert '<span>Fixture observations</span><strong>Unavailable</strong>' in metrics
    assert '<span>Fixture observations</span><strong>0</strong>' not in metrics
    assert (
        "<dt>Observations / anomalies / canonical candidates / current ideas</dt>"
        "<dd>Unavailable / Unavailable / 1 / 1</dd>"
    ) in page
    assert "observations unavailable" in page
    assert "anomalies unavailable" in page
    assert "0 observations" not in page
    assert "0 warm baselines" not in page
    assert "<dt>Baseline</dt><dd>Unavailable</dd>" in page
    assert "<dt>Spread verified</dt><dd>Unavailable</dd>" in page


def test_missing_run_booleans_and_counts_render_as_not_recorded_or_unavailable() -> None:
    source = _snapshot()
    receipt = {
        "attempt_id": "attempt-with-missing-fields",
        "recorded_at": "2026-07-14T10:00:00+00:00",
        "status": "unknown",
        "provider": "coingecko",
    }
    snapshot = replace(
        source,
        current_request_ledger={"provider": "coingecko"},
        market_generation={"status": "complete", "provider": "coingecko"},
        campaign_attempts=(receipt,),
        campaign_latest_attempt=receipt,
        campaign_reservation={"status": "released"},
        campaign_history_metadata={
            "attempts": {
                "authority": "historical_non_authoritative",
                "source_row_count": None,
                "returned_row_count": 0,
            }
        },
    )

    page = render_campaign_page(snapshot, {})

    assert "<dt>Raw / selected rows</dt><dd>Unavailable / Unavailable</dd>" in page
    assert "<dt>Core / cards</dt><dd>Unavailable / Unavailable</dd>" in page
    assert "<dt>Direct / proxy features</dt><dd>Unavailable / Unavailable</dd>" in page
    assert (
        '<dt>Authorization at generation</dt><dd><span class="status-badge '
        'status-badge--neutral">Not recorded</span></dd>'
    ) in page
    assert (
        '<dt>Provider request</dt><dd><span class="status-badge '
        'status-badge--neutral">Not recorded</span></dd>'
    ) in page
    assert "<dt>Provider call attempted</dt>" in page
    assert "<dt>Request succeeded</dt>" in page
    assert "<dt>Campaign counted</dt>" in page
    metrics = page.split('<div class="metric-grid">', 1)[1].split("</div>", 1)[0]
    assert '<span>Successful data fetches</span><strong>Not recorded</strong>' in metrics
    assert '<span>Pilot runs counted</span><strong>Not recorded</strong>' in metrics
    assert (
        '<dt>No-send</dt><dd><span class="status-badge '
        'status-badge--neutral">Not recorded</span></dd>'
    ) in page
    assert "No send not recorded" in page
    assert '<td data-label="Source rows">Unavailable</td>' in page
    assert '<td data-label="Loaded rows">0</td>' in page


def test_current_run_summary_names_missing_provider_state() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        current_request_ledger={},
        market_generation={},
    )

    page = render_campaign_page(snapshot, {})

    assert "Provider not recorded" in page
    assert '<div class="chip-row"><span class="status-badge status-badge--positive">Authoritative</span><span class="status-badge status-badge--positive">Validation passed</span><span class="status-badge status-badge--neutral">Unavailable</span>' not in page


def test_health_contract_does_not_convert_missing_booleans_to_no() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        operator_state={"generated_at": "2026-07-14T10:00:00+00:00"},
        current_request_ledger={"provider": "coingecko"},
    )

    page = render_health_page(snapshot)

    for label in (
        "Research only",
        "No-send enforced",
        "Authorization at request",
        "Provider call attempted",
        "Request succeeded",
        "No-send",
    ):
        assert (
            f'<dt>{label}</dt><dd><span class="status-badge '
            'status-badge--neutral">Not recorded</span></dd>'
        ) in page
    assert "CoinGecko request state was not recorded" in page
    assert "CoinGecko request was not attempted" not in page


def test_today_baseline_snapshot_does_not_invent_zeroes_without_market_rows() -> None:
    source = _snapshot()
    snapshot = replace(
        source,
        current_market_observations=(),
        market_generation={},
    )

    page = render_today_page(snapshot, query={})
    section = page.split("<h2>Baseline maturity</h2>", 1)[1].split("</section>", 1)[0]

    assert "<dt>Current-row baseline</dt><dd>Unavailable</dd>" in section
    assert (
        "<dt>Current rows · warm / warming / cold</dt><dd>Unavailable</dd>"
        in section
    )
    assert "<dt>Spread coverage</dt><dd>Unavailable</dd>" in section
    assert "0 / 0 / 0" not in section
    assert "0/0" not in section


def test_shell_reserves_campaign_excluded_for_explicit_false() -> None:
    snapshot = _snapshot()

    page = render_shell(snapshot, title="Run history", path="/campaign-history", body="")

    assert "CAMPAIGN NOT RECORDED" in page
    assert "CAMPAIGN EXCLUDED" not in page
    assert "Validation passed" in page
    assert "Doctor clean" not in page
    assert 'aria-label="Navigate. Current page: Run history"' in page
    assert "Research only · human decision required · no execution" in page
    assert "How to use this run:" in page
    assert "Safety boundary:" not in page


def test_health_source_gap_names_affected_provider_once() -> None:
    page = render_health_page(_snapshot())

    assert (
        "Provider configuration is missing. Affected providers: Tokenomist."
        in page
    )
    assert "Missing provider configuration. Missing:" not in page


def test_run_history_authority_note_is_operator_oriented() -> None:
    page = render_campaign_page(_snapshot(), {})

    assert "Use this exact run and revision as the reference point" in page
    assert "the receipts below are historical context" in page
    assert "This is the only section on this page allowed" not in page
