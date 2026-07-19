"""Fixture-only Tokenomist v5 immutable capture regressions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.tokenomist_v5_capture import (
    CAPTURE_MODE_FIXTURE,
    CAPTURE_MODE_LIVE,
    TokenomistV5CaptureError,
    persist_capture,
    prepare_capture,
    run_fixture_capture_smoke,
    validate_capture,
)
from crypto_rsi_scanner.event_alpha.operations import tokenomist_v5_capture
from crypto_rsi_scanner.event_alpha.namespace import lifecycle


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_discovery"
    / "tokenomist_unlock_events_v5_capture.json"
)


def _source() -> bytes:
    return FIXTURE.read_bytes()


def _persist(base: Path, source: bytes | None = None) -> dict[str, object]:
    return persist_capture(
        base,
        _source() if source is None else source,
        capture_mode=CAPTURE_MODE_FIXTURE,
        confirm=True,
    )


def test_prepare_closes_fixture_without_authority_or_io() -> None:
    prepared = prepare_capture(_source(), capture_mode=CAPTURE_MODE_FIXTURE)

    assert prepared.summary["status"] == "complete"
    assert prepared.summary["coverage_complete"] is True
    assert prepared.summary["result_status"] == "observed"
    assert prepared.summary["accepted_unlock_event_count"] == 1
    assert prepared.summary["artifact_count"] == 5
    assert prepared.summary["exact_source_bytes_retained"] is True
    assert prepared.summary["fixture_synthetic"] is True
    assert prepared.summary["provider_calls_recorded"] == 0
    assert prepared.summary["credentials_read"] == 0
    assert prepared.summary["environment_reads"] == 0
    assert prepared.summary["input_quality_eligible"] is False
    assert prepared.summary["source_authority_eligible"] is False
    assert prepared.summary["campaign_attached"] is False
    assert prepared.summary["dashboard_authority_eligible"] is False
    assert prepared.summary["protocol_v2_evidence_eligible"] is False
    assert prepared.summary["latest_pointer_published"] is False
    assert prepared.summary["writes_performed"] is False


def test_live_capture_mode_is_explicitly_unimplemented() -> None:
    with pytest.raises(TokenomistV5CaptureError, match="live_transport_not_implemented"):
        prepare_capture(_source(), capture_mode=CAPTURE_MODE_LIVE)


def test_persistence_requires_confirmation_and_leaves_no_namespace(tmp_path: Path) -> None:
    with pytest.raises(
        TokenomistV5CaptureError, match="explicit_confirmation_required"
    ):
        persist_capture(
            tmp_path,
            _source(),
            capture_mode=CAPTURE_MODE_FIXTURE,
        )
    assert list(tmp_path.iterdir()) == []


def test_persist_and_doctor_rederive_exact_closed_artifact_set(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    namespace = str(result["artifact_namespace"])
    directory = tmp_path / namespace

    assert result["created"] is True
    assert result["strict_doctor_status"] == "pass"
    assert {path.name for path in directory.iterdir()} == {
        "exact_fixture_capture.json",
        "request_ledger.json",
        "normalized_snapshot.json",
        "capture_manifest.json",
        "capture_completion_receipt.json",
    }
    assert (directory / "exact_fixture_capture.json").read_bytes() == _source()
    ledger = json.loads((directory / "request_ledger.json").read_text())
    snapshot = json.loads((directory / "normalized_snapshot.json").read_text())
    manifest = json.loads((directory / "capture_manifest.json").read_text())
    receipt = json.loads((directory / "capture_completion_receipt.json").read_text())
    assert ledger["request"] == json.loads(_source())["request"]
    assert ledger["request_identity_sha256"] == snapshot["request_identity_sha256"]
    assert ledger["provider_response_sha256"] == snapshot["provider_response_sha256"]
    assert snapshot["unlock_events"][0]["symbol"] == "TESTV5"
    assert snapshot["unlock_events"][0]["unlock_value_to_market_cap_unit"] == (
        "percent_points"
    )
    assert [row["name"] for row in manifest["artifacts"]] == [
        "exact_fixture_capture.json",
        "request_ledger.json",
        "normalized_snapshot.json",
    ]
    assert receipt["manifest"]["sha256"]
    assert receipt["latest_pointer_published"] is False
    assert receipt["genuine_provider_bytes_retention_approved"] is False
    assert validate_capture(tmp_path, namespace)["capture_id"] == result["capture_id"]


def test_identical_capture_is_idempotent(tmp_path: Path) -> None:
    first = _persist(tmp_path)
    second = _persist(tmp_path)

    assert second["artifact_namespace"] == first["artifact_namespace"]
    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["canonical_capture_reused"] is True
    assert second["writes_performed"] is False
    assert second["staging_writes_performed"] is False
    assert second["retained_staging_quarantine"] is False
    assert second["retained_staging_quarantine_name"] is None
    assert second["retained_staging_artifact_count"] == 0
    assert second["retained_staging_artifact_names"] == []


def test_existing_namespace_reuse_requires_full_capture_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _persist(tmp_path)
    original = tokenomist_v5_capture.prepare_capture
    actual = original(_source(), capture_mode=CAPTURE_MODE_FIXTURE)
    replacement_digit = "0" if actual.capture_id[12] != "0" else "1"
    collision_id = (
        actual.capture_id[:12] + replacement_digit + actual.capture_id[13:]
    )
    collision = replace(
        actual,
        capture_id=collision_id,
        summary={**actual.summary, "capture_id": collision_id},
    )
    calls = 0

    def colliding_prepare(source_bytes: bytes, *, capture_mode: str) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            return collision
        return original(source_bytes, capture_mode=capture_mode)

    monkeypatch.setattr(tokenomist_v5_capture, "prepare_capture", colliding_prepare)
    with pytest.raises(TokenomistV5CaptureError, match="capture_identity_collision"):
        _persist(tmp_path)

    assert collision.namespace == first["artifact_namespace"]
    assert collision.capture_id[:12] == actual.capture_id[:12]
    assert collision.capture_id != actual.capture_id


def test_race_reuse_requires_complete_incoming_payload_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _persist(tmp_path)
    namespace = str(first["artifact_namespace"])
    original_prepare = tokenomist_v5_capture.prepare_capture
    original_exists = tokenomist_v5_capture._namespace_exists_at
    actual = original_prepare(_source(), capture_mode=CAPTURE_MODE_FIXTURE)
    changed_payloads = tuple(
        (name, raw + b" " if name == "request_ledger.json" else raw)
        for name, raw in actual.payloads
    )
    collision = replace(actual, payloads=changed_payloads)
    prepare_calls = 0
    exists_calls = 0

    def colliding_prepare(source_bytes: bytes, *, capture_mode: str) -> object:
        nonlocal prepare_calls
        prepare_calls += 1
        if prepare_calls == 1:
            return collision
        return original_prepare(source_bytes, capture_mode=capture_mode)

    def miss_then_find(base_fd: int, candidate: str) -> bool:
        nonlocal exists_calls
        if candidate == namespace:
            exists_calls += 1
            if exists_calls == 1:
                return False
        return original_exists(base_fd, candidate)

    monkeypatch.setattr(tokenomist_v5_capture, "prepare_capture", colliding_prepare)
    monkeypatch.setattr(tokenomist_v5_capture, "_namespace_exists_at", miss_then_find)
    with pytest.raises(TokenomistV5CaptureError, match="capture_identity_collision"):
        _persist(tmp_path)

    assert validate_capture(tmp_path, namespace)["strict_doctor_status"] == "pass"


def test_exact_source_mutation_fails_full_rederivation(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    source = tmp_path / str(result["artifact_namespace"]) / "exact_fixture_capture.json"
    source.write_bytes(source.read_bytes().replace(b"TESTV5", b"TESTV6", 1))

    with pytest.raises(TokenomistV5CaptureError, match="capture_identity_invalid"):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_derived_artifact_mutation_fails_full_rederivation(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    snapshot = tmp_path / str(result["artifact_namespace"]) / "normalized_snapshot.json"
    snapshot.write_bytes(snapshot.read_bytes().replace(b"TESTV5", b"TESTV6", 1))

    with pytest.raises(
        TokenomistV5CaptureError,
        match="capture_artifact_drift:normalized_snapshot.json",
    ):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_extra_symlink_and_hardlink_leaves_fail_closed(tmp_path: Path) -> None:
    first_root = tmp_path / "extra_case"
    first_root.mkdir()
    first = _persist(first_root)
    first_dir = first_root / str(first["artifact_namespace"])
    (first_dir / "unexpected.json").write_text("{}\n")
    with pytest.raises(TokenomistV5CaptureError, match="capture_artifact_set_invalid"):
        validate_capture(first_root, str(first["artifact_namespace"]))

    second_root = tmp_path / "symlink_case"
    second_root.mkdir()
    second = _persist(second_root)
    second_dir = second_root / str(second["artifact_namespace"])
    snapshot = second_dir / "normalized_snapshot.json"
    snapshot.unlink()
    snapshot.symlink_to(FIXTURE)
    with pytest.raises(TokenomistV5CaptureError, match="capture_artifact_leaf_invalid"):
        validate_capture(second_root, str(second["artifact_namespace"]))

    third_root = tmp_path / "hardlink_case"
    third_root.mkdir()
    third = _persist(third_root)
    third_dir = third_root / str(third["artifact_namespace"])
    ledger = third_dir / "request_ledger.json"
    ledger.unlink()
    ledger.hardlink_to(third_dir / "normalized_snapshot.json")
    with pytest.raises(TokenomistV5CaptureError, match="capture_artifact_leaf_invalid"):
        validate_capture(third_root, str(third["artifact_namespace"]))


def test_secret_like_fixture_content_is_rejected_before_write(tmp_path: Path) -> None:
    source = json.loads(_source())
    source["response"]["data"][0]["dataSource"] = "sk-proj-abcdefghijklmnop"
    raw = (json.dumps(source) + "\n").encode()

    with pytest.raises(
        TokenomistV5CaptureError, match="capture_secret_or_auth_material_rejected"
    ):
        _persist(tmp_path, raw)
    assert list(tmp_path.iterdir()) == []


def test_escaped_secret_is_rejected_after_json_decoding(tmp_path: Path) -> None:
    source = json.loads(_source())
    source["response"]["data"][0]["dataSource"] = "sk-proj-abcdefghijklmnop"
    text = json.dumps(source).replace("sk-proj", r"sk-\u0070roj") + "\n"
    raw = text.encode()
    assert b"sk-proj" not in raw

    with pytest.raises(
        TokenomistV5CaptureError, match="capture_secret_or_auth_material_rejected"
    ):
        _persist(tmp_path, raw)
    assert list(tmp_path.iterdir()) == []


def test_nul_content_and_artifact_base_paths_are_explicitly_rejected(
    tmp_path: Path,
) -> None:
    source = json.loads(_source())
    source["response"]["data"][0]["dataSource"] = "embedded\x00nul"
    escaped = (json.dumps(source) + "\n").encode()
    assert b"\\u0000" in escaped

    with pytest.raises(TokenomistV5CaptureError, match="capture_nul_rejected"):
        prepare_capture(escaped, capture_mode=CAPTURE_MODE_FIXTURE)
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_nul_rejected"):
        persist_capture(
            Path(f"{tmp_path}\x00replaced"),
            _source(),
            capture_mode=CAPTURE_MODE_FIXTURE,
            confirm=True,
        )


def test_duplicate_event_identity_is_rejected() -> None:
    source = json.loads(_source())
    source["response"]["data"].append(source["response"]["data"][0])
    source["response"]["metadata"].update({"total": 2, "totalPages": 1})

    with pytest.raises(TokenomistV5CaptureError, match="capture_duplicate_event_identity"):
        prepare_capture((json.dumps(source) + "\n").encode(), capture_mode=CAPTURE_MODE_FIXTURE)


def test_healthy_empty_and_partial_coverage_remain_distinct() -> None:
    empty = json.loads(_source())
    empty["response"]["metadata"].update({"total": 0, "totalPages": 0})
    empty["response"]["data"] = []
    empty_prepared = prepare_capture(
        (json.dumps(empty) + "\n").encode(), capture_mode=CAPTURE_MODE_FIXTURE
    )
    assert empty_prepared.summary["coverage_status"] == "complete"
    assert empty_prepared.summary["coverage_complete"] is True
    assert empty_prepared.summary["result_status"] == "healthy_empty"
    assert empty_prepared.summary["accepted_unlock_event_count"] == 0

    partial = json.loads(_source())
    partial["request"]["page_size"] = 1
    partial["response"]["metadata"].update(
        {"pageSize": 1, "total": 2, "totalPages": 2}
    )
    partial_prepared = prepare_capture(
        (json.dumps(partial) + "\n").encode(), capture_mode=CAPTURE_MODE_FIXTURE
    )
    assert partial_prepared.summary["coverage_status"] == "partial_page"
    assert partial_prepared.summary["coverage_complete"] is False
    assert partial_prepared.summary["result_status"] == "partial"


def test_persisted_healthy_empty_and_partial_captures_pass_strict_doctor(
    tmp_path: Path,
) -> None:
    empty = json.loads(_source())
    empty["response"]["metadata"].update({"total": 0, "totalPages": 0})
    empty["response"]["data"] = []
    empty_base = tmp_path / "empty"
    empty_base.mkdir()
    empty_result = _persist(
        empty_base,
        (json.dumps(empty) + "\n").encode(),
    )
    empty_doctor = validate_capture(
        empty_base,
        str(empty_result["artifact_namespace"]),
    )
    assert empty_doctor["result_status"] == "healthy_empty"
    assert empty_doctor["coverage_status"] == "complete"
    assert empty_doctor["strict_doctor_status"] == "pass"

    partial = json.loads(_source())
    partial["request"]["page_size"] = 1
    partial["response"]["metadata"].update(
        {"pageSize": 1, "total": 2, "totalPages": 2}
    )
    partial_base = tmp_path / "partial"
    partial_base.mkdir()
    partial_result = _persist(
        partial_base,
        (json.dumps(partial) + "\n").encode(),
    )
    partial_doctor = validate_capture(
        partial_base,
        str(partial_result["artifact_namespace"]),
    )
    assert partial_doctor["result_status"] == "partial"
    assert partial_doctor["coverage_status"] == "partial_page"
    assert partial_doctor["strict_doctor_status"] == "pass"


def test_nonfinite_and_deep_json_fail_with_stable_reasons() -> None:
    nonfinite = json.loads(_source())
    nonfinite["response"]["data"][0]["cliffUnlocks"]["cliffAmount"] = float("nan")
    with pytest.raises(TokenomistV5CaptureError, match="capture_json_nonfinite_rejected"):
        prepare_capture(
            (json.dumps(nonfinite) + "\n").encode(), capture_mode=CAPTURE_MODE_FIXTURE
        )

    deep: object = "end"
    for _ in range(40):
        deep = {"value": deep}
    source = json.loads(_source())
    source["deep"] = deep
    with pytest.raises(TokenomistV5CaptureError, match="capture_json_depth_bound_exceeded"):
        prepare_capture(
            (json.dumps(source) + "\n").encode(), capture_mode=CAPTURE_MODE_FIXTURE
        )


def test_strict_doctor_rejects_deep_mutated_ledger_with_stable_error(
    tmp_path: Path,
) -> None:
    result = _persist(tmp_path)
    ledger = tmp_path / str(result["artifact_namespace"]) / "request_ledger.json"
    ledger.write_bytes((b'{"nested":' * 1500) + b"0" + (b"}" * 1500) + b"\n")

    with pytest.raises(
        TokenomistV5CaptureError,
        match="capture_(ledger_invalid|json_depth_bound_exceeded)",
    ):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_file_snapshot_identity_includes_ctime(tmp_path: Path) -> None:
    source = tmp_path / "snapshot.json"
    source.write_bytes(b"{}\n")
    before = source.stat()
    os.chmod(source, 0o640)
    os.chmod(source, before.st_mode & 0o777)
    after = source.stat()

    assert before.st_dev == after.st_dev
    assert before.st_ino == after.st_ino
    assert before.st_mode == after.st_mode
    assert before.st_size == after.st_size
    assert before.st_mtime_ns == after.st_mtime_ns
    assert before.st_ctime_ns != after.st_ctime_ns
    assert tokenomist_v5_capture._same_file_snapshot(before, after) is False


def test_duplicate_json_keys_and_total_bundle_bound_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = _source().replace(
        b'"schema_version": 1,',
        b'"schema_version": 1, "schema_version": 1,',
        1,
    )
    with pytest.raises(TokenomistV5CaptureError, match="capture_response_contract_invalid"):
        prepare_capture(duplicate, capture_mode=CAPTURE_MODE_FIXTURE)

    monkeypatch.setattr(tokenomist_v5_capture, "_MAX_BUNDLE_BYTES", 100)
    with pytest.raises(TokenomistV5CaptureError, match="capture_bundle_size_bound_exceeded"):
        prepare_capture(_source(), capture_mode=CAPTURE_MODE_FIXTURE)


def test_interrupted_staging_is_retained_as_quarantine_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tokenomist_v5_capture._write_leaf_at
    calls = 0

    def interrupted(directory_fd: int, name: str, raw: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise TokenomistV5CaptureError("injected_interruption")
        original(directory_fd, name, raw)

    monkeypatch.setattr(tokenomist_v5_capture, "_write_leaf_at", interrupted)
    with pytest.raises(TokenomistV5CaptureError, match="injected_interruption"):
        _persist(tmp_path)
    retained = [
        path
        for path in tmp_path.iterdir()
        if path.name.startswith("tmp_tokenomist_v5_stage_")
    ]
    assert len(retained) == 1
    assert {path.name for path in retained[0].iterdir()} == {
        "exact_fixture_capture.json",
        "request_ledger.json",
    }

    monkeypatch.setattr(tokenomist_v5_capture, "_write_leaf_at", original)
    assert _persist(tmp_path)["strict_doctor_status"] == "pass"


def test_staging_cleanup_never_deletes_replaced_unowned_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tokenomist_v5_capture._write_leaf_at
    calls = 0
    replacement_name: str | None = None

    def replace_staging(directory_fd: int, name: str, raw: bytes) -> None:
        nonlocal calls, replacement_name
        calls += 1
        if calls != 3:
            original(directory_fd, name, raw)
            return
        parent_fd = os.open(
            "..",
            os.O_RDONLY | os.O_DIRECTORY,
            dir_fd=directory_fd,
        )
        try:
            replacement_name = next(
                item
                for item in os.listdir(parent_fd)
                if item.startswith("tmp_tokenomist_v5_stage_")
            )
            os.rename(
                replacement_name,
                f"{replacement_name}.stolen",
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.mkdir(replacement_name, 0o700, dir_fd=parent_fd)
            replacement_fd = os.open(
                replacement_name,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=parent_fd,
            )
            try:
                poison_fd = os.open(
                    "unowned.txt",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=replacement_fd,
                )
                try:
                    os.write(poison_fd, b"must remain")
                finally:
                    os.close(poison_fd)
            finally:
                os.close(replacement_fd)
        finally:
            os.close(parent_fd)
        raise TokenomistV5CaptureError("injected_after_staging_replacement")

    monkeypatch.setattr(tokenomist_v5_capture, "_write_leaf_at", replace_staging)
    with pytest.raises(
        TokenomistV5CaptureError,
        match="capture_staging_cleanup_identity_drift",
    ):
        _persist(tmp_path)

    assert replacement_name is not None
    replacement = tmp_path / replacement_name
    assert (replacement / "unowned.txt").read_bytes() == b"must remain"


def test_staging_cleanup_retains_leaf_replacement_without_unlinking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write = tokenomist_v5_capture._write_leaf_at
    original_cleanup = tokenomist_v5_capture._cleanup_owned_staging_at
    write_calls = 0
    swapped = False

    def interrupted(directory_fd: int, name: str, raw: bytes) -> None:
        nonlocal write_calls
        write_calls += 1
        if write_calls == 3:
            raise TokenomistV5CaptureError("injected_leaf_cleanup_race")
        original_write(directory_fd, name, raw)

    def swap_leaf_then_retain(
        base_fd: int,
        staging: str,
        expected_identity: os.stat_result,
    ) -> None:
        nonlocal swapped
        staging_fd = os.open(
            staging,
            os.O_RDONLY | os.O_DIRECTORY,
            dir_fd=base_fd,
        )
        try:
            os.rename(
                "request_ledger.json",
                "stolen-ledger.json",
                src_dir_fd=staging_fd,
                dst_dir_fd=base_fd,
            )
            replacement_fd = os.open(
                "request_ledger.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=staging_fd,
            )
            try:
                os.write(replacement_fd, b"unowned replacement\n")
            finally:
                os.close(replacement_fd)
            swapped = True
        finally:
            os.close(staging_fd)
        original_cleanup(base_fd, staging, expected_identity)

    monkeypatch.setattr(tokenomist_v5_capture, "_write_leaf_at", interrupted)
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_cleanup_owned_staging_at",
        swap_leaf_then_retain,
    )
    monkeypatch.setattr(
        tokenomist_v5_capture.os,
        "unlink",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("staging retention must never unlink by name")
        ),
    )

    with pytest.raises(TokenomistV5CaptureError, match="injected_leaf_cleanup_race"):
        _persist(tmp_path)

    retained = next(
        path
        for path in tmp_path.iterdir()
        if path.name.startswith("tmp_tokenomist_v5_stage_")
    )
    assert swapped is True
    assert (tmp_path / "stolen-ledger.json").is_file()
    assert (retained / "request_ledger.json").read_bytes() == b"unowned replacement\n"


def test_no_replace_publication_preserves_racing_empty_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tokenomist_v5_capture._rename_directory_noreplace
    raced_destination: str | None = None

    def create_empty_destination(
        base_fd: int,
        source: str,
        destination: str,
    ) -> bool:
        nonlocal raced_destination
        raced_destination = destination
        os.mkdir(destination, 0o700, dir_fd=base_fd)
        return original(base_fd, source, destination)

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_rename_directory_noreplace",
        create_empty_destination,
    )
    with pytest.raises(TokenomistV5CaptureError, match="capture_artifact_set_invalid"):
        _persist(tmp_path)

    assert raced_destination is not None
    destination = tmp_path / raced_destination
    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert len([
        path for path in tmp_path.iterdir()
        if path.name.startswith("tmp_tokenomist_v5_stage_")
    ]) == 1


def test_kernel_no_replace_handles_destination_when_all_prechecks_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_exists = tokenomist_v5_capture._namespace_exists_at
    target_namespace = prepare_capture(
        _source(),
        capture_mode=CAPTURE_MODE_FIXTURE,
    ).namespace
    checks = 0

    def miss_and_create_on_syscall_precheck(base_fd: int, namespace: str) -> bool:
        nonlocal checks
        if namespace == target_namespace:
            checks += 1
            if checks == 3:
                os.mkdir(namespace, 0o700, dir_fd=base_fd)
            return False
        return original_exists(base_fd, namespace)

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_namespace_exists_at",
        miss_and_create_on_syscall_precheck,
    )
    with pytest.raises(TokenomistV5CaptureError, match="capture_artifact_set_invalid"):
        _persist(tmp_path)

    destination = tmp_path / target_namespace
    assert checks == 3
    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert len(
        [
            path
            for path in tmp_path.iterdir()
            if path.name.startswith("tmp_tokenomist_v5_stage_")
        ]
    ) == 1


def test_exact_peer_kernel_race_reports_retained_staging_writes_truthfully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _persist(tmp_path)
    namespace = str(first["artifact_namespace"])
    original_exists = tokenomist_v5_capture._namespace_exists_at
    checks = 0

    def hide_exact_peer(base_fd: int, candidate: str) -> bool:
        nonlocal checks
        if candidate == namespace:
            checks += 1
            return False
        return original_exists(base_fd, candidate)

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_namespace_exists_at",
        hide_exact_peer,
    )
    result = _persist(tmp_path)

    assert checks == 3
    assert result["artifact_namespace"] == namespace
    assert result["created"] is False
    assert result["canonical_capture_reused"] is True
    assert result["idempotent"] is False
    assert result["writes_performed"] is True
    assert result["staging_writes_performed"] is True
    assert result["retained_staging_quarantine"] is True
    assert result["retained_staging_artifact_count"] == 5
    assert set(result["retained_staging_artifact_names"]) == {
        "exact_fixture_capture.json",
        "request_ledger.json",
        "normalized_snapshot.json",
        "capture_manifest.json",
        "capture_completion_receipt.json",
    }
    retained_name = str(result["retained_staging_quarantine_name"])
    assert retained_name.startswith("tmp_tokenomist_v5_stage_")
    retained = tmp_path / retained_name
    assert retained.is_dir()
    assert len(list(retained.iterdir())) == 5
    assert validate_capture(tmp_path, namespace)["strict_doctor_status"] == "pass"


def test_retained_staging_count_uses_descriptor_observed_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _persist(tmp_path)
    namespace = str(first["artifact_namespace"])
    original_exists = tokenomist_v5_capture._namespace_exists_at
    original_cleanup = tokenomist_v5_capture._cleanup_owned_staging_at

    def hide_exact_peer(base_fd: int, candidate: str) -> bool:
        if candidate == namespace:
            return False
        return original_exists(base_fd, candidate)

    def delete_one_before_inventory(
        base_fd: int,
        staging: str,
        expected_identity: os.stat_result,
    ) -> tuple[str, ...]:
        staging_fd = os.open(
            staging,
            os.O_RDONLY | os.O_DIRECTORY,
            dir_fd=base_fd,
        )
        try:
            os.unlink("normalized_snapshot.json", dir_fd=staging_fd)
        finally:
            os.close(staging_fd)
        return original_cleanup(base_fd, staging, expected_identity)

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_namespace_exists_at",
        hide_exact_peer,
    )
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_cleanup_owned_staging_at",
        delete_one_before_inventory,
    )
    result = _persist(tmp_path)

    assert result["created"] is False
    assert result["writes_performed"] is True
    assert result["retained_staging_artifact_count"] == 4
    assert "normalized_snapshot.json" not in result["retained_staging_artifact_names"]
    retained = tmp_path / str(result["retained_staging_quarantine_name"])
    assert sorted(path.name for path in retained.iterdir()) == sorted(
        result["retained_staging_artifact_names"]
    )
    assert validate_capture(tmp_path, namespace)["strict_doctor_status"] == "pass"


@pytest.mark.parametrize("missing_boundary", ["platform", "symbol"])
def test_no_replace_has_no_plain_rename_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_boundary: str,
) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    if missing_boundary == "platform":
        monkeypatch.setattr(tokenomist_v5_capture.sys, "platform", "unsupported")
    else:
        monkeypatch.setattr(tokenomist_v5_capture.sys, "platform", "linux")
        monkeypatch.setattr(
            tokenomist_v5_capture.ctypes,
            "CDLL",
            lambda *_args, **_kwargs: object(),
        )
    monkeypatch.setattr(
        tokenomist_v5_capture.os,
        "rename",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("plain rename fallback is forbidden")
        ),
    )
    base_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(
            TokenomistV5CaptureError,
            match="capture_no_replace_rename_unsupported",
        ):
            tokenomist_v5_capture._rename_directory_noreplace(
                base_fd,
                "stage",
                "destination",
            )
    finally:
        os.close(base_fd)

    assert stage.is_dir()
    assert not (tmp_path / "destination").exists()


@pytest.mark.parametrize(
    ("source", "destination", "reason"),
    [
        ("stage\x00replacement", "destination", "capture_path_nul_rejected"),
        ("stage", "destination\x00replacement", "capture_path_nul_rejected"),
        ("../stage", "destination", "capture_path_leaf_invalid"),
        ("stage", "nested/destination", "capture_path_leaf_invalid"),
    ],
)
def test_no_replace_rejects_nul_and_non_leaf_names_before_syscall(
    tmp_path: Path,
    source: str,
    destination: str,
    reason: str,
) -> None:
    base_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(TokenomistV5CaptureError, match=reason):
            tokenomist_v5_capture._rename_directory_noreplace(
                base_fd,
                source,
                destination,
            )
    finally:
        os.close(base_fd)

    assert list(tmp_path.iterdir()) == []


def test_concurrent_identical_capture_has_one_writer(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: _persist(tmp_path), range(2)))

    assert sorted(bool(row["created"]) for row in results) == [False, True]
    assert {str(row["artifact_namespace"]) for row in results} == {
        str(results[0]["artifact_namespace"])
    }
    assert all(row["strict_doctor_status"] == "pass" for row in results)


def test_artifact_root_swap_cannot_redirect_post_publish_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "artifact_base"
    moved = tmp_path / "moved_artifact_base"
    base.mkdir()
    original = tokenomist_v5_capture._publish_staged_bundle_at

    def swap_after_publish(base_fd: int, prepared: object) -> bool:
        created = original(base_fd, prepared)  # type: ignore[arg-type]
        base.rename(moved)
        base.mkdir()
        return created

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_publish_staged_bundle_at",
        swap_after_publish,
    )
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_identity_drift"):
        _persist(base)
    assert list(base.iterdir()) == []
    assert any(path.name.startswith("radar_tokenomist_v5_") for path in moved.iterdir())


def test_persist_rejects_exit_ancestor_symlink_back_to_original_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    base = holder / "artifacts"
    base.mkdir(parents=True)
    moved_holder = tmp_path / "holder_original"
    original_publish = tokenomist_v5_capture._publish_staged_bundle_at
    published_namespace: str | None = None

    def publish_then_replace_ancestor(base_fd: int, prepared: object) -> bool:
        nonlocal published_namespace
        created = original_publish(base_fd, prepared)  # type: ignore[arg-type]
        published_namespace = str(prepared.namespace)  # type: ignore[attr-defined]
        holder.rename(moved_holder)
        holder.symlink_to(moved_holder, target_is_directory=True)
        return created

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_publish_staged_bundle_at",
        publish_then_replace_ancestor,
    )
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_identity_drift"):
        _persist(base)

    assert holder.is_symlink()
    assert published_namespace is not None
    assert (moved_holder / "artifacts" / published_namespace).is_dir()


def test_persist_rejects_symlink_swap_after_final_nofollow_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    base = holder / "artifacts"
    base.mkdir(parents=True)
    moved_holder = tmp_path / "holder_original"
    prepared = prepare_capture(_source(), capture_mode=CAPTURE_MODE_FIXTURE)
    original_open_chain = tokenomist_v5_capture.anchored_io._open_directory_chain
    base_walks = 0

    def open_chain_then_swap(directory: Path) -> int:
        nonlocal base_walks
        descriptor = original_open_chain(directory)
        if directory == base:
            base_walks += 1
            if base_walks == 2:
                holder.rename(moved_holder)
                holder.symlink_to(moved_holder, target_is_directory=True)
        return descriptor

    monkeypatch.setattr(
        tokenomist_v5_capture.anchored_io,
        "_open_directory_chain",
        open_chain_then_swap,
    )
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_identity_drift"):
        _persist(base)

    assert base_walks == 2
    assert holder.is_symlink()
    assert (moved_holder / "artifacts" / prepared.namespace).is_dir()


def test_validation_rejects_full_artifact_base_ancestry_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    base = holder / "artifacts"
    base.mkdir(parents=True)
    result = _persist(base)
    moved_holder = tmp_path / "holder_original"
    original_open_chain = tokenomist_v5_capture.anchored_io._open_directory_chain
    swapped = False

    def swap_parent_then_open(directory: Path) -> int:
        nonlocal swapped
        if directory == base and not swapped:
            swapped = True
            holder.rename(moved_holder)
            base.mkdir(parents=True)
        return original_open_chain(directory)

    monkeypatch.setattr(
        tokenomist_v5_capture.anchored_io,
        "_open_directory_chain",
        swap_parent_then_open,
    )
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_identity_drift"):
        validate_capture(base, str(result["artifact_namespace"]))

    assert swapped is True
    assert (moved_holder / "artifacts" / str(result["artifact_namespace"])).is_dir()
    assert list(base.iterdir()) == []


def test_persist_rejects_parent_swap_immediately_after_base_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    base = holder / "artifacts"
    base.mkdir(parents=True)
    moved_holder = tmp_path / "holder_original"
    original_resolve = Path.resolve
    swapped = False

    def resolve_then_swap(path: Path, *args: object, **kwargs: object) -> Path:
        nonlocal swapped
        resolved = original_resolve(path, *args, **kwargs)
        if path == base and not swapped:
            swapped = True
            holder.rename(moved_holder)
            base.mkdir(parents=True)
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_then_swap)
    with pytest.raises(TokenomistV5CaptureError, match="artifact_base_identity_drift"):
        _persist(base)

    assert swapped is True
    assert list((moved_holder / "artifacts").iterdir()) == []
    assert list(base.iterdir()) == []


def test_fixture_read_rejects_parent_ancestry_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    source = holder / "fixtures" / "tokenomist.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(_source())
    moved_holder = tmp_path / "holder_original"
    original_open_chain = tokenomist_v5_capture._open_directory_chain
    swapped = False

    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE", source)
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_DEFAULT_FIXTURE_SHA256",
        tokenomist_v5_capture._sha256(_source()),
    )
    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE_SIZE", len(_source()))

    def swap_parent_then_open(directory: Path) -> int:
        nonlocal swapped
        if directory == source.parent and not swapped:
            swapped = True
            holder.rename(moved_holder)
            source.parent.mkdir(parents=True)
            source.write_bytes(b'{"attacker":true}\n')
        return original_open_chain(directory)

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_open_directory_chain",
        swap_parent_then_open,
    )
    with pytest.raises(TokenomistV5CaptureError, match="fixture_parent_identity_invalid"):
        tokenomist_v5_capture._read_checked_fixture(source)

    assert swapped is True
    assert (moved_holder / "fixtures" / "tokenomist.json").read_bytes() == _source()


def test_fixture_read_rejects_identical_parent_swap_after_second_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    source = holder / "fixtures" / "tokenomist.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(_source())
    moved_holder = tmp_path / "holder_original"
    original_resolve = Path.resolve
    resolve_calls = 0
    swapped = False

    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE", source)
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_DEFAULT_FIXTURE_SHA256",
        tokenomist_v5_capture._sha256(_source()),
    )
    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE_SIZE", len(_source()))

    def resolve_then_swap(path: Path, *args: object, **kwargs: object) -> Path:
        nonlocal resolve_calls, swapped
        resolved = original_resolve(path, *args, **kwargs)
        if path == source:
            resolve_calls += 1
            if resolve_calls == 2:
                swapped = True
                holder.rename(moved_holder)
                source.parent.mkdir(parents=True)
                source.write_bytes(_source())
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_then_swap)
    with pytest.raises(TokenomistV5CaptureError, match="fixture_parent_identity_invalid"):
        tokenomist_v5_capture._read_checked_fixture(source)

    assert swapped is True
    assert resolve_calls == 2
    assert source.read_bytes() == _source()
    assert (moved_holder / "fixtures" / "tokenomist.json").read_bytes() == _source()


def test_fixture_read_rejects_exit_ancestor_symlink_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    source = holder / "fixtures" / "tokenomist.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(_source())
    moved_holder = tmp_path / "holder_original"
    original_read = tokenomist_v5_capture.os.read
    swapped = False

    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE", source)
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_DEFAULT_FIXTURE_SHA256",
        tokenomist_v5_capture._sha256(_source()),
    )
    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE_SIZE", len(_source()))

    def read_then_replace_ancestor(descriptor: int, maximum: int) -> bytes:
        nonlocal swapped
        raw = original_read(descriptor, maximum)
        if not swapped:
            swapped = True
            holder.rename(moved_holder)
            holder.symlink_to(moved_holder, target_is_directory=True)
        return raw

    monkeypatch.setattr(tokenomist_v5_capture.os, "read", read_then_replace_ancestor)
    with pytest.raises(TokenomistV5CaptureError, match="fixture_parent_identity_invalid"):
        tokenomist_v5_capture._read_checked_fixture(source)

    assert swapped is True
    assert holder.is_symlink()
    assert source.read_bytes() == _source()


def test_fixture_read_rejects_symlink_swap_after_final_nofollow_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    source = holder / "fixtures" / "tokenomist.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(_source())
    moved_holder = tmp_path / "holder_original"
    original_open_chain = tokenomist_v5_capture._open_directory_chain
    parent_walks = 0

    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE", source)
    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_DEFAULT_FIXTURE_SHA256",
        tokenomist_v5_capture._sha256(_source()),
    )
    monkeypatch.setattr(tokenomist_v5_capture, "_DEFAULT_FIXTURE_SIZE", len(_source()))

    def open_chain_then_swap(directory: Path) -> int:
        nonlocal parent_walks
        descriptor = original_open_chain(directory)
        if directory == source.parent:
            parent_walks += 1
            if parent_walks == 2:
                holder.rename(moved_holder)
                holder.symlink_to(moved_holder, target_is_directory=True)
        return descriptor

    monkeypatch.setattr(
        tokenomist_v5_capture,
        "_open_directory_chain",
        open_chain_then_swap,
    )
    with pytest.raises(
        TokenomistV5CaptureError,
        match="fixture_source_changed_during_read",
    ):
        tokenomist_v5_capture._read_checked_fixture(source)

    assert parent_walks == 2
    assert holder.is_symlink()
    assert source.read_bytes() == _source()


def test_smoke_rejects_noncanonical_fixture_copy(tmp_path: Path) -> None:
    copied = tmp_path / "tokenomist.json"
    copied.write_bytes(_source())

    with pytest.raises(TokenomistV5CaptureError, match="fixture_path_not_canonical"):
        run_fixture_capture_smoke(copied)


def test_lifecycle_classifies_capture_without_mutating_sealed_inventory(
    tmp_path: Path,
) -> None:
    artifact_base = tmp_path / "artifacts"
    reports = tmp_path / "reports"
    artifact_base.mkdir()
    captured = _persist(artifact_base)
    namespace = str(captured["artifact_namespace"])
    namespace_dir = artifact_base / namespace
    before = {path.name for path in namespace_dir.iterdir()}

    registry = lifecycle.write_namespace_lifecycle_report(
        artifact_base,
        out_dir=reports,
        now=datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc),
    )

    row = next(item for item in registry["namespaces"] if item["namespace"] == namespace)
    assert row["status"] == "manual_review"
    assert row["safe_for_send_readiness"] is False
    assert {path.name for path in namespace_dir.iterdir()} == before
    assert "event_alpha_namespace_status.json" not in before
    assert validate_capture(artifact_base, namespace)["strict_doctor_status"] == "pass"


def test_disposable_smoke_retains_nothing_and_calls_no_provider() -> None:
    value = run_fixture_capture_smoke(FIXTURE)

    assert value["strict_doctor_status"] == "pass"
    assert value["fixture_artifacts_retained"] is False
    assert value["disposable_artifact_write_count"] == 5
    assert value["provider_calls_performed_by_smoke"] == 0
    assert value["provider_calls_recorded"] == 0
    assert value["artifact_count"] == 5
    assert "artifact_path" not in value
