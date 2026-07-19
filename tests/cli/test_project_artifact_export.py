"""Canonical project-artifact selection and optional-history regressions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from tests.rsi._api_helpers import REPO_ROOT


_POLICY_PATH = Path("research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json")
_STANDARD_MANIFEST = "event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json"
_HISTORY_MANIFEST = "PROJECT_ARTIFACT_HISTORY_MANIFEST.json"
_HISTORY_CHECKSUMS = "PROJECT_ARTIFACT_HISTORY_SHA256SUMS.txt"


def _load_export_module(name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        REPO_ROOT / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _project_tree(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "tree"
    root.mkdir()
    _write(root / "Makefile", b"verify:\n\t@true\n")
    _write(root / _POLICY_PATH, (REPO_ROOT / _POLICY_PATH).read_bytes())
    current = "radar_market_no_send_current"
    latest = "radar_market_no_send_latest"
    pointer = {
        "artifact_namespace": current,
        "authority_checked_at": "2026-07-16T00:00:00+00:00",
        "contract_version": 1,
        "generation_authority_status": "authoritative",
        "operator_state_sha256": "a" * 64,
        "profile": "no_key_live",
        "revision": 7,
        "run_id": "2026-07-16T00:00:00+00:00|no_key_live",
    }
    attempt = {
        "artifact_namespace": latest,
        "attempt_id": "attempt-1",
        "candidate_source_mode": "live_no_send",
        "data_acquisition_mode": "live_provider",
        "data_mode": "live",
        "decision_radar_campaign_counted": True,
        "no_send": True,
        "provider_call_attempted": True,
        "research_only": True,
        "row_type": "event_market_no_send_latest_attempt",
        "status": "complete",
    }
    artifact_root = root / "event_fade_cache"
    _write(artifact_root / "radar_current_namespace.json", _canonical_json(pointer))
    _write(
        artifact_root / "event_market_no_send_latest_attempt.json",
        _canonical_json(attempt),
    )
    _write(artifact_root / current / "operator.json", b'{"current":true}\n')
    _write(artifact_root / latest / "attempt.json", b'{"latest":true}\n')
    _write(
        artifact_root / "radar_market_history_cache/history.jsonl",
        b'{"campaign":"current"}\n',
    )
    _write(
        artifact_root / "event_source_independence_contracts/current.json",
        b'{"contract":"current"}\n',
    )
    _write(artifact_root / "old_fixture/result.json", b'{"fixture":true}\n')
    _write(artifact_root / "historical_rows.jsonl", b'{"historical":true}\n')
    liquidation_namespace = (
        "radar_bybit_liquidation_transcript_20260719t140000000000z_0123456789ab"
    )
    _write(
        artifact_root / liquidation_namespace / "capture_manifest.json",
        b'{"detached":true}\n',
    )
    _write(
        artifact_root / liquidation_namespace / "application_payload_003.bin",
        b'{"topic":"allLiquidation.BTCUSDT"}',
    )
    tokenomist_namespace = (
        "radar_tokenomist_v5_20260719t160000000000z_0123456789ab"
    )
    for name in (
        "exact_fixture_capture.json",
        "request_ledger.json",
        "normalized_snapshot.json",
        "capture_manifest.json",
        "capture_completion_receipt.json",
    ):
        _write(
            artifact_root / tokenomist_namespace / name,
            _canonical_json({"synthetic_fixture": True, "name": name}),
        )
    _write(
        artifact_root
        / "tmp_bybit_liquidation_stage_123_456"
        / "partial_payload.bin",
        b'{"retained_quarantine":true}\n',
    )
    _write(artifact_root / ".runtime.lock", b"machine-local\n")
    return root, current, latest


def test_standard_export_contains_only_manifested_canonical_artifacts(
    tmp_path: Path,
) -> None:
    module = _load_export_module("project_artifact_export_standard")
    root, current, latest = _project_tree(tmp_path)
    output = root / "review.zip"
    pointer_path = root / "event_fade_cache/radar_current_namespace.json"
    pointer_before = pointer_path.read_bytes()

    assert module.main(root=root, out=output) == 0
    assert pointer_path.read_bytes() == pointer_before

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest_raw = archive.read(_STANDARD_MANIFEST)
        manifest = json.loads(manifest_raw)

    expected_artifacts = {
        "event_fade_cache/radar_current_namespace.json",
        "event_fade_cache/event_market_no_send_latest_attempt.json",
        f"event_fade_cache/{current}/operator.json",
        f"event_fade_cache/{latest}/attempt.json",
        "event_fade_cache/radar_market_history_cache/history.jsonl",
        "event_fade_cache/event_source_independence_contracts/current.json",
    }
    assert {
        name
        for name in names
        if name.startswith("event_fade_cache/") and name != _STANDARD_MANIFEST
    } == expected_artifacts
    assert "event_fade_cache/old_fixture/result.json" not in names
    assert "event_fade_cache/historical_rows.jsonl" not in names
    assert not any(
        name.startswith("event_fade_cache/radar_bybit_liquidation_transcript_")
        for name in names
    )
    assert not any(
        name.startswith("event_fade_cache/radar_tokenomist_v5_")
        for name in names
    )
    assert not any(
        name.startswith("event_fade_cache/tmp_bybit_liquidation_stage_")
        for name in names
    )
    assert "event_fade_cache/.runtime.lock" not in names
    assert manifest["entry_count"] == len(expected_artifacts)
    assert manifest["excluded_history_count"] == 10
    assert manifest["excluded_noise"] == ["event_fade_cache/.runtime.lock"]
    assert manifest["canonical_selection_is_closed"] is True
    assert manifest["canonical_source_coverage_status"] == "partial"
    assert manifest["missing_canonical_shared_directories"] == [
        "official_macro_calendar"
    ]
    assert {row["path"] for row in manifest["entries"]} == expected_artifacts
    assert manifest["local_artifacts_deleted_or_moved"] is False
    assert manifest["history_archive"]["included_in_standard_export"] is False
    assert hashlib.sha256(manifest_raw).hexdigest()


def test_provider_unavailable_latest_attempt_is_manifested_canonical_truth(
    tmp_path: Path,
) -> None:
    module = _load_export_module("project_artifact_export_provider_unavailable")
    root, _current, latest = _project_tree(tmp_path)
    output = root / "review.zip"
    attempt_path = root / "event_fade_cache/event_market_no_send_latest_attempt.json"
    attempt = json.loads(attempt_path.read_bytes())
    attempt.update(
        {
            "decision_radar_campaign_counted": False,
            "provider_request_succeeded": False,
            "status": "provider_unavailable",
        }
    )
    attempt_path.write_bytes(_canonical_json(attempt))

    assert module.main(root=root, out=output) == 0

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(_STANDARD_MANIFEST))

    assert f"event_fade_cache/{latest}/attempt.json" in names
    selected = {
        row["kind"]: row for row in manifest["selector_results"]
    }
    assert selected["latest_live_no_send_attempt_namespace"] == {
        "artifact_namespace": latest,
        "attempt_id": "attempt-1",
        "kind": "latest_live_no_send_attempt_namespace",
        "provider_call_attempted": True,
        "path": "event_market_no_send_latest_attempt.json",
        "status": "selected",
        "terminal_status": "provider_unavailable",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_call_attempted", False),
        ("provider_request_succeeded", True),
        ("decision_radar_campaign_counted", True),
    ],
)
def test_provider_unavailable_latest_attempt_rejects_contradictory_truth(
    tmp_path: Path,
    field: str,
    value: bool,
) -> None:
    module = _load_export_module(
        f"project_artifact_export_provider_unavailable_invalid_{field}"
    )
    root, _current, _latest = _project_tree(tmp_path)
    output = root / "review.zip"
    output.write_bytes(b"prior-success")
    attempt_path = root / "event_fade_cache/event_market_no_send_latest_attempt.json"
    attempt = json.loads(attempt_path.read_bytes())
    attempt.update(
        {
            "decision_radar_campaign_counted": False,
            "provider_request_succeeded": False,
            "status": "provider_unavailable",
            field: value,
        }
    )
    attempt_path.write_bytes(_canonical_json(attempt))

    assert module.main(root=root, out=output) == 1
    assert output.read_bytes() == b"prior-success"
    assert not (root / "review.zip.tmp").exists()


def test_optional_project_history_is_exact_disjoint_checksummed_complement(
    tmp_path: Path,
) -> None:
    module = _load_export_module("project_artifact_export_history")
    root, _current, _latest = _project_tree(tmp_path)
    source_before = {
        path.relative_to(root): path.read_bytes()
        for path in (root / "event_fade_cache").rglob("*")
        if path.is_file() and not path.is_symlink()
    }

    assert module.project_history_main(root=root) == 0

    output = root / "crypto_rsi_scanner_artifact_history.zip"
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(_HISTORY_MANIFEST))
        checksums = archive.read(_HISTORY_CHECKSUMS).decode()

    expected_history = {
        "event_fade_cache/old_fixture/result.json",
        "event_fade_cache/historical_rows.jsonl",
        "event_fade_cache/radar_bybit_liquidation_transcript_20260719t140000000000z_0123456789ab/capture_manifest.json",
        "event_fade_cache/radar_bybit_liquidation_transcript_20260719t140000000000z_0123456789ab/application_payload_003.bin",
        "event_fade_cache/radar_tokenomist_v5_20260719t160000000000z_0123456789ab/exact_fixture_capture.json",
        "event_fade_cache/radar_tokenomist_v5_20260719t160000000000z_0123456789ab/request_ledger.json",
        "event_fade_cache/radar_tokenomist_v5_20260719t160000000000z_0123456789ab/normalized_snapshot.json",
        "event_fade_cache/radar_tokenomist_v5_20260719t160000000000z_0123456789ab/capture_manifest.json",
        "event_fade_cache/radar_tokenomist_v5_20260719t160000000000z_0123456789ab/capture_completion_receipt.json",
        "event_fade_cache/tmp_bybit_liquidation_stage_123_456/partial_payload.bin",
    }
    assert names == expected_history | {_HISTORY_MANIFEST, _HISTORY_CHECKSUMS}
    assert {row["path"] for row in manifest["entries"]} == expected_history
    assert manifest["complement_of_standard_project_selection"] is True
    assert manifest["canonical_artifacts_included"] is False
    assert manifest["local_artifacts_deleted_or_moved"] is False
    detached_rows = [
        row
        for row in manifest["entries"]
        if "radar_bybit_liquidation_transcript_" in row["path"]
    ]
    assert len(detached_rows) == 2
    assert {row["role"] for row in detached_rows} == {
        "noncanonical_namespace_artifact"
    }
    assert {row["semantic_ids"]["historical_or_noncanonical"] for row in detached_rows} == {
        True
    }
    tokenomist_rows = [
        row
        for row in manifest["entries"]
        if "radar_tokenomist_v5_" in row["path"]
    ]
    assert len(tokenomist_rows) == 5
    assert {row["role"] for row in tokenomist_rows} == {
        "noncanonical_namespace_artifact"
    }
    assert {
        row["semantic_ids"]["historical_or_noncanonical"]
        for row in tokenomist_rows
    } == {True}
    quarantine_rows = [
        row
        for row in manifest["entries"]
        if "tmp_bybit_liquidation_stage_" in row["path"]
    ]
    assert len(quarantine_rows) == 1
    assert quarantine_rows[0]["role"] == "noncanonical_namespace_artifact"
    assert quarantine_rows[0]["semantic_ids"]["historical_or_noncanonical"] is True
    assert checksums == "".join(
        f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}\n"
        for path in sorted(expected_history)
    )
    source_after = {
        path.relative_to(root): path.read_bytes()
        for path in (root / "event_fade_cache").rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    assert source_after == source_before


def test_non_live_latest_selector_fails_closed_and_preserves_prior_archive(
    tmp_path: Path,
) -> None:
    module = _load_export_module("project_artifact_export_non_live")
    root, _current, _latest = _project_tree(tmp_path)
    output = root / "review.zip"
    output.write_bytes(b"preserve-prior-success")
    attempt_path = root / "event_fade_cache/event_market_no_send_latest_attempt.json"
    attempt = json.loads(attempt_path.read_bytes())
    attempt["data_mode"] = "mock"
    attempt_path.write_bytes(_canonical_json(attempt))

    assert module.main(root=root, out=output) == 1
    assert output.read_bytes() == b"preserve-prior-success"
    assert not (root / "review.zip.tmp").exists()


def test_unsafe_artifact_tree_and_missing_policy_fail_closed(tmp_path: Path) -> None:
    module = _load_export_module("project_artifact_export_unsafe")
    root, _current, _latest = _project_tree(tmp_path)
    output = root / "review.zip"
    output.write_bytes(b"prior")
    outside = tmp_path / "outside.json"
    outside.write_text('{"outside":true}\n', encoding="utf-8")
    (root / "event_fade_cache/old_fixture/link.json").symlink_to(outside)

    assert module.main(root=root, out=output) == 1
    assert output.read_bytes() == b"prior"

    (root / "event_fade_cache/old_fixture/link.json").unlink()
    (root / _POLICY_PATH).unlink()
    assert module.main(root=root, out=output) == 1
    assert output.read_bytes() == b"prior"


@pytest.mark.parametrize("history", [False, True])
def test_post_write_project_source_drift_preserves_prior_archive(
    tmp_path: Path,
    history: bool,
) -> None:
    module = _load_export_module(f"project_artifact_source_drift_{history}")
    root, _current, _latest = _project_tree(tmp_path)
    output = root / (
        "crypto_rsi_scanner_artifact_history.zip" if history else "review.zip"
    )
    output.write_bytes(b"prior-success")
    target = root / (
        "event_fade_cache/old_fixture/result.json"
        if history
        else "event_fade_cache/radar_market_history_cache/history.jsonl"
    )
    original_write = module._write_file_to_zip
    mutated = False

    def mutating_write(archive, path, arcname, **kwargs):
        nonlocal mutated
        original_write(archive, path, arcname, **kwargs)
        if path == target and not mutated:
            path.write_bytes(b'{"drifted":true}\n')
            mutated = True

    module._write_file_to_zip = mutating_write
    try:
        result = (
            module.project_history_main(root=root)
            if history
            else module.main(root=root, out=output)
        )
    finally:
        module._write_file_to_zip = original_write

    assert mutated is True
    assert result == 1
    assert output.read_bytes() == b"prior-success"
    assert not output.with_name(output.name + ".tmp").exists()


def test_project_history_make_target_is_fixed_and_optional() -> None:
    rendered = subprocess.check_output(
        [
            "make",
            "--no-print-directory",
            "-n",
            "export-project-artifact-history",
            "PYTHON=chosen-python",
        ],
        cwd=REPO_ROOT,
        text=True,
    )

    assert rendered.strip() == "chosen-python scripts/export_project_artifact_history.py"
    assert "rm " not in rendered
    assert "mv " not in rendered


def test_standalone_release_runner_uses_one_disposable_artifact_base() -> None:
    rendered = subprocess.run(
        ["make", "-n", "test", "PYTHON=python3"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "mktemp -d" in rendered
    assert "crypto-rsi-standalone" in rendered
    assert "trap 'rm -rf" in rendered
    assert 'RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR="$tmp/event-alpha-artifacts"' in rendered
    assert 'RSI_EVENT_DISCOVERY_CACHE_DIR="$tmp/event-discovery-cache"' in rendered
    for name in (
        "RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
        "RSI_EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "RSI_EVENT_INCIDENT_STORE_PATH",
        "RSI_EVENT_ALPHA_NOTIFICATION_DELIVERIES_PATH",
    ):
        assert f"-u {name}" in rendered
        assert f"{name}=\"$tmp/event-discovery-cache/" not in rendered
