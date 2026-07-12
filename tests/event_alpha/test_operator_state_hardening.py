"""Narrow fail-closed regressions for operator-state fingerprint authority."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import fingerprints, operator_state


_NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def _run_row(*, namespace: str = "notify_no_key") -> dict[str, object]:
    return {
        "run_id": "run-current",
        "profile": "notify_no_key",
        "artifact_namespace": namespace,
        "run_mode": "event_alpha_cycle",
    }


def _begin_run(namespace_dir, row):
    ledger = namespace_dir / "event_alpha_runs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return operator_state.begin_run(
        namespace_dir,
        row,
        run_ledger_path=ledger,
        updated_at=_NOW,
    )


def test_fingerprint_metadata_rejects_deprecated_and_kind_incoherent_run_fields():
    file_metadata = fingerprints.fingerprint_bytes(b"artifact")

    assert fingerprints.fingerprint_metadata_error(
        {"run_row_sha256": "a" * 64}
    ) == "fingerprint_run_row_sha256_deprecated"
    assert fingerprints.fingerprint_metadata_error(
        dict(file_metadata, run_row_identity={"run_id": "run"})
    ) == "fingerprint_run_row_fields_invalid_for_kind"
    assert fingerprints.fingerprint_metadata_error(
        dict(file_metadata, run_row_match_count=1)
    ) == "fingerprint_run_row_fields_invalid_for_kind"


def test_canonical_fingerprints_wrap_unencodable_surrogates_without_payload_leak():
    unsafe = {"run_id": "run-\ud800"}

    for fingerprint_call in (
        lambda: fingerprints.canonical_json_bytes(unsafe),
        lambda: fingerprints.canonical_run_row_fingerprint(unsafe),
    ):
        with pytest.raises(
            fingerprints.FingerprintError,
            match="^canonical_json_failed:UnicodeEncodeError$",
        ) as raised:
            fingerprint_call()
        assert "run-" not in str(raised.value)


def test_run_ledger_fingerprint_rejects_duplicate_keys_and_non_string_identity(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    identity = {
        "run_id": "run-current",
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
    }
    ledger.write_text(
        '{"run_id":"run-current","profile":"notify_no_key",'
        '"artifact_namespace":"notify_no_key","nested":{"key":1,"key":2}}\n',
        encoding="utf-8",
    )
    with pytest.raises(
        fingerprints.FingerprintError,
        match="^run_ledger_duplicate_object_key:1$",
    ):
        fingerprints.fingerprint_run_ledger_row(ledger, identity)

    for field, invalid in (("run_id", True), ("profile", 7), ("artifact_namespace", False)):
        invalid_identity = dict(identity, **{field: invalid})
        ledger.write_text(
            json.dumps(invalid_identity, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(fingerprints.FingerprintError, match="^run_row_identity_incomplete$"):
            fingerprints.fingerprint_run_ledger_row(ledger, invalid_identity)

    ledger.write_text(
        json.dumps(dict(identity, run_id=7), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        fingerprints.FingerprintError,
        match="^run_row_match_count_mismatch:0$",
    ):
        fingerprints.fingerprint_run_ledger_row(ledger, dict(identity, run_id="7"))

    for field in identity:
        for padded in (f" {identity[field]}", f"{identity[field]} ", f"\u00a0{identity[field]}"):
            invalid_identity = dict(identity, **{field: padded})
            ledger.write_text(
                json.dumps(invalid_identity, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            with pytest.raises(fingerprints.FingerprintError, match="^run_row_identity_incomplete$"):
                fingerprints.fingerprint_run_ledger_row(ledger, invalid_identity)


def test_begin_run_rejects_explicit_non_string_or_empty_identity(tmp_path):
    valid = _run_row()
    for field in ("run_id", "profile", "artifact_namespace"):
        for invalid in (True, 7, None, ""):
            with pytest.raises(ValueError, match=f"operator state requires string {field}"):
                operator_state.begin_run(
                    tmp_path / f"{field}-{invalid!s}",
                    dict(valid, **{field: invalid}),
                    updated_at=_NOW,
                )
        for padded in (f" {valid[field]}", f"{valid[field]} ", f"\u00a0{valid[field]}"):
            with pytest.raises(ValueError, match=f"operator state requires string {field}"):
                operator_state.begin_run(
                    tmp_path / f"{field}-whitespace",
                    dict(valid, **{field: padded}),
                    updated_at=_NOW,
                )

    defaulted = operator_state.begin_run(
        tmp_path / "defaulted",
        {"run_id": "run-defaults"},
        updated_at=_NOW,
    )
    assert defaulted["profile"] == "default"
    assert defaulted["artifact_namespace"] == "defaulted"


def test_record_doctor_status_rejects_coerced_or_negative_integer_inputs(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    initial = _begin_run(namespace_dir, _run_row())
    common = {
        "run_id": "run-current",
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
        "expected_revision": 1,
        "strict": True,
        "schema_only": False,
        "skip_api_checks": False,
        "status": "OK",
        "blocker_count": 0,
        "warning_count": 0,
        "checked_at": _NOW,
    }
    for field in ("expected_revision", "blocker_count", "warning_count"):
        for invalid in (True, "1", -1):
            arguments = dict(common, **{field: invalid})
            with pytest.raises(ValueError, match=f"{field} must be a non-negative integer"):
                operator_state.record_doctor_status(namespace_dir, **arguments)

    unchanged = operator_state.load_operator_state(namespace_dir)
    assert unchanged.valid is True
    assert unchanged.state == initial
    stamped = operator_state.record_doctor_status(
        namespace_dir,
        **dict(common, blocker_count=2, warning_count=3),
    )
    assert stamped["doctor"]["blocker_count"] == 2
    assert stamped["doctor"]["warning_count"] == 3


def test_authoritative_doctor_requires_exact_nested_types(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    _begin_run(namespace_dir, _run_row())
    authoritative = operator_state.record_doctor_status(
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
    cases = (
        ("status", 1, "invalid_doctor_status"),
        ("verified_revision", "1", "doctor_authority_invalid_verified_revision"),
        ("verified_revision", True, "doctor_authority_invalid_verified_revision"),
        ("blocker_count", "0", "doctor_authority_invalid_blocker_count"),
        ("blocker_count", -1, "doctor_authority_invalid_blocker_count"),
        ("warning_count", False, "doctor_authority_invalid_warning_count"),
    )
    for field, invalid, expected_error in cases:
        corrupted = json.loads(json.dumps(authoritative))
        corrupted["doctor"][field] = invalid
        operator_state.write_json_atomic(
            operator_state.operator_state_path(namespace_dir),
            corrupted,
        )
        loaded = operator_state.load_operator_state(namespace_dir)
        assert loaded.valid is False
        assert loaded.error == expected_error


def test_legacy_fingerprints_downgrade_authority_in_memory_without_rewriting(tmp_path):
    for legacy_kind in ("fingerprintless", "sha_only"):
        namespace_dir = tmp_path / legacy_kind
        state = _begin_run(namespace_dir, _run_row(namespace=legacy_kind))
        entry = state["artifacts"]["run_ledger"]
        digest = entry["sha256"]
        for field in (
            *fingerprints.FINGERPRINT_FIELDS,
            "run_row_identity",
            "run_row_match_count",
        ):
            entry.pop(field, None)
        if legacy_kind == "sha_only":
            entry["sha256"] = digest
        state["doctor"] = {
            "status": "OK",
            "run_id": "run-current",
            "authoritative": True,
            "strict": True,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": _NOW.isoformat(),
            "verified_revision": state["revision"],
            "blocker_count": 0,
            "warning_count": 0,
        }
        path = operator_state.operator_state_path(namespace_dir)
        operator_state.write_json_atomic(path, state)
        persisted = path.read_bytes()

        loaded = operator_state.load_operator_state(namespace_dir)

        assert loaded.valid is True
        assert loaded.state is not None
        assert loaded.state["doctor"]["status"] == "stale"
        assert loaded.state["doctor"]["authoritative"] is False
        assert loaded.state["doctor"]["verified_revision"] is None
        assert path.read_bytes() == persisted


def test_operator_state_loader_never_follows_leaf_symlink(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir()
    target = tmp_path / "outside-state.json"
    target.write_text('{}\n', encoding="utf-8")
    path = operator_state.operator_state_path(namespace_dir)
    path.symlink_to(target)

    loaded = operator_state.load_operator_state(namespace_dir)

    assert loaded.exists is True
    assert loaded.valid is False
    assert loaded.error == "symlink_not_allowed"


def test_operator_artifact_resolution_never_falls_back_to_same_basename(tmp_path):
    namespace_dir = tmp_path / "notify_no_key"
    _begin_run(namespace_dir, _run_row())
    root_artifact = namespace_dir / "coverage.json"
    root_artifact.write_text('{"root":true}\n', encoding="utf-8")
    declared = namespace_dir / "missing" / "coverage.json"

    state = operator_state.record_artifact(
        namespace_dir,
        run_id="run-current",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        name="source_coverage_json",
        path=declared,
        updated_at=_NOW,
    )

    entry = state["artifacts"]["source_coverage_json"]
    assert entry["status"] == operator_state.STATUS_MISSING
    assert entry["path"] == "missing/coverage.json"
    assert entry["reason"] == "artifact_path_missing_for_fingerprint"
    assert state["manifest_status"] == "incoherent"
    with pytest.raises(ValueError, match="manifest is not complete"):
        operator_state.record_doctor_status(
            namespace_dir,
            run_id="run-current",
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            expected_revision=2,
            strict=True,
            schema_only=False,
            skip_api_checks=False,
            status="OK",
            checked_at=_NOW,
        )
