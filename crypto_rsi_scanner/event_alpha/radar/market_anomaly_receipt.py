"""Descriptor-anchored byte binding for market-anomaly completion receipts."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import stat
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks
_MKDIR_SUPPORTS_DIR_FD = os.mkdir in os.supports_dir_fd
_RENAME_SUPPORTS_DIR_FD = os.rename in os.supports_dir_fd
_IDENTITY_CHANGED_ERRNO = getattr(errno, "ESTALE", errno.EIO)
_RENAME_EXCL = 0x00000004
_RENAME_NOREPLACE = 0x00000001


def namespace_identity(directory: Path) -> tuple[int, int]:
    descriptor = _open_namespace(directory)
    try:
        status = os.fstat(descriptor)
        return status.st_dev, status.st_ino
    finally:
        os.close(descriptor)


def artifact_payloads(
    directory: Path,
    *,
    namespace_identity: tuple[int, int],
    paths: tuple[Path, ...],
    expected_names: tuple[str, ...],
) -> dict[str, bytes]:
    directory = Path(os.path.abspath(Path(directory).expanduser()))
    namespace = _safe_leaf(directory.name)
    parent_fd = -1
    descriptor = -1
    payloads: dict[str, bytes] = {}
    try:
        (
            parent_fd,
            parent_status,
            descriptor,
            opened_namespace,
        ) = _open_mutation_namespace(
            directory.parent,
            namespace=namespace,
            expected_namespace_identity=namespace_identity,
        )
        for supplied, filename in zip(paths, expected_names, strict=True):
            if Path(os.path.abspath(Path(supplied).expanduser())) != directory / filename:
                raise RuntimeError("market_anomaly_completion_receipt_invalid:path")
            _assert_directory_path_identity(directory.parent, parent_status)
            _assert_namespace_identity(parent_fd, namespace, opened_namespace)
            payloads[filename] = _read_regular_leaf(descriptor, filename)
            _assert_directory_path_identity(directory.parent, parent_status)
            _assert_namespace_identity(parent_fd, namespace, opened_namespace)
    except OSError as exc:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_unavailable"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if parent_fd >= 0:
            os.close(parent_fd)
    return payloads


def write_artifacts_atomic(
    directory: Path,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
    expected_namespace_identity: tuple[int, int] | None = None,
    expected_existing_sha256: Mapping[str, str] | None = None,
    expected_guarded_sha256: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    """Publish one fail-closed scanner bundle through one namespace fd.

    Every leaf is fully persisted and descriptor-verified before any public
    pathname changes.  Each public rename is atomic, and the complete bundle is
    trustworthy only when this function returns after full byte and identity
    validation.  Filesystems do not provide a portable multi-leaf transaction:
    on failure this function deliberately performs no pathname rollback or
    cleanup.  A partial public prefix and private stages may remain as
    non-authoritative evidence for the caller's generation-level doctor.

    ``expected_guarded_sha256`` binds extra regular leaves that participate in
    the transaction but must not be rewritten.  They are rechecked before,
    during, and after the bundle replacement.
    """

    _require_mutation_support()
    if tuple(payloads) != expected_names or any(
        not isinstance(payloads.get(name), bytes) for name in expected_names
    ):
        raise RuntimeError("market_anomaly_completion_receipt_invalid:artifact_bundle")
    guarded_sha256 = _guarded_sha256_mapping(
        expected_guarded_sha256,
        rewritten_names=expected_names,
    )
    absolute = Path(os.path.abspath(Path(directory).expanduser()))
    namespace = _safe_leaf(absolute.name)
    parent_path = absolute.parent
    parent_fd = -1
    namespace_fd = -1
    staged_names: dict[str, str] = {}
    staged_descriptors: dict[str, int] = {}
    staged_statuses: dict[str, os.stat_result] = {}
    installed_names: dict[str, os.stat_result] = {}
    original_leaves: dict[str, os.stat_result | None] = {}
    try:
        (
            parent_fd,
            parent_status,
            namespace_fd,
            opened_namespace,
        ) = _open_mutation_namespace(
            parent_path,
            namespace=namespace,
            expected_namespace_identity=expected_namespace_identity,
        )
        original_leaves = _existing_bundle_state(
            namespace_fd,
            expected_names=expected_names,
            expected_existing_sha256=expected_existing_sha256,
        )
        _assert_guarded_sha256(namespace_fd, guarded_sha256)
        _stage_bundle(
            namespace_fd,
            payloads=payloads,
            expected_names=expected_names,
            staged_names=staged_names,
            staged_descriptors=staged_descriptors,
            staged_statuses=staged_statuses,
            parent_path=parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        _assert_original_bundle(
            namespace_fd,
            expected_names=expected_names,
            original_leaves=original_leaves,
            expected_existing_sha256=expected_existing_sha256,
        )
        _commit_staged_bundle(
            namespace_fd,
            payloads=payloads,
            expected_names=expected_names,
            original_leaves=original_leaves,
            expected_existing_sha256=expected_existing_sha256,
            staged_names=staged_names,
            staged_descriptors=staged_descriptors,
            staged_statuses=staged_statuses,
            installed_names=installed_names,
            parent_path=parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        return opened_namespace.st_dev, opened_namespace.st_ino
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_write"
        ) from exc
    finally:
        for descriptor in staged_descriptors.values():
            os.close(descriptor)
        if namespace_fd >= 0:
            os.close(namespace_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _open_mutation_namespace(
    parent_path: Path,
    *,
    namespace: str,
    expected_namespace_identity: tuple[int, int] | None,
) -> tuple[int, os.stat_result, int, os.stat_result]:
    parent_fd, parent_status = _open_directory(parent_path)
    namespace_fd = -1
    try:
        try:
            namespace_status = os.stat(
                namespace,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if expected_namespace_identity is not None:
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:namespace_identity"
                )
            os.mkdir(namespace, 0o700, dir_fd=parent_fd)
            namespace_status = os.stat(
                namespace,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        if not stat.S_ISDIR(namespace_status.st_mode):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:namespace_not_directory"
            )
        namespace_fd = os.open(namespace, _directory_flags(), dir_fd=parent_fd)
        opened_namespace = os.fstat(namespace_fd)
        if not stat.S_ISDIR(opened_namespace.st_mode) or not _same_identity(
            namespace_status,
            opened_namespace,
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:namespace_identity"
            )
        if expected_namespace_identity is not None and (
            opened_namespace.st_dev,
            opened_namespace.st_ino,
        ) != expected_namespace_identity:
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:namespace_identity"
            )
        _assert_directory_path_identity(parent_path, parent_status)
        _assert_namespace_identity(parent_fd, namespace, opened_namespace)
        return parent_fd, parent_status, namespace_fd, opened_namespace
    except BaseException:
        if namespace_fd >= 0:
            os.close(namespace_fd)
        os.close(parent_fd)
        raise


def _existing_bundle_state(
    namespace_fd: int,
    *,
    expected_names: tuple[str, ...],
    expected_existing_sha256: Mapping[str, str] | None,
) -> dict[str, os.stat_result | None]:
    original_leaves = {
        name: _regular_leaf_status(namespace_fd, name)
        for name in expected_names
    }
    if expected_existing_sha256 is None:
        return original_leaves
    if set(expected_existing_sha256) != set(expected_names):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_bundle"
        )
    for name in expected_names:
        if sha256(_read_regular_leaf(namespace_fd, name)) != (
            expected_existing_sha256[name]
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )
    return original_leaves


def _stage_bundle(
    namespace_fd: int,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
    staged_names: dict[str, str],
    staged_descriptors: dict[str, int],
    staged_statuses: dict[str, os.stat_result],
    parent_path: Path,
    parent_status: os.stat_result,
    parent_fd: int,
    namespace: str,
    opened_namespace: os.stat_result,
    guarded_sha256: Mapping[str, str],
) -> None:
    for index, name in enumerate(expected_names):
        _assert_transaction_context(
            parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            namespace_fd=namespace_fd,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        temporary = f".{name}.{os.getpid()}.{time.time_ns()}.{index}.tmp"
        descriptor, status = _stage_leaf(
            namespace_fd,
            temporary=temporary,
            payload=payloads[name],
        )
        staged_names[name] = temporary
        staged_descriptors[name] = descriptor
        staged_statuses[name] = status


def _stage_leaf(
    namespace_fd: int,
    *,
    temporary: str,
    payload: bytes,
) -> tuple[int, os.stat_result]:
    succeeded = False
    descriptor = os.open(
        temporary,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | _required_flag("O_NOFOLLOW")
        | getattr(os, "O_CLOEXEC", 0),
        0o600,
        dir_fd=namespace_fd,
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size != 0
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:temporary_not_regular"
            )
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "artifact stage write stalled")
            offset += written
        os.fsync(descriptor)
        persisted = _read_exact_fd(descriptor, maximum_bytes=len(payload))
        completed = os.fstat(descriptor)
        if (
            persisted != payload
            or not stat.S_ISREG(completed.st_mode)
            or completed.st_nlink != 1
            or completed.st_size != len(payload)
            or not _same_identity(opened, completed)
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:temporary_identity"
            )
        succeeded = True
        return descriptor, completed
    finally:
        if not succeeded:
            os.close(descriptor)


def _read_exact_fd(descriptor: int, *, maximum_bytes: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = maximum_bytes + 1
    while remaining:
        chunk = os.read(descriptor, min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _assert_named_stage(
    namespace_fd: int,
    temporary: str,
    expected: os.stat_result,
) -> None:
    named = os.stat(
        _safe_leaf(temporary),
        dir_fd=namespace_fd,
        follow_symlinks=False,
    )
    if (
        not stat.S_ISREG(named.st_mode)
        or named.st_nlink != 1
        or not _same_file_snapshot(expected, named)
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "artifact stage changed")


def _rename_noreplace(
    namespace_fd: int,
    source: str,
    destination: str,
) -> bool:
    """Use the native Darwin/Linux no-replace rename primitive."""

    source = _safe_leaf(source)
    destination = _safe_leaf(destination)
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
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:native_noreplace_unsupported"
        )
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
        namespace_fd,
        os.fsencode(source),
        namespace_fd,
        os.fsencode(destination),
        flags,
    )
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        return False
    if error in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:native_noreplace_unsupported"
        )
    raise OSError(error, os.strerror(error))


def _verify_published_stage(
    namespace_fd: int,
    *,
    name: str,
    descriptor: int,
    staged: os.stat_result,
    payload: bytes,
) -> os.stat_result:
    before = os.fstat(descriptor)
    persisted = _read_exact_fd(descriptor, maximum_bytes=len(payload))
    completed = os.fstat(descriptor)
    named = os.stat(
        _safe_leaf(name),
        dir_fd=namespace_fd,
        follow_symlinks=False,
    )
    if (
        persisted != payload
        or not _same_identity(staged, before)
        or not _same_file_snapshot(before, completed)
        or not _same_file_snapshot(completed, named)
        or not stat.S_ISREG(named.st_mode)
        or named.st_nlink != 1
        or named.st_size != len(payload)
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "published artifact changed")
    return named


def _commit_staged_bundle(
    namespace_fd: int,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
    original_leaves: Mapping[str, os.stat_result | None],
    expected_existing_sha256: Mapping[str, str] | None,
    staged_names: Mapping[str, str],
    staged_descriptors: Mapping[str, int],
    staged_statuses: Mapping[str, os.stat_result],
    installed_names: dict[str, os.stat_result],
    parent_path: Path,
    parent_status: os.stat_result,
    parent_fd: int,
    namespace: str,
    opened_namespace: os.stat_result,
    guarded_sha256: Mapping[str, str],
) -> None:
    for index, name in enumerate(expected_names):
        _assert_transaction_context(
            parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            namespace_fd=namespace_fd,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        _assert_original_leaf(
            namespace_fd,
            name=name,
            original=original_leaves[name],
            expected_sha256=(
                expected_existing_sha256.get(name)
                if expected_existing_sha256 is not None
                else None
            ),
        )
        _assert_named_stage(
            namespace_fd,
            staged_names[name],
            staged_statuses[name],
        )
        installed_names[name] = _install_staged_leaf(
            namespace_fd,
            name=name,
            staged_name=staged_names[name],
            staged_descriptor=staged_descriptors[name],
            staged_status=staged_statuses[name],
            payload=payloads[name],
            target_existed=original_leaves[name] is not None,
        )
        _assert_transaction_context(
            parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            namespace_fd=namespace_fd,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        _assert_installed_bundle(
            namespace_fd,
            payloads=payloads,
            expected_names=expected_names[: index + 1],
            installed_names=installed_names,
        )
    _assert_guarded_sha256(namespace_fd, guarded_sha256)
    _assert_installed_bundle(
        namespace_fd,
        payloads=payloads,
        expected_names=expected_names,
        installed_names=installed_names,
    )
    os.fsync(namespace_fd)
    _assert_guarded_sha256(namespace_fd, guarded_sha256)


def _install_staged_leaf(
    namespace_fd: int,
    *,
    name: str,
    staged_name: str,
    staged_descriptor: int,
    staged_status: os.stat_result,
    payload: bytes,
    target_existed: bool,
) -> os.stat_result:
    _assert_named_stage(namespace_fd, staged_name, staged_status)
    if target_existed:
        os.rename(
            staged_name,
            name,
            src_dir_fd=namespace_fd,
            dst_dir_fd=namespace_fd,
        )
    elif not _rename_noreplace(namespace_fd, staged_name, name):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    return _verify_published_stage(
        namespace_fd,
        name=name,
        descriptor=staged_descriptor,
        staged=staged_status,
        payload=payload,
    )


def _assert_transaction_context(
    parent_path: Path,
    *,
    parent_status: os.stat_result,
    parent_fd: int,
    namespace: str,
    namespace_fd: int,
    opened_namespace: os.stat_result,
    guarded_sha256: Mapping[str, str],
) -> None:
    _assert_directory_path_identity(parent_path, parent_status)
    _assert_namespace_identity(parent_fd, namespace, opened_namespace)
    _assert_guarded_sha256(namespace_fd, guarded_sha256)


def strict_jsonl(payload: bytes, *, row_type: str) -> tuple[dict[str, Any], ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_encoding"
        ) from exc
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_json"
            ) from exc
        if not isinstance(value, Mapping) or value.get("row_type") != row_type:
            raise RuntimeError("market_anomaly_completion_receipt_invalid:artifact_row")
        rows.append(dict(value))
    return tuple(rows)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _open_namespace(directory: Path) -> int:
    try:
        descriptor = os.open(
            Path(os.path.abspath(Path(directory).expanduser())),
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | _required_flag("O_NOFOLLOW")
            | _required_flag("O_DIRECTORY"),
        )
    except OSError as exc:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:namespace_unavailable"
        ) from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RuntimeError("market_anomaly_completion_receipt_invalid:namespace_not_directory")
    return descriptor


def _open_directory(directory: Path) -> tuple[int, os.stat_result]:
    before = os.stat(directory, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:parent_not_directory"
        )
    descriptor = os.open(directory, _directory_flags())
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:parent_identity"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, opened


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | _required_flag("O_NOFOLLOW")
        | _required_flag("O_DIRECTORY")
    )


def _regular_leaf_status(directory_fd: int, name: str) -> os.stat_result | None:
    name = _safe_leaf(name)
    try:
        status = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(status.st_mode):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_not_regular"
        )
    if status.st_nlink != 1:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    return status


def _read_regular_leaf(directory_fd: int, name: str) -> bytes:
    payload, _status = _read_regular_leaf_snapshot(directory_fd, name)
    return payload


def _read_regular_leaf_snapshot(
    directory_fd: int,
    name: str,
) -> tuple[bytes, os.stat_result]:
    name = _safe_leaf(name)
    before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_not_regular"
        )
    if before.st_nlink != 1:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    descriptor = os.open(
        name,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | _required_flag("O_NOFOLLOW"),
        dir_fd=directory_fd,
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not _same_file_snapshot(before, opened)
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )
        payload = _read_exact_fd(descriptor, maximum_bytes=opened.st_size)
        completed = os.fstat(descriptor)
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            len(payload) != completed.st_size
            or not stat.S_ISREG(completed.st_mode)
            or completed.st_nlink != 1
            or not _same_file_snapshot(opened, completed)
            or not _same_file_snapshot(completed, after)
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )
        return payload, after
    finally:
        os.close(descriptor)


def _guarded_sha256_mapping(
    supplied: Mapping[str, str] | None,
    *,
    rewritten_names: tuple[str, ...],
) -> dict[str, str]:
    if supplied is None:
        return {}
    if not isinstance(supplied, Mapping):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_bundle"
        )
    guarded: dict[str, str] = {}
    for raw_name, expected in supplied.items():
        if not isinstance(raw_name, str):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_bundle"
            )
        name = _safe_leaf(raw_name)
        if name in rewritten_names or name in guarded or not _is_sha256(expected):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_bundle"
            )
        guarded[name] = expected
    return guarded


def _assert_guarded_sha256(
    directory_fd: int,
    expected_sha256: Mapping[str, str],
) -> None:
    for name, expected in expected_sha256.items():
        try:
            actual = sha256(_read_regular_leaf(directory_fd, name))
        except OSError as exc:
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            ) from exc
        if actual != expected:
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )


def _assert_original_bundle(
    directory_fd: int,
    *,
    expected_names: tuple[str, ...],
    original_leaves: Mapping[str, os.stat_result | None],
    expected_existing_sha256: Mapping[str, str] | None,
) -> None:
    for name in expected_names:
        _assert_original_leaf(
            directory_fd,
            name=name,
            original=original_leaves[name],
            expected_sha256=(
                expected_existing_sha256.get(name)
                if expected_existing_sha256 is not None
                else None
            ),
        )


def _assert_original_leaf(
    directory_fd: int,
    *,
    name: str,
    original: os.stat_result | None,
    expected_sha256: str | None,
) -> None:
    current = _regular_leaf_status(directory_fd, name)
    if not _same_optional_snapshot(original, current):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    if expected_sha256 is not None:
        payload, observed = _read_regular_leaf_snapshot(directory_fd, name)
        if (
            not _same_optional_snapshot(original, observed)
            or sha256(payload) != expected_sha256
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )


def _assert_installed_bundle(
    directory_fd: int,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
    installed_names: Mapping[str, os.stat_result],
) -> None:
    for name in expected_names:
        try:
            payload, current = _read_regular_leaf_snapshot(directory_fd, name)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            ) from exc
        installed = installed_names.get(name)
        if (
            installed is None
            or not _same_optional_snapshot(installed, current)
            or payload != payloads[name]
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _assert_directory_path_identity(
    directory: Path,
    expected: os.stat_result,
) -> None:
    current = os.stat(directory, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or not _same_identity(current, expected):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:parent_identity"
        )


def _assert_namespace_identity(
    parent_fd: int,
    namespace: str,
    expected: os.stat_result,
) -> None:
    current = os.stat(namespace, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or not _same_identity(current, expected):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:namespace_identity"
        )


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_identity(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _same_optional_snapshot(
    left: os.stat_result | None,
    right: os.stat_result | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return (
        _same_identity(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _safe_leaf(value: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise RuntimeError("market_anomaly_completion_receipt_invalid:path")
    return value


def _require_mutation_support() -> None:
    if not all(
        (
            _OPEN_SUPPORTS_DIR_FD,
            _STAT_SUPPORTS_DIR_FD,
            _STAT_SUPPORTS_FOLLOW_SYMLINKS,
            _MKDIR_SUPPORTS_DIR_FD,
            _RENAME_SUPPORTS_DIR_FD,
        )
    ):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:descriptor_no_follow_unsupported"
        )


def _required_flag(name: str) -> int:
    value = getattr(os, name, None)
    if not isinstance(value, int):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:descriptor_no_follow_unsupported"
        )
    return value


__all__ = (
    "artifact_payloads",
    "namespace_identity",
    "sha256",
    "strict_jsonl",
    "write_artifacts_atomic",
)
