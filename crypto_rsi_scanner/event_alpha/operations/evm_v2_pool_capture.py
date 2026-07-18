"""Immutable local-import boundary for exact EVM v2 pool snapshots.

This module never contacts an RPC provider.  It can validate an operator-made
bundle without writes, or confirmation-gated import can seal the exact bundle
and its deterministic projection in one immutable namespace.  No latest
pointer is published: consumers must name the exact capture explicitly.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterator, Mapping, Sequence

from .common import secret_hits_in_text
from .evm_v2_pool_snapshot import (
    CAPTURE_MODE_OPERATOR_IMPORT,
    EvmV2PoolSnapshotError,
    normalize_evm_v2_pool_snapshot,
    read_capture_bytes,
)
from .market_no_send_io import (
    _open_verified_namespace_dir,
    ensure_safe_namespace_dir,
    parse_json_object_bytes,
    read_regular_bytes,
    write_bytes_immutable,
)
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = "decision_radar_evm_v2_pool_immutable_import_v1"
RAW_FILENAME = "source_rpc_bundle.json"
SNAPSHOT_FILENAME = "normalized_snapshot.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
_LOCK_FILENAME = ".radar_evm_v2_pool_capture.lock"
_NAMESPACE_RE = re.compile(
    r"^radar_evm_v2_pool_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_FORBIDDEN_IMPORT_PATH_PARTS = frozenset(
    {"fixture", "fixtures", "mock", "mocks", "replay", "test", "tests"}
)


class EvmV2PoolCaptureError(ValueError):
    """Raised when immutable local import or validation fails closed."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode()


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _artifact_descriptor(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


def _capture_identity(raw: bytes, snapshot_raw: bytes, acquired_at: str) -> tuple[str, str]:
    try:
        completed = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise EvmV2PoolCaptureError("capture_acquired_at_invalid") from exc
    seed = _canonical_bytes(
        {
            "contract_version": CONTRACT_VERSION,
            "raw_sha256": _sha256(raw),
            "snapshot_sha256": _sha256(snapshot_raw),
        }
    )
    capture_id = _sha256(seed)
    timestamp = completed.strftime("%Y%m%dt%H%M%S%fz")
    return f"radar_evm_v2_pool_{timestamp}_{capture_id[:12]}", capture_id


def _validate_import_path(path: Path) -> None:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvmV2PoolCaptureError("import_source_unreadable") from exc
    if any(part.casefold() in _FORBIDDEN_IMPORT_PATH_PARTS for part in resolved.parts):
        raise EvmV2PoolCaptureError("import_source_nonlive_path_rejected")


def _validated_local_import(path: str | Path) -> tuple[bytes, dict[str, Any]]:
    source = Path(path)
    _validate_import_path(source)
    try:
        raw = read_capture_bytes(source)
        projection = normalize_evm_v2_pool_snapshot(
            raw, expected_capture_mode=CAPTURE_MODE_OPERATOR_IMPORT
        )
    except EvmV2PoolSnapshotError as exc:
        raise EvmV2PoolCaptureError(str(exc)) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvmV2PoolCaptureError("import_source_utf8_invalid") from exc
    secret_markers = (
        '"api_key"', '"api-key"', '"authorization"', '"auth_token"',
        '"private_key"', '"secret"', '"x-api-key"', "bearer ", "sk-",
        "telegram_bot_token",
    )
    if secret_hits_in_text(text) or any(
        marker in text.casefold() for marker in secret_markers
    ):
        raise EvmV2PoolCaptureError("import_source_secret_like_value_rejected")
    return raw, projection


def validate_local_import(path: str | Path) -> dict[str, Any]:
    """Validate one explicit operator bundle without provider calls or writes."""

    _raw, projection = _validated_local_import(path)
    return projection


def _common_values(
    namespace: str,
    capture_id: str,
    projection: Mapping[str, object],
) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "source_authority": "operator_attested_immutable_local_import",
        "authority_basis": "operator_supplied_exact_rpc_bundle",
        "transport_captured_by_project": False,
        "provider_id": projection["provider_id"],
        "chain_id": projection["chain_id"],
        "dex_id": projection["dex_id"],
        "pool_address": projection["pool_address"],
        "block_number": projection["block_number"],
        "block_hash": projection["block_hash"],
        "acquired_at": projection["acquired_at"],
        "source_lineage_id": projection["source_lineage_id"],
        "evidence_authority_eligible": True,
        "protocol_v2_input_quality_eligible": True,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "research_only": True,
        "no_send": True,
        "provider_calls": 0,
        "credentials_read": 0,
        "private_data_read": 0,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


def _capture_payloads(
    raw: bytes, projection: Mapping[str, object]
) -> tuple[str, str, bytes, bytes, bytes, bytes]:
    snapshot_raw = _pretty_bytes(projection)
    namespace, capture_id = _capture_identity(
        raw, snapshot_raw, str(projection["acquired_at"])
    )
    common = _common_values(namespace, capture_id, projection)
    manifest = {
        "schema_id": "decision_radar.evm_v2_pool_capture_manifest",
        "schema_version": 1,
        "status": "complete",
        **common,
        "artifacts": [
            _artifact_descriptor(RAW_FILENAME, "exact_operator_rpc_bundle", raw),
            _artifact_descriptor(
                SNAPSHOT_FILENAME, "deterministic_normalized_snapshot", snapshot_raw
            ),
        ],
    }
    manifest_raw = _pretty_bytes(manifest)
    receipt = {
        "schema_id": "decision_radar.evm_v2_pool_completion_receipt",
        "schema_version": 1,
        "status": "complete",
        **common,
        "manifest": {
            "name": MANIFEST_FILENAME,
            **_fingerprint(manifest_raw),
        },
    }
    return (
        namespace,
        capture_id,
        raw,
        snapshot_raw,
        manifest_raw,
        _pretty_bytes(receipt),
    )


@contextmanager
def _publication_lock(base: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = (
                os.O_RDWR
                | os.O_CREAT
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = os.open(_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise EvmV2PoolCaptureError("capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except EvmV2PoolCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise EvmV2PoolCaptureError("capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _read_capture_files(namespace_dir: Path) -> dict[str, bytes]:
    expected = {RAW_FILENAME, SNAPSHOT_FILENAME, MANIFEST_FILENAME, RECEIPT_FILENAME}
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            names = set(os.listdir(namespace_fd))
        if names != expected:
            raise EvmV2PoolCaptureError("capture_artifact_set_invalid")
        files = {}
        for name in sorted(expected):
            raw = read_regular_bytes(namespace_dir / name)
            if raw is None:
                raise EvmV2PoolCaptureError("capture_artifact_missing")
            files[name] = raw
        return files
    except EvmV2PoolCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise EvmV2PoolCaptureError("capture_artifact_unreadable") from exc


def _parse_object(raw: bytes, reason: str) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise EvmV2PoolCaptureError(reason) from exc


def _validate_common(
    value: Mapping[str, object], expected: Mapping[str, object]
) -> None:
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise EvmV2PoolCaptureError("capture_common_contract_invalid")


def validate_capture(
    artifact_base_dir: str | Path, namespace: str
) -> dict[str, object]:
    """Re-derive and validate one exact immutable capture namespace."""

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise EvmV2PoolCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    namespace_dir = base / namespace
    files = _read_capture_files(namespace_dir)
    raw = files[RAW_FILENAME]
    try:
        projection = normalize_evm_v2_pool_snapshot(
            raw, expected_capture_mode=CAPTURE_MODE_OPERATOR_IMPORT
        )
    except EvmV2PoolSnapshotError as exc:
        raise EvmV2PoolCaptureError("capture_source_contract_invalid") from exc
    snapshot_raw = _pretty_bytes(projection)
    if files[SNAPSHOT_FILENAME] != snapshot_raw:
        raise EvmV2PoolCaptureError("capture_snapshot_drift")
    expected_namespace, capture_id = _capture_identity(
        raw, snapshot_raw, str(projection["acquired_at"])
    )
    if expected_namespace != namespace:
        raise EvmV2PoolCaptureError("capture_namespace_identity_mismatch")
    common = _common_values(namespace, capture_id, projection)
    manifest = _parse_object(files[MANIFEST_FILENAME], "capture_manifest_invalid")
    receipt = _parse_object(files[RECEIPT_FILENAME], "capture_receipt_invalid")
    manifest_keys = {
        "schema_id", "schema_version", "status", "artifacts", *common.keys()
    }
    receipt_keys = {
        "schema_id", "schema_version", "status", "manifest", *common.keys()
    }
    if (
        set(manifest) != manifest_keys
        or manifest.get("schema_id")
        != "decision_radar.evm_v2_pool_capture_manifest"
        or manifest.get("schema_version") != 1
        or manifest.get("status") != "complete"
        or set(receipt) != receipt_keys
        or receipt.get("schema_id")
        != "decision_radar.evm_v2_pool_completion_receipt"
        or receipt.get("schema_version") != 1
        or receipt.get("status") != "complete"
    ):
        raise EvmV2PoolCaptureError("capture_envelope_contract_invalid")
    _validate_common(manifest, common)
    _validate_common(receipt, common)
    expected_artifacts = [
        _artifact_descriptor(RAW_FILENAME, "exact_operator_rpc_bundle", raw),
        _artifact_descriptor(
            SNAPSHOT_FILENAME, "deterministic_normalized_snapshot", snapshot_raw
        ),
    ]
    if manifest.get("artifacts") != expected_artifacts:
        raise EvmV2PoolCaptureError("capture_manifest_fingerprint_mismatch")
    expected_manifest = {
        "name": MANIFEST_FILENAME,
        **_fingerprint(files[MANIFEST_FILENAME]),
    }
    if receipt.get("manifest") != expected_manifest:
        raise EvmV2PoolCaptureError("capture_receipt_fingerprint_mismatch")
    if not _SHA256_RE.fullmatch(capture_id):
        raise EvmV2PoolCaptureError("capture_id_invalid")
    return {
        "status": "complete",
        **common,
        "artifact_path": str(namespace_dir),
        "raw_source": {"name": RAW_FILENAME, **_fingerprint(raw)},
        "snapshot": {"name": SNAPSHOT_FILENAME, **_fingerprint(snapshot_raw)},
        "receipt": {
            "name": RECEIPT_FILENAME,
            **_fingerprint(files[RECEIPT_FILENAME]),
        },
    }


def persist_local_import(
    artifact_base_dir: str | Path,
    source_path: str | Path,
    *,
    confirm: bool = False,
) -> dict[str, object]:
    """Seal one operator bundle; never call a provider or publish a latest pointer."""

    if not confirm:
        raise EvmV2PoolCaptureError("explicit_confirmation_required")
    base = Path(artifact_base_dir).expanduser().absolute()
    if not base.is_dir():
        raise EvmV2PoolCaptureError("artifact_base_unavailable")
    source = Path(source_path)
    raw, projection = _validated_local_import(source)
    namespace, _capture_id, raw, snapshot, manifest, receipt = _capture_payloads(
        raw, projection
    )
    namespace_dir = base / namespace
    with _publication_lock(base):
        if namespace_dir.exists():
            result = validate_capture(base, namespace)
            if result["raw_source"]["sha256"] != _sha256(raw):
                raise EvmV2PoolCaptureError("capture_namespace_collision")
            return {**result, "created": False, "idempotent": True}
        try:
            ensure_safe_namespace_dir(namespace_dir)
            for name, payload in (
                (RAW_FILENAME, raw),
                (SNAPSHOT_FILENAME, snapshot),
                (MANIFEST_FILENAME, manifest),
                (RECEIPT_FILENAME, receipt),
            ):
                write_bytes_immutable(namespace_dir / name, payload)
        except MarketNoSendError as exc:
            raise EvmV2PoolCaptureError("capture_immutable_write_failed") from exc
        result = validate_capture(base, namespace)
    return {**result, "created": True, "idempotent": False}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or immutably import one exact EVM v2 pool bundle."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("validate-local")
    local.add_argument("--input", required=True)
    imported = commands.add_parser("import-local")
    imported.add_argument("--input", required=True)
    imported.add_argument("--artifact-base", required=True)
    imported.add_argument("--confirm", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("--artifact-base", required=True)
    status.add_argument("--namespace", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate-local":
        result: Mapping[str, object] = validate_local_import(args.input)
    elif args.command == "import-local":
        result = persist_local_import(
            args.artifact_base, args.input, confirm=bool(args.confirm)
        )
    else:
        result = validate_capture(args.artifact_base, args.namespace)
    print(json.dumps(dict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI exercised through Make/tests
    raise SystemExit(main())


__all__ = (
    "EvmV2PoolCaptureError",
    "persist_local_import",
    "validate_capture",
    "validate_local_import",
)
