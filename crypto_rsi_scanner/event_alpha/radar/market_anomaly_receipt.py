"""Descriptor-anchored byte binding for market-anomaly completion receipts."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks
_MKDIR_SUPPORTS_DIR_FD = os.mkdir in os.supports_dir_fd
_RENAME_SUPPORTS_DIR_FD = os.rename in os.supports_dir_fd
_UNLINK_SUPPORTS_DIR_FD = os.unlink in os.supports_dir_fd


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
    descriptor = _open_namespace(directory)
    payloads: dict[str, bytes] = {}
    try:
        status = os.fstat(descriptor)
        if (status.st_dev, status.st_ino) != namespace_identity:
            raise RuntimeError("market_anomaly_completion_receipt_invalid:namespace_identity")
        for supplied, filename in zip(paths, expected_names, strict=True):
            if Path(os.path.abspath(Path(supplied).expanduser())) != directory / filename:
                raise RuntimeError("market_anomaly_completion_receipt_invalid:path")
            artifact_fd = -1
            try:
                artifact_fd = os.open(
                    filename,
                    os.O_RDONLY
                    | getattr(os, "O_CLOEXEC", 0)
                    | _required_flag("O_NOFOLLOW"),
                    dir_fd=descriptor,
                )
                if not stat.S_ISREG(os.fstat(artifact_fd).st_mode):
                    raise RuntimeError(
                        "market_anomaly_completion_receipt_invalid:artifact_not_regular"
                    )
                with os.fdopen(artifact_fd, "rb") as handle:
                    artifact_fd = -1
                    payloads[filename] = handle.read()
            finally:
                if artifact_fd >= 0:
                    os.close(artifact_fd)
    except OSError as exc:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_unavailable"
        ) from exc
    finally:
        os.close(descriptor)
    return payloads


def write_artifacts_atomic(
    directory: Path,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
) -> tuple[int, int]:
    """Write one complete scanner bundle through one anchored namespace fd."""

    _require_mutation_support()
    if tuple(payloads) != expected_names or any(
        not isinstance(payloads.get(name), bytes) for name in expected_names
    ):
        raise RuntimeError("market_anomaly_completion_receipt_invalid:artifact_bundle")
    absolute = Path(os.path.abspath(Path(directory).expanduser()))
    namespace = _safe_leaf(absolute.name)
    parent_path = absolute.parent
    parent_fd = -1
    namespace_fd = -1
    temporary_names: set[str] = set()
    try:
        parent_fd, parent_status = _open_directory(parent_path)
        try:
            namespace_status = os.stat(
                namespace,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
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
        _assert_directory_path_identity(parent_path, parent_status)
        _assert_namespace_identity(parent_fd, namespace, opened_namespace)
        original_leaves = {
            name: _regular_leaf_status(namespace_fd, name)
            for name in expected_names
        }
        for index, name in enumerate(expected_names):
            _assert_directory_path_identity(parent_path, parent_status)
            _assert_namespace_identity(parent_fd, namespace, opened_namespace)
            temporary = f".{name}.{os.getpid()}.{time.time_ns()}.{index}.tmp"
            temporary_names.add(temporary)
            descriptor = os.open(
                temporary,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | _required_flag("O_NOFOLLOW")
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=namespace_fd,
            )
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise RuntimeError(
                        "market_anomaly_completion_receipt_invalid:temporary_not_regular"
                    )
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    handle.write(payloads[name])
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            _assert_directory_path_identity(parent_path, parent_status)
            _assert_namespace_identity(parent_fd, namespace, opened_namespace)
            current = _regular_leaf_status(namespace_fd, name)
            if not _same_optional_identity(original_leaves[name], current):
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:artifact_identity"
                )
            os.rename(
                temporary,
                name,
                src_dir_fd=namespace_fd,
                dst_dir_fd=namespace_fd,
            )
            temporary_names.remove(temporary)
            written = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
            if not stat.S_ISREG(written.st_mode):
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:artifact_not_regular"
                )
            _assert_directory_path_identity(parent_path, parent_status)
            _assert_namespace_identity(parent_fd, namespace, opened_namespace)
        os.fsync(namespace_fd)
        return opened_namespace.st_dev, opened_namespace.st_ino
    except RuntimeError:
        raise
    except OSError as exc:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_write"
        ) from exc
    finally:
        if namespace_fd >= 0:
            for temporary in temporary_names:
                try:
                    os.unlink(temporary, dir_fd=namespace_fd)
                except OSError:
                    pass
            os.close(namespace_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


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
    return status


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


def _same_optional_identity(
    left: os.stat_result | None,
    right: os.stat_result | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return _same_identity(left, right)


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
            _UNLINK_SUPPORTS_DIR_FD,
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
