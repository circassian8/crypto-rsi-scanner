"""Read-only local radar dashboard regressions."""

from __future__ import annotations

import copy
import hashlib
from http.client import HTTPConnection
import json
import socket
import shutil
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from wsgiref.simple_server import WSGIRequestHandler

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import fingerprints, operator_state
from crypto_rsi_scanner.event_alpha.dashboard import loader as dashboard_loader
from crypto_rsi_scanner.event_alpha.dashboard.__main__ import _smoke
from crypto_rsi_scanner.event_alpha.dashboard.app import (
    RadarDashboardApp,
    _make_dashboard_server,
    serve_dashboard,
)
from crypto_rsi_scanner.event_alpha.dashboard.loader import _dashboard_decision_row, load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardLoadError
from crypto_rsi_scanner.event_alpha.dashboard.render import (
    _candidate_data_quality,
    render_dashboard_page,
)


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"
_TEST_NOW = "2026-07-12T06:03:00+00:00"
_STATE_FILENAME = "event_alpha_operator_state.json"


def _snapshot():
    return load_dashboard_snapshot(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)


def _fixture_state() -> dict[str, object]:
    return json.loads((_FIXTURE_BASE / _FIXTURE_NAMESPACE / _STATE_FILENAME).read_text())


def _state_result(state: dict[str, object]):
    return operator_state.EventAlphaOperatorStateReadResult(
        path=_FIXTURE_BASE / _FIXTURE_NAMESPACE / _STATE_FILENAME,
        exists=True,
        valid=True,
        state=copy.deepcopy(state),
    )


def _snapshot_from_state(state: dict[str, object]):
    return load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        state_loader=lambda _path: _state_result(state),
        max_attempts=1,
        now=_TEST_NOW,
    )


def _copy_namespace(tmp_path: Path) -> Path:
    target = tmp_path / _FIXTURE_NAMESPACE
    shutil.copytree(_FIXTURE_BASE / _FIXTURE_NAMESPACE, target)
    return target


def _read_state(namespace_dir: Path) -> dict[str, object]:
    return json.loads((namespace_dir / _STATE_FILENAME).read_text())


def _write_state(namespace_dir: Path, state: dict[str, object]) -> None:
    (namespace_dir / _STATE_FILENAME).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _refresh_fingerprint(namespace_dir: Path, state: dict[str, object], artifact_name: str) -> None:
    entry = state["artifacts"][artifact_name]
    artifact_path = namespace_dir / entry["path"]
    kind = entry["fingerprint_kind"]
    entry.update(fingerprints.fingerprint_path(artifact_path, kind=kind))


def _add_current_artifact(
    namespace_dir: Path,
    state: dict[str, object],
    artifact_name: str,
    path: Path,
    *,
    kind: str,
    count: int,
) -> None:
    state["artifacts"][artifact_name] = {
        "status": "current",
        "run_id": state["run_id"],
        "path": path.name,
        "reason": None,
        "generated_at": state["generated_at"],
        "count": count,
        **fingerprints.fingerprint_path(path, kind=kind),
    }


def _add_exact_market_jsonl_artifacts(
    namespace_dir: Path,
    state: dict[str, object],
) -> None:
    identity = {
        "run_id": state["run_id"],
        "profile": state["profile"],
        "artifact_namespace": state["artifact_namespace"],
    }
    snapshots_path = namespace_dir / "event_market_state_snapshots.jsonl"
    snapshots_path.write_text(
        json.dumps(
            {
                **identity,
                "row_type": "event_market_state_snapshot",
                "symbol": "SNAP",
                "coin_id": "snapshot-asset",
                "observed_at": "2026-07-12T06:01:30+00:00",
                "return_24h": 7.5,
                "return_unit": "percent_points",
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_current_artifact(
        namespace_dir,
        state,
        "market_state_snapshots",
        snapshots_path,
        kind="jsonl_lines",
        count=1,
    )
    anomalies_path = namespace_dir / "event_market_anomalies.jsonl"
    anomalies_path.write_text(
        json.dumps(
            {
                **identity,
                "row_type": "event_market_anomaly",
                "market_anomaly_id": "market-anomaly:fixture",
                "symbol": "ANOM",
                "market_state_class": "rapid_move",
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_current_artifact(
        namespace_dir,
        state,
        "market_anomalies",
        anomalies_path,
        kind="jsonl_lines",
        count=1,
    )


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
    assert snapshot.generation_authoritative is True
    assert snapshot.generation_authority_reasons == ()
    assert snapshot.current_generation_count == 4
    assert snapshot.cumulative_store_count == 5
    assert "OLD" not in {row["symbol"] for row in snapshot.current_candidates}
    assert {row["calendar_event_id"] for row in snapshot.current_calendar_events} == {
        "calendar:current-cpi",
        "calendar:current-regulatory-window",
    }


def test_dashboard_badges_distinguish_current_fixture_and_live_no_send():
    fixture = _snapshot()
    fixture_page = render_dashboard_page(fixture, "/")
    assert "CURRENT" in fixture_page.body
    assert "FIXTURE" in fixture_page.body
    assert "NO-SEND" in fixture_page.body

    live = replace(
        fixture,
        current_candidates=tuple(
            {**row, "data_mode": "live"}
            for row in fixture.current_candidates
        ),
    )
    live_page = render_dashboard_page(live, "/")
    assert "UNVERIFIED LIVE CLAIM" in live_page.body
    assert "LIVE / REAL DATA" not in live_page.body


def test_dashboard_badges_disclose_exact_market_provenance_and_campaign_status():
    from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
        normalize_market_provenance,
    )

    fixture = _snapshot()
    base_row = dict(
        next(
            row
            for row in fixture.current_candidates
            if row.get("_dashboard_route") != "diagnostic"
        )
    )
    common_provenance = {
        "schema_version": "crypto_radar_market_provenance_v2",
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "provider_call_attempted": True,
        "provider_call_succeeded": True,
        "request_ledger_path": "event_market_no_send_request_ledger.json",
        "request_ledger_sha256": "1" * 64,
        "provider_source_artifact": "event_market_no_send_market_rows.json",
        "provider_source_artifact_sha256": "2" * 64,
        "provider_generation_id": "dashboard-market-run",
        "cache_status": "write_through",
        "feature_basis": {"spread": "provider_observed"},
        "data_quality": {"baseline_status": "warm"},
    }
    mocked_provenance = normalize_market_provenance({
        **common_provenance,
        "data_acquisition_mode": "mocked_fixture",
        "candidate_source_mode": "mocked_fixture",
        "provider": "mock_coingecko",
        "live_provider_authorized": False,
    })
    live_provenance = normalize_market_provenance({
        **common_provenance,
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "live_provider_authorized": True,
    })
    mocked = {
        **base_row,
        "market_provenance": mocked_provenance,
    }
    live = {
        **base_row,
        "market_provenance": live_provenance,
    }

    mocked_snapshot = replace(
        fixture,
        operator_state={
            **fixture.operator_state,
            "market_no_send_provenance": mocked["market_provenance"],
        },
        current_candidates=(mocked,),
    )
    live_snapshot = replace(
        fixture,
        operator_state={
            **fixture.operator_state,
            "market_no_send_provenance": live["market_provenance"],
        },
        current_candidates=(live,),
    )
    mocked_page = render_dashboard_page(
        mocked_snapshot,
        "/",
    )
    live_page = render_dashboard_page(
        live_snapshot,
        "/",
    )

    assert "MOCKED FIXTURE" in mocked_page.body
    assert "CAMPAIGN EXCLUDED" in mocked_page.body
    assert "LIVE DATA" in live_page.body
    assert "CAMPAIGN COUNTED" in live_page.body
    detail = render_dashboard_page(
        live_snapshot,
        f"/candidate/{live['core_opportunity_id']}",
    )
    assert "Cache status" in detail.body
    assert "write_through" in detail.body


def test_dashboard_prefers_per_asset_market_quality_over_generation_aggregate():
    row = {
        "data_quality": {
            "direct_feature_count": 99,
            "proxy_feature_count": 88,
        },
        "market_state_snapshot": {},
        "market_snapshot": {
            "market_data_quality": {
                "baseline_status": "cold",
                "direct_feature_count": 7,
                "proxy_feature_count": 1,
                "spread_basis": "provider_observed",
            }
        },
    }

    assert _candidate_data_quality(row) == row["market_snapshot"]["market_data_quality"]


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


def test_dashboard_renders_exact_fingerprinted_market_source_rows_and_coverage(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    identity = {
        "run_id": state["run_id"],
        "profile": state["profile"],
        "artifact_namespace": state["artifact_namespace"],
    }
    rows = [
        {
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "observed_at": "2026-07-12T06:01:30+00:00",
            "price": 60_000.0,
            "return_1h": 0.01,
            "return_4h": 0.03,
            "return_24h": 0.10,
            "return_unit": "fraction",
            "volume_zscore_24h": 1.25,
            "liquidity_usd": 30_000_000_000.0,
            "temporal_baseline_status": "warming",
            "spread_status": "unavailable",
            "freshness_status": "fresh",
            "provider": "coingecko",
        },
        {
            "symbol": "ETH",
            "coin_id": "ethereum",
            "observed_at": "2026-07-12T06:01:30+00:00",
            "price": 2_000.0,
            "return_1h": -1.0,
            "return_4h": -2.0,
            "return_24h": -4.0,
            "return_unit": "percent_points",
            "volume_zscore_24h": -0.2,
            "liquidity_usd": 8_000_000_000.0,
            "temporal_baseline_status": "warm",
            "spread_status": "verified",
            "freshness_status": "fresh",
            "provider": "coingecko",
        },
    ]
    source_path = target / "event_market_no_send_market_rows.json"
    source_path.write_text(
        json.dumps({**identity, "selected_market_row_count": len(rows), "rows": rows}) + "\n",
        encoding="utf-8",
    )
    _add_current_artifact(
        target,
        state,
        "market_no_send_source_cache",
        source_path,
        kind="file_bytes",
        count=1,
    )
    coverage_path = target / state["artifacts"]["source_coverage_json"]["path"]
    coverage = json.loads(coverage_path.read_text())
    coverage["packs"] = [
        {
            "source_pack": "market_anomaly_pack",
            "provider_coverage_status": "partial",
            "accepted_evidence_count": 0,
            "configured_providers": ["coingecko"],
            "healthy_providers": ["coingecko"],
            "missing_providers": ["gdelt"],
            "coverage_gap_reason": "gdelt_not_observed",
        }
    ]
    coverage_path.write_text(json.dumps(coverage, sort_keys=True) + "\n", encoding="utf-8")
    _refresh_fingerprint(target, state, "source_coverage_json")
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    page = render_dashboard_page(snapshot, "/anomalies")
    health = render_dashboard_page(snapshot, "/health")

    assert snapshot.generation_authoritative is True
    assert len(snapshot.current_market_observations) == 2
    assert snapshot.source_coverage["packs"][0]["provider_coverage_status"] == "partial"
    assert "Current market observation scan" in page.body
    assert "Exact market observations" in page.body
    assert "+10.00%" in page.body
    assert "-4.00%" in page.body
    assert "warming=1" in page.body
    assert "warm=1" in page.body
    assert "Execution spread confirmed" in page.body
    assert "1 / 2" in page.body
    assert "Exact-generation source-pack coverage" in health.body
    assert "gdelt_not_observed" in health.body


def test_dashboard_prefers_exact_market_snapshots_and_anomalies_when_manifested(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    identity = {
        "run_id": state["run_id"],
        "profile": state["profile"],
        "artifact_namespace": state["artifact_namespace"],
    }
    source_path = target / "event_market_no_send_market_rows.json"
    source_path.write_text(
        json.dumps(
            {
                **identity,
                "selected_market_row_count": 1,
                "rows": [{"symbol": "SOURCE_ONLY", "return_24h": 0.5, "return_unit": "fraction"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_current_artifact(
        target,
        state,
        "market_no_send_source_cache",
        source_path,
        kind="file_bytes",
        count=1,
    )
    _add_exact_market_jsonl_artifacts(target, state)
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    default_page = render_dashboard_page(snapshot, "/anomalies")
    page = render_dashboard_page(snapshot, "/anomalies", include_diagnostics=True)

    assert snapshot.generation_authoritative is True
    assert [row["symbol"] for row in snapshot.current_market_observations] == ["SNAP"]
    assert [row["symbol"] for row in snapshot.current_market_anomalies] == ["ANOM"]
    assert "SOURCE_ONLY" not in page.body
    assert "SNAP" in page.body
    assert "ANOM" in page.body
    assert "ANOM" in default_page.body
    assert "rapid_move" in default_page.body
    assert "scan evidence" in default_page.body.casefold()
    assert "SOURCE_ONLY" not in default_page.body


@pytest.mark.parametrize(
    "artifact_name",
    ("market_state_snapshots", "market_anomalies"),
)
def test_dashboard_market_jsonl_count_mismatch_fails_authority(
    tmp_path,
    artifact_name,
):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    _add_exact_market_jsonl_artifacts(target, state)
    state["artifacts"][artifact_name]["count"] = 2
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert f"{artifact_name}:current_count_mismatch" in (
        snapshot.generation_authority_reasons
    )


def test_dashboard_market_source_count_mismatch_fails_current_authority(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    source_path = target / "event_market_no_send_market_rows.json"
    source_path.write_text(
        json.dumps(
            {
                "run_id": state["run_id"],
                "profile": state["profile"],
                "artifact_namespace": state["artifact_namespace"],
                "selected_market_row_count": 2,
                "rows": [{"symbol": "BTC"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _add_current_artifact(
        target,
        state,
        "market_no_send_source_cache",
        source_path,
        kind="file_bytes",
        count=1,
    )
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert "market_no_send_source_cache:selected_count_mismatch" in (
        snapshot.generation_authority_reasons
    )


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
    for label in (
        "Primary thesis origin",
        "Thesis origins",
        "Timing",
        "Preferred horizon",
        "Expires",
        "Spread",
        "Urgency",
        "Chase risk",
    ):
        assert label in page.body


def test_dashboard_candidate_table_shows_trader_timing_and_execution_dimensions():
    page = render_dashboard_page(_snapshot(), "/")

    for label in ("Urgency", "Horizon", "Expires", "Spread", "Chase risk"):
        assert label in page.body


def test_dashboard_calendar_renders_uncertain_window_and_current_scope_labels():
    page = render_dashboard_page(_snapshot(), "/calendar")

    assert "Expected regulatory decision window" in page.body
    assert "2026-07-20T00:00:00+00:00" in page.body
    assert "2026-07-31T23:59:59+00:00" in page.body
    assert "(window)" in page.body
    assert "needs_confirmation" in page.body
    assert "Current generation:" in page.body
    assert "namespace-local core store rows 5" in page.body


def test_dashboard_calendar_prefers_exact_generation_snapshot_status_for_empty_layer():
    snapshot = replace(
        _snapshot(),
        current_calendar_events=(),
        market_generation={
            "calendar_snapshot": {
                "status": "skipped_missing_config",
                "configured": False,
                "counts": {"scheduled": 0, "unlocks": 0},
                "error": None,
            }
        },
    )

    page = render_dashboard_page(snapshot, "/calendar")

    assert "Calendar acquisition was not configured" in page.body
    assert "not evidence that no scheduled events exist" in page.body
    assert "status=skipped_missing_config" in page.body
    assert "scheduled=0" in page.body


def test_dashboard_calendar_distinguishes_healthy_empty_from_normalization_rejection():
    healthy = replace(
        _snapshot(),
        current_calendar_events=(),
        market_generation={
            "calendar_snapshot": {
                "status": "healthy_empty",
                "configured": True,
                "retained_row_count": 0,
                "unified_calendar_count": 0,
                "normalization_rejected_count": 0,
                "normalization_status": "healthy_empty",
            }
        },
    )
    rejected = replace(
        healthy,
        market_generation={
            "calendar_snapshot": {
                "status": "healthy_nonempty",
                "configured": True,
                "retained_row_count": 1,
                "unified_calendar_count": 0,
                "normalization_rejected_count": 1,
                "normalization_status": "normalization_rejected",
            }
        },
    )

    healthy_page = render_dashboard_page(healthy, "/calendar")
    rejected_page = render_dashboard_page(rejected, "/calendar")

    assert "calendar snapshot was observed" in healthy_page.body
    assert "healthy_empty" in healthy_page.body
    assert "failed unified-calendar normalization" in rejected_page.body
    assert "normalization_rejected_count=1" in rejected_page.body


@pytest.mark.parametrize(
    ("status", "error_class", "expected"),
    (
        ("unavailable", "snapshot_unreadable", "failed or was unavailable"),
        ("stale", "snapshot_too_old", "calendar snapshot was stale"),
        ("fixture_rejected_live", "fixture_provenance", "calendar provenance was rejected"),
    ),
)
def test_dashboard_calendar_does_not_label_failed_stale_or_rejected_input_unconfigured(
    status,
    error_class,
    expected,
):
    snapshot = replace(
        _snapshot(),
        current_calendar_events=(),
        market_generation={
            "calendar_snapshot": {
                "status": status,
                "configured": True,
                "error_class": error_class,
                "retained_row_count": 0,
            }
        },
    )

    page = render_dashboard_page(snapshot, "/calendar")

    assert expected in page.body
    assert error_class in page.body
    assert "Calendar acquisition was not configured" not in page.body


def test_dashboard_empty_calendar_uses_source_pack_coverage_for_legacy_generation():
    snapshot = replace(
        _snapshot(),
        current_calendar_events=(),
        market_generation={},
        source_coverage={
            "packs": [
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "not_configured",
                }
            ]
        },
    )

    page = render_dashboard_page(snapshot, "/calendar")

    assert "Relevant source packs were not configured" in page.body
    assert "not evidence that no relevant events exist" in page.body


def test_dashboard_is_get_head_only_and_never_mutates_fixture_artifacts():
    before = _fixture_hashes()
    app = RadarDashboardApp(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)

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
    state = _fixture_state()
    changed_state = copy.deepcopy(state)
    changed_state["revision"] = int(changed_state["revision"]) + 1
    results = iter((_state_result(state), _state_result(changed_state)))

    with pytest.raises(DashboardLoadError, match="changed"):
        load_dashboard_snapshot(
            _FIXTURE_BASE,
            _FIXTURE_NAMESPACE,
            state_loader=lambda _path: next(results),
            max_attempts=1,
            now=_TEST_NOW,
        )


def test_dashboard_marks_generation_untrusted_when_current_core_count_does_not_match_manifest():
    mismatched_state = _fixture_state()
    mismatched_state["current_generation_core_rows"] = 99
    mismatched_state["artifacts"]["core_opportunities"]["count"] = 99

    snapshot = _snapshot_from_state(mismatched_state)

    assert snapshot.generation_authoritative is False
    assert "core_opportunities:current_count_mismatch" in snapshot.generation_authority_reasons
    page = render_dashboard_page(snapshot, "/")
    assert page.status_code == 200
    assert "Current-generation research content is unavailable" in page.body
    assert "Fresh high-liquidity breakout" not in page.body
    assert "current candidates suppressed (untrusted)" in page.body
    assert "namespace-local core store rows 5" not in page.body


def test_dashboard_marks_generation_untrusted_when_manifest_calendar_changes_without_revision(tmp_path):
    target = _copy_namespace(tmp_path)
    with (target / "event_unified_calendar_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert not snapshot.current_calendar_events
    assert any(
        reason.startswith("unified_calendar:fingerprint_content_mismatch")
        for reason in snapshot.generation_authority_reasons
    )
    health = render_dashboard_page(snapshot, "/health")
    current = render_dashboard_page(snapshot, "/calendar")
    assert health.status_code == 200
    assert "Generation authority" in health.body
    assert current.status_code == 200
    assert "Expected regulatory decision window" not in current.body


def test_dashboard_compares_full_operator_state_even_when_revision_is_unchanged():
    before = _fixture_state()
    after = copy.deepcopy(before)
    after["doctor"]["warning_count"] = 1
    results = iter((_state_result(before), _state_result(after)))

    with pytest.raises(DashboardLoadError, match="operator state changed"):
        load_dashboard_snapshot(
            _FIXTURE_BASE,
            _FIXTURE_NAMESPACE,
            state_loader=lambda _path: next(results),
            max_attempts=1,
            now=_TEST_NOW,
        )


def test_dashboard_reads_each_current_file_once_and_parses_verified_bytes(monkeypatch):
    state = _fixture_state()
    current_paths = {
        (_FIXTURE_BASE / _FIXTURE_NAMESPACE / entry["path"]).resolve()
        for entry in state["artifacts"].values()
        if entry["status"] == "current"
        and entry.get("fingerprint_kind") in {"file_bytes", "jsonl_lines"}
    }
    read_counts = {path: 0 for path in current_paths}
    original = dashboard_loader.AnchoredNamespaceReader.read_bytes

    def counted(reader, relative):
        resolved = (reader.namespace_dir / relative).resolve()
        if resolved in read_counts:
            read_counts[resolved] += 1
        return original(reader, relative)

    monkeypatch.setattr(dashboard_loader.AnchoredNamespaceReader, "read_bytes", counted)
    snapshot = _snapshot()

    assert snapshot.generation_authoritative is True
    assert read_counts == {path: 1 for path in current_paths}


def test_dashboard_file_swap_after_read_cannot_change_the_parsed_calendar(tmp_path, monkeypatch):
    target = _copy_namespace(tmp_path)
    calendar_path = target / "event_unified_calendar_events.jsonl"
    original = dashboard_loader.AnchoredNamespaceReader.read_bytes
    calendar_reads = 0

    def swap_after_read(reader, relative):
        nonlocal calendar_reads
        data, error = original(reader, relative)
        path = reader.namespace_dir / relative
        if path == calendar_path:
            calendar_reads += 1
            if calendar_reads == 1 and data is not None:
                calendar_path.write_bytes(data + b'\n{"title":"SWAPPED CONTENT"}\n')
        return data, error

    monkeypatch.setattr(
        dashboard_loader.AnchoredNamespaceReader,
        "read_bytes",
        swap_after_read,
    )
    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert calendar_reads == 1
    assert snapshot.generation_authoritative is True
    assert "SWAPPED CONTENT" not in json.dumps(snapshot.current_calendar_events)
    assert "Expected regulatory decision window" in json.dumps(snapshot.current_calendar_events)


def test_dashboard_rejects_namespace_directory_swap_mid_load(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    target = _copy_namespace(base)
    outside = tmp_path / "outside"
    shutil.copytree(_FIXTURE_BASE / _FIXTURE_NAMESPACE, outside)
    state = _read_state(target)
    outside_core = outside / state["artifacts"]["core_opportunities"]["path"]
    outside_core.write_text(
        outside_core.read_text(encoding="utf-8").replace(
            '"symbol":"ALPHA"',
            '"symbol":"EXTERNAL_ONLY"',
            1,
        ),
        encoding="utf-8",
    )
    _refresh_fingerprint(outside, state, "core_opportunities")
    _write_state(target, state)
    _write_state(outside, state)
    held = base / "held-current"
    real_loader = dashboard_loader._load_dashboard_operator_state
    calls = 0

    def swap_after_first_state_read(path):
        nonlocal calls
        result = real_loader(path)
        calls += 1
        if calls == 1:
            target.rename(held)
            target.symlink_to(outside, target_is_directory=True)
        return result

    with pytest.raises(DashboardLoadError, match="namespace changed or is unsafe"):
        load_dashboard_snapshot(
            base,
            "current",
            state_loader=swap_after_first_state_read,
            max_attempts=1,
            now=_TEST_NOW,
        )
    assert calls == 1


def test_dashboard_missing_fingerprint_is_untrusted_health_only(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    state["artifacts"]["core_opportunities"].pop("size_bytes")
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert snapshot.current_candidates == ()
    assert "core_opportunities:fingerprint_metadata_missing:size_bytes" in (
        snapshot.generation_authority_reasons
    )
    health = render_dashboard_page(snapshot, "/health")
    today = render_dashboard_page(snapshot, "/")
    detail = render_dashboard_page(snapshot, "/candidate/core:alpha")
    assert health.status_code == 200
    assert "UNTRUSTED CURRENT GENERATION" in health.body
    assert "Fresh high-liquidity breakout" not in today.body
    assert detail.status_code == 409
    assert "Fresh high-liquidity breakout" not in detail.body


def test_dashboard_smoke_fails_when_generation_is_not_authoritative(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    state["artifacts"]["core_opportunities"].pop("sha256")
    _write_state(target, state)

    with pytest.raises(SystemExit, match="generation is not authoritative"):
        _smoke(tmp_path, "current", now=_TEST_NOW)


def test_dashboard_rejects_manifest_symlink_without_parsing_referent(tmp_path):
    target = _copy_namespace(tmp_path)
    calendar_path = target / "event_unified_calendar_events.jsonl"
    referent = target / "calendar-referent.jsonl"
    calendar_path.rename(referent)
    calendar_path.symlink_to(referent.name)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert snapshot.current_calendar_events == ()
    assert "unified_calendar:artifact_symlink_not_allowed" in snapshot.generation_authority_reasons


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    (
        ("manifest", "manifest:not_complete"),
        ("authoritative", "doctor:not_authoritative"),
        ("strict", "doctor:not_strict"),
        ("schema_only", "doctor:schema_only_or_missing"),
        ("api_checks", "doctor:api_checks_skipped_or_missing"),
        ("run_id", "doctor:run_id_mismatch"),
        ("revision", "doctor:revision_mismatch"),
        ("revision_string", "doctor:revision_mismatch"),
        ("status", "doctor:status_not_authoritative"),
        ("status_lowercase", "doctor:status_not_authoritative"),
        ("blockers", "doctor:blockers_present"),
        ("blocker_string", "doctor:blocker_count_invalid"),
        ("blockers_malformed", "doctor:blockers_invalid"),
        ("warning_string", "doctor:warning_count_invalid"),
        ("warning_bool", "doctor:warning_count_invalid"),
        ("warning_negative", "doctor:warning_count_invalid"),
        ("doctor_stale", "doctor:stale"),
        ("generation_stale", "generation:stale"),
    ),
)
def test_dashboard_authority_requires_complete_fresh_full_strict_doctor(case, expected_reason):
    state = _fixture_state()
    doctor = state["doctor"]
    if case == "manifest":
        state["manifest_status"] = "partial"
    elif case == "authoritative":
        doctor["authoritative"] = False
    elif case == "strict":
        doctor["strict"] = False
    elif case == "schema_only":
        doctor["schema_only"] = True
    elif case == "api_checks":
        doctor["skip_api_checks"] = True
    elif case == "run_id":
        doctor["run_id"] = "different-run"
    elif case == "revision":
        doctor["verified_revision"] = 8
    elif case == "revision_string":
        doctor["verified_revision"] = "7"
    elif case == "status":
        doctor["status"] = "BLOCKED"
    elif case == "status_lowercase":
        doctor["status"] = "ok"
    elif case == "blockers":
        doctor["blocker_count"] = 1
        doctor["blockers"] = ["fixture blocker"]
    elif case == "blocker_string":
        doctor["blocker_count"] = "0"
    elif case == "blockers_malformed":
        doctor["blockers"] = {"unexpected": "mapping"}
    elif case == "warning_string":
        doctor["warning_count"] = "0"
    elif case == "warning_bool":
        doctor["warning_count"] = True
    elif case == "warning_negative":
        doctor["warning_count"] = -1
    elif case == "doctor_stale":
        doctor["verified_at"] = "2026-07-11T00:00:00+00:00"
    elif case == "generation_stale":
        state["run_started_at"] = "2026-07-11T00:00:00+00:00"

    snapshot = _snapshot_from_state(state)

    assert snapshot.generation_authoritative is False
    assert expected_reason in snapshot.generation_authority_reasons
    assert render_dashboard_page(snapshot, "/health").status_code == 200
    assert "Fresh high-liquidity breakout" not in render_dashboard_page(snapshot, "/").body


def test_dashboard_accepts_fresh_warn_doctor_with_zero_blockers():
    state = _fixture_state()
    state["doctor"]["status"] = "WARN"
    state["doctor"]["warning_count"] = 1

    snapshot = _snapshot_from_state(state)

    assert snapshot.generation_authoritative is True


@pytest.mark.parametrize("value", (float("nan"), float("inf")))
@pytest.mark.parametrize("limit_name", ("max_generation_age_hours", "max_doctor_age_hours"))
def test_dashboard_rejects_nonfinite_authority_age_limits(value, limit_name):
    with pytest.raises(DashboardLoadError, match="age limit is invalid"):
        load_dashboard_snapshot(
            _FIXTURE_BASE,
            _FIXTURE_NAMESPACE,
            now=_TEST_NOW,
            **{limit_name: value},
        )


def test_dashboard_cannot_refresh_an_ancient_generation_with_doctor_updated_at():
    state = _fixture_state()
    state["run_started_at"] = "2026-07-10T00:00:00+00:00"
    state["generated_at"] = "2026-07-10T00:01:00+00:00"
    state["updated_at"] = "2026-07-12T06:02:30+00:00"
    state["doctor"]["verified_at"] = "2026-07-12T06:02:30+00:00"

    snapshot = _snapshot_from_state(state)

    assert snapshot.generation_authoritative is False
    assert "generation:stale" in snapshot.generation_authority_reasons


def test_dashboard_requires_complete_known_manifest_structure():
    state = _fixture_state()
    state["artifacts"] = {
        "daily_brief": copy.deepcopy(state["artifacts"]["daily_brief"]),
    }
    state["manifest_status"] = "complete"

    snapshot = _snapshot_from_state(state)

    assert snapshot.generation_authoritative is False
    assert "manifest:missing_artifact_entry:core_opportunities" in (
        snapshot.generation_authority_reasons
    )


def test_dashboard_recomputes_manifest_status_from_entry_statuses():
    state = _fixture_state()
    state["artifacts"]["daily_brief"]["status"] = "pending"
    state["artifacts"]["daily_brief"]["reason"] = "still building"
    state["manifest_status"] = "complete"

    snapshot = _snapshot_from_state(state)

    assert snapshot.generation_authoritative is False
    assert "manifest:status_mismatch" in snapshot.generation_authority_reasons


def test_dashboard_fail_soft_cumulative_corruption_is_labeled(tmp_path):
    target = _copy_namespace(tmp_path)
    (target / "event_alpha_feedback.jsonl").write_text('{"broken":\n', encoding="utf-8")

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is True
    assert snapshot.cumulative_feedback == ()
    metadata = snapshot.cumulative_history_metadata["event_alpha_feedback.jsonl"]
    assert metadata["error"] == "invalid_jsonl:1"
    page = render_dashboard_page(snapshot, "/feedback-outcomes")
    assert page.status_code == 200
    assert "Cumulative artifact reads (non-authoritative)" in page.body
    assert "invalid_jsonl:1" in page.body


def test_dashboard_fail_soft_provider_health_is_separate_from_exact_readiness(tmp_path):
    target = _copy_namespace(tmp_path)
    (target / "event_provider_health.json").write_text("{broken", encoding="utf-8")

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is True
    assert snapshot.provider_readiness
    assert snapshot.provider_health == {}
    assert snapshot.provider_health_error == "invalid_json"
    page = render_dashboard_page(snapshot, "/health")
    assert "Exact-generation provider readiness" in page.body
    assert "Cumulative provider health (non-authoritative)" in page.body
    assert "invalid_json" in page.body


def test_dashboard_provider_rows_render_activation_preflight_health_and_live_fields():
    snapshot = replace(
        _snapshot(),
        provider_readiness={
            "providers": [
                {
                    "provider": "cryptopanic",
                    "configured": True,
                    "live_call_allowed": False,
                    "activation_phase": "config_ready_no_live",
                    "preflight_status": "disabled",
                    "latest_provider_health_status": "not_observed",
                    "latest_rehearsal_status": "not_run",
                }
            ]
        },
        provider_health={
            "providers": {
                "coingecko": {
                    "last_success_at": "2026-07-12T06:00:00+00:00",
                    "request_http_status": 200,
                    "result_count": 80,
                    "consecutive_failures": 0,
                }
            }
        },
    )

    page = render_dashboard_page(snapshot, "/health")

    assert "config_ready_no_live" in page.body
    assert "configured=true" in page.body
    assert "live_call_allowed=false" in page.body
    assert "preflight=disabled" in page.body
    assert "latest_health=not_observed" in page.body
    assert "observed_healthy" in page.body
    assert "HTTP=200" in page.body
    assert "result_count=80" in page.body


def test_dashboard_reads_shared_campaign_outcomes_separately_and_non_authoritatively(tmp_path):
    _copy_namespace(tmp_path)
    history_dir = tmp_path / "radar_market_history_cache"
    history_dir.mkdir()
    ledger = history_dir / "event_decision_radar_campaign_outcomes.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "core_opportunity_id": "agg:dexe",
                "symbol": "DEXE",
                "outcome_status": "pending",
                "radar_route": "diagnostic",
                "confidence_band": "diagnostic",
                "artifact_namespace": "radar_market_no_send_previous",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    page = render_dashboard_page(snapshot, "/feedback-outcomes")

    assert snapshot.generation_authoritative is True
    assert len(snapshot.campaign_outcomes) == 1
    assert len(snapshot.cumulative_outcomes) == 2
    assert "Namespace-local outcome rows (2)" in page.body
    assert "Decision campaign outcomes (1, shared / non-authoritative)" in page.body
    assert "DEXE" in page.body
    assert "radar_market_no_send_previous" in page.body
    metadata = snapshot.cumulative_history_metadata[
        "radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl"
    ]
    assert metadata["authority"] == "shared_campaign_non_authoritative"


def test_dashboard_shared_campaign_outcome_parent_symlink_is_fail_soft(tmp_path):
    _copy_namespace(tmp_path)
    outside = tmp_path / "outside-history"
    outside.mkdir()
    (outside / "event_decision_radar_campaign_outcomes.jsonl").write_text(
        '{"symbol":"OUTSIDE"}\n',
        encoding="utf-8",
    )
    (tmp_path / "radar_market_history_cache").symlink_to(outside, target_is_directory=True)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    page = render_dashboard_page(snapshot, "/feedback-outcomes")

    assert snapshot.generation_authoritative is True
    assert snapshot.campaign_outcomes == ()
    assert "OUTSIDE" not in page.body
    metadata = snapshot.cumulative_history_metadata[
        "radar_market_history_cache/event_decision_radar_campaign_outcomes.jsonl"
    ]
    assert metadata["error"] == "artifact_symlink_not_allowed"


@pytest.mark.parametrize(
    ("artifact_name", "payload", "page_path"),
    (
        (
            "event_alpha_feedback.jsonl",
            '{"core_opportunity_id":"OUTSIDE","label":"outside"}\n',
            "/feedback-outcomes",
        ),
        (
            "event_integrated_radar_outcomes.jsonl",
            '{"core_opportunity_id":"OUTSIDE","outcome_status":"outside"}\n',
            "/feedback-outcomes",
        ),
        (
            "event_alpha_outcomes.jsonl",
            '{"core_opportunity_id":"OUTSIDE","outcome_status":"outside"}\n',
            "/feedback-outcomes",
        ),
        (
            "event_provider_health.json",
            '{"providers":{"OUTSIDE":{"status":"outside"}}}\n',
            "/health",
        ),
    ),
)
def test_dashboard_cumulative_fixed_paths_reject_symlinks(
    tmp_path,
    artifact_name,
    payload,
    page_path,
):
    target = _copy_namespace(tmp_path)
    outside = tmp_path / f"outside-{artifact_name}"
    outside.write_text(payload, encoding="utf-8")
    linked = target / artifact_name
    linked.unlink(missing_ok=True)
    linked.symlink_to(outside)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    page = render_dashboard_page(snapshot, page_path)

    assert snapshot.generation_authoritative is True
    assert "OUTSIDE" not in page.body
    if artifact_name == "event_provider_health.json":
        assert snapshot.provider_health == {}
        assert snapshot.provider_health_error == "artifact_unreadable_or_symlink"
    else:
        assert snapshot.cumulative_history_metadata[artifact_name]["error"] == (
            "artifact_unreadable_or_symlink"
        )


def test_dashboard_exact_provider_readiness_requires_generation_lineage(tmp_path):
    target = _copy_namespace(tmp_path)
    readiness_path = target / "event_live_provider_activation_readiness.json"
    readiness = json.loads(readiness_path.read_text())
    readiness["profile"] = "wrong-profile"
    readiness_path.write_text(json.dumps(readiness, sort_keys=True) + "\n", encoding="utf-8")
    state = _read_state(target)
    _refresh_fingerprint(target, state, "provider_readiness_json")
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert snapshot.provider_readiness == {}
    assert "provider_readiness_json:profile_mismatch" in snapshot.generation_authority_reasons


def test_dashboard_labels_fixture_parser_coverage_as_fixture_only():
    from crypto_rsi_scanner.event_alpha.dashboard.system_pages import _provider_assessment

    label, tone, detail = _provider_assessment(
        {
            "provider_name": "defillama_tvl_fees_revenue",
            "configured": False,
            "configuration_scope": "fixture_input_only",
            "fixture_input_configured": True,
            "fixture_parser_status": "pass",
            "live_transport_status": "not_implemented",
            "live_authorization_status": "not_defined",
            "live_mapping_status": "missing_real_registry",
            "live_rehearsal_eligible": False,
            "live_call_allowed": False,
        }
    )

    assert label == "Fixture only"
    assert tone == "muted"
    assert "no live provider transport" in detail
    assert "Missing real registry" in detail


def test_dashboard_verifies_one_exact_canonical_run_ledger_row(tmp_path):
    target = _copy_namespace(tmp_path)
    state = _read_state(target)
    identity = {
        "run_id": state["run_id"],
        "profile": state["profile"],
        "artifact_namespace": state["artifact_namespace"],
    }
    run_row = {**identity, "run_started_at": state["run_started_at"], "research_only": True}
    ledger_path = target / "event_alpha_runs.jsonl"
    ledger_path.write_text(json.dumps(run_row, sort_keys=True) + "\n", encoding="utf-8")
    entry = state["artifacts"]["run_ledger"]
    entry.update(
        {
            "status": "current",
            "path": ledger_path.name,
            "reason": None,
            "run_row_identity": identity,
            "run_row_match_count": 1,
            **fingerprints.canonical_run_row_fingerprint(run_row),
        }
    )
    _write_state(target, state)

    authoritative = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_row, sort_keys=True) + "\n")
    duplicate = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert authoritative.generation_authoritative is True
    assert duplicate.generation_authoritative is False
    assert "run_ledger:run_row_match_count_mismatch:2" in duplicate.generation_authority_reasons


def test_dashboard_current_schema_failure_is_untrusted_and_suppressed(tmp_path):
    target = _copy_namespace(tmp_path)
    core_path = target / "event_core_opportunities.jsonl"
    rows = [json.loads(line) for line in core_path.read_text().splitlines() if line.strip()]
    current = next(row for row in rows if row.get("core_opportunity_id") == "core:alpha")
    current.pop("core_opportunity_id")
    core_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    state = _read_state(target)
    _refresh_fingerprint(target, state, "core_opportunities")
    _write_state(target, state)

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert snapshot.generation_authoritative is False
    assert "core_opportunities:schema_validation_failed" in snapshot.generation_authority_reasons
    assert "Fresh high-liquidity breakout" not in render_dashboard_page(snapshot, "/").body


@pytest.mark.parametrize("value", (True, "7"))
def test_dashboard_noninteger_revision_is_invalid(value):
    state = _fixture_state()
    state["revision"] = value

    with pytest.raises(DashboardLoadError, match="generation identity"):
        _snapshot_from_state(state)


@pytest.mark.parametrize("location", ("count", "count_string", "side_effect"))
def test_dashboard_bool_integer_metadata_fails_closed(location):
    state = _fixture_state()
    if location == "count":
        state["artifacts"]["core_opportunities"]["count"] = True
        expected = "artifact count is invalid"
    elif location == "count_string":
        state["artifacts"]["core_opportunities"]["count"] = "4"
        expected = "artifact count is invalid"
    else:
        state["trades_created"] = False
        expected = "safety counter is invalid"

    with pytest.raises(DashboardLoadError, match=expected):
        _snapshot_from_state(state)


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


def test_dashboard_server_serves_while_another_client_stalls():
    class ObservedRequestHandler(WSGIRequestHandler):
        entered = Event()

        def handle(self) -> None:
            self.entered.set()
            super().handle()

    fixture_hashes_before = _fixture_hashes()
    app = RadarDashboardApp(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    server = _make_dashboard_server(
        "127.0.0.1",
        0,
        app,
        handler_class=ObservedRequestHandler,
    )
    server_thread = Thread(target=server.serve_forever, daemon=True)
    stalled_client = None
    healthy_client = None
    try:
        server_thread.start()
        stalled_client = socket.create_connection(server.server_address, timeout=2.0)
        stalled_client.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n")
        assert ObservedRequestHandler.entered.wait(timeout=2.0)

        healthy_client = HTTPConnection(*server.server_address, timeout=2.0)
        healthy_client.request("GET", "/")
        response = healthy_client.getresponse()

        assert response.status == 200
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("X-Frame-Options") == "DENY"
        assert response.getheader("X-Robots-Tag") == "noindex, nofollow, noarchive"
        assert response.getheader("Referrer-Policy") == "no-referrer"
        assert response.getheader("Permissions-Policy") == (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        assert b"Crypto Radar" in response.read()
    finally:
        if healthy_client is not None:
            healthy_client.close()
        if stalled_client is not None:
            stalled_client.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
    assert _fixture_hashes() == fixture_hashes_before
