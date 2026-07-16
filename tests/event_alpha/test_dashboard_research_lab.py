from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.dashboard import research_lab_loader
from crypto_rsi_scanner.event_alpha.dashboard.app import RadarDashboardApp
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page
from crypto_rsi_scanner.event_alpha.dashboard.research_lab_loader import (
    LIVE_CAMPAIGN_REPORT,
    ORIGINS,
    POLICY_REPORT,
    ROUTES,
    VALIDATION_REPORT,
    WALK_FORWARD_REPORT,
    load_research_lab_snapshot,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_policy_lab import (
    simulate_shadow_policies,
    walk_forward_evaluation,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_analysis import (
    build_empirical_replay_analysis,
)


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"
_NOW = "2026-07-12T06:03:00+00:00"


def _live_campaign_report() -> dict[str, object]:
    return {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "generated_at": "2026-07-16T03:00:00Z",
        "campaign_status": "in_progress_baseline_warming",
        "campaign_metrics": {
            "real_cycles": 8,
            "real_observations": 240,
            "historical_ideas": 2,
            "route_counts": {"risk_watch": 2},
        },
        "shadow_anomaly_episodes": {
            "status": "ready",
            "method": "fixed_start_window_declustering",
            "primary_episode_count": 2,
            "primary_repeat_member_count": 1,
            "sensitivity_counts": {},
        },
        "outcomes": {"total": 2, "matured": 1, "pending": 1, "due_missing_price": 0},
        "decision_v2_episode_outcome_scorecard": {
            "status": "ready",
            "primary_episode_count": 2,
            "matured_episode_count": 1,
            "scoreable_directional_episode_count": 1,
            "representative_count": 0,
            "policy_conclusion": "insufficient_for_policy_change",
            "policy_conclusion_reasons": ["matched_non_idea_controls_unavailable"],
            "matched_control_available": False,
            "out_of_sample_validation_available": False,
            "representatives": [],
        },
        "data_quality_limitations": [
            {"category": "spread", "detail": "Historical spread is unavailable."}
        ],
        "safety": {
            "research_only": True,
            "automatic_route_changes": False,
            "automatic_threshold_changes": False,
            "normal_rsi_signal_rows_written": 0,
            "paper_trades_created": 0,
            "provider_authorization_modified": False,
            "provider_calls_made_by_report": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "triggered_fade_created": 0,
        },
    }


def _write_reports(root: Path, *, malicious: str = "") -> None:
    root.mkdir()
    analysis = build_empirical_replay_analysis(
        [],
        partition="fixture",
        evidence_mode="fixture_replay",
    )
    validation = {
        "schema_id": "decision_radar.empirical_validation_report",
        "schema_version": 1,
        "generated_at": "2026-07-16T03:00:00Z",
        "status": "descriptive_only",
        "empirical_analysis": analysis,
        "replay_summary": {"episode_count": 0},
        "controls_and_benchmarks": {"matched_controls": "unavailable"},
        "live_campaign": {"aggregated_with_replay": False},
        "final_test_confirmation": {"accessed_for_selection": False},
        "conclusions": ["Insufficient sample for policy change."],
        "limitations": [{"category": "sample", "detail": malicious or "No matured episodes."}],
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
    }
    walk = walk_forward_evaluation([], [])
    simulation = simulate_shadow_policies(
        [],
        [],
        partitions=("development", "validation"),
    )
    policy = {
        "schema_id": "decision_radar.empirical_policy_report",
        "schema_version": 1,
        "status": "shadow_only",
        "selection_simulation": simulation,
        "recommendation_seal": {},
        "final_test_confirmation": {},
        "recommendations": simulation["recommendations"],
        "research_only": True,
        "auto_apply": False,
        "production_policy_mutations": 0,
    }
    for name, value in (
        (VALIDATION_REPORT, validation),
        (WALK_FORWARD_REPORT, walk),
        (POLICY_REPORT, policy),
        (LIVE_CAMPAIGN_REPORT, _live_campaign_report()),
    ):
        (root / name).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


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
    assert set(lab["reports"]) == {"validation", "walk_forward", "policy", "live_campaign"}
    validation = lab["reports"]["validation"]["projection"]
    route_rows = validation["analyses"][0]["route_cohorts"]
    origin_rows = validation["analyses"][0]["primary_origin_cohorts"]
    assert tuple(row["cohort"] for row in route_rows) == ROUTES
    assert tuple(row["cohort"] for row in origin_rows) == ORIGINS
    assert all(row["episode_count"] == 0 for row in route_rows + origin_rows)
    assert "DO_NOT_READ.secret" not in json.dumps(lab)
    assert lab["provider_calls"] == lab["writes"] == 0
    assert lab["dashboard_authority_mutations"] == 0


def test_research_lab_missing_and_unsafe_reports_fail_soft(tmp_path: Path) -> None:
    research = tmp_path / "research"
    research.mkdir()
    assert load_research_lab_snapshot(research)["status"] == "unavailable"

    target = tmp_path / "target.json"
    target.write_text("{}")
    (research / VALIDATION_REPORT).symlink_to(target)
    lab = load_research_lab_snapshot(research)
    assert lab["reports"]["validation"]["status"] == "unsafe_or_unreadable"

    (research / VALIDATION_REPORT).unlink()
    (research / VALIDATION_REPORT).write_text('{"schema_id":"a","schema_id":"b"}')
    lab = load_research_lab_snapshot(research)
    assert lab["reports"]["validation"]["status"] == "invalid"


def test_research_lab_rejects_oversized_buffer_before_parsing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    research = tmp_path / "research"
    research.mkdir()
    (research / VALIDATION_REPORT).write_text("{" + " " * 64 + "}")
    monkeypatch.setitem(
        research_lab_loader._REPORT_FILES,
        "validation",
        (VALIDATION_REPORT, 32),
    )

    lab = load_research_lab_snapshot(research)

    assert lab["reports"]["validation"]["status"] == "oversized"
    assert lab["reports"]["validation"]["sha256"] is None


def test_research_lab_render_is_explicit_descriptive_and_escaped(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_reports(research, malicious='<script>alert("x")</script>')
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
    for heading in (
        "Closed route evidence",
        "Closed origin evidence",
        "Score monotonicity",
        "Regimes, liquidity &amp; data quality",
        "Market vs catalyst",
        "Missed, false-positive &amp; late ideas",
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
    assert "Shadow recommendations do not auto-apply" in page.body
    assert "Live no-send" in page.body
    assert "Fixture evidence" in page.body
    assert "Insufficient sample" in page.body
    assert "<script>alert" not in page.body
    assert "&lt;script&gt;alert" in page.body
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
