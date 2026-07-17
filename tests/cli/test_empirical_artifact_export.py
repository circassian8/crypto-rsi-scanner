"""Bounded source and optional-history export for empirical lab artifacts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_review import (
    build_targeted_review_queue,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_review_feedback import (
    build_feedback_event,
    canonical_json_bytes as feedback_json_bytes,
)
from tests.rsi._api_helpers import REPO_ROOT


_LIMITS = {
    "max_canonical_lab_file_count": 96,
    "max_canonical_lab_total_bytes": 220_200_960,
    "max_feedback_event_bytes": 8_192,
    "max_feedback_event_count": 4_096,
    "max_feedback_total_bytes": 4_194_304,
    "max_history_file_count": 1_024,
    "max_history_total_bytes": 1_610_612_736,
    "max_lab_file_count": 1_152,
    "max_lab_total_bytes": 1_879_048_192,
    "max_single_empirical_file_bytes": 67_108_864,
    "max_standard_empirical_file_count": 128,
    "max_standard_empirical_total_bytes": 268_435_456,
}
_LAB = Path("event_fade_cache/decision_radar_research_lab")
_STANDARD_MANIFEST = _LAB / "EMPIRICAL_ARTIFACT_EXPORT_MANIFEST.json"
_HISTORY_OUTPUT = "crypto_rsi_scanner_empirical_artifact_history.zip"
_REPORT_PATHS = (
    "research/DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md",
    "research/DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json",
    "research/DECISION_RADAR_WALK_FORWARD_REPORT.md",
    "research/DECISION_RADAR_WALK_FORWARD_REPORT.json",
    "research/DECISION_RADAR_POLICY_SIMULATION_REPORT.md",
    "research/DECISION_RADAR_POLICY_SIMULATION_REPORT.json",
    "research/DECISION_RADAR_RESEARCH_LIMITATIONS.md",
)
_SHIPPED_REPORT_DATA = tuple(
    (path, (REPO_ROOT / path).read_bytes()) for path in _REPORT_PATHS
)
_SHIPPED_SUPPLEMENT_DATA = (
    REPO_ROOT / "research/DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json"
).read_bytes()
_SHIPPED_SUPPLEMENT = json.loads(_SHIPPED_SUPPLEMENT_DATA)


def _load_export_module(name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        REPO_ROOT / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _fingerprint(data: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def _feedback_queue(
    run_fingerprint: str,
    protocol_sha: str,
    protocol_version: str,
) -> dict[str, object]:
    missed = {
        "missed_move_id": "missed-move-v1:" + "d" * 64,
        "directional_bias": "long",
        "primary_endpoint_return_fraction": 0.20,
        "qualifies_as_missed_opportunity": True,
        "observation": {
            "canonical_asset_id": "bitcoin",
            "symbol": "BTC",
            "observed_at": "2022-01-01T00:00:00+00:00",
            "partition": "development",
            "data_quality_mode": "historical_ohlcv",
            "baseline_status": "warm",
            "liquidity_tier": "high",
            "observation_digest": "e" * 64,
        },
        "outcome": {
            "status": "matured",
            "primary_direction_adjusted_return": 0.20,
            "max_favorable_excursion": 0.25,
            "max_adverse_excursion": -0.03,
            "return_unit": "fraction",
        },
    }
    return build_targeted_review_queue(
        [],
        {"episodes": []},
        {"partitions": {}},
        {
            "protocol_version": protocol_version,
            "protocol_sha256": protocol_sha,
            "contract_digest": "c" * 64,
            "evidence_mode": "historical_replay",
            "missed_move_evaluation": {
                "missed_opportunity_count": 1,
                "missed_opportunities": [missed],
            },
        },
        run_fingerprint=run_fingerprint,
    )


def _empirical_tree(tmp_path: Path) -> tuple[Path, dict[str, object], list[str]]:
    root = tmp_path / "tree"
    root.mkdir()
    _write(root / "Makefile", b"verify:\n\t@true\n")
    _write(root / "event_fade_cache/other/kept.json", b'{"safe":true}\n')

    supplement_data = _SHIPPED_SUPPLEMENT_DATA
    supplement_value = _SHIPPED_SUPPLEMENT
    bundle = supplement_value["v1_report_bundle"]
    protocol_sha = str(bundle["protocol_sha256"])
    protocol_version = str(bundle["protocol_version"])
    v1_bundle_id = str(bundle["bundle_id"])

    contract_sha = "3" * 64
    protocol_rows = (
        (
            "research/DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.json",
            b'{"frozen":true}\n',
            "frozen_protocol_json",
            "protocol-v1",
        ),
        (
            "research/DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.md",
            b"# Frozen protocol\n",
            "frozen_protocol_markdown",
            "protocol-v1",
        ),
        (
            "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md",
            f"# Protocol v2 readiness\nReadiness SHA-256: `{contract_sha}`\n".encode(),
            "frozen_protocol_v2_readiness",
            "decision_radar_empirical_validation_v2_readiness_v1",
        ),
        (
            "crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2.py",
            b'CONTRACT_VERSION = "decision_radar_empirical_validation_v2_readiness_v1"\n',
            "frozen_protocol_v2_contract_implementation",
            "decision_radar_empirical_validation_v2_readiness_v1",
        ),
    )
    protocol_artifacts = []
    for path, data, role, semantic_id in protocol_rows:
        _write(root / path, data)
        protocol_artifacts.append(
            {
                "path": path,
                "role": role,
                "semantic_id": semantic_id,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    report_rows = []
    for index, (report_path, data) in enumerate(_SHIPPED_REPORT_DATA):
        _write(root / report_path, data)
        report_rows.append(
            {
                "path": report_path,
                "role": f"report_{index}",
                "semantic_id": f"report-{index}",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    supplement_id = str(supplement_value["supplement_id"])
    supplement_path = "research/DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json"
    _write(root / supplement_path, supplement_data)
    supplement = {
        "path": supplement_path,
        "role": "current_empirical_hardening_supplement",
        "semantic_id": "decision_radar_empirical_hardening_supplement_v1",
        "sha256": hashlib.sha256(supplement_data).hexdigest(),
        "size_bytes": len(supplement_data),
        "supplement_id": supplement_id,
        "v1_report_bundle_member": False,
    }

    run_ids = [character * 64 for character in "abcd"]
    roles = (
        "canonical_fixture_smoke",
        "canonical_medium",
        "current_selection",
        "current_final_test",
    )
    seal_sha = "f" * 64
    canonical_runs = []
    lab = root / _LAB
    queue: dict[str, object] | None = None
    for index, (run_id, role) in enumerate(zip(run_ids, roles, strict=True)):
        run_directory = lab / "runs" / run_id
        files = {"execution_summary.json": f'{{"run":{index}}}\n'.encode()}
        required = ["replay_run_manifest.json"]
        if index:
            seal = {
                "auto_apply": False,
                "protocol_sha256": protocol_sha,
                "research_only": True,
                "seal_sha256": seal_sha,
            }
            files["recommendation_seal.json"] = _canonical_json(seal)
            required.insert(0, "recommendation_seal.json")
        if role == "current_selection":
            queue = _feedback_queue(run_id, protocol_sha, protocol_version)
            files["targeted_review_queue.json"] = _canonical_json(queue)
        if role == "current_final_test":
            files["final_test_confirmation.json"] = b'{"status":"closed"}\n'
            required.insert(0, "final_test_confirmation.json")
        for name, data in files.items():
            _write(run_directory / name, data)
        manifest = {
            "artifacts": {name: _fingerprint(data) for name, data in files.items()},
            "auto_apply": False,
            "immutable": True,
            "protocol_sha256": protocol_sha,
            "protocol_version": protocol_version,
            "research_only": True,
            "run_fingerprint": run_id,
        }
        manifest_raw = _canonical_json(manifest)
        _write(run_directory / "replay_run_manifest.json", manifest_raw)
        canonical_runs.append(
            {
                "expected_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
                "required_files": required,
                "role": role,
                "run_fingerprint": run_id,
            }
        )

    assert queue is not None and queue["items"]
    item = queue["items"][0]
    event = build_feedback_event(
        queue,
        review_item_id=str(item["review_item_id"]),
        label="useful",
        observed_at="2026-07-16T12:00:00+00:00",
        reviewer_alias="owner",
    )
    _write(lab / "empirical_review_feedback.jsonl", feedback_json_bytes(event) + b"\n")
    _write(lab / "runs" / ("9" * 64) / "old.json", b'{"superseded":true}\n')
    _write(lab / "superseded_reports/old/REPORT.md", b"superseded report\n")

    policy = {
        "canonical_runs": canonical_runs,
        "canonical_semantics": {
            "current_final_test_run_fingerprint": run_ids[3],
            "current_selection_run_fingerprint": run_ids[2],
            "protocol_sha256": protocol_sha,
            "protocol_version": protocol_version,
            "recommendation_seal_sha256": seal_sha,
            "v1_bundle_id": v1_bundle_id,
        },
        "hardening_supplement": supplement,
        "history_archive": {
            "checksums_archive_path": "EMPIRICAL_ARTIFACT_HISTORY_SHA256SUMS.txt",
            "manifest_archive_path": "EMPIRICAL_ARTIFACT_HISTORY_MANIFEST.json",
            "output_filename": _HISTORY_OUTPUT,
        },
        "lab_root": _LAB.as_posix(),
        "limits": deepcopy(_LIMITS),
        "optional_feedback_path": (_LAB / "empirical_review_feedback.jsonl").as_posix(),
        "policy": {
            "canonical_evidence_is_immutable": True,
            "history_export_is_optional": True,
            "local_artifacts_are_never_deleted_or_moved": True,
            "standard_export_excludes_superseded_runs": True,
        },
        "protocol_artifacts": protocol_artifacts,
        "protocol_v2_readiness": {
            "contract_sha256": contract_sha,
            "document_path": "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md",
            "implementation_path": (
                "crypto_rsi_scanner/event_alpha/operations/"
                "empirical_validation_protocol_v2.py"
            ),
        },
        "reports": report_rows,
        "schema_id": "decision_radar.empirical_artifact_export_policy",
        "schema_version": 1,
        "standard_manifest_archive_path": _STANDARD_MANIFEST.as_posix(),
    }
    _write(
        root / "research/DECISION_RADAR_EMPIRICAL_ARTIFACT_POLICY.json",
        _canonical_json(policy),
    )
    _write(
        root / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json",
        (
            REPO_ROOT
            / "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
        ).read_bytes(),
    )
    return root, policy, run_ids


def _tree_fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix != ".zip"
    }


def _policy(root: Path) -> dict[str, object]:
    return json.loads(
        (root / "research/DECISION_RADAR_EMPIRICAL_ARTIFACT_POLICY.json").read_bytes()
    )


def _write_policy(root: Path, policy: dict[str, object]) -> None:
    _write(
        root / "research/DECISION_RADAR_EMPIRICAL_ARTIFACT_POLICY.json",
        _canonical_json(policy),
    )


def test_standard_export_keeps_only_bounded_canonical_empirical_evidence(tmp_path):
    module = _load_export_module("bounded_empirical_standard_export")
    root, policy, run_ids = _empirical_tree(tmp_path)
    output = root / "review.zip"
    before = _tree_fingerprints(root)

    assert module.main(root=root, out=output) == 0
    first_archive = output.read_bytes()
    os.chmod(root / "event_fade_cache/other/kept.json", 0o600)
    assert module.main(root=root, out=output) == 0
    assert output.read_bytes() == first_archive
    assert _tree_fingerprints(root) == before
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read(policy["standard_manifest_archive_path"]))
        assert all(((row.external_attr >> 16) & 0o777) == 0o644 for row in archive.infolist())

    assert "event_fade_cache/other/kept.json" not in names
    assert "event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json" in names
    assert all(
        any(f"/runs/{run_id}/" in name for run_id in run_ids)
        for name in names
        if "/decision_radar_research_lab/runs/" in name
    )
    assert not any("/runs/" + "9" * 64 + "/" in name for name in names)
    assert not any("superseded_reports" in name for name in names)
    assert manifest["canonical_semantics"] == policy["canonical_semantics"]
    assert manifest["hardening_supplement"] == policy["hardening_supplement"]
    assert manifest["protocol_v2_readiness"] == policy["protocol_v2_readiness"]
    supplement_rows = [
        row for row in manifest["entries"] if row["path"] == policy["hardening_supplement"]["path"]
    ]
    assert len(supplement_rows) == 1
    assert supplement_rows[0]["semantic_ids"]["supplement_id"] == policy[
        "hardening_supplement"
    ]["supplement_id"]
    assert supplement_rows[0]["semantic_ids"]["v1_report_bundle_member"] is False
    assert manifest["entry_count"] == len(manifest["entries"])


def test_optional_history_is_exact_disjoint_complement_and_does_not_mutate_tree(tmp_path):
    module = _load_export_module("bounded_empirical_history_export")
    root, policy, run_ids = _empirical_tree(tmp_path)
    standard = root / "review.zip"
    output = root / _HISTORY_OUTPUT
    before = _tree_fingerprints(root)

    assert module.main(root=root, out=standard) == 0
    assert module.empirical_history_main(root=root, out=output) == 0
    first_archive = output.read_bytes()
    assert module.empirical_history_main(root=root, out=output) == 0
    assert output.read_bytes() == first_archive
    assert _tree_fingerprints(root) == before
    with zipfile.ZipFile(standard) as archive:
        standard_lab = {
            name
            for name in archive.namelist()
            if name.startswith(_LAB.as_posix() + "/")
            and name != _STANDARD_MANIFEST.as_posix()
        }
    with zipfile.ZipFile(output) as archive:
        history_manifest = json.loads(
            archive.read(policy["history_archive"]["manifest_archive_path"])
        )
        checksums = archive.read(
            policy["history_archive"]["checksums_archive_path"]
        ).decode()
    history_paths = {row["path"] for row in history_manifest["entries"]}
    local_paths = {
        path.relative_to(root).as_posix()
        for path in (root / _LAB).rglob("*")
        if path.is_file()
    }

    assert standard_lab.isdisjoint(history_paths)
    assert standard_lab | history_paths == local_paths
    assert any("/runs/" + "9" * 64 + "/old.json" in name for name in history_paths)
    assert not any(any(f"/runs/{run_id}/" in name for run_id in run_ids) for name in history_paths)
    assert history_manifest["complement_of_standard_empirical_selection"] is True
    assert checksums == "".join(
        f"{row['sha256']}  {row['path']}\n" for row in history_manifest["entries"]
    )


def test_canonical_manifest_reseal_drift_fails_closed_and_preserves_archive(tmp_path):
    module = _load_export_module("bounded_empirical_manifest_reseal_drift")
    root, _, run_ids = _empirical_tree(tmp_path)
    output = root / "review.zip"
    assert module.main(root=root, out=output) == 0
    previous = output.read_bytes()
    run = root / _LAB / "runs" / run_ids[0]
    changed = b'{"resealed_drift":true}\n'
    _write(run / "execution_summary.json", changed)
    manifest_path = run / "replay_run_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"]["execution_summary.json"] = _fingerprint(changed)
    _write(manifest_path, _canonical_json(manifest))

    assert module.main(root=root, out=output) == 1
    assert output.read_bytes() == previous
    assert not output.with_name(f"{output.name}.tmp").exists()


@pytest.mark.parametrize(
    "relative_path",
    [
        "research/DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md",
        "research/DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json",
        "crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2.py",
    ],
)
def test_frozen_tracked_artifact_drift_fails_closed(tmp_path, relative_path):
    module = _load_export_module("bounded_empirical_tracked_drift_" + relative_path.replace("/", "_"))
    root, _, _ = _empirical_tree(tmp_path)
    _write(root / relative_path, b"drift\n")

    assert module.main(root=root, out=root / "review.zip") == 1


def test_supplement_is_strictly_bound_to_exact_seven_report_bytes(tmp_path):
    module = _load_export_module("bounded_empirical_supplement_report_binding")
    root, _, _ = _empirical_tree(tmp_path)
    report_path = root / _REPORT_PATHS[0]
    replacement = report_path.read_bytes() + b"semantic drift\n"
    _write(report_path, replacement)
    policy = _policy(root)
    row = next(
        item for item in policy["reports"] if item["path"] == _REPORT_PATHS[0]
    )
    row["sha256"] = hashlib.sha256(replacement).hexdigest()
    _write_policy(root, policy)

    assert module.main(root=root, out=root / "review.zip") == 1


def test_semantic_validation_to_manifest_race_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_semantic_manifest_race")
    root, policy, _ = _empirical_tree(tmp_path)
    output = root / "review.zip"
    assert module.main(root=root, out=output) == 0
    previous = output.read_bytes()
    supplement_path = root / str(policy["hardening_supplement"]["path"])
    original_validate = module._validate_empirical_hardening_supplement
    mutated = False

    def validating_then_mutating(*, payload, report_payloads):
        nonlocal mutated
        result = original_validate(
            payload=payload,
            report_payloads=report_payloads,
        )
        supplement_path.write_bytes(payload + b"semantic-to-manifest-race\n")
        mutated = True
        return result

    module._validate_empirical_hardening_supplement = validating_then_mutating
    try:
        assert module.main(root=root, out=output) == 1
    finally:
        module._validate_empirical_hardening_supplement = original_validate

    assert mutated is True
    assert output.read_bytes() == previous
    assert not output.with_name(f"{output.name}.tmp").exists()


def test_protocol_v2_contract_digest_must_be_visible_in_bound_document(tmp_path):
    module = _load_export_module("bounded_empirical_v2_contract")
    root, _, _ = _empirical_tree(tmp_path)
    document = root / "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md"
    replacement = b"# Digest omitted\n"
    _write(document, replacement)
    policy = _policy(root)
    row = next(item for item in policy["protocol_artifacts"] if item["path"] == document.relative_to(root).as_posix())
    row["sha256"] = hashlib.sha256(replacement).hexdigest()
    _write_policy(root, policy)

    assert module.main(root=root, out=root / "review.zip") == 1


def test_invalid_optional_feedback_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_feedback_invalid")
    root, _, _ = _empirical_tree(tmp_path)
    _write(root / _LAB / "empirical_review_feedback.jsonl", b'{"not":"canonical feedback"}\n')

    assert module.main(root=root, out=root / "review.zip") == 1


@pytest.mark.parametrize("noise_name", ["stray.tmp", ".DS_Store", "swap.swp"])
def test_empirical_lab_noise_is_not_silently_omitted(tmp_path, noise_name):
    module = _load_export_module("bounded_empirical_noise_" + noise_name.replace(".", "_"))
    root, _, _ = _empirical_tree(tmp_path)
    _write(root / _LAB / noise_name, b"noise\n")

    assert module.main(root=root, out=root / "review.zip") == 1


@pytest.mark.parametrize("control_name", ["ambiguous\nrow.json", "tab\trow.json"])
def test_empirical_lab_control_character_name_fails_closed(tmp_path, control_name):
    module = _load_export_module("bounded_empirical_control_name_" + str(len(control_name)))
    root, _, _ = _empirical_tree(tmp_path)
    _write(root / _LAB / control_name, b"ambiguous\n")

    assert module.main(root=root, out=root / "review.zip") == 1


def test_standard_synthetic_manifest_collision_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_manifest_collision")
    root, _, _ = _empirical_tree(tmp_path)
    _write(root / _STANDARD_MANIFEST, b'{}\n')

    assert module.main(root=root, out=root / "review.zip") == 1


def test_policy_present_without_lab_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_policy_without_lab")
    root, _, _ = _empirical_tree(tmp_path)
    (root / _LAB).rename(root / "lab.removed")

    assert module.main(root=root, out=root / "review.zip") == 1


def test_policy_cannot_raise_empirical_bounds(tmp_path):
    module = _load_export_module("bounded_empirical_policy_limit_tamper")
    root, _, _ = _empirical_tree(tmp_path)
    policy = _policy(root)
    policy["limits"]["max_lab_file_count"] += 1
    _write_policy(root, policy)

    assert module.main(root=root, out=root / "review.zip") == 1


def test_empirical_lab_file_count_bound_is_enforced(tmp_path):
    module = _load_export_module("bounded_empirical_file_count")
    root, _, _ = _empirical_tree(tmp_path)
    overflow = root / _LAB / "overflow"
    existing_count = sum(path.is_file() for path in (root / _LAB).rglob("*"))
    for index in range(_LIMITS["max_lab_file_count"] - existing_count + 1):
        _write(overflow / f"{index:04d}.json", b"{}\n")

    assert module.main(root=root, out=root / "review.zip") == 1


def test_empirical_lab_without_checked_policy_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_missing_policy")
    root = tmp_path / "tree"
    _write(root / _LAB / "run.json", b"{}\n")

    assert module.main(root=root, out=root / "review.zip") == 1


def test_policy_cannot_redirect_history_output_or_synthetic_paths(tmp_path):
    module = _load_export_module("bounded_empirical_history_redirect")
    root, _, _ = _empirical_tree(tmp_path)
    victim = root / "victim.txt"
    _write(victim, b"preserve me\n")
    policy = _policy(root)
    policy["history_archive"]["output_filename"] = "victim.txt"
    _write_policy(root, policy)

    assert module.empirical_history_main(root=root) == 1
    assert victim.read_bytes() == b"preserve me\n"


def test_history_explicit_nonfixed_output_is_rejected(tmp_path):
    module = _load_export_module("bounded_empirical_history_explicit_redirect")
    root, _, _ = _empirical_tree(tmp_path)
    outside = tmp_path / "outside.zip"

    assert module.empirical_history_main(root=root, out=outside) == 1
    assert not outside.exists()


@pytest.mark.parametrize("history", [False, True])
def test_preexisting_unowned_candidate_is_preserved(tmp_path, history):
    module = _load_export_module("bounded_empirical_preexisting_candidate_" + str(history))
    root, _, _ = _empirical_tree(tmp_path)
    output = root / (_HISTORY_OUTPUT if history else "review.zip")
    candidate = output.with_name(output.name + ".tmp")
    marker = b"unowned candidate\n"
    _write(candidate, marker)

    result = (
        module.empirical_history_main(root=root, out=output)
        if history
        else module.main(root=root, out=output)
    )
    assert result == 1
    assert candidate.read_bytes() == marker
    assert not output.exists()


@pytest.mark.parametrize("history", [False, True])
def test_post_write_source_content_drift_blocks_publish(tmp_path, history):
    module = _load_export_module("bounded_empirical_source_drift_" + str(history))
    root, policy, _ = _empirical_tree(tmp_path)
    output = root / (_HISTORY_OUTPUT if history else "review.zip")
    target = (
        root / _LAB / "runs" / ("9" * 64) / "old.json"
        if history
        else root / str(policy["hardening_supplement"]["path"])
    )
    original_write = module._write_file_to_zip
    mutated = False

    def mutating_write(archive, path, arcname, **kwargs):
        nonlocal mutated
        original_write(archive, path, arcname, **kwargs)
        if path == target and not mutated:
            path.write_bytes(b"post-write source drift\n")
            mutated = True

    module._write_file_to_zip = mutating_write
    try:
        result = (
            module.empirical_history_main(root=root, out=output)
            if history
            else module.main(root=root, out=output)
        )
    finally:
        module._write_file_to_zip = original_write

    assert mutated is True
    assert result == 1
    assert not output.exists()


@pytest.mark.parametrize("swap_phase", ["candidate_create", "final_validation"])
def test_history_output_root_swap_fails_closed(tmp_path, swap_phase):
    module = _load_export_module("bounded_empirical_output_root_swap_" + swap_phase)
    root, _, _ = _empirical_tree(tmp_path)
    output = root / _HISTORY_OUTPUT
    candidate_name = output.name + ".tmp"
    displaced = tmp_path / "tree.checked"
    outside = tmp_path / "outside-output"
    outside.mkdir()
    private = outside / "private.txt"
    private.write_bytes(b"outside private material\n")
    swapped = False

    def swap_root() -> None:
        nonlocal swapped
        root.rename(displaced)
        root.symlink_to(outside, target_is_directory=True)
        swapped = True

    original_open = module.os.open
    original_validate = module._validate_archive_entries

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        if (
            swap_phase == "candidate_create"
            and path == candidate_name
            and dir_fd is not None
            and not swapped
        ):
            swap_root()
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def racing_validate(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        if swap_phase == "final_validation" and not swapped:
            swap_root()
        return result

    module.os.open = racing_open
    module.os.supports_dir_fd.add(racing_open)
    module._validate_archive_entries = racing_validate
    try:
        assert module.empirical_history_main(root=root, out=output) == 1
    finally:
        module.os.open = original_open
        module.os.supports_dir_fd.discard(racing_open)
        module._validate_archive_entries = original_validate

    assert swapped is True
    assert private.read_bytes() == b"outside private material\n"
    assert not (outside / _HISTORY_OUTPUT).exists()
    assert not (displaced / candidate_name).exists()


def test_lab_symlink_redirection_fails_closed(tmp_path):
    module = _load_export_module("bounded_empirical_symlink")
    root, _, _ = _empirical_tree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    _write(outside / "private.json", b'{"private":true}\n')
    linked = root / _LAB / "linked"
    linked.symlink_to(outside, target_is_directory=True)

    assert module.main(root=root, out=root / "review.zip") == 1
    assert not (root / "review.zip").exists()


@pytest.mark.parametrize("swap_component", ["decision_radar_research_lab", "runs"])
def test_descriptor_walk_directory_swap_fails_closed(tmp_path, swap_component):
    module = _load_export_module("bounded_empirical_walk_swap_" + swap_component)
    root, _, _ = _empirical_tree(tmp_path)
    lab = root / _LAB
    target = lab if swap_component == "decision_radar_research_lab" else lab / "runs"
    displaced = target.with_name(target.name + ".checked")
    outside = tmp_path / ("outside-" + swap_component)
    _write(outside / "private.json", b"outside private material\n")
    original_open = module.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == swap_component and dir_fd is not None and not swapped:
            target.rename(displaced)
            target.symlink_to(outside, target_is_directory=True)
            swapped = True
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    module.os.open = racing_open
    try:
        assert module.main(root=root, out=root / "review.zip") == 1
    finally:
        module.os.open = original_open

    assert swapped is True
    assert not (root / "review.zip").exists()
    assert (outside / "private.json").read_bytes() == b"outside private material\n"


def test_optional_history_make_target_uses_selected_python():
    output = subprocess.check_output(
        ["make", "-n", "export-empirical-artifact-history", "PYTHON=chosen-python"],
        cwd=REPO_ROOT,
        text=True,
    )

    assert output.strip() == "chosen-python scripts/export_empirical_artifact_history.py"
