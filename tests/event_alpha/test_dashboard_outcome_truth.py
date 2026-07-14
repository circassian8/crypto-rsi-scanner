from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.system_pages import render_outcomes_page
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot


def _metric(page: str, label: str) -> str:
    start = page.index(f"<span>{label}</span>")
    return page[start:start + 180]


@pytest.mark.parametrize(
    ("state", "visible_label"),
    (
        ("missing_data", "Missing data"),
        ("stale_market_data", "Stale market data"),
        ("insufficient_market_data", "Insufficient market data"),
        ("skipped_no_asset", "Skipped no asset"),
        ("future_state_not_understood", "Future state not understood"),
    ),
)
def test_explicit_unavailable_outcome_states_are_preserved_and_fail_closed(
    state: str,
    visible_label: str,
) -> None:
    source = _snapshot()
    outcome = dict(source.current_outcomes[0], outcome_status=state)
    snapshot = replace(source, current_outcomes=(outcome,))

    page = render_outcomes_page(snapshot, {"scope": "current"})

    assert visible_label in page
    assert "<strong>0</strong>" in _metric(page, "Current pending")
    assert "<strong>1</strong>" in _metric(page, "Current unavailable")


def test_unavailable_filter_selects_only_incomplete_outcome_rows() -> None:
    source = _snapshot()
    pending = source.current_outcomes[0]
    unavailable = dict(
        source.current_outcomes[1],
        outcome_status="missing_data",
        outcome_label=None,
        outcome_evaluated_at=None,
    )
    snapshot = replace(
        source,
        current_candidates=(
            source.current_candidates[0],
            {"candidate_id": "candidate:eth", "symbol": "ETH"},
        ),
        current_outcomes=(pending, unavailable),
    )

    page = render_outcomes_page(
        snapshot,
        {"scope": "current", "status": "unavailable"},
    )

    assert 'option value="unavailable" selected' in page
    assert 'data-label="Idea">ETH</th>' in page
    assert 'data-label="Idea">BTC</th>' not in page
    assert "Missing data" in page


def test_degraded_fingerprint_verified_outcomes_remain_admitted_but_incomplete() -> None:
    page = render_outcomes_page(_snapshot(), {"scope": "current"})

    assert "<strong>2 admitted</strong>" in _metric(page, "Current outcome rows")
    assert "<strong>Incomplete</strong>" in _metric(page, "Current outcome coverage")
    assert "<strong>1</strong>" in _metric(page, "Current pending")
    assert "<strong>1</strong>" in _metric(page, "Current matured")
    assert "<strong>0</strong>" in _metric(page, "Current unavailable")
    assert 'data-label="Idea">BTC</th>' in page
    assert 'data-label="Idea">ETH</th>' in page


def test_wholly_unavailable_outcome_coverage_suppresses_unverified_rows() -> None:
    source = _snapshot()
    snapshot = replace(source, current_outcomes_metadata={})

    page = render_outcomes_page(snapshot, {"scope": "current"})

    assert "<strong>Unavailable</strong>" in _metric(page, "Current outcome coverage")
    for label in (
        "Current outcome rows",
        "Current pending",
        "Current matured",
        "Current unavailable",
    ):
        assert f"<span>{label}</span>" not in page
    assert "No fingerprint-verified exact outcome artifact is available" in page
    assert "Current outcomes unavailable" in page
    assert "Nothing here yet" not in page
    assert 'data-label="Idea">BTC</th>' not in page
    assert 'data-label="Idea">ETH</th>' not in page


def test_outcome_empty_titles_name_verified_filter_and_historical_states() -> None:
    source = _snapshot()
    verified_empty = render_outcomes_page(
        replace(source, current_candidates=(), current_outcomes=()),
        {"scope": "current"},
    )
    filtered = render_outcomes_page(
        source,
        {"scope": "current", "search": "does-not-exist"},
    )
    historical = render_outcomes_page(
        replace(source, campaign_outcomes=(), cumulative_outcomes=()),
        {"scope": "historical"},
    )

    assert "No current outcome rows" in verified_empty
    assert "No current outcomes match these filters" in filtered
    assert "No historical outcomes match these filters" in historical
    assert "Nothing here yet" not in verified_empty + filtered + historical


def test_outcomes_use_the_same_canonical_operator_route_labels() -> None:
    source = _snapshot()
    outcomes = (
        dict(source.current_outcomes[0], radar_route="actionable_watch"),
        dict(source.current_outcomes[1], radar_route="high_confidence_watch"),
    )

    page = render_outcomes_page(
        replace(source, current_outcomes=outcomes),
        {"scope": "current"},
    )

    assert 'data-label="Route">Actionable idea</td>' in page
    assert 'data-label="Route">High-confidence idea</td>' in page
    assert '<option value="actionable_watch">Actionable idea</option>' in page
    assert (
        '<option value="high_confidence_watch">High-confidence idea</option>'
        in page
    )


def test_zero_matured_warning_describes_observation_stage_not_zero_edge() -> None:
    source = _snapshot()
    snapshot = replace(source, current_outcomes=(source.current_outcomes[0],))

    page = render_outcomes_page(snapshot, {"scope": "current"})

    assert "Observation stage." in page
    assert "not evidence of zero edge" in page
    assert "Only 0 matured rows" not in page
