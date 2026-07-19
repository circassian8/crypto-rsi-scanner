"""Descriptor-anchored I/O for guarded market no-send artifacts."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import stat
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping

from .market_no_send_models import MarketNoSendError


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks
_MKDIR_SUPPORTS_DIR_FD = os.mkdir in os.supports_dir_fd
_RENAME_SUPPORTS_DIR_FD = os.rename in os.supports_dir_fd
_IDENTITY_CHANGED_ERRNO = getattr(errno, "ESTALE", errno.EIO)
_RENAME_EXCL = 0x00000004
_RENAME_NOREPLACE = 0x00000001


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
    # Schema registration imports provenance helpers that depend on this
    # low-level I/O module.  Resolve the compatibility facade only when a row
    # is actually written so either side can be imported first.
    from ..artifacts import schema_v1

    lines = []
    for row in rows:
        stamped = schema_v1.stamp_artifact_row(row, path=path)
        lines.append(json.dumps(stamped, sort_keys=True, separators=(",", ":")))
    write_bytes_atomic(path, (("\n".join(lines) + "\n") if lines else "").encode("utf-8"))


def _safe_component(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or value in {".", ".."}
        or Path(value).name != value
    ):
        raise MarketNoSendError("market artifact target has an unsafe leaf name")
    return value


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


def _open_and_write_stage(
    namespace_fd: int,
    temporary: str,
    data: bytes,
) -> tuple[int, os.stat_result]:
    """Write exact bytes while retaining the inode-bound descriptor."""

    temporary = _safe_component(temporary)
    if not isinstance(data, bytes):
        raise MarketNoSendError("market artifact payload must be bytes")
    descriptor: int | None = None
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(temporary, flags, 0o600, dir_fd=namespace_fd)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size != 0
        ):
            raise OSError(errno.EINVAL, "market artifact stage is not private")
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "market artifact stage write stalled")
            offset += written
        os.fsync(descriptor)
        persisted = _read_exact_fd(descriptor, maximum_bytes=len(data))
        completed = os.fstat(descriptor)
        if (
            persisted != data
            or not stat.S_ISREG(completed.st_mode)
            or completed.st_nlink != 1
            or completed.st_size != len(data)
            or not _same_identity(opened, completed)
        ):
            raise OSError(errno.EIO, "market artifact stage verification failed")
        return descriptor, completed
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _assert_named_stage(
    namespace_fd: int,
    temporary: str,
    expected: os.stat_result,
) -> None:
    named = os.stat(
        _safe_component(temporary),
        dir_fd=namespace_fd,
        follow_symlinks=False,
    )
    if (
        not stat.S_ISREG(named.st_mode)
        or named.st_nlink != 1
        or not _same_file_snapshot(expected, named)
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "market artifact stage changed")


def _verify_published_stage(
    namespace_fd: int,
    leaf: str,
    descriptor: int,
    staged: os.stat_result,
    data: bytes,
) -> None:
    before = os.fstat(descriptor)
    persisted = _read_exact_fd(descriptor, maximum_bytes=len(data))
    completed = os.fstat(descriptor)
    named = os.stat(
        _safe_component(leaf),
        dir_fd=namespace_fd,
        follow_symlinks=False,
    )
    if (
        persisted != data
        or not _same_identity(staged, before)
        or not _same_file_snapshot(before, completed)
        or not _same_file_snapshot(completed, named)
        or not stat.S_ISREG(named.st_mode)
        or named.st_nlink != 1
        or named.st_size != len(data)
    ):
        raise OSError(
            _IDENTITY_CHANGED_ERRNO,
            "market artifact published identity mismatch",
        )


def _rename_noreplace(
    namespace_fd: int,
    source: str,
    destination: str,
) -> bool:
    """Use the host's atomic no-replace rename for one exact namespace."""

    source = _safe_component(source)
    destination = _safe_component(destination)
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
        raise MarketNoSendError(
            "native no-replace artifact creation is unsupported"
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
        raise MarketNoSendError(
            "native no-replace artifact creation is unsupported"
        )
    raise OSError(error, os.strerror(error))


def _rename_replace(namespace_fd: int, source: str, destination: str) -> None:
    os.rename(
        _safe_component(source),
        _safe_component(destination),
        src_dir_fd=namespace_fd,
        dst_dir_fd=namespace_fd,
    )


def write_bytes_immutable(path: Path, data: bytes) -> None:
    """Atomically create a regular leaf while refusing replacement.

    A fully written temporary remains open through one native no-replace
    rename and final byte/identity verification. Failed or raced stages are
    retained; cleanup never unlinks a mutable pathname.
    """

    _require_descriptor_directory_support(mutation=True)
    namespace_dir, leaf = _safe_leaf_name(path)
    temporary = f".{leaf}.{os.getpid()}.{time.time_ns()}.immutable"
    descriptor: int | None = None
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise MarketNoSendError("immutable artifact already exists")
            descriptor, staged = _open_and_write_stage(
                namespace_fd,
                temporary,
                data,
            )
            _assert_named_stage(namespace_fd, temporary, staged)
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            if not _rename_noreplace(namespace_fd, temporary, leaf):
                raise MarketNoSendError("immutable artifact already exists")
            _verify_published_stage(namespace_fd, leaf, descriptor, staged, data)
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            os.fsync(namespace_fd)
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("immutable artifact write failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Atomically replace a leaf while retaining an inode-bound stage fd."""

    _require_descriptor_directory_support(mutation=True)
    namespace_dir, leaf = _safe_leaf_name(path)
    temporary = f".{leaf}.{os.getpid()}.{time.time_ns()}.tmp"
    descriptor: int | None = None
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            base_fd, namespace_fd, namespace, namespace_identity = anchored
            try:
                existing = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            if existing is not None and not stat.S_ISREG(existing.st_mode):
                raise MarketNoSendError("market artifact target is not a regular file")
            descriptor, staged = _open_and_write_stage(
                namespace_fd,
                temporary,
                data,
            )
            _assert_named_stage(namespace_fd, temporary, staged)
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            try:
                current = os.stat(leaf, dir_fd=namespace_fd, follow_symlinks=False)
            except FileNotFoundError:
                current = None
            if current is not None and not stat.S_ISREG(current.st_mode):
                raise MarketNoSendError("market artifact target is not a regular file")
            _rename_replace(namespace_fd, temporary, leaf)
            _verify_published_stage(namespace_fd, leaf, descriptor, staged, data)
            _assert_namespace_identity(base_fd, namespace, namespace_identity)
            os.fsync(namespace_fd)
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
    return target.parent, _safe_component(target.name)


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
    "safe_existing_namespace_dir",
    "write_bytes_atomic",
    "write_json_atomic",
    "write_jsonl",
]
