"""Authoritative dashboard pointer, query, and readiness regressions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

import pytest

import crypto_rsi_scanner.event_alpha.dashboard.__main__ as dashboard_cli
from crypto_rsi_scanner.event_alpha.artifacts import operator_state
from crypto_rsi_scanner.event_alpha.dashboard.__main__ import main as dashboard_main
from crypto_rsi_scanner.event_alpha.dashboard.app import (
    DashboardGenerationBinding,
    RadarDashboardApp,
)
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    DashboardReadinessError,
    publish_current_namespace_pointer,
    read_current_namespace_pointer,
    resolve_authoritative_dashboard,
)
from crypto_rsi_scanner.event_alpha.dashboard.render import (
    filter_sort_candidates,
    render_dashboard_page,
)


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"
_TEST_NOW = "2026-07-12T06:03:00+00:00"


def _copy_fixture(tmp_path: Path) -> Path:
    shutil.copytree(_FIXTURE_BASE / _FIXTURE_NAMESPACE, tmp_path / _FIXTURE_NAMESPACE)
    return tmp_path


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _request(app: RadarDashboardApp, path: str = "/") -> tuple[str, str]:
    captured: dict[str, object] = {}

    def start_response(status, _headers, _exc_info=None):
        captured["status"] = status

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path,
                "QUERY_STRING": "",
            },
            start_response,
        )
    ).decode("utf-8")
    return str(captured["status"]), body


def test_dashboard_readiness_rejects_smoke_only_clock(tmp_path, capsys):
    status = dashboard_main([
        "--artifact-base",
        str(tmp_path),
        "--readiness",
        "--smoke-now",
        _TEST_NOW,
    ])

    assert status == 1
    assert "--smoke-now is allowed only with --smoke" in capsys.readouterr().err


def test_dashboard_readiness_publishes_exact_pointer_and_default_cli_uses_it(tmp_path, capsys):
    base = _copy_fixture(tmp_path)
    namespace_dir = base / _FIXTURE_NAMESPACE
    namespace_hashes = _file_hashes(namespace_dir)

    published = publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    pointer_before = pointer_path.read_bytes()
    pointer = read_current_namespace_pointer(base)

    assert published.snapshot.generation_authoritative is True
    assert pointer["artifact_namespace"] == _FIXTURE_NAMESPACE
    assert pointer["run_id"] == published.snapshot.run_id
    assert pointer["revision"] == published.snapshot.revision
    assert pointer["operator_state_sha256"] == published.snapshot.operator_state_sha256
    assert _file_hashes(namespace_dir) == namespace_hashes

    resolved = resolve_authoritative_dashboard(base, now=_TEST_NOW)
    assert resolved.namespace_source == "pointer"
    assert resolved.snapshot.run_id == published.snapshot.run_id
    assert pointer_path.read_bytes() == pointer_before
    assert dashboard_main(
        ["--artifact-base", str(base), "--smoke", "--smoke-now", _TEST_NOW]
    ) == 0
    output = capsys.readouterr()
    assert "radar_dashboard_smoke:" in output.out
    assert "Traceback" not in output.err
    assert pointer_path.read_bytes() == pointer_before
    assert _file_hashes(namespace_dir) == namespace_hashes


def test_published_pointer_survives_unchanged_strict_doctor_reverification(tmp_path):
    base = _copy_fixture(tmp_path)
    namespace_dir = base / _FIXTURE_NAMESPACE
    published = publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_before = (base / CURRENT_NAMESPACE_POINTER).read_bytes()
    state = published.snapshot.operator_state

    operator_state.record_doctor_status(
        namespace_dir,
        run_id=published.snapshot.run_id,
        profile=published.snapshot.profile,
        artifact_namespace=published.snapshot.artifact_namespace,
        expected_revision=published.snapshot.revision,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status=str(state["doctor"]["status"]),
        blocker_count=int(state["doctor"]["blocker_count"]),
        warning_count=int(state["doctor"]["warning_count"]),
        checked_at=datetime.fromisoformat("2026-07-12T06:04:00+00:00"),
    )

    resolved = resolve_authoritative_dashboard(
        base,
        now="2026-07-12T06:04:00+00:00",
    )
    assert resolved.snapshot.operator_state_sha256 == published.snapshot.operator_state_sha256
    assert (base / CURRENT_NAMESPACE_POINTER).read_bytes() == pointer_before


def test_published_pointer_invalidates_when_doctor_result_changes(tmp_path):
    base = _copy_fixture(tmp_path)
    namespace_dir = base / _FIXTURE_NAMESPACE
    published = publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    state = published.snapshot.operator_state

    operator_state.record_doctor_status(
        namespace_dir,
        run_id=published.snapshot.run_id,
        profile=published.snapshot.profile,
        artifact_namespace=published.snapshot.artifact_namespace,
        expected_revision=published.snapshot.revision,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="WARN",
        blocker_count=0,
        warning_count=int(state["doctor"]["warning_count"]) + 1,
        checked_at=datetime.fromisoformat("2026-07-12T06:04:00+00:00"),
    )

    with pytest.raises(
        DashboardReadinessError,
        match="pointer does not match the exact operator generation",
    ):
        resolve_authoritative_dashboard(base, now="2026-07-12T06:04:00+00:00")


def test_published_pointer_invalidates_when_fingerprinted_artifact_changes(tmp_path):
    base = _copy_fixture(tmp_path)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    pointer_before = pointer_path.read_bytes()
    brief_path = base / _FIXTURE_NAMESPACE / "event_alpha_daily_brief.md"
    brief_path.write_text(
        brief_path.read_text(encoding="utf-8") + "\nchanged after publication\n",
        encoding="utf-8",
    )

    with pytest.raises(DashboardReadinessError, match="not authoritative"):
        resolve_authoritative_dashboard(base, now=_TEST_NOW)
    assert pointer_path.read_bytes() == pointer_before


def test_pointer_bound_dashboard_refuses_operator_state_drift_after_startup(tmp_path):
    base = _copy_fixture(tmp_path)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    resolved = resolve_authoritative_dashboard(base, now=_TEST_NOW)
    app = RadarDashboardApp(
        base,
        resolved.snapshot.artifact_namespace,
        now=_TEST_NOW,
        generation_binding=DashboardGenerationBinding.from_snapshot(resolved.snapshot),
    )

    initial_status, initial_body = _request(app)
    assert initial_status == "200 OK"
    assert "Research idea, not a trade instruction" in initial_body

    state_path = base / _FIXTURE_NAMESPACE / "event_alpha_operator_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["cumulative_store_rows"] = int(state["cumulative_store_rows"]) + 1
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    changed = load_dashboard_snapshot(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    assert changed.generation_authoritative is True

    drift_status, drift_body = _request(app)
    assert drift_status == "503 Service Unavailable"
    assert "dashboard pointer generation changed after startup" in drift_body
    assert "operator_state_sha256" in drift_body
    assert "Research idea, not a trade instruction" not in drift_body


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("run_id", "later-run"),
        ("revision", 8),
        ("operator_state_sha256", "f" * 64),
    ),
)
def test_pointer_binding_checks_every_generation_identity_field(
    field,
    replacement,
    monkeypatch,
):
    snapshot = load_dashboard_snapshot(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    binding = DashboardGenerationBinding.from_snapshot(snapshot)
    app = RadarDashboardApp(
        _FIXTURE_BASE,
        _FIXTURE_NAMESPACE,
        now=_TEST_NOW,
        generation_binding=binding,
    )
    monkeypatch.setattr(
        "crypto_rsi_scanner.event_alpha.dashboard.app.load_dashboard_snapshot",
        lambda *_args, **_kwargs: replace(snapshot, **{field: replacement}),
    )

    status, body = _request(app)

    assert status == "503 Service Unavailable"
    assert field in body


def test_dashboard_cli_binds_pointer_mode_but_preserves_explicit_namespace_mode(
    tmp_path,
    monkeypatch,
):
    base = _copy_fixture(tmp_path)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_result = resolve_authoritative_dashboard(base, now=_TEST_NOW)
    calls: list[object] = []

    def fake_resolve(_base, artifact_namespace=None, **_kwargs):
        return replace(
            pointer_result,
            namespace_source="explicit" if artifact_namespace else "pointer",
        )

    def fake_serve(_base, _namespace, **kwargs):
        calls.append(kwargs.get("generation_binding"))

    monkeypatch.setattr(dashboard_cli, "resolve_authoritative_dashboard", fake_resolve)
    monkeypatch.setattr(dashboard_cli, "serve_dashboard", fake_serve)

    assert dashboard_cli.main(["--artifact-base", str(base)]) == 0
    assert isinstance(calls[-1], DashboardGenerationBinding)
    assert dashboard_cli.main(
        ["--artifact-base", str(base), "--namespace", _FIXTURE_NAMESPACE]
    ) == 0
    assert calls[-1] is None


def test_dashboard_readiness_refuses_stale_generation_without_replacing_pointer(tmp_path):
    base = _copy_fixture(tmp_path)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    trusted_pointer = pointer_path.read_bytes()
    stale_now = "2026-07-13T06:03:00+00:00"

    with pytest.raises(DashboardReadinessError, match="not authoritative"):
        publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=stale_now)
    with pytest.raises(DashboardReadinessError, match="not authoritative"):
        resolve_authoritative_dashboard(base, now=stale_now)

    assert pointer_path.read_bytes() == trusted_pointer
    stale_snapshot = load_dashboard_snapshot(base, _FIXTURE_NAMESPACE, now=stale_now)
    stale_page = render_dashboard_page(stale_snapshot, "/")
    assert stale_snapshot.generation_authoritative is False
    assert "UNTRUSTED CURRENT GENERATION" in stale_page.body
    assert "Fresh high-liquidity breakout" not in stale_page.body


def test_dashboard_readiness_requires_exact_current_counts_before_pointer_update(tmp_path):
    base = _copy_fixture(tmp_path)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    trusted_pointer = pointer_path.read_bytes()
    state_path = base / _FIXTURE_NAMESPACE / "event_alpha_operator_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["artifacts"]["core_opportunities"].pop("count")
    state["current_generation_core_rows"] = None
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(DashboardReadinessError, match="current count"):
        publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)

    assert pointer_path.read_bytes() == trusted_pointer


def test_dashboard_readiness_rejects_partial_product_manifest_even_if_loader_is_authoritative(
    tmp_path,
):
    base = _copy_fixture(tmp_path)
    state_path = base / _FIXTURE_NAMESPACE / "event_alpha_operator_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["artifacts"]["decision_v2_notification_preview"]["status"] = "skipped"
    state["artifacts"]["decision_v2_notification_preview"]["reason"] = "fixture_partial"
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    snapshot = load_dashboard_snapshot(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    assert snapshot.generation_authoritative is True
    with pytest.raises(
        DashboardReadinessError,
        match="lacks current decision_v2_notification_preview artifact",
    ):
        publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)


def test_dashboard_cli_missing_pointer_is_concise_and_has_no_traceback(tmp_path, capsys):
    assert dashboard_main(["--artifact-base", str(tmp_path)]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "radar_dashboard_readiness: NOT_READY" in output.err
    assert "current namespace pointer is missing" in output.err
    assert "Traceback" not in output.err


def test_dashboard_filters_sorts_dashboard_watch_risk_watch_and_snapshot_svg():
    snapshot = load_dashboard_snapshot(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    rows = [dict(row) for row in snapshot.visible_current_candidates]
    by_symbol = {row["symbol"]: row for row in rows}

    assert [row["symbol"] for row in filter_sort_candidates(rows, {"sort": "actionability_desc"})] == [
        "LIST",
        "ALPHA",
        "FADE",
    ]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"sort": "urgency_desc"})] == [
        "ALPHA",
        "LIST",
        "FADE",
    ]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"sort": "risk_asc"})] == [
        "LIST",
        "ALPHA",
        "FADE",
    ]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"origin": "catalyst_led"})] == ["LIST"]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"confidence": "exploratory"})] == ["FADE"]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"catalyst": "unknown"})] == ["ALPHA"]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"risk": "medium"})] == ["FADE"]
    assert [row["symbol"] for row in filter_sort_candidates(rows, {"timing": "breakout"})] == ["ALPHA"]

    dashboard_watch = dict(by_symbol["ALPHA"])
    dashboard_watch["_dashboard_route"] = "dashboard_watch"
    dashboard_watch["radar_actionable"] = False
    dashboard_watch["market_state_snapshot"] = {
        "price_series": [100.0, 102.0, 101.5, 105.0],
    }
    risk_watch = dict(by_symbol["FADE"])
    risk_watch["_dashboard_route"] = "risk_watch"
    visible = replace(
        snapshot,
        current_candidates=(dashboard_watch, by_symbol["LIST"], risk_watch),
    )

    today = render_dashboard_page(
        visible,
        "/",
        query={"route": "dashboard_watch", "sort": "urgency_desc"},
    )
    ideas = render_dashboard_page(
        visible,
        "/ideas",
        query={"route": "dashboard_watch", "sort": "urgency_desc"},
    )
    fade = render_dashboard_page(visible, "/fade-risk", query={"route": "risk_watch"})
    assert "Dashboard watch" in today.body
    assert "ALPHA" in today.body
    assert "LIST" not in today.body
    assert 'class="attention-card route-dashboard_watch"' in today.body
    assert "Existing market snapshot trend" in ideas.body
    assert "risk_watch" in fade.body
    assert "FADE" in fade.body


def test_dashboard_wsgi_applies_allowlisted_query_filters():
    app = RadarDashboardApp(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    captured: dict[str, object] = {}

    def start_response(status, headers, _exc_info=None):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/",
                "QUERY_STRING": "catalyst=unknown&sort=urgency_desc",
            },
            start_response,
        )
    ).decode("utf-8")

    assert captured["status"] == "200 OK"
    assert "ALPHA" in body
    assert "/candidate/core%3Alist" not in body
    assert 'value="urgency_desc" selected' in body


def test_dashboard_calendar_renders_v2_release_context_fields():
    snapshot = load_dashboard_snapshot(_FIXTURE_BASE, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    event = dict(snapshot.current_calendar_events[0])
    event.update(
        {
            "timezone": "America/New_York",
            "previous_value": 3.1,
            "forecast_value": 3.0,
            "actual_value": 2.8,
            "surprise_value": -0.2,
            "impact_window_before": "24h",
            "impact_window_after": "4h",
        }
    )
    page = render_dashboard_page(
        replace(snapshot, current_calendar_events=(event,)),
        "/calendar",
    )

    assert "America/New_York" in page.body
    assert "3.1 / 3 / 2.8 / -0.2" in page.body
    assert "-24h / +4h" in page.body


def test_dashboard_readiness_and_default_load_make_no_provider_calls_or_namespace_writes(
    tmp_path,
    monkeypatch,
):
    base = _copy_fixture(tmp_path)
    namespace_dir = base / _FIXTURE_NAMESPACE
    namespace_hashes = _file_hashes(namespace_dir)

    def forbidden_provider_call(*_args, **_kwargs):
        raise AssertionError("dashboard readiness must not open network connections")

    monkeypatch.setattr(socket, "create_connection", forbidden_provider_call)
    publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    pointer = (base / CURRENT_NAMESPACE_POINTER).read_bytes()
    resolve_authoritative_dashboard(base, now=_TEST_NOW)

    assert _file_hashes(namespace_dir) == namespace_hashes
    assert (base / CURRENT_NAMESPACE_POINTER).read_bytes() == pointer


def test_dashboard_make_targets_use_pointer_by_default_and_explicit_namespace_when_supplied():
    default_serve = subprocess.check_output(
        ["make", "-n", "radar-dashboard", "PYTHON=python3"],
        cwd=_ROOT,
        text=True,
    )
    explicit_serve = subprocess.check_output(
        ["make", "-n", "radar-dashboard", "PYTHON=python3", "ARTIFACT_NAMESPACE=current"],
        cwd=_ROOT,
        text=True,
    )
    readiness = subprocess.check_output(
        [
            "make",
            "-n",
            "radar-dashboard-readiness",
            "PYTHON=python3",
            "ARTIFACT_NAMESPACE=current",
        ],
        cwd=_ROOT,
        text=True,
    )

    assert "--namespace" not in default_serve
    assert "--namespace current" in explicit_serve
    assert "--readiness" in readiness
    assert "--namespace current" in readiness
