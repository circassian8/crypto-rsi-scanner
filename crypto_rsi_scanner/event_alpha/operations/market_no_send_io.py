"""Descriptor-anchored I/O for guarded market no-send artifacts."""

from __future__ import annotations

import errno
import json
import os
import re
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import schema_v1
from .market_no_send_models import MarketNoSendError


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks
_MKDIR_SUPPORTS_DIR_FD = os.mkdir in os.supports_dir_fd
_RENAME_SUPPORTS_DIR_FD = os.rename in os.supports_dir_fd
_UNLINK_SUPPORTS_DIR_FD = os.unlink in os.supports_dir_fd
_IDENTITY_CHANGED_ERRNO = getattr(errno, "ESTALE", errno.EIO)


def ensure_safe_namespace_dir(path: Path) -> None:
    """Create or verify one namespace below an already-created artifact base."""

    _require_descriptor_directory_support(mutation=True)
    namespace_dir = Path(path).expanduser().absolute()
    namespace = _safe_namespace(namespace_dir.name)
    base_fd: int | None = None
    try:
        base_fd, _ = _open_verified_base_dir(namespace_dir.parent)
        try:
            info = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
        except FileNotFoundError:
            os.mkdir(namespace, 0o700, dir_fd=base_fd)
            info = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise MarketNoSendError("market artifact namespace is not a directory")
        with _open_verified_namespace_dir(namespace_dir):
            pass
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("market artifact namespace is unreadable") from exc
    finally:
        if base_fd is not None:
            os.close(base_fd)


def safe_existing_namespace_dir(base: Path, namespace: str) -> Path:
    path = Path(base).expanduser().absolute() / _safe_namespace(namespace)
    try:
        with _open_verified_namespace_dir(path):
            pass
    except OSError as exc:
        raise MarketNoSendError(
            "market artifact namespace is missing or unreadable"
        ) from exc
    return path


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_bytes_atomic(path, data)


def write_json_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    """Create one immutable JSON artifact without replacing an existing leaf."""

    data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_bytes_immutable(path, data)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    lines = []
    for row in rows:
        stamped = schema_v1.stamp_artifact_row(row, path=path)
        lines.append(json.dumps(stamped, sort_keys=True, separators=(",", ":")))
    write_bytes_atomic(path, (("\n".join(lines) + "\n") if lines else "").encode("utf-8"))


def write_bytes_immutable(path: Path, data: bytes) -> None:
    """Atomically create a regular leaf while refusing replacement.

    A fully written temporary file is hard-linked into the final name through
    the verified namespace descriptor.  The link operation is atomic and
    fails when the immutable target already exists.
    """

    _require_descriptor_directory_support(mutation=True)
    if os.link not in os.supports_dir_fd:
        raise MarketNoSendError("immutable artifact creation is unsupported")
    namespace_dir, leaf = _safe_leaf_name(path)
    temporary = f".{leaf}.{os.getpid()}.{time.time_ns()}.immutable"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor: int | None = None
    temporary_exists = False
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                descriptor = os.open(temporary, flags, 0o600, dir_fd=namespace_fd)
                temporary_exists = True
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode):
                    raise OSError(errno.EINVAL, "immutable artifact temporary is not regular")
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = None
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                _assert_namespace_identity(base_fd, namespace, namespace_identity)
                os.link(
                    temporary,
                    leaf,
                    src_dir_fd=namespace_fd,
                    dst_dir_fd=namespace_fd,
                    follow_symlinks=False,
                )
                created = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
                staged = os.stat(temporary, dir_fd=namespace_fd, follow_symlinks=False)
                if not stat.S_ISREG(created.st_mode) or not _same_file_snapshot(
                    created, staged
                ):
                    raise OSError(errno.EIO, "immutable artifact identity mismatch")
                os.unlink(temporary, dir_fd=namespace_fd)
                temporary_exists = False
                _assert_namespace_identity(base_fd, namespace, namespace_identity)
                os.fsync(namespace_fd)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                    descriptor = None
                if temporary_exists:
                    try:
                        os.unlink(temporary, dir_fd=namespace_fd)
                    except FileNotFoundError:
                        pass
                    temporary_exists = False
    except FileExistsError as exc:
        raise MarketNoSendError("immutable artifact already exists") from exc
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("immutable artifact write failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Atomically replace a regular leaf through a verified namespace fd."""

    _require_descriptor_directory_support(mutation=True)
    namespace_dir, leaf = _safe_leaf_name(path)
    temporary = f".{leaf}.{os.getpid()}.{time.time_ns()}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor: int | None = None
    temporary_exists = False
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                try:
                    existing = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
                except FileNotFoundError:
                    existing = None
                if existing is not None and not stat.S_ISREG(existing.st_mode):
                    raise MarketNoSendError("market artifact target is not a regular file")
                descriptor = os.open(temporary, flags, 0o600, dir_fd=namespace_fd)
                temporary_exists = True
                opened_temporary = os.fstat(descriptor)
                if not stat.S_ISREG(opened_temporary.st_mode):
                    raise OSError(errno.EINVAL, "market artifact temporary is not regular")
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = None
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                _assert_namespace_identity(base_fd, namespace, namespace_identity)
                try:
                    current = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
                except FileNotFoundError:
                    current = None
                if current is not None and not stat.S_ISREG(current.st_mode):
                    raise MarketNoSendError("market artifact target is not a regular file")
                os.rename(
                    temporary,
                    leaf,
                    src_dir_fd=namespace_fd,
                    dst_dir_fd=namespace_fd,
                )
                temporary_exists = False
                written = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
                if not stat.S_ISREG(written.st_mode):
                    raise OSError(errno.EINVAL, "market artifact replacement is not regular")
                _assert_namespace_identity(base_fd, namespace, namespace_identity)
                os.fsync(namespace_fd)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                    descriptor = None
                if temporary_exists:
                    try:
                        os.unlink(temporary, dir_fd=namespace_fd)
                    except FileNotFoundError:
                        pass
                    temporary_exists = False
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("market artifact write failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_regular_bytes(path: Path, *, missing_ok: bool = False) -> bytes | None:
    """Read an unchanged regular leaf through a verified namespace fd."""

    _require_descriptor_directory_support(mutation=False)
    namespace_dir, leaf = _safe_leaf_name(path)
    descriptor: int | None = None
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                before = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            except FileNotFoundError:
                if missing_ok:
                    return None
                raise
            if not stat.S_ISREG(before.st_mode):
                raise MarketNoSendError("market provenance artifact is not a regular file")
            flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(leaf, flags, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or not _same_file_snapshot(
                before, opened
            ):
                raise OSError(
                    _IDENTITY_CHANGED_ERRNO,
                    "market provenance artifact changed during validation",
                )
            handle = os.fdopen(descriptor, "rb")
            descriptor = None
            with handle:
                data = handle.read()
                read_complete = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(read_complete.st_mode)
                or not _same_file_snapshot(opened, read_complete)
                or len(data) != read_complete.st_size
            ):
                raise OSError(
                    _IDENTITY_CHANGED_ERRNO,
                    "market provenance artifact changed during read",
                )
            after = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            if not stat.S_ISREG(after.st_mode) or not _same_file_snapshot(
                read_complete, after
            ):
                raise OSError(
                    _IDENTITY_CHANGED_ERRNO,
                    "market provenance artifact changed during read",
                )
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            return data
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError(
            "market provenance artifact is missing or unreadable"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def remove_regular_artifact(path: Path, *, missing_ok: bool = False) -> None:
    """Remove one namespace-local regular leaf through a verified directory fd."""

    _require_descriptor_directory_support(mutation=True)
    namespace_dir, leaf = _safe_leaf_name(path)
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                before = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            except FileNotFoundError:
                if missing_ok:
                    return
                raise
            if not stat.S_ISREG(before.st_mode):
                raise MarketNoSendError("market artifact removal target is not regular")
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            os.unlink(leaf, dir_fd=namespace_fd)
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            os.fsync(namespace_fd)
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("market artifact removal failed") from exc


def parse_json_object_bytes(raw: bytes) -> dict[str, Any]:
    """Parse one exact JSON buffer while rejecting duplicate object keys."""

    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MarketNoSendError("market provenance artifact is invalid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise MarketNoSendError("market provenance artifact is not an object")
    return dict(parsed)


def parse_jsonl_bytes(raw: bytes) -> list[dict[str, Any]]:
    """Parse one exact JSONL buffer with strict object and key validation."""

    rows: list[dict[str, Any]] = []
    try:
        lines = raw.decode("utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            value = json.loads(line, object_pairs_hook=_unique_object)
            if not isinstance(value, Mapping):
                raise ValueError("JSONL row is not an object")
            rows.append(dict(value))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MarketNoSendError("market provenance artifact is invalid JSONL") from exc
    return rows


def read_json_object(path: Path) -> dict[str, Any]:
    raw = read_regular_bytes(path)
    if raw is None:
        raise MarketNoSendError("market provenance artifact is missing")
    return parse_json_object_bytes(raw)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = read_regular_bytes(path, missing_ok=True)
    if raw is None:
        return []
    return parse_jsonl_bytes(raw)


def _require_descriptor_directory_support(*, mutation: bool) -> None:
    supported = (
        _OPEN_SUPPORTS_DIR_FD
        and _STAT_SUPPORTS_DIR_FD
        and _STAT_SUPPORTS_FOLLOW_SYMLINKS
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
    )
    if mutation:
        supported = (
            supported
            and _MKDIR_SUPPORTS_DIR_FD
            and _RENAME_SUPPORTS_DIR_FD
            and _UNLINK_SUPPORTS_DIR_FD
        )
    if not supported:
        raise MarketNoSendError(
            "descriptor-relative no-follow market artifact access is unsupported"
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


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _open_verified_base_dir(base: Path) -> tuple[int, os.stat_result]:
    base_path = Path(base).expanduser().absolute()
    before = os.stat(base_path, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise OSError(errno.ENOTDIR, "market artifact base is not a directory")
    descriptor = os.open(base_path, _directory_open_flags())
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
            raise OSError(
                _IDENTITY_CHANGED_ERRNO,
                "market artifact base changed during validation",
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, opened


def _assert_namespace_identity(
    base_fd: int,
    namespace: str,
    expected: os.stat_result,
) -> None:
    current = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or not _same_identity(current, expected):
        raise OSError(
            _IDENTITY_CHANGED_ERRNO,
            "market artifact namespace changed during access",
        )


@contextmanager
def _open_verified_namespace_dir(path: Path):
    _require_descriptor_directory_support(mutation=False)
    namespace_dir = Path(path).expanduser().absolute()
    namespace = _safe_namespace(namespace_dir.name)
    base_fd: int | None = None
    namespace_fd: int | None = None
    try:
        base_fd, _ = _open_verified_base_dir(namespace_dir.parent)
        before = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise OSError(errno.ENOTDIR, "market artifact namespace is not a directory")
        namespace_fd = os.open(namespace, _directory_open_flags(), dir_fd=base_fd)
        opened = os.fstat(namespace_fd)
        if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
            raise OSError(
                _IDENTITY_CHANGED_ERRNO,
                "market artifact namespace changed during validation",
            )
        _assert_namespace_identity(base_fd, namespace, opened)
        yield base_fd, namespace_fd, namespace, opened
        _assert_namespace_identity(base_fd, namespace, opened)
    finally:
        if namespace_fd is not None:
            os.close(namespace_fd)
        if base_fd is not None:
            os.close(base_fd)


def _safe_namespace(value: str) -> str:
    namespace = str(value or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise MarketNoSendError("invalid market no-send artifact namespace")
    return namespace


def _safe_leaf_name(path: Path) -> tuple[Path, str]:
    target = Path(path).expanduser().absolute()
    leaf = target.name
    if not leaf or leaf in {".", ".."} or Path(leaf).name != leaf:
        raise MarketNoSendError("market artifact target has an unsafe leaf name")
    return target.parent, leaf


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


__all__ = [
    "ensure_safe_namespace_dir",
    "parse_json_object_bytes",
    "parse_jsonl_bytes",
    "read_json_object",
    "read_jsonl",
    "read_regular_bytes",
    "remove_regular_artifact",
    "safe_existing_namespace_dir",
    "write_bytes_atomic",
    "write_json_atomic",
    "write_jsonl",
]
