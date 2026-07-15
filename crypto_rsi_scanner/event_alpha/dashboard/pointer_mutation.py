"""Descriptor-anchored serialization for dashboard pointer mutations."""

from __future__ import annotations

import errno
import fcntl
import os
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..operations.market_no_send_io import _open_verified_namespace_dir


CURRENT_POINTER_MUTATION_LOCK = ".radar_current_namespace.mutation.lock"


class _CurrentPointerMutationError(RuntimeError):
    """Raised when the shared pointer mutation lock cannot be trusted."""


@dataclass(frozen=True)
class _CurrentPointerMutation:
    """One pointer transaction anchored to the verified artifact-root fd."""

    root_fd: int

    def read_regular_bytes(
        self,
        leaf: str,
        *,
        missing_ok: bool = False,
    ) -> bytes | None:
        """Read one unchanged regular leaf without reopening the root path."""

        return _read_regular_bytes(self.root_fd, leaf, missing_ok=missing_ok)

    def write_bytes_atomic(self, leaf: str, data: bytes) -> None:
        """Atomically replace one regular leaf through the held root fd."""

        _write_bytes_atomic(self.root_fd, leaf, data)

    def remove_regular(self, leaf: str, *, missing_ok: bool = False) -> None:
        """Remove one regular leaf through the held root fd."""

        _remove_regular(self.root_fd, leaf, missing_ok=missing_ok)


CurrentPointerMutation = _CurrentPointerMutation
CurrentPointerMutationError = _CurrentPointerMutationError


def _read_regular_bytes(
    root_fd: int,
    leaf: str,
    *,
    missing_ok: bool,
) -> bytes | None:
    safe_leaf = _safe_leaf(leaf)
    descriptor: int | None = None
    try:
        try:
            before = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            if missing_ok:
                return None
            raise
        if not stat.S_ISREG(before.st_mode):
            raise CurrentPointerMutationError(
                "current pointer mutation target is not regular"
            )
        descriptor = os.open(
            safe_leaf,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=root_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise OSError(errno.ESTALE, "current pointer identity changed")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            data = handle.read()
            complete = os.fstat(handle.fileno())
        after = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(complete.st_mode)
            or not _same_snapshot(opened, complete)
            or not _same_snapshot(complete, after)
            or len(data) != complete.st_size
        ):
            raise OSError(errno.ESTALE, "current pointer changed during read")
        return data
    except CurrentPointerMutationError:
        raise
    except OSError as exc:
        raise CurrentPointerMutationError(
            "current pointer mutation target is unreadable"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_bytes_atomic(root_fd: int, leaf: str, data: bytes) -> None:
    safe_leaf = _safe_leaf(leaf)
    temporary = f".{safe_leaf}.{os.getpid()}.{time.time_ns()}.tmp"
    descriptor: int | None = None
    temporary_exists = False
    try:
        try:
            existing = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise CurrentPointerMutationError(
                "current pointer mutation target is not regular"
            )
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=root_fd,
        )
        temporary_exists = True
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "current pointer temporary is not regular")
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            current = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if existing is None and current is not None:
            raise OSError(errno.ESTALE, "current pointer appeared during write")
        if existing is not None and (
            current is None or not _same_snapshot(existing, current)
        ):
            raise OSError(errno.ESTALE, "current pointer changed during write")
        os.rename(temporary, safe_leaf, src_dir_fd=root_fd, dst_dir_fd=root_fd)
        temporary_exists = False
        written = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        if not stat.S_ISREG(written.st_mode):
            raise OSError(errno.EINVAL, "current pointer replacement is not regular")
        os.fsync(root_fd)
    except CurrentPointerMutationError:
        raise
    except OSError as exc:
        raise CurrentPointerMutationError(
            "current pointer mutation target could not be written"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_exists:
            try:
                os.unlink(temporary, dir_fd=root_fd)
            except FileNotFoundError:
                pass


def _remove_regular(root_fd: int, leaf: str, *, missing_ok: bool) -> None:
    safe_leaf = _safe_leaf(leaf)
    try:
        try:
            current = os.stat(safe_leaf, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            if missing_ok:
                return
            raise
        if not stat.S_ISREG(current.st_mode):
            raise CurrentPointerMutationError(
                "current pointer mutation target is not regular"
            )
        os.unlink(safe_leaf, dir_fd=root_fd)
        os.fsync(root_fd)
    except CurrentPointerMutationError:
        raise
    except OSError as exc:
        raise CurrentPointerMutationError(
            "current pointer mutation target could not be removed"
        ) from exc


@contextmanager
def current_pointer_mutation_lock(
    artifact_base: str | Path,
) -> Iterator[CurrentPointerMutation]:
    """Serialize every current-pointer writer through one verified root fd.

    The lock leaf is opened relative to the descriptor-verified artifact base,
    refuses symlinks, and is identity-checked again after ``flock``.  The held
    namespace descriptor also detects a base-directory swap before the caller
    can successfully finish its mutation.
    """

    root = Path(artifact_base).expanduser().absolute()
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(root) as anchored:
            _parent_fd, root_fd, _root_name, _root_identity = anchored
            flags = (
                os.O_RDWR
                | os.O_CREAT
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = os.open(
                CURRENT_POINTER_MUTATION_LOCK,
                flags,
                0o600,
                dir_fd=root_fd,
            )
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise CurrentPointerMutationError(
                    "current pointer mutation lock is not regular"
                )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            current = os.stat(
                CURRENT_POINTER_MUTATION_LOCK,
                dir_fd=root_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(current.st_mode)
                or (opened.st_dev, opened.st_ino)
                != (current.st_dev, current.st_ino)
            ):
                raise CurrentPointerMutationError(
                    "current pointer mutation lock identity changed"
                )
            yield CurrentPointerMutation(root_fd=root_fd)
            current = os.stat(
                CURRENT_POINTER_MUTATION_LOCK,
                dir_fd=root_fd,
                follow_symlinks=False,
            )
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise CurrentPointerMutationError(
                    "current pointer mutation lock identity changed"
                )
    except CurrentPointerMutationError:
        raise
    except OSError as exc:
        raise CurrentPointerMutationError(
            "current pointer mutation lock is unavailable"
        ) from exc
    finally:
        if descriptor is not None:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _safe_leaf(value: str) -> str:
    leaf = str(value or "")
    if not leaf or leaf in {".", ".."} or Path(leaf).name != leaf:
        raise CurrentPointerMutationError("current pointer mutation leaf is unsafe")
    return leaf


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return bool(
        _same_file(left, right)
        and left.st_mode == right.st_mode
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


__all__ = (
    "CURRENT_POINTER_MUTATION_LOCK",
    "CurrentPointerMutation",
    "CurrentPointerMutationError",
    "current_pointer_mutation_lock",
)
