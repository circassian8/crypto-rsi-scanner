"""Descriptor-anchored I/O for historical outcome recovery application."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import fcntl
import os
from pathlib import Path
import stat
import time
from typing import Iterator

from . import market_no_send_io
from .market_no_send_campaign_guard import CAMPAIGN_LOCK_FILENAME
from .market_no_send_history_cache import LIVE_HISTORY_CACHE_NAMESPACE
from .market_no_send_models import MarketNoSendError
from .outcome_price_recovery_error import OutcomePriceRecoveryError


@dataclass(frozen=True)
class AnchoredRecoveryApplicationState:
    """Exact descriptors and identities held for one recovery application."""

    base: Path
    base_fd: int
    state_fd: int
    state_name: str
    base_identity: tuple[int, int]
    state_identity: tuple[int, int]
    lock_fd: int
    lock_identity: tuple[int, int]


def assert_application_state_identity(
    state: AnchoredRecoveryApplicationState,
) -> None:
    """Require the same named base, state directory, and root lock."""

    try:
        opened_base = os.fstat(state.base_fd)
        named_base = os.stat(state.base, follow_symlinks=False)
        opened_state = os.fstat(state.state_fd)
        named_state = os.stat(
            state.state_name,
            dir_fd=state.base_fd,
            follow_symlinks=False,
        )
        opened_lock = os.fstat(state.lock_fd)
        named_lock = os.stat(
            CAMPAIGN_LOCK_FILENAME,
            dir_fd=state.base_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_state_identity_changed"
        ) from exc
    if any((
        not stat.S_ISDIR(opened_base.st_mode),
        not stat.S_ISDIR(named_base.st_mode),
        _identity(opened_base) != state.base_identity,
        _identity(named_base) != state.base_identity,
        not stat.S_ISDIR(opened_state.st_mode),
        not stat.S_ISDIR(named_state.st_mode),
        _identity(opened_state) != state.state_identity,
        _identity(named_state) != state.state_identity,
        not stat.S_ISREG(opened_lock.st_mode),
        not stat.S_ISREG(named_lock.st_mode),
        opened_lock.st_nlink != 1,
        named_lock.st_nlink != 1,
        _identity(opened_lock) != state.lock_identity,
        _identity(named_lock) != state.lock_identity,
    )):
        raise OutcomePriceRecoveryError(
            "recovery_application_state_identity_changed"
        )


def read_application_state_required(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    reason: str,
) -> bytes:
    raw = read_application_state_optional(state, leaf, reason)
    if raw is None:
        raise OutcomePriceRecoveryError(f"{reason}_missing")
    return raw


def read_application_state_optional(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    reason: str,
) -> bytes | None:
    name = _safe_leaf(leaf)
    descriptor: int | None = None
    try:
        assert_application_state_identity(state)
        try:
            before = os.stat(
                name,
                dir_fd=state.state_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise OSError(errno.EINVAL, "application artifact is not regular")
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(name, flags, dir_fd=state.state_fd)
        opened = os.fstat(descriptor)
        if not _same_file(before, opened):
            raise OSError(errno.ESTALE, "application artifact changed")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read()
            completed = os.fstat(handle.fileno())
        after = os.stat(
            name,
            dir_fd=state.state_fd,
            follow_symlinks=False,
        )
        if (
            not _same_file(opened, completed)
            or not _same_file(completed, after)
            or len(raw) != completed.st_size
        ):
            raise OSError(errno.ESTALE, "application artifact changed")
        assert_application_state_identity(state)
        return raw
    except OutcomePriceRecoveryError:
        raise
    except OSError as exc:
        raise OutcomePriceRecoveryError(f"{reason}_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def write_application_state_atomic(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    data: bytes,
    reason: str,
) -> None:
    _write_application_state_atomic(
        state,
        leaf,
        data,
        reason,
        require_named_identity=True,
    )


def restore_application_state_atomic(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    data: bytes,
    reason: str,
) -> None:
    """Restore exact bytes through the held descriptor even after path drift."""

    _write_application_state_atomic(
        state,
        leaf,
        data,
        reason,
        require_named_identity=False,
    )


def _write_application_state_atomic(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    data: bytes,
    reason: str,
    *,
    require_named_identity: bool,
) -> None:
    name = _safe_leaf(leaf)
    temporary = _temporary_name(name, "tmp")
    descriptor: int | None = None
    temporary_exists = False
    try:
        _assert_write_state(state, require_named_identity=require_named_identity)
        before = _existing_regular(state.state_fd, name)
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        descriptor = os.open(temporary, flags, 0o600, dir_fd=state.state_fd)
        temporary_exists = True
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise OSError(errno.EINVAL, "application temporary is not regular")
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_write_state(state, require_named_identity=require_named_identity)
        current = _existing_regular(state.state_fd, name)
        if not _same_optional_file(before, current):
            raise OSError(errno.ESTALE, "application target changed")
        os.rename(
            temporary,
            name,
            src_dir_fd=state.state_fd,
            dst_dir_fd=state.state_fd,
        )
        temporary_exists = False
        written = os.stat(
            name,
            dir_fd=state.state_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(written.st_mode)
            or written.st_nlink != 1
            or written.st_size != len(data)
        ):
            raise OSError(errno.EIO, "application write verification failed")
        os.fsync(state.state_fd)
        _assert_write_state(state, require_named_identity=require_named_identity)
    except OutcomePriceRecoveryError:
        raise
    except OSError as exc:
        raise OutcomePriceRecoveryError(reason) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_exists:
            _remove_temporary(state.state_fd, temporary)


def write_application_state_immutable(
    state: AnchoredRecoveryApplicationState,
    leaf: str,
    data: bytes,
    reason: str,
) -> None:
    name = _safe_leaf(leaf)
    temporary = _temporary_name(name, "immutable")
    descriptor: int | None = None
    temporary_exists = False
    target_created = False
    try:
        assert_application_state_identity(state)
        if _existing_regular(state.state_fd, name) is not None:
            raise OSError(errno.EEXIST, "application receipt already exists")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        descriptor = os.open(temporary, flags, 0o600, dir_fd=state.state_fd)
        temporary_exists = True
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise OSError(errno.EINVAL, "application temporary is not regular")
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        assert_application_state_identity(state)
        os.link(
            temporary,
            name,
            src_dir_fd=state.state_fd,
            dst_dir_fd=state.state_fd,
            follow_symlinks=False,
        )
        target_created = True
        created = os.stat(name, dir_fd=state.state_fd, follow_symlinks=False)
        staged = os.stat(
            temporary,
            dir_fd=state.state_fd,
            follow_symlinks=False,
        )
        if not _same_linked_files(created, staged):
            raise OSError(errno.EIO, "application receipt identity mismatch")
        os.unlink(temporary, dir_fd=state.state_fd)
        temporary_exists = False
        final = os.stat(name, dir_fd=state.state_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(final.st_mode)
            or final.st_nlink != 1
            or final.st_size != len(data)
        ):
            raise OSError(errno.EIO, "application receipt verification failed")
        os.fsync(state.state_fd)
        assert_application_state_identity(state)
        target_created = False
    except OutcomePriceRecoveryError:
        raise
    except OSError as exc:
        raise OutcomePriceRecoveryError(reason) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_exists:
            _remove_temporary(state.state_fd, temporary)
        if target_created:
            _remove_temporary(state.state_fd, name)


@contextmanager
def locked_recovery_application_state(
    artifact_base_dir: str | Path,
) -> Iterator[AnchoredRecoveryApplicationState]:
    """Hold the existing campaign root lock and exact mutable state directory."""

    base = Path(artifact_base_dir).expanduser().absolute()
    state_dir = base / LIVE_HISTORY_CACHE_NAMESPACE
    lock_fd: int | None = None
    locked = False
    try:
        with market_no_send_io._open_verified_namespace_dir(state_dir) as anchored:  # noqa: SLF001
            base_fd, state_fd, state_name, state_info = anchored
            base_info = os.fstat(base_fd)
            named_base = os.stat(base, follow_symlinks=False)
            if (
                not stat.S_ISDIR(base_info.st_mode)
                or not stat.S_ISDIR(named_base.st_mode)
                or _identity(base_info) != _identity(named_base)
            ):
                raise OutcomePriceRecoveryError(
                    "recovery_application_state_identity_changed"
                )
            flags = os.O_RDWR | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            lock_fd = os.open(CAMPAIGN_LOCK_FILENAME, flags, dir_fd=base_fd)
            opened_lock = os.fstat(lock_fd)
            named_lock = os.stat(
                CAMPAIGN_LOCK_FILENAME,
                dir_fd=base_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(opened_lock.st_mode)
                or opened_lock.st_nlink != 1
                or not _same_identity(opened_lock, named_lock)
            ):
                raise OutcomePriceRecoveryError(
                    "recovery_application_campaign_lock_invalid"
                )
            _lock_nonblocking(lock_fd)
            locked = True
            state = AnchoredRecoveryApplicationState(
                base=base,
                base_fd=base_fd,
                state_fd=state_fd,
                state_name=state_name,
                base_identity=_identity(base_info),
                state_identity=_identity(state_info),
                lock_fd=lock_fd,
                lock_identity=_identity(opened_lock),
            )
            assert_application_state_identity(state)
            yield state
            assert_application_state_identity(state)
    except OutcomePriceRecoveryError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_campaign_lock_unavailable"
        ) from exc
    finally:
        if locked and lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        if lock_fd is not None:
            os.close(lock_fd)


def _lock_nonblocking(lock_fd: int) -> None:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            raise OutcomePriceRecoveryError(
                "recovery_application_campaign_busy"
            ) from exc
        raise


def _assert_write_state(
    state: AnchoredRecoveryApplicationState,
    *,
    require_named_identity: bool,
) -> None:
    if require_named_identity:
        assert_application_state_identity(state)
        return
    try:
        opened_base = os.fstat(state.base_fd)
        opened_state = os.fstat(state.state_fd)
        opened_lock = os.fstat(state.lock_fd)
    except OSError as exc:
        raise OutcomePriceRecoveryError(
            "recovery_application_rollback_failed"
        ) from exc
    if any((
        not stat.S_ISDIR(opened_base.st_mode),
        _identity(opened_base) != state.base_identity,
        not stat.S_ISDIR(opened_state.st_mode),
        _identity(opened_state) != state.state_identity,
        not stat.S_ISREG(opened_lock.st_mode),
        opened_lock.st_nlink != 1,
        _identity(opened_lock) != state.lock_identity,
    )):
        raise OutcomePriceRecoveryError(
            "recovery_application_rollback_failed"
        )


def _existing_regular(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        value = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise OSError(errno.EINVAL, "application artifact is not regular")
    return value


def _safe_leaf(value: str) -> str:
    name = str(value or "")
    if not name or name in {".", ".."} or Path(name).name != name:
        raise OutcomePriceRecoveryError("recovery_application_artifact_name_invalid")
    return name


def _temporary_name(name: str, suffix: str) -> str:
    return f".{name}.{os.getpid()}.{time.time_ns()}.{suffix}"


def _remove_temporary(directory_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except OSError:
        pass


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return _identity(left) == _identity(right)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_ISREG(left.st_mode)
        and stat.S_ISREG(right.st_mode)
        and left.st_nlink == 1
        and right.st_nlink == 1
        and _identity(left) == _identity(right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
    )


def _same_linked_files(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_ISREG(left.st_mode)
        and stat.S_ISREG(right.st_mode)
        and left.st_nlink == 2
        and right.st_nlink == 2
        and _identity(left) == _identity(right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
    )


def _same_optional_file(
    left: os.stat_result | None,
    right: os.stat_result | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return _same_file(left, right)


__all__ = (
    "AnchoredRecoveryApplicationState",
    "assert_application_state_identity",
    "locked_recovery_application_state",
    "read_application_state_optional",
    "read_application_state_required",
    "restore_application_state_atomic",
    "write_application_state_atomic",
    "write_application_state_immutable",
)
