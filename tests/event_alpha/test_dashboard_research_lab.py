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
from crypto_rsi_scanner.event_alpha.operations import (
    empirical_hardening_supplement,
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


def _supplement_payload() -> bytes:
    reports = _report_payloads()
    payload = (
        _ROOT / "research" / empirical_hardening_supplement.SUPPLEMENT_FILENAME
    ).read_bytes()
    empirical_hardening_supplement.parse_and_validate_hardening_supplement(
        payload,
        report_payloads=reports,
    )
    return payload


def _write_supplement(root: Path) -> bytes:
    payload = _supplement_payload()
    (root / empirical_hardening_supplement.SUPPLEMENT_FILENAME).write_bytes(payload)
    return payload


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
        "267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf"
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


def test_hardening_supplement_uses_same_anchored_fixed_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    payload = _write_supplement(research)
    original_read = secure_reader.AnchoredNamespaceReader.read_bytes
    original_parse = (
        empirical_hardening_supplement.parse_and_validate_hardening_supplement
    )
    reads: list[tuple[int, str, int | None]] = []
    parsed: list[bytes] = []

    def observed_read(self, relative, *, max_bytes=None):
        reads.append((id(self), str(relative), max_bytes))
        return original_read(self, relative, max_bytes=max_bytes)

    def observed_parse(value, *, report_payloads):
        assert report_payloads == _report_payloads()
        parsed.append(value)
        return original_parse(value, report_payloads=report_payloads)

    monkeypatch.setattr(
        secure_reader.AnchoredNamespaceReader,
        "read_bytes",
        observed_read,
    )
    monkeypatch.setattr(
        empirical_hardening_supplement,
        "parse_and_validate_hardening_supplement",
        observed_parse,
    )

    lab = load_research_lab_snapshot(research)

    assert [row[1] for row in reads] == [
        *REPORT_FILENAMES,
        empirical_hardening_supplement.SUPPLEMENT_FILENAME,
    ]
    assert len({row[0] for row in reads}) == 1
    assert reads[-1][2] == empirical_hardening_supplement.MAX_SUPPLEMENT_BYTES
    assert parsed == [payload]
    assert lab["status"] == "ready"
    assert lab["bundle_status"] == "validated"
    assert tuple(lab["reports"]) == REPORT_FILENAMES
    assert len(lab["reports"]) == 7
    hardening = lab["hardening_supplement"]
    assert set(hardening) == {"status", "record", "projection", "warnings"}
    assert hardening["status"] == "ready"
    assert hardening["record"]["filename"] == (
        empirical_hardening_supplement.SUPPLEMENT_FILENAME
    )
    assert hardening["record"]["size_bytes"] == len(payload)
    assert hardening["record"]["maximum_size_bytes"] == (
        empirical_hardening_supplement.MAX_SUPPLEMENT_BYTES
    )
    assert hardening["projection"]["negative_conclusion"] is True
    assert hardening["projection"]["unsupported_shadow_alternative_count"] == 9
    route_conditioned = hardening["projection"]["route_conditioned_calibration"]
    assert tuple(route_conditioned["score_fields"]) == (
        "actionability_score",
        "evidence_confidence_score",
        "risk_score",
        "urgency_score",
        "chase_risk_score",
    )
    assert len(route_conditioned["rows"]) == 16
    assert [
        (
            row["partition"],
            row["route"],
            row["evaluated_pair_count"],
            row["violation_count"],
        )
        for row in route_conditioned["rows"]
        if row["route"] in {"dashboard_watch", "risk_watch"}
    ] == [
        ("development", "dashboard_watch", 0, 0),
        ("development", "risk_watch", 2, 1),
        ("validation", "dashboard_watch", 0, 0),
        ("validation", "risk_watch", 2, 1),
    ]
    market_wide = hardening["projection"]["market_wide_risk_diagnostics"]
    assert (
        market_wide["risk_item_count"],
        market_wide["partition_day_count"],
        market_wide["market_wide_group_count"],
    ) == (2412, 411, 130)
    assert market_wide["correlated_family_suppression_status"] == (
        "not_evaluable_missing_correlation_and_family_lineage"
    )
    assert market_wide["peak_group"] == {
        "utc_day": "2022-05-12",
        "risk_item_count": 94,
        "distinct_asset_count": 94,
        "partition": "development",
        "market_regime_status": "consistent",
        "top_assets": [
            "binance-usdt:luna",
            "binance-usdt:people",
            "binance-usdt:spell",
            "binance-usdt:alpine",
            "binance-usdt:astr",
            "binance-usdt:tlm",
            "binance-usdt:slp",
            "binance-usdt:gala",
            "binance-usdt:mask",
            "binance-usdt:rose",
        ],
    }
    frozen_costs = hardening["projection"]["frozen_cost_sensitivity"]
    assert tuple(frozen_costs["cost_bps"]) == (0, 20, 50, 100, 200)
    assert [
        (
            row["partition"],
            row["sealed_final_display_only"],
            [scenario["round_trip_cost_bps"] for scenario in row["scenarios"]],
        )
        for row in frozen_costs["partitions"]
    ] == [
        ("development", False, [0, 20, 50, 100, 200]),
        ("validation", False, [0, 20, 50, 100, 200]),
        ("final_test", True, [0, 20, 50, 100, 200]),
    ]
    assert {
        row["partition"]: [
            (
                scenario["round_trip_cost_bps"],
                scenario["mean_net_directional_return_fraction"],
                scenario["net_hit_rate"],
            )
            for scenario in row["scenarios"]
        ]
        for row in frozen_costs["partitions"]
    } == {
        "development": [
            (0, -0.000571035194965149, 0.5319622012229016),
            (20, -0.0025710351949651505, 0.5241801000555865),
            (50, -0.005571035194965151, 0.5169538632573653),
            (100, -0.010571035194965151, 0.49972206781545303),
            (200, -0.02057103519496515, 0.47192884936075596),
        ],
        "validation": [
            (0, -0.007347436929152366, 0.5294117647058824),
            (20, -0.009347436929152369, 0.5203619909502263),
            (50, -0.01234743692915237, 0.5090497737556561),
            (100, -0.017347436929152367, 0.4894419306184012),
            (200, -0.02734743692915237, 0.45324283559577677),
        ],
        "final_test": [
            (0, -0.004513142441460612, 0.5038650737877723),
            (20, -0.006513142441460613, 0.49402670414617006),
            (50, -0.009513142441460615, 0.48067463106113845),
            (100, -0.014513142441460614, 0.4680252986647927),
            (200, -0.024513142441460613, 0.43359100491918484),
        ],
    }
    snapshot_text = json.dumps(hardening, sort_keys=True)
    assert "route_conditioned_calibration" in snapshot_text
    assert "market_wide_risk_diagnostics" in snapshot_text
    assert "daily_risk_groups" not in snapshot_text
    assert "ranked_asset_evidence" not in snapshot_text
    assert "between_route_bucket_composition" not in snapshot_text
    assert "supplement_id" not in snapshot_text
    assert len(snapshot_text) < 24_000


@pytest.mark.parametrize(
    ("failure_mode", "expected_status"),
    (("missing", "missing"), ("invalid", "invalid"), ("oversized", "oversized")),
)
def test_hardening_supplement_failures_suppress_only_supplement_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
    expected_status: str,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    supplement_path = (
        research / empirical_hardening_supplement.SUPPLEMENT_FILENAME
    )
    if failure_mode == "invalid":
        supplement_path.write_bytes(b"{}")
    elif failure_mode == "oversized":
        monkeypatch.setattr(research_lab_loader, "MAX_SUPPLEMENT_BYTES", 32)
        supplement_path.write_bytes(_supplement_payload())

    lab = load_research_lab_snapshot(research)

    assert lab["status"] == "ready"
    assert lab["bundle_status"] == "validated"
    assert tuple(lab["reports"]) == REPORT_FILENAMES
    assert len(lab["reports"]) == 7
    assert lab["bundle"]["report_artifacts"] == REPORT_FILENAMES
    assert lab["projections"]["validation"]["analyses"]
    hardening = lab["hardening_supplement"]
    assert hardening["status"] == expected_status
    assert hardening["record"]["status"] == expected_status
    assert hardening["projection"] == {}
    assert hardening["warnings"] == (f"hardening_supplement_{expected_status}",)
    assert lab["warnings"] == ()

    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )
    page = render_dashboard_page(snapshot, "/research-lab")
    assert page.status_code == 200
    assert "Empirical hardening supplement" in page.body
    assert "Hardening supplement unavailable" in page.body
    assert "Seven file v1 evidence remains available" in page.body
    assert f"hardening_supplement_{expected_status}" in page.body
    assert "Final empirical verdict" in page.body
    assert "Closed route evidence" in page.body


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
    assert "8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489" in page.body
    assert "3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72" in page.body
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
    assert "immutable campaign snapshot bound into this empirical bundle" in page.body
    assert "not the current dashboard campaign" in page.body
    assert "1 fixed-start episode and 1 dependent repeat" in page.body
    assert "statistical independence is not claimed" in page.body
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


def test_hardening_operator_panel_leads_with_negative_conclusion(
    tmp_path: Path,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    _write_supplement(research)
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )

    page = render_dashboard_page(snapshot, "/research-lab")

    assert page.status_code == 200
    boundary_index = page.body.index("Research boundary")
    operator_index = page.body.index("Operator conclusion")
    overview_index = page.body.index("Research reports")
    identity_index = page.body.index("Validated evidence identity")
    sealed_index = page.body.index("Final empirical verdict")
    assert boundary_index < operator_index < overview_index < identity_index
    assert operator_index < sealed_index
    for text in (
        "No supported production policy change.",
        "9 unsupported shadow alternatives",
        "Risk watch",
        "Dashboard watch",
        "Descriptive results vary by regime",
        "Historical spread not observed",
        "10 descriptive violations",
        "91 items in one day",
        "Matured visible episodes</span><strong>1378",
        "Current policy mean</span><strong>-0.64%",
        "Current policy hit rate</span><strong>49.56%",
        "Quick-failure rate</span><strong>34.69%",
        "Routes with no empirical evidence",
        "Origins with no empirical evidence",
        "Missing data most needed",
        "Live evidence insufficient",
        "Insufficient for policy change",
        "Sealed v1 final-test summary only",
        "did not access raw final-test data",
        "did not use the holdout for scenario selection",
        "Within-route score diagnostics",
        "closed 16-route matrix",
        "older global mixed-route monotonicity result is confounded by route composition",
        "Dashboard-watch and risk-watch score detail",
        "Outcome-blind market-wide risk grouping",
        "Risk items</span><strong>2,412",
        "Partition-days</span><strong>411",
        "Market-wide groups</span><strong>130",
        "2022-05-12",
        "binance-usdt:luna",
        "binance-usdt:people",
        "binance-usdt:spell",
        "Correlated-family suppression is not evaluable",
        "correlation and family-lineage evidence are missing",
        "Exact frozen Protocol-v1 cost sensitivity",
        "0 / 20 / 50 / 100 / 200 bps",
        "Final test · sealed display only",
        "-0.06%",
        "53.20%",
        "-0.73%",
        "52.94%",
        "-0.45%",
        "50.39%",
        "Not execution evidence",
    ):
        assert text in page.body
    assert "Final empirical verdict" in page.body
    assert "No candidate recommendations" in page.body
    assert page.body.count("7/7") >= 1


def test_hardening_operator_panel_escapes_every_projected_value(
    tmp_path: Path,
) -> None:
    research = tmp_path / "research"
    _write_reports(research)
    _write_supplement(research)
    snapshot = load_dashboard_snapshot(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_NOW,
        research_root=research,
    )
    research_lab = deepcopy(dict(snapshot.research_lab))
    hardening = deepcopy(dict(research_lab["hardening_supplement"]))
    projection = deepcopy(dict(hardening["projection"]))
    projection["regime_dependence"] = '<script>alert("regime")</script>'
    projection["missing_data"] = ['<img src=x onerror="alert(1)">']
    projection["route_level_result"]["risk_watch"][
        "evidence_status"
    ] = '<svg onload="alert(2)">'
    projection["market_wide_risk_diagnostics"]["peak_group"][
        "top_assets"
    ][0] = '<a href="javascript:alert(3)">asset</a>'
    hardening["projection"] = projection
    research_lab["hardening_supplement"] = hardening

    page = render_dashboard_page(
        replace(snapshot, research_lab=research_lab),
        "/research-lab",
    )

    assert '<script>alert("regime")</script>' not in page.body
    assert '<img src=x onerror="alert(1)">' not in page.body
    assert '<svg onload="alert(2)">' not in page.body
    assert '<a href="javascript:alert(3)">asset</a>' not in page.body
    assert "&lt;script&gt;alert(&quot;regime&quot;)&lt;/script&gt;" in page.body
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in page.body
    assert "&lt;svg onload=&quot;alert(2)&quot;&gt;" in page.body
    assert (
        "&lt;a href=&quot;javascript:alert(3)&quot;&gt;asset&lt;/a&gt;"
        in page.body
    )


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
    _write_supplement(research)
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
    assert b"No supported production policy change" in get_body
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
