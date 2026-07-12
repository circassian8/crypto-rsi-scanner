"""Read-only local radar dashboard regressions."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import operator_state
from crypto_rsi_scanner.event_alpha.dashboard.app import RadarDashboardApp, serve_dashboard
from crypto_rsi_scanner.event_alpha.dashboard.loader import _dashboard_decision_row, load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardLoadError
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"


def _snapshot():
    return load_dashboard_snapshot(_FIXTURE_BASE, _FIXTURE_NAMESPACE)


def _fixture_hashes() -> dict[str, str]:
    return {
        path.relative_to(_FIXTURE_BASE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURE_BASE.rglob("*"))
        if path.is_file()
    }


def _request(app, path="/", *, method="GET", query=""):
    captured = {}

    def start_response(status, headers, _exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": query,
            },
            start_response,
        )
    )
    return captured, body


def test_dashboard_loads_only_current_operator_run_and_revision():
    snapshot = _snapshot()

    assert snapshot.run_id == "dashboard-run-current"
    assert snapshot.revision == 7
    assert snapshot.doctor_status == "OK"
    assert snapshot.doctor_verified_revision == 7
    assert snapshot.current_generation_count == 4
    assert snapshot.cumulative_store_count == 5
    assert "OLD" not in {row["symbol"] for row in snapshot.current_candidates}
    assert {row["calendar_event_id"] for row in snapshot.current_calendar_events} == {
        "calendar:current-cpi",
        "calendar:current-regulatory-window",
    }


def test_dashboard_requires_explicit_supported_v2_version_and_hides_legacy_default():
    snapshot = _snapshot()
    by_symbol = {row["symbol"]: row for row in snapshot.current_candidates}

    assert by_symbol["ALPHA"]["_decision_model_status"] == "v2"
    assert by_symbol["<script>alert(1)</script>"]["_decision_model_status"] == "legacy_unclassified"
    default_page = render_dashboard_page(snapshot, "/")
    diagnostic_page = render_dashboard_page(snapshot, "/", include_diagnostics=True)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" not in default_page.body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in diagnostic_page.body
    assert "<script>alert(1)</script>" not in diagnostic_page.body

    partial = dict(by_symbol["ALPHA"])
    partial.pop("actionability_score_components")
    partial.pop("why_still_worth_reviewing")
    assert _dashboard_decision_row(partial)["_decision_model_status"] == "legacy_unclassified"


def test_dashboard_hides_diagnostic_candidate_detail_without_explicit_opt_in():
    snapshot = _snapshot()
    diagnostic = next(
        row for row in snapshot.current_candidates if row.get("_dashboard_route") == "diagnostic"
    )
    identifier = diagnostic["core_opportunity_id"]

    hidden = render_dashboard_page(snapshot, f"/candidate/{identifier}")
    visible = render_dashboard_page(
        snapshot,
        f"/candidate/{identifier}",
        include_diagnostics=True,
    )

    assert hidden.status_code == 404
    assert visible.status_code == 200


def test_market_anomaly_page_uses_only_manifest_scoped_v2_core_rows():
    snapshot = _snapshot()
    page = render_dashboard_page(snapshot, "/anomalies")
    diagnostics = render_dashboard_page(snapshot, "/anomalies", include_diagnostics=True)

    assert "ALPHA" in page.body
    assert "OLD" not in page.body
    assert "SUSP" not in page.body
    assert "SUSP" not in diagnostics.body


def test_candidate_detail_renders_v2_explanations_components_and_safe_source_url():
    page = render_dashboard_page(_snapshot(), "/candidate/core:alpha")

    assert page.status_code == 200
    assert "Fresh high-liquidity breakout" in page.body
    assert "confirmed catalyst" in page.body
    assert "breakout holds above the prior range" in page.body
    assert "market snapshot becomes stale" in page.body
    assert "Actionability score components" in page.body
    assert "Evidence-confidence score components" in page.body
    assert "Risk score components" in page.body
    assert "Actionability penalty components" in page.body
    assert "Hard blockers" in page.body
    assert "Soft penalties" in page.body
    assert "Decision warnings" in page.body
    assert "unknown_catalyst_penalty" in page.body
    assert "fixture &lt;wire&gt;" in page.body
    assert "asset=ALPHA&amp;view=1" in page.body


def test_dashboard_calendar_renders_uncertain_window_and_current_scope_labels():
    page = render_dashboard_page(_snapshot(), "/calendar")

    assert "Expected regulatory decision window" in page.body
    assert "2026-07-20T00:00:00+00:00" in page.body
    assert "2026-07-31T23:59:59+00:00" in page.body
    assert "(window)" in page.body
    assert "needs_confirmation" in page.body
    assert "Current generation:" in page.body
    assert "cumulative core history 5" in page.body


def test_dashboard_is_get_head_only_and_never_mutates_fixture_artifacts():
    before = _fixture_hashes()
    app = RadarDashboardApp(_FIXTURE_BASE, _FIXTURE_NAMESPACE)

    get_meta, get_body = _request(app, "/")
    head_meta, head_body = _request(app, "/health", method="HEAD")
    post_meta, post_body = _request(app, "/", method="POST")

    assert get_meta["status"] == "200 OK"
    assert b"Research idea, not a trade instruction" in get_body
    assert head_meta["status"] == "200 OK"
    assert head_body == b""
    assert post_meta["status"] == "405 Method Not Allowed"
    assert post_meta["headers"]["Allow"] == "GET, HEAD"
    assert post_body == b"Method Not Allowed\n"
    assert _fixture_hashes() == before


def test_dashboard_rejects_missing_operator_state_and_namespace_traversal(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(DashboardLoadError, match="will not guess"):
        load_dashboard_snapshot(tmp_path, "empty")
    with pytest.raises(DashboardLoadError, match="invalid dashboard artifact namespace"):
        load_dashboard_snapshot(tmp_path, "../outside")


def test_dashboard_fails_closed_when_operator_revision_changes_mid_read():
    loaded = operator_state.load_operator_state(_FIXTURE_BASE / _FIXTURE_NAMESPACE)
    assert loaded.valid is True and loaded.state is not None
    changed_state = dict(loaded.state)
    changed_state["revision"] = int(changed_state["revision"]) + 1
    changed = operator_state.EventAlphaOperatorStateReadResult(
        path=loaded.path,
        exists=True,
        valid=True,
        state=changed_state,
    )
    results = iter((loaded, changed))

    with pytest.raises(DashboardLoadError, match="changed"):
        load_dashboard_snapshot(
            _FIXTURE_BASE,
            _FIXTURE_NAMESPACE,
            state_loader=lambda _path: next(results),
            max_attempts=1,
        )


def test_dashboard_fails_closed_when_current_core_count_does_not_match_manifest():
    loaded = operator_state.load_operator_state(_FIXTURE_BASE / _FIXTURE_NAMESPACE)
    assert loaded.valid is True and loaded.state is not None
    mismatched_state = dict(loaded.state)
    mismatched_state["current_generation_core_rows"] = 99
    artifacts = dict(mismatched_state["artifacts"])
    core = dict(artifacts["core_opportunities"])
    core["count"] = 99
    artifacts["core_opportunities"] = core
    mismatched_state["artifacts"] = artifacts
    mismatched = operator_state.EventAlphaOperatorStateReadResult(
        path=loaded.path,
        exists=True,
        valid=True,
        state=mismatched_state,
    )

    with pytest.raises(DashboardLoadError, match="count does not match"):
        load_dashboard_snapshot(
            _FIXTURE_BASE,
            _FIXTURE_NAMESPACE,
            state_loader=lambda _path: mismatched,
            max_attempts=1,
        )


def test_dashboard_fails_closed_when_manifest_calendar_changes_without_revision(tmp_path):
    target = tmp_path / "current"
    shutil.copytree(_FIXTURE_BASE / _FIXTURE_NAMESPACE, target)
    with (target / "event_unified_calendar_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(DashboardLoadError, match="digest does not match"):
        load_dashboard_snapshot(tmp_path, "current")


def test_dashboard_never_turns_unsafe_source_url_into_a_link():
    snapshot = _snapshot()
    row = dict(snapshot.current_candidates[0])
    row["latest_source_url"] = "javascript:alert(1)"
    unsafe_snapshot = replace(snapshot, current_candidates=(row, *snapshot.current_candidates[1:]))
    page = render_dashboard_page(unsafe_snapshot, f"/candidate/{row['core_opportunity_id']}")

    assert "href=\"javascript:" not in page.body
    assert "unsafe or unavailable source URL" in page.body


def test_dashboard_refuses_non_loopback_bind():
    with pytest.raises(ValueError, match="loopback"):
        serve_dashboard(_FIXTURE_BASE, _FIXTURE_NAMESPACE, host="0.0.0.0")
