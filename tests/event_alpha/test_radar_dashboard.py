"""Read-only local radar dashboard regressions."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import fingerprints, operator_state
from crypto_rsi_scanner.event_alpha.dashboard import loader as dashboard_loader
from crypto_rsi_scanner.event_alpha.dashboard.__main__ import _smoke
from crypto_rsi_scanner.event_alpha.dashboard.app import RadarDashboardApp, serve_dashboard
from crypto_rsi_scanner.event_alpha.dashboard.loader import _dashboard_decision_row, load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardLoadError
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page


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
    assert "cumulative core history 5" not in page.body


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
    }
    read_counts = {path: 0 for path in current_paths}
    original = dashboard_loader._read_regular_file_once

    def counted(path):
        resolved = path.resolve()
        if resolved in read_counts:
            read_counts[resolved] += 1
        return original(path)

    monkeypatch.setattr(dashboard_loader, "_read_regular_file_once", counted)
    snapshot = _snapshot()

    assert snapshot.generation_authoritative is True
    assert read_counts == {path: 1 for path in current_paths}


def test_dashboard_file_swap_after_read_cannot_change_the_parsed_calendar(tmp_path, monkeypatch):
    target = _copy_namespace(tmp_path)
    calendar_path = target / "event_unified_calendar_events.jsonl"
    original = dashboard_loader._read_regular_file_once
    calendar_reads = 0

    def swap_after_read(path):
        nonlocal calendar_reads
        data, error = original(path)
        if path == calendar_path:
            calendar_reads += 1
            if calendar_reads == 1 and data is not None:
                calendar_path.write_bytes(data + b'\n{"title":"SWAPPED CONTENT"}\n')
        return data, error

    monkeypatch.setattr(dashboard_loader, "_read_regular_file_once", swap_after_read)
    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_TEST_NOW)

    assert calendar_reads == 1
    assert snapshot.generation_authoritative is True
    assert "SWAPPED CONTENT" not in json.dumps(snapshot.current_calendar_events)
    assert "Expected regulatory decision window" in json.dumps(snapshot.current_calendar_events)


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
