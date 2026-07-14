"""Read-time expiry overlay regressions for the local Decision Radar."""

from __future__ import annotations

import copy
from dataclasses import replace

from crypto_rsi_scanner.event_alpha.dashboard.loader import _dashboard_decision_row
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page
from tests.event_alpha.test_radar_dashboard import _snapshot


def test_dashboard_suppresses_expired_actionability_without_mutating_canonical_values():
    snapshot = _snapshot()
    rows = tuple(
        _dashboard_decision_row(row, read_at="2026-07-12T12:00:00+00:00")
        for row in snapshot.current_candidates
    )
    expired_snapshot = replace(snapshot, current_candidates=rows)
    alpha = next(row for row in rows if row.get("symbol") == "ALPHA")

    assert alpha["radar_route"] == "actionable_watch"
    assert alpha["radar_actionable"] is True
    assert alpha["_dashboard_route"] == "diagnostic"
    assert alpha["_decision_expired_at_read_time"] is True
    assert alpha["_decision_read_time_reason"] == (
        "canonical_expiry_at_or_before_dashboard_read_time"
    )

    page = render_dashboard_page(expired_snapshot, "/")
    assert "Expired ideas (not currently actionable)" in page.body
    assert "Expired; current actionability suppressed" in page.body
    expired_section = page.body.split(
        "Expired ideas (not currently actionable)", 1
    )[1]
    assert "Expired · Actionable idea at evaluation" in expired_section
    assert "route-actionable_watch" in expired_section
    assert "/candidate/core%3Aalpha" not in page.body.split(
        "Expired ideas (not currently actionable)", 1
    )[0]

    detail = render_dashboard_page(expired_snapshot, "/candidate/core:alpha")
    assert detail.status_code == 200
    assert "Expired · read-time visibility suppressed" in detail.body
    assert "Historical evaluation snapshot" in detail.body
    assert ">Expired</span>" in detail.body
    assert "Actionable idea at evaluation" in detail.body
    assert "canonical_expiry_at_or_before_dashboard_read_time" in detail.body


def test_dashboard_expiry_suppresses_non_actionable_watch_without_mutation():
    snapshot = _snapshot()
    loaded_fade = next(
        row for row in snapshot.current_candidates if row.get("symbol") == "FADE"
    )
    source = {
        key: value
        for key, value in loaded_fade.items()
        if not key.startswith("_decision_") and key != "_dashboard_route"
    }
    source["expires_at"] = "2026-07-12T11:59:59+00:00"
    before = copy.deepcopy(source)

    projected = _dashboard_decision_row(
        source,
        read_at="2026-07-12T12:00:00+00:00",
    )
    expired_snapshot = replace(snapshot, current_candidates=(projected,))

    assert source == before
    assert projected["radar_route"] == "fade_exhaustion_review"
    assert projected["radar_actionable"] is False
    assert projected["expires_at"] == "2026-07-12T11:59:59+00:00"
    assert projected["_dashboard_route"] == "diagnostic"
    assert projected["_decision_expired_at_read_time"] is True
    assert projected["_decision_read_time_reason"] == (
        "canonical_expiry_at_or_before_dashboard_read_time"
    )
    assert expired_snapshot.visible_current_candidates == ()
    assert expired_snapshot.diagnostic_candidates == ()
    assert expired_snapshot.expired_current_candidates == (projected,)


def test_visible_candidate_projection_defensively_rejects_expired_overlay():
    snapshot = _snapshot()
    visible = snapshot.visible_current_candidates[0]
    expired_with_visible_route = dict(
        visible,
        _dashboard_route="risk_watch",
        _decision_expired_at_read_time=True,
        _decision_read_time_reason=(
            "canonical_expiry_at_or_before_dashboard_read_time"
        ),
    )
    projected = replace(snapshot, current_candidates=(expired_with_visible_route,))

    assert projected.visible_current_candidates == ()
    assert projected.diagnostic_candidates == ()
    assert projected.expired_current_candidates == (expired_with_visible_route,)


def test_expired_canonical_diagnostic_requires_opt_in_across_dashboard_surfaces():
    source = _snapshot()
    expired_diagnostic = dict(
        source.current_candidates[0],
        core_opportunity_id="core:expired-diagnostic",
        symbol="EXPIRED_DIAGNOSTIC",
        radar_route="diagnostic",
        radar_actionable=False,
        _dashboard_route="diagnostic",
        _decision_model_status="v2",
        _decision_expired_at_read_time=True,
        _decision_read_time_reason=(
            "canonical_expiry_at_or_before_dashboard_read_time"
        ),
    )
    snapshot = replace(source, current_candidates=(expired_diagnostic,))

    assert snapshot.expired_visible_current_candidates == ()
    assert snapshot.expired_current_candidates == ()
    assert snapshot.expired_diagnostic_candidates == (expired_diagnostic,)

    default_today = render_dashboard_page(snapshot, "/")
    default_ideas = render_dashboard_page(snapshot, "/ideas")
    default_detail = render_dashboard_page(
        snapshot,
        "/candidate/core:expired-diagnostic",
    )

    assert "EXPIRED_DIAGNOSTIC" not in default_today.body
    assert "EXPIRED_DIAGNOSTIC" not in default_ideas.body
    assert default_detail.status_code == 404

    diagnostic_today = render_dashboard_page(
        snapshot,
        "/",
        include_diagnostics=True,
    )
    diagnostic_ideas = render_dashboard_page(
        snapshot,
        "/ideas",
        include_diagnostics=True,
    )
    diagnostic_detail = render_dashboard_page(
        snapshot,
        "/candidate/core:expired-diagnostic",
        include_diagnostics=True,
    )

    assert "EXPIRED_DIAGNOSTIC" in diagnostic_today.body
    assert "EXPIRED_DIAGNOSTIC" in diagnostic_ideas.body
    assert "Expired diagnostic controls" in diagnostic_ideas.body
    assert diagnostic_detail.status_code == 200
    assert "Historical evaluation snapshot" in diagnostic_detail.body
