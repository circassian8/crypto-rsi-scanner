"""Focused current-generation operator-state and coherence regressions."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from crypto_rsi_scanner.cli.services import event_alpha_reports as daily_report_service
from crypto_rsi_scanner.cli.services.event_alpha_notifications import preview as preview_service
from crypto_rsi_scanner.cli.services.scanner_parts import reports as scanner_report_service
from crypto_rsi_scanner.event_alpha.artifacts import fingerprints as artifact_fingerprints
from crypto_rsi_scanner.event_alpha.artifacts import operator_state, schema_v1
from crypto_rsi_scanner.event_alpha.doctor.checks import operations
from crypto_rsi_scanner.event_alpha.namespace import lifecycle as namespace_lifecycle
from crypto_rsi_scanner.event_alpha.namespace import status as namespace_status
from crypto_rsi_scanner.event_alpha.notifications import readiness as send_readiness


_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _run_row(namespace: str = "notify_no_key", run_id: str = "run-current") -> dict[str, object]:
    return {
        "run_id": run_id,
        "profile": "notify_no_key",
        "artifact_namespace": namespace,
        "run_mode": "event_alpha_cycle",
    }


def _begin_run(
    namespace_dir: Path,
    run_row: dict[str, object],
    *,
    updated_at: datetime,
    run_ledger_path: Path | None = None,
) -> dict[str, object]:
    """Persist the exact run row before building its authoritative state."""

    ledger = run_ledger_path or namespace_dir / "event_alpha_runs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(run_row, default=str, sort_keys=True, separators=(",", ":")) + "\n"
        )
    return operator_state.begin_run(
        namespace_dir,
        run_row,
        run_ledger_path=ledger,
        updated_at=updated_at,
    )


def _assert_value_error(call: Callable[[], object], fragment: str) -> None:
    try:
        call()
    except ValueError as exc:
        assert fragment in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_operator_text_run_id_matching_is_prefix_safe():
    text = "# Event Alpha preview\nrun_id: run-10\nstatus: no_send\n"

    assert operator_state.text_has_exact_run_id(text, "run-10") is True
    assert operator_state.text_has_exact_run_id(text, "run-1") is False
    assert operator_state.text_has_exact_run_id(text, "") is False


def test_operator_state_begin_run_is_atomic_valid_and_private(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    custom_ledger = namespace_dir / "custom_runs.jsonl"
    state = _begin_run(
        namespace_dir,
        _run_row(),
        run_ledger_path=custom_ledger,
        updated_at=_NOW,
    )
    state_path = namespace_dir / operator_state.OPERATOR_STATE_FILENAME

    assert json.loads(state_path.read_text(encoding="utf-8")) == state
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    assert not tuple(namespace_dir.glob(f".{state_path.name}.*.tmp"))
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.exists is True
    assert loaded.valid is True
    assert loaded.error is None
    assert loaded.state == state
    assert state["artifacts"]["run_ledger"]["path"] == "custom_runs.jsonl"


def test_artifact_fingerprint_contract_binds_exact_bytes_lines_and_tree(tmp_path):
    jsonl = tmp_path / "rows.jsonl"
    payload = b'{"row":1}\n\n {"row":2}\r\n'
    jsonl.write_bytes(payload)
    file_fingerprint = artifact_fingerprints.fingerprint_path(jsonl)
    assert file_fingerprint == {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "item_count": 2,
        "fingerprint_kind": "jsonl_lines",
        "fingerprint_contract_version": 1,
    }
    assert artifact_fingerprints.verify_bytes_fingerprint(payload, file_fingerprint) == (
        True,
        None,
    )
    invalid_version = dict(file_fingerprint, fingerprint_contract_version=True)
    assert artifact_fingerprints.fingerprint_metadata_error(invalid_version) == (
        "fingerprint_contract_version_unsupported"
    )

    tree = tmp_path / "cards"
    (tree / "nested").mkdir(parents=True)
    (tree / "a.md").write_bytes(b"a")
    (tree / "nested" / "b.md").write_bytes(b"bb")
    before = artifact_fingerprints.fingerprint_path(tree)
    assert before["fingerprint_kind"] == "directory_tree_v1"
    assert before["size_bytes"] == 3
    assert before["item_count"] == 2

    from unittest.mock import patch
    original_reader = artifact_fingerprints._read_regular_file_once  # noqa: SLF001
    mutated = False
    def mutate_during_read(path):
        nonlocal mutated
        data = original_reader(path)
        if not mutated:
            (tree / "concurrent.md").write_text("new", encoding="utf-8")
            mutated = True
        return data

    with patch.object(artifact_fingerprints, "_read_regular_file_once", side_effect=mutate_during_read):
        try:
            artifact_fingerprints.fingerprint_path(tree)
        except artifact_fingerprints.FingerprintError as exc:
            assert str(exc) == "directory_changed_during_fingerprint"
        else:
            raise AssertionError("directory mutation during fingerprint must fail closed")
    (tree / "concurrent.md").unlink()

    (tree / "nested" / "b.md").write_bytes(b"changed")
    verified, reason = artifact_fingerprints.verify_path_fingerprint(tree, before)
    assert verified is False
    assert reason == "fingerprint_content_mismatch:sha256"

    symlink = tree / "unsafe-link"
    symlink.symlink_to(tree / "a.md")
    try:
        artifact_fingerprints.fingerprint_path(tree)
    except artifact_fingerprints.FingerprintError as exc:
        assert str(exc) == "directory_symlink_not_allowed"
    else:
        raise AssertionError("directory fingerprints must reject symlinks")


def test_operator_state_fingerprints_current_files_directories_and_mutations(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    core_path = namespace_dir / "event_core_opportunities.jsonl"
    cards_dir = namespace_dir / "research_cards"
    cards_dir.mkdir(parents=True)
    core_path.write_text('{"row_type":"event_core_opportunity"}\n\n', encoding="utf-8")
    (cards_dir / "one.md").write_text("one\n", encoding="utf-8")
    run_row = {
        **_run_row(),
        "core_opportunity_store_path": core_path,
        "core_opportunity_write_success": True,
        "research_cards_dir": cards_dir,
        "research_card_paths": [cards_dir / "one.md"],
        "research_cards_written": 1,
    }

    state = _begin_run(namespace_dir, run_row, updated_at=_NOW)
    core_entry = state["artifacts"]["core_opportunities"]
    cards_entry = state["artifacts"]["research_cards"]
    ledger_entry = state["artifacts"]["run_ledger"]
    assert core_entry["fingerprint_kind"] == "jsonl_lines"
    assert core_entry["item_count"] == 1
    assert cards_entry["fingerprint_kind"] == "directory_tree_v1"
    assert cards_entry["item_count"] == 1
    assert ledger_entry["fingerprint_kind"] == "canonical_run_row"
    assert ledger_entry["item_count"] == 1
    assert ledger_entry["run_row_identity"] == {
        "run_id": "run-current",
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
    }
    assert ledger_entry["run_row_match_count"] == 1
    assert operator_state.state_has_complete_artifact_fingerprints(
        state,
        base=namespace_dir,
    ) is True

    core_path.write_text('{"row_type":"event_core_opportunity","changed":true}\n', encoding="utf-8")
    changed_core = operator_state.load_operator_state(namespace_dir)
    assert changed_core.valid is False
    assert changed_core.error == (
        "artifact_fingerprint_invalid:core_opportunities:"
        "fingerprint_content_mismatch:sha256"
    )

    core_path.write_text('{"row_type":"event_core_opportunity"}\n\n', encoding="utf-8")
    (cards_dir / "two.md").write_text("two\n", encoding="utf-8")
    changed_tree = operator_state.load_operator_state(namespace_dir)
    assert changed_tree.valid is False
    assert changed_tree.error == (
        "artifact_fingerprint_invalid:research_cards:"
        "fingerprint_content_mismatch:sha256"
    )


def test_operator_state_run_ledger_fingerprint_is_append_stable_and_edit_sensitive(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    exact = _run_row()
    state = _begin_run(namespace_dir, exact, updated_at=_NOW)
    ledger_path = namespace_dir / "event_alpha_runs.jsonl"
    baseline = dict(state["artifacts"]["run_ledger"])

    unrelated = _run_row(run_id="run-later")
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(unrelated, sort_keys=True, separators=(",", ":")) + "\n")
    appended = operator_state.load_operator_state(namespace_dir)
    assert appended.valid is True
    assert appended.state is not None
    assert appended.state["artifacts"]["run_ledger"] == baseline

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["run_mode"] = "edited_after_fingerprint"
    ledger_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    edited = operator_state.load_operator_state(namespace_dir)
    assert edited.valid is False
    assert edited.error == (
        "artifact_fingerprint_invalid:run_ledger:fingerprint_content_mismatch:sha256"
    )


def test_operator_state_run_ledger_duplicate_exact_identity_fails_closed(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    exact = _run_row()
    _begin_run(namespace_dir, exact, updated_at=_NOW)
    ledger_path = namespace_dir / "event_alpha_runs.jsonl"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(exact, sort_keys=True, separators=(",", ":")) + "\n")

    duplicated = operator_state.load_operator_state(namespace_dir)
    assert duplicated.valid is False
    assert duplicated.error == (
        "artifact_fingerprint_invalid:run_ledger:run_row_match_count_mismatch:2"
    )


def test_legacy_fingerprintless_state_remains_readable_but_cannot_gain_authority(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    state = _begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    legacy_sha_only = json.loads(json.dumps(state))
    ledger = legacy_sha_only["artifacts"]["run_ledger"]
    for field in (
        *(field for field in artifact_fingerprints.FINGERPRINT_FIELDS if field != "sha256"),
        "run_row_identity",
        "run_row_match_count",
    ):
        ledger.pop(field, None)
    operator_state.write_json_atomic(
        operator_state.operator_state_path(namespace_dir),
        legacy_sha_only,
    )
    assert operator_state.load_operator_state(namespace_dir).valid is True

    legacy = json.loads(json.dumps(legacy_sha_only))
    legacy["artifacts"]["run_ledger"].pop("sha256", None)
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), legacy)

    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is True
    assert loaded.state is not None
    assert operator_state.state_has_complete_artifact_fingerprints(
        loaded.state,
        base=namespace_dir,
    ) is False
    stray_legacy = json.loads(json.dumps(legacy_sha_only))
    stray_legacy["artifacts"]["run_ledger"]["run_row_sha256"] = "0" * 64
    assert operator_state.operator_artifact_fingerprint_error(
        stray_legacy,
        base=namespace_dir,
        require_complete=False,
    ) == "artifact_fingerprint_partial:run_ledger"
    _assert_value_error(
        lambda: operator_state.record_doctor_status(
            namespace_dir,
            run_id="run-current",
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            expected_revision=1,
            strict=True,
            schema_only=False,
            skip_api_checks=False,
            status="OK",
            checked_at=_NOW,
        ),
        "fingerprint authority unavailable",
    )


def test_missing_declared_artifact_is_non_current_and_malformed_legacy_digest_fails(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    missing_core = namespace_dir / "event_core_opportunities.jsonl"
    run_row = {
        **_run_row(),
        "core_opportunity_store_path": missing_core,
        "core_opportunity_write_success": True,
    }

    state = _begin_run(namespace_dir, run_row, updated_at=_NOW)
    core_entry = state["artifacts"]["core_opportunities"]
    assert core_entry["status"] == operator_state.STATUS_MISSING
    assert core_entry["reason"] == "artifact_path_missing_for_fingerprint"
    assert not any(field in core_entry for field in artifact_fingerprints.FINGERPRINT_FIELDS)
    assert state["manifest_status"] == "incoherent"
    assert operator_state.load_operator_state(namespace_dir).valid is True

    corrupted = json.loads(json.dumps(state))
    ledger = corrupted["artifacts"]["run_ledger"]
    for field in (
        "size_bytes",
        "item_count",
        "fingerprint_kind",
        "fingerprint_contract_version",
        "run_row_identity",
        "run_row_match_count",
    ):
        ledger.pop(field, None)
    ledger["sha256"] = "not-a-valid-legacy-digest"
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), corrupted)
    invalid = operator_state.load_operator_state(namespace_dir)
    assert invalid.valid is False
    assert invalid.error in {
        "artifact_legacy_sha256_invalid:run_ledger",
        "schema_error:operator_state_current_artifact_missing_fingerprint:run_ledger:size_bytes",
    }


def test_operator_state_rejects_leaf_and_component_symlink_artifacts(tmp_path):
    for case_name in ("leaf", "component"):
        namespace_dir = tmp_path / case_name
        _begin_run(namespace_dir, _run_row(namespace=case_name), updated_at=_NOW)
        real_dir = namespace_dir / "real"
        real_dir.mkdir()
        real = real_dir / "coverage.json"
        real.write_text("{}\n", encoding="utf-8")
        if case_name == "leaf":
            artifact_path = namespace_dir / "coverage-link.json"
            artifact_path.symlink_to(real)
        else:
            alias = namespace_dir / "alias"
            alias.symlink_to(real_dir, target_is_directory=True)
            artifact_path = alias / real.name
        state = operator_state.record_artifact(
            namespace_dir,
            run_id="run-current",
            profile="notify_no_key",
            artifact_namespace=case_name,
            name="source_coverage_json",
            path=artifact_path,
            updated_at=_NOW,
        )
        entry = state["artifacts"]["source_coverage_json"]
        assert entry["status"] == operator_state.STATUS_MISSING
        assert entry["reason"] == "artifact_path_missing_for_fingerprint"
        assert "fingerprint_contract_version" not in entry


def test_operator_state_revision_invalidates_completed_doctor(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    _begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    state = operator_state.record_doctor_status(
        namespace_dir,
        run_id="run-current",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        expected_revision=1,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        checked_at=_NOW,
    )
    assert state["revision"] == 1
    assert state["doctor"]["status"] == "OK"
    assert state["doctor"]["verified_revision"] == 1

    preview_path = namespace_dir / "event_alpha_notification_preview.md"
    preview_path.write_text("run_id: run-current\n", encoding="utf-8")
    state = operator_state.record_artifact(
        namespace_dir,
        run_id="run-current",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        name="notification_preview",
        path=preview_path,
        updated_at=_NOW,
    )

    assert state["revision"] == 2
    assert state["doctor"] == {
        "status": "stale",
        "run_id": "run-current",
        "authoritative": False,
        "strict": False,
        "schema_only": False,
        "skip_api_checks": False,
        "verified_at": None,
        "verified_revision": None,
        "blocker_count": 0,
        "warning_count": 0,
    }
    assert operator_state.load_operator_state(namespace_dir).valid is True
    _assert_value_error(
        lambda: operator_state.record_doctor_status(
            namespace_dir,
            run_id="run-current",
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            expected_revision=1,
            strict=True,
            schema_only=False,
            skip_api_checks=False,
            status="OK",
            checked_at=_NOW,
        ),
        "revision mismatch",
    )
    _assert_value_error(
        lambda: operator_state.record_doctor_status(
            namespace_dir,
            run_id="run-current",
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            expected_revision=2,
            strict=False,
            schema_only=False,
            skip_api_checks=False,
            status="OK",
            checked_at=_NOW,
        ),
        "only a full strict doctor",
    )


def test_operator_state_rejects_every_exact_identity_mismatch(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    artifact_path = namespace_dir / "event_alpha_source_coverage.json"
    artifact_path.write_text("{}\n", encoding="utf-8")

    for run_id, profile, namespace in (
        ("run-other", "notify_no_key", "notify_no_key"),
        ("run-current", "other-profile", "notify_no_key"),
        ("run-current", "notify_no_key", "other-namespace"),
    ):
        _assert_value_error(
            lambda run_id=run_id, profile=profile, namespace=namespace: operator_state.record_artifact(
                namespace_dir,
                run_id=run_id,
                profile=profile,
                artifact_namespace=namespace,
                name="source_coverage_json",
                path=artifact_path,
                updated_at=_NOW,
            ),
            "operator state identity mismatch",
        )

    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is True
    assert loaded.state is not None
    assert loaded.state["revision"] == 1


def test_operator_state_requires_reason_for_every_non_current_artifact(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    state = operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)

    for non_current_status in (
        operator_state.STATUS_SKIPPED,
        operator_state.STATUS_MISSING,
        operator_state.STATUS_STALE,
        operator_state.STATUS_FAILED,
        operator_state.STATUS_PENDING,
    ):
        _assert_value_error(
            lambda non_current_status=non_current_status: operator_state.record_artifact(
                namespace_dir,
                run_id="run-current",
                profile="notify_no_key",
                artifact_namespace="notify_no_key",
                name="source_coverage_json",
                status=non_current_status,
                updated_at=_NOW,
            ),
            "requires skip_reason",
        )

    corrupted = dict(state)
    corrupted["artifacts"] = dict(state["artifacts"])
    corrupted["artifacts"]["source_coverage_json"] = {
        "status": operator_state.STATUS_SKIPPED,
        "run_id": "run-current",
        "path": None,
        "generated_at": _NOW.isoformat(),
        "reason": None,
    }
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), corrupted)
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is False
    assert loaded.error == "missing_artifact_reason:source_coverage_json"


def test_operator_state_is_schema_safe_and_keeps_paths_portable(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    core_path = namespace_dir / "event_core_opportunities.jsonl"
    run_row = _run_row()
    run_row.update(
        {
            "core_opportunity_store_path": core_path,
            "core_opportunity_write_success": True,
        }
    )
    state = operator_state.begin_run(namespace_dir, run_row, updated_at=_NOW)

    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []
    assert state["schema_id"] == "operator_state_v1"
    assert state["row_type"] == "event_alpha_operator_state"
    assert state["research_only"] is True
    assert state["no_send_rehearsal"] is True
    assert state["sent"] is False
    assert state["trades_created"] == 0
    assert state["paper_trades_created"] == 0
    assert state["normal_rsi_signal_rows_written"] == 0
    assert state["triggered_fade_created"] == 0
    assert state["artifacts"]["run_ledger"]["path"] == "event_alpha_runs.jsonl"
    assert state["artifacts"]["core_opportunities"]["path"] == "event_core_opportunities.jsonl"
    assert all(
        not Path(str(entry["path"])).is_absolute()
        for entry in state["artifacts"].values()
        if entry.get("path")
    )

    corrupted = json.loads(json.dumps(state))
    corrupted["manifest_status"] = "partial"
    corrupted["artifacts"]["run_ledger"]["path"] = "../outside.jsonl"
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), corrupted)
    invalid = operator_state.load_operator_state(namespace_dir)
    assert invalid.valid is False
    assert invalid.error in {"artifact_path_outside_namespace:run_ledger", "manifest_status_mismatch"}


def test_operator_state_resolves_repo_relative_run_paths_against_namespace(tmp_path):
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        namespace_dir = tmp_path / "event_fade_cache" / "notify_no_key"
        run_row = _run_row()
        run_row.update(
            {
                "core_opportunity_store_path": (
                    "event_fade_cache/notify_no_key/event_core_opportunities.jsonl"
                ),
                "core_opportunity_write_success": True,
            }
        )
        state = operator_state.begin_run(namespace_dir, run_row, updated_at=_NOW)
    finally:
        os.chdir(previous_cwd)

    assert state["artifacts"]["core_opportunities"]["path"] == "event_core_opportunities.jsonl"


def test_operator_state_reports_actual_guarded_send_facts(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    run_row = _run_row()
    run_row.update(
        {
            "send_requested": True,
            "send_attempted": True,
            "send_success": True,
            "send_items_delivered": 2,
        }
    )

    state = operator_state.begin_run(namespace_dir, run_row, updated_at=_NOW)

    assert state["no_send_rehearsal"] is False
    assert state["sent"] is True
    assert state["send_requested"] is True
    assert state["send_attempted"] is True
    assert state["send_success"] is True
    assert state["send_items_delivered"] == 2
    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []
    missing_sent = dict(state)
    missing_sent.pop("sent")
    assert "missing_required_field:sent" in schema_v1.validate_row_against_schema(
        missing_sent,
        "operator_state_v1",
    )


def test_operator_state_reports_partial_guarded_delivery_as_sent(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    run_row = _run_row()
    run_row.update(
        {
            "send_requested": True,
            "send_attempted": True,
            "send_success": False,
            "send_items_delivered": 1,
        }
    )

    state = operator_state.begin_run(namespace_dir, run_row, updated_at=_NOW)

    assert state["no_send_rehearsal"] is False
    assert state["sent"] is True
    assert state["send_success"] is False
    assert state["send_items_delivered"] == 1
    assert schema_v1.validate_row_against_schema(state, "operator_state_v1") == []


def test_operator_state_failed_live_attempt_is_not_a_no_send_rehearsal(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    run_row = _run_row()
    run_row.update(
        {
            "send_requested": True,
            "send_attempted": True,
            "send_success": False,
            "send_items_delivered": 0,
        }
    )

    state = operator_state.begin_run(namespace_dir, run_row, updated_at=_NOW)

    assert state["sent"] is False
    assert state["no_send_rehearsal"] is False
    assert state["send_requested"] is True
    assert state["send_attempted"] is True
    assert state["send_success"] is False
    assert state["send_items_delivered"] == 0
    assert operator_state.load_operator_state(namespace_dir).valid is True

    corrupted = dict(state, no_send_rehearsal=True)
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), corrupted)
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is False
    assert loaded.error == "no_send_fact_mismatch"


def test_operator_state_rejects_impossible_send_fact_combinations(tmp_path):
    cases = {
        "attempt_without_request": (
            {
                "send_requested": False,
                "send_attempted": True,
                "send_success": False,
                "send_items_delivered": 0,
            },
            "send_attempt_without_request",
        ),
        "success_without_delivery": (
            {
                "send_requested": True,
                "send_attempted": True,
                "send_success": True,
                "send_items_delivered": 0,
            },
            "send_success_fact_mismatch",
        ),
        "success_without_request_or_attempt": (
            {
                "send_requested": False,
                "send_attempted": False,
                "send_success": True,
                "send_items_delivered": 0,
            },
            "send_success_fact_mismatch",
        ),
        "delivery_without_attempt": (
            {
                "send_requested": True,
                "send_attempted": False,
                "send_success": False,
                "send_items_delivered": 1,
            },
            "schema_error:unsafe_side_effect_flag:sent",
        ),
    }

    for case_name, (send_facts, expected_error) in cases.items():
        namespace_dir = tmp_path / case_name
        state = operator_state.begin_run(
            namespace_dir,
            dict(_run_row(namespace=case_name), **send_facts),
            updated_at=_NOW,
        )
        assert state["send_items_delivered"] == send_facts["send_items_delivered"]
        loaded = operator_state.load_operator_state(namespace_dir)
        assert loaded.valid is False, case_name
        assert loaded.error == expected_error, case_name


def test_operator_state_selects_and_enforces_exact_latest_run_identity(tmp_path):
    context_profile = "notify_no_key"
    context_namespace = "notify_no_key"
    exact_old = dict(
        _run_row(run_id="run-old"),
        started_at="2026-07-11T10:00:00+00:00",
    )
    exact_new = dict(
        _run_row(run_id="run-new"),
        started_at="2026-07-11T11:00:00+00:00",
    )
    wrong_profile = dict(
        _run_row(run_id="run-wrong-profile"),
        profile="notify_llm_deep",
        started_at="2026-07-11T12:00:00+00:00",
    )
    wrong_namespace = dict(
        _run_row(namespace="other", run_id="run-wrong-namespace"),
        started_at="2026-07-11T13:00:00+00:00",
    )

    latest = operator_state.latest_matching_run(
        (wrong_namespace, exact_old, wrong_profile, exact_new),
        profile=context_profile,
        artifact_namespace=context_namespace,
    )
    assert latest is not None
    assert latest["run_id"] == "run-new"

    namespace_dir = tmp_path / context_namespace
    old_state = operator_state.begin_run(namespace_dir, exact_old, updated_at=_NOW)
    assert operator_state.state_matches_run(
        old_state,
        latest,
        profile=context_profile,
        artifact_namespace=context_namespace,
    ) is False
    current_state = operator_state.begin_run(namespace_dir, latest, updated_at=_NOW)
    assert operator_state.state_matches_run(
        current_state,
        latest,
        profile=context_profile,
        artifact_namespace=context_namespace,
    ) is True


def test_report_helpers_replace_valid_but_stale_operator_generation(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    context = SimpleNamespace(
        namespace_dir=namespace_dir,
        run_ledger_path=namespace_dir / "event_alpha_runs.jsonl",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_mode="event_alpha_cycle",
    )
    old_run = dict(
        _run_row(run_id="run-old"),
        started_at="2026-07-11T10:00:00+00:00",
    )
    new_run = dict(
        _run_row(run_id="run-new"),
        started_at="2026-07-11T11:00:00+00:00",
    )
    old_finished = datetime(2026, 7, 11, 10, 5, tzinfo=timezone.utc)
    new_finished = datetime(2026, 7, 11, 11, 5, tzinfo=timezone.utc)

    for ensure in (
        scanner_report_service._ensure_operator_state_from_latest_run,
        daily_report_service._ensure_daily_operator_state,
    ):
        operator_state.begin_run(namespace_dir, old_run, updated_at=old_finished)
        selected = ensure(context, (new_run,))
        assert selected is not None
        assert selected["run_id"] == "run-new"
        loaded = operator_state.load_operator_state(namespace_dir)
        assert loaded.valid is True
        assert loaded.state is not None
        assert loaded.state["run_id"] == "run-new"

        operator_state.begin_run(namespace_dir, new_run, updated_at=new_finished)
        assert ensure(context, (old_run,)) is None
        loaded = operator_state.load_operator_state(namespace_dir)
        assert loaded.valid is True
        assert loaded.state is not None
        assert loaded.state["run_id"] == "run-new"

    operator_state.begin_run(namespace_dir, old_run, updated_at=old_finished)
    selected = preview_service._ensure_preview_operator_state(context, new_run)
    assert selected is not None
    assert selected["run_id"] == "run-new"
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is True
    assert loaded.state is not None
    assert loaded.state["run_id"] == "run-new"
    operator_state.begin_run(namespace_dir, new_run, updated_at=new_finished)
    assert preview_service._ensure_preview_operator_state(context, old_run) is None
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is True
    assert loaded.state is not None
    assert loaded.state["run_id"] == "run-new"


def test_namespace_refresh_preserves_all_explicit_safety_policy_booleans(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_status.write_namespace_status(
        namespace_dir,
        {
            "namespace": "notify_no_key",
            "status": namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            "safe_for_send_readiness": True,
            "safe_for_burn_in_measurement": False,
            "safe_for_calibration": True,
        },
        now=_NOW,
    )
    operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    namespace_status.refresh_namespace_status(
        namespace_dir,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_mode="event_alpha_cycle",
        now=_NOW,
    )

    loaded = namespace_status.load_namespace_status(namespace_dir)
    assert loaded is not None
    assert loaded.safe_for_send_readiness is True
    assert loaded.safe_for_burn_in_measurement is False
    assert loaded.safe_for_calibration is True
    marker = json.loads(
        (namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME).read_text(encoding="utf-8")
    )
    assert schema_v1.validate_row_against_schema(marker, "namespace_status_v1") == []

    namespace_status.refresh_namespace_status(
        namespace_dir,
        profile="wrong-profile",
        artifact_namespace="wrong-namespace",
        run_mode="event_alpha_cycle",
        now=_NOW,
    )
    marker = json.loads(
        (namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME).read_text(encoding="utf-8")
    )
    assert marker["profile"] == "notify_no_key"
    assert marker["namespace"] == "notify_no_key"


def test_namespace_refresh_and_load_fail_closed_on_string_policy_values(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_status.write_namespace_status(
        namespace_dir,
        {
            "namespace": "notify_no_key",
            "status": namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            "safe_for_send_readiness": "false",
            "safe_for_burn_in_measurement": "true",
            "safe_for_calibration": "true",
        },
        now=_NOW,
    )
    operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    namespace_status.refresh_namespace_status(
        namespace_dir,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_mode="event_alpha_cycle",
        now=_NOW,
    )

    marker = json.loads(
        (namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME).read_text(encoding="utf-8")
    )
    assert marker["safe_for_send_readiness"] is False
    assert marker["safe_for_burn_in_measurement"] is False
    assert marker["safe_for_calibration"] is False
    loaded = namespace_status.load_namespace_status(namespace_dir)
    assert loaded is not None
    assert loaded.safe_for_send_readiness is False
    assert loaded.safe_for_burn_in_measurement is False
    assert loaded.safe_for_calibration is False


def test_corrupt_namespace_marker_blocks_send_readiness(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir(parents=True)
    (namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME).write_text("{", encoding="utf-8")

    loaded = namespace_status.load_namespace_status(namespace_dir)
    assert loaded is not None
    assert loaded.status == "invalid"
    assert loaded.safe_for_send_readiness is False
    blockers = send_readiness._namespace_send_readiness_blockers(
        resolved_preview_path=namespace_dir / "event_alpha_notification_preview.md",
        preview_path=None,
        artifact_namespace="notify_no_key",
    )
    assert blockers == [
        "artifact namespace status is invalid or unknown and blocked for send-readiness"
    ]


def test_namespace_marker_mappings_fail_closed_for_send_readiness(tmp_path):
    valid_base = {
        "schema_id": "namespace_status_v1",
        "schema_version": schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
        "row_type": "event_alpha_namespace_status",
        "namespace": "notify_no_key",
        "status": namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
        "safe_for_send_readiness": True,
    }
    cases = {
        "schema_invalid": {key: value for key, value in valid_base.items() if key != "namespace"},
        "wrong_schema_id": dict(valid_base, schema_id="notification_delivery_v1"),
        "wrong_schema_version": dict(valid_base, schema_version="event_alpha_schema_v0"),
        "wrong_row_type": dict(valid_base, row_type="not_a_namespace_status"),
        "copied_namespace": dict(valid_base, namespace="different_namespace"),
        "invalid_status": dict(valid_base, status="invalid"),
        "unknown_status": dict(valid_base, status=namespace_status.STATUS_UNKNOWN),
        "missing_status": {key: value for key, value in valid_base.items() if key != "status"},
    }

    for case_name, payload in cases.items():
        namespace_dir = tmp_path / case_name / "notify_no_key"
        namespace_dir.mkdir(parents=True)
        (namespace_dir / namespace_status.NAMESPACE_STATUS_FILENAME).write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

        loaded = namespace_status.load_namespace_status(namespace_dir)
        assert loaded is not None
        assert loaded.safe_for_send_readiness is False, case_name
        blockers = send_readiness._namespace_send_readiness_blockers(
            resolved_preview_path=namespace_dir / "event_alpha_notification_preview.md",
            preview_path=None,
            artifact_namespace="notify_no_key",
        )
        assert blockers, case_name
        if case_name in {"invalid_status", "unknown_status", "missing_status"}:
            assert blockers == [
                "artifact namespace status is invalid or unknown and blocked for send-readiness"
            ]
        if case_name == "copied_namespace":
            assert blockers == ["artifact namespace marker identity does not match its directory"]


def test_operator_doctor_rejects_stale_authority_and_invalid_existing_authority(tmp_path):
    for stale_status in ("stale", "STALE"):
        namespace_dir = tmp_path / f"stamp-{stale_status}"
        operator_state.begin_run(
            namespace_dir,
            _run_row(namespace=namespace_dir.name),
            updated_at=_NOW,
        )
        _assert_value_error(
            lambda namespace_dir=namespace_dir, stale_status=stale_status: operator_state.record_doctor_status(
                namespace_dir,
                run_id="run-current",
                profile="notify_no_key",
                artifact_namespace=namespace_dir.name,
                expected_revision=1,
                strict=True,
                schema_only=False,
                skip_api_checks=False,
                status=stale_status,
                checked_at=_NOW,
            ),
            "invalid completed doctor status",
        )

    namespace_dir = tmp_path / "corrupt-authority"
    state = operator_state.begin_run(
        namespace_dir,
        _run_row(namespace=namespace_dir.name),
        updated_at=_NOW,
    )
    corrupted = dict(state)
    corrupted["doctor"] = {
        "status": "STALE",
        "run_id": "run-current",
        "authoritative": True,
        "strict": True,
        "schema_only": False,
        "skip_api_checks": False,
        "verified_at": _NOW.isoformat(),
        "verified_revision": 1,
        "blocker_count": 0,
        "warning_count": 0,
    }
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), corrupted)
    loaded = operator_state.load_operator_state(namespace_dir)
    assert loaded.valid is False
    assert loaded.error == "doctor_authority_mode_mismatch"


def test_namespace_lifecycle_never_reports_policy_safe_with_stale_doctor(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_status.write_namespace_status(
        namespace_dir,
        {
            "namespace": "notify_no_key",
            "profile": "notify_no_key",
            "status": namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            "safe_for_send_readiness": True,
            "safe_for_burn_in_measurement": True,
            "safe_for_calibration": True,
        },
        now=_NOW,
    )
    operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)

    stale = namespace_lifecycle._namespace_row(namespace_dir)

    assert stale.current_doctor_status == "not_run"
    assert stale.safe_for_send_readiness is False
    assert stale.safe_for_burn_in_measurement is False
    assert stale.safe_for_calibration is False


def test_operator_state_invalidation_advances_revision_and_stales_doctor(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    _begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    verified = operator_state.record_doctor_status(
        namespace_dir,
        run_id="run-current",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        expected_revision=1,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        checked_at=_NOW,
    )

    _assert_value_error(
        lambda: operator_state.invalidate_operator_state(
            namespace_dir,
            reason="stale_retention_plan",
            expected_run_id="run-other",
            expected_revision=int(verified["revision"]),
            updated_at=_NOW,
        ),
        "run_id mismatch",
    )
    _assert_value_error(
        lambda: operator_state.invalidate_operator_state(
            namespace_dir,
            reason="stale_retention_plan",
            expected_run_id="run-current",
            expected_revision=int(verified["revision"]) - 1,
            updated_at=_NOW,
        ),
        "revision mismatch",
    )

    invalidated = operator_state.invalidate_operator_state(
        namespace_dir,
        reason="retention_mutation",
        expected_run_id="run-current",
        expected_revision=int(verified["revision"]),
        updated_at=_NOW,
    )

    assert invalidated["revision"] == verified["revision"] + 1
    assert invalidated["invalidation_reason"] == "retention_mutation"
    assert invalidated["doctor"]["status"] == "stale"
    assert invalidated["doctor"]["verified_revision"] is None
    assert schema_v1.validate_row_against_schema(invalidated, "operator_state_v1") == []


def test_doctor_blocks_wrong_preview_run_without_delivery_rows(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    run_ledger = namespace_dir / "event_alpha_runs.jsonl"
    run_ledger.parent.mkdir(parents=True)
    run_ledger.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    operator_state.begin_run(namespace_dir, _run_row(run_id="run-1"), updated_at=_NOW)
    preview_path = namespace_dir / "event_alpha_notification_preview.md"
    preview_path.write_text("# Event Alpha preview\nrun_id: run-10\n", encoding="utf-8")
    operator_state.record_artifact(
        namespace_dir,
        run_id="run-1",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        name="notification_preview",
        path=preview_path,
        updated_at=_NOW,
    )
    ctx = SimpleNamespace(
        namespace_dir=namespace_dir,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        latest_run_id="run-1",
        notification_deliveries=(),
        namespace_status=SimpleNamespace(
            status=namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            safe_for_burn_in_measurement=False,
        ),
        daily_burn_in_run={},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
    )
    blockers: list[str] = []
    warnings: list[str] = []

    operations.apply_checks(ctx, blockers, warnings)

    assert any("operator_notification_preview_run_mismatch" in item for item in blockers)


def test_doctor_blocks_missing_operator_state_for_selected_current_run(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir(parents=True)
    (namespace_dir / "event_alpha_runs.jsonl").write_text(
        '{"run_id":"run-current"}\n',
        encoding="utf-8",
    )
    ctx = SimpleNamespace(
        namespace_dir=namespace_dir,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        latest_run_id="run-current",
        notification_deliveries=(),
        namespace_status=SimpleNamespace(
            status=namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            safe_for_burn_in_measurement=False,
        ),
        daily_burn_in_run={},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
    )
    blockers: list[str] = []
    warnings: list[str] = []

    operations.apply_checks(ctx, blockers, warnings)

    assert any("operator_state_missing_for_latest_run=run-current" in item for item in blockers)


def test_doctor_custom_ledger_missing_operator_state_fails_closed(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir(parents=True)
    custom_ledger = tmp_path / "custom" / "current-runs.jsonl"
    custom_ledger.parent.mkdir(parents=True)
    custom_ledger.write_text('{"run_id":"run-current"}\n', encoding="utf-8")
    ctx = SimpleNamespace(
        namespace_dir=namespace_dir,
        run_ledger_path=custom_ledger,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        latest_run_id="run-current",
        notification_deliveries=(),
        namespace_status=SimpleNamespace(
            status=namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            safe_for_burn_in_measurement=False,
        ),
        daily_burn_in_run={},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
    )
    blockers: list[str] = []
    warnings: list[str] = []

    operations.apply_checks(ctx, blockers, warnings)

    assert any("operator_state_missing_for_latest_run=run-current" in item for item in blockers)
    assert not any("operator_state_missing_legacy_namespace" in item for item in warnings)


def test_operator_report_mutation_guard_and_fixed_writer_routes_fail_closed(tmp_path):
    import inspect

    from crypto_rsi_scanner.cli.services.scanner_parts import provider_preflights
    from crypto_rsi_scanner.event_alpha.artifacts import locks as event_alpha_locks

    context = SimpleNamespace(
        namespace_dir=tmp_path / "notify_no_key",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_mode="notification_burn_in",
        run_ledger_path=tmp_path / "notify_no_key" / "event_alpha_runs.jsonl",
        alert_store_path=tmp_path / "notify_no_key" / "event_alpha_alerts.jsonl",
        notification_runs_path=tmp_path / "notify_no_key" / "event_alpha_notification_runs.jsonl",
        feedback_path=tmp_path / "notify_no_key" / "event_alpha_feedback.jsonl",
        provider_health_path=tmp_path / "notify_no_key" / "event_provider_health.json",
        impact_hypothesis_store_path=tmp_path / "notify_no_key" / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=tmp_path / "notify_no_key" / "event_core_opportunities.jsonl",
        incident_store_path=tmp_path / "notify_no_key" / "event_incidents.jsonl",
        evidence_acquisition_path=tmp_path / "notify_no_key" / "event_evidence_acquisition.jsonl",
        research_cards_dir=tmp_path / "notify_no_key" / "research_cards",
    )
    held = event_alpha_locks.acquire_artifact_mutation_lock(
        context,
        run_id="active-writer",
        profile=context.profile,
        namespace=context.artifact_namespace,
        # This lock must be fresh relative to the mutation guard's real clock.
        # A fixed date eventually crosses the 24-hour stale-recovery boundary.
        now=datetime.now(timezone.utc),
    )
    assert held.owned is True
    called: list[bool] = []
    try:
        scanner_report_service._run_operator_report_mutation(
            context,
            "artifact-doctor-report",
            "artifact_doctor_report_skipped",
            lambda: called.append(True),
        )
    finally:
        assert event_alpha_locks.release_run_lock(held) is True
    assert called == []

    for function in (
        scanner_report_service.event_alpha_artifact_doctor_report,
        scanner_report_service.event_alpha_unlock_calendar_preflight_report,
        scanner_report_service.event_alpha_integrated_radar_calibration_report,
    ):
        assert "_run_operator_report_mutation" in inspect.getsource(function)
    for function in (
        provider_preflights.event_alpha_coinalyze_preflight_report,
        provider_preflights.event_alpha_coinalyze_no_send_rehearsal,
        provider_preflights.event_alpha_bybit_announcements_preflight_report,
        provider_preflights.event_alpha_bybit_announcements_no_send_rehearsal,
        provider_preflights.event_alpha_mark_namespace_stale,
    ):
        assert "_run_provider_artifact_mutation" in inspect.getsource(function)


def test_strict_artifact_doctor_exits_nonzero_on_blocked_or_skipped_result(tmp_path):
    from unittest.mock import patch

    context = SimpleNamespace(
        namespace_dir=tmp_path / "fixture",
        profile="fixture",
        artifact_namespace="fixture",
    )
    blocked = SimpleNamespace(status="BLOCKED", blockers=("schema.validation_errors",))
    warned = SimpleNamespace(status="WARN", blockers=())

    with (
        patch.object(scanner_report_service, "resolve_event_alpha_artifact_context_for_report", return_value=context),
        patch.object(scanner_report_service.config, "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT", False),
        patch.object(scanner_report_service, "_run_operator_report_mutation", return_value=blocked),
    ):
        try:
            scanner_report_service.event_alpha_artifact_doctor_report(strict=True)
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("strict BLOCKED doctor must exit nonzero")

    with (
        patch.object(scanner_report_service, "resolve_event_alpha_artifact_context_for_report", return_value=context),
        patch.object(scanner_report_service.config, "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT", False),
        patch.object(scanner_report_service, "_run_operator_report_mutation", return_value=None),
    ):
        try:
            scanner_report_service.event_alpha_artifact_doctor_report(strict=True)
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("strict skipped doctor must exit nonzero")

    with (
        patch.object(scanner_report_service, "resolve_event_alpha_artifact_context_for_report", return_value=context),
        patch.object(scanner_report_service.config, "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT", False),
        patch.object(scanner_report_service, "_run_operator_report_mutation", return_value=warned),
    ):
        scanner_report_service.event_alpha_artifact_doctor_report(strict=True)

    unstamped = scanner_report_service._guarded_report_writes.ArtifactDoctorExecution(
        warned,
        False,
    )
    with (
        patch.object(scanner_report_service, "resolve_event_alpha_artifact_context_for_report", return_value=context),
        patch.object(scanner_report_service.config, "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT", False),
        patch.object(scanner_report_service, "_run_operator_report_mutation", return_value=unstamped),
    ):
        try:
            scanner_report_service.event_alpha_artifact_doctor_report(strict=True)
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("strict doctor without an exact-revision stamp must exit nonzero")

    race_context = SimpleNamespace(
        namespace_dir=tmp_path / "fixture",
        profile="fixture",
        artifact_namespace="fixture",
        run_mode="fixture",
    )
    with (
        patch.object(
            scanner_report_service._operator_state,
            "load_operator_state",
            return_value=SimpleNamespace(valid=True, state={"revision": 3}),
        ),
        patch.object(scanner_report_service._operator_state, "state_matches_run", return_value=True),
        patch.object(
            scanner_report_service._operator_state,
            "record_doctor_status",
            side_effect=ValueError("operator state revision mismatch"),
        ),
    ):
        recorded = scanner_report_service._record_operator_doctor_result(
            race_context,
            warned,
            run_row={"run_id": "run-race", "run_mode": "fixture"},
            expected_revision=3,
            strict=True,
            schema_only=False,
            skip_api_checks=False,
        )
    assert recorded is False


def test_namespace_lifecycle_writer_fails_closed_on_active_namespace_mutation(tmp_path):
    from crypto_rsi_scanner.event_alpha.artifacts import locks as event_alpha_locks

    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir(parents=True)
    context = SimpleNamespace(namespace_dir=namespace_dir)
    held = event_alpha_locks.acquire_artifact_mutation_lock(
        context,
        run_id="active-writer",
        namespace="notify_no_key",
        now=_NOW,
    )
    assert held.owned is True
    try:
        try:
            namespace_lifecycle.write_namespace_lifecycle_report(tmp_path, now=_NOW)
        except RuntimeError as exc:
            assert "namespace lifecycle report blocked" in str(exc)
        else:
            raise AssertionError("expected lifecycle writer to fail closed")
    finally:
        assert event_alpha_locks.release_run_lock(held) is True
    assert not (tmp_path / namespace_lifecycle.REGISTRY_FILENAME).exists()


def test_provider_rechecks_stale_namespace_inside_held_mutation_action(tmp_path):
    import inspect
    from unittest.mock import patch

    from crypto_rsi_scanner.cli.services.scanner_parts import provider_preflights
    from crypto_rsi_scanner.event_alpha.artifacts import locks as event_alpha_locks

    base = tmp_path / "coinalyze_preflight"
    context = SimpleNamespace(
        namespace_dir=base,
        profile="notify_llm_deep",
        artifact_namespace="coinalyze_preflight",
        run_mode="provider_preflight",
        run_ledger_path=base / "event_alpha_runs.jsonl",
        alert_store_path=base / "event_alpha_alerts.jsonl",
        notification_runs_path=base / "event_alpha_notification_runs.jsonl",
        feedback_path=base / "event_alpha_feedback.jsonl",
        provider_health_path=base / "event_provider_health.json",
        impact_hypothesis_store_path=base / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=base / "event_core_opportunities.jsonl",
        incident_store_path=base / "event_incidents.jsonl",
        evidence_acquisition_path=base / "event_evidence_acquisition.jsonl",
        research_cards_dir=base / "research_cards",
    )
    with patch.dict(
        os.environ,
        {"ALLOW_STALE_NAMESPACE_WRITE": "", "RSI_EVENT_ALPHA_ALLOW_STALE_NAMESPACE_WRITE": ""},
    ):
        assert provider_preflights._coinalyze_namespace_write_blocked(
            context,
            suggested_namespace="coinalyze_preflight",
        ) is False
        namespace_status.mark_namespace_stale(
            base,
            namespace="coinalyze_preflight",
            reason="became stale between outer check and lock",
            now=_NOW,
        )
        with event_alpha_locks.artifact_mutation_guard(
            context,
            profile=context.profile,
            namespace=context.artifact_namespace,
            command="coinalyze-preflight-report",
            now=_NOW,
        ) as mutation_lock:
            assert mutation_lock.owned is True
            with patch.object(
                provider_preflights.event_coinalyze_preflight,
                "build_preflight_report",
                side_effect=AssertionError("stale namespace must block before build/write"),
            ) as build:
                provider_preflights._event_alpha_coinalyze_preflight_report_locked(
                    context,
                    smoke_mode=True,
                    allow_live_preflight=False,
                )
                assert build.call_count == 0

    for function in (
        provider_preflights._event_alpha_coinalyze_preflight_report_locked,
        provider_preflights._event_alpha_coinalyze_no_send_rehearsal_locked,
        provider_preflights._event_alpha_bybit_announcements_preflight_report_locked,
        provider_preflights._event_alpha_bybit_announcements_no_send_rehearsal_locked,
    ):
        assert "_namespace_write_blocked" in inspect.getsource(function)


def test_namespace_lifecycle_fails_closed_if_child_set_changes_after_locking(tmp_path):
    from unittest.mock import patch

    (tmp_path / "existing").mkdir()
    original = namespace_lifecycle._lifecycle_child_dirs
    calls = 0

    def changing_children(base: Path) -> tuple[Path, ...]:
        nonlocal calls
        calls += 1
        if calls == 2:
            (base / "arrived_during_locking").mkdir()
        return original(base)

    with patch.object(namespace_lifecycle, "_lifecycle_child_dirs", side_effect=changing_children):
        try:
            namespace_lifecycle.write_namespace_lifecycle_report(tmp_path, now=_NOW)
        except RuntimeError as exc:
            assert "namespace set changed while locks were acquired" in str(exc)
        else:
            raise AssertionError("expected lifecycle namespace-set race to fail closed")
    assert not (tmp_path / namespace_lifecycle.REGISTRY_FILENAME).exists()


def test_doctor_blocks_operator_state_profile_mismatch(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    run_ledger = namespace_dir / "event_alpha_runs.jsonl"
    run_ledger.parent.mkdir(parents=True)
    run_ledger.write_text('{"run_id":"run-current"}\n', encoding="utf-8")
    state = operator_state.begin_run(namespace_dir, _run_row(), updated_at=_NOW)
    state["profile"] = "notify_llm_deep"
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace_dir), state)
    ctx = SimpleNamespace(
        namespace_dir=namespace_dir,
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        latest_run_id="run-current",
        notification_deliveries=(),
        namespace_status=SimpleNamespace(
            status=namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            safe_for_burn_in_measurement=False,
        ),
        daily_burn_in_run={},
        candidate_mode_manifest={},
        burn_in_scorecard={},
        source_yield_report={},
        daily_review_inbox={},
        burn_in_archive_manifest={},
    )
    blockers: list[str] = []
    warnings: list[str] = []

    operations.apply_checks(ctx, blockers, warnings)

    assert any("operator_state_profile_mismatch" in item for item in blockers)
