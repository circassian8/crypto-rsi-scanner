from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.dashboard import research_lab_loader
from crypto_rsi_scanner.event_alpha.dashboard import secure_reader
from crypto_rsi_scanner.event_alpha.dashboard.app import RadarDashboardApp
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page
from crypto_rsi_scanner.event_alpha.dashboard.research_lab_loader import (
    ORIGINS,
    ROUTES,
    load_research_lab_snapshot,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_research_reports import (
    REPORT_FILENAMES,
    validate_report_bundle,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_store import (
    canonical_json_bytes,
)


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"
_NOW = "2026-07-12T06:03:00+00:00"


def _report_payloads() -> dict[str, bytes]:
    payloads = {
        name: (_ROOT / "research" / name).read_bytes()
        for name in REPORT_FILENAMES
    }
    validate_report_bundle(payloads)
    return payloads


def _write_reports(root: Path) -> None:
    root.mkdir()
    _restore_reports(root)


def _restore_reports(root: Path) -> None:
    for name, payload in _report_payloads().items():
        (root / name).write_bytes(payload)


def _request(app: RadarDashboardApp, path: str, *, method: str = "GET") -> tuple[str, bytes]:
    observed: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        observed["status"] = status
        observed["headers"] = dict(headers)

    payload = b"".join(app({"REQUEST_METHOD": method, "PATH_INFO": path}, start_response))
    return str(observed["status"]), payload


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink()
    }


def test_research_lab_loads_only_fixed_bounded_reports(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    (research / "DO_NOT_READ.secret").write_text("credential-shaped material")

    lab = load_research_lab_snapshot(research)

    assert lab["status"] == "ready"
    assert lab["bundle_status"] == "validated"
    assert tuple(lab["reports"]) == REPORT_FILENAMES
    assert lab["bundle"]["report_artifacts"] == REPORT_FILENAMES
    assert lab["bundle"]["bundle_id"] == (
        "75d50598fd03a07433caa6ef29c4f7f9f24b17408fbf433dbc34b373c07d89fa"
    )
    validation = lab["projections"]["validation"]
    assert tuple(row["partition"] for row in validation["analyses"]) == (
        "development",
        "validation",
        "final_test",
    )
    for analysis in validation["analyses"]:
        assert tuple(row["cohort"] for row in analysis["route_cohorts"]) == ROUTES
        assert tuple(row["cohort"] for row in analysis["primary_origin_cohorts"]) == ORIGINS
    assert lab["projections"]["live"]["evidence_mode"] == "live_no_send"
    assert lab["projections"]["live"]["replay_evidence_aggregated"] is False
    assert "DO_NOT_READ.secret" not in json.dumps(lab)
    assert lab["provider_calls"] == lab["writes"] == 0
    assert lab["dashboard_authority_mutations"] == 0


def test_research_lab_missing_and_unsafe_reports_fail_soft(tmp_path: Path) -> None:
    research = tmp_path / "research"
    research.mkdir()
    empty = load_research_lab_snapshot(research)
    assert empty["status"] == "unavailable"
    assert empty["bundle_status"] == "incomplete"
    assert empty["projections"] == {}

    research.rmdir()
    _write_reports(research)

    target = tmp_path / "target.json"
    target.write_text("{}")
    validation_report = REPORT_FILENAMES[1]
    (research / validation_report).unlink()
    (research / validation_report).symlink_to(target)
    lab = load_research_lab_snapshot(research)
    assert lab["bundle_status"] == "incomplete"
    assert lab["reports"][validation_report]["status"] == "unsafe_or_unreadable"
    assert lab["projections"] == {}

    (research / validation_report).unlink()
    (research / validation_report).write_text('{"schema_id":"a","schema_id":"b"}')
    lab = load_research_lab_snapshot(research)
    assert lab["bundle_status"] == "invalid"
    assert lab["projections"] == {}


def test_research_lab_rejects_oversized_buffer_before_parsing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    validation_report = REPORT_FILENAMES[1]
    monkeypatch.setitem(research_lab_loader._REPORT_FILES, validation_report, 32)

    lab = load_research_lab_snapshot(research)

    assert lab["bundle_status"] == "incomplete"
    assert lab["reports"][validation_report]["status"] == "oversized"
    assert lab["reports"][validation_report]["sha256"] is None
    assert lab["projections"] == {}


@pytest.mark.parametrize("failure_mode", ("missing", "markdown_drift", "spliced_json"))
def test_research_lab_suppresses_the_whole_bundle_on_contract_drift(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    if failure_mode == "missing":
        (research / REPORT_FILENAMES[0]).unlink()
        expected_status = "incomplete"
    elif failure_mode == "markdown_drift":
        path = research / REPORT_FILENAMES[0]
        path.write_bytes(path.read_bytes() + b"tampered\n")
        expected_status = "invalid"
    else:
        path = research / REPORT_FILENAMES[5]
        value = json.loads(path.read_bytes())
        value["bundle"]["bundle_id"] = "0" * 64
        path.write_bytes(canonical_json_bytes(value))
        expected_status = "invalid"

    lab = load_research_lab_snapshot(research)

    assert lab["bundle_status"] == expected_status
    assert lab["projections"] == {}
    assert lab["bundle"] == {}


def test_research_lab_fails_closed_if_research_root_is_replaced(
    tmp_path: Path,
    monkeypatch,
) -> None:
    research = tmp_path / "research"
    replacement = tmp_path / "replacement"
    displaced = tmp_path / "displaced"
    _write_reports(research)
    _write_reports(replacement)
    original = secure_reader.AnchoredNamespaceReader.read_bytes
    read_count = 0

    def swap_after_first_read(self, relative, *, max_bytes=None):
        nonlocal read_count
        result = original(self, relative, max_bytes=max_bytes)
        read_count += 1
        if read_count == 1:
            os.rename(research, displaced)
            os.rename(replacement, research)
        return result

    monkeypatch.setattr(
        secure_reader.AnchoredNamespaceReader,
        "read_bytes",
        swap_after_first_read,
    )

    lab = load_research_lab_snapshot(research)

    assert lab["status"] == "unavailable"
    assert lab["bundle_status"] == "unavailable"
    assert lab["projections"] == {}
    assert "research_root_unavailable_or_unsafe" in lab["warnings"]


def test_research_lab_render_is_explicit_descriptive_and_escaped(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    (research / "DO_NOT_READ.secret").write_text(
        '<script>alert("x")</script>', encoding="utf-8"
    )
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )

    page = render_dashboard_page(snapshot, "/research-lab")

    assert page.status_code == 200
    assert "Decision Radar Research Lab" in page.body
    assert '<a href="/research-lab" aria-current="page">Research Lab</a>' in page.body
    assert "Read state" in page.body
    for heading in (
        "Closed route evidence",
        "Closed origin evidence",
        "Score monotonicity",
        "Regimes, liquidity &amp; data quality",
        "Market vs catalyst",
        "Missed moves &amp; false/late symptoms",
        "MFE, MAE &amp; assumed costs",
        "Chronological walk-forward",
        "Shadow policy &amp; operator burden",
        "Live no-send vs replay",
        "Warnings &amp; limitations",
    ):
        assert heading in page.body
    assert "High-confidence idea" in page.body
    assert "Macro-led" in page.body
    assert "Production policy unchanged" in page.body
    assert ">None<" not in page.body
    assert ">nan<" not in page.body
    assert ">null<" not in page.body
    assert "Shadow recommendations do not auto-apply" in page.body
    assert "Live no-send" in page.body
    assert "Insufficient sample" in page.body
    assert "7/7" in page.body
    assert "No candidate recommendations" in page.body
    assert "Final empirical verdict" in page.body
    assert "e906229597af15c6dc3caf3cb37a1846b5d273776c8477bc4637453a78ab7cec" in page.body
    assert "c4361588a7bc6165bf780e7dcd90ba81625be3fb5da711080a0f8c4cbf168933" in page.body
    assert "No evidence" in page.body
    assert "Not evaluable" in page.body
    assert "Fewer than two populated score buckets" in page.body
    assert "-12.96%" in page.body
    assert "MAE is a signed direction-adjusted adverse excursion" in page.body
    assert "Costs are assumed sensitivity, not execution evidence" in page.body
    assert "Route survivability" in page.body
    assert "Outcome leakage controls" in page.body
    assert "Zero-idea days" in page.body
    assert "Live no-send evidence is a separate observational lane" in page.body
    assert "Historical spread" in page.body
    assert "not observed" in page.body.casefold()
    assert "Failed quickly symptom" in page.body
    assert "Late pre-signal symptom" in page.body
    assert "Rows summarized" in page.body
    assert 'data-label="Urgent">1455</td><td data-label="Repeated family">171</td>' in page.body
    assert 'data-label="Urgent">957</td><td data-label="Repeated family">125</td>' in page.body
    assert 'data-label="Urgent">1149</td><td data-label="Repeated family">87</td>' in page.body
    assert "<script>alert" not in page.body
    assert "&lt;script&gt;alert" not in page.body
    assert "<form" not in page.body

    untrusted = replace(
        snapshot,
        generation_authority_status="untrusted",
        generation_authority_reasons=("generation:stale",),
    )
    historical_page = render_dashboard_page(untrusted, "/research-lab")
    assert historical_page.status_code == 200
    assert "Decision Radar Research Lab" in historical_page.body
    assert "Evidence here is descriptive and remains outside dashboard authority" in historical_page.body
    assert "Historical research · current authority unavailable" in historical_page.body


def test_research_lab_hides_absent_live_projection_and_renders_future_sealed_status(
    tmp_path: Path,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )
    lab = deepcopy(dict(snapshot.research_lab))
    projections = deepcopy(dict(lab["projections"]))
    projections["live"] = {
        "available": False,
        "binding": {"status": "not_configured"},
    }
    lab["projections"] = projections

    no_live_page = render_dashboard_page(
        replace(snapshot, research_lab=lab),
        "/research-lab",
    )

    assert (
        '<span class="status-badge status-badge--info"><span class="status-badge__icon '
        'status-badge__icon--data" aria-hidden="true">◆</span>Live no-send</span>'
        not in no_live_page.body
    )
    assert '<th scope="row" data-label="Evidence mode">Live no-send</th>' not in no_live_page.body

    future_lab = deepcopy(lab)
    conclusions = future_lab["projections"]["validation"]["conclusions"]
    conclusions["final_confirmation_status"] = "confirmed_candidates"
    conclusions["confirmed_candidate_count"] = 1
    future_page = render_dashboard_page(
        replace(snapshot, research_lab=future_lab),
        "/research-lab",
    )

    assert "Sealed evaluation result" in future_page.body
    assert "is the sealed final-test result for the preselected candidate set" in future_page.body
    assert "<strong>No candidate recommendations</strong>" not in future_page.body


def test_research_lab_invalid_bundle_renders_inventory_only(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    path = research / REPORT_FILENAMES[6]
    path.write_bytes(path.read_bytes() + b"tampered\n")
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )

    page = render_dashboard_page(snapshot, "/research-lab")

    assert page.status_code == 200
    assert "Research evidence inventory" in page.body
    assert page.body.count(">Readable</span>") == len(REPORT_FILENAMES)
    assert "Bundle validation failed closed" in page.body
    assert "Semantic evidence suppressed" in page.body
    assert "Closed route evidence" not in page.body
    assert "Final empirical verdict" not in page.body


def test_research_lab_renderer_escapes_validated_projection_text(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )
    research_lab = deepcopy(dict(snapshot.research_lab))
    projections = deepcopy(research_lab["projections"])
    validation = deepcopy(projections["validation"])
    conclusions = deepcopy(validation["conclusions"])
    conclusions["additional_data_most_needed"] = ['<script>alert("x")</script>']
    validation["conclusions"] = conclusions
    projections["validation"] = validation
    research_lab["projections"] = projections

    page = render_dashboard_page(
        replace(snapshot, research_lab=research_lab),
        "/research-lab",
    )

    assert "<script>alert" not in page.body
    assert "&lt;script&gt;alert" in page.body


def test_research_lab_get_head_are_read_only_and_do_not_change_authority(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    before = _hashes(research)
    app = RadarDashboardApp(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )

    get_status, get_body = _request(app, "/research-lab")
    head_status, head_body = _request(app, "/research-lab", method="HEAD")
    post_status, post_body = _request(app, "/research-lab", method="POST")

    assert get_status == "200 OK"
    assert b"Decision Radar Research Lab" in get_body
    assert head_status == "200 OK" and head_body == b""
    assert post_status == "405 Method Not Allowed"
    assert post_body == b"Method Not Allowed\n"
    assert _hashes(research) == before
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )
    assert snapshot.generation_authoritative is True
    assert snapshot.research_lab["dashboard_authority_mutations"] == 0
