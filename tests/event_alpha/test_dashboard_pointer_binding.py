"""Per-request dashboard pointer binding regressions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.app import (
    DashboardGenerationBinding,
    RadarDashboardApp,
)
from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    publish_current_namespace_pointer,
    read_current_namespace_pointer,
)


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_BASE = _ROOT / "fixtures/event_alpha/radar_dashboard"
_FIXTURE_NAMESPACE = "current"
_TEST_NOW = "2026-07-12T06:03:00+00:00"


def _copy_fixture(tmp_path: Path) -> Path:
    shutil.copytree(_FIXTURE_BASE / _FIXTURE_NAMESPACE, tmp_path / _FIXTURE_NAMESPACE)
    return tmp_path


def _bound_app(tmp_path: Path) -> tuple[Path, RadarDashboardApp]:
    base = _copy_fixture(tmp_path)
    published = publish_current_namespace_pointer(
        base,
        _FIXTURE_NAMESPACE,
        now=_TEST_NOW,
    )
    app = RadarDashboardApp(
        base,
        published.snapshot.artifact_namespace,
        now=_TEST_NOW,
        generation_binding=DashboardGenerationBinding.from_snapshot(published.snapshot),
    )
    return base, app


def _request(
    app: RadarDashboardApp,
    *,
    method: str = "GET",
    path: str = "/",
) -> tuple[str, str]:
    captured: dict[str, object] = {}

    def start_response(status, _headers, _exc_info=None):
        captured["status"] = status

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": "",
            },
            start_response,
        )
    ).decode("utf-8")
    return str(captured["status"]), body


def _write_pointer(base: Path, pointer: dict[str, object]) -> bytes:
    payload = (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (base / CURRENT_NAMESPACE_POINTER).write_bytes(payload)
    return payload


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("artifact_namespace", "different_generation"),
        ("profile", "different_profile"),
        ("run_id", "different-run"),
        ("revision", 99),
        ("operator_state_sha256", "f" * 64),
    ),
)
def test_pointer_bound_get_rejects_persisted_pointer_identity_drift(
    tmp_path,
    field,
    replacement,
):
    base, app = _bound_app(tmp_path)
    initial_status, initial_body = _request(app)
    assert initial_status == "200 OK"
    assert "Research idea, not a trade instruction" in initial_body

    pointer = read_current_namespace_pointer(base)
    pointer[field] = replacement
    _write_pointer(base, pointer)

    status, body = _request(app)

    assert status == "503 Service Unavailable"
    assert "dashboard pointer generation changed after startup" in body
    assert field in body
    assert "Research idea, not a trade instruction" not in body


@pytest.mark.parametrize("invalid_state", ("missing", "invalid_json", "untrusted"))
def test_pointer_bound_get_rejects_invalid_or_untrusted_current_pointer(
    tmp_path,
    invalid_state,
):
    base, app = _bound_app(tmp_path)
    assert _request(app)[0] == "200 OK"
    pointer_path = base / CURRENT_NAMESPACE_POINTER
    if invalid_state == "missing":
        pointer_path.unlink()
    elif invalid_state == "invalid_json":
        pointer_path.write_bytes(b"{not-json\n")
    else:
        pointer = read_current_namespace_pointer(base)
        pointer["generation_authority_status"] = "untrusted"
        _write_pointer(base, pointer)

    status, body = _request(app)

    assert status == "503 Service Unavailable"
    assert "dashboard pointer is no longer valid" in body
    assert "Research idea, not a trade instruction" not in body


def test_pointer_bound_head_revalidates_pointer_and_returns_empty_503_body(tmp_path):
    base, app = _bound_app(tmp_path)
    assert _request(app, method="HEAD") == ("200 OK", "")
    pointer = read_current_namespace_pointer(base)
    pointer["run_id"] = "later-run"
    _write_pointer(base, pointer)

    status, body = _request(app, method="HEAD")

    assert status == "503 Service Unavailable"
    assert body == ""


def test_pointer_authority_timestamp_only_refresh_remains_allowed_and_read_only(tmp_path):
    base, app = _bound_app(tmp_path)
    namespace_dir = base / _FIXTURE_NAMESPACE
    namespace_before = _tree_hashes(namespace_dir)
    pointer = read_current_namespace_pointer(base)
    pointer["authority_checked_at"] = "2026-07-12T06:04:00+00:00"
    refreshed_pointer = _write_pointer(base, pointer)

    get_status, get_body = _request(app)
    head_status, head_body = _request(app, method="HEAD")

    assert get_status == "200 OK"
    assert "Research idea, not a trade instruction" in get_body
    assert (head_status, head_body) == ("200 OK", "")
    assert (base / CURRENT_NAMESPACE_POINTER).read_bytes() == refreshed_pointer
    assert _tree_hashes(namespace_dir) == namespace_before


@pytest.mark.parametrize(
    ("max_generation_age_hours", "max_doctor_age_hours", "expected_reason"),
    (
        (6.0, 12.0, "generation:stale"),
        (12.0, 6.0, "doctor:stale"),
        (6.0, 6.0, "generation:stale"),
    ),
)
def test_pointer_bound_freshness_loss_serves_quarantined_shell_with_503(
    tmp_path,
    max_generation_age_hours,
    max_doctor_age_hours,
    expected_reason,
):
    base = _copy_fixture(tmp_path)
    published = publish_current_namespace_pointer(base, _FIXTURE_NAMESPACE, now=_TEST_NOW)
    app = RadarDashboardApp(
        base,
        published.snapshot.artifact_namespace,
        now="2026-07-12T13:03:00+00:00",
        max_generation_age_hours=max_generation_age_hours,
        max_doctor_age_hours=max_doctor_age_hours,
        generation_binding=DashboardGenerationBinding.from_snapshot(published.snapshot),
    )

    today_status, today_body = _request(app)
    health_status, health_body = _request(app, path="/health")
    outcomes_status, outcomes_body = _request(app, path="/outcomes")
    feedback_status, feedback_body = _request(app, path="/feedback-outcomes")
    history_status, history_body = _request(app, path="/campaign-history")
    unknown_status, unknown_body = _request(app, path="/not-a-dashboard-route")

    assert today_status == "503 Service Unavailable"
    assert "UNTRUSTED CURRENT GENERATION" in today_body
    assert expected_reason in today_body
    assert "Current-generation research content is unavailable" in today_body
    assert "Fresh high-liquidity breakout" not in today_body
    assert "Dashboard unavailable" not in today_body
    assert health_status == "503 Service Unavailable"
    assert "System Health" in health_body
    assert "UNTRUSTED CURRENT GENERATION" in health_body
    assert "Fresh high-liquidity breakout" not in health_body
    assert outcomes_status == "503 Service Unavailable"
    assert "Historical campaign outcomes" in outcomes_body
    assert "UNTRUSTED CURRENT GENERATION" in outcomes_body
    assert "Fresh high-liquidity breakout" not in outcomes_body
    assert feedback_status == "503 Service Unavailable"
    assert "shared / non-authoritative" in feedback_body
    assert "UNTRUSTED CURRENT GENERATION" in feedback_body
    assert "Fresh high-liquidity breakout" not in feedback_body
    assert history_status == "503 Service Unavailable"
    assert "Run history" in history_body
    assert "UNTRUSTED CURRENT GENERATION" in history_body
    assert "Fresh high-liquidity breakout" not in history_body
    assert unknown_status == "404 Not Found"
    assert "Unknown dashboard page" in unknown_body
    assert "UNTRUSTED CURRENT GENERATION" not in unknown_body


def test_pointer_bound_integrity_loss_keeps_minimal_hard_error(tmp_path):
    base, app = _bound_app(tmp_path)
    brief_path = base / _FIXTURE_NAMESPACE / "event_alpha_daily_brief.md"
    brief_path.write_text(
        brief_path.read_text(encoding="utf-8") + "\nchanged after publication\n",
        encoding="utf-8",
    )

    status, body = _request(app)

    assert status == "503 Service Unavailable"
    assert "Dashboard unavailable" in body
    assert "daily_brief:fingerprint_content_mismatch:sha256" in body
    assert "UNTRUSTED CURRENT GENERATION" not in body
    assert "Fresh high-liquidity breakout" not in body


def test_explicit_namespace_app_does_not_require_a_current_pointer(tmp_path):
    base = _copy_fixture(tmp_path)
    app = RadarDashboardApp(
        base,
        _FIXTURE_NAMESPACE,
        now=_TEST_NOW,
    )

    status, body = _request(app)

    assert status == "200 OK"
    assert "Research idea, not a trade instruction" in body
    assert not (base / CURRENT_NAMESPACE_POINTER).exists()
