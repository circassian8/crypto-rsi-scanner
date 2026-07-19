"""Immutable fixture-only capture envelope for Tokenomist unlock-events v5.

This module deliberately has no HTTP client, environment lookup, credential
reader, pointer, or live operator command.  It seals one exact synthetic v5
fixture together with its deterministic request identity and normalized rows,
then re-derives every derived artifact from the retained source bytes during
strict validation.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
from typing import Any, Iterator, Sequence

from . import bybit_liquidation_capture_io as anchored_io
from . import tokenomist_v5_capture_contract as capture_contract
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = capture_contract.CONTRACT_VERSION
CAPTURE_MODE_FIXTURE = capture_contract.CAPTURE_MODE_FIXTURE
CAPTURE_MODE_LIVE = capture_contract.CAPTURE_MODE_LIVE
CAPTURE_MODES = capture_contract.CAPTURE_MODES
SOURCE_FILENAME = capture_contract.SOURCE_FILENAME
LEDGER_FILENAME = capture_contract.LEDGER_FILENAME
SNAPSHOT_FILENAME = capture_contract.SNAPSHOT_FILENAME
MANIFEST_FILENAME = capture_contract.MANIFEST_FILENAME
RECEIPT_FILENAME = capture_contract.RECEIPT_FILENAME
_NAMESPACE_RE = re.compile(
    r"^radar_tokenomist_v5_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_MAX_SOURCE_BYTES = capture_contract.MAX_SOURCE_BYTES
_MAX_ARTIFACT_BYTES = capture_contract.MAX_ARTIFACT_BYTES
_MAX_BUNDLE_BYTES = capture_contract.DEFAULT_MAX_BUNDLE_BYTES
_ARTIFACT_NAMES = frozenset(
    {
        SOURCE_FILENAME,
        LEDGER_FILENAME,
        SNAPSHOT_FILENAME,
        MANIFEST_FILENAME,
        RECEIPT_FILENAME,
    }
)
_DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "event_discovery"
    / "tokenomist_unlock_events_v5_capture.json"
)
_DEFAULT_FIXTURE_SHA256 = (
    "e3d9f80502473854d17c485dafee416040fb1a2c2995222dd7545efe0af3a3b9"
)
_DEFAULT_FIXTURE_SIZE = 2246
_RENAME_EXCL = 0x00000004
_RENAME_NOREPLACE = 0x00000001


TokenomistV5CaptureError = capture_contract.TokenomistV5CaptureError
_PreparedCapture = capture_contract._PreparedCapture
_fingerprint = capture_contract._fingerprint
_parse_artifact_object = capture_contract._parse_artifact_object
_sha256 = capture_contract._sha256


@dataclass(frozen=True)
class _PublicationResult:
    namespace_created: bool
    staging_writes_performed: bool
    retained_staging_quarantine: bool
    retained_staging_quarantine_name: str | None
    retained_staging_artifact_count: int
    retained_staging_artifact_names: tuple[str, ...]


def prepare_capture(source_bytes: bytes, *, capture_mode: str) -> _PreparedCapture:
    """Derive the immutable fixture bundle through the pure contract module."""

    return capture_contract.prepare_capture(
        source_bytes,
        capture_mode=capture_mode,
        maximum_bundle_bytes=_MAX_BUNDLE_BYTES,
    )


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_nlink,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_nlink,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _open_directory_chain(directory: Path) -> int:
    """Open every absolute fixture-parent component without following links."""

    if not directory.is_absolute() or directory.anchor != os.sep:
        raise TokenomistV5CaptureError("fixture_parent_not_absolute")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.sep, _directory_flags())
        for part in directory.parts[1:]:
            before = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise TokenomistV5CaptureError("fixture_parent_identity_invalid")
            next_descriptor = os.open(part, _directory_flags(), dir_fd=descriptor)
            opened = os.fstat(next_descriptor)
            if not stat.S_ISDIR(opened.st_mode) or not _same_identity(
                before, opened
            ):
                os.close(next_descriptor)
                raise TokenomistV5CaptureError("fixture_parent_identity_invalid")
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except TokenomistV5CaptureError:
        if descriptor is not None:
            os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise TokenomistV5CaptureError("fixture_source_unreadable") from exc


@contextmanager
def _hold_capture_base(
    value: str | Path,
    *,
    exclusive: bool,
) -> Iterator[Any]:
    """Hold the complete canonical base ancestry for one operation."""

    if "\x00" in os.fspath(value):
        raise TokenomistV5CaptureError("artifact_base_nul_rejected")
    try:
        with anchored_io.hold_anchored_base(value, exclusive=exclusive) as anchored:
            yield anchored
    except TokenomistV5CaptureError:
        raise
    except anchored_io.BybitLiquidationCaptureIOError as exc:
        raise TokenomistV5CaptureError(str(exc)) from exc


def _bounded_entry_names(directory_fd: int) -> frozenset[str]:
    names: set[str] = set()
    try:
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                names.add(entry.name)
                if len(names) > len(_ARTIFACT_NAMES) + 1:
                    raise TokenomistV5CaptureError(
                        "capture_artifact_inventory_bound_exceeded"
                    )
    except TokenomistV5CaptureError:
        raise
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_staging_unreadable") from exc
    return frozenset(names)


def _namespace_exists_at(base_fd: int, namespace: str) -> bool:
    try:
        info = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        raise TokenomistV5CaptureError("capture_namespace_leaf_invalid")
    return True


def _safe_capture_leaf(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise TokenomistV5CaptureError("capture_path_leaf_invalid")
    if "\x00" in name:
        raise TokenomistV5CaptureError("capture_path_nul_rejected")
    if name in {".", ".."} or Path(name).name != name:
        raise TokenomistV5CaptureError("capture_path_leaf_invalid")
    return name


def _rename_directory_noreplace(
    base_fd: int,
    source: str,
    destination: str,
) -> bool:
    """Atomically publish one directory without replacing any destination."""

    source = _safe_capture_leaf(source)
    destination = _safe_capture_leaf(destination)
    if _namespace_exists_at(base_fd, destination):
        return False
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = getattr(library, "renameatx_np", None)
        flags = _RENAME_EXCL
    elif sys.platform.startswith("linux"):
        rename = getattr(library, "renameat2", None)
        flags = _RENAME_NOREPLACE
    else:
        rename = None
        flags = 0
    if rename is None:
        raise TokenomistV5CaptureError("capture_no_replace_rename_unsupported")
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = rename(
        base_fd,
        os.fsencode(source),
        base_fd,
        os.fsencode(destination),
        flags,
    )
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        return False
    if error in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
        raise TokenomistV5CaptureError(
            "capture_no_replace_rename_unsupported"
        )
    raise OSError(error, os.strerror(error))


@contextmanager
def _open_child_directory(base_fd: int, namespace: str) -> Iterator[int]:
    descriptor: int | None = None
    try:
        before = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise TokenomistV5CaptureError("capture_artifact_unreadable")
        descriptor = os.open(
            namespace,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=base_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
            raise TokenomistV5CaptureError("capture_namespace_identity_invalid")
        yield descriptor
        after = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
        if not _same_identity(opened, after):
            raise TokenomistV5CaptureError("capture_namespace_identity_invalid")
    except TokenomistV5CaptureError:
        raise
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_artifact_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_leaf_at(directory_fd: int, name: str, raw: bytes) -> None:
    if name not in _ARTIFACT_NAMES or not isinstance(raw, bytes) or not raw:
        raise TokenomistV5CaptureError("capture_artifact_write_invalid")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise TokenomistV5CaptureError("capture_artifact_write_invalid")
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            completed = os.fstat(handle.fileno())
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            completed.st_size != len(raw)
            or not _same_identity(opened, completed)
            or not stat.S_ISREG(completed.st_mode)
            or completed.st_nlink != 1
            or not _same_file_snapshot(completed, after)
        ):
            raise TokenomistV5CaptureError("capture_artifact_write_invalid")
    except TokenomistV5CaptureError:
        raise
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_artifact_write_failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _cleanup_owned_staging_at(
    base_fd: int,
    staging: str,
    expected_identity: os.stat_result,
) -> tuple[str, ...]:
    """Fail safely by retaining an interrupted staging tree without deletion."""

    staging_fd: int | None = None
    try:
        before = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode) or not _same_identity(
            expected_identity, before
        ):
            raise TokenomistV5CaptureError(
                "capture_staging_cleanup_identity_drift"
            )
        staging_fd = os.open(
            staging,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=base_fd,
        )
        opened = os.fstat(staging_fd)
        if not _same_identity(expected_identity, opened):
            raise TokenomistV5CaptureError(
                "capture_staging_cleanup_identity_drift"
            )
        names = _bounded_entry_names(staging_fd)
        if not names.issubset(_ARTIFACT_NAMES):
            raise TokenomistV5CaptureError("capture_staging_cleanup_unsafe")
        current = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not _same_identity(expected_identity, current):
            raise TokenomistV5CaptureError(
                "capture_staging_cleanup_identity_drift"
            )
        # There is no portable conditional unlink-by-inode operation.  Never
        # unlink a leaf by name after a separate identity check: an unowned
        # replacement could win that gap.  The tmp_ directory is retained as
        # explicit quarantine; unique stage names keep retries independent.
        return tuple(sorted(names))
    except TokenomistV5CaptureError:
        raise
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise TokenomistV5CaptureError(
            "capture_staging_cleanup_identity_drift"
        ) from exc
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_staging_cleanup_failed") from exc
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


def _publish_staged_bundle_at(
    base_fd: int,
    prepared: _PreparedCapture,
) -> _PublicationResult:
    staging = f"tmp_tokenomist_v5_stage_{os.getpid()}_{time.time_ns()}"
    staging_fd: int | None = None
    staging_identity: os.stat_result | None = None
    created_staging = False
    try:
        os.mkdir(staging, 0o700, dir_fd=base_fd)
        created_staging = True
        staging_fd = os.open(
            staging,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=base_fd,
        )
        staging_identity = os.fstat(staging_fd)
        named_staging = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(staging_identity.st_mode) or not _same_identity(
            staging_identity, named_staging
        ):
            raise TokenomistV5CaptureError("capture_staging_identity_drift")
        for name, raw in prepared.payloads:
            _write_leaf_at(staging_fd, name, raw)
        os.fsync(staging_fd)
        staged = _read_exact_capture_files_at(base_fd, staging)
        if staged != dict(prepared.payloads):
            raise TokenomistV5CaptureError("capture_staging_artifact_drift")
        staging_current = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not _same_identity(staging_identity, staging_current):
            raise TokenomistV5CaptureError("capture_staging_identity_drift")
        if _namespace_exists_at(base_fd, prepared.namespace):
            retained_names = _cleanup_owned_staging_at(
                base_fd,
                staging,
                staging_identity,
            )
            created_staging = False
            return _PublicationResult(
                namespace_created=False,
                staging_writes_performed=True,
                retained_staging_quarantine=True,
                retained_staging_quarantine_name=staging,
                retained_staging_artifact_count=len(retained_names),
                retained_staging_artifact_names=retained_names,
            )
        renamed = _rename_directory_noreplace(
            base_fd,
            staging,
            prepared.namespace,
        )
        if not renamed:
            retained_names = _cleanup_owned_staging_at(
                base_fd,
                staging,
                staging_identity,
            )
            created_staging = False
            return _PublicationResult(
                namespace_created=False,
                staging_writes_performed=True,
                retained_staging_quarantine=True,
                retained_staging_quarantine_name=staging,
                retained_staging_artifact_count=len(retained_names),
                retained_staging_artifact_names=retained_names,
            )
        created_staging = False
        published = os.stat(
            prepared.namespace,
            dir_fd=base_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(published.st_mode) or not _same_identity(
            staging_identity, published
        ):
            raise TokenomistV5CaptureError("capture_publish_identity_drift")
        os.fsync(base_fd)
        return _PublicationResult(
            namespace_created=True,
            staging_writes_performed=True,
            retained_staging_quarantine=False,
            retained_staging_quarantine_name=None,
            retained_staging_artifact_count=0,
            retained_staging_artifact_names=(),
        )
    except BaseException as exc:
        if created_staging and staging_identity is not None:
            try:
                _cleanup_owned_staging_at(base_fd, staging, staging_identity)
            except TokenomistV5CaptureError as cleanup_exc:
                raise cleanup_exc from exc
        raise
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


def _read_exact_capture_files_at(base_fd: int, namespace: str) -> dict[str, bytes]:
    try:
        with _open_child_directory(base_fd, namespace) as namespace_fd:
            names = _bounded_entry_names(namespace_fd)
            if names != _ARTIFACT_NAMES:
                raise TokenomistV5CaptureError("capture_artifact_set_invalid")
            files: dict[str, bytes] = {}
            total_bytes = 0
            for name in sorted(names):
                before = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size <= 0
                    or before.st_size > _MAX_ARTIFACT_BYTES
                ):
                    raise TokenomistV5CaptureError("capture_artifact_leaf_invalid")
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=namespace_fd,
                )
                try:
                    opened = os.fstat(descriptor)
                    if not _same_file_snapshot(before, opened):
                        raise TokenomistV5CaptureError("capture_artifact_identity_invalid")
                    chunks: list[bytes] = []
                    remaining = before.st_size
                    while remaining:
                        chunk = os.read(descriptor, min(65_536, remaining))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    raw = b"".join(chunks)
                    current = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
                    if (
                        remaining != 0
                        or len(raw) != before.st_size
                        or not _same_file_snapshot(before, os.fstat(descriptor))
                        or not _same_file_snapshot(before, current)
                    ):
                        raise TokenomistV5CaptureError(
                            "capture_artifact_changed_during_read"
                        )
                    files[name] = raw
                    total_bytes += len(raw)
                    if total_bytes > _MAX_BUNDLE_BYTES:
                        raise TokenomistV5CaptureError(
                            "capture_bundle_size_bound_exceeded"
                        )
                finally:
                    os.close(descriptor)
            return files
    except TokenomistV5CaptureError:
        raise
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_artifact_unreadable") from exc


def _validate_capture_at(
    base: Path,
    base_fd: int,
    namespace: str,
    *,
    expected_prepared: _PreparedCapture | None = None,
) -> dict[str, object]:
    files = _read_exact_capture_files_at(base_fd, namespace)
    ledger = _parse_artifact_object(files[LEDGER_FILENAME], artifact="ledger")
    required = {
        "schema_id", "schema_version", "status", "contract_version",
        "artifact_namespace", "capture_id", "capture_mode", "provider",
        "provider_api_version", "method", "host", "path", "request",
        "request_identity_sha256", "provider_response_sha256", "source_artifact",
        "capture_acquired_at", "provider_query_at", "provider_page",
        "provider_page_size", "provider_total_pages", "provider_total_rows",
        "coverage_status", "provider_call_performed",
        "transport_captured_by_project", "redirects_observed", "retries_observed",
        "credentials_read", "environment_read",
    }
    if (
        set(ledger) != required
        or ledger.get("schema_id") != "decision_radar.tokenomist_v5_request_ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("contract_version") != CONTRACT_VERSION
        or ledger.get("artifact_namespace") != namespace
        or ledger.get("capture_mode") != CAPTURE_MODE_FIXTURE
        or ledger.get("provider") != "tokenomist"
        or ledger.get("provider_api_version") != "v5"
        or ledger.get("provider_call_performed") is not False
        or ledger.get("transport_captured_by_project") is not False
        or ledger.get("credentials_read") is not False
        or ledger.get("environment_read") is not False
    ):
        raise TokenomistV5CaptureError("capture_ledger_contract_invalid")
    prepared = prepare_capture(
        files[SOURCE_FILENAME], capture_mode=str(ledger["capture_mode"])
    )
    expected = dict(prepared.payloads)
    if prepared.namespace != namespace or set(expected) != set(files):
        raise TokenomistV5CaptureError("capture_identity_invalid")
    for name, raw in expected.items():
        if files[name] != raw:
            raise TokenomistV5CaptureError(f"capture_artifact_drift:{name}")
    if expected_prepared is not None and (
        expected_prepared.namespace != prepared.namespace
        or expected_prepared.capture_id != prepared.capture_id
        or expected_prepared.payloads != prepared.payloads
    ):
        raise TokenomistV5CaptureError("capture_identity_collision")
    return {
        **dict(prepared.summary),
        "artifact_path": str(base / namespace),
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(files[RECEIPT_FILENAME])},
        "strict_doctor_status": "pass",
    }


def validate_capture(artifact_base_dir: str | Path, namespace: str) -> dict[str, object]:
    """Strictly re-derive one fixture namespace from exact retained bytes."""

    if not isinstance(namespace, str) or not _NAMESPACE_RE.fullmatch(namespace):
        raise TokenomistV5CaptureError("capture_namespace_invalid")
    try:
        with _hold_capture_base(artifact_base_dir, exclusive=False) as anchored:
            return _validate_capture_at(
                anchored.path,
                anchored.descriptor,
                namespace,
            )
    except TokenomistV5CaptureError:
        raise
    except OSError as exc:
        raise TokenomistV5CaptureError("capture_artifact_unreadable") from exc


def persist_capture(
    artifact_base_dir: str | Path,
    source_bytes: bytes,
    *,
    capture_mode: str,
    confirm: bool = False,
) -> dict[str, object]:
    """Seal synthetic fixture bytes; never contact Tokenomist or publish a pointer."""

    if not confirm:
        raise TokenomistV5CaptureError("explicit_confirmation_required")
    prepared = prepare_capture(source_bytes, capture_mode=capture_mode)
    with _hold_capture_base(artifact_base_dir, exclusive=True) as anchored:
        base = anchored.path
        base_fd = anchored.descriptor
        if _namespace_exists_at(base_fd, prepared.namespace):
            result = _validate_capture_at(
                base,
                base_fd,
                prepared.namespace,
                expected_prepared=prepared,
            )
            return {
                **result,
                "created": False,
                "idempotent": True,
                "canonical_capture_reused": True,
                "writes_performed": False,
                "staging_writes_performed": False,
                "retained_staging_quarantine": False,
                "retained_staging_quarantine_name": None,
                "retained_staging_artifact_count": 0,
                "retained_staging_artifact_names": [],
            }
        try:
            publication = _publish_staged_bundle_at(base_fd, prepared)
        except (MarketNoSendError, OSError) as exc:
            raise TokenomistV5CaptureError("capture_immutable_write_failed") from exc
        if not publication.namespace_created:
            result = _validate_capture_at(
                base,
                base_fd,
                prepared.namespace,
                expected_prepared=prepared,
            )
            return {
                **result,
                "created": False,
                "idempotent": not publication.staging_writes_performed,
                "canonical_capture_reused": True,
                "writes_performed": publication.staging_writes_performed,
                "staging_writes_performed": publication.staging_writes_performed,
                "retained_staging_quarantine": (
                    publication.retained_staging_quarantine
                ),
                "retained_staging_quarantine_name": (
                    publication.retained_staging_quarantine_name
                ),
                "retained_staging_artifact_count": (
                    publication.retained_staging_artifact_count
                ),
                "retained_staging_artifact_names": list(
                    publication.retained_staging_artifact_names
                ),
            }
        result = _validate_capture_at(
            base,
            base_fd,
            prepared.namespace,
            expected_prepared=prepared,
        )
    return {
        **result,
        "created": True,
        "idempotent": False,
        "canonical_capture_reused": False,
        "writes_performed": True,
        "staging_writes_performed": publication.staging_writes_performed,
        "retained_staging_quarantine": publication.retained_staging_quarantine,
        "retained_staging_quarantine_name": (
            publication.retained_staging_quarantine_name
        ),
        "retained_staging_artifact_count": (
            publication.retained_staging_artifact_count
        ),
        "retained_staging_artifact_names": list(
            publication.retained_staging_artifact_names
        ),
    }


def _verify_fixture_ancestry_at_return(
    source: Path,
    expected: Path,
    parent_identity: os.stat_result,
    source_identity: os.stat_result,
) -> None:
    """Re-resolve and re-walk the complete fixture ancestry after reading."""

    verification_fd: int | None = None
    try:
        resolved_source_before = source.resolve(strict=True)
        resolved_expected_before = expected.resolve(strict=True)
        path_parent_before = os.stat(source.parent, follow_symlinks=False)
        path_source_before = os.stat(source, follow_symlinks=False)
        verification_fd = _open_directory_chain(source.parent)
        verified_parent = os.fstat(verification_fd)
        verified_source = os.stat(
            source.name,
            dir_fd=verification_fd,
            follow_symlinks=False,
        )
        path_parent_after = os.stat(source.parent, follow_symlinks=False)
        path_source_after = os.stat(source, follow_symlinks=False)
        resolved_source_after = source.resolve(strict=True)
        resolved_expected_after = expected.resolve(strict=True)
        if (
            resolved_source_before != source
            or resolved_expected_before != expected
            or resolved_source_after != source
            or resolved_expected_after != expected
            or not _same_identity(parent_identity, path_parent_before)
            or not _same_file_snapshot(source_identity, path_source_before)
            or not _same_identity(parent_identity, verified_parent)
            or not _same_identity(verified_parent, path_parent_after)
            or not _same_file_snapshot(source_identity, verified_source)
            or not _same_file_snapshot(verified_source, path_source_after)
        ):
            raise TokenomistV5CaptureError(
                "fixture_source_changed_during_read"
            )
    finally:
        if verification_fd is not None:
            os.close(verification_fd)


def _read_checked_fixture(path: Path) -> bytes:
    descriptor: int | None = None
    parent_fd: int | None = None
    try:
        if "\x00" in os.fspath(path):
            raise TokenomistV5CaptureError("fixture_path_nul_rejected")
        expected = Path(os.path.abspath(_DEFAULT_FIXTURE))
        source = Path(os.path.abspath(path.expanduser()))
        if source != expected:
            raise TokenomistV5CaptureError("fixture_path_not_canonical")
        parent_initial = os.stat(source.parent, follow_symlinks=False)
        source_initial = os.stat(source, follow_symlinks=False)
        parent_fd = _open_directory_chain(source.parent)
        parent_opened = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent_opened.st_mode) or not _same_identity(
            parent_initial, parent_opened
        ):
            raise TokenomistV5CaptureError("fixture_parent_identity_invalid")
        before = os.stat(source.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > _MAX_SOURCE_BYTES
        ):
            raise TokenomistV5CaptureError("fixture_source_leaf_invalid")
        if not _same_file_snapshot(source_initial, before):
            raise TokenomistV5CaptureError("fixture_source_identity_invalid")
        if (
            source.resolve(strict=True) != source
            or expected.resolve(strict=True) != expected
        ):
            raise TokenomistV5CaptureError("fixture_path_not_canonical")
        path_parent = os.stat(source.parent, follow_symlinks=False)
        path_source = os.stat(source, follow_symlinks=False)
        if not _same_identity(parent_opened, path_parent):
            raise TokenomistV5CaptureError("fixture_parent_identity_invalid")
        if not _same_file_snapshot(before, path_source):
            raise TokenomistV5CaptureError("fixture_source_identity_invalid")
        descriptor = os.open(
            source.name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        if not _same_file_snapshot(before, opened):
            raise TokenomistV5CaptureError("fixture_source_identity_invalid")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.stat(source.name, dir_fd=parent_fd, follow_symlinks=False)
        path_after = os.stat(source, follow_symlinks=False)
        parent_after = os.stat(source.parent, follow_symlinks=False)
        if (
            remaining != 0
            or len(raw) != before.st_size
            or not _same_file_snapshot(before, os.fstat(descriptor))
            or not _same_file_snapshot(before, after)
            or not _same_file_snapshot(before, path_after)
            or not _same_identity(parent_opened, parent_after)
        ):
            raise TokenomistV5CaptureError("fixture_source_changed_during_read")
        _verify_fixture_ancestry_at_return(
            source,
            expected,
            parent_opened,
            before,
        )
        if len(raw) != _DEFAULT_FIXTURE_SIZE or _sha256(raw) != _DEFAULT_FIXTURE_SHA256:
            raise TokenomistV5CaptureError("fixture_source_fingerprint_invalid")
        return raw
    except TokenomistV5CaptureError:
        raise
    except (OSError, anchored_io.BybitLiquidationCaptureIOError) as exc:
        raise TokenomistV5CaptureError("fixture_source_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)


def run_fixture_capture_smoke(fixture: Path) -> dict[str, object]:
    """Prove the capture and strict doctor inside one disposable directory."""

    source_bytes = _read_checked_fixture(fixture)
    with tempfile.TemporaryDirectory(prefix="radar_tokenomist_v5_capture_smoke_") as root:
        artifact_base = Path(root).resolve(strict=True)
        result = persist_capture(
            artifact_base,
            source_bytes,
            capture_mode=CAPTURE_MODE_FIXTURE,
            confirm=True,
        )
        validated = validate_capture(
            artifact_base,
            str(result["artifact_namespace"]),
        )
        return {
            key: value
            for key, value in {
                **validated,
                "artifact_path": None,
                "fixture_artifacts_retained": False,
                "disposable_artifact_write_count": result["artifact_count"],
                "provider_calls_performed_by_smoke": 0,
                "writes_performed": True,
            }.items()
            if key != "artifact_path" or value is not None
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=_DEFAULT_FIXTURE,
    )
    args = parser.parse_args(argv)
    try:
        result = run_fixture_capture_smoke(args.fixture)
    except (OSError, TokenomistV5CaptureError, ValueError) as exc:
        print(f"radar_tokenomist_v5_capture_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "CAPTURE_MODE_FIXTURE",
    "CAPTURE_MODE_LIVE",
    "CONTRACT_VERSION",
    "TokenomistV5CaptureError",
    "persist_capture",
    "prepare_capture",
    "run_fixture_capture_smoke",
    "validate_capture",
)


if __name__ == "__main__":
    raise SystemExit(main())
