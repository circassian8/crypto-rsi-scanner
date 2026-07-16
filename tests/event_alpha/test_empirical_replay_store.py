from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.empirical_replay_store import (
    MANIFEST_FILENAME,
    code_fingerprint,
    load_manifest,
    load_verified_run,
    run_fingerprint,
    write_immutable_run,
)


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def _safety():
    return {
        "research_only": True,
        "auto_apply": False,
        "provider_calls": 0,
        "authorization_mutations": 0,
        "telegram_sends": 0,
        "trades": 0,
        "orders": 0,
        "event_alpha_paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "dashboard_authority_mutations": 0,
    }


def _write(tmp_path: Path, artifacts=None):
    return write_immutable_run(
        tmp_path / "lab",
        protocol_version="v1",
        protocol_sha256=_A,
        input_sha256=_B,
        code_sha256=_C,
        configuration={"mode": "smoke", "top_n": 3},
        artifacts=artifacts or {"ideas.jsonl": b'{"id":"one"}\n'},
        metrics={"ideas": 1, "runtime_seconds": 0.1},
        safety=_safety(),
    )


def test_immutable_run_writes_manifest_and_exact_resume(tmp_path: Path) -> None:
    first = _write(tmp_path)
    second = _write(tmp_path)

    assert first.resumed is False
    assert second.resumed is True
    assert first.run_dir == second.run_dir
    assert first.run_fingerprint == second.run_fingerprint
    manifest = load_manifest(first.run_dir)
    assert manifest["run_fingerprint"] == first.run_fingerprint
    assert manifest["artifacts"]["ideas.jsonl"]["size_bytes"] == len(b'{"id":"one"}\n')
    assert manifest["safety"] == _safety()
    verified_manifest, payloads = load_verified_run(first.run_dir)
    assert verified_manifest == manifest
    assert payloads["ideas.jsonl"] == b'{"id":"one"}\n'
    assert payloads[MANIFEST_FILENAME] == (first.run_dir / MANIFEST_FILENAME).read_bytes()


def test_immutable_run_rejects_mutation_and_extra_files(tmp_path: Path) -> None:
    stored = _write(tmp_path)
    (stored.run_dir / "ideas.jsonl").write_bytes(b"changed\n")
    with pytest.raises(RuntimeError, match="immutable_drift"):
        _write(tmp_path)

    # Restore the exact leaf, then prove an unexpected leaf also closes the run.
    (stored.run_dir / "ideas.jsonl").write_bytes(b'{"id":"one"}\n')
    (stored.run_dir / "extra.txt").write_text("extra")
    with pytest.raises(RuntimeError, match="artifact_set_drift"):
        _write(tmp_path)


def test_immutable_run_rejects_unsafe_names_sizes_and_safety(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="name invalid"):
        _write(tmp_path, {"../escape": b"x"})
    bad = _safety()
    bad["provider_calls"] = 1
    with pytest.raises(ValueError, match="provider_calls"):
        write_immutable_run(
            tmp_path / "lab",
            protocol_version="v1",
            protocol_sha256=_A,
            input_sha256=_B,
            code_sha256=_C,
            configuration={"mode": "smoke"},
            artifacts={"ideas.jsonl": b""},
            metrics={},
            safety=bad,
        )
    with pytest.raises(ValueError, match="sensitive value"):
        _write(tmp_path, {"leak.json": b'{"api_key":"should-not-be-here"}\n'})
    with pytest.raises(ValueError, match="machine path"):
        _write(tmp_path, {"leak.json": b'{"path":"/Users/operator/private.json"}\n'})


def test_immutable_run_rejects_symlink_namespace(tmp_path: Path) -> None:
    root = tmp_path / "lab"
    (root / "runs").mkdir(parents=True)
    fingerprint = run_fingerprint(
        protocol_sha256=_A,
        input_sha256=_B,
        code_sha256=_C,
        configuration={"mode": "smoke", "top_n": 3},
    )
    target = tmp_path / "outside"
    target.mkdir()
    (root / "runs" / fingerprint).symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="namespace_unsafe"):
        _write(tmp_path)


def test_code_fingerprint_is_content_bound_and_rejects_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("VALUE = 1\n")
    first = code_fingerprint({"source.py": source})
    source.write_text("VALUE = 2\n")
    second = code_fingerprint({"source.py": source})
    assert first != second

    link = tmp_path / "link.py"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="path invalid"):
        code_fingerprint({"link.py": link})


def test_manifest_is_canonical_json_and_contains_no_absolute_output_path(tmp_path: Path) -> None:
    stored = _write(tmp_path)
    raw = (stored.run_dir / MANIFEST_FILENAME).read_text()
    manifest = json.loads(raw)

    assert str(tmp_path) not in raw
    assert raw.endswith("\n")
    assert manifest["configuration"] == {"mode": "smoke", "top_n": 3}


def test_manifest_load_rejects_symlink_leaf_and_self_inconsistency(tmp_path: Path) -> None:
    stored = _write(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(stored.run_dir, target_is_directory=True)
    with pytest.raises(RuntimeError, match="namespace_unsafe"):
        load_manifest(alias)

    manifest_path = stored.run_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["configuration"]["top_n"] = 4
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(RuntimeError, match="run_fingerprint_mismatch"):
        load_manifest(stored.run_dir)


def test_output_root_symlink_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="output_root_unsafe"):
        write_immutable_run(
            linked,
            protocol_version="v1",
            protocol_sha256=_A,
            input_sha256=_B,
            code_sha256=_C,
            configuration={"mode": "smoke"},
            artifacts={"ideas.jsonl": b""},
            metrics={},
            safety=_safety(),
        )
