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
    expected_namespace_identity: tuple[int, int] | None = None,
    expected_existing_sha256: Mapping[str, str] | None = None,
    expected_guarded_sha256: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    """Write one complete scanner bundle through one anchored namespace fd.

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
    temporary_names: set[str] = set()
    backup_names: dict[str, str] = {}
    installation_intents: dict[str, os.stat_result] = {}
    installed_names: dict[str, os.stat_result] = {}
    original_leaves: dict[str, os.stat_result | None] = {}
    transaction_committed = False
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
        staged_names, staged_statuses = _stage_bundle(
            namespace_fd,
            payloads=payloads,
            expected_names=expected_names,
            temporary_names=temporary_names,
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
            staged_statuses=staged_statuses,
            temporary_names=temporary_names,
            backup_names=backup_names,
            installation_intents=installation_intents,
            installed_names=installed_names,
            parent_path=parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
        )
        transaction_committed = True
        _discard_backups(namespace_fd, expected_names, backup_names)
        return opened_namespace.st_dev, opened_namespace.st_ino
    except (OSError, RuntimeError) as exc:
        if namespace_fd >= 0 and not transaction_committed:
            try:
                _rollback_bundle(
                    namespace_fd,
                    expected_names=expected_names,
                    backup_names=backup_names,
                    installation_intents=installation_intents,
                    payloads=payloads,
                    original_leaves=original_leaves,
                    expected_existing_sha256=expected_existing_sha256,
                )
            except (OSError, RuntimeError) as rollback_exc:
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:artifact_rollback"
                ) from rollback_exc
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_write"
        ) from exc
    finally:
        if namespace_fd >= 0:
            _discard_temporaries(namespace_fd, temporary_names)
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
    temporary_names: set[str],
    parent_path: Path,
    parent_status: os.stat_result,
    parent_fd: int,
    namespace: str,
    opened_namespace: os.stat_result,
    guarded_sha256: Mapping[str, str],
) -> tuple[dict[str, str], dict[str, os.stat_result]]:
    staged_names: dict[str, str] = {}
    staged_statuses: dict[str, os.stat_result] = {}
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
        temporary_names.add(temporary)
        status = _stage_leaf(
            namespace_fd,
            temporary=temporary,
            payload=payloads[name],
        )
        staged_names[name] = temporary
        staged_statuses[name] = status
    return staged_names, staged_statuses


def _stage_leaf(
    namespace_fd: int,
    *,
    temporary: str,
    payload: bytes,
) -> os.stat_result:
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
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            return os.fstat(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _commit_staged_bundle(
    namespace_fd: int,
    *,
    payloads: Mapping[str, bytes],
    expected_names: tuple[str, ...],
    original_leaves: Mapping[str, os.stat_result | None],
    expected_existing_sha256: Mapping[str, str] | None,
    staged_names: Mapping[str, str],
    staged_statuses: Mapping[str, os.stat_result],
    temporary_names: set[str],
    backup_names: dict[str, str],
    installation_intents: dict[str, os.stat_result],
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
        if original_leaves[name] is not None:
            _backup_leaf(
                namespace_fd,
                name=name,
                index=index,
                backup_names=backup_names,
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
        installation_intents[name] = staged_statuses[name]
        installed_names[name] = _install_staged_leaf(
            namespace_fd,
            name=name,
            staged_name=staged_names[name],
        )
        temporary_names.remove(staged_names[name])
        _assert_transaction_context(
            parent_path,
            parent_status=parent_status,
            parent_fd=parent_fd,
            namespace=namespace,
            namespace_fd=namespace_fd,
            opened_namespace=opened_namespace,
            guarded_sha256=guarded_sha256,
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


def _backup_leaf(
    namespace_fd: int,
    *,
    name: str,
    index: int,
    backup_names: dict[str, str],
) -> None:
    backup = f".{name}.{os.getpid()}.{time.time_ns()}.{index}.rollback"
    if _leaf_status(namespace_fd, backup) is not None:
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    backup_names[name] = backup
    os.rename(
        name,
        backup,
        src_dir_fd=namespace_fd,
        dst_dir_fd=namespace_fd,
    )


def _install_staged_leaf(
    namespace_fd: int,
    *,
    name: str,
    staged_name: str,
) -> os.stat_result:
    os.rename(
        staged_name,
        name,
        src_dir_fd=namespace_fd,
        dst_dir_fd=namespace_fd,
    )
    written = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
    if not stat.S_ISREG(written.st_mode):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_not_regular"
        )
    return written


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


def _discard_backups(
    namespace_fd: int,
    expected_names: tuple[str, ...],
    backup_names: dict[str, str],
) -> None:
    for name in expected_names:
        backup = backup_names.pop(name, None)
        if backup is None:
            continue
        try:
            os.unlink(backup, dir_fd=namespace_fd)
        except OSError:
            # The replacement is fully validated and durable; cleanup cannot
            # make the old public bundle authoritative again.
            pass
    try:
        os.fsync(namespace_fd)
    except OSError:
        pass


def _discard_temporaries(namespace_fd: int, temporary_names: set[str]) -> None:
    for temporary in temporary_names:
        try:
            os.unlink(temporary, dir_fd=namespace_fd)
        except OSError:
            pass


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


def _read_regular_leaf(directory_fd: int, name: str) -> bytes:
    name = _safe_leaf(name)
    descriptor = os.open(
        name,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | _required_flag("O_NOFOLLOW"),
        dir_fd=directory_fd,
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_not_regular"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read()
    finally:
        if descriptor >= 0:
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
    if expected_sha256 is not None and (
        sha256(_read_regular_leaf(directory_fd, name)) != expected_sha256
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
        current = _regular_leaf_status(directory_fd, name)
        installed = installed_names.get(name)
        if (
            current is None
            or installed is None
            or not _same_optional_snapshot(installed, current)
            or sha256(_read_regular_leaf(directory_fd, name))
            != sha256(payloads[name])
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )


def _rollback_bundle(
    directory_fd: int,
    *,
    expected_names: tuple[str, ...],
    backup_names: dict[str, str],
    installation_intents: Mapping[str, os.stat_result],
    payloads: Mapping[str, bytes],
    original_leaves: Mapping[str, os.stat_result | None],
    expected_existing_sha256: Mapping[str, str] | None,
) -> None:
    for name in reversed(expected_names):
        backup = backup_names.pop(name, None)
        if backup is not None:
            backup_status = _regular_leaf_status(directory_fd, backup)
            original = original_leaves.get(name)
            expected_sha256 = (
                expected_existing_sha256.get(name)
                if expected_existing_sha256 is not None
                else None
            )
            if backup_status is None:
                _assert_original_leaf(
                    directory_fd,
                    name=name,
                    original=original,
                    expected_sha256=expected_sha256,
                )
                continue
            if original is None or not _same_rename_preserved(
                original,
                backup_status,
            ):
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:artifact_identity"
                )
            if expected_sha256 is not None and (
                sha256(_read_regular_leaf(directory_fd, backup)) != expected_sha256
            ):
                raise RuntimeError(
                    "market_anomaly_completion_receipt_invalid:artifact_identity"
                )
            os.rename(
                backup,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            continue
        intended = installation_intents.get(name)
        if intended is None:
            continue
        current = _regular_leaf_status(directory_fd, name)
        if current is None:
            continue
        if (
            not _same_identity(intended, current)
            or intended.st_size != current.st_size
            or intended.st_mtime_ns != current.st_mtime_ns
            or sha256(_read_regular_leaf(directory_fd, name))
            != sha256(payloads[name])
        ):
            raise RuntimeError(
                "market_anomaly_completion_receipt_invalid:artifact_identity"
            )
        os.unlink(name, dir_fd=directory_fd)
    os.fsync(directory_fd)


def _leaf_status(directory_fd: int, name: str) -> os.stat_result | None:
    name = _safe_leaf(name)
    try:
        return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


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


def _same_rename_preserved(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_identity(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
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
