"""Immutable, fingerprint-addressed storage for empirical replay runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..radar import market_anomaly_receipt


MANIFEST_FILENAME = "replay_run_manifest.json"
MANIFEST_SCHEMA_ID = "decision_radar.empirical_replay_run_manifest"
MANIFEST_SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_BUNDLE_BYTES = 96 * 1024 * 1024
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_BYTES = re.compile(
    rb"(?:authorization[\"']?\s*:\s*[\"']?bearer|(?:api[_-]?key|access[_-]?token|password|passwd|secret|credential)[\"']?\s*[:=]\s*[\"']?[^\s,}\]]+|-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----)",
    re.IGNORECASE,
)
_MACHINE_PATH_BYTES = re.compile(rb"(?:/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\Users\\[^\\\s]+\\)")


@dataclass(frozen=True)
class StoredReplayRun:
    run_dir: Path
    run_fingerprint: str
    manifest: dict[str, Any]
    resumed: bool


def run_fingerprint(
    *,
    protocol_sha256: str,
    input_sha256: str,
    code_sha256: str,
    configuration: Mapping[str, Any],
) -> str:
    for value in (protocol_sha256, input_sha256, code_sha256):
        if not _DIGEST.fullmatch(str(value)):
            raise ValueError("replay fingerprint input digest invalid")
    payload = {
        "protocol_sha256": protocol_sha256,
        "input_sha256": input_sha256,
        "code_sha256": code_sha256,
        "configuration": _json_safe_mapping(configuration),
    }
    return _sha256(canonical_json_bytes(payload))


def write_immutable_run(
    output_root: str | Path,
    *,
    protocol_version: str,
    protocol_sha256: str,
    input_sha256: str,
    code_sha256: str,
    configuration: Mapping[str, Any],
    artifacts: Mapping[str, bytes],
    metrics: Mapping[str, Any],
    safety: Mapping[str, Any],
) -> StoredReplayRun:
    """Write or resume one exact immutable replay bundle.

    The run leaf is derived solely from protocol, input, code, and configuration
    fingerprints. Existing exact bytes resume; any mutation or extra leaf fails
    closed. No latest pointer or production authority is written here.
    """

    clean_artifacts = _validate_artifacts(artifacts)
    clean_configuration = _json_safe_mapping(configuration)
    clean_metrics = _json_safe_mapping(metrics)
    clean_safety = _json_safe_mapping(safety)
    if clean_safety.get("research_only") is not True or clean_safety.get("auto_apply") is not False:
        raise ValueError("replay safety contract invalid")
    for field in (
        "provider_calls",
        "authorization_mutations",
        "telegram_sends",
        "trades",
        "orders",
        "event_alpha_paper_trades",
        "normal_rsi_writes",
        "event_alpha_triggered_fade",
        "dashboard_authority_mutations",
    ):
        if type(clean_safety.get(field)) is not int or clean_safety[field] != 0:
            raise ValueError(f"replay safety counter invalid:{field}")
    fingerprint = run_fingerprint(
        protocol_sha256=protocol_sha256,
        input_sha256=input_sha256,
        code_sha256=code_sha256,
        configuration=clean_configuration,
    )
    artifact_manifest = {
        name: {"sha256": _sha256(payload), "size_bytes": len(payload)}
        for name, payload in clean_artifacts.items()
    }
    manifest = {
        "schema_id": MANIFEST_SCHEMA_ID,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_fingerprint": fingerprint,
        "protocol_version": str(protocol_version),
        "protocol_sha256": protocol_sha256,
        "input_sha256": input_sha256,
        "code_sha256": code_sha256,
        "configuration": clean_configuration,
        "artifacts": artifact_manifest,
        "metrics": clean_metrics,
        "safety": clean_safety,
        "immutable": True,
        "research_only": True,
        "auto_apply": False,
    }
    payloads = {MANIFEST_FILENAME: canonical_json_bytes(manifest), **clean_artifacts}
    expected_names = tuple(payloads)
    root = _prepare_output_root(output_root)
    run_dir = root / "runs" / fingerprint
    (root / "runs").mkdir(mode=0o700, exist_ok=True)
    _assert_directory(root / "runs")
    if run_dir.exists() or run_dir.is_symlink():
        observed = _read_existing_bundle(run_dir, expected_names)
        if observed != payloads:
            raise RuntimeError("empirical_replay_run_immutable_drift")
        return StoredReplayRun(run_dir, fingerprint, manifest, True)
    market_anomaly_receipt.write_artifacts_atomic(
        run_dir,
        payloads=payloads,
        expected_names=expected_names,
    )
    observed = _read_existing_bundle(run_dir, expected_names)
    if observed != payloads:
        raise RuntimeError("empirical_replay_run_post_write_drift")
    return StoredReplayRun(run_dir, fingerprint, manifest, False)


def load_manifest(run_dir: str | Path) -> dict[str, Any]:
    """Load one exact manifest after validating every immutable run artifact."""

    manifest, _payloads = load_verified_run(run_dir)
    return manifest


def load_verified_run(
    run_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Return a complete descriptor-read bundle after exact manifest checks.

    This is intentionally all-or-nothing.  Consumers such as the sealed final-
    test loader must not validate one receipt while reading its source
    simulation from a different namespace snapshot.
    """

    supplied = Path(run_dir).expanduser()
    if supplied.is_symlink():
        raise RuntimeError("empirical_replay_run_namespace_unsafe")
    directory = supplied.resolve(strict=True)
    payloads = _read_existing_bundle(directory, tuple(sorted(
        path.name for path in directory.iterdir() if path.name != ".DS_Store"
    )))
    raw = payloads.get(MANIFEST_FILENAME)
    if raw is None:
        raise RuntimeError("empirical_replay_manifest_missing")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("empirical_replay_manifest_invalid") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError("empirical_replay_manifest_invalid")
    manifest = dict(value)
    if raw != canonical_json_bytes(manifest):
        raise RuntimeError("empirical_replay_manifest_invalid:noncanonical_json")
    errors = validate_manifest(manifest, payloads, expected_run_fingerprint=directory.name)
    if errors:
        raise RuntimeError("empirical_replay_manifest_invalid:" + ";".join(errors))
    return manifest, payloads


def validate_manifest(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    *,
    expected_run_fingerprint: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_id") != MANIFEST_SCHEMA_ID or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("schema_invalid")
    if manifest.get("immutable") is not True or manifest.get("research_only") is not True or manifest.get("auto_apply") is not False:
        errors.append("state_invalid")
    observed_fingerprint = str(manifest.get("run_fingerprint") or "")
    if not _DIGEST.fullmatch(observed_fingerprint):
        errors.append("run_fingerprint_invalid")
    for field in ("protocol_sha256", "input_sha256", "code_sha256"):
        if not _DIGEST.fullmatch(str(manifest.get(field) or "")):
            errors.append(f"{field}_invalid")
    configuration = manifest.get("configuration")
    if isinstance(configuration, Mapping) and all(
        _DIGEST.fullmatch(str(manifest.get(field) or ""))
        for field in ("protocol_sha256", "input_sha256", "code_sha256")
    ):
        calculated = run_fingerprint(
            protocol_sha256=str(manifest["protocol_sha256"]),
            input_sha256=str(manifest["input_sha256"]),
            code_sha256=str(manifest["code_sha256"]),
            configuration=configuration,
        )
        if observed_fingerprint != calculated:
            errors.append("run_fingerprint_mismatch")
    else:
        errors.append("configuration_invalid")
    if expected_run_fingerprint is not None and observed_fingerprint != expected_run_fingerprint:
        errors.append("run_leaf_mismatch")
    safety = manifest.get("safety")
    if not isinstance(safety, Mapping) or safety.get("research_only") is not True or safety.get("auto_apply") is not False:
        errors.append("safety_invalid")
    elif any(
        type(safety.get(field)) is not int or safety.get(field) != 0
        for field in (
            "provider_calls",
            "authorization_mutations",
            "telegram_sends",
            "trades",
            "orders",
            "event_alpha_paper_trades",
            "normal_rsi_writes",
            "event_alpha_triggered_fade",
            "dashboard_authority_mutations",
        )
    ):
        errors.append("safety_counter_invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        errors.append("artifacts_invalid")
        return errors
    if set(artifacts) != set(payloads) - {MANIFEST_FILENAME}:
        errors.append("artifact_set_mismatch")
    for name, expected in artifacts.items():
        if not isinstance(expected, Mapping) or name not in payloads:
            errors.append(f"artifact_invalid:{name}")
            continue
        if expected.get("sha256") != _sha256(payloads[name]) or expected.get("size_bytes") != len(payloads[name]):
            errors.append(f"artifact_fingerprint_mismatch:{name}")
    return errors


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def code_fingerprint(paths: Mapping[str, str | Path]) -> str:
    rows: list[dict[str, str]] = []
    for name, supplied in sorted(paths.items()):
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError("code fingerprint name invalid")
        payload = _read_regular_file_no_follow(Path(supplied).expanduser())
        rows.append({"name": name, "sha256": _sha256(payload)})
    if not rows:
        raise ValueError("code fingerprint paths required")
    return _sha256(canonical_json_bytes(rows))


def _validate_artifacts(artifacts: Mapping[str, bytes]) -> dict[str, bytes]:
    if not artifacts or MANIFEST_FILENAME in artifacts:
        raise ValueError("replay artifact bundle invalid")
    clean: dict[str, bytes] = {}
    total = 0
    for name, payload in artifacts.items():
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
            raise ValueError("replay artifact name invalid")
        if not isinstance(payload, bytes) or len(payload) > MAX_ARTIFACT_BYTES:
            raise ValueError("replay artifact payload invalid")
        if _SENSITIVE_BYTES.search(payload):
            raise ValueError("replay artifact sensitive value rejected")
        if _MACHINE_PATH_BYTES.search(payload):
            raise ValueError("replay artifact machine path rejected")
        total += len(payload)
        clean[name] = payload
    if total > MAX_BUNDLE_BYTES:
        raise ValueError("replay artifact bundle too large")
    return clean


def _prepare_output_root(output_root: str | Path) -> Path:
    supplied = Path(output_root).expanduser()
    if supplied.is_symlink():
        raise RuntimeError("empirical_replay_output_root_unsafe")
    supplied.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = supplied.resolve(strict=True)
    _assert_directory(root)
    return root


def _assert_directory(path: Path) -> None:
    status = path.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISDIR(status.st_mode):
        raise RuntimeError("empirical_replay_output_root_unsafe")


def _read_existing_bundle(directory: Path, expected_names: tuple[str, ...]) -> dict[str, bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError("empirical_replay_run_namespace_unsafe")
    observed_names = tuple(sorted(path.name for path in directory.iterdir()))
    if observed_names != tuple(sorted(expected_names)):
        raise RuntimeError("empirical_replay_run_artifact_set_drift")
    identity = market_anomaly_receipt.namespace_identity(directory)
    return market_anomaly_receipt.artifact_payloads(
        directory,
        namespace_identity=identity,
        paths=tuple(directory / name for name in expected_names),
        expected_names=expected_names,
    )


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        encoded = canonical_json_bytes(dict(value))
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("replay mapping is not canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("replay mapping invalid")
    return decoded


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_regular_file_no_follow(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("code fingerprint path invalid") from exc
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise ValueError("code fingerprint path invalid")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


__all__ = [
    "MANIFEST_FILENAME",
    "StoredReplayRun",
    "canonical_json_bytes",
    "code_fingerprint",
    "load_manifest",
    "load_verified_run",
    "run_fingerprint",
    "validate_manifest",
    "write_immutable_run",
]
